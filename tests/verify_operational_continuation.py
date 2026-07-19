#!/usr/bin/env python3
"""Existing-project journey: durable checkpoint -> fresh session -> verified unit.

The fixture is internal operational evidence, never field or external-
effectiveness evidence. It runs the production adoption helper, goal verifier,
state validator, pre-flight hook, git, and real unittest commands against a
temporary mature repository.
"""
from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid


try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
ADOPT = ROOT / "skills" / "adopt" / "scripts" / "itd_adopt.py"
GOAL_VERIFY = ROOT / "skills" / "goal" / "scripts" / "itd_goal_verify.py"
VALIDATE_STATE = ROOT / "scripts" / "validate_state.py"
PREFLIGHT = ROOT / "hooks" / "pre-flight-check.sh"
CORPUS = ROOT / "benchmarks" / "operational-friction" / "CONTINUATION.json"
CORPUS_SHA = ROOT / "benchmarks" / "operational-friction" / "CONTINUATION.sha256"
PY = sys.executable or "python3"
FAILURES: list[str] = []


def runtime_env() -> dict[str, str]:
    env = dict(os.environ)
    if os.name != "nt" or shutil.which("sh", path=env.get("PATH")):
        return env
    git_exe = shutil.which("git", path=env.get("PATH"))
    candidates: list[Path] = []
    if git_exe:
        candidates.append(Path(git_exe).resolve().parent.parent / "bin" / "sh.exe")
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
        root = env.get(variable)
        if root:
            candidates.extend((
                Path(root) / "Git" / "bin" / "sh.exe",
                Path(root) / "Programs" / "Git" / "bin" / "sh.exe",
            ))
    for candidate in candidates:
        if candidate.is_file():
            env["PATH"] = str(candidate.parent) + os.pathsep + env.get("PATH", "")
            break
    return env


BASE_ENV = runtime_env()


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("  OK   " if ok else " FAIL  ") + name
          + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def run(args: list[str], cwd: Path, timeout: int = 300,
        env: dict[str, str] | None = None,
        input_text: str | None = None) -> tuple[int, str]:
    effective_env = dict(BASE_ENV)
    if env:
        effective_env.update(env)
    result = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=effective_env,
        input=input_text,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def git(project: Path, *args: str) -> tuple[int, str]:
    return run(["git", *args], project, timeout=60)


def commit(project: Path, message: str) -> None:
    rc, out = git(project, "add", "-A")
    if rc != 0:
        raise RuntimeError(out)
    rc, out = git(
        project, "-c", "user.email=ops@example.invalid",
        "-c", "user.name=Ops Fixture", "commit", "-qm", message)
    if rc != 0:
        raise RuntimeError(out)


def native_shell_join(*args: str) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(args))
    return shlex.join(args)


def verification_shell_join(*args: str) -> str:
    # The production goal verifier executes verificationCommand via POSIX sh,
    # including on Windows where Git Bash supplies that contract.
    return shlex.join(args)


def run_shell(command: str, cwd: Path) -> tuple[int, str]:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env=BASE_ENV,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def directory_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(
            (candidate for candidate in path.rglob("*") if candidate.is_file()),
            key=lambda candidate: candidate.relative_to(path).as_posix()):
        rel = item.relative_to(path).as_posix().encode("utf-8")
        raw = item.read_bytes()
        digest.update(len(rel).to_bytes(8, "big"))
        digest.update(rel)
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


def load_preflight():
    loader = importlib.machinery.SourceFileLoader(
        "itd_operational_continuation_preflight", str(PREFLIGHT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def corpus_contract() -> dict:
    raw = CORPUS.read_bytes()
    try:
        expected, declared = CORPUS_SHA.read_text(
            encoding="utf-8").strip().split(None, 1)
    except ValueError:
        expected, declared = "", ""
    actual = hashlib.sha256(raw).hexdigest()
    check("continuation corpus seal matches",
          expected == actual
          and declared
          == "benchmarks/operational-friction/CONTINUATION.json",
          f"expected={expected or '(missing)'} actual={actual} "
          f"declared={declared or '(missing)'}")
    mutated = raw.replace(b'"version": 1', b'"version": 9', 1)
    check("mutation: changed continuation corpus breaks the frozen seal",
          bool(expected) and hashlib.sha256(mutated).hexdigest() != expected)
    data = json.loads(raw)
    purpose = data.get("purpose", "").lower()
    check("corpus is explicitly internal, never external outcome evidence",
          "internal" in purpose and "never external" in purpose)
    return data


def init_mature_project(project: Path) -> str:
    project.mkdir()
    original_agents = (
        "# Existing project rules\n\n"
        "- Preserve status(), completed_feature(), and the public CLI contract.\n"
    )
    (project / "AGENTS.md").write_text(original_agents, encoding="utf-8")
    (project / ".gitignore").write_text(
        "__pycache__/\n*.pyc\n.claude/\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[project]\nname = \"continuation-fixture\"\nversion = \"1.0.0\"\n",
        encoding="utf-8")
    (project / "app.py").write_text(
        "def status():\n"
        "    return 'stable'\n\n"
        "def completed_feature():\n"
        "    return 'v1'\n",
        encoding="utf-8")
    tests = project / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("", encoding="utf-8")
    (tests / "test_baseline.py").write_text(
        "import unittest\n\n"
        "from app import completed_feature, status\n\n"
        "class BaselineTest(unittest.TestCase):\n"
        "    def test_existing_contract(self):\n"
        "        self.assertEqual(status(), 'stable')\n"
        "        self.assertEqual(completed_feature(), 'v1')\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n",
        encoding="utf-8")
    (tests / "test_continuation.py").write_text(
        "import unittest\n\n"
        "from app import pending_feature\n\n"
        "class ContinuationTest(unittest.TestCase):\n"
        "    def test_pending_feature(self):\n"
        "        self.assertEqual(pending_feature(), 'continued')\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n",
        encoding="utf-8")
    (project / "history.txt").write_text("baseline\n", encoding="utf-8")
    rc, out = git(project, "init", "-q")
    if rc != 0:
        raise RuntimeError(out)
    commit(project, "existing project baseline")
    for number in range(2, 5):
        with (project / "history.txt").open("a", encoding="utf-8") as handle:
            handle.write(f"mature-change-{number}\n")
        commit(project, f"existing history {number}")
    return original_agents


def set_two_unit_goal(project: Path, scenario: dict,
                      continuation_command: str) -> Path:
    goal_path = project / ".itd-memory" / "GOAL.json"
    goal = json.loads(goal_path.read_text(encoding="utf-8"))
    goal["goal"] = (
        "Preserve the mature baseline and continue the next bounded unit.")
    goal["units"].append({
        "id": scenario["resumeUnitId"],
        "criterion": scenario["resumeCriterion"],
        "verificationCommand": continuation_command,
        "status": "pending",
        "verifiedAt": "",
        "evidence": "",
        "skippedReason": "",
    })
    goal_path.write_text(
        json.dumps(goal, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return goal_path


def checkpoint_state(project: Path, scenario: dict) -> None:
    state_path = project / ".itd-memory" / "STATE.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["currentUnit"] = {
        "id": scenario["precedingUnitId"],
        "goal": scenario["precedingCriterion"],
        "status": "verified",
        "startedAt": state.get("currentUnit", {}).get("startedAt", ""),
        "completedAt": "2026-07-18T00:00:00Z",
    }
    state["nextAction"] = (
        "Activate U-002 and implement pending_feature without changing "
        "status or completed_feature.")
    state["blockers"] = [
        "U-002 verification is red until pending_feature exists"]
    state.setdefault("gateResults", {}).update({
        "baseline": "passed",
        "tests": "pending",
        "review": "pending",
    })
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    memory = project / ".itd-memory"
    (memory / "session_2026-07-18.md").write_text(
        "# Durable continuation checkpoint\n\n"
        "- U-001 verified through its sealed oracle.\n"
        "- Next action: Activate U-002 and implement pending_feature.\n"
        "- Preserve status() and completed_feature().\n",
        encoding="utf-8")
    (memory / "MEMORY.md").write_text(
        "- [continue U-002](session_2026-07-18.md) — warm brownfield resume\n",
        encoding="utf-8")


def verify_registration() -> None:
    needle = "verify_operational_continuation"
    paths = (
        ROOT / "tests" / "run-all.sh",
        ROOT / ".github" / "workflows" / "meta-review.yml",
        ROOT / ".github" / "workflows" / "windows-verify.yml",
    )
    registered: list[bool] = []
    for path in paths:
        present = needle in path.read_text(encoding="utf-8")
        registered.append(present)
        check(f"continuation benchmark registered in {path.relative_to(ROOT)}",
              present)
    mutated = registered.copy()
    if mutated:
        mutated[0] = False
    check("mutation: dropping one registration fails the registration contract",
          all(registered) and not all(mutated))


def main() -> int:
    corpus = corpus_contract()
    verify_registration()
    scenario = corpus["scenarios"][0]
    thresholds = corpus["thresholds"]
    metrics = {
        "recoveredContextMarkers": 0,
        "manualContextReentry": 0,
        "wrongUnitActivations": 0,
        "reAdoptionWrites": 0,
        "baselineRegressions": 0,
        "continuationVerified": False,
        "wipOneEnforced": False,
        "freshHostHome": False,
    }
    started = time.monotonic()

    with tempfile.TemporaryDirectory(
            prefix="itd-operational-continuation-") as td:
        project = Path(td) / "mature-project"
        host_home = Path(td) / "fresh-host-home"
        host_home.mkdir()
        original_agents = init_mature_project(project)
        rc, commit_count = git(project, "rev-list", "--count", "HEAD")
        check("fixture begins as a mature repository",
              rc == 0 and int(commit_count.strip()) >= 4, commit_count)

        baseline_command = native_shell_join(
            PY, "-m", "unittest", "tests.test_baseline", "-v")
        baseline_verify = verification_shell_join(
            PY, "-m", "unittest", "tests.test_baseline", "-v")
        continuation_command = verification_shell_join(
            PY, "-m", "unittest", "tests.test_continuation", "-v")
        continuation_native = native_shell_join(
            PY, "-m", "unittest", "tests.test_continuation", "-v")
        common = [
            PY, str(ADOPT),
            "--project", str(project),
            "--plugin-root", str(ROOT),
            "--baseline-command", baseline_command,
            "--verification-command", baseline_verify,
            "--unit-id", scenario["precedingUnitId"],
            "--unit-criterion", scenario["precedingCriterion"],
            "--allowed-area", "app.py",
            "--allowed-area", "tests/",
        ]
        rc, out = run([*common, "--apply", "--approved"], project)
        check("already-started project adopts without source rewrite",
              rc == 0 and "ADOPTION: PASS" in out, out[-800:])
        goal_path = set_two_unit_goal(
            project, scenario, continuation_command)
        rc, out = run(
            [PY, str(GOAL_VERIFY), "--goal", str(goal_path), "--seal"],
            project)
        check("two-unit continuation oracle seals", rc == 0, out[-800:])
        rc, out = run(
            [PY, str(GOAL_VERIFY), scenario["precedingUnitId"],
             "--goal", str(goal_path), "--activate"],
            project)
        check("predecessor unit activates", rc == 0, out[-800:])
        rc_busy, out_busy = run(
            [PY, str(GOAL_VERIFY), scenario["resumeUnitId"],
             "--goal", str(goal_path), "--activate"],
            project)
        metrics["wipOneEnforced"] = (
            rc_busy != 0 and "WIP=1" in out_busy)
        if not metrics["wipOneEnforced"]:
            metrics["wrongUnitActivations"] += 1
        check("WIP=1 rejects the next unit while predecessor is active",
              metrics["wipOneEnforced"], out_busy[-800:])
        rc, out = run(
            [PY, str(GOAL_VERIFY), scenario["precedingUnitId"],
             "--goal", str(goal_path),
             "--approach", "Re-run the preserved mature-project baseline."],
            project)
        check("predecessor verifies through production goal verifier",
              rc == 0 and "VERIFIED U-001" in out, out[-1000:])
        checkpoint_state(project, scenario)
        commit(project, "durable checkpoint before fresh continuation")

        checkpoint_agents = (project / "AGENTS.md").read_bytes()
        checkpoint_contracts = directory_digest(project / ".itd")
        checkpoint_app = (project / "app.py").read_text(encoding="utf-8")
        rc, baseline_out = run_shell(baseline_command, project)
        check("checkpoint baseline is green", rc == 0, baseline_out[-500:])

        # New host/session: no transcript, no private project memory, and no
        # copied prompt context. Only project-local durable state exists.
        fresh_env = {
            "HOME": str(host_home),
            "USERPROFILE": str(host_home),
            "TMPDIR": str(host_home / "tmp"),
            "TMP": str(host_home / "tmp"),
            "TEMP": str(host_home / "tmp"),
            "CLAUDE_SESSION_ID": "continuation-" + uuid.uuid4().hex,
        }
        (host_home / "tmp").mkdir()
        metrics["freshHostHome"] = (
            list(host_home.iterdir()) == [host_home / "tmp"])
        rc, preflight_out = run(
            [PY, str(PREFLIGHT)], project, env=fresh_env,
            input_text=json.dumps({
                "session_id": fresh_env["CLAUDE_SESSION_ID"],
                "cwd": str(project),
                "prompt": "continue the existing project",
            }))
        check("fresh-session pre-flight succeeds", rc == 0, preflight_out[-800:])
        markers = scenario["requiredContextMarkers"]
        recovered = [marker for marker in markers if marker in preflight_out]
        metrics["recoveredContextMarkers"] = len(recovered)
        metrics["manualContextReentry"] = (
            0 if len(recovered) == len(markers) else 1)
        check("fresh session reconstructs every required continuation marker",
              len(recovered) == len(markers),
              f"recovered={recovered!r} output={preflight_out[-1200:]}")
        check("fresh host has no transcript or private project memory",
              metrics["freshHostHome"]
              and not (host_home / ".claude" / "projects").exists())

        preflight = load_preflight()
        direct_context = preflight.itd_state_context(project)
        check("direct context selects pending U-002 without recreating GOAL",
              "текущий `U-002`" in direct_context
              and "Последнее verified evidence (`U-001`)" in direct_context
              and "`GOAL.json` не пересоздаётся" in direct_context,
              direct_context[-1000:])

        rc, out = run(
            [PY, str(GOAL_VERIFY), scenario["resumeUnitId"],
             "--goal", str(goal_path), "--activate"],
            project)
        check("fresh session activates the exact pending unit",
              rc == 0 and "activated U-002" in out, out[-800:])
        rc_red, out_red = run_shell(continuation_native, project)
        check("continued unit has real red evidence",
              rc_red != 0 and "pending_feature" in out_red, out_red[-800:])

        (project / "app.py").write_text(
            checkpoint_app
            + "\n\ndef pending_feature():\n"
              "    return 'continued'\n",
            encoding="utf-8")
        rc, out = run(
            [PY, str(GOAL_VERIFY), scenario["resumeUnitId"],
             "--goal", str(goal_path),
             "--approach",
             "Add only pending_feature and preserve the baseline."],
            project)
        goal = json.loads(goal_path.read_text(encoding="utf-8"))
        units = {unit["id"]: unit for unit in goal["units"]}
        metrics["continuationVerified"] = (
            rc == 0 and units["U-001"]["status"] == "verified"
            and units["U-002"]["status"] == "verified")
        check("continued unit verifies through production goal verifier",
              metrics["continuationVerified"], out[-1000:])

        state_path = project / ".itd-memory" / "STATE.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["currentUnit"] = {
            "id": "U-002",
            "goal": scenario["resumeCriterion"],
            "status": "verified",
            "startedAt": "",
            "completedAt": "2026-07-19T00:00:00Z",
        }
        state["nextAction"] = (
            "Run the full baseline and prepare the next handoff.")
        state["blockers"] = []
        state["gateResults"]["tests"] = "passed"
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        rc, out = run(
            [PY, str(VALIDATE_STATE), str(state_path)], project)
        check("continued project state remains schema-valid",
              rc == 0, out[-800:])

        full_command = native_shell_join(
            PY, "-m", "unittest", "discover", "-s", "tests", "-v")
        rc, out = run_shell(full_command, project)
        if rc != 0:
            metrics["baselineRegressions"] += 1
        check("existing baseline and continued unit pass together",
              rc == 0, out[-1000:])
        check("project-owned guidance is byte-preserved during continuation",
              (project / "AGENTS.md").read_bytes() == checkpoint_agents
              and (project / "AGENTS.md").read_text(
                  encoding="utf-8").startswith(original_agents))
        check("adoption contracts are unchanged during continuation",
              directory_digest(project / ".itd") == checkpoint_contracts)
        metrics["reAdoptionWrites"] = int(
            (project / "AGENTS.md").read_bytes() != checkpoint_agents
            or directory_digest(project / ".itd") != checkpoint_contracts)
        check("continuation performs no re-adoption writes",
              metrics["reAdoptionWrites"] == 0)

        events = (project / ".itd-memory" / "events.jsonl").read_text(
            encoding="utf-8")
        check("durable event ledger records both unit transitions",
              all(token in events for token in (
                  '"name": "U-001"', '"decision": "verified"',
                  '"name": "U-002"', '"decision": "activated"')))

    check("recovered-context threshold",
          metrics["recoveredContextMarkers"]
          >= thresholds["minRecoveredContextMarkers"])
    check("manual-context threshold",
          metrics["manualContextReentry"]
          <= thresholds["maxManualContextReentry"])
    check("wrong-unit threshold",
          metrics["wrongUnitActivations"]
          <= thresholds["maxWrongUnitActivations"])
    check("re-adoption-write threshold",
          metrics["reAdoptionWrites"]
          <= thresholds["maxReAdoptionWrites"])
    check("baseline-regression threshold",
          metrics["baselineRegressions"]
          <= thresholds["maxBaselineRegressions"])
    check("all required continuation outcomes",
          metrics["continuationVerified"]
          and metrics["wipOneEnforced"]
          and metrics["freshHostHome"],
          json.dumps(metrics, sort_keys=True))
    metrics["elapsedSeconds"] = round(time.monotonic() - started, 3)
    print("METRICS " + json.dumps(metrics, sort_keys=True))
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print("ALL PASS — existing project resumed without manual context reconstruction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
