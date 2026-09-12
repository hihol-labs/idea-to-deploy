#!/usr/bin/env python3
"""Behavioural proof for the completion-gate.sh hard gate (v1.51.0, Completion Gate).

Spawns hooks/completion-gate.sh with a real staged-source git repo and a
runtime-signal ledger, and asserts the actual blocking outcome:

  - a failed L2 (tests) signal  -> permissionDecision "deny" + exit 2 (VETO)
  - green L1+L2 signals          -> allow (exit 0, no deny)
  - no signals at all            -> degrade to advisory (exit 0, no deny)
  - reasoned COMPLETION_BYPASS    -> allow and append an audit event

This is the coverage proof required by verify_harness_map_fixtures.py so
completion-gate can be graded a hard gate. Self-contained, stdlib only.
Run: python3 tests/verify_completion_gate.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "hooks" / "completion-gate.sh"

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        FAIL += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, timeout=20)


def seed(cwd, rows):
    d = Path(cwd) / ".claude" / "completion"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "signals.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(dict(r, session="probe", ts="2026-07-06T12:00:00+00:00")) + "\n")


def seed_raw(cwd, rows):
    """Как seed(), но строки пишутся как есть — тест сам решает, что в них
    лежит (в частности, есть ли `producer`)."""
    d = Path(cwd) / ".claude" / "completion"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "signals.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def run_gate(cwd, command="git commit -m x", description="", env=None):
    payload = {"session_id": "probe", "cwd": str(cwd), "tool_name": "Bash",
               "tool_input": {"command": command, "description": description}}
    run_env = dict(os.environ)
    if env:
        run_env.update(env)
    p = subprocess.run([sys.executable, str(GATE)], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=30, env=run_env)
    try:
        out = json.loads(p.stdout) if p.stdout.strip() else {}
    except Exception:
        out = {}
    decision = (out.get("hookSpecificOutput") or {}).get("permissionDecision")
    return out, p.returncode, decision


def main():
    check("hooks/completion-gate.sh exists", GATE.exists())

    # --- v1.86.0: FIX_HINTS — классы из инцидент-корпуса (in-process) --------
    sys.path.insert(0, str(REPO / "hooks"))
    import completion_lib as cl
    hint_cases = [
        ("UnicodeEncodeError: 'charmap' codec can't encode character",
         "PYTHONIOENCODING"),
        ("Prisma P1001: Can't reach database server at localhost:5432, "
         "operation timed out", "DATABASE_URL"),
        ('ERROR: duplicate key value violates unique constraint "ux_docs"',
         "идемпотент"),
        ("update on table violates foreign key constraint fk_header",
         "FK-нарушение"),
        ('ERROR: column "apd.movement_type" does not exist (SQLSTATE 42703)',
         "information_schema"),
        ("ERROR: could not determine data type of parameter $3 (42P08)",
         "::type"),
        ("FATAL ERROR: JavaScript heap out of memory", "max-old-space-size"),
        ("Error: read ECONNRESET at TCP.onStreamRead", "таймаут"),
        ("413 Request Entity Too Large", "client_max_body_size"),
    ]
    for text, frag in hint_cases:
        check("fix_for hints: " + frag, frag in cl.fix_for(text),
              cl.fix_for(text))
    check("fix_for: unknown text falls back to generic hint",
          "корневую причину" in cl.fix_for("что-то пошло не так"))
    check("fix_for: specific class wins over generic timeout (order pin)",
          "DATABASE_URL" in cl.fix_for("P1001 connection timed out"))

    FAIL_L2 = [{"layer": 1, "outcome": "pass"},
               {"layer": 2, "kind": "test_run", "outcome": "fail", "command": "npm test",
                "evidence": "1 failed"}]
    GREEN = [{"layer": 1, "outcome": "pass"},
             {"layer": 2, "kind": "test_run", "outcome": "pass", "command": "npm test",
              "evidence": "5 passed"}]

    with tempfile.TemporaryDirectory() as tmp:
        git(tmp, "init")
        git(tmp, "config", "user.email", "t@t.t")
        git(tmp, "config", "user.name", "t")
        (Path(tmp) / "app.ts").write_text("export const x = 1\n", encoding="utf-8")
        git(tmp, "add", "app.ts")

        # 1) VETO: failed L2 + staged source -> deny + exit 2
        seed(tmp, FAIL_L2)
        out, rc, decision = run_gate(tmp)
        reason = (out.get("hookSpecificOutput") or {}).get("permissionDecisionReason", "")
        check("failed L2 -> permissionDecision deny", decision == "deny")
        check("failed L2 -> returncode == 2", rc == 2)
        check("deny reason carries a FIX hint", "FIX:" in reason)

        # 2) green layers -> allow
        seed(tmp, GREEN)
        out, rc, decision = run_gate(tmp)
        check("green layers -> not deny", decision != "deny", "decision=%r" % decision)
        check("green layers -> returncode 0", rc == 0)

        # 3) no signals -> degrade to advisory (allow)
        (Path(tmp) / ".claude" / "completion" / "signals.jsonl").unlink()
        out, rc, decision = run_gate(tmp)
        check("no signals -> degraded, not deny", decision != "deny" and rc == 0)

        # 4) conscious bypass -> allow even with failed signals
        #
        # RSI-DEBT-2. The audit row is durable, but it may NOT land in the
        # tracked ledger: this hook runs DURING `git commit`, so a row written
        # into `.itd-memory/events.jsonl` makes the working tree differ from
        # the candidate that was reviewed, and the exact-tree review gate then
        # refuses the very commit the bypass was granted for. The canonical
        # destination is the untracked append-only `completion-bypass.jsonl`;
        # ledger-close carries the rows into events.jsonl as its own step.
        seed(tmp, FAIL_L2)
        events = Path(tmp) / ".itd-memory" / "events.jsonl"
        events.parent.mkdir(parents=True, exist_ok=True)
        sentinel = '{"id": "evt-pre-existing", "type": "unit"}\n'
        events.write_text(sentinel, encoding="utf-8")
        # Forced, because `.itd-memory/` is git-ignored in real projects too:
        # the tracked-ness is exactly what makes the append harmful.
        git(tmp, "add", "-f", ".itd-memory/events.jsonl")
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", ".itd-memory/events.jsonl"],
            cwd=tmp, capture_output=True, text=True, timeout=20)
        check("probe repository really tracks events.jsonl", tracked.returncode == 0)

        out, rc, decision = run_gate(tmp, description="COMPLETION_BYPASS: hotfix")
        check("COMPLETION_BYPASS -> not deny", decision != "deny" and rc == 0)
        ledger = Path(tmp) / ".itd-memory" / "completion-bypass.jsonl"
        check("COMPLETION_BYPASS -> durable audit event in the untracked ledger",
              ledger.is_file() and "hotfix" in ledger.read_text(encoding="utf-8"),
              "ledger=%r" % (ledger.read_text(encoding="utf-8")[:200]
                             if ledger.is_file() else None))
        check("COMPLETION_BYPASS leaves the tracked ledger byte-identical",
              events.read_text(encoding="utf-8") == sentinel,
              "events.jsonl=%r" % events.read_text(encoding="utf-8")[:200])
        # «Файла нет в индексе» - пустая гарантия: ЛЮБОЙ только что созданный
        # файл её проходит, даже когда правило игнора удалено (находка
        # независимого ревьюера). Проверяется именно ПРАВИЛО, и проверять его
        # надо в настоящем репозитории: пробная площадка - голый `git init`
        # без .gitignore, и требовать правило от неё значило бы проверять
        # собственные леса, а не продукт.
        real = subprocess.run(
            ["git", "check-ignore", "-v",
             ".itd-memory/completion-bypass.jsonl"],
            cwd=str(REPO), capture_output=True, text=True, timeout=20)
        check("a repository rule keeps the bypass ledger out of git",
              real.returncode == 0 and ".itd-memory" in real.stdout,
              "check-ignore rc=%r out=%r" % (real.returncode, real.stdout[:200]))

        # 4b) The append is anchored and refuses to follow a symlink: a link
        # planted at the ledger path must not redirect a trusted audit write
        # into another file. A failed audit stays fail-closed (deny).
        victim = Path(tmp) / "victim.jsonl"
        victim.write_text("", encoding="utf-8")
        ledger.unlink(missing_ok=True)
        symlinked = True
        try:
            os.symlink(victim, ledger)
        except (OSError, NotImplementedError):
            symlinked = False  # host cannot create symlinks; parity leg covers it
        if symlinked:
            out, rc, decision = run_gate(
                tmp, description="COMPLETION_BYPASS: symlink probe")
            check("symlinked bypass ledger -> fail-closed deny",
                  decision == "deny" and rc == 2,
                  "decision=%r rc=%r" % (decision, rc))
            check("symlinked bypass ledger -> the link target stays empty",
                  victim.read_text(encoding="utf-8") == "",
                  "victim=%r" % victim.read_text(encoding="utf-8")[:200])
            ledger.unlink(missing_ok=True)

        # 4c) The kill switch shares the same audited destination.
        out, rc, decision = run_gate(
            tmp, env={"ITD_COMPLETION_GATE": "0",
                      "ITD_COMPLETION_BYPASS_REASON": "switch probe"})
        check("kill switch -> not deny", decision != "deny" and rc == 0)
        check("kill switch -> row in the untracked bypass ledger",
              ledger.is_file() and "switch probe" in ledger.read_text(encoding="utf-8"))
        check("kill switch leaves the tracked ledger byte-identical",
              events.read_text(encoding="utf-8") == sentinel)

    # --- RSI-DEBT-2: одна и та же цель аудита в обеих копиях ---------------
    # Путь живёт в двух producer'ах (коммит-гейт и шаблон гигиены). Слить их в
    # один модуль нельзя: шаблон копируется в чужие проекты. Поэтому копии не
    # объединяются, а ПИНЯТСЯ: расхождение обязано быть красным, иначе один
    # boundary чинится, а второй продолжает пачкать отслеживаемый журнал.
    gate_text = GATE.read_text(encoding="utf-8")
    hygiene = REPO / "docs" / "templates" / "itd" / "itd_hygiene.py"
    hygiene_text = hygiene.read_text(encoding="utf-8") if hygiene.is_file() else ""
    literal = '"' + ".itd-memory/completion-bypass.jsonl" + '"'
    check("commit gate declares the untracked bypass ledger",
          ("BYPASS_AUDIT_LEDGER = " + literal) in gate_text)
    check("hygiene twin declares the same ledger",
          ("BYPASS_AUDIT_LEDGER = " + literal) in hygiene_text)
    # r8: загрузчик общего модуля не должен писать байткод в неизменяемый
    # рантайм, а шаблон обязан находить модуль после установки в чужой проект.
    check("both loaders forbid bytecode while executing the shared module",
          gate_text.count("dont_write_bytecode") >= 2
          and hygiene_text.count("dont_write_bytecode") >= 2,
          "gate=%d hygiene=%d" % (gate_text.count("dont_write_bytecode"),
                                  hygiene_text.count("dont_write_bytecode")))
    # r9: доверенный примитив берётся только из host-owned установки. Поиск по
    # предкам проверяемого проекта давал бы выполнение произвольного кода.
    check("the hygiene template never searches the audited project for the primitive",
          "for parent in here.parents" not in hygiene_text
          and ".claude/skills/_shared/itd_safe_atomic.py" in hygiene_text,
          "template still resolves the primitive from the project")

    check("both producers refuse when trackedness cannot be proved",
          "cannot prove" in gate_text and "cannot prove" in hygiene_text,
          "gate=%s hygiene=%s" % ("cannot prove" in gate_text,
                                  "cannot prove" in hygiene_text))
    check("both producers refuse a git-tracked ledger, not only a bad path",
          "is tracked by git" in gate_text and "is tracked by git" in hygiene_text,
          "gate=%s hygiene=%s" % ("is tracked by git" in gate_text,
                                  "is tracked by git" in hygiene_text))
    check("no producer falls back to the tracked events.jsonl",
          '".itd-memory/events.jsonl"' not in gate_text
          and '".itd-memory/events.jsonl"' not in hygiene_text,
          "gate=%s hygiene=%s" % (
              '".itd-memory/events.jsonl"' in gate_text,
              '".itd-memory/events.jsonl"' in hygiene_text))

    # Перенос при ledger-close: строки попадают в журнал, повтор не дублирует.
    carry = REPO / "skills/_shared/itd_bypass_audit.py"
    check("ledger-close carry step exists", carry.is_file())
    if carry.is_file():
        with tempfile.TemporaryDirectory() as tmp:
            memory = Path(tmp) / ".itd-memory"
            memory.mkdir(parents=True, exist_ok=True)
            row = {"id": "evt-completion-bypass-1", "type": "completion_bypass",
                   "reason": "carried probe"}
            (memory / "completion-bypass.jsonl").write_text(
                json.dumps(row) + "\n", encoding="utf-8")
            (memory / "events.jsonl").write_text("", encoding="utf-8")
            first = subprocess.run([sys.executable, str(carry), "carry",
                                    "--root", tmp],
                                   capture_output=True, text=True, timeout=30)
            journal = (memory / "events.jsonl").read_text(encoding="utf-8")
            check("carry moves the row into events.jsonl",
                  first.returncode == 0 and "carried probe" in journal,
                  first.stdout + first.stderr)
            # Леджер намеренно НЕ очищается: удаление и было источником
            # потери строк (см. r2/1 ниже).
            check("carry leaves the working ledger in place",
                  (memory / "completion-bypass.jsonl").is_file())
            # Идемпотентность: строка осталась в леджере, повтор не удваивает.
            subprocess.run([sys.executable, str(carry), "carry", "--root", tmp],
                           capture_output=True, text=True, timeout=30)
            again = (memory / "events.jsonl").read_text(encoding="utf-8")
            check("carry is idempotent on an already carried id",
                  again.count("carried probe") == 1,
                  "journal=%r" % again[:300])

            # r2/1: потеря строки устранена СТРУКТУРНО - перенос не удаляет
            # леджер, поэтому удалять нечему и гонки нет. Проверяется и
            # отсутствие удаления в исходнике, и то, что строка, появившаяся
            # между двумя переносами, доезжает вторым и ровно один раз.
            carry_source = carry.read_text(encoding="utf-8")
            check("carry never unlinks the bypass ledger",
                  "ledger.unlink" not in carry_source
                  and "os.replace(ledger" not in carry_source,
                  "source mentions a delete of the working ledger")
            (memory / "completion-bypass.jsonl").write_text(
                json.dumps({"id": "evt-late-1", "reason": "late row"}) + "\n",
                encoding="utf-8")
            subprocess.run([sys.executable, str(carry), "carry", "--root", tmp],
                           capture_output=True, text=True, timeout=30)
            subprocess.run([sys.executable, str(carry), "carry", "--root", tmp],
                           capture_output=True, text=True, timeout=30)
            late = (memory / "events.jsonl").read_text(encoding="utf-8")
            check("a row added after an earlier carry still reaches the journal",
                  late.count("late row") == 1, "journal=%r" % late[-300:])
            check("the working ledger survives the carry",
                  (memory / "completion-bypass.jsonl").is_file())

            # r3/1: дедупликация обязана работать и ВНУТРИ партии. Один и тот
            # же `id` может лежать в леджере дважды или встретиться и в
            # леджере, и в осевшем хвосте; тогда журнал получал две копии.
            dup = {"id": "evt-dup-1", "reason": "dup row"}
            (memory / "completion-bypass.jsonl").write_text(
                json.dumps(dup) + "\n" + json.dumps(dup) + "\n", encoding="utf-8")
            (memory / "completion-bypass.jsonl.carrying").write_text(
                json.dumps(dup) + "\n", encoding="utf-8")
            subprocess.run([sys.executable, str(carry), "carry", "--root", tmp],
                           capture_output=True, text=True, timeout=30)
            deduped = (memory / "events.jsonl").read_text(encoding="utf-8")
            check("carry appends one row per id even within a single batch",
                  deduped.count("dup row") == 1, "journal=%r" % deduped[-300:])

            # Одинаковый `id` с РАЗНЫМ содержимым - не безобидный повтор, а
            # признак порчи: молча взять первый попавшийся нельзя.
            (memory / "completion-bypass.jsonl").write_text(
                json.dumps({"id": "evt-clash-1", "reason": "left"}) + "\n"
                + json.dumps({"id": "evt-clash-1", "reason": "right"}) + "\n",
                encoding="utf-8")
            (memory / "completion-bypass.jsonl.carrying").unlink()
            clash = subprocess.run([sys.executable, str(carry), "carry",
                                    "--root", tmp],
                                   capture_output=True, text=True, timeout=30)
            # r7/1: читатель обязан быть таким же якорным, как писатель.
            # Подложенный симлинк на леджер втягивал бы чужой JSON прямо в
            # канонический журнал в обход всей защиты записи.
            (memory / "events.jsonl").write_text("", encoding="utf-8")
            (memory / "completion-bypass.jsonl").unlink(missing_ok=True)
            foreign = Path(tmp) / "foreign.jsonl"
            foreign.write_text(
                json.dumps({"id": "evt-foreign-1", "reason": "smuggled"})
                + "\n", encoding="utf-8")
            linked = True
            try:
                os.symlink(foreign, memory / "completion-bypass.jsonl")
            except (OSError, NotImplementedError):
                linked = False
            if linked:
                smuggle = subprocess.run([sys.executable, str(carry), "carry",
                                          "--root", tmp],
                                         capture_output=True, text=True,
                                         timeout=30)
                journal_now = (memory / "events.jsonl").read_text(encoding="utf-8")
                check("a symlinked ledger cannot smuggle rows into the journal",
                      "smuggled" not in journal_now,
                      "journal=%r out=%r" % (journal_now[:200],
                                             (smuggle.stdout + smuggle.stderr)[:200]))
                (memory / "completion-bypass.jsonl").unlink()

            # r4/1: то же правило обязано действовать и ПРОТИВ журнала. Если
            # в events.jsonl уже лежит этот `id` с другим содержимым, строка
            # не «уже перенесена» - это конфликт, и молча её терять нельзя.
            (memory / "events.jsonl").write_text(
                json.dumps({"id": "evt-journal-1", "reason": "journal side"})
                + "\n", encoding="utf-8")
            (memory / "completion-bypass.jsonl").write_text(
                json.dumps({"id": "evt-journal-1", "reason": "ledger side"})
                + "\n", encoding="utf-8")
            against = subprocess.run([sys.executable, str(carry), "carry",
                                      "--root", tmp],
                                     capture_output=True, text=True, timeout=30)
            check("carry refuses a pending id that clashes with the journal",
                  against.returncode != 0
                  and "evt-journal-1" in (against.stdout + against.stderr),
                  "rc=%r out=%r" % (against.returncode,
                                    (against.stdout + against.stderr)[:300]))

            check("carry refuses two different payloads under one id",
                  clash.returncode != 0
                  and "evt-clash-1" in (clash.stdout + clash.stderr),
                  "rc=%r out=%r" % (clash.returncode,
                                    (clash.stdout + clash.stderr)[:300]))

    # r1/2: политика не может назначить целью ОТСЛЕЖИВАЕМЫЙ путь. Инвариант
    # заявлен как «никакая политика», поэтому проверять только относительность
    # пути недостаточно - явный `.itd-memory/events.jsonl` снова ломает дерево.
    with tempfile.TemporaryDirectory() as tmp:
        git(tmp, "init")
        git(tmp, "config", "user.email", "t@t.t")
        git(tmp, "config", "user.name", "t")
        (Path(tmp) / "app.ts").write_text("export const x = 1\n", encoding="utf-8")
        git(tmp, "add", "app.ts")
        seed(tmp, FAIL_L2)
        memory = Path(tmp) / ".itd-memory"
        memory.mkdir(parents=True, exist_ok=True)
        (memory / "events.jsonl").write_text("", encoding="utf-8")
        git(tmp, "add", "-f", ".itd-memory/events.jsonl")
        (Path(tmp) / ".itd").mkdir(parents=True, exist_ok=True)
        (Path(tmp) / ".itd" / "COMPLETION_POLICY.json").write_text(
            json.dumps({"bypassAuditLedger": ".itd-memory/events.jsonl"}),
            encoding="utf-8")
        out, rc, decision = run_gate(tmp, description="COMPLETION_BYPASS: tracked target")
        check("a policy naming a tracked ledger is refused",
              decision == "deny" and rc == 2,
              "decision=%r rc=%r" % (decision, rc))
        check("the tracked ledger stays empty after the refusal",
              (memory / "events.jsonl").read_text(encoding="utf-8") == "",
              "events=%r" % (memory / "events.jsonl").read_text(encoding="utf-8")[:200])


    # r5/1: создание каталогов не должно опережать проверку пути. Симлинк в
    # промежуточном звене уводил `mkdir(parents=True)` за пределы проекта ещё
    # до того, как якорный писатель откажется писать.
    with tempfile.TemporaryDirectory() as tmp:
        git(tmp, "init")
        git(tmp, "config", "user.email", "t@t.t")
        git(tmp, "config", "user.name", "t")
        (Path(tmp) / "app.ts").write_text("export const x = 1\n", encoding="utf-8")
        git(tmp, "add", "app.ts")
        seed(tmp, FAIL_L2)
        outside = Path(tmp) / "outside"
        outside.mkdir(parents=True, exist_ok=True)
        memory = Path(tmp) / ".itd-memory"
        memory.mkdir(parents=True, exist_ok=True)
        planted = True
        try:
            os.symlink(outside, memory / "audit")
        except (OSError, NotImplementedError):
            planted = False
        if planted:
            (Path(tmp) / ".itd").mkdir(parents=True, exist_ok=True)
            (Path(tmp) / ".itd" / "COMPLETION_POLICY.json").write_text(
                json.dumps({"bypassAuditLedger":
                            ".itd-memory/audit/nested/bypass.jsonl"}),
                encoding="utf-8")
            out, rc, decision = run_gate(
                tmp, description="COMPLETION_BYPASS: symlinked parent")
            check("a symlinked ledger parent is refused", decision == "deny" and rc == 2,
                  "decision=%r rc=%r" % (decision, rc))
            check("no directory is created through the symlinked parent",
                  not (outside / "nested").exists(),
                  "created=%r" % sorted(p.name for p in outside.iterdir()))

        # r6/1: цепочки каталогов гейт не строит вообще - значит подменять
        # между проверкой и созданием нечего. Отсутствующий вложенный родитель
        # обязан давать отказ, а не тихое создание.
        (Path(tmp) / ".itd" / "COMPLETION_POLICY.json").write_text(
            json.dumps({"bypassAuditLedger":
                        ".itd-memory/deep/deeper/bypass.jsonl"}),
            encoding="utf-8")
        out, rc, decision = run_gate(
            tmp, description="COMPLETION_BYPASS: deep parent")
        check("a missing nested ledger parent is refused",
              decision == "deny" and rc == 2,
              "decision=%r rc=%r" % (decision, rc))
        check("the gate builds no directory chain",
              not (memory / "deep").exists(),
              "created=%r" % sorted(p.name for p in memory.iterdir()))
        gate_src = GATE.read_text(encoding="utf-8")
        check("the gate never calls mkdir(parents=True)",
              "parents=True" not in gate_src,
              "hook still builds directory chains")

    # --- S9-U3: layer-0 delegation telemetry must not fail the ledger -------
    # Строгая ветка гейта исполняется только при валидном
    # .itd/VERIFICATION_CONTRACT.json, который побайтово равен и HEAD, и
    # последнему source-чекпоинту — поэтому репозиторий собирается отдельно и
    # контракт коммитится вместе с исходником.
    with tempfile.TemporaryDirectory() as tmp:
        git(tmp, "init")
        git(tmp, "config", "user.email", "t@t.t")
        git(tmp, "config", "user.name", "t")
        (Path(tmp) / "app.ts").write_text("export const x = 1\n", encoding="utf-8")
        (Path(tmp) / ".itd").mkdir(parents=True, exist_ok=True)
        (Path(tmp) / ".itd" / "VERIFICATION_CONTRACT.json").write_text(
            json.dumps({"commands": [{"id": "noop", "command": "exit 0",
                                      "passFailParser": "exit_code_zero",
                                      "timeoutSeconds": 30}]}),
            encoding="utf-8")
        git(tmp, "add", "app.ts", ".itd/VERIFICATION_CONTRACT.json")
        git(tmp, "commit", "-m", "base")
        (Path(tmp) / "app.ts").write_text("export const x = 2\n", encoding="utf-8")
        git(tmp, "add", "app.ts")

        TS = "2026-08-15T12:00:00+00:00"
        L1 = {"ts": TS, "kind": "test_run", "layer": 1, "command": "ruff",
              "outcome": "pass", "evidence": "ok", "session": "probe",
              "producer": "itd-completion-signals"}
        L2 = {"ts": TS, "kind": "test_run", "layer": 2, "command": "npm test",
              "outcome": "pass", "evidence": "5 passed", "session": "probe",
              "producer": "itd-completion-signals"}
        # Ровно та строка, которую пишет record-agent-skill.sh до фикса:
        # учёт делегирования, слой 0, без `producer`.
        AGENT0 = {"ts": TS, "kind": "agent", "layer": 0, "class": "delegation",
                  "command": "agent:general-purpose", "outcome": "empty",
                  "evidence": "пустой финал субагента", "session": "probe"}
        STRICT = {"ITD_COMPLETION_POLICY": "strict"}

        seed_raw(tmp, [L1, L2])
        out, rc, decision = run_gate(tmp, env=STRICT)
        check("strict: green runtime signals -> allow (control)",
              decision != "deny" and rc == 0, json.dumps(out, ensure_ascii=False))

        seed_raw(tmp, [L1, L2, AGENT0])
        out, rc, decision = run_gate(tmp, env=STRICT)
        check("strict: layer-0 delegation telemetry without producer -> allow",
              decision != "deny" and rc == 0, json.dumps(out, ensure_ascii=False))

        # Послабление не должно расползаться на слои завершения.
        forged_l2 = dict(L2)
        forged_l2.pop("producer")
        seed_raw(tmp, [L1, forged_l2])
        out, rc, decision = run_gate(tmp, env=STRICT)
        check("strict: layer-2 signal without producer -> still deny",
              decision == "deny", json.dumps(out, ensure_ascii=False))

        wrong_l2 = dict(L2, producer="somebody-else")
        seed_raw(tmp, [L1, wrong_l2])
        out, rc, decision = run_gate(tmp, env=STRICT)
        check("strict: layer-2 signal with foreign producer -> still deny",
              decision == "deny", json.dumps(out, ensure_ascii=False))

        # А если политика ОБЪЯВИЛА слой 0 runtime-слоем — он снова строгий.
        pol = Path(tmp) / ".itd"
        pol.mkdir(parents=True, exist_ok=True)
        (pol / "COMPLETION_POLICY.json").write_text(
            json.dumps({"runtimeLayers": [0, 2, 3],
                        "runtimeKinds": ["test_run", "app_start", "agent"]}),
            encoding="utf-8")
        seed_raw(tmp, [L1, L2, AGENT0])
        out, rc, decision = run_gate(tmp, env=STRICT)
        check("strict: layer 0 declared runtime -> telemetry checked strictly",
              decision == "deny", json.dumps(out, ensure_ascii=False))
        (pol / "COMPLETION_POLICY.json").unlink()

    # --- S9-U3: the writer stamps its own provenance ------------------------
    with tempfile.TemporaryDirectory() as tmp2:
        payload = {"session_id": "probe2", "cwd": tmp2,
                   "tool_name": "Task",
                   "tool_input": {"subagent_type": "general-purpose"},
                   "tool_response": {"content": [{"type": "text", "text": "done"}]}}
        subprocess.run([sys.executable, str(REPO / "hooks" / "record-agent-skill.sh")],
                       input=json.dumps(payload), capture_output=True, text=True,
                       timeout=30)
        led = Path(tmp2) / ".claude" / "completion" / "signals.jsonl"
        rows = []
        if led.is_file():
            for line in led.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
        agent_rows = [r for r in rows if r.get("kind") == "agent"]
        check("writer: agent telemetry row is written", bool(agent_rows),
              str(rows)[:200])
        check("writer: agent telemetry row carries its own producer",
              bool(agent_rows) and agent_rows[-1].get("producer")
              == "itd-record-agent-skill",
              str(agent_rows[-1:])[:200])

    print("\n%d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
