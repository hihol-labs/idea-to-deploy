#!/usr/bin/env python3
"""Positive/negative behavioral probes for the deterministic 5/5 gate."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCORE = ROOT / "skills" / "goal" / "scripts" / "itd_goal_score.py"
PY = sys.executable
passed = failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS  {name}")
    else:
        failed += 1
        print(f"FAIL  {name}" + (f" — {detail}" if detail else ""))


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([PY, str(SCORE), *args], cwd=cwd,
                          capture_output=True, encoding="utf-8", errors="replace",
                          env={**os.environ, "PYTHONUTF8": "1"}, timeout=30)


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    oracle = {
        "version": 1,
        "sealedAt": "2026-07-14T00:00:00Z",
        "tasks": [
            {"id": f"P-{i}", "findings": [
                {"id": f"P-{i}-critical", "severity": "critical"},
                {"id": f"P-{i}-important", "severity": "important"},
            ]} for i in range(1, 6)
        ],
    }
    oracle_path = root / "oracle.json"
    write(oracle_path, oracle)
    oracle_hash = hashlib.sha256(oracle_path.read_bytes()).hexdigest()
    stop_path = root / "stop-evidence.txt"
    stop_path.write_text("35 passed, 0 failed\nALL PASS\n", encoding="utf-8")
    stop_hash = hashlib.sha256(stop_path.read_bytes()).hexdigest()
    pairs = []
    for i in range(1, 6):
        common = {
            "commit": "a" * 40,
            "tree": "b" * 40,
            "promptSha256": "c" * 64,
            "environmentSha256": "d" * 64,
            "startedAt": f"2026-07-14T0{i}:00:00Z",
            "infrastructureErrors": [],
        }
        pairs.append({
            "id": f"P-{i}",
            "riskTier": "high" if i == 5 else "medium",
            "order": "manual_first" if i % 2 else "loop_first",
            "manual": {**common, "wallSeconds": 100, "inputTokens": 1000,
                       "findingIds": [f"P-{i}-critical"]},
            "loop": {**common, "wallSeconds": 190 if i == 5 else 120,
                     "inputTokens": 1200,
                     "findingIds": [f"P-{i}-critical", f"P-{i}-important"]},
        })
    evaluation = {
        "version": 1,
        "oracle": {"path": "oracle.json", "sha256": oracle_hash},
        "pairs": pairs,
        "memory": {"repetitionsWithout": 10, "repetitionsWith": 4,
                   "contextTokensByRound": [1000, 1050, 1090],
                   "maxCheckpointBytesObserved": 1200,
                   "controlIsolated": True, "stateReadViolations": 0},
        "quiz": {"immediateScore": 0.9, "delayed24hScore": 0.85,
                 "immediateAt": "2026-07-14T08:00:00Z",
                 "delayedAt": "2026-07-15T08:00:00Z",
                 "criticalUnknownCount": 0},
        "cognitiveSurrenderCount": 0,
        "budgets": {"stopTestsPassed": True, "extraRoundsAfterDod": 0,
                    "evidencePath": "stop-evidence.txt",
                    "evidenceSha256": stop_hash},
    }
    eval_path = root / "evaluation.json"
    write(eval_path, evaluation)

    r = run(cwd=root)
    check("no input is a quiet no-op", r.returncode == 0 and not r.stdout.strip(),
          r.stdout + r.stderr)
    r = run("--input", str(eval_path), "--json", cwd=root)
    result = json.loads(r.stdout)
    check("clean five-pair evidence reaches exactly 5/5",
          r.returncode == 0 and result["status"] == "FIVE_STAR"
          and result["score"] == 5 and all(result["gates"].values()),
          r.stdout + r.stderr)

    contaminated = copy.deepcopy(evaluation)
    contaminated["pairs"][0]["loop"]["environmentSha256"] = "e" * 64
    contaminated_path = root / "contaminated.json"
    write(contaminated_path, contaminated)
    r = run("--input", str(contaminated_path), "--json", cwd=root)
    first = r.stdout.splitlines()[0]
    result = json.loads(first)
    check("environment mismatch invalidates the integrity point",
          r.returncode == 1 and result["score"] == 4
          and result["gates"]["integrity"] is False
          and "WHY" in r.stdout and "FIX" in r.stdout,
          r.stdout + r.stderr)

    weak_quality = copy.deepcopy(evaluation)
    for pair in weak_quality["pairs"]:
        pair["loop"]["findingIds"] = [f"{pair['id']}-important"]
    weak_path = root / "weak-quality.json"
    write(weak_path, weak_quality)
    r = run("--input", str(weak_path), "--json", cwd=root)
    result = json.loads(r.stdout.splitlines()[0])
    check("missed critical findings prevent a five-star score",
          r.returncode == 1 and result["gates"]["quality"] is False
          and result["metrics"]["missedCritical"], r.stdout + r.stderr)

    early_quiz = copy.deepcopy(evaluation)
    early_quiz["quiz"]["delayedAt"] = "2026-07-14T09:00:00Z"
    early_path = root / "early-quiz.json"
    write(early_path, early_quiz)
    r = run("--input", str(early_path), "--json", cwd=root)
    result = json.loads(r.stdout.splitlines()[0])
    check("an immediate rerun cannot masquerade as the 24-hour quiz",
          r.returncode == 1 and result["gates"]["understanding"] is False,
          r.stdout + r.stderr)

    larger_oracle = copy.deepcopy(oracle)
    larger_oracle["tasks"].append({"id": "P-6", "findings": [
        {"id": "P-6-critical", "severity": "critical"}]})
    larger_path = root / "larger-oracle.json"
    write(larger_path, larger_oracle)
    omitted = copy.deepcopy(evaluation)
    omitted["oracle"] = {
        "path": "larger-oracle.json",
        "sha256": hashlib.sha256(larger_path.read_bytes()).hexdigest(),
    }
    omitted_path = root / "omitted-oracle-task.json"
    write(omitted_path, omitted)
    r = run("--input", str(omitted_path), "--json", cwd=root)
    result = json.loads(r.stdout.splitlines()[0])
    check("omitting a frozen oracle task invalidates integrity",
          r.returncode == 1 and result["gates"]["integrity"] is False
          and result["metrics"]["oracleTaskCoverage"] is False,
          r.stdout + r.stderr)

    invalid = copy.deepcopy(evaluation)
    invalid["oracle"]["sha256"] = "0" * 64
    invalid_path = root / "invalid.json"
    write(invalid_path, invalid)
    r = run("--input", str(invalid_path), cwd=root)
    check("mutated oracle fails closed as invalid evidence",
          r.returncode == 2 and "WHY invalid evidence" in r.stdout,
          r.stdout + r.stderr)

print(f"\n{passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("ALL PASS")
