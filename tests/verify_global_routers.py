#!/usr/bin/env python3
"""Host acceptance of plan session 4 (ADR-016): the four global routers carry one consistent ITD layer.

- ~/.claude/CLAUDE.md on WSL and Windows: exactly one managed block, byte-equal to the block of
  docs/templates/global-claude-md.md (verify_operating_loops_release.verify_router), and outside it no second
  methodology layer - no skill-decision line, no SKILL_BYPASS ritual, no override of the block;
- ~/.codex/AGENTS.md on WSL and Windows: equal to docs/templates/global-codex-agents.md (same function).

Not part of run-all: it reads the user homes of both hosts. Exit status 1 with the reason on the first violation.
The Windows leg checks reparse points through powershell.exe, so on WSL it must be on PATH.

Usage: python3 tests/verify_global_routers.py [--wsl-home DIR] [--windows-home DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_operating_loops_release as release  # noqa: E402

BEGIN, END = "<!-- ITD:BEGIN", "<!-- ITD:END methodology -->"
# Text that would put a second rule layer next to the managed block: the removed ritual and an override of the block.
SECOND_LAYER = ("SKILL_BYPASS", "Скилл:", "skill-decision", "приоритет над блоком")


def outside_block(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    rest = text[:text.find(BEGIN)] + text[text.find(END) + len(END):]
    return [marker for marker in SECOND_LAYER if marker in rest]


def check(wsl_home: Path, win_home: Path) -> dict:
    for home, windows, host in ((wsl_home, False, "WSL"), (win_home, True, "Windows")):
        release.verify_router(home / ".codex" / "AGENTS.md", f"{host} Codex", windows)
        claude = home / ".claude" / "CLAUDE.md"
        release.verify_router(claude, f"{host} Claude", windows)
        found = outside_block(claude)
        release.require(not found, f"{claude} has a second rule layer outside the managed block: {found}")
    return {"routers": 4, "homes": [str(wsl_home), str(win_home)]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wsl-home", type=Path)
    parser.add_argument("--windows-home", type=Path)
    args = parser.parse_args()
    try:
        details = check((args.wsl_home or Path.home()).absolute(),
                        (args.windows_home or release.windows_home()).absolute())
    except (release.ReleaseError, OSError, ValueError, UnicodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "PASSED", **details}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
