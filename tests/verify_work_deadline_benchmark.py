#!/usr/bin/env python3
"""Frozen A/B and no-regression benchmark for the working-deadline profile.

The benchmark compares identical sealed cases through two strategies:

* baseline: every reviewed verification contour (always-full);
* candidate: the current host-neutral targeted/release selector.

Quality is capability equality, not a subjective score. Tool calls are the
selected contour invocations. Wall-clock evidence is a local monotonic process
benchmark whose work is proportional to the already-frozen contour time units;
it is explicitly internal evidence and never external adoption/outcome proof.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "benchmarks" / "working-deadline" / "CORPUS.json"
CORPUS_SEAL = ROOT / "benchmarks" / "working-deadline" / "CORPUS.sha256"
PROPORTIONALITY_CORPUS = ROOT / "benchmarks" / "proportionality" / "CORPUS.json"
PROPORTIONALITY_SEAL = ROOT / "benchmarks" / "proportionality" / "CORPUS.sha256"
SELECTOR_PATH = ROOT / "skills" / "_shared" / "itd_verification_profiles.py"
SHA256_RE = re.compile(r"[0-9a-f]{64}")
WORK_FACTOR = 2500
REPEATS = 5


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path.relative_to(ROOT)}: root must be an object")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_seal(path: Path, seal: Path) -> None:
    expected = seal.read_text(encoding="utf-8").strip().split()[0]
    actual = sha256(path)
    if not SHA256_RE.fullmatch(expected) or expected != actual:
        raise AssertionError(
            f"{path.relative_to(ROOT)}: frozen seal mismatch; "
            "restore the reviewed corpus instead of changing the benchmark")


def load_selector() -> ModuleType:
    spec = importlib.util.spec_from_file_location("itd_verification_profiles", SELECTOR_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load the host-neutral verification selector")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def head_identity() -> bytes:
    """Return the immutable base commit used to construct the candidate."""
    return subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
        cwd=ROOT, capture_output=True, check=True,
    ).stdout.strip()


def candidate_sha256() -> str:
    """Hash base HEAD, tracked diff, and every non-ignored untracked file."""
    diff = subprocess.run(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD"],
        cwd=ROOT, capture_output=True, check=True,
    ).stdout
    untracked_raw = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, capture_output=True, check=True,
    ).stdout
    digest = hashlib.sha256()
    digest.update(b"base-head\0")
    digest.update(head_identity())
    digest.update(b"\0")
    digest.update(b"tracked-diff\0")
    digest.update(diff)
    for raw_path in sorted(item for item in untracked_raw.split(b"\0") if item):
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        path = ROOT / relative
        digest.update(b"untracked\0")
        digest.update(raw_path)
        digest.update(b"\0")
        digest.update(path.read_bytes() if path.is_file() else b"<non-file>")
    return digest.hexdigest()


def capabilities(contours: list[str], policy: dict[str, Any]) -> set[str]:
    return {
        capability
        for contour in contours
        for capability in policy["contours"][contour]["capabilities"]
    }


def required_capabilities(case: dict[str, Any], policy: dict[str, Any]) -> set[str]:
    risk = case.get("risk")
    normalized = risk if risk in policy["riskRoutes"] else "high"
    required = set(policy["riskRoutes"][normalized]["requiredCapabilities"])
    for signal in case.get("signals") or []:
        contour = policy.get("signalContours", {}).get(signal)
        if contour:
            required.update(policy["contours"][contour]["capabilities"])
    return required


def baseline_contours(policy: dict[str, Any]) -> list[str]:
    return list(policy["invariants"]["alwaysFullContours"])


def select_case(case: dict[str, Any], candidate: str, selector: ModuleType,
                work: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    request: dict[str, Any] = {
        "profile": case["requestedProfile"],
        "risk": case["risk"],
        "signals": list(case.get("signals") or []),
        "changed": [case["id"]],
        "impactKnown": True,
        "impactGraph": {case["id"]: []},
        "candidateSha256": candidate,
    }
    return selector.select_profile(request, work, policy)


def burn(contours: list[str], policy: dict[str, Any], salt: str) -> bytes:
    units = sum(policy["contours"][name]["normalizedTimeUnits"] for name in contours)
    state = salt.encode("utf-8")
    for _ in range(int(units * WORK_FACTOR)):
        state = hashlib.sha256(state).digest()
    return state


def measure_pair(baseline: list[str], selected: list[str],
                 policy: dict[str, Any], case_id: str) -> tuple[int, int]:
    """Return median monotonic nanoseconds, alternating order to limit bias."""
    burn(baseline, policy, case_id + "-warm-baseline")
    burn(selected, policy, case_id + "-warm-selected")
    baseline_samples: list[int] = []
    selected_samples: list[int] = []

    def timed(contours: list[str], label: str) -> int:
        started = time.perf_counter_ns()
        burn(contours, policy, label)
        return time.perf_counter_ns() - started

    for index in range(REPEATS):
        if index % 2 == 0:
            baseline_samples.append(timed(baseline, f"{case_id}-b-{index}"))
            selected_samples.append(timed(selected, f"{case_id}-s-{index}"))
        else:
            selected_samples.append(timed(selected, f"{case_id}-s-{index}"))
            baseline_samples.append(timed(baseline, f"{case_id}-b-{index}"))
    return int(statistics.median(baseline_samples)), int(statistics.median(selected_samples))


def validate_summary(summary: dict[str, Any], expected_candidate: str) -> list[str]:
    issues: list[str] = []
    if summary.get("routeDrifts") != 0:
        issues.append("frozen route/contour expectations drifted")
    if summary.get("qualityRegressions") != 0:
        issues.append("targeted-to-release quality regression detected")
    if summary.get("highRiskBypasses") != 0:
        issues.append("high/unknown risk bypassed strict release")
    if summary.get("criticalFalseCompletions") != 0:
        issues.append("a route was reported successful without required capability")
    if summary.get("selectedToolCalls", 0) >= summary.get("baselineToolCalls", 0):
        issues.append("eligible daily cases did not reduce contour/tool calls")
    if summary.get("selectedWallClockNs", 0) >= summary.get("baselineWallClockNs", 0):
        issues.append("eligible daily cases did not reduce monotonic wall-clock work")
    candidate = str(summary.get("candidateSha256") or "")
    if not SHA256_RE.fullmatch(candidate) or candidate != expected_candidate:
        issues.append("release benchmark is not bound to an exact candidate SHA-256")
    if summary.get("externalEvidence") is not False:
        issues.append("internal benchmark must never claim external evidence")
    if summary.get("measurementProvenance") != "local-monotonic-process-benchmark":
        issues.append("wall-clock result lacks explicit local measurement provenance")
    return issues


def mutation_guards(summary: dict[str, Any], expected_candidate: str) -> dict[str, bool]:
    """Require each mutant to introduce its own diagnostic on a clean base."""
    guards: dict[str, bool] = {}
    baseline_issues = validate_summary(summary, expected_candidate)

    def killed(mutant: dict[str, Any], expected_issue: str) -> bool:
        mutant_issues = validate_summary(mutant, expected_candidate)
        return not baseline_issues and mutant_issues == [expected_issue]

    mutant = copy.deepcopy(summary)
    mutant["qualityRegressions"] = 1
    guards["quality-loss"] = killed(
        mutant, "targeted-to-release quality regression detected")
    mutant = copy.deepcopy(summary)
    mutant["highRiskBypasses"] = 1
    guards["high-risk-bypass"] = killed(
        mutant, "high/unknown risk bypassed strict release")
    mutant = copy.deepcopy(summary)
    mutant["criticalFalseCompletions"] = 1
    guards["false-completion"] = killed(
        mutant, "a route was reported successful without required capability")
    mutant = copy.deepcopy(summary)
    mutant["selectedToolCalls"] = mutant["baselineToolCalls"]
    guards["tool-call-no-improvement"] = killed(
        mutant, "eligible daily cases did not reduce contour/tool calls")
    mutant = copy.deepcopy(summary)
    mutant["selectedWallClockNs"] = mutant["baselineWallClockNs"]
    guards["wall-clock-no-improvement"] = killed(
        mutant, "eligible daily cases did not reduce monotonic wall-clock work")
    mutant = copy.deepcopy(summary)
    mutant["candidateSha256"] = (
        "0" * 64 if expected_candidate != "0" * 64 else "1" * 64)
    guards["candidate-binding"] = killed(
        mutant, "release benchmark is not bound to an exact candidate SHA-256")
    mutant = copy.deepcopy(summary)
    mutant["externalEvidence"] = True
    guards["synthetic-external-evidence"] = killed(
        mutant, "internal benchmark must never claim external evidence")
    return guards


def main() -> int:
    try:
        require_seal(CORPUS_PATH, CORPUS_SEAL)
        require_seal(PROPORTIONALITY_CORPUS, PROPORTIONALITY_SEAL)
        corpus = load_object(CORPUS_PATH)
        proportionality_corpus = load_object(PROPORTIONALITY_CORPUS)
        selector = load_selector()
        work, policy = selector.load_policies()
        if corpus.get("policySha256") != sha256(selector.WORK_POLICY_PATH):
            raise AssertionError("working-deadline corpus/policy binding is stale")
        if corpus.get("inheritedPolicySha256") != sha256(selector.PROPORTIONALITY_PATH):
            raise AssertionError("working-deadline inherited-policy binding is stale")
        if proportionality_corpus.get("policySha256") != sha256(selector.PROPORTIONALITY_PATH):
            raise AssertionError("proportionality corpus/policy binding is stale")

        candidate = candidate_sha256()
        rows: list[dict[str, Any]] = []
        route_drifts = 0
        quality_regressions = 0
        high_risk_bypasses = 0
        false_completions = 0
        baseline_calls = selected_calls = 0
        baseline_wall = selected_wall = 0

        for case in corpus.get("cases") or []:
            result = select_case(case, candidate, selector, work, policy)
            baseline = baseline_contours(policy)
            selected = list(result["contours"])
            required = required_capabilities(case, policy)
            baseline_quality = required <= capabilities(baseline, policy)
            selected_quality = required <= capabilities(selected, policy)
            drift = (result["route"] != case.get("expectedRoute")
                     or selected != case.get("expectedContours"))
            route_drifts += int(drift)
            quality_regressions += int(baseline_quality and not selected_quality)
            if not selected_quality:
                false_completions += 1
            if case.get("risk") in {"high", "unknown"} \
                    and result["route"] != "strict.release":
                high_risk_bypasses += 1

            eligible = result["route"] == "working_deadline.targeted"
            wall_baseline = wall_selected = 0
            if eligible:
                wall_baseline, wall_selected = measure_pair(
                    baseline, selected, policy, str(case["id"]))
                baseline_calls += len(baseline)
                selected_calls += len(selected)
                baseline_wall += wall_baseline
                selected_wall += wall_selected
            rows.append({
                "id": case["id"],
                "risk": case["risk"],
                "route": result["route"],
                "contours": selected,
                "qualityVerified": selected_quality,
                "eligibleDailyAB": eligible,
                "baselineToolCalls": len(baseline) if eligible else 0,
                "selectedToolCalls": len(selected) if eligible else 0,
                "wallClockRatio": (
                    round(wall_selected / wall_baseline, 4)
                    if eligible and wall_baseline else None),
            })

        summary: dict[str, Any] = {
            "routeDrifts": route_drifts,
            "qualityRegressions": quality_regressions,
            "highRiskBypasses": high_risk_bypasses,
            "criticalFalseCompletions": false_completions,
            "eligibleDailyCases": sum(row["eligibleDailyAB"] for row in rows),
            "baselineToolCalls": baseline_calls,
            "selectedToolCalls": selected_calls,
            "toolCallRatio": round(selected_calls / baseline_calls, 4),
            "baselineWallClockNs": baseline_wall,
            "selectedWallClockNs": selected_wall,
            "wallClockRatio": round(selected_wall / baseline_wall, 4),
            "baseHead": head_identity().decode("ascii"),
            "candidateSha256": candidate,
            "measurementProvenance": "local-monotonic-process-benchmark",
            "externalEvidence": False,
        }
        expected_candidate = candidate_sha256()
        issues = validate_summary(summary, expected_candidate)
        guards = mutation_guards(summary, expected_candidate)
        missed = sorted(name for name, killed in guards.items() if not killed)
        if missed:
            issues.append("mutation guards missed: " + ", ".join(missed))
        output = {
            "status": "FAIL" if issues else "PASS",
            "corpus": corpus.get("id"),
            "cases": len(rows),
            **summary,
            "mutationGuards": f"{sum(guards.values())}/{len(guards)}",
            "issues": issues,
            "results": rows,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if issues else 0
    except Exception as exc:
        print(json.dumps({
            "status": "FAIL",
            "error": str(exc),
            "why": "the frozen A/B could not produce trustworthy evidence",
            "fix": "restore sealed inputs or fix the current selector before rerunning",
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
