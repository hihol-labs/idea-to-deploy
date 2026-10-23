#!/usr/bin/env python3
"""Host acceptance of plan session 4 (ADR-016): the four global routers carry one consistent ITD layer.

- ~/.claude/CLAUDE.md on WSL and Windows: exactly one managed block, byte-equal to the block of
  docs/templates/global-claude-md.md (verify_operating_loops_release.verify_router), and outside it none of the
  markers of a second rule layer (the removed ritual, routing words, an override of the block);
- with --personal-sha256: the bytes outside the managed block are exactly the personal section the owner approved
  (sha256 of the raw file bytes around the ASCII markers, which must be strict UTF-8; no newline conversion), on both
  hosts. Markers alone cannot prove "personal data only" - any wording can carry a rule - so the acceptance binds the
  exact approved text, which itself stays out of the repository;
- ~/.codex/AGENTS.md on WSL and Windows: equal to docs/templates/global-codex-agents.md (same function).

Not part of run-all: it reads the user homes of both hosts. Exit status 1 with the reason on the first violation.
The Windows leg checks reparse points through powershell.exe, so on WSL it must be on PATH.

Usage: python3 tests/verify_global_routers.py [--wsl-home DIR] [--windows-home DIR] [--personal-sha256 HEX]
       python3 tests/verify_global_routers.py --self-test   # the marker and pin rules, no home directory read
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_operating_loops_release as release  # noqa: E402

BEGIN, END = "<!-- ITD:BEGIN", "<!-- ITD:END methodology -->"
# Text that would put a second rule layer next to the managed block: the removed ritual, the old routing and an
# override of the block.
SECOND_LAYER = ("SKILL_BYPASS", "Скилл:", "skill-decision", "MANDATORY", "Core routing", "Verification Loop",
                "приоритет над", "override", "`/task`", "`/goal`", "`/project`", "`/adopt`")


def outside_block(raw: bytes) -> bytes:
    """The raw bytes outside the one managed block, cut at the ASCII markers (verify_router checks there is one)."""
    begin, end = raw.find(BEGIN.encode("ascii")), raw.find(END.encode("ascii"))
    if begin < 0 or end < begin:
        raise ValueError("no managed ITD block")
    return raw[:begin] + raw[end + len(END):]


def layer_problems(rest: bytes, personal_sha256: str = "") -> list[str]:
    """Why the bytes outside the managed block are not personal data only; [] when nothing was found."""
    try:
        text = rest.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"not UTF-8 outside the managed block ({exc.reason} at byte {exc.start})"]
    problems = [f"second rule layer marker {marker!r}" for marker in SECOND_LAYER if marker.lower() in text.lower()]
    actual = hashlib.sha256(rest).hexdigest()
    if personal_sha256 and actual != personal_sha256:
        problems.append(f"not the approved personal section (sha256 {actual})")
    return problems


def check(wsl_home: Path, win_home: Path, personal_sha256: str = "") -> dict:
    for home, windows, host in ((wsl_home, False, "WSL"), (win_home, True, "Windows")):
        release.verify_router(home / ".codex" / "AGENTS.md", f"{host} Codex", windows)
        claude = home / ".claude" / "CLAUDE.md"
        release.verify_router(claude, f"{host} Claude", windows)
        problems = layer_problems(outside_block(claude.read_bytes()), personal_sha256)
        release.require(not problems, f"{claude}: {problems}")
    return {"routers": 4, "homes": [str(wsl_home), str(win_home)], "personalPinned": bool(personal_sha256)}


def self_test() -> int:
    """The marker and pin rules on fixed texts; reads no home directory."""
    block = f"{BEGIN} m -->\n# rules\n{END}"
    personal = "\n\n# Личное\n\n- Отвечай на русском; `/review`, `/test` - статусы в полном тексте.\n"
    pin = hashlib.sha256(personal.encode("utf-8")).hexdigest()
    cases = [
        ("personal data passes", personal, "", 0),
        ("pinned approved text passes", personal, pin, 0),
        ("one added rule breaks the pin", personal + "- Всегда начинай с плана.\n", pin, 1),
        ("routing skill outside", personal + "- Каждую задачу - через `/task`.\n", "", 1),
        ("override in any case", personal + "# Override of the ITD block\n", "", 1),
        ("old ritual outside", "Первая строка: `Скилл: /x`; SKILL_BYPASS: <reason>\n", "", 2),
        ("old MANDATORY title outside", "# Methodology (MANDATORY)\n", "", 1),
        ("CRLF copy of the approved text breaks the pin", personal.replace("\n", "\r\n"), pin, 1),
        ("invalid UTF-8 outside", personal.encode("utf-8") + b"\xff\n", "", 1),
        ("invalid UTF-8 is not pinned as U+FFFD", personal.encode("utf-8") + b"\xff",
         hashlib.sha256((personal + "\ufffd").encode("utf-8")).hexdigest(), 1),
    ]
    failed = 0
    for label, rest, expected_pin, expected in cases:
        raw = rest if isinstance(rest, bytes) else rest.encode("utf-8")
        found = layer_problems(outside_block(block.encode("utf-8") + raw), expected_pin)
        ok = len(found) == expected
        failed += not ok
        print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"  - {found}"))
    print(f"{len(cases) - failed} passed, {failed} failed")
    return 1 if failed else 0


def sha256_hex(text: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise argparse.ArgumentTypeError("must be 64 lowercase hex characters")
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wsl-home", type=Path)
    parser.add_argument("--windows-home", type=Path)
    parser.add_argument("--personal-sha256", type=sha256_hex)
    parser.add_argument("--self-test", action="store_true", help="check the marker and pin rules only")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    try:
        details = check((args.wsl_home or Path.home()).absolute(),
                        (args.windows_home or release.windows_home()).absolute(), args.personal_sha256 or "")
    except (release.ReleaseError, OSError, ValueError, UnicodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "PASSED", **details}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
