#!/usr/bin/env python3
"""
PreToolUse hook — fires before Bash/Edit/Write/NotebookEdit.
Reminds Claude to verify a skill from Idea-to-Deploy doesn't fit before
raw tool calls.

v1.19.0 change: **enforcement mode** (Gap #4 from ROADMAP_v1.19.md).

Previous behavior (v1.5.0–v1.18.1):
  - Rate-limited reminder every 60s, always exit 0, never blocks.
  - Claude could (and did) ignore reminders indefinitely.

New behavior (v1.19.0):
  - Still rate-limited to 60s between reminders.
  - Tracks consecutive ignored reminders in a state file.
  - After MAX_IGNORES (3) consecutive reminders without a Skill call,
    the hook BLOCKS the next tool call (returns decision: "block")
    with a message requiring Claude to either:
      a) Call a Skill first, OR
      b) Justify the bypass by including "SKILL_BYPASS: <reason>"
         in the model's response text before retrying.
  - Skill tool calls reset the ignore counter to 0.
  - The ignore counter also resets when Claude provides a bypass
    justification (detected by checking tool_input for SKILL_BYPASS marker).

v1.24.0 change: **skill-active grace window** (infra fix #2).

  Problem fixed: PreToolUse/PostToolUse hooks do NOT fire for the Skill tool
  (confirmed: the harness does not emit hook events for Skill invocations), so
  the `tool == "Skill"` reset branch below was dead code in production. The
  ignore counter therefore accumulated *through* a legitimately-active skill
  and then falsely blocked its flow — fatally so for Edit/Write/NotebookEdit,
  which carry no `description` field and thus cannot supply an in-band
  SKILL_BYPASS to escape the block (a true dead-end).

  Fix: a per-session "skill-active" sentinel grants a grace window.
    1. The sentinel is written by `check-skills.sh` (a UserPromptSubmit hook,
       which DOES fire reliably) whenever the user's prompt matches a skill
       trigger — i.e. methodology context is established for this task. It is
       ALSO written here whenever a SKILL_BYPASS is accepted, so one bypass
       opens a grace window instead of resetting a single call.
    2. On any Bash/Edit/Write/NotebookEdit call, a *fresh* sentinel
       (age < SKILL_ACTIVE_TTL_SECONDS) is treated as "a skill is running":
       the counter resets and the call is allowed silently. The TTL bounds
       the grace so enforcement resumes once the skill window lapses — this is
       the never-block-FOREVER guard (regression-tested).
    3. `Skill` is also added to the PreToolUse matcher for forward-compat: if
       a future harness starts emitting Skill hook events, the reset+sentinel
       branch below activates automatically. Harmless no-op until then.

State files (per-session):
  /tmp/claude-skill-check-{session}.state    — last reminder timestamp
  /tmp/claude-skill-ignores-{session}.state  — ignore count (int)
  /tmp/claude-skill-active-{session}.state    — last Skill-call timestamp (grace)

Session id: CLAUDE_SESSION_ID env var → parent pid → "default".

Reads JSON on stdin: {"tool_name": "...", "tool_input": {...}}
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

REMIND_WINDOW_SECONDS = 60
MAX_IGNORES = 3  # block after this many consecutive ignored reminders
# A Skill call grants this many seconds of grace before enforcement resumes.
# Bounded on purpose: an expired sentinel must NOT suppress the block, otherwise
# one early skill would disable enforcement for the whole session (never-block).
SKILL_ACTIVE_TTL_SECONDS = 900  # 15 minutes


# NOTE: this function MUST stay byte-for-byte behaviourally identical to the
# copy in hooks/check-skills.sh — both derive the per-session sentinel path, and
# any divergence silently breaks the skill-active grace window. The drift-guard
# in tests/verify_skill_enforcement.py asserts the two bodies match.
def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    # getppid() differs on every hook spawn (a fresh python process per call,
    # especially on Windows) -> the ignore counter never accumulated past 1 and
    # the gate never blocked. Anchor to a single per-day file so all hook spawns
    # in a working session share one counter. CLAUDE_SESSION_ID, when set, still
    # wins for true per-session isolation.
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


def state_paths() -> tuple[str, str]:
    """Return (reminder_state_path, ignore_count_path)."""
    sid = session_id()
    tmp = tempfile.gettempdir()
    return (
        os.path.join(tmp, f"claude-skill-check-{sid}.state"),
        os.path.join(tmp, f"claude-skill-ignores-{sid}.state"),
    )


def skill_active_path() -> str:
    """Per-session sentinel stamped with the timestamp of the last Skill call."""
    return os.path.join(
        tempfile.gettempdir(), f"claude-skill-active-{session_id()}.state"
    )


def mark_skill_active() -> None:
    """Record that a Skill is running. Best-effort, never raises."""
    try:
        with open(skill_active_path(), "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def skill_active_fresh() -> bool:
    """True if a Skill was invoked within SKILL_ACTIVE_TTL_SECONDS.

    A stale or missing sentinel returns False so enforcement resumes — this is
    the never-block-forever guard. Reads the stored timestamp rather than the
    file mtime so the TTL is explicit and testable.
    """
    try:
        with open(skill_active_path()) as f:
            ts = float(f.read().strip() or "0")
    except Exception:
        return False
    return (time.time() - ts) < SKILL_ACTIVE_TTL_SECONDS


def read_ignore_count(path: str) -> int:
    try:
        with open(path) as f:
            return int(f.read().strip() or "0")
    except Exception:
        return 0


def write_ignore_count(path: str, count: int) -> None:
    try:
        with open(path, "w") as f:
            f.write(str(count))
    except Exception:
        pass


def should_remind(reminder_path: str) -> bool:
    """Return True if enough time passed since last reminder."""
    now = time.time()
    try:
        with open(reminder_path) as f:
            last = float(f.read().strip() or "0")
    except Exception:
        last = 0

    if now - last < REMIND_WINDOW_SECONDS:
        return False

    try:
        with open(reminder_path, "w") as f:
            f.write(str(now))
    except Exception:
        pass
    return True


def has_bypass_marker(payload: dict) -> bool:
    """Check if the tool input contains a SKILL_BYPASS justification.

    Only checks the 'description' field (human-visible Bash description)
    to prevent accidental bypass via crafted command strings or file paths.
    See Anthropic compliance audit I-3.
    """
    tool_input = payload.get("tool_input") or {}
    val = tool_input.get("description", "")
    return isinstance(val, str) and "SKILL_BYPASS:" in val


def log_bypass(payload: dict) -> None:
    """Append an explicit SKILL_BYPASS decision to the per-session ledger
    (v1.23.0, Layer 2). Consumed by /session-save self-audit. Best-effort —
    never raises, never blocks the tool call."""
    try:
        desc = (payload.get("tool_input") or {}).get("description") or ""
        reason = (
            desc.split("SKILL_BYPASS:", 1)[1].strip()
            if "SKILL_BYPASS:" in desc else ""
        )
        rec = {
            "ts": time.time(),
            "tool": payload.get("tool_name") or "?",
            "reason": reason[:300],
        }
        ledger = os.path.join(
            tempfile.gettempdir(), "claude-skill-ledger-%s.jsonl" % session_id()
        )
        with open(ledger, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def is_readonly_bash(payload: dict) -> bool:
    """True for pure inspection Bash (ls/cat/grep/find/git status|log|diff …).

    Read-only recon is not "entering a task", so demanding a skill decision on
    every such call is pure ceremony (v1.35.0). Mutations (Edit/Write/
    NotebookEdit) and any state-changing or unrecognised Bash still go through
    the gate below. Conservative by design: the command is split on ; | && ||
    and EVERY segment must match the read-only allowlist, any redirection
    (>, >>, tee) forces False, so a read-only prefix cannot smuggle a mutation
    ("ls && rm -rf", "cat x > y"). Erring toward False only keeps the reminder —
    it never wrongly suppresses enforcement.
    """
    if (payload or {}).get("tool_name") != "Bash":
        return False
    cmd = ((payload or {}).get("tool_input") or {}).get("command") or ""
    if not cmd.strip():
        return False
    import re
    # v1.47.0 (retro 2026-07-04, finding #2): unwrap `wsl.exe [-d X] [--exec|-e]
    # bash -lc "<inner>"` and judge the INNER command — on a Windows+WSL setup
    # every repo command travels in this wrapper, so the exemption never fired
    # and read-only recon produced hundreds of ceremony SKILL_BYPASS records
    # (628 in the ledger, top reason «read-only lookup»).
    # v1.53.0 (retro 2026-07-05, P1): also unwrap the SHORT `-e` form of --exec.
    # v1.47.0 only matched the long `--exec`, but `wsl -e bash -lc …` is the far
    # more common spelling — it never unwrapped, so a whole session of read-only
    # recon produced 691 ceremony SKILL_BYPASS records (all Bash) in the ledger.
    for _ in range(3):  # nested wrappers are theoretical; bound the loop
        m = re.match(
            r"""^\s*wsl(?:\.exe)?\s+(?:-d\s+\S+\s+)?(?:(?:--exec|-e)\s+)?
                bash\s+-l?c\s+(["'])(.*)\1\s*$""",
            cmd.strip(), re.VERBOSE | re.DOTALL,
        )
        if not m:
            break
        cmd = m.group(2)
    if re.search(r">>?|\btee\b", cmd):
        return False
    allow = re.compile(
        r"^(ls|ll|cat|bat|head|tail|less|more|grep|rg|ag|find|fd|wc|pwd|echo|"
        r"printf|which|type|command|stat|file|tree|du|df|env|whoami|hostname|"
        r"date|realpath|readlink|dirname|basename|awk|cut|sort|uniq|column|jq|"
        r"sed\s+-n|cd|sleep|true|diff|md5sum|sha\d*sum|"
        # test-runners: running a suite is verification recon, not entering a new
        # task (v1.54.0, Release E1). Narrow on purpose — bare `pytest`,
        # `python[3] -m pytest` / `python[3] tests/…`, `npm test` / `npm run test`,
        # `go test`. `python app.py`, `npm run build`, `npm run dev` etc. stay
        # gated (they run product code, not the suite). Evidence: 691 ceremony
        # SKILL_BYPASS records this session, dominated by verification/recon.
        r"pytest\b|python3?\s+(?:-m\s+pytest\b|tests/\S+)|npm\s+(?:test|run\s+test)\b|"
        r"go\s+test\b|"
        # gh: read-only subcommands only — merge/create/edit/close stay gated
        r"gh\s+(pr|run|issue|release)\s+(view|list|checks|status|diff)|"
        # git: optional `-C <dir>` prefix, then a read-only subcommand (v1.54.0,
        # Release E1 — `git -C <path> status|log|…` is the same read-only recon;
        # a non-read-only sub after `-C` still fails and stays gated).
        r"git\s+(?:-C\s+\S+\s+)?(status|log|diff|show|"
        r"branch\b(?!\s+(-[dDmMf]|--delete|--move|--force))|"
        r"remote\b(?!\s+(add|remove|rename|set-url))|rev-parse|ls-files|describe|"
        r"blame|shortlog|config\s+--get))\b"
    )
    segs = [s.strip() for s in re.split(r"&&|\|\||;|\|", cmd) if s.strip()]
    return bool(segs) and all(allow.match(s) for s in segs)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = (payload or {}).get("tool_name") or "?"
    reminder_path, ignore_path = state_paths()

    # --- Read-only inspection Bash → not a task entry, skip the gate silently ---
    # (v1.35.0) Does not touch the ignore counter or grace window: recon is
    # neither skill work nor an ignore. Mutations fall through to enforcement.
    if is_readonly_bash(payload):
        return 0

    # --- Skill call detected → reset ignore counter, open grace window ---
    if tool == "Skill":
        write_ignore_count(ignore_path, 0)
        mark_skill_active()
        return 0

    # --- Bypass marker in tool input → log, reset, open grace window, allow ---
    if has_bypass_marker(payload):
        log_bypass(payload)
        write_ignore_count(ignore_path, 0)
        mark_skill_active()  # one bypass opens a grace window, not a single call
        return 0

    # --- Fresh skill-active sentinel → a skill is running, grant grace ---
    # A legitimate skill-driven Edit/Bash flow must never be falsely blocked.
    # Edit/Write/NotebookEdit carry no 'description' field, so they cannot
    # supply an in-band SKILL_BYPASS — the grace window is their only escape.
    # Reset and allow silently. The TTL (checked inside skill_active_fresh)
    # bounds this so enforcement resumes after the skill window lapses.
    if skill_active_fresh():
        write_ignore_count(ignore_path, 0)
        return 0

    # --- Check if we should enforce (block) ---
    ignore_count = read_ignore_count(ignore_path)

    if ignore_count >= MAX_IGNORES:
        # BLOCK: too many consecutive ignores
        block_msg = (
            f"[SKILL ENFORCEMENT — БЛОКИРОВКА] ⛔ Подряд {ignore_count} "
            "напоминаний о скиллах были проигнорированы. Tool call ЗАБЛОКИРОВАН.\n\n"
            "Чтобы продолжить, выбери ОДНО из двух:\n"
            "1. Вызови подходящий скилл через инструмент Skill "
            "(/bugfix, /test, /refactor, /doc, /review, /explain, /perf, "
            "/project, /task, /blueprint, /guide, /session-save, "
            "/security-audit, /deps-audit, /migrate, /harden, /infra)\n"
            "2. Обоснуй обход — добавь в description Bash/Edit/Write текст "
            "'SKILL_BYPASS: <причина почему ни один скилл не подходит>'\n\n"
            "Подробности: ROADMAP_v1.19.md Gap #4, "
            "~/.claude/CLAUDE.md раздел «ЖЁСТКОЕ ПРАВИЛО»."
        )
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": block_msg,
            }
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        sys.stderr.write(block_msg)
        sys.exit(2)

    # --- Rate-limited reminder ---
    if not should_remind(reminder_path):
        return 0  # silent no-op when recently reminded

    # Increment ignore counter (will be reset if Skill is called next)
    write_ignore_count(ignore_path, ignore_count + 1)

    context = (
        f"[SKILL CHECK — реши явно] Сейчас вызов {tool}. "
        "Если это вход в новую задачу — оцени task-level: подходит ли "
        "/bugfix, /test, /refactor, /doc, /review, /explain, /perf, /project, "
        "/task, /blueprint, /guide, /session-save, /advisor, /grill-me, "
        "/discover? Если подходит — вызови его через Skill ПЕРВЫМ. Молча "
        "продолжать руками нельзя: вынеси решение видимой ПЕРВОЙ строкой "
        "ответа — «Скилл: /X» либо «Скилл: не нужен — <причина>». При "
        "осознанном отказе добавь 'SKILL_BYPASS: <причина>' в description "
        "(это валидный выбор, не игнор — счётчик сбросится). "
        "Подробности: ~/.claude/CLAUDE.md.\n\n"
        f"⚠️ Счётчик игнорирований: {ignore_count + 1}/{MAX_IGNORES}. "
        f"После {MAX_IGNORES} подряд без Skill или SKILL_BYPASS — tool calls "
        "будут ЗАБЛОКИРОВАНЫ."
    )

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
