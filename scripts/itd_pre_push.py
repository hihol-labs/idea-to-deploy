#!/usr/bin/env python3
"""Global Git pre-push UX guard for registered ITD repositories."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "skills" / "_shared"
sys.path.insert(0, str(SHARED))

import itd_gate_control as gate  # noqa: E402


MAX_STDIN_BYTES = 1024 * 1024
MAX_RECEIPT_BYTES = 4 * 1024 * 1024
ZERO_SHA = "0" * 40


class PushBlocked(RuntimeError):
    pass


def git_root() -> Path:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PushBlocked("Git repository identity is unavailable") from exc
    if completed.returncode != 0 or len(completed.stdout) > 32768:
        raise PushBlocked("Git repository identity is unavailable")
    try:
        return Path(completed.stdout.decode("utf-8").strip()).resolve()
    except UnicodeError as exc:
        raise PushBlocked("Git repository path is not UTF-8") from exc


def parse_updates(raw: bytes) -> list[dict[str, str]]:
    if not raw or len(raw) > MAX_STDIN_BYTES or b"\x00" in raw:
        raise PushBlocked("pre-push update stream is empty or invalid")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise PushBlocked("pre-push update stream is not UTF-8") from exc
    if not 1 <= len(lines) <= 1000:
        raise PushBlocked("pre-push update count is outside its bound")
    updates: list[dict[str, str]] = []
    for line in lines:
        fields = line.split()
        if (
            len(fields) != 4
            or not gate.SHA_RE.fullmatch(fields[1].lower())
            or not gate.SHA_RE.fullmatch(fields[3].lower())
            or not fields[0]
            or not fields[2].startswith("refs/")
        ):
            raise PushBlocked("pre-push update coordinates are invalid")
        updates.append(
            {
                "localRef": fields[0],
                "localSha": fields[1].lower(),
                "remoteRef": fields[2],
                "remoteSha": fields[3].lower(),
            }
        )
    return updates


def protected_ref(value: str) -> bool:
    return (
        value in {"refs/heads/main", "refs/heads/master"}
        or value.startswith("refs/heads/release/")
    )


def load_machine_receipt(path: Path) -> dict[str, Any]:
    if not path.is_absolute() or not path.is_file():
        raise PushBlocked("guarded push machine receipt is unavailable")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PushBlocked("guarded push machine receipt is unreadable") from exc
    if not raw or len(raw) > MAX_RECEIPT_BYTES:
        raise PushBlocked("guarded push machine receipt size is invalid")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PushBlocked("guarded push machine receipt is invalid JSON") from exc
    if not isinstance(value, dict):
        raise PushBlocked("guarded push machine receipt is not an object")
    unsigned = dict(value)
    supplied = unsigned.pop("receiptSha256", None)
    calculated = hashlib.sha256(gate.canonical_json(unsigned)).hexdigest()
    if (
        supplied != calculated
        or value.get("version") != 2
        or value.get("kind") != "itd-machine-oracle"
        or value.get("status") != "PASSED"
        or value.get("executionCheckout") != "isolated-exact-head-tree"
        or value.get("verifierTrust")
        not in {"LOCAL_ONLY", "PROTECTED_BASE_CONTENT_BOUND"}
        or value.get("trustedVerifierFailures") != []
        or not isinstance(value.get("trustedVerifierBindings"), list)
        or not value["trustedVerifierBindings"]
        or not any(
            isinstance(row, dict)
            and row.get("objectKind") == "tree"
            and row.get("status") in {"LOCAL_ONLY", "MATCHED"}
            for row in value["trustedVerifierBindings"]
        )
        or not gate.SHA_RE.fullmatch(str(value.get("headSha", "")).lower())
        or not gate.SHA_RE.fullmatch(str(value.get("tree", "")).lower())
        or not isinstance(value.get("commands"), list)
        or not value["commands"]
        or any(row.get("status") != "PASSED" for row in value["commands"])
    ):
        raise PushBlocked(
            "guarded push receipt is stale, malformed, or did not pass"
        )
    return value


def enforce(
    remote_url: str,
    raw_updates: bytes,
    *,
    environment: dict[str, str] | None = None,
    registry: dict[str, Any] | None = None,
    root: Path | None = None,
) -> None:
    updates = parse_updates(raw_updates)
    protected = [
        row["remoteRef"] for row in updates if protected_ref(row["remoteRef"])
    ]
    if protected:
        raise PushBlocked(
            "direct push to protected branch is forbidden: "
            + ", ".join(sorted(protected))
        )
    try:
        repository = gate.github_repository_from_remote(remote_url)
    except gate.GateError:
        return
    if registry is None:
        try:
            registry = gate.load_registry()
        except gate.GateError as exc:
            raise PushBlocked(
                "GitHub pushes require an available ITD gate registry"
            ) from exc
    matches = [
        row
        for row in registry["repositories"]
        if row["repository"].casefold() == repository.casefold()
    ]
    if not matches:
        raise PushBlocked(
            "GitHub repository is not registered in the ITD gate"
        )
    environment = environment if environment is not None else os.environ
    if environment.get("ITD_GUARDED_PR_PUSH") != "1":
        raise PushBlocked(
            "registered repository pushes must use `itd pr create`"
        )
    for name in (
        "ITD_MAKER_VENDOR",
        "ITD_MAKER_MODEL",
        "ITD_MAKER_SESSION",
    ):
        value = environment.get(name, "")
        if (
            not value
            or len(value) > 200
            or "\r" in value
            or "\n" in value
        ):
            raise PushBlocked(
                "guarded push maker provenance is missing or invalid"
            )
    receipt_raw = environment.get("ITD_MACHINE_RECEIPT", "")
    receipt = load_machine_receipt(Path(receipt_raw))
    expected_head = str(receipt["headSha"]).lower()
    if any(
        row["localSha"] in {ZERO_SHA}
        or row["localSha"] != expected_head
        for row in updates
    ):
        raise PushBlocked(
            "pushed commit does not equal the exact machine receipt HEAD"
        )
    actual_root = (root or git_root()).resolve()
    if actual_root != Path(matches[0]["checkout"]).resolve():
        raise PushBlocked(
            "registered checkout differs from the active Git repository"
        )
    if Path(str(receipt.get("repository", ""))).resolve() != actual_root:
        raise PushBlocked(
            "machine receipt repository differs from the active checkout"
        )


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 2:
        print(
            "BLOCKED: pre-push requires remote name and URL. "
            "FIX: reinstall the ITD global Git hooks.",
            file=sys.stderr,
        )
        return 1
    del arguments[0]
    try:
        raw = sys.stdin.buffer.read(MAX_STDIN_BYTES + 1)
        enforce(arguments[0], raw)
    except (PushBlocked, gate.GateError) as exc:
        print(
            f"BLOCKED: {exc}. FIX: use `itd pr create` or repair "
            "`itd gate doctor --all` findings.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
