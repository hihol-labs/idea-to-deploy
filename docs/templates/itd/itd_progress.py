#!/usr/bin/env python3
"""itd_progress.py — derived PROGRESS view (v1.70.0).

Renders a single human-glanceable .itd-memory/PROGRESS.md from the canonical
machine-readable state: STATE.json + GOAL.json + events.jsonl + git +
.itd/DECISIONS.md (+ completion verdict when present).

Contract (best-effort invariant): PROGRESS.md is a DERIVED, regenerable VIEW —
never the contract itself. Gates and handoffs must keep reading STATE.json /
GOAL.json; if this script or its output disappears, nothing may break.
The script therefore degrades per-section on any missing/broken input and
always exits 0 (unless --strict).

Usage (from the project root, where /adopt copied it into .itd/):
    python3 .itd/itd_progress.py            # write .itd-memory/PROGRESS.md
    python3 .itd/itd_progress.py --stdout   # print instead of writing
    python3 .itd/itd_progress.py --project-root /path/to/repo
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Windows: при редиректе stdout кодировка = локаль (cp1251) → кириллица падает.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

STATUS_MARK = {
    "verified": "[x]",
    "done": "[x]",
    "in_progress": "[~]",
    "verifying": "[~]",
    "recovery_required": "[!]",
    "skipped": "[-]",
}


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _git(project_root: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(project_root), *args],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def section_current_state(root: Path, state) -> list[str]:
    lines = ["## Current State", ""]
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    commit = _git(root, "log", "-1", "--format=%h %s")
    dirty = _git(root, "status", "--porcelain")
    if branch or commit:
        lines.append(f"- Git: `{branch or '?'}` @ {commit or '?'}")
        n_dirty = len([l for l in dirty.splitlines() if l.strip()])
        lines.append(f"- Незакоммичено: {n_dirty} файл(ов)" if n_dirty else "- Рабочее дерево чистое")
    else:
        lines.append("- Git: недоступен (не репозиторий / git не найден)")
    if isinstance(state, dict):
        st = state.get("sessionState", "")
        stage = state.get("currentStage", "")
        intent = state.get("intent", "")
        if st or stage:
            lines.append(f"- Сессия: {st or '?'} / стадия {stage or '?'}" + (f" — {intent}" if intent else ""))
    verdict = _read_json(root / ".claude" / "completion" / "completion.json")
    if isinstance(verdict, dict) and verdict:
        v = verdict.get("verdict") or verdict.get("status") or "?"
        lines.append(f"- Completion Gate: {v}")
    return lines


def section_goal(goal) -> list[str]:
    units = goal.get("units") if isinstance(goal, dict) else None
    if not isinstance(units, list) or not units:
        return []
    lines = ["## Цель и юниты (GOAL.json)", "", f"**{goal.get('goal', '?')}** — статус: {goal.get('status', '?')}", ""]
    next_unit = None
    for u in units:
        if not isinstance(u, dict):
            continue
        status = u.get("status", "pending")
        mark = STATUS_MARK.get(status, "[ ]")
        line = f"- {mark} `{u.get('id', '?')}` {u.get('criterion', '')} ({status}"
        if u.get("evidence"):
            line += f"; evidence: {u['evidence']}"
        line += ")"
        lines.append(line)
        if next_unit is None and status not in ("verified", "done", "skipped"):
            next_unit = u
    if next_unit is not None:
        lines += ["", f"**Продолжать с:** `{next_unit.get('id', '?')}` — {next_unit.get('criterion', '')}"]
        if next_unit.get("verificationCommand"):
            lines.append(f"Проверка: `{next_unit['verificationCommand']}`")
    return lines


def section_current_unit(state) -> list[str]:
    cu = state.get("currentUnit") if isinstance(state, dict) else None
    if not isinstance(cu, dict) or not cu.get("id"):
        return []
    return [
        "## Текущий unit (STATE.json)", "",
        f"- `{cu.get('id')}` — {cu.get('goal', '')}",
        f"- Статус: {cu.get('status', '?')} (начат {cu.get('startedAt') or '?'})",
    ]


def section_events(root: Path, limit: int = 5) -> list[str]:
    path = root / ".itd-memory" / "events.jsonl"
    try:
        raw = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        return []
    if not raw:
        return []
    lines = [f"## Последние события (events.jsonl, хвост {limit})", ""]
    for l in raw[-limit:]:
        try:
            e = json.loads(l)
            ts = e.get("ts") or e.get("timestamp") or ""
            desc = " ".join(str(e[k]) for k in ("type", "name", "decision") if e.get(k))
            lines.append("- " + " ".join(x for x in (str(ts), desc or l[:120]) if x))
        except Exception:
            lines.append(f"- {l[:120]}")
    return lines


def section_decisions(root: Path, limit: int = 3) -> list[str]:
    path = root / ".itd" / "DECISIONS.md"
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []
    heads: list[str] = []
    in_comment = False  # заголовок-пример внутри <!-- --> — не запись
    for l in text.splitlines():
        if "<!--" in l:
            in_comment = True
        if not in_comment and l.startswith("## ") and l[3:4].isdigit():
            heads.append(l[3:].strip())
        if "-->" in l:
            in_comment = False
    if not heads:
        return []
    lines = [f"## Последние решения (.itd/DECISIONS.md, {min(limit, len(heads))} из {len(heads)})", ""]
    lines += [f"- {h}" for h in heads[-limit:]]
    return lines


def section_next(state) -> list[str]:
    rec = ""
    if isinstance(state, dict):
        hs = state.get("humanSteering")
        if isinstance(hs, dict):
            rec = hs.get("recommendedNextStep", "")
    if not rec:
        return []
    return ["## Next Steps", "", f"1. {rec}"]


def render(root: Path) -> str:
    state = _read_json(root / ".itd-memory" / "STATE.json")
    goal = _read_json(root / ".itd-memory" / "GOAL.json")
    # No wall-clock timestamp in the body (v1.71.1, review finding): the view
    # is regenerated on every /session-save — a timestamp would produce a git
    # diff even when nothing changed. Freshness = mtime / the git state below.
    parts: list[list[str]] = [
        [
            "# PROGRESS — derived view",
            "",
            "> DERIVED, regenerable — сгенерировано `itd_progress.py`; кандидат",
            "> в `.gitignore` целевого проекта. НЕ редактируй руками и НЕ",
            "> завязывай на этот файл гейты: канон — `STATE.json` / `GOAL.json`",
            "> / `events.jsonl`. Перегенерация: `python3 .itd/itd_progress.py`.",
        ],
        section_current_state(root, state),
        section_goal(goal),
        section_current_unit(state),
        section_events(root),
        section_decisions(root),
        section_next(state),
    ]
    return "\n\n".join("\n".join(p) for p in parts if p) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Render derived PROGRESS.md from ITD state")
    ap.add_argument("--project-root", default=".", help="project root (default: cwd)")
    ap.add_argument("--stdout", action="store_true", help="print to stdout instead of writing")
    ap.add_argument("--strict", action="store_true", help="non-zero exit on write failure")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    text = render(root)
    if args.stdout:
        sys.stdout.write(text)
        return 0
    out = root / ".itd-memory" / "PROGRESS.md"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"PROGRESS view -> {out}")
        return 0
    except Exception as exc:  # best-effort: view must never break the flow
        print(f"WARN: PROGRESS view not written ({exc})", file=sys.stderr)
        return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
