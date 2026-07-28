#!/usr/bin/env python3
"""Fail-closed verifier for harness-demo UX absorption into ITD."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import re
import shutil
import shlex
import statistics
import subprocess
import sys
import tempfile
from typing import Callable


ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "HARNESS_DEMO_ABSORPTION_CONTRACT.json"
DIGEST = ROOT / "docs" / "HARNESS_DEMO_ABSORPTION_CONTRACT.sha256"
ADR = ROOT / "docs" / "adr" / "ADR-004-harness-demo-ux-absorption.md"
PLAN = ROOT / "LAUNCH_PLAN.md"
BACKLOG = ROOT / "BACKLOG.md"
PHASES = ("contract", "context", "facade", "diagnostics", "isolation", "navigation")


class ContractError(ValueError):
    """A reader-actionable contract failure."""


def fail(message: str) -> int:
    print(f"FAILED: harness-demo absorption | WHY: {message} | FIX: restore the frozen contract or implement the missing phase evidence")
    return 2


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def path_label(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: pathlib.Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"{path_label(path)} is missing") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"{path_label(path)}:{exc.lineno} is invalid JSON") from exc
    require(isinstance(value, dict), f"{path_label(path)} must contain an object")
    return value


def run(command: list[str], cwd: pathlib.Path = ROOT, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=str(cwd), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ContractError(f"cannot execute {' '.join(command)}: {exc}") from exc


def require_exit(result: subprocess.CompletedProcess[str], expected: int, label: str) -> None:
    require(result.returncode == expected,
            f"{label}: expected exit {expected}, got {result.returncode}: "
            f"{(result.stdout + result.stderr).strip()[-600:]}")


def receipt_self_digest_valid(receipt: dict) -> bool:
    expected = receipt.get("receiptSha256") or ""
    payload = dict(receipt)
    payload.pop("receiptSha256", None)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    return len(expected) == 64 and hashlib.sha256(canonical).hexdigest() == expected


def validate_mutable_namespaces(resources: object, namespaces: object,
                                session_id: object) -> None:
    require(isinstance(session_id, str)
            and re.fullmatch(r"[0-9a-f]{32}", session_id) is not None,
            "pilot sessionId must be exactly 32 lowercase hexadecimal characters")
    require(isinstance(resources, list) and len(resources) >= 1
            and len(set(resources)) == len(resources)
            and all(isinstance(item, str) and item for item in resources),
            "each real pilot must isolate at least one named mutable resource")
    require(isinstance(namespaces, dict) and set(namespaces) == set(resources),
            "each mutable resource must have exactly one namespace")
    namespace_ids: list[str] = []
    for resource in resources:
        namespace = namespaces.get(resource)
        require(isinstance(namespace, dict)
                and namespace.get("resource") == resource
                and namespace.get("sessionId") == session_id
                and namespace.get("id") == f"{resource}:{session_id}"
                and namespace.get("exclusive") is True
                and namespace.get("shared") is False,
                "mutable namespace must bind resource and exact session id exclusively")
        namespace_ids.append(namespace["id"])
    require(len(set(namespace_ids)) == len(namespace_ids),
            "mutable namespace ids must be unique")


def validate_isolation_refutations() -> None:
    session_id = "a" * 32
    valid = {"database": {
        "resource": "database", "sessionId": session_id,
        "id": f"database:{session_id}", "exclusive": True, "shared": False,
    }}
    validate_mutable_namespaces(["database"], valid, session_id)
    invalid_cases = [
        ([], {}, session_id),
        (["database"], {"database": {
            "resource": "database", "sessionId": "a",
            "id": "database", "exclusive": True, "shared": False,
        }}, "a"),
        (["database"], {"database": {
            "resource": "database", "sessionId": session_id,
            "id": f"database:{session_id}", "exclusive": False, "shared": True,
        }}, session_id),
    ]
    for resources, namespaces, candidate_session in invalid_cases:
        try:
            validate_mutable_namespaces(resources, namespaces, candidate_session)
        except ContractError:
            continue
        raise ContractError("mutable namespace refutation guard is vacuous")


def validate_contract_value(contract: dict) -> None:
    require(contract.get("version") == 4, "contract.version must remain 4")
    require(contract.get("id") == "harness-demo-ux-absorption-v4", "contract id drifted")
    approval = contract.get("approvalProvenance") or {}
    require(approval.get("kind") == "host-observed-user-turn"
            and approval.get("threadId") == "019f9eb9-6a10-70d0-8500-a8b74d46335a"
            and approval.get("observedAt"),
            "contract approval provenance is missing")
    instruction = approval.get("normalizedInstruction") or ""
    require(instruction.startswith("реализуй: context-модули в /adopt;"),
            "approval does not bind the selected implementation sequence")
    require(hashlib.sha256(instruction.encode("utf-8")).hexdigest() ==
            approval.get("instructionSha256"),
            "approval instruction hash mismatch")
    repair = contract.get("repairApprovalProvenance") or {}
    require(repair.get("kind") == "host-observed-user-turn"
            and repair.get("threadId") == approval.get("threadId")
            and repair.get("observedAt")
            and repair.get("userInstruction") == "одобряю",
            "versioned repair approval provenance is missing")
    require(hashlib.sha256(repair["userInstruction"].encode("utf-8")).hexdigest() ==
            repair.get("instructionSha256"),
            "repair approval instruction hash mismatch")
    approved_change = repair.get("approvedChange") or ""
    require("exclude reserved underscore-prefixed skill directories" in approved_change
            and "preserve public baseline 40 and delta 0" in approved_change
            and hashlib.sha256(approved_change.encode("utf-8")).hexdigest() ==
            repair.get("approvedChangeSha256"),
            "repair approval does not bind the exact public-skill oracle change")
    require(repair.get("baseCandidateTree") ==
            "cfdd5ae845d8efbf1853dfcd81d17fbb7238d9a2",
            "repair must start from the accepted HDX-003 candidate tree")
    require(repair.get("allowedChangedPaths") == [
        "docs/HARNESS_DEMO_ABSORPTION_CONTRACT.json",
        "docs/HARNESS_DEMO_ABSORPTION_CONTRACT.sha256",
        "tests/verify_harness_demo_absorption.py",
    ] and repair.get("scopeBinding") ==
            "verification-loop-v1 exact candidate plus base-tree delta",
            "repair scope binding drifted or expanded")
    require(repair.get("acceptedRepairCandidateTree") ==
            "e6690162c45d8cf5c5bcebccd83a9aebb8d11bd3",
            "accepted v2 repair tree drifted")
    require(repair.get("acceptedRepairSeal") == {
        "docs/HARNESS_DEMO_ABSORPTION_CONTRACT.json":
            "20940c6238b15f9c9cca8118644cd6819272b61cb343099bbed142b7636c4b64",
        "docs/HARNESS_DEMO_ABSORPTION_CONTRACT.sha256":
            "654f196fd687d273e2a4a667bc0d92c7cf7d96e1c294b474b15f775828f88a48",
        "tests/verify_harness_demo_absorption.py":
            "e991bd09a7a5f0ea2b14de4d4cc4e67b866220f8beaa3ef13a15528ad229e222",
    }, "accepted v2 repair blob seal drifted")

    successor = contract.get("successorApprovalProvenance") or {}
    require(successor.get("kind") == "host-observed-user-turn"
            and successor.get("threadId") == approval.get("threadId")
            and successor.get("observedAt"),
            "v3 successor approval provenance is missing")
    successor_instruction = successor.get("userInstruction") or ""
    require(successor_instruction.startswith("Одобряю v3:")
            and hashlib.sha256(successor_instruction.encode("utf-8")).hexdigest() ==
            successor.get("instructionSha256"),
            "v3 successor approval instruction hash mismatch")
    successor_change = successor.get("approvedChange") or ""
    require("validate the exact v2 repair historically" in successor_change
            and "successor unit deltas remain bound by Scope Lock" in successor_change
            and hashlib.sha256(successor_change.encode("utf-8")).hexdigest() ==
            successor.get("approvedChangeSha256"),
            "v3 approval does not bind successor-safe historical validation")
    security_repair = contract.get("securityRepairApprovalProvenance") or {}
    require(security_repair.get("kind") == "host-observed-user-turn"
            and security_repair.get("threadId") == approval.get("threadId")
            and security_repair.get("observedAt"),
            "v4 security-repair approval provenance is missing")
    security_instruction = security_repair.get("userInstruction") or ""
    require(security_instruction.startswith("Одобряю v4 security repair:")
            and hashlib.sha256(security_instruction.encode("utf-8")).hexdigest() ==
            security_repair.get("instructionSha256"),
            "v4 security-repair approval instruction hash mismatch")
    security_change = security_repair.get("approvedChange") or ""
    require("full hash-bound v1 packet containing parent STATE and mutableResources"
            in security_change
            and "remove compatibility from the production runner afterward"
            in security_change
            and "successor HDX candidates to only those three frozen files"
            in security_change
            and hashlib.sha256(security_change.encode("utf-8")).hexdigest() ==
            security_repair.get("approvedChangeSha256"),
            "v4 approval does not bind the exact fixture and successor repair")
    require(security_repair.get("baseCandidateTree") ==
            "0d48fdd6893ec90e0712c03917306cde6eb35d27"
            and security_repair.get("allowedChangedPaths") == [
                "docs/HARNESS_DEMO_ABSORPTION_CONTRACT.json",
                "docs/HARNESS_DEMO_ABSORPTION_CONTRACT.sha256",
                "tests/verify_harness_demo_absorption.py",
            ]
            and security_repair.get("scopeBinding") ==
            "verification-loop-v1 exact historical repair plus successor exact-candidate receipts"
            and security_repair.get("successorDeltaPolicy") ==
            "successor HDX candidates are bound by Scope Lock and need not contain only the three historical repair files",
            "v4 security-repair scope or successor policy drifted")
    require((contract.get("source") or {}).get("reviewedCommit") ==
            "0eef0112daeaf3b5067d39b030ca33e53bf4c61b",
            "upstream reviewed commit must stay pinned")
    change = contract.get("changePolicy") or {}
    require(change.get("mode") == "new-version-and-human-approval",
            "frozen requirements cannot be edited in place")

    invariants = contract.get("invariants") or {}
    require(invariants.get("wip") == 1, "WIP must remain 1")
    require(invariants.get("ownedRuntime") is False, "an ITD-owned runtime is forbidden")
    require(invariants.get("newLifecycleSkills") == 0, "new lifecycle skills are forbidden")
    require(invariants.get("canonicalState") == [".itd", ".itd-memory"],
            "canonical state must remain .itd plus .itd-memory")
    require(invariants.get("authoritativeMarkdownState") is False,
            "Markdown cannot become authoritative state")
    require(invariants.get("authoritativeSentinelState") is False,
            "sentinel files cannot become completion authority")
    require(invariants.get("completionAuthority") == "verification-loop-v1 exact staged candidate",
            "completion must remain bound to the exact staged candidate")
    require(invariants.get("isolationFailure") == "fail-closed",
            "isolation failure must not fall back to a shared resource")
    require(invariants.get("internalPilotCountsAsExternalAdoption") is False,
            "internal pilots cannot become external adoption evidence")
    require(invariants.get("bundledLanguageSpecificNavigationServer") is False,
            "a bundled language-specific navigation server is forbidden")

    thresholds = contract.get("thresholds") or {}
    require((thresholds.get("generatedContextIndexes") or {}) ==
            {"required": 1, "unsupportedClaims": 0},
            "context-index target or unsupported-claim ceiling drifted")
    require((thresholds.get("capturedExampleReplays") or {}) ==
            {"passed": 1, "required": 1},
            "captured example must replay 1/1")
    public_skill_contract = thresholds.get("publicLifecycleSkills") or {}
    require({key: public_skill_contract.get(key) for key in (
        "root", "population", "reservedNamePrefix",
        "reservedSkillDirectories", "baseline",
    )} == {
        "root": "skills",
        "population": "top-level-directories-containing-SKILL.md",
        "reservedNamePrefix": "_",
        "reservedSkillDirectories": ["_shared"],
        "baseline": 40,
    }, "public lifecycle skill population definition or baseline drifted")
    require(public_skill_contract.get("baselineNames") == [
        "adopt", "advisor", "autopilot", "blueprint", "browser-check",
        "bugfix", "caveman", "context-mode-setup", "cross-review", "deploy",
        "deps-audit", "discover", "doc", "explain", "github-workflow",
        "goal", "grill-me", "guide", "handoff", "harden", "infra",
        "kickstart", "market-scan", "mcp-docs", "migrate", "migrate-prod",
        "obsidian-export", "perf", "project", "refactor", "retro", "review",
        "security-audit", "security-guidance-setup", "seo-setup",
        "session-save", "strategy", "task", "test", "tool-sync",
    ], "public lifecycle skill baseline names drifted")
    require(thresholds.get("publicLifecycleSkillDelta") == 0,
            "public lifecycle skill count must not grow")
    diagnostics = thresholds.get("incrementalDiagnostics") or {}
    require(diagnostics.get("defaultOn") is False, "incremental diagnostics must remain default-off")
    require(diagnostics.get("acceptanceEvidence") is False,
            "incremental diagnostics cannot count as acceptance evidence")
    require(diagnostics.get("minimumLabeledRuns") == 30,
            "diagnostic promotion requires 30 labeled runs")
    require(diagnostics.get("minimumLabeledEmissions") == 30,
            "diagnostic promotion requires 30 human-labeled emissions")
    require(diagnostics.get("baseline") == "same project checks without incremental diagnostics"
            and diagnostics.get("treatment") == "same project checks with the opt-in incremental profile",
            "diagnostic A/B baseline and treatment drifted")
    require(diagnostics.get("falseNoiseDefinition") ==
            "human-labeled nonactionable diagnostics divided by all emitted diagnostics",
            "false-noise denominator or label provenance is undefined")
    require(diagnostics.get("measurement") == "host-observed",
            "diagnostic latency must be host-observed")
    require(diagnostics.get("medianLatencyMsMax") == 2000, "median latency ceiling drifted")
    require(diagnostics.get("p95LatencyMsMax") == 5000, "p95 latency ceiling drifted")
    require(diagnostics.get("falseNoiseRatioMax") == 0.1, "false-noise ceiling drifted")
    pilots = thresholds.get("freshSessionPilots") or {}
    require(pilots.get("passed") == 3 and pilots.get("required") == 3,
            "three passing fresh-session pilots are required")
    require(pilots.get("minimumMutableResourcesPerPilot") == 1,
            "each fresh-session pilot must isolate a mutable resource")
    require(pilots.get("sessionIdPattern") == "^[0-9a-f]{32}$"
            and pilots.get("namespaceScheme") == "resource-plus-exact-session",
            "pilot session and namespace identity contract drifted")
    require(pilots.get("sharedMutableFallbacksMax") == 0,
            "shared mutable-resource fallback is forbidden")
    require(pilots.get("exactCandidateReceiptRequired") is True,
            "each pilot must carry an exact-candidate receipt")
    fixture = thresholds.get("sealedIsolationFixture") or {}
    require(fixture == {
        "packetVersion": 1,
        "packetKind": "fresh-session-unit-packet",
        "parentStateOwner": "parent",
        "parentStateHashRequired": True,
        "minimumMutableResources": 1,
        "sharedMutableResources": [],
        "legacyFourFieldPacketAllowed": False,
        "completionEvidence": False,
        "externalAdoptionEvidence": False,
    }, "sealed isolation fixture must use the full non-evidence v1 packet")
    navigation = thresholds.get("semanticNavigation") or {}
    require(navigation.get("requiredLanguages") == ["python", "typescript"],
            "Python and TypeScript coverage is required")
    require(navigation.get("demandGateRequired") is True
            and navigation.get("notActivatedIsValidDecision") is True,
            "semantic navigation must remain conditional on the frozen demand gate")
    require(navigation.get("operations") == ["definitions", "references", "outline"],
            "semantic navigation operations drifted")
    require(navigation.get("plainTextFallbackRequired") is True,
            "plain-text fallback is required")
    require(navigation.get("coverageDeclarationRequired") is True
            and navigation.get("confidenceDeclarationRequired") is True,
            "providers must declare coverage and confidence")

    units = contract.get("units") or []
    require([row.get("id") for row in units] ==
            [f"HDX-{number:03d}" for number in range(1, 15)],
            "contract must bind the complete HDX-001..HDX-014 unit sequence")
    require([row.get("phase") for row in units] ==
            ["contract", "context", "facade", "facade", "facade",
             "diagnostics", "diagnostics", "isolation", "isolation",
             "isolation", "isolation", "navigation", "navigation", "all"],
            "unit-to-phase mapping drifted")
    require(all(row.get("deliverable") for row in units),
            "each implementation unit needs an explicit deliverable")

    phase_rows = contract.get("phases") or []
    require([row.get("id") for row in phase_rows] ==
            ["contract", "context", "facade", "diagnostics", "isolation", "navigation", "all"],
            "phase order or coverage drifted")
    require([row.get("unitId") for row in phase_rows] ==
            ["HDX-001", "HDX-002", "HDX-005", "HDX-007",
             "HDX-011", "HDX-013", "HDX-014"],
            "phase-to-goal-unit binding drifted")
    expected_guards = {
        "owned_runtime", "wip_above_one", "new_lifecycle_skill", "markdown_authority",
        "sentinel_authority", "non_exact_completion", "isolation_fail_open",
        "synthetic_external_adoption", "diagnostics_default_on",
        "diagnostics_as_acceptance", "diagnostic_sample_reduced",
        "latency_threshold_weakened",
        "noise_threshold_weakened", "pilot_count_reduced", "shared_resource_fallback",
        "empty_mutable_namespace", "substring_session_namespace",
        "shared_mutable_namespace",
        "single_language_navigation", "missing_plain_text_fallback",
        "bundled_language_specific_server", "mutable_contract_without_approval",
        "missing_approval_provenance", "missing_repair_approval",
        "public_skill_reserved_scope", "public_skill_baseline_drift",
        "repair_base_tree_drift", "repair_scope_expansion",
        "missing_successor_approval", "accepted_repair_tree_drift",
        "accepted_repair_seal_drift",
        "missing_security_repair_approval", "security_repair_scope_expansion",
        "legacy_unbound_isolation_fixture",
    }
    require(set(contract.get("mutationGuards") or []) == expected_guards,
            "mutation guard inventory is incomplete")


def validate_digest() -> None:
    try:
        rows = [line.split() for line in DIGEST.read_text(encoding="utf-8").splitlines()
                if line.strip()]
        declared = {row[1]: row[0] for row in rows if len(row) == 2}
    except FileNotFoundError as exc:
        raise ContractError("frozen contract digest is missing") from exc
    sealed = {
        "docs/HARNESS_DEMO_ABSORPTION_CONTRACT.json": CONTRACT,
        "tests/verify_harness_demo_absorption.py": pathlib.Path(__file__).resolve(),
    }
    require(set(declared) == set(sealed), "digest must seal the contract and its evaluator")
    for label, path in sealed.items():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        require(declared[label] == actual, f"frozen digest mismatch for {label}")


def expect_rejected(base: dict, mutate: Callable[[dict], None], label: str) -> None:
    candidate = copy.deepcopy(base)
    mutate(candidate)
    try:
        validate_contract_value(candidate)
    except ContractError:
        return
    raise ContractError(f"mutation guard {label!r} is vacuous")


def validate_mutations(contract: dict) -> int:
    mutations: list[tuple[str, Callable[[dict], None]]] = [
        ("owned_runtime", lambda c: c["invariants"].__setitem__("ownedRuntime", True)),
        ("wip_above_one", lambda c: c["invariants"].__setitem__("wip", 2)),
        ("new_lifecycle_skill", lambda c: c["invariants"].__setitem__("newLifecycleSkills", 1)),
        ("markdown_authority", lambda c: c["invariants"].__setitem__("authoritativeMarkdownState", True)),
        ("sentinel_authority", lambda c: c["invariants"].__setitem__("authoritativeSentinelState", True)),
        ("non_exact_completion", lambda c: c["invariants"].__setitem__("completionAuthority", "DONE.txt")),
        ("isolation_fail_open", lambda c: c["invariants"].__setitem__("isolationFailure", "shared-fallback")),
        ("synthetic_external_adoption", lambda c: c["invariants"].__setitem__("internalPilotCountsAsExternalAdoption", True)),
        ("diagnostics_default_on", lambda c: c["thresholds"]["incrementalDiagnostics"].__setitem__("defaultOn", True)),
        ("diagnostics_as_acceptance", lambda c: c["thresholds"]["incrementalDiagnostics"].__setitem__("acceptanceEvidence", True)),
        ("diagnostic_sample_reduced", lambda c: c["thresholds"]["incrementalDiagnostics"].__setitem__("minimumLabeledEmissions", 0)),
        ("latency_threshold_weakened", lambda c: c["thresholds"]["incrementalDiagnostics"].__setitem__("p95LatencyMsMax", 10000)),
        ("noise_threshold_weakened", lambda c: c["thresholds"]["incrementalDiagnostics"].__setitem__("falseNoiseRatioMax", 0.5)),
        ("pilot_count_reduced", lambda c: c["thresholds"]["freshSessionPilots"].__setitem__("required", 1)),
        ("empty_mutable_namespace", lambda c: c["thresholds"]["freshSessionPilots"].__setitem__("minimumMutableResourcesPerPilot", 0)),
        ("substring_session_namespace", lambda c: c["thresholds"]["freshSessionPilots"].__setitem__("sessionIdPattern", ".+")),
        ("shared_mutable_namespace", lambda c: c["thresholds"]["freshSessionPilots"].__setitem__("namespaceScheme", "substring-only")),
        ("shared_resource_fallback", lambda c: c["thresholds"]["freshSessionPilots"].__setitem__("sharedMutableFallbacksMax", 1)),
        ("single_language_navigation", lambda c: c["thresholds"]["semanticNavigation"].__setitem__("requiredLanguages", ["python"])),
        ("missing_plain_text_fallback", lambda c: c["thresholds"]["semanticNavigation"].__setitem__("plainTextFallbackRequired", False)),
        ("bundled_language_specific_server", lambda c: c["invariants"].__setitem__("bundledLanguageSpecificNavigationServer", True)),
        ("mutable_contract_without_approval", lambda c: c["changePolicy"].__setitem__("mode", "edit-in-place")),
        ("missing_approval_provenance", lambda c: c.__setitem__("approvalProvenance", {})),
        ("missing_repair_approval", lambda c: c.__setitem__("repairApprovalProvenance", {})),
        ("public_skill_reserved_scope", lambda c: c["thresholds"]["publicLifecycleSkills"].__setitem__("reservedNamePrefix", "")),
        ("public_skill_baseline_drift", lambda c: c["thresholds"]["publicLifecycleSkills"].__setitem__("baseline", 41)),
        ("repair_base_tree_drift", lambda c: c["repairApprovalProvenance"].__setitem__("baseCandidateTree", "0" * 40)),
        ("repair_scope_expansion", lambda c: c["repairApprovalProvenance"]["allowedChangedPaths"].append("skills/task/SKILL.md")),
        ("missing_successor_approval", lambda c: c.__setitem__("successorApprovalProvenance", {})),
        ("accepted_repair_tree_drift", lambda c: c["repairApprovalProvenance"].__setitem__("acceptedRepairCandidateTree", "0" * 40)),
        ("accepted_repair_seal_drift", lambda c: c["repairApprovalProvenance"]["acceptedRepairSeal"].__setitem__(
            "tests/verify_harness_demo_absorption.py", "0" * 64)),
        ("missing_security_repair_approval",
         lambda c: c.__setitem__("securityRepairApprovalProvenance", {})),
        ("security_repair_scope_expansion",
         lambda c: c["securityRepairApprovalProvenance"]["allowedChangedPaths"].append(
             "skills/_shared/itd_fresh_session_worktree.py")),
        ("legacy_unbound_isolation_fixture",
         lambda c: c["thresholds"]["sealedIsolationFixture"].__setitem__(
             "legacyFourFieldPacketAllowed", True)),
    ]
    for label, mutate in mutations:
        expect_rejected(contract, mutate, label)
    return len(mutations)


def validate_strategy_docs() -> None:
    adr = ADR.read_text(encoding="utf-8")
    plan = PLAN.read_text(encoding="utf-8")
    backlog = BACKLOG.read_text(encoding="utf-8")
    require("Status:** Accepted" in adr and "Review date:** 2026-08-30" in adr,
            "ADR-004 must be accepted and carry its review date")
    require("## Block I — Harness-demo UX absorption" in plan,
            "LAUNCH_PLAN must contain the accepted implementation block")
    require(all(f"HDX-{number:03d}" in plan for number in range(1, 15)),
            "LAUNCH_PLAN must bind every implementation unit")
    require("## Icebox / rejected" in backlog and "Ralph" in backlog,
            "BACKLOG must preserve the rejected mechanisms")


def validate_public_skill_population(contract: dict) -> None:
    definition = (contract.get("thresholds") or {}).get(
        "publicLifecycleSkills") or {}
    skills_root = ROOT / str(definition.get("root") or "")
    prefix = definition.get("reservedNamePrefix")
    require(skills_root.is_dir() and isinstance(prefix, str) and prefix,
            "public lifecycle skill root or reserved-name rule is invalid")
    all_skill_dirs = sorted(
        path.name for path in skills_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    )
    reserved = sorted(name for name in all_skill_dirs if name.startswith(prefix))
    public = sorted(name for name in all_skill_dirs if not name.startswith(prefix))
    require(reserved == definition.get("reservedSkillDirectories"),
            "reserved skill directory population drifted")
    require(public == definition.get("baselineNames")
            and len(public) == definition.get("baseline"),
            "actual public lifecycle skill population drifted from the frozen baseline")
    require(len(public) - int(definition.get("baseline")) ==
            (contract.get("thresholds") or {}).get("publicLifecycleSkillDelta") == 0,
            "actual public lifecycle skill delta is not zero")


def validate_accepted_repair(contract: dict) -> None:
    repair = contract.get("repairApprovalProvenance") or {}
    base_tree = str(repair.get("baseCandidateTree") or "")
    accepted_tree = str(repair.get("acceptedRepairCandidateTree") or "")
    delta = run([
        "git", "diff", "--name-only", base_tree, accepted_tree, "--",
    ])
    require_exit(delta, 0, "historical v2 repair delta")
    observed = [row for row in delta.stdout.splitlines() if row]
    require(observed == repair.get("allowedChangedPaths"),
            "historical v2 repair delta exceeds or misses the approved paths")
    seal = repair.get("acceptedRepairSeal") or {}
    require(set(seal) == set(observed),
            "historical v2 repair seal inventory is incomplete")
    for relative in observed:
        try:
            result = subprocess.run(
                ["git", "show", f"{accepted_tree}:{relative}"],
                cwd=str(ROOT), capture_output=True, timeout=120)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ContractError(
                f"cannot read historical v2 repair blob {relative}: {exc}") from exc
        require(result.returncode == 0
                and hashlib.sha256(result.stdout).hexdigest() == seal.get(relative),
                f"historical v2 repair blob seal mismatch: {relative}")


def validate_context() -> None:
    runner = ROOT / "skills" / "adopt" / "scripts" / "itd_context_map.py"
    require(runner.is_file(),
            "context generator is missing")
    template = ROOT / "docs" / "templates" / "itd" / "AGENT_CONTEXT_CONTRACT.json"
    require(template.is_file(),
            "context contract template is missing")
    with tempfile.TemporaryDirectory(prefix="itd-context-") as raw:
        fixture = pathlib.Path(raw)
        (fixture / ".itd").mkdir()
        (fixture / ".itd" / "PROJECT_CONTRACT.md").write_text(
            "# Project contract\n\nObserved project rules remain authoritative.\n", encoding="utf-8")
        (fixture / "src").mkdir()
        (fixture / "tests").mkdir()
        (fixture / "pyproject.toml").write_text(
            "[project]\nname='ledger-service'\nversion='0.1.0'\n"
            "[tool.pytest.ini_options]\ntestpaths=['tests']\n", encoding="utf-8")
        (fixture / "src" / "ledger.py").write_text(
            '"""Ledger service."""\n\ndef reconcile(invoice_id: str) -> bool:\n    return bool(invoice_id)\n',
            encoding="utf-8")
        (fixture / "tests" / "test_ledger.py").write_text(
            "from src.ledger import reconcile\n\ndef test_reconcile():\n    assert reconcile('INV-42')\n",
            encoding="utf-8")
        before_itd = hashlib.sha256(
            (fixture / ".itd" / "PROJECT_CONTRACT.md").read_bytes()).hexdigest()
        plan = run([sys.executable, str(runner), "plan", "--root", str(fixture)])
        require_exit(plan, 0, "context plan")
        require(not (fixture / "docs" / "agent-context").exists(),
                "context plan must not write generated views")
        denied = run([sys.executable, str(runner), "apply", "--root", str(fixture)])
        require(denied.returncode != 0, "context apply without --approved must fail")
        applied = run([sys.executable, str(runner), "apply", "--root", str(fixture), "--approved"])
        require_exit(applied, 0, "approved context apply")
        index_path = fixture / "docs" / "agent-context" / "index.json"
        index = load_json(index_path)
        require(index.get("authority") == "derived-non-normative",
                "context index must declare derived authority")
        claims = index.get("claims") or []
        require(claims, "context index must contain source-backed claims")
        for claim in claims:
            require(set(claim) >= {"id", "topic", "condition", "value", "sourcePath",
                                   "sourceSha256", "trustClass"},
                    "each context claim must carry applicability, provenance, and trust")
            source = fixture / claim["sourcePath"]
            require(source.is_file() and source.resolve().is_relative_to(fixture.resolve()),
                    "context claim source must stay inside the project")
            require(hashlib.sha256(source.read_bytes()).hexdigest() == claim["sourceSha256"],
                    "context claim source hash mismatch")
            require(claim["trustClass"] == "observed",
                    "unapproved inferred/domain context cannot be auto-generated")
        first_bytes = {
            path.relative_to(fixture).as_posix(): path.read_bytes()
            for path in (fixture / "docs" / "agent-context").rglob("*") if path.is_file()
        }
        repeated = run([sys.executable, str(runner), "apply", "--root", str(fixture), "--approved"])
        require_exit(repeated, 0, "idempotent context apply")
        second_bytes = {
            path.relative_to(fixture).as_posix(): path.read_bytes()
            for path in (fixture / "docs" / "agent-context").rglob("*") if path.is_file()
        }
        require(first_bytes == second_bytes, "repeated context generation must be byte-idempotent")
        require(hashlib.sha256(
            (fixture / ".itd" / "PROJECT_CONTRACT.md").read_bytes()).hexdigest() == before_itd,
            "derived context generation must not modify authoritative .itd contracts")
        valid = run([sys.executable, str(runner), "validate", "--root", str(fixture)])
        require_exit(valid, 0, "fresh context validation")
        (fixture / "src" / "ledger.py").write_text("# stale source\n", encoding="utf-8")
        stale = run([sys.executable, str(runner), "validate", "--root", str(fixture)])
        require(stale.returncode != 0, "stale source hash must fail context validation")
        index["claims"][0]["sourcePath"] = "../outside.py"
        index_path.write_text(json.dumps(index), encoding="utf-8")
        escaped = run([sys.executable, str(runner), "validate", "--root", str(fixture)])
        require(escaped.returncode != 0, "out-of-root context source must fail closed")


def validate_facade() -> None:
    manifest = ROOT / "docs" / "examples" / "brownfield-piv" / "manifest.json"
    require(manifest.is_file(),
            "captured brownfield run manifest is missing")
    task = (ROOT / "skills" / "task" / "SKILL.md").read_text(encoding="utf-8")
    require("PIV-lite" in task and all(stage in task for stage in
                                      ("Plan", "Implement", "Validate", "Review")),
            "existing /task does not expose all four PIV-lite stages")
    validate_public_skill_population(load_json(CONTRACT))
    route = load_json(ROOT / "skills" / "task" / "PIV_LITE_ROUTE.json")
    require(route.get("publicLifecycleSkillDelta") == 0
            and route.get("stateAuthority") == [".itd", ".itd-memory"]
            and route.get("completionAuthority") == "verification-loop-v1",
            "PIV-lite route must reuse ITD state and completion authority")
    require([row.get("id") for row in (route.get("stages") or [])] ==
            ["plan", "implement", "validate", "review"],
            "PIV-lite route must preserve the four-stage envelope")
    risks = route.get("riskRoutes") or {}
    require(set(risks) == {"low", "medium", "high"}
            and risks["low"].get("checker") == "machine-only"
            and risks["medium"].get("checker") == "targeted-fresh-session"
            and risks["high"].get("checker") == "different-provider-full",
            "PIV-lite risk routing must remain proportional and fail closed")
    captured = load_json(manifest)
    require(captured.get("externalAdoptionEvidence") is False,
            "internal captured run cannot claim external adoption")
    bindings = captured.get("bindings") or {}
    require(set(bindings) >= {"candidateTree", "ticketSha256", "contextSha256",
                              "taskContractSha256", "patchSha256", "machineReceiptSha256",
                              "checkerReceiptSha256", "adjudicationReceiptSha256",
                              "reviewReportSha256", "metricsSha256"},
            "captured run does not bind every load-bearing artifact")
    example_root = manifest.parent.resolve()
    artifacts = captured.get("artifacts") or {}
    require(isinstance(artifacts, dict) and artifacts,
            "captured run must enumerate its replay artifacts")
    for relative, expected_hash in artifacts.items():
        artifact = (example_root / relative).resolve()
        require(artifact.is_relative_to(example_root) and artifact.is_file(),
                f"captured artifact escapes or is missing: {relative}")
        require(hashlib.sha256(artifact.read_bytes()).hexdigest() == expected_hash,
                f"captured artifact hash mismatch: {relative}")
    candidate_tree = bindings.get("candidateTree") or ""
    require(len(candidate_tree) == 40
            and all(char in "0123456789abcdef" for char in candidate_tree),
            "captured candidateTree must be a full Git tree id")
    binding_artifacts = captured.get("bindingArtifacts") or {}
    hash_bindings = set(bindings) - {"candidateTree"}
    require(set(binding_artifacts) == hash_bindings,
            "every named captured binding must map to exactly one artifact path")
    for binding in hash_bindings:
        relative = binding_artifacts[binding]
        require(relative in artifacts and bindings[binding] == artifacts[relative],
                f"captured binding {binding} is not bound to its named artifact")
    machine = load_json(example_root / binding_artifacts["machineReceiptSha256"])
    checker = load_json(example_root / binding_artifacts["checkerReceiptSha256"])
    adjudication = load_json(
        example_root / binding_artifacts["adjudicationReceiptSha256"])
    require(machine.get("kind") == "machine-verification"
            and checker.get("kind") == "checker"
            and adjudication.get("kind") == "adjudication",
            "captured receipt kinds are invalid")
    require(all(receipt_self_digest_valid(receipt)
                for receipt in (machine, checker, adjudication)),
            "captured receipt self-digest is invalid")
    unit_ids = {machine.get("unitId"), checker.get("unitId"),
                adjudication.get("unitId")}
    risk_tiers = {machine.get("riskTier"), checker.get("riskTier"),
                  adjudication.get("riskTier")}
    receipt_trees = {
        (receipt.get("candidate") or {}).get("reviewedTree")
        for receipt in (machine, checker, adjudication)
    }
    require(len(unit_ids) == 1 and None not in unit_ids
            and len(risk_tiers) == 1 and None not in risk_tiers
            and receipt_trees == {candidate_tree},
            "captured receipts must bind one unit, risk tier, and candidate tree")
    require(machine.get("verdict") == "PASSED"
            and checker.get("verdict") == "PASSED"
            and adjudication.get("outcome") == "PASSED",
            "captured receipts must all carry passing verdicts")
    dependencies = adjudication.get("dependencies") or {}
    require((dependencies.get("machine") or {}).get("sha256") ==
            bindings["machineReceiptSha256"]
            and (dependencies.get("checker") or {}).get("sha256") ==
            bindings["checkerReceiptSha256"],
            "captured adjudication must hash-bind the named machine and checker receipts")
    replay = captured.get("replay") or {}
    before_dir = (example_root / str(replay.get("beforeDir") or "")).resolve()
    patch = (example_root / str(replay.get("patch") or "")).resolve()
    require(before_dir.is_relative_to(example_root) and before_dir.is_dir()
            and patch.is_relative_to(example_root) and patch.is_file(),
            "captured replay inputs are missing or escape the example")
    commands = replay.get("commands") or []
    require(commands and all(isinstance(command, list) and command
                             and all(isinstance(arg, str) for arg in command)
                             for command in commands),
            "captured replay commands must be explicit argv arrays")
    with tempfile.TemporaryDirectory(prefix="itd-piv-replay-") as raw:
        fixture = pathlib.Path(raw) / "project"
        shutil.copytree(before_dir, fixture)
        before_results = [
            run([sys.executable if arg == "{python}" else arg for arg in command],
                cwd=fixture, timeout=120)
            for command in commands
        ]
        require(any(result.returncode != 0 for result in before_results),
                "captured patch must repair an observable failing command")
        require_exit(run(["git", "init", "-q"], cwd=fixture), 0,
                     "captured replay git init")
        require_exit(run(["git", "config", "user.email", "fixture@example.invalid"],
                         cwd=fixture), 0, "captured replay git email")
        require_exit(run(["git", "config", "user.name", "ITD Fixture"],
                         cwd=fixture), 0, "captured replay git name")
        base_tracked_paths = replay.get("baseTrackedPaths") or []
        require(base_tracked_paths and all(isinstance(item, str) and item
                                           and not pathlib.PurePosixPath(item).is_absolute()
                                           and ".." not in pathlib.PurePosixPath(item).parts
                                           for item in base_tracked_paths),
                "captured replay must declare exact base paths")
        require_exit(run(["git", "add", "--", *base_tracked_paths], cwd=fixture), 0,
                     "captured replay base stage")
        require_exit(run(["git", "commit", "-qm", "captured base"], cwd=fixture), 0,
                     "captured replay base commit")
        applied = run(["git", "apply", "--check", str(patch)], cwd=fixture)
        require_exit(applied, 0, "captured patch preflight")
        applied = run(["git", "apply", str(patch)], cwd=fixture)
        require_exit(applied, 0, "captured patch application")
        for index, command in enumerate(commands):
            replayed = run([sys.executable if arg == "{python}" else arg for arg in command],
                           cwd=fixture, timeout=120)
            require_exit(replayed, 0, f"captured replay command {index}")
        tracked_paths = replay.get("trackedPaths") or []
        require(tracked_paths and all(isinstance(item, str) and item
                                      and not pathlib.PurePosixPath(item).is_absolute()
                                      and ".." not in pathlib.PurePosixPath(item).parts
                                      for item in tracked_paths),
                "captured replay must declare exact staged paths")
        require_exit(run(["git", "add", "--", *tracked_paths], cwd=fixture), 0,
                     "captured replay exact stage")
        replayed_tree = run(["git", "write-tree"], cwd=fixture)
        require_exit(replayed_tree, 0, "captured replay tree")
        require(replayed_tree.stdout.strip() == candidate_tree,
                "captured receipts must bind the exact filesystem tree produced by replay")
        unit_id = str(machine["unitId"])
        risk_tier = str(machine["riskTier"])
        require(risk_tier == "medium",
                "captured brownfield example must use the targeted medium-risk route")
        loop = ROOT / "skills" / "_shared" / "itd_verification_loop.py"
        machine_command = " ".join(
            shlex.quote(sys.executable if arg == "{python}" else arg)
            for arg in commands[-1])
        live_machine = run([
            sys.executable, str(loop), "machine", "--root", str(fixture),
            "--unit-id", unit_id, "--risk-tier", risk_tier,
            "--command", f"captured-replay={machine_command}",
        ], timeout=300)
        require_exit(live_machine, 0, "canonical captured machine replay")
        live_machine_path = pathlib.Path(live_machine.stdout.strip())
        evidence_root = fixture / ".itd-memory" / "verification-loop"
        report = evidence_root / "reports" / "captured-replay.md"
        prompt = evidence_root / "prompts" / "captured-replay.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        prompt.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({
            "verdict": "PASSED", "findings": [], "unverified": []}),
            encoding="utf-8")
        prompt.write_text(
            "Independently verify the captured replay tree and its declared repair.\n",
            encoding="utf-8")
        live_checker = run([
            sys.executable, str(loop), "checker", "--root", str(fixture),
            "--unit-id", unit_id, "--risk-tier", risk_tier, "--mode", "targeted",
            "--report", str(report), "--prompt-file", str(prompt),
            "--maker-provider", "fixture", "--maker-model", "fixture-maker",
            "--maker-session", "captured-maker-session",
            "--checker-provider", "fixture", "--checker-model", "fixture-checker",
            "--checker-session", "captured-checker-session",
        ], timeout=120)
        require_exit(live_checker, 0, "canonical captured checker replay")
        live_checker_path = pathlib.Path(live_checker.stdout.strip())
        live_adjudication = run([
            sys.executable, str(loop), "adjudicate", "--root", str(fixture),
            "--unit-id", unit_id, "--risk-tier", risk_tier,
            "--machine", str(live_machine_path), "--checker", str(live_checker_path),
        ], timeout=120)
        require_exit(live_adjudication, 0, "canonical captured adjudication replay")
        live_receipt_path = pathlib.Path(live_adjudication.stdout.strip())
        canonical_check = run([
            sys.executable, str(loop), "check", "--root", str(fixture),
            "--unit-id", unit_id, "--risk-tier", risk_tier,
            "--receipt", str(live_receipt_path),
        ])
        require_exit(canonical_check, 0, "canonical captured receipt check")


def validate_diagnostics() -> None:
    runner = ROOT / "skills" / "_shared" / "itd_incremental_diagnostics.py"
    require(runner.is_file(),
            "incremental diagnostic runner is missing")
    template = ROOT / "docs" / "templates" / "itd" / "INCREMENTAL_DIAGNOSTICS_CONTRACT.json"
    require(template.is_file(),
            "incremental diagnostic project contract is missing")
    with tempfile.TemporaryDirectory(prefix="itd-diagnostics-") as raw:
        fixture = pathlib.Path(raw)
        changed = fixture / "changed.py"
        changed.write_text("value = 1\n", encoding="utf-8")
        disabled = run([sys.executable, str(runner), "run", "--root", str(fixture),
                        "--contract", str(template), "--changed", str(changed)])
        require_exit(disabled, 0, "default-off diagnostic probe")
        disabled_result = json.loads(disabled.stdout)
        require(disabled_result.get("status") == "disabled"
                and disabled_result.get("commandExecuted") is False,
                "incremental diagnostics must be disabled by default")
        argv_probe = fixture / "argv_probe.py"
        argv_probe.write_text(
            "import json, pathlib, sys\n"
            "pathlib.Path('argv.json').write_text(json.dumps(sys.argv[1:]))\n",
            encoding="utf-8")
        enabled_contract = load_json(template)
        enabled_contract["enabled"] = True
        enabled_contract["commands"] = [[sys.executable, str(argv_probe),
                                         "literal;touch", "SHOULD_NOT_EXIST"]]
        enabled_path = fixture / "diagnostics.json"
        enabled_path.write_text(json.dumps(enabled_contract), encoding="utf-8")
        enabled = run([sys.executable, str(runner), "run", "--root", str(fixture),
                       "--contract", str(enabled_path), "--changed", str(changed)])
        require_exit(enabled, 0, "opt-in diagnostic probe")
        enabled_result = json.loads(enabled.stdout)
        require(enabled_result.get("status") == "completed"
                and enabled_result.get("advisory") is True
                and enabled_result.get("completionEvidence") is False,
                "opt-in diagnostic result must remain advisory")
        require(json.loads((fixture / "argv.json").read_text(encoding="utf-8")) ==
                ["literal;touch", "SHOULD_NOT_EXIST"]
                and not (fixture / "SHOULD_NOT_EXIST").exists(),
                "diagnostic commands must execute as argv without shell interpolation")
    results = load_json(ROOT / "docs" / "diagnostics-pilot" / "RESULTS.json")
    require(results.get("measurement") == "host-observed",
            "diagnostic pilot latency must be host-observed")
    require(results.get("baseline") == "same project checks without incremental diagnostics"
            and results.get("treatment") == "same project checks with the opt-in incremental profile",
            "diagnostic pilot does not use the frozen A/B pairing")
    runs = results.get("labeledRuns") or []
    baseline_runs = [row for row in runs if row.get("arm") == "baseline"]
    treatment_runs = [row for row in runs if row.get("arm") == "treatment"]
    require(len(treatment_runs) >= 30 and len(baseline_runs) == len(treatment_runs),
            "diagnostic promotion requires at least 30 paired labeled runs per arm")
    baseline_pairs = {row.get("pairId") for row in baseline_runs}
    treatment_pairs = {row.get("pairId") for row in treatment_runs}
    require(None not in baseline_pairs and baseline_pairs == treatment_pairs
            and len(baseline_pairs) == len(baseline_runs),
            "diagnostic A/B runs must have unique one-to-one pair ids")
    emissions = [
        emission
        for row in treatment_runs
        for emission in (row.get("emissions") or [])
    ]
    require(len(emissions) >= 30
            and all(row.get("humanLabel") in {"actionable", "nonactionable"}
                    for row in emissions),
            "diagnostic noise decision requires 30 human-labeled emissions")
    false_noise = [row for row in emissions
                   if row.get("humanLabel") == "nonactionable"]
    ratio = len(false_noise) / len(emissions)
    latencies = sorted(int(row["latencyMs"]) for row in treatment_runs)
    median = statistics.median(latencies)
    p95 = latencies[max(0, (95 * len(latencies) + 99) // 100 - 1)]
    require(median <= 2000 and p95 <= 5000 and ratio <= 0.1,
            "diagnostic pilot exceeds the frozen latency/noise thresholds")
    require(all(row.get("completionEvidence") is False for row in treatment_runs),
            "incremental diagnostics cannot become completion evidence")


def validate_isolation_fixture() -> None:
    recipes = load_json(ROOT / "skills" / "_shared" / "OPERATING_LOOP_RECIPES.json")
    require(any(row.get("id") == "fresh-session-worktree"
                for row in (recipes.get("recipes") or [])),
            "fresh-session worktree recipe is missing")
    runner = ROOT / "skills" / "_shared" / "itd_fresh_session_worktree.py"
    require(runner.is_file(), "fresh-session worktree runner is missing")
    with tempfile.TemporaryDirectory(prefix="itd-worktree-") as raw:
        fixture = pathlib.Path(raw) / "main"
        fixture.mkdir()
        require_exit(run(["git", "init", "-q"], cwd=fixture), 0, "pilot fixture git init")
        require_exit(run(["git", "config", "user.email", "fixture@example.invalid"],
                         cwd=fixture), 0, "pilot fixture git email")
        require_exit(run(["git", "config", "user.name", "ITD Fixture"],
                         cwd=fixture), 0, "pilot fixture git name")
        (fixture / "tracked.txt").write_text("base\n", encoding="utf-8")
        require_exit(run(["git", "add", "tracked.txt"], cwd=fixture), 0,
                     "pilot fixture stage")
        require_exit(run(["git", "commit", "-qm", "base"], cwd=fixture), 0,
                     "pilot fixture commit")
        base = run(["git", "rev-parse", "HEAD"], cwd=fixture).stdout.strip()
        state_path = fixture / ".itd-memory" / "STATE.json"
        state_path.parent.mkdir()
        state = {
            "version": 1,
            "currentUnit": {
                "id": "HDX-FIXTURE",
                "status": "in_progress",
                "riskTier": "high",
            },
            "wip": 1,
        }
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n",
            encoding="utf-8")
        packet = {
            "version": 1,
            "kind": "fresh-session-unit-packet",
            "unitId": "HDX-FIXTURE",
            "baseCommit": base,
            "allowedPaths": ["tracked.txt"],
            "mutableResources": ["workspace"],
            "sharedMutableResources": [],
            "parentState": {
                "path": ".itd-memory/STATE.json",
                "sha256": hashlib.sha256(state_path.read_bytes()).hexdigest(),
            },
        }
        packet_path = pathlib.Path(raw) / "packet.json"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        worktree = pathlib.Path(raw) / "isolated"
        prepared = run([sys.executable, str(runner), "prepare", "--root", str(fixture),
                        "--packet", str(packet_path), "--worktree", str(worktree)],
                       timeout=120)
        require_exit(prepared, 0, "fresh-session worktree prepare")
        session = json.loads(prepared.stdout)
        require(session.get("stateOwner") == "parent"
                and session.get("sharedMutableFallbacks") == 0
                and session.get("unitId") == "HDX-FIXTURE"
                and session.get("packetSha256") ==
                hashlib.sha256(packet_path.read_bytes()).hexdigest()
                and session.get("parentStateSha256") ==
                hashlib.sha256(state_path.read_bytes()).hexdigest()
                and set(session.get("mutableNamespaces") or {}) == {"workspace"}
                and session.get("fixtureCompatibility") is False
                and session.get("syntheticParentState") is False,
                "fresh-session packet must keep parent-owned state and zero fallback")
        isolated_head = run(["git", "rev-parse", "HEAD"], cwd=worktree).stdout.strip()
        main_head = run(["git", "rev-parse", "HEAD"], cwd=fixture).stdout.strip()
        require(isolated_head == base == main_head,
                "fresh session must start from the immutable packet base")
        packet["sharedMutableResources"] = ["database:shared"]
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        denied = run([sys.executable, str(runner), "prepare", "--root", str(fixture),
                      "--packet", str(packet_path),
                      "--worktree", str(pathlib.Path(raw) / "denied")])
        require(denied.returncode != 0,
                "unisolated mutable resources must fail closed")


def validate_isolation() -> None:
    validate_isolation_fixture()
    pilot = ROOT / "docs" / "harness-demo-pilots" / "INDEX.json"
    evidence = load_json(pilot)
    episodes = evidence.get("episodes") or []
    require(len(episodes) == 3 and all(row.get("status") == "passed" for row in episodes),
            "three passing real brownfield pilot episodes are required")
    require(all(row.get("externalAdoptionEvidence") is False for row in episodes),
            "internal pilots cannot claim external adoption")
    for field in ("unitId", "sessionId"):
        values = [row.get(field) for row in episodes]
        require(None not in values and len(set(values)) == 3,
                f"pilot episodes must use three distinct {field} values")
    canonical_roots: list[pathlib.Path] = []
    common_dirs: list[pathlib.Path] = []
    checker = ROOT / "skills" / "_shared" / "itd_verification_loop.py"
    for row in episodes:
        require(row.get("projectRoot") and row.get("worktreeRoot")
                and row.get("unitId") and row.get("sessionId")
                and row.get("packet") and row.get("sessionArtifact")
                and row.get("parentStateSnapshot"),
                "pilot episode lacks project/worktree/unit/session provenance")
        project_root = pathlib.Path(row["projectRoot"]).resolve()
        top_level = run(["git", "rev-parse", "--show-toplevel"], cwd=project_root)
        require_exit(top_level, 0, f"pilot project root {project_root}")
        canonical_root = pathlib.Path(top_level.stdout.strip()).resolve()
        require(project_root == canonical_root,
                "pilot projectRoot must be the canonical Git top-level")
        canonical_roots.append(canonical_root)
        common_dir_result = run(["git", "rev-parse", "--git-common-dir"],
                                cwd=canonical_root)
        require_exit(common_dir_result, 0, f"pilot common dir {canonical_root}")
        common_dir = pathlib.Path(common_dir_result.stdout.strip())
        if not common_dir.is_absolute():
            common_dir = canonical_root / common_dir
        common_dir = common_dir.resolve()
        common_dirs.append(common_dir)
        worktree_root = pathlib.Path(row["worktreeRoot"]).resolve()
        worktree_top = run(["git", "rev-parse", "--show-toplevel"], cwd=worktree_root)
        require_exit(worktree_top, 0, f"pilot worktree root {worktree_root}")
        require(pathlib.Path(worktree_top.stdout.strip()).resolve() == worktree_root
                and worktree_root != canonical_root,
                "pilot worktree must be a distinct canonical Git worktree")
        worktree_common_result = run(["git", "rev-parse", "--git-common-dir"],
                                     cwd=worktree_root)
        require_exit(worktree_common_result, 0, f"pilot worktree common dir {worktree_root}")
        worktree_common = pathlib.Path(worktree_common_result.stdout.strip())
        if not worktree_common.is_absolute():
            worktree_common = worktree_root / worktree_common
        require(worktree_common.resolve() == common_dir,
                "pilot worktree must belong to its declared project repository")
        packet_path = pathlib.Path(row["packet"])
        if not packet_path.is_absolute():
            packet_path = worktree_root / packet_path
        session_path = pathlib.Path(row["sessionArtifact"])
        if not session_path.is_absolute():
            session_path = worktree_root / session_path
        state_snapshot_path = pathlib.Path(row["parentStateSnapshot"])
        if not state_snapshot_path.is_absolute():
            state_snapshot_path = worktree_root / state_snapshot_path
        packet = load_json(packet_path)
        session = load_json(session_path)
        state_snapshot = load_json(state_snapshot_path)
        packet_hash = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        session_hash = hashlib.sha256(session_path.read_bytes()).hexdigest()
        state_snapshot_hash = hashlib.sha256(state_snapshot_path.read_bytes()).hexdigest()
        require(row.get("packetSha256") == packet_hash
                and row.get("sessionArtifactSha256") == session_hash,
                "pilot episode must hash-bind its packet and session artifact")
        require(packet.get("unitId") == row["unitId"]
                and packet.get("sharedMutableResources") == []
                and session.get("unitId") == row["unitId"]
                and session.get("sessionId") == row["sessionId"]
                and session.get("packetSha256") == packet_hash
                and session.get("stateOwner") == "parent"
                and session.get("sharedMutableFallbacks") == 0,
                "pilot isolation packet/session contract is inconsistent")
        require(session.get("parentStateSha256") == state_snapshot_hash
                and (state_snapshot.get("currentUnit") or {}).get("id") == row["unitId"]
                and (state_snapshot.get("currentUnit") or {}).get("status") == "in_progress",
                "pilot session must bind an in-progress parent-owned state snapshot")
        worktree_git_result = run(["git", "rev-parse", "--git-dir"], cwd=worktree_root)
        require_exit(worktree_git_result, 0, f"pilot worktree git dir {worktree_root}")
        worktree_git_dir = pathlib.Path(worktree_git_result.stdout.strip())
        if not worktree_git_dir.is_absolute():
            worktree_git_dir = worktree_root / worktree_git_dir
        require(pathlib.Path(session.get("worktreeRoot") or "").resolve() == worktree_root
                and pathlib.Path(session.get("worktreeGitDir") or "").resolve() ==
                worktree_git_dir.resolve(),
                "pilot session artifact must bind the exact linked worktree identity")
        namespaces = session.get("mutableNamespaces")
        resources = packet.get("mutableResources") or []
        validate_mutable_namespaces(resources, namespaces, row["sessionId"])
        require(session.get("namespaceManifestSha256") ==
                hashlib.sha256(json.dumps(
                    namespaces, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":")).encode("utf-8")).hexdigest(),
                "pilot mutable resources must have session-scoped hash-bound namespaces")
        receipt_path = pathlib.Path(row.get("adjudicationReceipt") or "")
        if not receipt_path.is_absolute():
            receipt_path = worktree_root / receipt_path
        require(receipt_path.is_file(), "pilot adjudication receipt is missing")
        checked = run([sys.executable, str(checker), "check", "--root",
                       str(worktree_root), "--unit-id", row["unitId"],
                       "--risk-tier", row.get("riskTier") or "medium",
                       "--receipt", str(receipt_path)])
        require_exit(checked, 0, f"pilot receipt {row.get('unitId')}")
        adjudication = load_json(receipt_path)
        machine_dependency = (adjudication.get("dependencies") or {}).get("machine") or {}
        machine_path = pathlib.Path(machine_dependency.get("path") or "")
        if not machine_path.is_absolute():
            machine_path = worktree_root / machine_path
        machine_receipt = load_json(machine_path)
        require(machine_dependency.get("sha256") ==
                hashlib.sha256(machine_path.read_bytes()).hexdigest(),
                "pilot adjudication machine dependency hash mismatch")
        declared_inputs = {
            item.get("path"): item.get("sha256")
            for item in (machine_receipt.get("declaredInputs") or [])
        }
        require(packet_path.resolve().is_relative_to(worktree_root)
                and session_path.resolve().is_relative_to(worktree_root)
                and state_snapshot_path.resolve().is_relative_to(worktree_root),
                "pilot isolation artifacts must stay inside the worktree")
        packet_relative = packet_path.resolve().relative_to(worktree_root).as_posix()
        session_relative = session_path.resolve().relative_to(worktree_root).as_posix()
        state_relative = state_snapshot_path.resolve().relative_to(worktree_root).as_posix()
        require(declared_inputs.get(packet_relative) == packet_hash
                and declared_inputs.get(session_relative) == session_hash
                and declared_inputs.get(state_relative) == state_snapshot_hash,
                "pilot machine receipt must bind packet, worker session, and parent state")
        candidate = machine_receipt.get("candidate") or {}
        require(packet.get("baseCommit") == candidate.get("baseCommit")
                and session.get("candidateTree") == candidate.get("reviewedTree"),
                "pilot packet/session must bind the machine receipt candidate")
        checker_dependency = (adjudication.get("dependencies") or {}).get("checker") or {}
        checker_path = pathlib.Path(checker_dependency.get("path") or "")
        if not checker_path.is_absolute():
            checker_path = worktree_root / checker_path
        checker_receipt = load_json(checker_path)
        require(checker_dependency.get("sha256") ==
                hashlib.sha256(checker_path.read_bytes()).hexdigest(),
                "pilot adjudication checker dependency hash mismatch")
        checker_provenance = (checker_receipt.get("provenance") or {}).get("checker") or {}
        maker_provenance = (checker_receipt.get("provenance") or {}).get("maker") or {}
        require(checker_receipt.get("unitId") == row["unitId"]
                and pathlib.Path((checker_receipt.get("candidate") or {})
                                 .get("repository") or "").resolve() == worktree_root
                and maker_provenance.get("session") == row["sessionId"]
                and session.get("makerSession") == row["sessionId"]
                and checker_provenance.get("session") != row["sessionId"],
                "pilot worktree, unit, and maker session must match receipt provenance")
    require(len(set(canonical_roots)) == 3,
            "pilot evidence must come from three distinct canonical repositories")
    require(len(set(common_dirs)) == 3,
            "multiple worktrees of one repository count as one pilot project")


def validate_navigation() -> None:
    registry = load_json(ROOT / "docs" / "templates" / "itd" /
                         "TOOL_CAPABILITY_REGISTRY.json")
    navigation = next((row for row in (registry.get("tools") or [])
                       if row.get("id") == "semantic-navigation"), None)
    require(isinstance(navigation, dict), "semantic-navigation capability is missing")
    demand = navigation.get("demandGate") or {}
    require(demand.get("status") in {"activated", "not_activated"},
            "semantic-navigation demand gate must be explicit")
    if demand.get("status") == "activated":
        semantic = navigation.get("semanticNavigation") or {}
        require(set(semantic.get("languages") or []) >=
                {"python", "typescript"},
                "activated semantic navigation must cover Python and TypeScript")
        provider = ROOT / str(semantic.get("provider") or "")
        require(provider.is_file(), "activated semantic-navigation provider is missing")
        with tempfile.TemporaryDirectory(prefix="itd-navigation-") as raw:
            fixture = pathlib.Path(raw)
            (fixture / "sample.py").write_text(
                "def reconcile(value: str) -> bool:\n    return bool(value)\n\n"
                "result = reconcile('x')\n", encoding="utf-8")
            (fixture / "sample.ts").write_text(
                "export function reconcile(value: string): boolean { return !!value; }\n"
                "const result = reconcile('x');\n", encoding="utf-8")
            for language in ("python", "typescript"):
                operation_payloads: list[str] = []
                for operation in ("definitions", "references", "outline"):
                    result = run([sys.executable, str(provider), "--root", str(fixture),
                                  "--language", language, "--operation", operation,
                                  "--symbol", "reconcile"])
                    require_exit(result, 0, f"{language} {operation}")
                    payload = json.loads(result.stdout)
                    require(payload.get("semantic") is True
                            and payload.get("confidence") in {"high", "medium"}
                            and isinstance(payload.get("results"), list)
                            and payload.get("results"),
                            "semantic provider must return declared semantic results")
                    rows = payload["results"]
                    expected_path = f"sample.{ 'py' if language == 'python' else 'ts' }"
                    require(all(row.get("path") == expected_path for row in rows),
                            "semantic results must identify the queried language source")
                    if operation == "definitions":
                        require(any(row.get("kind") == "definition"
                                    and row.get("symbol") == "reconcile"
                                    and row.get("line") == 1 for row in rows),
                                "definition query must locate reconcile at line 1")
                    elif operation == "references":
                        expected_line = 4 if language == "python" else 2
                        require(any(row.get("kind") == "reference"
                                    and row.get("symbol") == "reconcile"
                                    and row.get("line") == expected_line for row in rows),
                                "reference query must locate the actual call site")
                    else:
                        symbols = {row.get("symbol") for row in rows
                                   if row.get("kind") == "symbol"}
                        require({"reconcile", "result"} <= symbols,
                                "outline query must return both declared symbols")
                    operation_payloads.append(json.dumps(rows, sort_keys=True))
                require(len(set(operation_payloads)) == 3,
                        "semantic definitions, references, and outline must be distinct")
            fallback = run([sys.executable, str(provider), "--root", str(fixture),
                            "--language", "text", "--operation", "references",
                            "--symbol", "reconcile"])
            require_exit(fallback, 0, "textual navigation fallback")
            payload = json.loads(fallback.stdout)
            require(payload.get("semantic") is False
                    and payload.get("confidence") == "textual",
                    "plain-text fallback must be honestly labeled non-semantic")
    else:
        require(navigation.get("semanticNavigation") in ({}, None),
                "not-activated navigation must not claim provider behavior")


PHASE_VALIDATORS: dict[str, Callable[[], None]] = {
    "context": validate_context,
    "facade": validate_facade,
    "diagnostics": validate_diagnostics,
    "isolation": validate_isolation,
    "navigation": validate_navigation,
}


def validate_phase(phase: str) -> None:
    validator = PHASE_VALIDATORS.get(phase)
    require(validator is not None, f"no behavioral validator is registered for phase {phase}")
    validator()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True,
                        choices=("contract", *PHASES[1:], "all"))
    parser.add_argument("--fixture-only", action="store_true")
    args = parser.parse_args()
    try:
        contract = load_json(CONTRACT)
        validate_contract_value(contract)
        validate_digest()
        guards = validate_mutations(contract)
        validate_public_skill_population(contract)
        validate_accepted_repair(contract)
        validate_isolation_refutations()
        validate_strategy_docs()
        if args.fixture_only:
            require(args.phase == "isolation",
                    "--fixture-only is valid only for the isolation phase")
            validate_isolation_fixture()
        elif args.phase == "all":
            for phase in PHASES[1:]:
                validate_phase(phase)
        elif args.phase != "contract":
            validate_phase(args.phase)
    except (ContractError, OSError) as exc:
        return fail(str(exc))
    print(json.dumps({"phase": args.phase, "mutationGuards": guards, "status": "PASSED"},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
