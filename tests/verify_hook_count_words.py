#!/usr/bin/env python3
"""Regression pin for the M-C15 spelled-number parser (v1.53.0, retro P2).

M-C15 (in meta_review.py) checks that hook counts written in prose match the
real hook count. Two live incidents motivated widening its number vocabulary:
  * «семнадцать хуков» (17) sat stale in README.ru through v1.49/v1.50 — the
    old parser only knew 1-9, so a teen count slipped past the guard;
  * «двадцать четыре хука» was misread as «четыре» = 4 (compound not handled),
    producing a false BLOCK in v1.51.0.

This test drives the module-level `num_ru` / `num_en` parsers directly, pinning
teen + twenties + compound behaviour and the "not a hook context" guard.

Self-contained, stdlib only. Run: python3 tests/verify_hook_count_words.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("_mr", ROOT / "tests" / "meta_review.py")
mr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mr)  # type: ignore

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def main() -> int:
    # Russian
    ru = [
        ("семнадцать", 17),      # incident A: the teen that slipped stale
        ("двадцать четыре", 24),  # incident B: compound (was misread as 4)
        ("двадцать", 20),
        ("двадцать один", 21),
        ("четыре", 4),
        ("девять", 9),
        ("тридцать", 30),
        ("десять", 10),
        ("девятнадцать", 19),
    ]
    for phrase, exp in ru:
        check(f"num_ru('{phrase}') == {exp}", mr.num_ru(phrase) == exp,
              f"got {mr.num_ru(phrase)}")
    check("num_ru('банан') is None (not a number)", mr.num_ru("банан") is None)

    # English
    en = [
        ("seventeen", 17),
        ("twenty-four", 24),   # hyphenated compound
        ("twenty four", 24),   # spaced compound
        ("twenty", 20),
        ("four", 4),
        ("thirty", 30),
        ("nineteen", 19),
    ]
    for phrase, exp in en:
        check(f"num_en('{phrase}') == {exp}", mr.num_en(phrase) == exp,
              f"got {mr.num_en(phrase)}")
    check("num_en('banana') is None (not a number)", mr.num_en("banana") is None)

    # Over-match guard: the word-regexes REQUIRE a hook-word after the number,
    # so a spelled number followed by any other noun (hours/часа) never fires
    # the count check. This is the guard that keeps M-C15 from flagging
    # «двадцать четыре часа» / "twenty-four hours" as a stale hook count.
    check("RU regex matches «двадцать четыре хука»",
          mr.HOOK_RU_WORD_RE.search("итого двадцать четыре хука в наборе") is not None)
    check("RU regex GUARD: «двадцать четыре часа» does NOT match (24 hours)",
          mr.HOOK_RU_WORD_RE.search("прошло двадцать четыре часа") is None)
    check("EN regex matches 'twenty-four hooks'",
          mr.HOOK_EN_WORD_RE.search("there are twenty-four hooks now") is not None)
    check("EN regex GUARD: 'twenty-four hours' does NOT match (24 hours)",
          mr.HOOK_EN_WORD_RE.search("waited twenty-four hours") is None)

    print("\n%d passed, %d failed" % (PASSED, FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
