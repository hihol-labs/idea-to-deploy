"""Tier early-exit for advisory hooks (G-003, HOOKS-TIER-EXIT-1).

`TIER_EXEMPT.json` next to this file names the advisory hooks that may stay silent when
the ACTIVE unit's riskTier is exactly `low`. A listed hook calls `exempt(<script>,
payload)` right after reading its payload and returns 0 on True - before any state read,
state write or output.

Active means `STATE.currentUnit.status` (or the GOAL unit named by `currentUnitId`) is
`in_progress` or `verifying`; a closed unit (verified, recovery_required, blocked, ...)
silences nothing - the harness leaves a verified unit in `currentUnit`, and its tier must
not keep the hooks quiet after the unit ends.

The project is resolved from the payload `cwd` ONLY (Claude Code and codex-dispatch.py
send it on every event these hooks handle), walked up to the nearest `.itd-memory/`. There
is no fall-through to `CLAUDE_PROJECT_DIR` or the process cwd: a payload without `cwd`, or
a `cwd` outside any ITD project, silences nothing - so a test or a session in one
directory is never governed by another project's (or the methodology repo's own) tier.

The GOAL fallback applies only to an active goal (`status: active`) and, when STATE holds
an active unit, only to that same unit id (an active STATE unit without an id and without
a tier silences nothing).

STATE is read first: an active STATE unit with an explicit tier decides alone, and GOAL
is not read at all. GOAL is consulted only as the fallback (no STATE unit, or an active
STATE unit without a tier).

Fail toward normal behaviour: a missing/invalid list, no `cwd`, no `.itd-memory/`, a
STATE that exists (a dangling symlink included) but cannot be read or parsed, a GOAL that
cannot be read or parsed when the fallback needs it (never a fall-through from a broken
file to the other one), a tier that is not exactly the JSON string "low" (e.g. "LOW"), or
an active unit without an explicit riskTier all answer False (the policy
default tier is deliberately NOT consulted - the project template default is `low`, and a
missing tier must never silence a hook). Gates are never listed;
tests/verify_hook_tier_exit.py enforces that.
"""
from __future__ import annotations

import json
from pathlib import Path

LIST_PATH = Path(__file__).with_name("TIER_EXEMPT.json")
ACTIVE = {"in_progress", "verifying"}


def _read(path: Path) -> dict | None:
    """{} when there is no such entry; None when an entry exists (a dangling symlink
    included) but cannot be read or parsed into an object."""
    if not path.exists() and not path.is_symlink():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _memory_dir(payload: dict) -> Path | None:
    raw = payload.get("cwd")
    if not raw:
        return None  # no payload cwd: no project
    current = Path(str(raw)).resolve()
    while True:
        if (current / ".itd-memory").is_dir():
            return current / ".itd-memory"
        if current.parent == current:
            return None
        current = current.parent


def active_tier(payload: dict) -> object:
    memory = _memory_dir(payload)
    if memory is None:
        return None
    state = _read(memory / "STATE.json")
    if state is None:
        return None  # unreadable STATE
    unit = state.get("currentUnit")
    state_id = None
    if isinstance(unit, dict) and unit:
        if unit.get("status") not in ACTIVE:
            return None  # closed unit
        if unit.get("riskTier"):
            return unit["riskTier"]  # exact JSON value
        state_id = unit.get("id")
        if not state_id:
            return None  # active STATE unit without id: cannot tie it to a GOAL unit
    goal = _read(memory / "GOAL.json")
    if goal is None or goal.get("status") != "active":
        return None  # no active goal
    current = goal.get("currentUnitId")
    if state_id and current != state_id:
        return None  # STATE and GOAL name different units
    units = goal.get("units")
    if current and isinstance(units, list):
        for candidate in units:
            if isinstance(candidate, dict) and candidate.get("id") == current:
                if candidate.get("status") in ACTIVE and candidate.get("riskTier"):
                    return candidate["riskTier"]  # exact JSON value
                break
    return None  # no tier


def exempt(script: str, payload: object) -> bool:
    try:
        data = _read(LIST_PATH) or {}
        tier = data.get("exemptTier")
        entries = data.get("hooks")
        if tier != "low" or not isinstance(entries, list):
            return False
        if script not in {e.get("script") for e in entries if isinstance(e, dict)}:
            return False
        tier = active_tier(payload if isinstance(payload, dict) else {})
        return tier == "low"
    except Exception:
        return False
