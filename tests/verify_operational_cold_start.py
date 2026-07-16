#!/usr/bin/env python3
"""Real external-repository journey: cold start -> adopt -> verified unit.

No mocks and no copied fake outcome: every transition runs the production
adoption helper, goal verifier, contract drift checker, state validator, git,
and isolated-clone init validator against a temporary repository.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
ADOPT = ROOT / "skills" / "adopt" / "scripts" / "itd_adopt.py"
GOAL_VERIFY = ROOT / "skills" / "goal" / "scripts" / "itd_goal_verify.py"
VALIDATE_STATE = ROOT / "scripts" / "validate_state.py"
CORPUS = ROOT / "benchmarks" / "operational-friction" / "COLD_START.json"
CORPUS_SHA = ROOT / "benchmarks" / "operational-friction" / "COLD_START.sha256"
PY = sys.executable or "python3"
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("  OK   " if ok else " FAIL  ") + name + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def run(args: list[str], cwd: Path, timeout: int = 300) -> tuple[int, str]:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def native_shell_join(*args: str) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(args))
    return shlex.join(args)


def verification_shell_join(*args: str) -> str:
    # verificationCommand has a POSIX-sh contract on every host, including
    # Windows where the verifier resolves Git Bash.  cmd.exe quoting leaves
    # backslashes in C:\\... executable paths unprotected; `sh -c` then eats
    # them and cannot launch Python (especially under a non-ASCII profile).
    return shlex.join(args)


def git(project: Path, *args: str) -> tuple[int, str]:
    return run(["git", *args], project, timeout=60)


def init_project(project: Path) -> str:
    project.mkdir()
    original_agents = "# Existing project rules\n\n- Preserve the public API.\n"
    (project / "AGENTS.md").write_text(original_agents, encoding="utf-8")
    (project / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    (project / "app.py").write_text(
        "def status():\n    return 'booting'\n",
        encoding="utf-8",
    )
    tests = project / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("", encoding="utf-8")
    (tests / "test_smoke.py").write_text(
        "import unittest\n\n"
        "from app import status\n\n"
        "class SmokeTest(unittest.TestCase):\n"
        "    def test_existing_baseline(self):\n"
        "        self.assertEqual(status(), 'booting')\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )
    (tests / "test_first_task.py").write_text(
        "import unittest\n\n"
        "from app import ready\n\n"
        "class FirstTaskTest(unittest.TestCase):\n"
        "    def test_ready(self):\n"
        "        self.assertEqual(ready(), 'ready')\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )
    for args in (
        ("init", "-q"),
        ("add", "-A"),
        ("-c", "user.email=ops@example.invalid", "-c", "user.name=Ops Fixture",
         "commit", "-qm", "external baseline"),
    ):
        rc, out = git(project, *args)
        if rc != 0:
            raise RuntimeError(out)
    return original_agents


def corpus_contract() -> dict:
    import hashlib

    raw = CORPUS.read_bytes()
    expected = CORPUS_SHA.read_text(encoding="utf-8").strip().split()[0]
    actual = hashlib.sha256(raw).hexdigest()
    check("cold-start corpus seal matches", actual == expected, f"expected={expected} actual={actual}")
    return json.loads(raw)


def main() -> int:
    corpus = corpus_contract()
    scenario = corpus["scenarios"][0]
    metrics = {
        "manualRepairs": 0,
        "deadEnds": 0,
        "falseBlocks": 0,
        "firstTaskVerified": False,
        "isolatedClonePassed": False,
        "idempotentRerun": False,
    }

    with tempfile.TemporaryDirectory(prefix="itd-external-cold-start-") as td:
        project = Path(td) / "external-project"
        original_agents = init_project(project)
        baseline = native_shell_join(PY, "-m", "unittest", "tests.test_smoke", "-v")
        unit_command = verification_shell_join(
            PY, "-m", "unittest", "tests.test_first_task", "-v")
        common = [
            PY, str(ADOPT),
            "--project", str(project),
            "--plugin-root", str(ROOT),
            "--baseline-command", baseline,
            "--verification-command", unit_command,
            "--unit-id", scenario["unitId"],
            "--unit-criterion", scenario["criterion"],
            "--allowed-area", "app.py",
            "--allowed-area", "tests/",
        ]

        # Cold start must be inspectable and inert before approval.
        rc, out = run([*common, "--plan"], project)
        check("plan succeeds", rc == 0 and "PLAN ONLY" in out, out[-500:])
        rc_status, status = git(project, "status", "--porcelain")
        check("plan performs zero writes", rc_status == 0 and not status.strip(), status)

        # An apply without approval is a useful denial, not a dead end.
        rc, out = run([*common, "--apply"], project)
        check("unapproved apply is denied", rc != 0, out[-500:])
        check("approval denial has WHY and FIX", "WHY:" in out and "FIX:" in out, out[-500:])
        rc_status, status = git(project, "status", "--porcelain")
        check("denied apply performs zero writes", rc_status == 0 and not status.strip(), status)

        # The approved path is one command; no interpreter/path retry is allowed.
        rc, out = run([*common, "--apply", "--approved"], project)
        check("approved adoption succeeds first try", rc == 0 and "ADOPTION: PASS" in out, out[-800:])
        if rc != 0:
            metrics["deadEnds"] += 1
        check("adoption reports zero manual repairs", '"manualRepairs": 0' in out, out[-500:])
        check("existing AGENTS content preserved",
              (project / "AGENTS.md").read_text(encoding="utf-8").startswith(original_agents))
        check("Codex marker appended exactly once",
              (project / "AGENTS.md").read_text(encoding="utf-8").count(
                  "<!-- idea-to-deploy:begin codex-v1 -->") == 1)
        check("no Claude project adapter written", not (project / "CLAUDE.md").exists()
              and not (project / ".claude").exists())
        check("no repo-local Codex hook duplication", not (project / ".codex").exists())

        rc, out = run([PY, str(project / ".itd" / "check_contract_drift.py"),
                       "--filled", "--strict"], project)
        check("adoption contracts are filled", rc == 0, out[-800:])
        rc, out = run([PY, str(VALIDATE_STATE), str(project / ".itd-memory" / "STATE.json")], project)
        check("adoption state validates", rc == 0, out[-800:])

        goal = project / ".itd-memory" / "GOAL.json"
        rc, out = run([PY, str(GOAL_VERIFY), "--goal", str(goal), "--seal"], project)
        check("first-unit oracle seals", rc == 0, out[-800:])
        rc, out = run([PY, str(GOAL_VERIFY), scenario["unitId"], "--goal", str(goal),
                       "--activate"], project)
        check("first unit activates", rc == 0, out[-800:])

        rc_red, out_red = run_shell_for_test(unit_command, project)
        check("first task has real red evidence", rc_red != 0, out_red[-500:])
        (project / "app.py").write_text(
            "def status():\n    return 'booting'\n\n"
            "def ready():\n    return 'ready'\n",
            encoding="utf-8",
        )
        rc, out = run([PY, str(GOAL_VERIFY), scenario["unitId"], "--goal", str(goal),
                       "--approach", "Implement the smallest source change that satisfies the sealed unit test."], project)
        goal_data = json.loads(goal.read_text(encoding="utf-8"))
        unit = goal_data["units"][0]
        metrics["firstTaskVerified"] = rc == 0 and unit["status"] == "verified"
        check("first task verifies through production goal verifier",
              metrics["firstTaskVerified"], out[-1000:])

        # Commit the adopted state so the production init validator can prove a clean clone.
        for args in (
            ("add", "-A"),
            ("-c", "user.email=ops@example.invalid", "-c", "user.name=Ops Fixture",
             "commit", "-qm", "adopt and verify first unit"),
        ):
            rc, out = git(project, *args)
            check("fixture commit step succeeds", rc == 0, out[-500:])
        bootstrap = native_shell_join(PY, "-c", "print('bootstrap-ok')")
        full_tests = native_shell_join(
            PY, "-m", "unittest", "discover", "-s", "tests", "-v")
        rc, out = run([PY, str(project / ".itd" / "itd_init_validate.py"),
                       "--bootstrap", bootstrap, "--test", full_tests, "--timeout", "120"], project)
        metrics["isolatedClonePassed"] = rc == 0 and "PASS." in out
        check("clean-clone bootstrap and tests pass", metrics["isolatedClonePassed"], out[-1200:])

        rc_status, before = git(project, "status", "--porcelain")
        rc, out = run([*common, "--apply", "--approved"], project)
        rc_status2, after = git(project, "status", "--porcelain")
        metrics["idempotentRerun"] = (
            rc_status == rc_status2 == 0 and rc == 0 and before == after == ""
            and (project / "AGENTS.md").read_text(encoding="utf-8").count(
                "<!-- idea-to-deploy:begin codex-v1 -->") == 1
        )
        check("approved adoption rerun is idempotent", metrics["idempotentRerun"],
              f"before={before!r} after={after!r} out={out[-500:]}")

    thresholds = corpus["thresholds"]
    check("manual repair threshold", metrics["manualRepairs"] <= thresholds["maxManualRepairs"])
    check("dead-end threshold", metrics["deadEnds"] <= thresholds["maxDeadEnds"])
    check("false-block threshold", metrics["falseBlocks"] <= thresholds["maxFalseBlocks"])
    check("all required journey outcomes", all(metrics[key] for key in (
        "firstTaskVerified", "isolatedClonePassed", "idempotentRerun")), json.dumps(metrics))
    print("METRICS " + json.dumps(metrics, sort_keys=True))
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print("ALL PASS — external cold-start journey completed without manual repair")
    return 0


def run_shell_for_test(command: str, cwd: Path) -> tuple[int, str]:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


if __name__ == "__main__":
    sys.exit(main())
