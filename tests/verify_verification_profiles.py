#!/usr/bin/env python3
"""Behavioural oracle for targeted/release, diagnostics, and backlog boundaries."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "skills" / "_shared" / "itd_verification_profiles.py"
WORK_POLICY = ROOT / "skills" / "_shared" / "WORKING_DEADLINE_POLICY.json"
PROPORTIONALITY_POLICY = ROOT / "skills" / "_shared" / "PROPORTIONALITY_POLICY.json"
WORK_CORPUS = ROOT / "benchmarks" / "working-deadline" / "CORPUS.json"
TASK_SKILL = ROOT / "skills" / "task" / "SKILL.md"
HELPERS = ROOT / "skills" / "_shared" / "helpers.md"
DOC = ROOT / "docs" / "WORKING_DEADLINE_MODE.md"
RUN_ALL = ROOT / "tests" / "run-all.sh"
PY = sys.executable
A = "a" * 64
B = "b" * 64

SPEC = importlib.util.spec_from_file_location("itd_verification_profiles", RUNTIME)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {RUNTIME}")
ENGINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS  {name}")
    else:
        failed += 1
        print(f"FAIL  {name}" + (f" — {detail}" if detail else ""))


def invoke(request: dict | None = None, runtime: Path = RUNTIME,
           subprocess_mode: bool = False) \
        -> tuple[subprocess.CompletedProcess, dict]:
    if request is not None and runtime == RUNTIME and not subprocess_mode:
        try:
            payload = ENGINE.decide(copy.deepcopy(request))
            rc = 0
        except ENGINE.DecisionError as exc:
            payload = {
                "status": "FAIL",
                "verified": False,
                "why": exc.why,
                "fix": exc.fix,
                **exc.fields,
            }
            rc = 1
        stdout = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return subprocess.CompletedProcess([], rc, stdout, ""), payload
    env = {**os.environ, "PYTHONUTF8": "1"}
    if request is None:
        result = subprocess.run(
            [PY, str(runtime)], cwd=str(ROOT), capture_output=True,
            encoding="utf-8", errors="replace", env=env, timeout=30,
        )
    else:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "request.json"
            path.write_text(json.dumps(request), encoding="utf-8")
            result = subprocess.run(
                [PY, str(runtime), "--input", str(path)], cwd=str(ROOT),
                capture_output=True, encoding="utf-8", errors="replace",
                env=env, timeout=30,
            )
    try:
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    return result, payload


def invoke_mutant(replacements: tuple[tuple[str, str], ...],
                  request: dict | None) -> tuple[subprocess.CompletedProcess, dict]:
    """Run a source mutant in an isolated policy tree; never touch the real source."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        shared = root / "skills" / "_shared"
        shared.mkdir(parents=True)
        source = RUNTIME.read_text(encoding="utf-8")
        for old, new in replacements:
            if old not in source:
                raise AssertionError(f"mutation target drifted: {old}")
            source = source.replace(old, new)
        runtime = shared / RUNTIME.name
        runtime.write_text(source, encoding="utf-8")
        (shared / WORK_POLICY.name).write_bytes(WORK_POLICY.read_bytes())
        (shared / PROPORTIONALITY_POLICY.name).write_bytes(
            PROPORTIONALITY_POLICY.read_bytes())
        return invoke(request, runtime)


def select_request(risk: str = "low", profile: str = "targeted") -> dict:
    return {
        "operation": "select",
        "profile": profile,
        "risk": risk,
        "signals": [],
        "impactKnown": True,
        "changed": ["api"],
        "impactGraph": {
            "api": ["service"],
            "service": ["tests"],
            "tests": [],
        },
        "requestedCapabilities": [],
    }


def diagnostics_request() -> dict:
    return {
        "operation": "diagnostics",
        "collectionComplete": True,
        "collectedBeforeFixes": True,
        "failures": [
            {"id": "F-1", "rootCause": "parser", "cascade": False},
            {"id": "F-2", "rootCause": "parser", "cascade": True},
            {"id": "F-3", "rootCause": "config", "cascade": False},
        ],
        "clusterHistory": [
            {
                "rootCause": "parser",
                "risky": True,
                "cheapDiscriminatingCheck": {"exitCode": 0},
            },
            {"rootCause": "config", "risky": False},
        ],
        "originalDiagnosticCommand": "python -m tests",
        "finalRerun": {"command": "python -m tests", "exitCode": 0},
    }


def backlog_request() -> dict:
    return {
        "operation": "backlog",
        "preExisting": True,
        "outOfScope": True,
        "nonBlocking": True,
        "introducedByCurrentDiff": False,
        "blockingKinds": [],
        "capture": {
            "path": "BACKLOG.md",
            "id": "BL-123",
            "summary": "Unrelated pre-existing formatting defect",
        },
    }


# Deployment baseline: no input means quiet no-op.
r, payload = invoke()
check("no input is a quiet no-op",
      r.returncode == 0 and not r.stdout and not r.stderr,
      r.stdout + r.stderr)

# Targeted profile: risk route + transitive impact + signals.
r, payload = invoke(select_request("low"))
check("low targeted selects only static contour",
      r.returncode == 0 and payload.get("route") == "working_deadline.targeted"
      and payload.get("contours") == ["static"], r.stdout + r.stderr)
check("targeted computes transitive impact closure",
      payload.get("impactClosure") == ["api", "service", "tests"], r.stdout)
check("required syntax capability cannot be removed by user criteria",
      payload.get("requiredCapabilities") == ["syntax"], r.stdout)

r, payload = invoke(select_request("medium"))
check("medium targeted keeps behavior contour",
      r.returncode == 0 and payload.get("contours") == ["static", "targeted"]
      and set(payload.get("requiredCapabilities") or []) == {"syntax", "behavior"},
      r.stdout + r.stderr)

request = select_request("medium")
request["signals"] = ["auth", "future-signal"]
r, payload = invoke(request)
check("known security signal adds security contour",
      r.returncode == 0 and payload.get("contours") == ["static", "targeted", "security"],
      r.stdout + r.stderr)
check("unknown signal is visible and invents no contour",
      payload.get("warnings") == ["unknown signal: future-signal"], r.stdout)

request = select_request("low")
request["changed"] = ["модуль"]
request["impactGraph"] = {"модуль": ["тесты"], "тесты": ["модуль"]}
r, payload = invoke(request)
check("impact closure is cycle-safe and unicode-safe",
      r.returncode == 0 and payload.get("impactClosure") == ["модуль", "тесты"],
      r.stdout + r.stderr)

for label, mutate in (
    ("high risk", lambda q: q.update(risk="high")),
    ("unknown risk", lambda q: q.update(risk="mystery")),
    ("unknown impact", lambda q: q.update(impactKnown=False)),
):
    request = select_request("medium")
    mutate(request)
    r, payload = invoke(request)
    check(f"{label} exits targeted to strict release",
          r.returncode == 0 and payload.get("route") == "strict.release"
          and payload.get("verified") is False
          and payload.get("contours") == ["static", "targeted", "review", "full"],
          r.stdout + r.stderr)

request = select_request("medium")
request["impactKnown"] = False
request.pop("impactGraph")
r, payload = invoke(request)
check("unknown impact needs no invented graph before strict release",
      r.returncode == 0 and payload.get("route") == "strict.release"
      and payload.get("impactClosure") == ["api"], r.stdout + r.stderr)

# Explicit release and exact-candidate evidence.
request = select_request("medium", "release")
request["candidateSha256"] = A
r, payload = invoke(request)
check("release selection binds the exact candidate hash",
      r.returncode == 0 and payload.get("route") == "strict.release"
      and payload.get("candidateSha256") == A, r.stdout + r.stderr)

request["signals"] = ["security"]
r, payload = invoke(request)
check("release selection preserves matching security contour",
      r.returncode == 0
      and payload.get("contours") == ["static", "targeted", "review", "full", "security"],
      r.stdout + r.stderr)

request = select_request("medium", "release")
request["candidateSha256"] = "not-a-sha"
r, payload = invoke(request)
check("release rejects a malformed candidate hash",
      r.returncode != 0 and payload.get("status") == "FAIL"
      and payload.get("fix"), r.stdout + r.stderr)

evidence = {
    "operation": "release-evidence",
    "candidateSha256": A,
    "evidence": {
        "candidateSha256": A,
        "contours": ["static", "targeted", "review", "full"],
        "windowsWslMatrix": {
            "candidateSha256": A, "status": "PASSED", "runsForCandidate": 1,
        },
        "ciOrNative": {"candidateSha256": A, "status": "PASSED"},
    },
}
r, payload = invoke(evidence)
check("release evidence passes only for one exact candidate",
      r.returncode == 0 and payload.get("status") == "PASS"
      and payload.get("verified") is True, r.stdout + r.stderr)

mutant = copy.deepcopy(evidence)
mutant["candidateSha256"] = B
r, payload = invoke(mutant)
check("any candidate change invalidates cached release evidence",
      r.returncode != 0 and payload.get("verified") is False
      and "candidate" in str(payload.get("why", "")).lower(), r.stdout + r.stderr)

for field in ("windowsWslMatrix", "ciOrNative"):
    mutant = copy.deepcopy(evidence)
    mutant["evidence"].pop(field)
    r, payload = invoke(mutant)
    check(f"release cannot omit {field} evidence",
          r.returncode != 0 and payload.get("verified") is False, r.stdout + r.stderr)

mutant = copy.deepcopy(evidence)
mutant["evidence"]["windowsWslMatrix"]["runsForCandidate"] = 2
r, payload = invoke(mutant)
check("Windows/WSL matrix runs once per exact candidate hash",
      r.returncode != 0 and payload.get("verified") is False, r.stdout + r.stderr)

mutant = copy.deepcopy(evidence)
mutant["evidence"]["windowsWslMatrix"]["runsForCandidate"] = True
r, payload = invoke(mutant, subprocess_mode=True)
check("boolean true is not accepted as one Windows/WSL matrix run",
      r.returncode != 0 and payload.get("verified") is False, r.stdout + r.stderr)

security_evidence = copy.deepcopy(evidence)
security_evidence["signals"] = ["security"]
security_evidence["evidence"]["contours"].append("security")
r, payload = invoke(security_evidence)
check("release evidence includes every signal-selected contour",
      r.returncode == 0 and payload.get("contours")[-1] == "security",
      r.stdout + r.stderr)
security_evidence["evidence"]["contours"].remove("security")
r, payload = invoke(security_evidence)
check("release evidence cannot omit a signal-selected contour",
      r.returncode != 0 and payload.get("verified") is False, r.stdout + r.stderr)

# Diagnostic lifecycle: complete failure collection, causal clusters, one final rerun.
r, payload = invoke(diagnostics_request())
check("diagnostics preserve the complete failure set",
      r.returncode == 0 and payload.get("failureSet") == ["F-1", "F-2", "F-3"],
      r.stdout + r.stderr)
check("diagnostics classify cascades into independent causal clusters",
      payload.get("independentFailureSet") == ["F-1", "F-3"]
      and payload.get("causalClusters") == {"parser": ["F-1", "F-2"], "config": ["F-3"]},
      r.stdout)
check("original diagnostic rerun is required for verification",
      payload.get("status") == "PASS" and payload.get("verified") is True, r.stdout)

for label, mutate in (
    ("incomplete collection", lambda q: q.update(collectionComplete=False)),
    ("fix before collection", lambda q: q.update(collectedBeforeFixes=False)),
    ("different final command", lambda q: q["finalRerun"].update(command="pytest")),
    ("failed final rerun", lambda q: q["finalRerun"].update(exitCode=1)),
    ("missing risky-cluster discriminating check",
     lambda q: q["clusterHistory"][0].pop("cheapDiscriminatingCheck")),
    ("duplicate causal-cluster fix",
     lambda q: q["clusterHistory"].append(copy.deepcopy(q["clusterHistory"][0]))),
):
    mutant = diagnostics_request()
    mutate(mutant)
    r, payload = invoke(mutant)
    check(f"diagnostics reject {label}",
          r.returncode != 0 and payload.get("verified") is False
          and payload.get("fix"), r.stdout + r.stderr)

# Backlog is the conjunction of all eligibility facts plus durable capture.
r, payload = invoke(backlog_request())
check("eligible unrelated finding is captured without scope expansion",
      r.returncode == 0 and payload.get("status") == "BACKLOG"
      and payload.get("fixInCurrentUnit") is False, r.stdout + r.stderr)

for field in ("preExisting", "outOfScope", "nonBlocking"):
    mutant = backlog_request()
    mutant[field] = False
    r, payload = invoke(mutant)
    check(f"backlog rejects missing {field} eligibility",
          r.returncode != 0 and payload.get("status") == "BLOCK_CURRENT_UNIT",
          r.stdout + r.stderr)

mutant = backlog_request()
mutant["introducedByCurrentDiff"] = True
r, payload = invoke(mutant)
check("current-diff regression never becomes backlog",
      r.returncode != 0 and payload.get("status") == "BLOCK_CURRENT_UNIT",
      r.stdout + r.stderr)

for blocker in (
    "acceptance-criterion-failure", "required-risk-invariant-failure",
    "current-diff-regression", "critical-security", "data-loss",
):
    mutant = backlog_request()
    mutant["blockingKinds"] = [blocker]
    r, payload = invoke(mutant)
    check(f"{blocker} remains a current-unit blocker",
          r.returncode != 0 and payload.get("status") == "BLOCK_CURRENT_UNIT"
          and blocker in payload.get("blockingKinds", []), r.stdout + r.stderr)

mutant = backlog_request()
mutant["blockingKinds"] = ["test-suite-failure"]
r, payload = invoke(mutant)
check("a declared blocking finding cannot contradict nonBlocking eligibility",
      r.returncode != 0 and payload.get("status") == "BLOCK_CURRENT_UNIT",
      r.stdout + r.stderr)

mutant = backlog_request()
mutant["capture"] = {}
r, payload = invoke(mutant)
check("backlog decision requires a durable capture record",
      r.returncode != 0 and payload.get("status") == "BLOCK_CURRENT_UNIT",
      r.stdout + r.stderr)

# The implementation must consume, not rewrite, the frozen policy contracts.
corpus = json.loads(WORK_CORPUS.read_text(encoding="utf-8"))
check("working-deadline policy remains frozen",
      hashlib.sha256(WORK_POLICY.read_bytes()).hexdigest() == corpus["policySha256"])
check("proportionality policy remains frozen",
      hashlib.sha256(PROPORTIONALITY_POLICY.read_bytes()).hexdigest()
      == corpus["inheritedPolicySha256"])

r, payload = invoke({"operation": "unbounded-scan"}, subprocess_mode=True)
check("unknown operation fails with actionable output",
      r.returncode != 0 and payload.get("why") and payload.get("fix"),
      r.stdout + r.stderr)

# Refute pass: each semantic mutant must make its corresponding assertion fail.
r, payload = invoke_mutant((
    ('contours = list(routes[normalized_risk]["contours"])',
     'contours = list(profiles["release"]["baseContours"])'),
), select_request("low"))
check("mutation guard kills always-full targeted routing",
      r.returncode == 0 and payload.get("contours") != ["static"], r.stdout + r.stderr)

signal_request = select_request("medium")
signal_request["signals"] = ["auth"]
r, payload = invoke_mutant((
    ("elif contour not in contours:", "elif False:"),
), signal_request)
check("mutation guard kills dropped signal contour",
      r.returncode == 0 and "security" not in (payload.get("contours") or []),
      r.stdout + r.stderr)

changed_candidate = copy.deepcopy(evidence)
changed_candidate["candidateSha256"] = B
r, payload = invoke_mutant((
    ('if evidence.get("candidateSha256") != candidate:', "if False:"),
    ('if record.get("candidateSha256") != candidate:', "if False:"),
), changed_candidate)
check("mutation guard kills candidate-binding bypass",
      r.returncode == 0 and payload.get("verified") is True, r.stdout + r.stderr)

failed_rerun = diagnostics_request()
failed_rerun["finalRerun"]["exitCode"] = 1
r, payload = invoke_mutant((
    ('if type(rerun.get("exitCode")) is not int or rerun.get("exitCode") != 0:',
     "if False:"),
), failed_rerun)
check("mutation guard kills failed-rerun false pass",
      r.returncode == 0 and payload.get("verified") is True, r.stdout + r.stderr)

introduced = backlog_request()
introduced["introducedByCurrentDiff"] = True
r, payload = invoke_mutant((
    ('if request.get("introducedByCurrentDiff") is True:', "if False:"),
    ('"notIntroducedByCurrentDiff": request.get("introducedByCurrentDiff") is False,',
     '"notIntroducedByCurrentDiff": True,'),
), introduced)
check("mutation guard kills current-diff backlog bypass",
      r.returncode == 0 and payload.get("status") == "BACKLOG", r.stdout + r.stderr)

r, payload = invoke_mutant((
    ("if not args_list:\n        return 0",
     'if not args_list:\n        print("unexpected full-scan noise")\n        return 0'),
), None)
check("mutation guard kills noisy no-input behavior",
      r.returncode == 0 and bool(r.stdout), r.stdout + r.stderr)

runtime_marker = "skills/_shared/itd_verification_profiles.py"
for path in (TASK_SKILL, HELPERS, DOC):
    text = path.read_text(encoding="utf-8")
    check(f"{path.relative_to(ROOT)} names the executable selector",
          runtime_marker in text)
check("quick suite includes verification profile oracle",
      "verify_verification_profiles" in RUN_ALL.read_text(encoding="utf-8"))

print(f"RESULT: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
