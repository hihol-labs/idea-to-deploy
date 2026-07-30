#!/usr/bin/env python3
"""HTTP transport and single-worker runtime for the ITD review broker."""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "skills" / "_shared"
sys.path.insert(0, str(SHARED))

import itd_review_broker as core  # noqa: E402


class RequestError(RuntimeError):
    def __init__(self, http_status: int, status: str, reason: str) -> None:
        super().__init__(reason)
        self.http_status = http_status
        self.status = status
        self.reason = reason


def _absolute_path(name: str) -> Path:
    value = Path(os.environ[name])
    if not value.is_absolute():
        raise core.BrokerError(
            "UNAVAILABLE", f"{name} must name an absolute path"
        )
    return value.resolve()


def _validate_public_keyring(
    value: Any, policy: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or not 1 <= len(value) <= 1024:
        raise core.BrokerError(
            "UNAVAILABLE", "provenance public keyring size is invalid"
        )
    expected = set(policy["provenance"]["keyRegistryRecordFields"])
    result: dict[str, dict[str, Any]] = {}
    for key_id, record in value.items():
        if (
            not isinstance(key_id, str)
            or not isinstance(record, dict)
            or set(record) != expected
            or record.get("keyId") != key_id
            or record.get("status") not in {"active", "revoked"}
            or any(
                not isinstance(record.get(field), str)
                or not record[field]
                for field in (
                    "repository",
                    "authorizedMakerVendor",
                    "authorizedMakerModel",
                    "issuerPrincipal",
                )
            )
        ):
            raise core.BrokerError(
                "UNAVAILABLE", "provenance public keyring entry is invalid"
            )
        core.b64url_decode(
            str(record.get("publicKey", "")),
            32,
            "provenance public key",
        )
        core.canonical_json(record)
        result[key_id] = dict(record)
    return result


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address,
        request_handler,
        *,
        max_handlers: int,
    ) -> None:
        if not 1 <= max_handlers <= 256:
            raise ValueError("max_handlers is invalid")
        self._handler_slots = threading.BoundedSemaphore(max_handlers)
        self._active_lock = threading.Lock()
        self._active_handlers = 0
        super().__init__(server_address, request_handler)

    @property
    def active_handlers(self) -> int:
        with self._active_lock:
            return self._active_handlers

    def process_request(self, request, client_address) -> None:
        if not self._handler_slots.acquire(blocking=False):
            body = b'{"status":"UNAVAILABLE"}'
            response = (
                b"HTTP/1.1 503 Service Unavailable\r\n"
                b"Content-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\n".encode("ascii")
                + b"Connection: close\r\n\r\n"
                + body
            )
            try:
                request.sendall(response)
            except OSError:
                pass
            self.shutdown_request(request)
            return
        with self._active_lock:
            self._active_handlers += 1
        try:
            super().process_request(request, client_address)
        except Exception:
            with self._active_lock:
                self._active_handlers -= 1
            self._handler_slots.release()
            raise

    def process_request_thread(self, request, client_address) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self._active_lock:
                self._active_handlers -= 1
            self._handler_slots.release()


class BrokerWorker:
    def __init__(self, broker: core.ReviewBroker, store: core.BrokerStore) -> None:
        self.broker = broker
        self.store = store
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.thread = threading.Thread(
            target=self._run, name="itd-review-worker", daemon=True
        )
        self.started = False

    def start(self) -> None:
        if self.started:
            return
        self.thread.start()
        self.started = True

    def notify(self) -> None:
        self.wake.set()

    def close(self) -> None:
        self.stop.set()
        self.wake.set()
        if self.started:
            self.thread.join(timeout=10)

    def _run(self) -> None:
        self.store.reconcile_interrupted_jobs()
        while not self.stop.is_set():
            try:
                recovered = self.broker.recover_pending_publications()
            except core.BrokerError:
                recovered = 0
            if recovered:
                continue
            claimed = self.store.claim()
            if claimed is None:
                prepared = 0
                try:
                    repositories = (
                        self.store.waiting_merge_group_repositories()
                    )
                except core.BrokerError:
                    repositories = []
                for repository in repositories:
                    try:
                        prepared += self.broker.prepare_waiting_merge_groups(
                            repository
                        )
                    except core.BrokerError:
                        continue
                if prepared:
                    continue
                self.wake.wait(timeout=5)
                self.wake.clear()
                continue
            job_id, coordinates = claimed
            try:
                result = self.broker.process(coordinates)
            except core.BrokerError as exc:
                self.store.finish_job(
                    job_id,
                    False,
                    {"status": exc.status, "reason": exc.reason},
                )
            except Exception:
                self.store.finish_job(
                    job_id,
                    False,
                    {
                        "status": "UNAVAILABLE",
                        "reason": "broker worker failed closed",
                    },
                )
            else:
                self.store.finish_job(job_id, True, result)


class BrokerRuntime:
    def __init__(
        self,
        policy: dict[str, Any],
        store: core.BrokerStore,
        broker: core.ReviewBroker,
        webhook_material: bytes,
        provenance_keyring: dict[str, dict[str, Any]],
    ) -> None:
        self.policy = policy
        self.store = store
        self.broker = broker
        self.webhook_material = webhook_material
        self.provenance_keyring = provenance_keyring
        self.worker = BrokerWorker(broker, store)

    @classmethod
    def from_environment(cls) -> "BrokerRuntime":
        required = {
            "ITD_GITHUB_APP_CLIENT_ID",
            "ITD_GITHUB_APP_PRIVATE_KEY_FILE",
            "ITD_GITHUB_WEBHOOK_SECRET_FILE",
            "ITD_PROVENANCE_KEYRING_FILE",
            "ITD_OPENAI_API_KEY_FILE",
            "ITD_BROKER_DATABASE",
        }
        missing = sorted(name for name in required if not os.environ.get(name))
        if missing:
            raise core.BrokerError(
                "UNAVAILABLE",
                "broker secret/config file variables are missing: "
                + ", ".join(missing),
            )
        if os.environ.get("OPENAI_API_KEY"):
            raise core.BrokerError(
                "UNAVAILABLE",
                "OPENAI_API_KEY environment use is forbidden in broker mode",
            )
        policy = core.load_policy()
        database_config = Path(os.environ["ITD_BROKER_DATABASE"])
        if not database_config.is_absolute():
            raise core.BrokerError(
                "UNAVAILABLE", "ITD_BROKER_DATABASE must be absolute"
            )
        database = database_config.resolve()
        database.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        keyring_path = _absolute_path(
            "ITD_PROVENANCE_KEYRING_FILE"
        )
        keyring_raw = core.load_secret_file(
            keyring_path, "provenance public keyring", 65536
        )
        keyring_value = core.decode_strict_json(
            keyring_raw, "provenance public keyring"
        )
        provenance_keyring = _validate_public_keyring(
            keyring_value, policy
        )
        github = core.GitHubApi(api_version=policy["github"]["apiVersion"])
        auth = core.GitHubAppAuth(
            client_id=os.environ["ITD_GITHUB_APP_CLIENT_ID"],
            private_key_file=_absolute_path(
                "ITD_GITHUB_APP_PRIVATE_KEY_FILE"
            ),
            policy=policy,
        )
        reviewer_credential = core.load_secret_file(
            _absolute_path("ITD_OPENAI_API_KEY_FILE"),
            "OpenAI API key",
            4096,
        ).decode("utf-8")
        reviewer = core.ReviewerAdapter(reviewer_credential)
        webhook_material = core.load_secret_file(
            _absolute_path("ITD_GITHUB_WEBHOOK_SECRET_FILE"),
            "GitHub webhook secret",
            4096,
        )
        store = core.BrokerStore(
            database,
            policy=policy,
            provenance_keyring=provenance_keyring,
        )
        broker = core.ReviewBroker(policy, store, github, auth, reviewer)
        return cls(
            policy, store, broker, webhook_material, provenance_keyring
        )

    def close(self) -> None:
        self.worker.close()
        self.store.close()


class BrokerHandler(BaseHTTPRequestHandler):
    runtime: BrokerRuntime
    server_version = "ITDReviewBroker/1"
    sys_version = ""

    def setup(self) -> None:
        super().setup()
        timeout = float(
            self.runtime.policy["service"]["requestReadTimeoutSeconds"]
        )
        self.connection.settimeout(timeout)

    def log_message(self, format_string: str, *args: Any) -> None:
        # Bounded metadata only. Request bodies, signatures and credentials are
        # never logged.
        message = format_string % args
        sys.stderr.write(
            json.dumps(
                {
                    "at": core.now_iso(),
                    "remote": self.client_address[0],
                    "message": message[:500],
                },
                sort_keys=True,
            )
            + "\n"
        )

    def _json(self, status: int, value: dict[str, Any]) -> None:
        body = json.dumps(value, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _body(self, limit: int) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError as exc:
            raise RequestError(
                400, "UNVERIFIED", "invalid Content-Length"
            ) from exc
        if length <= 0:
            raise RequestError(
                400, "UNVERIFIED", "request body size is invalid"
            )
        if length > limit:
            self.close_connection = True
            raise RequestError(
                413, "UNVERIFIED", "request body exceeds its bound"
            )
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0]
        if content_type.strip().lower() != "application/json":
            raise RequestError(
                415, "UNVERIFIED", "application/json is required"
            )
        # Content-Length is the framing boundary. Reading one extra byte can
        # block on a persistent HTTP connection or consume the next pipelined
        # request; the declared length was already checked against the bound.
        body = self.rfile.read(length)
        if len(body) != length:
            raise RequestError(
                400, "UNVERIFIED", "request body length mismatch"
            )
        return body

    def do_GET(self) -> None:  # noqa: N802
        if self.path == self.runtime.policy["service"]["healthPath"]:
            self._json(200, {"status": "ok"})
            return
        if self.path == self.runtime.policy["service"]["readinessPath"]:
            try:
                budget = self.runtime.store.budget_status()
            except sqlite3.Error:
                self._json(503, {"status": "UNAVAILABLE"})
                return
            self._json(200, {"status": "ready", "budget": budget})
            return
        self._json(404, {"status": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            if self.path == self.runtime.policy["service"]["webhookPath"]:
                self._webhook()
                return
            if self.path == self.runtime.policy["service"]["provenancePath"]:
                self._provenance()
                return
            self._json(404, {"status": "not_found"})
        except RequestError as exc:
            self._json(
                exc.http_status,
                {"status": exc.status, "reason": exc.reason},
            )
        except core.BrokerError as exc:
            code = 503 if exc.status == "UNAVAILABLE" else 422
            self._json(code, {"status": exc.status, "reason": exc.reason})
        except (TimeoutError, socket.timeout):
            self.close_connection = True
            try:
                self._json(
                    408,
                    {
                        "status": "UNAVAILABLE",
                        "reason": "request body read timed out",
                    },
                )
            except OSError:
                pass

    def _webhook(self) -> None:
        limit = int(self.runtime.policy["github"]["webhooks"]["maxBodyBytes"])
        body = self._body(limit)
        signature = self.headers.get("X-Hub-Signature-256", "")
        try:
            core.verify_webhook_signature(
                body,
                signature,
                self.runtime.webhook_material,
                self.runtime.policy,
            )
        except core.BrokerError as exc:
            raise RequestError(401, exc.status, exc.reason) from exc
        event = self.headers.get("X-GitHub-Event", "").strip()
        delivery = self.headers.get("X-GitHub-Delivery", "").strip()
        if not event or not delivery:
            raise RequestError(
                400, "UNVERIFIED", "GitHub event/delivery header is required"
            )
        try:
            payload = core.decode_strict_json(
                body, "GitHub webhook payload"
            )
        except core.BrokerError as exc:
            raise RequestError(400, exc.status, exc.reason) from exc
        if not isinstance(payload, dict):
            raise RequestError(
                400, "UNVERIFIED", "webhook payload is not an object"
            )
        action = str(payload.get("action", "")).strip()
        try:
            coordinates = core.normalize_webhook(
                event, action, payload, self.runtime.policy
            )
        except core.BrokerError as exc:
            raise RequestError(400, exc.status, exc.reason) from exc
        if coordinates is None:
            self._json(202, {"status": "ignored"})
            return
        recorded = self.runtime.store.record_delivery_candidate(
            delivery,
            event,
            action,
            core.sha256_bytes(body),
            coordinates,
        )
        if not recorded:
            self._json(202, {"status": "duplicate"})
            return
        if coordinates.subject_type == "merge_group":
            try:
                self.runtime.broker.prepare_merge_group(coordinates)
            except core.BrokerError:
                state = "waiting_for_provenance"
            else:
                self.runtime.worker.notify()
                state = "queued"
        else:
            state = "waiting_for_provenance"
        self._json(
            202,
            {
                "status": state,
                "repository": coordinates.repository,
                "pullRequest": coordinates.pull_request,
                "headSha": coordinates.head_sha,
                "baseSha": coordinates.base_sha,
            },
        )

    def _provenance(self) -> None:
        body = self._body(65536)
        payload = core.decode_strict_json(body, "maker provenance")
        if not isinstance(payload, dict):
            raise core.BrokerError(
                "UNVERIFIED", "provenance payload is not an object"
            )
        repository = payload.get("repository")
        pull_request = payload.get("pullRequest")
        head_sha = payload.get("headSha")
        base_sha = payload.get("baseSha")
        if (
            not isinstance(repository, str)
            or type(pull_request) is not int
            or not isinstance(head_sha, str)
            or not isinstance(base_sha, str)
        ):
            raise core.BrokerError(
                "UNVERIFIED", "provenance coordinates are invalid"
            )
        installation_id = self.runtime.store.latest_installation(
            repository,
            pull_request,
            head_sha,
            base_sha,
        )
        coordinates = core.Coordinates(
            repository=repository,
            pull_request=pull_request,
            head_sha=head_sha,
            base_sha=base_sha,
            installation_id=installation_id,
        ).validate()
        self.runtime.store.put_provenance_and_queue(
            payload, coordinates
        )
        self.runtime.broker.prepare_waiting_merge_groups(
            coordinates.repository
        )
        self.runtime.worker.notify()
        self._json(
            202,
            {
                "status": "queued",
                "repository": coordinates.repository,
                "pullRequest": coordinates.pull_request,
                "headSha": coordinates.head_sha,
                "baseSha": coordinates.base_sha,
            },
        )


def serve(runtime: BrokerRuntime, host: str, port: int) -> int:
    BrokerHandler.runtime = runtime
    server = BoundedThreadingHTTPServer(
        (host, port),
        BrokerHandler,
        max_handlers=int(
            runtime.policy["service"]["maxRequestHandlers"]
        ),
    )
    stopped = threading.Event()

    def stop_server(_signum: int, _frame: Any) -> None:
        if not stopped.is_set():
            stopped.set()
            threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop_server)
    signal.signal(signal.SIGINT, stop_server)
    runtime.worker.start()
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        runtime.close()
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Serve the ITD review broker")
    result.add_argument(
        "--host", default=os.environ.get("ITD_BROKER_HOST", "127.0.0.1")
    )
    result.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("ITD_BROKER_PORT", "8080")),
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        raise SystemExit("invalid port")
    try:
        runtime = BrokerRuntime.from_environment()
        return serve(runtime, args.host, args.port)
    except core.BrokerError as exc:
        print(
            json.dumps({"status": exc.status, "reason": exc.reason}, sort_keys=True),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
