#!/usr/bin/env python3
"""Static release oracle for the v1.95 external-reviewer capability."""
from __future__ import annotations

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.95.0"
REQUIRED_FILES = {
    ".github/workflows/itd-machine-oracle.yml",
    "docs/API_REVIEWER.md",
    "docs/adr/ADR-003-verifiable-external-reviewer.md",
    "docs/api-reviewer/SHADOW_PILOT.json",
    "docs/api-reviewer/RELEASE_CONTRACT.json",
    "skills/_shared/EXTERNAL_REVIEW_POLICY.json",
    "skills/_shared/EXTERNAL_REVIEW_VERDICT_SCHEMA.json",
    "skills/_shared/itd_external_reviewer.py",
    "skills/_shared/REVIEW_BROKER_POLICY.json",
    "skills/_shared/REVIEW_BROKER_RUNTIME.schema.json",
    "skills/_shared/itd_review_broker_primitives.py",
    "skills/_shared/itd_review_broker.py",
    "services/review_broker/server.py",
    "scripts/itd.py",
    "scripts/itd_machine_oracle.py",
    "tests/verify_api_reviewer.py",
}
CRITERIA = {f"API-001-AC{number}" for number in range(1, 8)}


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def validate_contract(contract: dict, scope: str) -> list[str]:
    issues: list[str] = []
    if set(contract) != {
        "version", "purpose", "criteria", "scopeMarkers", "scopeEvidence",
        "completionAuthority",
    }:
        issues.append("release contract fields are not closed")
    rows = contract.get("criteria")
    if not isinstance(rows, list) or set(rows) != CRITERIA:
        issues.append("API-001 criteria are incomplete")
    if contract.get("version") != VERSION:
        issues.append("release contract version drift")
    if contract.get("completionAuthority") != "verification-loop-v1":
        issues.append("release contract completion authority drift")
    required_markers = {
        "Verification Loop",
        "same-model",
        "same-provider",
        "UNAVAILABLE",
        "UNVERIFIED",
        "silently truncated",
        "administrator mutation of the ruleset",
    }
    if set(contract.get("scopeMarkers") or []) != required_markers:
        issues.append("release scope marker set drift")
    for marker in required_markers:
        if marker not in scope:
            issues.append(f"scope omits: {marker}")
    return issues


def main() -> int:
    issues: list[str] = []
    manifests = [
        load(".claude-plugin/plugin.json"),
        load(".codex-plugin/plugin.json"),
        load(".claude-plugin/marketplace.json")["plugins"][0],
    ]
    if {row.get("version") for row in manifests} != {VERSION}:
        issues.append("plugin version drift")
    if f"## [{VERSION}] - 2026-07-30" not in (
            ROOT / "CHANGELOG.md").read_text(encoding="utf-8"):
        issues.append("dated release changelog is absent")
    for path in REQUIRED_FILES:
        if not (ROOT / path).is_file():
            issues.append(f"missing release file: {path}")
    acceptance = load("docs/api-reviewer/RELEASE_CONTRACT.json")
    scope_paths = acceptance.get("scopeEvidence") or []
    scope = "\n".join((ROOT / path).read_text(encoding="utf-8")
                      for path in scope_paths if (ROOT / path).is_file())
    if len(scope_paths) != 2:
        issues.append("release scope evidence set drift")
    issues.extend(validate_contract(acceptance, scope))
    policy = load("skills/_shared/EXTERNAL_REVIEW_POLICY.json")
    providers = [row.get("id") for row in policy.get("providers", [])]
    if providers != [
        "openai-responses", "openai-responses-terra",
        "codex-cli", "gemini-cli",
    ]:
        issues.append("provider set/order drift")
    eligibility = [row.get("automatedEligible") for row in policy.get("providers", [])]
    if eligibility != [True, True, False, False]:
        issues.append("unsafe automated-provider eligibility drift")
    if policy.get("completionAuthority") != "verification-loop-v1":
        issues.append("parallel completion authority")
    if any(policy.get("retention", {}).get(key) is not False for key in (
            "persistRawRequest", "persistRawResponse")):
        issues.append("raw provider payload retention enabled")
    run_all = (ROOT / "tests/run-all.sh").read_text(encoding="utf-8")
    if ("verify_external_reviewer_release" not in run_all
            or "verify_operating_loops_release" in run_all.split('CORE="', 1)[1].split('"', 1)[0]):
        issues.append("current suite still routes through the historical v1.94 release oracle")
    workflow = (
        ROOT / ".github/workflows/itd-machine-oracle.yml"
    ).read_text(encoding="utf-8")
    for marker in (
        "pull_request:",
        "merge_group:",
        "name: ITD machine oracle",
        "persist-credentials: false",
        "scripts/itd_machine_oracle.py",
        'OPENAI_API_KEY: ""',
    ):
        if marker not in workflow:
            issues.append(f"machine gate omits: {marker}")
    if (
        (ROOT / ".github/workflows/external-review-gate.yml").exists()
        or "repository_dispatch:" in workflow
        or "ITD_PROVENANCE_HMAC_KEY" in workflow
    ):
        issues.append("obsolete repository-secret API gate remains active")
    broker_policy = load("skills/_shared/REVIEW_BROKER_POLICY.json")
    if (
        broker_policy.get("authority", {}).get("externalReview")
        != "github-app-check-run"
        or broker_policy.get("provenance", {}).get("algorithm") != "ed25519"
        or broker_policy.get("routing", {}).get(
            "automatedCliFallbackAllowed"
        )
        is not False
    ):
        issues.append("central App/broker release authority drift")

    mutations = 0
    for mutation in ("provider", "authority", "scope"):
        mutant_policy = copy.deepcopy(policy)
        mutant_contract = copy.deepcopy(acceptance)
        mutant_scope = scope
        if mutation == "provider":
            mutant_policy["providers"].pop()
        elif mutation == "authority":
            mutant_policy["completionAuthority"] = "external-reviewer"
        else:
            mutant_scope = scope.replace("UNVERIFIED", "")
        rejected = (
            [row.get("id") for row in mutant_policy.get("providers", [])]
            != [
                "openai-responses", "openai-responses-terra",
                "codex-cli", "gemini-cli",
            ]
            or mutant_policy.get("completionAuthority") != "verification-loop-v1"
            or bool(validate_contract(mutant_contract, mutant_scope))
        )
        if not rejected:
            issues.append(f"mutation survived: {mutation}")
        mutations += 1

    if issues:
        print("FAIL external reviewer release")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(json.dumps({
        "status": "PASSED", "version": VERSION, "providers": providers,
        "criteria": len(CRITERIA), "requiredFiles": len(REQUIRED_FILES),
        "mutationGuards": mutations,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
