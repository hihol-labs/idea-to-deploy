#!/usr/bin/env python3
"""Doc-contract: declared-source read contract — no silent continuation (v1.77.0).

Pins helpers §11 (retro 2026-07-10 candidate #2): a subagent that cannot read
a DECLARED mandatory source must answer READ_FAILED instead of silently
completing the task from other sources, and dispatchers must dictate that
refusal in the thin prompt. Evidence behind the rule: 6/21 silent
substitutions in the 2026-07-10 lost-in-the-middle measurement, 0/6 after the
refusal instruction was added to the prompt.

Self-contained, stdlib only. Run: python3 tests/verify_source_read_contract.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / "skills" / "_shared" / "helpers.md"

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def has_all(hay: str, *needles: str) -> bool:
    low = hay.lower()
    return all(n.lower() in low for n in needles)


def slice_section(raw: str, start: str, end: str) -> str:
    i = raw.find(start)
    if i == -1:
        return ""
    j = raw.find(end, i)
    return raw[i:] if j == -1 else raw[i:j]


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if not HELPERS.is_file():
        print("FAIL  helpers.md missing")
        return 1
    raw = HELPERS.read_text(encoding="utf-8", errors="replace")

    s11 = slice_section(raw, "## 11. Declared-source read contract", "\n## 12.")
    check("helpers §11: section exists", bool(s11))
    check("helpers §11: READ_FAILED marker with path is the refusal contract",
          has_all(s11, "READ_FAILED: <путь>"))
    check("helpers §11: subagent must NOT complete from other sources",
          has_all(s11, "НЕ выполняй задачу из других источников"))
    check("helpers §11: dispatcher dictates the refusal verbatim",
          has_all(s11, "ответь ровно READ_FAILED"))
    check("helpers §11: dispatcher marks the source as mandatory",
          has_all(s11, "ЕДИНСТВЕННЫЙ источник"))
    check("helpers §11: READ_FAILED answer is not accepted as the result",
          has_all(s11, "не принимается как результат"))
    check("helpers §11: grounded in the 2026-07-10 measurement (both numbers)",
          has_all(s11, "6 из 21") and has_all(s11, "6/6"))

    s8 = slice_section(raw, "## 8. Delegation Intent Template", "\n## 9.")
    check("helpers §8: delegation template cross-references §11",
          has_all(s8, "Declared-source contract") and has_all(s8, "§11"))

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
