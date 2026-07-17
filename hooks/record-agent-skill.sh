#!/usr/bin/env python3
"""
PostToolUse hook on Task/Agent — records delegated `/test` completion.

Problem
-------
The legacy commit gates detected skill completion through per-session
sentinels. Review and security now require a successful bound verdict; only
the still existence-based `/test` signal is produced here.

Test generation is frequently delegated to a SUBAGENT (the Agent/Task tool).
That left no sentinel, so the DoD gate saw "no test" and falsely blocked the
commit. Two facts make "let the agent write its own sentinel" unworkable:

  * A read-only test-generator cannot write a sentinel itself.
  * The Skill tool emits no hook events, but the Task/Agent tool DOES —
    so a PostToolUse hook is the one reliable place to observe that a
    subagent finished.

Fix
---
After a subagent finishes, write the matching skill sentinel on its
behalf. Mapping (subagent_type -> gate skill), restricted to agents that
satisfy a real commit gate — expanded deliberately, not speculatively:

    test-generator    -> test            (check-dod-before-commit.sh)

Review/security completion is no longer enough to satisfy a gate: their
workflow caller must explicitly pass the independent verdict to
`itd_review_cache.py`. Neither this PostToolUse observer nor the generic
SubagentStop verdict-contract may mint a success marker from agent output.

PostToolUse (not Pre) so the sentinel marks ACTUALLY-COMPLETED test work,
mirroring the skill convention (sentinel at the final step) rather than an
intent. The sentinel is written to every temp dir the DoD gate searches for
cross-platform robustness. This hook NEVER blocks — it always exits 0.

Reads JSON on stdin:
  {"tool_name": "Task"|"Agent", "tool_input": {"subagent_type": "..."}}
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

# subagent_type -> gate skill sentinel name. Only agents that map to a
# real commit gate are listed.
AGENT_TO_SKILL = {
    "test-generator": "test",
}

# Tool names that spawn a subagent across harness generations.
SUBAGENT_TOOLS = {"Task", "Agent"}

# Declared hook event for meta_review M-C10. This hook emits no output of
# its own (a PostToolUse "block" is ignored per the hooks spec — see the
# v1.5.1 note in hooks/README.md), so the event type is declared here for
# the schema linter rather than inferred from an emitted payload:
#   {"hookEventName": "PostToolUse"}


def session_id() -> str:
    return os.environ.get("CLAUDE_SESSION_ID") or str(os.getppid())


def sentinel_dirs() -> list:
    dirs = []
    for d in ("/tmp", tempfile.gettempdir()):
        if d and d not in dirs:
            dirs.append(d)
    return dirs


def sentinel_content(skill: str) -> str:
    """Existence-based `/test` DoD signal; review/security are not mapped."""
    return str(int(time.time()))


def write_sentinel(skill: str) -> None:
    sid = session_id()
    content = sentinel_content(skill)
    for d in sentinel_dirs():
        try:
            path = os.path.join(d, "claude-%s-done-%s" % (skill, sid))
            with open(path, "w") as f:
                f.write(content)
        except OSError:
            continue


def record_agent_signal(payload: dict, agent: str) -> None:
    """Дописать сигнал завершения субагента в signals.jsonl проекта (GO-003).
    Best-effort: любая ошибка проглатывается — телеметрия не ломает сессию."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import completion_lib as cl
        from pathlib import Path
        cwd = Path((payload or {}).get("cwd") or os.getcwd())
        resp = (payload or {}).get("tool_response")
        if resp is None:
            resp = (payload or {}).get("tool_result")
        sig = cl.agent_result_signal(agent, resp)
        cl.append_signal(cwd, str((payload or {}).get("session_id") or "unknown"), sig)
    except Exception:
        pass


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if (payload or {}).get("tool_name") not in SUBAGENT_TOOLS:
        return 0
    tool_input = (payload or {}).get("tool_input") or {}
    agent = (tool_input.get("subagent_type") or "").strip()
    skill = AGENT_TO_SKILL.get(agent)
    if skill:
        write_sentinel(skill)
    # v1.89.0 (GO-003): сигнал по завершению субагента — пустой финал делает
    # состояние «субагент вернул результат ↔ умер молча» различимым в леджере.
    record_agent_signal(payload, agent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
