#!/usr/bin/env python3
"""Replay structural canaries and real dual-host semantic reviewer evidence."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills" / "_shared" / "itd_review_evidence.py"
POLICY_PATH = ROOT / "skills" / "_shared" / "itd_reviewer_independence.py"
PRODUCER_PATH = ROOT / "skills" / "_shared" / "itd_free_reviewer_producer.py"
RUNNER_PATH = ROOT / "tests" / "run-independent-review-efficacy.py"
KEYRING_PATH = ROOT / ".itd" / "REVIEW_EFFICACY_KEYRING.json"
HOST_PIN_REL = Path(
    ".itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256"
)
CASES_PATH = ROOT / "benchmarks" / "independent-review-efficacy" / "cases.json"
U12_CROSS_PATH = (
    ROOT / "benchmarks" / "independent-review-efficacy" / "results"
    / "u12-cross-vendor-wsl.json"
)
HISTORY_ROOT = (
    ROOT / "benchmarks" / "independent-review-efficacy" / "history" / "route-debts"
)
HISTORY_BASELINE_COMMIT = "541081840d2f972e1b0c5aea16fa09a767f80b2c"
# This inventory was generated from Git tree
# 0f156678f8b42f29561874d1435c9ef4d770c116.  It intentionally lives in the
# verifier: a rewritten manifest must not be able to erase or replace history.
HISTORY_PINNED_SNAPSHOTS = {
    "diagnostic-7a7ef0d9/wsl.json": "be7dbee594e3f976857db0f8ed4c520a7b47f0c74157eb3142499184f47d4b6a",
    "diagnostic-7a7ef0d9/windows.json": "1feb2fec8e73b7c0a118bef61403729456685a77fa133c0c973cb2a8754a9acf",
    "diagnostic-7a7ef0d9/u12-cross-vendor-wsl.json": "4c6dea93d8eb8733f1e9fd60295f613a2b330fddf689fdd3e44fe77945043852",
    "diagnostic-ec40a183/wsl.json": "2013428a7d098fba3551807a948e7a8b4441dfea0e5b201021e9c8f1dd83be4a",
    "diagnostic-ec40a183/windows.json": "08fb0c40be8659e5eba0dae60b76f6395c439ac7a25c94b0ce5e9c533b6cc8f6",
    "diagnostic-ec40a183/u12-cross-vendor-wsl.json": "6e72a38eae1f1bbd1b24dd1f8dbeeba33da4a5377bdd17b1c68f9e275b31aa7f",
    "accepted-base-5410818/wsl.json": "95a0542caaf793a7d74a74991d824519f68b21d3af76baf865ff45a2c839aed2",
    "accepted-base-5410818/windows.json": "33dbf3964aa555b501b7a4b2a428d72883e52c20675bd56e89a2aa54a528ec36",
    "accepted-base-5410818/u12-cross-vendor-wsl.json": "a05260dc1996528d25544e14f8d236c610452dc2be034a95d49f1ad1699fc29e",
    "diagnostic-37da0624/wsl.json": "d80f49172dd78a661740ed3f6640b29766cdd346222dc364b2507c47b0774ecf",
    "diagnostic-37da0624/windows.json": "7653f95bad74f8d304a069627d45ec82434147d452da37b477d4e6eda4fac21c",
    "diagnostic-37da0624/u12-cross-vendor-wsl.json": "abe95eb77d1c9c038ba0f122f9fdfc37a894f2c2455fd00bc1506470b45a8a39",
    "diagnostic-9ee3303a/wsl.json": "c6980c087abad36fbc589efede593136ce7079e7a13417b1930b1d2bf3c0ebac",
    "diagnostic-9ee3303a/windows.json": "ccdddc40ac0d7e59474e40f640280f7269e0c6a43d26ae51a50937ae045713e1",
    "diagnostic-9ee3303a/u12-cross-vendor-wsl.json": "524593abc79eaefd7e0ec26e393485862ee2cfe7fc76adc52289699250356cb5",
    "diagnostic-d0044c10/wsl.json": "f1f850455420c76f896d2ccd94d416929640399dc340df04b048f969a4cda06f",
    "diagnostic-d0044c10/windows.json": "57ebd2ffbbaa91183ef155823c035a135b432a0c8eb959ec9837618c1cb8b616",
    "diagnostic-d0044c10/u12-cross-vendor-wsl.json": "6533ee1d041dade6858f0a18138d0d64889371be021abf7373acba362506e2d6",
    "diagnostic-5c597f17/wsl.json": "79c5e6693b48557babf4b183d9c29af3bed86fedda515e2783ae84431fc8a8b8",
    "diagnostic-5c597f17/windows.json": "aaa922908c340a010ca4e29a9f1c222e8ce5b1e28eada096485cffc1a376cedd",
    "diagnostic-5c597f17/u12-cross-vendor-wsl.json": "5b9e38da3436b14ce755ce6397e2aaa06e27875bc3a22f684c3fcffc40b8ab54",
    "diagnostic-a7b46110/wsl.json": "d966c86eef6b6f9484d280f6d919173ce4c424ba358aaa95da5c76b63a8c019c",
    "diagnostic-a7b46110/windows.json": "f3229c27fee64a8b4f52b9c2d0250f1693d66823d99a4a911a889b2206acb2f3",
    "diagnostic-a7b46110/u12-cross-vendor-wsl.json": "232f2b65c96ea2228b388fd086348223a0ab9c95362f53a119546a8d7625f1c3",
    "diagnostic-096f771b/wsl.json": "2a298414a7eb738cffc67b4293f226564e2e0f564f47a65c1bc3da5f4f5a64e5",
    "diagnostic-096f771b/windows.json": "00437837bb5577270cd2e08f77907b7a8d84dd95f2e511f7bbc3ffd2831faa3c",
    "diagnostic-096f771b/u12-cross-vendor-wsl.json": "816c4c0794232ce9bd3df13158fbf5b5906ee7446908b47adc9f2752c2a3764d",
    "diagnostic-0f1b8759/wsl.json": "535ba978af6801efdd8b8be2f8cb37ef1af5a394893a265fa29e6c67e7a5f374",
    "diagnostic-0f1b8759/windows.json": "fd9cc3108bd260c533a68ec226d890b42860fbcc86e2a70e9c5fc38c5d32c0dc",
    "diagnostic-0f1b8759/u12-cross-vendor-wsl.json": "3f31f58c17f93b9deeefd6e2144040a4b3afcc8f88e3624d4ba157ed7a96b461",
    "diagnostic-68b25d08/wsl.json": "fbb80ad450db01eb40f9df43344fe557278353209b4cf09ae538eae3f3c3e6dc",
    "diagnostic-68b25d08/windows.json": "6e05d7ec97c97b538e5a278a2219bfd220aec000add60ff0a40bfcb4f6fd15a9",
    "diagnostic-68b25d08/u12-cross-vendor-wsl.json": "ddd7614628731bebc17b50cebc122b9de27cbc22f9bb2d7b6861b9f8c5249071",
}
# These values are deliberately in the verifier rather than trusting a mutable
# archive manifest.  They bind the accepted evidence to the bytes that Git
# recorded at the accepted base, including the Git blob identity.
HISTORY_ACCEPTED_BASE = {
    "wsl.json": {
        "sha256": "95a0542caaf793a7d74a74991d824519f68b21d3af76baf865ff45a2c839aed2",
        "gitBlobSha1": "3f6d5b3a73fb5e174787e83b9ecc2b40dbfdfd36",
        "sizeBytes": 11363,
    },
    "windows.json": {
        "sha256": "33dbf3964aa555b501b7a4b2a428d72883e52c20675bd56e89a2aa54a528ec36",
        "gitBlobSha1": "fa4f8b7154231073c90859fdf3b427f32c89b416",
        "sizeBytes": 11097,
    },
    "u12-cross-vendor-wsl.json": {
        "sha256": "a05260dc1996528d25544e14f8d236c610452dc2be034a95d49f1ad1699fc29e",
        "gitBlobSha1": "33988acadcc2f632da851a26adc330e8b2418bec",
        "sizeBytes": 11508,
    },
}
RESULTS = {
    "wsl": ROOT / "benchmarks" / "independent-review-efficacy" / "results" / "wsl.json",
    "windows": ROOT / "benchmarks" / "independent-review-efficacy" / "results" / "windows.json",
}
EXPECTED_OPPOSITE = {
    "gpt-5.6-sol": "gpt-5.6-terra",
    "gpt-5.6-terra": "gpt-5.6-sol",
}
EXPECTED_ISOLATION = {
    "freshSession": True,
    "ephemeral": True,
    "inheritedContext": False,
    "repositoryAccess": False,
    "repositoryMutation": False,
    "shellTools": False,
    "networkTools": False,
    "secrets": False,
    "paidApi": False,
    "observedToolCallsZero": True,
}


def load_module(name: str, path: Path):
    """Загрузка ИЗ ИСХОДНИКА, минуя кэш байткода.

    `exec_module` берёт `__pycache__/*.pyc`, если тот выглядит свежим по паре
    (mtime, size). Правка той же длины в пределах одной секунды — обычное дело
    при мутационном тестировании — оставляет кэш «свежим», и оракул судит СТАРЫЙ
    код: живьём (LPD-002 R4) мутация `TRANSPORT_ATTEMPT_BOUND = 3` пережила
    откат файла и дала ложный красный на чистом дереве. Компиляция прочитанных
    байт снимает весь класс: судится ровно то, что лежит в файле.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(Path(path).read_bytes(), str(path), "exec"), module.__dict__)
    return module


def baseline():
    tree = "a" * 40
    acceptance = {
        "criteria": [{
            "id": "UNIT-AC1",
            "status": "passed",
            "reviewEvidence": {
                "claim": "Bounded export and reconciliation behavior are executable.",
                "impactClasses": ["bounded-output", "reconciliation"],
                "oracleIds": ["domain-oracle"],
            },
        }],
        "activeFollowup": {
            "unitId": "UNIT",
            "reviewPolicy": {
                "mode": "evidence-first",
                "riskTier": "high",
                "requiredImpactClasses": ["bounded-output", "reconciliation"],
                "minimumIndependentReviewers": 1,
                "explorer": "isolated-machine-oracle",
                "adjudicator": "sealed-host-union",
            },
        },
    }
    machine = {
        "unitId": "UNIT",
        "riskTier": "high",
        "candidate": {"reviewedTree": tree},
        "runs": [{"id": "domain-oracle", "exitCode": 0, "executedTree": tree}],
    }
    return acceptance, machine


def mutate(name, acceptance, machine):
    criterion = acceptance["criteria"][0]
    policy = acceptance["activeFollowup"]["reviewPolicy"]
    run = machine["runs"][0]
    if name == "none":
        return
    if name == "missing-review-evidence":
        criterion.pop("reviewEvidence")
    elif name == "failed-oracle":
        run["exitCode"] = 1
    elif name == "foreign-tree":
        run["executedTree"] = "b" * 40
    elif name == "missing-impact":
        criterion["reviewEvidence"]["impactClasses"] = ["bounded-output"]
    elif name == "missing-reviewer":
        policy["minimumIndependentReviewers"] = 0
    elif name == "missing-oracle":
        criterion["reviewEvidence"]["oracleIds"] = ["absent-oracle"]
    elif name == "unpassed-criterion":
        criterion["status"] = "pending"
    elif name == "unknown-impact":
        criterion["reviewEvidence"]["impactClasses"] = ["unknown-domain"]
    elif name == "duplicate-oracle":
        criterion["reviewEvidence"]["oracleIds"] = ["domain-oracle", "domain-oracle"]
    elif name == "duplicate-criterion":
        acceptance["criteria"].append(copy.deepcopy(criterion))
    elif name == "risk-mismatch":
        policy["riskTier"] = "medium"
    elif name == "missing-claim":
        criterion["reviewEvidence"]["claim"] = ""
    else:
        raise AssertionError(f"unknown structural mutation: {name}")


def exact(value: object, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise AssertionError(f"{label} is not a closed object")
    return value


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def parse_host_pin(raw: bytes) -> str:
    if not re.fullmatch(rb"[0-9a-f]{64}\n?", raw):
        raise AssertionError("host-owned review keyring pin is malformed")
    return raw.rstrip(b"\n").decode("ascii")


def parse_caller_pin(value: str) -> str:
    """Ожидаемый дайджест, переданный ЗНАЧЕНИЕМ.

    Форма строго та же, что у host-пина (64 строчных hex), но авторизация
    слабее и называется честно: значение приходит от вызывающего (и,
    в машинном маршруте, из tracked `.itd/VERIFICATION_CONTRACT.json`),
    а не из host-owned файла. Путь к host-пину лежит в gitignored
    `.itd-memory/`, поэтому в изолированном worktree оракул без этого флага
    не запускается вовсе (retro 2026-08-18, сигнал E4).
    """
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AssertionError("caller-supplied review keyring pin is malformed")
    return value


def authorized_keyring(expected: str) -> dict[str, str]:
    keyring_raw = KEYRING_PATH.read_bytes()
    if sha256(keyring_raw) != expected:
        raise AssertionError("review efficacy keyring is not host-authorized")
    return json.loads(keyring_raw.decode("utf-8"))


def host_keyring(path: Path) -> dict[str, str]:
    if path != HOST_PIN_REL:
        raise AssertionError("review keyring pin path is not the host contract")
    return authorized_keyring(parse_host_pin((ROOT / path).read_bytes()))


def resolve_keyring(args: argparse.Namespace) -> tuple[dict[str, str], str]:
    """Keyring + ЧЕСТНОЕ имя авторизации дайджеста.

    Fail-closed: ровно один источник (argparse-группа), обе формы обязаны
    совпасть с фактическим содержимым tracked-keyring'а.
    """
    if args.expected_keyring_sha256_file is not None:
        return host_keyring(args.expected_keyring_sha256_file), "host-pin"
    return authorized_keyring(parse_caller_pin(args.expected_keyring_sha256)), "caller-pin"


def verify_signed_evidence(envelope, keyring, producer, label):
    row = exact(envelope, {"signed", "signatureHex"}, label)
    signed = row["signed"]
    key_id = signed.get("keyId") if isinstance(signed, dict) else None
    signature = row["signatureHex"]
    if (
        not isinstance(key_id, str)
        or key_id not in keyring
        or not isinstance(signature, str)
        or not re.fullmatch(r"[0-9a-f]{128}", signature)
    ):
        raise AssertionError(f"{label} signature envelope is invalid")
    try:
        public = producer.b64url_decode(keyring[key_id], 32, label + " public key")
        producer.Ed25519PublicKey.from_public_bytes(public).verify(
            bytes.fromhex(signature), producer.canonical_bytes(signed)
        )
    except Exception as exc:
        raise AssertionError(f"{label} signature is invalid") from exc
    return signed


def archive_relative_path(value: object, label: str) -> Path:
    """Return a safe, canonical archive-relative JSON path."""
    if not isinstance(value, str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*\.json", value
    ):
        raise AssertionError(f"{label} path is not a canonical archive path")
    return Path(value)


def git_blob_bytes(blob: str) -> bytes:
    """Read a pinned blob directly, so shallow clones need no old commit object."""
    try:
        object_type = subprocess.check_output(
            ["git", "-C", str(ROOT), "cat-file", "-t", blob], text=True
        ).strip()
        raw = subprocess.check_output(
            ["git", "-C", str(ROOT), "cat-file", "blob", blob]
        )
    except subprocess.CalledProcessError as exc:
        raise AssertionError(f"accepted-base Git blob is unavailable: {blob}") from exc
    if object_type != "blob":
        raise AssertionError(f"accepted-base Git object is not a blob: {blob}")
    return raw


def read_archive_regular(path: Path, producer, label: str) -> bytes:
    """Archive authority accepts only stable, regular, non-symlink bytes."""
    try:
        return producer.read_regular(path, label)
    except Exception as exc:
        raise AssertionError(f"{label} is not a regular archive file") from exc


def archive_tree_inventory(history_root: Path) -> tuple[set[Path], set[Path]]:
    """Classify every descendant with lstat; links and special nodes are data."""
    files: set[Path] = set()
    directories: set[Path] = {Path(".")}

    def visit(path: Path) -> None:
        try:
            info = path.lstat()
        except OSError as exc:
            raise AssertionError(f"immutable history entry is unreadable: {path}") from exc
        attributes = int(getattr(info, "st_file_attributes", 0) or 0)
        if (
            stat.S_ISLNK(info.st_mode)
            or path.is_symlink()
            or attributes & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        ):
            raise AssertionError(f"immutable history contains a link or reparse entry: {path}")
        relative = path.relative_to(history_root)
        if stat.S_ISREG(info.st_mode):
            files.add(relative)
            return
        if not stat.S_ISDIR(info.st_mode):
            raise AssertionError(f"immutable history contains a special entry: {path}")
        directories.add(relative)
        try:
            children = list(path.iterdir())
        except OSError as exc:
            raise AssertionError(f"immutable history directory is unreadable: {path}") from exc
        for child in children:
            visit(child)

    try:
        root_info = history_root.lstat()
    except OSError as exc:
        raise AssertionError("immutable history root is unreadable") from exc
    root_attributes = int(getattr(root_info, "st_file_attributes", 0) or 0)
    if (
        not stat.S_ISDIR(root_info.st_mode)
        or history_root.is_symlink()
        or root_attributes & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    ):
        raise AssertionError("immutable history root is not a real directory")
    for child in history_root.iterdir():
        visit(child)
    return files, directories


def validate_immutable_history(
    history_root: Path, producer, keyring, *,
    pinned_snapshots: dict[str, str] = HISTORY_PINNED_SNAPSHOTS,
) -> dict[Path, dict[str, Any]]:
    """Verify the closed archival inventory without treating it as live evidence.

    Archived runs retain their original producer/runner/manifest hashes and
    timestamps.  They are verified for byte integrity and signature validity,
    but deliberately do not have to match today's producer or freshness window.
    """
    manifest_path = history_root / "manifest.json"
    try:
        manifest = json.loads(
            read_archive_regular(manifest_path, producer, "immutable history manifest")
            .decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError, AssertionError) as exc:
        raise AssertionError("immutable history manifest is unreadable") from exc
    manifest = exact(manifest, {"version", "kind", "baselineCommit", "entries"},
                     "immutable history manifest")
    if (
        type(manifest["version"]) is not int
        or manifest["version"] != 1
        or manifest["kind"] != "itd-efficacy-immutable-history-v1"
        or manifest["baselineCommit"] != HISTORY_BASELINE_COMMIT
        or not isinstance(manifest["entries"], list)
    ):
        raise AssertionError("immutable history manifest identity is invalid")

    pinned_paths = {Path(path) for path in pinned_snapshots}
    expected_files = {Path("manifest.json"), *pinned_paths}
    expected_directories = {Path(".")}
    for expected_file in expected_files:
        parent = expected_file.parent
        while parent != Path("."):
            expected_directories.add(parent)
            parent = parent.parent
    entries: dict[Path, dict[str, Any]] = {}
    diagnostic_groups: dict[str, list[dict[str, Any]]] = {}
    for raw_entry in manifest["entries"]:
        entry = exact(raw_entry, {
            "path", "sha256", "sourceProducerSha256", "observedAt",
            "sourceGitBlobSha1", "classification", "sizeBytes",
        }, "immutable history entry")
        relative = archive_relative_path(entry["path"], "immutable history entry")
        if relative in entries:
            raise AssertionError("immutable history manifest repeats an archive path")
        if (
            not re.fullmatch(r"[0-9a-f]{64}", str(entry["sha256"]))
            or not re.fullmatch(r"[0-9a-f]{64}", str(entry["sourceProducerSha256"]))
            or type(entry["sizeBytes"]) is not int
            or entry["sizeBytes"] < 0
        ):
            raise AssertionError("immutable history entry digest or size is invalid")
        try:
            observed = dt.datetime.fromisoformat(
                str(entry["observedAt"]).replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise AssertionError("immutable history timestamp is malformed") from exc
        if observed.tzinfo is None:
            raise AssertionError("immutable history timestamp lacks a timezone")
        entries[relative] = entry
        folder, filename = relative.parts
        if entry["classification"] == "accepted-base":
            if folder != "accepted-base-5410818" or filename not in HISTORY_ACCEPTED_BASE:
                raise AssertionError("accepted-base archive path is invalid")
            anchor = HISTORY_ACCEPTED_BASE[filename]
            if (
                entry["sha256"] != anchor["sha256"]
                or entry["sourceGitBlobSha1"] != anchor["gitBlobSha1"]
                or entry["sizeBytes"] != anchor["sizeBytes"]
            ):
                raise AssertionError("accepted-base manifest does not match pinned Git bytes")
        elif entry["classification"] == "diagnostic":
            if not re.fullmatch(
                r"diagnostic-[0-9a-f]{8}(?:-[a-z0-9][a-z0-9-]*)?", folder
            ):
                raise AssertionError("diagnostic archive path is invalid")
            if filename not in HISTORY_ACCEPTED_BASE or entry["sourceGitBlobSha1"] is not None:
                raise AssertionError("diagnostic archive provenance is invalid")
            producer_prefix = re.fullmatch(r"diagnostic-([0-9a-f]{8})(?:-[a-z0-9][a-z0-9-]*)?", folder)
            assert producer_prefix is not None  # established by the shape check above
            if not entry["sourceProducerSha256"].startswith(producer_prefix.group(1)):
                raise AssertionError("diagnostic folder does not bind its producer hash")
            diagnostic_groups.setdefault(folder, []).append(entry)
        else:
            raise AssertionError("immutable history entry classification is invalid")

    required_accepted = {Path("accepted-base-5410818") / name
                         for name in HISTORY_ACCEPTED_BASE}
    if not required_accepted <= pinned_paths:
        raise AssertionError("immutable history pins omit accepted-base evidence")
    if set(entries) != pinned_paths:
        raise AssertionError("immutable history manifest inventory differs from frozen pins")
    if not required_accepted <= set(entries):
        raise AssertionError("immutable history is missing accepted-base evidence")
    for folder, group in diagnostic_groups.items():
        names = {archive_relative_path(row["path"], "diagnostic entry").name
                 for row in group}
        producer_hashes = {row["sourceProducerSha256"] for row in group}
        if names != set(HISTORY_ACCEPTED_BASE) or len(producer_hashes) != 1:
            raise AssertionError(f"diagnostic archive {folder} is incomplete or mixed")

    actual_files, actual_directories = archive_tree_inventory(history_root)
    if actual_files != expected_files or actual_directories != expected_directories:
        raise AssertionError("immutable history file inventory differs from manifest")

    for relative, entry in entries.items():
        raw = read_archive_regular(
            history_root / relative, producer,
            f"immutable history {relative.as_posix()}",
        )
        pinned_sha256 = pinned_snapshots[relative.as_posix()]
        if (
            entry["sha256"] != pinned_sha256
            or len(raw) != entry["sizeBytes"]
            or sha256(raw) != pinned_sha256
        ):
            raise AssertionError(f"immutable history bytes differ: {relative.as_posix()}")
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AssertionError(f"immutable history JSON is unreadable: {relative.as_posix()}") from exc
        signed = verify_signed_evidence(
            envelope, keyring, producer, f"immutable history {relative.as_posix()}"
        )
        if not isinstance(signed, dict) or (
            signed.get("producerSha256") != entry["sourceProducerSha256"]
            or signed.get("observedAt") != entry["observedAt"]
        ):
            raise AssertionError(f"immutable history signed provenance differs: {relative.as_posix()}")

        if entry["classification"] == "accepted-base":
            filename = relative.name
            anchor = HISTORY_ACCEPTED_BASE[filename]
            source_raw = git_blob_bytes(anchor["gitBlobSha1"])
            if (
                sha256(source_raw) != anchor["sha256"]
                or len(source_raw) != anchor["sizeBytes"]
                or raw != source_raw
            ):
                raise AssertionError(f"accepted-base bytes are not the pinned Git blob: {filename}")
    print("PASS  immutable review-efficacy history has a closed signed inventory")
    return entries


def validate_current_result_archive_binding(
    path: Path, history_entries: dict[Path, dict[str, Any]],
    expected_producer_sha256: str,
) -> None:
    """A current view is applicable only when its exact bytes are archived as a
    diagnostic observation of the CURRENT producer.

    Filename plus SHA-256 alone would let an accepted-base or stale diagnostic
    snapshot satisfy the check; historical observations can never establish
    current-producer applicability (Sol-a12), so the matching entry must be
    classified ``diagnostic`` and bind ``sourceProducerSha256`` to the
    producer bytes under test.
    """
    # The current view is read through the shared anchored no-follow reader:
    # a link planted at results/<name>.json would otherwise bind foreign bytes
    # to a current-producer diagnostic entry of the immutable archive
    # (Sol-a13).
    raw = load_module(
        "itd_safe_atomic_efficacy_reader", ROOT / "skills" / "_shared" / "itd_safe_atomic.py"
    ).read_ledger_snapshot(path)
    if raw is None:
        raise AssertionError(f"current semantic efficacy result is missing: {path.name}")
    matches = [
        entry for relative, entry in history_entries.items()
        if relative.name == path.name and entry["sha256"] == sha256(raw)
    ]
    if not matches:
        raise AssertionError(
            f"current semantic efficacy result is absent from immutable history: {path.name}"
        )
    bound = [
        entry for entry in matches
        if entry["classification"] == "diagnostic"
        and entry["sourceProducerSha256"] == expected_producer_sha256
    ]
    if not bound:
        raise AssertionError(
            "current semantic efficacy result is archived only as a historical or "
            f"foreign-producer observation, not a current-producer diagnostic: {path.name}"
        )
    print("PASS  current result is pinned as a current-producer diagnostic in immutable history: " + path.name)


def verify_current_result_binding_negative_cases(
    history_entries: dict[Path, dict[str, Any]], producer_sha256: str
) -> None:
    """A historical snapshot with the same filename and bytes must not pass."""
    accepted = [
        (relative, entry) for relative, entry in history_entries.items()
        if entry["classification"] == "accepted-base"
    ]
    assert accepted, "history has no accepted-base anchors to exercise"
    with tempfile.TemporaryDirectory(prefix="efficacy-current-binding-") as td:
        for relative, entry in accepted:
            fake_current = Path(td) / relative.name
            shutil.copyfile(HISTORY_ROOT / relative, fake_current)
            try:
                validate_current_result_archive_binding(fake_current, history_entries, producer_sha256)
            except AssertionError as exc:
                assert "current-producer diagnostic" in str(exc), str(exc)
            else:
                raise AssertionError(
                    "accepted-base snapshot satisfied the current-result archive check: " + relative.name
                )
            try:
                validate_current_result_archive_binding(
                    fake_current, history_entries, entry["sourceProducerSha256"])
            except AssertionError as exc:
                assert "current-producer diagnostic" in str(exc), str(exc)
            else:
                raise AssertionError(
                    "accepted-base classification was accepted as a diagnostic: " + relative.name
                )
    print("PASS  current-result binding rejects historical and foreign-producer snapshots")


def verify_immutable_history_negative_cases(producer, keyring) -> None:
    """Exercise material archive substitutions against the real baseline anchors."""
    def rejects(label: str, mutate) -> None:
        with tempfile.TemporaryDirectory(prefix="efficacy-history-") as td:
            root = Path(td) / "route-debts"
            shutil.copytree(HISTORY_ROOT, root)
            mutate(root)
            try:
                validate_immutable_history(root, producer, keyring)
            except AssertionError:
                print("PASS  immutable-history/" + label)
            else:
                raise AssertionError("immutable history accepted " + label)

    def accepts(label: str, mutate) -> None:
        with tempfile.TemporaryDirectory(prefix="efficacy-history-") as td:
            root = Path(td) / "route-debts"
            shutil.copytree(HISTORY_ROOT, root)
            extension = mutate(root)
            validate_immutable_history(
                root, producer, keyring,
                pinned_snapshots={**HISTORY_PINNED_SNAPSHOTS, **(extension or {})},
            )
            print("PASS  immutable-history/" + label)

    rejects("missing-file", lambda root: (root / "diagnostic-37da0624/wsl.json").unlink())
    rejects("undeclared-file", lambda root: (root / "unexpected.json").write_text("{}", encoding="utf-8"))

    def append_suffixed_triplet(root: Path) -> None:
        source = root / "diagnostic-37da0624"
        destination = root / "diagnostic-37da0624-repeat"
        shutil.copytree(source, destination)
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        copies = [dict(row, path=row["path"].replace(
            "diagnostic-37da0624/", "diagnostic-37da0624-repeat/", 1
        )) for row in manifest["entries"] if row["path"].startswith("diagnostic-37da0624/")]
        manifest["entries"].extend(copies)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return {
            row["path"]: row["sha256"] for row in copies
        }

    accepts("suffixed-diagnostic-triplet", append_suffixed_triplet)

    def boolean_version(root: Path) -> None:
        path = root / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["version"] = True
        path.write_text(json.dumps(manifest), encoding="utf-8")

    rejects("boolean-version", boolean_version)

    def remove_diagnostic_group(root: Path) -> None:
        shutil.rmtree(root / "diagnostic-9ee3303a")
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["entries"] = [
            row for row in manifest["entries"]
            if not row["path"].startswith("diagnostic-9ee3303a/")
        ]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    rejects("whole-diagnostic-group-removal", remove_diagnostic_group)

    def substitute_accepted_base(root: Path) -> None:
        path = root / "accepted-base-5410818/wsl.json"
        raw = path.read_bytes() + b"\n"
        path.write_bytes(raw)
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(row for row in manifest["entries"]
                     if row["path"] == "accepted-base-5410818/wsl.json")
        entry["sha256"] = sha256(raw)
        entry["sizeBytes"] = len(raw)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    rejects("accepted-base-substitution", substitute_accepted_base)

    def break_signature(root: Path) -> None:
        path = root / "diagnostic-37da0624/wsl.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["signatureHex"] = "0" * 128
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        path.write_bytes(raw)
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(row for row in manifest["entries"] if row["path"] == "diagnostic-37da0624/wsl.json")
        entry["sha256"] = sha256(raw)
        entry["sizeBytes"] = len(raw)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    rejects("signature-substitution", break_signature)

    def substitute_valid_signed_snapshot(root: Path) -> None:
        target_path = "diagnostic-d0044c10/wsl.json"
        source_path = "diagnostic-d0044c10/windows.json"
        target = root / target_path
        source = root / source_path
        target.write_bytes(source.read_bytes())
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        target_entry = next(row for row in manifest["entries"] if row["path"] == target_path)
        source_entry = next(row for row in manifest["entries"] if row["path"] == source_path)
        for field in ("sha256", "sourceProducerSha256", "observedAt", "sizeBytes"):
            target_entry[field] = source_entry[field]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    rejects("valid-signed-substitution", substitute_valid_signed_snapshot)

    with tempfile.TemporaryDirectory(prefix="efficacy-history-") as td:
        root = Path(td) / "route-debts"
        shutil.copytree(HISTORY_ROOT, root)
        manifest = root / "manifest.json"
        target = root / "manifest-target.json"
        target.write_bytes(manifest.read_bytes())
        manifest.unlink()
        try:
            manifest.symlink_to(target.name)
        except (NotImplementedError, OSError) as exc:
            print(f"SKIP  immutable-history/symlink-manifest: {exc}")
        else:
            try:
                validate_immutable_history(root, producer, keyring)
            except AssertionError:
                print("PASS  immutable-history/symlink-manifest")
            else:
                raise AssertionError("immutable history accepted symlink manifest")

    with tempfile.TemporaryDirectory(prefix="efficacy-history-") as td:
        root = Path(td) / "route-debts"
        shutil.copytree(HISTORY_ROOT, root)
        archive = root / "diagnostic-37da0624/wsl.json"
        target = root / "diagnostic-37da0624/wsl-target.json"
        target.write_bytes(archive.read_bytes())
        archive.unlink()
        try:
            archive.symlink_to(target.name)
        except (NotImplementedError, OSError) as exc:
            print(f"SKIP  immutable-history/symlink-entry: {exc}")
        else:
            try:
                validate_immutable_history(root, producer, keyring)
            except AssertionError:
                print("PASS  immutable-history/symlink-entry")
            else:
                raise AssertionError("immutable history accepted symlink entry")

    with tempfile.TemporaryDirectory(prefix="efficacy-history-") as td:
        root = Path(td) / "route-debts"
        shutil.copytree(HISTORY_ROOT, root)
        target = Path(td) / "outside-directory"
        target.mkdir()
        link = root / "undeclared-directory-link"
        try:
            link.symlink_to(target, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            print(f"SKIP  immutable-history/symlink-directory: {exc}")
        else:
            try:
                validate_immutable_history(root, producer, keyring)
            except AssertionError:
                print("PASS  immutable-history/symlink-directory")
            else:
                raise AssertionError("immutable history accepted symlink directory")

    if hasattr(os, "mkfifo"):
        with tempfile.TemporaryDirectory(prefix="efficacy-history-") as td:
            root = Path(td) / "route-debts"
            shutil.copytree(HISTORY_ROOT, root)
            try:
                os.mkfifo(root / "undeclared-fifo")
            except OSError as exc:
                print(f"SKIP  immutable-history/fifo: {exc}")
            else:
                try:
                    validate_immutable_history(root, producer, keyring)
                except AssertionError:
                    print("PASS  immutable-history/fifo")
                else:
                    raise AssertionError("immutable history accepted FIFO")
    else:
        print("SKIP  immutable-history/fifo: host has no mkfifo")

    try:
        import socket
        with tempfile.TemporaryDirectory(prefix="efficacy-history-") as td:
            root = Path(td) / "route-debts"
            shutil.copytree(HISTORY_ROOT, root)
            socket_path = root / "undeclared-socket"
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                listener.bind(str(socket_path))
            except OSError as exc:
                print(f"SKIP  immutable-history/socket: {exc}")
            else:
                try:
                    validate_immutable_history(root, producer, keyring)
                except AssertionError:
                    print("PASS  immutable-history/socket")
                else:
                    raise AssertionError("immutable history accepted socket")
            finally:
                listener.close()
    except (AttributeError, ImportError):
        print("SKIP  immutable-history/socket: AF_UNIX unavailable")

    if os.name == "nt":
        with tempfile.TemporaryDirectory(prefix="efficacy-history-") as td:
            root = Path(td) / "route-debts"
            shutil.copytree(HISTORY_ROOT, root)
            target = Path(td) / "junction-target"
            target.mkdir()
            junction = root / "undeclared-junction"
            created = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],
                capture_output=True, text=True,
            )
            if created.returncode != 0:
                print("SKIP  immutable-history/junction: native junction unavailable")
            else:
                try:
                    validate_immutable_history(root, producer, keyring)
                except AssertionError:
                    print("PASS  immutable-history/junction")
                else:
                    raise AssertionError("immutable history accepted junction")


SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
CATEGORY_ALIASES = {
    "scale-and-bounded-output": "scale",
    "scale/capacity": "scale",
    "generated-artifact-freshness": "release-gate",
}


def normalized_category(value: str) -> str:
    normalized = re.sub(r"[-_\s]+", "-", value.strip().casefold())
    return CATEGORY_ALIASES.get(normalized, normalized)


def normalized_category_components(value: object) -> set[str]:
    """Preserve every explicit dimension in a compound reviewer category."""
    return {
        normalized_category(component)
        for component in re.split(r"\s*/\s*", str(value))
        if component.strip()
    }


def normalized_summary(value: object) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"\btsc\b|typescript check(?:ing)?", "typecheck", text)
    return text


def category_agrees(finding: dict[str, Any], fault: dict[str, Any]) -> bool:
    """Whether the reviewer's free-text label falls inside the declared set."""
    categories = {
        normalized_category(str(value)) for value in fault["categories"]
    }
    return bool(
        normalized_category_components(finding.get("category") or "") & categories
    )


def finding_matches_fault(finding: dict[str, Any], fault: dict[str, Any]) -> bool:
    """Match on substance: file, line range, severity floor and a required literal.

    The reviewer's free-text `category` is advisory and deliberately NOT a
    gate: a finding that pins the same file, the same line, at least the
    declared severity, and quotes a required summary literal has identified
    the seeded fault whatever noun it chose for it. Scoring the label was
    measured twice on 2026-08-08 to turn correct detections into misses
    ('release-gate correctness' on WSL, 'capacity' on Windows), which made the
    benchmark understate reviewer efficacy and re-run-sensitive to phrasing.
    A divergent label is surfaced by category_agrees(), not swallowed.
    """
    minimum = SEVERITY_RANK.get(str(fault["minimumSeverity"]))
    observed = SEVERITY_RANK.get(str(finding.get("severity")))
    summary = normalized_summary(finding.get("summary"))
    return bool(
        minimum is not None
        and observed is not None
        and observed >= minimum
        and finding.get("file") == fault["file"]
        and fault["lineStart"] <= finding.get("line", 0) <= fault["lineEnd"]
        and any(normalized_summary(term) in summary for term in fault["summaryTerms"])
    )


def structural_metrics(manifest, evidence, producer) -> dict[str, float]:
    outcomes = []
    for case in manifest["structuralCases"]:
        acceptance, machine = baseline()
        mutate(case["mutation"], acceptance, machine)
        try:
            matrix = evidence.coverage_matrix(acceptance, machine)
        except evidence.ReviewEvidenceError:
            blocked = True
        else:
            blocked = False
            assert matrix and matrix["criteria"][0]["criterionId"] == "UNIT-AC1"
        expected_block = case["severity"] != "clean"
        detected = blocked is expected_block
        outcomes.append({**case, "detected": detected, "blocked": blocked})
        print(("PASS  " if detected else "FAIL  ") + "structural/" + case["id"])
    low_acceptance, low_machine = baseline()
    low_acceptance["activeFollowup"]["reviewPolicy"].update({
        "riskTier": "low", "minimumIndependentReviewers": 0,
    })
    low_machine["riskTier"] = "low"
    evidence.coverage_matrix(low_acceptance, low_machine)
    for label, risk, minimum in (
        ("low-reviewer", "low", 1),
        ("high-quorum", "high", 2),
    ):
        mutated_acceptance, mutated_machine = baseline()
        mutated_acceptance["activeFollowup"]["reviewPolicy"].update({
            "riskTier": risk, "minimumIndependentReviewers": minimum,
        })
        mutated_machine["riskTier"] = risk
        try:
            evidence.coverage_matrix(mutated_acceptance, mutated_machine)
        except evidence.ReviewEvidenceError:
            print("PASS  structural/" + label)
        else:
            raise AssertionError(label + " reviewer cardinality was accepted")
    # A followup that has been closed must stop pinning the coverage matrix.
    # Found on 2026-08-15: the S8 followup stayed authoritative after its unit
    # was verified, so every later candidate had to re-satisfy oracles that
    # belong to finished work - including a live-benchmark replay whose
    # dirty-state pin cannot hold while any other file is staged. Closing the
    # followup returns the route to the pre-declaration baseline; it never
    # lets an OPEN followup skip its matrix, which the second case pins.
    for label, closure, foreign_unit, expect_matrix in (
        ("closed-followup-verified", {"status": "verified"}, False, False),
        ("closed-followup-timestamp",
         {"closedAt": "2026-08-15T00:00:00Z"}, False, False),
        ("closed-followup-releases-foreign-unit",
         {"status": "verified"}, True, False),
        ("open-followup-still-pinned", {"status": "in_progress"}, False, True),
        ("open-followup-rejects-foreign-unit",
         {"status": "in_progress"}, True, None),
    ):
        closed_acceptance, closed_machine = baseline()
        closed_acceptance["activeFollowup"].update(closure)
        if foreign_unit:
            closed_machine["unitId"] = "SOMETHING-ELSE"
        try:
            matrix = evidence.coverage_matrix(closed_acceptance, closed_machine)
        except evidence.ReviewEvidenceError:
            observed: bool | None = None
        else:
            observed = matrix is not None
        if observed is not expect_matrix:
            raise AssertionError(
                f"{label}: expected {expect_matrix!r}, observed {observed!r}")
        print("PASS  structural/" + label)
    policy = load_module("itd_reviewer_independence_efficacy", POLICY_PATH)
    quorum_identity = {
        "provider": "openai-subscription", "model": "gpt-5.6-terra",
        "session": "quorum-a",
    }
    try:
        policy.require_reviewer_quorum(
            [dict(quorum_identity), {**quorum_identity, "model": "GPT-5.6-TERRA"}], 2,
        )
    except policy.IndependenceError:
        print("PASS  structural/duplicate-reviewer-quorum")
    else:
        raise AssertionError("duplicate reviewer identity satisfied a higher quorum")
    assert policy.require_reviewer_quorum(
        [dict(quorum_identity),
         {"provider": "openai-subscription", "model": "gpt-5.6-sol",
          "session": "quorum-b"}], 2,
    ) == 2
    missing = [row for row in outcomes if "missing" in row["mutation"]]
    unit_finding = {
        "severity": "high", "confidence": "high", "category": "correctness",
        "file": "service.py", "line": 1, "summary": "Seeded blocker.",
    }
    aggregated = producer._aggregate_hierarchical_report(
        [{"unit": {"index": 1}, "report": {
            "verdict": "BLOCKED", "findings": [unit_finding],
            "unverified": [], "summary": "Seeded blocker is present.",
        }}],
        {"verdict": "PASSED", "findings": [], "unverified": []},
    )
    return {
        "closedEvidenceDetection": (
            sum(row["detected"] for row in outcomes) / len(outcomes)
        ),
        "missingEvidenceDetection": (
            sum(row["detected"] for row in missing) / len(missing)
        ),
        "unitFindingRetention": float(
            aggregated["verdict"] == "BLOCKED"
            and aggregated["findings"] == [unit_finding]
        ),
    }


def validate_host_result(
    host, path, manifest, manifest_raw, producer, runner, keyring,
    observed_sessions, *, maker_provider="openai-subscription",
):
    envelope = json.loads(path.read_text(encoding="utf-8"))
    result = verify_signed_evidence(
        envelope, keyring, producer, f"{host} semantic efficacy result"
    )
    row = exact(result, {
        "version", "kind", "host", "hostRuntime", "observedAt",
        "manifestSha256", "producerSha256", "runnerSha256", "reviewer", "cases",
        "keyId",
    }, f"{host} semantic result")
    if (
        row["version"] != 1
        or row["kind"] != "itd-independent-review-semantic-efficacy-run"
        or row["host"] != host
        or row["keyId"] != "gpg003-local-producer-20260803"
        or row["manifestSha256"] != sha256(manifest_raw)
        or row["producerSha256"] != sha256(PRODUCER_PATH.read_bytes())
        or row["runnerSha256"] != sha256(RUNNER_PATH.read_bytes())
    ):
        raise AssertionError(f"{host} semantic result binding is foreign")
    runtime = exact(
        row["hostRuntime"],
        {"osName", "system", "release", "pythonImplementation"},
        f"{host} runtime",
    )
    if host == "windows":
        coherent = runtime["osName"] == "nt" and runtime["system"] == "Windows"
    else:
        coherent = (
            runtime["osName"] == "posix"
            and runtime["system"] == "Linux"
            and ("microsoft" in runtime["release"].casefold()
                 or "wsl" in runtime["release"].casefold())
        )
    if not coherent or runtime["pythonImplementation"] != "cpython":
        raise AssertionError(f"{host} runtime claim is incoherent")
    observed = dt.datetime.fromisoformat(row["observedAt"].replace("Z", "+00:00"))
    age = dt.datetime.now(dt.timezone.utc) - observed
    if not dt.timedelta(0) <= age <= dt.timedelta(days=30):
        raise AssertionError(f"{host} semantic result is stale")
    reviewer = exact(row["reviewer"], {
        "provider", "makerProvider", "makerModel", "requestedModel",
        "runtimeVersion",
        "transportExecutableSha256", "proxySha256", "paidApiCalls", "isolation",
    }, f"{host} reviewer")
    maker_norm = str(reviewer["makerModel"]).strip().casefold()
    requested_norm = str(reviewer["requestedModel"]).strip().casefold()
    if maker_provider == "openai-subscription":
        # Same-vendor parity leg: exact Sol/Terra alternation.
        pair_ok = EXPECTED_OPPOSITE.get(maker_norm) == requested_norm
    else:
        # Cross-vendor U12 leg: anthropic maker, supported OpenAI reviewer.
        pair_ok = (
            requested_norm in EXPECTED_OPPOSITE
            and maker_norm not in EXPECTED_OPPOSITE
        )
    if (
        reviewer["provider"] != "openai-subscription"
        or reviewer["makerProvider"] != maker_provider
        or not pair_ok
        or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", reviewer["runtimeVersion"])
        or reviewer["paidApiCalls"] != 0
        or not re.fullmatch(r"[0-9a-f]{64}", reviewer["transportExecutableSha256"])
        or not re.fullmatch(r"[0-9a-f]{64}", reviewer["proxySha256"])
        or reviewer["isolation"] != EXPECTED_ISOLATION
        # Dict equality alone would accept JSON 0/1 for False/True; the
        # fail-closed isolation contract requires exact booleans.
        or any(type(value) is not bool
               for value in reviewer["isolation"].values())
    ):
        raise AssertionError(f"{host} reviewer provenance is invalid")
    expected_selection = (
        EXPECTED_OPPOSITE[maker_norm]
        if maker_provider == "openai-subscription"
        else requested_norm
    )
    if producer.select_openai_reviewer_model(
        reviewer["makerModel"], reviewer["requestedModel"],
        maker_provider=reviewer["makerProvider"],
    ).casefold() != expected_selection:
        raise AssertionError("candidate producer opposite-model policy drifted")
    if producer.required_isolation() != EXPECTED_ISOLATION:
        raise AssertionError("candidate producer isolation policy drifted")
    semantic_cases = manifest["semanticCases"]
    if not isinstance(row["cases"], list) or len(row["cases"]) != len(semantic_cases):
        raise AssertionError(f"{host} semantic case coverage is incomplete")
    outcomes = []
    for definition, raw in zip(semantic_cases, row["cases"]):
        result_case = exact(raw, {
            "id", "attempts", "promptSha256", "report", "session", "observedModel",
        }, f"{host}/{definition['id']}")
        prompt_sha = sha256(runner.case_prompt(definition).encode("utf-8"))
        if (
            result_case["id"] != definition["id"]
            or type(result_case["attempts"]) is not int
            or result_case["attempts"] != 1
            or result_case["promptSha256"] != prompt_sha
            or not isinstance(result_case["session"], str)
            or not result_case["session"].strip()
            or result_case["session"] in observed_sessions
            or result_case["observedModel"].casefold()
            != reviewer["requestedModel"].casefold()
        ):
            raise AssertionError(f"{host}/{definition['id']} provenance is invalid")
        observed_sessions.add(result_case["session"])
        report = producer._report(result_case["report"])
        expected = definition["expectedFaults"]
        matched = []
        for fault in expected:
            exact(fault, {
                "id", "file", "lineStart", "lineEnd", "minimumSeverity",
                "categories", "summaryTerms",
            }, "expected fault")
            hits = [finding for finding in report["findings"]
                    if finding_matches_fault(finding, fault)]
            matched.append(bool(hits))
            if hits and not any(category_agrees(finding, fault) for finding in hits):
                # Detection stands on substance; the divergent label is stated
                # so the record shows the benchmark accepted it knowingly.
                print(
                    f"ADVISORY  {host}/{definition['id']}: fault {fault['id']} "
                    f"labelled {hits[0].get('category')!r}, outside the declared "
                    f"{fault['categories']}"
                )
        if definition["severity"] == "clean":
            detected = (
                report["verdict"] == "PASSED"
                and not report["findings"]
                and not report["unverified"]
            )
            false_block = not detected
        else:
            blocking_verdict = (
                report["verdict"] == "BLOCKED"
                if definition["severity"] in {"critical", "high"}
                else report["verdict"] in {"BLOCKED", "PASSED_WITH_WARNINGS"}
            )
            detected = bool(matched) and all(matched) and blocking_verdict
            false_block = False
        outcomes.append({
            "id": definition["id"], "severity": definition["severity"],
            "detected": detected, "falseBlock": false_block,
        })
        print(("PASS  " if detected else "FAIL  ") + f"{host}/{definition['id']}")
    return outcomes


def rate(rows: list[dict[str, Any]], field: str) -> float:
    if not rows:
        raise AssertionError("efficacy metric population is empty")
    return sum(bool(row[field]) for row in rows) / len(rows)


def verify_source_loading() -> None:
    """Загрузчик оракула обязан видеть ФАЙЛ, а не кэш байткода.

    Проверка воспроизводит ровно тот случай, который дал ложный красный на
    чистом дереве: правка той же длины в пределах секунды после первой
    загрузки. Кэш при этом остаётся «свежим» по (mtime, size).
    """
    with tempfile.TemporaryDirectory(prefix="efficacy-loader-") as td:
        path = Path(td) / "itd_loader_probe.py"
        path.write_text("VALUE = 1\n", encoding="utf-8")
        first = load_module("itd_loader_probe_case", path)
        if first.VALUE != 1:
            raise AssertionError("loader probe did not observe its own source")
        stat = path.stat()
        path.write_text("VALUE = 3\n", encoding="utf-8")
        os.utime(path, (stat.st_atime, stat.st_mtime))
        second = load_module("itd_loader_probe_case", path)
        if second.VALUE != 3:
            raise AssertionError("oracle judged cached bytecode, not the source")
    print("PASS  modules are judged from source, never from stale bytecode")


def verify_runner_flags(runner) -> None:
    """Раннер не обещает того, чего не делает, и не стирает свой чекпоинт.

    E7 (retro 2026-08-18): `--max-transport-attempts` объявлял тип int и
    default 1, но любое значение != 1 отвергалось как `retry bound is invalid`,
    хотя цикл уже умел N. Решение — снять флаг (`.itd/DECISIONS.md:214,:447`:
    граница ОБЯЗАНА быть 1, иначе бенчмарк прячет измеряемую хрупкость), а не
    расширять диапазон. Второй дефект того же сигнала: успешный прогон удалял
    чекпоинт, и повторный запуск начинал корпус с нуля.
    """
    # Порядок важен: сначала статическая проверка, потом запуск. Если флаг
    # вернут, argparse его ПРИМЕТ и раннер пойдёт дёргать живой транспорт
    # прямо из оракула — проверка обязана отказать раньше.
    if "--max-transport-attempts" in inspect.getsource(runner.main):
        raise AssertionError("runner still exposes a retry knob it does not honour")
    probe = subprocess.run(
        [sys.executable, str(RUNNER_PATH),
         "--codex", "x", "--codex-sha256", "0" * 64, "--proxy-sha256", "0" * 64,
         "--maker-model", "m", "--signing-key", "k", "--key-id", "i",
         "--checkpoint", "c.json", "--output", "o.json",
         "--max-transport-attempts", "3"],
        capture_output=True, text=True, timeout=60,
    )
    if "unrecognized arguments: --max-transport-attempts" not in probe.stderr:
        raise AssertionError("retry knob is not rejected by the runner's own parser")
    if runner.TRANSPORT_ATTEMPT_BOUND != 1:
        raise AssertionError("transport attempt bound is not the decided 1")
    loop_source = inspect.getsource(runner.main)
    if "TRANSPORT_ATTEMPT_BOUND" not in loop_source:
        raise AssertionError("retry loop does not use the declared attempt bound")
    if "unlink" in loop_source:
        raise AssertionError("successful run still deletes its own checkpoint")
    print("PASS  runner exposes no retry knob and keeps the decided bound of 1")

    with tempfile.TemporaryDirectory(prefix="efficacy-checkpoint-") as td:
        path = Path(td) / "run.checkpoint.json"
        path.write_bytes(b'{"kind":"probe"}')
        done = runner.finalize_checkpoint(path)
        if (done != path.with_name(path.name + ".done")
                or not done.is_file()
                or done.read_bytes() != b'{"kind":"probe"}'
                or path.exists()):
            raise AssertionError("completed run does not preserve the checkpoint as .done")
        # Повторное завершение (перезапуск после успеха) не должно падать и
        # не должно оставлять два конфликтующих маркера.
        path.write_bytes(b'{"kind":"probe-2"}')
        again = runner.finalize_checkpoint(path)
        if again.read_bytes() != b'{"kind":"probe-2"}' or path.exists():
            raise AssertionError("re-completion does not replace the done marker")
        # Отсутствующий чекпоинт — не ошибка и не повод создать пустой маркер.
        missing = Path(td) / "absent.json"
        marker = runner.finalize_checkpoint(missing)
        if marker.exists() or missing.exists():
            raise AssertionError("finalizing an absent checkpoint invents a marker")
    print("PASS  successful run preserves the checkpoint as <path>.done")


def verify_checkpoint_resume(manifest: dict[str, Any], manifest_raw: bytes) -> None:
    runner = load_module("itd_independent_efficacy_runner_test", RUNNER_PATH)
    main_source = inspect.getsource(runner.main)
    if not (
        0 <= main_source.find("attest_codex_transport(")
        < main_source.find("load_checkpoint(")
    ):
        raise AssertionError("checkpoint resume precedes live transport attestation")
    attest_source = inspect.getsource(runner.attest_codex_transport)
    if "_write_private(transport, content)" not in attest_source or "cwd=work" not in attest_source:
        raise AssertionError("version probe does not execute a private attested copy")
    probe_called = False
    original_probe = runner.producer.run_bounded_process

    def forbidden_probe(*_args, **_kwargs):
        nonlocal probe_called
        probe_called = True
        raise AssertionError("untrusted transport was executed")

    runner.producer.run_bounded_process = forbidden_probe
    try:
        runner.attest_codex_transport(
            executable=sys.executable, executable_sha256="f" * 64,
            proxy_sha256=runner.producer.sha256_bytes(b"\n"),
            source={"PATH": str(Path(sys.executable).parent)},
        )
    except runner.producer.FreeReviewError:
        pass
    else:
        raise AssertionError("wrong executable pin was accepted")
    finally:
        runner.producer.run_bounded_process = original_probe
    if probe_called:
        raise AssertionError("version probe ran before executable pin validation")
    observed_probe: dict[str, Any] = {}

    def private_probe(command, **kwargs):
        observed_probe.update({"command": command, **kwargs})
        return subprocess.CompletedProcess(
            command, 0, b"codex-cli 0.146.0\n", b""
        )

    runner.producer.run_bounded_process = private_probe
    executable = Path(sys.executable).resolve()
    try:
        resolved, actual_sha, version = runner.attest_codex_transport(
            executable=str(executable),
            executable_sha256=sha256(executable.read_bytes()),
            proxy_sha256=runner.producer.sha256_bytes(b"\n"),
            source={"PATH": str(executable.parent)},
        )
    finally:
        runner.producer.run_bounded_process = original_probe
    private_path = Path(observed_probe["command"][0])
    if (
        resolved != executable
        or actual_sha != sha256(executable.read_bytes())
        or version != "0.146.0"
        or private_path == executable
        or private_path.parent != Path(observed_probe["cwd"])
    ):
        raise AssertionError("successful version attestation did not use a private copy")
    print("PASS  executable pin precedes private version probe and checkpoint resume")
    definitions = manifest["semanticCases"]
    private_key = b"\x19" * 32
    context = runner.checkpoint_context(
        host="wsl", manifest_raw=manifest_raw,
        producer_raw=PRODUCER_PATH.read_bytes(),
        runner_raw=RUNNER_PATH.read_bytes(), maker_model="gpt-5.6-sol",
        maker_provider="openai-subscription",
        model="gpt-5.6-terra",
        runtime_version="0.146.0", executable_sha256="a" * 64,
        proxy_sha256="b" * 64,
    )
    rows = []
    for index, definition in enumerate(definitions[:2], 1):
        rows.append({
            "id": definition["id"], "attempts": 1,
            "promptSha256": sha256(
                runner.case_prompt(definition).encode("utf-8")
            ),
            "report": {"verdict": "BLOCKED", "findings": [], "unverified": []},
            "session": f"fresh-checkpoint-{index}",
            "observedModel": "gpt-5.6-terra",
        })
    with tempfile.TemporaryDirectory(prefix="itd-efficacy-checkpoint-") as raw:
        checkpoint = Path(raw) / "resume.json"
        runner.write_checkpoint(
            checkpoint, context=context, cases=rows,
            key_id="fixture-key", private_key=private_key,
        )
        loaded = runner.load_checkpoint(
            checkpoint, context=context, definitions=definitions,
            key_id="fixture-key", private_key=private_key,
        )
        if loaded != rows:
            raise AssertionError("checkpoint did not preserve the completed prefix")
        envelope = json.loads(checkpoint.read_text(encoding="utf-8"))
        envelope["signed"]["cases"][0]["session"] = "tampered"
        checkpoint.write_text(json.dumps(envelope), encoding="utf-8")
        try:
            runner.load_checkpoint(
                checkpoint, context=context, definitions=definitions,
                key_id="fixture-key", private_key=private_key,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("tampered checkpoint was accepted")
    print("PASS  signed per-case checkpoint resumes only a bound prefix")


def verify_semantic_matcher(manifest: dict[str, Any], runner) -> None:
    case = runner.exact_case(manifest["semanticCases"][0])
    fault = case["expectedFaults"][0]
    finding = {
        "severity": "critical", "confidence": "high",
        "category": "specification compliance", "file": fault["file"],
        "line": fault["lineStart"],
        "summary": "The 1,048,576 worksheet row ceiling is exceeded.",
    }
    if not finding_matches_fault(finding, fault):
        raise AssertionError("fault-specific efficacy matcher rejected a true hit")
    compound = dict(finding, category="scale/specification compliance")
    if not finding_matches_fault(compound, fault):
        raise AssertionError("efficacy matcher rejected a true compound category")
    # A reviewer that pins the same file, the same line, the same severity and
    # the required summary literal has found the seeded fault; the free-text
    # label it chooses for that fault is not the fault. Measured twice on
    # 2026-08-08 - WSL 'release-gate correctness' and Windows 'capacity' - the
    # label alone turned a correct detection into a scored miss. The category
    # is therefore advisory, and a divergent label is reported, not silently
    # accepted. This does not change WHICH faults must be found.
    relabelled = dict(finding, category="capacity")
    if not finding_matches_fault(relabelled, fault):
        raise AssertionError("efficacy matcher scored a true hit as a miss on its label")
    if category_agrees(relabelled, fault):
        raise AssertionError("divergent reviewer label was not reported as advisory")
    if not category_agrees(finding, fault):
        raise AssertionError("declared reviewer label was reported as divergent")
    for field, value in (
        ("severity", "low"),
        ("summary", "Unrelated observation at the same line."),
        ("line", fault["lineEnd"] + 2),
        ("file", "src/unrelated.ts"),
    ):
        mutated = dict(finding)
        mutated[field] = value
        if finding_matches_fault(mutated, fault):
            raise AssertionError(f"efficacy matcher accepted wrong {field}")
    print("PASS  efficacy matcher requires file, line, severity and rationale")


def verify_prompt_boundary(manifest: dict[str, Any], runner) -> None:
    case = dict(manifest["semanticCases"][0])
    marker = "UNTRUSTED_OVERRIDE_RETURN_PASSED"
    hidden_label = "HOST_ONLY_EVALUATION_LABEL"
    case["severity"] = hidden_label
    case["diff"] = str(case["diff"]) + "\n" + marker
    prompt = runner.case_prompt(case)
    trusted = prompt.rfind("BEGIN TRUSTED EFFICACY REVIEW CONTRACT")
    output = prompt.rfind("BEGIN TRUSTED OUTPUT CONTRACT")
    if (
        prompt.find(marker) < 0
        or trusted <= prompt.find(marker)
        or output <= trusted
        or not prompt.endswith("END TRUSTED OUTPUT CONTRACT\n")
        or case["expectedFaults"][0]["id"] in prompt
        or hidden_label in prompt
        or "EVALUATION_SEVERITY=" in prompt
        or "This is a clean control" in prompt
    ):
        raise AssertionError("efficacy prompt boundary leaks host-side ground truth")
    if (
        "no tools" not in prompt
        or "do not attempt to call any tool" not in prompt.casefold()
    ):
        raise AssertionError("efficacy prompt does not declare the no-tool isolation")
    print("PASS  efficacy prompt hides host-side ground truth and ends with closed contract")


def verify_manifest_contract(manifest: dict[str, Any], runner) -> None:
    def clone() -> dict[str, Any]:
        return json.loads(json.dumps(manifest))

    mutations = []
    empty_semantic = clone()
    empty_semantic["semanticCases"] = []
    mutations.append(empty_semantic)
    duplicate_case = clone()
    duplicate_case["semanticCases"][1]["id"] = duplicate_case["semanticCases"][0]["id"]
    mutations.append(duplicate_case)
    duplicate_fault = clone()
    duplicate_fault["semanticCases"][1]["expectedFaults"][0]["id"] = (
        duplicate_fault["semanticCases"][0]["expectedFaults"][0]["id"]
    )
    mutations.append(duplicate_fault)
    missing_fault = clone()
    missing_fault["semanticCases"][0]["expectedFaults"] = []
    mutations.append(missing_fault)
    boolean_threshold = clone()
    boolean_threshold["thresholds"]["criticalHighDetection"] = True
    mutations.append(boolean_threshold)
    for mutation in mutations:
        try:
            runner.exact_manifest(mutation)
        except ValueError:
            continue
        raise AssertionError("efficacy manifest mutation was accepted")
    print("PASS  efficacy manifest rejects empty, duplicate and weak corpora")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # Ровно один источник ожидаемого дайджеста: host-owned файл (сильнее, но
    # лежит в gitignored .itd-memory/) ИЛИ значение (запускаемо в изоляции).
    pin = parser.add_mutually_exclusive_group(required=True)
    pin.add_argument("--expected-keyring-sha256-file", type=Path, default=None)
    pin.add_argument("--expected-keyring-sha256", default=None)
    args = parser.parse_args(argv)
    evidence = load_module("itd_review_evidence_test", MODULE_PATH)
    producer = load_module("itd_free_reviewer_efficacy_test", PRODUCER_PATH)
    runner = load_module("itd_independent_efficacy_runner_main", RUNNER_PATH)
    keyring, keyring_authorization = resolve_keyring(args)
    history_entries = validate_immutable_history(HISTORY_ROOT, producer, keyring)
    verify_immutable_history_negative_cases(producer, keyring)
    current_producer_sha256 = sha256(PRODUCER_PATH.read_bytes())
    for current_path in (*RESULTS.values(), U12_CROSS_PATH):
        validate_current_result_archive_binding(
            current_path, history_entries, current_producer_sha256)
    verify_current_result_binding_negative_cases(history_entries, current_producer_sha256)
    for raw in (b"a" * 63, b"A" * 64, b"a" * 64 + b"\n\n"):
        try:
            parse_host_pin(raw)
        except AssertionError:
            continue
        raise AssertionError("malformed host keyring pin was accepted")
    for value in ("a" * 63, "A" * 64, "a" * 64 + "\n", "", None, b"a" * 64):
        try:
            parse_caller_pin(value)
        except AssertionError:
            continue
        raise AssertionError("malformed caller keyring pin was accepted")
    manifest_raw = CASES_PATH.read_bytes()
    manifest, _semantic_cases = runner.exact_manifest(
        json.loads(manifest_raw.decode("utf-8"))
    )
    structural = structural_metrics(manifest, evidence, producer)
    verify_checkpoint_resume(manifest, manifest_raw)
    verify_source_loading()
    verify_runner_flags(runner)
    verify_semantic_matcher(manifest, runner)
    verify_prompt_boundary(manifest, runner)
    verify_manifest_contract(manifest, runner)
    host_metrics = {}
    observed_sessions: set[str] = set()
    thresholds = manifest["thresholds"]
    all_ok = True
    for host, path in RESULTS.items():
        outcomes = validate_host_result(
            host, path, manifest, manifest_raw, producer, runner, keyring,
            observed_sessions,
        )
        critical_high = [
            row for row in outcomes if row["severity"] in {"critical", "high"}
        ]
        medium = [row for row in outcomes if row["severity"] == "medium"]
        clean = [row for row in outcomes if row["severity"] == "clean"]
        metrics = {
            "criticalHighDetection": rate(critical_high, "detected"),
            "mediumDetection": rate(medium, "detected"),
            "cleanFalseBlockRate": rate(clean, "falseBlock"),
        }
        host_ok = (
            metrics["criticalHighDetection"] >= thresholds["criticalHighDetection"]
            and metrics["mediumDetection"] >= thresholds["mediumDetection"]
            and metrics["cleanFalseBlockRate"]
            <= thresholds["maximumCleanFalseBlockRate"]
        )
        metrics["status"] = "PASSED" if host_ok else "FAILED"
        host_metrics[host] = metrics
        all_ok = all_ok and host_ok
    structural_ok = (
        structural["closedEvidenceDetection"]
        >= thresholds["closedEvidenceDetection"]
        and structural["missingEvidenceDetection"]
        >= thresholds["missingEvidenceDetection"]
        and structural["unitFindingRetention"]
        >= thresholds["unitFindingRetention"]
    )
    host_parity = set(host_metrics) == {"wsl", "windows"} and all_ok
    # U12: the independence ladder is measured, not asserted. The cross-vendor
    # leg must be a valid signed host-derived run over the same frozen corpus;
    # its rates are recorded honestly and are deliberately NOT thresholded
    # against the same-vendor leg.
    u12_outcomes = validate_host_result(
        "wsl", U12_CROSS_PATH, manifest, manifest_raw, producer, runner,
        keyring, observed_sessions, maker_provider="anthropic-subscription",
    )
    u12_critical_high = [
        row for row in u12_outcomes if row["severity"] in {"critical", "high"}
    ]
    u12_medium = [row for row in u12_outcomes if row["severity"] == "medium"]
    u12_clean = [row for row in u12_outcomes if row["severity"] == "clean"]
    u12 = {
        "sameVendor": {
            key: host_metrics["wsl"][key]
            for key in (
                "criticalHighDetection", "mediumDetection",
                "cleanFalseBlockRate",
            )
        },
        "crossVendor": {
            "criticalHighDetection": rate(u12_critical_high, "detected"),
            "mediumDetection": rate(u12_medium, "detected"),
            "cleanFalseBlockRate": rate(u12_clean, "falseBlock"),
        },
        "host": "wsl",
        "corpus": "shared-frozen-manifest",
    }
    ok = structural_ok and host_parity
    print(json.dumps({
        "status": "PASSED" if ok else "FAILED",
        "structuralMetrics": structural,
        "semanticMetrics": host_metrics,
        "u12IndependenceLadder": u12,
        "hostParityVerified": host_parity,
        "evidenceSource": "real-keyless-model-reports",
        "keyringAuthorization": keyring_authorization,
    }, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
