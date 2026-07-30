#!/usr/bin/env python3
"""Trust primitives for the central ITD GitHub App review broker.

The broker is deliberately not a CI runner.  It verifies GitHub webhook
deliveries, obtains a repository-scoped installation token, fetches a bounded
PR diff through GitHub's API, sanitizes it, calls an independent API reviewer,
persists exact-coordinate evidence, and publishes a Check Run attributed to
the dedicated GitHub App.  It never checks out or executes candidate code.
"""
from __future__ import annotations

import base64
import binascii
import contextlib
import datetime as dt
import hashlib
import hmac
import http.client
import importlib.util
import json
import math
import os
import re
import secrets
import sqlite3
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = Path(__file__).with_name("REVIEW_BROKER_POLICY.json")
POLICY_SCHEMA_PATH = Path(__file__).with_name("REVIEW_BROKER_POLICY.schema.json")
RUNTIME_SCHEMA_PATH = Path(__file__).with_name("REVIEW_BROKER_RUNTIME.schema.json")
REVIEW_POLICY_PATH = Path(__file__).with_name("EXTERNAL_REVIEW_POLICY.json")
VERDICT_SCHEMA_PATH = Path(__file__).with_name("EXTERNAL_REVIEW_VERDICT_SCHEMA.json")
REVIEWER_PATH = Path(__file__).with_name("itd_external_reviewer.py")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(
    r"^(?![.]{1,2}/)(?![^/]+/[.]{1,2}$)"
    r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$"
)
NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
DELIVERY_RE = re.compile(r"^[A-Za-z0-9-]{8,128}$")
SAFE_TEXT_RE = re.compile(r"^[^\r\n]{1,200}$")
DIFF_HEADER_RE = re.compile(r"^diff --git ", re.MULTILINE)
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)
MAX_JSON_BYTES = 4 * 1024 * 1024
PROVIDER_SYSTEM_PROMPT = (
    "Return only the requested strict structured review verdict."
)
JCS_SAFE_INTEGER_MAX = (2**53) - 1
JCS_SAFE_INTEGER_MIN = -JCS_SAFE_INTEGER_MAX
JCS_SHORT_ESCAPES = {
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
    '"': '\\"',
    "\\": "\\\\",
}


def b64url_decode(value: str, expected_bytes: int, label: str) -> bytes:
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]+", value)
        or "=" in value
    ):
        raise BrokerError("UNVERIFIED", f"{label} is not canonical base64url")
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, binascii.Error) as exc:
        raise BrokerError("UNVERIFIED", f"{label} is invalid") from exc
    if len(raw) != expected_bytes or b64url(raw) != value:
        raise BrokerError("UNVERIFIED", f"{label} has the wrong length")
    return raw


class BrokerError(RuntimeError):
    """A typed fail-closed broker outcome."""

    def __init__(self, status: str, reason: str) -> None:
        if status not in {"UNAVAILABLE", "UNVERIFIED", "BLOCKED"}:
            raise ValueError(f"invalid broker error status: {status}")
        super().__init__(reason)
        self.status = status
        self.reason = reason


def _jcs_string(value: str) -> bytes:
    """Serialize a string according to RFC 8785 section 3.2.2.2."""
    serialized = ['"']
    for character in value:
        codepoint = ord(character)
        if 0xD800 <= codepoint <= 0xDFFF:
            raise BrokerError("UNVERIFIED", "JCS input contains a lone surrogate")
        replacement = JCS_SHORT_ESCAPES.get(character)
        if replacement is not None:
            serialized.append(replacement)
        elif codepoint <= 0x1F:
            serialized.append(f"\\u{codepoint:04x}")
        else:
            serialized.append(character)
    serialized.append('"')
    try:
        return "".join(serialized).encode("utf-8")
    except UnicodeEncodeError as exc:
        raise BrokerError("UNVERIFIED", "JCS input is not valid Unicode") from exc


def _jcs_float(value: float) -> bytes:
    """Emit ECMAScript-compatible binary64 text required by RFC 8785."""
    if not math.isfinite(value):
        raise BrokerError("UNVERIFIED", "JCS numbers must be finite")
    if value == 0:
        return b"0"
    if value < 0:
        return b"-" + _jcs_float(-value)

    # CPython 3.8+ uses a shortest-round-trip binary64 representation.  JCS
    # uses the same significant digits, but ECMAScript selects plain notation
    # for exponents in [-6, 20].  The transformation below implements that
    # presentation boundary and normalizes exponent signs and leading zeroes.
    shortest = repr(value).lower()
    mantissa, marker, exponent_text = shortest.partition("e")
    exponent = int(exponent_text) if marker else 0
    integer, dot, fraction = mantissa.partition(".")
    if fraction == "0":
        dot = ""
        fraction = ""

    if marker and 0 < exponent < 21:
        digits = integer + fraction
        zeroes = exponent - len(integer) - len(fraction) + 1
        return (digits + ("0" * max(zeroes, 0))).encode("ascii")
    if marker and -7 < exponent < 0:
        digits = integer + fraction
        return ("0." + ("0" * (-exponent - 1)) + digits).encode("ascii")
    if marker:
        normalized_exponent = f"{exponent:+d}" if exponent > 0 else str(exponent)
        return f"{integer}{dot}{fraction}e{normalized_exponent}".encode("ascii")
    return f"{integer}{dot}{fraction}".encode("ascii")


def _jcs_serialize(value: Any, output: bytearray) -> None:
    value_type = type(value)
    if value is None:
        output.extend(b"null")
    elif value_type is bool:
        output.extend(b"true" if value else b"false")
    elif value_type is int:
        if value < JCS_SAFE_INTEGER_MIN or value > JCS_SAFE_INTEGER_MAX:
            raise BrokerError(
                "UNVERIFIED", "JCS integer exceeds the interoperable binary64 domain"
            )
        output.extend(str(value).encode("ascii"))
    elif value_type is float:
        output.extend(_jcs_float(value))
    elif value_type is str:
        output.extend(_jcs_string(value))
    elif value_type is list:
        output.extend(b"[")
        for index, item in enumerate(value):
            if index:
                output.extend(b",")
            _jcs_serialize(item, output)
        output.extend(b"]")
    elif value_type is dict:
        for key in value:
            if type(key) is not str:
                raise BrokerError("UNVERIFIED", "JCS object keys must be strings")
            _jcs_string(key)
        try:
            keys = sorted(value, key=lambda key: key.encode("utf-16-be"))
        except UnicodeEncodeError as exc:
            raise BrokerError(
                "UNVERIFIED", "JCS object key is not valid Unicode"
            ) from exc
        output.extend(b"{")
        for index, key in enumerate(keys):
            if index:
                output.extend(b",")
            output.extend(_jcs_string(key))
            output.extend(b":")
            _jcs_serialize(value[key], output)
        output.extend(b"}")
    else:
        raise BrokerError(
            "UNVERIFIED", f"JCS input has unsupported type {value_type.__name__}"
        )


def canonical_json(value: Any) -> bytes:
    """Return RFC 8785 JSON Canonicalization Scheme (JCS) bytes."""
    output = bytearray()
    try:
        _jcs_serialize(value, output)
    except RecursionError as exc:
        raise BrokerError("UNVERIFIED", "JCS input nesting is too deep") from exc
    return bytes(output)


def decode_strict_json(raw: bytes, label: str) -> Any:
    """Parse I-JSON and reject inputs that cannot be safely canonicalized."""
    if type(raw) is not bytes:
        raise BrokerError("UNVERIFIED", f"{label} is not exact bytes")

    def reject_duplicate_names(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, item in pairs:
            if name in result:
                raise ValueError("duplicate JSON property")
            result[name] = item
        return result

    def reject_nonfinite_number(token: str) -> None:
        raise ValueError(f"non-finite JSON number: {token}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicate_names,
            parse_constant=reject_nonfinite_number,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise BrokerError("UNVERIFIED", f"{label} is invalid JSON") from exc
    canonical_json(value)
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def now_iso() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def utc_period() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")


def parse_iso(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise BrokerError("UNVERIFIED", "provenance issuedAt is not ISO-8601") from exc
    if parsed.tzinfo is None:
        raise BrokerError("UNVERIFIED", "provenance issuedAt has no timezone")
    return parsed.astimezone(dt.timezone.utc)


def read_json(path: Path, limit: int = MAX_JSON_BYTES) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise BrokerError("UNAVAILABLE", f"cannot read {path.name}") from exc
    if len(raw) > limit:
        raise BrokerError("UNVERIFIED", f"{path.name} exceeds its size limit")

    value = decode_strict_json(raw, path.name)
    if not isinstance(value, dict):
        raise BrokerError("UNVERIFIED", f"{path.name} must contain an object")
    return value


def canonical_provider_request(
    provider: dict[str, Any],
    prompt: str,
    response_schema: dict[str, Any],
    schema_name: str,
    output_cap: int,
) -> bytes:
    """Build the exact credential-free Responses API request body."""
    if (
        not isinstance(provider, dict)
        or not isinstance(provider.get("model"), str)
        or not provider["model"]
        or not isinstance(prompt, str)
        or not isinstance(response_schema, dict)
        or not re.fullmatch(r"[a-z0-9_]{1,64}", schema_name)
        or type(output_cap) is not int
        or output_cap <= 0
    ):
        raise BrokerError("UNVERIFIED", "provider request binding is invalid")
    return canonical_json(
        {
            "model": provider["model"],
            "store": False,
            "input": [
                {
                    "role": "system",
                    "content": PROVIDER_SYSTEM_PROMPT,
                },
                {"role": "user", "content": prompt},
            ],
            "max_output_tokens": output_cap,
            "reasoning": {
                "effort": str(provider.get("reasoningEffort", "medium"))
            },
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": response_schema,
                }
            },
        }
    )


def _exact_keys(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise BrokerError("UNVERIFIED", f"{label} fields are not closed")
    return value


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    """Validate the complete frozen policy through its closed schema."""
    schema = read_json(POLICY_SCHEMA_PATH)
    required = set(schema.get("required") or [])
    properties = schema.get("properties")
    if (
        schema.get("additionalProperties") is not False
        or not isinstance(properties, dict)
        or set(policy) != required
        or set(properties) != required
    ):
        raise BrokerError("UNVERIFIED", "broker policy schema is not closed")
    for name in sorted(required):
        row = properties.get(name)
        if not isinstance(row, dict) or set(row) != {"const"}:
            raise BrokerError(
                "UNVERIFIED", f"broker policy schema does not freeze {name}"
            )
        if policy.get(name) != row["const"]:
            raise BrokerError("UNVERIFIED", f"broker policy drift: {name}")
    return policy


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    return validate_policy(read_json(path))


def validate_runtime_record(name: str, value: dict[str, Any]) -> None:
    runtime = read_json(RUNTIME_SCHEMA_PATH)
    try:
        Draft202012Validator(
            {
                "$schema": runtime["$schema"],
                "$defs": runtime["$defs"],
                "$ref": f"#/$defs/{name}",
            }
        ).validate(value)
    except (KeyError, ValidationError) as exc:
        raise BrokerError(
            "UNVERIFIED", f"{name} does not satisfy the closed runtime schema"
        ) from exc


def classify_maker(
    vendor: str, model: str, policy: dict[str, Any]
) -> str:
    classification = policy["routing"]["classification"]
    normalized_vendor = str(vendor).strip().casefold()
    normalized_model = str(model).strip().casefold()
    rules = classification["rules"]
    for name in classification["firstMatchOrder"]:
        rule = rules[name]
        if name == "unknownMaker":
            return name
        if "vendorEquals" in rule:
            if normalized_vendor != str(rule["vendorEquals"]).casefold():
                continue
        elif "vendorIn" in rule:
            allowed = {str(item).casefold() for item in rule["vendorIn"]}
            if normalized_vendor not in allowed:
                continue
        if "modelEquals" in rule and (
            normalized_model != str(rule["modelEquals"]).casefold()
        ):
            continue
        if "modelPrefix" in rule and not normalized_model.startswith(
            str(rule["modelPrefix"]).casefold()
        ):
            continue
        return name
    return "unknownMaker"


def select_reviewer(
    maker_class: str, maker_vendor: str, maker_model: str,
    policy: dict[str, Any],
) -> str:
    routes = policy["routing"].get(maker_class)
    if not isinstance(routes, list) or not routes:
        raise BrokerError("UNVERIFIED", "maker has no eligible automatic route")
    maker_identity = (
        str(maker_vendor).strip().casefold(),
        str(maker_model).strip().casefold(),
    )
    for reviewer_id in routes:
        reviewer = policy["routing"]["reviewers"].get(reviewer_id)
        if not isinstance(reviewer, dict):
            continue
        checker_identity = (
            str(reviewer.get("vendor", "")).strip().casefold(),
            str(reviewer.get("model", "")).strip().casefold(),
        )
        if checker_identity != maker_identity:
            return reviewer_id
    raise BrokerError("UNAVAILABLE", "no different reviewer identity is eligible")


@dataclass(frozen=True)
class Coordinates:
    repository: str
    pull_request: int
    head_sha: str
    base_sha: str
    installation_id: int

    @property
    def subject_type(self) -> str:
        return "merge_group" if self.pull_request == 0 else "pull_request"

    def validate(self) -> "Coordinates":
        if not REPO_RE.fullmatch(self.repository):
            raise BrokerError("UNVERIFIED", "invalid repository coordinate")
        if type(self.pull_request) is not int or self.pull_request < 0:
            raise BrokerError("UNVERIFIED", "invalid pull request coordinate")
        if not SHA_RE.fullmatch(self.head_sha):
            raise BrokerError("UNVERIFIED", "invalid head SHA coordinate")
        if not SHA_RE.fullmatch(self.base_sha):
            raise BrokerError("UNVERIFIED", "invalid base SHA coordinate")
        if type(self.installation_id) is not int or self.installation_id <= 0:
            raise BrokerError("UNVERIFIED", "invalid App installation coordinate")
        return self

    def key(self) -> str:
        subject = (
            f"pr-{self.pull_request}"
            if self.pull_request
            else "merge-group"
        )
        return (
            f"{self.repository}#{subject}:"
            f"{self.head_sha}:{self.base_sha}"
        )


def read_bounded_body(stream: Any, max_body_bytes: int) -> bytes:
    """Read at most the configured webhook body without unbounded buffering."""
    if type(max_body_bytes) is not int or max_body_bytes <= 0:
        raise BrokerError("UNVERIFIED", "webhook body limit is invalid")
    body = bytearray()
    while True:
        allowance = max_body_bytes - len(body)
        chunk = stream.read(min(65536, allowance + 1))
        if not isinstance(chunk, bytes):
            raise BrokerError("UNVERIFIED", "webhook body stream returned non-bytes")
        if not chunk:
            return bytes(body)
        if len(chunk) > allowance:
            raise BrokerError("UNVERIFIED", "webhook body exceeds policy bound")
        body.extend(chunk)


def verify_webhook_signature(
    body: bytes,
    supplied: str,
    shared_material: bytes,
    policy: dict[str, Any],
) -> None:
    frozen = validate_policy(policy)
    if not isinstance(body, bytes):
        raise BrokerError("UNVERIFIED", "webhook body must be exact bytes")
    if len(body) > int(
        frozen["github"]["webhooks"]["maxBodyBytes"]
    ):
        raise BrokerError("UNVERIFIED", "webhook body exceeds policy bound")
    if not shared_material:
        raise BrokerError("UNAVAILABLE", "webhook secret is unavailable")
    if not re.fullmatch(r"sha256=[0-9a-f]{64}", supplied or ""):
        raise BrokerError("UNVERIFIED", "webhook signature is missing or malformed")
    expected = (
        "sha256="
        + hmac.new(shared_material, body, hashlib.sha256).hexdigest()
    )
    if not hmac.compare_digest(expected, supplied):
        raise BrokerError("UNVERIFIED", "webhook signature mismatch")


def derive_webhook_event(payload: dict[str, Any], policy: dict[str, Any]) -> str:
    binding = policy["github"]["webhooks"]["eventBinding"]
    if not isinstance(payload, dict):
        raise BrokerError("UNVERIFIED", "webhook payload is not an object")
    matches: list[str] = []
    for event, shape in binding["payloadShapes"].items():
        required = set(shape["requiredTopLevelFields"])
        forbidden = set(shape["forbiddenTopLevelFields"])
        if required.issubset(payload) and not forbidden.intersection(payload):
            matches.append(event)
    if len(matches) != 1:
        raise BrokerError("UNVERIFIED", "webhook payload shape is ambiguous or unsupported")
    return matches[0]


def normalize_webhook(
    event: str, action: str, payload: dict[str, Any], policy: dict[str, Any]
) -> Coordinates | None:
    accepted = policy["github"]["webhooks"]["accepted"]
    if event not in accepted:
        return None
    derived = derive_webhook_event(payload, policy)
    payload_action = payload.get(
        policy["github"]["webhooks"]["eventBinding"]["actionField"]
    )
    if derived != event or payload_action != action or action not in accepted[event]:
        raise BrokerError(
            "UNVERIFIED", "webhook event header, payload shape, or action mismatch"
        )
    installation = payload.get("installation")
    repository = payload.get("repository")
    if not isinstance(installation, dict) or not isinstance(repository, dict):
        raise BrokerError("UNVERIFIED", "webhook lacks App installation/repository")
    full_name = str(repository.get("full_name", "")).strip()
    installation_id = installation.get("id")
    if event == "pull_request":
        pull = payload.get("pull_request")
        if not isinstance(pull, dict):
            raise BrokerError("UNVERIFIED", "pull_request payload is missing")
        head = pull.get("head")
        base = pull.get("base")
        if not isinstance(head, dict) or not isinstance(base, dict):
            raise BrokerError("UNVERIFIED", "pull request refs are missing")
        head_repository = head.get("repo")
        base_repository = base.get("repo")
        if not isinstance(head_repository, dict) or not isinstance(base_repository, dict):
            raise BrokerError("UNVERIFIED", "pull request repositories are missing")
        head_full_name = str(head_repository.get("full_name", "")).strip()
        base_full_name = str(base_repository.get("full_name", "")).strip()
        if base_full_name.casefold() != full_name.casefold():
            raise BrokerError("UNVERIFIED", "pull request base repository mismatch")
        if (
            not policy["candidate"]["allowForkPullRequests"]
            and head_full_name.casefold() != full_name.casefold()
        ):
            raise BrokerError("UNVERIFIED", "fork pull requests are not allowed")
        return Coordinates(
            repository=full_name,
            pull_request=int(payload.get("number", 0)),
            head_sha=str(head.get("sha", "")).lower(),
            base_sha=str(base.get("sha", "")).lower(),
            installation_id=int(installation_id or 0),
        ).validate()
    group = payload.get("merge_group")
    if not isinstance(group, dict):
        raise BrokerError("UNVERIFIED", "merge_group payload is missing")
    return Coordinates(
        repository=full_name,
        pull_request=0,
        head_sha=str(group.get("head_sha", "")).lower(),
        base_sha=str(group.get("base_sha", "")).lower(),
        installation_id=int(installation_id or 0),
    ).validate()


def provenance_payload(value: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "repository", "pullRequest", "headSha", "baseSha", "makerVendor",
        "makerModel", "makerSession", "issuedAt", "nonce", "keyId",
    }
    row = _exact_keys(value, expected | {"signature"}, "maker provenance")
    unsigned = {key: row[key] for key in expected}
    if not REPO_RE.fullmatch(str(unsigned["repository"])):
        raise BrokerError("UNVERIFIED", "maker provenance repository is invalid")
    if type(unsigned["pullRequest"]) is not int or unsigned["pullRequest"] <= 0:
        raise BrokerError("UNVERIFIED", "maker provenance pull request is invalid")
    if not SHA_RE.fullmatch(str(unsigned["headSha"])):
        raise BrokerError("UNVERIFIED", "maker provenance head is invalid")
    if not SHA_RE.fullmatch(str(unsigned["baseSha"])):
        raise BrokerError("UNVERIFIED", "maker provenance base is invalid")
    for name in ("makerVendor", "makerModel", "makerSession"):
        if not SAFE_TEXT_RE.fullmatch(str(unsigned[name])):
            raise BrokerError("UNVERIFIED", f"maker provenance {name} is invalid")
    if not NONCE_RE.fullmatch(str(unsigned["nonce"])):
        raise BrokerError("UNVERIFIED", "maker provenance nonce is invalid")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", str(unsigned["keyId"])):
        raise BrokerError("UNVERIFIED", "maker provenance keyId is invalid")
    if not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
        str(unsigned["issuedAt"]),
    ):
        raise BrokerError("UNVERIFIED", "maker provenance issuedAt is not canonical")
    return unsigned


def validate_provenance_key_record(
    value: dict[str, Any], provenance: dict[str, Any], policy: dict[str, Any]
) -> bytes:
    fields = set(policy["provenance"]["keyRegistryRecordFields"])
    row = _exact_keys(value, fields, "provenance key registry record")
    if (
        row["repository"] != provenance["repository"]
        or row["keyId"] != provenance["keyId"]
        or row["authorizedMakerVendor"] != provenance["makerVendor"]
        or row["authorizedMakerModel"] != provenance["makerModel"]
        or row["status"] != policy["provenance"]["acceptedKeyStatus"]
        or not SAFE_TEXT_RE.fullmatch(str(row["issuerPrincipal"]))
    ):
        raise BrokerError(
            "UNVERIFIED", "provenance key authorization does not match maker"
        )
    return b64url_decode(str(row["publicKey"]), 32, "Ed25519 public key")


def verify_provenance(
    value: dict[str, Any], keyring: dict[str, dict[str, Any]],
    policy: dict[str, Any],
    current_time: dt.datetime | None = None,
) -> dict[str, Any]:
    unsigned = provenance_payload(value)
    record = keyring.get(str(unsigned["keyId"]))
    if not isinstance(record, dict):
        raise BrokerError("UNVERIFIED", "maker provenance keyId is not trusted")
    public_key = validate_provenance_key_record(record, unsigned, policy)
    supplied = b64url_decode(str(value["signature"]), 64, "Ed25519 signature")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            supplied, canonical_json(unsigned)
        )
    except (ValueError, InvalidSignature) as exc:
        raise BrokerError("UNVERIFIED", "maker provenance signature mismatch")
    issued = parse_iso(str(unsigned["issuedAt"]))
    current = current_time or dt.datetime.now(dt.timezone.utc)
    skew = abs((current - issued).total_seconds())
    if skew > policy["provenance"]["maxClockSkewSeconds"]:
        raise BrokerError("UNVERIFIED", "maker provenance is stale or future-dated")
    return unsigned


def sign_provenance(
    unsigned: dict[str, Any], key: bytes | Ed25519PrivateKey
) -> dict[str, Any]:
    unsigned = provenance_payload({**unsigned, "signature": "A" * 86})
    try:
        signer = (
            key
            if isinstance(key, Ed25519PrivateKey)
            else Ed25519PrivateKey.from_private_bytes(key)
        )
        signature = signer.sign(canonical_json(unsigned))
    except (TypeError, ValueError) as exc:
        raise BrokerError("UNVERIFIED", "Ed25519 private key is invalid") from exc
    value = dict(unsigned)
    value["signature"] = b64url(signature)
    return value


class BrokerStore:
    """SQLite evidence, replay and atomic-budget store."""

    def __init__(
        self,
        path: Path | str,
        *,
        policy: dict[str, Any] | None = None,
        provenance_keyring: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        frozen = load_policy() if policy is None else validate_policy(policy)
        self.policy = frozen
        self.reservation_microusd = int(
            frozen["budget"]["reservationMicrousd"]
        )
        self.monthly_microusd = int(frozen["budget"]["monthlyMicrousd"])
        supplied_keyring = {} if provenance_keyring is None else provenance_keyring
        if not isinstance(supplied_keyring, dict):
            raise BrokerError("UNVERIFIED", "provenance keyring is invalid")
        self.provenance_keyring: dict[str, dict[str, Any]] = {}
        for key_id, record in supplied_keyring.items():
            if (
                not isinstance(key_id, str)
                or not isinstance(record, dict)
                or record.get("keyId") != key_id
            ):
                raise BrokerError(
                    "UNVERIFIED", "provenance keyring record is not exact"
                )
            canonical_json(record)
            self.provenance_keyring[key_id] = dict(record)
        self.path = str(path)
        self._lock = threading.RLock()
        self.db = sqlite3.connect(
            self.path,
            timeout=30,
            isolation_level=None,
            check_same_thread=False,
        )
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=30000")
        if self.path != ":memory:":
            self.db.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def close(self) -> None:
        with self._lock:
            self.db.close()

    def _migrate(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS webhook_deliveries (
              body_sha256 TEXT PRIMARY KEY,
              delivery_id TEXT NOT NULL UNIQUE,
              derived_event_type TEXT NOT NULL,
              received_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS repositories (
              repository TEXT PRIMARY KEY,
              expected_app_id INTEGER NOT NULL,
              enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
              enrolled_at TEXT NOT NULL,
              active_receipt_sha256 TEXT
            );
            CREATE TABLE IF NOT EXISTS enrollment_receipts (
              receipt_sha256 TEXT PRIMARY KEY,
              repository TEXT NOT NULL,
              expected_app_id INTEGER NOT NULL,
              receipt_json TEXT NOT NULL UNIQUE,
              observed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS enrollment_events (
              event_id INTEGER PRIMARY KEY AUTOINCREMENT,
              repository TEXT NOT NULL,
              event_type TEXT NOT NULL
                CHECK(event_type IN ('enabled','disabled')),
              receipt_sha256 TEXT NOT NULL,
              reason TEXT,
              observed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS provenance (
              repository TEXT NOT NULL,
              pull_request INTEGER NOT NULL,
              head_sha TEXT NOT NULL,
              base_sha TEXT NOT NULL,
              maker_vendor TEXT NOT NULL,
              maker_model TEXT NOT NULL,
              maker_session TEXT NOT NULL,
              issued_at TEXT NOT NULL,
              nonce TEXT NOT NULL,
              key_id TEXT NOT NULL,
              payload_sha256 TEXT NOT NULL,
              signature_sha256 TEXT NOT NULL,
              PRIMARY KEY(repository, pull_request, head_sha, base_sha)
            );
            CREATE TABLE IF NOT EXISTS provenance_nonces (
              repository TEXT NOT NULL,
              key_id TEXT NOT NULL,
              nonce TEXT NOT NULL,
              payload_sha256 TEXT NOT NULL,
              received_at TEXT NOT NULL,
              PRIMARY KEY(repository,key_id,nonce)
            );
            CREATE TABLE IF NOT EXISTS budget_v2 (
              period TEXT PRIMARY KEY,
              reserved_microusd INTEGER NOT NULL CHECK(reserved_microusd >= 0),
              spent_microusd INTEGER NOT NULL CHECK(spent_microusd >= 0)
            );
            CREATE TABLE IF NOT EXISTS reservations_v2 (
              reservation_id TEXT PRIMARY KEY,
              period TEXT NOT NULL,
              reviewer_id TEXT NOT NULL,
              candidate_manifest_sha256 TEXT NOT NULL,
              amount_microusd INTEGER NOT NULL CHECK(amount_microusd > 0),
              status TEXT NOT NULL CHECK(status IN ('reserved','settled','uncertain')),
              observed_microusd INTEGER,
              usage_json TEXT,
              settlement_json TEXT,
              settlement_sha256 TEXT,
              created_at TEXT NOT NULL,
              settled_at TEXT
            );
            CREATE TABLE IF NOT EXISTS reviews (
              receipt_id TEXT PRIMARY KEY,
              repository TEXT NOT NULL,
              pull_request INTEGER NOT NULL,
              head_sha TEXT NOT NULL,
              base_sha TEXT NOT NULL,
              installation_id INTEGER NOT NULL,
              check_run_id INTEGER,
              status TEXT NOT NULL,
              conclusion TEXT NOT NULL,
              provider_id TEXT,
              checker_model TEXT,
              candidate_manifest_sha256 TEXT,
              sanitized_diff_sha256 TEXT,
              verdict_sha256 TEXT,
              prompt TEXT,
              verdict_json TEXT,
              usage_json TEXT,
              cost_usd REAL,
              evidence_sha256 TEXT NOT NULL,
              observed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reviews_v3 (
              receipt_id TEXT PRIMARY KEY,
              repository TEXT NOT NULL,
              subject_type TEXT NOT NULL,
              pull_request INTEGER NOT NULL,
              head_sha TEXT NOT NULL,
              base_sha TEXT NOT NULL,
              installation_id INTEGER NOT NULL,
              check_run_id INTEGER NOT NULL UNIQUE,
              check_run_app_id INTEGER NOT NULL,
              check_run_external_id TEXT NOT NULL UNIQUE,
              receipt_json TEXT NOT NULL,
              candidate_manifest_json TEXT NOT NULL,
              verdict_json TEXT NOT NULL,
              budget_settlement_json TEXT NOT NULL,
              external_id_payload_json TEXT NOT NULL,
              sanitized_prompt TEXT NOT NULL,
              evidence_sha256 TEXT NOT NULL,
              observed_at TEXT NOT NULL,
              UNIQUE(repository,subject_type,pull_request,head_sha,base_sha)
            );
            CREATE TABLE IF NOT EXISTS review_preparations (
              preparation_id TEXT PRIMARY KEY,
              repository TEXT NOT NULL,
              subject_type TEXT NOT NULL,
              pull_request INTEGER NOT NULL,
              head_sha TEXT NOT NULL,
              base_sha TEXT NOT NULL,
              installation_id INTEGER NOT NULL,
              check_run_id INTEGER NOT NULL UNIQUE,
              check_run_app_id INTEGER NOT NULL,
              check_run_external_id TEXT NOT NULL UNIQUE,
              receipt_template_json TEXT NOT NULL,
              candidate_manifest_json TEXT NOT NULL,
              verdict_json TEXT NOT NULL,
              budget_settlement_json TEXT NOT NULL,
              external_id_payload_json TEXT NOT NULL,
              sanitized_prompt TEXT NOT NULL,
              provider_request_sha256 TEXT NOT NULL,
              provider_request_bytes INTEGER NOT NULL,
              evidence_sha256 TEXT NOT NULL,
              state TEXT NOT NULL
                CHECK(state IN ('prepared','finalized','failed')),
              prepared_at TEXT NOT NULL,
              finalized_at TEXT,
              failure_reason TEXT,
              UNIQUE(repository,subject_type,pull_request,head_sha,base_sha)
            );
            CREATE TABLE IF NOT EXISTS failure_preparations (
              preparation_id TEXT PRIMARY KEY,
              repository TEXT NOT NULL,
              subject_type TEXT NOT NULL,
              pull_request INTEGER NOT NULL,
              head_sha TEXT NOT NULL,
              base_sha TEXT NOT NULL,
              installation_id INTEGER NOT NULL,
              check_run_id INTEGER NOT NULL UNIQUE,
              check_run_app_id INTEGER NOT NULL,
              check_run_external_id TEXT NOT NULL UNIQUE,
              payload_json TEXT NOT NULL UNIQUE,
              review_preparation_id TEXT,
              state TEXT NOT NULL
                CHECK(state IN ('prepared','finalized')),
              prepared_at TEXT NOT NULL,
              observed_at TEXT,
              FOREIGN KEY(review_preparation_id)
                REFERENCES review_preparations(preparation_id)
            );
            CREATE TABLE IF NOT EXISTS jobs (
              job_id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_id TEXT NOT NULL UNIQUE,
              repository TEXT NOT NULL,
              pull_request INTEGER NOT NULL,
              head_sha TEXT NOT NULL,
              base_sha TEXT NOT NULL,
              installation_id INTEGER NOT NULL,
              status TEXT NOT NULL
                CHECK(status IN ('waiting','queued','running','completed','failed')),
              attempts INTEGER NOT NULL DEFAULT 0,
              result_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS jobs_exact_candidate_once
              ON jobs(repository,pull_request,head_sha,base_sha);
            """
        )
        repository_columns = {
            row["name"]
            for row in self.db.execute("PRAGMA table_info(repositories)")
        }
        if "active_receipt_sha256" not in repository_columns:
            self.db.execute(
                "ALTER TABLE repositories ADD COLUMN active_receipt_sha256 TEXT"
            )

    @contextlib.contextmanager
    def immediate(self) -> Iterable[sqlite3.Connection]:
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
            except Exception:
                self.db.execute("ROLLBACK")
                raise
            else:
                self.db.execute("COMMIT")

    @staticmethod
    def _insert_job(
        db: sqlite3.Connection,
        source_id: str,
        coordinates: Coordinates,
    ) -> bool:
        coordinates.validate()
        try:
            db.execute(
                """
                INSERT INTO jobs(
                  source_id,repository,pull_request,head_sha,base_sha,
                  installation_id,status,attempts,result_json,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,'waiting',0,NULL,?,?)
                """,
                (
                    source_id,
                    coordinates.repository,
                    coordinates.pull_request,
                    coordinates.head_sha,
                    coordinates.base_sha,
                    coordinates.installation_id,
                    now_iso(),
                    now_iso(),
                ),
            )
        except sqlite3.IntegrityError:
            return False
        return True

    def record_delivery_candidate(
        self,
        delivery_id: str,
        event: str,
        action: str,
        payload_sha256: str,
        coordinates: Coordinates,
    ) -> bool:
        del action
        if not DELIVERY_RE.fullmatch(delivery_id):
            raise BrokerError("UNVERIFIED", "GitHub delivery id is malformed")
        if not re.fullmatch(r"[0-9a-f]{64}", payload_sha256 or ""):
            raise BrokerError("UNVERIFIED", "authenticated webhook digest is invalid")
        if event not in self.policy["github"]["webhooks"]["accepted"]:
            raise BrokerError("UNVERIFIED", "derived webhook event is unsupported")
        coordinates.validate()
        with self.immediate() as db:
            same_body = db.execute(
                """
                SELECT delivery_id,derived_event_type FROM webhook_deliveries
                WHERE body_sha256=?
                """,
                (payload_sha256,),
            ).fetchone()
            if same_body is not None:
                return False
            same_delivery = db.execute(
                """
                SELECT body_sha256 FROM webhook_deliveries
                WHERE delivery_id=?
                """,
                (delivery_id,),
            ).fetchone()
            if same_delivery is not None:
                raise BrokerError(
                    "UNVERIFIED",
                    "GitHub delivery id was reused for a different authenticated body",
                )
            try:
                db.execute(
                    "INSERT INTO webhook_deliveries VALUES (?,?,?,?)",
                    (payload_sha256, delivery_id, event, now_iso()),
                )
            except sqlite3.IntegrityError as exc:
                raise BrokerError(
                    "UNVERIFIED", "authenticated webhook replay conflict"
                ) from exc
            inserted_job = self._insert_job(
                db, f"github-body:{payload_sha256}", coordinates
            )
        return inserted_job

    def enroll(self, receipt: dict[str, Any]) -> str:
        """Atomically enable one exact, schema-validated enrollment receipt.

        An active receipt is immutable.  App or ruleset rotation therefore
        requires an explicit disable before a fresh receipt can be persisted
        and activated.  Historical receipts and state transitions are never
        overwritten.
        """
        validate_runtime_record("enrollmentReceipt", receipt)
        repository = receipt["repository"]
        expected_app_id = receipt["requiredStatusChecks"]["externalReview"][
            "integrationId"
        ]
        if receipt["policyId"] != self.policy["id"]:
            raise BrokerError("UNVERIFIED", "enrollment policy id differs")
        serialized = canonical_json(receipt).decode("utf-8")
        receipt_sha256 = sha256_bytes(serialized.encode("utf-8"))
        observed_at = now_iso()
        with self.immediate() as db:
            current = db.execute(
                """
                SELECT expected_app_id,enabled,active_receipt_sha256
                FROM repositories WHERE repository=?
                """,
                (repository,),
            ).fetchone()
            if current is not None and current["enabled"] == 1:
                if (
                    current["expected_app_id"] == expected_app_id
                    and current["active_receipt_sha256"] == receipt_sha256
                ):
                    stored_active = db.execute(
                        """
                        SELECT repository,expected_app_id,receipt_json
                        FROM enrollment_receipts WHERE receipt_sha256=?
                        """,
                        (receipt_sha256,),
                    ).fetchone()
                    if (
                        stored_active is None
                        or stored_active["repository"] != repository
                        or stored_active["expected_app_id"] != expected_app_id
                        or stored_active["receipt_json"] != serialized
                    ):
                        raise BrokerError(
                            "UNVERIFIED",
                            "active enrollment has no matching immutable receipt",
                        )
                    return receipt_sha256
                raise BrokerError(
                    "UNVERIFIED",
                    "active enrollment is immutable; disable before rotation",
                )
            if (
                current is not None
                and current["active_receipt_sha256"] == receipt_sha256
            ):
                raise BrokerError(
                    "UNVERIFIED",
                    "disabled enrollment requires a freshly validated receipt",
                )
            try:
                db.execute(
                    """
                    INSERT INTO enrollment_receipts(
                      receipt_sha256,repository,expected_app_id,receipt_json,
                      observed_at
                    ) VALUES (?,?,?,?,?)
                    """,
                    (
                        receipt_sha256,
                        repository,
                        expected_app_id,
                        serialized,
                        observed_at,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                stored = db.execute(
                    """
                    SELECT repository,expected_app_id,receipt_json
                    FROM enrollment_receipts WHERE receipt_sha256=?
                    """,
                    (receipt_sha256,),
                ).fetchone()
                if (
                    stored is None
                    or stored["repository"] != repository
                    or stored["expected_app_id"] != expected_app_id
                    or stored["receipt_json"] != serialized
                ):
                    raise BrokerError(
                        "UNVERIFIED", "enrollment receipt identity conflict"
                    ) from exc
            if current is None:
                db.execute(
                    """
                    INSERT INTO repositories(
                      repository,expected_app_id,enabled,enrolled_at,
                      active_receipt_sha256
                    ) VALUES (?,?,1,?,?)
                    """,
                    (
                        repository,
                        expected_app_id,
                        observed_at,
                        receipt_sha256,
                    ),
                )
            else:
                db.execute(
                    """
                    UPDATE repositories
                    SET expected_app_id=?,enabled=1,enrolled_at=?,
                        active_receipt_sha256=?
                    WHERE repository=? AND enabled=0
                    """,
                    (
                        expected_app_id,
                        observed_at,
                        receipt_sha256,
                        repository,
                    ),
                )
                if db.execute("SELECT changes()").fetchone()[0] != 1:
                    raise BrokerError(
                        "UNVERIFIED", "enrollment activation race detected"
                    )
            db.execute(
                """
                INSERT INTO enrollment_events(
                  repository,event_type,receipt_sha256,reason,observed_at
                ) VALUES (?,'enabled',?,NULL,?)
                """,
                (repository, receipt_sha256, observed_at),
            )
        return receipt_sha256

    def disable_enrollment(
        self,
        repository: str,
        active_receipt_sha256: str,
        reason: str,
    ) -> None:
        if (
            not REPO_RE.fullmatch(repository or "")
            or not re.fullmatch(r"[0-9a-f]{64}", active_receipt_sha256 or "")
            or not SAFE_TEXT_RE.fullmatch(reason or "")
        ):
            raise BrokerError("UNVERIFIED", "invalid enrollment disable request")
        observed_at = now_iso()
        with self.immediate() as db:
            current = db.execute(
                """
                SELECT enabled,active_receipt_sha256 FROM repositories
                WHERE repository=?
                """,
                (repository,),
            ).fetchone()
            if (
                current is None
                or current["enabled"] != 1
                or current["active_receipt_sha256"] != active_receipt_sha256
            ):
                raise BrokerError(
                    "UNVERIFIED", "enrollment disable target is not exact"
                )
            db.execute(
                """
                UPDATE repositories SET enabled=0
                WHERE repository=? AND enabled=1 AND active_receipt_sha256=?
                """,
                (repository, active_receipt_sha256),
            )
            if db.execute("SELECT changes()").fetchone()[0] != 1:
                raise BrokerError(
                    "UNVERIFIED", "enrollment disable race detected"
                )
            db.execute(
                """
                INSERT INTO enrollment_events(
                  repository,event_type,receipt_sha256,reason,observed_at
                ) VALUES (?,'disabled',?,?,?)
                """,
                (repository, active_receipt_sha256, reason, observed_at),
            )

    def require_enrolled(self, repository: str, app_id: int) -> None:
        with self._lock:
            row = self.db.execute(
                """
                SELECT r.expected_app_id,r.enabled,r.active_receipt_sha256,
                       e.repository AS receipt_repository,
                       e.expected_app_id AS receipt_app_id
                FROM repositories AS r
                LEFT JOIN enrollment_receipts AS e
                  ON e.receipt_sha256=r.active_receipt_sha256
                WHERE r.repository=?
                """,
                (repository,),
            ).fetchone()
        if (
            row is None
            or row["enabled"] != 1
            or row["active_receipt_sha256"] is None
            or row["receipt_repository"] != repository
            or row["receipt_app_id"] != row["expected_app_id"]
        ):
            raise BrokerError("UNVERIFIED", "repository is not enrolled in broker")
        if row["expected_app_id"] != app_id:
            raise BrokerError("UNVERIFIED", "repository expects a different GitHub App")

    def enrollment_app_id(self, repository: str) -> int:
        """Return the App integration id bound by the active enrollment receipt."""
        with self._lock:
            row = self.db.execute(
                """
                SELECT r.expected_app_id,r.enabled,r.active_receipt_sha256,
                       e.repository AS receipt_repository,
                       e.expected_app_id AS receipt_app_id
                FROM repositories AS r
                LEFT JOIN enrollment_receipts AS e
                  ON e.receipt_sha256=r.active_receipt_sha256
                WHERE r.repository=?
                """,
                (repository,),
            ).fetchone()
        if (
            row is None
            or row["enabled"] != 1
            or row["active_receipt_sha256"] is None
            or row["receipt_repository"] != repository
            or row["receipt_app_id"] != row["expected_app_id"]
            or type(row["expected_app_id"]) is not int
            or row["expected_app_id"] <= 0
        ):
            raise BrokerError("UNVERIFIED", "repository is not enrolled in broker")
        return int(row["expected_app_id"])

    def enrollment_status(
        self, repository: str, app_id: int
    ) -> dict[str, Any]:
        self.require_enrolled(repository, app_id)
        with self._lock:
            row = self.db.execute(
                """
                SELECT active_receipt_sha256,enrolled_at
                FROM repositories
                WHERE repository=? AND expected_app_id=? AND enabled=1
                """,
                (repository, app_id),
            ).fetchone()
        if (
            row is None
            or not re.fullmatch(
                r"[0-9a-f]{64}",
                str(row["active_receipt_sha256"] or ""),
            )
            or not isinstance(row["enrolled_at"], str)
        ):
            raise BrokerError(
                "UNVERIFIED", "repository enrollment status is unavailable"
            )
        return {
            "repository": repository,
            "appId": app_id,
            "receiptSha256": row["active_receipt_sha256"],
            "enrolledAt": row["enrolled_at"],
        }

    def put_provenance_and_queue(
        self,
        signed_record: dict[str, Any],
        coordinates: Coordinates,
    ) -> bool:
        coordinates.validate()
        value = verify_provenance(
            signed_record,
            self.provenance_keyring,
            self.policy,
        )
        supplied_signature = str(signed_record["signature"])
        if (
            coordinates.repository != value["repository"]
            or coordinates.pull_request != value["pullRequest"]
            or coordinates.head_sha != value["headSha"]
            or coordinates.base_sha != value["baseSha"]
        ):
            raise BrokerError(
                "UNVERIFIED", "provenance/job coordinates differ"
            )
        payload_sha256 = sha256_bytes(canonical_json(signed_record))
        fields = (
            value["repository"], value["pullRequest"], value["headSha"],
            value["baseSha"], value["makerVendor"], value["makerModel"],
            value["makerSession"], value["issuedAt"], value["nonce"],
            value["keyId"],
            payload_sha256,
            sha256_bytes(supplied_signature.encode("ascii")),
        )
        with self.immediate() as db:
            try:
                db.execute(
                    """
                    INSERT INTO provenance_nonces(
                      repository,key_id,nonce,payload_sha256,received_at
                    ) VALUES (?,?,?,?,?)
                    """,
                    (
                        value["repository"],
                        value["keyId"],
                        value["nonce"],
                        payload_sha256,
                        now_iso(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise BrokerError(
                    "UNVERIFIED",
                    "maker provenance nonce replay rejected without enqueue",
                ) from exc
            inserted_provenance = True
            try:
                db.execute(
                    """
                    INSERT INTO provenance(
                      repository,pull_request,head_sha,base_sha,maker_vendor,
                      maker_model,maker_session,issued_at,nonce,key_id,
                      payload_sha256,signature_sha256
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    fields,
                )
            except sqlite3.IntegrityError as exc:
                inserted_provenance = False
                existing = db.execute(
                    """
                    SELECT payload_sha256 FROM provenance
                    WHERE repository=? AND pull_request=? AND head_sha=? AND base_sha=?
                    """,
                    fields[:4],
                ).fetchone()
                if not (
                    existing
                    and existing["payload_sha256"] == fields[10]
                ):
                    raise BrokerError(
                        "UNVERIFIED",
                        "maker provenance nonce/coordinate replay conflict",
                    ) from exc
            queued = db.execute(
                """
                UPDATE jobs SET status='queued',updated_at=?
                WHERE repository=? AND pull_request=? AND head_sha=? AND base_sha=?
                  AND status='waiting'
                """,
                (
                    now_iso(),
                    coordinates.repository,
                    coordinates.pull_request,
                    coordinates.head_sha,
                    coordinates.base_sha,
                ),
            ).rowcount
            existing_job = db.execute(
                """
                SELECT 1 FROM jobs
                WHERE repository=? AND pull_request=? AND head_sha=? AND base_sha=?
                """,
                (
                    coordinates.repository,
                    coordinates.pull_request,
                    coordinates.head_sha,
                    coordinates.base_sha,
                ),
            ).fetchone()
            if existing_job is None:
                raise BrokerError(
                    "UNVERIFIED",
                    "provenance has no exact signed webhook candidate",
                )
        return inserted_provenance or queued == 1

    def latest_installation(
        self, repository: str, pull_request: int, head_sha: str, base_sha: str
    ) -> int:
        with self._lock:
            row = self.db.execute(
                """
                SELECT installation_id FROM jobs
                WHERE repository=? AND pull_request=? AND head_sha=? AND base_sha=?
                ORDER BY job_id DESC LIMIT 1
                """,
                (repository, pull_request, head_sha, base_sha),
            ).fetchone()
        if row is None:
            raise BrokerError(
                "UNVERIFIED",
                "no signed GitHub webhook exists for these provenance coordinates",
            )
        return int(row["installation_id"])

    def waiting_merge_groups(
        self, repository: str
    ) -> list[Coordinates]:
        if not REPO_RE.fullmatch(repository or ""):
            raise BrokerError(
                "UNVERIFIED", "merge-group repository is invalid"
            )
        with self._lock:
            rows = self.db.execute(
                """
                SELECT repository,pull_request,head_sha,base_sha,installation_id
                FROM jobs
                WHERE repository=? AND pull_request=0 AND status='waiting'
                ORDER BY job_id
                LIMIT 101
                """,
                (repository,),
            ).fetchall()
        if len(rows) > 100:
            raise BrokerError(
                "UNAVAILABLE", "too many waiting merge groups"
            )
        return [
            Coordinates(
                row["repository"],
                int(row["pull_request"]),
                row["head_sha"],
                row["base_sha"],
                int(row["installation_id"]),
            ).validate()
            for row in rows
        ]

    def waiting_merge_group_repositories(self) -> list[str]:
        with self._lock:
            rows = self.db.execute(
                """
                SELECT DISTINCT repository FROM jobs
                WHERE pull_request=0 AND status='waiting'
                ORDER BY repository
                LIMIT 101
                """
            ).fetchall()
        if len(rows) > 100:
            raise BrokerError(
                "UNAVAILABLE", "too many repositories have waiting merge groups"
            )
        repositories = [str(row["repository"]) for row in rows]
        if any(not REPO_RE.fullmatch(value) for value in repositories):
            raise BrokerError(
                "UNVERIFIED", "waiting merge-group repository is invalid"
            )
        return repositories

    def claim(self) -> tuple[int, Coordinates] | None:
        with self.immediate() as db:
            row = db.execute(
                """
                SELECT * FROM jobs WHERE status='queued'
                ORDER BY job_id LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            changed = db.execute(
                """
                UPDATE jobs SET status='running',attempts=attempts+1,updated_at=?
                WHERE job_id=? AND status='queued'
                """,
                (now_iso(), row["job_id"]),
            ).rowcount
            if changed != 1:
                return None
        return int(row["job_id"]), Coordinates(
            repository=row["repository"],
            pull_request=int(row["pull_request"]),
            head_sha=row["head_sha"],
            base_sha=row["base_sha"],
            installation_id=int(row["installation_id"]),
        ).validate()

    def finish_job(
        self, job_id: int, success: bool, result: dict[str, Any]
    ) -> None:
        with self._lock:
            self.db.execute(
                """
                UPDATE jobs SET status=?,result_json=?,updated_at=? WHERE job_id=?
                """,
                (
                    "completed" if success else "failed",
                    json.dumps(result, ensure_ascii=False, sort_keys=True),
                    now_iso(),
                    job_id,
                ),
            )

    def job_result(self, source_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.db.execute(
                "SELECT status,result_json FROM jobs WHERE source_id=?",
                (source_id,),
            ).fetchone()
        if row is None:
            return None
        result = (
            json.loads(row["result_json"])
            if row["result_json"] is not None
            else None
        )
        return {"status": row["status"], "result": result}

    def get_provenance(self, coordinates: Coordinates) -> dict[str, Any]:
        with self._lock:
            row = self.db.execute(
                """
                SELECT * FROM provenance
                WHERE repository=? AND pull_request=? AND head_sha=? AND base_sha=?
                """,
                (
                    coordinates.repository, coordinates.pull_request,
                    coordinates.head_sha, coordinates.base_sha,
                ),
            ).fetchone()
        if row is None:
            raise BrokerError(
                "UNVERIFIED", "exact-head/base maker provenance is unavailable"
            )
        return {
            "vendor": row["maker_vendor"],
            "model": row["maker_model"],
            "session": row["maker_session"],
            "issuedAt": row["issued_at"],
            "payloadSha256": row["payload_sha256"],
        }

    def get_component_provenance(
        self, components: list[Coordinates]
    ) -> list[dict[str, Any]]:
        if (
            not isinstance(components, list)
            or not 1 <= len(components) <= 100
        ):
            raise BrokerError(
                "UNVERIFIED", "merge-group provenance components are invalid"
            )
        seen: set[tuple[str, int, str, str]] = set()
        result: list[dict[str, Any]] = []
        repository: str | None = None
        for coordinates in components:
            coordinates.validate()
            if coordinates.pull_request <= 0:
                raise BrokerError(
                    "UNVERIFIED",
                    "merge-group provenance requires exact PR coordinates",
                )
            if repository is None:
                repository = coordinates.repository
            elif coordinates.repository != repository:
                raise BrokerError(
                    "UNVERIFIED",
                    "merge-group provenance crosses repositories",
                )
            identity = (
                coordinates.repository,
                coordinates.pull_request,
                coordinates.head_sha,
                coordinates.base_sha,
            )
            if identity in seen:
                raise BrokerError(
                    "UNVERIFIED", "duplicate merge-group PR coordinate"
                )
            seen.add(identity)
            result.append(self.get_provenance(coordinates))
        return result

    def queue_merge_group(
        self,
        coordinates: Coordinates,
        components: list[Coordinates],
    ) -> list[dict[str, Any]]:
        """Atomically bind a merge-group job to homogeneous exact PR makers."""
        coordinates.validate()
        if (
            coordinates.pull_request != 0
            or not isinstance(components, list)
            or not 1 <= len(components) <= 100
        ):
            raise BrokerError(
                "UNVERIFIED", "merge-group queue coordinates are invalid"
            )
        result: list[dict[str, Any]] = []
        identities: set[tuple[str, str]] = set()
        seen: set[tuple[int, str, str]] = set()
        with self.immediate() as db:
            for component in components:
                component.validate()
                identity = (
                    component.pull_request,
                    component.head_sha,
                    component.base_sha,
                )
                if (
                    component.pull_request <= 0
                    or component.repository != coordinates.repository
                    or component.installation_id != coordinates.installation_id
                    or identity in seen
                ):
                    raise BrokerError(
                        "UNVERIFIED",
                        "merge-group PR components are not exact and unique",
                    )
                seen.add(identity)
                row = db.execute(
                    """
                    SELECT maker_vendor,maker_model,maker_session,issued_at,
                           payload_sha256
                    FROM provenance
                    WHERE repository=? AND pull_request=?
                      AND head_sha=? AND base_sha=?
                    """,
                    (
                        component.repository,
                        component.pull_request,
                        component.head_sha,
                        component.base_sha,
                    ),
                ).fetchone()
                if row is None:
                    raise BrokerError(
                        "UNVERIFIED",
                        "merge-group component provenance is unavailable",
                    )
                identities.add(
                    (
                        row["maker_vendor"].strip().casefold(),
                        row["maker_model"].strip().casefold(),
                    )
                )
                result.append(
                    {
                        "vendor": row["maker_vendor"],
                        "model": row["maker_model"],
                        "session": row["maker_session"],
                        "issuedAt": row["issued_at"],
                        "payloadSha256": row["payload_sha256"],
                    }
                )
            if len(identities) != 1:
                raise BrokerError(
                    "UNVERIFIED",
                    "mixed merge-group makers cannot use an automatic route",
                )
            maker = result[0]
            maker_class = classify_maker(
                maker["vendor"], maker["model"], self.policy
            )
            select_reviewer(
                maker_class, maker["vendor"], maker["model"], self.policy
            )
            queued = db.execute(
                """
                UPDATE jobs SET status='queued',updated_at=?
                WHERE repository=? AND pull_request=0
                  AND head_sha=? AND base_sha=? AND installation_id=?
                  AND status='waiting'
                """,
                (
                    now_iso(),
                    coordinates.repository,
                    coordinates.head_sha,
                    coordinates.base_sha,
                    coordinates.installation_id,
                ),
            ).rowcount
            if queued != 1:
                raise BrokerError(
                    "UNVERIFIED",
                    "merge-group provenance has no exact waiting webhook job",
                )
        return result

    def reserve(
        self,
        reviewer_id: str,
        candidate_manifest_sha256: str,
        amount_microusd: int | None = None,
    ) -> str:
        if reviewer_id not in self.policy["routing"]["reviewers"]:
            raise BrokerError("UNAVAILABLE", "reviewer pricing is unavailable")
        if not re.fullmatch(r"[0-9a-f]{64}", candidate_manifest_sha256 or ""):
            raise BrokerError(
                "UNVERIFIED", "candidate manifest digest is invalid"
            )
        amount = (
            self.reservation_microusd
            if amount_microusd is None
            else amount_microusd
        )
        if type(amount) is not int or amount <= 0:
            raise BrokerError(
                "UNVERIFIED", "reviewer reservation amount is invalid"
            )
        if amount != self.reservation_microusd:
            per_call = self.policy["budget"][
                "hierarchicalCallReservationMicrousd"
            ].get(reviewer_id)
            maximum_calls = int(
                self.policy["budget"]["maxHierarchicalProviderCalls"]
            )
            if (
                type(per_call) is not int
                or per_call <= 0
                or amount % per_call != 0
                or not 2 <= amount // per_call <= maximum_calls
            ):
                raise BrokerError(
                    "UNVERIFIED",
                    "hierarchical reviewer reservation is invalid",
                )
        reservation_id = secrets.token_hex(16)
        period = utc_period()
        with self.immediate() as db:
            db.execute(
                "INSERT OR IGNORE INTO budget_v2 VALUES (?,0,0)", (period,)
            )
            row = db.execute(
                """
                SELECT reserved_microusd,spent_microusd
                FROM budget_v2 WHERE period=?
                """,
                (period,),
            ).fetchone()
            if (
                row is None
                or row["reserved_microusd"] + row["spent_microusd"] + amount
                > self.monthly_microusd
            ):
                raise BrokerError("UNAVAILABLE", "monthly reviewer budget exhausted")
            db.execute(
                """
                UPDATE budget_v2
                SET reserved_microusd=reserved_microusd+?
                WHERE period=?
                """,
                (amount, period),
            )
            db.execute(
                """
                INSERT INTO reservations_v2(
                  reservation_id,period,reviewer_id,candidate_manifest_sha256,
                  amount_microusd,status,observed_microusd,usage_json,
                  settlement_json,settlement_sha256,created_at,settled_at
                ) VALUES (?,?,?,?,?,'reserved',NULL,NULL,NULL,NULL,?,NULL)
                """,
                (
                    reservation_id,
                    period,
                    reviewer_id,
                    candidate_manifest_sha256,
                    amount,
                    now_iso(),
                ),
            )
        return reservation_id

    def settle_uncertain(
        self,
        reservation_id: str,
        observed_usage: dict[str, int],
        ambiguous_microusd: int,
    ) -> None:
        with self.immediate() as db:
            row = db.execute(
                "SELECT * FROM reservations_v2 WHERE reservation_id=?",
                (reservation_id,),
            ).fetchone()
            if row is None or row["status"] != "reserved":
                raise BrokerError(
                    "UNVERIFIED", "budget reservation is not active"
                )
            if (
                not isinstance(observed_usage, dict)
                or set(observed_usage) != {"inputTokens", "outputTokens"}
                or any(
                    type(observed_usage[name]) is not int
                    or observed_usage[name] < 0
                    for name in ("inputTokens", "outputTokens")
                )
            ):
                raise BrokerError(
                    "UNVERIFIED", "observed reviewer usage is invalid"
                )
            allowed_caps = {
                int(self.reservation_microusd),
                *(
                    int(value)
                    for value in self.policy["budget"][
                        "hierarchicalCallReservationMicrousd"
                    ].values()
                    if type(value) is int
                ),
            }
            amount = int(row["amount_microusd"])
            if (
                type(ambiguous_microusd) is not int
                or ambiguous_microusd not in allowed_caps
                or ambiguous_microusd > amount
            ):
                raise BrokerError(
                    "UNVERIFIED", "ambiguous reviewer charge is invalid"
                )
            pricing = self.policy["routing"]["reviewers"].get(
                row["reviewer_id"]
            )
            if not isinstance(pricing, dict):
                raise BrokerError(
                    "UNAVAILABLE", "frozen reviewer pricing is unavailable"
                )
            try:
                observed_charge = int((
                    Decimal(observed_usage["inputTokens"])
                    * Decimal(str(pricing["inputUsdPerMillion"]))
                    + Decimal(observed_usage["outputTokens"])
                    * Decimal(str(pricing["outputUsdPerMillion"]))
                ).to_integral_value(rounding=ROUND_CEILING))
            except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
                raise BrokerError(
                    "UNAVAILABLE", "frozen reviewer pricing is invalid"
                ) from exc
            charge = min(amount, observed_charge + ambiguous_microusd)
            settled_at = now_iso()
            db.execute(
                """
                UPDATE budget_v2
                SET reserved_microusd=reserved_microusd-?,
                    spent_microusd=spent_microusd+?
                WHERE period=?
                """,
                (amount, charge, row["period"]),
            )
            db.execute(
                """
                UPDATE reservations_v2
                SET status='uncertain',observed_microusd=?,usage_json=?,
                    settlement_json=NULL,settlement_sha256=NULL,settled_at=?
                WHERE reservation_id=?
                """,
                (
                    charge,
                    canonical_json(observed_usage).decode("utf-8"),
                    settled_at,
                    reservation_id,
                ),
            )

    def settle(
        self, reservation_id: str, usage: dict[str, int] | None
    ) -> dict[str, Any] | None:
        overspent = False
        settlement: dict[str, Any] | None = None
        with self.immediate() as db:
            row = db.execute(
                "SELECT * FROM reservations_v2 WHERE reservation_id=?",
                (reservation_id,),
            ).fetchone()
            if row is None or row["status"] != "reserved":
                raise BrokerError("UNVERIFIED", "budget reservation is not active")
            amount = int(row["amount_microusd"])
            settled_at = now_iso()
            if usage is None:
                charge = amount
                status = "uncertain"
            else:
                if (
                    not isinstance(usage, dict)
                    or set(usage) != {"inputTokens", "outputTokens"}
                    or any(type(usage[name]) is not int or usage[name] < 0
                           for name in ("inputTokens", "outputTokens"))
                ):
                    raise BrokerError(
                        "UNVERIFIED", "primary provider usage is invalid"
                    )
                pricing = self.policy["routing"]["reviewers"].get(
                    row["reviewer_id"]
                )
                if not isinstance(pricing, dict):
                    raise BrokerError(
                        "UNAVAILABLE", "frozen reviewer pricing is unavailable"
                    )
                try:
                    charge = int((
                        Decimal(usage["inputTokens"])
                        * Decimal(str(pricing["inputUsdPerMillion"]))
                        + Decimal(usage["outputTokens"])
                        * Decimal(str(pricing["outputUsdPerMillion"]))
                    ).to_integral_value(rounding=ROUND_CEILING))
                except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
                    raise BrokerError(
                        "UNAVAILABLE", "frozen reviewer pricing is invalid"
                    ) from exc
                status = "settled"
                overspent = charge > amount
                settlement = {
                    "version": 1,
                    "reservationId": reservation_id,
                    "period": row["period"],
                    "reviewerId": row["reviewer_id"],
                    "policySha256": sha256_bytes(POLICY_PATH.read_bytes()),
                    "candidateManifestSha256":
                        row["candidate_manifest_sha256"],
                    "usage": usage,
                    "reservationMicrousd": amount,
                    "status": "settled",
                    "settledAt": settled_at,
                }
            db.execute(
                """
                UPDATE budget_v2
                SET reserved_microusd=reserved_microusd-?,
                    spent_microusd=spent_microusd+?
                WHERE period=?
                """,
                (amount, charge, row["period"]),
            )
            settlement_json = (
                canonical_json(settlement).decode("utf-8")
                if settlement is not None else None
            )
            db.execute(
                """
                UPDATE reservations_v2
                SET status=?,observed_microusd=?,usage_json=?,
                    settlement_json=?,settlement_sha256=?,settled_at=?
                WHERE reservation_id=?
                """,
                (
                    status,
                    charge,
                    canonical_json(usage).decode("utf-8")
                    if usage is not None else None,
                    settlement_json,
                    sha256_bytes(settlement_json.encode("utf-8"))
                    if settlement_json is not None else None,
                    settled_at,
                    reservation_id,
                ),
            )
        if overspent:
            raise BrokerError(
                "UNVERIFIED",
                "derived reviewer cost exceeded its reservation and was recorded",
            )
        return settlement

    def budget_status(self) -> dict[str, Any]:
        with self._lock:
            row = self.db.execute(
                """
                SELECT reserved_microusd,spent_microusd
                FROM budget_v2 WHERE period=?
                """,
                (utc_period(),),
            ).fetchone()
        return {
            "period": utc_period(),
            "reservedMicrousd": int(row["reserved_microusd"]) if row else 0,
            "spentMicrousd": int(row["spent_microusd"]) if row else 0,
        }

    def prepare_review(
        self,
        receipt_template: dict[str, Any],
        sanitized_prompt: str,
        github_api: "GitHubApi",
        installation_token: str,
        *,
        provider_request: bytes,
        candidate_manifest: dict[str, Any],
        verdict: dict[str, Any],
        budget_settlement: dict[str, Any],
        external_id_payload: dict[str, Any],
    ) -> str:
        """Durably bind complete evidence before the Check Run can pass."""
        return self._write_review(
            "prepare",
            receipt_template,
            sanitized_prompt,
            github_api,
            installation_token,
            provider_request=provider_request,
            candidate_manifest=candidate_manifest,
            verdict=verdict,
            budget_settlement=budget_settlement,
            external_id_payload=external_id_payload,
        )

    def record_review(
        self,
        receipt: dict[str, Any],
        sanitized_prompt: str,
        github_api: "GitHubApi",
        installation_token: str,
        *,
        provider_request: bytes | None,
        candidate_manifest: dict[str, Any],
        verdict: dict[str, Any],
        budget_settlement: dict[str, Any],
        external_id_payload: dict[str, Any],
    ) -> str:
        """Persist only a closed, cross-bound exact-candidate broker receipt."""
        return self._write_review(
            "finalize",
            receipt,
            sanitized_prompt,
            github_api,
            installation_token,
            provider_request=provider_request,
            candidate_manifest=candidate_manifest,
            verdict=verdict,
            budget_settlement=budget_settlement,
            external_id_payload=external_id_payload,
        )

    def _write_review(
        self,
        phase: str,
        receipt: dict[str, Any],
        sanitized_prompt: str,
        github_api: "GitHubApi",
        installation_token: str,
        *,
        provider_request: bytes | None,
        candidate_manifest: dict[str, Any],
        verdict: dict[str, Any],
        budget_settlement: dict[str, Any],
        external_id_payload: dict[str, Any],
    ) -> str:
        if phase not in {"prepare", "finalize"}:
            raise BrokerError("UNVERIFIED", "review evidence phase is invalid")
        validate_runtime_record("brokerReceipt", receipt)
        validate_runtime_record("candidateManifest", candidate_manifest)
        validate_runtime_record("budgetSettlement", budget_settlement)
        validate_runtime_record("externalIdPayload", external_id_payload)
        verdict_schema = read_json(VERDICT_SCHEMA_PATH)
        try:
            Draft202012Validator(verdict_schema).validate(verdict)
        except ValidationError as exc:
            raise BrokerError(
                "UNVERIFIED", "reviewer verdict violates its closed schema"
            ) from exc
        if not isinstance(sanitized_prompt, str):
            raise BrokerError("UNVERIFIED", "review publication evidence is invalid")
        if phase == "prepare" and not isinstance(provider_request, bytes):
            raise BrokerError("UNVERIFIED", "provider request evidence is invalid")
        if provider_request is not None and not isinstance(provider_request, bytes):
            raise BrokerError("UNVERIFIED", "provider request evidence is invalid")

        installation_id = int(receipt["installationId"])
        check_publication = receipt["checkPublication"]
        check_run_id = int(check_publication["id"])
        if not isinstance(github_api, GitHubApi):
            raise BrokerError("UNVERIFIED", "GitHub check observer is invalid")
        if not isinstance(installation_token, str) or not re.fullmatch(
            r"[^\s]{1,4096}", installation_token
        ):
            raise BrokerError(
                "UNAVAILABLE", "GitHub installation token is unavailable"
            )
        observed_check = github_api.request_json(
            "GET",
            f"/repos/{receipt['repository']}/check-runs/{check_run_id}",
            installation_token,
        )
        if not isinstance(observed_check, dict):
            raise BrokerError(
                "UNVERIFIED", "GitHub check publication was not observed"
            )
        observed_app = observed_check.get("app")
        observed_publication = {
            "id": observed_check.get("id"),
            "appIntegrationId": (
                observed_app.get("id")
                if isinstance(observed_app, dict) else None
            ),
            "name": observed_check.get("name"),
            "headSha": observed_check.get("head_sha"),
            "externalId": observed_check.get("external_id"),
            "status": observed_check.get("status"),
            "conclusion": observed_check.get("conclusion"),
        }
        if phase == "prepare":
            intended_identity = {
                key: check_publication[key]
                for key in (
                    "id",
                    "appIntegrationId",
                    "name",
                    "headSha",
                    "externalId",
                )
            }
            observed_identity = {
                key: observed_publication[key] for key in intended_identity
            }
            if (
                observed_identity != intended_identity
                or observed_publication["status"] != "in_progress"
                or observed_publication["conclusion"] is not None
            ):
                raise BrokerError(
                    "UNVERIFIED",
                    "pre-publication Check Run identity is not exact",
                )
        else:
            try:
                validate_runtime_record("checkPublication", observed_publication)
            except BrokerError as exc:
                raise BrokerError(
                    "UNVERIFIED", "GitHub check publication is incomplete"
                ) from exc
            if observed_publication != check_publication:
                raise BrokerError(
                    "UNVERIFIED", "GitHub check publication differs from receipt"
                )
        policy_sha = sha256_bytes(POLICY_PATH.read_bytes())
        candidate_sha = sha256_bytes(canonical_json(candidate_manifest))
        verdict_sha = sha256_bytes(canonical_json(verdict))
        settlement_sha = sha256_bytes(canonical_json(budget_settlement))
        external_id_sha = sha256_bytes(canonical_json(external_id_payload))
        redaction_manifest = receipt["redactionManifest"]
        redaction_sha = sha256_bytes(canonical_json(redaction_manifest))
        reservation_binding = True
        if provider_request is not None:
            request_evidence = decode_strict_json(
                provider_request, "provider request evidence"
            )
            if (
                isinstance(request_evidence, dict)
                and request_evidence.get("version") == 1
                and request_evidence.get("mode") == "hierarchical"
            ):
                if set(request_evidence) != {
                    "version",
                    "mode",
                    "plannedCalls",
                    "requests",
                }:
                    raise BrokerError(
                        "UNVERIFIED",
                        "hierarchical provider evidence is not closed",
                    )
                planned_calls = request_evidence["plannedCalls"]
                requests = request_evidence["requests"]
                maximum_calls = int(
                    self.policy["budget"][
                        "maxHierarchicalProviderCalls"
                    ]
                )
                if (
                    type(planned_calls) is not int
                    or not 2 <= planned_calls <= maximum_calls
                    or not isinstance(requests, list)
                    or not requests
                    or len(requests) > planned_calls
                ):
                    raise BrokerError(
                        "UNVERIFIED",
                        "hierarchical provider evidence coverage is invalid",
                    )
                seen_units: set[str] = set()
                for index, item in enumerate(requests):
                    if (
                        not isinstance(item, dict)
                        or set(item)
                        != {
                            "kind",
                            "unitId",
                            "sha256",
                            "bytes",
                            "outputCap",
                        }
                        or item["kind"] not in {"unit", "integration"}
                        or not re.fullmatch(
                            r"[0-9a-f]{64}", str(item["sha256"])
                        )
                        or type(item["bytes"]) is not int
                        or not 0 < item["bytes"] <= self.policy[
                            "candidate"
                        ]["maxProviderRequestBytes"]
                        or type(item["outputCap"]) is not int
                        or item["outputCap"] <= 0
                    ):
                        raise BrokerError(
                            "UNVERIFIED",
                            "hierarchical provider request evidence is invalid",
                        )
                    if item["kind"] == "unit":
                        if (
                            not isinstance(item["unitId"], str)
                            or not re.fullmatch(
                                r"unit-[0-9]{3}", item["unitId"]
                            )
                            or item["unitId"] in seen_units
                        ):
                            raise BrokerError(
                                "UNVERIFIED",
                                "hierarchical unit request evidence is invalid",
                            )
                        seen_units.add(item["unitId"])
                    elif (
                        item["unitId"] is not None
                        or index != len(requests) - 1
                    ):
                        raise BrokerError(
                            "UNVERIFIED",
                            "integration request evidence is invalid",
                        )
                if receipt["status"] == "PASSED" and (
                    len(requests) != planned_calls
                    or requests[-1]["kind"] != "integration"
                ):
                    raise BrokerError(
                        "UNVERIFIED",
                        "hierarchical success lacks complete provider coverage",
                    )
                prompt_evidence = decode_strict_json(
                    sanitized_prompt.encode("utf-8"),
                    "hierarchical sanitized prompt evidence",
                )
                if (
                    not isinstance(prompt_evidence, dict)
                    or set(prompt_evidence)
                    != {
                        "version",
                        "mode",
                        "reviewPlan",
                        "prompts",
                        "unitVerdicts",
                    }
                    or prompt_evidence["version"] != 1
                    or prompt_evidence["mode"] != "hierarchical"
                    or not isinstance(prompt_evidence["reviewPlan"], str)
                    or not isinstance(prompt_evidence["prompts"], list)
                    or any(
                        not isinstance(value, str)
                        for value in prompt_evidence["prompts"]
                    )
                    or not isinstance(
                        prompt_evidence["unitVerdicts"], list
                    )
                ):
                    raise BrokerError(
                        "UNVERIFIED",
                        "hierarchical prompt evidence is invalid",
                    )
                api_base_schema = json.loads(json.dumps(verdict_schema))
                api_base_schema.pop("$schema", None)
                api_base_schema.pop("title", None)
                api_unit_schema = json.loads(json.dumps(api_base_schema))
                api_unit_schema["properties"]["summary"] = {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 4000,
                }
                api_unit_schema["required"] = [
                    *api_unit_schema["required"],
                    "summary",
                ]
                reviewer_definition = self.policy["routing"][
                    "reviewers"
                ].get(receipt["checkerReviewerId"])
                if not isinstance(reviewer_definition, dict):
                    raise BrokerError(
                        "UNVERIFIED",
                        "hierarchical reviewer definition is unavailable",
                    )
                review_plan_bytes = prompt_evidence[
                    "reviewPlan"
                ].encode("utf-8")
                review_plan = decode_strict_json(
                    review_plan_bytes, "hierarchical review plan"
                )
                if (
                    not isinstance(review_plan, dict)
                    or set(review_plan)
                    != {
                        "version",
                        "mode",
                        "algorithm",
                        "fullDiffSha256",
                        "fullDiffBytes",
                        "unitCount",
                        "units",
                    }
                    or review_plan["version"] != 1
                    or review_plan["mode"] != "hierarchical"
                    or review_plan["algorithm"]
                    != "deterministic-complete-file-then-utf8-line-boundary"
                    or not re.fullmatch(
                        r"[0-9a-f]{64}",
                        str(review_plan["fullDiffSha256"]),
                    )
                    or type(review_plan["fullDiffBytes"]) is not int
                    or not (
                        self.policy["candidate"]["maxRawDiffBytes"]
                        < review_plan["fullDiffBytes"]
                        <= self.policy["candidate"][
                            "maxHierarchicalRawDiffBytes"
                        ]
                    )
                    or type(review_plan["unitCount"]) is not int
                    or review_plan["unitCount"] + 1 != planned_calls
                    or not isinstance(review_plan["units"], list)
                    or len(review_plan["units"])
                    != review_plan["unitCount"]
                    or sha256_bytes(review_plan_bytes)
                    != candidate_manifest["reviewDiffSha256"]
                    or len(review_plan_bytes)
                    != candidate_manifest["reviewDiffBytes"]
                ):
                    raise BrokerError(
                        "UNVERIFIED",
                        "hierarchical review plan binding is invalid",
                    )
                plan_unit_ids: list[str] = []
                total_unit_bytes = 0
                for expected_index, unit_record in enumerate(
                    review_plan["units"], start=1
                ):
                    if (
                        not isinstance(unit_record, dict)
                        or set(unit_record)
                        != {
                            "id",
                            "index",
                            "reviewDiffSha256",
                            "reviewDiffBytes",
                            "paths",
                        }
                        or unit_record["id"]
                        != f"unit-{expected_index:03d}"
                        or unit_record["index"] != expected_index
                        or not re.fullmatch(
                            r"[0-9a-f]{64}",
                            str(unit_record["reviewDiffSha256"]),
                        )
                        or type(unit_record["reviewDiffBytes"]) is not int
                        or not 0 < unit_record["reviewDiffBytes"] <= (
                            self.policy["candidate"]["maxRawDiffBytes"]
                        )
                        or not isinstance(unit_record["paths"], list)
                        or not unit_record["paths"]
                        or any(
                            not isinstance(path, str)
                            or path not in candidate_manifest["files"]
                            for path in unit_record["paths"]
                        )
                    ):
                        raise BrokerError(
                            "UNVERIFIED",
                            "hierarchical review unit binding is invalid",
                        )
                    plan_unit_ids.append(unit_record["id"])
                    total_unit_bytes += unit_record["reviewDiffBytes"]
                request_unit_ids = [
                    item["unitId"]
                    for item in requests
                    if item["kind"] == "unit"
                ]
                if (
                    total_unit_bytes != review_plan["fullDiffBytes"]
                    or request_unit_ids
                    != plan_unit_ids[:len(request_unit_ids)]
                    or len(prompt_evidence["unitVerdicts"])
                    != len(request_unit_ids)
                    or len(prompt_evidence["prompts"]) != len(requests)
                ):
                    raise BrokerError(
                        "UNVERIFIED",
                        "hierarchical review coverage does not agree",
                    )

                def prompt_field(
                    prompt: str, name: str
                ) -> Any:
                    prefix = f"{name}="
                    values = [
                        line[len(prefix):]
                        for line in prompt.splitlines()
                        if line.startswith(prefix)
                    ]
                    if len(values) != 1:
                        raise BrokerError(
                            "UNVERIFIED",
                            "hierarchical prompt field coverage is invalid",
                        )
                    return decode_strict_json(
                        values[0].encode("utf-8"),
                        f"hierarchical prompt {name}",
                    )

                candidate_binding_sha = sha256_bytes(
                    canonical_json(candidate_manifest)
                )
                plan_by_id = {
                    unit["id"]: unit for unit in review_plan["units"]
                }
                for item, prompt in zip(
                    requests, prompt_evidence["prompts"], strict=True
                ):
                    is_unit = item["kind"] == "unit"
                    response_schema = (
                        api_unit_schema if is_unit else api_base_schema
                    )
                    schema_name = (
                        "itd_hierarchical_unit_review"
                        if is_unit else "itd_external_review"
                    )
                    expected_request = canonical_provider_request(
                        reviewer_definition,
                        prompt,
                        response_schema,
                        schema_name,
                        item["outputCap"],
                    )
                    if (
                        len(expected_request) != item["bytes"]
                        or sha256_bytes(expected_request) != item["sha256"]
                    ):
                        raise BrokerError(
                            "UNVERIFIED",
                            "hierarchical request/prompt binding differs",
                        )
                    observed_schema = prompt_field(
                        prompt, "REQUIRED_JSON_SCHEMA"
                    )
                    if observed_schema != response_schema:
                        raise BrokerError(
                            "UNVERIFIED",
                            "hierarchical prompt schema differs",
                        )
                    if is_unit:
                        unit_record = plan_by_id.get(item["unitId"])
                        expected_binding = {
                            "candidateManifestSha256":
                                candidate_binding_sha,
                            "repository":
                                candidate_manifest["repository"],
                            "subjectType":
                                candidate_manifest["subjectType"],
                            "headSha": candidate_manifest["headSha"],
                            "baseSha": candidate_manifest["baseSha"],
                            "reviewPlanSha256":
                                candidate_manifest["reviewDiffSha256"],
                            "changedPaths": sorted(
                                candidate_manifest["files"],
                                key=lambda value:
                                    value.encode("utf-16-be"),
                            ),
                            "unit": unit_record,
                        }
                        unit_diff = prompt_field(
                            prompt, "UNTRUSTED_DIFF_UNIT_JSON"
                        )
                        if (
                            unit_record is None
                            or prompt_field(
                                prompt, "CANDIDATE_BINDING"
                            ) != expected_binding
                            or not isinstance(unit_diff, str)
                            or sha256_bytes(
                                unit_diff.encode("utf-8")
                            ) != unit_record["reviewDiffSha256"]
                            or len(unit_diff.encode("utf-8"))
                            != unit_record["reviewDiffBytes"]
                        ):
                            raise BrokerError(
                                "UNVERIFIED",
                                "hierarchical prompt/unit binding differs",
                            )
                    else:
                        expected_integration = {
                            "candidateManifest": candidate_manifest,
                            "reviewPlan": review_plan,
                            "unitVerdicts":
                                prompt_evidence["unitVerdicts"],
                        }
                        if prompt_field(
                            prompt, "HIERARCHICAL_REVIEW_EVIDENCE"
                        ) != expected_integration:
                            raise BrokerError(
                                "UNVERIFIED",
                                "hierarchical integration binding differs",
                            )
                per_call = self.policy["budget"][
                    "hierarchicalCallReservationMicrousd"
                ].get(receipt["checkerReviewerId"])
                pricing = reviewer_definition
                call_costs_bounded = (
                    type(per_call) is int
                    and isinstance(pricing, dict)
                    and all(
                        (
                            Decimal(item["bytes"])
                            * Decimal(str(pricing["inputUsdPerMillion"]))
                            + Decimal(item["outputCap"])
                            * Decimal(str(pricing["outputUsdPerMillion"]))
                        )
                        <= Decimal(per_call)
                        for item in requests
                    )
                )
                reservation_binding = (
                    type(per_call) is int
                    and call_costs_bounded
                    and budget_settlement["reservationMicrousd"]
                    == planned_calls * per_call
                )
            else:
                reservation_binding = (
                    isinstance(request_evidence, dict)
                    and budget_settlement["reservationMicrousd"]
                    == self.policy["budget"]["reservationMicrousd"]
                )
        common_equal = (
            receipt["policySha256"] == policy_sha
            and receipt["candidateManifestSha256"] == candidate_sha
            and receipt["verdictSha256"] == verdict_sha
            and receipt["budgetSettlementSha256"] == settlement_sha
            and receipt["externalIdPayloadSha256"] == external_id_sha
            and (
                provider_request is None
                or receipt["providerRequestSha256"]
                == sha256_bytes(provider_request)
            )
            and (
                provider_request is None
                or receipt["providerRequestBytes"] == len(provider_request)
            )
            and receipt["providerRequestBytes"]
            <= self.policy["candidate"]["maxProviderRequestBytes"]
            and receipt["repository"] == candidate_manifest["repository"]
            and receipt["subjectType"] == candidate_manifest["subjectType"]
            and receipt["headSha"] == candidate_manifest["headSha"]
            and receipt["baseSha"] == candidate_manifest["baseSha"]
            and receipt["reviewDiffSha256"]
            == candidate_manifest["reviewDiffSha256"]
            and receipt["reviewDiffBytes"] == candidate_manifest["reviewDiffBytes"]
            and receipt["fileCount"] == len(candidate_manifest["files"])
            and receipt["paginationComplete"]
            == candidate_manifest["pagination"]["complete"]
            and candidate_manifest["redactionManifestSha256"] == redaction_sha
            and redaction_manifest["status"] == "clean"
            and redaction_manifest["redactions"] == []
            and redaction_manifest["reviewDiffSha256"]
            == candidate_manifest["reviewDiffSha256"]
            and budget_settlement["policySha256"] == policy_sha
            and budget_settlement["candidateManifestSha256"] == candidate_sha
            and budget_settlement["reviewerId"] == receipt["checkerReviewerId"]
            and budget_settlement["usage"] == receipt["usage"]
            and reservation_binding
            and external_id_payload["repository"] == receipt["repository"]
            and external_id_payload["subjectType"] == receipt["subjectType"]
            and external_id_payload["headSha"] == receipt["headSha"]
            and external_id_payload["baseSha"] == receipt["baseSha"]
            and external_id_payload["candidateManifestSha256"] == candidate_sha
            and external_id_payload["verdictSha256"] == verdict_sha
            and check_publication["externalId"] == external_id_sha
            and check_publication["name"]
            == self.policy["github"]["externalCheck"]["name"]
        )
        if not common_equal:
            raise BrokerError(
                "UNVERIFIED", "broker receipt evidence bindings do not agree"
            )
        if receipt["status"] == "PASSED" and (
            verdict != {"verdict": "PASSED", "findings": [], "unverified": []}
        ):
            raise BrokerError(
                "UNVERIFIED", "successful broker receipt has a non-clean verdict"
            )

        if receipt["subjectType"] == "pull_request":
            if not (
                receipt["pullRequest"] == candidate_manifest["pullRequest"]
                == external_id_payload["pullRequest"]
                and receipt["checkSha"] == candidate_manifest["checkSha"]
                == external_id_payload["checkSha"]
                and receipt["provenanceReceiptSha256"]
                == candidate_manifest["provenanceReceiptSha256"]
                == external_id_payload["provenanceReceiptSha256"]
            ):
                raise BrokerError(
                    "UNVERIFIED", "pull-request receipt coordinates do not agree"
                )
            if check_publication["headSha"] != candidate_manifest["checkSha"]:
                raise BrokerError(
                    "UNVERIFIED", "published check is bound to the wrong PR SHA"
                )
            pull_request = int(receipt["pullRequest"])
        else:
            expected_pulls = {
                key: True for key in candidate_manifest["components"]
            }
            if external_id_payload["pullRequests"] != expected_pulls:
                raise BrokerError(
                    "UNVERIFIED", "merge-group composition does not agree"
                )
            if check_publication["headSha"] != candidate_manifest["headSha"]:
                raise BrokerError(
                    "UNVERIFIED", "published check is bound to the wrong merge SHA"
                )
            pull_request = 0

        coordinates = Coordinates(
            receipt["repository"],
            pull_request,
            receipt["headSha"],
            receipt["baseSha"],
            installation_id,
        ).validate()
        with self.immediate() as db:
            job = db.execute(
                """
                SELECT installation_id,status FROM jobs
                WHERE repository=? AND pull_request=? AND head_sha=? AND base_sha=?
                """,
                (
                    coordinates.repository,
                    coordinates.pull_request,
                    coordinates.head_sha,
                    coordinates.base_sha,
                ),
            ).fetchone()
            if (
                job is None
                or job["installation_id"] != installation_id
                or (
                    phase == "prepare"
                    and job["status"] != "running"
                )
            ):
                raise BrokerError(
                    "UNVERIFIED",
                    "receipt has no matching candidate in the required phase",
                )
            enrollment = db.execute(
                """
                SELECT r.expected_app_id,r.enabled,r.active_receipt_sha256,
                       e.repository AS receipt_repository,
                       e.expected_app_id AS receipt_app_id
                FROM repositories AS r
                LEFT JOIN enrollment_receipts AS e
                  ON e.receipt_sha256=r.active_receipt_sha256
                WHERE r.repository=?
                """,
                (coordinates.repository,),
            ).fetchone()
            if (
                enrollment is None
                or enrollment["enabled"] != 1
                or enrollment["active_receipt_sha256"] is None
                or enrollment["receipt_repository"] != coordinates.repository
                or enrollment["receipt_app_id"] != enrollment["expected_app_id"]
                or enrollment["expected_app_id"]
                != check_publication["appIntegrationId"]
            ):
                raise BrokerError(
                    "UNVERIFIED",
                    "published check is not owned by the enrolled GitHub App",
                )
            settled_budget = db.execute(
                """
                SELECT settlement_json FROM reservations_v2
                WHERE settlement_sha256=? AND status='settled'
                """,
                (settlement_sha,),
            ).fetchone()
            if (
                settled_budget is None
                or settled_budget["settlement_json"]
                != canonical_json(budget_settlement).decode("utf-8")
            ):
                raise BrokerError(
                    "UNVERIFIED", "budget settlement is not immutable store evidence"
                )
            if pull_request > 0:
                provenance = db.execute(
                    """
                    SELECT maker_vendor,maker_model,payload_sha256
                    FROM provenance
                    WHERE repository=? AND pull_request=? AND head_sha=? AND base_sha=?
                    """,
                    (
                        coordinates.repository,
                        pull_request,
                        coordinates.head_sha,
                        coordinates.base_sha,
                    ),
                ).fetchone()
                if (
                    provenance is None
                    or provenance["payload_sha256"]
                    != receipt["provenanceReceiptSha256"]
                ):
                    raise BrokerError(
                        "UNVERIFIED", "receipt provenance is not exact"
                    )
                maker_class = classify_maker(
                    provenance["maker_vendor"],
                    provenance["maker_model"],
                    self.policy,
                )
                selected = select_reviewer(
                    maker_class,
                    provenance["maker_vendor"],
                    provenance["maker_model"],
                    self.policy,
                )
                if (
                    receipt["makerClass"] != maker_class
                    or receipt["checkerReviewerId"] != selected
                ):
                    raise BrokerError(
                        "UNVERIFIED", "receipt does not use the mandatory maker route"
                    )
            else:
                identities: set[tuple[str, str]] = set()
                exact_identity: tuple[str, str] | None = None
                for pull_key, component in sorted(
                    candidate_manifest["components"].items(),
                    key=lambda item: int(item[0]),
                ):
                    provenance = db.execute(
                        """
                        SELECT maker_vendor,maker_model,payload_sha256
                        FROM provenance
                        WHERE repository=? AND pull_request=?
                          AND head_sha=? AND base_sha=?
                        """,
                        (
                            coordinates.repository,
                            int(pull_key),
                            component["pullRequestHeadSha"],
                            component["pullRequestBaseSha"],
                        ),
                    ).fetchone()
                    if (
                        provenance is None
                        or provenance["payload_sha256"]
                        != component["provenanceReceiptSha256"]
                    ):
                        raise BrokerError(
                            "UNVERIFIED",
                            "merge-group component provenance is not exact",
                        )
                    exact_identity = (
                        provenance["maker_vendor"],
                        provenance["maker_model"],
                    )
                    identities.add(
                        (
                            exact_identity[0].strip().casefold(),
                            exact_identity[1].strip().casefold(),
                        )
                    )
                if len(identities) != 1 or exact_identity is None:
                    raise BrokerError(
                        "UNVERIFIED",
                        "mixed merge-group makers cannot use an automatic route",
                    )
                maker_class = classify_maker(
                    exact_identity[0], exact_identity[1], self.policy
                )
                selected = select_reviewer(
                    maker_class,
                    exact_identity[0],
                    exact_identity[1],
                    self.policy,
                )
                if (
                    receipt["makerClass"] != maker_class
                    or receipt["checkerReviewerId"] != selected
                ):
                    raise BrokerError(
                        "UNVERIFIED",
                        "merge-group receipt does not use the mandatory maker route",
                    )
            receipt_for_preparation = dict(receipt)
            receipt_for_preparation.pop("observedAt", None)
            prepared_evidence = {
                "receiptTemplate": receipt_for_preparation,
                "candidateManifest": candidate_manifest,
                "verdict": verdict,
                "budgetSettlement": budget_settlement,
                "externalIdPayload": external_id_payload,
                "sanitizedPromptSha256": sha256_bytes(
                    sanitized_prompt.encode("utf-8")
                ),
                "providerRequestSha256": receipt["providerRequestSha256"],
                "providerRequestBytes": receipt["providerRequestBytes"],
            }
            prepared_evidence_sha = sha256_bytes(
                canonical_json(prepared_evidence)
            )
            preparation_id = prepared_evidence_sha[:32]
            receipt_template_json = canonical_json(receipt).decode("utf-8")
            candidate_json = canonical_json(candidate_manifest).decode("utf-8")
            verdict_json = canonical_json(verdict).decode("utf-8")
            settlement_json = canonical_json(budget_settlement).decode("utf-8")
            external_json = canonical_json(external_id_payload).decode("utf-8")
            if phase == "prepare":
                try:
                    db.execute(
                        """
                        INSERT INTO review_preparations(
                          preparation_id,repository,subject_type,pull_request,
                          head_sha,base_sha,installation_id,check_run_id,
                          check_run_app_id,check_run_external_id,
                          receipt_template_json,candidate_manifest_json,
                          verdict_json,budget_settlement_json,
                          external_id_payload_json,sanitized_prompt,
                          provider_request_sha256,provider_request_bytes,
                          evidence_sha256,state,prepared_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            preparation_id,
                            receipt["repository"],
                            receipt["subjectType"],
                            pull_request,
                            receipt["headSha"],
                            receipt["baseSha"],
                            installation_id,
                            check_run_id,
                            check_publication["appIntegrationId"],
                            check_publication["externalId"],
                            receipt_template_json,
                            candidate_json,
                            verdict_json,
                            settlement_json,
                            external_json,
                            sanitized_prompt,
                            receipt["providerRequestSha256"],
                            receipt["providerRequestBytes"],
                            prepared_evidence_sha,
                            "prepared",
                            now_iso(),
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise BrokerError(
                        "UNVERIFIED",
                        "candidate or Check Run already has a preparation",
                    ) from exc
                return preparation_id

            preparation = db.execute(
                """
                SELECT * FROM review_preparations
                WHERE check_run_id=? AND repository=? AND subject_type=?
                  AND pull_request=? AND head_sha=? AND base_sha=?
                """,
                (
                    check_run_id,
                    receipt["repository"],
                    receipt["subjectType"],
                    pull_request,
                    receipt["headSha"],
                    receipt["baseSha"],
                ),
            ).fetchone()
            if preparation is None:
                raise BrokerError(
                    "UNVERIFIED",
                    "published Check Run has no durable pre-publication evidence",
                )
            stored_template = decode_strict_json(
                preparation["receipt_template_json"].encode("utf-8"),
                "stored review receipt template",
            )
            stored_without_observed = dict(stored_template)
            stored_without_observed.pop("observedAt", None)
            exact_preparation = (
                preparation["state"] in {"prepared", "finalized"}
                and stored_without_observed == receipt_for_preparation
                and preparation["candidate_manifest_json"] == candidate_json
                and preparation["verdict_json"] == verdict_json
                and preparation["budget_settlement_json"] == settlement_json
                and preparation["external_id_payload_json"] == external_json
                and preparation["sanitized_prompt"] == sanitized_prompt
                and preparation["provider_request_sha256"]
                == receipt["providerRequestSha256"]
                and preparation["provider_request_bytes"]
                == receipt["providerRequestBytes"]
                and preparation["evidence_sha256"]
                == prepared_evidence_sha
            )
            if not exact_preparation:
                raise BrokerError(
                    "UNVERIFIED",
                    "final publication differs from durable preparation",
                )
            evidence = {
                "receipt": receipt,
                "candidateManifest": candidate_manifest,
                "verdict": verdict,
                "budgetSettlement": budget_settlement,
                "externalIdPayload": external_id_payload,
            }
            evidence_sha = sha256_bytes(canonical_json(evidence))
            receipt_id = evidence_sha[:32]
            if preparation["state"] == "finalized":
                existing = db.execute(
                    """
                    SELECT receipt_id,evidence_sha256 FROM reviews_v3
                    WHERE check_run_id=?
                    """,
                    (check_run_id,),
                ).fetchone()
                if (
                    existing is None
                    or existing["receipt_id"] != receipt_id
                    or existing["evidence_sha256"] != evidence_sha
                ):
                    raise BrokerError(
                        "UNVERIFIED",
                        "finalized preparation has inconsistent evidence",
                    )
                return receipt_id
            try:
                db.execute(
                    """
                    INSERT INTO reviews_v3(
                      receipt_id,repository,subject_type,pull_request,head_sha,
                      base_sha,installation_id,check_run_id,check_run_app_id,
                      check_run_external_id,receipt_json,
                      candidate_manifest_json,verdict_json,budget_settlement_json,
                      external_id_payload_json,sanitized_prompt,evidence_sha256,
                      observed_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        receipt_id,
                        receipt["repository"],
                        receipt["subjectType"],
                        pull_request,
                        receipt["headSha"],
                        receipt["baseSha"],
                        installation_id,
                        check_run_id,
                        check_publication["appIntegrationId"],
                        check_publication["externalId"],
                        canonical_json(receipt).decode("utf-8"),
                        candidate_json,
                        verdict_json,
                        settlement_json,
                        external_json,
                        sanitized_prompt,
                        evidence_sha,
                        receipt["observedAt"],
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise BrokerError(
                    "UNVERIFIED",
                    "candidate or published check already has immutable evidence",
                ) from exc
            changed = db.execute(
                """
                UPDATE review_preparations
                SET state='finalized',finalized_at=?,failure_reason=NULL
                WHERE preparation_id=? AND state='prepared'
                """,
                (now_iso(), preparation["preparation_id"]),
            ).rowcount
            if changed != 1:
                raise BrokerError(
                    "UNVERIFIED", "review preparation did not finalize atomically"
                )
        return receipt_id

    def prepare_failure_publication(
        self,
        coordinates: Coordinates,
        check_sha: str,
        app_integration_id: int,
        check_run_id: int,
        external_id: str,
        status: str,
        conclusion: str,
        reason: str,
        github_api: "GitHubApi",
        installation_token: str,
        *,
        review_preparation_id: str | None = None,
    ) -> str:
        """Durably explain a fail-closed terminal Check before its PATCH."""
        coordinates.validate()
        if (
            not re.fullmatch(r"[0-9a-f]{40}", check_sha or "")
            or type(app_integration_id) is not int
            or app_integration_id <= 0
            or type(check_run_id) is not int
            or check_run_id <= 0
            or not re.fullmatch(r"[0-9a-f]{64}", external_id or "")
            or not isinstance(reason, str)
            or not 1 <= len(reason) <= 1000
            or (
                review_preparation_id is not None
                and not re.fullmatch(
                    r"[0-9a-f]{32}", review_preparation_id
                )
            )
        ):
            raise BrokerError(
                "UNVERIFIED", "failure publication evidence is invalid"
            )
        expected_conclusion = (
            self.policy["github"]["externalCheck"]["unavailableConclusion"]
            if status == "UNAVAILABLE"
            else self.policy["github"]["externalCheck"]["unverifiedConclusion"]
            if status == "UNVERIFIED"
            else None
        )
        if expected_conclusion is None or conclusion != expected_conclusion:
            raise BrokerError(
                "UNVERIFIED", "failure publication status/conclusion is invalid"
            )
        if not isinstance(github_api, GitHubApi) or not re.fullmatch(
            r"[^\s]{1,4096}", installation_token or ""
        ):
            raise BrokerError(
                "UNAVAILABLE", "GitHub failure publication observer is unavailable"
            )
        observed = github_api.request_json(
            "GET",
            f"/repos/{coordinates.repository}/check-runs/{check_run_id}",
            installation_token,
        )
        app = observed.get("app") if isinstance(observed, dict) else None
        observed_identity = {
            "id": observed.get("id") if isinstance(observed, dict) else None,
            "appIntegrationId": (
                app.get("id") if isinstance(app, dict) else None
            ),
            "name": observed.get("name") if isinstance(observed, dict) else None,
            "headSha": (
                observed.get("head_sha") if isinstance(observed, dict) else None
            ),
            "externalId": (
                observed.get("external_id")
                if isinstance(observed, dict) else None
            ),
        }
        intended_identity = {
            "id": check_run_id,
            "appIntegrationId": app_integration_id,
            "name": self.policy["github"]["externalCheck"]["name"],
            "headSha": check_sha,
            "externalId": external_id,
        }
        observed_status = (
            observed.get("status") if isinstance(observed, dict) else None
        )
        observed_conclusion = (
            observed.get("conclusion") if isinstance(observed, dict) else None
        )
        if (
            observed_identity != intended_identity
            or observed_status not in {"in_progress", "completed"}
            or (
                observed_status == "in_progress"
                and observed_conclusion is not None
            )
            or (
                observed_status == "completed"
                and observed_conclusion
                not in {"success", "failure", "action_required"}
            )
        ):
            raise BrokerError(
                "UNVERIFIED",
                "failure publication source Check Run is not exact",
            )
        publication = {
            **intended_identity,
            "status": "completed",
            "conclusion": conclusion,
        }
        payload = {
            "version": 1,
            "repository": coordinates.repository,
            "subjectType": coordinates.subject_type,
            "pullRequest": coordinates.pull_request,
            "headSha": coordinates.head_sha,
            "baseSha": coordinates.base_sha,
            "installationId": coordinates.installation_id,
            "checkPublication": publication,
            "failureStatus": status,
            "failureReasonSha256": sha256_bytes(reason.encode("utf-8")),
            "reviewPreparationId": review_preparation_id,
            "preparedAt": now_iso(),
        }
        payload_json = canonical_json(payload).decode("utf-8")
        preparation_id = sha256_bytes(payload_json.encode("utf-8"))[:32]
        with self.immediate() as db:
            job = db.execute(
                """
                SELECT installation_id FROM jobs
                WHERE repository=? AND pull_request=? AND head_sha=? AND base_sha=?
                """,
                (
                    coordinates.repository,
                    coordinates.pull_request,
                    coordinates.head_sha,
                    coordinates.base_sha,
                ),
            ).fetchone()
            enrollment = db.execute(
                """
                SELECT expected_app_id,enabled,active_receipt_sha256
                FROM repositories WHERE repository=?
                """,
                (coordinates.repository,),
            ).fetchone()
            if (
                job is None
                or job["installation_id"] != coordinates.installation_id
                or enrollment is None
                or enrollment["enabled"] != 1
                or enrollment["active_receipt_sha256"] is None
                or enrollment["expected_app_id"] != app_integration_id
            ):
                raise BrokerError(
                    "UNVERIFIED",
                    "failure publication lacks an enrolled exact candidate",
                )
            if review_preparation_id is not None:
                review_preparation = db.execute(
                    """
                    SELECT check_run_id,state FROM review_preparations
                    WHERE preparation_id=?
                    """,
                    (review_preparation_id,),
                ).fetchone()
                if (
                    review_preparation is None
                    or review_preparation["check_run_id"] != check_run_id
                    or review_preparation["state"] != "prepared"
                ):
                    raise BrokerError(
                        "UNVERIFIED",
                        "failure publication review preparation is not exact",
                    )
            try:
                db.execute(
                    """
                    INSERT INTO failure_preparations(
                      preparation_id,repository,subject_type,pull_request,
                      head_sha,base_sha,installation_id,check_run_id,
                      check_run_app_id,check_run_external_id,payload_json,
                      review_preparation_id,state,prepared_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        preparation_id,
                        coordinates.repository,
                        coordinates.subject_type,
                        coordinates.pull_request,
                        coordinates.head_sha,
                        coordinates.base_sha,
                        coordinates.installation_id,
                        check_run_id,
                        app_integration_id,
                        external_id,
                        payload_json,
                        review_preparation_id,
                        "prepared",
                        payload["preparedAt"],
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise BrokerError(
                    "UNVERIFIED",
                    "Check Run already has immutable failure evidence",
                ) from exc
        return preparation_id

    def authorize_terminal_publication(
        self,
        evidence_kind: str,
        preparation_id: str,
        check_run_id: int,
        app_integration_id: int,
        external_id: str,
        conclusion: str,
    ) -> None:
        """Fail closed unless the exact terminal PATCH already has evidence."""
        if evidence_kind == "review":
            with self._lock:
                row = self.db.execute(
                    """
                    SELECT receipt_template_json,state
                    FROM review_preparations WHERE preparation_id=?
                    """,
                    (preparation_id,),
                ).fetchone()
            publication = (
                decode_strict_json(
                    row["receipt_template_json"].encode("utf-8"),
                    "stored review receipt template",
                )["checkPublication"]
                if row is not None and row["state"] == "prepared"
                else None
            )
        elif evidence_kind == "failure":
            with self._lock:
                row = self.db.execute(
                    """
                    SELECT payload_json,state FROM failure_preparations
                    WHERE preparation_id=?
                    """,
                    (preparation_id,),
                ).fetchone()
            publication = (
                decode_strict_json(
                    row["payload_json"].encode("utf-8"),
                    "stored failure publication",
                )["checkPublication"]
                if row is not None and row["state"] == "prepared"
                else None
            )
        else:
            raise BrokerError(
                "UNVERIFIED", "terminal publication evidence kind is invalid"
            )
        expected = {
            "id": check_run_id,
            "appIntegrationId": app_integration_id,
            "externalId": external_id,
            "conclusion": conclusion,
        }
        if not isinstance(publication, dict) or any(
            publication.get(key) != value for key, value in expected.items()
        ):
            raise BrokerError(
                "UNVERIFIED",
                "terminal Check Run PATCH has no exact durable preparation",
            )

    def record_failure_publication(
        self,
        preparation_id: str,
        github_api: "GitHubApi",
        installation_token: str,
    ) -> None:
        with self._lock:
            row = self.db.execute(
                """
                SELECT * FROM failure_preparations WHERE preparation_id=?
                """,
                (preparation_id,),
            ).fetchone()
        if row is None:
            raise BrokerError(
                "UNVERIFIED", "failure publication preparation is missing"
            )
        if row["state"] == "finalized":
            return
        payload = decode_strict_json(
            row["payload_json"].encode("utf-8"),
            "stored failure publication",
        )
        expected = payload["checkPublication"]
        observed = github_api.request_json(
            "GET",
            f"/repos/{payload['repository']}/check-runs/{expected['id']}",
            installation_token,
        )
        app = observed.get("app") if isinstance(observed, dict) else None
        actual = {
            "id": observed.get("id") if isinstance(observed, dict) else None,
            "appIntegrationId": (
                app.get("id") if isinstance(app, dict) else None
            ),
            "name": observed.get("name") if isinstance(observed, dict) else None,
            "headSha": (
                observed.get("head_sha") if isinstance(observed, dict) else None
            ),
            "externalId": (
                observed.get("external_id")
                if isinstance(observed, dict) else None
            ),
            "status": (
                observed.get("status") if isinstance(observed, dict) else None
            ),
            "conclusion": (
                observed.get("conclusion")
                if isinstance(observed, dict) else None
            ),
        }
        if actual != expected:
            raise BrokerError(
                "UNVERIFIED", "failure Check Run final observation differs"
            )
        with self.immediate() as db:
            changed = db.execute(
                """
                UPDATE failure_preparations
                SET state='finalized',observed_at=?
                WHERE preparation_id=? AND state='prepared'
                """,
                (now_iso(), preparation_id),
            ).rowcount
            if changed != 1:
                raise BrokerError(
                    "UNVERIFIED",
                    "failure publication did not finalize atomically",
                )
            if row["review_preparation_id"] is not None:
                db.execute(
                    """
                    UPDATE review_preparations
                    SET state='failed',failure_reason=?
                    WHERE preparation_id=? AND state='prepared'
                    """,
                    (
                        "terminal publication downgraded with durable evidence",
                        row["review_preparation_id"],
                    ),
                )

    def pending_failure_preparations(
        self, limit: int = 100
    ) -> list[dict[str, Any]]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise BrokerError("UNVERIFIED", "failure recovery limit is invalid")
        with self._lock:
            rows = self.db.execute(
                """
                SELECT f.*,j.job_id
                FROM failure_preparations AS f
                JOIN jobs AS j
                  ON j.repository=f.repository
                 AND j.pull_request=f.pull_request
                 AND j.head_sha=f.head_sha
                 AND j.base_sha=f.base_sha
                WHERE f.state='prepared'
                ORDER BY f.prepared_at,f.preparation_id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "preparationId": row["preparation_id"],
                "jobId": int(row["job_id"]),
                "coordinates": Coordinates(
                    row["repository"],
                    int(row["pull_request"]),
                    row["head_sha"],
                    row["base_sha"],
                    int(row["installation_id"]),
                ).validate(),
                "payload": decode_strict_json(
                    row["payload_json"].encode("utf-8"),
                    "stored failure publication",
                ),
            }
            for row in rows
        ]

    def pending_review_preparations(
        self, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Return bounded durable publications that need GitHub reconciliation."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise BrokerError("UNVERIFIED", "preparation recovery limit is invalid")
        with self._lock:
            rows = self.db.execute(
                """
                SELECT p.*,j.job_id
                FROM review_preparations AS p
                JOIN jobs AS j
                  ON j.repository=p.repository
                 AND j.pull_request=p.pull_request
                 AND j.head_sha=p.head_sha
                 AND j.base_sha=p.base_sha
                WHERE p.state='prepared'
                  AND NOT EXISTS (
                    SELECT 1 FROM failure_preparations AS f
                    WHERE f.review_preparation_id=p.preparation_id
                  )
                ORDER BY p.prepared_at,p.preparation_id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "preparationId": row["preparation_id"],
                    "jobId": int(row["job_id"]),
                    "coordinates": Coordinates(
                        row["repository"],
                        int(row["pull_request"]),
                        row["head_sha"],
                        row["base_sha"],
                        int(row["installation_id"]),
                    ).validate(),
                    "receiptTemplate": decode_strict_json(
                        row["receipt_template_json"].encode("utf-8"),
                        "stored review receipt template",
                    ),
                    "candidateManifest": decode_strict_json(
                        row["candidate_manifest_json"].encode("utf-8"),
                        "stored candidate manifest",
                    ),
                    "verdict": decode_strict_json(
                        row["verdict_json"].encode("utf-8"),
                        "stored reviewer verdict",
                    ),
                    "budgetSettlement": decode_strict_json(
                        row["budget_settlement_json"].encode("utf-8"),
                        "stored budget settlement",
                    ),
                    "externalIdPayload": decode_strict_json(
                        row["external_id_payload_json"].encode("utf-8"),
                        "stored external-id payload",
                    ),
                    "sanitizedPrompt": row["sanitized_prompt"],
                    "providerRequestSha256": row["provider_request_sha256"],
                    "providerRequestBytes": int(row["provider_request_bytes"]),
                }
            )
        return result

    def fail_review_preparation(
        self, preparation_id: str, reason: str
    ) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", preparation_id or ""):
            raise BrokerError("UNVERIFIED", "review preparation id is invalid")
        if not isinstance(reason, str) or not 1 <= len(reason) <= 500:
            raise BrokerError("UNVERIFIED", "review preparation failure is invalid")
        with self.immediate() as db:
            row = db.execute(
                """
                SELECT state FROM review_preparations
                WHERE preparation_id=?
                """,
                (preparation_id,),
            ).fetchone()
            if row is None:
                raise BrokerError("UNVERIFIED", "review preparation is missing")
            if row["state"] == "finalized":
                raise BrokerError(
                    "UNVERIFIED", "finalized review preparation cannot fail"
                )
            if row["state"] == "failed":
                return
            db.execute(
                """
                UPDATE review_preparations
                SET state='failed',failure_reason=?
                WHERE preparation_id=? AND state='prepared'
                """,
                (reason, preparation_id),
            )

    def reconcile_interrupted_jobs(self) -> dict[str, int]:
        """Recover single-worker jobs left running by a terminated process."""
        counts = {"requeued": 0, "completed": 0, "failed": 0, "pending": 0}
        with self.immediate() as db:
            rows = db.execute(
                """
                SELECT j.job_id,
                       p.state AS review_state,p.receipt_template_json,
                       f.state AS failure_state,f.payload_json
                FROM jobs AS j
                LEFT JOIN review_preparations AS p
                  ON p.repository=j.repository
                 AND p.pull_request=j.pull_request
                 AND p.head_sha=j.head_sha
                 AND p.base_sha=j.base_sha
                LEFT JOIN failure_preparations AS f
                  ON f.repository=j.repository
                 AND f.pull_request=j.pull_request
                 AND f.head_sha=j.head_sha
                 AND f.base_sha=j.base_sha
                WHERE j.status='running'
                ORDER BY j.job_id
                """
            ).fetchall()
            for row in rows:
                failure_state = row["failure_state"]
                review_state = row["review_state"]
                if failure_state == "prepared":
                    counts["pending"] += 1
                    continue
                if failure_state == "finalized":
                    failure = decode_strict_json(
                        row["payload_json"].encode("utf-8"),
                        "stored failure publication",
                    )
                    result = {
                        "receiptId": None,
                        "status": failure["failureStatus"],
                        "conclusion": failure["checkPublication"]["conclusion"],
                        "checkRunId": failure["checkPublication"]["id"],
                    }
                    db.execute(
                        """
                        UPDATE jobs SET status='failed',result_json=?,updated_at=?
                        WHERE job_id=? AND status='running'
                        """,
                        (
                            json.dumps(
                                result, ensure_ascii=False, sort_keys=True
                            ),
                            now_iso(),
                            row["job_id"],
                        ),
                    )
                    counts["failed"] += 1
                    continue
                if review_state is None:
                    db.execute(
                        """
                        UPDATE jobs SET status='queued',updated_at=?
                        WHERE job_id=? AND status='running'
                        """,
                        (now_iso(), row["job_id"]),
                    )
                    counts["requeued"] += 1
                    continue
                if review_state == "prepared":
                    counts["pending"] += 1
                    continue
                receipt = decode_strict_json(
                    row["receipt_template_json"].encode("utf-8"),
                    "stored review receipt template",
                )
                if review_state == "finalized":
                    review = db.execute(
                        """
                        SELECT receipt_id FROM reviews_v3
                        WHERE check_run_id=?
                        """,
                        (receipt["checkPublication"]["id"],),
                    ).fetchone()
                    if review is None:
                        raise BrokerError(
                            "UNVERIFIED",
                            "finalized preparation has no durable review",
                        )
                    result = {
                        "receiptId": review["receipt_id"],
                        "status": receipt["status"],
                        "conclusion": receipt["checkPublication"]["conclusion"],
                        "checkRunId": receipt["checkPublication"]["id"],
                    }
                    next_status = "completed"
                    counts["completed"] += 1
                else:
                    result = {
                        "receiptId": None,
                        "status": "UNVERIFIED",
                        "conclusion": self.policy["github"]["externalCheck"][
                            "unverifiedConclusion"
                        ],
                        "checkRunId": receipt["checkPublication"]["id"],
                    }
                    next_status = "failed"
                    counts["failed"] += 1
                db.execute(
                    """
                    UPDATE jobs SET status=?,result_json=?,updated_at=?
                    WHERE job_id=? AND status='running'
                    """,
                    (
                        next_status,
                        json.dumps(result, ensure_ascii=False, sort_keys=True),
                        now_iso(),
                        row["job_id"],
                    ),
                )
        return counts


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class GitHubAppAuth:
    def __init__(
        self, client_id: str, private_key_file: Path,
        api: "GitHubApi | None" = None,
        signer: Callable[[bytes], bytes] | None = None,
        signer_algorithm: str | None = None,
        policy: dict[str, Any] | None = None,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{8,100}", client_id or ""):
            raise BrokerError("UNAVAILABLE", "GitHub App client id is unavailable")
        self.client_id = client_id
        self.private_key_file = private_key_file
        self.api = api
        self.signer = signer
        self.policy = load_policy() if policy is None else validate_policy(policy)
        if (
            (signer is None and signer_algorithm is not None)
            or (signer is not None and signer_algorithm != "RS256")
        ):
            raise BrokerError(
                "UNVERIFIED", "injected GitHub App signer is not RS256"
            )
        if signer is None:
            self._validate_private_key_file()

    def _validate_private_key_file(self) -> None:
        if not self.private_key_file.is_file():
            raise BrokerError("UNAVAILABLE", "GitHub App private key is unavailable")
        try:
            mode = self.private_key_file.stat().st_mode & 0o777
            if os.name != "nt" and mode & 0o077:
                raise BrokerError(
                    "UNAVAILABLE", "GitHub App private key permissions are too broad"
                )
            validation = subprocess.run(
                [
                    "openssl",
                    "rsa",
                    "-in",
                    str(self.private_key_file),
                    "-check",
                    "-noout",
                ],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=False,
                timeout=10,
            )
            if validation.returncode != 0:
                raise BrokerError(
                    "UNAVAILABLE", "GitHub App private key is not valid RSA"
                )
        except (OSError, subprocess.SubprocessError) as exc:
            raise BrokerError(
                "UNAVAILABLE", "GitHub App private key validator unavailable"
            ) from exc

    def _sign(self, value: bytes) -> bytes:
        if self.signer is not None:
            return self.signer(value)
        self._validate_private_key_file()
        try:
            result = subprocess.run(
                [
                    "openssl", "dgst", "-sha256", "-sign",
                    str(self.private_key_file),
                ],
                input=value,
                capture_output=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise BrokerError("UNAVAILABLE", "GitHub App JWT signer unavailable") from exc
        if result.returncode != 0 or not result.stdout:
            raise BrokerError("UNAVAILABLE", "GitHub App JWT signing failed")
        return result.stdout

    def jwt(self, now: int | None = None) -> str:
        timestamp = int(time.time() if now is None else now)
        auth = self.policy["github"]["appAuthentication"]
        header = b64url(canonical_json({"alg": "RS256", "typ": "JWT"}))
        issued_at = timestamp - int(auth["jwtIssuedAtBackdateSeconds"])
        expires_at = issued_at + int(auth["jwtMaximumLifetimeSeconds"])
        payload = b64url(
            canonical_json(
                {"iat": issued_at, "exp": expires_at, "iss": self.client_id}
            )
        )
        signing_input = f"{header}.{payload}".encode("ascii")
        return f"{header}.{payload}.{b64url(self._sign(signing_input))}"

    def installation_token(
        self,
        installation_id: int,
        repository: str,
        expected_app_id: int,
    ) -> str:
        if self.api is None:
            raise BrokerError("UNAVAILABLE", "GitHub API transport is unavailable")
        if (
            type(installation_id) is not int
            or installation_id <= 0
            or type(expected_app_id) is not int
            or expected_app_id <= 0
            or not REPO_RE.fullmatch(repository or "")
        ):
            raise BrokerError(
                "UNVERIFIED",
                "GitHub App installation or repository scope is invalid",
            )
        repository_name = repository.split("/", 1)[1]
        app_jwt = self.jwt()
        live_installation = self.api.request_json(
            "GET",
            f"/repos/{repository}/installation",
            app_jwt,
        )
        if (
            not isinstance(live_installation, dict)
            or live_installation.get("id") != installation_id
            or live_installation.get("app_id") != expected_app_id
        ):
            raise BrokerError(
                "UNVERIFIED",
                "live repository installation differs from webhook/enrollment",
            )
        value = self.api.request_json(
            "POST",
            f"/app/installations/{installation_id}/access_tokens",
            app_jwt,
            data={
                "permissions": {
                    "checks": "write",
                    "contents": "read",
                    "pull_requests": "read",
                },
                "repositories": [repository_name],
            },
        )
        installation_credential = (
            value.get("token") if isinstance(value, dict) else None
        )
        if (
            not isinstance(installation_credential, str)
            or not installation_credential
        ):
            raise BrokerError("UNAVAILABLE", "GitHub installation token missing")
        return installation_credential


class RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req, fp, code, msg, headers, newurl
    ):
        del req, fp, code, msg, headers, newurl
        raise BrokerError(
            "UNVERIFIED", "GitHub API redirect is forbidden"
        )


class GitHubApi:
    def __init__(
        self, base_url: str = "https://api.github.com",
        api_version: str = "2026-03-10",
        opener: Callable[..., Any] | None = None,
    ) -> None:
        parsed = urllib.parse.urlparse(base_url)
        if (
            parsed.scheme != "https"
            or (parsed.hostname or "").casefold() != "api.github.com"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in {None, 443}
            or parsed.path not in {"", "/"}
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            raise BrokerError(
                "UNVERIFIED",
                "GitHub API base URL must be canonical api.github.com HTTPS",
            )
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self.opener = opener or urllib.request.build_opener(
            RejectRedirectHandler()
        ).open

    def _request(
        self, method: str, path: str, token: str, data: dict[str, Any] | None,
        accept: str, limit: int,
    ) -> tuple[bytes, dict[str, str]]:
        if not path.startswith("/") or path.startswith("//"):
            raise BrokerError("UNVERIFIED", "unsafe GitHub API path")
        body = canonical_json(data) if data is not None else None
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={
                "Accept": accept,
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "idea-to-deploy-review-broker/1",
                "X-GitHub-Api-Version": self.api_version,
            },
        )
        try:
            with self.opener(request, timeout=30) as response:
                raw = response.read(limit + 1)
                headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
                final = urllib.parse.urlparse(response.geturl())
        except (
            urllib.error.URLError, http.client.HTTPException, ssl.SSLError,
            TimeoutError, OSError,
        ) as exc:
            raise BrokerError(
                "UNAVAILABLE", f"GitHub API request failed: {type(exc).__name__}"
            ) from exc
        expected = urllib.parse.urlparse(self.base_url)
        if (
            final.scheme != expected.scheme
            or final.netloc != expected.netloc
        ):
            raise BrokerError(
                "UNVERIFIED", "GitHub API response origin changed"
            )
        if len(raw) > limit:
            raise BrokerError("UNVERIFIED", "GitHub API response exceeds its bound")
        return raw, headers

    def request_json(
        self, method: str, path: str, token: str,
        data: dict[str, Any] | None = None,
        limit: int = MAX_JSON_BYTES,
    ) -> Any:
        raw, _ = self._request(
            method, path, token, data, "application/vnd.github+json", limit
        )
        return decode_strict_json(raw, "GitHub API response")

    def request_bytes(
        self, path: str, token: str, accept: str, limit: int
    ) -> bytes:
        raw, _ = self._request("GET", path, token, None, accept, limit)
        return raw

    def pages(
        self, path: str, token: str, page_size: int, max_items: int
    ) -> list[dict[str, Any]]:
        if (
            type(page_size) is not int
            or not 1 <= page_size <= 100
            or type(max_items) is not int
            or not 1 <= max_items <= 10000
        ):
            raise BrokerError(
                "UNVERIFIED", "GitHub pagination bounds are invalid"
            )
        rows: list[dict[str, Any]] = []
        page = 1
        separator = "&" if "?" in path else "?"
        while True:
            value = self.request_json(
                "GET",
                f"{path}{separator}per_page={page_size}&page={page}",
                token,
            )
            if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
                raise BrokerError("UNVERIFIED", "GitHub pagination returned invalid data")
            rows.extend(value)
            if len(rows) > max_items:
                raise BrokerError(
                    "UNVERIFIED", f"candidate file limit exceeded: > {max_items}"
                )
            if len(value) < page_size:
                return rows
            page += 1
