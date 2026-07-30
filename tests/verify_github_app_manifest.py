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
    return {
        "id": 424242,
        "client_id": "Iv1.fixtureclient",
        "client_secret": "discard-me",
        "slug": "itd-review-gate",
        "node_id": "MDM6QXBwNDI0MjQy",
        "owner": {"login": "hihol-labs"},
        "pem": (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "fixture-not-used-for-signing\n"
            "-----END RSA PRIVATE KEY-----\n"
        ),
        "webhook_secret": "w" * 40,
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
        value["default_events"] == ["pull_request", "merge_group"],
        "manifest subscribes only to required events",
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

    page = module.registration_page(
        "https://github.com/organizations/hihol-labs/settings/apps/new",
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
