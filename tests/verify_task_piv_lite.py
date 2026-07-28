#!/usr/bin/env python3
"""Structural, behavioral-boundary and mutation oracle for /task PIV-lite."""
from __future__ import annotations

import copy
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
ROUTE = ROOT / "skills" / "task" / "PIV_LITE_ROUTE.json"
TASK = ROOT / "skills" / "task" / "SKILL.md"
MATRIX = ROOT / "skills" / "task" / "references" / "routing-matrix.md"
CONTRACT = ROOT / "docs" / "HARNESS_DEMO_ABSORPTION_CONTRACT.json"


class RouteError(ValueError):
    """A fail-closed PIV-lite route error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RouteError(message)


def load(path: pathlib.Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def validate_route(route: dict) -> None:
    require(route.get("version") == 1 and route.get("id") == "itd-task-piv-lite-v1",
            "PIV-lite route identity drifted")
    require(route.get("authority") == "facade-only-no-independent-completion-authority"
            and route.get("routeOwner") == "/task"
            and route.get("appliesTo") ==
            "new-feature-in-adopted-brownfield-project",
            "PIV-lite must remain a /task-owned brownfield façade")
    require(route.get("preconditions") == [
        ".itd/SCOPE_LOCK.md", ".itd-memory/STATE.json",
    ], "PIV-lite must require adopted state before claiming WIP=1")
    require(route.get("publicLifecycleSkillDelta") == 0,
            "PIV-lite cannot add a public lifecycle skill")
    require(route.get("stateAuthority") == [".itd", ".itd-memory"],
            "PIV-lite cannot create another state plane")
    require(route.get("completionAuthority") == "verification-loop-v1",
            "PIV-lite cannot create completion authority")
    require(route.get("wipLimit") == 1, "PIV-lite must preserve WIP=1")

    stages = route.get("stages") or []
    require([row.get("id") for row in stages] ==
            ["plan", "implement", "validate", "review"],
            "PIV-lite must contain the exact four ordered stages")
    require([row.get("label") for row in stages] ==
            ["Plan", "Implement", "Validate", "Review"],
            "PIV-lite reader labels drifted")
    required_reuse = {
        "plan": {"scope-lock", "task-contract", "bounded-plan", "human-approval"},
        "implement": {"scope-bound-edits", "wip-gate", "producer-first"},
        "validate": {"/test", "machine-producer", "exact-staged-candidate"},
        "review": {"/review", "risk-tier-checker", "adjudication",
                   "receipt-recheck"},
    }
    expected_exits = {
        "plan": "approved-plan",
        "implement": "declared-change-only",
        "validate": "machine-receipt-passed",
        "review": "current-adjudication-receipt-passed",
    }
    for row in stages:
        require(set(row.get("reuses") or []) == required_reuse[row["id"]]
                and row.get("exitGate") == expected_exits[row["id"]],
                f"PIV-lite stage {row['id']} bypasses an existing gate")

    risks = route.get("riskRoutes") or {}
    require(set(risks) == {"low", "medium", "high"},
            "PIV-lite risk routes must be exactly low/medium/high")
    require(risks.get("low") == {
        "checker": "machine-only", "receiptRequired": True,
    }, "low risk must remain machine-only with a receipt")
    require(risks.get("medium") == {
        "checker": "targeted-fresh-session", "receiptRequired": True,
    }, "medium risk must require a targeted fresh checker")
    require(risks.get("high") == {
        "checker": "different-provider-full", "receiptRequired": True,
    }, "high risk must require a full independent checker")
    require(route.get("unknownRisk") == {"route": "high", "failClosed": True},
            "unknown risk must fail closed to high")

    completion = route.get("completionGate") or {}
    require(set(completion.get("requires") or []) == {
        "adjudication-receipt", "receipt-recheck", "verified-unit-transition",
    }, "PIV-lite completion must require adjudication and recheck")
    require(set(completion.get("rejects") or []) == {
        "narrated-pass", "standalone-review", "diagnostic-pass", "sentinel-file",
    }, "PIV-lite must reject non-authoritative completion claims")
    require(set(route.get("forbidden") or []) == {
        "new-lifecycle-skill", "parallel-state-ledger", "owned-runtime",
        "review-bypass", "approval-bypass", "broad-staging",
    }, "PIV-lite forbidden-boundary inventory drifted")


def validate_public_skills(contract: dict) -> None:
    definition = (contract.get("thresholds") or {}).get(
        "publicLifecycleSkills") or {}
    root = ROOT / str(definition.get("root") or "")
    prefix = str(definition.get("reservedNamePrefix") or "")
    all_names = sorted(
        item.name for item in root.iterdir()
        if item.is_dir() and (item / "SKILL.md").is_file()
    )
    public = [name for name in all_names if not name.startswith(prefix)]
    reserved = [name for name in all_names if name.startswith(prefix)]
    require(public == definition.get("baselineNames")
            and len(public) == definition.get("baseline") == 40,
            "PIV-lite changed the frozen public skill population")
    require(reserved == definition.get("reservedSkillDirectories") == ["_shared"],
            "PIV-lite changed the reserved skill population")


def mutation_count(route: dict) -> int:
    cases = []
    missing_stage = copy.deepcopy(route)
    missing_stage["stages"].pop()
    cases.append(("missing stage", missing_stage))
    alternate_state = copy.deepcopy(route)
    alternate_state["stateAuthority"] = [".piv"]
    cases.append(("alternate state", alternate_state))
    alternate_completion = copy.deepcopy(route)
    alternate_completion["completionAuthority"] = "PIV_DONE.md"
    cases.append(("alternate completion", alternate_completion))
    wip_bypass = copy.deepcopy(route)
    wip_bypass["wipLimit"] = 2
    cases.append(("WIP bypass", wip_bypass))
    approval_bypass = copy.deepcopy(route)
    approval_bypass["stages"][0]["reuses"].remove("human-approval")
    cases.append(("approval bypass", approval_bypass))
    weak_plan_exit = copy.deepcopy(route)
    weak_plan_exit["stages"][0]["exitGate"] = "plan-written"
    cases.append(("weak plan exit", weak_plan_exit))
    weak_review_exit = copy.deepcopy(route)
    weak_review_exit["stages"][3]["exitGate"] = "review-written"
    cases.append(("weak review exit", weak_review_exit))
    no_adopted_state = copy.deepcopy(route)
    no_adopted_state["preconditions"] = []
    cases.append(("missing adopted state", no_adopted_state))
    medium_bypass = copy.deepcopy(route)
    medium_bypass["riskRoutes"]["medium"]["checker"] = "machine-only"
    cases.append(("medium checker bypass", medium_bypass))
    high_bypass = copy.deepcopy(route)
    high_bypass["riskRoutes"]["high"]["checker"] = "targeted-fresh-session"
    cases.append(("high checker bypass", high_bypass))
    missing_receipt = copy.deepcopy(route)
    missing_receipt["riskRoutes"]["low"]["receiptRequired"] = False
    cases.append(("receipt bypass", missing_receipt))
    unknown_fail_open = copy.deepcopy(route)
    unknown_fail_open["unknownRisk"] = {"route": "medium", "failClosed": False}
    cases.append(("unknown risk fail-open", unknown_fail_open))
    skill_growth = copy.deepcopy(route)
    skill_growth["publicLifecycleSkillDelta"] = 1
    cases.append(("public skill growth", skill_growth))
    narrated_completion = copy.deepcopy(route)
    narrated_completion["completionGate"]["requires"] = ["narrated-pass"]
    cases.append(("narrated completion", narrated_completion))
    broad_stage = copy.deepcopy(route)
    broad_stage["forbidden"].remove("broad-staging")
    cases.append(("broad stage", broad_stage))

    for label, candidate in cases:
        try:
            validate_route(candidate)
        except RouteError:
            continue
        raise RouteError(f"mutation {label!r} passed")
    return len(cases)


def main() -> int:
    require(ROUTE.is_file(), "PIV-lite route is missing")
    route = load(ROUTE)
    contract = load(CONTRACT)
    validate_route(route)
    validate_public_skills(contract)

    task = TASK.read_text(encoding="utf-8")
    matrix = MATRIX.read_text(encoding="utf-8")
    require("PIV-lite façade" in task
            and "Plan → Implement → Validate →" in task
            and "Review" in task,
            "/task does not expose the PIV-lite reader journey")
    require("PIV_LITE_ROUTE.json" in task
            and "Only the existing Verification Loop may complete the unit" in task,
            "/task does not preserve route/completion authority")
    require(task.count("including a one-file PIV-lite") >= 2
            and "explicit user approval before code" in task
            and "before PIV-lite completion or commit" in task,
            "/task permits one-file approval or review bypass")
    require("PIV-lite requires an adopted brownfield project" in task
            and "must not label the run PIV-lite" in task,
            "/task overclaims WIP=1 for non-adopted projects")
    require("PIV-lite через `/task` Step 3f" in matrix
            and "не новый lifecycle skill" in matrix,
            "routing matrix does not expose the existing PIV-lite route")
    require(not (ROOT / "skills" / "piv-lite").exists(),
            "PIV-lite added a public skill directory")

    mutations = mutation_count(route)
    print(json.dumps({
        "mutationCases": mutations,
        "publicLifecycleSkills": 40,
        "stages": ["plan", "implement", "validate", "review"],
        "status": "PASSED",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, RouteError) as exc:
        print(f"FAILED: PIV-lite route | WHY: {exc} | "
              "FIX: restore the existing /task gates and exact route contract")
        raise SystemExit(2)
