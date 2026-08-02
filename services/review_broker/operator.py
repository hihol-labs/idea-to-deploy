#!/usr/bin/env python3
"""Offline operator boundary for broker keyring and enrollment changes."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "skills" / "_shared"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SHARED))

import itd_review_broker_primitives as core  # noqa: E402
from services.review_broker.server import (  # noqa: E402
    validate_public_keyring,
)


MAX_KEYRING_BYTES = 65536


def canonical_line(value: Any) -> bytes:
    return core.canonical_json(value) + b"\n"


def atomic_write(path: Path, value: bytes) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def load_keyring(path: Path, policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise core.BrokerError(
            "UNAVAILABLE", "provenance keyring is unavailable"
        ) from exc
    if not raw or len(raw) > MAX_KEYRING_BYTES:
        raise core.BrokerError(
            "UNVERIFIED", "provenance keyring size is invalid"
        )
    value = core.decode_strict_json(raw, "provenance keyring")
    return validate_public_keyring(value, policy)


def keyring_add(args: argparse.Namespace) -> dict[str, Any]:
    policy = core.load_policy()
    try:
        record = core.read_json(args.record, MAX_KEYRING_BYTES)
    except core.BrokerError:
        raise
    key_id = record.get("keyId") if isinstance(record, dict) else None
    if not isinstance(key_id, str):
        raise core.BrokerError(
            "UNVERIFIED", "provenance key record has no keyId"
        )
    if args.keyring.exists():
        current = load_keyring(args.keyring, policy)
    else:
        current = {}
    previous = current.get(key_id)
    if previous is not None and previous != record:
        raise core.BrokerError(
            "UNVERIFIED", "provenance keyId already has different material"
        )
    candidate = dict(current)
    candidate[key_id] = record
    validated = validate_public_keyring(candidate, policy)
    payload = canonical_line(validated)
    result = {
        "status": "PREVIEW",
        "keyId": key_id,
        "repository": record.get("repository"),
        "keyring": str(args.keyring.resolve()),
        "keyringSha256": core.sha256_bytes(payload),
        "restartRequired": previous is None,
    }
    if not args.apply:
        return result
    atomic_write(args.keyring, payload)
    result["status"] = "APPLIED"
    return result


def open_store(
    database: Path,
    keyring: Path,
) -> core.BrokerStore:
    if not database.is_absolute():
        raise core.BrokerError(
            "UNVERIFIED", "broker database path must be absolute"
        )
    database = database.resolve()
    policy = core.load_policy()
    keys = load_keyring(keyring, policy)
    database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    return core.BrokerStore(
        database,
        policy=policy,
        provenance_keyring=keys,
    )


def enrollment_apply(args: argparse.Namespace) -> dict[str, Any]:
    receipt = core.read_json(args.receipt)
    core.validate_runtime_record("enrollmentReceipt", receipt)
    serialized = core.canonical_json(receipt)
    result = {
        "status": "PREVIEW",
        "repository": receipt["repository"],
        "appId": receipt["requiredStatusChecks"]["externalReview"][
            "integrationId"
        ],
        "receiptSha256": core.sha256_bytes(serialized),
        "database": str(args.database.resolve()),
    }
    if not args.apply:
        return result
    store = open_store(args.database, args.keyring)
    try:
        stored = store.enroll(receipt)
    finally:
        store.close()
    if stored != result["receiptSha256"]:
        raise core.BrokerError(
            "UNVERIFIED", "stored enrollment digest differs from preview"
        )
    result["status"] = "ENROLLED"
    return result


def enrollment_status(args: argparse.Namespace) -> dict[str, Any]:
    store = open_store(args.database, args.keyring)
    try:
        value = store.enrollment_status(args.repository, args.app_id)
    finally:
        store.close()
    return {"status": "ENROLLED", **value}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Operate the offline ITD broker trust store"
    )
    sub = result.add_subparsers(dest="command", required=True)

    keyring = sub.add_parser("keyring-add")
    keyring.add_argument("--keyring", type=Path, required=True)
    keyring.add_argument("--record", type=Path, required=True)
    keyring.add_argument("--apply", action="store_true")
    keyring.set_defaults(handler=keyring_add)

    enroll = sub.add_parser("enroll")
    enroll.add_argument("--database", type=Path, required=True)
    enroll.add_argument("--keyring", type=Path, required=True)
    enroll.add_argument("--receipt", type=Path, required=True)
    enroll.add_argument("--apply", action="store_true")
    enroll.set_defaults(handler=enrollment_apply)

    status = sub.add_parser("status")
    status.add_argument("--database", type=Path, required=True)
    status.add_argument("--keyring", type=Path, required=True)
    status.add_argument("--repository", required=True)
    status.add_argument("--app-id", type=int, required=True)
    status.set_defaults(handler=enrollment_status)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        value = args.handler(args)
    except (core.BrokerError, OSError) as exc:
        status = (
            exc.status
            if isinstance(exc, core.BrokerError)
            else "UNAVAILABLE"
        )
        print(
            json.dumps(
                {"status": status, "reason": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
