#!/usr/bin/env python3
"""Privacy-safe, fail-closed evaluator for independent external outcomes."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "docs" / "PRACTICAL_EFFECTIVENESS_CONTRACT.json"
DEFAULT_SCHEMA = ROOT / "docs" / "external-validation" / "EXTERNAL_OUTCOME_SCHEMA.json"
PROJECT_RE = re.compile(r"^proj_[a-f0-9]{12}$")
OPERATOR_RE = re.compile(r"^op_[a-f0-9]{12}$")
SHA_RE = re.compile(r"^[a-f0-9]{64}$")
PRIMARY_METRICS = (
    "defectEscapeRate", "falseCompletionRate", "medianCycleMinutes",
    "tokenUnitsPerVerifiedUnit", "operatorFrictionRate",
)
ALL_METRICS = PRIMARY_METRICS + ("criticalRegressions",)
FORBIDDEN_KEYS = {
    "name", "email", "repositoryurl", "repositorypath", "path", "prompt",
    "sourcecode", "secret", "customerdata", "customer", "useremail",
}


def fail(what: str, why: str, fix: str, code: int = 1) -> int:
    print(f"FAILED: {what} | WHY: {why} | FIX: {fix}")
    return code


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_time(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return parsed.astimezone(dt.timezone.utc)


def canonical_record(record: dict) -> bytes:
    value = copy.deepcopy(record)
    attestation = value.get("attestation")
    if isinstance(attestation, dict):
        attestation.pop("recordDigest", None)
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def record_digest(record: dict) -> str:
    return hashlib.sha256(canonical_record(record)).hexdigest()


def forbidden_paths(value: Any, prefix: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z]", "", str(key).lower())
            child_path = f"{prefix}.{key}"
            if normalized in FORBIDDEN_KEYS:
                found.append(child_path)
            found.extend(forbidden_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(forbidden_paths(child, f"{prefix}[{index}]"))
    return found


def policy_from(contract: dict) -> dict:
    policy = dict(contract["externalEvidencePolicy"])
    policy["maxAgeDays"] = int(contract["freshness"]["maxExternalOutcomeAgeDays"])
    policy["frozenAt"] = contract["frozenAt"]
    return policy


def validate_record(record: dict, schema: dict, policy: dict,
                    now: dt.datetime) -> list[str]:
    issues: list[str] = []
    required = schema["requiredRecordFields"]
    issues.extend(f"missing {field}" for field in required if field not in record)
    if issues:
        return issues
    if not PROJECT_RE.fullmatch(str(record["projectId"])):
        issues.append("projectId is not pseudonymous")
    if not OPERATOR_RE.fullmatch(str(record["operatorId"])):
        issues.append("operatorId is not pseudonymous")
    if record.get("repositoryClass") == "methodology" or record.get("isMethodologyRepository") is True:
        issues.append("methodology repository is ineligible")
    if record.get("synthetic") is not False or record.get("fixture") is not False:
        issues.append("synthetic/fixture evidence is ineligible")
    privacy = record.get("privacy") or {}
    if privacy != {"containsPII": False, "containsSourceCode": False,
                   "containsSecrets": False, "containsCustomerData": False}:
        issues.append("privacy attestation is incomplete or non-false")
    prohibited = forbidden_paths(record)
    if prohibited:
        issues.append("prohibited fields: " + ", ".join(prohibited))
    try:
        started = parse_time(str(record["startedAt"]))
        observed = parse_time(str(record["observedAt"]))
        frozen = parse_time(str(policy["frozenAt"]))
        if observed <= started:
            issues.append("observedAt must be after startedAt")
        if (observed - started).days < int(policy["minimumObservationDays"]):
            issues.append("observation duration below frozen minimum")
        if observed <= frozen:
            issues.append("evidence does not postdate the frozen contract")
        if observed > now or (now - observed).days > int(policy["maxAgeDays"]):
            issues.append("evidence is future-dated or stale")
    except (ValueError, TypeError) as exc:
        issues.append(f"invalid timestamp: {exc}")
    if type(record.get("comparableUnits")) is not int or record["comparableUnits"] <= 0:
        issues.append("comparableUnits must be a positive integer")
    for phase in ("baseline", "followup"):
        metrics = record.get(phase)
        if not isinstance(metrics, dict):
            issues.append(f"{phase} is not an object")
            continue
        if set(metrics) != set(ALL_METRICS):
            issues.append(f"{phase} metric set is not comparable")
            continue
        if any(not isinstance(metrics[key], (int, float)) or metrics[key] < 0
               for key in ALL_METRICS):
            issues.append(f"{phase} metrics must be non-negative numbers")
    hashes = record.get("sourceHashes")
    if not isinstance(hashes, list) or not hashes:
        issues.append("sourceHashes must be a non-empty array")
    else:
        for index, item in enumerate(hashes):
            if not isinstance(item, dict) or set(item) != set(schema["provenance"]["sourceHashFields"]):
                issues.append(f"sourceHashes[{index}] fields invalid")
                continue
            if not SHA_RE.fullmatch(str(item["artifactDigest"])) or not SHA_RE.fullmatch(str(item["sha256"])):
                issues.append(f"sourceHashes[{index}] digest invalid")
            if not OPERATOR_RE.fullmatch(str(item["verifiedBy"])) or item["verifiedBy"] == record["operatorId"]:
                issues.append(f"sourceHashes[{index}] lacks independent verifier")
            try:
                parse_time(str(item["verifiedAt"]))
            except (ValueError, TypeError):
                issues.append(f"sourceHashes[{index}] verifiedAt invalid")
    attestation = record.get("attestation")
    expected_attestation = set(schema["provenance"]["attestationFields"])
    if not isinstance(attestation, dict) or set(attestation) != expected_attestation:
        issues.append("attestation fields invalid")
    else:
        if attestation.get("consent") is not True or attestation.get("accurate") is not True:
            issues.append("consent/accuracy attestation missing")
        if attestation.get("independentOperator") is not True:
            issues.append("operator is not independent")
        if attestation.get("authorAffiliated") is not False:
            issues.append("author-affiliated self-report is ineligible")
        if attestation.get("recordDigest") != record_digest(record):
            issues.append("recordDigest does not verify")
    return issues


def evaluate(index: dict, contract: dict, schema: dict,
             now: dt.datetime | None = None, independence_only: bool = False) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    policy = policy_from(contract)
    issues: list[str] = []
    if not isinstance(index, dict) or index.get("version") != 1:
        return {"passed": False, "issues": ["index version/object invalid"]}
    if index.get("evidenceKind") != "observed_external_outcome":
        issues.append("index evidenceKind is not observed_external_outcome")
    records = index.get("projects")
    if not isinstance(records, list):
        return {"passed": False, "issues": issues + ["projects is not an array"]}
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            issues.append(f"projects[{idx}] is not an object")
            continue
        issues.extend(f"projects[{idx}]: {issue}"
                      for issue in validate_record(record, schema, policy, now))
    project_ids = [row.get("projectId") for row in records if isinstance(row, dict)]
    operator_ids = [row.get("operatorId") for row in records if isinstance(row, dict)]
    if len(set(project_ids)) < int(policy["minimumIndependentProjects"]):
        issues.append("independent project threshold not met")
    if len(set(operator_ids)) < int(policy["minimumIndependentOperators"]):
        issues.append("independent operator threshold not met")
    units = sum(row.get("comparableUnits", 0) for row in records
                if isinstance(row, dict) and type(row.get("comparableUnits")) is int)
    if units < int(policy["minimumComparableUnits"]):
        issues.append("comparable unit threshold not met")
    if not independence_only and not issues:
        max_regression = float(schema["decision"]["maximumPrimaryMetricRegressionPercent"]) / 100.0
        improvements = 0
        for idx, row in enumerate(records):
            baseline = row["baseline"]
            followup = row["followup"]
            if followup["criticalRegressions"] != schema["decision"]["requiredCriticalRegressions"]:
                issues.append(f"projects[{idx}]: critical regression present")
            for metric in PRIMARY_METRICS:
                before = float(baseline[metric])
                after = float(followup[metric])
                if before > 0 and after > before * (1.0 + max_regression):
                    issues.append(f"projects[{idx}]: {metric} regressed beyond limit")
                if after < before:
                    improvements += 1
        if schema["decision"]["requiresAtLeastOneMaterialImprovement"] and improvements == 0:
            issues.append("no material primary-metric improvement")
    return {
        "passed": not issues,
        "issues": issues,
        "projects": len(set(project_ids)),
        "operators": len(set(operator_ids)),
        "comparableUnits": units,
        "evaluatedAt": now.isoformat(),
        "independenceOnly": independence_only,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate privacy-safe external outcome evidence")
    sub = parser.add_subparsers(dest="command", required=True)
    digest = sub.add_parser("digest-record")
    digest.add_argument("--record", type=Path, required=True)
    for name in ("evaluate", "independence"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--index", type=Path, required=True)
        cmd.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
        cmd.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    export = sub.add_parser("export")
    export.add_argument("--index", type=Path, required=True)
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    export.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()
    try:
        if args.command == "digest-record":
            record = load_json(args.record)
            print(record_digest(record))
            return 0
        if not args.index.is_file():
            return fail("external outcome evidence", f"index is missing: {args.index}",
                        "run opt-in pilots and write consented real records; never copy fixtures")
        index = load_json(args.index)
        contract = load_json(args.contract)
        schema = load_json(args.schema)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        return fail("external outcome input", str(exc), "repair the JSON/schema/contract and retry")
    result = evaluate(index, contract, schema, independence_only=args.command == "independence")
    if not result["passed"]:
        return fail("external outcome evaluation", "; ".join(result["issues"]),
                    "collect fresh independent provenance or correct the invalid record; do not lower the frozen thresholds")
    if args.command == "export":
        export_payload = {
            "version": 1,
            "evidenceKind": index["evidenceKind"],
            "observedAt": max(row["observedAt"] for row in index["projects"]),
            "projects": index["projects"],
            "evaluation": result,
        }
        args.out.write_text(json.dumps(export_payload, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        print(f"EXPORTED validated privacy-safe evidence: {args.out}")
    else:
        print("PASS " + json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
