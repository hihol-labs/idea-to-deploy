#!/usr/bin/env python3
"""verify_no_bare_python3.py — positional-гейт: в bash/sh-фенсах skills/**/*.md
нет голого `python3`/`python`-вызова (v1.83.0, retro 2026-07-11 P2).

Порядок: на Windows Git Bash `python`/`python3` указывают на WindowsApps-шим
(Store-заглушку) — вызов падает (exit 49) либо, под пайпом, молча отдаёт мусор
(live-инцидент 2026-07-11: Step 1 /retro печатал «Python» вместо скана).
Функциональные вызовы python-скриптов в сниппетах идут ТОЛЬКО через запускатель
`skills/_shared/itd_py.sh`; осознанно-легитимные исключения (fallback-цепочки
до `py -3`/`/tmp`, команды под окружение проекта пользователя, probes)
помечаются маркером `win-ok` на той же строке.

Скоуп: fenced-блоки ```bash / ```sh / ```shell / ``` (без языка) в skills/**/*.md.
ASCII-safe вывод, stdlib only. Exit 0 — чисто, 1 — есть голые вызовы, 2 — сбой.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"

FENCE_OPEN_RE = re.compile(r"^```([A-Za-z0-9_-]*)\s*$")
SHELL_LANGS = {"", "bash", "sh", "shell", "console"}
# голый интерпретатор: python/python3 как команда (после начала строки, |, ;,
# &&, ||, $(, ` или пробела), не часть пути/слова
BARE_RE = re.compile(r"(^|[\s;|&`(])(python3?)(\s|$)")


def scan_file(md: Path) -> list[str]:
    hits: list[str] = []
    in_fence = False
    fence_lang = ""
    try:
        lines = md.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"cannot read {md}: {exc}")
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if not in_fence:
            m = FENCE_OPEN_RE.match(stripped)
            if m:
                in_fence = True
                fence_lang = m.group(1).lower()
            continue
        if stripped.startswith("```"):
            in_fence = False
            fence_lang = ""
            continue
        if fence_lang not in SHELL_LANGS:
            continue
        if "win-ok" in line or "itd_py.sh" in line:
            continue
        if stripped.startswith("#"):
            continue
        if BARE_RE.search(line):
            rel = md.relative_to(ROOT).as_posix()
            hits.append(f"{rel}:{lineno}: {stripped[:110]}")
    return hits


def main() -> int:
    if not SKILLS.is_dir():
        print("FAIL: skills/ not found")
        return 2
    fails: list[str] = []
    n_files = 0
    for md in sorted(SKILLS.rglob("*.md")):
        n_files += 1
        try:
            fails.extend(scan_file(md))
        except RuntimeError as exc:
            print(f"FAIL: {exc}")
            return 2
    if fails:
        print(f"FAIL verify_no_bare_python3: {len(fails)} bare python call(s) "
              f"in fenced shell blocks (use skills/_shared/itd_py.sh or mark win-ok):")
        for f in fails:
            print("  " + f)
        return 1
    print(f"PASS verify_no_bare_python3: {n_files} md files scanned, 0 bare python calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
