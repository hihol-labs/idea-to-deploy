#!/usr/bin/env python3
"""verify_goal_verify_shell.py — POSIX-контракт исполнения verificationCommand (v1.87.0).

Кросс-слоевой дефект (retro 2026-07-11, сет-3, упр.1 «юнит vs e2e»):
shell=True на Windows шёл в cmd.exe — одинарные кавычки не снимались, $VAR не
раскрывался, и деградировавшая команда могла вернуть exit 0 → ТИХИЙ ложный
verified (live-репро: evidence '"HOME=$HOME"''). Юнит-слой (Linux) этого не
видел — тест закрепляет контракт семантикой, а не только exit-кодом:

  1. $VAR раскрывается: evidence содержит РЕАЛЬНОЕ значение, не литерал '$HOME';
  2. одинарные кавычки снимаются: echo 'a b' → evidence 'a b' без кавычек;
  3. ненулевой exit доходит: юнит остаётся in_progress;
  4. sh обязателен: контракт объявлен в шапке скрипта (["sh","-c"] в коде).
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "goal", "scripts", "itd_goal_verify.py")

fails = []


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + ((" " + detail) if (detail and not cond) else ""))
    if not cond:
        fails.append(name)


def make_ledger(tmp, unit_id, command):
    mem = os.path.join(tmp, ".itd-memory")
    os.makedirs(mem, exist_ok=True)
    goal = {
        "version": 1, "goal": "shell-contract probe", "status": "active",
        "createdAt": "2026-07-11T00:00:00Z", "updatedAt": "2026-07-11T00:00:00Z",
        "currentUnitId": unit_id,
        "units": [{"id": unit_id, "criterion": "probe",
                   "verificationCommand": command, "status": "in_progress"}],
    }
    with open(os.path.join(mem, "GOAL.json"), "w", encoding="utf-8") as f:
        json.dump(goal, f, ensure_ascii=False)
    return mem


def run_verify(tmp, unit_id):
    return subprocess.run([sys.executable, SCRIPT, unit_id], cwd=tmp,
                          capture_output=True, text=True, timeout=60)


def read_unit(mem):
    with open(os.path.join(mem, "GOAL.json"), encoding="utf-8") as f:
        return json.load(f)["units"][0]


# 1. $VAR раскрывается + 2. одинарные кавычки снимаются
with tempfile.TemporaryDirectory() as tmp:
    mem = make_ledger(tmp, "V-1", "sh -c 'test -n \"$HOME\" && echo \"HOME=$HOME\"'")
    r = run_verify(tmp, "V-1")
    u = read_unit(mem)
    ev = u.get("evidence", "")
    home = os.environ.get("HOME", "")
    check("var-expanded-verified", r.returncode == 0 and u["status"] == "verified",
          f"rc={r.returncode} status={u['status']} out={r.stdout[-120:]!r}")
    check("var-expanded-semantics", "$HOME" not in ev and home != "" and f"HOME={home}" in ev,
          f"evidence={ev!r}")

with tempfile.TemporaryDirectory() as tmp:
    mem = make_ledger(tmp, "V-2", "echo 'a b'")
    run_verify(tmp, "V-2")
    ev = read_unit(mem).get("evidence", "")
    check("single-quotes-stripped", "a b" in ev and "'a b'" not in ev, f"evidence={ev!r}")

# 3. Ненулевой exit — громкий провал, юнит остаётся in_progress
with tempfile.TemporaryDirectory() as tmp:
    mem = make_ledger(tmp, "V-3", "sh -c 'exit 3'")
    r = run_verify(tmp, "V-3")
    u = read_unit(mem)
    check("nonzero-exit-fails-loud", r.returncode != 0 and u["status"] == "in_progress",
          f"rc={r.returncode} status={u['status']}")

# 4. Контракт объявлен в коде: ["sh","-c"] + отказ без sh
with open(SCRIPT, encoding="utf-8") as f:
    src = f.read()
check("code-uses-sh-dash-c", '[sh, "-c", command]' in src)
check("code-refuses-cmd-fallback", "refusing cmd.exe fallback" in src)

if fails:
    print("FAILED:", " ".join(fails))
    sys.exit(1)
print("verify_goal_verify_shell: all ok")
