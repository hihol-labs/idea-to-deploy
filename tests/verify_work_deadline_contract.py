#!/usr/bin/env python3
"""Frozen contract proof for the opt-in working-deadline mode."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "skills" / "_shared" / "WORKING_DEADLINE_POLICY.json"
INHERITED_PATH = ROOT / "skills" / "_shared" / "PROPORTIONALITY_POLICY.json"
CORPUS_PATH = ROOT / "benchmarks" / "working-deadline" / "CORPUS.json"
SEAL_PATH = ROOT / "benchmarks" / "working-deadline" / "CORPUS.sha256"
DOC_PATH = ROOT / "docs" / "WORKING_DEADLINE_MODE.md"
LAUNCH_PLAN = ROOT / "LAUNCH_PLAN.md"
EXPECTED_GUARDS = {
    "soft-checkpoint-drift",
    "hard-pause-drift",
    "multi-unit-handoff",
    "allow-high-in-work-profile",
    "drop-required-risk-override",
    "drop-release-hash-binding",
    "accept-blocked-review-cache",
    "general-review-resets-security",
    "backlog-critical-security",
    "external-approval-without-payload-binding",
    "low-effort-review",
    "backlog-current-diff-eligibility-drift",
    "low-effort-allowlist-conflict",
    "rollback-trigger-removal",
    "inherited-policy-digest-drift",
    "missing-frozen-case",
}
REQUIRED_CACHE_KEYS = {
    "repository", "baseCommit", "reviewedTree", "diffHash",
    "scopeContractHash", "acceptanceContractHash", "rubricHash",
    "methodologyVersion", "riskTier",
}
REQUIRED_BACKLOG_BLOCKERS = {
    "acceptance-criterion-failure", "required-risk-invariant-failure",
    "current-diff-regression", "critical-security", "data-loss",
}
REQUIRED_BACKLOG_ELIGIBILITY = {
    "pre-existing", "out-of-scope", "non-blocking",
    "not-introduced-by-current-diff",
}
REQUIRED_LOW_EFFORT_ALLOWLIST = {
    "bounded-low-mechanical", "bounded-medium-mechanical",
}
REQUIRED_ROLLBACK_TRIGGERS = {
    "critical-false-completion", "high-risk-bypass",
    "stale-review-cache-accept", "unapproved-external-write",
    "material-release-failure-increase",
}


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path}: root must be an object")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal_ok() -> bool:
    try:
        expected = SEAL_PATH.read_text(encoding="utf-8").strip().split()[0]
    except Exception:
        return False
    return len(expected) == 64 and expected == sha256(CORPUS_PATH)


def validate_policy(policy: dict, inherited_path: Path = INHERITED_PATH) -> list[str]:
    issues: list[str] = []
    if policy.get("version") != 1 or policy.get("id") != "working-deadline-v1":
        issues.append("policy identity/version drift")

    activation = policy.get("activation") or {}
    if activation.get("profile") != "working_deadline" \
            or activation.get("explicitOptInRequired") is not True \
            or activation.get("defaultEnabled") is not False:
        issues.append("profile must remain explicit opt-in and default-off")
    if activation.get("allowedRiskTiers") != ["low", "medium"]:
        issues.append("work profile may cover only low and medium risk")
    if activation.get("unknownRisk") != "escalate-to-high" \
            or activation.get("highRisk") != "exit-to-strict-release":
        issues.append("unknown/high risk escalation drift")
    if activation.get("riskSignalsOverrideUserCriteria") is not True:
        issues.append("risk signals must override incomplete user criteria")

    inherited = policy.get("inheritsVerificationPolicy") or {}
    if inherited.get("path") != "skills/_shared/PROPORTIONALITY_POLICY.json" \
            or inherited.get("relationship") != "cadence-overlay-only" \
            or inherited.get("sha256") != sha256(inherited_path):
        issues.append("inherited proportionality policy binding drift")

    timebox = policy.get("timebox") or {}
    if timebox.get("measurement") != "host-observed-unit-elapsed" \
            or timebox.get("softCheckpointSeconds") != 1800 \
            or timebox.get("hardPauseSeconds") != 2700:
        issues.append("30/45-minute observed timebox drift")
    if timebox.get("softCheckpointAction") \
            != "report-ready-blocker-remainder-estimate" \
            or timebox.get("hardPauseOutcome") != "budget_exhausted" \
            or timebox.get("hardPauseState") != "recovery_required":
        issues.append("typed checkpoint/pause semantics drift")
    for field in ("stopBeforeNextExpensiveAttempt", "allowCheapInspectionAndCheckpoint",
                  "stopAtSafeBoundary"):
        if timebox.get(field) is not True:
            issues.append(f"timebox.{field} must remain true")
    if timebox.get("partialCompletionIsVerified") is not False:
        issues.append("partial completion must never become verified")

    cadence = policy.get("unitCadence") or {}
    if cadence.get("maxOpenUnits") != 1 \
            or cadence.get("handoffAfterVerifiedUnit") is not True \
            or cadence.get("maxVerifiedUnitsPerHandoff") != 1 \
            or cadence.get("nextUnitRequiresNewHandoffEntry") is not True:
        issues.append("one-unit WIP/handoff cadence drift")
    if cadence.get("boundedAutonomousOverrideRequiresExplicitApproval") is not True \
            or cadence.get("unitMustBeIndependentVerticalSlice") is not True:
        issues.append("bounded override/vertical-slice guard drift")

    profiles = policy.get("verificationProfiles") or {}
    targeted = profiles.get("targeted") or {}
    release = profiles.get("release") or {}
    if targeted.get("selection") != "risk-derived-impact-closure" \
            or targeted.get("requiredCapabilitiesSource") \
            != "inheritsVerificationPolicy.riskRoutes" \
            or targeted.get("matchingSignalContoursRequired") is not True \
            or targeted.get("transitiveImpactRequired") is not True \
            or targeted.get("unknownImpact") != "exit-to-strict-release" \
            or targeted.get("userCriteriaMayRemoveRequiredCapability") is not False:
        issues.append("targeted risk/impact closure drift")
    if release.get("baseContours") != ["static", "targeted", "review", "full"] \
            or release.get("matchingSignalContoursRequired") is not True \
            or release.get("exactCandidateHashRequired") is not True \
            or release.get("candidateHashAlgorithm") != "sha256" \
            or release.get("invalidateOnAnyCandidateChange") is not True \
            or release.get("windowsWslMatrixOncePerCandidateHash") is not True \
            or release.get("ciOrNativeEvidenceRequired") is not True:
        issues.append("release exact-candidate evidence binding drift")

    cache = policy.get("reviewCache") or {}
    if set(cache.get("keyFields") or []) != REQUIRED_CACHE_KEYS \
            or cache.get("acceptedVerdicts") != ["PASSED"] \
            or cache.get("warningVerdictRequiresDurableWarnings") is not True \
            or cache.get("blockedOrUnverifiedSatisfiesGate") is not False \
            or cache.get("invalidateOnKeyChange") is not True \
            or cache.get("acceptedVerdictRequiresAdjudicatedReceipt") is not True \
            or cache.get("receiptPolicy") != "verification-loop-v1":
        issues.append("successful context-bound review-cache rule drift")

    risk = policy.get("riskBudget") or {}
    if risk.get("resetRequiresSuccessfulBoundVerdict") is not True \
            or risk.get("reviewResets") != ["general-change-risk"] \
            or risk.get("securityReviewResets") != ["security-change-risk"] \
            or risk.get("generalReviewMayResetSecurity") is not False \
            or risk.get("countOnlyPostGateDelta") is not True:
        issues.append("status-aware separated risk-budget rule drift")

    diagnostics = policy.get("diagnostics") or {}
    for field in ("collectIndependentFailuresBeforeFixing", "classifyCascadesByRootCause",
                  "fixOneCausalClusterAtATime", "cheapDiscriminatingCheckAfterRiskyCluster"):
        if diagnostics.get(field) is not True:
            issues.append(f"diagnostics.{field} must remain true")
    if diagnostics.get("finalRerun") != "original-diagnostic-command" \
            or diagnostics.get("failedFinalRerunIsVerified") is not False:
        issues.append("diagnostic final-rerun semantics drift")

    backlog = policy.get("backlog") or {}
    if set(backlog.get("eligible") or []) != REQUIRED_BACKLOG_ELIGIBILITY \
            or not REQUIRED_BACKLOG_BLOCKERS <= set(backlog.get("neverBacklog") or []) \
            or backlog.get("captureRequired") is not True \
            or backlog.get("fixInCurrentUnit") is not False:
        issues.append("backlog eligibility or blocking-defect boundary drift")

    external = policy.get("externalWrites") or {}
    for field in ("exactPreviewRequired", "exactTargetsRequired", "fullPayloadRequired",
                  "attachmentsIncluded", "sessionProvenanceRequired",
                  "invalidateOnPayloadOrTargetChange"):
        if external.get(field) is not True:
            issues.append(f"externalWrites.{field} must remain true")
    if external.get("approvalBinding") \
            != "sha256-canonical-tool-name-targets-payload" \
            or external.get("readOnlyRequiresWriteApproval") is not False \
            or external.get("exactAlreadyAuthorizedActionRequiresRepeatApproval") is not False:
        issues.append("external approval is not bound to exact action payload")

    model = policy.get("modelRouting") or {}
    forbidden = set(model.get("lowEffortForbiddenFor") or [])
    allowed = set(model.get("lowEffortAllowedFor") or [])
    if allowed != REQUIRED_LOW_EFFORT_ALLOWLIST \
            or allowed & forbidden \
            or not {"review", "security", "root-cause", "architecture", "high-risk",
            "unknown-risk"} <= forbidden \
            or model.get("modelChoiceMayRemoveEvidenceContour") is not False \
            or model.get("speedOrCreditMultipliersAreContractual") is not False:
        issues.append("model speed setting weakened a quality gate")

    session = policy.get("sessionBoundary") or {}
    if session.get("afterResult") != "return-result-and-cheap-checkpoint" \
            or session.get("automaticExplicitClose") is not False \
            or session.get("explicitCloseRequiresUserIntent") is not True:
        issues.append("result handoff was confused with explicit close")
    rollout = policy.get("rollout") or {}
    if rollout.get("defaultOn") is not False \
            or rollout.get("stage") != "contract-only" \
            or rollout.get("minimumCanaryUnits") != 10 \
            or rollout.get("minimumComparableUnitsBeforeDefault") != 30 \
            or set(rollout.get("rollbackOn") or []) != REQUIRED_ROLLBACK_TRIGGERS:
        issues.append("opt-in canary rollout guard drift")
    return issues


def route_case(policy: dict, inherited: dict, case: dict) -> tuple[str, list[str]]:
    requested = case.get("requestedProfile")
    risk = case.get("risk")
    known_risk = risk if risk in inherited["riskRoutes"] else "high"
    allowed = set(policy["activation"]["allowedRiskTiers"])
    if requested == "release" or risk not in allowed:
        route = "strict.release"
        contours = list(policy["verificationProfiles"]["release"]["baseContours"])
    else:
        route = "working_deadline.targeted"
        contours = list(inherited["riskRoutes"][known_risk]["contours"])
    for signal in case.get("signals") or []:
        contour = inherited.get("signalContours", {}).get(signal)
        if contour and contour not in contours:
            contours.append(contour)
    return route, contours


def validate_corpus(corpus: dict, policy: dict, inherited: dict) -> list[str]:
    issues: list[str] = []
    if corpus.get("schemaVersion") != 1 \
            or corpus.get("id") != "working-deadline-contract-v1":
        issues.append("corpus identity/schema drift")
    if "never external adoption" not in str(corpus.get("scope") or ""):
        issues.append("internal corpus is not separated from external evidence")
    if corpus.get("policyPath") != "skills/_shared/WORKING_DEADLINE_POLICY.json" \
            or corpus.get("policySha256") != sha256(POLICY_PATH):
        issues.append("corpus is not bound to the reviewed deadline policy")
    if corpus.get("inheritedPolicyPath") \
            != "skills/_shared/PROPORTIONALITY_POLICY.json" \
            or corpus.get("inheritedPolicySha256") != sha256(INHERITED_PATH):
        issues.append("corpus is not bound to the inherited verification policy")
    if set(corpus.get("mutationGuards") or []) != EXPECTED_GUARDS:
        issues.append("mutation guard inventory drift")

    requirements = corpus.get("requirements") or {}
    if requirements.get("softCheckpointSeconds") \
            != policy["timebox"]["softCheckpointSeconds"] \
            or requirements.get("hardPauseSeconds") \
            != policy["timebox"]["hardPauseSeconds"] \
            or requirements.get("maxVerifiedUnitsPerHandoff") \
            != policy["unitCadence"]["maxVerifiedUnitsPerHandoff"]:
        issues.append("corpus thresholds drift from policy")
    cases = corpus.get("cases")
    if not isinstance(cases, list):
        return issues + ["cases must be a list"]
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if len(ids) != len(set(ids)) or set(ids) != set(requirements.get("requiredCaseIds") or []):
        issues.append("frozen case coverage is missing or duplicated")

    contour_capabilities = inherited["contours"]
    for case in cases:
        if not isinstance(case, dict):
            issues.append("case must be an object")
            continue
        route, contours = route_case(policy, inherited, case)
        if route != case.get("expectedRoute") or contours != case.get("expectedContours"):
            issues.append(f"{case.get('id')}: route/contour expectation drift")
        risk = case.get("risk") if case.get("risk") in inherited["riskRoutes"] else "high"
        required = set(inherited["riskRoutes"][risk]["requiredCapabilities"])
        for signal in case.get("signals") or []:
            contour = inherited.get("signalContours", {}).get(signal)
            if contour:
                required.update(contour_capabilities[contour]["capabilities"])
        covered = {
            capability for contour in contours
            for capability in contour_capabilities[contour]["capabilities"]
        }
        if not required <= covered:
            issues.append(f"{case.get('id')}: selected route lost required capability")
        if case.get("requestedProfile") == "release" \
                and not re.fullmatch(r"[0-9a-f]{64}", str(case.get("candidateSha256") or "")):
            issues.append(f"{case.get('id')}: release case lacks exact candidate hash")
    return issues


def mutation_guard_results(corpus: dict, policy: dict, inherited: dict) -> dict[str, bool]:
    results: dict[str, bool] = {}

    mutant = copy.deepcopy(policy)
    mutant["timebox"]["softCheckpointSeconds"] = 1200
    results["soft-checkpoint-drift"] = bool(validate_policy(mutant))
    mutant = copy.deepcopy(policy)
    mutant["timebox"]["hardPauseSeconds"] = 3600
    results["hard-pause-drift"] = bool(validate_policy(mutant))
    mutant = copy.deepcopy(policy)
    mutant["unitCadence"]["maxVerifiedUnitsPerHandoff"] = 2
    results["multi-unit-handoff"] = bool(validate_policy(mutant))
    mutant = copy.deepcopy(policy)
    mutant["activation"]["allowedRiskTiers"].append("high")
    results["allow-high-in-work-profile"] = bool(validate_policy(mutant))
    mutant = copy.deepcopy(policy)
    mutant["activation"]["riskSignalsOverrideUserCriteria"] = False
    results["drop-required-risk-override"] = bool(validate_policy(mutant))
    mutant = copy.deepcopy(policy)
    mutant["verificationProfiles"]["release"]["exactCandidateHashRequired"] = False
    results["drop-release-hash-binding"] = bool(validate_policy(mutant))
    mutant = copy.deepcopy(policy)
    mutant["reviewCache"]["acceptedVerdicts"].append("BLOCKED")
    results["accept-blocked-review-cache"] = bool(validate_policy(mutant))
    mutant = copy.deepcopy(policy)
    mutant["riskBudget"]["generalReviewMayResetSecurity"] = True
    results["general-review-resets-security"] = bool(validate_policy(mutant))
    mutant = copy.deepcopy(policy)
    mutant["backlog"]["neverBacklog"].remove("critical-security")
    results["backlog-critical-security"] = bool(validate_policy(mutant))
    mutant = copy.deepcopy(policy)
    mutant["externalWrites"]["approvalBinding"] = "session-only"
    results["external-approval-without-payload-binding"] = bool(validate_policy(mutant))
    mutant = copy.deepcopy(policy)
    mutant["modelRouting"]["lowEffortForbiddenFor"].remove("review")
    results["low-effort-review"] = bool(validate_policy(mutant))
    mutant = copy.deepcopy(policy)
    mutant["backlog"]["eligible"].remove("not-introduced-by-current-diff")
    results["backlog-current-diff-eligibility-drift"] = bool(validate_policy(mutant))
    mutant = copy.deepcopy(policy)
    mutant["modelRouting"]["lowEffortAllowedFor"].append("security")
    results["low-effort-allowlist-conflict"] = bool(validate_policy(mutant))
    mutant = copy.deepcopy(policy)
    mutant["rollout"]["rollbackOn"].remove("critical-false-completion")
    results["rollback-trigger-removal"] = bool(validate_policy(mutant))
    mutant = copy.deepcopy(policy)
    mutant["inheritsVerificationPolicy"]["sha256"] = "0" * 64
    results["inherited-policy-digest-drift"] = bool(validate_policy(mutant))
    corpus_mutant = copy.deepcopy(corpus)
    corpus_mutant["cases"] = corpus_mutant["cases"][:-1]
    results["missing-frozen-case"] = bool(validate_corpus(corpus_mutant, policy, inherited))
    return results


def validate_docs() -> list[str]:
    issues: list[str] = []
    try:
        doc = DOC_PATH.read_text(encoding="utf-8")
        launch = LAUNCH_PLAN.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"working-deadline docs are missing: {exc}"]
    markers = (
        "opt-in", "30 минут", "45 минут", "targeted", "release",
        "risk policy", "handoff", "payload hash", "не является explicit close",
    )
    missing = [marker for marker in markers if marker not in doc]
    if missing:
        issues.append("working-deadline doc lacks: " + ", ".join(missing))
    if "PE5-010" not in launch or "working_deadline" not in launch:
        issues.append("launch plan lacks the approved working-deadline program")
    return issues


def main() -> int:
    try:
        policy = load_json(POLICY_PATH)
        inherited = load_json(INHERITED_PATH)
        corpus = load_json(CORPUS_PATH)
        issues = validate_policy(policy)
        issues.extend(validate_corpus(corpus, policy, inherited))
        issues.extend(validate_docs())
        if not seal_ok():
            issues.append("working-deadline corpus seal is missing or stale")
        guards = mutation_guard_results(corpus, policy, inherited)
        missed = sorted(name for name, caught in guards.items() if not caught)
        if set(guards) != EXPECTED_GUARDS or missed:
            issues.append(f"mutation guards failed: missing={missed} got={sorted(guards)}")
        if issues:
            print("FAIL working-deadline contract")
            for issue in issues:
                print("  - " + issue)
            return 1
        print(
            "ALL PASS — working_deadline is sealed, opt-in, one-unit, "
            "risk-preserving and exact-action-bound"
        )
        print(json.dumps({
            "cases": len(corpus["cases"]),
            "mutationGuards": len(guards),
            "softCheckpointSeconds": policy["timebox"]["softCheckpointSeconds"],
            "hardPauseSeconds": policy["timebox"]["hardPauseSeconds"],
            "defaultOn": policy["rollout"]["defaultOn"],
        }, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"FAIL working-deadline contract: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
