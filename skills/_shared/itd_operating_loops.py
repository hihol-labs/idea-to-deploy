#!/usr/bin/env python3
"""Fail-closed validator for ITD operating-loop contracts and run records.

This module deliberately does not schedule work or execute actions. Hosts own
transport and approval; ITD only validates the durable contract and evidence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable


HERE = Path(__file__).resolve().parent
POLICY_PATH = HERE / "OPERATING_LOOP_POLICY.json"
RECIPES_PATH = HERE / "OPERATING_LOOP_RECIPES.json"
SUPPORTED_HOSTS = {"claude-code", "codex", "github-actions"}
SCHEDULED_MODES = {"observe", "report"}
OUTCOMES = {"no-op", "report", "draft", "approved-action", "escalated", "paused", "failed"}
FAILURES = {
    "runaway", "state_rot", "verifier_theater", "flake", "overreach",
    "notification_fatigue", "comprehension_debt", "parallel_collision",
    "escalation_failure",
}
FAILURE_SIGNAL_MAP = {
    "budgetExceeded": "runaway",
    "attemptBudgetExceeded": "runaway",
    "stateStale": "state_rot",
    "receiptMissing": "verifier_theater",
    "receiptInvalid": "verifier_theater",
    "nondeterministicCheck": "flake",
    "scopeDrift": "overreach",
    "unapprovedAction": "overreach",
    "tooManyNoopNotifications": "notification_fatigue",
    "unboundedContext": "comprehension_debt",
    "lockContended": "parallel_collision",
    "concurrentMutation": "parallel_collision",
    "requiredEscalationUnsent": "escalation_failure",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RECIPE_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
JOB_RE = RECIPE_RE
ADJUDICATION_FIELDS = {
    "version", "kind", "createdAt", "unitId", "riskTier", "candidate", "candidateDigest",
    "policySha256", "producer", "producerRunId", "assurance", "attempt", "attemptLedger",
    "checkerMode", "dependencies", "outcome", "receiptSha256",
}


class OperatingLoopError(ValueError):
    def __init__(self, why: str, fix: str) -> None:
        super().__init__(why)
        self.why = why
        self.fix = fix


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise OperatingLoopError(f"{label} is unreadable: {path}: {exc}",
                                 f"Repair {path} and retry.") from exc
    if not isinstance(value, dict):
        raise OperatingLoopError(f"{label} must be a JSON object", "Use the documented object shape.")
    return value


def parse_time(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise OperatingLoopError(f"{label} is not a timestamp", "Use an RFC 3339 timestamp with timezone.")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OperatingLoopError(f"{label} is invalid", "Use an RFC 3339 timestamp with timezone.") from exc
    if parsed.tzinfo is None:
        raise OperatingLoopError(f"{label} has no timezone", "Include Z or an explicit UTC offset.")
    return parsed.astimezone(dt.timezone.utc)


def validate_authorization(value: Any) -> tuple[dt.datetime, dt.datetime]:
    required = {"leaseId", "recipeId", "capability", "action", "issuedAt", "expiresAt", "hostApproval"}
    if not isinstance(value, dict) or set(value) != required:
        raise OperatingLoopError("trust lease is malformed", "Use exactly the authorization fields in the contract schema.")
    for field, limit in (("leaseId", 160), ("capability", 160)):
        if not isinstance(value[field], str) or not value[field] or len(value[field]) > limit:
            raise OperatingLoopError(f"trust lease {field} is empty", "Bind every lease field explicitly.")
    if not isinstance(value["recipeId"], str) or not RECIPE_RE.fullmatch(value["recipeId"]):
        raise OperatingLoopError("trust lease recipeId is invalid", "Use a registered lowercase recipe id.")
    action = value["action"]
    if not isinstance(action, dict) or set(action) != {"tool", "targetsSha256", "payloadSha256"}:
        raise OperatingLoopError("trust lease action is malformed", "Bind tool, exact targets hash, and payload hash.")
    if not isinstance(action["tool"], str) or not action["tool"] or len(action["tool"]) > 160:
        raise OperatingLoopError("trust lease tool is empty", "Name the approved host tool.")
    for field in ("targetsSha256", "payloadSha256"):
        if not isinstance(action[field], str) or not SHA256_RE.fullmatch(action[field]):
            raise OperatingLoopError(f"trust lease action.{field} is invalid", "Use a lowercase SHA-256 digest.")
    approval = value["hostApproval"]
    if not isinstance(approval, dict) or set(approval) != {"host", "sessionId", "approvalHash"}:
        raise OperatingLoopError("host approval is malformed", "Bind the approving session and approval hash.")
    if approval["host"] not in SUPPORTED_HOSTS:
        raise OperatingLoopError("host approval names an unsupported host", "Use a supported host adapter.")
    if (not isinstance(approval["sessionId"], str) or not approval["sessionId"]
            or len(approval["sessionId"]) > 200):
        raise OperatingLoopError("host approval session is empty", "Record the approving host session.")
    if not isinstance(approval["approvalHash"], str) or not SHA256_RE.fullmatch(approval["approvalHash"]):
        raise OperatingLoopError("host approval hash is invalid", "Use a lowercase SHA-256 digest.")
    issued, expires = parse_time(value["issuedAt"], "issuedAt"), parse_time(value["expiresAt"], "expiresAt")
    if issued >= expires:
        raise OperatingLoopError("trust lease does not have a positive lifetime", "Set expiresAt after issuedAt.")
    return issued, expires


def read_registry() -> dict[str, Any]:
    policy = read_object(POLICY_PATH, "operating-loop policy")
    registry = read_object(RECIPES_PATH, "operating-loop recipe registry")
    if (set(registry) != {"version", "policyId", "patterns", "recipes"}
            or registry.get("version") != 1 or registry.get("policyId") != policy.get("id")):
        raise OperatingLoopError("recipe registry is not bound to the active policy", "Restore version and policyId.")
    patterns = registry.get("patterns")
    if not isinstance(patterns, list):
        raise OperatingLoopError("pattern registry is malformed", "Use the installed closed pattern definitions.")
    terms: set[str] = set()
    for item in patterns:
        if (not isinstance(item, dict) or set(item) != {"job", "skill", "aliases"}
                or not isinstance(item["job"], str) or not JOB_RE.fullmatch(item["job"])
                or not isinstance(item["skill"], str) or not RECIPE_RE.fullmatch(item["skill"])
                or not isinstance(item["aliases"], list)
                or any(not isinstance(alias, str) or not JOB_RE.fullmatch(alias) for alias in item["aliases"])
                or len(item["aliases"]) != len(set(item["aliases"]))):
            raise OperatingLoopError("pattern registry is malformed", "Use job, existing skill, and unique aliases.")
        current = {item["job"], *item["aliases"]}
        if terms & current:
            raise OperatingLoopError("pattern registry contains ambiguous jobs", "Keep every job and alias unique.")
        skill_file = HERE.parent / item["skill"] / "SKILL.md"
        if not skill_file.is_file():
            raise OperatingLoopError(f"pattern targets missing skill: {item['skill']}",
                                     "Route only to an existing skills/<name>/SKILL.md.")
        terms.update(current)
    recipes = registry.get("recipes")
    recipe_fields = {"id", "title", "job", "skill", "transport", "scheduledMode", "initialStage",
                     "onDemandMaxWithoutLease", "approvedExecution", "irreversibleActions",
                     "autoMerge", "wip", "output"}
    pattern_jobs = {item["job"] for item in patterns}
    if not isinstance(recipes, list):
        raise OperatingLoopError("recipe registry is malformed", "Use closed declarative recipe objects.")
    for item in recipes:
        if (not isinstance(item, dict) or set(item) != recipe_fields
                or not isinstance(item["id"], str) or not RECIPE_RE.fullmatch(item["id"])
                or not isinstance(item["title"], str) or not item["title"] or len(item["title"]) > 160
                or item["job"] not in pattern_jobs
                or not isinstance(item["skill"], str) or not RECIPE_RE.fullmatch(item["skill"])
                or not (HERE.parent / item["skill"] / "SKILL.md").is_file()
                or item["transport"] != "host-native" or item["scheduledMode"] != "report"
                or item["initialStage"] not in {"report", "draft"}
                or item["onDemandMaxWithoutLease"] != "draft"
                or item["approvedExecution"] != "temporary-exact-lease"
                or item["irreversibleActions"] != "human-gate" or item["autoMerge"] is not False
                or type(item["wip"]) is not int or item["wip"] != 1
                or not isinstance(item["output"], str) or not RECIPE_RE.fullmatch(item["output"])):
            raise OperatingLoopError("recipe registry grants unsafe or invalid authority",
                                     "Use an existing skill, host-native report scheduling, WIP=1, and temporary exact leases.")
    ids = [item["id"] for item in recipes]
    if len(ids) != len(set(ids)):
        raise OperatingLoopError("recipe registry contains duplicate ids", "Keep one definition per recipe.")
    return registry


def load_registry() -> set[str]:
    return {item["id"] for item in read_registry()["recipes"]}


def pick_pattern(job: str) -> dict[str, Any]:
    if not isinstance(job, str) or not JOB_RE.fullmatch(job):
        raise OperatingLoopError("job is invalid", "Use one exact supported lowercase job or alias.")
    registry = read_registry()
    matches = [item for item in registry["patterns"] if job == item["job"] or job in item["aliases"]]
    if len(matches) != 1:
        supported = ", ".join(item["job"] for item in registry["patterns"])
        raise OperatingLoopError(f"unsupported job: {job}", f"Choose one supported job: {supported}.")
    match = matches[0]
    return {"status": "ready", "job": match["job"], "skill": match["skill"],
            "skillPath": f"skills/{match['skill']}/SKILL.md"}


def _artifact(root: Path, relative: str) -> Path:
    return root / Path(relative)


def _usable_acceptance(value: dict[str, Any]) -> bool:
    criteria = value.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        return False
    schema = value.get("criteriaSchema")
    required = {"id", "status"}
    allowed = {"pending", "passed", "failed", "blocked", "recovery_required"}
    if schema is not None:
        if (not isinstance(schema, dict) or not isinstance(schema.get("requiredFields"), list)
                or not isinstance(schema.get("allowedStatus"), list)
                or any(not isinstance(item, str) for item in schema["requiredFields"])
                or any(not isinstance(item, str) for item in schema["allowedStatus"])):
            return False
        required = set(schema["requiredFields"])
        allowed = set(schema["allowedStatus"])
        if not {"id", "status"} <= required or not allowed:
            return False
    return all(isinstance(item, dict) and required <= set(item)
               and isinstance(item.get("id"), str) and bool(item["id"])
               and isinstance(item.get("status"), str) and item["status"] in allowed
               for item in criteria)


def _usable_state(value: dict[str, Any]) -> bool:
    required = {"sessionState", "currentStage", "intent", "currentUnit"}
    unit = value.get("currentUnit")
    return (required <= set(value) and isinstance(value["sessionState"], str)
            and bool(value["sessionState"]) and isinstance(value["currentStage"], str)
            and bool(value["currentStage"]) and isinstance(value["intent"], str)
            and bool(value["intent"]) and isinstance(unit, dict)
            and isinstance(unit.get("id"), str) and bool(unit["id"])
            and isinstance(unit.get("status"), str) and bool(unit["status"]))


def diagnose_readiness(root: Path, host: str) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise OperatingLoopError(f"project root is not a directory: {root}",
                                 "Pass an existing project directory with --root.")
    if host not in SUPPORTED_HOSTS:
        raise OperatingLoopError(f"unsupported host: {host}",
                                 "Use claude-code, codex, or github-actions.")

    dimensions: list[dict[str, str]] = []

    def add(name: str, status: str, why: str, fix: str, evidence: str) -> None:
        dimensions.append({"name": name, "status": status, "why": why, "fix": fix,
                           "evidence": evidence})

    guidance = _artifact(root, "AGENTS.md")
    legacy_guidance = _artifact(root, "CLAUDE.md")
    if guidance.is_file() and guidance.stat().st_size > 0:
        add("project_guidance", "ready", "AGENTS.md is present and nonempty", "none", "AGENTS.md")
    elif legacy_guidance.is_file() and legacy_guidance.stat().st_size > 0:
        add("project_guidance", "degraded", "only vendor-specific CLAUDE.md guidance is present",
            "Add model-neutral AGENTS.md guidance.", "CLAUDE.md")
    else:
        add("project_guidance", "missing", "project guidance is absent",
            "Add a nonempty AGENTS.md.", "AGENTS.md")

    contract_dir = _artifact(root, ".itd")
    scope = contract_dir / "SCOPE_LOCK.md"
    acceptance = contract_dir / "ACCEPTANCE_CONTRACT.json"
    acceptance_usable = False
    if scope.is_file() and scope.stat().st_size > 0 and acceptance.is_file():
        try:
            acceptance_value = read_object(acceptance, "acceptance contract")
            if not _usable_acceptance(acceptance_value):
                raise OperatingLoopError("acceptance contract has no usable criteria",
                                         "Restore nonempty typed acceptance criteria.")
        except OperatingLoopError:
            add("methodology_contracts", "degraded", "acceptance contract is malformed",
                "Repair .itd/ACCEPTANCE_CONTRACT.json.", ".itd/ACCEPTANCE_CONTRACT.json")
        else:
            acceptance_usable = True
            add("methodology_contracts", "ready", "scope and acceptance contracts are present",
                "none", ".itd/SCOPE_LOCK.md,.itd/ACCEPTANCE_CONTRACT.json")
    elif contract_dir.exists():
        add("methodology_contracts", "degraded", "the .itd contract set is incomplete",
            "Restore SCOPE_LOCK.md and a valid ACCEPTANCE_CONTRACT.json.", ".itd")
    else:
        add("methodology_contracts", "missing", "the project is not adopted into ITD",
            "Run the bounded ITD adopt workflow.", ".itd")

    state_dir = _artifact(root, ".itd-memory")
    state = state_dir / "STATE.json"
    if state.is_file():
        try:
            state_value = read_object(state, "durable state")
            if not _usable_state(state_value):
                raise OperatingLoopError("STATE.json lacks required durable fields",
                                         "Restore sessionState, currentStage, intent, and currentUnit.")
        except OperatingLoopError:
            add("durable_state", "degraded", "STATE.json is malformed",
                "Repair .itd-memory/STATE.json from evidence.", ".itd-memory/STATE.json")
        else:
            add("durable_state", "ready", "canonical durable state is readable", "none",
                ".itd-memory/STATE.json")
    elif state_dir.exists():
        add("durable_state", "degraded", ".itd-memory exists without canonical STATE.json",
            "Create STATE.json through the ITD adoption/state workflow.", ".itd-memory")
    else:
        add("durable_state", "missing", "durable project state is absent",
            "Run ITD adoption to initialize .itd-memory/STATE.json.", ".itd-memory/STATE.json")

    check_markers = ["tests", "package.json", "pyproject.toml", "Cargo.toml", "go.mod", "Makefile"]
    present_checks = []
    for item in check_markers:
        candidate = _artifact(root, item)
        if candidate.is_file() and candidate.stat().st_size > 0:
            present_checks.append(item)
        elif candidate.is_dir() and any(path.is_file() and path.stat().st_size > 0
                                        for path in candidate.rglob("*")):
            present_checks.append(item)
    if present_checks:
        add("project_checks", "ready", "project check entry points are discoverable", "none",
            ",".join(present_checks))
    else:
        add("project_checks", "missing", "no supported project check entry point was found",
            "Add tests or a supported build/test manifest.", ",".join(check_markers))

    verifier = HERE / "itd_verification_loop.py"
    if acceptance_usable and verifier.is_file():
        add("verification_loop", "ready", "acceptance contract and installed verifier are available",
            "none", ".itd/ACCEPTANCE_CONTRACT.json")
    elif acceptance_usable:
        add("verification_loop", "degraded", "project contract exists but verifier is unavailable",
            "Repair the active ITD installation.", "skills/_shared/itd_verification_loop.py")
    elif acceptance.is_file():
        add("verification_loop", "degraded", "project acceptance contract is unusable",
            "Repair typed acceptance criteria before relying on verification.",
            ".itd/ACCEPTANCE_CONTRACT.json")
    else:
        add("verification_loop", "missing", "no project acceptance contract is available",
            "Run ITD adoption and freeze acceptance evidence.", ".itd/ACCEPTANCE_CONTRACT.json")

    host_evidence = {
        "codex": ["AGENTS.md"],
        "claude-code": ["CLAUDE.md", ".claude-plugin/plugin.json", "AGENTS.md"],
        "github-actions": [".github/workflows"],
    }[host]
    found_host = next((item for item in host_evidence if _artifact(root, item).exists()), None)
    if found_host:
        add("supported_host_adapter", "ready", f"{host} project adapter surface is present",
            "none", found_host)
    else:
        add("supported_host_adapter", "missing", f"{host} project adapter surface is absent",
            f"Install or configure the {host} adapter.", ",".join(host_evidence))

    statuses = {item["status"] for item in dimensions}
    overall = "missing" if "missing" in statuses else "degraded" if "degraded" in statuses else "ready"
    return {"version": 1, "status": overall, "host": host, "root": str(root),
            "dimensions": dimensions}


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    required = {"$schema", "version", "policyId", "enabled", "project", "recipes", "schedulerBindings",
                "trustLeases", "budgets", "telemetry", "humanInbox", "notes"}
    if (set(contract) != required or type(contract.get("version")) is not int or contract["version"] != 1
            or contract.get("policyId") != "operating-loop-v1"
            or contract.get("$schema") != "./OPERATING_LOOP_CONTRACT.schema.json"):
        raise OperatingLoopError("operating-loop contract is malformed", "Start from the installed contract template.")
    if type(contract["enabled"]) is not bool:
        raise OperatingLoopError("contract enabled flag is not boolean",
                                 "Use true for explicit opt-in or false with no authority.")
    if not isinstance(contract["project"], str) or not contract["project"] or len(contract["project"]) > 200:
        raise OperatingLoopError("contract project is invalid", "Record a nonempty bounded project name.")
    if not isinstance(contract["notes"], str) or len(contract["notes"]) > 2000:
        raise OperatingLoopError("contract notes are invalid", "Use bounded text.")
    recipe_ids = load_registry()
    selected = contract.get("recipes")
    if (not isinstance(selected, list) or any(not isinstance(item, str) or not RECIPE_RE.fullmatch(item)
                                               for item in selected)
            or len(selected) != len(set(selected)) or not set(selected) <= recipe_ids):
        raise OperatingLoopError("contract selects unknown or duplicate recipes", "Choose unique ids from the recipe registry.")
    bindings = contract.get("schedulerBindings")
    if not isinstance(bindings, list):
        raise OperatingLoopError("schedulerBindings must be an array", "Declare host-native report-only bindings.")
    bound: set[str] = set()
    binding_ids: set[str] = set()
    for item in bindings:
        if not isinstance(item, dict) or set(item) != {"recipeId", "host", "binding", "mode"}:
            raise OperatingLoopError("scheduler binding is malformed", "Use recipeId, host, binding, and mode.")
        if item["recipeId"] not in selected or item["recipeId"] in bound:
            raise OperatingLoopError("scheduler binding is unknown or duplicated", "Bind each selected recipe at most once.")
        if item["host"] not in SUPPORTED_HOSTS or item["mode"] not in SCHEDULED_MODES:
            raise OperatingLoopError("scheduler binding can exceed report-only host transport",
                                     "Use a supported host with observe or report mode.")
        if not isinstance(item["binding"], str) or not item["binding"] or len(item["binding"]) > 500 \
                or item["binding"] in binding_ids:
            raise OperatingLoopError("scheduler binding identifier is empty", "Record the host-native binding id.")
        bound.add(item["recipeId"])
        binding_ids.add(item["binding"])
    leases = contract.get("trustLeases")
    if not isinstance(leases, list) or len(leases) > 1:
        raise OperatingLoopError("trust leases violate WIP=1", "Keep at most one exact, expiring lease.")
    for lease in leases:
        validate_authorization(lease)
        if lease["recipeId"] not in selected:
            raise OperatingLoopError("trust lease references an unselected recipe", "Select the recipe before granting a lease.")
    if not contract.get("enabled") and (selected or bindings or leases):
        raise OperatingLoopError("disabled contract grants operating-loop authority",
                                 "Keep recipes, bindings, and leases empty until explicit opt-in.")
    budgets = contract["budgets"]
    budget_fields = {"maxObservedTokensPerDay", "maxRunsPerDay", "maxAttemptsPerItem", "softRatio", "hardRatio"}
    if not isinstance(budgets, dict) or set(budgets) != budget_fields:
        raise OperatingLoopError("contract budgets are malformed", "Use the installed bounded budget shape.")
    for field in ("maxObservedTokensPerDay", "maxRunsPerDay"):
        if budgets[field] is not None and (type(budgets[field]) is not int or budgets[field] < 1):
            raise OperatingLoopError(f"budget {field} is invalid", "Use null or a positive integer.")
    if (type(budgets["maxAttemptsPerItem"]) is not int or not 1 <= budgets["maxAttemptsPerItem"] <= 3
            or type(budgets["softRatio"]) not in {int, float} or budgets["softRatio"] != 0.8
            or type(budgets["hardRatio"]) not in {int, float} or budgets["hardRatio"] != 1.0):
        raise OperatingLoopError("contract budget thresholds are invalid", "Restore the bounded retry and 80/100 thresholds.")
    telemetry = contract["telemetry"]
    if (not isinstance(telemetry, dict) or set(telemetry) != {"ledger", "schema", "retentionDays"}
            or telemetry.get("ledger") != ".itd-memory/operating-loop-runs.jsonl"
            or telemetry.get("schema") != ".itd/OPERATING_LOOP_RUN.schema.json"
            or type(telemetry.get("retentionDays")) is not int or not 1 <= telemetry["retentionDays"] <= 365):
        raise OperatingLoopError("contract telemetry binding is invalid", "Restore the canonical ledger, schema, and retention.")
    inbox = contract["humanInbox"]
    if (not isinstance(inbox, dict)
            or set(inbox) != {"target", "notifyOnlyWhenActionRequired", "maxUnacknowledgedHours"}
            or not isinstance(inbox.get("target"), str) or len(inbox["target"]) > 500
            or inbox.get("notifyOnlyWhenActionRequired") is not True
            or type(inbox.get("maxUnacknowledgedHours")) is not int
            or not 1 <= inbox["maxUnacknowledgedHours"] <= 168):
        raise OperatingLoopError("human inbox contract is invalid", "Restore action-only bounded notification settings.")
    return contract


def _verification_module():
    path = HERE / "itd_verification_loop.py"
    spec = importlib.util.spec_from_file_location("itd_operating_loop_verification", path)
    if spec is None or spec.loader is None:
        raise OperatingLoopError("Verification Loop validator is unavailable", "Restore itd_verification_loop.py.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_run(root: Path, contract: dict[str, Any], run: dict[str, Any], *,
                 now: dt.datetime | None = None,
                 host_attestation_validator: Callable[[Path, dict[str, Any]], Any] | None = None,
                 _historical: bool = False) -> dict[str, Any]:
    validate_contract(contract)
    if not contract["enabled"]:
        raise OperatingLoopError("disabled contract cannot accept runs", "Enable the contract explicitly first.")
    allowed = {"version", "runId", "recipeId", "startedAt", "durationMs", "tokenUsage", "itemsInspected",
               "itemsActionable", "actionsTaken", "escalations", "outcome", "invocation", "trustStage",
               "preflight", "hostProof", "failureSignals", "failureClasses", "verificationReceipts", "authorization",
               "executedAction", "pauseReason", "summary"}
    required = {"version", "runId", "recipeId", "startedAt", "durationMs", "tokenUsage", "itemsInspected",
                "itemsActionable", "actionsTaken", "escalations", "outcome", "invocation", "preflight"}
    if (not isinstance(run, dict) or not required <= set(run) or not set(run) <= allowed
            or type(run.get("version")) is not int or run["version"] != 1):
        raise OperatingLoopError("run record is malformed", "Include every required durable telemetry field.")
    if not isinstance(run["runId"], str) or not run["runId"] or len(run["runId"]) > 160:
        raise OperatingLoopError("run id is invalid", "Use a nonempty bounded run id.")
    parse_time(run["startedAt"], "startedAt")
    for field in ("durationMs", "itemsInspected", "itemsActionable", "actionsTaken", "escalations"):
        if type(run[field]) is not int or run[field] < 0:
            raise OperatingLoopError(f"run {field} is not a non-negative integer", "Record an observed integer count.")
    if run.get("recipeId") not in contract["recipes"]:
        raise OperatingLoopError("run recipe is not enabled", "Enable a registered recipe before recording its run.")
    if not isinstance(run["recipeId"], str) or not RECIPE_RE.fullmatch(run["recipeId"]):
        raise OperatingLoopError("run recipe id is malformed", "Use a registered lowercase recipe id.")
    if run.get("outcome") not in OUTCOMES:
        raise OperatingLoopError("run outcome is unknown", "Use a closed policy outcome.")
    preflight = run.get("preflight")
    preflight_fields = {"watchlistItems", "observedTokensBefore", "runsBefore", "attempt", "decision", "reason"}
    if (not isinstance(preflight, dict) or set(preflight) != preflight_fields
            or any(type(preflight[field]) is not int or preflight[field] < 0
                   for field in ("watchlistItems", "observedTokensBefore", "runsBefore", "attempt"))
            or preflight["decision"] not in {"early-exit", "downgrade", "pause", "continue"}
            or preflight["reason"] not in {"empty-watchlist", "soft-budget", "hard-budget", "within-budget"}):
        raise OperatingLoopError("run preflight is malformed", "Record the exact host-observed preflight decision.")
    expected_reason = {"early-exit": "empty-watchlist", "downgrade": "soft-budget",
                       "pause": "hard-budget", "continue": "within-budget"}[preflight["decision"]]
    if preflight["reason"] != expected_reason:
        raise OperatingLoopError("run preflight decision and reason disagree", "Use the deterministic decision reason.")
    if (preflight["decision"] == "early-exit"
            and (preflight["watchlistItems"] != 0 or run["outcome"] != "no-op"
                 or any(run[field] != 0 for field in ("itemsInspected", "itemsActionable", "actionsTaken")))):
        raise OperatingLoopError("empty-watchlist run did not early-exit cleanly",
                                 "Record no-op and zero inspected/actionable/action counts.")
    if preflight["decision"] == "pause" and run["outcome"] != "paused":
        raise OperatingLoopError("hard budget did not pause the run", "Record a paused outcome.")
    if (preflight["decision"] == "downgrade"
            and (run.get("trustStage") != "report" or run["outcome"] != "report")):
        raise OperatingLoopError("soft budget did not downgrade to a report",
                                 "Record report trust and a report outcome after soft budget.")
    invocation = run.get("invocation")
    invocation_fields = {"origin", "host", "sessionId", "attestationHash"}
    if not isinstance(invocation, dict) or not invocation_fields <= set(invocation) \
            or not set(invocation) <= invocation_fields | {"schedulerBinding"} \
            or invocation["host"] not in SUPPORTED_HOSTS \
            or not isinstance(invocation["sessionId"], str) or not invocation["sessionId"] \
            or len(invocation["sessionId"]) > 200 \
            or not isinstance(invocation["attestationHash"], str) \
            or not SHA256_RE.fullmatch(invocation["attestationHash"]):
        raise OperatingLoopError("run invocation provenance is malformed", "Use host-attested invocation provenance.")
    if invocation["attestationHash"] != run_attestation_hash(run):
        raise OperatingLoopError("run attestation hash does not bind the full record",
                                 "Have the host hash the canonical run before recording it.")
    expected_stored_proof = stored_host_proof(run)
    if invocation["origin"] == "scheduled" and run.get("hostProof") != expected_stored_proof:
        raise OperatingLoopError("scheduled run lacks its exact persisted host proof",
                                 "Persist the closed host proof returned for this run and preflight.")
    if invocation["origin"] == "scheduled":
        scheduled = invocation.get("schedulerBinding")
        matches = [item for item in contract["schedulerBindings"] if item["binding"] == scheduled]
        if len(matches) != 1 or invocation["host"] != matches[0]["host"] or run["recipeId"] != matches[0]["recipeId"]:
            raise OperatingLoopError("run does not match one declared scheduler binding",
                                     "Bind host, recipe, and binding to the project contract.")
        if run["outcome"] not in {"no-op", "report", "escalated", "paused", "failed"}:
            raise OperatingLoopError("scheduled run attempted a mutating outcome",
                                     "Keep background schedules observe/report-only; run approvals on demand.")
        if run["actionsTaken"] != 0 or any(key in run for key in
                                           ("authorization", "executedAction", "verificationReceipts")):
            raise OperatingLoopError("scheduled run contains action evidence",
                                     "Scheduled observation/report runs must record zero actions and no authority.")
    elif invocation["origin"] != "on-demand" or "schedulerBinding" in invocation:
        raise OperatingLoopError("run invocation origin is invalid", "Use on-demand or an exact scheduled binding.")
    if invocation["origin"] == "scheduled" or run["outcome"] == "approved-action":
        if _historical:
            if invocation["origin"] != "scheduled" or run.get("hostProof") != expected_stored_proof:
                raise OperatingLoopError("historical run proof is invalid",
                                         "Repair the ledger from original host evidence.")
        elif host_attestation_validator is None:
            raise OperatingLoopError("host invocation attestation was not validated",
                                     "Have the supported host adapter validate the attestation.")
        else:
            try:
                proof_request = {
                    "invocation": invocation,
                    "preflight": preflight,
                    "runSha256": run_attestation_hash(run),
                    "authorization": run.get("authorization"),
                    "executedAction": run.get("executedAction"),
                    "requirements": ["exclusive-lease", "one-time-use", "exact-action"],
                }
                attested = host_attestation_validator(root, proof_request)
                expected_attestation = {
                    "valid": True,
                    "host": invocation["host"],
                    "sessionId": invocation["sessionId"],
                    "attestationHash": invocation["attestationHash"],
                    "preflight": preflight,
                    "runSha256": run_attestation_hash(run),
                    "authorization": run.get("authorization"),
                    "action": run.get("executedAction"),
                    "exclusive": True,
                    "oneTime": True,
                }
                if (attested != expected_attestation
                        or (invocation["origin"] == "scheduled"
                            and run.get("hostProof") != expected_stored_proof)):
                    raise ValueError("adapter did not return the exact closed attestation proof")
            except Exception as exc:
                raise OperatingLoopError(f"host invocation attestation is invalid: {exc}",
                                         "Obtain fresh host-observed invocation evidence.") from exc
    usage = run.get("tokenUsage")
    if not isinstance(usage, dict) or set(usage) != {"measurement", "value", "source"} \
            or usage.get("measurement") != "host-observed" \
            or type(usage.get("value")) is not int or usage["value"] < 0 \
            or not isinstance(usage.get("source"), str) or not usage["source"] or len(usage["source"]) > 160:
        raise OperatingLoopError("token usage is not host-observed", "Record the host's observed token count and source.")
    if "trustStage" in run and run["trustStage"] not in {"observe", "report", "draft", "approved_execute"}:
        raise OperatingLoopError("run trust stage is unknown", "Use a closed trust stage.")
    for field, limit in (("pauseReason", 1000), ("summary", 2000)):
        if field in run and (not isinstance(run[field], str) or len(run[field]) > limit):
            raise OperatingLoopError(f"run {field} is invalid", "Use bounded text.")
    if "failureClasses" in run:
        classes = run["failureClasses"]
        if (not isinstance(classes, list) or any(not isinstance(item, str) for item in classes)
                or len(classes) != len(set(classes)) or not set(classes) <= FAILURES):
            raise OperatingLoopError("failure classification is invalid", "Use unique closed failure classes.")
    if ("failureSignals" in run) != ("failureClasses" in run):
        raise OperatingLoopError("failure signals and classes are not paired",
                                 "Record typed signals and their deterministic classes together.")
    if "failureSignals" in run and run["failureClasses"] != classify_failures(run["failureSignals"]):
        raise OperatingLoopError("failure classes do not match observed signals",
                                 "Derive failureClasses with classify_failures.")
    if run["outcome"] == "failed":
        if "failureSignals" not in run:
            raise OperatingLoopError("failed run lacks observed failure signals",
                                     "Record typed signals and derived failure classes.")
    if run["outcome"] != "approved-action":
        if run["actionsTaken"] != 0:
            raise OperatingLoopError("non-approved run records an action",
                                     "Only approved-action may record exactly one action.")
        if any(key in run for key in ("authorization", "executedAction", "verificationReceipts")):
            raise OperatingLoopError("non-action run contains action authority",
                                     "Attach lease/action/receipts only to approved-action records.")
        return run
    if run.get("trustStage") != "approved_execute" or type(run.get("actionsTaken")) is not int or run["actionsTaken"] != 1:
        raise OperatingLoopError("approved action lacks executable trust evidence", "Bind approved_execute and a performed action.")
    leases = contract["trustLeases"]
    auth = run.get("authorization")
    if len(leases) != 1 or auth != leases[0]:
        raise OperatingLoopError("approved action does not match the sole project lease", "Copy the exact current contract lease.")
    issued, expires = validate_authorization(auth)
    if auth["recipeId"] != run["recipeId"]:
        raise OperatingLoopError("approved action recipe does not match its lease", "Bind authorization.recipeId to run.recipeId.")
    if auth["hostApproval"]["host"] != invocation["host"]:
        raise OperatingLoopError("executing host does not match the approved host", "Execute on the explicitly approved host.")
    if run.get("executedAction") != auth["action"]:
        raise OperatingLoopError("executed action does not match the exact lease", "Bind the observed tool, targets, and payload hashes.")
    instant = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    if not issued <= instant < expires:
        raise OperatingLoopError("approved action lease is not currently valid", "Obtain a fresh exact host approval.")
    receipts = run.get("verificationReceipts")
    if not isinstance(receipts, list) or not receipts:
        raise OperatingLoopError("approved action lacks revalidated receipts", "Attach a current adjudication receipt.")
    validator = _verification_module().validate_adjudication
    unit_id = f"operating-loop:{run['recipeId']}:{run['runId']}"
    for receipt in receipts:
        if (not isinstance(receipt, dict) or set(receipt) != {"path", "riskTier"}
                or not isinstance(receipt["path"], str) or not receipt["path"] or len(receipt["path"]) > 500
                or receipt["riskTier"] not in {"low", "medium", "high"}):
            raise OperatingLoopError("verification receipt reference is malformed", "Bind path and riskTier.")
        try:
            verified = validator(root, Path(receipt["path"]), receipt["riskTier"], unit_id)
            if (not isinstance(verified, dict) or set(verified) != ADJUDICATION_FIELDS
                    or verified.get("version") != 1 or verified.get("kind") != "adjudication"
                    or verified.get("unitId") != unit_id or verified.get("riskTier") != receipt["riskTier"]
                    or verified.get("outcome") != "PASSED" or not isinstance(verified.get("candidate"), dict)
                    or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(verified.get("candidateDigest") or ""))
                    or not SHA256_RE.fullmatch(str(verified.get("policySha256") or ""))
                    or not SHA256_RE.fullmatch(str(verified.get("receiptSha256") or ""))
                    or not isinstance(verified.get("dependencies"), dict)
                    or type(verified.get("attempt")) is not int or verified["attempt"] < 1
                    or (verified.get("producer") or {}).get("id") != "itd-verification-loop"
                    or (verified.get("assurance") or {}).get("trustRoot") != "honest-host-orchestrator"):
                raise ValueError("Verification Loop did not return a PASSED adjudication")
        except OperatingLoopError:
            raise
        except Exception as exc:
            raise OperatingLoopError(f"verification receipt is not current: {exc}",
                                     "Re-run and adjudicate the exact current candidate.") from exc
    return run


def run_attestation_hash(run: dict[str, Any]) -> str:
    bound = json.loads(json.dumps(run))
    bound.pop("hostProof", None)
    invocation = bound.get("invocation")
    if isinstance(invocation, dict):
        invocation.pop("attestationHash", None)
    payload = json.dumps(bound, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def stored_host_proof(run: dict[str, Any]) -> dict[str, Any]:
    invocation = run.get("invocation") or {}
    preflight = run.get("preflight")
    preflight_sha = hashlib.sha256(json.dumps(
        preflight, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"valid": True, "host": invocation.get("host"), "sessionId": invocation.get("sessionId"),
            "attestationHash": invocation.get("attestationHash"), "runSha256": run_attestation_hash(run),
            "preflightSha256": preflight_sha}


def classify_failures(signals: dict[str, Any]) -> list[str]:
    if (not isinstance(signals, dict) or not signals
            or set(signals) - set(FAILURE_SIGNAL_MAP)
            or any(type(value) is not bool for value in signals.values())):
        raise OperatingLoopError("failure signals are malformed",
                                 "Use one or more closed boolean failure signals.")
    selected = {FAILURE_SIGNAL_MAP[name] for name, active in signals.items() if active}
    if not selected:
        raise OperatingLoopError("failure signals contain no active failure",
                                 "Set at least one observed failure signal to true.")
    policy_order = read_object(POLICY_PATH, "operating-loop policy")["failureTaxonomy"]
    return [item for item in policy_order if item in selected]


def evaluate_preflight(contract: dict[str, Any], *, watchlist_items: int,
                       observed_tokens_today: int, runs_today: int, attempt: int) -> dict[str, Any]:
    validate_contract(contract)
    values = {"watchlist_items": watchlist_items, "observed_tokens_today": observed_tokens_today,
              "runs_today": runs_today, "attempt": attempt}
    if any(type(value) is not int or value < 0 for value in values.values()):
        raise OperatingLoopError("preflight counters are not host-observed non-negative integers",
                                 "Pass integer watchlist, token, run, and attempt counters from the host.")
    if watchlist_items == 0:
        return {"decision": "early-exit", "outcome": "no-op", "trustStage": "observe",
                "reason": "empty-watchlist", "failureClasses": []}
    budgets = contract["budgets"]
    token_limit, run_limit = budgets["maxObservedTokensPerDay"], budgets["maxRunsPerDay"]
    hard = ((token_limit is not None and observed_tokens_today >= token_limit)
            or (run_limit is not None and runs_today >= run_limit)
            or attempt > budgets["maxAttemptsPerItem"])
    if hard:
        return {"decision": "pause", "outcome": "paused", "trustStage": "report",
                "reason": "hard-budget", "failureClasses": ["runaway"]}
    soft = ((token_limit is not None and observed_tokens_today >= token_limit * budgets["softRatio"])
            or (run_limit is not None and runs_today >= run_limit * budgets["softRatio"]))
    if soft:
        return {"decision": "downgrade", "outcome": "report", "trustStage": "report",
                "reason": "soft-budget", "failureClasses": []}
    return {"decision": "continue", "outcome": "report", "trustStage": "report",
            "reason": "within-budget", "failureClasses": []}


def _acquire_ledger_lock(fd: int) -> Callable[[], None]:
    try:
        if os.name == "nt":
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return lambda: (os.lseek(fd, 0, os.SEEK_SET), msvcrt.locking(fd, msvcrt.LK_UNLCK, 1))
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lambda: fcntl.flock(fd, fcntl.LOCK_UN)
    except (OSError, BlockingIOError) as exc:
        raise OperatingLoopError("telemetry append collided with another writer",
                                 "Classify parallel_collision and retry through the host budget.") from exc


def append_run(root: Path, contract: dict[str, Any], run: dict[str, Any], *,
               now: dt.datetime | None = None,
               host_attestation_validator: Callable[[Path, dict[str, Any]], Any] | None = None) -> Path:
    project = root.resolve()
    if not project.is_dir():
        raise OperatingLoopError("project root is not a directory", "Pass an existing project root.")
    contract_path = project / ".itd" / "OPERATING_LOOP_CONTRACT.json"
    if (not contract_path.is_file() or contract_path.is_symlink()
            or contract_path.resolve().parent.parent != project
            or read_object(contract_path, "project operating-loop contract") != contract):
        raise OperatingLoopError("operating-loop contract is not bound to this project root",
                                 "Use the exact project-local .itd/OPERATING_LOOP_CONTRACT.json.")
    validate_contract(contract)
    if (not isinstance(run, dict) or (run.get("invocation") or {}).get("origin") != "scheduled"
            or run.get("outcome") == "approved-action"):
        raise OperatingLoopError("telemetry writer accepts scheduled non-action runs only",
                                 "Record approved actions through the on-demand host workflow.")
    validate_run(project, contract, run, now=now,
                 host_attestation_validator=host_attestation_validator)
    memory = project / ".itd-memory"
    if not memory.is_dir() or memory.is_symlink():
        raise OperatingLoopError("telemetry boundary is not a project-local directory",
                                 "Initialize a local .itd-memory directory during explicit opt-in setup.")
    if memory.resolve().parent != project:
        raise OperatingLoopError("telemetry boundary escapes the project",
                                 "Replace the .itd-memory symlink with a project-local directory.")
    memory_real = memory.resolve()
    ledger = memory / "operating-loop-runs.jsonl"
    if not ledger.is_file() or ledger.is_symlink():
        raise OperatingLoopError("telemetry ledger is not an initialized regular file",
                                 "Create an empty project-local ledger during explicit opt-in setup.")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(ledger, os.O_APPEND | os.O_RDWR | nofollow)
    except OSError as exc:
        raise OperatingLoopError("telemetry ledger could not be opened safely",
                                 "Restore the regular project-local ledger and retry.") from exc
    unlock: Callable[[], None] | None = None
    try:
        opened = os.fstat(fd)
        linked = os.stat(ledger, follow_symlinks=False)
        if (memory.is_symlink() or memory.resolve() != memory_real
                or (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino)
                or opened.st_nlink != 1 or linked.st_nlink != 1
                or ledger.resolve().parent != memory_real):
            raise OperatingLoopError("telemetry boundary changed during append",
                                     "Classify parallel_collision and retry safely.")
        unlock = _acquire_ledger_lock(fd)
        if memory.is_symlink() or memory.resolve() != memory_real:
            raise OperatingLoopError("telemetry boundary changed after locking",
                                     "Classify parallel_collision and retry safely.")
        existing: list[dict[str, Any]] = []
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            chunks = []
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                chunks.append(chunk)
            raw = b"".join(chunks)
            if raw and not raw.endswith(b"\n"):
                committed_size = raw.rfind(b"\n") + 1
                os.ftruncate(fd, committed_size)
                os.fsync(fd)
                raw = raw[:committed_size]
            existing = [json.loads(line) for line in raw.decode("utf-8").splitlines()
                        if line.strip()]
        except Exception as exc:
            raise OperatingLoopError("telemetry ledger is malformed",
                                     "Classify state_rot and repair the append-only ledger.") from exc
        if existing:
            try:
                for item in existing:
                    if not isinstance(item, dict) or (item.get("invocation") or {}).get("origin") != "scheduled":
                        raise OperatingLoopError("ledger contains a non-scheduled record",
                                                 "Keep this telemetry ledger scheduled and report-only.")
                    validate_run(project, contract, item, _historical=True)
            except Exception as exc:
                if isinstance(exc, OperatingLoopError):
                    raise
                raise OperatingLoopError("telemetry ledger contains an invalid run",
                                         "Classify state_rot and repair from source evidence.") from exc
            if any(item.get("runId") == run.get("runId") for item in existing):
                raise OperatingLoopError("telemetry runId already exists",
                                         "Use a unique host-observed run id; never overwrite a run.")
            historical_ids = [item["runId"] for item in existing]
            if len(historical_ids) != len(set(historical_ids)):
                raise OperatingLoopError("telemetry ledger contains duplicate historical run ids",
                                         "Classify state_rot and repair duplicate history from evidence.")
        started_day = parse_time(run.get("startedAt"), "startedAt").date()
        same_day = [item for item in existing if parse_time(item["startedAt"], "startedAt").date() == started_day]
        observed_tokens = sum(item["tokenUsage"]["value"] for item in same_day)
        supplied = run.get("preflight")
        if not isinstance(supplied, dict):
            raise OperatingLoopError("run preflight is missing", "Record the host-bound preflight counters.")
        expected = evaluate_preflight(contract, watchlist_items=supplied.get("watchlistItems"),
                                      observed_tokens_today=observed_tokens, runs_today=len(same_day),
                                      attempt=supplied.get("attempt"))
        expected_preflight = {"watchlistItems": supplied.get("watchlistItems"),
                              "observedTokensBefore": observed_tokens, "runsBefore": len(same_day),
                              "attempt": supplied.get("attempt"), "decision": expected["decision"],
                              "reason": expected["reason"]}
        if supplied != expected_preflight:
            raise OperatingLoopError("run preflight does not match the append-only ledger",
                                     "Recompute counters and decision under the writer lock.")
        validated = validate_run(project, contract, run, now=now,
                                 host_attestation_validator=host_attestation_validator)
        payload = (json.dumps(validated, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        current = os.stat(ledger, follow_symlinks=False)
        if (memory.is_symlink() or memory.resolve() != memory_real or ledger.is_symlink()
                or ledger.resolve().parent != memory_real
                or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
                or opened.st_nlink != 1 or current.st_nlink != 1):
            raise OperatingLoopError("telemetry boundary changed before write",
                                     "Classify parallel_collision and retry safely.")
        start_size = os.fstat(fd).st_size
        try:
            offset = 0
            while offset < len(payload):
                offset += os.write(fd, payload[offset:])
            os.fsync(fd)
            current = os.stat(ledger, follow_symlinks=False)
            if (memory.is_symlink() or memory.resolve() != memory_real or ledger.is_symlink()
                    or ledger.resolve().parent != memory_real
                    or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
                    or opened.st_nlink != 1 or current.st_nlink != 1):
                os.ftruncate(fd, start_size)
                os.fsync(fd)
                raise OperatingLoopError("telemetry ledger was replaced during append",
                                         "Classify parallel_collision and retry the run.")
        except Exception:
            os.ftruncate(fd, start_size)
            os.fsync(fd)
            raise
    finally:
        if unlock is not None:
            unlock()
        os.close(fd)
    return ledger


def fail(exc: OperatingLoopError) -> int:
    print(json.dumps({"status": "UNVERIFIED", "why": exc.why, "fix": exc.fix}, sort_keys=True))
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate ITD operating-loop contracts and run evidence")
    sub = parser.add_subparsers(dest="action")
    contract_cmd = sub.add_parser("validate-contract")
    contract_cmd.add_argument("--contract", type=Path, required=True)
    run_cmd = sub.add_parser("validate-run")
    run_cmd.add_argument("--root", type=Path, default=Path.cwd())
    run_cmd.add_argument("--contract", type=Path, required=True)
    run_cmd.add_argument("--run", type=Path, required=True)
    readiness_cmd = sub.add_parser("readiness")
    readiness_cmd.add_argument("--root", type=Path, required=True)
    readiness_cmd.add_argument("--host", required=True)
    picker_cmd = sub.add_parser("pick")
    picker_cmd.add_argument("--job", required=True)
    classify_cmd = sub.add_parser("classify-failures")
    classify_cmd.add_argument("--signals", type=Path, required=True)
    preflight_cmd = sub.add_parser("preflight")
    preflight_cmd.add_argument("--contract", type=Path, required=True)
    preflight_cmd.add_argument("--watchlist-items", type=int, required=True)
    preflight_cmd.add_argument("--observed-tokens-today", type=int, required=True)
    preflight_cmd.add_argument("--runs-today", type=int, required=True)
    preflight_cmd.add_argument("--attempt", type=int, required=True)
    append_cmd = sub.add_parser("append-run")
    append_cmd.add_argument("--root", type=Path, required=True)
    append_cmd.add_argument("--contract", type=Path, required=True)
    append_cmd.add_argument("--run", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action is None:
        return 0
    try:
        if args.action == "readiness":
            print(json.dumps(diagnose_readiness(args.root, args.host), sort_keys=True))
            return 0
        if args.action == "pick":
            print(json.dumps(pick_pattern(args.job), sort_keys=True))
            return 0
        if args.action == "classify-failures":
            print(json.dumps({"failureClasses": classify_failures(
                read_object(args.signals, "failure signals"))}, sort_keys=True))
            return 0
        if args.action == "preflight":
            contract = validate_contract(read_object(args.contract, "operating-loop contract"))
            print(json.dumps(evaluate_preflight(
                contract, watchlist_items=args.watchlist_items,
                observed_tokens_today=args.observed_tokens_today, runs_today=args.runs_today,
                attempt=args.attempt), sort_keys=True))
            return 0
        contract = validate_contract(read_object(args.contract, "operating-loop contract"))
        if args.action == "validate-run":
            validate_run(args.root.resolve(), contract, read_object(args.run, "operating-loop run"))
        elif args.action == "append-run":
            print(append_run(args.root, contract, read_object(args.run, "operating-loop run")))
    except OperatingLoopError as exc:
        return fail(exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
