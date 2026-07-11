#!/usr/bin/env python3
"""verify_project_checks.py — first-class слот project-level проверок (v1.87.0).

Контракты:
  1. нет .itd/checks/ → no-op exit 0 (opt-in);
  2. провал любой проверки → exit 1, вывод содержит имя и сообщение (WHY/FIX);
  3. --list перечисляет проверки без запуска;
  4. --files транспортируется в ITD_CHANGED_FILES;
  5. DoD-хук: staged-коммит в проекте с красной проверкой → deny (exit 2),
     без .itd/checks/ → пропуск (exit 0).
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "skills", "_shared", "itd_project_checks.sh")
HOOK = os.path.join(ROOT, "hooks", "check-dod-before-commit.sh")

fails = []


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + ((" " + detail) if (detail and not cond) else ""))
    if not cond:
        fails.append(name)


def run(args, cwd):
    return subprocess.run(["sh", RUNNER] + args, cwd=cwd, capture_output=True, text=True, timeout=60)


# 1. no-op без каталога
with tempfile.TemporaryDirectory() as tmp:
    r = run(["--root", tmp], cwd=tmp)
    check("noop-without-dir", r.returncode == 0 and "no-op" in r.stdout, f"rc={r.returncode} out={r.stdout!r}")

# 2-4. ok + fail + list + env
with tempfile.TemporaryDirectory() as tmp:
    d = os.path.join(tmp, ".itd", "checks")
    os.makedirs(d)
    open(os.path.join(d, "aa-ok.sh"), "w").write('echo "all good"\nexit 0\n')
    open(os.path.join(d, "bb-fail.sh"), "w").write(
        'echo "WHY: правило нарушено"\necho "FIX: почини так-то"\nexit 1\n')
    open(os.path.join(d, "cc-env.sh"), "w").write(
        'printf "CHANGED:[%s]\\n" "$(printf \'%s\' "$ITD_CHANGED_FILES" | tr \'\\n\' \',\')"\nexit 0\n')
    r = run(["--root", tmp, "--files", "src/a.ts", "src/b.ts"], cwd=tmp)
    check("fail-propagates", r.returncode == 1 and "bb-fail.sh" in r.stdout and "FIX: почини" in r.stdout,
          f"rc={r.returncode} out={r.stdout[-200:]!r}")
    check("files-transported", "src/a.ts,src/b.ts" in r.stdout, f"out={r.stdout[-200:]!r}")
    rl = run(["--root", tmp, "--list"], cwd=tmp)
    check("list-mode", rl.returncode == 0 and "aa-ok.sh" in rl.stdout and "bb-fail.sh" in rl.stdout)

# 5. DoD-хук интеграция
def hook_run(cwd, cmd="git commit -m x"):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    return subprocess.run([sys.executable, HOOK], input=payload, cwd=cwd,
                          capture_output=True, text=True, timeout=60)

with tempfile.TemporaryDirectory() as tmp:
    subprocess.run(["git", "init", "-q", tmp], capture_output=True)
    open(os.path.join(tmp, "f.txt"), "w").write("x\n")
    subprocess.run(["git", "-C", tmp, "add", "f.txt"], capture_output=True)
    # без .itd/checks — пропуск
    r = hook_run(tmp)
    check("hook-noop-without-checks", r.returncode == 0, f"rc={r.returncode} err={r.stderr[-150:]!r}")
    # с красной проверкой — deny
    d = os.path.join(tmp, ".itd", "checks")
    os.makedirs(d)
    open(os.path.join(d, "fail.sh"), "w").write('echo "WHY/FIX тут"\nexit 1\n')
    r = hook_run(tmp)
    check("hook-denies-on-red", r.returncode == 2 and "project-level" in (r.stdout + r.stderr),
          f"rc={r.returncode} out={(r.stdout + r.stderr)[-200:]!r}")
    # зелёная проверка — пропуск
    open(os.path.join(d, "fail.sh"), "w").write("exit 0\n")
    r = hook_run(tmp)
    check("hook-passes-on-green", r.returncode == 0, f"rc={r.returncode} err={r.stderr[-150:]!r}")

if fails:
    print("FAILED:", " ".join(fails))
    sys.exit(1)
print("verify_project_checks: all ok")
