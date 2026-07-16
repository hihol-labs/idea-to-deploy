#!/usr/bin/env python3
"""Local, privacy-safe raw ledger for external outcome pilots.

The tool never contacts pilots or uploads data.  It records pseudonymous paired
baseline/follow-up units, deterministically aggregates the six frozen outcome
metrics, and lets a second operator attest the resulting record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import statistics
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from itd_external_outcomes import (  # noqa: E402
    OPERATOR_RE,
    PROJECT_RE,
    forbidden_paths,
    parse_time,
    record_digest,
)

COMPARISON_RE = re.compile(r"^cmp_[a-f0-9]{12}$")
REPOSITORY_CLASS_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,47}$")
PHASES = ("baseline", "followup")
PRIVACY = {
    "containsPII": False,
    "containsSourceCode": False,
    "containsSecrets": False,
    "containsCustomerData": False,
}
META_FIELDS = {
    "recordType", "version", "projectId", "operatorId", "repositoryClass",
    "startedAt", "consent", "synthetic", "fixture", "privacy",
}
UNIT_FIELDS = {
    "recordType", "phase", "comparisonId", "startedAt", "finishedAt",
    "verified", "defectEscapes", "falseCompletions", "tokenUnits",
    "frictionEvents", "criticalRegressions",
}


class PilotError(ValueError):
    """A fail-closed pilot input error with actionable context."""


def fail(what: str, why: str, fix: str, code: int = 1) -> int:
    print(f"FAILED: {what} | WHY: {why} | FIX: {fix}")
    return code


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def append_jsonl(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json(value) + b"\n"
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)


def positive_number(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def validate_time(value: str, field: str) -> None:
    try:
        parse_time(value)
    except (TypeError, ValueError) as exc:
        raise PilotError(f"{field} is invalid: {exc}") from exc


def validate_metadata(meta: dict, source: str) -> None:
    if set(meta) != META_FIELDS or meta.get("recordType") != "metadata":
        raise PilotError(f"{source}: metadata fields are invalid")
    if meta.get("version") != 1:
        raise PilotError(f"{source}: metadata version must be 1")
    if not PROJECT_RE.fullmatch(str(meta.get("projectId", ""))):
        raise PilotError(f"{source}: projectId is not pseudonymous")
    if not OPERATOR_RE.fullmatch(str(meta.get("operatorId", ""))):
        raise PilotError(f"{source}: operatorId is not pseudonymous")
    repository_class = str(meta.get("repositoryClass", ""))
    if (not REPOSITORY_CLASS_RE.fullmatch(repository_class)
            or repository_class == "methodology"):
        raise PilotError(f"{source}: repositoryClass is invalid or ineligible")
    validate_time(str(meta.get("startedAt", "")), f"{source}:startedAt")
    if meta.get("consent") is not True:
        raise PilotError(f"{source}: explicit consent is missing")
    if meta.get("synthetic") is not False or meta.get("fixture") is not False:
        raise PilotError(f"{source}: synthetic or fixture pilot is ineligible")
    if meta.get("privacy") != PRIVACY:
        raise PilotError(f"{source}: privacy declaration is invalid")


def validate_unit(unit: dict, meta: dict, source: str) -> None:
    if set(unit) != UNIT_FIELDS or unit.get("recordType") != "unit":
        raise PilotError(f"{source}: unit fields are invalid")
    if unit.get("phase") not in PHASES:
        raise PilotError(f"{source}: phase must be baseline or followup")
    if not COMPARISON_RE.fullmatch(str(unit.get("comparisonId", ""))):
        raise PilotError(f"{source}: comparisonId is not pseudonymous")
    validate_time(str(unit.get("startedAt", "")), f"{source}:startedAt")
    validate_time(str(unit.get("finishedAt", "")), f"{source}:finishedAt")
    started = parse_time(str(unit["startedAt"]))
    finished = parse_time(str(unit["finishedAt"]))
    pilot_started = parse_time(str(meta["startedAt"]))
    if started < pilot_started:
        raise PilotError(f"{source}: unit starts before pilot enrollment")
    if finished <= started:
        raise PilotError(f"{source}: finishedAt must be after startedAt")
    if unit.get("verified") is not True:
        raise PilotError(f"{source}: only verified comparable units may be recorded")
    for field in ("defectEscapes", "falseCompletions", "frictionEvents",
                  "criticalRegressions"):
        if type(unit.get(field)) is not int or unit[field] < 0:
            raise PilotError(f"{source}: {field} must be a non-negative integer")
    if not isinstance(unit.get("tokenUnits"), (int, float)) or unit["tokenUnits"] < 0:
        raise PilotError(f"{source}: tokenUnits must be a non-negative number")


def load_ledger(path: Path) -> tuple[dict, list[dict]]:
    if not path.is_file():
        raise PilotError(f"{path}: ledger does not exist")
    records: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PilotError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise PilotError(f"{path}:{line_number}: record is not an object")
        prohibited = forbidden_paths(value)
        if prohibited:
            raise PilotError(
                f"{path}:{line_number}: prohibited fields: {', '.join(prohibited)}"
            )
        records.append(value)
    if not records:
        raise PilotError(f"{path}: ledger is empty")
    meta = records[0]
    validate_metadata(meta, f"{path}:1")
    units = records[1:]
    for index, unit in enumerate(units, 2):
        validate_unit(unit, meta, f"{path}:{index}")
    return meta, units


def aggregate_ledger(path: Path) -> dict:
    meta, units = load_ledger(path)
    if not units:
        raise PilotError(f"{path}: no comparable units recorded")
    pairs: dict[str, dict[str, dict]] = {}
    for unit in units:
        phases = pairs.setdefault(unit["comparisonId"], {})
        phase = unit["phase"]
        if phase in phases:
            raise PilotError(
                f"{path}: duplicate {phase} for {unit['comparisonId']}"
            )
        phases[phase] = unit
    incomplete = sorted(key for key, value in pairs.items()
                        if set(value) != set(PHASES))
    if incomplete:
        raise PilotError(
            f"{path}: unpaired comparison IDs: {', '.join(incomplete)}"
        )

    def phase_metrics(phase: str) -> dict:
        rows = [pairs[key][phase] for key in sorted(pairs)]
        count = len(rows)
        cycles = [
            (parse_time(row["finishedAt"]) - parse_time(row["startedAt"])).total_seconds() / 60
            for row in rows
        ]
        verified = sum(1 for row in rows if row["verified"] is True)
        if verified == 0:
            raise PilotError(f"{path}: {phase} has no verified units")
        return {
            "defectEscapeRate": round(sum(row["defectEscapes"] for row in rows) / count, 6),
            "falseCompletionRate": round(sum(row["falseCompletions"] for row in rows) / count, 6),
            "medianCycleMinutes": round(float(statistics.median(cycles)), 3),
            "tokenUnitsPerVerifiedUnit": round(sum(float(row["tokenUnits"]) for row in rows) / verified, 3),
            "operatorFrictionRate": round(sum(1 for row in rows if row["frictionEvents"] > 0) / count, 6),
            "criticalRegressions": sum(row["criticalRegressions"] for row in rows),
        }

    observed_at = max(parse_time(row["finishedAt"]) for row in units)
    return {
        "projectId": meta["projectId"],
        "operatorId": meta["operatorId"],
        "repositoryClass": meta["repositoryClass"],
        "isMethodologyRepository": False,
        "synthetic": False,
        "fixture": False,
        "startedAt": meta["startedAt"],
        "observedAt": observed_at.isoformat().replace("+00:00", "Z"),
        "comparableUnits": len(pairs),
        "baseline": phase_metrics("baseline"),
        "followup": phase_metrics("followup"),
        "privacy": dict(PRIVACY),
    }


def command_new_id(args: argparse.Namespace) -> int:
    prefix = {"project": "proj_", "operator": "op_", "comparison": "cmp_"}[args.kind]
    print(prefix + secrets.token_hex(6))
    return 0


def command_init(args: argparse.Namespace) -> int:
    if args.ledger.exists():
        return fail(str(args.ledger), "ledger already exists",
                    "choose a new path; never overwrite an enrolled pilot")
    if not args.consent:
        return fail("pilot enrollment", "explicit consent flag is missing",
                    "rerun only after the operator consents and add --consent")
    meta = {
        "recordType": "metadata",
        "version": 1,
        "projectId": args.project_id,
        "operatorId": args.operator_id,
        "repositoryClass": args.repository_class,
        "startedAt": args.started_at,
        "consent": True,
        "synthetic": False,
        "fixture": False,
        "privacy": dict(PRIVACY),
    }
    try:
        validate_metadata(meta, str(args.ledger))
    except PilotError as exc:
        return fail("pilot enrollment", str(exc),
                    "use pseudonymous IDs, a non-methodology class and a timezone timestamp")
    append_jsonl(args.ledger, meta)
    return 0


def command_append(args: argparse.Namespace) -> int:
    try:
        meta, units = load_ledger(args.ledger)
        unit = {
            "recordType": "unit",
            "phase": args.phase,
            "comparisonId": args.comparison_id,
            "startedAt": args.started_at,
            "finishedAt": args.finished_at,
            "verified": args.verified,
            "defectEscapes": args.defect_escapes,
            "falseCompletions": args.false_completions,
            "tokenUnits": args.token_units,
            "frictionEvents": args.friction_events,
            "criticalRegressions": args.critical_regressions,
        }
        validate_unit(unit, meta, f"{args.ledger}:new")
        if any(row["comparisonId"] == unit["comparisonId"]
               and row["phase"] == unit["phase"] for row in units):
            raise PilotError(
                f"{args.ledger}: duplicate {unit['phase']} for {unit['comparisonId']}"
            )
    except PilotError as exc:
        return fail("pilot unit", str(exc),
                    "repair the pseudonymous paired unit; never edit prior ledger lines")
    append_jsonl(args.ledger, unit)
    return 0


def command_aggregate(args: argparse.Namespace) -> int:
    try:
        result = aggregate_ledger(args.ledger)
    except (OSError, PilotError) as exc:
        return fail("pilot aggregate", str(exc),
                    "record exactly one verified baseline and followup for every comparison ID")
    atomic_json(args.out, result)
    return 0


def command_attest(args: argparse.Namespace) -> int:
    missing_flags = [
        flag for flag, present in (
            ("--consent", args.consent),
            ("--independent-operator", args.independent_operator),
            ("--not-author-affiliated", args.not_author_affiliated),
            ("--accurate", args.accurate),
        ) if not present
    ]
    if missing_flags:
        return fail("pilot attestation", "missing explicit attestations: " + ", ".join(missing_flags),
                    "the operator and verifier must truthfully opt in to every attestation")
    try:
        expected = aggregate_ledger(args.ledger)
        supplied = json.loads(args.aggregate.read_text(encoding="utf-8"))
        if supplied != expected:
            raise PilotError("aggregate does not replay from the raw ledger")
        if not OPERATOR_RE.fullmatch(args.verified_by):
            raise PilotError("verifiedBy is not pseudonymous")
        if args.verified_by == expected["operatorId"]:
            raise PilotError("source hash verifier must differ from the project operator")
        validate_time(args.verified_at, "verifiedAt")
        if parse_time(args.verified_at) < parse_time(expected["observedAt"]):
            raise PilotError("verifiedAt predates the final observed unit")
        record = dict(expected)
        record["sourceHashes"] = [{
            "artifactDigest": hashlib.sha256(canonical_json(expected)).hexdigest(),
            "sha256": hashlib.sha256(args.ledger.read_bytes()).hexdigest(),
            "verifiedBy": args.verified_by,
            "verifiedAt": args.verified_at,
        }]
        record["attestation"] = {
            "consent": True,
            "independentOperator": True,
            "authorAffiliated": False,
            "accurate": True,
            "recordDigest": "",
        }
        record["attestation"]["recordDigest"] = record_digest(record)
        prohibited = forbidden_paths(record)
        if prohibited:
            raise PilotError("attested record contains prohibited fields: " + ", ".join(prohibited))
    except (OSError, json.JSONDecodeError, PilotError) as exc:
        return fail("pilot attestation", str(exc),
                    "replay the aggregate and have a distinct independent operator verify the hashes")
    atomic_json(args.out, record)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Collect pseudonymous external pilot outcomes")
    sub = root.add_subparsers(dest="command")

    new_id = sub.add_parser("new-id")
    new_id.add_argument("--kind", choices=("project", "operator", "comparison"), required=True)
    new_id.set_defaults(func=command_new_id)

    init = sub.add_parser("init")
    init.add_argument("--ledger", type=Path, required=True)
    init.add_argument("--project-id", required=True)
    init.add_argument("--operator-id", required=True)
    init.add_argument("--repository-class", required=True)
    init.add_argument("--started-at", required=True)
    init.add_argument("--consent", action="store_true")
    init.set_defaults(func=command_init)

    append = sub.add_parser("append")
    append.add_argument("--ledger", type=Path, required=True)
    append.add_argument("--phase", choices=PHASES, required=True)
    append.add_argument("--comparison-id", required=True)
    append.add_argument("--started-at", required=True)
    append.add_argument("--finished-at", required=True)
    append.add_argument("--verified", action="store_true")
    append.add_argument("--defect-escapes", type=positive_integer, required=True)
    append.add_argument("--false-completions", type=positive_integer, required=True)
    append.add_argument("--token-units", type=positive_number, required=True)
    append.add_argument("--friction-events", type=positive_integer, required=True)
    append.add_argument("--critical-regressions", type=positive_integer, required=True)
    append.set_defaults(func=command_append)

    aggregate = sub.add_parser("aggregate")
    aggregate.add_argument("--ledger", type=Path, required=True)
    aggregate.add_argument("--out", type=Path, required=True)
    aggregate.set_defaults(func=command_aggregate)

    attest = sub.add_parser("attest")
    attest.add_argument("--ledger", type=Path, required=True)
    attest.add_argument("--aggregate", type=Path, required=True)
    attest.add_argument("--verified-by", required=True)
    attest.add_argument("--verified-at", required=True)
    attest.add_argument("--out", type=Path, required=True)
    attest.add_argument("--consent", action="store_true")
    attest.add_argument("--independent-operator", action="store_true")
    attest.add_argument("--not-author-affiliated", action="store_true")
    attest.add_argument("--accurate", action="store_true")
    attest.set_defaults(func=command_attest)
    return root


def main() -> int:
    if len(sys.argv) == 1:
        return 0
    args = parser().parse_args()
    if not hasattr(args, "func"):
        return fail("pilot command", "no subcommand selected",
                    "use new-id, init, append, aggregate or attest", 2)
    try:
        return int(args.func(args))
    except (OSError, ValueError) as exc:
        return fail("pilot command", str(exc), "repair the input and retry")


if __name__ == "__main__":
    raise SystemExit(main())
