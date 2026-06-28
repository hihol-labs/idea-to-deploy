#!/usr/bin/env python3
"""
PostToolUse hook — cost/token tracking with a two-stage budget gate.

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

v1.18.0: Adaptation from GSD v2 cost tracking (soft warn).
v1.30.0: Hard-ceiling ASK gate (omnigent cost_budget port).

Reads JSON on stdin: {"tool_name": "...", "tool_input": {...}, "response": "..."}
"""
from __future__ import annotations

import json
import os
import sys
import time

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

# Env overrides — let a project tune the ceiling without editing the hook.
# ITD_COST_CEILING_TOKENS (int) and ITD_COST_PER_1M_USD (float).
try:
    BUDGET_CEILING_TOKENS = int(os.environ.get("ITD_COST_CEILING_TOKENS", BUDGET_CEILING_TOKENS))
except Exception:
    pass
try:
    COST_PER_1M_TOKENS = float(os.environ.get("ITD_COST_PER_1M_USD", COST_PER_1M_TOKENS))
except Exception:
    pass


def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def ledger_file() -> str:
    return f"/tmp/claude-cost-{session_id()}.json"


def read_ledger() -> dict:
    try:
        with open(ledger_file()) as f:
            return json.load(f)
    except Exception:
        return {
            "session_start": time.time(),
            "total_tokens": 0,
            "total_calls": 0,
            "by_tool": {},
            "warnings_sent": 0,
            "hard_fired_at_tokens": 0,
        }


def write_ledger(ledger: dict) -> None:
    try:
        with open(ledger_file(), "w") as f:
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


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = (payload or {}).get("tool_name") or "default"

    ledger = read_ledger()
    tokens = TOKEN_ESTIMATES.get(tool, TOKEN_ESTIMATES["default"])

    ledger["total_tokens"] = ledger.get("total_tokens", 0) + tokens
    ledger["total_calls"] = ledger.get("total_calls", 0) + 1

    by_tool = ledger.get("by_tool", {})
    if tool not in by_tool:
        by_tool[tool] = {"calls": 0, "tokens": 0}
    by_tool[tool]["calls"] += 1
    by_tool[tool]["tokens"] += tokens
    ledger["by_tool"] = by_tool

    total = ledger["total_tokens"]
    cost_usd = (total / 1_000_000) * COST_PER_1M_TOKENS
    pct = int((total / BUDGET_CEILING_TOKENS) * 100) if BUDGET_CEILING_TOKENS else 0

    # Ceiling of 0 (or negative) means "disable the budget gate" — keep tracking
    # the ledger for visibility, but never warn or ASK.
    if BUDGET_CEILING_TOKENS <= 0:
        write_ledger(ledger)
        return 0

    # --- HARD stage: ASK at/above 100%, re-fire every +HARD_REFIRE_TOKENS ---
    hard_fired_at = ledger.get("hard_fired_at_tokens", 0)
    hard_due = total >= BUDGET_CEILING_TOKENS * HARD_THRESHOLD and (
        hard_fired_at == 0 or (total - hard_fired_at) >= HARD_REFIRE_TOKENS
    )

    if hard_due:
        ledger["hard_fired_at_tokens"] = total
        write_ledger(ledger)
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
            f"Only proceed if the user approves continuing. Ledger: `cat {ledger_file()}`"
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
        write_ledger(ledger)
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
            f"Ledger: `cat {ledger_file()}`"
        )
        emit(context)
        return 0

    write_ledger(ledger)
    return 0


if __name__ == "__main__":
    sys.exit(main())
