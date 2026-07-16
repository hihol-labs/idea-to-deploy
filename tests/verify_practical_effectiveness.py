#!/usr/bin/env python3
"""Fail-closed evaluator for the frozen practical-effectiveness audit oracle.

The contract, not this program, defines the six weighted axes.  An axis can
earn 5.0 only from independent focused evidence.  Missing programs/artifacts,
stale or synthetic external outcomes, timeouts and non-zero exits stay
UNVERIFIED and therefore cannot produce a weighted 5.0/5.0.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "docs" / "PRACTICAL_EFFECTIVENESS_CONTRACT.json"
APPROVED_CONTRACT_SHA256 = "e59ae5f47de9b983ede42df17b7086dcc24056760881260103d4b338e64cde75"
EXPECTED_AXES = (
    "defects",
    "efficiency",
    "operations",
    "feedback",
    "portability",
    "adoption",
)
EXPECTED_WEIGHTS = {
    "defects": 30,
    "efficiency": 20,
    "operations": 15,
    "feedback": 15,
    "portability": 10,
    "adoption": 10,
}
EXPECTED_BASELINES = {
    "defects": 4.5,
    "efficiency": 3.0,
    "operations": 3.6,
    "feedback": 4.2,
    "portability": 4.2,
    "adoption": 2.5,
}
EXPECTED_PREFIXES = {
    "defects": "DEF-R",
    "efficiency": "EFF-R",
    "operations": "OPS-R",
    "feedback": "FDB-R",
    "portability": "PRT-R",
    "adoption": "ADP-R",
}
ALLOWED_KINDS = {
    "behavioral",
    "adversarial",
    "host-parity",
    "benchmark",
    "telemetry",
    "operational",
    "feedback-loop",
    "freshness",
    "external-contract",
    "external-outcome",
}


def finding(path: str, why: str, fix: str) -> dict[str, str]:
    return {"path": path, "why": why, "fix": fix}


def parse_time(value: str) -> dt.datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def focused_test_target(command: str) -> tuple[str | None, str | None]:
    """Return the unique focused test path or a fail-closed reason."""
    if not command or "\n" in command or "\r" in command or re.search(r"[;&|><`$()#]", command):
        return None, "evidence command is not a bounded focused test launcher"
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None, "evidence command cannot be parsed as a bounded focused test launcher"
    if len(tokens) < 3 or tokens[:2] != ["sh", "skills/_shared/itd_py.sh"]:
        return None, "evidence command must use 'sh skills/_shared/itd_py.sh tests/<focused>.py'"
    target = tokens[2].replace("\\", "/")
    if not re.fullmatch(r"tests/[A-Za-z0-9_.-]+\.py", target):
        return None, "evidence command target is not one focused tests/*.py program"
    if any(not re.fullmatch(r"[A-Za-z0-9_./:=+,-]+", arg) for arg in tokens[3:]):
        return None, "evidence command arguments are not bounded data tokens"
    return target, None


def validate_seal(contract_path: Path) -> list[dict[str, str]]:
    seal_path = contract_path.with_suffix(".sha256")
    shown = str(seal_path.relative_to(ROOT)) if seal_path.is_relative_to(ROOT) else str(seal_path)
    if not seal_path.is_file():
        return [finding(shown, "frozen practical-effectiveness contract has no digest", "create a reviewed sha256 seal before implementing any scored axis")]
    try:
        expected, declared_path = seal_path.read_text(encoding="utf-8").strip().split(None, 1)
        declared_path = declared_path.strip()
    except (OSError, ValueError):
        return [finding(shown, "digest file is not '<sha256>  <path>'", "replace it with one canonical sha256sum line")]
    actual = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    issues: list[dict[str, str]] = []
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        issues.append(finding(shown, "digest is not sha256", "write a 64-hex sha256 digest"))
    if expected.lower() != actual:
        issues.append(finding(str(contract_path), "contract bytes no longer match the approved digest", "create a newly approved contract version instead of weakening this oracle"))
    if expected.lower() != APPROVED_CONTRACT_SHA256:
        issues.append(finding(shown, "digest does not match the human-approved frozen oracle", "do not accept an in-place edit plus a recomputed seal"))
    wanted = contract_path.relative_to(ROOT).as_posix() if contract_path.is_relative_to(ROOT) else str(contract_path)
    if declared_path != wanted:
        issues.append(finding(shown, f"digest seals '{declared_path}', not '{wanted}'", "seal the exact contract path used by the evaluator"))
    return issues


def validate_contract_data(data: Any) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not isinstance(data, dict):
        return [finding("$", "contract root is not an object", "use a JSON object")]
    if data.get("version") != 1:
        issues.append(finding("version", "unsupported or missing version", "restore approved version 1"))
    try:
        parse_time(str(data.get("frozenAt", "")))
    except (TypeError, ValueError):
        issues.append(finding("frozenAt", "missing or invalid UTC timestamp", "set an ISO-8601 freeze timestamp"))

    audit = data.get("audit")
    if not isinstance(audit, dict):
        issues.append(finding("audit", "source audit is missing", "record the approved baseline, weights and scale"))
    else:
        exact = audit.get("exactWeightedBaseline")
        if audit.get("source") != "user-provided-practical-effectiveness-audit":
            issues.append(finding("audit.source", "audit source changed", "restore the user-approved audit source"))
        if audit.get("reportedTotal") != 3.8 or exact != 3.79:
            issues.append(finding("audit", "reported or exact baseline changed", "restore reportedTotal=3.8 and exactWeightedBaseline=3.79"))
        if audit.get("weightUnit") != "percent" or audit.get("scoreMaximum") != 5.0:
            issues.append(finding("audit", "audit scale or weight unit changed", "restore percent weights on a five-point scale"))

    scale = data.get("scoreScale")
    if not isinstance(scale, dict):
        issues.append(finding("scoreScale", "score scale is missing", "define the six-axis five-point rule"))
    else:
        if scale.get("maximum") != 5.0 or scale.get("targetPerAxis") != 5.0:
            issues.append(finding("scoreScale", "target is not 5.0 on every axis", "restore maximum=targetPerAxis=5.0"))
        rule = str(scale.get("passRule", "")).lower()
        for marker in ("missing", "stale", "self-referential", "synthetic external", "all six"):
            if marker not in rule:
                issues.append(finding("scoreScale.passRule", f"fail-closed marker '{marker}' is absent", "restore the approved evidence rule"))

    freshness = data.get("freshness")
    if not isinstance(freshness, dict) or freshness.get("maxOperationalEvidenceAgeDays") != 30 or freshness.get("maxExternalOutcomeAgeDays") != 90 or freshness.get("externalEvidenceMustPostdateFreeze") is not True:
        issues.append(finding("freshness", "evidence freshness thresholds changed or are incomplete", "restore 30-day operational, 90-day external and post-freeze requirements"))

    policy = data.get("externalEvidencePolicy")
    expected_mins = {
        "minimumIndependentProjects": 3,
        "minimumIndependentOperators": 2,
        "minimumComparableUnits": 30,
        "minimumObservationDays": 30,
    }
    if not isinstance(policy, dict):
        issues.append(finding("externalEvidencePolicy", "external outcome policy is missing", "restore independent adoption thresholds"))
    else:
        for key, value in expected_mins.items():
            if policy.get(key) != value:
                issues.append(finding(f"externalEvidencePolicy.{key}", f"threshold changed from {value}", f"restore {key}={value}"))
        for key in ("forbidMethodologyRepository", "forbidAuthorSelfReportOnly", "forbidSyntheticOrFixtureEvidence"):
            if policy.get(key) is not True:
                issues.append(finding(f"externalEvidencePolicy.{key}", "synthetic or non-independent evidence could count", f"set {key}=true"))
        required = policy.get("requiredProvenanceFields")
        needed = {"projectId", "operatorId", "repositoryClass", "startedAt", "observedAt", "baseline", "followup", "sourceHashes", "attestation"}
        if not isinstance(required, list) or set(required) != needed:
            issues.append(finding("externalEvidencePolicy.requiredProvenanceFields", "provenance fields are missing or changed", "restore the complete approved provenance field set"))

    change = data.get("changePolicy")
    if not isinstance(change, dict) or change.get("mode") != "new-version-and-human-approval":
        issues.append(finding("changePolicy.mode", "oracle may be edited in place", "require a new version and explicit human approval"))

    evaluator = data.get("evaluator")
    evaluator_path = "tests/verify_practical_effectiveness.py"
    if not isinstance(evaluator, dict):
        issues.append(finding("evaluator", "evaluator policy is missing", "declare path, self-reference ban and timeout"))
    else:
        evaluator_path = str(evaluator.get("path", evaluator_path))
        if evaluator_path != "tests/verify_practical_effectiveness.py" or evaluator.get("forbidSelfReference") is not True:
            issues.append(finding("evaluator", "evaluator identity or self-reference rule changed", "restore the approved evaluator and forbidSelfReference=true"))
        timeout = evaluator.get("commandTimeoutSeconds")
        if not isinstance(timeout, int) or not 1 <= timeout <= 3600:
            issues.append(finding("evaluator.commandTimeoutSeconds", "timeout is missing or unbounded", "use an integer timeout in 1..3600"))

    axes = data.get("axes")
    if not isinstance(axes, list):
        return issues + [finding("axes", "audit axes are missing", "restore all six ordered axes")]
    ids = tuple(axis.get("id") for axis in axes if isinstance(axis, dict))
    if ids != EXPECTED_AXES:
        issues.append(finding("axes", f"expected ordered axes {EXPECTED_AXES}, got {ids}", "restore all six axes without duplicates or omissions"))

    total_weight = 0
    weighted_baseline = 0.0
    targets_seen: set[str] = set()
    for axis_index, axis in enumerate(axes):
        axis_path = f"axes[{axis_index}]"
        if not isinstance(axis, dict):
            issues.append(finding(axis_path, "axis is not an object", "use an axis object"))
            continue
        axis_id = str(axis.get("id", ""))
        expected_weight = EXPECTED_WEIGHTS.get(axis_id)
        expected_baseline = EXPECTED_BASELINES.get(axis_id)
        if axis.get("weight") != expected_weight:
            issues.append(finding(f"{axis_path}.weight", f"weight changed from {expected_weight}", f"restore {axis_id} weight"))
        else:
            total_weight += int(axis["weight"])
        if axis.get("baselineScore") != expected_baseline:
            issues.append(finding(f"{axis_path}.baselineScore", f"baseline changed from {expected_baseline}", f"restore the user-provided {axis_id} baseline"))
        elif expected_weight is not None:
            weighted_baseline += float(expected_baseline) * expected_weight / 100
        if axis.get("targetScore") != 5.0:
            issues.append(finding(f"{axis_path}.targetScore", "axis target is not 5.0", "restore targetScore=5.0"))
        requirements = axis.get("requirements")
        if not isinstance(requirements, list) or len(requirements) < 2:
            issues.append(finding(f"{axis_path}.requirements", "axis lacks multiple binary requirements", "restore independent requirements"))
            continue
        kinds: set[str] = set()
        for req_index, requirement in enumerate(requirements):
            req_path = f"{axis_path}.requirements[{req_index}]"
            if not isinstance(requirement, dict):
                issues.append(finding(req_path, "requirement is not an object", "use a requirement object"))
                continue
            if not str(requirement.get("id", "")).startswith(EXPECTED_PREFIXES.get(axis_id, "!")):
                issues.append(finding(f"{req_path}.id", "requirement id is not axis-scoped", "restore the approved axis prefix"))
            if not str(requirement.get("criterion", "")).strip():
                issues.append(finding(f"{req_path}.criterion", "binary criterion is empty", "state an observable pass condition"))
            evidence = requirement.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                issues.append(finding(f"{req_path}.evidence", "requirement has no independent evidence", "add a focused evidence command"))
                continue
            for ev_index, item in enumerate(evidence):
                ev_path = f"{req_path}.evidence[{ev_index}]"
                if not isinstance(item, dict):
                    issues.append(finding(ev_path, "evidence is not an object", "use an evidence object"))
                    continue
                kind = item.get("kind")
                if kind not in ALLOWED_KINDS:
                    issues.append(finding(f"{ev_path}.kind", f"unsupported evidence kind '{kind}'", "use an approved independent kind"))
                else:
                    kinds.add(str(kind))
                command = str(item.get("command", "")).strip()
                target, target_issue = focused_test_target(command)
                if target_issue:
                    issues.append(finding(f"{ev_path}.command", target_issue, "use the repository launcher with one focused tests/*.py program"))
                if target and Path(target).name == Path(evaluator_path).name:
                    issues.append(finding(f"{ev_path}.command", "self-referential evidence asks the scorer to prove its own axis", "use an independent focused test"))
                if target and target in targets_seen:
                    issues.append(finding(f"{ev_path}.command", "the same focused test target is reused as independent proof", "use a distinct focused evidence program"))
                if target:
                    targets_seen.add(target)
                if item.get("expectedExitCode") != 0:
                    issues.append(finding(f"{ev_path}.expectedExitCode", "evidence does not require exit 0", "set expectedExitCode=0"))
                if kind == "external-outcome":
                    for field in ("artifact", "observedAtField", "maxAgeDays", "mustPostdateFreeze"):
                        if field not in item:
                            issues.append(finding(f"{ev_path}.{field}", "external outcome lacks freshness metadata", "declare artifact, timestamp, age and post-freeze requirement"))
                    artifact = str(item.get("artifact", ""))
                    if not artifact or Path(artifact).is_absolute() or ".." in Path(artifact).parts:
                        issues.append(finding(f"{ev_path}.artifact", "external artifact path is absent or escapes the repository", "use one repository-relative evidence index"))
                    if item.get("maxAgeDays") != 90 or item.get("mustPostdateFreeze") is not True:
                        issues.append(finding(ev_path, "external freshness threshold changed", "restore 90 days and mustPostdateFreeze=true"))
        if axis_id == "adoption" and not {"external-contract", "external-outcome"}.issubset(kinds):
            issues.append(finding(axis_path, "adoption lacks contract and real external-outcome evidence classes", "restore both evidence classes"))
        if axis_id != "adoption" and "external-outcome" in kinds:
            issues.append(finding(axis_path, "external adoption evidence is attached to the wrong axis", "keep it only on adoption"))

    if total_weight != 100:
        issues.append(finding("axes[*].weight", f"weights total {total_weight}, not 100", "restore the approved weights"))
    if round(weighted_baseline, 2) != 3.79:
        issues.append(finding("axes[*].baselineScore", f"weighted baseline is {weighted_baseline:.2f}, not 3.79", "restore the audit baselines"))
    return issues


def check_artifact(item: dict[str, Any], contract: dict[str, Any], now: dt.datetime, root: Path = ROOT) -> list[dict[str, str]]:
    artifact_value = str(item.get("artifact", ""))
    if not artifact_value:
        return []
    artifact = root / artifact_value
    if not artifact.is_file():
        return [finding(artifact_value, "required external outcome artifact is missing", "collect independent pilot evidence; do not substitute a fixture")]
    try:
        payload = load_json(artifact)
        observed = parse_time(str(payload[item.get("observedAtField", "observedAt")]))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return [finding(artifact_value, "external outcome index or observedAt is invalid", "regenerate the signed evidence index")]
    issues: list[dict[str, str]] = []
    age = now - observed
    max_age = dt.timedelta(days=int(item.get("maxAgeDays", 0)))
    if age < dt.timedelta(0) or age > max_age:
        issues.append(finding(artifact_value, f"external evidence age {age} is outside 0..{max_age}", "collect a fresh independent follow-up"))
    if item.get("mustPostdateFreeze"):
        try:
            if observed < parse_time(str(contract["frozenAt"])):
                issues.append(finding(artifact_value, "external evidence predates the frozen oracle", "collect evidence after the approved freeze"))
        except (KeyError, TypeError, ValueError):
            issues.append(finding("frozenAt", "cannot compare external evidence to the freeze", "repair the contract timestamp"))
    return issues


def selected_requirements(contract: dict[str, Any], axis_id: str) -> list[dict[str, Any]]:
    resolved_axis = "adoption" if axis_id == "adoption-contract" else axis_id
    axis = next(axis for axis in contract["axes"] if axis["id"] == resolved_axis)
    if axis_id == "adoption-contract":
        return [next(req for req in axis["requirements"] if req["id"] == "ADP-R1")]
    return list(axis["requirements"])


def preflight_evidence(contract: dict[str, Any], axis_ids: tuple[str, ...], now: dt.datetime, root: Path = ROOT) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for requested in axis_ids:
        axis_id = "adoption" if requested == "adoption-contract" else requested
        for requirement in selected_requirements(contract, requested):
            for item in requirement["evidence"]:
                issues.extend(check_artifact(item, contract, now, root))
                target, target_issue = focused_test_target(item["command"])
                if target_issue or target is None:
                    issues.append(finding(f"{axis_id}.{requirement['id']}.command", target_issue or "focused target is missing", "repair the frozen contract"))
                elif not (root / target).is_file():
                    issues.append(finding(f"{axis_id}.{requirement['id']}.{target}", "focused evidence program is missing", f"implement and verify {target} before scoring {axis_id}"))
    return issues


def run_command(command: str, timeout: int, root: Path = ROOT) -> tuple[int, str]:
    try:
        completed = subprocess.run(["sh", "-c", command], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, env=os.environ.copy(), check=False)
        return completed.returncode, completed.stdout[-4000:]
    except subprocess.TimeoutExpired as exc:
        tail = exc.stdout if isinstance(exc.stdout, str) else ""
        return 124, tail[-4000:]
    except OSError as exc:
        return 127, str(exc)


def evaluate_axis(contract: dict[str, Any], requested: str, now: dt.datetime, root: Path = ROOT) -> dict[str, Any]:
    axis_id = "adoption" if requested == "adoption-contract" else requested
    timeout = int(contract["evaluator"]["commandTimeoutSeconds"])
    issues: list[dict[str, str]] = []
    results: list[dict[str, Any]] = []
    for requirement in selected_requirements(contract, requested):
        for item in requirement["evidence"]:
            artifact_issues = check_artifact(item, contract, now, root)
            if artifact_issues:
                issues.extend(artifact_issues)
                results.append({"requirement": requirement["id"], "command": item["command"], "status": "missing-or-stale", "returncode": None})
                continue
            rc, output = run_command(item["command"], timeout, root)
            ok = rc == item["expectedExitCode"]
            results.append({"requirement": requirement["id"], "command": item["command"], "status": "passed" if ok else "failed", "returncode": rc, "outputTail": output})
            if not ok:
                issues.append(finding(f"{axis_id}.{requirement['id']}", f"evidence command exited {rc}, expected 0", f"run and fix: {item['command']}"))
    return {"axis": requested, "passed": not issues, "score": 5.0 if not issues else None, "results": results, "issues": issues}


def contract_mutation_tests(contract: dict[str, Any]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []

    def expect_issue(label: str, mutated: dict[str, Any], needle: str) -> None:
        joined = json.dumps(validate_contract_data(mutated), ensure_ascii=False).lower()
        if needle.lower() not in joined:
            failures.append(finding(label, f"mutation was not rejected with marker '{needle}'", "harden contract validation"))

    mutated = copy.deepcopy(contract)
    mutated["axes"].pop()
    expect_issue("mutation.incomplete-axes", mutated, "expected ordered axes")

    mutated = copy.deepcopy(contract)
    mutated["axes"][0]["weight"] = 29
    expect_issue("mutation.changed-weight", mutated, "weight changed")

    mutated = copy.deepcopy(contract)
    mutated["axes"][1]["baselineScore"] = 4.0
    expect_issue("mutation.changed-baseline", mutated, "baseline changed")

    mutated = copy.deepcopy(contract)
    mutated["axes"][2]["targetScore"] = 4.9
    expect_issue("mutation.lower-target", mutated, "target is not 5.0")

    mutated = copy.deepcopy(contract)
    del mutated["axes"][0]["requirements"][0]["evidence"][0]["command"]
    expect_issue("mutation.missing-command", mutated, "bounded focused test launcher")

    mutated = copy.deepcopy(contract)
    mutated["axes"][0]["requirements"][0]["evidence"][0]["command"] = "sh skills/_shared/itd_py.sh tests/verify_practical_effectiveness.py --axis defects"
    expect_issue("mutation.self-reference", mutated, "self-referential")

    mutated = copy.deepcopy(contract)
    mutated["axes"][0]["requirements"][0]["evidence"][0]["command"] = "true # pass"
    expect_issue("mutation.arbitrary-shell", mutated, "bounded focused test launcher")

    mutated = copy.deepcopy(contract)
    mutated["axes"][0]["requirements"][1]["evidence"][0]["command"] = mutated["axes"][0]["requirements"][0]["evidence"][0]["command"]
    expect_issue("mutation.duplicate-target", mutated, "same focused test target")

    mutated = copy.deepcopy(contract)
    mutated["externalEvidencePolicy"]["forbidSyntheticOrFixtureEvidence"] = False
    expect_issue("mutation.synthetic-adoption", mutated, "synthetic or non-independent")

    mutated = copy.deepcopy(contract)
    mutated["axes"][5]["requirements"][1]["evidence"][0].pop("artifact")
    expect_issue("mutation.external-artifact", mutated, "freshness metadata")

    with tempfile.TemporaryDirectory(prefix="itd-practical-contract-") as tmp:
        tmp_root = Path(tmp)
        stale = tmp_root / "stale.json"
        stale.write_text(json.dumps({"observedAt": "2020-01-01T00:00:00Z"}), encoding="utf-8")
        item = {"artifact": "stale.json", "observedAtField": "observedAt", "maxAgeDays": 90, "mustPostdateFreeze": True}
        stale_issues = check_artifact(item, contract, dt.datetime(2026, 7, 15, tzinfo=dt.timezone.utc), tmp_root)
        if not any("outside" in issue["why"] or "predates" in issue["why"] for issue in stale_issues):
            failures.append(finding("mutation.stale-external", "stale external evidence was accepted", "enforce age and post-freeze freshness"))

        missing = copy.deepcopy(contract)
        missing["axes"][0]["requirements"] = [{"id": "DEF-RX", "criterion": "missing", "evidence": [{"kind": "behavioral", "command": "sh skills/_shared/itd_py.sh tests/fixture-missing-practical.py", "expectedExitCode": 0}]}]
        result = preflight_evidence(missing, ("defects",), dt.datetime.now(dt.timezone.utc), tmp_root)
        if not any("focused evidence program is missing" in issue["why"] for issue in result):
            failures.append(finding("mutation.missing-evidence", "missing focused evidence did not fail preflight", "keep scoring fail-closed"))

        changed_path = tmp_root / "changed.json"
        changed = copy.deepcopy(contract)
        changed["axes"][0]["requirements"][0]["criterion"] += " weakened"
        changed_bytes = (json.dumps(changed, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        changed_path.write_bytes(changed_bytes)
        changed_path.with_suffix(".sha256").write_text(f"{hashlib.sha256(changed_bytes).hexdigest()}  {changed_path}\n", encoding="utf-8")
        if not any("human-approved" in issue["why"] for issue in validate_seal(changed_path)):
            failures.append(finding("mutation.resealed-contract", "in-place edit plus recomputed seal was accepted", "pin the approved digest in evaluator code"))
    return failures


def render_findings(issues: list[dict[str, str]]) -> None:
    for issue in issues:
        print(f"{issue['path']}: WHY: {issue['why']} | FIX: {issue['fix']}")


def main() -> int:
    choices = ("contract", "all", "adoption-contract", *EXPECTED_AXES)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--axis", choices=choices, default="contract")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    contract_path = args.contract.resolve()
    if not contract_path.is_file():
        issues = [finding(str(contract_path), "practical-effectiveness contract is missing", "restore the approved contract")]
        render_findings(issues)
        return 1
    try:
        contract = load_json(contract_path)
    except (OSError, json.JSONDecodeError) as exc:
        issues = [finding(str(contract_path), f"contract is unreadable: {exc}", "restore valid JSON")]
        render_findings(issues)
        return 1

    issues = validate_contract_data(contract)
    issues.extend(validate_seal(contract_path))
    if args.axis == "contract":
        if not issues:
            issues.extend(contract_mutation_tests(contract))
        result = {
            "status": "passed" if not issues else "failed",
            "axis": "contract",
            "axes": [axis.get("id") for axis in contract.get("axes", []) if isinstance(axis, dict)],
            "requirements": sum(len(axis.get("requirements", [])) for axis in contract.get("axes", []) if isinstance(axis, dict)),
            "evidenceCommands": sum(len(req.get("evidence", [])) for axis in contract.get("axes", []) if isinstance(axis, dict) for req in axis.get("requirements", []) if isinstance(req, dict)),
            "issues": issues,
        }
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif issues:
            render_findings(issues)
        else:
            print(f"PASS contract: {result['requirements']} binary requirements, {result['evidenceCommands']} independent evidence commands, sealed six-axis oracle and negative mutation guards")
        return 0 if not issues else 1

    if issues:
        if args.json:
            print(json.dumps({"status": "failed", "issues": issues}, ensure_ascii=False, indent=2))
        else:
            render_findings(issues)
        return 1

    now = dt.datetime.now(dt.timezone.utc)
    requested = EXPECTED_AXES if args.axis == "all" else (args.axis,)
    preflight = preflight_evidence(contract, requested, now)
    if preflight:
        if args.json:
            print(json.dumps({"status": "failed", "axis": args.axis, "issues": preflight}, ensure_ascii=False, indent=2))
        else:
            render_findings(preflight)
            print("SCORE: UNVERIFIED")
        return 1

    results = [evaluate_axis(contract, axis_id, now) for axis_id in requested]
    all_passed = all(result["passed"] for result in results)
    if args.axis == "all":
        weighted = sum((5.0 if result["passed"] else 0.0) * EXPECTED_WEIGHTS[result["axis"]] / 100 for result in results)
    else:
        weighted = 5.0 if all_passed else 0.0
    if args.axis == "all" and weighted != 5.0:
        all_passed = False
    payload = {"status": "passed" if all_passed else "failed", "axis": args.axis, "score": weighted if all_passed else None, "maximum": 5.0, "results": results}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for result in results:
            if result["passed"]:
                print(f"PASS {result['axis']}: 5.0/5.0")
            else:
                render_findings(result["issues"])
        print(f"SCORE: {weighted:.1f}/5.0" if all_passed else "SCORE: UNVERIFIED")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
