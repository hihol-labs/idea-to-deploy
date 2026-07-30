#!/usr/bin/env python3
"""HTTP/runtime regressions for the fail-closed central review service."""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import http.client
import json
import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.review_broker import server  # noqa: E402

core = server.core
CHECKS = 0
REPOSITORY = "hihol-labs/server-fixture"
HEAD = "a" * 40
BASE = "b" * 40
INSTALLATION_ID = 73
APP_ID = 424242
CLIENT_ID = "Iv1_fixture-client"
PRIVATE_KEY = Ed25519PrivateKey.generate()
PUBLIC_KEY = PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)


def check(value: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not value:
        raise AssertionError(label)


def expect_error(status: str, fn, label: str) -> None:
    global CHECKS
    CHECKS += 1
    try:
        fn()
    except core.BrokerError as exc:
        if exc.status != status:
            raise AssertionError(
                f"{label}: {exc.status} != {status}: {exc.reason}"
            ) from exc
    else:
        raise AssertionError(f"{label}: expected BrokerError")


def key_record() -> dict[str, Any]:
    return {
        "repository": REPOSITORY,
        "keyId": "maker-key",
        "authorizedMakerVendor": "openai",
        "authorizedMakerModel": "gpt-5.6-sol",
        "publicKey": core.b64url(PUBLIC_KEY),
        "issuerPrincipal": "windows-user-dmitry",
        "status": "active",
    }


class FakeBroker:
    def __init__(self) -> None:
        self.calls: list[core.Coordinates] = []
        self.error: core.BrokerError | None = None

    def process(self, coordinates: core.Coordinates) -> dict[str, Any]:
        self.calls.append(coordinates)
        if self.error is not None:
            raise self.error
        return {
            "status": "PASSED",
            "conclusion": "success",
            "checkRunId": 101,
        }

    def prepare_merge_group(self, coordinates: core.Coordinates) -> bool:
        del coordinates
        raise core.BrokerError(
            "UNVERIFIED", "merge fixture has no associated pull requests"
        )

    def prepare_waiting_merge_groups(self, repository: str) -> int:
        del repository
        return 0

    def recover_pending_publications(self) -> int:
        return 0


def pull_payload() -> dict[str, Any]:
    return {
        "action": "synchronize",
        "installation": {"id": INSTALLATION_ID},
        "repository": {"full_name": REPOSITORY},
        "number": 9,
        "pull_request": {
            "head": {
                "sha": HEAD,
                "repo": {"full_name": REPOSITORY},
            },
            "base": {
                "sha": BASE,
                "repo": {"full_name": REPOSITORY},
            },
        },
    }


def provenance_payload(nonce: str = "n" * 24) -> dict[str, Any]:
    return core.sign_provenance(
        {
            "repository": REPOSITORY,
            "pullRequest": 9,
            "headSha": HEAD,
            "baseSha": BASE,
            "makerVendor": "openai",
            "makerModel": "gpt-5.6-sol",
            "makerSession": "maker-session",
            "issuedAt": core.now_iso(),
            "nonce": nonce,
            "keyId": "maker-key",
        },
        PRIVATE_KEY,
    )


def signature(body: bytes, shared_material: bytes) -> str:
    return (
        "sha256="
        + hmac.new(shared_material, body, hashlib.sha256).hexdigest()
    )


def request(
    port: int,
    method: str,
    path: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        raw = response.read()
        value = json.loads(raw.decode("utf-8"))
        response_headers = {
            name.lower(): header_value
            for name, header_value in response.getheaders()
        }
        return response.status, value, response_headers
    finally:
        connection.close()


def webhook_headers(
    body: bytes,
    shared_material: bytes,
    delivery: str = "delivery-0001",
    event: str = "pull_request",
) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": signature(body, shared_material),
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": delivery,
    }


@contextlib.contextmanager
def running_server():
    policy = core.load_policy()
    keyring = {"maker-key": key_record()}
    store = core.BrokerStore(
        ":memory:", policy=policy, provenance_keyring=keyring
    )
    fake = FakeBroker()
    shared_material = b"webhook-fixture-material"
    runtime = server.BrokerRuntime(
        policy, store, fake, shared_material, keyring
    )
    server.BrokerHandler.runtime = runtime
    httpd = server.BoundedThreadingHTTPServer(
        ("127.0.0.1", 0),
        server.BrokerHandler,
        max_handlers=policy["service"]["maxRequestHandlers"],
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    runtime.worker.start()
    thread.start()
    try:
        yield httpd.server_address[1], runtime, fake, shared_material
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)
        runtime.close()


def wait_for_calls(fake: FakeBroker, count: int) -> None:
    deadline = time.monotonic() + 3
    while len(fake.calls) < count and time.monotonic() < deadline:
        time.sleep(0.01)
    check(len(fake.calls) == count, f"worker processed {count} jobs")


def http_phase() -> None:
    with running_server() as (port, runtime, fake, shared_material):
        status, value, headers = request(port, "GET", "/healthz")
        check(status == 200 and value == {"status": "ok"}, "liveness")
        check(headers.get("cache-control") == "no-store", "no-store response")
        status, value, _ = request(port, "GET", "/readyz")
        check(status == 200 and value["status"] == "ready", "readiness")
        check("budget" in value, "readiness includes budget")
        status, value, _ = request(port, "GET", "/missing")
        check(status == 404 and value["status"] == "not_found", "GET 404")

        body = core.canonical_json(pull_payload())
        headers = webhook_headers(body, shared_material)
        status, value, _ = request(port, "POST", "/webhook", body, headers)
        check(
            status == 202 and value["status"] == "waiting_for_provenance",
            "PR waits for verified maker provenance",
        )
        time.sleep(0.05)
        check(fake.calls == [], "webhook alone cannot dispatch reviewer")

        provenance = core.canonical_json(provenance_payload())
        status, value, _ = request(
            port,
            "POST",
            "/provenance",
            provenance,
            {"Content-Type": "application/json"},
        )
        check(status == 202 and value["status"] == "queued", "provenance queues")
        wait_for_calls(fake, 1)
        check(fake.calls[0].head_sha == HEAD, "worker receives exact head")

        status, value, _ = request(port, "POST", "/webhook", body, headers)
        check(status == 202 and value["status"] == "duplicate", "body replay")
        status, value, _ = request(
            port,
            "POST",
            "/provenance",
            provenance,
            {"Content-Type": "application/json"},
        )
        check(status == 422 and value["status"] == "UNVERIFIED", "nonce replay rejected")

        forged = dict(headers)
        forged["X-Hub-Signature-256"] = "sha256=" + "0" * 64
        status, value, _ = request(port, "POST", "/webhook", body, forged)
        check(status == 401 and value["status"] == "UNVERIFIED", "forged HMAC is 401")

        malformed = b"{"
        status, value, _ = request(
            port,
            "POST",
            "/webhook",
            malformed,
            webhook_headers(malformed, shared_material, "delivery-0002"),
        )
        check(status == 400 and value["status"] == "UNVERIFIED", "signed malformed JSON")

        fork = pull_payload()
        fork["pull_request"]["head"]["repo"]["full_name"] = "other/fork"
        fork_body = core.canonical_json(fork)
        status, value, _ = request(
            port,
            "POST",
            "/webhook",
            fork_body,
            webhook_headers(fork_body, shared_material, "delivery-0003"),
        )
        check(status == 400, "signed shape/coordinate mismatch is 400")

        wrong_type = dict(headers)
        wrong_type["Content-Type"] = "text/plain"
        status, _, _ = request(port, "POST", "/webhook", body, wrong_type)
        check(status == 415, "non-JSON media type rejected")

        ignored = core.canonical_json({"action": "created"})
        status, value, _ = request(
            port,
            "POST",
            "/webhook",
            ignored,
            webhook_headers(
                ignored, shared_material, "delivery-0004", event="push"
            ),
        )
        check(status == 202 and value["status"] == "ignored", "unsupported event")

        original = runtime.store.budget_status
        runtime.store.budget_status = mock.Mock(
            side_effect=server.sqlite3.OperationalError("fixture")
        )
        try:
            status, value, _ = request(port, "GET", "/readyz")
            check(status == 503 and value["status"] == "UNAVAILABLE", "DB readiness")
        finally:
            runtime.store.budget_status = original


def worker_failure_phase() -> None:
    with running_server() as (port, runtime, fake, shared_material):
        fake.error = core.BrokerError("UNAVAILABLE", "fixture outage")
        body = core.canonical_json(pull_payload())
        status, value, _ = request(
            port,
            "POST",
            "/webhook",
            body,
            webhook_headers(body, shared_material, "delivery-failure"),
        )
        check(value["status"] == "waiting_for_provenance", "failure waits")
        provenance = core.canonical_json(provenance_payload("f" * 24))
        request(
            port,
            "POST",
            "/provenance",
            provenance,
            {"Content-Type": "application/json"},
        )
        wait_for_calls(fake, 1)
        source = f"github-body:{core.sha256_bytes(body)}"
        deadline = time.monotonic() + 3
        result = None
        while time.monotonic() < deadline:
            result = runtime.store.job_result(source)
            if result and result["status"] == "failed":
                break
            time.sleep(0.01)
        check(result is not None and result["status"] == "failed", "worker failure stored")
        check(result["result"]["status"] == "UNAVAILABLE", "worker fail closed")


def request_bound_phase() -> None:
    policy = core.load_policy()
    policy["service"]["requestReadTimeoutSeconds"] = 1
    policy["service"]["maxRequestHandlers"] = 1
    keyring = {"maker-key": key_record()}
    runtime = server.BrokerRuntime(
        policy,
        core.BrokerStore(":memory:", provenance_keyring=keyring),
        FakeBroker(),
        b"webhook-fixture-material",
        keyring,
    )
    server.BrokerHandler.runtime = runtime
    httpd = server.BoundedThreadingHTTPServer(
        ("127.0.0.1", 0), server.BrokerHandler, max_handlers=1
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    slow = socket.create_connection(
        ("127.0.0.1", httpd.server_address[1]), timeout=3
    )
    try:
        slow.sendall(
            b"POST /webhook HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 10\r\n\r\n{"
        )
        deadline = time.monotonic() + 1
        while httpd.active_handlers != 1 and time.monotonic() < deadline:
            time.sleep(0.01)
        check(httpd.active_handlers == 1, "slow request occupies bounded slot")
        status, value, _ = request(
            httpd.server_address[1], "GET", "/healthz"
        )
        check(status == 503 and value["status"] == "UNAVAILABLE", "overload 503")
        slow.settimeout(3)
        response = slow.recv(4096)
        check(not response or b"408" in response, "slow request terminated")
    finally:
        slow.close()
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)
        runtime.close()


def environment_phase() -> None:
    forbidden = {
        "ITD_GITHUB_APP_CLIENT_ID": CLIENT_ID,
        "ITD_GITHUB_APP_PRIVATE_KEY_FILE": "/missing/app.pem",
        "ITD_GITHUB_WEBHOOK_SECRET_FILE": "/missing/webhook",
        "ITD_PROVENANCE_KEYRING_FILE": "/missing/keyring.json",
        "ITD_OPENAI_API_KEY_FILE": "/missing/openai",
        "ITD_BROKER_DATABASE": "/tmp/itd-broker-fixture.sqlite3",
        "OPENAI_API_KEY": "forbidden-ambient-value",
    }
    with mock.patch.dict(os.environ, forbidden, clear=True):
        expect_error(
            "UNAVAILABLE",
            server.BrokerRuntime.from_environment,
            "ambient OpenAI key rejected",
        )

    with tempfile.TemporaryDirectory(prefix="itd-broker-server-") as raw:
        root = Path(raw)
        root.chmod(0o700)
        app = root / "app.pem"
        webhook = root / "webhook"
        openai = root / "openai"
        keyring = root / "keyring.json"
        app.write_bytes(
            generate_private_key(
                public_exponent=65537, key_size=2048
            ).private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        webhook.write_bytes(b"fixture-webhook-material")
        openai.write_bytes(b"x" * 30)
        keyring.write_bytes(
            core.canonical_json({"maker-key": key_record()})
        )
        for path in (app, webhook, openai, keyring):
            path.chmod(0o600)
        configured = {
            "ITD_GITHUB_APP_CLIENT_ID": CLIENT_ID,
            "ITD_GITHUB_APP_PRIVATE_KEY_FILE": str(app),
            "ITD_GITHUB_WEBHOOK_SECRET_FILE": str(webhook),
            "ITD_PROVENANCE_KEYRING_FILE": str(keyring),
            "ITD_OPENAI_API_KEY_FILE": str(openai),
            "ITD_BROKER_DATABASE": str(root / "broker.sqlite3"),
        }
        with mock.patch.dict(os.environ, configured, clear=True):
            runtime = server.BrokerRuntime.from_environment()
            try:
                check(
                    runtime.webhook_material == b"fixture-webhook-material",
                    "webhook file",
                )
                check(runtime.provenance_keyring["maker-key"] == key_record(), "public keyring")
                check(
                    runtime.broker.reviewer.reviewer_credential == "x" * 30,
                    "reviewer key file",
                )
                check(runtime.broker.auth.client_id == CLIENT_ID, "App client id")
            finally:
                runtime.close()

        relative = dict(configured)
        relative["ITD_OPENAI_API_KEY_FILE"] = "openai"
        with mock.patch.dict(os.environ, relative, clear=True):
            expect_error(
                "UNAVAILABLE",
                server.BrokerRuntime.from_environment,
                "relative secret path rejected",
            )

        original_app = app.read_bytes()
        app.write_bytes(b"not-an-rsa-private-key")
        app.chmod(0o600)
        with mock.patch.dict(os.environ, configured, clear=True):
            expect_error(
                "UNAVAILABLE",
                server.BrokerRuntime.from_environment,
                "malformed App private key rejected at startup",
            )
        app.write_bytes(original_app)
        app.chmod(0o644)
        with mock.patch.dict(os.environ, configured, clear=True):
            expect_error(
                "UNAVAILABLE",
                server.BrokerRuntime.from_environment,
                "permissive App private key rejected at startup",
            )
        app.chmod(0o600)

        keyring.write_text('{"maker-key":{"publicKey":"bad"}}', encoding="utf-8")
        keyring.chmod(0o600)
        with mock.patch.dict(os.environ, configured, clear=True):
            expect_error(
                "UNAVAILABLE",
                server.BrokerRuntime.from_environment,
                "malformed public keyring rejected",
            )


def main() -> int:
    http_phase()
    worker_failure_phase()
    request_bound_phase()
    environment_phase()
    print(json.dumps({"checks": CHECKS, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
