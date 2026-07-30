#!/usr/bin/env python3
"""Mutation checks for global ITD gate/ruleset control primitives."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "skills" / "_shared" / "itd_gate_control.py"
spec = importlib.util.spec_from_file_location("itd_gate_control_test", MODULE)
assert spec and spec.loader
gate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gate
spec.loader.exec_module(gate)
CHECKS = 0


def check(value: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not value:
        raise AssertionError(label)


def rejects(status: str, fn, label: str) -> None:
    global CHECKS
    CHECKS += 1
    try:
        fn()
    except gate.GateError as exc:
        if exc.status != status:
            raise AssertionError(f"{label}: {exc.status} != {status}") from exc
    else:
        raise AssertionError(f"{label}: mutation passed")


APP_ID = 424242
WORKFLOW_REPOSITORY_ID = 515151
WORKFLOW_SHA = "1" * 40
REPOSITORY = "hihol-labs/example"
PRIVATE_KEY = bytes(range(32))
PUBLIC_KEY = gate.provenance_public_key(PRIVATE_KEY)


def write_key(path: Path) -> None:
    gate.write_provenance_private_key(path, PRIVATE_KEY)


def registry(checkout: Path, key_file: Path) -> dict[str, Any]:
    return {
        "version": 1,
        "repositories": [
            {
                "repository": REPOSITORY,
                "checkout": str(checkout),
                "brokerUrl": "https://broker.example.test",
                "appId": APP_ID,
                "rulesetScope": "organization",
                "rulesetId": 91,
                "machineWorkflowRepositoryId": WORKFLOW_REPOSITORY_ID,
                "machineWorkflowSha": WORKFLOW_SHA,
                "provenanceKeyId": "current",
                "provenanceKeyFile": str(key_file),
            }
        ],
    }


def ruleset_phase() -> None:
    value = gate.ruleset_payload(
        APP_ID,
        scope="organization",
        workflow_repository_id=WORKFLOW_REPOSITORY_ID,
        workflow_sha=WORKFLOW_SHA,
    )
    check(value["enforcement"] == "active", "ruleset active")
    check(value["bypass_actors"] == [], "no bypass actors")
    by_type = {row["type"]: row for row in value["rules"]}
    check("deletion" in by_type, "deletion blocked")
    check("non_fast_forward" in by_type, "force push blocked")
    status = by_type["required_status_checks"]["parameters"]
    check(status["strict_required_status_checks_policy"] is True, "strict checks")
    checks = {
        (row["context"], row["integration_id"])
        for row in status["required_status_checks"]
    }
    check(
        checks
        == {(gate.EXTERNAL_CHECK, APP_ID)},
        "external check is bound to the dedicated App",
    )
    workflows = by_type["workflows"]["parameters"]
    check(
        workflows
        == {
            "do_not_enforce_on_create": False,
            "workflows": [
                {
                    "path": gate.MACHINE_WORKFLOW_PATH,
                    "repository_id": WORKFLOW_REPOSITORY_ID,
                    "sha": WORKFLOW_SHA,
                }
            ],
        },
        "machine oracle is a pinned organization ruleset workflow",
    )
    check(
        gate.validate_live_ruleset(
            value,
            APP_ID,
            scope="organization",
            workflow_repository_id=WORKFLOW_REPOSITORY_ID,
            workflow_sha=WORKFLOW_SHA,
        )
        == [],
        "canonical organization ruleset",
    )

    mutations = [
        ("disabled", lambda row: row.update(enforcement="disabled")),
        ("admin bypass", lambda row: row["bypass_actors"].append(
            {"actor_type": "OrganizationAdmin", "actor_id": None, "bypass_mode": "always"}
        )),
        ("force push", lambda row: row["rules"].remove(
            next(item for item in row["rules"] if item["type"] == "non_fast_forward")
        )),
        ("non-strict", lambda row: next(
            item for item in row["rules"] if item["type"] == "required_status_checks"
        )["parameters"].update(strict_required_status_checks_policy=False)),
        ("fake App", lambda row: next(
            item for item in row["rules"] if item["type"] == "required_status_checks"
        )["parameters"]["required_status_checks"][0].update(integration_id=APP_ID + 1)),
        (
            "workflow SHA",
            lambda row: next(
                item
                for item in row["rules"]
                if item["type"] == "workflows"
            )["parameters"]["workflows"][0].update(sha="2" * 40),
        ),
        (
            "unexpected rule",
            lambda row: row["rules"].append({"type": "creation"}),
        ),
    ]
    for label, mutate in mutations:
        changed = copy.deepcopy(value)
        mutate(changed)
        check(
            bool(
                gate.validate_live_ruleset(
                    changed,
                    APP_ID,
                    scope="organization",
                    workflow_repository_id=WORKFLOW_REPOSITORY_ID,
                    workflow_sha=WORKFLOW_SHA,
                )
            ),
            f"drift detected: {label}",
        )

    check(
        value["conditions"]["repository_name"]["include"] == ["~ALL"],
        "organization covers future repositories",
    )
    rejects(
        "UNVERIFIED",
        lambda: gate.ruleset_payload(
            APP_ID,
            scope="repository",
            workflow_repository_id=WORKFLOW_REPOSITORY_ID,
            workflow_sha=WORKFLOW_SHA,
            repository_name="example",
        ),
        "repository ruleset cannot impersonate protected workflow authority",
    )


def registry_phase() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-gate-control-") as raw:
        root = Path(raw)
        checkout = root / "checkout"
        checkout.mkdir()
        key_file = root / "provenance.key"
        write_key(key_file)
        value = registry(checkout, key_file)
        validated = gate.validate_registry(value)
        check(validated["repositories"][0]["appId"] == APP_ID, "registry valid")

        duplicate = copy.deepcopy(value)
        duplicate["repositories"].append(copy.deepcopy(value["repositories"][0]))
        rejects(
            "UNVERIFIED",
            lambda: gate.validate_registry(duplicate),
            "duplicate registry repository",
        )
        credential_url = copy.deepcopy(value)
        credential_url["repositories"][0][
            "brokerUrl"
        ] = "https://user:password@broker.example.test"
        rejects(
            "UNVERIFIED",
            lambda: gate.validate_registry(credential_url),
            "credential-bearing broker URL",
        )
        relative_key = copy.deepcopy(value)
        relative_key["repositories"][0]["provenanceKeyFile"] = "relative.key"
        rejects(
            "UNVERIFIED",
            lambda: gate.validate_registry(relative_key),
            "relative provenance key",
        )


def transport_phase() -> None:
    calls: list[dict[str, Any]] = []

    def runner(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=b'{"id":91}',
            stderr=b"",
        )

    value = gate.gh_json(
        ["--method", "POST", "repos/hihol-labs/example/rulesets", "--input", "-"],
        input_value={"name": "fixture"},
        runner=runner,
    )
    check(value == {"id": 91}, "GitHub JSON parsed")
    command = calls[0]["command"]
    check(
        command[:2] == ["gh", "api"]
        and "X-GitHub-Api-Version: 2026-03-10" in command,
        "versioned gh API",
    )
    check(
        calls[0]["input"] == b'{"name":"fixture"}',
        "payload only through stdin",
    )
    check(
        all("fixture" not in argument for argument in command),
        "payload absent from argv",
    )

    def failure(command, **kwargs):
        return subprocess.CompletedProcess(
            command, 1, stdout=b"", stderr=b"denied"
        )

    rejects(
        "UNAVAILABLE",
        lambda: gate.gh_json(["repos/x/y/rulesets"], runner=failure),
        "GitHub failure",
    )


def doctor_phase() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-gate-doctor-") as raw:
        root = Path(raw)
        checkout = root / "checkout"
        contract = checkout / ".itd" / "VERIFICATION_CONTRACT.json"
        contract.parent.mkdir(parents=True)
        verifier = checkout / "tests" / "verify.py"
        verifier.parent.mkdir()
        verifier.write_text("raise SystemExit(0)\n", encoding="utf-8")
        contract.write_text(
            json.dumps(
                {
                    "version": 2,
                    "failClosed": "missing commands block",
                    "commands": [
                        {
                            "id": "tests",
                            "argv": ["python3", "-I", "tests/verify.py"],
                            "trustedVerifierPaths": ["tests"],
                            "timeoutSeconds": 30,
                            "expectedOutput": "",
                            "passFailParser": "exit_code_zero",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "init", "-q", str(checkout)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            ["git", "-C", str(checkout), "add", "."],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        key_file = root / "provenance.key"
        write_key(key_file)
        entry = registry(checkout, key_file)["repositories"][0]
        live = gate.ruleset_payload(
            APP_ID,
            scope="organization",
            workflow_repository_id=WORKFLOW_REPOSITORY_ID,
            workflow_sha=WORKFLOW_SHA,
        )
        base_contract_raw = json.dumps(
            {
                "version": 2,
                "failClosed": "missing commands block",
                "commands": [
                    {
                        "id": "tests",
                        "argv": ["python3", "-I", "tests/verify.py"],
                        "trustedVerifierPaths": ["tests"],
                        "timeoutSeconds": 30,
                        "expectedOutput": "",
                        "passFailParser": "exit_code_zero",
                    }
                ],
            }
        ).encode("utf-8")
        base_contract = {
            "type": "file",
            "path": ".itd/VERIFICATION_CONTRACT.json",
            "sha": hashlib.sha1(
                b"blob "
                + str(len(base_contract_raw)).encode("ascii")
                + b"\0"
                + base_contract_raw,
                usedforsecurity=False,
            ).hexdigest(),
            "encoding": "base64",
            "size": len(base_contract_raw),
            "content": gate.base64.b64encode(
                base_contract_raw
            ).decode("ascii"),
        }

        def github(arguments):
            endpoint = arguments[0]
            if endpoint == f"repos/{REPOSITORY}":
                return {"default_branch": "main"}
            if "/contents/.itd/VERIFICATION_CONTRACT.json" in endpoint:
                return base_contract
            return live

        result = gate.doctor_entry(
            entry,
            gh=github,
            readiness=lambda _url, _repository, _app_id, _key_id, _public: {
                "status": "ready",
                "budget": {"spentUsd": 0.0},
            },
        )
        check(result["status"] == "PROTECTED", "doctor protected")

        missing_base_contract = gate.doctor_entry(
            entry,
            gh=lambda arguments: (
                {"default_branch": "main"}
                if arguments[0] == f"repos/{REPOSITORY}"
                else {"message": "not found"}
                if "/contents/.itd/VERIFICATION_CONTRACT.json"
                in arguments[0]
                else live
            ),
            readiness=lambda _url, _repository, _app_id, _key_id, _public: {
                "status": "ready"
            },
        )
        check(
            missing_base_contract["status"] == "UNVERIFIED"
            and any(
                "protected base contract" in row
                for row in missing_base_contract["drift"]
            ),
            "doctor rejects a local-only adoption contract",
        )

        live_drift = copy.deepcopy(live)
        live_drift["bypass_actors"] = [
            {
                "actor_type": "OrganizationAdmin",
                "actor_id": None,
                "bypass_mode": "always",
            }
        ]
        result = gate.doctor_entry(
            entry,
            gh=lambda arguments: (
                {"default_branch": "main"}
                if arguments[0] == f"repos/{REPOSITORY}"
                else base_contract
                if "/contents/.itd/VERIFICATION_CONTRACT.json"
                in arguments[0]
                else live_drift
            ),
            readiness=lambda _url, _repository, _app_id, _key_id, _public: {
                "status": "ready"
            },
        )
        check(
            result["status"] == "UNVERIFIED"
            and any("bypass" in row for row in result["drift"]),
            "doctor detects bypass drift",
        )


def readiness_phase() -> None:
    policy = json.loads(gate.POLICY_PATH.read_text(encoding="utf-8"))
    value = {
        "status": "ready",
        "policyId": policy["id"],
        "policySha256": hashlib.sha256(
            gate.POLICY_PATH.read_bytes()
        ).hexdigest(),
        "reviewers": [
            {
                "id": reviewer_id,
                "vendor": row["vendor"],
                "model": row["model"],
            }
            for reviewer_id, row in sorted(
                policy["routing"]["reviewers"].items()
            )
        ],
        "budget": {
            "period": "2026-07",
            "reservedMicrousd": 0,
            "spentMicrousd": 100000,
            "monthlyMicrousd": 10000000,
            "reservationMicrousd": 750000,
            "remainingMicrousd": 9900000,
            "admissionAvailable": True,
        },
        "enrollment": {
            "repository": REPOSITORY,
            "appId": APP_ID,
            "receiptSha256": "a" * 64,
            "enrolledAt": "2026-07-30T00:00:00Z",
        },
        "provenanceKeys": [
            {
                "repository": REPOSITORY,
                "keyId": "current",
                "authorizedMakerVendor": "openai",
                "authorizedMakerModel": "gpt-5.6-sol",
                "publicKey": PUBLIC_KEY,
                "issuerPrincipal": "fixture",
                "status": "active",
            }
        ],
    }
    observed: list[str] = []

    class Response:
        status = 200

        def __init__(self, payload: dict[str, Any]) -> None:
            self.payload = json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, limit: int) -> bytes:
            return self.payload[:limit]

    def opener(request, timeout: int):
        check(timeout == 10, "readiness timeout bounded")
        observed.append(request.full_url)
        return Response(value)

    result = gate.broker_ready(
        "https://broker.example.test",
        REPOSITORY,
        APP_ID,
        "current",
        PUBLIC_KEY,
        opener=opener,
    )
    query = parse_qs(urlsplit(observed[0]).query)
    check(
        result["status"] == "ready"
        and query == {
            "repository": [REPOSITORY],
            "appId": [str(APP_ID)],
        },
        "readiness binds exact enrollment coordinates",
    )

    for label, mutate, status in [
        (
            "policy drift",
            lambda row: row.update(policySha256="b" * 64),
            "UNVERIFIED",
        ),
        (
            "reviewer drift",
            lambda row: row.update(reviewers=[]),
            "UNVERIFIED",
        ),
        (
            "budget exhausted",
            lambda row: row["budget"].update(admissionAvailable=False),
            "UNAVAILABLE",
        ),
        (
            "wrong App enrollment",
            lambda row: row["enrollment"].update(appId=APP_ID + 1),
            "UNVERIFIED",
        ),
    ]:
        changed = copy.deepcopy(value)
        mutate(changed)
        rejects(
            status,
            lambda changed=changed: gate.broker_ready(
                "https://broker.example.test",
                REPOSITORY,
                APP_ID,
                "current",
                PUBLIC_KEY,
                opener=lambda _request, timeout: Response(changed),
            ),
            label,
        )


def main() -> int:
    ruleset_phase()
    registry_phase()
    transport_phase()
    doctor_phase()
    readiness_phase()
    print(json.dumps({"checks": CHECKS, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
