#!/usr/bin/env python3
"""
PreToolUse hook on Task/Agent — model/effort routing boundary (v1.91.0,
PE5-015 working-deadline profile).

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
  * explicit `effort=low` on an agent that already declares low effort ->
    silent (the mechanical role default is not a downgrade);
  * any other explicit `effort=low` requires an active low/medium-risk
    `working_deadline` unit plus a description beginning `[itd:mechanical]`;
  * high-effort/protected roles and unknown/high risk require a host-native ASK
    before the override can run. Review, security, root-cause, architecture and
    gate-producing roles therefore cannot be downgraded silently, while the
    hook remains a policy/oversight boundary rather than a new hard gate.

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
from pathlib import Path

RANK = {"haiku": 1, "sonnet": 2, "opus": 3}
EFFORT_RANK = {"low": 1, "medium": 2, "high": 3}
MECHANICAL_PREFIX = "[itd:mechanical]"
PROTECTED_AGENTS = {
    "architect",
    "code-reviewer",
    "devils-advocate",
    "perf-analyzer",
    "security-reviewer",
    "test-generator",
}


def frontmatter(agent_type: str) -> dict[str, str]:
    """Read model/effort from checkout, plugin bundle, or active install."""
    if not re.fullmatch(r"[\w-]+", agent_type or ""):
        return {}
    script_root = Path(__file__).resolve().parent.parent
    bases = (
        Path.cwd() / "agents",
        script_root / "agents",
        Path(os.path.expanduser(os.path.join("~", ".claude", "agents"))),
    )
    for base in bases:
        path = base / (agent_type + ".md")
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        result: dict[str, str] = {}
        for key in ("model", "effort"):
            match = re.search(r"^" + key + r":\s*([\w-]+)", head, re.M)
            if match:
                result[key] = match.group(1).strip().lower()
        if result:
            return result
    return {}


def active_work_context() -> tuple[str, str]:
    """Return (risk tier, work profile); missing/ambiguous stays unknown."""
    memory = Path.cwd() / ".itd-memory"
    goal_path = memory / "GOAL.json"
    try:
        goal = json.loads(goal_path.read_text(encoding="utf-8"))
        current = str(goal.get("currentUnitId") or "")
        units = goal.get("units") or []
        unit = next((item for item in units
                     if isinstance(item, dict)
                     and str(item.get("id") or "") == current
                     and str(item.get("status") or "") == "in_progress"), None)
        if unit:
            deadline = unit.get("deadlineState") or {}
            return (str(unit.get("riskTier") or "unknown").lower(),
                    str(deadline.get("profile") or "").lower())
    except (OSError, ValueError, TypeError):
        pass

    state_path = memory / "STATE.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        unit = state.get("currentUnit") or {}
        deadline = unit.get("deadlineState") or {}
        if str(unit.get("status") or "") in {"in_progress", "verifying"}:
            return (str(unit.get("riskTier") or "unknown").lower(),
                    str(deadline.get("profile") or unit.get("workProfile") or "").lower())
    except (OSError, ValueError, TypeError):
        pass
    return "unknown", ""


def ask_low_effort(why: str, agent_type: str) -> int:
    reason = (
        "[MODEL POLICY - confirmation required] effort=low is outside the "
        "automatic safe route for Agent '{agent}'. "
        "WHY: {why}. FIX: keep the declared effort, or use a low/medium-risk "
        "working_deadline unit and prefix a genuinely mechanical slice "
        "description with '[itd:mechanical]'. Review, security, root-cause, "
        "architecture and gate-producing roles cannot be downgraded."
    ).format(agent=agent_type or "unknown", why=why)
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=True))
    return 0


def low_effort_check(tool_input: dict, agent_type: str,
                     declared_effort: str) -> int | None:
    """Return 0 after an ASK for an unsafe explicit low override, else None."""
    override = str(tool_input.get("effort") or "").strip().lower()
    if override != "low":
        return None
    if declared_effort == "low":
        return None
    if not agent_type or declared_effort not in EFFORT_RANK:
        return ask_low_effort("agent effort floor is unknown (risk fails closed)",
                              agent_type)
    if agent_type in PROTECTED_AGENTS or declared_effort == "high":
        return ask_low_effort(
            "the agent is a protected quality-floor role with declared effort '%s'"
            % declared_effort, agent_type)

    risk, profile = active_work_context()
    if risk not in {"low", "medium"}:
        return ask_low_effort("active risk is '%s', not known low/medium" % risk,
                              agent_type)
    if profile != "working_deadline":
        return ask_low_effort("working_deadline is not active", agent_type)
    description = str(tool_input.get("description") or "").strip().lower()
    if not description.startswith(MECHANICAL_PREFIX):
        return ask_low_effort("the bounded slice is not marked mechanical",
                              agent_type)
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
    declared = frontmatter(agent_type)
    denied = low_effort_check(ti, agent_type, declared.get("effort", ""))
    if denied is not None:
        return denied
    if not override or not agent_type:
        return 0
    declared_model = declared.get("model", "")
    if not declared_model or override not in RANK or declared_model not in RANK:
        return 0
    if RANK[override] >= RANK[declared_model]:
        return 0
    ctx = (
        "[MODEL POLICY - advisory] Agent '{a}' declares model '{d}' "
        "(frontmatter, pinned to MODEL-ROUTING-POLICY.md by CI gate G-003), "
        "but this spawn overrides it with a WEAKER tier: '{o}'. "
        "Risk-tier => model monotonicity: verify agents must not be quietly "
        "downgraded. If the downgrade is deliberate (cheap mechanical slice), "
        "proceed and say so explicitly; otherwise drop the override."
    ).format(a=agent_type, d=declared_model, o=override)
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": ctx,
        }
    }, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
