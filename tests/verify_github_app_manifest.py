#!/usr/bin/env python3
"""Focused checks for the GitHub App manifest bootstrap boundary."""
from __future__ import annotations

import importlib.util
import io
import json
import stat
import sys
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "itd_github_app_manifest.py"
spec = importlib.util.spec_from_file_location(
    "itd_github_app_manifest_test", MODULE
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
CHECKS = 0


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
    except module.ManifestError:
        return
    raise AssertionError(label)


def conversion_fixture() -> dict:
    client_secret_key = "client" + "_secret"
    webhook_secret_key = "webhook" + "_secret"
    return {
        "id": 424242,
        "client_id": "Iv1.fixtureclient",
        client_secret_key: "discard" + "-me",
        "slug": "itd-review-gate",
        "node_id": "MDM6QXBwNDI0MjQy",
        "owner": {"login": "example-owner"},
        "pem": (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "fixture-not-used-for-signing\n"
            "-----END RSA PRIVATE KEY-----\n"
        ),
        webhook_secret_key: "w" * 40,
    }


class FakeResponse:
    status = 201

    def __init__(self, value: dict) -> None:
        self._payload = json.dumps(value).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return io.BytesIO(self._payload).read(limit)


def main() -> int:
    profiles = module.deployment_profiles()
    check(
        set(profiles) == {
            "version", "roles", "reviewerAppPermissions",
            "deploymentProfiles", "protectionProfiles",
        },
        "deployment profile contract fields are not closed",
    )
    check(
        profiles["roles"]["independentReviewer"]["mustDifferFrom"]
        == ["maker"]
        and set(profiles["roles"]["maintainer"]["mayOverlapWith"])
        == {"maker", "deployer"}
        and set(profiles["roles"]["deployer"]["mayOverlapWith"])
        == {"maker", "maintainer"},
        "role separation forbids a legitimate owner/merger/deployer overlap",
    )
    check(
        set(profiles["deploymentProfiles"])
        == {"local-submission", "self-hosted-app", "managed-app"}
        and profiles["deploymentProfiles"]["local-submission"]["appRequired"]
        is False
        and profiles["deploymentProfiles"]["self-hosted-app"]["visibility"]
        == ["private", "public"]
        and profiles["deploymentProfiles"]["managed-app"]["visibility"]
        == ["public"],
        "portable deployment profiles are incomplete",
    )
    check(
        profiles["protectionProfiles"]["organization-workflow"]["claim"]
        == "PROTECTED"
        and all(
            row["claim"] != "PROTECTED"
            for name, row in profiles["protectionProfiles"].items()
            if name != "organization-workflow"
        ),
        "a weaker protection profile can overclaim PROTECTED",
    )
    value = module.manifest(
        name="ITD Independent Review Gate",
        broker_url="https://review.example.test",
        redirect_url="http://127.0.0.1:49152/callback",
    )
    check(
        value["public"] is False
        and value["hook_attributes"]["url"]
        == "https://review.example.test/webhook",
        "manifest is private and binds the exact broker webhook",
    )
    public_value = module.manifest(
        name="ITD Independent Review Gate",
        broker_url="https://review.example.test",
        redirect_url="http://127.0.0.1:49152/callback",
        visibility="public",
    )
    check(public_value["public"] is True,
          "managed/public App visibility is not represented exactly")
    check(
        module.resolve_app_visibility("self-hosted-app", None) == "private"
        and module.resolve_app_visibility("self-hosted-app", "public")
        == "public"
        and module.resolve_app_visibility("managed-app", None) == "public",
        "deployment profile does not resolve App visibility fail-closed",
    )
    rejects(
        lambda: module.resolve_app_visibility("managed-app", "private"),
        "managed App accepted private visibility",
    )
    check(
        value["default_permissions"]
        == {
            "checks": "write",
            "contents": "read",
            "metadata": "read",
            "pull_requests": "read",
        },
        "manifest permissions are least-privilege exact",
    )
    check(
        profiles["reviewerAppPermissions"] == value["default_permissions"]
        and not any(
            value["default_permissions"].get(permission) == "write"
            for permission in ("contents", "pull_requests", "deployments")
        ),
        "reviewer App can mutate code, merge, or deploy",
    )
    check(
        value["default_events"] == ["pull_request", "merge_group"],
        "manifest subscribes only to required events",
    )
    check(
        issubclass(module.CALLBACK_SERVER_CLASS, module.HTTPServer)
        and module.CALLBACK_SERVER_CLASS is not module.HTTPServer,
        "manifest callback is serialized by a bounded single-thread server",
    )
    connection = mock.Mock()
    server = object.__new__(module.CALLBACK_SERVER_CLASS)
    with mock.patch.object(
        module.HTTPServer,
        "get_request",
        return_value=(connection, ("127.0.0.1", 49152)),
    ):
        accepted, address = module.CALLBACK_SERVER_CLASS.get_request(server)
    check(
        accepted is connection and address == ("127.0.0.1", 49152),
        "bounded callback server preserves the accepted connection",
    )
    check(
        connection.settimeout.call_args
        == mock.call(module.CALLBACK_CONNECTION_TIMEOUT_SECONDS),
        "accepted callback connection receives a read timeout",
    )
    rejects(
        lambda: module.manifest(
            name="ITD",
            broker_url="http://review.example.test",
            redirect_url="http://127.0.0.1:49152/callback",
        ),
        "non-TLS broker URL rejected",
    )
    rejects(
        lambda: module.manifest(
            name="ITD",
            broker_url="https://review.example.test",
            redirect_url="https://attacker.example.test/callback",
        ),
        "non-loopback callback rejected",
    )
    rejects(
        lambda: module.organization("hihol labs"),
        "invalid organization rejected in preview and apply paths",
    )
    rejects(
        lambda: module.callback_code("code", "expected-state"),
        "malformed callback query is rejected without escaping the handler",
    )

    requests = []

    def opener(request, timeout):
        requests.append((request, timeout))
        return FakeResponse(conversion_fixture())

    converted = module.conversion("a" * 40, opener=opener)
    check(
        converted["id"] == 424242
        and requests[0][1] == 30
        and requests[0][0].get_header("X-github-api-version")
        == "2026-03-10",
        "conversion uses the bounded official GitHub manifest endpoint",
    )
    rejects(
        lambda: module.conversion("../bad", opener=opener),
        "invalid conversion code rejected before network access",
    )

    def persistence_failure(_value, _output):
        raise OSError("fixture disk failure")

    rejects(
        lambda: module.convert_and_persist(
            "a" * 40,
            Path("/outside-repository"),
            converter=lambda _code: conversion_fixture(),
            persister=persistence_failure,
        ),
        "credential persistence I/O failure is normalized for serve propagation",
    )
    rejects(
        lambda: module.convert_and_persist(
            "a" * 40,
            Path("/outside-repository"),
            converter=lambda _code: conversion_fixture(),
            expected_owner="different-organization",
        ),
        "converted App owner must equal the requested organization",
    )

    with tempfile.TemporaryDirectory(
        prefix="itd-app-manifest-"
    ) as raw:
        output = Path(raw) / "credentials"
        result = module.persist_conversion(
            conversion_fixture(), output
        )
        registration = json.loads(
            (output / "github-app-registration.json").read_text(
                encoding="utf-8"
            )
        )
        check(
            result["status"] == "CREATED"
            and result["clientSecretRetained"] is False,
            "conversion persists only broker-required material",
        )
        check(
            set(registration)
            == {
                "version",
                "id",
                "clientId",
                "slug",
                "nodeId",
                "owner",
            }
            and "client_secret" not in json.dumps(registration),
            "non-secret registration record excludes generated secrets",
        )
        if module.os.name != "nt":
            check(
                all(
                    stat.S_IMODE(path.stat().st_mode) == 0o600
                    for path in output.iterdir()
                )
                and stat.S_IMODE(output.stat().st_mode) == 0o700,
                "manifest directory and outputs use private file modes",
            )
        rejects(
            lambda: module.persist_conversion(
                conversion_fixture(), output
            ),
            "existing App material cannot be overwritten",
        )

    organization_action = module.registration_action(
        "example-owner", "organization", "manifest-state"
    )
    user_action = module.registration_action(
        "example-owner", "user", "manifest-state"
    )
    check(
        organization_action.startswith(
            "https://github.com/organizations/example-owner/settings/apps/new?"
        )
        and user_action.startswith("https://github.com/settings/apps/new?")
        and "manifest-state" in organization_action
        and "manifest-state" in user_action,
        "manifest registration is not portable across user/organization owners",
    )
    parsed_legacy = module.parser().parse_args([
        "--organization", "example-owner",
        "--broker-url", "https://review.example.test",
        "--output-dir", "/secure/itd-review-app",
        "--plan",
    ])
    check(
        module.requested_owner(parsed_legacy)
        == ("example-owner", "organization"),
        "legacy organization bootstrap no longer maps to self-hosted ownership",
    )
    with tempfile.TemporaryDirectory(prefix="itd-app-preview-") as preview_raw:
        stdout = io.StringIO()
        with mock.patch.object(module.sys, "stdout", stdout):
            preview_rc = module.main([
                "--owner", "example-owner", "--account-type", "user",
                "--profile", "managed-app",
                "--broker-url", "https://review.example.test",
                "--output-dir", str(Path(preview_raw) / "credentials"),
                "--plan",
            ])
        preview = json.loads(stdout.getvalue())
    check(
        preview_rc == 0
        and preview["owner"] == "example-owner"
        and preview["accountType"] == "user"
        and preview["profile"] == "managed-app"
        and preview["visibility"] == "public"
        and preview["manifest"]["public"] is True,
        "managed user-owned manifest preview is not profile-bound",
    )
    page = module.registration_page(
        organization_action,
        value,
    ).decode("utf-8")
    check(
        'method="post"' in page
        and 'name="manifest"' in page
        and "sk-proj-" not in page,
        "registration page uses the official manifest POST without secrets",
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
