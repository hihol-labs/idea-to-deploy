#!/usr/bin/env python3
"""
PostToolUse hook — cost/token tracking with a two-stage budget gate
plus a context-usage sensor for the /handoff 60% rule.

Tracks tool call counts per skill/task, estimates token usage, and gates on a
budget ceiling in two stages:

  • SOFT (>= 80% of ceiling) — warn-only reminder via additionalContext
    (visibility, suggests /session-save). Does not interrupt.
  • HARD (>= 100% of ceiling) — escalates to an ASK: injects a forceful
    instruction telling the model to STOP and get explicit user approval
    before continuing. Re-fires every +500k tokens so a runaway loop keeps
    surfacing instead of silently burning budget.

Inspired by GSD v2 (per-unit cost ledger) and by the omnigent `cost_budget`
policy (soft ASK / hard limit) — ported as an OUTCOME (don't overspend
unnoticed), not as omnigent's server-side policy engine. A plugin hook cannot
literally pause the agent loop, so the HARD stage realizes "limit" as a
high-priority ASK the model must surface to the user.

Writes a ledger file reviewable with `cat /tmp/claude-cost-<session>.json`.

Ledger key (v1.71.0, retro 2026-07-09 P1 — боевой инцидент): the key prefers
`payload["session_id"]` — Claude Code puts it in the stdin JSON of every hook
event, and it is STABLE per agent (main loop and each subagent get their own).
The v1.47.0 day-anchor fallback pooled ALL sessions AND parallel subagents of
the day into one ledger: in the amnesia-lab experiment a subagent with ~183k
own tokens was halted by a "2,000,700 tokens (100% of ceiling)" HARD ASK fed
by its neighbours. Same fix class as v1.69.1 (crash-checkpoint keyed by
payload sid). Fallback order: payload sid → CLAUDE_SESSION_ID env → shared
per-day anchor (aggregate visibility) → "default".

Context sensor (v1.71.0, retro 2026-07-09 P2 — partial adopt of ledger F-18):
estimates context-window usage from the transcript file size
(`payload["transcript_path"]`, bytes/4 ≈ tokens) and injects a ONE-TIME hint
at >= ITD_CONTEXT_HANDOFF_PCT (default 60%) of ITD_CONTEXT_WINDOW_TOKENS
(default 200k): «подготовь /handoff». Best-effort TRANSPORT of the 60% rule
codified in v1.70.0 (skills/handoff, global-claude-md) — the text rule stays
the vendor-neutral contract; if this sensor or transcript_path disappears,
nothing breaks. Known limitation: after an auto-compaction the transcript
keeps growing while the live context resets, so the estimate overshoots —
acceptable, because the hint's job is the FIRST approach to 60%, before the
first compaction destroys handoff material.

v1.18.0: Adaptation from GSD v2 cost tracking (soft warn).
v1.30.0: Hard-ceiling ASK gate (omnigent cost_budget port).
v1.47.0: day-anchor session key + 14-day ledger rotation (retro 2026-07-04 #6).
v1.71.0: ledger keyed by payload session_id (parallel-agents false ceiling) +
         transcript-size context sensor for the /handoff 60% rule.

Reads JSON on stdin: {"session_id": "...", "transcript_path": "...",
"tool_name": "...", "tool_input": {...}, "response": "..."}
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time

# Legacy Windows console (cp1252/cp866) must not crash the hook when emitting
# Cyrillic/emoji advisories — same bug class fixed in pre-flight-check v1.68.1.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Rough token estimates per tool call type (conservative)
TOKEN_ESTIMATES = {
    "Bash": 800,
    "Read": 2000,
    "Write": 1500,
    "Edit": 1000,
    "Grep": 600,
    "Glob": 300,
    "Agent": 15000,  # subagent calls are expensive
    "Skill": 500,
    "default": 500,
}

# Approximate cost per 1M tokens (input+output blended, Opus)
COST_PER_1M_TOKENS = 30.0  # USD, rough Opus estimate
BUDGET_CEILING_TOKENS = 2_000_000  # 2M tokens = ~$60
WARNING_THRESHOLD = 0.8  # SOFT: warn at 80% of ceiling
HARD_THRESHOLD = 1.0     # HARD: ASK at 100% of ceiling
HARD_REFIRE_TOKENS = 500_000  # re-fire the HARD ASK every +500k tokens

# Context sensor defaults (v1.71.0). Window is the model context in tokens;
# transcript bytes/4 is a deliberately rough pre-compaction proxy.
CONTEXT_WINDOW_TOKENS = 200_000
CONTEXT_HANDOFF_PCT = 60
CONTEXT_BYTES_PER_TOKEN = 4

# Env overrides — let a project tune the ceiling without editing the hook.
# ITD_COST_CEILING_TOKENS (int) and ITD_COST_PER_1M_USD (float).
# ITD_CONTEXT_WINDOW_TOKENS (int), ITD_CONTEXT_HANDOFF_PCT (int; 0 = off).
try:
    BUDGET_CEILING_TOKENS = int(os.environ.get("ITD_COST_CEILING_TOKENS", BUDGET_CEILING_TOKENS))
except Exception:
    pass
try:
    COST_PER_1M_TOKENS = float(os.environ.get("ITD_COST_PER_1M_USD", COST_PER_1M_TOKENS))
except Exception:
    pass
try:
    CONTEXT_WINDOW_TOKENS = int(os.environ.get("ITD_CONTEXT_WINDOW_TOKENS", CONTEXT_WINDOW_TOKENS))
except Exception:
    pass
try:
    CONTEXT_HANDOFF_PCT = int(os.environ.get("ITD_CONTEXT_HANDOFF_PCT", CONTEXT_HANDOFF_PCT))
except Exception:
    pass


def session_id(payload: dict | None = None) -> str:
    # v1.71.0 (retro 2026-07-09 P1): payload sid first — stable per agent, so
    # parallel subagents stop pooling into one ledger and inheriting a false
    # HARD ceiling from their neighbours (amnesia-lab live incident).
    sid = str((payload or {}).get("session_id") or "").strip()
    if sid:
        return sid
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    # v1.47.0 (retro 2026-07-04, finding #6): getppid() differs on EVERY hook
    # spawn (fresh python per call, especially on Windows) → a new tiny ledger
    # per tool call: the scan found 500 ledgers averaging ~1.3k tokens, i.e.
    # cost was never accumulated per session at all. Reuse the shared per-day
    # anchor written by check-skills.sh / check-tool-skill.sh so all spawns of
    # a working session aggregate into ONE ledger (env var still wins for true
    # per-session isolation).
    try:
        anchor = os.path.join(tempfile.gettempdir(), "claude-skill-session-anchor")
        try:
            with open(anchor) as f:
                tok = f.read().strip()
            if tok:
                return tok
        except Exception:
            pass
        tok = time.strftime("day%Y%m%d")
        with open(anchor, "w") as f:
            f.write(tok)
        return tok
    except Exception:
        return "default"


def ledger_file(sid: str) -> str:
    # Keep the filename filesystem-safe even if a sid ever contains separators.
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in sid)[:80]
    return os.path.join(tempfile.gettempdir(), f"claude-cost-{safe}.json")


ROTATE_AFTER_DAYS = 14
ROTATE_MARKER = "claude-cost-rotate.marker"


def rotate_old_ledgers() -> None:
    """Delete cost ledgers older than ROTATE_AFTER_DAYS (retro #6: 500 stale
    files had accumulated). Runs at most once a day (marker file), best-effort,
    never raises, never touches today's ledger."""
    tmp = tempfile.gettempdir()
    marker = os.path.join(tmp, ROTATE_MARKER)
    now = time.time()
    try:
        if now - os.path.getmtime(marker) < 86400:
            return
    except Exception:
        pass
    try:
        with open(marker, "w") as f:
            f.write(str(now))
    except Exception:
        return
    import glob
    cutoff = now - ROTATE_AFTER_DAYS * 86400
    for path in glob.glob(os.path.join(tmp, "claude-cost-*.json")):
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
        except Exception:
            continue


# Trade-off (v1.71.0, review finding): read-modify-write below is NOT atomic.
# Parallel tool calls of ONE agent share a session_id and can race, losing an
# increment or two. Accepted: the ledger holds rough per-tool ESTIMATES for a
# best-effort ASK, not billing — an advisory lock is not worth the complexity.
def read_ledger(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {
            "session_start": time.time(),
            "total_tokens": 0,
            "total_calls": 0,
            "by_tool": {},
            "warnings_sent": 0,
            "hard_fired_at_tokens": 0,
            "context_hint_fired": False,
        }


def write_ledger(path: str, ledger: dict) -> None:
    try:
        with open(path, "w") as f:
            json.dump(ledger, f, indent=2)
    except Exception:
        pass


def emit(context: str) -> None:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


def context_usage_hint(payload: dict, ledger: dict) -> str | None:
    """v1.71.0 (retro 2026-07-09 P2): one-time /handoff hint at ~60% of the
    context window, estimated from transcript file size. Best-effort transport
    of the v1.70.0 text rule — returns None on any doubt."""
    if CONTEXT_HANDOFF_PCT <= 0 or CONTEXT_WINDOW_TOKENS <= 0:
        return None
    if ledger.get("context_hint_fired"):
        return None
    tp = str(payload.get("transcript_path") or "")
    if not tp:
        return None
    try:
        if not os.path.isfile(tp):  # directory / missing → no estimate
            return None
        est_tokens = os.path.getsize(tp) // CONTEXT_BYTES_PER_TOKEN
    except Exception:
        return None
    pct = int(est_tokens * 100 / CONTEXT_WINDOW_TOKENS)
    if pct < CONTEXT_HANDOFF_PCT:
        return None
    ledger["context_hint_fired"] = True
    return (
        f"[CONTEXT SENSOR — ~{pct}% окна (оценка по транскрипту)]\n"
        f"Порог {CONTEXT_HANDOFF_PCT}% достигнут (правило v1.70.0). Если конец работы в этой "
        f"сессии НЕ виден — подготовь передачу СЕЙЧАС, до авто-компакции:\n"
        f"- /handoff (компактный пакет для следующего актора), или\n"
        f"- /session-save (веха для будущего «я») + свежий PROGRESS view.\n"
        f"После компакции детали для пакета уже потеряны. Оценка грубая "
        f"(байты транскрипта/4; после первой компакции завышает) — это транспорт "
        f"текстового правила, не гейт."
    )


def main() -> int:
    # PostToolUse hook: NEVER crash, NEVER block — any failure degrades to 0.
    try:
        return _main()
    except Exception:
        return 0


def _main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        payload = {}

    tool = payload.get("tool_name") or "default"

    rotate_old_ledgers()  # at most once a day, best-effort (retro #6)
    lpath = ledger_file(session_id(payload))
    ledger = read_ledger(lpath)
    tokens = TOKEN_ESTIMATES.get(tool, TOKEN_ESTIMATES["default"])

    ledger["total_tokens"] = ledger.get("total_tokens", 0) + tokens
    ledger["total_calls"] = ledger.get("total_calls", 0) + 1

    by_tool = ledger.get("by_tool", {})
    if tool not in by_tool:
        by_tool[tool] = {"calls": 0, "tokens": 0}
    by_tool[tool]["calls"] += 1
    by_tool[tool]["tokens"] += tokens
    ledger["by_tool"] = by_tool

    # v1.83.0 (retro 2026-07-11, компонент «Модель»): атрибуция стоимости
    # per-agent РЕАЛЬНЫМИ токенами. Task/Agent-результат несёт usage
    # (`<subagent_tokens>N</subagent_tokens>` или поле subagent_tokens) — это
    # связывает model-routing решения с фактической ценой; агрегат виден в
    # /retro-скане. Оценка by_tool при этом не меняется (совместимость).
    if tool in ("Task", "Agent"):
        try:
            ti = payload.get("tool_input") or {}
            agent_type = str(ti.get("subagent_type") or "general-purpose")
            model = str(ti.get("model") or "inherit")
            resp = payload.get("tool_response")
            resp_text = resp if isinstance(resp, str) else json.dumps(resp or {})
            m = re.search(r"subagent_tokens[>\"':\s]+(\d+)", resp_text)
            real = int(m.group(1)) if m else 0
            by_agent = ledger.get("by_agent", {})
            key = f"{agent_type}({model})"
            if key not in by_agent:
                by_agent[key] = {"calls": 0, "tokens": 0}
            by_agent[key]["calls"] += 1
            by_agent[key]["tokens"] += real
            ledger["by_agent"] = by_agent
            if real:
                ledger["total_tokens"] += real  # реальные токены субагента поверх оценки
        except Exception:
            pass

    total = ledger["total_tokens"]
    cost_usd = (total / 1_000_000) * COST_PER_1M_TOKENS
    pct = int((total / BUDGET_CEILING_TOKENS) * 100) if BUDGET_CEILING_TOKENS else 0

    # Ceiling of 0 (or negative) means "disable the budget gate" — keep tracking
    # the ledger for visibility, but never warn or ASK. The context sensor is
    # independent of the budget gate and still runs.
    if BUDGET_CEILING_TOKENS <= 0:
        hint = context_usage_hint(payload, ledger)
        write_ledger(lpath, ledger)
        if hint:
            emit(hint)
        return 0

    # --- HARD stage: ASK at/above 100%, re-fire every +HARD_REFIRE_TOKENS ---
    hard_fired_at = ledger.get("hard_fired_at_tokens", 0)
    hard_due = total >= BUDGET_CEILING_TOKENS * HARD_THRESHOLD and (
        hard_fired_at == 0 or (total - hard_fired_at) >= HARD_REFIRE_TOKENS
    )

    if hard_due:
        ledger["hard_fired_at_tokens"] = total
        write_ledger(lpath, ledger)
        context = (
            f"[COST BUDGET — HARD CEILING REACHED]\n"
            f"🛑 Session cost estimate: ~${cost_usd:.2f} "
            f"({total:,} tokens, {pct}% of the {BUDGET_CEILING_TOKENS:,}-token ceiling).\n"
            f"📊 Tool calls: {ledger['total_calls']}\n\n"
            f"STOP and get explicit user approval before continuing this session.\n"
            f"This estimate has crossed the budget ceiling — a runaway loop or an "
            f"over-scoped task can burn real money unnoticed. Before any further "
            f"tool calls you MUST:\n"
            f"1. Tell the user the current estimate and what remains to be done.\n"
            f"2. Ask explicitly whether to continue, raise the ceiling "
            f"(ITD_COST_CEILING_TOKENS), or stop.\n"
            f"3. Run /session-save to checkpoint progress before deciding.\n\n"
            f"Only proceed if the user approves continuing. Ledger: `cat {lpath}`"
        )
        emit(context)
        return 0

    # --- SOFT stage: warn-only between 80% and 100% (up to 3 times) ---
    should_warn = (
        total >= BUDGET_CEILING_TOKENS * WARNING_THRESHOLD
        and total < BUDGET_CEILING_TOKENS * HARD_THRESHOLD
        and ledger.get("warnings_sent", 0) < 3
    )

    if should_warn:
        ledger["warnings_sent"] = ledger.get("warnings_sent", 0) + 1
        write_ledger(lpath, ledger)
        context = (
            f"[COST TRACKER — approaching budget ceiling]\n"
            f"💰 Session cost estimate: ~${cost_usd:.2f} "
            f"({total:,} tokens, {pct}% of ceiling)\n"
            f"📊 Tool calls: {ledger['total_calls']}\n\n"
            f"⚠️ Approaching budget ceiling ({pct}% of {BUDGET_CEILING_TOKENS:,} tokens).\n"
            f"Consider:\n"
            f"- Completing current task and saving session\n"
            f"- Using /session-save to checkpoint progress\n"
            f"- Starting a fresh session for remaining work\n\n"
            f"Ledger: `cat {lpath}`"
        )
        emit(context)
        return 0

    # --- Context sensor (independent of budget; one hint per ledger) ---
    hint = context_usage_hint(payload, ledger)
    write_ledger(lpath, ledger)
    if hint:
        emit(hint)
    return 0


if __name__ == "__main__":
    sys.exit(main())
