#!/usr/bin/env python3
"""Self-contained verifier for sealed historical Harness Demo pilot evidence."""
from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FROZEN_VERIFIER = ROOT / "tests" / "verify_harness_demo_absorption.py"
INDEX = ROOT / "docs" / "harness-demo-pilots" / "INDEX.json"
DEMAND = ROOT / "docs" / "semantic-navigation" / "DEMAND.json"
EVIDENCE = ROOT / "docs" / "harness-demo-pilots" / "PORTABLE_EVIDENCE.json"
SEAL = ROOT / "docs" / "harness-demo-pilots" / "PORTABLE_EVIDENCE.sha256"
REPAIR_FIXTURE = ROOT / "docs" / "harness-demo-pilots" / "HISTORICAL_REPAIR_FIXTURE.json"
REPAIR_SEAL = ROOT / "docs" / "harness-demo-pilots" / "HISTORICAL_REPAIR_FIXTURE.sha256"
EVIDENCE_SHA256 = "6dd88c9b1a604c075a227a9ab0a2181ce09a88b5f03a833016a529f71ff7d80e"
ARTIFACTS = {"packet", "session", "parentState", "adjudication", "machine",
             "checker", "checkerPrompt", "checkerReport", "semanticSources"}
JSON_FILE_MAX_BYTES = 512 * 1024
ENCODED_BLOB_MAX_BYTES = 512 * 1024
DECODED_BLOB_MAX_BYTES = 256 * 1024
AGGREGATE_DECODED_MAX_BYTES = 512 * 1024


class PortableEvidenceError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PortableEvidenceError(message)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def is_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        junction_probe = getattr(path, "is_junction", None)
        if callable(junction_probe) and junction_probe():
            return True
        attributes = int(getattr(path.lstat(), "st_file_attributes", 0) or 0)
    except (FileNotFoundError, OSError):
        return False
    return bool(
        attributes
        & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    )


def require_no_link_components(path: Path, label: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if os.path.lexists(current):
            require(
                not is_link_or_reparse(current),
                f"{label} contains a symlink or reparse component: {current}",
            )


def bounded_file_bytes(path: Path, label: str,
                       limit: int = JSON_FILE_MAX_BYTES) -> bytes:
    fd: int | None = None
    try:
        require_no_link_components(path, label)
        before = path.lstat()
        require(
            not is_link_or_reparse(path)
            and stat.S_ISREG(before.st_mode)
            and before.st_size <= limit,
            f"{label} is not a bounded regular file",
        )
        flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
        flags |= int(getattr(os, "O_NOFOLLOW", 0))
        fd = os.open(path, flags)
        opened = os.fstat(fd)
        require(
            stat.S_ISREG(opened.st_mode)
            and (opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino),
            f"{label} changed while opening",
        )
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(fd, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        require_no_link_components(path, label)
        current = path.lstat()
        require(
            len(raw) <= limit
            and not is_link_or_reparse(path)
            and (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            == (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns),
            f"{label} changed while reading or exceeds its size limit",
        )
        return raw
    except OSError as exc:
        raise PortableEvidenceError(f"{label} is unavailable: {exc}") from exc
    finally:
        if fd is not None:
            os.close(fd)


def decode_b64(content: object, label: str, budget: list[int]) -> bytes:
    require(
        isinstance(content, str)
        and len(content) <= ENCODED_BLOB_MAX_BYTES,
        f"{label} encoded payload exceeds its size limit",
    )
    encoded_length = len(content)
    padding = len(content) - len(content.rstrip("="))
    remaining_budget = AGGREGATE_DECODED_MAX_BYTES - budget[0]
    predicted_length = (
        (encoded_length // 4) * 3 - padding
        if encoded_length % 4 == 0 and padding <= 2
        else DECODED_BLOB_MAX_BYTES + 1
    )
    require(
        predicted_length <= DECODED_BLOB_MAX_BYTES
        and predicted_length <= remaining_budget,
        f"{label} decoded payload exceeds its size limit",
    )
    try:
        raw = base64.b64decode(content, validate=True)
    except Exception as exc:
        raise PortableEvidenceError(f"{label} is not canonical base64") from exc
    require(
        len(raw) == predicted_length
        and base64.b64encode(raw).decode("ascii") == content,
        f"{label} is not canonical base64",
    )
    budget[0] += len(raw)
    return raw


def object_from(raw: bytes, label: str) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise PortableEvidenceError(f"{label} is invalid JSON: {exc}") from exc
    require(isinstance(value, dict), f"{label} must be a JSON object")
    return value


def validate_bounded_reader_guards() -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="itd-portable-reader-") as raw:
        root = Path(raw)
        stable = root / "stable.json"
        stable.write_text("{}\n", encoding="utf-8")
        require(
            bounded_file_bytes(stable, "stable portable fixture") == b"{}\n",
            "bounded reader changed stable input",
        )

        replacement = root / "replacement.json"
        replacement.write_text('{"replacement":true}\n', encoding="utf-8")
        original_read = os.read
        replaced = False

        def replace_during_read(fd: int, size: int) -> bytes:
            nonlocal replaced
            chunk = original_read(fd, size)
            if not replaced:
                os.replace(replacement, stable)
                replaced = True
            return chunk

        os.read = replace_during_read
        try:
            try:
                bounded_file_bytes(stable, "racing portable fixture")
            except PortableEvidenceError:
                pass
            else:
                raise PortableEvidenceError("portable replacement race was accepted")
        finally:
            os.read = original_read

        real_parent = root / "real-parent"
        real_parent.mkdir()
        (real_parent / "fixture.json").write_text("{}\n", encoding="utf-8")
        linked_parent = root / "linked-parent"
        try:
            linked_parent.symlink_to(real_parent, target_is_directory=True)
        except OSError:
            if os.name == "nt":
                created = subprocess.run(
                    [
                        os.environ.get("COMSPEC", "cmd.exe"),
                        "/d",
                        "/c",
                        "mklink",
                        "/J",
                        str(linked_parent),
                        str(real_parent),
                    ],
                    capture_output=True,
                    check=False,
                    shell=False,
                )
                require(
                    created.returncode == 0,
                    "cannot create Windows junction rejection fixture",
                )
            else:
                raise
        try:
            bounded_file_bytes(
                linked_parent / "fixture.json",
                "linked portable fixture",
            )
        except PortableEvidenceError:
            pass
        else:
            raise PortableEvidenceError("portable link/reparse ancestor was accepted")
        finally:
            if os.name == "nt" and linked_parent.exists():
                os.rmdir(linked_parent)

    return {
        "replacementRace": "PASSED",
        "linkOrReparseAncestor": "PASSED",
    }


def receipt_valid(receipt: dict) -> bool:
    expected = receipt.get("receiptSha256")
    value = dict(receipt)
    value.pop("receiptSha256", None)
    return isinstance(expected, str) and expected == hashlib.sha256(canonical(value)).hexdigest()


def validate_portable_accepted_repair(contract: dict, fixture: dict) -> None:
    repair = contract.get("repairApprovalProvenance") or {}
    require(
        set(fixture) == {
            "version",
            "kind",
            "baseCandidateTree",
            "acceptedRepairCandidateTree",
            "changedPaths",
            "acceptedBlobs",
        }
        and fixture.get("version") == 1
        and fixture.get("kind") == "accepted-historical-repair-fixture",
        "portable historical repair fixture contract is not closed",
    )
    changed = fixture.get("changedPaths")
    blobs = fixture.get("acceptedBlobs")
    require(
        fixture.get("baseCandidateTree") == repair.get("baseCandidateTree")
        and fixture.get("acceptedRepairCandidateTree")
        == repair.get("acceptedRepairCandidateTree")
        and changed == repair.get("allowedChangedPaths")
        and isinstance(blobs, dict)
        and set(blobs) == set(changed or []),
        "portable historical repair fixture does not match the frozen repair",
    )
    expected_seals = repair.get("acceptedRepairSeal") or {}
    require(
        set(expected_seals) == set(blobs),
        "portable historical repair blob inventory is incomplete",
    )
    budget = [0]
    for path in changed:
        item = blobs.get(path)
        require(
            isinstance(item, dict)
            and set(item) == {"sha256", "encoding", "content"}
            and item.get("encoding") == "base64",
            f"portable historical repair blob metadata is invalid: {path}",
        )
        raw = decode_b64(
            item.get("content"),
            f"portable historical repair blob {path}",
            budget,
        )
        observed = hashlib.sha256(raw).hexdigest()
        require(
            observed == item.get("sha256") == expected_seals.get(path),
            f"portable historical repair blob seal mismatch: {path}",
        )


def verified_historical_repair(contract: dict) -> dict:
    raw = bounded_file_bytes(REPAIR_FIXTURE, "portable historical repair fixture")
    digest = hashlib.sha256(raw).hexdigest()
    require(
        bounded_file_bytes(REPAIR_SEAL, "portable historical repair fixture seal", 4096)
        .decode("ascii")
        == f"{digest}  HISTORICAL_REPAIR_FIXTURE.json\n",
        "portable historical repair fixture seal differs",
    )
    fixture = object_from(raw, "portable historical repair fixture")
    validate_portable_accepted_repair(contract, fixture)
    return fixture


def decode_artifacts(row: dict, budget: list[int]) -> tuple[dict[str, bytes], dict[str, dict]]:
    artifacts = row.get("artifacts")
    require(isinstance(artifacts, dict) and set(artifacts) == ARTIFACTS,
            "portable artifact graph is incomplete")
    decoded: dict[str, bytes] = {}
    values: dict[str, dict] = {}
    for name, artifact in artifacts.items():
        require(isinstance(artifact, dict)
                and set(artifact) == {"path", "sha256", "encoding", "content"}
                and artifact.get("encoding") == "base64",
                f"artifact metadata is not closed: {name}")
        path = str(artifact.get("path") or "")
        pure = PurePosixPath(path)
        require(path and pure.as_posix() == path and not pure.is_absolute()
                and ".." not in pure.parts and "\\" not in path and ":" not in path,
                f"artifact path is not canonical: {name}")
        raw = decode_b64(artifact.get("content"), f"portable artifact {name}", budget)
        require(hashlib.sha256(raw).hexdigest() == artifact.get("sha256"),
                f"artifact hash mismatch: {name}")
        decoded[name] = raw
        if name != "checkerPrompt":
            values[name] = object_from(raw, name)
    return decoded, values


def semantic_source_texts(bundle: dict, source: dict, row: dict,
                          observation: dict, budget: list[int]) -> dict[str, str]:
    require(set(bundle) == {"version", "unitId", "candidateTree", "symbol",
                            "paths", "files"}
            and bundle.get("version") == 1
            and bundle.get("unitId") == row.get("unitId")
            and bundle.get("candidateTree") == row.get("candidateTree")
            and bundle.get("symbol") == observation.get("symbol")
            and bundle.get("paths") == observation.get("paths")
            and bundle.get("paths") == source.get("allowedPaths"),
            "portable semantic source bundle is not bound to its pilot/demand")
    files = bundle.get("files")
    require(isinstance(files, list) and len(files) == len(bundle["paths"]),
            "portable semantic source file set is incomplete")
    texts: dict[str, str] = {}
    for expected_path, item in zip(bundle["paths"], files):
        require(isinstance(item, dict)
                and set(item) == {"path", "sha256", "encoding", "content"}
                and item.get("path") == expected_path
                and item.get("encoding") == "base64",
                "portable semantic source metadata is not closed")
        try:
            raw = decode_b64(
                item.get("content"),
                f"portable semantic source {expected_path}",
                budget,
            )
            text = raw.decode("utf-8")
        except (PortableEvidenceError, UnicodeDecodeError) as exc:
            raise PortableEvidenceError(
                f"portable semantic source is not canonical UTF-8/base64: {expected_path}") from exc
        require(hashlib.sha256(raw).hexdigest() == item.get("sha256"),
                f"portable semantic source hash mismatch: {expected_path}")
        texts[expected_path] = text
    require(sum(text.count(bundle["symbol"]) for text in texts.values()) >= 2,
            "portable semantic sources lack definition/reference evidence")
    return texts


def validate_payload(portable: dict, index: dict) -> dict[str, dict[str, str]]:
    require(set(portable) == {"version", "evidenceKind", "sourceIndexPath",
                              "sourceIndexSha256", "externalAdoptionEvidence", "episodes"}
            and portable.get("version") == 1
            and portable.get("evidenceKind") == "hash-bound-portable-historical-pilot-export"
            and portable.get("sourceIndexPath") == "docs/harness-demo-pilots/INDEX.json"
            and portable.get("externalAdoptionEvidence") is False,
            "portable export contract is not closed")
    require(portable.get("sourceIndexSha256")
            == hashlib.sha256(bounded_file_bytes(INDEX, "pilot index")).hexdigest(),
            "portable export does not bind the current pilot index")
    source_rows, rows = index.get("episodes") or [], portable.get("episodes") or []
    require(len(source_rows) == len(rows) == 3, "exactly three portable pilot episodes are required")
    demand = object_from(
        bounded_file_bytes(DEMAND, "semantic-navigation demand"),
        "semantic-navigation demand",
    )
    observations = {item.get("unitId"): item for item in demand.get("observations") or []
                    if isinstance(item, dict)}
    repository_ids: set[str] = set()
    semantic_sources: dict[str, dict[str, str]] = {}
    budget = [0]
    for source, row in zip(source_rows, rows):
        require(set(row) == {"unitId", "sessionId", "riskTier", "candidateTree",
                             "externalAdoptionEvidence", "indexEpisodeSha256",
                             "repositoryIdentitySha256", "artifacts"},
                "portable episode fields are not closed")
        require(source.get("status") == "passed"
                and source.get("externalAdoptionEvidence") is False
                and row.get("externalAdoptionEvidence") is False
                and all(row.get(key) == source.get(key)
                        for key in ("unitId", "sessionId", "riskTier", "candidateTree")),
                "portable episode does not match the passed indexed pilot")
        require(row.get("indexEpisodeSha256") == hashlib.sha256(canonical(source)).hexdigest(),
                "portable episode lacks exact index-row binding")
        repository_id = str(row.get("repositoryIdentitySha256") or "")
        require(re.fullmatch(r"[0-9a-f]{64}", repository_id) is not None,
                "portable repository identity is invalid")
        repository_ids.add(repository_id)
        _raw, values = decode_artifacts(row, budget)
        artifacts = row["artifacts"]
        observation = observations.get(row["unitId"])
        require(isinstance(observation, dict)
                and observation.get("candidateTree") == row["candidateTree"],
                "portable semantic observation is missing or belongs to another tree")
        semantic_sources[row["unitId"]] = semantic_source_texts(
            values["semanticSources"], source, row, observation, budget)
        packet, session, state = values["packet"], values["session"], values["parentState"]
        adjudication, machine, checker = values["adjudication"], values["machine"], values["checker"]
        require(artifacts["packet"]["sha256"] == source.get("packetSha256")
                and artifacts["session"]["sha256"] == source.get("sessionArtifactSha256")
                and artifacts["parentState"]["sha256"] == source.get("parentStateSnapshotSha256")
                and session.get("parentStateSha256") == artifacts["parentState"]["sha256"],
                "packet/session/parent-state raw-byte bindings drifted")
        require(packet.get("unitId") == row["unitId"]
                and packet.get("baseCommit") == source.get("baseCommit")
                and packet.get("sharedMutableResources") == []
                and session.get("unitId") == row["unitId"]
                and session.get("sessionId") == row["sessionId"]
                and session.get("packetSha256") == artifacts["packet"]["sha256"]
                and session.get("stateOwner") == "parent"
                and session.get("sharedMutableFallbacks") == 0
                and (state.get("currentUnit") or {}).get("id") == row["unitId"]
                and (state.get("currentUnit") or {}).get("status") == "in_progress",
                "portable isolation packet/session/state is inconsistent")
        spec = importlib.util.spec_from_file_location("frozen_absorption_for_portable", FROZEN_VERIFIER)
        require(spec is not None and spec.loader is not None, "frozen verifier cannot be imported")
        frozen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(frozen)
        frozen.validate_mutable_namespaces(packet.get("mutableResources") or [],
                                           session.get("mutableNamespaces"), row["sessionId"])
        namespace_hash = hashlib.sha256(canonical(session.get("mutableNamespaces"))).hexdigest()
        require(session.get("namespaceManifestSha256") == namespace_hash,
                "portable mutable namespace manifest hash is invalid")
        require(all(receipt_valid(value) for value in (adjudication, machine, checker)),
                "portable receipt self-digest is invalid")
        dependencies = adjudication.get("dependencies") or {}
        checker_artifacts = checker.get("artifacts") or {}
        require((dependencies.get("machine") or {}).get("path") == artifacts["machine"]["path"]
                and (dependencies.get("machine") or {}).get("sha256") == artifacts["machine"]["sha256"]
                and (dependencies.get("checker") or {}).get("path") == artifacts["checker"]["path"]
                and (dependencies.get("checker") or {}).get("sha256") == artifacts["checker"]["sha256"]
                and (checker_artifacts.get("prompt") or {}).get("path") == artifacts["checkerPrompt"]["path"]
                and (checker_artifacts.get("prompt") or {}).get("sha256") == artifacts["checkerPrompt"]["sha256"]
                and (checker_artifacts.get("report") or {}).get("path") == artifacts["checkerReport"]["path"]
                and (checker_artifacts.get("report") or {}).get("sha256") == artifacts["checkerReport"]["sha256"],
                "portable receipt dependency graph is invalid")
        candidate = machine.get("candidate") or {}
        maker = (checker.get("provenance") or {}).get("maker") or {}
        independent = (checker.get("provenance") or {}).get("checker") or {}
        declared = {item.get("path"): item.get("sha256")
                    for item in (machine.get("declaredInputs") or [])}
        require(adjudication.get("unitId") == machine.get("unitId") == checker.get("unitId") == row["unitId"]
                and adjudication.get("outcome") == "PASSED" and machine.get("verdict") == "PASSED"
                and values["checkerReport"].get("verdict") == "PASSED"
                and packet.get("baseCommit") == candidate.get("baseCommit")
                and session.get("candidateTree") == candidate.get("reviewedTree") == row["candidateTree"]
                and maker.get("session") == session.get("makerSession") == row["sessionId"]
                and independent.get("session") != row["sessionId"]
                and declared.get(artifacts["packet"]["path"]) == artifacts["packet"]["sha256"]
                and declared.get(artifacts["session"]["path"]) == artifacts["session"]["sha256"]
                and declared.get(artifacts["parentState"]["path"]) == artifacts["parentState"]["sha256"],
                "portable candidate/provenance/input binding is invalid")
    require(len(repository_ids) == 3, "portable evidence must bind three distinct repositories")
    return semantic_sources


def verified_semantic_sources() -> dict[str, dict[str, str]]:
    raw = bounded_file_bytes(EVIDENCE, "portable evidence")
    digest = hashlib.sha256(raw).hexdigest()
    require(digest == EVIDENCE_SHA256
            and bounded_file_bytes(SEAL, "portable evidence seal", 4096).decode("ascii")
            == f"{digest}  PORTABLE_EVIDENCE.json\n",
            "portable evidence seal differs from the reviewed export")
    return validate_payload(
        object_from(raw, "portable export"),
        object_from(bounded_file_bytes(INDEX, "pilot index"), "pilot index"),
    )


def main() -> int:
    try:
        spec = importlib.util.spec_from_file_location("frozen_absorption", FROZEN_VERIFIER)
        require(spec is not None and spec.loader is not None, "frozen verifier cannot be imported")
        frozen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(frozen)
        contract = frozen.load_json(frozen.CONTRACT)
        frozen.validate_contract_value(contract)
        frozen.validate_digest()
        guards = frozen.validate_mutations(contract)
        frozen.validate_public_skill_population(contract)
        repair_fixture = verified_historical_repair(contract)
        frozen.validate_isolation_refutations()
        frozen.validate_strategy_docs()
        for phase in ("context", "facade", "diagnostics", "navigation"):
            frozen.validate_phase(phase)
        frozen.validate_isolation_fixture()
        semantic_sources = verified_semantic_sources()
        reader_guards = validate_bounded_reader_guards()
        portable = object_from(
            bounded_file_bytes(EVIDENCE, "portable export"), "portable export"
        )
        index = object_from(bounded_file_bytes(INDEX, "pilot index"), "pilot index")
        mutant = copy.deepcopy(portable)
        mutant["episodes"][0]["artifacts"]["packet"]["content"] += "A"
        try:
            validate_payload(mutant, index)
        except PortableEvidenceError:
            pass
        else:
            raise PortableEvidenceError("portable artifact mutation survived validation")
        oversized_artifact = copy.deepcopy(portable)
        valid_oversized_blob = base64.b64encode(
            b"\0" * (DECODED_BLOB_MAX_BYTES + 1)
        ).decode("ascii")
        oversized_artifact["episodes"][0]["artifacts"]["packet"]["content"] = (
            valid_oversized_blob
        )
        try:
            validate_payload(oversized_artifact, index)
        except PortableEvidenceError:
            pass
        else:
            raise PortableEvidenceError("oversized portable artifact was accepted")
        oversized_semantic = copy.deepcopy(portable)
        oversized_semantic["episodes"][0]["artifacts"]["semanticSources"]["content"] = (
            valid_oversized_blob
        )
        try:
            validate_payload(oversized_semantic, index)
        except PortableEvidenceError:
            pass
        else:
            raise PortableEvidenceError("oversized portable semantic source was accepted")
        mutant_repair = copy.deepcopy(repair_fixture)
        first_path = mutant_repair["changedPaths"][0]
        mutant_repair["acceptedBlobs"][first_path]["content"] += "A"
        try:
            validate_portable_accepted_repair(contract, mutant_repair)
        except PortableEvidenceError:
            pass
        else:
            raise PortableEvidenceError(
                "portable historical repair mutation survived validation"
            )
        oversized_repair = copy.deepcopy(repair_fixture)
        first_path = oversized_repair["changedPaths"][0]
        oversized_repair["acceptedBlobs"][first_path]["content"] = (
            valid_oversized_blob
        )
        try:
            validate_portable_accepted_repair(contract, oversized_repair)
        except PortableEvidenceError:
            pass
        else:
            raise PortableEvidenceError(
                "oversized portable historical repair fixture was accepted"
            )
        with tempfile.TemporaryDirectory(prefix="itd-portable-bounds-") as raw:
            oversized_file = Path(raw) / "oversized.json"
            oversized_file.write_bytes(b" " * (JSON_FILE_MAX_BYTES + 1))
            try:
                bounded_file_bytes(oversized_file, "oversized portable fixture")
            except PortableEvidenceError:
                pass
            else:
                raise PortableEvidenceError("oversized portable JSON file was accepted")
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"episodes": 3, "frozenMutationGuards": guards, "frozenFixture": "PASSED",
                      "portableMutationGuard": "PASSED",
                      "oversizedGuards": 4,
                      "historicalRepairFixture": "PASSED",
                      "readerGuards": reader_guards,
                      "portableSemanticFiles": sum(len(files) for files in semantic_sources.values()),
                      "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
