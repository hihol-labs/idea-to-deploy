#!/usr/bin/env python3
"""Mutation checks for the offline broker enrollment operator."""
from __future__ import annotations

import importlib.util
import json
import stat
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "services" / "review_broker" / "operator.py"
spec = importlib.util.spec_from_file_location(
    "itd_review_broker_operator_test", MODULE
)
assert spec and spec.loader
operator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = operator
spec.loader.exec_module(operator)

CHECKS = 0
REPOSITORY = "hihol-labs/operator-fixture"
APP_ID = 424242


def check(value: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not value:
        raise AssertionError(label)


def rejects(fn, label: str) -> None:
    global CHECKS
    CHECKS += 1
    try:
        fn()
    except operator.core.BrokerError:
        return
    raise AssertionError(label)


def key_record() -> dict:
    return {
        "repository": REPOSITORY,
        "keyId": "current",
        "authorizedMakerVendor": "openai",
        "authorizedMakerModel": "gpt-5.6-sol",
        "publicKey": operator.core.b64url(bytes(range(32))),
        "issuerPrincipal": "operator-fixture",
        "status": "active",
    }


def enrollment_receipt(ruleset_id: int = 91) -> dict:
    return {
        "repository": REPOSITORY,
        "rulesetId": ruleset_id,
        "rulesetEnforcement": "active",
        "rulesetTarget": "branch",
        "defaultBranchRef": "refs/heads/main",
        "protectedRefPatterns": {
            "~DEFAULT_BRANCH": True,
            "refs/heads/release/*": True,
        },
        "excludedRefPatterns": {},
        "requiredPullRequest": True,
        "requireUpToDate": True,
        "requiredStatusChecks": {
            "externalReview": {
                "name": "ITD external review gate",
                "expectedPublisher": "github-app-integration-id",
                "integrationId": APP_ID,
            },
            "machineOracle": {
                "name": "ITD machine oracle",
                "expectedPublisher": "github-actions",
                "integrationId": 15368,
                "authority": "organization-ruleset-workflow",
                "workflowRepository": "hihol-labs/idea-to-deploy",
                "workflowRepositoryId": 515151,
                "workflowPath": ".github/workflows/itd-machine-oracle.yml",
                "workflowSha": "1" * 40,
            },
        },
        "githubAppClientId": "Iv1.operatorfixture",
        "githubAppSlug": "itd-review-gate",
        "githubAppOwner": "hihol-labs",
        "githubAppNodeId": "MDM6QXBwNDI0MjQy",
        "blockDeletion": True,
        "blockForcePush": True,
        "mergeGroupEventsRequired": True,
        "bypassActors": [],
        "policyId": "itd-central-review-broker-v1",
        "observedAt": operator.core.now_iso(),
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="itd-broker-operator-") as raw:
        root = Path(raw)
        keyring = root / "provenance-keyring.json"
        record = root / "record.json"
        receipt = root / "enrollment.json"
        database = root / "broker.sqlite3"
        record.write_text(json.dumps(key_record()), encoding="utf-8")
        receipt.write_text(
            json.dumps(enrollment_receipt()), encoding="utf-8"
        )

        key_args = operator.parser().parse_args(
            [
                "keyring-add",
                "--keyring",
                str(keyring),
                "--record",
                str(record),
            ]
        )
        preview = key_args.handler(key_args)
        check(
            preview["status"] == "PREVIEW" and not keyring.exists(),
            "keyring preview is read-only",
        )
        key_args.apply = True
        applied = key_args.handler(key_args)
        check(
            applied["status"] == "APPLIED" and keyring.is_file(),
            "keyring apply persists the validated public record",
        )
        if operator.os.name != "nt":
            check(
                stat.S_IMODE(keyring.stat().st_mode) == 0o600,
                "keyring file mode is private",
            )
        loaded = operator.load_keyring(
            keyring, operator.core.load_policy()
        )
        check(
            loaded["current"]["repository"] == REPOSITORY,
            "keyring reload preserves exact authorization",
        )
        rejects(
            lambda: operator.open_store(
                Path("relative-broker.sqlite3"), keyring
            ),
            "operator rejects a relative broker database path",
        )

        changed = key_record()
        changed["authorizedMakerModel"] = "gpt-5.6-terra"
        record.write_text(json.dumps(changed), encoding="utf-8")
        rejects(
            lambda: key_args.handler(key_args),
            "keyId rotation cannot overwrite active authorization",
        )

        enroll_args = operator.parser().parse_args(
            [
                "enroll",
                "--database",
                str(database),
                "--keyring",
                str(keyring),
                "--receipt",
                str(receipt),
            ]
        )
        preview = enroll_args.handler(enroll_args)
        check(
            preview["status"] == "PREVIEW" and not database.exists(),
            "enrollment preview is read-only",
        )
        enroll_args.apply = True
        enrolled = enroll_args.handler(enroll_args)
        check(
            enrolled["status"] == "ENROLLED"
            and database.is_file(),
            "enrollment apply stores the immutable receipt",
        )
        repeated = enroll_args.handler(enroll_args)
        check(
            repeated["receiptSha256"] == enrolled["receiptSha256"],
            "exact enrollment replay is idempotent",
        )

        status_args = operator.parser().parse_args(
            [
                "status",
                "--database",
                str(database),
                "--keyring",
                str(keyring),
                "--repository",
                REPOSITORY,
                "--app-id",
                str(APP_ID),
            ]
        )
        status = status_args.handler(status_args)
        check(
            status["status"] == "ENROLLED"
            and status["receiptSha256"] == enrolled["receiptSha256"],
            "operator status returns the active exact receipt",
        )

        receipt.write_text(
            json.dumps(enrollment_receipt(92)), encoding="utf-8"
        )
        rejects(
            lambda: enroll_args.handler(enroll_args),
            "active enrollment is immutable across ruleset drift",
        )

    print(
        json.dumps(
            {"checks": CHECKS, "status": "PASSED"},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
