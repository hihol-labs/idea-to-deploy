#!/usr/bin/env python3
from __future__ import annotations

import base64
import importlib.util
import json
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "itd.py"
spec = importlib.util.spec_from_file_location("itd_cli_test", MODULE)
assert spec and spec.loader
cli = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cli
spec.loader.exec_module(cli)
CHECKS = 0
APP_ID = 424242
WORKFLOW_REPOSITORY_ID = 515151
WORKFLOW_SHA = "1" * 40
HEAD = "a" * 40
BASE = "b" * 40
REPOSITORY = "hihol-labs/example"
CHECK_SHA = "c" * 40
PRIVATE_KEY = bytes(range(32))


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
    except cli.gate.GateError as exc:
        if exc.status != status:
            raise AssertionError(f"{label}: {exc.status} != {status}") from exc
    else:
        raise AssertionError(f"{label}: expected error")


class Response:
    def __init__(
        self,
        value: dict[str, Any],
        *,
        url: str = "https://broker.example.test/provenance",
    ) -> None:
        self.raw = json.dumps(value).encode()
        self.url = url
        self.status = 202

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, limit: int) -> bytes:
        return self.raw[:limit]

    def geturl(self) -> str:
        return self.url


def entry(key_file: Path) -> dict[str, Any]:
    return {
        "repository": REPOSITORY,
        "checkout": str(key_file.parent),
        "brokerUrl": "https://broker.example.test",
        "appId": APP_ID,
        "rulesetScope": "organization",
        "rulesetId": 91,
        "machineWorkflowRepositoryId": WORKFLOW_REPOSITORY_ID,
        "machineWorkflowSha": WORKFLOW_SHA,
        "provenanceKeyId": "current",
        "provenanceKeyFile": str(key_file),
    }


def write_key(path: Path) -> None:
    cli.gate.write_provenance_private_key(path, PRIVATE_KEY)


def provenance_phase() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-cli-provenance-") as raw:
        key_file = Path(raw) / "signing.key"
        material = PRIVATE_KEY
        write_key(key_file)
        observed: dict[str, Any] = {}

        def opener(request, timeout: int):
            check(timeout == 15, "broker timeout")
            payload = json.loads(request.data)
            observed.update(payload)
            unsigned = cli.gate.provenance_payload(payload)
            supplied = base64.urlsafe_b64decode(
                payload["signature"] + "=="
            )
            Ed25519PrivateKey.from_private_bytes(material).public_key().verify(
                supplied, cli.gate.canonical_json(unsigned)
            )
            check(len(payload["signature"]) == 86, "Ed25519 provenance")
            return Response(
                {
                    "status": "queued",
                    "repository": REPOSITORY,
                    "pullRequest": 9,
                    "headSha": HEAD,
                    "baseSha": BASE,
                }
            )

        result = cli.submit_provenance(
            entry(key_file),
            {
                "number": 9,
                "headRefOid": HEAD,
                "baseRefOid": BASE,
            },
            "openai",
            "gpt-5.6-sol",
            "maker-session",
            opener=opener,
        )
        check(result["status"] == "queued", "provenance accepted")
        check(observed["keyId"] == "current", "provenance key id")
        check(len(observed["nonce"]) >= 24, "fresh nonce")
        rejects(
            "UNVERIFIED",
            lambda: cli.RejectRedirectHandler().redirect_request(
                None,
                None,
                307,
                "Temporary Redirect",
                {},
                "https://attacker.example.test/provenance",
            ),
            "default opener rejects redirect before resend",
        )

        def redirect(_request, timeout: int):
            return Response(
                {
                    "status": "queued",
                    "repository": REPOSITORY,
                    "pullRequest": 9,
                    "headSha": HEAD,
                    "baseSha": BASE,
                },
                url="https://attacker.example.test/provenance",
            )

        rejects(
            "UNVERIFIED",
            lambda: cli.submit_provenance(
                entry(key_file),
                {
                    "number": 9,
                    "headRefOid": HEAD,
                    "baseRefOid": BASE,
                },
                "openai",
                "gpt-5.6-sol",
                "maker-session",
                opener=redirect,
            ),
            "cross-origin redirect",
        )


def check_phase() -> None:
    pull = {
        "number": 9,
        "state": "open",
        "draft": True,
        "mergeable": True,
        "head": {"sha": HEAD, "repo": {"full_name": REPOSITORY}},
        "base": {"sha": BASE, "repo": {"full_name": REPOSITORY}},
        "merge_commit_sha": CHECK_SHA,
    }
    pending = {"check_runs": []}
    success = {
        "check_runs": [
            {
                "id": 101,
                "name": cli.gate.MACHINE_CHECK,
                "status": "completed",
                "conclusion": "success",
                "app": {"id": cli.gate.GITHUB_ACTIONS_INTEGRATION_ID},
            },
            {
                "id": 102,
                "name": cli.gate.EXTERNAL_CHECK,
                "status": "completed",
                "conclusion": "success",
                "app": {"id": APP_ID},
            },
        ]
    }
    sequence = [pending, success]
    calls = 0

    def gh(arguments):
        nonlocal calls
        if "/pulls/" in arguments[0]:
            return pull
        value = sequence[min(calls, len(sequence) - 1)]
        calls += 1
        return value

    clock = iter([0.0, 0.0, 1.0])
    cli.wait_checks(
        REPOSITORY,
        9,
        HEAD,
        BASE,
        CHECK_SHA,
        APP_ID,
        timeout_seconds=10,
        gh=gh,
        monotonic=lambda: next(clock),
        sleep=lambda _seconds: None,
    )
    check(calls == 2, "check polling reaches exact success")

    computing = json.loads(json.dumps(pull))
    computing["mergeable"] = None
    pull_sequence = [computing, pull]

    def transient_gh(arguments):
        if "/pulls/" in arguments[0]:
            return pull_sequence.pop(0) if pull_sequence else pull
        return success

    transient_clock = iter([0.0, 0.0])
    cli.wait_checks(
        REPOSITORY,
        9,
        HEAD,
        BASE,
        CHECK_SHA,
        APP_ID,
        timeout_seconds=10,
        gh=transient_gh,
        monotonic=lambda: next(transient_clock),
        sleep=lambda _seconds: None,
    )
    check(not pull_sequence, "transient test-merge calculation is retried")

    forged = {
        "check_runs": [
            {
                "name": cli.gate.EXTERNAL_CHECK,
                "status": "completed",
                "conclusion": "success",
                "app": {"id": APP_ID + 1},
            },
            success["check_runs"][0],
        ]
    }
    complete, failure, external_seen = cli.check_state(
        forged, app_id=APP_ID
    )
    check(not complete and failure is None, "same-name forged check ignored")
    check(not external_seen, "forged App is not an eligible external check")

    _, _, external_ids = cli.check_state(success, app_id=APP_ID)
    complete, failure, external_seen = cli.check_state(
        success,
        app_id=APP_ID,
        ignored_external_ids=external_ids,
    )
    check(
        not complete and failure is None and not external_seen,
        "pre-submission App check is ignored",
    )

    failed = {
        "check_runs": [
            success["check_runs"][0],
            {
                "id": 103,
                "name": cli.gate.EXTERNAL_CHECK,
                "status": "completed",
                "conclusion": "action_required",
                "app": {"id": APP_ID},
            },
        ]
    }

    def failed_gh(arguments):
        return pull if "/pulls/" in arguments[0] else failed

    rejects(
        "BLOCKED",
        lambda: cli.wait_checks(
            REPOSITORY,
            9,
            HEAD,
            BASE,
            CHECK_SHA,
            APP_ID,
            timeout_seconds=10,
            gh=failed_gh,
            monotonic=lambda: 0.0,
            sleep=lambda _seconds: None,
        ),
        "failed external check",
    )

    ticks = iter([0.0, 11.0])

    def pending_gh(arguments):
        return pull if "/pulls/" in arguments[0] else pending

    rejects(
        "UNAVAILABLE",
        lambda: cli.wait_checks(
            REPOSITORY,
            9,
            HEAD,
            BASE,
            CHECK_SHA,
            APP_ID,
            timeout_seconds=10,
            gh=pending_gh,
            monotonic=lambda: next(ticks),
            sleep=lambda _seconds: None,
        ),
        "check timeout",
    )

    stale_pull = json.loads(json.dumps(pull))
    stale_pull["base"]["sha"] = "d" * 40
    rejects(
        "BLOCKED",
        lambda: cli.wait_checks(
            REPOSITORY,
            9,
            HEAD,
            BASE,
            CHECK_SHA,
            APP_ID,
            timeout_seconds=10,
            gh=lambda arguments: (
                stale_pull if "/pulls/" in arguments[0] else pending
            ),
            monotonic=lambda: 0.0,
            sleep=lambda _seconds: None,
        ),
        "base drift invalidates pending result",
    )

    stale_merge = json.loads(json.dumps(pull))
    stale_merge["merge_commit_sha"] = "e" * 40
    rejects(
        "BLOCKED",
        lambda: cli.wait_checks(
            REPOSITORY,
            9,
            HEAD,
            BASE,
            CHECK_SHA,
            APP_ID,
            timeout_seconds=10,
            gh=lambda arguments: (
                stale_merge if "/pulls/" in arguments[0] else pending
            ),
            monotonic=lambda: 0.0,
            sleep=lambda _seconds: None,
        ),
        "test-merge drift invalidates pending result",
    )


def registry_phase() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-cli-registry-") as raw:
        root = Path(raw)
        key_file = root / "signing.key"
        write_key(key_file)
        target = root / "registry.json"
        cli.save_registry(
            {"version": 1, "repositories": [entry(key_file)]},
            target,
        )
        if cli.os.name != "nt":
            check(
                stat.S_IMODE(target.stat().st_mode) == 0o600,
                "registry mode",
            )
        loaded = cli.gate.load_registry(target)
        check(loaded["repositories"][0]["appId"] == APP_ID, "registry reload")


def gate_adoption_phase() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-cli-gate-adopt-") as raw:
        root = Path(raw)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "remote",
                "add",
                "origin",
                "https://github.com/hihol-labs/example.git",
            ],
            check=True,
        )
        contract = root / ".itd" / "VERIFICATION_CONTRACT.json"
        contract.parent.mkdir()
        contract.write_text(
            json.dumps(
                {
                    "version": 2,
                    "failClosed": "yes",
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
        key_file = root / "signing.key"
        write_key(key_file)
        registry_path = root / "gate-registry.json"
        args = cli.parser().parse_args(
            [
                "gate",
                "adopt",
                "--root",
                str(root),
                "--broker-url",
                "https://broker.example.test",
                "--app-id",
                str(APP_ID),
                "--scope",
                "organization",
                "--ruleset-id",
                "91",
                "--workflow-repository-id",
                str(WORKFLOW_REPOSITORY_ID),
                "--workflow-sha",
                WORKFLOW_SHA,
                "--provenance-key-id",
                "current",
                "--provenance-key-file",
                str(key_file),
                "--registry",
                str(registry_path),
            ]
        )
        protected = {
            "repository": REPOSITORY,
            "status": "PROTECTED",
            "drift": [],
            "itdVersion": "1.95.0",
            "broker": {"status": "ready"},
        }
        with mock.patch.object(
            cli.gate, "doctor_entry", return_value=protected
        ):
            result = args.handler(args)
        check(
            result["status"] == "PROTECTED"
            and registry_path.is_file(),
            "adopt registers only a fully enforceable gate",
        )
        registry_path.unlink()
        pending = dict(protected)
        pending["status"] = "UNVERIFIED"
        pending["drift"] = [
            ".itd/VERIFICATION_CONTRACT.json is not tracked",
            "protected base contract response is invalid",
        ]
        with mock.patch.object(
            cli.gate, "doctor_entry", return_value=pending
        ):
            rejects(
                "UNVERIFIED",
                lambda: args.handler(args),
                "adopt rejects a local-only bootstrap contract",
            )
        check(
            not registry_path.exists(),
            "pending bootstrap leaves no registry entry",
        )
        blocked = dict(protected)
        blocked["status"] = "UNVERIFIED"
        blocked["drift"] = ["ruleset: UNVERIFIED: expected App differs"]
        with mock.patch.object(
            cli.gate, "doctor_entry", return_value=blocked
        ):
            rejects(
                "UNVERIFIED",
                lambda: args.handler(args),
                "adopt rejects a non-enforceable GitHub gate",
            )
        check(
            not registry_path.exists(),
            "failed gate adoption leaves no registry entry",
        )


def doctor_inventory_phase() -> None:
    registry = {
        "version": 1,
        "repositories": [
            {
                **entry(Path("/tmp/itd-maker.key")),
                "rulesetScope": "organization",
            }
        ],
    }
    args = type(
        "Args",
        (),
        {"registry": None, "all": True, "repository": None},
    )()
    protected = {
        "repository": REPOSITORY,
        "status": "PROTECTED",
        "drift": [],
        "itdVersion": "1.95.0",
        "broker": {"status": "ready"},
    }
    with (
        mock.patch.object(
            cli.gate, "load_registry", return_value=registry
        ),
        mock.patch.object(
            cli.gate, "doctor_entry", return_value=protected
        ),
        mock.patch.object(
            cli,
            "organization_repositories",
            return_value=[
                REPOSITORY,
                "hihol-labs/unadopted",
            ],
        ),
    ):
        result = cli.doctor(args)
    check(
        result["status"] == "UNVERIFIED"
        and result["protected"] == 1
        and result["total"] == 2,
        "doctor all discovers unregistered organization repositories",
    )
    check(
        result["repositories"][1]["repository"]
        == "hihol-labs/unadopted",
        "doctor inventory identifies the exact unadopted repository",
    )


def enrollment_observation_phase() -> None:
    with tempfile.TemporaryDirectory(
        prefix="itd-cli-enrollment-"
    ) as raw:
        output = Path(raw) / "enrollment.json"
        ruleset = cli.gate.ruleset_payload(
            APP_ID,
            scope="organization",
            workflow_repository_id=WORKFLOW_REPOSITORY_ID,
            workflow_sha=WORKFLOW_SHA,
        )
        ruleset["id"] = 91
        repository_value = {"default_branch": "main"}
        workflow_repository = {
            "id": WORKFLOW_REPOSITORY_ID,
            "full_name": cli.gate.MACHINE_WORKFLOW_REPOSITORY,
            "visibility": "public",
        }
        workflow_commit = {"sha": WORKFLOW_SHA}
        app = {
            "id": APP_ID,
            "slug": "itd-review-gate",
            "client_id": "Iv1fixtureclient",
            "node_id": "MDM6QXBwNDI0MjQy",
            "owner": {"login": "hihol-labs"},
            "permissions": {
                "checks": "write",
                "contents": "read",
                "pull_requests": "read",
                "metadata": "read",
            },
            "events": ["pull_request", "merge_group"],
        }
        args = cli.parser().parse_args(
            [
                "gate",
                "enrollment",
                "--repository",
                REPOSITORY,
                "--scope",
                "organization",
                "--ruleset-id",
                "91",
                "--app-id",
                str(APP_ID),
                "--app-slug",
                "itd-review-gate",
                "--workflow-repository-id",
                str(WORKFLOW_REPOSITORY_ID),
                "--workflow-sha",
                WORKFLOW_SHA,
                "--output",
                str(output),
            ]
        )

        def gh_for(
            selected_app,
            *,
            selected_workflow_repository=workflow_repository,
            selected_workflow_commit=workflow_commit,
        ):
            def gh(arguments):
                endpoint = arguments[0]
                if endpoint == f"repos/{REPOSITORY}":
                    return repository_value
                if endpoint == "apps/itd-review-gate":
                    return selected_app
                if endpoint == (
                    f"repos/{cli.gate.MACHINE_WORKFLOW_REPOSITORY}"
                ):
                    return selected_workflow_repository
                if endpoint.endswith(f"/commits/{WORKFLOW_SHA}"):
                    return selected_workflow_commit
                raise AssertionError(f"unexpected endpoint: {endpoint}")

            return gh

        with (
            mock.patch.object(
                cli.gate, "fetch_ruleset", return_value=ruleset
            ),
            mock.patch.object(
                cli.gate, "gh_json", side_effect=gh_for(app)
            ),
        ):
            preview = args.handler(args)
            check(
                preview["status"] == "PREVIEW"
                and not output.exists(),
                "enrollment observation preview is read-only",
            )
            args.apply = True
            observed = args.handler(args)
        value = json.loads(output.read_text(encoding="utf-8"))
        check(
            observed["status"] == "OBSERVED"
            and value["requiredStatusChecks"]["externalReview"][
                "integrationId"
            ]
            == APP_ID,
            "enrollment receipt binds the exact App source",
        )
        check(
            value["requiredStatusChecks"]["machineOracle"][
                "integrationId"
            ]
            == cli.gate.GITHUB_ACTIONS_INTEGRATION_ID
            and value["requiredStatusChecks"]["machineOracle"][
                "workflowSha"
            ]
            == WORKFLOW_SHA
            and value["bypassActors"] == [],
            "enrollment receipt binds machine source and no bypass",
        )
        bad_app = dict(app)
        bad_app["permissions"] = {
            **app["permissions"],
            "checks": "read",
        }
        with (
            mock.patch.object(
                cli.gate, "fetch_ruleset", return_value=ruleset
            ),
            mock.patch.object(
                cli.gate,
                "gh_json",
                side_effect=gh_for(bad_app),
            ),
        ):
            rejects(
                "UNVERIFIED",
                lambda: args.handler(args),
                "enrollment rejects App permission drift",
            )
        extra_permission_app = dict(app)
        extra_permission_app["permissions"] = {
            **app["permissions"],
            "issues": "write",
        }
        with (
            mock.patch.object(
                cli.gate, "fetch_ruleset", return_value=ruleset
            ),
            mock.patch.object(
                cli.gate,
                "gh_json",
                side_effect=gh_for(extra_permission_app),
            ),
        ):
            rejects(
                "UNVERIFIED",
                lambda: args.handler(args),
                "enrollment rejects an extra App permission",
            )
        extra_event_app = dict(app)
        extra_event_app["events"] = [
            "pull_request",
            "merge_group",
            "push",
        ]
        with (
            mock.patch.object(
                cli.gate, "fetch_ruleset", return_value=ruleset
            ),
            mock.patch.object(
                cli.gate,
                "gh_json",
                side_effect=gh_for(extra_event_app),
            ),
        ):
            rejects(
                "UNVERIFIED",
                lambda: args.handler(args),
                "enrollment rejects an extra App event",
            )
        wrong_workflow_repository = {
            **workflow_repository,
            "id": WORKFLOW_REPOSITORY_ID + 1,
        }
        with (
            mock.patch.object(
                cli.gate, "fetch_ruleset", return_value=ruleset
            ),
            mock.patch.object(
                cli.gate,
                "gh_json",
                side_effect=gh_for(
                    app,
                    selected_workflow_repository=wrong_workflow_repository,
                ),
            ),
        ):
            rejects(
                "UNVERIFIED",
                lambda: args.handler(args),
                "enrollment rejects a mismatched workflow repository",
            )
        wrong_workflow_commit = {"sha": "2" * 40}
        with (
            mock.patch.object(
                cli.gate, "fetch_ruleset", return_value=ruleset
            ),
            mock.patch.object(
                cli.gate,
                "gh_json",
                side_effect=gh_for(
                    app,
                    selected_workflow_commit=wrong_workflow_commit,
                ),
            ),
        ):
            rejects(
                "UNVERIFIED",
                lambda: args.handler(args),
                "enrollment rejects a mismatched workflow commit",
            )


def keygen_phase() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-cli-keygen-") as raw:
        key_file = Path(raw) / "maker.key"
        args = cli.parser().parse_args(
            [
                "gate",
                "keygen",
                "--repository",
                REPOSITORY,
                "--key-id",
                "sol-maker",
                "--maker-vendor",
                "openai",
                "--maker-model",
                "gpt-5.6-sol",
                "--issuer-principal",
                "windows-or-wsl-user",
                "--output",
                str(key_file),
            ]
        )
        generated = args.handler(args)
        private = cli.gate.read_provenance_private_key(key_file)
        check(
            generated["status"] == "GENERATED"
            and len(private) == 32,
            "host-protected Ed25519 key generated",
        )
        if cli.os.name != "nt":
            check(
                stat.S_IMODE(key_file.stat().st_mode) == 0o600,
                "POSIX provenance key mode",
            )
        key_entry = entry(key_file)
        key_entry["provenanceKeyId"] = "sol-maker"
        signed = cli.build_provenance(
            key_entry,
            {
                "number": 9,
                "headRefOid": HEAD,
                "baseRefOid": BASE,
            },
            "openai",
            "gpt-5.6-sol",
            "maker-session",
        )
        public_raw = base64.urlsafe_b64decode(
            generated["publicKeyRecord"]["publicKey"] + "="
        )
        unsigned = cli.gate.provenance_payload(signed)
        Ed25519PublicKey.from_public_bytes(public_raw).verify(
            base64.urlsafe_b64decode(signed["signature"] + "=="),
            cli.gate.canonical_json(unsigned),
        )
        check(
            unsigned["headSha"] == HEAD,
            "generated public record verifies exact provenance",
        )
        rejects(
            "BLOCKED",
            lambda: args.handler(args),
            "key generation cannot overwrite private material",
        )


def remote_phase() -> None:
    check(
        cli.github_repository_from_remote(
            "https://github.com/hihol-labs/example.git"
        )
        == REPOSITORY,
        "HTTPS origin normalized",
    )
    check(
        cli.github_repository_from_remote(
            "git@github.com:hihol-labs/example.git"
        )
        == REPOSITORY,
        "SSH origin normalized",
    )
    rejects(
        "UNVERIFIED",
        lambda: cli.github_repository_from_remote(
            "https://attacker.example.test/hihol-labs/example.git"
        ),
        "non-GitHub origin rejected",
    )
    with tempfile.TemporaryDirectory(prefix="itd-cli-origin-") as raw:
        root = Path(raw)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "remote",
                "add",
                "origin",
                "https://github.com/hihol-labs/example.git",
            ],
            check=True,
        )
        cli.require_registered_origin(root, REPOSITORY)
        rejects(
            "BLOCKED",
            lambda: cli.require_registered_origin(
                root, "hihol-labs/other"
            ),
            "registry/remote mismatch rejected",
        )

    response = {
        "number": 9,
        "headRefName": "topic",
        "headRefOid": HEAD,
        "baseRefOid": BASE,
        "url": "https://github.com/hihol-labs/example/pull/9",
        "isDraft": True,
        "state": "OPEN",
    }
    completed = type("Completed", (), {"returncode": 0})()
    with (
        mock.patch.object(cli, "git", return_value="topic"),
        mock.patch.object(
            cli, "run_json", return_value=(response, completed)
        ) as runner,
    ):
        cli.pr_view(Path("."), REPOSITORY)
    arguments = runner.call_args.args[0]
    check(
        arguments[2] == "view"
        and arguments[3] == "topic"
        and arguments[arguments.index("--repo") + 1] == REPOSITORY,
        "PR lookup explicitly binds branch and repository",
    )
    missing = type(
        "Completed", (), {
            "returncode": 1,
            "stdout": b"",
            "stderr": b'no pull requests found for branch "topic"\n',
        }
    )()
    with (
        mock.patch.object(cli, "git", return_value="topic"),
        mock.patch.object(cli, "run_json", return_value=(None, missing)),
    ):
        check(
            cli.pr_view(Path("."), REPOSITORY) is None,
            "exact no-PR result permits Draft creation",
        )
    for label, stderr in (
        (
            "different branch",
            b'no pull requests found for branch "other"\n',
        ),
        (
            "surrounding whitespace",
            b' no pull requests found for branch "topic"\n',
        ),
    ):
        substituted = type(
            "Completed", (), {
                "returncode": 1,
                "stdout": b"",
                "stderr": stderr,
            }
        )()
        with (
            mock.patch.object(cli, "git", return_value="topic"),
            mock.patch.object(
                cli, "run_json", return_value=(None, substituted)
            ),
        ):
            rejects(
                "UNAVAILABLE",
                lambda: cli.pr_view(Path("."), REPOSITORY),
                f"{label} cannot become absent PR",
            )
    unavailable = type(
        "Completed", (), {
            "returncode": 1,
            "stdout": b"",
            "stderr": b"TLS handshake timeout\n",
        }
    )()
    with (
        mock.patch.object(cli, "git", return_value="topic"),
        mock.patch.object(cli, "run_json", return_value=(None, unavailable)),
    ):
        rejects(
            "UNAVAILABLE",
            lambda: cli.pr_view(Path("."), REPOSITORY),
            "failed PR lookup never becomes absent PR",
        )
    malformed = type(
        "Completed", (), {
            "returncode": 1,
            "stdout": b"",
            "stderr": b"\xff",
        }
    )()
    with (
        mock.patch.object(cli, "git", return_value="topic"),
        mock.patch.object(cli, "run_json", return_value=(None, malformed)),
    ):
        rejects(
            "UNVERIFIED",
            lambda: cli.pr_view(Path("."), REPOSITORY),
            "malformed PR lookup error fails closed",
        )
    ready = dict(response, isDraft=False)
    with (
        mock.patch.object(cli, "pr_view", return_value=ready),
        mock.patch.object(cli, "run") as push,
    ):
        rejects(
            "BLOCKED",
            lambda: cli.create_draft_pr(
                Path("."), REPOSITORY, Path("."), "openai", "model", "session"
            ),
            "ready PR rejected",
        )
        check(not push.called, "ready PR rejected before push")

    updated_head = "e" * 40
    updated_response = dict(response, headRefOid=updated_head)
    with (
        mock.patch.object(
            cli, "pr_view", side_effect=[response, updated_response]
        ),
        mock.patch.object(
            cli, "git", side_effect=["topic", updated_head]
        ),
        mock.patch.object(cli, "run") as push,
    ):
        value = cli.create_draft_pr(
            Path("."), REPOSITORY, Path("receipt.json"),
            "openai", "model", "session", 600,
        )
        command = push.call_args.args[0]
        check(value == updated_response, "updated Draft PR returned")
        check(
            "--force-with-lease=refs/heads/topic:" + HEAD in command
            and "HEAD:refs/heads/topic" in command,
            "existing Draft update uses exact force-with-lease",
        )
        check(
            push.call_args.kwargs["env"]["ITD_GUARDED_PR_PUSH"] == "1",
            "Draft update retains guarded push environment",
        )
        check(
            push.call_args.kwargs["timeout"] == 600,
            "Draft update carries the bounded CLI timeout through pre-push",
        )

    check(
        cli.guarded_push_timeout(1200) == 1200
        and cli.guarded_push_timeout(30) == 300
        and cli.guarded_push_timeout(9999) == 3600,
        "guarded push timeout is bounded",
    )

    with (
        mock.patch.object(cli, "pr_view", side_effect=[response, response]),
        mock.patch.object(cli, "git", side_effect=["topic", HEAD]),
        mock.patch.object(cli, "run") as push,
    ):
        value = cli.create_draft_pr(
            Path("."), REPOSITORY, Path("receipt.json"),
            "openai", "model", "session",
        )
        check(value == response, "unchanged Draft PR returned")
        check(not push.called, "up-to-date Draft skips empty-stream push")

    create_command = [
        "gh", "pr", "create", "--repo", REPOSITORY, "--draft", "--fill",
    ]
    with (
        mock.patch.object(cli, "pr_view", side_effect=[None, None, response]),
        mock.patch.object(cli, "git", side_effect=["topic", HEAD]),
        mock.patch.object(cli, "remote_branch_head", return_value=HEAD),
        mock.patch.object(cli, "run") as calls,
    ):
        value = cli.create_draft_pr(
            Path("."), REPOSITORY, Path("receipt.json"),
            "openai", "model", "session",
        )
        commands = [call.args[0] for call in calls.call_args_list]
        check(value == response, "absent Draft PR created after synced remote")
        check(
            commands == [create_command],
            "synced remote without PR skips the empty-stream push",
        )

    for label, remote in (
        ("absent remote branch", None),
        ("stale remote branch", "d" * 40),
    ):
        with (
            mock.patch.object(
                cli, "pr_view", side_effect=[None, None, response]
            ),
            mock.patch.object(cli, "git", side_effect=["topic", HEAD]),
            mock.patch.object(cli, "remote_branch_head", return_value=remote),
            mock.patch.object(cli, "run") as calls,
        ):
            cli.create_draft_pr(
                Path("."), REPOSITORY, Path("receipt.json"),
                "openai", "model", "session",
            )
            commands = [call.args[0] for call in calls.call_args_list]
            check(
                commands == [
                    ["git", "push", "--set-upstream", "origin", "HEAD"],
                    create_command,
                ],
                f"{label} without PR still pushes before creation",
            )
            check(
                calls.call_args_list[0].kwargs["env"]["ITD_GUARDED_PR_PUSH"]
                == "1",
                f"{label} push stays inside the guarded environment",
            )

    listing = type(
        "Completed", (), {"returncode": 0, "stdout": b"", "stderr": b""}
    )()
    with mock.patch.object(cli, "run", return_value=listing) as runner:
        check(
            cli.remote_branch_head(Path("."), "topic") is None,
            "missing remote branch reads as absent",
        )
        check(
            runner.call_args.args[0][-2:] == ["origin", "refs/heads/topic"],
            "remote head listing binds the exact branch ref",
        )
    listed = type(
        "Completed", (), {
            "returncode": 0,
            "stdout": (HEAD.upper() + "\trefs/heads/topic\n").encode("utf-8"),
            "stderr": b"",
        }
    )()
    with mock.patch.object(cli, "run", return_value=listed):
        check(
            cli.remote_branch_head(Path("."), "topic") == HEAD,
            "remote head is normalized to lowercase",
        )
    for label, stdout in (
        ("unrelated ref", b"a" * 40 + b"\trefs/heads/other\n"),
        ("ambiguous listing", (HEAD + "\trefs/heads/topic\n") .encode() * 2),
        ("invalid object name", b"zz\trefs/heads/topic\n"),
        ("missing ref field", HEAD.encode("utf-8") + b"\n"),
    ):
        broken = type(
            "Completed", (), {
                "returncode": 0, "stdout": stdout, "stderr": b"",
            }
        )()
        with mock.patch.object(cli, "run", return_value=broken):
            rejects(
                "UNVERIFIED",
                lambda: cli.remote_branch_head(Path("."), "topic"),
                f"{label} never reads as a remote head",
            )


def parser_phase() -> None:
    parser = cli.parser()
    args = parser.parse_args(
        [
            "pr",
            "create",
            "--maker-vendor",
            "openai",
            "--maker-model",
            "gpt-5.6-sol",
            "--maker-session",
            "session",
        ]
    )
    check(args.handler is cli.pr_create, "pr create route")
    args = parser.parse_args(
        [
            "gate",
            "doctor",
            "--all",
        ]
    )
    check(args.handler is cli.doctor and args.all, "doctor all route")
    args = parser.parse_args(
        [
            "gate",
            "adopt",
            "--broker-url",
            "https://broker.example.test",
            "--app-id",
            str(APP_ID),
            "--scope",
            "organization",
            "--ruleset-id",
            "91",
            "--workflow-repository-id",
            str(WORKFLOW_REPOSITORY_ID),
            "--workflow-sha",
            WORKFLOW_SHA,
            "--provenance-key-id",
            "current",
            "--provenance-key-file",
            "maker.key",
        ]
    )
    check(args.handler is cli.adopt_gate, "gate adopt route")
    try:
        cli.positive_int("0")
    except cli.argparse.ArgumentTypeError:
        check(True, "zero ruleset id is rejected by the CLI")
    else:
        check(False, "zero ruleset id is rejected by the CLI")
    rejects(
        "UNVERIFIED",
        lambda: cli.ruleset_endpoint(REPOSITORY, "organization", 0),
        "zero ruleset id cannot select the collection endpoint",
    )
    args = parser.parse_args(
        [
            "gate",
            "enrollment",
            "--repository",
            REPOSITORY,
            "--scope",
            "organization",
            "--ruleset-id",
            "91",
            "--app-id",
            str(APP_ID),
            "--app-slug",
            "itd-review-gate",
            "--workflow-repository-id",
            str(WORKFLOW_REPOSITORY_ID),
            "--workflow-sha",
            WORKFLOW_SHA,
            "--output",
            "enrollment.json",
        ]
    )
    check(args.handler is cli.observe_enrollment, "enrollment route")


def main() -> int:
    provenance_phase()
    check_phase()
    registry_phase()
    gate_adoption_phase()
    doctor_inventory_phase()
    enrollment_observation_phase()
    keygen_phase()
    remote_phase()
    parser_phase()
    print(json.dumps({"checks": CHECKS, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
