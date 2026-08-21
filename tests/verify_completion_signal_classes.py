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

    # 9) A2 (LPD-002 debts): display/write-команды — не runtime-сигнал, даже
    # когда строка матчит проектный L2-паттерн; идентичность «latest-на-команду»
    # нормализуется (display-хвосты пайпа не делают команду другой); красный от
    # чужого HEAD — стейл, не вечный блок.
    import json as _json
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        (proj / ".claude" / "completion").mkdir(parents=True)
        (proj / ".claude" / "completion" / "config.json").write_text(_json.dumps(
            {"l2_evidence_patterns": ["tests/run-all\\.sh"]}), encoding="utf-8")
        s9 = cl.classify_bash("grep -n case tests/run-all.sh",
                              {"stdout": "42: esac", "exitCode": 0}, cwd=proj)
        check("A2: display-команда (grep по файлу из L2-паттерна) — не сигнал",
              s9 is None, str(s9))
        s9 = cl.classify_bash(
            "cat >> HANDOFF.md <<'EOF'\nbash tests/run-all.sh FAILED\nEOF",
            {"stdout": "", "exitCode": 0}, cwd=proj)
        check("A2: heredoc-запись с текстом про тесты — не сигнал",
              s9 is None, str(s9))
        s9 = cl.classify_bash("bash tests/run-all.sh --quick",
                              {"stdout": "DONE fails:none", "exitCode": 0}, cwd=proj)
        check("A2: настоящий прогон run-all остаётся сигналом L2/pass",
              bool(s9) and s9.get("layer") == 2 and s9.get("outcome") == "pass",
              str(s9))
        s9 = cl.classify_bash("bash tests/run-all.sh 2>&1 | tail -2",
                              {"stdout": "DONE fails:none", "exitCode": 0}, cwd=proj)
        check("A2: пайп с display-хвостом сохраняет сигнал",
              bool(s9) and s9.get("layer") == 2, str(s9))

    k1 = cl.normalize_command_key("bash tests/run-all.sh 2>&1 | tail -2")
    k2 = cl.normalize_command_key("bash tests/run-all.sh | grep -E 'DONE|FAIL' | head -3")
    k3 = cl.normalize_command_key("bash tests/run-all.sh")
    check("A2: display-хвост пайпа не меняет идентичность команды",
          k1 == k2 == k3, f"{k1!r} {k2!r} {k3!r}")
    check("A2: разные команды остаются разными ключами",
          cl.normalize_command_key("pytest -q tests/a.py")
          != cl.normalize_command_key("pytest -q tests/b.py"))
    check("A2: '>' внутри кавычек — часть команды, не редирект",
          cl.normalize_command_key('pytest -k "x>5"')
          != cl.normalize_command_key('pytest -k "x>99"'),
          cl.normalize_command_key('pytest -k "x>5"'))
    check("A2: настоящий хвостовой редирект по-прежнему отбрасывается",
          cl.normalize_command_key("pytest -q > out.log 2>&1")
          == cl.normalize_command_key("pytest -q"))
    check("A2: awk с system() — не display (исполняет код)",
          cl.display_only_command("awk '{system(\"pytest\")}' list.txt") is False)
    check("A2: sed с s///e — не display (исполняет код)",
          cl.display_only_command("sed 's/x/pytest/e' f") is False)
    check("A2: обычные sed -n / awk-печать остаются display",
          cl.display_only_command("sed -n 10,20p tests/run-all.sh")
          and cl.display_only_command("awk '{print $1}' report.txt"))
    check("A2: путь с /e2e не считается exec-маркером sed",
          cl.display_only_command("sed -n 5p tests/e2e/run.sh"))
    s9x = cl.classify_bash("echo start && pytest tests/foo.py",
                           {"stdout": "1 failed", "exitCode": 1})
    check("A2: display-префикс с && не глотает настоящий прогон",
          bool(s9x) and s9x.get("layer") == 2 and s9x.get("outcome") == "fail",
          str(s9x))
    check("A2: цепочка display-стейтментов остаётся подавленной",
          cl.display_only_command("echo a; grep b f && tail -1 g"))
    check("A2: `cat x || pytest y` — не display",
          cl.display_only_command("cat x || pytest y") is False)
    check("A2: diff — verification-инструмент, не display",
          cl.display_only_command("diff expected.txt actual.txt") is False)
    check("A2: '0 failed' в тексте — не провал (долг: подстрока failed зеленит/краснит)",
          cl.outcome_from("=== 5 passed, 0 failed ===", None) != "fail"
          and cl.outcome_from("=== 5 passed, 0 failed ===", 0) == "pass")
    check("A2: верхнерегистровый FAILED остаётся провалом",
          cl.outcome_from("FAILED tests/test_x.py::test_y", None) == "fail"
          and cl.outcome_from("FAIL  some check", None) == "fail")
    s9y = cl.classify_bash("cat <<EOF\nnotes about tests failed\nEOF\npytest -q tests/x.py",
                           {"stdout": "1 failed", "exitCode": 1})
    check("A2: команда ПОСЛЕ heredoc-терминатора не глотается",
          bool(s9y) and s9y.get("layer") == 2 and s9y.get("outcome") == "fail",
          str(s9y))
    check("A2: heredoc с командой после терминатора — не display",
          cl.display_only_command("cat <<EOF\ndata failed\nEOF\npytest -q") is False)
    check("A2: heredoc-тело не режется на стейтменты",
          cl.display_only_command(
              "cat >> notes.md <<'EOF'\nbash tests/run-all.sh && pytest\nEOF"))
    check("A2: два heredoc'а в одной команде — оба тела display (hd-r1)",
          cl.display_only_command("cat <<A <<B\npytest inside\nA\nmore pytest\nB"))
    check("A2: два heredoc'а + реальная команда после обоих тел — не display (hd-r1)",
          cl.display_only_command("cat <<A <<B\nx\nA\ny\nB\npytest -q") is False)
    check("A2: отступленный псевдо-терминатор НЕ закрывает plain <<EOF (hd-r1)",
          cl.display_only_command("cat <<EOF\n  EOF\npytest hidden\nEOF"))
    check("A2: <<- закрывается таб-отступленным терминатором, хвост виден (hd-r1)",
          cl.display_only_command("cat <<-EOF\n\tdata\n\tEOF\npytest -q") is False)
    check("A2: делимитер с дефисом END-1 распознан — хвост после терминатора виден (PUB4)",
          cl.display_only_command("cat <<END-1\ndata\nEND-1\npytest -q") is False
          and cl.display_only_command("cat <<END-1\npytest inside\nEND-1"))
    check("A2: кавычный делимитер с дефисом <<'E-D' распознан (PUB4)",
          cl.display_only_command("cat <<'E-D'\nx\nE-D\npytest -q") is False)
    check("A2: делимитер с точкой EOF.txt распознан (PUB4)",
          cl.display_only_command("cat <<EOF.txt\nx\nEOF.txt\npytest -q") is False)
    check("A2: кавычный VAR-префикс с пробелами — display-голова распознана (PUB5)",
          cl.display_only_command('NOTE="test output pending" cat >> HANDOFF.md')
          and cl.classify_bash('NOTE="test output pending" cat >> HANDOFF.md',
                               {"stdout": "", "exitCode": 0}) is None)
    check("A2: кавычный VAR-префикс перед реальной командой — не display (PUB5)",
          cl.display_only_command('NOTE="a b" pytest -q') is False)
    check("A2: кавычный аргумент не подменяет голову сегмента (PUB5)",
          cl.display_only_command('grep "pytest failed" log.txt'))
    hs = cl.classify_bash('cat <<<"hello" && pytest -q',
                          {"stdout": "1 failed", "exitCode": 1})
    check("A2: here-string <<< не глотает цепочку — сигнал pytest жив (hd-r2)",
          bool(hs) and hs.get("layer") == 2 and hs.get("outcome") == "fail",
          str(hs))
    check("A2: here-string с display-цепочкой остаётся display (hd-r2)",
          cl.display_only_command('cat <<<"hello" && ls'))
    check("A2: экранированная кавычка не ломает чётность (разные команды != один ключ)",
          cl.normalize_command_key('pytest -k "x\\">5"')
          != cl.normalize_command_key('pytest -k "x\\">99"'),
          cl.normalize_command_key('pytest -k "x\\">5"'))

    red = {"ts": "t1", "kind": "test_run", "layer": 2, "outcome": "fail",
           "command": "bash tests/run-all.sh 2>&1 | grep FAIL", "evidence": "1 failed"}
    green = {"ts": "t2", "kind": "test_run", "layer": 2, "outcome": "pass",
             "command": "bash tests/run-all.sh | tail -1", "evidence": "DONE fails:none"}
    st, _ = cl._layer_status([red, green], 2)
    check("A2: зелёный повтор той же команды с другим display-хвостом вытесняет красный",
          st == "pass", st)
    other_red = dict(red, command="python3 -I tests/verify_x.py")
    st, _ = cl._layer_status([other_red, green], 2)
    check("A2: красный ДРУГОЙ команды зелёным не вытесняется",
          st == "fail", st)

    stale = dict(red, head="aaaa1111")
    st, _ = cl._layer_status([stale], 2, current_head="bbbb2222")
    check("A2: красный от чужого HEAD — стейл, слой не в fail",
          st != "fail", st)
    st, _ = cl._layer_status([stale], 2, current_head="aaaa1111")
    check("A2: красный на текущем HEAD блокирует как раньше",
          st == "fail", st)
    stale_pass = {"ts": "t3", "kind": "test_run", "layer": 2, "outcome": "pass",
                  "command": "pytest -q other.py", "head": "aaaa1111",
                  "evidence": "5 passed"}
    st, _ = cl._layer_status([stale, stale_pass], 2, current_head="bbbb2222")
    check("A2: стейл-fail + стейл-pass -> unknown, не false-green", st == "unknown", st)
    st, _ = cl._layer_status([stale_pass], 2, current_head="bbbb2222")
    check("A2: стейл-pass один не доказывает текущее дерево", st == "unknown", st)
    fresh_pass = dict(stale_pass, head="bbbb2222")
    st, _ = cl._layer_status([stale, fresh_pass], 2, current_head="bbbb2222")
    check("A2: свежий pass при стейл-fail даёт pass", st == "pass", st)
    fresh_fail = dict(red, head="bbbb2222")
    st, _ = cl._layer_status([fresh_fail, stale_pass], 2, current_head="bbbb2222")
    check("A2: свежий fail при стейл-pass блокирует", st == "fail", st)
    legacy = dict(red)  # без поля head — консервативно блокирует
    st, _ = cl._layer_status([legacy], 2, current_head="bbbb2222")
    check("A2: сигнал без head консервативно остаётся блокирующим",
          st == "fail", st)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
