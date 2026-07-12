#!/usr/bin/env python3
"""Behavioural proof: signal classes v1.88.0 (GP-002, «пункт 1: сбор
рантайм-сигналов» — жизненный цикл / поток данных / ресурсы / контекст ошибки).

Asserts via completion_lib.classify_bash and the hook binary:

  - every signal carries "class" (verification / lifecycle / data_flow / resource)
  - app_start output markers -> phase startup|ready|shutdown
  - OOM / max_memory_restart in output -> resource anomaly, never "pass"
  - unclassified command with OOM output -> dedicated resource signal (layer 0)
  - failed signal carries error_tail (full error context, not just a message)
  - additive safety: compute_verdict blocks/passes exactly as before

Self-contained, stdlib only. Run: python3 tests/verify_completion_signal_classes.py
"""
import sys
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
    # 1) verification class на тестовом прогоне
    s = cl.classify_bash("pytest -q", {"stdout": "3 passed", "exitCode": 0})
    check("test_run -> class verification", s and s.get("class") == "verification", str(s))

    # 2) lifecycle: startup / ready / shutdown по маркерам вывода
    s = cl.classify_bash("npm run dev", {"stdout": "ready in 1.2s\nLocal: http://localhost:3000", "exitCode": 0})
    check("app_start ready", s and s.get("class") == "lifecycle" and s.get("phase") == "ready", str(s))
    s = cl.classify_bash("npm run start", {"stdout": "booting...", "exitCode": 0})
    check("app_start startup (нет ready-маркера)", s and s.get("phase") == "startup", str(s))
    s = cl.classify_bash("docker compose up", {"stdout": "received SIGTERM\nserver closed", "exitCode": 0})
    check("app_start shutdown", s and s.get("phase") == "shutdown", str(s))

    # 3) data_flow / resource классы учётных сигналов
    s = cl.classify_bash("npx prisma migrate deploy", {"stdout": "applied", "exitCode": 0})
    check("side_effect -> data_flow", s and s.get("class") == "data_flow", str(s))
    s = cl.classify_bash("docker compose down", {"stdout": "removed", "exitCode": 0})
    check("cleanup -> resource", s and s.get("class") == "resource", str(s))

    # 4) ресурсная аномалия — аннотация, НЕ мутация outcome (ревью v1.88.0):
    # зелёный прогон с упоминанием OOM в логе остаётся pass; реальный OOM
    # приносит exit != 0 и красен сам по себе.
    s = cl.classify_bash("npm test", {"stdout": "log: prior run died out of memory; 5 passed", "exitCode": 0})
    check("OOM-упоминание при exit 0 -> pass + anomaly-аннотация",
          s and s.get("anomaly") == "memory" and s.get("outcome") == "pass", str(s))
    s = cl.classify_bash("npm test", {"stdout": "FATAL ERROR: JavaScript heap out of memory", "exitCode": 134})
    check("реальный OOM (exit 134) -> fail + anomaly",
          s and s.get("anomaly") == "memory" and s.get("outcome") == "fail", str(s))

    # 5) неклассифицируемая команда с OOM-выводом -> отдельный resource-сигнал L0
    s = cl.classify_bash("node scripts/heavy.js", {"stdout": "Killed\nout of memory", "exitCode": 137})
    check("OOM без раннера -> resource L0",
          s and s.get("kind") == "resource" and s.get("layer") == 0 and s.get("class") == "resource",
          str(s))

    # 6) обычная неклассифицируемая команда по-прежнему None (нет шума)
    s = cl.classify_bash("ls -la", {"stdout": "total 8", "exitCode": 0})
    check("ls не сигнал (нет шума)", s is None, str(s))

    # 7) полный контекст ошибки на fail
    long_out = "\n".join(f"line{i}" for i in range(20)) + "\nAssertionError: boom"
    s = cl.classify_bash("pytest -q", {"stdout": long_out, "exitCode": 1})
    check("fail несёт error_tail с хвостом вывода",
          s and "AssertionError: boom" in s.get("error_tail", "") and "line19" in s.get("error_tail", ""),
          str(s)[:200])
    s = cl.classify_bash("pytest -q", {"stdout": "5 passed", "exitCode": 0})
    check("pass без error_tail", s and "error_tail" not in s, str(s))

    # 8) аддитивная безопасность: вердикт по слоям не изменился
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        sigs = [
            cl.classify_bash("tsc --noEmit; echo EXIT: 0", {"stdout": "EXIT: 0", "exitCode": 0}),
            cl.classify_bash("pytest -q", {"stdout": "3 passed", "exitCode": 0}),
        ]
        v = cl.compute_verdict(Path(td), sigs)
        check("verdict: зелёные L1+L2 не блокируют", not v.get("blocked"), str(v)[:200])
        sigs.append(cl.classify_bash("pytest -q", {"stdout": "1 failed", "exitCode": 1}))
        v = cl.compute_verdict(Path(td), sigs)
        check("verdict: красный L2 блокирует как раньше", v.get("blocked"), str(v)[:200])

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
