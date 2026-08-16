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
        seed(tmp, FAIL_L2)
        out, rc, decision = run_gate(tmp, description="COMPLETION_BYPASS: hotfix")
        check("COMPLETION_BYPASS -> not deny", decision != "deny" and rc == 0)
        events = Path(tmp) / ".itd-memory" / "events.jsonl"
        check("COMPLETION_BYPASS -> durable audit event",
              events.is_file() and "hotfix" in events.read_text(encoding="utf-8"))

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
