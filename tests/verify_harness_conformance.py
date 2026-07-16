#!/usr/bin/env python3
"""Fail-closed evaluator for the frozen Harness Engineering H1-H5 oracle.

The contract defines the score; this evaluator cannot be used as evidence for
any axis that it scores.  Axis evidence is produced by independent focused
commands.  A missing command/artifact, a stale live artifact, a timeout, or a
non-zero exit earns zero for that axis and therefore prevents a 5/5 result.
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
DEFAULT_CONTRACT = ROOT / "docs" / "HARNESS_CONFORMANCE_CONTRACT.json"
APPROVED_CONTRACT_SHA256 = "8f0f5d3bb7beff0c20b39ce5405a770de20d21e4cbb67162a8115f116366ef3e"
EXPECTED_AXES = ("H1", "H2", "H3", "H4", "H5")
ALLOWED_KINDS = {
    "behavioral",
    "host-parity",
    "adversarial",
    "live-model",
    "quality",
    "freshness",
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
    """Return the unique focused test target or a fail-closed reason."""
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
    if any(not re.fullmatch(r"[A-Za-z0-9_./:=+,-]+", argument) for argument in tokens[3:]):
        return None, "evidence command arguments are not bounded data tokens"
    return target, None


def validate_seal(contract_path: Path) -> list[dict[str, str]]:
    seal_path = contract_path.with_suffix(".sha256")
    if not seal_path.is_file():
        return [
            finding(
                str(seal_path.relative_to(ROOT) if seal_path.is_relative_to(ROOT) else seal_path),
                "frozen conformance contract has no digest",
                "create a reviewed sha256 seal before implementing H1-H5 changes",
            )
        ]
    try:
        line = seal_path.read_text(encoding="utf-8").strip()
        expected, declared_path = line.split(None, 1)
        declared_path = declared_path.strip()
    except (OSError, ValueError):
        return [
            finding(
                str(seal_path),
                "digest file is not '<sha256>  <path>'",
                "replace it with one canonical sha256sum line",
            )
        ]
    actual = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    issues: list[dict[str, str]] = []
    if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected.lower()):
        issues.append(finding(str(seal_path), "digest is not sha256", "write a 64-hex sha256 digest"))
    if expected.lower() != actual:
        issues.append(
            finding(
                str(contract_path),
                "contract bytes no longer match the approved digest",
                "do not weaken the frozen oracle; create a newly approved version if change is legitimate",
            )
        )
    if expected.lower() != APPROVED_CONTRACT_SHA256:
        issues.append(
            finding(
                str(seal_path),
                "digest does not match the human-approved frozen oracle",
                "do not recompute the seal after an in-place edit; create and approve a new contract version",
            )
        )
    expected_declared = contract_path.relative_to(ROOT).as_posix() if contract_path.is_relative_to(ROOT) else str(contract_path)
    if declared_path != expected_declared:
        issues.append(
            finding(
                str(seal_path),
                f"digest seals '{declared_path}', not '{expected_declared}'",
                "seal the exact contract path used by the evaluator",
            )
        )
    return issues


def validate_contract_data(data: Any) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not isinstance(data, dict):
        return [finding("$", "contract root is not an object", "use a JSON object")]

    if data.get("version") != 1:
        issues.append(finding("version", "unsupported or missing version", "set version to the approved value 1"))

    try:
        parse_time(data.get("frozenAt", ""))
    except (TypeError, ValueError):
        issues.append(finding("frozenAt", "missing or invalid UTC timestamp", "set an ISO-8601 freeze timestamp"))

    scale = data.get("scoreScale")
    if not isinstance(scale, dict):
        issues.append(finding("scoreScale", "score scale is missing", "define the five-point binary scale"))
    else:
        if scale.get("maximum") != 5 or scale.get("pointsPerAxis") != 1:
            issues.append(
                finding(
                    "scoreScale",
                    "score is not exactly one point for each of five axes",
                    "restore maximum=5 and pointsPerAxis=1",
                )
            )
        rule = scale.get("passRule", "")
        for marker in ("Missing", "stale", "self-referential", "5/5"):
            if marker.lower() not in str(rule).lower():
                issues.append(
                    finding(
                        "scoreScale.passRule",
                        f"fail-closed marker '{marker}' is absent",
                        "state that missing/stale/self-referential evidence prevents 5/5",
                    )
                )

    change_policy = data.get("changePolicy")
    if not isinstance(change_policy, dict) or change_policy.get("mode") != "new-version-and-human-approval":
        issues.append(
            finding(
                "changePolicy.mode",
                "oracle may be edited in place without an approval boundary",
                "require a new version and explicit human approval",
            )
        )

    evaluator = data.get("evaluator")
    evaluator_path = "tests/verify_harness_conformance.py"
    timeout = 0
    if not isinstance(evaluator, dict):
        issues.append(finding("evaluator", "evaluator policy is missing", "declare evaluator path and timeout"))
    else:
        evaluator_path = str(evaluator.get("path", evaluator_path))
        if not evaluator.get("forbidSelfReference"):
            issues.append(
                finding(
                    "evaluator.forbidSelfReference",
                    "the scorer is allowed to prove its own axes",
                    "set forbidSelfReference=true",
                )
            )
        timeout = evaluator.get("commandTimeoutSeconds", 0)
        if not isinstance(timeout, int) or timeout < 1 or timeout > 3600:
            issues.append(
                finding(
                    "evaluator.commandTimeoutSeconds",
                    "evidence timeout is missing or unbounded",
                    "use an integer timeout in the range 1..3600",
                )
            )

    axes = data.get("axes")
    if not isinstance(axes, list):
        return issues + [finding("axes", "axes are missing", "define H1 through H5")]
    axis_ids = [axis.get("id") for axis in axes if isinstance(axis, dict)]
    if tuple(axis_ids) != EXPECTED_AXES:
        issues.append(
            finding(
                "axes",
                f"expected ordered axes {EXPECTED_AXES}, got {tuple(axis_ids)}",
                "restore exactly H1,H2,H3,H4,H5 without duplicates or omissions",
            )
        )

    total_points = 0
    targets_seen: set[str] = set()
    for axis_index, axis in enumerate(axes):
        axis_path = f"axes[{axis_index}]"
        if not isinstance(axis, dict):
            issues.append(finding(axis_path, "axis is not an object", "use an axis object"))
            continue
        axis_id = axis.get("id", f"index-{axis_index}")
        if axis.get("point") != 1:
            issues.append(finding(f"{axis_path}.point", "axis is not worth exactly one point", "set point=1"))
        else:
            total_points += 1
        requirements = axis.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            issues.append(finding(f"{axis_path}.requirements", "axis has no binary requirements", "add at least one requirement"))
            continue
        kinds_for_axis: set[str] = set()
        for req_index, requirement in enumerate(requirements):
            req_path = f"{axis_path}.requirements[{req_index}]"
            if not isinstance(requirement, dict):
                issues.append(finding(req_path, "requirement is not an object", "use a requirement object"))
                continue
            if not str(requirement.get("id", "")).startswith(f"{axis_id}-R"):
                issues.append(finding(f"{req_path}.id", "requirement id is not axis-scoped", f"use {axis_id}-R<n>"))
            if not str(requirement.get("criterion", "")).strip():
                issues.append(finding(f"{req_path}.criterion", "binary criterion is empty", "state the observable pass condition"))
            evidence = requirement.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                issues.append(finding(f"{req_path}.evidence", "requirement has no evidence", "add an independent evidence command"))
                continue
            for evidence_index, item in enumerate(evidence):
                ev_path = f"{req_path}.evidence[{evidence_index}]"
                if not isinstance(item, dict):
                    issues.append(finding(ev_path, "evidence is not an object", "use an evidence object"))
                    continue
                kind = item.get("kind")
                if kind not in ALLOWED_KINDS:
                    issues.append(finding(f"{ev_path}.kind", f"unknown evidence kind '{kind}'", "use a supported independent kind"))
                else:
                    kinds_for_axis.add(kind)
                command = str(item.get("command", "")).strip()
                if not command:
                    issues.append(finding(f"{ev_path}.command", "evidence command is missing", "provide an executable focused command"))
                else:
                    target, target_issue = focused_test_target(command)
                    if target_issue:
                        issues.append(
                            finding(
                                f"{ev_path}.command",
                                target_issue,
                                "use the repository launcher with one dedicated tests/*.py target and bounded arguments",
                            )
                        )
                    if target and (target == evaluator_path.replace("\\", "/") or Path(evaluator_path).name == Path(target).name):
                        issues.append(
                            finding(
                                f"{ev_path}.command",
                                "self-referential evidence asks the scorer to prove its own axis",
                                "use a focused behavioural test outside the evaluator",
                            )
                        )
                    if target and target in targets_seen:
                        issues.append(
                            finding(
                                f"{ev_path}.command",
                                "the same focused test target is reused as multiple independent proofs",
                                "use one dedicated focused test target once; whitespace or argument variants are not independent evidence",
                            )
                        )
                    if target:
                        targets_seen.add(target)
                if item.get("expectedExitCode") != 0:
                    issues.append(
                        finding(
                            f"{ev_path}.expectedExitCode",
                            "evidence does not require exit code 0",
                            "set expectedExitCode=0",
                        )
                    )
                if kind == "live-model":
                    for field in ("artifact", "observedAtField", "maxAgeDays", "mustPostdateFreeze"):
                        if field not in item:
                            issues.append(
                                finding(
                                    f"{ev_path}.{field}",
                                    "live-model evidence lacks freshness metadata",
                                    "declare artifact, observed timestamp, age limit, and post-freeze requirement",
                                )
                            )
                    if not isinstance(item.get("maxAgeDays"), int) or not 1 <= item.get("maxAgeDays", 0) <= 90:
                        issues.append(finding(f"{ev_path}.maxAgeDays", "live evidence age is unbounded", "use 1..90 days"))
                    if item.get("mustPostdateFreeze") is not True:
                        issues.append(
                            finding(
                                f"{ev_path}.mustPostdateFreeze",
                                "pre-oracle evidence could satisfy the new score",
                                "require post-freeze evidence",
                            )
                        )
        if not kinds_for_axis.intersection({"behavioral", "host-parity", "adversarial", "live-model"}):
            issues.append(
                finding(
                    f"{axis_path}.requirements",
                    "axis has no executable behavioural evidence class",
                    "add behavioural, host-parity, adversarial, or live-model evidence",
                )
            )
        if axis_id == "H4" and "live-model" not in kinds_for_axis:
            issues.append(finding(axis_path, "H4 has no live-model evidence", "add a fresh independent live-model benchmark"))

    if total_points != 5:
        issues.append(finding("axes[*].point", f"total points are {total_points}, not 5", "restore one point per H1-H5 axis"))
    return issues


def check_artifact(
    item: dict[str, Any],
    contract: dict[str, Any],
    now: dt.datetime,
    root: Path = ROOT,
) -> list[dict[str, str]]:
    artifact_value = item.get("artifact")
    if not artifact_value:
        return []
    artifact = root / str(artifact_value)
    path_key = str(artifact_value)
    if not artifact.is_file():
        return [finding(path_key, "required external evidence artifact is missing", "run the live benchmark and persist its independent report")]
    try:
        payload = load_json(artifact)
    except (OSError, json.JSONDecodeError):
        return [finding(path_key, "external evidence artifact is not valid JSON", "regenerate the benchmark report")]
    field = str(item.get("observedAtField", "observedAt"))
    try:
        observed = parse_time(str(payload[field]))
    except (KeyError, TypeError, ValueError):
        return [finding(f"{path_key}.{field}", "observation timestamp is missing or invalid", "record a UTC ISO-8601 timestamp")]
    issues: list[dict[str, str]] = []
    max_age = dt.timedelta(days=int(item.get("maxAgeDays", 0)))
    age = now - observed
    if age < dt.timedelta(0) or age > max_age:
        issues.append(
            finding(
                f"{path_key}.{field}",
                f"external evidence age {age} is outside 0..{max_age}",
                "run the live benchmark again and store fresh evidence",
            )
        )
    if item.get("mustPostdateFreeze"):
        try:
            frozen = parse_time(str(contract["frozenAt"]))
            if observed < frozen:
                issues.append(
                    finding(
                        f"{path_key}.{field}",
                        "external evidence predates the frozen oracle",
                        "collect evidence after the oracle was approved",
                    )
                )
        except (KeyError, TypeError, ValueError):
            issues.append(finding("frozenAt", "cannot compare evidence to invalid freeze time", "repair the contract timestamp"))
    return issues


def run_command(command: str, timeout: int, root: Path = ROOT) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            ["sh", "-c", command],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            env=os.environ.copy(),
            check=False,
        )
        return completed.returncode, completed.stdout[-4000:]
    except subprocess.TimeoutExpired as exc:
        tail = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        return 124, tail[-4000:]
    except OSError as exc:
        return 127, str(exc)


def preflight_evidence(
    contract: dict[str, Any],
    axis_ids: tuple[str, ...],
    now: dt.datetime,
    root: Path = ROOT,
) -> list[dict[str, str]]:
    """Reject missing/stale inputs before spending time on any evidence run."""
    issues: list[dict[str, str]] = []
    selected = {axis["id"]: axis for axis in contract["axes"] if axis["id"] in axis_ids}
    for axis_id in axis_ids:
        axis = selected[axis_id]
        for requirement in axis["requirements"]:
            for item in requirement["evidence"]:
                issues.extend(check_artifact(item, contract, now, root))
                command = item["command"]
                target, target_issue = focused_test_target(command)
                if target_issue or target is None:
                    issues.append(
                        finding(
                            f"{axis_id}.{requirement['id']}.command",
                            target_issue or "focused evidence target is missing",
                            "repair the contract before running evidence",
                        )
                    )
                elif not (root / target).is_file():
                    issues.append(
                        finding(
                            f"{axis_id}.{requirement['id']}.{target}",
                            "focused evidence program is missing",
                            f"implement and verify {target} before scoring {axis_id}",
                        )
                    )
    return issues


def evaluate_axis(
    contract: dict[str, Any],
    axis_id: str,
    now: dt.datetime,
    root: Path = ROOT,
) -> dict[str, Any]:
    axis = next(axis for axis in contract["axes"] if axis["id"] == axis_id)
    timeout = int(contract["evaluator"]["commandTimeoutSeconds"])
    results: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for requirement in axis["requirements"]:
        for item in requirement["evidence"]:
            artifact_issues = check_artifact(item, contract, now, root)
            if artifact_issues:
                issues.extend(artifact_issues)
                results.append(
                    {
                        "requirement": requirement["id"],
                        "command": item["command"],
                        "status": "missing-or-stale",
                        "returncode": None,
                    }
                )
                continue
            rc, output = run_command(item["command"], timeout, root)
            ok = rc == item["expectedExitCode"]
            results.append(
                {
                    "requirement": requirement["id"],
                    "command": item["command"],
                    "status": "passed" if ok else "failed",
                    "returncode": rc,
                    "outputTail": output,
                }
            )
            if not ok:
                issues.append(
                    finding(
                        f"{axis_id}.{requirement['id']}",
                        f"evidence command exited {rc}, expected {item['expectedExitCode']}",
                        f"run and fix: {item['command']}",
                    )
                )
    return {"axis": axis_id, "passed": not issues, "point": 1 if not issues else 0, "results": results, "issues": issues}


def contract_mutation_tests(contract: dict[str, Any]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []

    def expect_issue(label: str, mutated: dict[str, Any], needle: str) -> None:
        issues = validate_contract_data(mutated)
        joined = json.dumps(issues, ensure_ascii=False).lower()
        if needle.lower() not in joined:
            failures.append(finding(label, f"mutation was not rejected with marker '{needle}'", "harden contract validation"))

    mutated = copy.deepcopy(contract)
    mutated["axes"].pop()
    expect_issue("mutation.incomplete-axes", mutated, "expected ordered axes")

    mutated = copy.deepcopy(contract)
    del mutated["axes"][0]["requirements"][0]["evidence"][0]["command"]
    expect_issue("mutation.missing-command", mutated, "command is missing")

    mutated = copy.deepcopy(contract)
    mutated["axes"][0]["requirements"][0]["evidence"][0]["command"] = (
        "sh skills/_shared/itd_py.sh tests/verify_harness_conformance.py --axis H1"
    )
    expect_issue("mutation.self-reference", mutated, "self-referential")

    mutated = copy.deepcopy(contract)
    mutated["axes"][0]["requirements"][0]["evidence"][0]["command"] = "true # H1"
    expect_issue("mutation.arbitrary-shell", mutated, "bounded focused test launcher")

    mutated = copy.deepcopy(contract)
    mutated["axes"][0]["requirements"][1]["evidence"][0]["command"] = (
        "sh  skills/_shared/itd_py.sh  tests/verify_graduated_trust.py"
    )
    expect_issue("mutation.duplicate-target", mutated, "same focused test target")

    mutated = copy.deepcopy(contract)
    mutated["axes"][3]["requirements"][1]["evidence"][0].pop("artifact")
    expect_issue("mutation.live-artifact", mutated, "freshness metadata")

    rc, _ = run_command(f'"{sys.executable}" -c "raise SystemExit(7)"', 30)
    if rc == 0:
        failures.append(finding("mutation.failing-command", "non-zero evidence was accepted", "treat any unexpected exit as axis failure"))

    with tempfile.TemporaryDirectory(prefix="itd-h5-contract-") as tmp:
        tmp_root = Path(tmp)
        artifact = tmp_root / "stale.json"
        artifact.write_text(json.dumps({"observedAt": "2020-01-01T00:00:00Z"}), encoding="utf-8")
        item = {
            "artifact": "stale.json",
            "observedAtField": "observedAt",
            "maxAgeDays": 30,
            "mustPostdateFreeze": True,
        }
        stale_issues = check_artifact(item, contract, dt.datetime(2026, 7, 15, tzinfo=dt.timezone.utc), tmp_root)
        if not any("outside" in issue["why"] or "predates" in issue["why"] for issue in stale_issues):
            failures.append(finding("mutation.stale-evidence", "stale evidence was accepted", "enforce age and post-freeze checks"))

        missing = copy.deepcopy(contract)
        missing["axes"][0]["requirements"] = [copy.deepcopy(missing["axes"][0]["requirements"][0])]
        missing["axes"][0]["requirements"][0]["evidence"] = [
            {
                "kind": "behavioral",
                "command": "sh skills/_shared/itd_py.sh tests/fixture-missing-evidence.py",
                "expectedExitCode": 0,
            }
        ]
        missing_result = preflight_evidence(
            missing,
            ("H1",),
            dt.datetime(2026, 7, 15, tzinfo=dt.timezone.utc),
            tmp_root,
        )
        if not any(
            issue["path"].endswith("tests/fixture-missing-evidence.py")
            and "focused evidence program is missing" in issue["why"]
            and issue["fix"]
            for issue in missing_result
        ):
            failures.append(
                finding(
                    "mutation.missing-evidence-path",
                    "a missing focused evidence program did not fail preflight with path + WHY + FIX",
                    "keep missing evidence fail-closed before axis scoring",
                )
            )

        stale_axis = copy.deepcopy(contract)
        stale_axis["axes"][3]["requirements"] = [copy.deepcopy(stale_axis["axes"][3]["requirements"][1])]
        stale_axis["axes"][3]["requirements"][0]["evidence"][0]["artifact"] = "stale.json"
        stale_result = evaluate_axis(
            stale_axis,
            "H4",
            dt.datetime(2026, 7, 15, tzinfo=dt.timezone.utc),
            tmp_root,
        )
        if stale_result["point"] != 0 or stale_result["passed"] or not stale_result["issues"]:
            failures.append(
                finding(
                    "mutation.stale-score",
                    "stale external evidence did not produce a zero-point axis result",
                    "bind artifact freshness failures to axis scoring",
                )
            )

    failing = copy.deepcopy(contract)
    failing["axes"][0]["requirements"] = [copy.deepcopy(failing["axes"][0]["requirements"][0])]
    failing["axes"][0]["requirements"][0]["evidence"] = [
        {
            "kind": "behavioral",
            "command": "sh skills/_shared/itd_py.sh tests/verify_harness_conformance.py --contract tests/fixture-does-not-exist.json",
            "expectedExitCode": 0,
        }
    ]
    failing_result = evaluate_axis(failing, "H1", dt.datetime.now(dt.timezone.utc))
    if failing_result["point"] != 0 or failing_result["passed"] or not failing_result["issues"]:
        failures.append(
            finding(
                "mutation.failing-score",
                "a non-zero evidence command did not produce a zero-point axis result",
                "bind non-zero command outcomes to axis scoring",
            )
        )

    with tempfile.TemporaryDirectory(prefix="itd-resealed-contract-") as tmp:
        tmp_root = Path(tmp)
        changed_contract = tmp_root / "changed-contract.json"
        changed_seal = changed_contract.with_suffix(".sha256")
        changed = copy.deepcopy(contract)
        changed["axes"][0]["requirements"][0]["criterion"] += " Changed after approval."
        changed_bytes = (json.dumps(changed, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        changed_contract.write_bytes(changed_bytes)
        changed_digest = hashlib.sha256(changed_bytes).hexdigest()
        changed_seal.write_text(f"{changed_digest}  {changed_contract}\n", encoding="utf-8")
        reseal_issues = validate_seal(changed_contract)
        if not any("human-approved" in issue["why"] for issue in reseal_issues):
            failures.append(
                finding(
                    "mutation.resealed-contract",
                    "an in-place contract edit plus a recomputed digest was accepted as the approved oracle",
                    "pin the approved digest independently from the mutable contract and seal files",
                )
            )

    return failures


def render_findings(issues: list[dict[str, str]]) -> None:
    for issue in issues:
        print(f"{issue['path']}: WHY: {issue['why']} | FIX: {issue['fix']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--axis", choices=("contract", "all", *EXPECTED_AXES), default="contract")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    contract_path = args.contract.resolve()
    if not contract_path.is_file():
        issues = [finding(str(contract_path), "conformance contract is missing", "restore the approved contract")]
        if args.json:
            print(json.dumps({"status": "failed", "issues": issues}, ensure_ascii=False, indent=2))
        else:
            render_findings(issues)
        return 1
    try:
        contract = load_json(contract_path)
    except (OSError, json.JSONDecodeError) as exc:
        issues = [finding(str(contract_path), f"contract is unreadable: {exc}", "restore valid JSON")]
        if args.json:
            print(json.dumps({"status": "failed", "issues": issues}, ensure_ascii=False, indent=2))
        else:
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
            "evidenceCommands": sum(
                len(requirement.get("evidence", []))
                for axis in contract.get("axes", [])
                if isinstance(axis, dict)
                for requirement in axis.get("requirements", [])
                if isinstance(requirement, dict)
            ),
            "issues": issues,
        }
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif issues:
            render_findings(issues)
        else:
            print(
                f"PASS contract: {result['requirements']} binary requirements, "
                f"{result['evidenceCommands']} independent evidence commands, "
                "sealed H1-H5 oracle and negative mutation guards"
            )
        return 0 if not issues else 1

    if issues:
        if args.json:
            print(json.dumps({"status": "failed", "issues": issues}, ensure_ascii=False, indent=2))
        else:
            render_findings(issues)
        return 1

    now = dt.datetime.now(dt.timezone.utc)
    axes_to_run = EXPECTED_AXES if args.axis == "all" else (args.axis,)
    preflight_issues = preflight_evidence(contract, axes_to_run, now)
    if preflight_issues:
        result = {
            "status": "failed",
            "axis": args.axis,
            "score": 0,
            "maximum": 5 if args.axis == "all" else 1,
            "issues": preflight_issues,
        }
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            render_findings(preflight_issues)
            print(f"SCORE: 0/{result['maximum']}")
        return 1
    axis_results = [evaluate_axis(contract, axis_id, now) for axis_id in axes_to_run]
    score = sum(result["point"] for result in axis_results)
    all_passed = all(result["passed"] for result in axis_results)
    if args.axis == "all":
        all_passed = all_passed and score == 5
    result = {
        "status": "passed" if all_passed else "failed",
        "axis": args.axis,
        "score": score,
        "maximum": 5 if args.axis == "all" else 1,
        "results": axis_results,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for axis_result in axis_results:
            if axis_result["passed"]:
                print(f"PASS {axis_result['axis']}: 1/1")
            else:
                render_findings(axis_result["issues"])
        print(f"SCORE: {score}/{result['maximum']}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
