#!/usr/bin/env python3
"""Read-only validator for control provenance, tool trust, and hook output."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_TYPES = {"production_incident", "repeated_independent_signals", "hard_external_constraint"}
SOURCE_KINDS = {"independent_observation", "external_constraint"}
INCIDENT_EVIDENCE_PREFIXES = ("docs/retros/", "hooks/README.md#case-study")
CONSTRAINT_EVIDENCE_PREFIXES = (
    "docs/adr/", "docs/HARNESS_ENGINEERING_MAP.md", "docs/HARNESS_TRUST_POLICY.json",
)
DISPOSITIONS = {"allow", "ask", "abstain"}
REGISTRY_FIELDS = {"version", "purpose", "admissionPolicy", "controls"}
POLICY_FIELDS = {
    "allowedEvidenceTypes", "minimumIndependentSignals",
    "singleSignalAllowedOnlyFor", "prohibited", "decisionAuthority",
}
CONTROL_FIELDS = {
    "id", "component", "owner", "introducedBy", "assumption", "expectedBehavior",
    "enforcedBy", "verifiedBy", "reviewBy", "retireWhen", "disableEnv",
    "costAndNoiseEvidence",
}
INTRODUCED_FIELDS = {"type", "evidence", "failureClass"}
EVIDENCE_FIELDS = {"path", "signalId", "independenceKey", "sourceKind", "contentSha256"}
TOOL_REGISTRY_FIELDS = {"version", "purpose", "trustPolicy", "tools"}
TOOL_POLICY_FIELDS = {
    "promptBearingTypes", "allowedDisposition",
    "defaultForUnknownPromptBearingProvider", "allowRequires", "rules",
}
TOOL_FIELDS = {
    "id", "type", "usedBy", "capabilities", "sideEffects", "authNeeded",
    "externalDataRisk", "fallbackMode", "approvalRequiredFor", "trust",
}
TOOL_OPTIONAL_FIELDS = {"demandGate", "semanticNavigation"}
TRUST_FIELDS = {
    "provider", "source", "versionPosture", "integrity", "promptTextSurface",
    "promptTextReviewed", "permissions", "networkScope", "dataScope",
    "reviewedAt", "disposition", "reviewEvidence",
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: invalid or unreadable JSON: {exc}") from exc


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_date(value: Any) -> bool:
    try:
        dt.date.fromisoformat(str(value))
        return True
    except ValueError:
        return False


def local_ref(root: Path, reference: str) -> Path:
    return root / reference.split("#", 1)[0]


def validate_controls(root: Path, registry: dict[str, Any], ablation: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if set(registry) != REGISTRY_FIELDS:
        issues.append("control registry fields must match the closed schema")
    policy = registry.get("admissionPolicy") or {}
    if not isinstance(policy, dict) or set(policy) != POLICY_FIELDS:
        issues.append("control admission policy fields must match the closed schema")
    if set(policy.get("allowedEvidenceTypes") or []) != EVIDENCE_TYPES:
        issues.append("control admission evidence types drift")
    if policy.get("minimumIndependentSignals") != 2:
        issues.append("control admission must require two independent signals")
    if policy.get("decisionAuthority") != "human":
        issues.append("control lifecycle must preserve human decision authority")
    controls = registry.get("controls")
    if not isinstance(controls, list) or not controls:
        return issues + ["control registry has no controls"]
    by_id: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(controls):
        label = f"control[{index}]"
        if not isinstance(row, dict):
            issues.append(f"{label} is not an object")
            continue
        missing = CONTROL_FIELDS - set(row)
        if missing:
            issues.append(f"{label} missing {sorted(missing)}")
            continue
        if set(row) != CONTROL_FIELDS:
            issues.append(f"{label} fields must match the closed schema")
        control_id = str(row["id"])
        if control_id in by_id:
            issues.append(f"duplicate control id: {control_id}")
        by_id[control_id] = row
        introduced = row.get("introducedBy") or {}
        if not isinstance(introduced, dict) or set(introduced) != INTRODUCED_FIELDS:
            issues.append(f"{control_id}: introducedBy fields must match the closed schema")
        evidence_type = introduced.get("type")
        if evidence_type not in EVIDENCE_TYPES:
            issues.append(f"{control_id}: unearned evidence type")
        evidence = introduced.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            issues.append(f"{control_id}: durable trigger evidence missing")
        else:
            independence: set[str] = set()
            signal_ids: set[str] = set()
            for item in evidence:
                if not isinstance(item, dict):
                    issues.append(f"{control_id}: evidence must be a provenance object")
                    continue
                if set(item) != EVIDENCE_FIELDS:
                    issues.append(f"{control_id}: evidence fields must match the closed schema")
                ref = item.get("path")
                signal_id = item.get("signalId")
                key = item.get("independenceKey")
                source_kind = item.get("sourceKind")
                content_sha = item.get("contentSha256")
                if not all(nonempty(value) for value in (ref, signal_id, key, source_kind, content_sha)):
                    issues.append(f"{control_id}: evidence provenance is incomplete")
                    continue
                if source_kind not in SOURCE_KINDS:
                    issues.append(f"{control_id}: self-metric or unknown evidence source cannot earn admission")
                if evidence_type == "production_incident" and (
                    source_kind != "independent_observation"
                    or not str(ref).startswith(INCIDENT_EVIDENCE_PREFIXES)
                ):
                    issues.append(f"{control_id}: production incident evidence is not bound to an incident record")
                if evidence_type == "hard_external_constraint" and (
                    source_kind != "external_constraint"
                    or not str(ref).startswith(CONSTRAINT_EVIDENCE_PREFIXES)
                ):
                    issues.append(f"{control_id}: external constraint evidence is not bound to a policy/ADR record")
                if evidence_type == "repeated_independent_signals" and source_kind != "independent_observation":
                    issues.append(f"{control_id}: repeated signal evidence must be independent observations")
                if signal_id in signal_ids:
                    issues.append(f"{control_id}: duplicate signalId: {signal_id}")
                signal_ids.add(signal_id)
                independence.add(key)
                evidence_path = local_ref(root, ref)
                if not evidence_path.is_file():
                    issues.append(f"{control_id}: trigger evidence missing: {ref}")
                elif hashlib.sha256(evidence_path.read_bytes()).hexdigest() != content_sha:
                    issues.append(f"{control_id}: trigger evidence content hash drift: {ref}")
            minimum = int(policy.get("minimumIndependentSignals") or 2)
            if evidence_type == "repeated_independent_signals" and len(independence) < minimum:
                issues.append(f"{control_id}: repeated signal evidence is not independent")
        for field in ("assumption", "expectedBehavior", "retireWhen", "owner"):
            if not nonempty(row.get(field)):
                issues.append(f"{control_id}: {field} must be explicit")
        for field in ("enforcedBy", "verifiedBy", "costAndNoiseEvidence"):
            values = row.get(field)
            if not isinstance(values, list) or not values:
                issues.append(f"{control_id}: {field} must be non-empty")
                continue
            for ref in values:
                if not nonempty(ref) or not local_ref(root, ref).exists():
                    issues.append(f"{control_id}: {field} path missing: {ref}")
        if not valid_date(row.get("reviewBy")):
            issues.append(f"{control_id}: reviewBy must be an ISO date")
        elif dt.date.fromisoformat(str(row["reviewBy"])) < dt.date.today():
            issues.append(f"{control_id}: reviewBy is stale")
        disable = row.get("disableEnv")
        if not isinstance(disable, dict) or len(disable) != 1:
            issues.append(f"{control_id}: exactly one reversible disableEnv is required")
        if not local_ref(root, str(row.get("component") or "")).is_file():
            issues.append(f"{control_id}: component path is missing")
    candidates = ablation.get("candidates")
    if not isinstance(candidates, list):
        return issues + ["ablation candidates must be an array"]
    covered: set[str] = set()
    for row in candidates:
        if not isinstance(row, dict):
            issues.append("ablation candidate is not an object")
            continue
        control_id = row.get("controlId")
        if control_id not in by_id:
            issues.append(f"ablation candidate has unknown controlId: {control_id}")
            continue
        if control_id in covered:
            issues.append(f"duplicate ablation controlId: {control_id}")
        covered.add(control_id)
        control = by_id[control_id]
        if row.get("component") != control.get("component"):
            issues.append(f"{control_id}: ablation component drift")
        if row.get("disableEnv") != control.get("disableEnv"):
            issues.append(f"{control_id}: ablation disableEnv drift")
        if not isinstance(row.get("benchmarkCommands"), list) or not row["benchmarkCommands"]:
            issues.append(f"{control_id}: fixed ablation benchmark missing")
        else:
            for spec in row["benchmarkCommands"]:
                if (not isinstance(spec, dict)
                        or spec.get("metricParser") != "json_number"
                        or spec.get("metricField") != "score"
                        or not str(spec.get("command") or "").startswith(
                            "python3 benchmarks/harness-components/")):
                    issues.append(f"{control_id}: ablation must use a direct behavioral score")
    if len(covered) < 5:
        issues.append("bounded ablation pilot must cover at least five controls")
    return issues


def validate_ablation_discrimination(root: Path, ablation: dict[str, Any]) -> list[str]:
    """Run each fixed probe enabled and disabled; disabled must lose behavior."""
    issues: list[str] = []
    for row in ablation.get("candidates") or []:
        if not isinstance(row, dict):
            continue
        control_id = str(row.get("controlId") or row.get("id") or "?")
        disable = {str(k): str(v) for k, v in (row.get("disableEnv") or {}).items()}
        for spec in row.get("benchmarkCommands") or []:
            command = str(spec.get("command") or "")
            scores: list[float | None] = []
            for extra_env in ({}, disable):
                env = dict(os.environ)
                env.update(extra_env)
                try:
                    proc = subprocess.run(
                        command, cwd=str(root), shell=True, capture_output=True,
                        text=True, encoding="utf-8", errors="replace", env=env,
                        timeout=60,
                    )
                    parsed = json.loads((proc.stdout or "").strip().splitlines()[-1])
                    score = float(parsed["score"]) if proc.returncode == 0 else None
                except (OSError, subprocess.SubprocessError, ValueError, KeyError,
                        IndexError, json.JSONDecodeError):
                    score = None
                scores.append(score)
            enabled, disabled = scores
            if enabled is None or disabled is None or enabled <= disabled:
                issues.append(
                    f"{control_id}: ablation probe is non-discriminating "
                    f"(enabled={enabled}, disabled={disabled})")
    return issues


def validate_tool_trust(registry: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if set(registry) != TOOL_REGISTRY_FIELDS:
        issues.append("tool registry fields must match the closed schema")
    if registry.get("version") != 2:
        issues.append("tool registry version must be 2")
    policy = registry.get("trustPolicy") or {}
    if not isinstance(policy, dict) or set(policy) != TOOL_POLICY_FIELDS:
        issues.append("tool trust policy fields must match the closed schema")
    prompt_types = set(policy.get("promptBearingTypes") or [])
    if policy.get("defaultForUnknownPromptBearingProvider") != "abstain":
        issues.append("unknown prompt-bearing providers must default to abstain")
    if set(policy.get("allowedDisposition") or []) != DISPOSITIONS:
        issues.append("tool trust dispositions drift")
    tools = registry.get("tools")
    if not isinstance(tools, list) or not tools:
        return issues + ["tool registry has no tools"]
    seen: set[str] = set()
    for index, tool in enumerate(tools):
        if not isinstance(tool, dict):
            issues.append(f"tool[{index}] is not an object")
            continue
        label = str(tool.get("id") or index)
        tool_fields = set(tool)
        if not TOOL_FIELDS <= tool_fields or tool_fields - TOOL_FIELDS - TOOL_OPTIONAL_FIELDS:
            issues.append(f"{label}: tool fields must match the closed schema")
        if label in seen:
            issues.append(f"duplicate tool id: {label}")
        seen.add(label)
        trust = tool.get("trust")
        if not isinstance(trust, dict):
            issues.append(f"{label}: trust record missing")
            continue
        missing = TRUST_FIELDS - set(trust)
        if missing:
            issues.append(f"{label}: trust record missing {sorted(missing)}")
            continue
        if set(trust) != TRUST_FIELDS:
            issues.append(f"{label}: trust fields must match the closed schema")
        disposition = trust.get("disposition")
        if disposition not in DISPOSITIONS:
            issues.append(f"{label}: invalid disposition")
        if not valid_date(trust.get("reviewedAt")):
            issues.append(f"{label}: reviewedAt must be an ISO date")
        for field in TRUST_FIELDS - {"promptTextReviewed", "permissions", "reviewedAt", "disposition"}:
            if not nonempty(trust.get(field)):
                issues.append(f"{label}: trust.{field} must be explicit")
        if not isinstance(trust.get("permissions"), list):
            issues.append(f"{label}: trust.permissions must be an array")
        externally_prompt_bearing = (
            tool.get("type") in prompt_types
            or str(tool.get("sideEffects") or "").startswith("external")
            or str(tool.get("externalDataRisk") or "") not in {"", "none"}
            or str(trust.get("networkScope") or "").lower() != "none"
            or "mcp" in str(trust.get("source") or "").lower()
        )
        if externally_prompt_bearing:
            reviewed = trust.get("promptTextReviewed") is True
            if disposition == "allow" and not reviewed:
                issues.append(f"{label}: unreviewed prompt-bearing provider cannot be allow")
            if disposition == "allow" and not local_ref(
                    MODULE_ROOT, str(trust.get("reviewEvidence") or "")).is_file():
                issues.append(f"{label}: allow requires durable local review evidence")
            elif disposition == "allow":
                review_path = local_ref(MODULE_ROOT, str(trust["reviewEvidence"]))
                try:
                    review = load_json(review_path)
                except ValueError:
                    review = {}
                expected_review = {
                    "toolId": tool.get("id"),
                    "provider": trust.get("provider"),
                    "disposition": "allow",
                    "promptTextReviewed": True,
                    "reviewedAt": trust.get("reviewedAt"),
                }
                if (not isinstance(review, dict)
                        or any(review.get(key) != value for key, value in expected_review.items())
                        or not nonempty(review.get("reviewer"))
                        or not nonempty(review.get("evidence"))):
                    issues.append(f"{label}: allow review evidence is not bound to this provider decision")
            if not reviewed and disposition not in {"ask", "abstain"}:
                issues.append(f"{label}: unknown prompt surface must ask or abstain")
    return issues


def run_hook(root: Path, case: dict[str, Any], probe: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update({str(k): str(v) for k, v in (case.get("probeEnv") or {}).items()})
    return subprocess.run(
        [sys.executable, str(root / case["hook"])],
        input=json.dumps(case[probe]), capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=str(root), env=env, timeout=30,
    )


def validate_hook_output(root: Path, contract: dict[str, Any], execute: bool = True) -> list[str]:
    issues: list[str] = []
    defaults = contract.get("defaults") or {}
    markers = defaults.get("failureRequiredMarkers")
    max_chars = defaults.get("maxFindingCharacters")
    if (markers != ["WHY:", "FIX:"] or not isinstance(max_chars, int)
            or defaults.get("findingShape") != "hookSpecificOutput.additionalContext"):
        issues.append("hook defaults must require host-recognized WHY:/FIX: output and a size bound")
    pilot = contract.get("pilot")
    if not isinstance(pilot, list) or len(pilot) < 2:
        return issues + ["hook output pilot must contain at least two hooks"]
    for case in pilot:
        hook = case.get("hook")
        if not nonempty(hook) or not (root / hook).is_file():
            issues.append(f"hook output pilot path missing: {hook}")
            continue
        noise = case.get("noiseControl") or {}
        if not all(nonempty(noise.get(key)) for key in ("mode", "deduplicateBy", "persistentRateLimit")):
            issues.append(f"{hook}: noise-control posture incomplete")
        if not execute:
            continue
        clean = run_hook(root, case, "successProbe")
        if clean.returncode != 0 or clean.stdout or clean.stderr:
            issues.append(f"{hook}: clean/no-op probe is not silent")
        finding = run_hook(root, case, "findingProbe")
        combined = (finding.stdout or "") + (finding.stderr or "")
        if finding.returncode not in {0, 2}:
            issues.append(f"{hook}: finding returned unsupported exit {finding.returncode}")
        if not combined:
            issues.append(f"{hook}: finding probe emitted no feedback")
        try:
            output = json.loads(finding.stdout)
        except json.JSONDecodeError:
            issues.append(f"{hook}: stdout is not one structured JSON finding")
            continue
        if not isinstance(output, dict) or set(output) != {"hookSpecificOutput"}:
            issues.append(f"{hook}: finding is not the host hookSpecificOutput object")
            continue
        specific = output.get("hookSpecificOutput")
        if (not isinstance(specific, dict)
                or not nonempty(specific.get("hookEventName"))
                or not nonempty(specific.get("additionalContext"))):
            issues.append(f"{hook}: finding lacks host event/additionalContext fields")
            continue
        text = specific["additionalContext"]
        if any(marker not in text for marker in markers or []):
            issues.append(f"{hook}: additionalContext lacks WHY:/FIX:")
        if isinstance(max_chars, int) and len(text) > max_chars:
            issues.append(f"{hook}: finding exceeds {max_chars} characters")
        if finding.stderr:
            issues.append(f"{hook}: structured finding must not duplicate feedback on stderr")
    return issues


def emit_issues(issues: list[str]) -> int:
    for issue in issues:
        print(f"FAILED: harness contract | WHY: {issue} | FIX: repair the named registry entry or probe.")
    return 2 if issues else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--phase", choices=("all", "provenance", "ablation", "tools", "hooks"), default="all")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    issues: list[str] = []
    try:
        if args.phase in {"all", "provenance", "ablation"}:
            controls = load_json(root / "docs/HARNESS_CONTROL_REGISTRY.json")
            ablation = load_json(root / "docs/HARNESS_ABLATION.json")
            issues.extend(validate_controls(root, controls, ablation))
            if args.phase in {"all", "ablation"}:
                issues.extend(validate_ablation_discrimination(root, ablation))
        if args.phase in {"all", "tools"}:
            issues.extend(validate_tool_trust(load_json(
                root / "docs/templates/itd/TOOL_CAPABILITY_REGISTRY.json")))
        if args.phase in {"all", "hooks"}:
            issues.extend(validate_hook_output(
                root, load_json(root / "docs/HOOK_OUTPUT_CONTRACT.json")))
    except ValueError as exc:
        issues.append(str(exc))
    if issues:
        return emit_issues(issues)
    if args.report:
        print(json.dumps({"status": "PASSED", "phase": args.phase}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
