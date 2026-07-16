#!/usr/bin/env python3
"""Frozen paired A/B oracle for risk-proportional verification cost."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "benchmarks" / "proportionality" / "CORPUS.json"
SEAL_PATH = ROOT / "benchmarks" / "proportionality" / "CORPUS.sha256"
TASK_SKILL = ROOT / "skills" / "task" / "SKILL.md"
HELPERS = ROOT / "skills" / "_shared" / "helpers.md"
EXPECTED_GUARDS = {
    "always-full-low",
    "drop-medium-targeted",
    "drop-high-full",
    "ignore-security-signal",
    "zero-cost-contour",
    "missing-risk-pair",
}


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path}: root must be an object")
    return value


def seal_ok(path: Path, seal_path: Path) -> bool:
    try:
        expected = seal_path.read_text(encoding="utf-8").strip().split()[0]
    except Exception:
        return False
    return len(expected) == 64 and hashlib.sha256(path.read_bytes()).hexdigest() == expected


def validate_policy(policy: dict) -> list[str]:
    issues: list[str] = []
    if policy.get("version") != 1:
        issues.append("policy version must be 1")
    if policy.get("id") != "risk-proportional-verification-v1":
        issues.append("policy id is invalid")
    if policy.get("riskAliases") != {
        "trivial": "low", "standard": "medium", "high-risk": "high"
    }:
        issues.append("risk aliases drifted")
    contours = policy.get("contours")
    if not isinstance(contours, dict) or set(contours) != {
        "static", "targeted", "review", "security", "full"
    }:
        return issues + ["contours must be the reviewed five-contour set"]
    for contour_id, row in contours.items():
        if not isinstance(row, dict):
            issues.append(f"{contour_id}: contour must be an object")
            continue
        for field in ("normalizedTimeUnits", "normalizedTokenUnits"):
            value = row.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                issues.append(f"{contour_id}.{field} must be positive")
        capabilities = row.get("capabilities")
        if not isinstance(capabilities, list) or not capabilities \
                or len(capabilities) != len(set(capabilities)):
            issues.append(f"{contour_id}.capabilities must be a unique non-empty list")

    routes = policy.get("riskRoutes")
    if not isinstance(routes, dict) or set(routes) != {"low", "medium", "high"}:
        return issues + ["riskRoutes must be exactly low, medium and high"]
    for risk, row in routes.items():
        if not isinstance(row, dict):
            issues.append(f"{risk}: route must be an object")
            continue
        selected = row.get("contours")
        required = row.get("requiredCapabilities")
        if not isinstance(selected, list) or not selected \
                or any(item not in contours for item in selected):
            issues.append(f"{risk}: route has invalid contours")
            continue
        covered = {
            capability for contour in selected
            for capability in contours[contour]["capabilities"]
        }
        if not isinstance(required, list) or not set(required) <= covered:
            issues.append(f"{risk}: required capabilities are not covered")

    signals = policy.get("signalContours")
    if not isinstance(signals, dict) \
            or any(contour not in contours for contour in signals.values()):
        issues.append("signalContours contains an invalid contour")
    invariants = policy.get("invariants")
    if not isinstance(invariants, dict):
        issues.append("invariants must be an object")
    else:
        if set(invariants.get("alwaysFullContours") or []) != set(contours):
            issues.append("alwaysFullContours must cover every contour")
        if set(invariants.get("lowForbiddenContours") or []) != {
            "review", "security", "full"
        }:
            issues.append("lowForbiddenContours drifted")
        if invariants.get("unknownRisk") != "fail-closed":
            issues.append("unknown risk must fail closed")
    return issues


def validate_corpus(corpus: dict, policy_path: Path, policy: dict) -> list[str]:
    issues: list[str] = []
    if corpus.get("schemaVersion") != 1 \
            or corpus.get("id") != "proportionality-paired-v1":
        issues.append("corpus identity/schema is invalid")
    if "never external adoption" not in str(corpus.get("scope") or ""):
        issues.append("internal benchmark is not explicitly separated from external adoption")
    try:
        policy_relative = policy_path.relative_to(ROOT).as_posix()
    except Exception:
        policy_relative = ""
    if corpus.get("policyPath") != policy_relative:
        issues.append("corpus policyPath does not resolve to the reviewed policy")
    digest = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    if corpus.get("policySha256") != digest:
        issues.append("policy digest differs from the frozen benchmark binding")
    if set(corpus.get("mutationGuards") or []) != EXPECTED_GUARDS:
        issues.append("mutation guards do not match the reviewed set")

    requirements = corpus.get("requirements")
    pairs = corpus.get("pairs")
    if not isinstance(requirements, dict) or not isinstance(pairs, list):
        return issues + ["requirements/pairs schema is invalid"]
    seen: set[str] = set()
    counts = {"low": 0, "medium": 0, "high": 0}
    for pair in pairs:
        if not isinstance(pair, dict):
            issues.append("pair must be an object")
            continue
        pair_id = pair.get("id")
        risk = pair.get("risk")
        if not isinstance(pair_id, str) or not pair_id or pair_id in seen:
            issues.append(f"pair id is missing/duplicate: {pair_id!r}")
        else:
            seen.add(pair_id)
        if risk not in counts:
            issues.append(f"{pair_id}: invalid risk")
            continue
        counts[risk] += 1
        signals = pair.get("signals")
        if not isinstance(signals, list) or len(signals) != len(set(signals)):
            issues.append(f"{pair_id}: signals must be a unique list")
            continue
        expected = set(policy["riskRoutes"][risk]["requiredCapabilities"])
        for signal in signals:
            contour = policy.get("signalContours", {}).get(signal)
            if contour:
                expected.update(policy["contours"][contour]["capabilities"])
        if set(pair.get("requiredCapabilities") or []) != expected:
            issues.append(f"{pair_id}: required capabilities drift from policy/signals")
    minimum = requirements.get("minimumPairsPerRisk")
    if type(minimum) is not int or minimum < 1:
        issues.append("minimumPairsPerRisk must be a positive integer")
    elif any(count < minimum for count in counts.values()):
        issues.append(f"pair count below frozen minimum: {counts}")
    for field in ("maxAdaptiveTimeRatio", "maxAdaptiveTokenRatio"):
        thresholds = requirements.get(field)
        if not isinstance(thresholds, dict) or set(thresholds) != set(counts) \
                or any(isinstance(value, bool) or not isinstance(value, (int, float))
                       or not 0 < value <= 1 for value in thresholds.values()):
            issues.append(f"{field} thresholds are invalid")
    return issues


def selected_contours(policy: dict, pair: dict, strategy: str) -> list[str]:
    if strategy == "always-full":
        return list(policy["invariants"]["alwaysFullContours"])
    selected = list(policy["riskRoutes"][pair["risk"]]["contours"])
    for signal in pair.get("signals") or []:
        contour = policy.get("signalContours", {}).get(signal)
        if contour and contour not in selected:
            selected.append(contour)
    return selected


def measure(policy: dict, pair: dict, strategy: str) -> dict:
    selected = selected_contours(policy, pair, strategy)
    capabilities = {
        capability for contour in selected
        for capability in policy["contours"][contour]["capabilities"]
    }
    required = set(pair["requiredCapabilities"])
    return {
        "contours": selected,
        "qualityVerified": required <= capabilities,
        "timeUnits": sum(policy["contours"][item]["normalizedTimeUnits"]
                         for item in selected),
        "tokenUnits": sum(policy["contours"][item]["normalizedTokenUnits"]
                          for item in selected),
    }


def evaluate(corpus: dict, policy_path: Path, policy: dict) -> tuple[list[str], list[dict]]:
    issues = validate_policy(policy) + validate_corpus(corpus, policy_path, policy)
    if issues:
        return issues, []
    requirements = corpus["requirements"]
    results = []
    regressions = 0
    for pair in corpus["pairs"]:
        baseline = measure(policy, pair, "always-full")
        adaptive = measure(policy, pair, "adaptive")
        time_ratio = adaptive["timeUnits"] / baseline["timeUnits"]
        token_ratio = adaptive["tokenUnits"] / baseline["tokenUnits"]
        if not baseline["qualityVerified"]:
            issues.append(f"{pair['id']}: always-full baseline lost required quality")
        if not adaptive["qualityVerified"]:
            issues.append(f"{pair['id']}: adaptive route lost required quality")
            if baseline["qualityVerified"]:
                regressions += 1
        risk = pair["risk"]
        if time_ratio > requirements["maxAdaptiveTimeRatio"][risk]:
            issues.append(f"{pair['id']}: adaptive time ratio {time_ratio:.3f} exceeds ceiling")
        if token_ratio > requirements["maxAdaptiveTokenRatio"][risk]:
            issues.append(f"{pair['id']}: adaptive token ratio {token_ratio:.3f} exceeds ceiling")
        if risk == "low" and set(adaptive["contours"]) & set(
                policy["invariants"]["lowForbiddenContours"]):
            issues.append(f"{pair['id']}: low route paid a forbidden high-cost contour")
        results.append({
            "id": pair["id"],
            "risk": risk,
            "baseline": baseline,
            "adaptive": adaptive,
            "timeRatio": round(time_ratio, 4),
            "tokenRatio": round(token_ratio, 4),
        })
    quality_rate = (
        sum(row["adaptive"]["qualityVerified"] for row in results) / len(results)
        if results else 0
    )
    if quality_rate < requirements["requiredQualityRate"]:
        issues.append(f"adaptive quality rate {quality_rate:.3f} is below requirement")
    if regressions > requirements["maxQualityRegressions"]:
        issues.append(f"quality regressions {regressions} exceed frozen maximum")
    return issues, results


def mutation_guard_results(corpus: dict, policy_path: Path, policy: dict) -> dict[str, bool]:
    results: dict[str, bool] = {}

    mutant = copy.deepcopy(policy)
    mutant["riskRoutes"]["low"]["contours"] = list(
        mutant["invariants"]["alwaysFullContours"])
    results["always-full-low"] = bool(evaluate(corpus, policy_path, mutant)[0])

    mutant = copy.deepcopy(policy)
    mutant["riskRoutes"]["medium"]["contours"].remove("targeted")
    results["drop-medium-targeted"] = bool(evaluate(corpus, policy_path, mutant)[0])

    mutant = copy.deepcopy(policy)
    mutant["riskRoutes"]["high"]["contours"].remove("full")
    results["drop-high-full"] = bool(evaluate(corpus, policy_path, mutant)[0])

    mutant = copy.deepcopy(policy)
    mutant["signalContours"] = {}
    results["ignore-security-signal"] = bool(evaluate(corpus, policy_path, mutant)[0])

    mutant = copy.deepcopy(policy)
    mutant["contours"]["static"]["normalizedTimeUnits"] = 0
    results["zero-cost-contour"] = bool(evaluate(corpus, policy_path, mutant)[0])

    mutant_corpus = copy.deepcopy(corpus)
    mutant_corpus["pairs"] = [
        pair for pair in mutant_corpus["pairs"] if pair["risk"] != "low"
    ]
    results["missing-risk-pair"] = bool(
        evaluate(mutant_corpus, policy_path, policy)[0])
    return results


def main() -> int:
    try:
        if not seal_ok(CORPUS_PATH, SEAL_PATH):
            raise AssertionError("frozen proportionality corpus seal mismatch")
        corpus = load_json(CORPUS_PATH)
        policy_path = ROOT / str(corpus.get("policyPath") or "")
        policy_path.resolve().relative_to(ROOT.resolve())
        policy = load_json(policy_path)
        issues, results = evaluate(corpus, policy_path, policy)

        for source in (TASK_SKILL, HELPERS):
            text = source.read_text(encoding="utf-8")
            if "skills/_shared/PROPORTIONALITY_POLICY.json" not in text:
                issues.append(f"{source.relative_to(ROOT)} does not consume the policy")
        guards = mutation_guard_results(corpus, policy_path, policy)
        missed = [name for name, killed in guards.items() if not killed]
        if missed:
            issues.append(f"mutation guards missed: {missed}")
        if issues:
            print(json.dumps({"status": "FAIL", "issues": issues}, indent=2))
            return 1

        maxima = {}
        for risk in ("low", "medium", "high"):
            rows = [row for row in results if row["risk"] == risk]
            maxima[risk] = {
                "maxTimeRatio": max(row["timeRatio"] for row in rows),
                "maxTokenRatio": max(row["tokenRatio"] for row in rows),
            }
        print(json.dumps({
            "status": "PASS",
            "corpus": corpus["id"],
            "pairs": len(results),
            "qualityVerified": len(results),
            "qualityRegressions": 0,
            "ratios": maxima,
            "mutationGuards": f"{len(guards)}/{len(guards)}",
            "externalEvidence": False,
        }, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
