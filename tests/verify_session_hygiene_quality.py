#!/usr/bin/env python3
"""Behavioural proof for session-close, cleanup, quality, and ablation contracts."""
from __future__ import annotations

import datetime as dt
import json
import os
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


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


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


def runner(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return run([sys.executable, str(RUNNER), *args, "--root", str(repo)], repo)


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


def main() -> int:
    check("runner exists", RUNNER.is_file(), str(RUNNER))
    test_cleanup()
    test_close_conjunction()
    test_quality()
    test_objective_quality_scorecard()
    test_periodic_cycles()
    test_fixed_component_benchmark()
    test_external_scheduler_contract()
    test_integration_contract()
    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} — " + ", ".join(FAILURES))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
