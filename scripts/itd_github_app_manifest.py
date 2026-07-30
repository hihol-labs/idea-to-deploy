#!/usr/bin/env python3
"""Create the dedicated ITD GitHub App through the official manifest flow."""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import secrets
import sys
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
MAX_CONVERSION_BYTES = 1024 * 1024
ORG_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{8,100}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
GITHUB_API_VERSION = "2026-03-10"


class ManifestError(RuntimeError):
    pass


def organization(value: str) -> str:
    if not isinstance(value, str) or not ORG_RE.fullmatch(value):
        raise ManifestError("GitHub organization is invalid")
    return value


def broker_base(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ManifestError(
            "broker URL must be a credential-free HTTPS origin"
        )
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, "", "", "")
    )


def manifest(
    *,
    name: str,
    broker_url: str,
    redirect_url: str,
) -> dict[str, Any]:
    if (
        not isinstance(name, str)
        or not 3 <= len(name) <= 100
        or any(ord(char) < 32 or ord(char) == 127 for char in name)
    ):
        raise ManifestError("GitHub App name is invalid")
    base = broker_base(broker_url)
    callback = urllib.parse.urlsplit(redirect_url)
    if (
        callback.scheme != "http"
        or callback.hostname not in {"127.0.0.1", "localhost"}
        or callback.path != "/callback"
        or callback.query
        or callback.fragment
    ):
        raise ManifestError(
            "manifest callback must be an exact loopback HTTP URL"
        )
    return {
        "name": name,
        "url": base,
        "hook_attributes": {
            "url": base + "/webhook",
            "active": True,
        },
        "redirect_url": redirect_url,
        "description": (
            "Fail-closed independent API review gate for Idea to Deploy."
        ),
        "public": False,
        "default_permissions": {
            "checks": "write",
            "contents": "read",
            "metadata": "read",
            "pull_requests": "read",
        },
        "default_events": ["pull_request", "merge_group"],
        "request_oauth_on_install": False,
        "setup_on_update": False,
    }


def conversion(
    code: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,200}", code):
        raise ManifestError("GitHub App manifest code is invalid")
    request = urllib.request.Request(
        "https://api.github.com/app-manifests/"
        + urllib.parse.quote(code, safe="")
        + "/conversions",
        data=b"{}",
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "itd-github-app-manifest/1",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
    )
    try:
        with opener(request, timeout=30) as response:
            raw = response.read(MAX_CONVERSION_BYTES + 1)
            status = getattr(response, "status", 201)
    except OSError as exc:
        raise ManifestError(
            "GitHub App manifest conversion request failed"
        ) from exc
    if status != 201 or not raw or len(raw) > MAX_CONVERSION_BYTES:
        raise ManifestError(
            "GitHub App manifest conversion response is invalid"
        )
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(
            "GitHub App manifest conversion is not valid JSON"
        ) from exc
    return validate_conversion(value)


def validate_conversion(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError("GitHub App conversion is not an object")
    owner = value.get("owner")
    pem = value.get("pem")
    webhook_secret = value.get("webhook_secret")
    if (
        type(value.get("id")) is not int
        or value["id"] <= 0
        or not CLIENT_ID_RE.fullmatch(str(value.get("client_id", "")))
        or not SLUG_RE.fullmatch(str(value.get("slug", "")))
        or not isinstance(value.get("node_id"), str)
        or not value["node_id"]
        or not isinstance(owner, dict)
        or not ORG_RE.fullmatch(str(owner.get("login", "")))
        or not isinstance(pem, str)
        or not pem.startswith("-----BEGIN RSA PRIVATE KEY-----\n")
        or not pem.rstrip().endswith(
            "-----END RSA PRIVATE KEY-----"
        )
        or not isinstance(webhook_secret, str)
        or not 20 <= len(webhook_secret) <= 200
        or any(
            ord(char) < 33 or ord(char) == 127
            for char in webhook_secret
        )
    ):
        raise ManifestError(
            "GitHub App conversion fields are incomplete or invalid"
        )
    return value


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def persist_conversion(
    value: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    value = validate_conversion(value)
    target = output_dir.expanduser().resolve()
    if target == ROOT or ROOT in target.parents:
        raise ManifestError(
            "GitHub App credentials must be stored outside the repository"
        )
    if target.exists():
        raise ManifestError(
            "GitHub App output target must not already exist"
        )
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging = target.with_name(
        f".{target.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    )
    os.mkdir(staging, mode=0o700)
    private_key = staging / "github-app-private-key.pem"
    webhook = staging / "github-webhook-secret"
    registration = staging / "github-app-registration.json"
    record = {
        "version": 1,
        "id": value["id"],
        "clientId": value["client_id"],
        "slug": value["slug"],
        "nodeId": value["node_id"],
        "owner": value["owner"]["login"],
    }
    try:
        atomic_write(private_key, value["pem"].encode("utf-8"))
        atomic_write(webhook, value["webhook_secret"].encode("utf-8"))
        atomic_write(
            registration,
            json.dumps(
                record,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            ).encode("utf-8")
            + b"\n",
        )
        os.replace(staging, target)
    except BaseException:
        for path in (private_key, webhook, registration):
            path.unlink(missing_ok=True)
        try:
            staging.rmdir()
        except FileNotFoundError:
            pass
        raise
    private_key = target / private_key.name
    webhook = target / webhook.name
    registration = target / registration.name
    return {
        "status": "CREATED",
        "appId": value["id"],
        "clientId": value["client_id"],
        "slug": value["slug"],
        "owner": value["owner"]["login"],
        "privateKeyFile": str(private_key),
        "webhookSecretFile": str(webhook),
        "registrationFile": str(registration),
        "clientSecretRetained": False,
    }


def registration_page(
    action: str,
    app_manifest: dict[str, Any],
) -> bytes:
    encoded_action = html.escape(action, quote=True)
    encoded_manifest = html.escape(
        json.dumps(
            app_manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        quote=True,
    )
    return (
        "<!doctype html><meta charset=\"utf-8\">"
        "<title>Create ITD review App</title>"
        "<h1>Create the dedicated ITD review App</h1>"
        "<p>GitHub will show the exact permissions and events before creation.</p>"
        f"<form action=\"{encoded_action}\" method=\"post\">"
        f"<input type=\"hidden\" name=\"manifest\" value=\"{encoded_manifest}\">"
        "<button type=\"submit\">Continue to GitHub</button>"
        "</form>"
    ).encode("utf-8")


def serve(args: argparse.Namespace) -> dict[str, Any]:
    if not args.apply:
        raise ManifestError("--serve requires explicit --apply")
    organization(args.organization)
    if not 30 <= args.timeout <= 3600:
        raise ManifestError("manifest timeout must be between 30 and 3600 seconds")
    output_dir = args.output_dir.expanduser().resolve()
    state = secrets.token_urlsafe(32)
    completed: dict[str, Any] = {}
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), BaseHTTPRequestHandler
    )
    port = int(server.server_address[1])
    callback_url = f"http://127.0.0.1:{port}/callback"
    app_manifest = manifest(
        name=args.name,
        broker_url=args.broker_url,
        redirect_url=callback_url,
    )
    action = (
        "https://github.com/organizations/"
        + urllib.parse.quote(args.organization, safe="")
        + "/settings/apps/new?"
        + urllib.parse.urlencode({"state": state})
    )
    page = registration_page(action, app_manifest)

    class Handler(BaseHTTPRequestHandler):
        server_version = "ITDManifest/1"
        sys_version = ""

        def log_message(self, _format: str, *_values: Any) -> None:
            return

        def send(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path == "/" and not parsed.query:
                self.send(200, page)
                return
            if parsed.path != "/callback":
                self.send(404, b"Not found")
                return
            query = urllib.parse.parse_qs(
                parsed.query,
                keep_blank_values=True,
                strict_parsing=True,
            )
            if (
                set(query) != {"code", "state"}
                or any(len(values) != 1 for values in query.values())
                or not secrets.compare_digest(query["state"][0], state)
            ):
                self.send(400, b"Invalid callback")
                return
            try:
                result = persist_conversion(
                    conversion(query["code"][0]),
                    output_dir,
                )
            except ManifestError:
                self.send(502, b"GitHub App conversion failed")
                return
            completed.update(result)
            self.send(
                200,
                b"ITD GitHub App created. Return to Codex.",
            )

    server.RequestHandlerClass = Handler
    deadline = time.monotonic() + args.timeout
    server.timeout = 1
    try:
        print(
            json.dumps(
                {
                    "status": "WAITING_FOR_BROWSER",
                    "url": f"http://127.0.0.1:{port}/",
                    "organization": args.organization,
                    "brokerUrl": broker_base(args.broker_url),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
        while not completed and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if not completed:
        raise ManifestError(
            "GitHub App manifest flow timed out before conversion"
        )
    return completed


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Create the dedicated ITD GitHub App"
    )
    result.add_argument("--organization", required=True)
    result.add_argument("--broker-url", required=True)
    result.add_argument(
        "--name", default="ITD Independent Review Gate"
    )
    result.add_argument("--output-dir", type=Path, required=True)
    mode = result.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--serve", action="store_true")
    result.add_argument("--apply", action="store_true")
    result.add_argument("--timeout", type=int, default=900)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        organization(args.organization)
        if args.serve:
            value = serve(args)
        else:
            if args.apply:
                raise ManifestError("--apply is valid only with --serve")
            value = {
                "status": "PREVIEW",
                "organization": args.organization,
                "manifest": manifest(
                    name=args.name,
                    broker_url=args.broker_url,
                    redirect_url="http://127.0.0.1:49152/callback",
                ),
                "outputDir": str(
                    args.output_dir.expanduser().resolve()
                ),
            }
    except (ManifestError, OSError, ValueError) as exc:
        print(
            json.dumps(
                {"status": "BLOCKED", "reason": str(exc)},
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
