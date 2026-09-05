#!/usr/bin/env python3
"""Q6 frozen CMP setup: validate real receipts and calculate no decision."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "PROTOCOL.json"
INSTRUMENT = Path(__file__).resolve()
CAMPAIGN_NAME = "CAMPAIGN.json"
WINDOW_DAYS = 90
COHORT_SIZE = 20


class ProtocolError(ValueError):
    pass


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def parse_json_bytes(data: bytes, label: str) -> object:
    def duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ProtocolError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result
    def constant(value: str) -> object:
        raise ProtocolError(f"{label}: non-finite JSON number {value}")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=duplicates,
                          parse_constant=constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"{label}: invalid UTF-8 JSON") from exc


def load_object(path: Path, label: str) -> dict:
    value = parse_json_bytes(path.read_bytes(), label)
    if not isinstance(value, dict):
        raise ProtocolError(f"{label}: expected JSON object")
    return value


def nonempty(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError(f"missing or invalid {label}")
    return value


def utc(value: object, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(nonempty(value, label).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProtocolError(f"invalid UTC {label}") from exc
    if parsed.tzinfo is None:
        raise ProtocolError(f"UTC offset required for {label}")
    return parsed.astimezone(timezone.utc)


def protocol_data(protocol: Path = PROTOCOL) -> dict:
    value = load_object(protocol, "protocol")
    aliases = value.get("repository", {}).get("aliases")
    if not isinstance(aliases, list) or not all(isinstance(x, str) and x for x in aliases):
        raise ProtocolError("protocol repository aliases are invalid")
    return value


def hex_value(value: object, label: str, lengths: tuple = (64,)) -> str:
    if not isinstance(value, str) or len(value) not in lengths or any(c not in "0123456789abcdef" for c in value):
        raise ProtocolError(f"invalid hexadecimal {label}")
    return value


def current_context(path: Path) -> dict:
    value = load_object(path, "current context")
    for key in ("vendor", "model", "harnessMajor", "promptPolicyDigest"):
        nonempty(value.get(key), f"current context.{key}")
    if set(value) != {"vendor", "model", "harnessMajor", "promptPolicyDigest"}:
        raise ProtocolError("current context fields must match the frozen schema")
    hex_value(value["promptPolicyDigest"], "prompt policy digest")
    if not value["harnessMajor"].isdigit():
        raise ProtocolError("harnessMajor must be an explicit decimal major version")
    return value


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=20)
    if result.returncode:
        raise ProtocolError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def source_file_at_head(root: Path, source: Path, head: str, label: str) -> str:
    """Require the actual adjacent module/protocol bytes to be tracked at HEAD."""
    try:
        relative = source.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ProtocolError(f"{label} is outside frozen source root") from exc
    tracked = git(root, "ls-files", "--error-unmatch", "--", relative)
    if tracked != relative:
        raise ProtocolError(f"{label} is not tracked in source root")
    expected = subprocess.run(["git", "show", f"{head}:{relative}"], cwd=root,
                              capture_output=True)
    if expected.returncode or digest_bytes(expected.stdout) != digest_file(source):
        raise ProtocolError(f"{label} bytes differ from clean merged source")
    return relative


def publish_exclusive(path: Path, value: dict) -> None:
    """Publish immutable JSON without an overwrite race (hard link on POSIX)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ProtocolError("stale campaign transaction exists") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
        try:
            if os.name == "nt": os.rename(temporary, path)
            else: os.link(temporary, path)
        except FileExistsError as exc:
            raise ProtocolError("campaign output is exclusive and already exists") from exc
    finally:
        temporary.unlink(missing_ok=True)


def freeze(output: Path, context_path: Path, root: Path,
           protocol: Path = PROTOCOL, instrument: Path = INSTRUMENT) -> dict:
    """Atomically create a single campaign from the actual clean merged source."""
    if protocol.resolve() != PROTOCOL or instrument.resolve() != INSTRUMENT:
        raise ProtocolError("freeze must bind the running instrument and its adjacent protocol")
    target = output / CAMPAIGN_NAME
    if target.exists():
        raise ProtocolError("campaign output is exclusive and already exists")
    context = current_context(context_path)
    root = root.resolve()
    if git(root, "status", "--porcelain"):
        raise ProtocolError("freeze requires a clean merged source")
    head = git(root, "rev-parse", "HEAD")
    git(root, "merge-base", "--is-ancestor", head, "origin/main")
    protocol_path = source_file_at_head(root, protocol, head, "protocol")
    instrument_path = source_file_at_head(root, instrument, head, "instrument")
    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    campaign = {
        "schemaVersion": 1, "protocolVersion": protocol_data(protocol).get("version"),
        "createdAt": created, "sourceHead": head, "windowDays": WINDOW_DAYS,
        "protocolSha256": digest_file(protocol), "instrumentSha256": digest_file(instrument),
        "context": context, "protocolPath": protocol_path, "instrumentPath": instrument_path,
        "status": "UNVALIDATED",
    }
    campaign["campaignSha256"] = digest_bytes(canonical(campaign))
    publish_exclusive(target, campaign)
    return campaign


def validate_campaign(campaign_path: Path, context_path: Path,
                      protocol: Path = PROTOCOL, instrument: Path = INSTRUMENT) -> dict:
    campaign = load_object(campaign_path, "campaign")
    required = ("schemaVersion", "protocolVersion", "createdAt", "sourceHead", "windowDays",
                "protocolSha256", "instrumentSha256", "context", "protocolPath", "instrumentPath",
                "status", "campaignSha256")
    if any(key not in campaign for key in required) or campaign.get("schemaVersion") != 1:
        raise ProtocolError("campaign schema is incomplete")
    stored = campaign.pop("campaignSha256")
    if stored != digest_bytes(canonical(campaign)):
        raise ProtocolError("campaign seal mismatch")
    campaign["campaignSha256"] = stored
    if (campaign.get("protocolVersion") != protocol_data(protocol).get("version")
            or campaign.get("windowDays") != WINDOW_DAYS or campaign.get("status") != "UNVALIDATED"):
        raise ProtocolError("campaign window or status invalid")
    hex_value(campaign["sourceHead"], "campaign.sourceHead", (40, 64))
    if utc(campaign.get("createdAt"), "campaign.createdAt") > datetime.now(timezone.utc):
        raise ProtocolError("campaign creation time is in the future")
    if campaign.get("protocolSha256") != digest_file(protocol):
        raise ProtocolError("protocol hash drift")
    if campaign.get("instrumentSha256") != digest_file(instrument):
        raise ProtocolError("instrument hash drift")
    actual = current_context(context_path)
    if campaign.get("context") != actual:
        raise ProtocolError("campaign context stale")
    return campaign


def receipt(receipt: dict, aliases: set[str]) -> None:
    required = ("version", "kind", "createdAt", "unitId", "riskTier", "producerRunId", "candidate",
                "candidateDigest", "runs", "verdict", "receiptSha256", "declaredInputs")
    if any(key not in receipt for key in required):
        raise ProtocolError("receipt missing real producer fields")
    if type(receipt.get("version")) is not int or receipt["version"] != 1 or receipt["kind"] != "machine-verification" or receipt["verdict"] not in ("PASSED", "FAILED"):
        raise ProtocolError("receipt kind or verdict invalid")
    utc(receipt["createdAt"], "receipt.createdAt")
    nonempty(receipt["unitId"], "receipt.unitId"); nonempty(receipt["producerRunId"], "receipt.producerRunId")
    candidate = receipt["candidate"]
    if not isinstance(candidate, dict) or candidate.get("repository") not in aliases:
        raise ProtocolError("receipt repository is not a frozen alias")
    tree = hex_value(candidate.get("reviewedTree"), "candidate.reviewedTree", (40, 64))
    hex_value(candidate.get("baseCommit"), "candidate.baseCommit", (40, 64))
    for field in ("diffHash", "scopeContractHash", "acceptanceContractHash", "rubricHash"):
        hex_value(candidate.get(field), f"candidate.{field}")
    nonempty(candidate.get("methodologyVersion"), "candidate.methodologyVersion")
    if candidate.get("riskTier") != receipt["riskTier"]:
        raise ProtocolError("candidate and receipt risk tier mismatch")
    if receipt.get("candidateDigest") != "sha256:" + digest_bytes(canonical(candidate)):
        raise ProtocolError("candidateDigest mismatch")
    if not isinstance(receipt.get("riskTier"), str) or receipt["riskTier"] not in ("low", "medium", "high", "unknown"):
        raise ProtocolError("receipt riskTier invalid")
    if not isinstance(receipt["runs"], list) or not receipt["runs"]:
        raise ProtocolError("receipt runs missing")
    producer = receipt.get("producer")
    if (not isinstance(producer, dict) or producer.get("id") != "itd-verification-loop"
            or producer.get("role") != "machine-verifier" or not isinstance(producer.get("host"), str)
            or not producer["host"].strip()):
        raise ProtocolError("receipt producer provenance invalid")
    hex_value(receipt.get("policySha256"), "receipt.policySha256")
    run_id = nonempty(receipt.get("producerRunId"), "receipt.producerRunId")
    hex_value(run_id, "receipt.producerRunId", (32,))
    assurance = receipt.get("assurance")
    if (not isinstance(assurance, dict) or assurance.get("trustRoot") != "honest-host-orchestrator"
            or assurance.get("class") != "integrity-and-process"
            or assurance.get("samePrincipalByzantineResistance") is not False):
        raise ProtocolError("receipt assurance boundary invalid")
    ids = set()
    previous_end = None
    for run in receipt["runs"]:
        required_run=("command","commandSha256","shell","shellSha256","startedAt","completedAt","executionMode","executedTree","exitCode","stdoutSha256","stderrSha256")
        if (not isinstance(run, dict) or any(key not in run for key in required_run)
                or run.get("executedTree") != tree or type(run.get("exitCode")) is not int
                or run.get("executionMode") != "isolated-staged-tree"):
            raise ProtocolError("receipt run does not bind reviewed tree and exit code")
        allowed_run = set(required_run) | {"id", "timeoutSeconds"}
        if set(run) - allowed_run:
            raise ProtocolError("receipt run has non-producer fields")
        run_id = nonempty(run.get("id"), "run.id")
        if run_id in ids or type(run.get("timeoutSeconds")) is not int or run["timeoutSeconds"] <= 0:
            raise ProtocolError("duplicate run id or invalid timeout")
        ids.add(run_id)
        nonempty(run["shell"], "run.shell")
        nonempty(run["command"], "run.command")
        if run["commandSha256"] != digest_bytes(run["command"].encode("utf-8")):
            raise ProtocolError("receipt command hash mismatch")
        if run["shell"] == "unavailable":
            raise ProtocolError("unavailable shell is missing oracle evidence")
        for field in ("shellSha256", "stdoutSha256", "stderrSha256"):
            hex_value(run[field], f"run.{field}")
        began = utc(run["startedAt"], "run.startedAt")
        ended = utc(run["completedAt"], "run.completedAt")
        if ended < began or ended > utc(receipt["createdAt"], "receipt.createdAt") or (previous_end and began < previous_end):
            raise ProtocolError("receipt run chronology invalid")
        previous_end = ended
    expected = "PASSED" if all(run["exitCode"] == 0 for run in receipt["runs"]) else "FAILED"
    if receipt["verdict"] != expected: raise ProtocolError("receipt verdict contradicts exit codes")
    inputs=receipt.get("declaredInputs", [])
    if not isinstance(inputs, list): raise ProtocolError("declaredInputs invalid")
    for item in inputs:
        if not isinstance(item, dict) or item.get("kind") not in ("file", "directory") or not isinstance(item.get("path"), str):
            raise ProtocolError("declared input shape invalid")
        portable_path(item["path"])
        hex_value(item.get("sha256"), "declared input digest")
        if type(item.get("fileCount")) is not int or item["fileCount"] < 0 or (item["kind"] == "file" and item["fileCount"] != 1):
            raise ProtocolError("declared input file count invalid")
    copied = dict(receipt); seal = copied.pop("receiptSha256")
    if seal != digest_bytes(canonical(copied)):
        raise ProtocolError("receiptSha256 mismatch")


def portable_path(value: object) -> str:
    text = nonempty(value, "relative source path")
    parts = text.split("/")
    if any(part in ("", ".", "..") for part in parts) or any(c in text for c in "\\:\0"):
        raise ProtocolError(f"noncanonical source path: {text}")
    if parts[0] == ".git":
        raise ProtocolError("Git database cannot be a source input")
    return text


def source_path(root: Path, relative: object, directory: bool = False) -> Path:
    relative = portable_path(relative)
    current = root
    for component in relative.split("/"):
        current = current / component
        junction = getattr(current, "is_junction", lambda: False)
        if current.is_symlink() or junction():
            raise ProtocolError(f"linked source component forbidden: {relative}")
    if not (current.is_dir() if directory else current.is_file()):
        raise ProtocolError(f"source {'directory' if directory else 'file'} missing: {relative}")
    return current


def identity_key(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ProtocolError("identity requires project, ledger, unitId and activationEventId")
    return tuple(nonempty(part, "identity component") for part in value)


def input_manifest(root: Path, item: dict) -> dict:
    """Mirror the real producer input_snapshot byte/entry hashing algorithm."""
    relative = portable_path(item.get("path"))
    is_directory = item.get("kind") == "directory"
    if item.get("kind") not in ("file", "directory"):
        raise ProtocolError("unsupported declared input kind")
    path = source_path(root, relative, is_directory)
    if not is_directory:
        return {"path": relative, "kind": "file", "sha256": digest_file(path), "fileCount": 1}
    entries = []
    for child in sorted(path.rglob("*"), key=lambda x: x.as_posix()):
        child_rel = child.relative_to(path).as_posix()
        child_source = child.relative_to(root).as_posix()
        source_path(root, child_source, child.is_dir())
        if child.is_dir():
            entries.append({"kind": "directory", "path": child_rel})
        else:
            entries.append({"kind": "file", "path": child_rel, "sha256": digest_file(child)})
    return {"path": relative, "kind": "directory", "sha256": digest_bytes(canonical(entries)),
            "fileCount": sum(item["kind"] == "file" for item in entries)}


def source_inventory(root: Path, inventory: object) -> dict[str, bytes]:
    if root.is_symlink() or not root.is_dir():
        raise ProtocolError("source root must be an existing real directory")
    if not isinstance(inventory, list):
        raise ProtocolError("sourceInventory must enumerate every source file")
    actual = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        source_path(root, relative, path.is_dir())
        if path.is_file():
            actual.add(relative)
    declared = {}
    for item in inventory:
        if not isinstance(item, dict):
            raise ProtocolError("invalid inventory entry")
        relative = portable_path(item.get("path"))
        if relative in declared:
            raise ProtocolError("duplicate source inventory path")
        declared[relative] = item.get("sha256")
    if set(declared) != actual:
        raise ProtocolError("source inventory omission or undeclared file; rebuild complete inventory")
    contents = {}
    for relative in sorted(actual):
        data = source_path(root, relative).read_bytes()
        if digest_bytes(data) != declared[relative]:
            raise ProtocolError(f"source inventory hash mismatch: {relative}")
        contents[relative] = data
    return contents


def source_objects(data: bytes, label: str) -> list[dict]:
    """Recognize JSON/JSONL content, never trust a filename or caller kind label."""
    stripped = data.lstrip()
    if not stripped.startswith((b"{", b"[")):
        return []  # Opaque declared-input bytes are still bound by inventory.
    try:
        parsed = parse_json_bytes(data, label)
    except ProtocolError:
        lines = [line for line in data.splitlines() if line.strip()]
        if len(lines) <= 1:
            raise
        parsed = [parse_json_bytes(line, label) for line in lines]
    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list) and all(isinstance(x, dict) for x in parsed):
        return parsed
    raise ProtocolError(f"{label}: structured source must contain objects")


def lifecycle_cycles(contents: dict[str, bytes], project: str) -> dict[tuple, dict]:
    cycles, event_ids, open_cycles = {}, {}, {}
    for path, data in contents.items():
        for event in source_objects(data, path):
            if event.get("type") != "unit":
                continue
            fields = ("id", "at", "actor", "name", "decision", "ledger")
            if any(not isinstance(event.get(k), str) or not event[k] for k in fields):
                raise ProtocolError(f"{path}: incomplete lifecycle event")
            event_bytes = canonical(event)
            if event["id"] in event_ids:
                if event_ids[event["id"]] != event_bytes:
                    raise ProtocolError("conflicting duplicate event id")
                continue
            event_ids[event["id"]] = event_bytes
            when = utc(event["at"], "event.at")
            pair = (project, event["ledger"], event["name"])
            if event["decision"] == "activated":
                if pair in open_cycles:
                    raise ProtocolError("overlapping activation cycles")
                key = (*pair, event["id"])
                cycles[key] = {"identity": key, "activated": when, "closed": None,
                               "terminal": None, "eventsPath": path}
                open_cycles[pair] = key
            elif event["decision"] in ("verified", "failed", "blocked"):
                key = open_cycles.pop(pair, None)
                if key is None:
                    raise ProtocolError("terminal event has no unambiguous activation")
                cycle = cycles[key]
                if path != cycle["eventsPath"] or when <= cycle["activated"]:
                    raise ProtocolError("lifecycle source or activation-terminal chronology mismatch")
                cycle.update(closed=when, terminal=event["decision"])
    return cycles


def lineage_descriptor(root: Path, first: dict, identity: tuple,
                       descriptor_path: str, repository: Path | None) -> dict:
    descriptor_path = portable_path(descriptor_path)
    matched = []
    for item in first["declaredInputs"]:
        input_path = portable_path(item.get("path"))
        if descriptor_path == input_path or (item["kind"] == "directory" and descriptor_path.startswith(input_path + "/")):
            actual = input_manifest(root, item)
            if any(actual[k] != item.get(k) for k in actual):
                raise ProtocolError("declared lineage input bytes or file count mismatch")
            matched.append(source_path(root, descriptor_path).read_bytes())
    if len(matched) > 1:
        raise ProtocolError("overlapping declared lineage inputs")
    if matched:
        data = matched[0]
    else:
        if repository is None:
            raise ProtocolError("first receipt lacks bound lineage bytes; supply actual candidate Git repository")
        tree = first["candidate"]["reviewedTree"]
        entry = git(repository, "ls-tree", tree, "--", descriptor_path)
        if not entry.startswith(("100644 blob ", "100755 blob ")):
            raise ProtocolError("lineage is not a regular blob in the first candidate tree")
        result = subprocess.run(["git", "cat-file", "blob", f"{tree}:{descriptor_path}"],
                                cwd=repository, capture_output=True, timeout=20)
        if result.returncode:
            raise ProtocolError("candidate lineage Git blob unavailable")
        data = result.stdout
    value = parse_json_bytes(data, "bound lineage descriptor")
    if not isinstance(value, dict) or value.get("schemaVersion") != 1 or identity_key(value.get("identity")) != identity:
        raise ProtocolError("lineage descriptor identity or schema mismatch")
    if not isinstance(value.get("parents"), list):
        raise ProtocolError("lineage parents must be explicit")
    parents = [identity_key(x) for x in value["parents"]]
    if len(set(parents)) != len(parents):
        raise ProtocolError("duplicate lineage parent")
    return {"parents": parents}


def validate_graph(rows: list[dict]) -> None:
    by_key = {row["identity"]: row for row in rows}
    if len(by_key) != len(rows):
        raise ProtocolError("duplicate lifecycle identity")
    visiting, visited = set(), set()
    def visit(key):
        if key in visiting:
            raise ProtocolError("lineage cycle")
        if key in visited:
            return
        visiting.add(key)
        row = by_key[key]
        for parent in row["parents"]:
            if parent not in by_key:
                raise ProtocolError("missing or foreign lineage parent")
            visit(parent)
            ancestor = by_key[parent]
            if ancestor["closed"] is None or ancestor["closed"] > row["activated"]:
                raise ProtocolError("parent must close before descendant activation")
        visiting.remove(key)
        visited.add(key)
    for key in by_key:
        visit(key)


class ReconciledRows(list):
    """Rows plus a derived source census; never persisted as a second ledger."""
    def __init__(self, rows, audit):
        super().__init__(rows)
        self.audit = audit


def reconcile(snapshot_path: Path, source_root: Path, campaign_path: Path,
              protocol: Path, instrument: Path, context_path: Path) -> tuple[list[dict], dict]:
    campaign = validate_campaign(campaign_path, context_path, protocol, instrument)
    snapshot = load_object(snapshot_path, "snapshot")
    root = source_root.absolute()
    contents = source_inventory(root, snapshot.get("sourceInventory"))
    definition = protocol_data(protocol)
    project = definition["repository"]["canonical"]
    aliases = set(definition["repository"]["aliases"])
    repository = snapshot.get("repositoryPath")
    if repository is not None:
        if repository not in aliases:
            raise ProtocolError("Git repository path is not a frozen alias")
        repository = Path(repository)
        if Path(git(repository, "rev-parse", "--show-toplevel")).resolve() != repository.resolve():
            raise ProtocolError("repositoryPath must name its Git root")
    receipts, run_ids = [], {}
    for path, data in contents.items():
        for value in source_objects(data, path):
            if value.get("kind") != "machine-verification":
                continue
            receipt(value, aliases)
            prior = run_ids.get(value["producerRunId"])
            if prior is not None:
                if prior != value["receiptSha256"]:
                    raise ProtocolError("conflicting producerRunId copies")
                continue
            run_ids[value["producerRunId"]] = value["receiptSha256"]
            if ":" not in value["unitId"]:  # Review/canary subclaims are not primary-unit trials.
                receipts.append(value)
    cycles = lifecycle_cycles(contents, project)
    units = snapshot.get("units")
    if not isinstance(units, list):
        raise ProtocolError("snapshot units must enumerate prospective lifecycle cycles")
    declared = {}
    for row in units:
        if not isinstance(row, dict):
            raise ProtocolError("invalid unit row")
        key = identity_key([row.get(k) for k in ("project", "ledger", "unitId", "activationEventId")])
        if key in declared or key[0] != project or key not in cycles:
            raise ProtocolError("duplicate, foreign or unknown lifecycle identity")
        if row.get("eventsPath") != cycles[key]["eventsPath"]:
            raise ProtocolError("unit eventsPath must bind the actual cycle source")
        declared[key] = row
    start = utc(campaign["createdAt"], "campaign.createdAt")
    end = start + timedelta(days=WINDOW_DAYS)
    excluded = set(definition["cohort"].get("excludedUnitIds", ["Q6-SETUP", "Q6-DECISION"]))
    eligible = {key for key, cycle in cycles.items() if key[2] not in excluded and
                ((cycle["closed"] is not None and start < cycle["closed"] < end) or
                 (start <= cycle["activated"] < end))}
    if set(declared) != eligible:
        raise ProtocolError("unit inventory omits or adds a prospective lifecycle cycle")
    results = []
    for key in sorted(declared):
        cycle = dict(cycles[key])
        if cycle["activated"] < start:
            raise ProtocolError("prefreeze lifecycle cannot supply prospective lineage")
        choices = [r for r in receipts if r["unitId"] == key[2] and
                   cycle["activated"] <= utc(r["createdAt"], "receipt.createdAt") and
                   (cycle["closed"] is None or utc(r["createdAt"], "receipt.createdAt") <= cycle["closed"])]
        # Same unit name in different ledgers is ambiguous: a receipt has no ledger field.
        for other_key, other in cycles.items():
            if other_key != key and other_key[2] == key[2] and any(
                other["activated"] <= utc(r["createdAt"], "receipt.createdAt") and
                (other["closed"] is None or utc(r["createdAt"], "receipt.createdAt") <= other["closed"])
                for r in choices):
                raise ProtocolError("primary receipt overlaps multiple ledger cycles")
        if not choices:
            raise ProtocolError("missing first machine evidence; do not impute an outcome")
        first = min(choices, key=lambda r: (utc(r["createdAt"], "receipt.createdAt"), r["producerRunId"]))
        if any(utc(run["startedAt"], "run.startedAt") < cycle["activated"] for run in first["runs"]):
            raise ProtocolError("first oracle began before this activation cycle")
        descriptor = lineage_descriptor(root, first, key, declared[key].get("lineagePath"), repository)
        cycle.update(receipt=first, parents=descriptor["parents"])
        results.append(cycle)
    validate_graph(results)
    exclusions = []
    for key, cycle in sorted(cycles.items()):
        if key not in eligible:
            reason = "preregistered excluded unit" if key[2] in excluded else "outside prospective population"
            exclusions.append({"identity": key, "reason": reason})
    audit = {"sourceFiles": len(contents), "uniqueMachineReceipts": len(run_ids),
             "primaryMachineReceipts": len(receipts), "lifecycleCycles": len(cycles),
             "includedCycles": len(results), "excludedCycles": exclusions}
    return ReconciledRows(results, audit), campaign


def fixed_cohort(rows: list[dict], campaign: dict) -> list[dict]:
    start = utc(campaign["createdAt"], "campaign.createdAt")
    end = start + timedelta(days=WINDOW_DAYS)
    roots = [row for row in rows if not row["parents"] and row["terminal"] == "verified" and
             row["closed"] is not None and start < row["closed"] < end]
    return sorted(roots, key=lambda row: (row["closed"], row["identity"]))[:COHORT_SIZE]


def population_summary(rows: list[dict], campaign: dict, roots: list[dict]) -> dict:
    selected = {row["identity"] for row in roots}
    classifications = []
    start = utc(campaign["createdAt"], "campaign.createdAt")
    end = start + timedelta(days=WINDOW_DAYS)
    for row in sorted(rows, key=lambda item: item["identity"]):
        if row["identity"] in selected:
            reason = "selected cohort root"
        elif row["parents"]:
            reason = "descendant, not an independent root"
        elif row["closed"] is None or row["closed"] >= end:
            reason = "censored root"
        elif row["terminal"] != "verified":
            reason = "root not verified"
        elif row["closed"] <= start:
            reason = "root outside window"
        else:
            reason = "later verified root, outside fixed first20"
        classifications.append({"identity": row["identity"], "reason": reason})
    return {**getattr(rows, "audit", {}), "cohortSize": len(roots), "classifications": classifications}


def score(rows: list[dict], campaign: dict) -> dict:
    """Pure synthetic-testable function. CLI disclosure uses guarded_score only."""
    validate_graph(rows)
    roots = fixed_cohort(rows, campaign)
    population = population_summary(rows, campaign, roots)
    if len(roots) < COHORT_SIZE:
        return {"status": "INSUFFICIENT_DATA", "reason": "fewer than first 20 verified roots", "population": population}
    end = utc(campaign["createdAt"], "campaign.createdAt") + timedelta(days=WINDOW_DAYS)
    used, values, censored = set(), [], []
    for root in roots:
        clade, todo = {}, [root["identity"]]
        while todo:
            parent = todo.pop()
            for row in rows:
                if parent in row["parents"] and row["identity"] not in clade:
                    clade[row["identity"]] = row
                    todo.append(row["identity"])
        if set(clade) & used:
            raise ProtocolError("overlapping cohort clades violate independent observations")
        used.update(clade)
        exposures = []
        for row in clade.values():
            if row["activated"] < root["closed"]:
                raise ProtocolError("descendant activation precedes root closure")
            if row["closed"] is None or row["closed"] >= end:
                censored.append(row["identity"])
                continue
            if not root["closed"] <= utc(row["receipt"]["createdAt"], "receipt.createdAt") < end:
                raise ProtocolError("first outcome outside prospective exposure window")
            exposures.append(row)
        if not exposures:
            return {"status": "INSUFFICIENT_DATA", "reason": "zero exposure in fixed cohort", "population": population}
        values.append({"root": root["identity"],
                       "cmp": sum(x["receipt"]["verdict"] == "PASSED" for x in exposures) / len(exposures)})
    return {"status": "UNVALIDATED", "scores": values, "censored": censored, "population": population,
            "operationalSignal": False, "d3Verdict": "NOT_RUN"}


def mature(campaign: dict) -> None:
    start = utc(campaign["createdAt"], "campaign.createdAt")
    now = datetime.now(timezone.utc)
    if now < start + timedelta(days=WINDOW_DAYS):
        raise ProtocolError("numeric disclosure unavailable before the 90-day window matures")
    if now >= start + timedelta(days=180):
        raise ProtocolError("campaign data timeout reached; no window extension permitted")


def validate_ratings(value: object, roots: list[dict]) -> list[dict]:
    if not isinstance(value, list):
        raise ProtocolError("complete owner ratings are required, not a roots-only seal")
    expected = {row["identity"] for row in roots}
    actual = set()
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != {"root", "rating"}:
            raise ProtocolError("each owner rating needs root identity and ordinal rating")
        key = identity_key(entry["root"])
        if key in actual or type(entry["rating"]) is not int or not 0 <= entry["rating"] <= 4:
            raise ProtocolError("duplicate root or invalid owner rating; use integer 0..4")
        actual.add(key)
    if len(expected) != COHORT_SIZE or actual != expected:
        raise ProtocolError("owner ratings must cover the exact first20 root cohort")
    return value


def seal_labels(rows: list[dict], campaign: dict, snapshot: Path, labels: Path, output: Path) -> None:
    mature(campaign)
    ratings = validate_ratings(load_object(labels, "owner labels").get("ratings"), fixed_cohort(rows, campaign))
    value = {"schemaVersion": 1, "campaignSha256": campaign["campaignSha256"],
             "snapshotSha256": digest_file(snapshot), "ratings": ratings,
             "sealedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    value["labelsSha256"] = digest_bytes(canonical(value))
    publish_exclusive(output, value)


def guarded_score(rows: list[dict], campaign: dict, labels_path: Path, snapshot: Path) -> dict:
    mature(campaign)
    labels = load_object(labels_path, "sealed owner labels")
    raw = {key: value for key, value in labels.items() if key != "labelsSha256"}
    if labels.get("schemaVersion") != 1 or labels.get("labelsSha256") != digest_bytes(canonical(raw)):
        raise ProtocolError("blind label seal mismatch")
    if labels.get("campaignSha256") != campaign["campaignSha256"] or labels.get("snapshotSha256") != digest_file(snapshot):
        raise ProtocolError("blind label campaign or source snapshot changed")
    sealed_at = utc(labels.get("sealedAt"), "labels.sealedAt")
    end = utc(campaign["createdAt"], "campaign.createdAt") + timedelta(days=WINDOW_DAYS)
    if not end <= sealed_at <= datetime.now(timezone.utc):
        raise ProtocolError("blind label seal time outside mature window")
    validate_ratings(labels.get("ratings"), fixed_cohort(rows, campaign))
    return score(rows, campaign)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode")
    freeze_parser = commands.add_parser("freeze")
    for option in ("--output", "--context", "--root"):
        freeze_parser.add_argument(option, type=Path, required=True)
    for mode in ("validate", "reconcile", "score", "seal-labels"):
        command = commands.add_parser(mode)
        command.add_argument("--campaign", type=Path, required=True)
        command.add_argument("--current-context", type=Path, required=True)
        if mode != "validate":
            command.add_argument("--snapshot", type=Path, required=True)
            command.add_argument("--source-root", type=Path, required=True)
        if mode == "seal-labels":
            command.add_argument("--labels", type=Path, required=True)
    args = parser.parse_args()
    if args.mode is None:
        return
    try:
        if args.mode == "freeze":
            freeze(args.output, args.context, args.root)
        elif args.mode == "validate":
            validate_campaign(args.campaign, args.current_context)
        else:
            rows, campaign = reconcile(args.snapshot, args.source_root, args.campaign,
                                       PROTOCOL, INSTRUMENT, args.current_context)
            labels_path = args.campaign.parent / "LABELS.json"
            if args.mode == "seal-labels":
                seal_labels(rows, campaign, args.snapshot, args.labels, labels_path)
            elif args.mode == "score":
                print(json.dumps(guarded_score(rows, campaign, labels_path, args.snapshot), sort_keys=True))
            else:
                print(json.dumps({"status": "RECONCILED", "population": population_summary(rows, campaign, fixed_cohort(rows, campaign))}))
    except (ProtocolError, OSError, TypeError, KeyError, RecursionError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}. Check the frozen protocol and source bindings; do not impute missing evidence.", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
