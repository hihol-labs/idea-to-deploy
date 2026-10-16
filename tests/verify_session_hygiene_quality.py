#!/usr/bin/env python3
"""Behavioural proof for session-close, cleanup, quality, and ablation contracts."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "docs" / "templates" / "itd" / "itd_hygiene.py"
FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"PASS  {label}")
    else:
        FAILURES.append(label)
        print(f"FAIL  {label}: {detail[:400]}")


def run(args: list[str], cwd: Path,
        env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return run(["git", *args], repo)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def command(code: str) -> str:
    return subprocess.list2cmdline([sys.executable, "-c", code])


def quality_row(mid: str, grade: str, evidence: str) -> dict:
    return {
        "id": mid,
        "grade": grade,
        "verification": "passing",
        "agentUnderstandable": "yes",
        "testStability": "stable",
        "architectureBoundaries": "compliant",
        "codeConventions": "followed",
        "reviewedAt": dt.date.today().isoformat(),
        "evidence": [evidence],
        "priorities": [],
    }


def init_repo(base: Path) -> Path:
    repo = base / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    write_json(repo / ".itd-memory" / "STATE.json", {"currentUnit": {"status": "verified"}})
    write_json(repo / ".itd-memory" / "session-artifacts.json",
               {"version": 1, "artifacts": []})
    write_json(repo / ".itd" / "QUALITY.json", {
        "version": 1,
        "reviewedAt": dt.date.today().isoformat(),
        "maxAgeDays": 30,
        "modules": [quality_row("app", "A", "src/app.py")],
    })
    write_json(repo / ".itd" / "VERIFICATION_CONTRACT.json", {
        "version": 1,
        "commands": [{
            "id": "tests",
            "command": command("raise SystemExit(0)"),
            "timeoutSeconds": 30,
            "expectedOutput": "",
            "passFailParser": "exit_code_zero",
        }],
    })
    write_json(repo / ".itd" / "SESSION_EXIT_CONTRACT.json", {
        "version": 1,
        "mode": "explicit_close",
        "verificationContract": ".itd/VERIFICATION_CONTRACT.json",
        "requireCleanGit": True,
        "requiredStateFiles": [".itd-memory/STATE.json"],
        "startupProbeCommand": command("raise SystemExit(0)"),
        "cleanupManifest": ".itd-memory/session-artifacts.json",
        "qualityLedger": ".itd/QUALITY.json",
        "qualityMaxAgeDays": 30,
        "debugScan": {
            "enabled": True,
            "paths": ["src"],
            "excludeGlobs": [],
            "patterns": [r"\bconsole\.log\s*\(", r"\bdebugger\b", r"\bTODO\b"],
        },
        "periodic": {
            "weeklyMaxAgeDays": 7,
            "weeklyCommands": [{
                "id": "weekly",
                "command": command("raise SystemExit(0)"),
                "timeoutSeconds": 30,
                "passFailParser": "exit_code_zero",
            }],
            "monthlyAblationMaxAgeDays": 31,
        },
    })
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "fixture")
    return repo


def runner(repo: Path, *args: str,
           env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return run([sys.executable, str(RUNNER), *args, "--root", str(repo)],
               repo, env)


def test_cleanup() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-hygiene-cleanup-") as td:
        repo = init_repo(Path(td))
        artifact = repo / "tmp" / "debug.log"
        artifact.parent.mkdir()
        artifact.write_text("temporary\n", encoding="utf-8")
        write_json(repo / ".itd-memory" / "session-artifacts.json", {
            "version": 1,
            "artifacts": [{"path": "tmp/debug.log", "createdBySession": True}],
        })
        git(repo, "add", ".itd-memory/session-artifacts.json")
        git(repo, "commit", "-qm", "manifest")
        first = runner(repo, "cleanup")
        second = runner(repo, "cleanup")
        check("cleanup removes declared untracked file", first.returncode == 0 and not artifact.exists(), first.stdout)
        check("cleanup second run is idempotent and quiet",
              second.returncode == 0 and not second.stdout.strip(), second.stdout)

        write_json(repo / ".itd-memory" / "session-artifacts.json", {
            "version": 1,
            "artifacts": [{"path": "src/app.py", "createdBySession": True}],
        })
        blocked = runner(repo, "cleanup")
        check("cleanup refuses tracked paths",
              blocked.returncode == 1 and (repo / "src" / "app.py").exists()
              and "tracked paths" in blocked.stdout, blocked.stdout)

        write_json(repo / ".itd-memory" / "session-artifacts.json", {
            "version": 1,
            "artifacts": [{"path": "../outside", "createdBySession": True}],
        })
        escaped = runner(repo, "cleanup")
        check("cleanup refuses paths outside root",
              escaped.returncode == 1 and "escapes the repository" in escaped.stdout,
              escaped.stdout)


def test_close_conjunction() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-hygiene-close-") as td:
        repo = init_repo(Path(td))
        green = runner(repo, "close")
        check("close passes only on verified clean state",
              green.returncode == 0 and not green.stdout.strip(), green.stdout)

        (repo / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
        dirty = runner(repo, "close")
        check("close rejects dirty git state",
              dirty.returncode == 1 and "working tree is dirty" in dirty.stdout,
              dirty.stdout)
        git(repo, "checkout", "--", "src/app.py")

        (repo / "src" / "app.py").write_text("console.log('debug')\n", encoding="utf-8")
        git(repo, "add", "src/app.py")
        git(repo, "commit", "-qm", "seed debug")
        debug = runner(repo, "close")
        check("close scans committed debug code, not only the diff",
              debug.returncode == 1 and "debug marker remains" in debug.stdout,
              debug.stdout)

        (repo / "src" / "app.py").write_text("VALUE = 3\n", encoding="utf-8")
        git(repo, "add", "src/app.py")
        git(repo, "commit", "-qm", "remove debug")
        verification = json.loads((repo / ".itd" / "VERIFICATION_CONTRACT.json").read_text())
        verification["commands"][0]["command"] = command("raise SystemExit(7)")
        write_json(repo / ".itd" / "VERIFICATION_CONTRACT.json", verification)
        git(repo, "add", ".itd/VERIFICATION_CONTRACT.json")
        git(repo, "commit", "-qm", "seed failing verification")
        red = runner(repo, "close")
        check("close rejects failed verification",
              red.returncode == 1 and "tests:" in red.stdout, red.stdout)

        verification["version"] = 2
        verification["commands"][0]["command"] = command("raise SystemExit(0)")
        verification["commands"][0]["trustedVerifierPaths"] = ["src/app.py"]
        write_json(repo / ".itd" / "VERIFICATION_CONTRACT.json", verification)
        git(repo, "add", ".itd/VERIFICATION_CONTRACT.json")
        git(repo, "commit", "-qm", "seed argv bypass")
        bypass = runner(repo, "close")
        check("v2 close rejects a legacy shell command without argv",
              bypass.returncode == 1
              and "shell-free argv is missing or malformed" in bypass.stdout,
              bypass.stdout)

        verification["commands"][0]["argv"] = [
            sys.executable, "-c", "raise SystemExit(0)"
        ]
        verification["commands"][0].pop("trustedVerifierPaths")
        write_json(repo / ".itd" / "VERIFICATION_CONTRACT.json", verification)
        git(repo, "add", ".itd/VERIFICATION_CONTRACT.json")
        git(repo, "commit", "-qm", "seed missing trust binding")
        unbound = runner(repo, "close")
        check("v2 close rejects an unbound verifier argv",
              unbound.returncode == 1
              and "trustedVerifierPaths" in unbound.stdout,
              unbound.stdout)

        verification["commands"][0]["trustedVerifierPaths"] = ["src/app.py"]
        for label, changes, needle in (
            ("malformed timeout", {"timeoutSeconds": "invalid"},
             "timeoutSeconds is invalid"),
            ("NUL argv", {"timeoutSeconds": 30,
                          "argv": [sys.executable, "src/app.py\0"]},
             "argv is missing or malformed"),
        ):
            verification["commands"][0].update(changes)
            write_json(repo / ".itd/VERIFICATION_CONTRACT.json", verification)
            malformed = runner(repo, "close")
            check(f"v2 close rejects {label}",
                  malformed.returncode == 1 and needle in malformed.stdout)

        verification["commands"][0]["argv"] = [
            sys.executable, "-I", "src/app.py"]
        write_json(repo / ".itd" / "VERIFICATION_CONTRACT.json", verification)
        git(repo, "add", ".itd/VERIFICATION_CONTRACT.json")
        git(repo, "commit", "-qm", "seed local v2 verifier")
        no_base = runner(repo, "close")
        check("v2 local close validates against clean HEAD without external base",
              no_base.returncode == 0,
              no_base.stdout)

        protected_base = git(repo, "rev-parse", "HEAD").stdout.strip()
        protected_env = os.environ.copy()
        protected_env["ITD_PROTECTED_BASE_SHA"] = protected_base
        protected = runner(repo, "close", env=protected_env)
        check("v2 close accepts a protected-base-identical verifier",
              protected.returncode == 0, protected.stdout)

        verification["commands"][0]["passFailParser"] = "stdout_contains"
        write_json(repo / ".itd" / "VERIFICATION_CONTRACT.json", verification)
        git(repo, "add", ".itd/VERIFICATION_CONTRACT.json")
        git(repo, "commit", "-qm", "mutate contract")
        mutated_contract = runner(repo, "close", env=protected_env)
        check("v2 close rejects protected contract mutation",
              mutated_contract.returncode == 1
              and "contract differs from protected base" in mutated_contract.stdout)
        verification["commands"][0]["passFailParser"] = "exit_code_zero"
        write_json(repo / ".itd" / "VERIFICATION_CONTRACT.json", verification)
        git(repo, "add", ".itd/VERIFICATION_CONTRACT.json")
        git(repo, "commit", "-qm", "restore contract")

        (repo / "src" / "app.py").write_text("VALUE = 4\n", encoding="utf-8")
        git(repo, "add", "src/app.py")
        git(repo, "commit", "-qm", "replace verifier")
        replaced = runner(repo, "close", env=protected_env)
        check("v2 close rejects verifier replacement after protected base",
              replaced.returncode == 1
              and "differs from protected base" in replaced.stdout,
              replaced.stdout)

        verification["commands"][0]["argv"] = [
            "bash", "-c", "printf ALL_PASS", "src/app.py"
        ]
        write_json(repo / ".itd" / "VERIFICATION_CONTRACT.json", verification)
        git(repo, "add", ".itd/VERIFICATION_CONTRACT.json")
        git(repo, "commit", "-qm", "seed inert trusted argument")
        inert_base = git(repo, "rev-parse", "HEAD").stdout.strip()
        protected_env["ITD_PROTECTED_BASE_SHA"] = inert_base
        inert = runner(repo, "close", env=protected_env)
        check("v2 close rejects shell code with an inert trusted argument",
              inert.returncode == 1
              and "directly invoke a trusted verifier" in inert.stdout,
              inert.stdout)

        (repo / "src" / "target.py").write_text(
            "raise SystemExit(0)\n", encoding="utf-8")
        (repo / "src" / "app.py").unlink()
        (repo / "src" / "app.py").symlink_to("target.py")
        verification["commands"][0]["argv"] = [sys.executable, "-I", "src/app.py"]
        write_json(repo / ".itd" / "VERIFICATION_CONTRACT.json", verification)
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "seed trusted symlink")
        protected_env["ITD_PROTECTED_BASE_SHA"] = (
            git(repo, "rev-parse", "HEAD").stdout.strip()
        )
        symlink = runner(repo, "close", env=protected_env)
        check("v2 close rejects a protected-base-identical symlink",
              symlink.returncode == 1
              and "not a regular tracked file/tree" in symlink.stdout)


def test_quality() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-hygiene-quality-") as td:
        repo = init_repo(Path(td))
        quality = json.loads((repo / ".itd" / "QUALITY.json").read_text())
        quality["modules"] = [
            quality_row("healthy", "A", "src/app.py"),
            quality_row("repair-first", "C", "src/app.py"),
        ]
        write_json(repo / ".itd" / "QUALITY.json", quality)
        ranked = runner(repo, "quality")
        lines = [line for line in ranked.stdout.splitlines() if line.strip()]
        check("quality report ranks the lowest grade first",
              ranked.returncode == 0 and lines and "repair-first" in lines[0], ranked.stdout)

        quality["modules"][1]["reviewedAt"] = "2000-01-01"
        write_json(repo / ".itd" / "QUALITY.json", quality)
        stale = runner(repo, "quality")
        check("quality report fails stale rows",
              stale.returncode == 1 and "quality row is stale" in stale.stderr,
              stale.stderr)


def test_objective_quality_scorecard() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-hygiene-scorecard-") as td:
        repo = init_repo(Path(td))
        pass_cmd = command("raise SystemExit(0)")
        fail_cmd = command("raise SystemExit(3)")
        write_json(repo / ".itd" / "QUALITY_SCORECARD.json", {
            "version": 1,
            "qualityLedger": ".itd/QUALITY.json",
            "gradeThresholds": {"A": 90, "B": 80, "C": 70, "D": 60, "F": 0},
            "failOnOverstatedGrade": True,
            "probes": [
                {"id": "pass", "command": pass_cmd, "attempts": 1,
                 "timeoutSeconds": 30, "passFailParser": "exit_code_zero"},
                {"id": "repeat", "command": pass_cmd, "attempts": 2,
                 "timeoutSeconds": 30, "passFailParser": "exit_code_zero"},
                {"id": "fail", "command": fail_cmd, "attempts": 1,
                 "timeoutSeconds": 30, "passFailParser": "exit_code_zero"},
            ],
            "modules": [{
                "id": "app",
                "minimumScore": 70,
                "dimensions": {
                    "verification": {"weight": 20, "probes": ["pass"]},
                    "agentUnderstandable": {"weight": 20, "probes": ["pass"]},
                    "testStability": {"weight": 20, "probes": ["repeat"]},
                    "architectureBoundaries": {"weight": 20, "probes": ["fail"]},
                    "codeConventions": {"weight": 20, "probes": ["pass"]},
                },
            }],
        })
        quality = json.loads((repo / ".itd" / "QUALITY.json").read_text())
        quality["modules"][0]["grade"] = "C"
        write_json(repo / ".itd" / "QUALITY.json", quality)
        today = dt.date.today().isoformat()
        scored = runner(repo, "quality", "--scorecard", ".itd/QUALITY_SCORECARD.json",
                        "--record", "--today", today, "--json")
        record_path = repo / ".itd-memory" / "hygiene" / f"quality-score-{today}.json"
        record = json.loads(record_path.read_text()) if record_path.exists() else {}
        module = (record.get("modules") or [{}])[0]
        attempts = ((record.get("probes") or {}).get("repeat") or {}).get("attempts")
        check("objective scorecard computes weighted grade and records probe evidence",
              scored.returncode == 0 and module.get("score") == 80.0
              and module.get("computedGrade") == "B" and attempts and len(attempts) == 2,
              scored.stdout + scored.stderr)

        quality["modules"][0]["grade"] = "A"
        write_json(repo / ".itd" / "QUALITY.json", quality)
        overstated = runner(repo, "quality", "--scorecard", ".itd/QUALITY_SCORECARD.json",
                            "--record", "--today", today, "--json")
        try:
            payload = json.loads(overstated.stdout)
        except Exception:
            payload = {}
        scored_module = (payload.get("modules") or [{}])[0]
        check("objective scorecard fails an overstated declared grade",
              overstated.returncode == 1 and scored_module.get("overstatedGrade") is True
              and "declared grade A exceeds computed B" in " ".join(payload.get("errors") or []),
              overstated.stdout + overstated.stderr)

        scorecard = json.loads((repo / ".itd" / "QUALITY_SCORECARD.json").read_text())
        scorecard["probes"][0]["metricScale"] = "not-a-number"
        write_json(repo / ".itd" / "QUALITY_SCORECARD.json", scorecard)
        invalid = runner(repo, "quality", "--scorecard", ".itd/QUALITY_SCORECARD.json",
                         "--record", "--today", today, "--json")
        try:
            invalid_payload = json.loads(invalid.stdout)
        except Exception:
            invalid_payload = {}
        check("objective scorecard rejects invalid numeric settings without crashing",
              invalid.returncode == 1 and "metricScale must be positive" in
              " ".join(invalid_payload.get("errors") or []) and "Traceback" not in invalid.stderr,
              invalid.stdout + invalid.stderr)


def test_external_scheduler_contract() -> None:
    workflow = ROOT / ".github" / "workflows" / "hygiene-schedule.yml"
    text = workflow.read_text(encoding="utf-8") if workflow.exists() else ""
    checks = {
        "external scheduler has weekly cron": "17 3 * * 1" in text,
        "external scheduler has monthly cron": "29 4 1 * *" in text,
        "external scheduler supports manual dispatch": "workflow_dispatch" in text,
        "scheduler transport is read-only": "contents: read" in text and "contents: write" not in text,
        "weekly job runs cleanup and objective scorecard":
            "periodic --mode weekly" in text and "quality --scorecard" in text,
        "monthly job runs reversible ablation": "periodic --mode monthly" in text,
        "scheduler records and uploads evidence even on failure":
            "--record" in text and "actions/upload-artifact@v4" in text and "if: always()" in text,
        "active objective scorecard exists": (ROOT / "docs" / "QUALITY_SCORECARD.json").is_file(),
        "adoptable objective scorecard template exists":
            (ROOT / "docs" / "templates" / "itd" / "QUALITY_SCORECARD.json").is_file(),
        "adoptable external scheduler template exists":
            (ROOT / "docs" / "templates" / "github" / "itd-hygiene.yml").is_file(),
    }
    for label, ok in checks.items():
        check(label, ok)


def test_periodic_cycles() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-hygiene-periodic-") as td:
        repo = init_repo(Path(td))
        artifact = repo / "tmp" / "weekly.log"
        artifact.parent.mkdir()
        artifact.write_text("temporary\n", encoding="utf-8")
        write_json(repo / ".itd-memory" / "session-artifacts.json", {
            "version": 1,
            "artifacts": [{"path": "tmp/weekly.log", "createdBySession": True}],
        })
        weekly = runner(repo, "periodic", "--mode", "weekly", "--record",
                        "--today", dt.date.today().isoformat())
        weekly_record = (repo / ".itd-memory" / "hygiene" /
                         f"weekly-{dt.date.today().isoformat()}.json")
        check("weekly cycle cleans, validates quality, runs checks, records evidence",
              weekly.returncode == 0 and not artifact.exists() and weekly_record.exists(),
              weekly.stdout)
        again = runner(repo, "periodic", "--mode", "weekly", "--record",
                       "--today", dt.date.today().isoformat())
        check("weekly cycle is idempotent on repeat", again.returncode == 0, again.stdout)

        bench = command(
            "import json,os; print(json.dumps({'score': 0 if os.getenv('FEATURE_OFF') else 1}))")
        write_json(repo / ".itd" / "HARNESS_ABLATION.json", {
            "version": 1,
            "cadenceDays": 31,
            "lastExperiment": {"date": "", "component": "", "evidence": "", "decision": ""},
            "candidates": [{
                "id": "feature",
                "component": "feature",
                "disableEnv": {"FEATURE_OFF": "1"},
                "benchmarkCommands": [{
                    "id": "score",
                    "command": bench,
                    "metricParser": "json_number",
                    "metricField": "score",
                    "higherIsBetter": True,
                    "maxRegression": 0.0,
                }],
            }],
        })
        monthly = runner(repo, "periodic", "--mode", "monthly", "--component",
                         "feature", "--record", "--today", dt.date.today().isoformat())
        monthly_record = (repo / ".itd-memory" / "hygiene" /
                          f"ablation-{dt.date.today().isoformat()}-feature.json")
        record = json.loads(monthly_record.read_text()) if monthly_record.exists() else {}
        check("monthly ablation compares baseline vs disabled and recommends restore",
              monthly.returncode == 1 and record.get("recommendation") == "restore"
              and record.get("humanDecision") == "pending", monthly.stdout)


def test_fixed_component_benchmark() -> None:
    bench = ROOT / "benchmarks" / "harness-components" / "completion-stop.py"
    normal = run([sys.executable, str(bench)], ROOT)
    env = dict(os.environ)
    env["ITD_COMPLETION_STOP"] = "0"
    disabled = subprocess.run([sys.executable, str(bench)], cwd=str(ROOT), env=env,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
    try:
        normal_score = json.loads(normal.stdout)["score"]
        disabled_score = json.loads(disabled.stdout)["score"]
    except Exception:
        normal_score = disabled_score = None
    check("fixed benchmark measures completion-stop value under its kill switch",
          normal.returncode == 0 and disabled.returncode == 0
          and normal_score == 1 and disabled_score == 0,
          f"normal={normal.stdout!r} disabled={disabled.stdout!r}")


def test_integration_contract() -> None:
    session = (ROOT / "skills" / "session-save" / "SKILL.md").read_text(encoding="utf-8")
    task = (ROOT / "skills" / "task" / "SKILL.md").read_text(encoding="utf-8")
    retro = (ROOT / "skills" / "retro" / "SKILL.md").read_text(encoding="utf-8")
    adopt = (ROOT / "skills" / "adopt" / "SKILL.md").read_text(encoding="utf-8")
    global_rules = (ROOT / "docs" / "templates" / "global-claude-md.md").read_text(encoding="utf-8")
    run_all = (ROOT / "tests" / "run-all.sh").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "meta-review.yml").read_text(encoding="utf-8")
    checks = {
        "/session-save exposes explicit close mode": "itd_hygiene.py close" in session,
        "/task reads quality ledger before scope": "itd_hygiene.py quality" in task,
        "/retro carries weekly and monthly cycles": all(
            token in retro for token in ("periodic --mode weekly", "periodic --mode monthly")),
        "/adopt fills new contracts": all(
            token in adopt for token in ("SESSION_EXIT_CONTRACT.json", "QUALITY.json",
                                         "QUALITY_SCORECARD.json", "HARNESS_ABLATION.json")),
        "global completion rule names explicit close": "/session-save --close" in global_rules,
        "run-all includes focused gate": "verify_session_hygiene_quality" in run_all,
        "CI includes focused gate": "verify_session_hygiene_quality.py" in ci,
        "methodology repo has a filled close verification contract":
            (ROOT / "docs" / "VERIFICATION_CONTRACT.json").is_file(),
    }
    for label, ok in checks.items():
        check(label, ok)


def test_methodology_debug_scan_exclusions() -> None:
    contract = json.loads((ROOT / "docs" / "SESSION_EXIT_CONTRACT.json").read_text(
        encoding="utf-8"))
    exclusions = set(contract.get("debugScan", {}).get("excludeGlobs", []))
    expected = {
        "skills/browser-check/playwright/run.js",
        "tests/verify_session_hygiene_quality.py",
    }
    check(
        "methodology close excludes only known non-debug console.log sites",
        expected.issubset(exclusions),
        f"missing={sorted(expected - exclusions)}",
    )


SESSION_CLOSE_RESOLVER = (
    'T="skills/_shared"; for d in "$HOME/.claude/skills/_shared" "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-/nonexistent}}/skills/_shared"; do [ -f "$d/itd_tool.sh" ] && T="$d"; done',
    '[ "$T" = skills/_shared ] && C=$(ls -d "$HOME"/.codex/plugins/cache/*/idea-to-deploy/*/skills/_shared 2>/dev/null | awk -F/ \'{print $(NF-2), $0}\' | sort -k1,1V | tail -1 | cut -d" " -f2-) && [ -f "${C:-/}/itd_tool.sh" ] && T="$C"',
    'CONTRACT="$(sh "$T/itd_py.sh" "$T/itd_contract_dir.py" SESSION_EXIT_CONTRACT.json)/SESSION_EXIT_CONTRACT.json"',
    'sh "$T/itd_tool.sh" itd_hygiene.py close --root . --contract "$CONTRACT"',
)
# CLOSE-DEBT-1 (2026-10-16): the startup probe is a bounded smoke of the shipped runtime (the
# installed-runtime inventory, 3 s offline), not a second quick mirror. The mirror runs exactly
# once, as the argv-bound `quick-regression` verifier of the verification contract, and its budget
# follows the measurement: 408 s unloaded on 2026-10-16, a timeout at 600 s under load, so 1200.
STARTUP_TIMEOUT_FLOOR = 60
QUICK_REGRESSION_FLOOR = 1200
QUICK_MIRROR_RE = re.compile(r"run-all\.sh\s+--quick|verify_quick_regression")
_spec = importlib.util.spec_from_file_location(
    "itd_contract_dir_model", ROOT / "skills" / "_shared" / "itd_contract_dir.py")
assert _spec is not None and _spec.loader is not None
CONTRACT_DIR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CONTRACT_DIR)


def startup_timeout_fits(contract: dict) -> bool:
    declared = contract.get("startupTimeoutSeconds")
    return type(declared) is int and declared >= STARTUP_TIMEOUT_FLOOR


def applied_session_close_contract(root: Path) -> Path:
    # The resolver pinned above, evaluated without a shell: on native Windows a
    # bare `bash` can resolve to the WSL shim, so the test models the pinned text
    # instead of executing it. Any edit to the resolver turns the pin below red
    # before this model can drift from it.
    # INSTALL-OWNED-1: the runner always comes from the installation; only the
    # contract differs - docs/ in the methodology repository (the parsed plugin
    # manifest names it, see skills/_shared/itd_contract_dir.py, and the docs/
    # contract exists - the helper checks both), .itd/ everywhere else. The model
    # calls the same helper with the same contract name.
    return root / CONTRACT_DIR.contract_dir(root, ["SESSION_EXIT_CONTRACT.json"]) / "SESSION_EXIT_CONTRACT.json"


def test_methodology_startup_timeout_declared() -> None:
    # The session-save resolver selects the contract (docs/ in the methodology
    # repository, .itd/ elsewhere), so the contract that runs is whatever the
    # resolver selects, not whichever file one expects. Keep the startup budget
    # explicit: the runtime smoke and the quick regression have separate limits.
    skill = (ROOT / "skills" / "session-save" / "SKILL.md").read_text(encoding="utf-8")
    lines = skill.splitlines()
    # The installation-first helper line also opens other snippets of the skill;
    # the close resolver is the one place where the whole pinned block occurs.
    anchors = [i for i in range(len(lines))
               if tuple(lines[i:i + len(SESSION_CLOSE_RESOLVER)]) == SESSION_CLOSE_RESOLVER]
    resolver = SESSION_CLOSE_RESOLVER if len(anchors) == 1 else ()
    check(
        "session-save resolver is the one this pin models",
        resolver == SESSION_CLOSE_RESOLVER,
        f"anchors={len(anchors)} resolver={list(resolver)!r}",
    )

    applied = applied_session_close_contract(ROOT)
    check(
        "the applied session-close contract exists",
        applied.is_file(),
        str(applied.relative_to(ROOT)),
    )
    contract = json.loads(applied.read_text(encoding="utf-8")) if applied.is_file() else {}
    check(
        "methodology close declares a bounded startup timeout",
        startup_timeout_fits(contract),
        f"{applied.name}: startupTimeoutSeconds={contract.get('startupTimeoutSeconds')!r}",
    )
    probe = str(contract.get("startupProbeCommand") or "")
    check(
        "the startup probe is a smoke of the shipped runtime, not a second quick mirror",
        "verify_itd_runtime_install" in probe and not QUICK_MIRROR_RE.search(probe),
        probe,
    )
    verification_rel = str(contract.get("verificationContract") or "")
    verification_path = applied.parent.parent / verification_rel if applied.is_file() else None
    try:
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - reported by the check below
        verification = {}
    quick = [c for c in verification.get("commands", []) if c.get("id") == "quick-regression"]
    check(
        "the quick mirror runs once, as the verification contract's quick-regression, with a measured budget",
        len(quick) == 1 and type(quick[0].get("timeoutSeconds")) is int
        and quick[0]["timeoutSeconds"] >= QUICK_REGRESSION_FLOOR
        and QUICK_MIRROR_RE.search(" ".join(quick[0].get("argv") or [])) is not None,
        f"{verification_rel}: {quick}",
    )
    live = [c for c in verification.get("commands", [])
            if c.get("id") == "live-model-evidence"]
    check(
        "methodology close replays the same strict live evidence as CI",
        len(live) == 1
        and live[0].get("argv") == [
            "python3", "-I", "tests/verify_live_model_benchmark.py",
            "--require-evidence", "--max-age-days", "30",
        ]
        and type(live[0].get("timeoutSeconds")) is int
        and 60 <= live[0]["timeoutSeconds"] <= 180
        and live[0].get("passFailParser") == "stdout_contains"
        and live[0].get("expectedOutput") == "passed, 0 failed"
        and {
            "tests/verify_live_model_benchmark.py", "tests/itd_benchmark_pin.py",
            "tests/run-live-model-benchmark.py", "tests/verify_snapshot.py",
        }.issubset(live[0].get("trustedVerifierPaths") or []),
        f"{verification_rel}: {live}",
    )

    # RED side of the same predicate, asserted on every run: the state the 2026-09-15
    # unit repaired (no key), a limit too tight for any probe (30, 59),
    # and the non-integer forms must all be refused.
    without_key = {k: v for k, v in contract.items() if k != "startupTimeoutSeconds"}
    refused = {
        "no key": without_key,
        "30": {**without_key, "startupTimeoutSeconds": 30},
        "59": {**without_key, "startupTimeoutSeconds": 59},
        "string": {**without_key, "startupTimeoutSeconds": "180"},
        "bool": {**without_key, "startupTimeoutSeconds": True},
        "float": {**without_key, "startupTimeoutSeconds": 180.0},
    }
    leaked = sorted(name for name, value in refused.items() if startup_timeout_fits(value))
    check(
        "the startup timeout predicate refuses every too-tight or malformed limit",
        not leaked,
        f"accepted={leaked}",
    )

    # The resolver model itself: both branches, on throwaway roots.
    with tempfile.TemporaryDirectory() as td:
        base = Path(td).resolve()
        methodology = base / "methodology"
        (methodology / ".claude-plugin").mkdir(parents=True)
        (methodology / ".claude-plugin" / "plugin.json").write_text('{\n  "name": "idea-to-deploy"\n}\n', encoding="utf-8")
        (methodology / "docs").mkdir()
        (methodology / "docs" / "SESSION_EXIT_CONTRACT.json").write_text("{}", encoding="utf-8")
        project = base / "project"
        (project / ".itd").mkdir(parents=True)
        (project / "docs" / "templates" / "itd").mkdir(parents=True)
        # Neither a legacy runner copy, nor a docs/templates/itd/itd_hygiene.py, nor a docs/ contract of its own
        # makes an ordinary project the methodology repository (INSTALL-OWNED-1).
        (project / ".itd" / "itd_hygiene.py").write_text("", encoding="utf-8")
        (project / "docs" / "templates" / "itd" / "itd_hygiene.py").write_text("", encoding="utf-8")
        (project / "docs" / "SESSION_EXIT_CONTRACT.json").write_text("{}", encoding="utf-8")
        (project / ".claude-plugin").mkdir()
        (project / ".claude-plugin" / "plugin.json").write_text('{"name": "my-app"}', encoding="utf-8")
        no_docs = base / "no-docs"
        (no_docs / ".claude-plugin").mkdir(parents=True)
        (no_docs / ".claude-plugin" / "plugin.json").write_text('{"name": "idea-to-deploy"}', encoding="utf-8")
        check(
            "resolver model never picks a docs/ contract that does not exist",
            applied_session_close_contract(no_docs) == no_docs / ".itd" / "SESSION_EXIT_CONTRACT.json",
        )
        check(
            "resolver model follows the docs contract in the methodology repository",
            applied_session_close_contract(methodology)
            == methodology / "docs" / "SESSION_EXIT_CONTRACT.json",
        )
        check(
            "resolver model keeps the project contract in an ordinary project that carries methodology-like paths",
            applied_session_close_contract(project)
            == project / ".itd" / "SESSION_EXIT_CONTRACT.json",
        )


def test_cleanup_requires_tracking_proof() -> None:
    # S2 deletion-safety pin: when git cannot prove tracking state (any rc
    # outside {0,1}, including the degraded rc=127 spawn fallback), cleanup
    # must refuse to delete instead of reading the failure as "untracked".
    # POSIX-only like the spawn-pressure pin: Windows CreateProcess resolves
    # "git" to git.exe only, so a .cmd shim never intercepts the runner's
    # subprocess.run(["git", ...]) and the scenario cannot be staged there.
    if os.name != "posix":
        return
    with tempfile.TemporaryDirectory(prefix="itd-hygiene-gitfail-") as td:
        repo = init_repo(Path(td))
        artifact = repo / "tmp" / "debug.log"
        artifact.parent.mkdir()
        artifact.write_text("temporary\n", encoding="utf-8")
        write_json(repo / ".itd-memory" / "session-artifacts.json", {
            "version": 1,
            "artifacts": [{"path": "tmp/debug.log", "createdBySession": True}],
        })
        shims = Path(td) / "shims"
        shims.mkdir()
        shim = shims / "git"
        shim.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")
        shim.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = str(shims) + os.pathsep + env.get("PATH", "")
        broken = runner(repo, "cleanup", env=env)
        check("cleanup refuses deletion without tracking proof",
              broken.returncode == 1 and artifact.exists()
              and "tracking state could not be proven" in broken.stdout,
              f"rc={broken.returncode} stdout={broken.stdout[:200]!r}")


def test_close_survives_spawn_pressure() -> None:
    # S2 flake pin (BACKLOG 2026-08-11): a transient fork failure (EAGAIN under
    # host process pressure) inside the runner used to crash `close` with an
    # empty stdout, which this suite then misread as a wrong gate verdict
    # ("close rejects dirty git state" with no detail).  RLIMIT_NPROC=1 makes
    # every internal spawn fail deterministically; the runner must still emit
    # a structured fail-closed report instead of dying with a traceback.
    if os.name != "posix":
        return
    import resource

    def clamp() -> None:
        resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))

    with tempfile.TemporaryDirectory(prefix="itd-hygiene-pressure-") as td:
        repo = init_repo(Path(td))
        (repo / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(RUNNER), "close", "--root", str(repo)],
            cwd=str(repo), capture_output=True, text=True,
            encoding="utf-8", errors="replace", preexec_fn=clamp)
        check("close under spawn pressure fails closed with a structured report",
              proc.returncode == 1 and bool(proc.stdout.strip())
              and "Traceback" not in proc.stderr,
              f"rc={proc.returncode} stdout={proc.stdout[:200]!r} "
              f"stderr={proc.stderr[:200]!r}")
        check("close under spawn pressure names the degraded inspection",
              "could not" in proc.stdout,
              proc.stdout[:400])


def main() -> int:
    check("runner exists", RUNNER.is_file(), str(RUNNER))
    test_cleanup()
    test_cleanup_requires_tracking_proof()
    test_close_conjunction()
    test_close_survives_spawn_pressure()
    test_quality()
    test_objective_quality_scorecard()
    test_periodic_cycles()
    test_fixed_component_benchmark()
    test_external_scheduler_contract()
    test_integration_contract()
    test_methodology_debug_scan_exclusions()
    test_methodology_startup_timeout_declared()
    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} — " + ", ".join(FAILURES))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
