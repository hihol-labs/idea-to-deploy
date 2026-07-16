#!/usr/bin/env python3
"""Host-neutral verification-profile and failure-boundary policy engine.

The engine consumes one explicit JSON request through ``--input``. With no
input it is a quiet no-op, so callers cannot accidentally turn a focused check
into a repository-wide scan. The canonical policy files remain immutable
inputs; this module only derives decisions from them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
WORK_POLICY_PATH = ROOT / "skills" / "_shared" / "WORKING_DEADLINE_POLICY.json"
PROPORTIONALITY_PATH = ROOT / "skills" / "_shared" / "PROPORTIONALITY_POLICY.json"
SHA256_RE = re.compile(r"[0-9a-f]{64}")


class DecisionError(ValueError):
    """An unsafe or malformed request that must fail closed."""

    def __init__(self, why: str, fix: str, **fields: Any) -> None:
        super().__init__(why)
        self.why = why
        self.fix = fix
        self.fields = fields


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        try:
            label = path.relative_to(ROOT)
        except ValueError:
            label = path
        raise DecisionError(
            f"cannot load JSON object {label}: {exc}",
            "Restore the reviewed file or fix the bounded request before retrying.",
        ) from exc
    if not isinstance(value, dict):
        raise DecisionError(
            f"{path} is not a JSON object",
            "Provide a JSON object with one explicit bounded operation.",
        )
    return value


def load_policies() -> tuple[dict[str, Any], dict[str, Any]]:
    work = load_object(WORK_POLICY_PATH)
    proportionality = load_object(PROPORTIONALITY_PATH)
    inherited = work.get("inheritsVerificationPolicy") or {}
    actual_digest = hashlib.sha256(PROPORTIONALITY_PATH.read_bytes()).hexdigest()
    if (work.get("id") != "working-deadline-v1"
            or proportionality.get("id") != "risk-proportional-verification-v1"
            or inherited.get("path") != "skills/_shared/PROPORTIONALITY_POLICY.json"
            or inherited.get("sha256") != actual_digest
            or inherited.get("relationship") != "cadence-overlay-only"):
        raise DecisionError(
            "working-deadline policy is not bound to the reviewed proportionality policy",
            "Restore both frozen policies and their SHA-256 binding; do not guess a route.",
        )
    profiles = work.get("verificationProfiles") or {}
    targeted = profiles.get("targeted") or {}
    release = profiles.get("release") or {}
    if (targeted.get("selection") != "risk-derived-impact-closure"
            or targeted.get("transitiveImpactRequired") is not True
            or targeted.get("unknownImpact") != "exit-to-strict-release"
            or targeted.get("userCriteriaMayRemoveRequiredCapability") is not False
            or release.get("exactCandidateHashRequired") is not True
            or release.get("candidateHashAlgorithm") != "sha256"
            or release.get("invalidateOnAnyCandidateChange") is not True
            or release.get("windowsWslMatrixOncePerCandidateHash") is not True
            or release.get("ciOrNativeEvidenceRequired") is not True):
        raise DecisionError(
            "verification profile policy is malformed or weakened",
            "Restore WORKING_DEADLINE_POLICY.json from the reviewed contract.",
        )
    return work, proportionality


def require_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DecisionError(
            f"{field} must be a JSON object",
            f"Provide {field} as an object with the fields named by the policy contract.",
        )
    return value


def require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionError(
            f"{field} must be a non-empty string",
            f"Provide a concrete {field}; empty evidence cannot satisfy the gate.",
        )
    return value.strip()


def valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def impact_closure(request: dict[str, Any]) -> list[str]:
    changed = request.get("changed")
    if (not isinstance(changed, list) or not changed
            or any(not isinstance(item, str) or not item for item in changed)
            or len(changed) != len(set(changed))):
        raise DecisionError(
            "changed must be a unique non-empty list of impact nodes",
            "List the changed files/components explicitly before selecting a profile.",
        )
    if request.get("impactKnown") is not True:
        return list(changed)
    graph = request.get("impactGraph")
    if not isinstance(graph, dict):
        raise DecisionError(
            "impactGraph must be a JSON object",
            "Provide the bounded direct-impact graph for the changed nodes.",
        )
    for source, targets in graph.items():
        if (not isinstance(source, str) or not source
                or not isinstance(targets, list)
                or any(not isinstance(target, str) or not target for target in targets)):
            raise DecisionError(
                "impactGraph contains an invalid node or edge list",
                "Use non-empty string nodes and arrays of directly impacted nodes.",
            )

    ordered: list[str] = []
    seen: set[str] = set()
    queue = deque(changed)
    while queue:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        ordered.append(node)
        queue.extend(graph.get(node, []))
    return ordered


def contours_and_capabilities(
        contours: list[str], proportionality: dict[str, Any]) -> list[str]:
    definitions = require_object(proportionality.get("contours"), "policy.contours")
    capabilities: list[str] = []
    for contour in contours:
        definition = definitions.get(contour)
        if not isinstance(definition, dict):
            raise DecisionError(
                f"selected contour {contour!r} has no reviewed definition",
                "Restore PROPORTIONALITY_POLICY.json; never invent a contour.",
            )
        for capability in definition.get("capabilities") or []:
            if capability not in capabilities:
                capabilities.append(capability)
    return capabilities


def add_signal_contours(contours: list[str], signals: Any,
                        proportionality: dict[str, Any]) -> list[str]:
    if (not isinstance(signals, list)
            or any(not isinstance(signal, str) or not signal for signal in signals)):
        raise DecisionError(
            "signals must be an array of non-empty strings",
            "Pass detected risk signals explicitly; omit the field only when none exist.",
        )
    warnings: list[str] = []
    signal_contours = proportionality.get("signalContours") or {}
    for signal in signals:
        contour = signal_contours.get(signal)
        if contour is None:
            warning = f"unknown signal: {signal}"
            if warning not in warnings:
                warnings.append(warning)
        elif contour not in contours:
            contours.append(contour)
    return warnings


def select_profile(request: dict[str, Any], work: dict[str, Any],
                   proportionality: dict[str, Any]) -> dict[str, Any]:
    profile = request.get("profile")
    if profile not in {"targeted", "release"}:
        raise DecisionError(
            "profile must be targeted or release",
            "Set profile to targeted for bounded daily work or release for PR/release evidence.",
        )

    closure = impact_closure(request)
    raw_risk = request.get("risk")
    aliases = proportionality.get("riskAliases") or {}
    normalized_risk = aliases.get(raw_risk, raw_risk)
    routes = require_object(proportionality.get("riskRoutes"), "policy.riskRoutes")
    known_risk = normalized_risk in routes
    allowed_risks = set((work.get("activation") or {}).get("allowedRiskTiers") or [])
    impact_known = request.get("impactKnown") is True
    reasons: list[str] = []

    strict_release = profile == "release"
    if not known_risk:
        strict_release = True
        reasons.append("unknown risk fails closed")
    elif normalized_risk not in allowed_risks:
        strict_release = True
        reasons.append(f"{normalized_risk} risk is outside the working-deadline profile")
    if not impact_known:
        strict_release = True
        reasons.append("unknown impact requires strict release")

    profiles = work["verificationProfiles"]
    if strict_release:
        route = "strict.release"
        contours = list(profiles["release"]["baseContours"])
    else:
        route = "working_deadline.targeted"
        contours = list(routes[normalized_risk]["contours"])

    warnings = add_signal_contours(
        contours, request.get("signals", []), proportionality)

    candidate = request.get("candidateSha256")
    if profile == "release" and not valid_sha256(candidate):
        raise DecisionError(
            "release selection requires an exact lowercase SHA-256 candidate hash",
            "Compute the release-candidate SHA-256 and retry with candidateSha256.",
            route=route,
            verified=False,
        )
    if candidate is not None and not valid_sha256(candidate):
        raise DecisionError(
            "candidateSha256 is malformed",
            "Provide exactly 64 lowercase hexadecimal characters or omit it until release.",
            route=route,
            verified=False,
        )

    return {
        "status": "SELECTED",
        "verified": False,
        "route": route,
        "risk": normalized_risk if known_risk else "unknown",
        "contours": contours,
        "requiredCapabilities": contours_and_capabilities(contours, proportionality),
        "impactClosure": closure,
        "warnings": warnings,
        "reasons": reasons,
        "candidateSha256": candidate or "",
        "evidenceRequired": route == "strict.release",
    }


def validate_release_evidence(request: dict[str, Any], work: dict[str, Any],
                              proportionality: dict[str, Any]) -> dict[str, Any]:
    candidate = request.get("candidateSha256")
    if not valid_sha256(candidate):
        raise DecisionError(
            "current release candidate is not an exact lowercase SHA-256",
            "Hash the exact candidate and bind every release evidence record to that hash.",
            verified=False,
        )
    evidence = require_object(request.get("evidence"), "evidence")
    if evidence.get("candidateSha256") != candidate:
        raise DecisionError(
            "release evidence belongs to a different candidate",
            "Invalidate the old result and rerun release checks for the current candidate hash.",
            verified=False,
        )
    release = work["verificationProfiles"]["release"]
    contours = list(release["baseContours"])
    warnings = add_signal_contours(
        contours, request.get("signals", []), proportionality)
    if evidence.get("contours") != contours:
        raise DecisionError(
            "release evidence contours do not match the candidate's risk signals",
            "Rerun every selected base/signal contour and bind the exact contour list to evidence.",
            verified=False,
        )
    for field in ("windowsWslMatrix", "ciOrNative"):
        record = evidence.get(field)
        if not isinstance(record, dict):
            raise DecisionError(
                f"release evidence is missing {field}",
                f"Run {field} once for this candidate and record its PASSED result and hash.",
                verified=False,
            )
        if record.get("candidateSha256") != candidate:
            raise DecisionError(
                f"{field} evidence belongs to a different candidate",
                f"Rerun {field} against the exact current candidate SHA-256.",
                verified=False,
            )
        if record.get("status") != "PASSED":
            raise DecisionError(
                f"{field} evidence is not PASSED",
                f"Fix the failure and rerun {field} for this candidate; do not mark release verified.",
                verified=False,
            )
        runs = record.get("runsForCandidate")
        if (field == "windowsWslMatrix"
                and (type(runs) is not int or runs != 1)):
            raise DecisionError(
                "Windows/WSL matrix evidence must represent one run for this candidate hash",
                "Run the matrix once after the candidate is frozen and record runsForCandidate: 1.",
                verified=False,
            )
    return {
        "status": "PASS",
        "verified": True,
        "route": "strict.release",
        "candidateSha256": candidate,
        "contours": contours,
        "warnings": warnings,
        "windowsWslMatrixRunsForCandidate": evidence["windowsWslMatrix"][
            "runsForCandidate"],
    }


def validate_diagnostics(request: dict[str, Any], work: dict[str, Any]) -> dict[str, Any]:
    policy = work.get("diagnostics") or {}
    if request.get("collectionComplete") is not True:
        raise DecisionError(
            "independent diagnostic failure collection is incomplete",
            "Finish the original diagnostic pass and record every failure before editing.",
            verified=False,
        )
    if request.get("collectedBeforeFixes") is not True:
        raise DecisionError(
            "fixes started before the failure set was frozen",
            "Restart the diagnostic pass, collect the complete set, then fix causal clusters.",
            verified=False,
        )
    failures = request.get("failures")
    if not isinstance(failures, list):
        raise DecisionError(
            "failures must be an array",
            "Record the diagnostic failure set, using an empty array only for a clean pass.",
            verified=False,
        )
    failure_ids: list[str] = []
    clusters: dict[str, list[str]] = {}
    representatives: dict[str, str] = {}
    for failure in failures:
        if not isinstance(failure, dict):
            raise DecisionError(
                "each diagnostic failure must be an object",
                "Record id, rootCause, and cascade for every failure.",
                verified=False,
            )
        failure_id = require_string(failure.get("id"), "failure.id")
        root_cause = require_string(failure.get("rootCause"), "failure.rootCause")
        if failure_id in failure_ids:
            raise DecisionError(
                f"duplicate diagnostic failure id: {failure_id}",
                "Give each captured failure a stable unique id.",
                verified=False,
            )
        failure_ids.append(failure_id)
        clusters.setdefault(root_cause, []).append(failure_id)
        if root_cause not in representatives or failure.get("cascade") is not True:
            representatives[root_cause] = failure_id

    history = request.get("clusterHistory")
    if not isinstance(history, list):
        raise DecisionError(
            "clusterHistory must be an ordered array",
            "Record one completed entry per causal cluster, in repair order.",
            verified=False,
        )
    seen_clusters: set[str] = set()
    for step in history:
        if not isinstance(step, dict):
            raise DecisionError(
                "each clusterHistory entry must be an object",
                "Record exactly one rootCause per repair step.",
                verified=False,
            )
        root_cause = require_string(step.get("rootCause"), "clusterHistory.rootCause")
        if root_cause in seen_clusters:
            raise DecisionError(
                f"causal cluster {root_cause!r} was fixed more than once",
                "Keep one ordered repair record per causal cluster; do not batch duplicate steps.",
                verified=False,
            )
        if root_cause not in clusters:
            raise DecisionError(
                f"clusterHistory references unknown root cause {root_cause!r}",
                "Classify the failure set first, then repair only a recorded causal cluster.",
                verified=False,
            )
        seen_clusters.add(root_cause)
        if step.get("risky") is True:
            cheap = step.get("cheapDiscriminatingCheck")
            if (not isinstance(cheap, dict)
                    or type(cheap.get("exitCode")) is not int
                    or cheap.get("exitCode") != 0):
                raise DecisionError(
                    f"risky cluster {root_cause!r} lacks a passing discriminating check",
                    "Run one cheap focused check after this risky cluster before continuing.",
                    verified=False,
                )
    if seen_clusters != set(clusters):
        missing = sorted(set(clusters) - seen_clusters)
        raise DecisionError(
            f"not every causal cluster has an ordered repair record: {missing}",
            "Finish one causal cluster at a time before the final original-command rerun.",
            verified=False,
        )

    original = require_string(
        request.get("originalDiagnosticCommand"), "originalDiagnosticCommand")
    rerun = require_object(request.get("finalRerun"), "finalRerun")
    if rerun.get("command") != original:
        raise DecisionError(
            "final rerun is not the original diagnostic command",
            "Rerun the exact original diagnostic command after all causal clusters are fixed.",
            verified=False,
        )
    if type(rerun.get("exitCode")) is not int or rerun.get("exitCode") != 0:
        raise DecisionError(
            "final original diagnostic rerun failed",
            "Keep the unit unverified, fix the remaining cause, and rerun the original command.",
            verified=False,
        )
    if (policy.get("collectIndependentFailuresBeforeFixing") is not True
            or policy.get("classifyCascadesByRootCause") is not True
            or policy.get("fixOneCausalClusterAtATime") is not True
            or policy.get("finalRerun") != "original-diagnostic-command"
            or policy.get("failedFinalRerunIsVerified") is not False):
        raise DecisionError(
            "diagnostic policy is malformed or weakened",
            "Restore the reviewed working-deadline diagnostic policy.",
            verified=False,
        )
    return {
        "status": "PASS",
        "verified": True,
        "failureSet": failure_ids,
        "independentFailureSet": [representatives[name] for name in clusters],
        "causalClusters": clusters,
        "finalRerunCommand": original,
    }


def backlog_block(why: str, fix: str, blocking_kinds: list[str] | None = None) -> None:
    raise DecisionError(
        why,
        fix,
        status="BLOCK_CURRENT_UNIT",
        verified=False,
        blockingKinds=blocking_kinds or [],
    )


def evaluate_backlog(request: dict[str, Any], work: dict[str, Any]) -> dict[str, Any]:
    policy = work.get("backlog") or {}
    blockers = request.get("blockingKinds", [])
    if (not isinstance(blockers, list)
            or any(not isinstance(item, str) or not item for item in blockers)):
        backlog_block(
            "blockingKinds must be an array of defect-class strings",
            "Classify the finding before making a backlog decision.",
        )
    never = set(policy.get("neverBacklog") or [])
    hard_blockers = [item for item in blockers if item in never]
    if hard_blockers:
        backlog_block(
            "the finding violates a never-backlog invariant",
            "Keep the unit open and resolve the blocking acceptance/risk regression first.",
            hard_blockers,
        )
    if blockers:
        backlog_block(
            "blockingKinds contradict non-blocking backlog eligibility",
            "Keep the finding in the current unit or reclassify it with evidence that it is non-blocking.",
            blockers,
        )
    if request.get("introducedByCurrentDiff") is True:
        backlog_block(
            "the current diff introduced this regression",
            "Fix or revert the current-diff regression before verifying the unit.",
            ["current-diff-regression"],
        )
    required_facts = {
        "preExisting": request.get("preExisting") is True,
        "outOfScope": request.get("outOfScope") is True,
        "nonBlocking": request.get("nonBlocking") is True,
        "notIntroducedByCurrentDiff": request.get("introducedByCurrentDiff") is False,
    }
    missing = [name for name, present in required_facts.items() if not present]
    if missing:
        backlog_block(
            f"finding is not eligible for backlog: missing {', '.join(missing)}",
            "Keep it in the current gate unless all four eligibility facts are evidenced.",
            blockers,
        )
    capture = request.get("capture")
    if not isinstance(capture, dict) or any(
            not isinstance(capture.get(field), str) or not capture[field].strip()
            for field in ("path", "id", "summary")):
        backlog_block(
            "eligible finding lacks a durable backlog capture record",
            "Write path, stable id, and summary to the project backlog before handoff.",
            blockers,
        )
    if (set(policy.get("eligible") or []) != {
            "pre-existing", "out-of-scope", "non-blocking",
            "not-introduced-by-current-diff",
            } or policy.get("captureRequired") is not True
            or policy.get("fixInCurrentUnit") is not False):
        backlog_block(
            "backlog policy is malformed or weakened",
            "Restore the reviewed working-deadline backlog policy.",
        )
    return {
        "status": "BACKLOG",
        "verified": True,
        "fixInCurrentUnit": False,
        "capture": capture,
        "eligibility": sorted(required_facts),
    }


def decide(request: dict[str, Any]) -> dict[str, Any]:
    work, proportionality = load_policies()
    operation = request.get("operation")
    if operation == "select":
        return select_profile(request, work, proportionality)
    if operation == "release-evidence":
        return validate_release_evidence(request, work, proportionality)
    if operation == "diagnostics":
        return validate_diagnostics(request, work)
    if operation == "backlog":
        return evaluate_backlog(request, work)
    raise DecisionError(
        "operation must be select, release-evidence, diagnostics, or backlog",
        "Set one bounded operation in the input manifest; do not run an implicit full scan.",
    )


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list:
        return 0
    parser = argparse.ArgumentParser(
        description="Select verification or validate bounded failure evidence.")
    parser.add_argument("--input", type=Path, required=True,
                        help="JSON request manifest; no input means a quiet no-op")
    args = parser.parse_args(args_list)
    try:
        request = load_object(args.input)
        result = decide(request)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except DecisionError as exc:
        result = {
            "status": "FAIL",
            "verified": False,
            "why": exc.why,
            "fix": exc.fix,
            **exc.fields,
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 1
    except Exception as exc:
        print(json.dumps({
            "status": "FAIL",
            "verified": False,
            "why": f"unexpected selector error: {exc}",
            "fix": "Inspect the bounded input and policy files; do not treat this run as evidence.",
        }, ensure_ascii=False, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
