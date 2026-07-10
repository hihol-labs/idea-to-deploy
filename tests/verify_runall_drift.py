#!/usr/bin/env python3
"""verify_runall_drift.py — дрифт-гард tests/run-all.sh ↔ CI-workflow (v1.79.1).

Упражнение «knowledge visibility gap» (2026-07-10) закрыло гэп «как прогнать
всё локально» скриптом tests/run-all.sh, зеркалящим оба workflow. Зеркало,
синхронизируемое руками, молча протухает: тест добавили в workflow — локальный
«DONE fails:none» перестаёт означать зелёный CI. Этот гард делает протухание
ГРОМКИМ: каждая verify-проверка, на которую ссылаются
.github/workflows/{meta-review,windows-verify}.yml, обязана присутствовать в
tests/run-all.sh.

Направление строгое одно: CI ⊆ run-all (обратное — run-all строже CI —
допустимо и лишь репортится). Anti-rot: парсер, ничего не нашедший, — это
false-green, поэтому минимальные счётчики распарсенного зашиты assert'ами.

Stdlib-only, кросс-платформенный (гоняется и в windows-verify).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = [
    ROOT / ".github" / "workflows" / "meta-review.yml",
    ROOT / ".github" / "workflows" / "windows-verify.yml",
]
RUNALL = ROOT / "tests" / "run-all.sh"

# Скрипты, чей запуск в run-all.sh оформлен не именем в CORE/FULL, а явной
# строкой — маппинг «имя из workflow» → регэксп присутствия в run-all.sh.
SPECIAL = {
    "verify_skill_profiles": r"scripts/verify_skill_profiles\.py",
    "verify-sync-to-active": r"scripts/verify-sync-to-active\.sh",
    "verify_snapshot": r"tests/verify_snapshot\.py --all",
    "meta_review": r"\bmeta_review\b",
}

# Осознанно НЕ требуем в run-all.sh (недоступно/не имеет смысла локально):
EXCLUDED: set = set()

passed = failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global passed, failed
    print("%s  %s%s" % ("PASS" if cond else "FAIL", name,
                        ("  [%s]" % detail) if detail and not cond else ""))
    if cond:
        passed += 1
    else:
        failed += 1


def ci_referenced() -> set:
    """Имена проверок (без .py), которые реально запускают workflow'ы."""
    names: set = set()
    rx = re.compile(
        r"run:\s*(?:python3?|py -3)?\s*"
        r"(?:bash\s+)?((?:tests|scripts)/[\w./-]+?\.(?:py|sh))")
    for wf in WORKFLOWS:
        text = wf.read_text(encoding="utf-8")
        for m in rx.finditer(text):
            stem = Path(m.group(1)).name
            stem = stem[:-3] if stem.endswith(".py") else stem[:-3]
            names.add(stem)
    return names - EXCLUDED


def runall_covered() -> set:
    """Имена проверок, которые запускает tests/run-all.sh."""
    text = RUNALL.read_text(encoding="utf-8")
    names = set(re.findall(r"\bverify_\w+\b", text))
    names.add("meta_review")
    for name, pat in SPECIAL.items():
        if re.search(pat, text):
            names.add(name)
    return names


def main() -> int:
    ci = ci_referenced()
    local = runall_covered()

    # anti-rot: парсер обязан находить нетривиальные множества
    check("parser: CI references >= 25 checks", len(ci) >= 25,
          "parsed only %d" % len(ci))
    check("parser: run-all covers >= 30 checks", len(local) >= 30,
          "parsed only %d" % len(local))

    missing = sorted(ci - local)
    check("every CI check is present in tests/run-all.sh", not missing,
          "missing from run-all.sh: %s" % missing)

    extra = sorted(local - ci)
    if extra:
        print("[info] run-all.sh runs extra (stricter than CI, OK):", extra)

    # самореференс: гард сам зарегистрирован и в CI, и в run-all
    check("this guard is wired into CI", "verify_runall_drift" in ci)
    check("this guard is wired into run-all.sh", "verify_runall_drift" in local)

    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
