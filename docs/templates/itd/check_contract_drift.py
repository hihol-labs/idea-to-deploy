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

Второй режим `--filled` (v1.67.0, init-audit gap #3): заполненность КЛЮЧЕВЫХ
контрактов. Скаффолд с шаблонными плейсхолдерами («Replace this line with…»,
пустой commands[]) — это не связывающий контракт, а декорация; /review Stage A
использует этот режим как Important-check I10: filled / TEMPLATE / MISSING по
FORBIDDEN_CHANGES.md, SCOPE_LOCK.md, VERIFICATION_CONTRACT.json.

Usage:
  python3 .itd/check_contract_drift.py [--strict] [--filled] [--selftest]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITD_DIR = ROOT / ".itd"
CLAUDE_MD = ROOT / "CLAUDE.md"
MARKER_RE = re.compile(r"снапшот\s*@\s*([0-9a-f]{7,40})", re.I)

# --filled: ключевые контракты и маркер шаблонного плейсхолдера
KEY_CONTRACTS = ("FORBIDDEN_CHANGES.md", "SCOPE_LOCK.md", "VERIFICATION_CONTRACT.json")
PLACEHOLDER_RE = re.compile(r"Replace this line with", re.I)


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


def filled_status(name: str, text: str) -> str:
    """filled | template | empty — чистая, тестируемая логика заполненности.

    .md: наличие шаблонного плейсхолдера => template.
    VERIFICATION_CONTRACT.json: пустой commands[] (или битый JSON) => template —
    контракт без единой исполняемой команды ничего не верифицирует.
    """
    if not text.strip():
        return "empty"
    if name.endswith(".json"):
        try:
            data = json.loads(text)
        except Exception:
            return "template"
        if name == "VERIFICATION_CONTRACT.json":
            return "filled" if isinstance(data, dict) and data.get("commands") else "template"
        return "filled"
    return "template" if PLACEHOLDER_RE.search(text) else "filled"


def run_filled(strict: bool) -> int:
    if not ITD_DIR.is_dir():
        print("SKIP: .itd/ не найден — заполненность не проверяется."); return 0
    gaps: list[str] = []
    for name in KEY_CONTRACTS:
        p = ITD_DIR / name
        if not p.is_file():
            print(f" MISS   {name}")
            gaps.append(name)
            continue
        try:
            status = filled_status(name, p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            status = "empty"
        tag = {"filled": "  ok  ", "template": " TMPL ", "empty": " EMPT "}[status]
        print(f"{tag}  {name}")
        if status != "filled":
            gaps.append(name)
    print()
    if gaps:
        print(f"НЕ ЗАПОЛНЕНО ({len(gaps)}): {', '.join(gaps)} — шаблон с плейсхолдерами "
              "не является связывающим контрактом.")
        print("FIX: заполни project-специфичные секции (Forbidden Changes / Scope Lock / "
              "commands[] в VERIFICATION_CONTRACT.json) или осознанно удали .itd/.")
    else:
        print("Ключевые контракты заполнены.")
    return 1 if (strict and gaps) else 0


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

    filled_cases = [
        ("SCOPE_LOCK.md", "## Current Task\n- Replace this line with the current task.", "template"),
        ("SCOPE_LOCK.md", "## Current Task\n- Починить init-валидатор.", "filled"),
        ("FORBIDDEN_CHANGES.md", "", "empty"),
        ("VERIFICATION_CONTRACT.json", '{"commands": []}', "template"),
        ("VERIFICATION_CONTRACT.json", '{"commands": [{"id": "t", "command": "make test"}]}', "filled"),
        ("VERIFICATION_CONTRACT.json", "{broken", "template"),
    ]
    for name, text, exp in filled_cases:
        got = filled_status(name, text)
        p = got == exp
        ok = ok and p
        print(("  OK  " if p else " FAIL "), f"filled_status({name!r}, …) -> {got!r}", "" if p else f"(exp {exp!r})")

    print("SELFTEST:", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Детектор дрейфа и заполненности .itd-контрактов.")
    ap.add_argument("--strict", action="store_true", help="exit 1 при DRIFT / незаполненности")
    ap.add_argument("--filled", action="store_true", help="проверить заполненность ключевых контрактов")
    ap.add_argument("--selftest", action="store_true", help="проверить чистую логику")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())
    sys.exit(run_filled(args.strict) if args.filled else run_check(args.strict))


if __name__ == "__main__":
    main()
