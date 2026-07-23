#!/usr/bin/env python3
"""Adversarial verifier for the host-neutral ITD operating-loop surface."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import importlib.util
import json
import pathlib
import sys
import tempfile
import types


ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ROOT / "skills" / "_shared" / "OPERATING_LOOP_POLICY.json"
CONTRACT = ROOT / "docs" / "templates" / "itd" / "OPERATING_LOOP_CONTRACT.json"
CONTRACT_SCHEMA = ROOT / "docs" / "templates" / "itd" / "OPERATING_LOOP_CONTRACT.schema.json"
RUN_SCHEMA = ROOT / "docs" / "templates" / "itd" / "OPERATING_LOOP_RUN.schema.json"
STORY_SCHEMA = ROOT / "docs" / "templates" / "itd" / "OPERATING_LOOP_STORY.schema.json"
SUCCESS_STORY = ROOT / "docs" / "templates" / "itd" / "OPERATING_LOOP_SUCCESS_STORY.json"
FAILURE_STORY = ROOT / "docs" / "templates" / "itd" / "OPERATING_LOOP_FAILURE_STORY.json"
RECIPES = ROOT / "skills" / "_shared" / "OPERATING_LOOP_RECIPES.json"
VALIDATOR = ROOT / "skills" / "_shared" / "itd_operating_loops.py"
EXTERNAL_SCHEMA = ROOT / "docs" / "external-validation" / "EXTERNAL_OUTCOME_SCHEMA.json"
EXTERNAL_PROTOCOL = ROOT / "docs" / "external-validation" / "PROTOCOL.md"
STORY_WORKFLOW = ROOT / "docs" / "external-validation" / "OPERATING_LOOP_STORIES.md"
OUTCOME_VALIDATOR = ROOT / "scripts" / "itd_external_outcomes.py"
EFFECTIVENESS_CONTRACT = ROOT / "docs" / "PRACTICAL_EFFECTIVENESS_CONTRACT.json"


class ContractError(ValueError):
    pass


def load_json(path: pathlib.Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"{path.relative_to(ROOT)}: missing; FIX: add the canonical artifact") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"{path.relative_to(ROOT)}:{exc.lineno}: invalid JSON; FIX: repair syntax") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{path.relative_to(ROOT)}: root must be an object")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def validate_schema_types(contract_schema: dict, run_schema: dict) -> None:
    trust_leases = ((contract_schema.get("properties") or {}).get("trustLeases") or {})
    contract_leases = trust_leases.get("items") or {}
    require(trust_leases.get("maxItems") == 1,
            "contract schema: trustLeases must preserve WIP=1")
    require(contract_leases.get("$ref") == "#/$defs/authorization",
            "contract schema: trustLeases must use the canonical authorization definition")
    contract_auth = ((contract_schema.get("$defs") or {}).get("authorization") or {})
    required_auth = {"leaseId", "recipeId", "capability", "action", "issuedAt", "expiresAt", "hostApproval"}
    require(contract_auth.get("type") == "object" and contract_auth.get("additionalProperties") is False,
            "contract schema: authorization must be a closed object")
    require(set(contract_auth.get("required") or []) == required_auth,
            "contract schema: authorization binding is incomplete")

    props = run_schema.get("properties") or {}
    require((props.get("tokenUsage") or {}).get("type") == "object",
            "run schema: tokenUsage must reject non-object values")
    require((props.get("verificationReceipts") or {}).get("type") == "array",
            "run schema: verificationReceipts must reject non-array values")
    receipt_items = (props.get("verificationReceipts") or {}).get("items") or {}
    require(receipt_items.get("type") == "object" and receipt_items.get("additionalProperties") is False,
            "run schema: receipts must be closed proof references, not arbitrary strings")
    require(set(receipt_items.get("required") or []) == {"path", "riskTier"},
            "run schema: receipt references must bind path and risk tier")
    run_auth = props.get("authorization") or {}
    require(run_auth.get("type") == "object" and run_auth.get("additionalProperties") is False,
            "run schema: authorization must be a closed object")
    require(set(run_auth.get("required") or []) == required_auth,
            "run schema: approved action authorization binding is incomplete")
    require((props.get("invocation") or {}).get("type") == "object",
            "run schema: host invocation provenance must be structured")
    require((props.get("executedAction") or {}).get("type") == "object",
            "run schema: executed action evidence must be structured")
    require((props.get("preflight") or {}).get("type") == "object"
            and (props.get("preflight") or {}).get("additionalProperties") is False,
            "run schema: preflight must be structured")
    require((props.get("failureSignals") or {}).get("additionalProperties") is False,
            "run schema: failure signals must use a closed object")
    require((props.get("hostProof") or {}).get("type") == "object"
            and (props.get("hostProof") or {}).get("additionalProperties") is False,
            "run schema: persisted host proof must be a closed object")


def validate_policy(policy: dict) -> None:
    require(policy.get("version") == 1, "policy.version: expected 1")
    require(policy.get("id") == "operating-loop-v1", "policy.id: expected operating-loop-v1")

    ownership = policy.get("ownership") or {}
    require(ownership.get("ownedRuntime") is False,
            "ownership.ownedRuntime: owned scheduler/runtime is forbidden; FIX: use host-native transport")
    require(ownership.get("scheduler") == "host-native",
            "ownership.scheduler: expected host-native")
    require(ownership.get("canonicalProjectState") == ".itd-memory/STATE.json",
            "ownership.canonicalProjectState: competing state is forbidden")
    require(ownership.get("markdownStateAllowed") is False,
            "ownership.markdownStateAllowed: LOOP.md/STATE.md cannot become canonical state")

    readiness = policy.get("readiness") or {}
    require(readiness.get("representation") == "binary-dimensions",
            "readiness.representation: expected binary-dimensions")
    require(readiness.get("scalarScore") is False,
            "readiness.scalarScore: scalar readiness score is forbidden")
    require(readiness.get("acceptanceGate") is False,
            "readiness.acceptanceGate: diagnostic cannot unlock completion")
    require(set(readiness.get("statuses") or []) == {"ready", "missing", "degraded"},
            "readiness.statuses: expected ready/missing/degraded")

    scheduling = policy.get("scheduling") or {}
    require(scheduling.get("transport") == "host-native",
            "scheduling.transport: owned scheduler/runtime is forbidden")
    require(scheduling.get("backgroundMutation") is False,
            "scheduling.backgroundMutation: periodic mutation is forbidden")
    require(scheduling.get("emptyWatchlist") == "early-exit",
            "scheduling.emptyWatchlist: expected early-exit")
    require(scheduling.get("externalWrites") == "on-demand-exact-host-approval",
            "scheduling.externalWrites: exact host approval is mandatory")
    require(scheduling.get("pushMergeDeployMoney") == "human-gate",
            "scheduling.pushMergeDeployMoney: irreversible actions require a human gate")

    trust = policy.get("trust") or {}
    require(trust.get("permanentL3") is False,
            "trust.permanentL3: permanent unattended authority is forbidden")
    require(trust.get("hostAttestationTrustRoot") == "honest-host-adapter"
            and trust.get("cryptographicHostIdentityClaim") is False,
            "trust: host evidence must state the honest-adapter boundary without a cryptographic claim")
    require(trust.get("scheduledMutationAuthority") is False,
            "trust.scheduledMutationAuthority: scheduled telemetry has no mutation authority")
    require(trust.get("maxConcurrentMutationUnits") == 1,
            "trust.maxConcurrentMutationUnits: WIP must remain 1")
    require(trust.get("stages") == ["observe", "report", "draft", "approved_execute"],
            "trust.stages: expected observe→report→draft→approved_execute")
    require(set(trust.get("leaseBindings") or []) >= {"recipe", "capability", "action", "expiresAt", "hostApproval"},
            "trust.leaseBindings: authority must be capability/action-bound and expiring")
    require((policy.get("invariants") or {}).get("wip") == 1,
            "invariants.wip: WIP must remain 1")

    telemetry = policy.get("telemetry") or {}
    require(telemetry.get("format") == "jsonl", "telemetry.format: expected jsonl")
    require(telemetry.get("appendOnly") is True, "telemetry.appendOnly: expected true")
    require(telemetry.get("recordCommitMarker") == "newline"
            and telemetry.get("crashTailRecovery") == "truncate-uncommitted-final-fragment",
            "telemetry: crash-safe JSONL commit/recovery policy is missing")
    require(telemetry.get("tokenMeasurement") == "host-observed",
            "telemetry.tokenMeasurement: estimates cannot satisfy observed evidence")
    require(telemetry.get("estimatedAsObserved") is False,
            "telemetry.estimatedAsObserved: forbidden")
    require(telemetry.get("validator") == "skills/_shared/itd_operating_loops.py",
            "telemetry.validator: executable validation binding is missing")

    failures = policy.get("failureTaxonomy") or []
    required_failures = {
        "runaway", "state_rot", "verifier_theater", "flake", "overreach",
        "notification_fatigue", "comprehension_debt", "parallel_collision",
        "escalation_failure",
    }
    require(set(failures) == required_failures,
            "failureTaxonomy: expected the complete closed nine-class taxonomy")

    evidence = policy.get("externalEvidence") or {}
    require(evidence.get("protocol") == "docs/external-validation/PROTOCOL.md",
            "externalEvidence.protocol: must reuse the existing protocol")
    require(evidence.get("selfReport") == "unverified", "externalEvidence.selfReport: must be unverified")
    require(evidence.get("starsOrBadges") == "unverified",
            "externalEvidence.starsOrBadges: popularity is not outcome evidence")
    require(evidence.get("syntheticFixture") == "unverified",
            "externalEvidence.syntheticFixture: synthetic outcomes are forbidden")
    require(evidence.get("methodologyOwnedProject") == "unverified",
            "externalEvidence.methodologyOwnedProject: self-owned evidence is not external")
    require(evidence.get("requires") == ["independent_operator", "independent_project", "baseline", "followup"],
            "externalEvidence.requires: expected independent before/after evidence")


def validate_contract() -> dict:
    policy = load_json(POLICY)
    validate_policy(policy)
    contract = load_json(CONTRACT)
    contract_schema = load_json(CONTRACT_SCHEMA)
    schema = load_json(RUN_SCHEMA)
    recipes = load_json(RECIPES)
    require(set(recipes) == {"version", "policyId", "patterns", "recipes"}
            and recipes.get("version") == 1 and recipes.get("policyId") == policy["id"]
            and isinstance(recipes.get("recipes"), list),
            "recipe registry: expected a policy-bound pattern and recipe registry")
    patterns = recipes.get("patterns") or []
    require(len(patterns) >= 5, "pattern registry: expected a useful supported-job set")
    terms = []
    for item in patterns:
        require(isinstance(item, dict) and set(item) == {"job", "skill", "aliases"},
                "pattern registry: definitions must be closed objects")
        require((ROOT / "skills" / item["skill"] / "SKILL.md").is_file(),
                f"pattern registry: {item.get('skill')} is not an existing skill")
        terms.extend([item["job"], *item["aliases"]])
    require(len(terms) == len(set(terms)), "pattern registry: ambiguous jobs or aliases")
    require(contract.get("$schema") == "./OPERATING_LOOP_CONTRACT.schema.json",
            "contract.$schema: project contract must bind its validator")
    require(contract.get("policyId") == policy["id"], "contract.policyId: policy binding mismatch")
    require(contract.get("enabled") is False, "contract.enabled: recurring work must be opt-in")
    require(contract.get("recipes") == [], "contract.recipes: project template must start empty")
    require(contract.get("trustLeases") == [], "contract.trustLeases: template must grant no authority")
    require(contract.get("schedulerBindings") == [], "contract.schedulerBindings: host binds transport explicitly")
    require(contract_schema.get("additionalProperties") is False,
            "contract schema: must use a closed object")
    disabled = next((item for item in (contract_schema.get("allOf") or [])
                     if (((item.get("if") or {}).get("properties") or {}).get("enabled") or {}).get("const") is False), None)
    require(disabled is not None and all(
        ((((disabled.get("then") or {}).get("properties") or {}).get(name) or {}).get("maxItems") == 0)
        for name in ("recipes", "schedulerBindings", "trustLeases")),
        "contract schema: disabled projects must grant no loop authority")
    scheduler = (((contract_schema.get("properties") or {}).get("schedulerBindings") or {}).get("items") or {})
    scheduler_props = scheduler.get("properties") or {}
    require(set((scheduler_props.get("host") or {}).get("enum") or []) ==
            {"claude-code", "codex", "github-actions"},
            "contract schema: scheduler hosts must be closed to supported adapters")
    require(set((scheduler_props.get("mode") or {}).get("enum") or []) == {"observe", "report"},
            "contract schema: scheduled modes must remain read-only")
    validate_schema_types(contract_schema, schema)
    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
            "run schema: expected JSON Schema 2020-12")
    required = set(schema.get("required") or [])
    require(required >= {"version", "runId", "recipeId", "startedAt", "durationMs", "tokenUsage",
                         "itemsInspected", "itemsActionable", "actionsTaken", "escalations", "outcome",
                         "preflight"},
            "run schema.required: missing durable telemetry fields")
    token_usage = (((schema.get("properties") or {}).get("tokenUsage") or {}).get("properties") or {})
    require((token_usage.get("measurement") or {}).get("const") == "host-observed",
            "run schema tokenUsage.measurement: must be host-observed")
    conditions = schema.get("allOf") or []
    approved = next((item for item in conditions
                     if (((item.get("if") or {}).get("properties") or {}).get("outcome") or {}).get("const")
                     == "approved-action"), None)
    require(approved is not None, "run schema: approved-action conditional evidence is missing")
    approved_then = approved.get("then") or {}
    require(set(approved_then.get("required") or []) >=
            {"trustStage", "verificationReceipts", "authorization", "executedAction"},
            "run schema: approved-action must require trust, verification, and approval evidence")
    approved_props = approved_then.get("properties") or {}
    require((approved_props.get("trustStage") or {}).get("const") == "approved_execute",
            "run schema: approved-action must bind approved_execute trust")
    require((approved_props.get("verificationReceipts") or {}).get("minItems") == 1,
            "run schema: approved-action requires a verification receipt")
    require((approved_props.get("actionsTaken") or {}).get("const") == 1,
            "run schema: one lease must authorize exactly one action")
    non_action = None
    for item in conditions:
        outcome_rule = (((item.get("if") or {}).get("properties") or {}).get("outcome") or {})
        if (outcome_rule.get("not") or {}).get("const") == "approved-action":
            non_action = item
            break
    require(non_action is not None and
            (((non_action.get("then") or {}).get("properties") or {}).get("actionsTaken") or {}).get("const") == 0,
            "run schema: non-approved outcomes must record zero actions")
    require("anyOf" in (((non_action.get("then") or {}).get("not") or {})),
            "run schema: non-approved outcomes must forbid action authority evidence")
    failed = next((item for item in conditions
                   if (((item.get("if") or {}).get("properties") or {}).get("outcome") or {}).get("const")
                   == "failed"), None)
    require(failed is not None, "run schema: failed conditional classification is missing")
    failed_then = failed.get("then") or {}
    require(set(failed_then.get("required") or []) >= {"failureClasses", "failureSignals"},
            "run schema: failed runs must require typed signals and derived classes")
    require((((failed_then.get("properties") or {}).get("failureClasses") or {}).get("minItems")) == 1,
            "run schema: failed runs require at least one failure class")
    scheduled = next((item for item in conditions
                      if (((((item.get("if") or {}).get("properties") or {}).get("invocation") or {})
                           .get("properties") or {}).get("origin") or {}).get("const") == "scheduled"), None)
    require(scheduled is not None and
            "approved-action" not in (((scheduled.get("then") or {}).get("properties") or {}).get("outcome") or {}).get("enum", []),
            "run schema: scheduled executions must forbid mutating outcomes")
    scheduled_then = scheduled.get("then") or {}
    require(((((scheduled_then.get("properties") or {}).get("actionsTaken") or {}).get("const")) == 0
             and "anyOf" in ((scheduled_then.get("not") or {}))),
            "run schema: scheduled runs must record zero actions and no authority evidence")
    return policy, contract_schema, schema


def mutation_guards(policy: dict) -> int:
    cases = [
        ("owned runtime", ("ownership", "ownedRuntime"), True),
        ("non-native scheduler", ("ownership", "scheduler"), "itd-daemon"),
        ("markdown state", ("ownership", "markdownStateAllowed"), True),
        ("scalar score", ("readiness", "scalarScore"), True),
        ("acceptance gate", ("readiness", "acceptanceGate"), True),
        ("background mutation", ("scheduling", "backgroundMutation"), True),
        ("owned scheduling transport", ("scheduling", "transport"), "itd-daemon"),
        ("automatic external writes", ("scheduling", "externalWrites"), "automatic"),
        ("automatic irreversible actions", ("scheduling", "pushMergeDeployMoney"), "automatic"),
        ("permanent L3", ("trust", "permanentL3"), True),
        ("fake cryptographic host identity", ("trust", "cryptographicHostIdentityClaim"), True),
        ("scheduled authority", ("trust", "scheduledMutationAuthority"), True),
        ("WIP two", ("trust", "maxConcurrentMutationUnits"), 2),
        ("invariant WIP two", ("invariants", "wip"), 2),
        ("estimated tokens", ("telemetry", "tokenMeasurement"), "estimated"),
        ("estimate accepted", ("telemetry", "estimatedAsObserved"), True),
        ("no crash-tail recovery", ("telemetry", "crashTailRecovery"), "none"),
        ("self report", ("externalEvidence", "selfReport"), "verified"),
        ("synthetic outcome", ("externalEvidence", "syntheticFixture"), "verified"),
    ]
    survived = []
    for name, path, value in cases:
        mutant = copy.deepcopy(policy)
        target = mutant
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        try:
            validate_policy(mutant)
        except ContractError:
            continue
        survived.append(name)
    require(not survived, f"mutation guards survived: {', '.join(survived)}")
    return len(cases)


def schema_mutation_guards(contract_schema: dict, run_schema: dict) -> int:
    cases = [
        ("run", ("properties", "tokenUsage", "type"), "null"),
        ("run", ("properties", "verificationReceipts", "type"), "string"),
        ("run", ("properties", "authorization", "additionalProperties"), True),
        ("run", ("properties", "verificationReceipts", "items", "type"), "string"),
        ("run", ("properties", "invocation", "type"), "string"),
        ("run", ("properties", "executedAction", "type"), "string"),
        ("run", ("properties", "preflight", "additionalProperties"), True),
        ("run", ("properties", "failureSignals", "additionalProperties"), True),
        ("run", ("properties", "hostProof", "additionalProperties"), True),
        ("contract", ("$defs", "authorization", "required"), ["leaseId", "recipeId"]),
        ("contract", ("properties", "trustLeases", "maxItems"), 2),
    ]
    survived = []
    for name, path, value in cases:
        contract_mutant = copy.deepcopy(contract_schema)
        run_mutant = copy.deepcopy(run_schema)
        target = run_mutant if name == "run" else contract_mutant
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        try:
            validate_schema_types(contract_mutant, run_mutant)
        except ContractError:
            continue
        survived.append(".".join(path))
    require(not survived, f"schema mutation guards survived: {', '.join(survived)}")
    return len(cases)


def load_validator():
    spec = importlib.util.spec_from_file_location("itd_operating_loops_contract_test", VALIDATOR)
    require(spec is not None and spec.loader is not None, "validator: cannot be imported")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bind_scheduled(module, run: dict) -> dict:
    run["invocation"]["attestationHash"] = module.run_attestation_hash(run)
    run["hostProof"] = module.stored_host_proof(run)
    return run


def behavioral_guards(contract: dict) -> int:
    module = load_validator()
    module.validate_contract(copy.deepcopy(contract))
    rejected = 0

    def must_reject(mutant: dict, label: str) -> None:
        nonlocal rejected
        try:
            module.validate_contract(mutant)
        except module.OperatingLoopError:
            rejected += 1
            return
        raise ContractError(f"validator accepted unsafe contract: {label}")

    base = copy.deepcopy(contract)
    base["enabled"] = True
    for unsafe_enabled in ("false", 1, None):
        mutant = copy.deepcopy(base)
        mutant["enabled"] = unsafe_enabled
        must_reject(mutant, f"non-boolean enabled={unsafe_enabled!r}")
    for label, host, mode in (("unsupported host", "other", "report"),
                              ("scheduled draft", "codex", "draft")):
        mutant = copy.deepcopy(base)
        mutant["schedulerBindings"] = [{"recipeId": "missing", "host": host,
                                         "binding": "job", "mode": mode}]
        must_reject(mutant, label)
    lease = {
        "leaseId": "lease-1", "recipeId": "missing", "capability": "write",
        "action": {"tool": "example", "targetsSha256": "a" * 64, "payloadSha256": "b" * 64},
        "issuedAt": "2026-07-22T10:00:00Z", "expiresAt": "2026-07-22T11:00:00Z",
        "hostApproval": {"host": "codex", "sessionId": "session", "approvalHash": "c" * 64},
    }
    mutant = copy.deepcopy(base)
    mutant["trustLeases"] = [lease, copy.deepcopy(lease)]
    must_reject(mutant, "multiple leases")

    # Inject one temporary registered id without changing the durable registry.
    original_loader = module.load_registry
    module.load_registry = lambda: {"fixture-recipe"}
    try:
        executable = copy.deepcopy(base)
        executable["recipes"] = ["fixture-recipe"]
        lease["recipeId"] = "fixture-recipe"
        executable["trustLeases"] = [lease]
        disabled = copy.deepcopy(executable)
        disabled["enabled"] = False
        must_reject(disabled, "disabled authority")
        run = {
            "version": 1, "runId": "run-1", "recipeId": "fixture-recipe",
            "startedAt": "2026-07-22T10:10:00Z", "durationMs": 1,
            "tokenUsage": {"measurement": "host-observed", "value": 1, "source": "host"},
            "itemsInspected": 1, "itemsActionable": 1, "actionsTaken": 1,
            "escalations": 0, "outcome": "approved-action", "trustStage": "approved_execute",
            "invocation": {"origin": "on-demand", "host": "codex", "sessionId": "execution",
                           "attestationHash": "d" * 64},
            "preflight": {"watchlistItems": 1, "observedTokensBefore": 0, "runsBefore": 0,
                          "attempt": 1, "decision": "continue", "reason": "within-budget"},
            "authorization": copy.deepcopy(lease),
            "executedAction": copy.deepcopy(lease["action"]),
            "verificationReceipts": [{"path": ".itd-memory/verification-loop/adjudications/x.json",
                                      "riskTier": "high"}],
        }
        run["invocation"]["attestationHash"] = module.run_attestation_hash(run)
        def host_success(_root, request):
            invocation = request["invocation"]
            return {
                "valid": True, "host": invocation["host"], "sessionId": invocation["sessionId"],
                "attestationHash": invocation["attestationHash"],
                "preflight": request["preflight"], "runSha256": request["runSha256"],
                "authorization": request["authorization"], "action": request["executedAction"],
                "exclusive": True, "oneTime": True,
            }

        def receipt_success(_root, _path, risk, unit_id):
            return {
                "version": 1, "kind": "adjudication", "createdAt": "2026-07-22T10:20:00Z",
                "unitId": unit_id, "riskTier": risk, "candidate": {"reviewedTree": "a" * 40},
                "candidateDigest": "sha256:" + "b" * 64, "policySha256": "c" * 64,
                "producer": {"id": "itd-verification-loop", "role": "adjudicator"},
                "producerRunId": "d" * 32,
                "assurance": {"trustRoot": "honest-host-orchestrator"},
                "attempt": 1, "attemptLedger": {"sequence": 1}, "checkerMode": "full",
                "dependencies": {"machine": {}}, "outcome": "PASSED", "receiptSha256": "e" * 64,
            }

        receipt_state = {"validator": receipt_success}
        original_verification_module = module._verification_module
        module._verification_module = lambda: types.SimpleNamespace(
            validate_adjudication=lambda *args: receipt_state["validator"](*args))

        calls = []
        host_calls = []
        def recording_host(root, request):
            host_calls.append((root, request))
            return host_success(root, request)

        def recording_receipt(*args):
            calls.append(args)
            return receipt_success(*args)

        receipt_state["validator"] = recording_receipt
        module.validate_run(ROOT, executable, run,
                            now=dt.datetime(2026, 7, 22, 10, 30, tzinfo=dt.timezone.utc),
                            host_attestation_validator=recording_host)
        require(calls and calls[0][2:] == ("high", "operating-loop:fixture-recipe:run-1"),
                "validator: receipt revalidation is not bound to the exact run unit")
        require(host_calls and host_calls[0][1]["authorization"] == lease
                and host_calls[0][1]["executedAction"] == lease["action"]
                and host_calls[0][1]["requirements"] ==
                ["exclusive-lease", "one-time-use", "exact-action"],
                "validator: host callback cannot validate exact approval and executed action")
        rejected += 1
        expired = copy.deepcopy(run)
        try:
            module.validate_run(ROOT, executable, expired,
                                now=dt.datetime(2026, 7, 22, 12, 0, tzinfo=dt.timezone.utc),
                                host_attestation_validator=host_success)
        except module.OperatingLoopError:
            pass
        else:
            raise ContractError("validator accepted an expired lease")
        mismatch = copy.deepcopy(run)
        mismatch["authorization"]["recipeId"] = "other-recipe"
        try:
            module.validate_run(ROOT, executable, mismatch,
                                now=dt.datetime(2026, 7, 22, 10, 30, tzinfo=dt.timezone.utc),
                                host_attestation_validator=host_success)
        except module.OperatingLoopError:
            rejected += 1
        else:
            raise ContractError("validator accepted a run/lease recipe mismatch")
        scheduled_contract = copy.deepcopy(executable)
        scheduled_contract["schedulerBindings"] = [{"recipeId": "fixture-recipe", "host": "codex",
                                                       "binding": "daily", "mode": "report"}]
        scheduled_action = copy.deepcopy(run)
        scheduled_action["invocation"] = {"origin": "scheduled", "host": "codex", "sessionId": "schedule",
                                           "attestationHash": "e" * 64, "schedulerBinding": "daily"}
        bind_scheduled(module, scheduled_action)
        try:
            module.validate_run(ROOT, scheduled_contract, scheduled_action,
                                now=dt.datetime(2026, 7, 22, 10, 30, tzinfo=dt.timezone.utc),
                                host_attestation_validator=host_success)
        except module.OperatingLoopError:
            rejected += 1
        else:
            raise ContractError("validator accepted an approved action from a scheduled run")
        scheduled_report = copy.deepcopy(scheduled_action)
        scheduled_report["outcome"] = "report"
        scheduled_report["trustStage"] = "report"
        for key in ("authorization", "executedAction", "verificationReceipts"):
            scheduled_report.pop(key)
        try:
            module.validate_run(ROOT, scheduled_contract, scheduled_report,
                                host_attestation_validator=host_success)
        except module.OperatingLoopError:
            rejected += 1
        else:
            raise ContractError("validator accepted actionsTaken > 0 from a scheduled report")
        scheduled_report["actionsTaken"] = 0
        bind_scheduled(module, scheduled_report)
        module.validate_run(ROOT, scheduled_contract, scheduled_report,
                            host_attestation_validator=host_success)
        on_demand_report = copy.deepcopy(scheduled_report)
        on_demand_report["invocation"] = {"origin": "on-demand", "host": "codex",
                                            "sessionId": "report", "attestationHash": "f" * 64}
        on_demand_report["actionsTaken"] = 1
        try:
            module.validate_run(ROOT, executable, on_demand_report)
        except module.OperatingLoopError:
            rejected += 1
        else:
            raise ContractError("validator accepted an action under a report outcome")
        malformed = copy.deepcopy(scheduled_report)
        malformed["durationMs"] = "not-an-int"
        malformed["unexpectedAuthority"] = True
        try:
            module.validate_run(ROOT, scheduled_contract, malformed,
                                host_attestation_validator=host_success)
        except module.OperatingLoopError:
            rejected += 1
        else:
            raise ContractError("validator accepted malformed or undeclared telemetry")
        wrong_action = copy.deepcopy(run)
        wrong_action["executedAction"]["payloadSha256"] = "f" * 64
        try:
            module.validate_run(ROOT, executable, wrong_action,
                                now=dt.datetime(2026, 7, 22, 10, 30, tzinfo=dt.timezone.utc),
                                host_attestation_validator=host_success)
        except module.OperatingLoopError:
            rejected += 1
        else:
            raise ContractError("validator accepted an action outside the exact lease")
        for label, mutate, reject_host, reject_receipt in (
            ("boolean version", lambda item: item.__setitem__("version", True), False, False),
            ("multiple approved actions", lambda item: item.__setitem__("actionsTaken", 2), False, False),
            ("overlong token source", lambda item: item["tokenUsage"].__setitem__("source", "x" * 161), False, False),
            ("rejected host attestation", lambda item: None, True, False),
            ("rejected receipt", lambda item: None, False, True),
        ):
            unsafe = copy.deepcopy(run)
            mutate(unsafe)
            receipt_state["validator"] = (lambda *_args: None) if reject_receipt else receipt_success
            try:
                module.validate_run(
                    ROOT, executable, unsafe,
                    now=dt.datetime(2026, 7, 22, 10, 30, tzinfo=dt.timezone.utc),
                    host_attestation_validator=(lambda *_args: None) if reject_host else host_success,
                )
            except module.OperatingLoopError:
                rejected += 1
            else:
                raise ContractError(f"validator accepted {label}")
        receipt_state["validator"] = lambda *_args: {"outcome": "PASSED"}
        try:
            module.validate_run(
                ROOT, executable, copy.deepcopy(run),
                now=dt.datetime(2026, 7, 22, 10, 30, tzinfo=dt.timezone.utc),
                host_attestation_validator=host_success,
            )
        except module.OperatingLoopError:
            rejected += 1
        else:
            raise ContractError("validator accepted a partial adjudication callback result")
        receipt_state["validator"] = receipt_success
        overlong_lease = copy.deepcopy(executable)
        overlong_lease["trustLeases"][0]["leaseId"] = "x" * 161
        must_reject(overlong_lease, "overlong lease id")
        original_loader2 = module.load_registry
        module.load_registry = lambda: {"Bad_ID"}
        try:
            invalid_recipe = copy.deepcopy(base)
            invalid_recipe["recipes"] = ["Bad_ID"]
            must_reject(invalid_recipe, "invalid recipe id")
        finally:
            module.load_registry = original_loader2
    finally:
        module.load_registry = original_loader
        if "original_verification_module" in locals():
            module._verification_module = original_verification_module
    return rejected + 1  # includes the valid exact-binding probe


def onboarding_guards() -> int:
    module = load_validator()
    checks = 0
    with tempfile.TemporaryDirectory(prefix="itd-readiness-") as raw:
        root = pathlib.Path(raw)
        (root / "AGENTS.md").write_text("# Project guidance\n", encoding="utf-8")
        (root / ".itd").mkdir()
        (root / ".itd" / "SCOPE_LOCK.md").write_text("# Scope\n", encoding="utf-8")
        acceptance = load_json(ROOT / "docs" / "templates" / "itd" / "ACCEPTANCE_CONTRACT.json")
        (root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(
            json.dumps(acceptance), encoding="utf-8")
        (root / ".itd-memory").mkdir()
        state = {"sessionState": "ACTIVE", "currentStage": "IMPLEMENTATION",
                 "intent": "fixture", "currentUnit": {"id": "U-1", "status": "in_progress"}}
        (root / ".itd-memory" / "STATE.json").write_text(json.dumps(state), encoding="utf-8")
        (root / "tests").mkdir()
        (root / "tests" / "verify_fixture.py").write_text("# check entry point\n", encoding="utf-8")
        before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
        ready = module.diagnose_readiness(root, "codex")
        after = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
        require(ready["status"] == "ready", "readiness: complete real-artifact fixture must be ready")
        require({item["name"] for item in ready["dimensions"]} == set(
            load_json(POLICY)["readiness"]["dimensions"]),
            "readiness: diagnostic dimensions drifted from policy")
        require(all(item["status"] == "ready" and item["why"] and item["fix"]
                    for item in ready["dimensions"]),
                "readiness: ready dimensions must have deterministic WHY/FIX")
        require("score" not in ready and "scalar" not in ready,
                "readiness: scalar output is forbidden")
        require(before == after, "readiness: diagnostic wrote to the project")
        checks += 5

        (root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text("{}\n", encoding="utf-8")
        invalid_contract = module.diagnose_readiness(root, "codex")
        invalid_by_name = {item["name"]: item for item in invalid_contract["dimensions"]}
        require(invalid_by_name["methodology_contracts"]["status"] == "degraded"
                and invalid_by_name["verification_loop"]["status"] == "degraded",
                "readiness: empty acceptance contract must not make any dependent dimension ready")
        (root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(
            json.dumps(acceptance), encoding="utf-8")
        malformed_schema = copy.deepcopy(acceptance)
        malformed_schema["criteriaSchema"]["requiredFields"].append({"not": "a string"})
        (root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(
            json.dumps(malformed_schema), encoding="utf-8")
        malformed_result = module.diagnose_readiness(root, "codex")
        malformed_by_name = {item["name"]: item for item in malformed_result["dimensions"]}
        require(malformed_by_name["methodology_contracts"]["status"] == "degraded"
                and malformed_by_name["verification_loop"]["status"] == "degraded",
                "readiness: malformed acceptance schema must degrade without crashing")
        (root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(
            json.dumps(acceptance), encoding="utf-8")
        (root / "tests" / "verify_fixture.py").unlink()
        empty_tests = module.diagnose_readiness(root, "codex")
        require(next(item for item in empty_tests["dimensions"]
                     if item["name"] == "project_checks")["status"] == "missing",
                "readiness: empty tests directory must not be ready")
        (root / "tests" / "verify_fixture.py").write_text("# check entry point\n", encoding="utf-8")
        checks += 3

        (root / "AGENTS.md").unlink()
        (root / "CLAUDE.md").write_text("# Vendor guidance\n", encoding="utf-8")
        (root / ".itd-memory" / "STATE.json").write_text("{}\n", encoding="utf-8")
        degraded = module.diagnose_readiness(root, "claude-code")
        by_name = {item["name"]: item for item in degraded["dimensions"]}
        require(degraded["status"] == "degraded"
                and by_name["project_guidance"]["status"] == "degraded"
                and by_name["durable_state"]["status"] == "degraded",
                "readiness: partial/malformed real artifacts must be degraded")
        require(all(item["why"] and item["fix"] for item in degraded["dimensions"]),
                "readiness: every result must include actionable WHY/FIX")
        checks += 2

    with tempfile.TemporaryDirectory(prefix="itd-missing-") as raw:
        missing = module.diagnose_readiness(pathlib.Path(raw), "codex")
        require(missing["status"] == "missing"
                and any(item["status"] == "missing" for item in missing["dimensions"]),
                "readiness: empty project must report missing artifacts")
        checks += 1
    try:
        module.diagnose_readiness(pathlib.Path(raw) / "absent", "codex")
    except module.OperatingLoopError as exc:
        require(exc.why and exc.fix, "readiness: invalid input must return WHY/FIX")
        checks += 1
    else:
        raise ContractError("readiness: nonexistent root did not fail closed")

    picked = module.pick_pattern("debug")
    require(picked == {"status": "ready", "job": "fix-bug", "skill": "bugfix",
                       "skillPath": "skills/bugfix/SKILL.md"},
            "pattern picker: alias did not map deterministically to the existing skill")
    require((ROOT / picked["skillPath"]).is_file(),
            "pattern picker: returned a nonexistent lifecycle skill")
    checks += 2
    try:
        module.pick_pattern("invent-new-lifecycle")
    except module.OperatingLoopError as exc:
        require("Choose one supported job" in exc.fix,
                "pattern picker: unknown job must list the supported path")
        checks += 1
    else:
        raise ContractError("pattern picker: unknown job did not fail closed")

    original = module.RECIPES_PATH
    with tempfile.TemporaryDirectory(prefix="itd-patterns-") as raw:
        bad = pathlib.Path(raw) / "registry.json"
        bad.write_text(json.dumps({"version": 1, "policyId": "operating-loop-v1",
                                   "patterns": [{"job": "bad-route", "skill": "not-a-skill",
                                                 "aliases": []}], "recipes": []}), encoding="utf-8")
        module.RECIPES_PATH = bad
        try:
            module.pick_pattern("bad-route")
        except module.OperatingLoopError:
            checks += 1
        else:
            raise ContractError("pattern picker: nonexistent skill mapping was accepted")
        finally:
            module.RECIPES_PATH = original
    return checks


def recipe_guards() -> int:
    module = load_validator()
    registry = load_json(RECIPES)
    parsed = module.read_registry()
    require(parsed == registry and len(parsed["recipes"]) >= 5,
            "recipes: registry must contain at least five validated recipes")
    require(len({item["id"] for item in parsed["recipes"]}) == len(parsed["recipes"]),
            "recipes: ids must be unique")
    checks = 2
    for item in parsed["recipes"]:
        require((ROOT / "skills" / item["skill"] / "SKILL.md").is_file(),
                f"recipes: {item['id']} does not target an existing skill")
        require(item["transport"] == "host-native" and item["scheduledMode"] == "report",
                f"recipes: {item['id']} exceeds host-native report scheduling")
        require(item["initialStage"] in {"report", "draft"}
                and item["onDemandMaxWithoutLease"] == "draft"
                and item["approvedExecution"] == "temporary-exact-lease",
                f"recipes: {item['id']} bypasses the trust ladder")
        require(item["wip"] == 1 and item["autoMerge"] is False
                and item["irreversibleActions"] == "human-gate",
                f"recipes: {item['id']} violates WIP/human gates")
        checks += 4

    cases = [
        ("owned transport", "transport", "itd-daemon"),
        ("scheduled draft", "scheduledMode", "draft"),
        ("scheduled execute", "scheduledMode", "approved_execute"),
        ("permanent execution", "approvedExecution", "permanent"),
        ("unleased execution", "onDemandMaxWithoutLease", "approved_execute"),
        ("auto merge", "autoMerge", True),
        ("WIP two", "wip", 2),
        ("missing skill", "skill", "not-a-skill"),
    ]
    original = module.RECIPES_PATH
    with tempfile.TemporaryDirectory(prefix="itd-recipes-") as raw:
        candidate = pathlib.Path(raw) / "registry.json"
        for label, field, value in cases:
            mutant = copy.deepcopy(registry)
            mutant["recipes"][0][field] = value
            candidate.write_text(json.dumps(mutant), encoding="utf-8")
            module.RECIPES_PATH = candidate
            try:
                module.read_registry()
            except module.OperatingLoopError:
                checks += 1
            else:
                raise ContractError(f"recipes: unsafe mutation survived: {label}")
        module.RECIPES_PATH = original
    return checks


def operations_guards(contract_template: dict) -> int:
    module = load_validator()
    registry = load_json(RECIPES)
    recipe_id = registry["recipes"][0]["id"]
    contract = copy.deepcopy(contract_template)
    contract["enabled"] = True
    contract["recipes"] = [recipe_id]
    contract["schedulerBindings"] = [{"recipeId": recipe_id, "host": "codex",
                                       "binding": "daily-state", "mode": "report"}]
    contract["budgets"] = {"maxObservedTokensPerDay": 1000, "maxRunsPerDay": 10,
                            "maxAttemptsPerItem": 3, "softRatio": 0.8, "hardRatio": 1.0}
    run = {
        "version": 1, "runId": "scheduled-1", "recipeId": recipe_id,
        "startedAt": "2026-07-22T12:00:00Z", "durationMs": 25,
        "tokenUsage": {"measurement": "host-observed", "value": 120, "source": "codex"},
        "itemsInspected": 3, "itemsActionable": 1, "actionsTaken": 0,
        "escalations": 1, "outcome": "report", "trustStage": "report",
        "invocation": {"origin": "scheduled", "host": "codex", "sessionId": "schedule-1",
                       "attestationHash": "a" * 64, "schedulerBinding": "daily-state"},
        "preflight": {"watchlistItems": 3, "observedTokensBefore": 0, "runsBefore": 0,
                      "attempt": 1, "decision": "continue", "reason": "within-budget"},
        "summary": "One stale state item requires attention.",
    }
    bind_scheduled(module, run)

    def host_success(_root, request):
        invocation = request["invocation"]
        return {"valid": True, "host": invocation["host"], "sessionId": invocation["sessionId"],
                "attestationHash": invocation["attestationHash"],
                "preflight": request["preflight"], "runSha256": request["runSha256"],
                "authorization": request["authorization"], "action": request["executedAction"],
                "exclusive": True, "oneTime": True}

    checks = 0
    with tempfile.TemporaryDirectory(prefix="itd-operations-") as raw:
        root = pathlib.Path(raw)
        (root / ".itd").mkdir()
        (root / ".itd" / "OPERATING_LOOP_CONTRACT.json").write_text(
            json.dumps(contract), encoding="utf-8")
        (root / ".itd-memory").mkdir()
        (root / ".itd-memory" / "operating-loop-runs.jsonl").write_text("", encoding="utf-8")
        ledger = module.append_run(root, contract, copy.deepcopy(run),
                                   host_attestation_validator=host_success)
        lines = ledger.read_text(encoding="utf-8").splitlines()
        require(len(lines) == 1 and json.loads(lines[0]) == run,
                "operations: validated scheduled run was not appended canonically")
        checks += 1
        before = ledger.read_bytes()
        try:
            module.append_run(root, contract, copy.deepcopy(run),
                              host_attestation_validator=host_success)
        except module.OperatingLoopError:
            require(ledger.read_bytes() == before, "operations: duplicate append changed the ledger")
            checks += 1
        else:
            raise ContractError("operations: duplicate run id was appended")
        invalid = copy.deepcopy(run)
        invalid["runId"] = "invalid-2"
        invalid["tokenUsage"]["measurement"] = "estimated"
        try:
            module.append_run(root, contract, invalid, host_attestation_validator=host_success)
        except module.OperatingLoopError:
            require(ledger.read_bytes() == before, "operations: invalid run changed the ledger")
            checks += 1
        else:
            raise ContractError("operations: non-observed telemetry was appended")
        collision = copy.deepcopy(run)
        collision["runId"] = "scheduled-2"
        bind_scheduled(module, collision)
        original_lock = module._acquire_ledger_lock
        def reject_lock(_fd):
            raise module.OperatingLoopError("telemetry append collided with another writer",
                                            "Classify parallel_collision and retry.")
        module._acquire_ledger_lock = reject_lock
        try:
            try:
                module.append_run(root, contract, collision, host_attestation_validator=host_success)
            except module.OperatingLoopError as exc:
                require("collided" in exc.why and ledger.read_bytes() == before,
                        "operations: collision did not fail closed without writing")
                checks += 1
            else:
                raise ContractError("operations: concurrent append was accepted")
        finally:
            module._acquire_ledger_lock = original_lock

        tampered_preflight = copy.deepcopy(run)
        tampered_preflight["runId"] = "scheduled-3"
        tampered_preflight["preflight"]["observedTokensBefore"] = 0
        tampered_preflight["preflight"]["runsBefore"] = 0
        bind_scheduled(module, tampered_preflight)
        try:
            module.append_run(root, contract, tampered_preflight,
                              host_attestation_validator=host_success)
        except module.OperatingLoopError:
            require(ledger.read_bytes() == before,
                    "operations: ledger-unbound budget decision changed the ledger")
            checks += 1
        else:
            raise ContractError("operations: ledger-unbound budget decision was accepted")

        wrong_contract = copy.deepcopy(contract)
        wrong_contract["project"] = "another-project"
        cross_project = copy.deepcopy(run)
        cross_project["runId"] = "scheduled-4"
        cross_project["preflight"]["observedTokensBefore"] = 120
        cross_project["preflight"]["runsBefore"] = 1
        bind_scheduled(module, cross_project)
        try:
            module.append_run(root, wrong_contract, cross_project,
                              host_attestation_validator=host_success)
        except module.OperatingLoopError:
            checks += 1
        else:
            raise ContractError("operations: contract from another project was accepted")

        changed_after_attestation = copy.deepcopy(run)
        changed_after_attestation["durationMs"] += 1
        try:
            module.validate_run(root, contract, changed_after_attestation,
                                host_attestation_validator=host_success)
        except module.OperatingLoopError:
            checks += 1
        else:
            raise ContractError("operations: record changed after host attestation was accepted")

        failed = copy.deepcopy(run)
        failed["runId"] = "failed-1"
        failed["outcome"] = "failed"
        failed["failureSignals"] = {"stateStale": True}
        failed["failureClasses"] = ["flake"]
        bind_scheduled(module, failed)
        try:
            module.validate_run(root, contract, failed, host_attestation_validator=host_success)
        except module.OperatingLoopError:
            checks += 1
        else:
            raise ContractError("operations: failure classes unrelated to signals were accepted")

        soft_wrong = copy.deepcopy(run)
        soft_wrong["runId"] = "soft-wrong"
        soft_wrong["preflight"] = {"watchlistItems": 1, "observedTokensBefore": 800,
                                   "runsBefore": 1, "attempt": 1,
                                   "decision": "downgrade", "reason": "soft-budget"}
        soft_wrong["outcome"] = "no-op"
        bind_scheduled(module, soft_wrong)
        try:
            module.validate_run(root, contract, soft_wrong, host_attestation_validator=host_success)
        except module.OperatingLoopError:
            checks += 1
        else:
            raise ContractError("operations: soft downgrade accepted a non-report outcome")

        original_line = json.loads(before.decode("utf-8"))
        original_line["hostProof"]["runSha256"] = "f" * 64
        ledger.write_text(json.dumps(original_line) + "\n", encoding="utf-8")
        forged_before = ledger.read_bytes()
        replay = copy.deepcopy(run)
        replay["runId"] = "replay-1"
        replay["preflight"]["observedTokensBefore"] = 120
        replay["preflight"]["runsBefore"] = 1
        bind_scheduled(module, replay)
        try:
            module.append_run(root, contract, replay, host_attestation_validator=host_success)
        except module.OperatingLoopError:
            require(ledger.read_bytes() == forged_before,
                    "operations: forged historical proof changed the ledger")
            checks += 1
        else:
            raise ContractError("operations: forged historical host proof was accepted")
        ledger.write_bytes(before)

        with ledger.open("ab") as handle:
            handle.write(b'{"runId":"torn"')
        recovered = copy.deepcopy(run)
        recovered["runId"] = "recovered-1"
        recovered["preflight"]["observedTokensBefore"] = 120
        recovered["preflight"]["runsBefore"] = 1
        bind_scheduled(module, recovered)
        module.append_run(root, contract, recovered, host_attestation_validator=host_success)
        recovered_lines = ledger.read_text(encoding="utf-8").splitlines()
        require(len(recovered_lines) == 2
                and [json.loads(line)["runId"] for line in recovered_lines]
                == ["scheduled-1", "recovered-1"],
                "operations: uncommitted crash tail was not recovered safely")
        checks += 1
        ledger.write_bytes(before)

        ledger.write_bytes(before + before)
        duplicate_before = ledger.read_bytes()
        duplicate_probe = copy.deepcopy(run)
        duplicate_probe["runId"] = "duplicate-probe"
        duplicate_probe["preflight"]["observedTokensBefore"] = 240
        duplicate_probe["preflight"]["runsBefore"] = 2
        bind_scheduled(module, duplicate_probe)
        try:
            module.append_run(root, contract, duplicate_probe,
                              host_attestation_validator=host_success)
        except module.OperatingLoopError:
            require(ledger.read_bytes() == duplicate_before,
                    "operations: duplicate historical ids changed the ledger")
            checks += 1
        else:
            raise ContractError("operations: duplicate historical run ids were accepted")
        ledger.write_bytes(before)

        with ledger.open("a", encoding="utf-8") as handle:
            handle.write('{"runId":[]}\n')
        malformed_before = ledger.read_bytes()
        next_run = copy.deepcopy(run)
        next_run["runId"] = "scheduled-5"
        next_run["preflight"]["observedTokensBefore"] = 120
        next_run["preflight"]["runsBefore"] = 1
        bind_scheduled(module, next_run)
        try:
            module.append_run(root, contract, next_run, host_attestation_validator=host_success)
        except module.OperatingLoopError:
            require(ledger.read_bytes() == malformed_before,
                    "operations: malformed historical ledger was modified")
            checks += 1
        else:
            raise ContractError("operations: semantically malformed ledger entry was accepted")

    with tempfile.TemporaryDirectory(prefix="itd-symlink-") as raw:
        root = pathlib.Path(raw)
        (root / ".itd").mkdir()
        (root / ".itd" / "OPERATING_LOOP_CONTRACT.json").write_text(
            json.dumps(contract), encoding="utf-8")
        (root / ".itd-memory").mkdir()
        target = root / "outside.jsonl"
        target.write_text("", encoding="utf-8")
        try:
            (root / ".itd-memory" / "operating-loop-runs.jsonl").symlink_to(target)
        except OSError:
            pass
        else:
            try:
                module.append_run(root, contract, copy.deepcopy(run),
                                  host_attestation_validator=host_success)
            except module.OperatingLoopError:
                require(target.read_text(encoding="utf-8") == "",
                        "operations: symlink target was modified")
                checks += 1
            else:
                raise ContractError("operations: symlink ledger escape was accepted")

    with tempfile.TemporaryDirectory(prefix="itd-hardlink-") as raw:
        root = pathlib.Path(raw)
        (root / ".itd").mkdir()
        (root / ".itd" / "OPERATING_LOOP_CONTRACT.json").write_text(
            json.dumps(contract), encoding="utf-8")
        (root / ".itd-memory").mkdir()
        target = root / "outside.jsonl"
        target.write_text("", encoding="utf-8")
        try:
            (root / ".itd-memory" / "operating-loop-runs.jsonl").hardlink_to(target)
        except OSError:
            pass
        else:
            try:
                module.append_run(root, contract, copy.deepcopy(run),
                                  host_attestation_validator=host_success)
            except module.OperatingLoopError:
                require(target.read_text(encoding="utf-8") == "",
                        "operations: hard-link target was modified")
                checks += 1
            else:
                raise ContractError("operations: hard-link ledger escape was accepted")

    with tempfile.TemporaryDirectory(prefix="itd-no-write-") as raw:
        root = pathlib.Path(raw)
        (root / ".itd").mkdir()
        (root / ".itd" / "OPERATING_LOOP_CONTRACT.json").write_text(
            json.dumps(contract), encoding="utf-8")
        invalid = copy.deepcopy(run)
        invalid["durationMs"] = "invalid"
        try:
            module.append_run(root, contract, invalid, host_attestation_validator=host_success)
        except module.OperatingLoopError:
            require(not (root / ".itd-memory").exists(),
                    "operations: rejected input created project state")
            checks += 1
        else:
            raise ContractError("operations: malformed input was accepted")

    decisions = [
        module.evaluate_preflight(contract, watchlist_items=0, observed_tokens_today=0,
                                  runs_today=0, attempt=0),
        module.evaluate_preflight(contract, watchlist_items=1, observed_tokens_today=800,
                                  runs_today=0, attempt=1),
        module.evaluate_preflight(contract, watchlist_items=1, observed_tokens_today=1000,
                                  runs_today=0, attempt=1),
        module.evaluate_preflight(contract, watchlist_items=1, observed_tokens_today=10,
                                  runs_today=1, attempt=1),
    ]
    require([item["decision"] for item in decisions] ==
            ["early-exit", "downgrade", "pause", "continue"],
            "operations: empty/soft/hard/continue budget decisions drifted")
    require(decisions[0]["outcome"] == "no-op" and decisions[2]["outcome"] == "paused"
            and decisions[2]["failureClasses"] == ["runaway"],
            "operations: early-exit and hard pause evidence is incomplete")
    checks += 2

    one_signal = {
        "budgetExceeded": "runaway", "stateStale": "state_rot",
        "receiptMissing": "verifier_theater", "nondeterministicCheck": "flake",
        "scopeDrift": "overreach", "tooManyNoopNotifications": "notification_fatigue",
        "unboundedContext": "comprehension_debt", "lockContended": "parallel_collision",
        "requiredEscalationUnsent": "escalation_failure",
    }
    for signal, expected in one_signal.items():
        require(module.classify_failures({signal: True}) == [expected],
                f"operations: {signal} did not classify as {expected}")
        checks += 1
    for bad in ({"unknown": True}, {"stateStale": False}, {"stateStale": 1}):
        try:
            module.classify_failures(bad)
        except module.OperatingLoopError:
            checks += 1
        else:
            raise ContractError(f"operations: invalid failure signals accepted: {bad}")
    try:
        module.evaluate_preflight(contract, watchlist_items=True, observed_tokens_today=0,
                                  runs_today=0, attempt=0)
    except module.OperatingLoopError:
        checks += 1
    else:
        raise ContractError("operations: boolean host counter was accepted")
    return checks


def evidence_guards() -> int:
    schema = load_json(STORY_SCHEMA)
    success = load_json(SUCCESS_STORY)
    failure = load_json(FAILURE_STORY)
    external = load_json(EXTERNAL_SCHEMA)
    protocol = EXTERNAL_PROTOCOL.read_text(encoding="utf-8")
    workflow = STORY_WORKFLOW.read_text(encoding="utf-8")
    spec = importlib.util.spec_from_file_location("itd_external_outcomes_story_test", OUTCOME_VALIDATOR)
    require(spec is not None and spec.loader is not None,
            "evidence: canonical external evaluator cannot be imported")
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    effectiveness = load_json(EFFECTIVENESS_CONTRACT)
    checks = 0

    required = {"$schema", "version", "storyId", "storyType", "evidenceStatus",
                "observedAt", "summary", "context", "intervention", "outcomes",
                "provenance", "privacy", "limitations"}
    require(schema.get("additionalProperties") is False
            and set(schema.get("required") or []) == required,
            "evidence: story schema must be closed and complete")
    checks += 1
    metrics = set(external.get("metrics") or [])
    schema_metrics = set((((schema.get("$defs") or {}).get("metrics") or {})
                          .get("properties") or {}))
    require(metrics and schema_metrics == metrics,
            "evidence: story outcomes drifted from the external-outcome metrics")
    checks += 1

    for template, expected_type in ((success, "success"), (failure, "failure")):
        require(set(template) == required and template.get("storyType") == expected_type,
                f"evidence: {expected_type} template shape/type is invalid")
        require(template.get("evidenceStatus") == "UNVERIFIED"
                and template.get("outcomes") == {
                    "baseline": None, "followup": None, "materialChange": "unmeasured"}
                and template.get("provenance", {}).get("recordDigest") is None
                and template.get("privacy", {}).get("consent") is False,
                f"evidence: {expected_type} template must fail closed before real evidence")
        checks += 2

    require("scripts/itd_external_outcomes.py evaluate" in workflow
            and "existing evaluator" in workflow
            and "UNVERIFIED" in workflow
            and "different pseudonymous operator" in workflow
            and "validate-story" in workflow
            and "Both success and failure stories must be retained" in workflow,
            "evidence: story workflow does not preserve evaluator, independence, or negative outcomes")
    require("OPERATING_LOOP_STORIES.md" in protocol
            and "Story prose never" in protocol,
            "evidence: canonical external protocol is not linked to the story boundary")
    checks += 2

    def record(project_hex: str, operator_hex: str, verifier_hex: str) -> dict:
        value = {
            "projectId": "proj_" + project_hex, "operatorId": "op_" + operator_hex,
            "repositoryClass": "external_private", "isMethodologyRepository": False,
            "synthetic": False, "fixture": False,
            "startedAt": "2026-06-14T19:30:00Z", "observedAt": "2026-07-15T19:30:00Z",
            "comparableUnits": 10,
            "baseline": {"defectEscapeRate": 0.2, "falseCompletionRate": 0.1,
                         "medianCycleMinutes": 120, "tokenUnitsPerVerifiedUnit": 100,
                         "operatorFrictionRate": 0.2, "criticalRegressions": 0},
            "followup": {"defectEscapeRate": 0.1, "falseCompletionRate": 0.05,
                         "medianCycleMinutes": 100, "tokenUnitsPerVerifiedUnit": 90,
                         "operatorFrictionRate": 0.1, "criticalRegressions": 0},
            "sourceHashes": [{"artifactDigest": project_hex[0] * 64,
                              "sha256": verifier_hex[0] * 64,
                              "verifiedBy": "op_" + verifier_hex,
                              "verifiedAt": "2026-07-15T19:35:00Z"}],
            "attestation": {"consent": True, "independentOperator": True,
                            "authorAffiliated": False, "accurate": True,
                            "recordDigest": ""},
            "privacy": {"containsPII": False, "containsSourceCode": False,
                        "containsSecrets": False, "containsCustomerData": False},
        }
        value["attestation"]["recordDigest"] = evaluator.record_digest(value)
        return value

    index = {"version": 1, "evidenceKind": "observed_external_outcome",
             "observedAt": "2026-07-15T19:30:00Z",
             "projects": [record("a1b2c3d4e5f6", "111111111111", "222222222222"),
                          record("b1c2d3e4f5a6", "222222222222", "111111111111"),
                          record("c1d2e3f4a5b6", "111111111111", "222222222222")]}
    accepted = index["projects"][0]
    eligible = copy.deepcopy(success)
    eligible.update({"storyId": "story_123456789abc", "evidenceStatus": "VALIDATED_EXTERNAL",
                     "observedAt": accepted["observedAt"]})
    eligible["context"] = {"projectId": accepted["projectId"],
                           "operatorId": accepted["operatorId"],
                           "repositoryClass": accepted["repositoryClass"],
                           "methodologyOwned": False}
    eligible["outcomes"] = {"baseline": copy.deepcopy(accepted["baseline"]),
                            "followup": copy.deepcopy(accepted["followup"]),
                            "materialChange": "improved"}
    eligible["provenance"] = {
        "protocol": "docs/external-validation/PROTOCOL.md",
        "indexPath": "docs/evidence/external-outcomes/INDEX.json",
        "recordDigest": accepted["attestation"]["recordDigest"],
        "sourceHashes": [accepted["sourceHashes"][0]["sha256"]],
        "verifiedBy": accepted["sourceHashes"][0]["verifiedBy"],
        "evidenceKinds": ["paired_baseline_followup", "independent_attestation"]}
    eligible["privacy"] = {"consent": True, "aggregateOnly": True,
                           "prohibitedFieldsAbsent": True}
    fixed_now = dt.datetime(2026, 7, 16, tzinfo=dt.timezone.utc)
    positive = evaluator.validate_story(eligible, index, effectiveness, external, now=fixed_now)
    require(positive["passed"],
            f"evidence: accepted index-backed story was rejected: {positive['issues']}")
    checks += 1

    mutations = []
    for kind in ("self_report", "stars", "synthetic_fixture"):
        item = copy.deepcopy(eligible)
        item["provenance"]["evidenceKinds"].append(kind)
        mutations.append((kind, item))
    owned = copy.deepcopy(eligible)
    owned["context"].update({"repositoryClass": "methodology_owned", "methodologyOwned": True})
    mutations.append(("methodology-owned project", owned))
    same_operator = copy.deepcopy(eligible)
    same_operator["provenance"]["verifiedBy"] = same_operator["context"]["operatorId"]
    mutations.append(("same operator", same_operator))
    for field in ("baseline", "followup"):
        item = copy.deepcopy(eligible)
        item["outcomes"][field] = None
        mutations.append((f"missing {field}", item))
    no_consent = copy.deepcopy(eligible)
    no_consent["privacy"]["consent"] = False
    mutations.append(("missing consent", no_consent))
    no_record = copy.deepcopy(eligible)
    no_record["provenance"]["recordDigest"] = None
    mutations.append(("missing record digest", no_record))
    wrong_protocol = copy.deepcopy(eligible)
    wrong_protocol["provenance"]["protocol"] = "another-protocol.md"
    mutations.append(("protocol drift", wrong_protocol))
    forged_index = copy.deepcopy(index)
    forged_index["projects"][0]["attestation"]["recordDigest"] = "f" * 64
    require(not evaluator.validate_story(eligible, forged_index, effectiveness, external,
                                         now=fixed_now)["passed"],
            "evidence: story passed against a rejected/tampered index")
    checks += 1
    for label, item in mutations:
        result = evaluator.validate_story(item, index, effectiveness, external, now=fixed_now)
        require(not result["passed"],
                f"evidence: {label} mutation claimed validated external evidence")
        checks += 1
    return checks


def not_implemented(phase: str) -> None:
    raise ContractError(f"phase {phase}: implementation evidence not present yet")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True,
                        choices=["contract", "onboarding", "recipes", "operations", "evidence", "all"])
    args = parser.parse_args()
    try:
        policy, contract_schema, run_schema = validate_contract()
        guards = mutation_guards(policy) + schema_mutation_guards(contract_schema, run_schema)
        guards += behavioral_guards(load_json(CONTRACT))
        if args.phase in {"onboarding", "all"}:
            guards += onboarding_guards()
        if args.phase in {"recipes", "all"}:
            guards += recipe_guards()
        if args.phase in {"operations", "all"}:
            guards += operations_guards(load_json(CONTRACT))
        if args.phase in {"evidence", "all"}:
            guards += evidence_guards()
        elif args.phase not in {"contract", "onboarding", "recipes", "operations"}:
            not_implemented(args.phase)
    except ContractError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"phase": args.phase, "mutationGuards": guards, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
