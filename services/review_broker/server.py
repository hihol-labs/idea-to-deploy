#!/usr/bin/env python3
"""HTTP transport and single-worker runtime for the ITD review broker."""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import socket
import sqlite3
import sys
import threading
import time
import urllib.parse
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


def validate_public_keyring(
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
            or not isinstance(record.get("publicKey"), str)
            or not record["publicKey"]
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
            record["publicKey"],
            32,
            "provenance public key",
        )
        core.canonical_json(record)
        result[key_id] = dict(record)
    return result


def validate_free_reviewer_keyring(value: Any) -> dict[str, dict[str, Any]]:
    free = core._free_reviewer_module()
    if not isinstance(value, dict) or not 1 <= len(value) <= 64:
        raise core.BrokerError("UNAVAILABLE", "free reviewer keyring size is invalid")
    result: dict[str, dict[str, Any]] = {}
    required = {
        "publicKey", "repository", "appIntegrationId", "producerId",
        "reviewerModels",
    }
    for key_id, record in value.items():
        if (
            not isinstance(key_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", key_id)
            or not isinstance(record, dict)
            or set(record) != required
            or not isinstance(record["publicKey"], str)
            or not isinstance(record["repository"], str)
            or not re.fullmatch(
                r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", record["repository"]
            )
            or type(record["appIntegrationId"]) is not int
            or record["appIntegrationId"] <= 0
            or record["producerId"] != "itd-free-reviewer-producer-v1"
            or not isinstance(record["reviewerModels"], dict)
            or set(record["reviewerModels"]) != set(free.MANDATORY_REVIEW_ROUTE)
            or set(record["reviewerModels"].get("openai-subscription", []))
            != set(free.OPENAI_REVIEW_MODEL_ALTERNATES)
            or any(
                not isinstance(models, list)
                or not models
                or any(
                    not isinstance(model, str)
                    or not model.strip()
                    or model != model.strip()
                    for model in models
                )
                or len(models) != len(set(models))
                for models in record["reviewerModels"].values()
            )
        ):
            raise core.BrokerError("UNAVAILABLE", "free reviewer keyring is invalid")
        try:
            free.b64url_decode(record["publicKey"], 32, "free reviewer public key")
        except free.FreeReviewError as exc:
            raise core.BrokerError(exc.status, exc.reason) from exc
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
            self.thread.join()

    def _wait(self, timeout: float = 5) -> None:
        self.wake.wait(timeout=timeout)
        self.wake.clear()

    def _finish_job(
        self,
        job_id: int,
        success: bool,
        result: dict[str, Any],
    ) -> bool:
        for attempt in range(3):
            try:
                self.store.finish_job(job_id, success, result)
                return True
            except (core.BrokerError, sqlite3.Error, OSError):
                if attempt < 2:
                    self._wait(timeout=0.1)
        return False

    def _run(self) -> None:
        while not self.stop.is_set():
            try:
                self.store.reconcile_interrupted_jobs()
            except (core.BrokerError, sqlite3.Error, OSError):
                # Startup storage can be transiently unavailable.  Keep the
                # worker alive and retry; never acknowledge work through a
                # permanently dead daemon thread.
                self._wait()
                continue
            break
        while not self.stop.is_set():
            try:
                self.store.reconcile_interrupted_jobs()
                recovered = self.broker.recover_pending_publications()
            except (core.BrokerError, sqlite3.Error, OSError):
                self._wait()
                continue
            if recovered:
                continue
            try:
                claimed = self.store.claim()
            except (core.BrokerError, sqlite3.Error, OSError):
                self._wait()
                continue
            if claimed is None:
                prepared = 0
                try:
                    repositories = (
                        self.store.waiting_merge_group_repositories()
                    )
                except (core.BrokerError, sqlite3.Error, OSError):
                    repositories = []
                for repository in repositories:
                    try:
                        prepared += self.broker.prepare_waiting_merge_groups(
                            repository
                        )
                    except (core.BrokerError, sqlite3.Error, OSError):
                        continue
                if prepared:
                    continue
                self._wait()
                continue
            job_id, coordinates = claimed
            try:
                result = self.broker.process(coordinates)
            except core.BrokerError as exc:
                success = False
                outcome = {"status": exc.status, "reason": exc.reason}
            except Exception:
                success = False
                outcome = {
                    "status": "UNAVAILABLE",
                    "reason": "broker worker failed closed",
                }
            else:
                success = True
                outcome = result
            if isinstance(outcome, dict) and outcome.get(
                "recoveryPreparationId"
            ):
                self._wait(timeout=0.1)
                continue
            if not self._finish_job(job_id, success, outcome):
                # The next loop reconciles the still-running job before new
                # work can be claimed.  Back off so a broken store is bounded.
                self._wait()


class BrokerRuntime:
    def __init__(
        self,
        policy: dict[str, Any],
        store: core.BrokerStore,
        broker: core.ReviewBroker,
        webhook_material: bytes,
        provenance_keyring: dict[str, dict[str, Any]],
        free_reviewer_keyring: dict[str, dict[str, Any]],
        free_app_key_id: str,
        free_app_private_key: bytes,
    ) -> None:
        self.policy = policy
        self.store = store
        self.broker = broker
        self.webhook_material = webhook_material
        self.provenance_keyring = provenance_keyring
        self.free_reviewer_keyring = free_reviewer_keyring
        self.free_app_key_id = free_app_key_id
        self.free_app_private_key = free_app_private_key
        self.worker = BrokerWorker(broker, store)

    @classmethod
    def from_environment(cls) -> "BrokerRuntime":
        required = {
            "ITD_GITHUB_APP_CLIENT_ID",
            "ITD_GITHUB_APP_PRIVATE_KEY_FILE",
            "ITD_GITHUB_WEBHOOK_SECRET_FILE",
            "ITD_PROVENANCE_KEYRING_FILE",
            "ITD_FREE_REVIEWER_KEYRING_FILE",
            "ITD_FREE_REVIEW_APP_SIGNING_KEY_FILE",
            "ITD_FREE_REVIEW_APP_KEY_ID",
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
        provenance_keyring = validate_public_keyring(
            keyring_value, policy
        )
        free_keyring_raw = core.load_secret_file(
            _absolute_path("ITD_FREE_REVIEWER_KEYRING_FILE"),
            "free reviewer public keyring", 65536,
        )
        free_keyring_value = core.decode_strict_json(
            free_keyring_raw, "free reviewer public keyring"
        )
        free_reviewer_keyring = validate_free_reviewer_keyring(
            free_keyring_value
        )
        free_app_key_id = os.environ["ITD_FREE_REVIEW_APP_KEY_ID"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", free_app_key_id):
            raise core.BrokerError("UNVERIFIED", "free review App key id is invalid")
        free_app_private_key = core.load_secret_file(
            _absolute_path("ITD_FREE_REVIEW_APP_SIGNING_KEY_FILE"),
            "free review App signing key", 32,
        )
        if len(free_app_private_key) != 32:
            raise core.BrokerError("UNVERIFIED", "free review App signing key is invalid")
        github = core.GitHubApi(api_version=policy["github"]["apiVersion"])
        auth = core.GitHubAppAuth(
            client_id=os.environ["ITD_GITHUB_APP_CLIENT_ID"],
            private_key_file=_absolute_path(
                "ITD_GITHUB_APP_PRIVATE_KEY_FILE"
            ),
            policy=policy,
        )
        paid_consent = os.environ.get("ITD_PAID_REVIEW_CONSENT") == "approved"
        if os.environ.get("ITD_PAID_REVIEW_CONSENT") not in {None, "", "approved"}:
            raise core.BrokerError("UNVERIFIED", "paid review consent is invalid")
        reviewer = None
        if paid_consent:
            if not os.environ.get("ITD_OPENAI_API_KEY_FILE"):
                raise core.BrokerError(
                    "UNAVAILABLE", "consented paid reviewer credential file is missing"
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
        broker = core.ReviewBroker(
            policy, store, github, auth, reviewer,
            paid_fallback_consent=paid_consent,
        )
        return cls(
            policy, store, broker, webhook_material, provenance_keyring,
            free_reviewer_keyring, free_app_key_id, free_app_private_key,
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
        transfer_encoding = self.headers.get_all("Transfer-Encoding", [])
        content_lengths = self.headers.get_all("Content-Length", [])
        if transfer_encoding or len(content_lengths) != 1:
            self.close_connection = True
            raise RequestError(
                400, "UNVERIFIED", "ambiguous request framing"
            )
        raw_length = content_lengths[0].strip()
        if not re.fullmatch(r"(?:0|[1-9][0-9]*)", raw_length):
            self.close_connection = True
            raise RequestError(
                400, "UNVERIFIED", "invalid Content-Length"
            )
        length = int(raw_length)
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
        # Body-bearing API requests are single-request connections. This makes
        # any bytes beyond the one accepted Content-Length non-reusable as a
        # pipelined request even when an upstream client attempts smuggling.
        self.close_connection = True
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
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == self.runtime.policy["service"]["healthPath"]:
            if parsed.query or parsed.fragment:
                self._json(400, {"status": "UNVERIFIED"})
                return
            self._json(200, {"status": "ok"})
            return
        if parsed.path == self.runtime.policy["service"]["readinessPath"]:
            if (
                not self.runtime.worker.started
                or not self.runtime.worker.thread.is_alive()
            ):
                self._json(503, {"status": "UNAVAILABLE"})
                return
            try:
                budget = self.runtime.store.budget_status()
            except (core.BrokerError, sqlite3.Error, OSError):
                self._json(503, {"status": "UNAVAILABLE"})
                return
            enrollment = None
            provenance_keys = None
            if parsed.query:
                try:
                    query = urllib.parse.parse_qs(
                        parsed.query,
                        keep_blank_values=True,
                        strict_parsing=True,
                    )
                except ValueError:
                    self._json(400, {"status": "UNVERIFIED"})
                    return
                if (
                    set(query) != {"repository", "appId"}
                    or any(len(values) != 1 for values in query.values())
                ):
                    self._json(400, {"status": "UNVERIFIED"})
                    return
                repository = query["repository"][0]
                try:
                    app_id = int(query["appId"][0])
                    enrollment = self.runtime.store.enrollment_status(
                        repository, app_id
                    )
                except (ValueError, core.BrokerError):
                    self._json(
                        503,
                        {
                            "status": "UNAVAILABLE",
                            "reason": "repository enrollment is unavailable",
                        },
                    )
                    return
                provenance_keys = [
                    dict(record)
                    for _key_id, record in sorted(
                        self.runtime.provenance_keyring.items()
                    )
                    if record.get("repository") == repository
                ]
                if not provenance_keys:
                    self._json(
                        503,
                        {
                            "status": "UNAVAILABLE",
                            "reason": (
                                "repository provenance key is unavailable"
                            ),
                        },
                    )
                    return
            monthly = int(
                self.runtime.policy["budget"]["monthlyMicrousd"]
            )
            reservation = int(
                self.runtime.policy["budget"]["reservationMicrousd"]
            )
            committed = (
                budget["reservedMicrousd"] + budget["spentMicrousd"]
            )
            budget.update(
                {
                    "monthlyMicrousd": monthly,
                    "reservationMicrousd": reservation,
                    "remainingMicrousd": max(0, monthly - committed),
                    "admissionAvailable": (
                        committed + reservation <= monthly
                    ),
                }
            )
            reviewers = [
                {
                    "id": reviewer_id,
                    "vendor": row["vendor"],
                    "model": row["model"],
                }
                for reviewer_id, row in sorted(
                    self.runtime.policy["routing"]["reviewers"].items()
                )
            ]
            response = {
                "status": "ready",
                "policyId": self.runtime.policy["id"],
                "policySha256": core.sha256_bytes(
                    core.POLICY_PATH.read_bytes()
                ),
                "reviewers": reviewers,
                "budget": budget,
            }
            if enrollment is not None:
                response["enrollment"] = enrollment
                response["provenanceKeys"] = provenance_keys
            self._json(200, response)
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
            if self.path == self.runtime.policy["service"]["freeReviewPath"]:
                self._free_review()
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
        try:
            recorded = self.runtime.store.record_delivery_candidate(
                delivery,
                event,
                action,
                core.sha256_bytes(body),
                coordinates,
            )
        except core.DeliveryConflictError as exc:
            raise RequestError(409, exc.status, exc.reason) from exc
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

    def _free_review(self) -> None:
        body = self._body(1024 * 1024)
        payload = core.decode_strict_json(body, "free review submission")
        required = {"repository", "pullRequest", "headSha", "baseSha", "phaseOne"}
        if not isinstance(payload, dict) or set(payload) != required:
            raise core.BrokerError("UNVERIFIED", "free review submission is not closed")
        repository = payload["repository"]
        pull_request = payload["pullRequest"]
        head_sha = payload["headSha"]
        base_sha = payload["baseSha"]
        if (
            not isinstance(repository, str)
            or type(pull_request) is not int
            or not isinstance(head_sha, str)
            or not isinstance(base_sha, str)
            or not isinstance(payload["phaseOne"], dict)
        ):
            raise core.BrokerError("UNVERIFIED", "free review coordinates are invalid")
        installation_id = self.runtime.store.latest_installation(
            repository, pull_request, head_sha, base_sha
        )
        coordinates = core.Coordinates(
            repository, pull_request, head_sha, base_sha, installation_id
        ).validate()
        result = self.runtime.broker.bind_free_review(
            coordinates,
            phase_one=payload["phaseOne"],
            producer_keys=self.runtime.free_reviewer_keyring,
            app_key_id=self.runtime.free_app_key_id,
            app_private_key=self.runtime.free_app_private_key,
        )
        code = 200 if result["status"] == "PASSED" else (
            503 if result["status"] == "UNAVAILABLE" else 422
        )
        self._json(code, {
            "status": result["status"],
            "receiptId": result["receiptId"],
            "checkRunId": result["checkRunId"],
        })


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
