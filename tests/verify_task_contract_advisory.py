#!/usr/bin/env python3
"""Behavioural proof: per-task Sprint Contract advisory (v1.88.0, GP-003,
«пункт 2: Sprint Contracts»).

Spawns hooks/check-dod-before-commit.sh against a real git repo with a staged
benign file and asserts:

  - active unit in .itd-memory/GOAL.json + NO contract  -> additionalContext warning
  - contract file present                                -> no warning
  - no .itd-memory at all                                -> no warning (opt-in)
  - advisory never blocks: exit 0 / no permissionDecision deny in these cases
  - template docs/templates/itd/TASK_CONTRACT.md exists with 3 sections
  - /task SKILL.md instructs generating the contract before code

Self-contained, stdlib only. Run: python3 tests/verify_task_contract_advisory.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "check-dod-before-commit.sh"
TPL = REPO / "docs" / "templates" / "itd" / "TASK_CONTRACT.md"
TASK_SKILL = REPO / "skills" / "task" / "SKILL.md"

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        FAIL += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def run_hook(cwd):
    payload = {"tool_name": "Bash", "cwd": str(cwd),
               "tool_input": {"command": "git commit -m x", "description": "test"}}
    p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=30, cwd=str(cwd))
    return p


def make_repo(td):
    subprocess.run(["git", "init", "-q"], cwd=td, timeout=20)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=td, timeout=20)
    subprocess.run(["git", "config", "user.name", "t"], cwd=td, timeout=20)
    Path(td, "notes.txt").write_text("hi", encoding="utf-8")
    subprocess.run(["git", "add", "notes.txt"], cwd=td, timeout=20)


def main():
    with tempfile.TemporaryDirectory() as td:
        make_repo(td)
        # 1) активный юнит без контракта -> advisory
        mem = Path(td, ".itd-memory")
        mem.mkdir()
        (mem / "GOAL.json").write_text(json.dumps({
            "version": 1, "goal": "g", "status": "active", "currentUnitId": "T-001",
            "units": [{"id": "T-001", "criterion": "c",
                       "verificationCommand": "true", "status": "in_progress"}],
        }), encoding="utf-8")
        p = run_hook(td)
        check("advisory при активном юните без контракта",
              p.returncode == 0 and "TASK-CONTRACT" in p.stdout and "T-001" in p.stdout,
              f"rc={p.returncode} out={p.stdout[:200]}")
        check("advisory не deny",
              '"permissionDecision": "deny"' not in p.stdout, p.stdout[:200])

        # 2) контракт есть -> тишина
        (mem / "contracts").mkdir()
        (mem / "contracts" / "T-001.md").write_text("# Task Contract", encoding="utf-8")
        p = run_hook(td)
        check("с контрактом — без предупреждения",
              p.returncode == 0 and "TASK-CONTRACT" not in p.stdout,
              f"rc={p.returncode} out={p.stdout[:200]}")

    with tempfile.TemporaryDirectory() as td:
        make_repo(td)
        # 3) без .itd-memory — opt-in, тишина
        p = run_hook(td)
        check("без .itd-memory — тишина (opt-in)",
              p.returncode == 0 and "TASK-CONTRACT" not in p.stdout,
              f"rc={p.returncode} out={p.stdout[:200]}")

    # 4) шаблон с тремя секциями
    t = TPL.read_text(encoding="utf-8") if TPL.exists() else ""
    check("шаблон TASK_CONTRACT.md: Scope/Verification/Exclusions",
          all(s in t for s in ("## Scope", "## Verification Standards", "## Exclusions")),
          str(TPL))

    # 5) /task генерирует контракт до кода
    s = TASK_SKILL.read_text(encoding="utf-8")
    check("/task SKILL.md: генерация контракта до кода",
          "TASK_CONTRACT" in s and ".itd-memory/contracts/" in s, "маркер не найден")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
