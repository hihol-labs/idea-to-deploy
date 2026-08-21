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

# A ledger-close candidate records that an already-delivered unit is finished.
# It moves the ledger state file and, at most, closes the acceptance contract's
# active followup. Anything else is ordinary work and is judged as before.
LEDGER_STATE_PATH = ".itd-memory/STATE.json"
CLOSING_FOLLOWUP_FIELDS = frozenset({"status", "closedAt"})
CANDIDATE_FACT_FIELDS = frozenset({
    "changedPaths", "modifiedPaths", "contractPath", "contractBefore",
    "stateBefore",
})


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


CLOSED_FOLLOWUP_STATUSES = frozenset({"verified", "closed", "done", "superseded"})


def followup_is_closed(followup: dict[str, Any]) -> bool:
    """A finished followup stops being authoritative over later candidates.

    The matrix exists to keep the ACTIVE unit's claim honest. Left pinned after
    the unit is verified it starts gating unrelated work: on 2026-08-15 the
    closed S8 followup still demanded a live-benchmark replay whose dirty-state
    pin cannot hold while any other file is staged, so no later commit could be
    routed at all. Closing releases the matrix back to the pre-declaration
    baseline - it never relaxes an OPEN followup, whose every criterion is
    still required.
    """
    status = followup.get("status")
    if isinstance(status, str) and status.strip().lower() in CLOSED_FOLLOWUP_STATUSES:
        return True
    closed_at = followup.get("closedAt")
    return isinstance(closed_at, str) and bool(closed_at.strip())


def evidence_first_policy(acceptance: dict[str, Any]) -> dict[str, Any] | None:
    followup = acceptance.get("activeFollowup")
    if not isinstance(followup, dict) or "reviewPolicy" not in followup:
        return None
    if followup_is_closed(followup):
        return None
    return _validated_policy(followup)


def _validated_policy(followup: dict[str, Any]) -> dict[str, Any]:
    """Validate a declared review policy regardless of the followup's state."""
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


def _closes_only_the_followup(
    before: dict[str, Any], after: dict[str, Any],
) -> bool:
    """True when the contract differs only by closing its active followup."""
    if set(before) != set(after):
        return False
    if any(before[key] != after[key] for key in before if key != "activeFollowup"):
        return False
    before_followup = before.get("activeFollowup")
    after_followup = after.get("activeFollowup")
    if not isinstance(before_followup, dict) or not isinstance(after_followup, dict):
        return False
    if followup_is_closed(before_followup):
        return False
    carried = set(before_followup) - CLOSING_FOLLOWUP_FIELDS
    if carried != set(after_followup) - CLOSING_FOLLOWUP_FIELDS:
        return False
    # A closing field necessarily differs: closedness is read from exactly
    # these two fields, and the caller has already established that the
    # candidate's followup is closed while this one is not.
    return not any(before_followup[key] != after_followup[key] for key in carried)


def ledger_close_policy(
    acceptance: dict[str, Any], candidate: dict[str, Any],
) -> dict[str, Any] | None:
    """Return the closed unit's policy when the candidate is a pure close.

    The circle this resolves was measured on S10: a closed followup released
    the matrix, so the reviewer saw no coverage at all and blocked for its
    absence; leaving the followup open at the same diff made STATE and the
    contract disagree, and the reviewer blocked for that. No bookkeeping
    commit could be routed in either position.

    Recognising the class never relaxes the requirement - it names where the
    coverage lives. The closed unit's own criteria must still all be passed,
    their oracles must still be exact passes on the reviewed tree, and the
    reviewer floor is clamped to at least one, so the route keeps every
    independent reviewer it has today.
    """
    facts = _closed_dict(candidate, set(CANDIDATE_FACT_FIELDS), "candidate facts")
    followup = acceptance.get("activeFollowup")
    if not isinstance(followup, dict) or "reviewPolicy" not in followup:
        return None
    if not followup_is_closed(followup):
        return None
    contract_path = facts["contractPath"]
    if not isinstance(contract_path, str) or not contract_path.strip():
        raise ReviewEvidenceError("candidate contract path is absent")
    changed = set(_string_list(facts["changedPaths"], "candidate changed paths"))
    modified = facts["modifiedPaths"]
    if not isinstance(modified, list) or any(
        not isinstance(item, str) for item in modified
    ):
        raise ReviewEvidenceError("candidate modified paths are malformed")
    # The contract transition is not optional evidence, it IS the close. Without
    # it the only remaining signal is "the merged contract's followup happens to
    # be closed" - true of every commit between one unit's close and the next
    # unit's open, so any later STATE-only edit would inherit a stale unit's
    # coverage and be announced to the reviewer as a closing commit. Requiring
    # the contract in the diff is what makes the class mean "THIS diff closed it".
    #
    # LPD002-A5: a plan-driven unit's close also updates its plan ledger (the
    # LPD-002 close measured this - the plan file was a third path and expelled
    # the candidate from the class). Extra ledger files are allowed ONLY when
    # ALL of the following hold, each fail-closed:
    #   - the file is declared in ledgerFiles of the BASE STATE.json (the
    #     declaration must PRECEDE the close - a candidate cannot smuggle a
    #     path by declaring it in its own diff);
    #   - the path lives under .itd-memory/ (ledger namespace, never code);
    #   - the row is a modification, like the two mandatory files.
    required = {LEDGER_STATE_PATH, contract_path}
    if not required <= changed:
        return None
    extra = changed - required
    if extra:
        state_before = facts.get("stateBefore")
        if not isinstance(state_before, dict):
            return None
        declared = state_before.get("ledgerFiles")
        if not isinstance(declared, list) or any(
            not isinstance(item, str) for item in declared
        ):
            return None
        declared_set = set(declared)
        for path in extra:
            if path not in declared_set:
                return None
            if not path.startswith(".itd-memory/") or ".." in path.split("/"):
                return None
    # Both files must be MODIFIED, never added, deleted or type-changed. A close
    # edits a ledger that already exists; a candidate that creates or destroys
    # it is doing something else entirely and must not be announced to the
    # reviewer as routine bookkeeping whose missing coverage is expected.
    if set(modified) != changed:
        return None
    before = facts["contractBefore"]
    if not isinstance(before, dict):
        return None
    if not _closes_only_the_followup(before, acceptance):
        return None
    policy = _validated_policy(followup)
    policy["minimumIndependentReviewers"] = max(
        policy["minimumIndependentReviewers"], 1
    )
    return policy


def coverage_matrix(
    acceptance: dict[str, Any], machine: dict[str, Any],
    *, candidate: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return a closed matrix or fail before any model can claim PASSED."""
    if not isinstance(acceptance, dict) or not isinstance(machine, dict):
        raise ReviewEvidenceError("acceptance or machine evidence is malformed")
    policy = evidence_first_policy(acceptance)
    coverage_source = "active-unit"
    if policy is None and candidate is not None:
        policy = ledger_close_policy(acceptance, candidate)
        if policy is not None:
            coverage_source = "closed-unit-inherited"
    if policy is None:
        return None
    followup = acceptance.get("activeFollowup")
    assert isinstance(followup, dict)
    unit_id = followup.get("unitId")
    if not isinstance(unit_id, str) or not unit_id or machine.get("unitId") != unit_id:
        raise ReviewEvidenceError("active unit and machine evidence differ")
    if machine.get("riskTier") != policy["riskTier"]:
        raise ReviewEvidenceError("machine and review risk tiers differ")
    machine_candidate = machine.get("candidate")
    tree = (
        machine_candidate.get("reviewedTree")
        if isinstance(machine_candidate, dict) else None
    )
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
    # LPD002-A1: ownership is explicit when declared. A bare prefix match once
    # captured a FOREIGN historical criterion (unit "R1" swallowed "R1-SCRUB-1").
    # If ANY criterion carries an explicit unitId for this unit, the explicit
    # set is authoritative and prefix matching is not consulted; the prefix
    # fallback remains only for contracts predating the field.
    explicit = [
        item for item in criteria
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and item.get("unitId") == unit_id
    ]
    active = explicit or [
        item for item in criteria
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and item["id"].startswith(unit_id + "-")
        and "unitId" not in item
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
        "coverageSource": coverage_source,
        "riskTier": policy["riskTier"],
        "minimumIndependentReviewers": policy["minimumIndependentReviewers"],
        "explorer": policy["explorer"],
        "adjudicator": policy["adjudicator"],
        "requiredImpactClasses": list(policy["requiredImpactClasses"]),
        "criteria": rows,
    }
