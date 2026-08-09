#!/usr/bin/env python3
"""Closed evidence-first coverage policy for independent review packets."""

from __future__ import annotations

from typing import Any


IMPACT_CLASSES = frozenset({
    "bounded-output",
    "compatibility",
    "correctness",
    "error-handling",
    "generated-artifact-freshness",
    "host-parity",
    "numerical-stability",
    "performance",
    "reconciliation",
    "repository-hygiene",
    "scale",
    "security",
})
RISK_TIERS = frozenset({"low", "medium", "high", "unknown"})


class ReviewEvidenceError(ValueError):
    """The declared acceptance evidence cannot support an independent PASS."""


def _closed_dict(value: object, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ReviewEvidenceError(f"{label} is not a closed object")
    return value


def _string_list(value: object, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item or item != item.strip()
               for item in value)
        or len(set(value)) != len(value)
    ):
        raise ReviewEvidenceError(f"{label} must be a unique non-empty string list")
    return list(value)


def evidence_first_policy(acceptance: dict[str, Any]) -> dict[str, Any] | None:
    followup = acceptance.get("activeFollowup")
    if not isinstance(followup, dict) or "reviewPolicy" not in followup:
        return None
    policy = _closed_dict(followup["reviewPolicy"], {
        "mode", "riskTier", "requiredImpactClasses",
        "minimumIndependentReviewers", "explorer", "adjudicator",
    }, "active review policy")
    if (
        policy["mode"] != "evidence-first"
        or policy["riskTier"] not in RISK_TIERS
        or policy["explorer"] != "isolated-machine-oracle"
        or policy["adjudicator"] != "sealed-host-union"
        or type(policy["minimumIndependentReviewers"]) is not int
        or not 0 <= policy["minimumIndependentReviewers"] <= 3
    ):
        raise ReviewEvidenceError("active review policy values are invalid")
    impacts = _string_list(
        policy["requiredImpactClasses"], "required impact classes"
    )
    if any(value not in IMPACT_CLASSES for value in impacts):
        raise ReviewEvidenceError("required impact class is unknown")
    minimum = policy["minimumIndependentReviewers"]
    expected_minimum = 0 if policy["riskTier"] == "low" else 1
    if minimum != expected_minimum:
        raise ReviewEvidenceError(
            "low review requires zero independent reviewers; "
            "medium/high/unknown review requires exactly one"
        )
    return dict(policy)


def coverage_matrix(
    acceptance: dict[str, Any], machine: dict[str, Any],
) -> dict[str, Any] | None:
    """Return a closed matrix or fail before any model can claim PASSED."""
    if not isinstance(acceptance, dict) or not isinstance(machine, dict):
        raise ReviewEvidenceError("acceptance or machine evidence is malformed")
    policy = evidence_first_policy(acceptance)
    if policy is None:
        return None
    followup = acceptance.get("activeFollowup")
    assert isinstance(followup, dict)
    unit_id = followup.get("unitId")
    if not isinstance(unit_id, str) or not unit_id or machine.get("unitId") != unit_id:
        raise ReviewEvidenceError("active unit and machine evidence differ")
    if machine.get("riskTier") != policy["riskTier"]:
        raise ReviewEvidenceError("machine and review risk tiers differ")
    candidate = machine.get("candidate")
    tree = candidate.get("reviewedTree") if isinstance(candidate, dict) else None
    if not isinstance(tree, str) or not tree:
        raise ReviewEvidenceError("machine reviewed tree is absent")
    runs = machine.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ReviewEvidenceError("machine evidence has no oracle runs")
    run_index: dict[str, dict[str, Any]] = {}
    for run in runs:
        if not isinstance(run, dict) or not isinstance(run.get("id"), str):
            raise ReviewEvidenceError("machine oracle run is malformed")
        run_id = run["id"]
        if not run_id or run_id in run_index:
            raise ReviewEvidenceError("machine oracle run identity is invalid")
        run_index[run_id] = run

    criteria = acceptance.get("criteria")
    if not isinstance(criteria, list):
        raise ReviewEvidenceError("acceptance criteria are malformed")
    active = [
        item for item in criteria
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and item["id"].startswith(unit_id + "-")
    ]
    if not active:
        raise ReviewEvidenceError("active unit has no acceptance criteria")
    rows: list[dict[str, Any]] = []
    observed_impacts: set[str] = set()
    criterion_ids: set[str] = set()
    for criterion in active:
        criterion_id = criterion["id"]
        if criterion_id in criterion_ids:
            raise ReviewEvidenceError("active acceptance criterion ID is duplicated")
        criterion_ids.add(criterion_id)
        if criterion.get("status") != "passed":
            raise ReviewEvidenceError(f"{criterion_id} is not passed")
        spec = _closed_dict(criterion.get("reviewEvidence"), {
            "claim", "impactClasses", "oracleIds",
        }, f"{criterion_id} review evidence")
        if (
            not isinstance(spec["claim"], str)
            or not spec["claim"].strip()
            or spec["claim"] != spec["claim"].strip()
        ):
            raise ReviewEvidenceError(f"{criterion_id} evidence claim is absent")
        impacts = _string_list(
            spec["impactClasses"], f"{criterion_id} impact classes"
        )
        if any(value not in IMPACT_CLASSES for value in impacts):
            raise ReviewEvidenceError(f"{criterion_id} impact class is unknown")
        oracle_ids = _string_list(spec["oracleIds"], f"{criterion_id} oracle IDs")
        for oracle_id in oracle_ids:
            run = run_index.get(oracle_id)
            if run is None:
                raise ReviewEvidenceError(
                    f"{criterion_id} oracle {oracle_id} is missing"
                )
            if run.get("exitCode") != 0 or run.get("executedTree") != tree:
                raise ReviewEvidenceError(
                    f"{criterion_id} oracle {oracle_id} is not an exact PASS"
                )
        observed_impacts.update(impacts)
        rows.append({
            "criterionId": criterion_id,
            "claim": spec["claim"],
            "impactClasses": impacts,
            "oracleIds": oracle_ids,
        })
    missing = sorted(set(policy["requiredImpactClasses"]) - observed_impacts)
    if missing:
        raise ReviewEvidenceError(
            "required impact evidence is missing: " + ", ".join(missing)
        )
    return {
        "version": 1,
        "kind": "itd-independent-review-evidence-coverage",
        "mode": policy["mode"],
        "unitId": unit_id,
        "riskTier": policy["riskTier"],
        "minimumIndependentReviewers": policy["minimumIndependentReviewers"],
        "explorer": policy["explorer"],
        "adjudicator": policy["adjudicator"],
        "requiredImpactClasses": list(policy["requiredImpactClasses"]),
        "criteria": rows,
    }
