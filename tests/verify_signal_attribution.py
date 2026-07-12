#!/usr/bin/env python3
"""Behavioural proof: signal unit-attribution + anti-FP classification
(v1.89.0, GO-002 — «атрибуция session/unit + достоверность классификации»).

  - unwrap_shell снимает wsl/sh -c обёртки
  - commit В ОБЁРТКЕ wsl -> None (не test_run; закрывает live-FP «commit=test»)
  - реальный тест в обёртке -> сигнал остаётся (unwrap не ломает детект)
  - команда над benchmarks/fixtures/review-evalset -> None (OOM-фикстура не сигнал)
  - append_signal проставляет sig["unit"] из GOAL.currentUnitId активной цели
  - без активной цели / чужой cwd — поле unit отсутствует (не мусорит)

Self-contained, stdlib only. Run: python3 tests/verify_signal_attribution.py
"""
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "hooks"))
import completion_lib as cl  # noqa: E402

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
    # unwrap
    inner = cl.unwrap_shell("wsl.exe -e sh -c 'git add x && git commit -m y'")
    check("unwrap wsl.exe -e sh -c", inner.startswith("git add"), inner)
    inner = cl.unwrap_shell('wsl bash -lc "pytest -q"')
    check("unwrap wsl bash -lc", inner == "pytest -q", inner)

    # commit в обёртке -> None (главный FP сет-4)
    s = cl.classify_bash("wsl.exe -e sh -c 'cd /r && git add . && git commit -m \"feat: x\"'",
                         {"stdout": "1 file changed", "exitCode": 0})
    check("commit-в-wsl -> None (не test_run)", s is None, str(s))

    # реальный тест в обёртке -> сигнал остаётся
    s = cl.classify_bash("wsl.exe -e sh -c 'cd /r && pytest -q'",
                         {"stdout": "3 passed", "exitCode": 0})
    check("тест-в-wsl -> test_run L2 pass", s and s["kind"] == "test_run" and s["outcome"] == "pass", str(s))

    # корпус методологии suppress -> None (узкие пути, не generic fixtures/)
    for cmd in [
        "node benchmarks/review-evalset/run.mjs",
        "python3 tests/../review-evalset/x.py",
        "cat benchmarks/fixtures/oom-sample.ts",
    ]:
        s = cl.classify_bash(cmd, {"stdout": "FAILED out of memory", "exitCode": 0})
        check(f"suppress корпус: {cmd[:32]}", s is None, str(s))

    # ЧУЖИЕ тестовые фикстуры/данные НЕ подавляются (ревью v1.89.0 #2):
    # generic-сегменты fixtures/testdata встречаются в обычных сьютах.
    s = cl.classify_bash("pytest tests/unit --fixtures-dir=tests/fixtures", {"stdout": "3 passed", "exitCode": 0})
    check("чужой tests/fixtures НЕ подавлен", s is not None and s["kind"] == "test_run", str(s))
    s = cl.classify_bash("jest --testPathPattern=src/__fixtures__", {"stdout": "5 passed", "exitCode": 0})
    check("чужой __fixtures__ НЕ подавлен", s is not None and s["kind"] == "test_run", str(s))

    # обычный тест НЕ подавляется
    s = cl.classify_bash("pytest tests/test_api.py", {"stdout": "3 passed", "exitCode": 0})
    check("обычный тест не подавлен", s is not None and s["kind"] == "test_run", str(s))

    # append_signal: unit из активной цели
    with tempfile.TemporaryDirectory() as td:
        mem = Path(td) / ".itd-memory"
        mem.mkdir()
        (mem / "GOAL.json").write_text(json.dumps({
            "version": 1, "goal": "g", "status": "active", "currentUnitId": "GO-002",
            "units": [{"id": "GO-002", "criterion": "c", "verificationCommand": "true",
                       "status": "in_progress"}],
        }), encoding="utf-8")
        sig = cl.classify_bash("pytest -q", {"stdout": "3 passed", "exitCode": 0})
        cl.append_signal(Path(td), "sess1", sig)
        rows = [json.loads(l) for l in (Path(td) / ".claude" / "completion" / "signals.jsonl")
                .read_text(encoding="utf-8").splitlines() if l.strip()]
        check("append_signal: unit=GO-002 из активной цели",
              rows and rows[-1].get("unit") == "GO-002", str(rows))

    # без активной цели -> нет поля unit
    with tempfile.TemporaryDirectory() as td:
        sig = cl.classify_bash("pytest -q", {"stdout": "3 passed", "exitCode": 0})
        cl.append_signal(Path(td), "sess2", sig)
        rows = [json.loads(l) for l in (Path(td) / ".claude" / "completion" / "signals.jsonl")
                .read_text(encoding="utf-8").splitlines() if l.strip()]
        check("без цели -> нет unit-поля", rows and "unit" not in rows[-1], str(rows))

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
