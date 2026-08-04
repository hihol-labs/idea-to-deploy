#!/usr/bin/env python3
"""Validate all mandatory reviewer transports and signed dual-host live proof."""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / ".itd" / "REVIEW_PROVIDER_FRESHNESS.json"
KEYRING = ROOT / ".itd" / "REVIEW_EFFICACY_KEYRING.json"
PRODUCER = ROOT / "skills" / "_shared" / "itd_free_reviewer_producer.py"


def load_producer():
    spec = importlib.util.spec_from_file_location("itd_provider_freshness", PRODUCER)
    if spec is None or spec.loader is None:
        raise AssertionError("mandatory keyless producer cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def version(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", value.strip())
    if not match:
        raise AssertionError(f"invalid semantic version: {value!r}")
    return tuple(int(part) for part in match.groups())


def current_host() -> str:
    if os.name == "nt":
        return "windows"
    release = platform.release().casefold()
    if os.name == "posix" and ("microsoft" in release or "wsl" in release):
        return "wsl"
    return "unsupported"


def exact(value: object, fields: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise AssertionError(f"{label} is not closed")
    return value


def fresh(value: str, max_age: int) -> None:
    observed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    age = dt.datetime.now(dt.timezone.utc) - observed
    if not dt.timedelta(0) <= age <= dt.timedelta(days=max_age):
        raise AssertionError("signed live provider proof is stale")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--live", action="store_true")
    value.add_argument("--executable", type=Path)
    value.add_argument("--executable-sha256")
    value.add_argument("--proxy-sha256")
    value.add_argument("--signing-key", type=Path)
    value.add_argument("--key-id")
    value.add_argument("--output", type=Path)
    return value


def signed(path: Path, producer, keys: dict[str, str], label: str) -> dict:
    envelope = json.loads(path.read_text(encoding="utf-8"))
    row = exact(envelope, {"signed", "signatureHex"}, label)
    payload = row["signed"]
    key_id = payload.get("keyId") if isinstance(payload, dict) else None
    signature = row["signatureHex"]
    if (
        not isinstance(key_id, str)
        or key_id not in keys
        or not isinstance(signature, str)
        or not re.fullmatch(r"[0-9a-f]{128}", signature)
    ):
        raise AssertionError(f"{label} signature envelope is invalid")
    try:
        public = producer.b64url_decode(keys[key_id], 32, label + " public key")
        producer.Ed25519PublicKey.from_public_bytes(public).verify(
            bytes.fromhex(signature), producer.canonical_bytes(payload)
        )
    except Exception as exc:
        raise AssertionError(f"{label} signature is invalid") from exc
    return payload


def signed_evidence(payload: dict, key_id: str, private_key: bytes, producer) -> dict:
    signed_payload = dict(payload)
    signed_payload["keyId"] = key_id
    signature = producer.Ed25519PrivateKey.from_private_bytes(private_key).sign(
        producer.canonical_bytes(signed_payload)
    )
    return {"signed": signed_payload, "signatureHex": signature.hex()}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    producer = load_producer()
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    keys = json.loads(KEYRING.read_text(encoding="utf-8"))
    exact(record, {
        "version", "checkedAt", "maxAgeDays", "mandatoryRoute",
        "legacyProvider", "rejectedCandidates", "requiredLiveHosts", "doneRule",
    }, "provider freshness record")
    if record["version"] != 3:
        raise AssertionError("provider freshness record version drifted")
    checked = dt.date.fromisoformat(record["checkedAt"])
    age = (dt.datetime.now(dt.timezone.utc).date() - checked).days
    if age < 0 or age > record["maxAgeDays"] or record["maxAgeDays"] > 30:
        raise AssertionError("mandatory reviewer-provider freshness expired")
    if record["requiredLiveHosts"] != ["wsl", "windows"]:
        raise AssertionError("dual-host live freshness proof is not mandatory")
    route = record["mandatoryRoute"]
    if (
        not isinstance(route, list)
        or [row.get("id") for row in route] != list(producer.MANDATORY_REVIEW_ROUTE)
    ):
        raise AssertionError("freshness record does not bind the complete route")
    for row in route:
        expected = {
            "id", "officialSource", "minimumVersion", "status",
            "requiredEvidence" if row.get("status") == "available"
            else "unavailabilityEvidence",
        }
        exact(row, expected, f"{row.get('id')} freshness row")
        version(row["minimumVersion"])
        if not row["officialSource"].startswith((
            "https://developers.openai.com/",
            "https://docs.anthropic.com/",
            "https://docs.github.com/",
        )):
            raise AssertionError("mandatory provider lacks an official source")
    if route[1]["status"] != "unavailable-no-paid-subscription":
        raise AssertionError("unconfigured Anthropic route is not typed unavailable")
    if route[0]["status"] != "available" or route[2]["status"] != "available":
        raise AssertionError("selected quorum transports are not available")

    if args.live:
        if any(value is None for value in (
            args.executable, args.executable_sha256, args.proxy_sha256,
            args.signing_key, args.key_id, args.output,
        )):
            raise AssertionError("--live requires executable, hashes, signer and output")
        host = current_host()
        if host not in record["requiredLiveHosts"]:
            raise AssertionError("live reviewer host is unsupported")
        executable = args.executable.resolve(strict=True)
        observed = subprocess.run(
            [str(executable), "--version"], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
            env={**os.environ, "CI": "1"},
        ).stdout.decode("utf-8")
        match = re.search(r"GitHub Copilot CLI ([0-9]+\.[0-9]+\.[0-9]+)\.", observed)
        if match is None or version(match.group(1)) < version(route[2]["minimumVersion"]):
            raise AssertionError("live Copilot CLI is below the pinned minimum")
        prompt = 'Return only {"verdict":"PASSED","findings":[],"unverified":[]}'
        report, session, model = producer.run_copilot_review(
            prompt, executable=str(executable), model="auto",
            expected_executable_sha256=args.executable_sha256,
            expected_proxy_sha256=args.proxy_sha256,
        )
        if report != {"verdict": "PASSED", "findings": [], "unverified": []}:
            raise AssertionError("live Copilot closed verdict is not clean")
        payload = {
            "version": 1, "kind": "itd-review-provider-live-proof",
            "provider": "github-copilot-user", "host": host,
            "observedAt": dt.datetime.now(dt.timezone.utc).replace(
                microsecond=0
            ).isoformat().replace("+00:00", "Z"),
            "runtimeVersion": match.group(1), "observedModel": model,
            "session": session,
            "transportExecutableSha256": args.executable_sha256,
            "proxySha256": args.proxy_sha256, "paidApiCalls": 0,
            "isolation": producer.required_isolation(), "status": "PASSED",
        }
        private_key = producer.gate.read_provenance_private_key(args.signing_key)
        producer.write_json(
            args.output,
            signed_evidence(payload, args.key_id, private_key, producer),
        )
        print(json.dumps({"status": "PASSED", "host": host, "live": True}, sort_keys=True))
        return 0

    observed_sessions: set[str] = set()
    for host, relative in zip(record["requiredLiveHosts"], route[0]["requiredEvidence"]):
        proof = signed(ROOT / relative, producer, keys, f"OpenAI {host} live proof")
        reviewer = proof.get("reviewer") or {}
        if (
            proof.get("kind") != "itd-independent-review-semantic-efficacy-run"
            or proof.get("host") != host
            or reviewer.get("provider") != "openai-subscription"
            or reviewer.get("paidApiCalls") != 0
            or version(str(reviewer.get("runtimeVersion")))
            < version(route[0]["minimumVersion"])
        ):
            raise AssertionError(f"OpenAI {host} live proof is invalid")
        fresh(proof["observedAt"], record["maxAgeDays"])
        sessions = [case.get("session") for case in proof.get("cases", [])]
        if not sessions or any(not value or value in observed_sessions for value in sessions):
            raise AssertionError("OpenAI live sessions are missing or reused")
        observed_sessions.update(sessions)

    copilot_sessions: set[str] = set()
    for host, relative in zip(record["requiredLiveHosts"], route[2]["requiredEvidence"]):
        proof = signed(ROOT / relative, producer, keys, f"Copilot {host} live proof")
        exact(proof, {
            "version", "kind", "provider", "host", "observedAt",
            "runtimeVersion", "observedModel", "session",
            "transportExecutableSha256", "proxySha256", "paidApiCalls",
            "isolation", "status", "keyId",
        }, f"Copilot {host} live payload")
        if (
            proof["version"] != 1
            or proof["kind"] != "itd-review-provider-live-proof"
            or proof["provider"] != "github-copilot-user"
            or proof["keyId"] != "gpg003-local-producer-20260803"
            or proof["host"] != host
            or proof["status"] != "PASSED"
            or proof["paidApiCalls"] != 0
            or proof["observedModel"] not in producer.COPILOT_ALLOWED_AUTO_MODELS
            or version(proof["runtimeVersion"]) < version(route[2]["minimumVersion"])
            or proof["session"] in copilot_sessions
            or proof["isolation"] != producer.required_isolation()
        ):
            raise AssertionError(f"Copilot {host} live proof is invalid")
        fresh(proof["observedAt"], record["maxAgeDays"])
        copilot_sessions.add(proof["session"])

    print(json.dumps({
        "status": "PASSED", "checkedAt": record["checkedAt"],
        "ageDays": age, "route": list(producer.MANDATORY_REVIEW_ROUTE),
        "signedDualHostProof": True, "live": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
