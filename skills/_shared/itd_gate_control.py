#!/usr/bin/env python3
"""Global ITD gate registry, GitHub ruleset and doctor primitives."""
from __future__ import annotations

import base64
import ctypes
import json
import hashlib
import os
import re
import subprocess
import urllib.parse
import urllib.request
from ctypes import wintypes
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

API_VERSION = "2026-03-10"
RULESET_NAME = "ITD protected branches"
EXTERNAL_CHECK = "ITD external review gate"
MACHINE_CHECK = "ITD machine oracle"
GITHUB_ACTIONS_INTEGRATION_ID = 15368
MACHINE_WORKFLOW_REPOSITORY = "hihol-labs/idea-to-deploy"
MACHINE_WORKFLOW_PATH = ".github/workflows/itd-machine-oracle.yml"
REPO_RE = re.compile(
    r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$"
)
KEY_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PROVENANCE_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
PROVENANCE_SAFE_TEXT_RE = re.compile(r"^[^\x00-\x1f\x7f]{1,200}$")
MAX_GH_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_HTTP_RESPONSE_BYTES = 1024 * 1024
POLICY_PATH = Path(__file__).with_name("REVIEW_BROKER_POLICY.json")
INSTALL_ROOT = Path(__file__).resolve().parents[2]
MIN_GATE_VERSION = (1, 95, 0)


class GateError(RuntimeError):
    def __init__(self, status: str, reason: str) -> None:
        if status not in {"UNAVAILABLE", "UNVERIFIED", "BLOCKED"}:
            raise ValueError(f"invalid gate status: {status}")
        super().__init__(reason)
        self.status = status
        self.reason = reason


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def registry_path() -> Path:
    configured = os.environ.get("ITD_GATE_REGISTRY")
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        base = Path(
            os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))
        )
        return (base / "ITD" / "gates.json").resolve()
    return (Path.home() / ".config" / "itd" / "gates.json").resolve()


def github_repository_from_remote(value: str) -> str:
    raw = value.strip()
    if raw.startswith("git@github.com:"):
        repository = raw[len("git@github.com:"):]
    else:
        parsed = urllib.parse.urlsplit(raw)
        if (
            parsed.scheme not in {"https", "ssh"}
            or (parsed.hostname or "").casefold() != "github.com"
            or (
                parsed.scheme == "https"
                and parsed.username is not None
            )
            or (
                parsed.scheme == "ssh"
                and parsed.username not in {None, "git"}
            )
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise GateError(
                "UNVERIFIED", "origin is not a canonical GitHub remote"
            )
        repository = parsed.path.lstrip("/")
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not REPO_RE.fullmatch(repository):
        raise GateError(
            "UNVERIFIED", "origin GitHub repository is invalid"
        )
    return repository


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise GateError("UNVERIFIED", f"{label} fields are invalid")
    return value


def installed_version() -> str:
    versions: list[str] = []
    for relative in (
        ".codex-plugin/plugin.json",
        ".claude-plugin/plugin.json",
    ):
        path = INSTALL_ROOT / relative
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GateError(
                "UNAVAILABLE", f"installed ITD manifest is unavailable: {relative}"
            ) from exc
        if (
            not isinstance(value, dict)
            or value.get("name") != "idea-to-deploy"
            or not isinstance(value.get("version"), str)
        ):
            raise GateError(
                "UNVERIFIED", f"installed ITD manifest is invalid: {relative}"
            )
        versions.append(value["version"])
    if len(set(versions)) != 1:
        raise GateError("UNVERIFIED", "Codex/Claude ITD versions differ")
    match = re.fullmatch(
        r"([0-9]+)\.([0-9]+)\.([0-9]+)(?:[-+][A-Za-z0-9.-]+)?",
        versions[0],
    )
    if not match or tuple(map(int, match.groups())) < MIN_GATE_VERSION:
        raise GateError(
            "UNVERIFIED", "installed ITD is older than required 1.95.0"
        )
    return versions[0]


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("size", ctypes.c_uint32),
        ("data", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _dpapi(value: bytes, *, protect: bool) -> bytes:
    if os.name != "nt":
        raise GateError("UNAVAILABLE", "Windows DPAPI is unavailable")
    source_buffer = ctypes.create_string_buffer(value)
    source = _DataBlob(
        len(value),
        ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    target = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    common = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    if protect:
        function = crypt32.CryptProtectData
        function.argtypes = [
            ctypes.POINTER(_DataBlob),
            wintypes.LPCWSTR,
            *common[1:],
        ]
        function.restype = wintypes.BOOL
        ok = function(
            ctypes.byref(source),
            "ITD maker provenance key",
            None,
            None,
            None,
            0x1,
            ctypes.byref(target),
        )
    else:
        function = crypt32.CryptUnprotectData
        function.argtypes = [
            ctypes.POINTER(_DataBlob),
            ctypes.POINTER(wintypes.LPWSTR),
            *common[1:],
        ]
        function.restype = wintypes.BOOL
        ok = function(
            ctypes.byref(source),
            None,
            None,
            None,
            None,
            0x1,
            ctypes.byref(target),
        )
    if not ok:
        raise GateError("UNAVAILABLE", "Windows DPAPI operation failed")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
        kernel32.LocalFree.restype = wintypes.HLOCAL
        kernel32.LocalFree(ctypes.cast(target.data, wintypes.HLOCAL))


def read_provenance_private_key(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise GateError("UNAVAILABLE", "provenance signing key is unavailable")
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise GateError(
            "UNAVAILABLE", "provenance signing key permissions are too broad"
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise GateError(
            "UNAVAILABLE", "provenance signing key is unreadable"
        ) from exc
    if os.name != "nt":
        if len(raw) != 32:
            raise GateError(
                "UNAVAILABLE",
                "provenance signing material must be a raw 32-byte Ed25519 key",
            )
        return raw
    try:
        envelope = json.loads(raw.decode("utf-8"))
        if (
            not isinstance(envelope, dict)
            or set(envelope) != {"version", "provider", "ciphertext"}
            or envelope["version"] != 1
            or envelope["provider"] != "windows-dpapi-current-user"
            or not isinstance(envelope["ciphertext"], str)
        ):
            raise ValueError("invalid envelope")
        encrypted = base64.b64decode(
            envelope["ciphertext"], validate=True
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise GateError(
            "UNVERIFIED", "Windows provenance key envelope is invalid"
        ) from exc
    private = _dpapi(encrypted, protect=False)
    if len(private) != 32:
        raise GateError(
            "UNVERIFIED", "Windows provenance key plaintext size is invalid"
        )
    return private


def write_provenance_private_key(path: Path, private: bytes) -> None:
    if len(private) != 32:
        raise GateError("UNVERIFIED", "Ed25519 private key size is invalid")
    path = path.resolve()
    if path.exists():
        raise GateError(
            "BLOCKED", "provenance private key target already exists"
        )
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "nt":
        encrypted = _dpapi(private, protect=True)
        payload = {
            "version": 1,
            "provider": "windows-dpapi-current-user",
            "ciphertext": base64.b64encode(encrypted).decode("ascii"),
        }
        data = canonical_json(payload) + b"\n"
    else:
        data = private
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


def provenance_public_key(private: bytes) -> str:
    try:
        public = Ed25519PrivateKey.from_private_bytes(private).public_key()
        raw = public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    except (TypeError, ValueError) as exc:
        raise GateError("UNVERIFIED", "Ed25519 private key is invalid") from exc
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def provenance_payload(value: Any) -> dict[str, Any]:
    fields = {
        "repository",
        "pullRequest",
        "headSha",
        "baseSha",
        "makerVendor",
        "makerModel",
        "makerSession",
        "issuedAt",
        "nonce",
        "keyId",
        "signature",
    }
    row = _exact(value, fields, "maker provenance")
    if (
        not REPO_RE.fullmatch(str(row["repository"]))
        or type(row["pullRequest"]) is not int
        or row["pullRequest"] <= 0
        or not SHA_RE.fullmatch(str(row["headSha"]))
        or not SHA_RE.fullmatch(str(row["baseSha"]))
        or not PROVENANCE_NONCE_RE.fullmatch(str(row["nonce"]))
        or not KEY_ID_RE.fullmatch(str(row["keyId"]))
        or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T"
            r"[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
            str(row["issuedAt"]),
        )
        or not re.fullmatch(
            r"[A-Za-z0-9_-]{86}", str(row["signature"])
        )
        or any(
            not PROVENANCE_SAFE_TEXT_RE.fullmatch(str(row[name]))
            for name in ("makerVendor", "makerModel", "makerSession")
        )
    ):
        raise GateError("UNVERIFIED", "maker provenance value is invalid")
    return {name: row[name] for name in fields if name != "signature"}


def sign_provenance(
    unsigned: dict[str, Any], private: bytes
) -> dict[str, Any]:
    normalized = provenance_payload(
        {**unsigned, "signature": "A" * 86}
    )
    try:
        signature = Ed25519PrivateKey.from_private_bytes(private).sign(
            canonical_json(normalized)
        )
    except (TypeError, ValueError) as exc:
        raise GateError("UNVERIFIED", "Ed25519 private key is invalid") from exc
    value = dict(normalized)
    value["signature"] = (
        base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    )
    return value


def validate_registry(value: Any) -> dict[str, Any]:
    root = _exact(value, {"version", "repositories"}, "gate registry")
    if root["version"] != 1 or not isinstance(root["repositories"], list):
        raise GateError("UNVERIFIED", "gate registry version/list is invalid")
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    required = {
        "repository",
        "checkout",
        "brokerUrl",
        "appId",
        "rulesetScope",
        "rulesetId",
        "machineWorkflowRepositoryId",
        "machineWorkflowSha",
        "provenanceKeyId",
        "provenanceKeyFile",
    }
    for raw in root["repositories"]:
        row = _exact(raw, required, "gate registry repository")
        repository = str(row["repository"])
        if not REPO_RE.fullmatch(repository) or repository in seen:
            raise GateError(
                "UNVERIFIED", "gate registry repository is invalid/duplicate"
            )
        checkout = Path(str(row["checkout"]))
        key_file = Path(str(row["provenanceKeyFile"]))
        parsed = urllib.parse.urlsplit(str(row["brokerUrl"]))
        if (
            not checkout.is_absolute()
            or not key_file.is_absolute()
            or parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise GateError(
                "UNVERIFIED", "gate registry paths/broker URL are invalid"
            )
        if type(row["appId"]) is not int or row["appId"] <= 0:
            raise GateError("UNVERIFIED", "gate registry App id is invalid")
        if row["rulesetScope"] != "organization":
            raise GateError(
                "UNVERIFIED",
                "only an organization ruleset can bind the protected "
                "machine workflow",
            )
        if type(row["rulesetId"]) is not int or row["rulesetId"] <= 0:
            raise GateError("UNVERIFIED", "gate registry ruleset id is invalid")
        if (
            type(row["machineWorkflowRepositoryId"]) is not int
            or row["machineWorkflowRepositoryId"] <= 0
            or not SHA_RE.fullmatch(str(row["machineWorkflowSha"]))
        ):
            raise GateError(
                "UNVERIFIED",
                "gate registry machine-workflow source is invalid",
            )
        if not KEY_ID_RE.fullmatch(str(row["provenanceKeyId"])):
            raise GateError("UNVERIFIED", "gate registry provenance key id is invalid")
        seen.add(repository)
        validated.append(dict(row))
    return {"version": 1, "repositories": validated}


def load_registry(path: Path | None = None) -> dict[str, Any]:
    target = path or registry_path()
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise GateError("UNAVAILABLE", f"gate registry unavailable: {target}") from exc
    if not raw or len(raw) > MAX_HTTP_RESPONSE_BYTES:
        raise GateError("UNVERIFIED", "gate registry size is invalid")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise GateError("UNVERIFIED", "gate registry JSON is invalid") from exc
    return validate_registry(value)


def ruleset_payload(
    app_id: int,
    *,
    scope: str,
    workflow_repository_id: int,
    workflow_sha: str,
    repository_name: str | None = None,
) -> dict[str, Any]:
    if type(app_id) is not int or app_id <= 0:
        raise GateError("UNVERIFIED", "GitHub App id is invalid")
    if scope != "organization":
        raise GateError(
            "UNVERIFIED",
            "protected machine workflows require an organization ruleset",
        )
    if (
        type(workflow_repository_id) is not int
        or workflow_repository_id <= 0
        or not SHA_RE.fullmatch(workflow_sha)
    ):
        raise GateError(
            "UNVERIFIED", "machine workflow repository/SHA is invalid"
        )
    ref_name = {
        "include": ["~DEFAULT_BRANCH", "refs/heads/release/*"],
        "exclude": [],
    }
    conditions: dict[str, Any] = {"ref_name": ref_name}
    if repository_name is not None:
        raise GateError(
            "UNVERIFIED", "organization ruleset cannot target one name here"
        )
    conditions["repository_name"] = {
        "include": ["~ALL"],
        "exclude": [],
        "protected": True,
    }
    return {
        "name": RULESET_NAME,
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": conditions,
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {
                "type": "pull_request",
                "parameters": {
                    "allowed_merge_methods": ["merge", "squash", "rebase"],
                    "dismiss_stale_reviews_on_push": True,
                    "require_code_owner_review": False,
                    "require_last_push_approval": False,
                    "required_approving_review_count": 0,
                    "required_review_thread_resolution": True,
                },
            },
            {
                "type": "required_status_checks",
                "parameters": {
                    "do_not_enforce_on_create": False,
                    "required_status_checks": [
                        {
                            "context": EXTERNAL_CHECK,
                            "integration_id": app_id,
                        },
                    ],
                    "strict_required_status_checks_policy": True,
                },
            },
            {
                "type": "workflows",
                "parameters": {
                    "do_not_enforce_on_create": False,
                    "workflows": [
                        {
                            "path": MACHINE_WORKFLOW_PATH,
                            "repository_id": workflow_repository_id,
                            "sha": workflow_sha,
                        }
                    ],
                },
            },
        ],
    }


def validate_live_ruleset(
    value: Any,
    app_id: int,
    *,
    scope: str,
    workflow_repository_id: int,
    workflow_sha: str,
    repository_name: str | None = None,
) -> list[str]:
    expected = ruleset_payload(
        app_id,
        scope=scope,
        workflow_repository_id=workflow_repository_id,
        workflow_sha=workflow_sha,
        repository_name=repository_name,
    )
    if not isinstance(value, dict):
        return ["ruleset response is not an object"]
    drift: list[str] = []
    for field in ("name", "target", "enforcement", "conditions"):
        if value.get(field) != expected[field]:
            drift.append(f"{field} differs from canonical policy")
    if value.get("bypass_actors") != []:
        drift.append("bypass_actors is missing or non-empty")
    raw_rules = value.get("rules")
    if not isinstance(raw_rules, list):
        return drift + ["rules are missing"]
    actual_by_type: dict[str, dict[str, Any]] = {}
    for row in raw_rules:
        if not isinstance(row, dict) or not isinstance(row.get("type"), str):
            drift.append("rules contain an invalid entry")
            continue
        if row["type"] in actual_by_type:
            drift.append(f"duplicate rule type: {row['type']}")
            continue
        actual_by_type[row["type"]] = row
    expected_by_type = {row["type"]: row for row in expected["rules"]}
    for rule_type in sorted(set(actual_by_type) - set(expected_by_type)):
        drift.append(f"unexpected rule type: {rule_type}")
    for rule_type, expected_rule in expected_by_type.items():
        if actual_by_type.get(rule_type) != expected_rule:
            drift.append(f"rule differs or is missing: {rule_type}")
    return drift


def gh_json(
    arguments: list[str],
    *,
    input_value: dict[str, Any] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> Any:
    command = [
        "gh",
        "api",
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        f"X-GitHub-Api-Version: {API_VERSION}",
        *arguments,
    ]
    payload = canonical_json(input_value) if input_value is not None else None
    try:
        completed = runner(
            command,
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GateError("UNAVAILABLE", "GitHub CLI invocation failed") from exc
    if completed.returncode != 0:
        reason = completed.stderr[:1000].decode("utf-8", errors="replace")
        raise GateError(
            "UNAVAILABLE",
            "GitHub API request failed"
            + (f": {reason.strip()}" if reason.strip() else ""),
        )
    if len(completed.stdout) > MAX_GH_OUTPUT_BYTES:
        raise GateError("UNVERIFIED", "GitHub API response exceeds its bound")
    try:
        return json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise GateError("UNVERIFIED", "GitHub API response is invalid JSON") from exc


def fetch_ruleset(
    repository: str,
    scope: str,
    ruleset_id: int,
    *,
    gh: Callable[..., Any] = gh_json,
) -> dict[str, Any]:
    if not REPO_RE.fullmatch(repository):
        raise GateError("UNVERIFIED", "repository coordinate is invalid")
    owner, _ = repository.split("/", 1)
    if scope == "organization":
        path = f"orgs/{owner}/rulesets/{ruleset_id}"
    elif scope == "repository":
        path = f"repos/{repository}/rulesets/{ruleset_id}"
    else:
        raise GateError("UNVERIFIED", "ruleset scope is invalid")
    value = gh([path])
    if not isinstance(value, dict):
        raise GateError("UNVERIFIED", "GitHub ruleset response is invalid")
    return value


def broker_ready(
    base_url: str,
    repository: str,
    app_id: int,
    provenance_key_id: str,
    provenance_public_key_value: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise GateError("UNVERIFIED", "broker URL must be credential-free HTTPS")
    if (
        not REPO_RE.fullmatch(repository)
        or type(app_id) is not int
        or app_id <= 0
        or not KEY_ID_RE.fullmatch(provenance_key_id)
        or not re.fullmatch(
            r"[A-Za-z0-9_-]{43}", provenance_public_key_value
        )
    ):
        raise GateError("UNVERIFIED", "broker enrollment query is invalid")
    url = (
        base_url.rstrip("/")
        + "/readyz?"
        + urllib.parse.urlencode(
            {"repository": repository, "appId": str(app_id)}
        )
    )
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "itd-gate-doctor/1"},
    )
    try:
        with opener(request, timeout=10) as response:
            raw = response.read(MAX_HTTP_RESPONSE_BYTES + 1)
            status = getattr(response, "status", 200)
    except OSError as exc:
        raise GateError("UNAVAILABLE", "broker readiness request failed") from exc
    if status != 200 or len(raw) > MAX_HTTP_RESPONSE_BYTES:
        raise GateError("UNAVAILABLE", "broker is not ready")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise GateError("UNVERIFIED", "broker readiness response is invalid") from exc
    if not isinstance(value, dict) or value.get("status") != "ready":
        raise GateError("UNAVAILABLE", "broker readiness response is not ready")
    try:
        expected_policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GateError(
            "UNAVAILABLE", "installed broker policy is unavailable"
        ) from exc
    expected_sha = hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()
    expected_reviewers = [
        {
            "id": reviewer_id,
            "vendor": row["vendor"],
            "model": row["model"],
        }
        for reviewer_id, row in sorted(
            expected_policy["routing"]["reviewers"].items()
        )
    ]
    if (
        value.get("policyId") != expected_policy["id"]
        or value.get("policySha256") != expected_sha
        or value.get("reviewers") != expected_reviewers
    ):
        raise GateError(
            "UNVERIFIED",
            "broker policy or reviewer routes differ from installed ITD",
        )
    budget = value.get("budget")
    budget_fields = {
        "period",
        "reservedMicrousd",
        "spentMicrousd",
        "monthlyMicrousd",
        "reservationMicrousd",
        "remainingMicrousd",
        "admissionAvailable",
    }
    if not isinstance(budget, dict) or set(budget) != budget_fields:
        raise GateError("UNVERIFIED", "broker budget status is invalid")
    numeric = [
        budget.get(name)
        for name in (
            "reservedMicrousd",
            "spentMicrousd",
            "monthlyMicrousd",
            "reservationMicrousd",
            "remainingMicrousd",
        )
    ]
    if (
        any(type(item) is not int or item < 0 for item in numeric)
        or type(budget.get("period")) is not str
        or not re.fullmatch(r"[0-9]{4}-(?:0[1-9]|1[0-2])", budget["period"])
        or type(budget.get("admissionAvailable")) is not bool
    ):
        raise GateError("UNVERIFIED", "broker budget values are invalid")
    if not budget["admissionAvailable"]:
        raise GateError(
            "UNAVAILABLE", "broker budget cannot admit another review"
        )
    enrollment = value.get("enrollment")
    if (
        not isinstance(enrollment, dict)
        or set(enrollment)
        != {"repository", "appId", "receiptSha256", "enrolledAt"}
        or enrollment.get("repository") != repository
        or enrollment.get("appId") != app_id
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(enrollment.get("receiptSha256", ""))
        )
        or not isinstance(enrollment.get("enrolledAt"), str)
    ):
        raise GateError(
            "UNVERIFIED", "broker repository enrollment is missing or stale"
        )
    keys = value.get("provenanceKeys")
    matching_keys = [
        row
        for row in keys
        if (
            isinstance(row, dict)
            and row.get("repository") == repository
            and row.get("keyId") == provenance_key_id
        )
    ] if isinstance(keys, list) else []
    if (
        len(matching_keys) != 1
        or matching_keys[0].get("publicKey")
        != provenance_public_key_value
        or matching_keys[0].get("status") != "active"
    ):
        raise GateError(
            "UNVERIFIED",
            "broker provenance key does not match the local signer",
        )
    return value


def adopted_checkout(path: Path) -> list[str]:
    drift: list[str] = []
    if not path.is_dir():
        return ["checkout directory is missing"]
    contract = path / ".itd" / "VERIFICATION_CONTRACT.json"
    if not contract.is_file():
        return [".itd/VERIFICATION_CONTRACT.json is missing"]
    try:
        tracked = subprocess.run(
            [
                "git",
                "-C",
                str(path),
                "ls-files",
                "--error-unmatch",
                ".itd/VERIFICATION_CONTRACT.json",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ["Git tracking state is unavailable"]
    if tracked.returncode != 0:
        drift.append(".itd/VERIFICATION_CONTRACT.json is not tracked")
    try:
        value = json.loads(contract.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return drift + ["verification contract is invalid JSON"]
    drift.extend(verification_contract_drift(value))
    if isinstance(value, dict) and isinstance(value.get("commands"), list):
        for index, row in enumerate(value["commands"]):
            if not isinstance(row, dict):
                continue
            paths = row.get("trustedVerifierPaths")
            if not isinstance(paths, list):
                continue
            has_namespace = any(
                isinstance(raw, str)
                and (path / raw).is_dir()
                and not (path / raw).is_symlink()
                for raw in paths
            )
            if not has_namespace:
                drift.append(
                    f"verification command {index + 1} has no tracked "
                    "verifier namespace directory"
                )
    return drift


def verification_contract_drift(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["verification contract is not an object"]
    drift: list[str] = []
    if value.get("version") != 2:
        drift.append("verification contract is not fail-closed version 2")
    if value.get("failClosed") is None:
        drift.append("verification contract is not fail-closed")
    commands = value.get("commands")
    if not isinstance(commands, list) or not commands:
        return drift + ["verification contract has no machine commands"]
    expected_fields = {
        "id",
        "argv",
        "trustedVerifierPaths",
        "timeoutSeconds",
        "expectedOutput",
        "passFailParser",
    }
    allowed_parsers = {
        "exit_code_zero",
        "stdout_contains",
        "json_field_equals",
        "manual_evidence",
    }
    for index, row in enumerate(commands):
        label = f"verification command {index + 1}"
        if not isinstance(row, dict) or set(row) != expected_fields:
            drift.append(f"{label} fields are invalid")
            continue
        argv = row.get("argv")
        paths = row.get("trustedVerifierPaths")
        timeout = row.get("timeoutSeconds")
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(item, str) or not item for item in argv)
        ):
            drift.append(f"{label} argv is invalid")
        else:
            executable = Path(
                argv[0].replace("\\", "/")
            ).name.casefold()
            if (
                executable.startswith("python")
                and "-I" not in argv[1:]
            ):
                drift.append(f"{label} Python verifier is not isolated")
            if (
                any(
                    item.replace("\\", "/").endswith(
                        "/itd_py.sh"
                    )
                    or item == "itd_py.sh"
                    for item in argv
                )
                and "--itd-isolated" not in argv
            ):
                drift.append(f"{label} ITD Python launcher is not isolated")
        if not isinstance(paths, list) or not paths:
            drift.append(f"{label} has no trusted verifier paths")
        else:
            normalized: list[str] = []
            for raw in paths:
                if not isinstance(raw, str):
                    drift.append(f"{label} trusted verifier path is invalid")
                    continue
                path = PurePosixPath(raw.replace("\\", "/"))
                if (
                    not raw
                    or path.is_absolute()
                    or ".." in path.parts
                    or any(part in {"", "."} for part in path.parts)
                ):
                    drift.append(
                        f"{label} trusted verifier path is unsafe"
                    )
                else:
                    normalized.append(path.as_posix())
            if len(normalized) != len(set(normalized)):
                drift.append(
                    f"{label} trusted verifier paths contain duplicates"
                )
        if type(timeout) is not int or not 1 <= timeout <= 3600:
            drift.append(f"{label} timeout is invalid")
        if row.get("passFailParser") not in allowed_parsers:
            drift.append(f"{label} parser is invalid")
    return drift


def protected_base_contract(
    repository: str,
    *,
    gh: Callable[..., Any] = gh_json,
) -> list[str]:
    try:
        metadata = gh([f"repos/{repository}"])
    except GateError as exc:
        return [f"protected base: {exc.status}: {exc.reason}"]
    if not isinstance(metadata, dict):
        return ["protected base repository metadata is invalid"]
    default_branch = metadata.get("default_branch")
    if (
        not isinstance(default_branch, str)
        or not re.fullmatch(
            r"[^\x00-\x20\x7f]{1,200}", default_branch
        )
    ):
        return ["protected base default branch is invalid"]
    endpoint = (
        f"repos/{repository}/contents/"
        ".itd/VERIFICATION_CONTRACT.json?ref="
        + urllib.parse.quote(default_branch, safe="")
    )
    try:
        value = gh([endpoint])
    except GateError as exc:
        return [f"protected base contract: {exc.status}: {exc.reason}"]
    if not isinstance(value, dict):
        return ["protected base contract response is invalid"]
    content = value.get("content")
    size = value.get("size")
    if (
        value.get("type") != "file"
        or value.get("path") != ".itd/VERIFICATION_CONTRACT.json"
        or not SHA_RE.fullmatch(str(value.get("sha", "")))
        or value.get("encoding") != "base64"
        or type(size) is not int
        or not 1 <= size <= MAX_HTTP_RESPONSE_BYTES
        or not isinstance(content, str)
    ):
        return ["protected base contract metadata is invalid"]
    try:
        raw = base64.b64decode(
            "".join(content.split()).encode("ascii"),
            validate=True,
        )
        contract = json.loads(raw.decode("utf-8"))
    except (
        UnicodeEncodeError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return ["protected base contract content is invalid"]
    if len(raw) != size:
        return ["protected base contract size differs"]
    blob_sha = hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()
    if blob_sha != value["sha"]:
        return ["protected base contract Git blob SHA differs"]
    return [
        f"protected base: {item}"
        for item in verification_contract_drift(contract)
    ]


def doctor_entry(
    entry: dict[str, Any],
    *,
    gh: Callable[..., Any] = gh_json,
    readiness: Callable[..., dict[str, Any]] = broker_ready,
) -> dict[str, Any]:
    drift = adopted_checkout(Path(entry["checkout"]))
    drift.extend(protected_base_contract(entry["repository"], gh=gh))
    try:
        version = installed_version()
    except GateError as exc:
        drift.append(f"version: {exc.status}: {exc.reason}")
        version = None
    try:
        live = fetch_ruleset(
            entry["repository"],
            entry["rulesetScope"],
            entry["rulesetId"],
            gh=gh,
        )
        drift.extend(
            validate_live_ruleset(
                live,
                entry["appId"],
                scope=entry["rulesetScope"],
                workflow_repository_id=entry[
                    "machineWorkflowRepositoryId"
                ],
                workflow_sha=entry["machineWorkflowSha"],
                repository_name=entry["repository"].split("/", 1)[1]
                if entry["rulesetScope"] == "repository"
                else None,
            )
        )
    except GateError as exc:
        drift.append(f"ruleset: {exc.status}: {exc.reason}")
    key_path = Path(entry["provenanceKeyFile"])
    try:
        private_key = read_provenance_private_key(key_path)
        public_key = provenance_public_key(private_key)
    except GateError as exc:
        drift.append(f"provenance key: {exc.status}: {exc.reason}")
        public_key = None
    if public_key is not None:
        try:
            ready = readiness(
                entry["brokerUrl"],
                entry["repository"],
                entry["appId"],
                entry["provenanceKeyId"],
                public_key,
            )
        except GateError as exc:
            drift.append(f"broker: {exc.status}: {exc.reason}")
            ready = None
    else:
        ready = None
    return {
        "repository": entry["repository"],
        "status": "PROTECTED" if not drift else "UNVERIFIED",
        "drift": drift,
        "itdVersion": version,
        "broker": ready,
    }
