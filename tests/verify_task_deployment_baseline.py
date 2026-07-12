#!/usr/bin/env python3
"""Proof: /task Step 3f carries a default deployment baseline (v1.89.0, GO-005 —
«качество без контракта: базлайн»).

Статическая проверка: SKILL.md шага 3f содержит дефолтную deployment-планку
со всеми ключевыми требованиями, применяемую БЕЗ явного Sprint Contract.
(Живой A/B-эффект оценивается отдельно судьёй — здесь фиксируем, что планка
присутствует как часть конвейера, а не разовая инструкция.)

Run: python3 tests/verify_task_deployment_baseline.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "task" / "SKILL.md"

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        FAIL += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def main():
    t = SKILL.read_text(encoding="utf-8")
    seg = t[t.index("Step 3f"):] if "Step 3f" in t else t
    check("шаг 3f содержит Deployment baseline", "Deployment baseline" in seg)
    # ключевые требования планки присутствуют
    for token, label in [
        ("Exit-семантика", "exit-семантика"),
        ("Diff-scoped", "diff-scoped/no-op"),
        ("Actionable", "actionable-вывод"),
        ("Тихий успех", "тихий успех"),
        ("Zero-dep", "zero-dep"),
        ("Самопроб", "самопроба"),
    ]:
        check(f"планка: {label}", token in seg, f"'{token}' не найден")
    check("планка применяется без явного контракта",
          "БЕЗ" in seg and "Task Contract" in seg and "по умолчанию" in seg)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
