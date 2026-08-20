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

# ---------------------------------------------------------------------------
# LPD-002 R6: the impact map is data in the repository, fed to impact_closure
# as impactGraph; completeness and proportionality are judged by the engine.
# ---------------------------------------------------------------------------
IMPACT_MAP = ROOT / ".itd" / "IMPACT_GRAPH.json"
BUILDER = ROOT / "tests" / "build_impact_graph.py"
SELF = "tests/verify_verification_profiles.py"
SELECTOR = "skills/_shared/itd_verification_profiles.py"


def audit_request(map_path: Path = IMPACT_MAP) -> dict:
    return {"operation": "impact-audit", "impactGraphPath": str(map_path),
            "root": str(ROOT)}


def map_select(changed: list[str], known: bool = True, risk: str = "medium",
               map_path: Path = IMPACT_MAP) -> dict:
    request = {
        "operation": "select", "profile": "targeted", "risk": risk, "signals": [],
        "impactKnown": known, "changed": changed, "requestedCapabilities": [],
    }
    if known:
        request["impactGraphPath"] = str(map_path)
    return request


MUTANT_COUNTER = [0]


def mutated_map(td: Path, mutate) -> Path:
    """Write a mutated map INSIDE the repository root (containment is enforced
    by the engine since the PUB3 security finding), under a git-ignored dir."""
    document = json.loads(IMPACT_MAP.read_text(encoding="utf-8"))
    mutate(document)
    MUTANT_COUNTER[0] += 1
    path = td / f"IMPACT_GRAPH-{MUTANT_COUNTER[0]}.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


check("impact map is committed data, not inferred at run time", IMPACT_MAP.is_file())
tracked = subprocess.run(
    ["git", "ls-files", "--error-unmatch", ".itd/IMPACT_GRAPH.json"],
    cwd=str(ROOT), capture_output=True, timeout=30)
check("impact map is tracked by git, not a worktree leftover",
      tracked.returncode == 0,
      tracked.stderr.decode("utf-8", "replace"))
document = json.loads(IMPACT_MAP.read_text(encoding="utf-8"))
check("impact map names its generator and schema",
      document.get("schemaVersion") == "1"
      and document.get("generator") == "tests/build_impact_graph.py"
      and BUILDER.is_file())
check("impact map declares the suite universe and the owned source globs",
      (document.get("universe") or {}).get("suites") == "tests/verify_*.py"
      and (document.get("universe") or {}).get("owned") == ["skills/_shared/*.py", "hooks/*.sh"])

all_suites = sorted(
    p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").glob("verify_*.py"))
owned_files = sorted(
    p.relative_to(ROOT).as_posix()
    for pattern in ("skills/_shared/*.py", "hooks/*.sh") for p in ROOT.glob(pattern))
r, payload = invoke(audit_request())
check("impact audit passes on the committed map and the live tree",
      r.returncode == 0 and payload.get("status") == "PASS"
      and payload.get("verified") is True, r.stdout + r.stderr)
check("completeness: every tests/verify_*.py suite appears in the map",
      payload.get("suites") == len(all_suites) and len(all_suites) >= 151
      and payload.get("unattachedSuites") == [], r.stdout)
check("completeness: every skills/_shared/*.py and hooks/*.sh has an owning suite",
      payload.get("owned") == len(owned_files) and payload.get("orphanOwned") == [],
      r.stdout)
check("completeness: no stale node or target survives in the map",
      payload.get("staleNodes") == [] and payload.get("staleTargets") == [], r.stdout)
check("proportionality: no node's closure reaches the full suite set",
      payload.get("saturatedNodes") == []
      and 0 < payload.get("maxClosure", 0) < payload.get("fullSet", 0), r.stdout)
r, payload_cli = invoke(audit_request(), subprocess_mode=True)
check("impact audit is reachable through the CLI with the same verdict",
      r.returncode == 0 and payload_cli.get("status") == "PASS"
      and payload_cli.get("edges") == payload.get("edges"), r.stdout + r.stderr)

r, payload = invoke(map_select([SELECTOR]))
selected = [node for node in payload.get("impactClosure") or [] if node in all_suites]
check("the committed map is fed to impact_closure as impactGraph",
      r.returncode == 0 and payload.get("route") == "working_deadline.targeted"
      and SELF in selected, r.stdout + r.stderr)
check("proportionality: a point change selects strictly fewer suites than the full set",
      0 < len(selected) < len(all_suites), f"{len(selected)}/{len(all_suites)}")
r, payload = invoke(map_select(["hooks/completion-stop.sh"]))
check("an owned hook resolves to its owning suite through the map",
      r.returncode == 0
      and "tests/verify_completion_policy_calibration.py" in (payload.get("impactClosure") or []),
      r.stdout + r.stderr)
r, payload = invoke(map_select([SELECTOR], known=False))
check("impactKnown:false exits to the strict release path without the map",
      r.returncode == 0 and payload.get("route") == "strict.release"
      and "unknown impact requires strict release" in (payload.get("reasons") or [])
      and payload.get("impactClosure") == [SELECTOR], r.stdout + r.stderr)
both = map_select([SELECTOR])
both["impactGraph"] = {SELECTOR: [SELF]}
r, payload = invoke(both)
check("inline graph and map path are mutually exclusive",
      r.returncode == 1 and "mutually exclusive" in payload.get("why", ""), r.stdout)
both_unknown = dict(both, impactKnown=False)
r, payload = invoke(both_unknown)
check("the exclusivity rule holds even when impact is unknown",
      r.returncode == 1 and "mutually exclusive" in payload.get("why", ""), r.stdout)
unknown_missing_map = map_select([SELECTOR], known=False)
unknown_missing_map["impactGraphPath"] = str(ROOT / "does-not-exist" / "IMPACT_GRAPH.json")
r, payload = invoke(unknown_missing_map)
check("unknown impact never loads the map, even when the path is given and missing",
      r.returncode == 0 and payload.get("route") == "strict.release"
      and payload.get("impactClosure") == [SELECTOR], r.stdout + r.stderr)
r, payload = invoke_mutant((
    ("    reject_ambiguous_graph(request)\n    if request.get(\"impactKnown\") is not True:",
     "    if request.get(\"impactKnown\") is not True:"),
), both_unknown)
check("mutation guard kills the early-return bypass of the exclusivity rule",
      r.returncode == 0 and payload.get("route") == "strict.release", r.stdout + r.stderr)

import shutil as _shutil
_scratch = ROOT / ".itd" / f"tmp-impact-oracle-{os.getpid()}"
_scratch.mkdir(parents=True, exist_ok=True)
try:
    tmp = _scratch
    def drop_edges_to_self(doc):
        for targets in doc["generated"].values():
            if SELF in targets:
                targets.remove(SELF)
        doc["declared"] = {}
    r, payload = invoke(audit_request(mutated_map(tmp, drop_edges_to_self)))
    check("mutation: removing every edge to a suite fails completeness",
          r.returncode == 0 and payload.get("status") == "FAIL"
          and payload.get("unattachedSuites") == [SELF], r.stdout + r.stderr)

    def drop_owned_node(doc):
        doc["generated"].pop("hooks/completion-stop.sh")
        doc["declared"] = {}
    r, payload = invoke(audit_request(mutated_map(tmp, drop_owned_node)))
    check("mutation: removing an owned source's edges fails completeness",
          r.returncode == 0 and payload.get("status") == "FAIL"
          and "hooks/completion-stop.sh" in (payload.get("orphanOwned") or []),
          r.stdout + r.stderr)

    def everything_adjacent(doc):
        doc["generated"] = {node: list(all_suites) for node in doc["generated"]}
    r, payload = invoke(audit_request(mutated_map(tmp, everything_adjacent)))
    check("mutation: declaring every node adjacent to every suite fails proportionality",
          r.returncode == 0 and payload.get("status") == "FAIL"
          and len(payload.get("saturatedNodes") or []) == len(document["generated"])
          and payload.get("unattachedSuites") == [] and payload.get("orphanOwned") == [],
          r.stdout + r.stderr)

    def stale_node(doc):
        doc["generated"]["skills/_shared/itd_ghost.py"] = [SELF]
    r, payload = invoke(audit_request(mutated_map(tmp, stale_node)))
    check("mutation: a node that no longer exists fails completeness",
          r.returncode == 0 and payload.get("status") == "FAIL"
          and payload.get("staleNodes") == ["skills/_shared/itd_ghost.py"], r.stdout)

    def stale_target(doc):
        doc["generated"][SELECTOR].append("tests/verify_ghost.py")
    r, payload = invoke(audit_request(mutated_map(tmp, stale_target)))
    check("mutation: an edge to a missing suite fails completeness",
          r.returncode == 0 and payload.get("status") == "FAIL"
          and payload.get("staleTargets") == ["tests/verify_ghost.py"], r.stdout)

    def declared_edge(doc):
        doc["declared"] = {"docs/WORKING_DEADLINE_MODE.md": [SELF]}
    declared_path = mutated_map(tmp, declared_edge)
    r, payload = invoke(map_select(["docs/WORKING_DEADLINE_MODE.md"], map_path=declared_path))
    check("hand-declared edges merge into the generated graph",
          r.returncode == 0 and SELF in (payload.get("impactClosure") or []), r.stdout)

    def laundered_coverage(doc):
        doc["generated"].pop("hooks/completion-stop.sh")
        doc["declared"] = {
            "hooks/completion-stop.sh": ["docs/WORKING_DEADLINE_MODE.md"],
            "docs/WORKING_DEADLINE_MODE.md": [SELF],
        }
    r, payload = invoke(audit_request(mutated_map(tmp, laundered_coverage)))
    check("mutation: covering an owned source through a non-suite intermediate fails",
          r.returncode == 0 and payload.get("status") == "FAIL"
          and payload.get("nonSuiteTargets") == ["docs/WORKING_DEADLINE_MODE.md"]
          and payload.get("orphanOwned") == [], r.stdout + r.stderr)

    def absolute_suites_pattern(doc):
        doc["universe"]["suites"] = "/etc/*"
    r, payload = invoke(audit_request(mutated_map(tmp, absolute_suites_pattern)))
    check("an absolute universe pattern fails closed",
          r.returncode == 1 and "root-relative glob" in payload.get("why", ""),
          r.stdout)

    def escaping_owned_pattern(doc):
        doc["universe"]["owned"] = ["../*/secrets/*.py"]
    r, payload = invoke(audit_request(mutated_map(tmp, escaping_owned_pattern)))
    check("an escaping owned pattern fails closed",
          r.returncode == 1 and "root-relative glob" in payload.get("why", ""),
          r.stdout)

    def select_escaping_declared(doc):
        doc["declared"] = {"../outside.py": [SELF]}
    r, payload = invoke(map_select([SELECTOR],
                                   map_path=mutated_map(tmp, select_escaping_declared)))
    check("select fails closed on a map with an escaping node",
          r.returncode == 1
          and "outside the repository root" in payload.get("why", ""), r.stdout)

    evil_name = f"verify_evil_{os.getpid()}"
    evil_dir = ROOT / "tests" / evil_name
    evil_rel = f"tests/{evil_name}/payload.py"
    evil_dir.mkdir(exist_ok=False)
    fake = evil_dir / "payload.py"
    fake.write_text("print('not a suite')\n", encoding="utf-8")
    def select_slash_crossing_target(doc):
        doc["declared"] = {SELECTOR: [evil_rel]}
    try:
        r, payload = invoke(map_select([SELECTOR],
                                       map_path=mutated_map(tmp, select_slash_crossing_target)))
    finally:
        fake.unlink(missing_ok=True)
        try:
            evil_dir.rmdir()
        except OSError:
            pass
    check("a nested path satisfying the pattern only via slash-crossing match is rejected",
          r.returncode == 1 and "is not a suite" in payload.get("why", ""), r.stdout)


    def select_non_suite_target(doc):
        doc["declared"] = {SELECTOR: ["docs/WORKING_DEADLINE_MODE.md"]}
    r, payload = invoke(map_select([SELECTOR],
                                   map_path=mutated_map(tmp, select_non_suite_target)))
    check("select fails closed on a map edge to a non-suite",
          r.returncode == 1
          and "is not a suite" in payload.get("why", ""), r.stdout)

    nonrepo = tmp / "not-a-repo"
    nonrepo.mkdir(exist_ok=True)
    (nonrepo / "IMPACT_GRAPH.json").write_bytes(IMPACT_MAP.read_bytes())
    nonrepo_request = {
        "operation": "impact-audit", "root": str(nonrepo),
        "impactGraphPath": str(nonrepo / "IMPACT_GRAPH.json"),
    }
    with tempfile.TemporaryDirectory() as td2:
        req_path = Path(td2) / "request.json"
        req_path.write_text(json.dumps(nonrepo_request), encoding="utf-8")
        result = subprocess.run(
            [PY, str(RUNTIME), "--input", str(req_path)], cwd=str(nonrepo),
            capture_output=True, encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONUTF8": "1"}, timeout=30)
    check("the engine refuses to run from a directory that is not a repository",
          result.returncode == 1
          and "not running from a repository" in result.stdout, result.stdout)

    def nul_node(doc):
        doc["generated"]["\u0000"] = [SELF]
    r, payload = invoke(audit_request(mutated_map(tmp, nul_node)))
    check("a NUL-carrying graph node fails closed, not with a raw ValueError",
          r.returncode == 1 and "NUL byte" in payload.get("why", ""), r.stdout)

    nul_path = audit_request()
    nul_path["impactGraphPath"] = ".itd/\u0000map.json"
    r, payload = invoke(nul_path)
    check("a NUL-carrying map path fails closed",
          r.returncode == 1 and "NUL byte" in payload.get("why", ""), r.stdout)

    sys.path.insert(0, str(ROOT / "tests"))
    import build_impact_graph as big
    alias_text = "from services.review_broker import server as srv\nimport json, hashlib\n"
    alias_candidates = big.import_candidates(alias_text)
    check("an import alias never fabricates a module edge",
          "services/review_broker/server" in alias_candidates
          and "services/review_broker/srv" not in alias_candidates,
          str(alias_candidates))
    check("comma-separated imports resolve every module, not only the first",
          "json" in alias_candidates and "hashlib" in alias_candidates,
          str(alias_candidates))
    check("generator suite matching is the glob, not a name-charset regex",
          big.is_suite("tests/verify_http.v2.py") is True
          and big.is_suite("tests/verify_x/payload.py") is False
          and big.is_suite("tests/helpers.py") is False)

    def missing_declared(doc):
        doc.pop("declared")
    r, payload = invoke(audit_request(mutated_map(tmp, missing_declared)))
    check("a map without the declared section fails closed",
          r.returncode == 1 and "section is missing" in payload.get("why", ""),
          r.stdout)

    def missing_generated(doc):
        doc.pop("generated")
    r, payload = invoke(map_select([SELECTOR],
                                   map_path=mutated_map(tmp, missing_generated)))
    check("select refuses a map without the generated section",
          r.returncode == 1 and "section is missing" in payload.get("why", ""),
          r.stdout)

    def broken_glob(doc):
        doc["universe"]["suites"] = "tests/**broken.py"
    r, payload = invoke(audit_request(mutated_map(tmp, broken_glob)))
    check("an invalid glob grammar fails closed, not with a raw ValueError",
          r.returncode == 1
          and "not a valid glob pattern" in payload.get("why", ""), r.stdout)

    def stamped_generator(doc):
        doc["generator"] = "someone-else.py"
    stamped_path = mutated_map(tmp, stamped_generator)
    drift = subprocess.run(
        [PY, str(BUILDER), "--check", "--path", str(stamped_path)],
        cwd=str(ROOT), capture_output=True, encoding="utf-8",
        errors="replace", timeout=120, env={**os.environ, "PYTHONUTF8": "1"})
    check("--check flags drift in generator-owned document fields, not only edges",
          drift.returncode == 1 and drift.stdout.startswith("DRIFT"),
          drift.stdout + drift.stderr)

    ambiguous_audit = audit_request()
    ambiguous_audit["impactGraph"] = {SELECTOR: [SELF]}
    r, payload = invoke(ambiguous_audit)
    check("impact-audit refuses both graph sources at once",
          r.returncode == 1 and "mutually exclusive" in payload.get("why", ""),
          r.stdout)

    def wrong_schema(doc):
        doc["schemaVersion"] = "2"
    r, payload = invoke(audit_request(mutated_map(tmp, wrong_schema)))
    check("an unsupported map schema fails closed",
          r.returncode == 1 and "schemaVersion" in payload.get("why", ""), r.stdout)

    empty_root = tmp / "no-suites"
    empty_root.mkdir(exist_ok=True)
    (empty_root / "IMPACT_GRAPH.json").write_bytes(IMPACT_MAP.read_bytes())
    empty_request = audit_request(empty_root / "IMPACT_GRAPH.json")
    empty_request["root"] = str(empty_root)
    r, payload = invoke(empty_request)
    check("an audit root without suites fails closed instead of passing vacuously",
          r.returncode == 1 and "no suites match" in payload.get("why", ""), r.stdout)

    # Engine mutants: each completeness/proportionality guard is load-bearing.
    r, payload = invoke_mutant((
        ("unattached = [suite for suite in suites if suite not in targets_seen]",
         "unattached = []"),
    ), audit_request(mutated_map(tmp, drop_edges_to_self)))
    check("mutation guard kills unattached-suite blindness",
          r.returncode == 0 and payload.get("status") == "PASS", r.stdout + r.stderr)
    r, payload = invoke_mutant((
        ("if not (set(walk_closure([node], graph)) & suite_set)]", "if False]"),
    ), audit_request(mutated_map(tmp, drop_owned_node)))
    check("mutation guard kills orphan-owned blindness",
          r.returncode == 0 and payload.get("status") == "PASS", r.stdout + r.stderr)
    r, payload = invoke_mutant((
        ("if reached >= len(suites):", "if False:"),
    ), audit_request(mutated_map(tmp, everything_adjacent)))
    check("mutation guard kills saturation blindness",
          r.returncode == 0 and payload.get("status") == "PASS", r.stdout + r.stderr)

    outside_request = audit_request()
    outside_request["impactGraphPath"] = "../outside-map.json"
    r, payload = invoke(outside_request)
    check("a map path that escapes the root fails closed",
          r.returncode == 1 and "escapes the declared root" in payload.get("why", ""),
          r.stdout)

    foreign_root = audit_request()
    foreign_root["root"] = tempfile.gettempdir()
    r, payload = invoke(foreign_root)
    check("a root outside the working repository fails closed",
          r.returncode == 1
          and "escapes the working repository" in payload.get("why", ""), r.stdout)

    link_name = ".itd/" + tmp.name + "/escape-link.py"
    symlink_supported = True
    try:
        (tmp / "escape-link.py").symlink_to(Path(tempfile.gettempdir()))
    except OSError:
        symlink_supported = False
    if symlink_supported:
        def symlinked_node(doc):
            doc["generated"][link_name] = [SELF]
        r, payload = invoke(audit_request(mutated_map(tmp, symlinked_node)))
        check("a symlinked node that resolves outside the root fails closed",
              r.returncode == 1
              and "outside the repository root" in payload.get("why", ""), r.stdout)
    else:
        check("a symlinked node that resolves outside the root fails closed",
              True, "symlinks unsupported on this host; guard exercised on POSIX")

    def escaping_node(doc):
        doc["generated"]["../outside.py"] = [SELF]
    r, payload = invoke(audit_request(mutated_map(tmp, escaping_node)))
    check("a graph node outside the repository root fails closed",
          r.returncode == 1
          and "outside the repository root" in payload.get("why", ""), r.stdout)

    def absolute_target(doc):
        doc["generated"][SELECTOR] = [str(ROOT / SELF)]
    r, payload = invoke(audit_request(mutated_map(tmp, absolute_target)))
    check("an absolute graph target fails closed",
          r.returncode == 1
          and "outside the repository root" in payload.get("why", ""), r.stdout)
finally:
    _shutil.rmtree(_scratch, ignore_errors=True)

fresh = subprocess.run(
    [PY, str(BUILDER), "--check"], cwd=str(ROOT), capture_output=True,
    encoding="utf-8", errors="replace", timeout=120,
    env={**os.environ, "PYTHONUTF8": "1"})
check("the committed map is fresh against the tracked tree (regenerate to fix)",
      fresh.returncode == 0 and fresh.stdout.startswith("FRESH"),
      fresh.stdout + fresh.stderr)

runtime_marker = "skills/_shared/itd_verification_profiles.py"
for path in (TASK_SKILL, HELPERS, DOC):
    text = path.read_text(encoding="utf-8")
    check(f"{path.relative_to(ROOT)} names the executable selector",
          runtime_marker in text)
check("quick suite includes verification profile oracle",
      "verify_verification_profiles" in RUN_ALL.read_text(encoding="utf-8"))

print(f"RESULT: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
