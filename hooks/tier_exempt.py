"""Tier early-exit for advisory hooks (G-003, HOOKS-TIER-EXIT-1).

`TIER_EXEMPT.json` next to this file names the advisory hooks that may stay silent when
the ACTIVE unit's riskTier is exactly `low`. A listed hook calls `exempt(<script>,
payload)` right after reading its payload and returns 0 on True - before any state read,
state write or output.

The tier comes from `.itd-memory/STATE.json` ONLY: `currentUnit` must be an object whose
`status` is `in_progress` or `verifying` (active) and whose `riskTier` is exactly the JSON
string "low". `GOAL.json` is never read - the goal harness and the unit writer both
project the active unit, with its riskTier, into STATE. A closed unit (the harness leaves
a verified unit in `currentUnit`) silences nothing.

The project is resolved from the payload `cwd` ONLY (Claude Code and codex-dispatch.py
send it on every event these hooks handle), walked up to the nearest `.itd-memory/`. There
is no fall-through to `CLAUDE_PROJECT_DIR` or the process cwd: a payload without `cwd`, or
a `cwd` outside any ITD project, silences nothing - so a test or a session in one
directory is never governed by another project's (or the methodology repo's own) tier.

Fail toward normal behaviour: a missing/invalid list, no `cwd`, no `.itd-memory/`, an
absent STATE, a STATE that exists (a dangling symlink included) but cannot be read or
parsed into an object, a `currentUnit` that is missing or not an object, a closed unit, a
unit without `riskTier`, or a tier that is not exactly "low" (e.g. "LOW") all answer
False. The policy default tier is deliberately NOT consulted - the project template
default is `low`, and a missing tier must never silence a hook. Gates are never listed;
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
    if not isinstance(unit, dict):
        return None  # no active STATE unit
    if unit.get("status") not in ACTIVE:
        return None  # closed unit
    if "riskTier" not in unit:
        return None  # no tier
    return unit["riskTier"]  # exact JSON value


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
