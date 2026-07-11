#!/usr/bin/env python3
"""
PreToolUse hook on Task/Agent — advisory model-policy hint (v1.83.0,
retro 2026-07-11, component "Model" of the harness five).

Gap it closes: risk-tier => model monotonicity (G-003) was enforced only at
CONFIG level (tests/verify_model_risk_monotonic.py pins agent frontmatter to
MODEL-ROUTING-POLICY.md in CI). At RUNTIME nothing watched ad-hoc spawns:
`Agent(subagent_type="security-reviewer", model="haiku")` silently downgraded
the highest-stakes verify class.

Behaviour:
  * no `model` override in tool_input  -> silent exit 0 (frontmatter governs,
    policy holds by construction);
  * override present and RANKED WEAKER than the agent's frontmatter `model:`
    -> additionalContext advisory (never a deny: a deliberate downgrade for a
    cheap mechanical slice is legitimate — semantics stay with the model, HARNESS_ENGINEERING_MAP §8.3);
  * unknown agent type / unknown model tier -> silent (fail-open, zero noise).

Output is ASCII-only JSON (ensure_ascii + English text): on the Windows
install a hook pipe may be cp1251 — non-ASCII silently kills the hook output
(RELEASE_RUNBOOK "grabli").

Reads JSON on stdin: {"tool_name": "Task"|"Agent",
                      "tool_input": {"subagent_type": "...", "model": "..."}}
"""
from __future__ import annotations

import json
import os
import re
import sys

RANK = {"haiku": 1, "sonnet": 2, "opus": 3}


def frontmatter_model(agent_type: str) -> str | None:
    """model: из frontmatter агента — репо-checkout (cwd) или активный инсталл."""
    if not re.fullmatch(r"[\w-]+", agent_type or ""):
        return None
    for base in (os.path.join(os.getcwd(), "agents"),
                 os.path.expanduser(os.path.join("~", ".claude", "agents"))):
        path = os.path.join(base, agent_type + ".md")
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                head = f.read(4000)
        except OSError:
            continue
        m = re.search(r"^model:\s*([\w-]+)", head, re.M)
        if m:
            return m.group(1).strip().lower()
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    ti = payload.get("tool_input") or {}
    override = str(ti.get("model") or "").strip().lower()
    agent_type = str(ti.get("subagent_type") or "").strip()
    if not override or not agent_type:
        return 0
    declared = frontmatter_model(agent_type)
    if not declared or override not in RANK or declared not in RANK:
        return 0
    if RANK[override] >= RANK[declared]:
        return 0
    ctx = (
        "[MODEL POLICY - advisory] Agent '{a}' declares model '{d}' "
        "(frontmatter, pinned to MODEL-ROUTING-POLICY.md by CI gate G-003), "
        "but this spawn overrides it with a WEAKER tier: '{o}'. "
        "Risk-tier => model monotonicity: verify agents must not be quietly "
        "downgraded. If the downgrade is deliberate (cheap mechanical slice), "
        "proceed and say so explicitly; otherwise drop the override."
    ).format(a=agent_type, d=declared, o=override)
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": ctx,
        }
    }, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
