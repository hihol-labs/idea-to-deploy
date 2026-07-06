#!/usr/bin/env python3
"""
PostToolUse hook on Task/Agent — records subagent-based skill completion
so the commit gates count work delegated to a subagent (bug #2 follow-up).

Problem
-------
The commit gates — check-review-before-commit.sh ("> 2 files -> /review")
and check-dod-before-commit.sh (migrations/money/new-code -> /migrate,
/test, /security-audit) — detect that a skill ran via a per-session
sentinel `<tmp>/claude-<skill>-done-<session>`, written by the SKILL
itself at its final step.

But the same review/test/security work is frequently delegated to a
SUBAGENT (the Agent/Task tool — e.g. the `code-reviewer` agent invoked
directly or by /review). That left no sentinel, so the gate saw "no
review" and falsely blocked the commit (notably from WSL). Two facts make
"let the agent write its own sentinel" unworkable, which is why this hook
exists:

  * Read-only agents. code-reviewer / security-reviewer / test-generator
    are constrained to Read/Grep/Glob (no Write/Bash) — they CANNOT write
    a sentinel themselves.
  * The Skill tool emits no hook events, but the Task/Agent tool DOES —
    so a PostToolUse hook is the one reliable place to observe that a
    subagent finished.

Fix
---
After a subagent finishes, write the matching skill sentinel on its
behalf. Mapping (subagent_type -> gate skill), restricted to agents that
satisfy a real commit gate — expanded deliberately, not speculatively:

    code-reviewer     -> review          (check-review-before-commit.sh)
    test-generator    -> test            (check-dod-before-commit.sh)
    security-reviewer -> security-audit  (check-dod-before-commit.sh)

PostToolUse (not Pre) so the sentinel marks an ACTUALLY-COMPLETED pass,
mirroring the skill convention (sentinel at the final step) rather than an
intent. The sentinel is written to every temp dir the gates search (`/tmp`
for the review gate; plus the platform temp dir for the DoD gate) for
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
    "code-reviewer": "review",
    "test-generator": "test",
    "security-reviewer": "security-audit",
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


def _staged_tree_hash() -> str:
    """`git write-tree` fingerprint of the current index, or "" on failure.

    Runs in the hook's cwd, which at runtime is the project repo where the
    delegated review happened and where the commit will occur — so the token
    matches what check-review-before-commit.sh computes at commit time.
    """
    try:
        import subprocess
        r = subprocess.run(["git", "write-tree"],
                           capture_output=True, text=True, timeout=5)
        h = r.stdout.strip() if r.returncode == 0 else ""
        return h if len(h) == 40 and all(c in "0123456789abcdef" for c in h) else ""
    except Exception:
        return ""


def sentinel_content(skill: str) -> str:
    """The /review gate (v1.59.0) is DIFF-BOUND: it accepts the review
    sentinel only when its content is `tree:<staged-tree-hash>` matching the
    commit. A subagent (code-reviewer) can't write its own sentinel, so this
    hook writes the bound token on its behalf. Other skills feed the
    existence-based DoD/commit gates, which don't parse content, so they keep
    the plain timestamp. If git can't fingerprint the tree, fall back to a
    timestamp — the review gate will then simply re-require /review (safe)."""
    if skill == "review":
        h = _staged_tree_hash()
        if h:
            return "tree:%s" % h
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
