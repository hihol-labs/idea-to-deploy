#!/usr/bin/env python3
"""Детектор дрейфа производных .itd-контрактов от источника истины (CLAUDE.md).

Проблема (упр. 3 аудита idea-to-deploy): файлы .itd/*.md — ПРОИЗВОДНЫЕ копии
правил из проектного CLAUDE.md. CLAUDE.md уходит вперёд, копии молча устаревают
и начинают вводить в заблуждение по деталям. Единственный источник истины —
CLAUDE.md; эта проверка делает рассинхрон ВИДИМЫМ, а не тихим.

Механика (вендор-нейтральная, stdlib-only):
  - Каждый производный док несёт маркер «снапшот @ <sha>» (короткий git-sha
    коммита CLAUDE.md, с которого он синхронизирован).
  - Проверка берёт последний коммит, тронувший CLAUDE.md, и сравнивает.
    marker == current  -> ok (в синхроне)
    marker != current  -> DRIFT (CLAUDE.md изменился с момента снапшота)
    нет маркера         -> UNMARKED (производная копия вне трекинга)

Advisory по умолчанию (exit 0). `--strict` -> exit 1 при любом DRIFT (для гейта/
хука). `--selftest` -> проверяет чистую логику сравнения без git. Никогда не
роняет сессию: git недоступен / не git-репо -> печатает и exit 0.

Usage:
  python3 .itd/check_contract_drift.py [--strict] [--selftest]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITD_DIR = ROOT / ".itd"
CLAUDE_MD = ROOT / "CLAUDE.md"
MARKER_RE = re.compile(r"снапшот\s*@\s*([0-9a-f]{7,40})", re.I)


def compare_sha(marker: str, current: str) -> str:
    """ok | drift | unmarked — чистая, тестируемая логика сравнения."""
    if not marker:
        return "unmarked"
    m, c = marker.lower(), current.lower()
    if m == c or c.startswith(m) or m.startswith(c):
        return "ok"
    return "drift"


def current_claude_sha() -> str | None:
    """Короткий sha последнего коммита, тронувшего CLAUDE.md (или None)."""
    try:
        res = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--", "CLAUDE.md"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=6,
        )
        sha = res.stdout.strip()
        return sha or None
    except Exception:
        return None


def marker_in(path: Path) -> str:
    try:
        m = MARKER_RE.search(path.read_text(encoding="utf-8", errors="replace"))
        return m.group(1) if m else ""
    except Exception:
        return ""


def run_check(strict: bool) -> int:
    if not CLAUDE_MD.is_file():
        print("SKIP: CLAUDE.md не найден — нечего сверять."); return 0
    current = current_claude_sha()
    if current is None:
        print("SKIP: git недоступен или не git-репо — дрейф не проверяется (advisory)."); return 0

    print(f"CLAUDE.md @ {current} (последний коммит источника истины)")
    drift, unmarked = [], []
    for md in sorted(ITD_DIR.glob("*.md")):
        status = compare_sha(marker_in(md), current)
        tag = {"ok": "  ok  ", "drift": " DRIFT", "unmarked": " unmk "}[status]
        print(f"{tag}  {md.name}  (маркер: {marker_in(md) or '—'})")
        if status == "drift":
            drift.append(md.name)
        elif status == "unmarked":
            unmarked.append(md.name)

    print()
    if drift:
        print(f"ДРЕЙФ ({len(drift)}): {', '.join(drift)} — CLAUDE.md изменился с момента снапшота.")
        print("FIX: пересверь эти доки с CLAUDE.md и обнови маркер «снапшот @ <sha>».")
    if unmarked:
        print(f"Без маркера ({len(unmarked)}): {', '.join(unmarked)} — вне трекинга дрейфа (опц. добавить маркер).")
    if not drift and not unmarked:
        print("Все производные .itd-доки в синхроне с CLAUDE.md.")
    return 1 if (strict and drift) else 0


def selftest() -> int:
    cases = [
        ("8d4fd43", "8d4fd43", "ok"),
        ("8d4fd43", "8d4fd43abc9", "ok"),      # marker короче — префикс
        ("8d4fd43abc9", "8d4fd43", "ok"),      # current короче — префикс
        ("8d4fd43", "abc1234", "drift"),
        ("", "8d4fd43", "unmarked"),
    ]
    ok = True
    for marker, current, exp in cases:
        got = compare_sha(marker, current)
        p = got == exp
        ok = ok and p
        print(("  OK  " if p else " FAIL "), f"compare_sha({marker!r},{current!r}) -> {got!r}", "" if p else f"(exp {exp!r})")
    print("SELFTEST:", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Детектор дрейфа .itd-контрактов от CLAUDE.md.")
    ap.add_argument("--strict", action="store_true", help="exit 1 при DRIFT")
    ap.add_argument("--selftest", action="store_true", help="проверить логику сравнения")
    args = ap.parse_args()
    sys.exit(selftest() if args.selftest else run_check(args.strict))


if __name__ == "__main__":
    main()
