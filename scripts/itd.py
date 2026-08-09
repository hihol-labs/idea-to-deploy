#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "skills" / "_shared"
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(ROOT / "scripts"))

import itd_gate_control as gate  # noqa: E402
import itd_machine_oracle as machine  # noqa: E402


MAX_COMMAND_OUTPUT = 4 * 1024 * 1024
MAX_BROKER_RESPONSE = 1024 * 1024
SENSITIVE_ENV_RE = re.compile(
    r"(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH)",
    re.IGNORECASE,
)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


class RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req, fp, code, msg, headers, newurl
    ):
        del req, fp, code, msg, headers, newurl
        raise gate.GateError(
            "UNVERIFIED", "broker provenance redirect is forbidden"
        )


def read_signing_material(path: Path) -> bytes:
    return gate.read_provenance_private_key(path)


def sign_provenance(unsigned: dict[str, Any], material: bytes) -> dict[str, Any]:
    return gate.sign_provenance(unsigned, material)


def save_registry(value: dict[str, Any], path: Path | None = None) -> Path:
    validated = gate.validate_registry(value)
    target = (path or gate.registry_path()).resolve()
    gate.assert_registry_write_isolated(validated, target)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    data = json.dumps(
        validated,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8") + b"\n"
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
        os.replace(temporary, target)
        if os.name != "nt":
            target.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def save_json_document(value: dict[str, Any], target: Path) -> Path:
    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = target.with_name(
        f".{target.name}.{os.getpid()}.tmp"
    )
    data = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8") + b"\n"
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
        os.replace(temporary, target)
        if os.name != "nt":
            target.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    input_bytes: bytes | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    writer = None
    errors = []
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=(os.name != "nt"),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        if process.stdin:
            def feed_input() -> None:
                try:
                    process.stdin.write(input_bytes)
                except BrokenPipeError:
                    pass
                except OSError as exc:
                    errors.append(exc)
                finally:
                    process.stdin.close()

            writer = threading.Thread(target=feed_input, daemon=True)
            writer.start()
        result = machine._capture_process(
            process,
            started="",
            timeout=timeout,
            max_output_bytes=MAX_COMMAND_OUTPUT,
        )
    except (OSError, machine.OracleError) as exc:
        raise gate.GateError(
            "UNAVAILABLE", f"command unavailable: {command[0]}"
        ) from exc
    if writer is not None:
        writer.join(10)
        if writer.is_alive() or errors:
            raise gate.GateError("UNAVAILABLE", "command input failed")
    if result["timedOut"]:
        raise gate.GateError("UNAVAILABLE", f"command unavailable: {command[0]}")
    if result["outputOverflow"]:
        raise gate.GateError("UNVERIFIED", "command output exceeds its bound")
    completed = subprocess.CompletedProcess(
        command, result["exitCode"], result["stdout"], result["stderr"]
    )
    if check and completed.returncode != 0:
        reason = completed.stderr[:1000].decode("utf-8", errors="replace")
        raise gate.GateError(
            "UNAVAILABLE",
            f"{command[0]} command failed"
            + (f": {reason.strip()}" if reason.strip() else ""),
        )
    return completed


def run_json(
    command: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> tuple[Any | None, subprocess.CompletedProcess[bytes]]:
    completed = run(command, cwd=cwd, check=check)
    if completed.returncode != 0:
        return None, completed
    try:
        return json.loads(completed.stdout.decode("utf-8")), completed
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise gate.GateError(
            "UNVERIFIED", f"{command[0]} returned invalid JSON"
        ) from exc


def repository_entry(
    registry: dict[str, Any],
    root: Path,
    repository: str | None,
) -> dict[str, Any]:
    root = root.resolve()
    matches = [
        row
        for row in registry["repositories"]
        if Path(row["checkout"]).resolve() == root
        and (
            repository is None
            or row["repository"].casefold() == repository.casefold()
        )
    ]
    if len(matches) != 1:
        raise gate.GateError(
            "UNVERIFIED",
            "checkout is not uniquely registered in the ITD gate registry",
        )
    return matches[0]


def registry_row(
    *,
    repository: str,
    checkout: Path,
    broker_url: str,
    app_id: int,
    scope: str,
    ruleset_id: int,
    workflow_repository_id: int,
    workflow_sha: str,
    provenance_key_id: str,
    provenance_key_file: Path,
) -> dict[str, Any]:
    return {
        "repository": repository,
        "checkout": str(checkout.resolve()),
        "brokerUrl": broker_url.rstrip("/"),
        "appId": app_id,
        "rulesetScope": scope,
        "rulesetId": ruleset_id,
        "machineWorkflowRepositoryId": workflow_repository_id,
        "machineWorkflowSha": workflow_sha,
        "provenanceKeyId": provenance_key_id,
        "provenanceKeyFile": str(provenance_key_file.resolve()),
    }


def profile_registry_row(args: argparse.Namespace) -> dict[str, Any]:
    receipt = args.local_review_receipt_file
    key_file = args.provenance_key_file
    return {
        "repository": args.repository,
        "checkout": str(args.checkout.resolve()),
        "repositoryOwnerType": args.repository_owner_type,
        "deploymentProfile": args.deployment_profile,
        "protectionProfile": args.protection_profile,
        "localReviewReceiptFile": (
            str(receipt.resolve()) if receipt is not None else None
        ),
        "localReviewUnitId": args.local_review_unit_id,
        "localReviewRiskTier": args.local_review_risk_tier,
        "localReviewProducerKeyringSha256": (
            args.local_review_producer_keyring_sha256
        ),
        "brokerUrl": (
            args.broker_url.rstrip("/") if args.broker_url is not None else None
        ),
        "appId": args.app_id,
        "appOwner": args.app_owner,
        "appOwnerType": args.app_owner_type,
        "appVisibility": args.app_visibility,
        "rulesetScope": args.scope,
        "rulesetId": args.ruleset_id,
        "machineWorkflowRepositoryId": args.workflow_repository_id,
        "machineWorkflowSha": args.workflow_sha,
        "provenanceKeyId": args.provenance_key_id,
        "provenanceKeyFile": (
            str(key_file.resolve()) if key_file is not None else None
        ),
        "enrollmentReceiptSha256": args.enrollment_receipt_sha256,
    }


def persist_registry_row(
    row: dict[str, Any],
    path: Path,
) -> Path:
    if path.exists():
        current = gate.load_registry(path)
        if current["version"] != 1:
            raise gate.GateError(
                "BLOCKED", "legacy registration cannot rewrite a v2 registry"
            )
    else:
        current = {"version": 1, "repositories": []}
    rows = [
        value
        for value in current["repositories"]
        if value["repository"].casefold()
        != str(row["repository"]).casefold()
    ]
    rows.append(row)
    rows.sort(key=lambda value: value["repository"].casefold())
    return save_registry({"version": 1, "repositories": rows}, path)


def persist_profile_registry_row(row: dict[str, Any], path: Path) -> Path:
    if path.exists():
        current = gate.load_registry(path)
        if current["version"] != 2:
            raise gate.GateError(
                "BLOCKED",
                "legacy v1 registry requires explicit profile re-registration",
            )
    else:
        current = {"version": 2, "repositories": []}
    rows = [
        value for value in current["repositories"]
        if value["repository"].casefold()
        != str(row["repository"]).casefold()
    ]
    rows.append(row)
    rows.sort(key=lambda value: value["repository"].casefold())
    return save_registry({"version": 2, "repositories": rows}, path)


def register_entry(args: argparse.Namespace) -> dict[str, Any]:
    path = args.registry.resolve() if args.registry else gate.registry_path()
    row = registry_row(
        repository=args.repository,
        checkout=args.checkout,
        broker_url=args.broker_url,
        app_id=args.app_id,
        scope=args.scope,
        ruleset_id=args.ruleset_id,
        workflow_repository_id=args.workflow_repository_id,
        workflow_sha=args.workflow_sha,
        provenance_key_id=args.provenance_key_id,
        provenance_key_file=args.provenance_key_file,
    )
    target = persist_registry_row(row, path)
    return {
        "status": "REGISTERED",
        "repository": args.repository,
        "registry": str(target),
    }


def register_profile_entry(args: argparse.Namespace) -> dict[str, Any]:
    path = args.registry.resolve() if args.registry else gate.registry_path()
    row = gate.validate_profile_registry(
        {"version": 2, "repositories": [profile_registry_row(args)]}
    )["repositories"][0]
    target = persist_profile_registry_row(row, path)
    return {
        "status": "REGISTERED",
        "repository": row["repository"],
        "deploymentProfile": row["deploymentProfile"],
        "protectionProfile": row["protectionProfile"],
        "registry": str(target),
    }


def adopt_gate(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    if not root.is_dir():
        raise gate.GateError(
            "UNVERIFIED", "adoption checkout directory is missing"
        )
    resolved_git_root = Path(
        git(root, "rev-parse", "--show-toplevel")
    ).resolve()
    if resolved_git_root != root:
        raise gate.GateError(
            "BLOCKED", "gate adoption must target the exact Git root"
        )
    remote = git(root, "remote", "get-url", "--push", "origin")
    repository = gate.github_repository_from_remote(remote)
    row = registry_row(
        repository=repository,
        checkout=root,
        broker_url=args.broker_url,
        app_id=args.app_id,
        scope=args.scope,
        ruleset_id=args.ruleset_id,
        workflow_repository_id=args.workflow_repository_id,
        workflow_sha=args.workflow_sha,
        provenance_key_id=args.provenance_key_id,
        provenance_key_file=args.provenance_key_file,
    )
    inspection = gate.doctor_entry(row)
    drift = inspection.get("drift")
    if not isinstance(drift, list) or any(
        not isinstance(item, str) for item in drift
    ):
        raise gate.GateError(
            "UNVERIFIED", "gate adoption doctor result is invalid"
        )
    if drift:
        raise gate.GateError(
            "UNVERIFIED",
            "GitHub gate is not enforceable: " + "; ".join(drift),
        )
    path = args.registry.resolve() if args.registry else gate.registry_path()
    target = persist_registry_row(row, path)
    return {
        "status": "PROTECTED",
        "repository": repository,
        "registry": str(target),
        "rulesetId": args.ruleset_id,
        "appId": args.app_id,
        "drift": drift,
    }


def generate_provenance_key(args: argparse.Namespace) -> dict[str, Any]:
    for label, value, maximum in (
        ("maker vendor", args.maker_vendor, 100),
        ("maker model", args.maker_model, 200),
        ("issuer principal", args.issuer_principal, 200),
    ):
        if (
            not isinstance(value, str)
            or not value
            or len(value) > maximum
            or "\r" in value
            or "\n" in value
        ):
            raise gate.GateError("UNVERIFIED", f"{label} is invalid")
    if (
        not gate.REPO_RE.fullmatch(args.repository)
        or not gate.KEY_ID_RE.fullmatch(args.key_id)
    ):
        raise gate.GateError(
            "UNVERIFIED", "repository or provenance key id is invalid"
        )
    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    gate.write_provenance_private_key(args.output, private_raw)
    return {
        "status": "GENERATED",
        "privateKeyFile": str(args.output.resolve()),
        "publicKeyRecord": {
            "repository": args.repository,
            "keyId": args.key_id,
            "authorizedMakerVendor": args.maker_vendor,
            "authorizedMakerModel": args.maker_model,
            "publicKey": gate.provenance_public_key(private_raw),
            "issuerPrincipal": args.issuer_principal,
            "status": "active",
        },
    }


def ruleset_endpoint(
    repository: str,
    scope: str,
    ruleset_id: int | None,
) -> str:
    if not gate.REPO_RE.fullmatch(repository):
        raise gate.GateError("UNVERIFIED", "repository is invalid")
    if (
        ruleset_id is not None
        and (type(ruleset_id) is not int or ruleset_id <= 0)
    ):
        raise gate.GateError(
            "UNVERIFIED", "ruleset id must be a positive integer"
        )
    owner, _ = repository.split("/", 1)
    prefix = (
        f"orgs/{owner}/rulesets"
        if scope == "organization"
        else f"repos/{repository}/rulesets"
    )
    return f"{prefix}/{ruleset_id}" if ruleset_id is not None else prefix


def apply_ruleset(args: argparse.Namespace) -> dict[str, Any]:
    endpoint = ruleset_endpoint(
        args.repository, args.scope, args.ruleset_id
    )
    repository_name = (
        args.repository.split("/", 1)[1]
        if args.scope == "repository"
        else None
    )
    payload = gate.ruleset_payload(
        args.app_id,
        scope=args.scope,
        workflow_repository_id=args.workflow_repository_id,
        workflow_sha=args.workflow_sha,
        repository_name=repository_name,
    )
    if not args.apply:
        return {
            "status": "PREVIEW",
            "endpoint": endpoint,
            "payload": payload,
        }
    method = "PUT" if args.ruleset_id is not None else "POST"
    result = gate.gh_json(
        ["--method", method, endpoint, "--input", "-"],
        input_value=payload,
    )
    if not isinstance(result, dict) or type(result.get("id")) is not int:
        raise gate.GateError(
            "UNVERIFIED", "GitHub did not return a ruleset id"
        )
    drift = gate.validate_live_ruleset(
        result,
        args.app_id,
        scope=args.scope,
        workflow_repository_id=args.workflow_repository_id,
        workflow_sha=args.workflow_sha,
        repository_name=repository_name,
    )
    if drift:
        raise gate.GateError(
            "UNVERIFIED",
            "created ruleset differs from canonical policy: "
            + "; ".join(drift),
        )
    return {
        "status": "ENFORCED",
        "repository": args.repository,
        "scope": args.scope,
        "rulesetId": result["id"],
    }


def observe_enrollment(args: argparse.Namespace) -> dict[str, Any]:
    repository = args.repository
    if not gate.REPO_RE.fullmatch(repository):
        raise gate.GateError("UNVERIFIED", "repository is invalid")
    owner, repository_name = repository.split("/", 1)
    live_ruleset = gate.fetch_ruleset(
        repository,
        args.scope,
        args.ruleset_id,
    )
    drift = gate.validate_live_ruleset(
        live_ruleset,
        args.app_id,
        scope=args.scope,
        workflow_repository_id=args.workflow_repository_id,
        workflow_sha=args.workflow_sha,
        repository_name=(
            repository_name if args.scope == "repository" else None
        ),
    )
    if drift:
        raise gate.GateError(
            "UNVERIFIED",
            "live ruleset differs from canonical policy: "
            + "; ".join(drift),
    )
    repository_value = gate.gh_json([f"repos/{repository}"])
    app = gate.gh_json([f"apps/{args.app_slug}"])
    workflow_repository = gate.gh_json(
        [f"repos/{gate.MACHINE_WORKFLOW_REPOSITORY}"]
    )
    workflow_commit = gate.gh_json(
        [
            f"repos/{gate.MACHINE_WORKFLOW_REPOSITORY}/commits/"
            f"{args.workflow_sha}"
        ]
    )
    if (
        not isinstance(repository_value, dict)
        or not isinstance(app, dict)
        or not isinstance(workflow_repository, dict)
        or not isinstance(workflow_commit, dict)
    ):
        raise gate.GateError(
            "UNVERIFIED", "GitHub enrollment metadata is invalid"
        )
    default_branch = repository_value.get("default_branch")
    app_owner = app.get("owner")
    permissions = app.get("permissions")
    events = app.get("events")
    if (
        not isinstance(default_branch, str)
        or not re.fullmatch(
            r"[^\x00-\x20\x7f]{1,200}", default_branch
        )
        or app.get("id") != args.app_id
        or app.get("slug") != args.app_slug
        or not isinstance(app.get("client_id"), str)
        or not gate.KEY_ID_RE.fullmatch(str(app.get("client_id")))
        or not isinstance(app.get("node_id"), str)
        or not app["node_id"]
        or not isinstance(app_owner, dict)
        or str(app_owner.get("login", "")).casefold()
        != owner.casefold()
        or not isinstance(permissions, dict)
        or permissions
        != {
            "checks": "write",
            "contents": "read",
            "metadata": "read",
            "pull_requests": "read",
        }
        or not isinstance(events, list)
        or len(events) != 2
        or set(events) != {"pull_request", "merge_group"}
        or workflow_repository.get("id")
        != args.workflow_repository_id
        or str(workflow_repository.get("full_name", "")).casefold()
        != gate.MACHINE_WORKFLOW_REPOSITORY.casefold()
        or workflow_repository.get("visibility") != "public"
        or workflow_commit.get("sha") != args.workflow_sha
    ):
        raise gate.GateError(
            "UNVERIFIED",
            "GitHub App identity, exact least-privilege permissions, "
            "events, or repository metadata differ from the broker "
            "contract",
        )
    try:
        policy = json.loads(gate.POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise gate.GateError(
            "UNAVAILABLE", "installed broker policy is unavailable"
        ) from exc
    if (
        not isinstance(policy, dict)
        or not isinstance(policy.get("id"), str)
        or not policy["id"]
    ):
        raise gate.GateError(
            "UNVERIFIED", "installed broker policy identity is invalid"
        )
    observed_at = (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    receipt = {
        "repository": repository,
        "rulesetId": args.ruleset_id,
        "rulesetEnforcement": "active",
        "rulesetTarget": "branch",
        "defaultBranchRef": f"refs/heads/{default_branch}",
        "protectedRefPatterns": {
            "~DEFAULT_BRANCH": True,
            "refs/heads/release/*": True,
        },
        "excludedRefPatterns": {},
        "requiredPullRequest": True,
        "requireUpToDate": True,
        "requiredStatusChecks": {
            "externalReview": {
                "name": gate.EXTERNAL_CHECK,
                "expectedPublisher": "github-app-integration-id",
                "integrationId": args.app_id,
            },
            "machineOracle": {
                "name": gate.MACHINE_CHECK,
                "expectedPublisher": "github-actions",
                "integrationId": gate.GITHUB_ACTIONS_INTEGRATION_ID,
                "authority": "organization-ruleset-workflow",
                "workflowRepository": gate.MACHINE_WORKFLOW_REPOSITORY,
                "workflowRepositoryId": args.workflow_repository_id,
                "workflowPath": gate.MACHINE_WORKFLOW_PATH,
                "workflowSha": args.workflow_sha,
            },
        },
        "githubAppClientId": app["client_id"],
        "githubAppSlug": app["slug"],
        "githubAppOwner": app_owner["login"],
        "githubAppNodeId": app["node_id"],
        "blockDeletion": True,
        "blockForcePush": True,
        "mergeGroupEventsRequired": True,
        "bypassActors": [],
        "policyId": policy["id"],
        "observedAt": observed_at,
    }
    status = "PREVIEW"
    output = None
    if args.apply:
        output = str(save_json_document(receipt, args.output))
        status = "OBSERVED"
    return {
        "status": status,
        "repository": repository,
        "rulesetId": args.ruleset_id,
        "appId": args.app_id,
        "receipt": receipt,
        "output": output,
    }


def organization_repositories(
    owner: str,
    *,
    gh: Callable[..., Any] = gate.gh_json,
) -> list[str]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", owner):
        raise gate.GateError(
            "UNVERIFIED", "organization identity is invalid"
        )
    repositories: list[str] = []
    seen: set[str] = set()
    for page in range(1, 101):
        value = gh(
            [
                f"orgs/{owner}/repos"
                f"?type=all&per_page=100&page={page}"
            ]
        )
        if not isinstance(value, list):
            raise gate.GateError(
                "UNVERIFIED", "organization repository inventory is invalid"
            )
        if not value:
            break
        for row in value:
            if not isinstance(row, dict):
                raise gate.GateError(
                    "UNVERIFIED",
                    "organization repository inventory entry is invalid",
                )
            full_name = str(row.get("full_name", ""))
            archived = row.get("archived")
            if (
                not gate.REPO_RE.fullmatch(full_name)
                or archived not in {True, False}
                or not full_name.casefold().startswith(
                    owner.casefold() + "/"
                )
                or full_name.casefold() in seen
            ):
                raise gate.GateError(
                    "UNVERIFIED",
                    "organization repository inventory identity is invalid",
                )
            seen.add(full_name.casefold())
            if not archived:
                repositories.append(full_name)
        if len(value) < 100:
            break
    else:
        raise gate.GateError(
            "UNVERIFIED", "organization repository inventory exceeds its bound"
        )
    return sorted(repositories, key=str.casefold)


def doctor(args: argparse.Namespace) -> dict[str, Any]:
    registry = gate.load_registry(args.registry)
    profiled = registry["version"] == 2
    selected = [
        row
        for row in registry["repositories"]
        if args.all
        or row["repository"].casefold() == str(args.repository).casefold()
    ]
    rows = [
        gate.profile_doctor_entry(row) if profiled else gate.doctor_entry(row)
        for row in selected
    ]
    if args.all:
        registered = {
            row["repository"].casefold()
            for row in registry["repositories"]
        }
        owners = {
            row["repository"].split("/", 1)[0]
            for row in registry["repositories"]
            if row["rulesetScope"] == "organization"
            and (
                not profiled
                or row["protectionProfile"] == "organization-workflow"
            )
        }
        for owner in sorted(owners, key=str.casefold):
            for repository in organization_repositories(owner):
                if repository.casefold() not in registered:
                    rows.append(
                        {
                            "repository": repository,
                            "status": "UNVERIFIED",
                            "drift": [
                                "organization repository has no local "
                                "ITD gate registration"
                            ],
                            "itdVersion": None,
                            "broker": None,
                        }
                    )
    if not rows:
        raise gate.GateError("UNVERIFIED", "no registry entries selected")
    rows.sort(key=lambda row: str(row["repository"]).casefold())
    protected = sum(row["status"] == "PROTECTED" for row in rows)
    status = (
        gate.aggregate_claim(rows)
        if profiled
        else "PROTECTED" if protected == len(rows) else "UNVERIFIED"
    )
    return {
        "status": status,
        "protected": protected,
        "total": len(rows),
        "repositories": rows,
    }


def git(root: Path, *arguments: str) -> str:
    completed = run(
        ["git", "-C", str(root), *arguments],
        timeout=30,
    )
    try:
        return completed.stdout.decode("utf-8").strip()
    except UnicodeError as exc:
        raise gate.GateError("UNVERIFIED", "Git output is not UTF-8") from exc


def ensure_clean_branch(root: Path) -> tuple[str, str]:
    status = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise gate.GateError(
            "UNVERIFIED", "working tree must be clean before guarded PR creation"
        )
    branch = git(root, "symbolic-ref", "--short", "HEAD")
    if not branch or branch in {"main", "master"}:
        raise gate.GateError(
            "BLOCKED", "guarded PR must originate from a non-default branch"
        )
    head = git(root, "rev-parse", "HEAD").lower()
    if not gate.SHA_RE.fullmatch(head):
        raise gate.GateError("UNVERIFIED", "Git HEAD is invalid")
    return branch, head


def github_repository_from_remote(value: str) -> str:
    return gate.github_repository_from_remote(value)


def require_registered_origin(root: Path, repository: str) -> None:
    remote = git(root, "remote", "get-url", "--push", "origin")
    actual = github_repository_from_remote(remote)
    if actual.casefold() != repository.casefold():
        raise gate.GateError(
            "BLOCKED",
            f"origin repository {actual} differs from registry {repository}",
        )


def machine_preflight(root: Path, head: str) -> Path:
    contract = root / ".itd" / "VERIFICATION_CONTRACT.json"
    receipt = machine.execute(root, contract)
    if receipt["headSha"] != head or receipt["status"] != "PASSED":
        raise gate.GateError(
            "UNVERIFIED", "local machine preflight did not pass exact HEAD"
        )
    target = (
        root
        / ".itd-memory"
        / "gate-preflight"
        / f"{head}-machine.json"
    )
    machine.write_receipt(target, receipt)
    return target


def pr_view(root, repository):
    branch = git(root, "symbolic-ref", "--short", "HEAD")
    if (
        not branch
        or len(branch) > 255
        or "\n" in branch
        or "\r" in branch
        or "\0" in branch
        or '"' in branch
    ):
        raise gate.GateError("UNVERIFIED", "current Git branch is invalid")
    value, completed = run_json(
        [
            "gh",
            "pr",
            "view",
            branch,
            "--repo",
            repository,
            "--json",
            "number,headRefName,headRefOid,baseRefOid,url,isDraft,state",
        ],
        cwd=root,
        check=False,
    )
    if completed.returncode != 0:
        try:
            stderr = completed.stderr.decode("utf-8")
        except UnicodeError as exc:
            raise gate.GateError(
                "UNVERIFIED", "GitHub PR lookup error is not UTF-8"
            ) from exc
        expected = f'no pull requests found for branch "{branch}"'
        if completed.stdout or stderr not in {
            expected,
            expected + "\n",
            expected + "\r\n",
        }:
            raise gate.GateError("UNAVAILABLE", "GitHub PR lookup failed")
        return None
    if not isinstance(value, dict):
        raise gate.GateError("UNVERIFIED", "GitHub PR response is invalid")
    return value


def draft(value):
    if (
        (value.get("state"), value.get("isDraft")) != ("OPEN", True)
        or type(value.get("number")) is not int
        or value["number"] <= 0
        or not isinstance(value.get("headRefName"), str)
        or not value["headRefName"]
        or any(
            not gate.SHA_RE.fullmatch(str(value.get(key, "")).lower())
            for key in ("headRefOid", "baseRefOid")
        )
    ):
        raise gate.GateError("BLOCKED", "PR is not an open exact Draft")
    return value


def guarded_push_environment(
    receipt,
    maker_vendor,
    maker_model,
    maker_session,
):
    environment = {
        name: value
        for name, value in os.environ.items()
        if not SENSITIVE_ENV_RE.search(name)
    }
    environment["ITD_GUARDED_PR_PUSH"] = "1"
    if receipt is not None:
        environment["ITD_MACHINE_RECEIPT"] = str(receipt.resolve())
    environment["ITD_MAKER_VENDOR"] = maker_vendor
    environment["ITD_MAKER_MODEL"] = maker_model
    environment["ITD_MAKER_SESSION"] = maker_session
    return environment


def guarded_push_timeout(value: int) -> int:
    if type(value) is not int or value <= 0:
        raise gate.GateError("UNVERIFIED", "guarded push timeout is invalid")
    return min(max(value, 300), 3600)


def create_draft_pr(
    root,
    repository,
    machine_receipt,
    maker_vendor,
    maker_model,
    maker_session,
    push_timeout_seconds=1200,
):
    value = pr_view(root, repository)
    push_command = ["git", "push", "--set-upstream", "origin", "HEAD"]
    if value is not None:
        current = draft(value)
        branch = git(root, "symbolic-ref", "--short", "HEAD")
        if current["headRefName"] != branch:
            raise gate.GateError(
                "BLOCKED", "existing Draft PR belongs to another branch"
            )
        local_head = git(root, "rev-parse", "HEAD").lower()
        remote_head = str(current["headRefOid"]).lower()
        if local_head != remote_head:
            remote_ref = f"refs/heads/{branch}"
            push_command = [
                "git",
                "push",
                f"--force-with-lease={remote_ref}:{remote_head}",
                "--set-upstream",
                "origin",
                f"HEAD:{remote_ref}",
            ]
        else:
            push_command = []
    if push_command:
        run(
            push_command,
            cwd=root,
            env=guarded_push_environment(
                machine_receipt,
                maker_vendor,
                maker_model,
                maker_session,
            ),
            timeout=guarded_push_timeout(push_timeout_seconds),
        )
    value = pr_view(root, repository)
    if value is None:
        run(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                repository,
                "--draft",
                "--fill",
            ],
            cwd=root,
            timeout=120,
        )
        value = pr_view(root, repository)
    if value is None:
        raise gate.GateError("UNAVAILABLE", "Draft PR was not created")
    return draft(value)


def build_provenance(
    entry: dict[str, Any],
    pull_request: dict[str, Any],
    maker_vendor: str,
    maker_model: str,
    maker_session: str,
) -> dict[str, Any]:
    for name, value in (
        ("maker vendor", maker_vendor),
        ("maker model", maker_model),
        ("maker session", maker_session),
    ):
        if not value or "\n" in value or "\r" in value or len(value) > 200:
            raise gate.GateError("UNVERIFIED", f"{name} is invalid")
    material = read_signing_material(Path(entry["provenanceKeyFile"]))
    unsigned = {
        "repository": entry["repository"],
        "pullRequest": pull_request["number"],
        "headSha": str(pull_request["headRefOid"]).lower(),
        "baseSha": str(pull_request["baseRefOid"]).lower(),
        "makerVendor": maker_vendor,
        "makerModel": maker_model,
        "makerSession": maker_session,
        "issuedAt": machine.now_iso(),
        "nonce": secrets.token_urlsafe(24),
        "keyId": entry["provenanceKeyId"],
    }
    return sign_provenance(unsigned, material)


def provenance_cache_path(
    root: Path,
    pull_request: dict[str, Any],
) -> Path:
    return (
        root
        / ".itd-memory"
        / "gate-provenance"
        / (
            f"pr-{pull_request['number']}-"
            f"{str(pull_request['headRefOid']).lower()}-"
            f"{str(pull_request['baseRefOid']).lower()}.json"
        )
    )


def cached_provenance(
    root: Path,
    entry: dict[str, Any],
    pull_request: dict[str, Any],
    maker_vendor: str,
    maker_model: str,
    maker_session: str,
) -> tuple[dict[str, Any], Path]:
    target = provenance_cache_path(root, pull_request)
    material = read_signing_material(Path(entry["provenanceKeyFile"]))
    if target.is_file():
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
            unsigned = gate.provenance_payload(payload)
            expected = {
                "repository": entry["repository"],
                "pullRequest": pull_request["number"],
                "headSha": str(pull_request["headRefOid"]).lower(),
                "baseSha": str(pull_request["baseRefOid"]).lower(),
                "makerVendor": maker_vendor,
                "makerModel": maker_model,
                "makerSession": maker_session,
                "keyId": entry["provenanceKeyId"],
            }
            if any(unsigned[name] != value for name, value in expected.items()):
                raise ValueError("cached provenance coordinates differ")
            if sign_provenance(unsigned, material) != payload:
                raise ValueError("cached provenance signature differs")
            return payload, target
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            ValueError,
            gate.GateError,
        ) as exc:
            raise gate.GateError(
                "UNVERIFIED",
                "cached maker provenance is invalid; remove it and retry",
            ) from exc
    payload = build_provenance(
        entry,
        pull_request,
        maker_vendor,
        maker_model,
        maker_session,
    )
    machine.write_receipt(target, payload)
    return payload, target


def submit_provenance(
    entry: dict[str, Any],
    pull_request: dict[str, Any],
    maker_vendor: str,
    maker_model: str,
    maker_session: str,
    *,
    payload: dict[str, Any] | None = None,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if payload is None:
        payload = build_provenance(
            entry,
            pull_request,
            maker_vendor,
            maker_model,
            maker_session,
        )
    try:
        unsigned = gate.provenance_payload(payload)
    except gate.GateError:
        raise
    expected_coordinates = {
        "repository": entry["repository"],
        "pullRequest": pull_request["number"],
        "headSha": str(pull_request["headRefOid"]).lower(),
        "baseSha": str(pull_request["baseRefOid"]).lower(),
        "makerVendor": maker_vendor,
        "makerModel": maker_model,
        "makerSession": maker_session,
        "keyId": entry["provenanceKeyId"],
    }
    if any(
        unsigned[name] != value
        for name, value in expected_coordinates.items()
    ):
        raise gate.GateError(
            "UNVERIFIED", "maker provenance does not match the exact PR"
        )
    base = urllib.parse.urlsplit(entry["brokerUrl"])
    url = entry["brokerUrl"].rstrip("/") + "/provenance"
    request = urllib.request.Request(
        url,
        data=gate.canonical_json(payload),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "itd-pr-create/1",
        },
    )
    active_opener = opener
    if active_opener is None:
        active_opener = urllib.request.build_opener(
            RejectRedirectHandler()
        ).open
    try:
        with active_opener(request, timeout=15) as response:
            raw = response.read(MAX_BROKER_RESPONSE + 1)
            status = getattr(response, "status", 200)
            final = urllib.parse.urlsplit(response.geturl())
    except urllib.error.HTTPError as exc:
        raw = exc.read(MAX_BROKER_RESPONSE + 1)
        if exc.code == 422 and len(raw) <= MAX_BROKER_RESPONSE:
            try:
                failure = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                failure = None
            if (
                isinstance(failure, dict)
                and failure.get("status") == "UNVERIFIED"
                and failure.get("reason")
                == "maker provenance nonce replay rejected without enqueue"
            ):
                return {
                    "status": "duplicate",
                    "repository": entry["repository"],
                    "pullRequest": pull_request["number"],
                    "headSha": unsigned["headSha"],
                    "baseSha": unsigned["baseSha"],
                }
        raise gate.GateError(
            "UNVERIFIED", "broker rejected maker provenance"
        ) from exc
    except (OSError, urllib.error.URLError) as exc:
        raise gate.GateError(
            "UNAVAILABLE", "broker provenance submission failed"
        ) from exc
    if (
        final.scheme != base.scheme
        or final.netloc != base.netloc
        or status != 202
        or len(raw) > MAX_BROKER_RESPONSE
    ):
        raise gate.GateError(
            "UNVERIFIED", "broker provenance response/redirect is invalid"
        )
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise gate.GateError(
            "UNVERIFIED", "broker provenance response is invalid JSON"
        ) from exc
    if (
        not isinstance(value, dict)
        or value.get("status") not in {"queued", "duplicate"}
        or value.get("repository") != entry["repository"]
        or value.get("pullRequest") != pull_request["number"]
        or value.get("headSha") != unsigned["headSha"]
        or value.get("baseSha") != unsigned["baseSha"]
    ):
        raise gate.GateError(
            "UNVERIFIED", "broker did not accept exact provenance coordinates"
        )
    return value


def check_state(
    value: Any,
    *,
    app_id: int,
    ignored_external_ids: frozenset[int] = frozenset(),
) -> tuple[bool, str | None, frozenset[int]]:
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("check_runs"), list)
    ):
        raise gate.GateError("UNVERIFIED", "GitHub check-runs response is invalid")
    expected = {
        gate.MACHINE_CHECK: gate.GITHUB_ACTIONS_INTEGRATION_ID,
        gate.EXTERNAL_CHECK: app_id,
    }
    passed: set[str] = set()
    candidates: dict[str, dict[str, Any]] = {}
    for row in value["check_runs"]:
        if not isinstance(row, dict) or row.get("name") not in expected:
            continue
        app = row.get("app")
        if not isinstance(app, dict) or app.get("id") != expected[row["name"]]:
            continue
        check_id = row.get("id")
        if type(check_id) is not int or check_id <= 0:
            continue
        if row["name"] == gate.EXTERNAL_CHECK:
            if check_id in ignored_external_ids:
                continue
        previous = candidates.get(row["name"])
        if previous is None or check_id > previous["id"]:
            candidates[row["name"]] = row
    external_ids = frozenset(
        {row["id"] for name, row in candidates.items()
         if name == gate.EXTERNAL_CHECK}
    )
    for name, row in candidates.items():
        if row.get("status") == "completed":
            if row.get("conclusion") == "success":
                passed.add(name)
            else:
                return False, (
                    f"{name} completed as {row.get('conclusion')}"
                ), external_ids
    return len(passed) == len(expected), None, external_ids


def current_pull_request(
    repository: str,
    pull_request: int,
    *,
    gh: Callable[..., Any] = gate.gh_json,
) -> dict[str, Any]:
    value = gh([f"repos/{repository}/pulls/{pull_request}"])
    if not isinstance(value, dict):
        raise gate.GateError("UNVERIFIED", "GitHub pull response is invalid")
    head = value.get("head")
    base = value.get("base")
    if (
        value.get("number") != pull_request
        or value.get("state") != "open"
        or value.get("draft") is not True
        or not isinstance(head, dict)
        or not isinstance(base, dict)
        or not gate.SHA_RE.fullmatch(str(head.get("sha", "")).lower())
        or not gate.SHA_RE.fullmatch(str(base.get("sha", "")).lower())
    ):
        raise gate.GateError(
            "BLOCKED",
            "GitHub PR is not an open exact Draft PR",
        )
    if value.get("mergeable") is None:
        raise gate.GateError(
            "UNAVAILABLE", "GitHub is still computing the test merge"
        )
    if value.get("mergeable") is not True or not gate.SHA_RE.fullmatch(
        str(value.get("merge_commit_sha", "")).lower()
    ):
        raise gate.GateError(
            "BLOCKED", "GitHub PR has no mergeable exact test-merge SHA"
        )
    head_repo = head.get("repo")
    base_repo = base.get("repo")
    if (
        not isinstance(head_repo, dict)
        or not isinstance(base_repo, dict)
        or str(head_repo.get("full_name", "")).casefold()
        != repository.casefold()
        or str(base_repo.get("full_name", "")).casefold()
        != repository.casefold()
    ):
        raise gate.GateError(
            "BLOCKED", "fork or cross-repository PR is not eligible"
        )
    return {
        "number": pull_request,
        "headSha": str(head["sha"]).lower(),
        "baseSha": str(base["sha"]).lower(),
        "checkSha": str(value["merge_commit_sha"]).lower(),
    }


def check_runs(
    repository: str,
    check_sha: str,
    *,
    gh: Callable[..., Any] = gate.gh_json,
) -> Any:
    return gh(
        [
            f"repos/{repository}/commits/{check_sha}/check-runs"
            "?filter=latest&per_page=100"
        ]
    )


def wait_pull_candidate(
    repository: str,
    pull_request: int,
    expected_head: str,
    expected_base: str,
    *,
    timeout_seconds: int,
    gh: Callable[..., Any] = gate.gh_json,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    deadline = monotonic() + timeout_seconds
    while True:
        try:
            current = current_pull_request(
                repository, pull_request, gh=gh
            )
        except gate.GateError as exc:
            if exc.status != "UNAVAILABLE":
                raise
            if monotonic() >= deadline:
                raise gate.GateError(
                    "UNAVAILABLE",
                    "GitHub did not produce the exact test merge in time",
                ) from exc
            sleep(2)
            continue
        if (
            current["headSha"] != expected_head
            or current["baseSha"] != expected_base
        ):
            raise gate.GateError(
                "BLOCKED",
                "PR head/base changed while GitHub computed the test merge",
            )
        return current


def wait_checks(
    repository: str,
    pull_request: int,
    head_sha: str,
    base_sha: str,
    check_sha: str,
    app_id: int,
    *,
    ignored_external_ids: frozenset[int] = frozenset(),
    timeout_seconds: int,
    gh: Callable[..., Any] = gate.gh_json,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    deadline = monotonic() + timeout_seconds
    while True:
        try:
            current = current_pull_request(
                repository, pull_request, gh=gh
            )
        except gate.GateError as exc:
            if exc.status != "UNAVAILABLE":
                raise
            if monotonic() >= deadline:
                raise gate.GateError(
                    "UNAVAILABLE",
                    "GitHub did not keep the exact test merge available",
                ) from exc
            sleep(2)
            continue
        if current != {
            "number": pull_request,
            "headSha": head_sha,
            "baseSha": base_sha,
            "checkSha": check_sha,
        }:
            raise gate.GateError(
                "BLOCKED",
                "PR head/base/test-merge changed while checks were pending",
            )
        value = check_runs(repository, check_sha, gh=gh)
        complete, failure, _ = check_state(
            value,
            app_id=app_id,
            ignored_external_ids=ignored_external_ids,
        )
        if failure:
            raise gate.GateError("BLOCKED", failure)
        if complete:
            return
        if monotonic() >= deadline:
            raise gate.GateError(
                "UNAVAILABLE", "required GitHub checks did not complete in time"
            )
        sleep(5)


def pr_create(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    registry = gate.load_registry(args.registry)
    entry = repository_entry(registry, root, args.repository)
    local_review = (
        registry["version"] == 2
        and entry["protectionProfile"] == "local-review"
    )
    if not local_review:
        adoption_drift = gate.adopted_checkout(root)
        if adoption_drift:
            raise gate.GateError(
                "UNVERIFIED",
                "checkout is not gate-ready: " + "; ".join(adoption_drift),
            )
    require_registered_origin(root, entry["repository"])
    _, head = ensure_clean_branch(root)
    if registry["version"] == 2 and entry["protectionProfile"] == "app-check":
        raise gate.GateError(
            "UNVERIFIED",
            "app-check guarded PR transport is not activated in this slice",
        )
    if local_review:
        inspection = gate.profile_doctor_entry(entry)
        if (
            inspection.get("status") != "LOCAL_REVIEWED"
            or inspection.get("drift") != []
        ):
            raise gate.GateError(
                "UNVERIFIED", "current local independent review is not valid"
            )
    preflight = None if local_review else machine_preflight(root, head)
    pull_request = create_draft_pr(
        root,
        entry["repository"],
        preflight,
        args.maker_vendor,
        args.maker_model,
        args.maker_session,
        args.timeout,
    )
    if str(pull_request["headRefOid"]).lower() != head:
        raise gate.GateError(
            "UNVERIFIED", "Draft PR head differs from exact reviewed HEAD"
        )
    if local_review:
        return {
            "status": "LOCAL_REVIEWED",
            "repository": entry["repository"],
            "pullRequest": pull_request["number"],
            "url": pull_request["url"],
            "headSha": head,
            "baseSha": str(pull_request["baseRefOid"]).lower(),
            "checkSha": None,
            "preflightReceipt": None,
            "provenanceReceipt": None,
            "provenance": "NOT_REQUIRED",
        }
    current = wait_pull_candidate(
        entry["repository"],
        pull_request["number"],
        head,
        str(pull_request["baseRefOid"]).lower(),
        timeout_seconds=min(args.timeout, 120),
    )
    if (
        current["headSha"] != head
        or current["baseSha"]
        != str(pull_request["baseRefOid"]).lower()
    ):
        raise gate.GateError(
            "UNVERIFIED",
            "Draft PR REST coordinates differ from the created PR",
        )
    initial_checks = check_runs(
        entry["repository"], current["checkSha"]
    )
    _, failure, ignored_external_ids = check_state(
        initial_checks, app_id=entry["appId"]
    )
    if failure:
        raise gate.GateError("BLOCKED", failure)
    provenance, provenance_path = cached_provenance(
        root,
        entry,
        pull_request,
        args.maker_vendor,
        args.maker_model,
        args.maker_session,
    )
    accepted = submit_provenance(
        entry,
        pull_request,
        args.maker_vendor,
        args.maker_model,
        args.maker_session,
        payload=provenance,
    )
    if not args.no_wait:
        wait_checks(
            entry["repository"],
            pull_request["number"],
            head,
            str(pull_request["baseRefOid"]).lower(),
            current["checkSha"],
            entry["appId"],
            ignored_external_ids=ignored_external_ids,
            timeout_seconds=args.timeout,
        )
    return {
        "status": "QUEUED" if args.no_wait else "CHECKS_PASSED",
        "repository": entry["repository"],
        "pullRequest": pull_request["number"],
        "url": pull_request["url"],
        "headSha": head,
        "baseSha": str(pull_request["baseRefOid"]).lower(),
        "checkSha": current["checkSha"],
        "preflightReceipt": str(preflight),
        "provenanceReceipt": (
            str(provenance_path) if provenance_path else None
        ),
        "provenance": accepted["status"],
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="itd")
    sub = result.add_subparsers(dest="command", required=True)
    gate_parser = sub.add_parser("gate")
    gate_sub = gate_parser.add_subparsers(dest="gate_command", required=True)

    register = gate_sub.add_parser("register")
    register.add_argument("--repository", required=True)
    register.add_argument("--checkout", type=Path, required=True)
    register.add_argument("--broker-url", required=True)
    register.add_argument("--app-id", type=int, required=True)
    register.add_argument("--scope", choices=["organization"], required=True)
    register.add_argument("--ruleset-id", type=positive_int, required=True)
    register.add_argument("--workflow-repository-id", type=int, required=True)
    register.add_argument("--workflow-sha", required=True)
    register.add_argument("--provenance-key-id", required=True)
    register.add_argument("--provenance-key-file", type=Path, required=True)
    register.add_argument("--registry", type=Path)
    register.set_defaults(handler=register_entry)

    profile = gate_sub.add_parser("register-profile")
    profile.add_argument("--repository", required=True)
    profile.add_argument("--checkout", type=Path, required=True)
    profile.add_argument(
        "--repository-owner-type", choices=["user", "organization"],
        required=True,
    )
    profile.add_argument(
        "--deployment-profile",
        choices=["local-submission", "self-hosted-app", "managed-app"],
        required=True,
    )
    profile.add_argument(
        "--protection-profile",
        choices=["local-review", "app-check", "organization-workflow"],
        required=True,
    )
    profile.add_argument("--local-review-receipt-file", type=Path)
    profile.add_argument("--local-review-unit-id")
    profile.add_argument(
        "--local-review-risk-tier",
        choices=["low", "medium", "high", "unknown"],
    )
    profile.add_argument("--local-review-producer-keyring-sha256")
    profile.add_argument("--broker-url")
    profile.add_argument("--app-id", type=int)
    profile.add_argument("--app-owner")
    profile.add_argument("--app-owner-type", choices=["user", "organization"])
    profile.add_argument("--app-visibility", choices=["private", "public"])
    profile.add_argument("--scope", choices=["repository", "organization"])
    profile.add_argument("--ruleset-id", type=positive_int)
    profile.add_argument("--workflow-repository-id", type=int)
    profile.add_argument("--workflow-sha")
    profile.add_argument("--provenance-key-id")
    profile.add_argument("--provenance-key-file", type=Path)
    profile.add_argument("--enrollment-receipt-sha256")
    profile.add_argument("--registry", type=Path)
    profile.set_defaults(handler=register_profile_entry)

    adopt = gate_sub.add_parser("adopt")
    adopt.add_argument("--root", type=Path, default=Path.cwd())
    adopt.add_argument("--broker-url", required=True)
    adopt.add_argument("--app-id", type=int, required=True)
    adopt.add_argument("--scope", choices=["organization"], required=True)
    adopt.add_argument("--ruleset-id", type=positive_int, required=True)
    adopt.add_argument("--workflow-repository-id", type=int, required=True)
    adopt.add_argument("--workflow-sha", required=True)
    adopt.add_argument("--provenance-key-id", required=True)
    adopt.add_argument("--provenance-key-file", type=Path, required=True)
    adopt.add_argument("--registry", type=Path)
    adopt.set_defaults(handler=adopt_gate)

    keygen = gate_sub.add_parser("keygen")
    keygen.add_argument("--repository", required=True)
    keygen.add_argument("--key-id", required=True)
    keygen.add_argument("--maker-vendor", required=True)
    keygen.add_argument("--maker-model", required=True)
    keygen.add_argument("--issuer-principal", required=True)
    keygen.add_argument("--output", type=Path, required=True)
    keygen.set_defaults(handler=generate_provenance_key)

    ruleset = gate_sub.add_parser("ruleset")
    ruleset.add_argument("--repository", required=True)
    ruleset.add_argument("--app-id", type=int, required=True)
    ruleset.add_argument("--scope", choices=["organization"], required=True)
    ruleset.add_argument("--workflow-repository-id", type=int, required=True)
    ruleset.add_argument("--workflow-sha", required=True)
    ruleset.add_argument("--ruleset-id", type=positive_int)
    ruleset.add_argument("--apply", action="store_true")
    ruleset.set_defaults(handler=apply_ruleset)

    enrollment = gate_sub.add_parser("enrollment")
    enrollment.add_argument("--repository", required=True)
    enrollment.add_argument("--scope", choices=["organization"], required=True)
    enrollment.add_argument("--ruleset-id", type=positive_int, required=True)
    enrollment.add_argument("--app-id", type=int, required=True)
    enrollment.add_argument("--app-slug", required=True)
    enrollment.add_argument("--workflow-repository-id", type=int, required=True)
    enrollment.add_argument("--workflow-sha", required=True)
    enrollment.add_argument("--output", type=Path, required=True)
    enrollment.add_argument("--apply", action="store_true")
    enrollment.set_defaults(handler=observe_enrollment)

    doctor_parser = gate_sub.add_parser("doctor")
    selection = doctor_parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--repository")
    doctor_parser.add_argument("--registry", type=Path)
    doctor_parser.set_defaults(handler=doctor)

    pr = sub.add_parser("pr")
    pr_sub = pr.add_subparsers(dest="pr_command", required=True)
    create = pr_sub.add_parser("create")
    create.add_argument("--root", type=Path, default=Path.cwd())
    create.add_argument("--repository")
    create.add_argument("--maker-vendor", required=True)
    create.add_argument("--maker-model", required=True)
    create.add_argument("--maker-session", required=True)
    create.add_argument("--timeout", type=positive_int, default=1200)
    create.add_argument("--no-wait", action="store_true")
    create.add_argument("--registry", type=Path)
    create.set_defaults(handler=pr_create)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = args.handler(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("status") not in {"UNVERIFIED", "BLOCKED"} else 1
    except gate.GateError as exc:
        print(
            json.dumps(
                {"status": exc.status, "reason": exc.reason},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
