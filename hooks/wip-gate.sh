#!/usr/bin/env python3
"""
PreToolUse hook (Edit|Write|MultiEdit) — WIP=1 activation gate (v1.41.0).

The scope-control principle: only ONE unit may be active at a time, and the
next unit must not start while the current one is unverified. "Unit activation"
has no tool-call signature a hook could intercept directly, so this gate fires
on the closest observable proxy: an Edit/Write OUTSIDE the current unit's
allowed scope while that unit sits in `verifying` / `recovery_required`.

Computational detect, soft enforcement (HARNESS_ENGINEERING_MAP.md §8.3): the
status check and path-prefix match are deterministic, but "is the user really
starting a new task or just fixing the current one?" is semantic — so this
emits an additionalContext hint, never a deny. The full hard block ("VCR<1.0 →
no new units") stays deferred until skills reliably write unit events.

Fires only when ALL hold:
  - a `.itd-memory/STATE.json` exists at cwd or an ancestor (≤ 8 levels);
  - `currentUnit.status` ∈ {"verifying", "recovery_required"};
  - `.itd/SCOPE_LOCK.md` declares REAL allowed areas (template prose ignored);
  - the edited path is outside every allowed area;
  - not rate-limited (one hint per ITD_WIP_GATE_RATE_MIN, default 30, per
    session+project).

Disable with ITD_WIP_GATE=0. Fail-safe: any error → exit 0, never blocks.

Reads JSON on stdin: {"tool_name": "...", "tool_input": {"file_path": "..."}}
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

RATE_MIN_DEFAULT = 30
MAX_ASCEND = 8
GATED_STATUSES = {"verifying", "recovery_required"}
TEMPLATE_PROSE = "replace this line"


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except Exception:
        return default


def session_id(payload: dict) -> str:
    sid = payload.get("session_id") or os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return str(sid)
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def find_project_root(start: Path) -> Path | None:
    """Nearest ancestor (incl. start) carrying .itd-memory/STATE.json."""
    cur = start.resolve()
    for _ in range(MAX_ASCEND):
        if (cur / ".itd-memory" / "STATE.json").is_file():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent
    return None


def allowed_areas(root: Path) -> list[str]:
    """Parse '## Allowed Change Areas' bullets from SCOPE_LOCK.md.

    Returns [] when the file is absent or still template prose — in that case
    the gate stays silent (no declared scope to compare against).
    """
    lock = root / ".itd" / "SCOPE_LOCK.md"
    if not lock.is_file():
        return []
    try:
        text = lock.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    areas: list[str] = []
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped.lower().startswith("## allowed change areas")
            continue
        if in_section and stripped.startswith("- "):
            item = stripped[2:].strip().strip("`")
            if item and TEMPLATE_PROSE not in item.lower():
                areas.append(item)
    return areas


def path_in_areas(rel_path: str, areas: list[str]) -> bool:
    rel_norm = rel_path.replace("\\", "/").lstrip("./")
    for area in areas:
        a = area.replace("\\", "/").strip("/").lstrip("./")
        if not a:
            continue
        # segment-aware containment: area "src/auth" matches "backend/src/auth/x.py"
        # but area "src" must NOT match "other-src-thing/file.ts"
        if rel_norm == a or rel_norm.startswith(a + "/") or f"/{a}/" in f"/{rel_norm}/":
            return True
    return False


def sentinel(sid: str, root: Path) -> Path:
    tag = hashlib.md5(str(root).encode("utf-8", "replace")).hexdigest()[:8]
    return Path(tempfile.gettempdir()) / f"claude-wip-gate-{sid}-{tag}"


def rate_limited(p: Path, rate_min: int) -> bool:
    try:
        return (time.time() - float(p.read_text().strip())) < rate_min * 60
    except Exception:
        return False


def main() -> int:
    if os.environ.get("ITD_WIP_GATE", "1") == "0":
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not file_path:
        return 0

    root = find_project_root(Path(payload.get("cwd") or os.getcwd()))
    if root is None:
        return 0

    try:
        state = json.loads((root / ".itd-memory" / "STATE.json").read_text(encoding="utf-8"))
    except Exception:
        return 0

    unit = state.get("currentUnit") or {}
    status = str(unit.get("status", "")).lower()
    if status not in GATED_STATUSES:
        return 0

    areas = allowed_areas(root)
    if not areas:
        return 0  # no declared scope — nothing computational to compare against

    try:
        rel = str(Path(file_path).resolve().relative_to(root))
    except Exception:
        rel = file_path
    if path_in_areas(rel, areas):
        return 0

    sid = session_id(payload)
    rate_min = env_int("ITD_WIP_GATE_RATE_MIN", RATE_MIN_DEFAULT)
    s = sentinel(sid, root)
    if rate_limited(s, rate_min):
        return 0
    try:
        s.write_text(str(time.time()))
    except Exception:
        pass

    unit_id = unit.get("id") or "?"
    goal = unit.get("goal") or ""
    context = (
        "[WIP-GATE — правило WIP=1] Текущий unit "
        f"`{unit_id}`{f' («{goal}»)' if goal else ''} в статусе `{status}`, "
        f"а правка `{rel}` — вне Allowed Change Areas его SCOPE_LOCK. "
        "Одна активная задача за раз: сначала доведи верификацию текущего unit'а "
        "(прогони verificationCommand'ы, обнови STATE.json), либо осознанно "
        "переклассифицируй задачу — обнови SCOPE_LOCK.md/currentUnit ПЕРЕД правкой. "
        f"(soft hint, раз в {rate_min} мин; отключить: ITD_WIP_GATE=0)"
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
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
