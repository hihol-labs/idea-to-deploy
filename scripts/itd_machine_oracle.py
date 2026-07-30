#!/usr/bin/env python3
"""Execute a tracked ITD verification contract and emit a SHA-bound receipt."""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
from pathlib import Path, PurePosixPath
from typing import Any


MAX_CONTRACT_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_GIT_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_COMMANDS = 50
MAX_TIMEOUT_SECONDS = 3600
MAX_ARGV_ITEMS = 64
MAX_ARG_BYTES = 8192
MAX_TRUSTED_PATHS = 32
ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
SENSITIVE_NAME_RE = re.compile(
    r"(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH)",
    re.IGNORECASE,
)
SAFE_ENV_NAMES = {
    "CI",
    "COLORTERM",
    "COMSPEC",
    "HOME",
    "LANG",
    "LC_ALL",
    "LOCALAPPDATA",
    "NUMBER_OF_PROCESSORS",
    "OS",
    "PATH",
    "PATHEXT",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TERM",
    "TMP",
    "TMPDIR",
    "USER",
    "USERPROFILE",
    "WINDIR",
    "WSL_DISTRO_NAME",
    "WSL_INTEROP",
}


class OracleError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path, limit: int = MAX_ARTIFACT_BYTES) -> str:
    digest = hashlib.sha256()
    total = 0
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    return digest.hexdigest()
                total += len(chunk)
                if total > limit:
                    raise OracleError(
                        "required artifact exceeds its hash bound"
                    )
                digest.update(chunk)
    except OSError as exc:
        raise OracleError("required artifact is unreadable") from exc


def now_iso() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def safe_relative(raw: str, label: str) -> str:
    path = PurePosixPath(raw.replace("\\", "/"))
    if (
        not raw
        or path.is_absolute()
        or ".." in path.parts
        or any(part in {"", "."} for part in path.parts)
    ):
        raise OracleError(f"{label} path is unsafe")
    return path.as_posix()


def load_contract(path: Path) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise OracleError("verification contract is unavailable") from exc
    if not raw or len(raw) > MAX_CONTRACT_BYTES:
        raise OracleError("verification contract size is invalid")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OracleError("verification contract is invalid JSON") from exc
    if not isinstance(value, dict):
        raise OracleError("verification contract is not an object")
    if value.get("version") != 2:
        raise OracleError(
            "verification contract version is unsupported; "
            "adopt or migrate to fail-closed version 2"
        )
    commands = value.get("commands")
    if (
        not isinstance(commands, list)
        or not 1 <= len(commands) <= MAX_COMMANDS
    ):
        raise OracleError("verification contract command count is invalid")
    expected_fields = {
        "id",
        "argv",
        "trustedVerifierPaths",
        "timeoutSeconds",
        "expectedOutput",
        "passFailParser",
    }
    seen: set[str] = set()
    for row in commands:
        if not isinstance(row, dict) or set(row) != expected_fields:
            raise OracleError("verification command fields are invalid")
        identifier = str(row["id"])
        argv = row["argv"]
        trusted_paths = row["trustedVerifierPaths"]
        timeout = row["timeoutSeconds"]
        parser = row["passFailParser"]
        if (
            not ID_RE.fullmatch(identifier)
            or identifier in seen
            or not isinstance(argv, list)
            or not 1 <= len(argv) <= MAX_ARGV_ITEMS
            or any(
                not isinstance(argument, str)
                or not argument
                or "\x00" in argument
                or len(argument.encode("utf-8")) > MAX_ARG_BYTES
                for argument in argv
            )
            or not isinstance(trusted_paths, list)
            or not 1 <= len(trusted_paths) <= MAX_TRUSTED_PATHS
            or any(not isinstance(item, str) for item in trusted_paths)
            or type(timeout) is not int
            or not 1 <= timeout <= MAX_TIMEOUT_SECONDS
            or parser
            not in {
                "exit_code_zero",
                "stdout_contains",
                "json_field_equals",
                "manual_evidence",
            }
        ):
            raise OracleError("verification command definition is invalid")
        normalized_paths = [
            safe_relative(item, "trusted verifier") for item in trusted_paths
        ]
        if len(normalized_paths) != len(set(normalized_paths)):
            raise OracleError("trusted verifier paths contain duplicates")
        row["trustedVerifierPaths"] = normalized_paths
        seen.add(identifier)
    artifacts = value.get("requiredArtifacts", [])
    if not isinstance(artifacts, list) or len(artifacts) > 200:
        raise OracleError("requiredArtifacts is invalid")
    for artifact in artifacts:
        if not isinstance(artifact, str):
            raise OracleError("required artifact is not a string")
        safe_relative(artifact, "required artifact")
    return value, sha256_bytes(raw)


def sanitized_environment() -> dict[str, str]:
    result: dict[str, str] = {}
    for name, value in os.environ.items():
        upper = name.upper()
        if SENSITIVE_NAME_RE.search(upper):
            continue
        if (
            upper in SAFE_ENV_NAMES
            or upper.startswith("GITHUB_")
            or upper.startswith("RUNNER_")
        ):
            result[name] = value
    result["ITD_MACHINE_ORACLE"] = "1"
    result["PYTHONDONTWRITEBYTECODE"] = "1"
    return result


def _terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
            if process.poll() is None:
                process.kill()
    except (OSError, ProcessLookupError):
        process.kill()


def _capture_process(
    process: subprocess.Popen[bytes],
    *,
    started: str,
    timeout: int,
    max_output_bytes: int,
) -> dict[str, Any]:
    if max_output_bytes <= 0:
        raise ValueError("max_output_bytes must be positive")
    if process.stdout is None or process.stderr is None:
        raise OracleError("bounded process pipes are unavailable")
    stdout_hash = hashlib.sha256()
    stderr_hash = hashlib.sha256()
    stdout_capture = bytearray()
    stderr_capture = bytearray()
    total = 0
    overflow = threading.Event()
    lock = threading.Lock()

    def consume(
        stream: Any,
        digest: Any,
        capture: bytearray,
    ) -> None:
        nonlocal total
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return
            digest.update(chunk)
            with lock:
                previous = total
                total += len(chunk)
                remaining = max(0, max_output_bytes - previous)
                if remaining:
                    capture.extend(chunk[:remaining])
                if total > max_output_bytes:
                    overflow.set()
                    _terminate(process)
                    return

    threads = [
        threading.Thread(
            target=consume,
            args=(process.stdout, stdout_hash, stdout_capture),
            daemon=True,
        ),
        threading.Thread(
            target=consume,
            args=(process.stderr, stderr_hash, stderr_capture),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        exit_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate(process)
        exit_code = process.wait(timeout=10)
    for thread in threads:
        thread.join(timeout=10)
    if any(thread.is_alive() for thread in threads):
        _terminate(process)
        raise OracleError("verification output reader did not terminate")
    return {
        "startedAt": started,
        "completedAt": now_iso(),
        "exitCode": exit_code,
        "timedOut": timed_out,
        "outputOverflow": overflow.is_set(),
        "stdoutSha256": stdout_hash.hexdigest(),
        "stderrSha256": stderr_hash.hexdigest(),
        "stdout": bytes(stdout_capture),
        "stderr": bytes(stderr_capture),
    }


def run_argv(
    arguments: list[str],
    *,
    cwd: Path,
    timeout: int,
    max_output_bytes: int,
) -> dict[str, Any]:
    started = now_iso()
    try:
        process = subprocess.Popen(
            arguments,
            cwd=str(cwd),
            env=sanitized_environment(),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=(os.name != "nt"),
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP
                if os.name == "nt"
                else 0
            ),
        )
    except OSError as exc:
        raise OracleError("bounded process could not start") from exc
    return _capture_process(
        process,
        started=started,
        timeout=timeout,
        max_output_bytes=max_output_bytes,
    )


def json_field(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if not part or not isinstance(current, dict) or part not in current:
            raise OracleError("json_field_equals path is unavailable")
        current = current[part]
    return current


def parser_passed(
    parser: str,
    expected: Any,
    result: dict[str, Any],
) -> bool:
    if result["timedOut"] or result["outputOverflow"]:
        return False
    if parser == "manual_evidence":
        return False
    if parser == "exit_code_zero":
        return result["exitCode"] == 0
    if parser == "stdout_contains":
        return (
            result["exitCode"] == 0
            and isinstance(expected, str)
            and expected.encode("utf-8") in result["stdout"]
        )
    if parser == "json_field_equals":
        if (
            result["exitCode"] != 0
            or not isinstance(expected, dict)
            or set(expected) != {"field", "value"}
            or not isinstance(expected["field"], str)
        ):
            return False
        try:
            value = json.loads(result["stdout"].decode("utf-8"))
            return json_field(value, expected["field"]) == expected["value"]
        except (UnicodeError, json.JSONDecodeError, OracleError):
            return False
    raise OracleError("unknown pass/fail parser")


def git_bytes(root: Path, *arguments: str) -> bytes:
    result = run_argv(
        ["git", "-C", str(root), *arguments],
        cwd=root,
        timeout=20,
        max_output_bytes=MAX_GIT_OUTPUT_BYTES,
    )
    if (
        result["exitCode"] != 0
        or result["timedOut"]
        or result["outputOverflow"]
    ):
        raise OracleError("Git candidate identity is unavailable")
    return result["stdout"]


def git_value(root: Path, *arguments: str) -> str:
    value = git_bytes(root, *arguments).decode(
        "ascii", errors="strict"
    ).strip()
    if not value:
        raise OracleError("Git candidate identity is unavailable")
    return value


def tracked_path_manifest(
    root: Path,
    raw_path: str,
) -> dict[str, Any] | None:
    """Return a content-bound Git manifest for one trusted file or tree."""
    relative = safe_relative(raw_path, "trusted verifier")
    output = git_bytes(
        root,
        "--literal-pathspecs",
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        "HEAD",
        "--",
        relative,
    )
    if not output:
        return None
    entries: list[dict[str, str]] = []
    prefix = relative + "/"
    for record in output.split(b"\0"):
        if not record:
            continue
        try:
            metadata, encoded_path = record.split(b"\t", 1)
            mode, kind, object_id = metadata.decode("ascii").split(" ")
            path = encoded_path.decode("utf-8", errors="strict")
        except (ValueError, UnicodeError) as exc:
            raise OracleError(
                "trusted verifier Git manifest is malformed"
            ) from exc
        if (
            kind != "blob"
            or mode not in {"100644", "100755"}
            or not re.fullmatch(r"[0-9a-f]{40,64}", object_id)
            or (path != relative and not path.startswith(prefix))
        ):
            raise OracleError(
                "trusted verifier must contain only regular tracked files"
            )
        entries.append(
            {
                "mode": mode,
                "objectId": object_id,
                "path": path,
            }
        )
    if not entries:
        return None
    object_kind = git_value(
        root,
        "cat-file",
        "-t",
        f"HEAD:{relative}",
    )
    if object_kind not in {"blob", "tree"}:
        raise OracleError(
            "trusted verifier is not a regular file or directory"
        )
    manifest_sha = sha256_bytes(canonical_json(entries))
    return {
        "path": relative,
        "objectKind": object_kind,
        "entryCount": len(entries),
        "manifestSha256": manifest_sha,
    }


def verifier_bindings(
    contract: dict[str, Any],
    candidate_root: Path,
    contract_root: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Bind every declared verifier path to protected-base Git objects."""
    paths = sorted(
        {
            path
            for row in contract["commands"]
            for path in row["trustedVerifierPaths"]
        }
    )
    bindings: list[dict[str, Any]] = []
    failures: list[str] = []
    protected_by_path: dict[str, dict[str, Any]] = {}
    for path in paths:
        protected = tracked_path_manifest(contract_root, path)
        if protected is None:
            raise OracleError(
                f"trusted verifier is absent from contract HEAD: {path}"
            )
        protected_by_path[path] = protected
        candidate = tracked_path_manifest(candidate_root, path)
        matches = (
            candidate is not None
            and candidate["objectKind"] == protected["objectKind"]
            and candidate["manifestSha256"]
            == protected["manifestSha256"]
            and candidate["entryCount"] == protected["entryCount"]
        )
        if not matches:
            failures.append(path)
        bindings.append(
            {
                "path": path,
                "objectKind": protected["objectKind"],
                "protectedManifestSha256": protected["manifestSha256"],
                "candidateManifestSha256": (
                    candidate["manifestSha256"]
                    if candidate is not None
                    else None
                ),
                "entryCount": protected["entryCount"],
                "status": (
                    "MATCHED"
                    if matches and contract_root != candidate_root
                    else "LOCAL_ONLY"
                    if matches
                    else "MISMATCH"
                ),
            }
        )
    for row in contract["commands"]:
        trusted = row["trustedVerifierPaths"]
        executable = Path(
            row["argv"][0].replace("\\", "/")
        ).name.casefold()
        if (
            executable.startswith("python")
            and "-I" not in row["argv"][1:]
        ):
            raise OracleError(
                f"Python verifier is not isolated with -I: {row['id']}"
            )
        if (
            any(
                argument.replace("\\", "/").endswith(
                    "/itd_py.sh"
                )
                or argument == "itd_py.sh"
                for argument in row["argv"]
            )
            and "--itd-isolated" not in row["argv"]
        ):
            raise OracleError(
                f"ITD Python launcher is not isolated: {row['id']}"
            )
        namespace_paths = [
            path
            for path in trusted
            if protected_by_path[path]["objectKind"] == "tree"
        ]
        namespace_referenced = False
        for argument in row["argv"]:
            normalized = argument.replace("\\", "/").lstrip("./")
            dotted = normalized.replace("/", ".")
            if any(
                normalized == path
                or normalized.startswith(path.rstrip("/") + "/")
                or dotted == path.replace("/", ".")
                or dotted.startswith(path.replace("/", ".") + ".")
                for path in namespace_paths
            ):
                namespace_referenced = True
            try:
                relative = safe_relative(
                    argument,
                    "verification argv",
                )
            except OracleError:
                continue
            tracked = tracked_path_manifest(contract_root, relative)
            if tracked is not None and not any(
                relative == path
                or relative.startswith(path.rstrip("/") + "/")
                for path in trusted
            ):
                raise OracleError(
                    f"verification argv references undeclared verifier "
                    f"input: {relative}"
                )
        if not namespace_referenced:
            raise OracleError(
                f"verification command does not invoke a content-bound "
                f"verifier namespace: {row['id']}"
            )
    return bindings, failures


def _argv_ok(
    arguments: list[str],
    *,
    cwd: Path,
    label: str,
) -> bytes:
    result = run_argv(
        arguments,
        cwd=cwd,
        timeout=30,
        max_output_bytes=MAX_GIT_OUTPUT_BYTES,
    )
    if (
        result["exitCode"] != 0
        or result["timedOut"]
        or result["outputOverflow"]
    ):
        raise OracleError(label)
    return result["stdout"]


@contextlib.contextmanager
def isolated_head(root: Path, head: str, tree: str):
    with tempfile.TemporaryDirectory(prefix="itd-machine-candidate-") as raw:
        candidate = Path(raw) / "candidate"
        _argv_ok(
            [
                "git",
                "clone",
                "--shared",
                "--no-checkout",
                "--quiet",
                str(root),
                str(candidate),
            ],
            cwd=root,
            label="isolated machine candidate could not be created",
        )
        _argv_ok(
            [
                "git",
                "-C",
                str(candidate),
                "read-tree",
                "--reset",
                "-u",
                tree,
            ],
            cwd=candidate,
            label="exact HEAD tree could not be materialized",
        )
        _argv_ok(
            [
                "git",
                "-C",
                str(candidate),
                "update-ref",
                "--no-deref",
                "HEAD",
                head,
            ],
            cwd=candidate,
            label="isolated machine HEAD could not be bound",
        )
        if git_value(candidate, "write-tree") != tree:
            raise OracleError("isolated machine tree differs from exact HEAD")
        if git_bytes(
            candidate, "ls-files", "--others", "--exclude-standard", "-z"
        ):
            raise OracleError(
                "isolated machine candidate contains an unexpected overlay"
            )
        yield candidate


def execute(
    root: Path,
    contract_path: Path,
    trusted_contract_root: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    contract_root = (
        trusted_contract_root.resolve()
        if trusted_contract_root is not None
        else root
    )
    contract_path = contract_path.resolve()
    try:
        contract_relative = contract_path.relative_to(
            contract_root
        ).as_posix()
    except ValueError as exc:
        raise OracleError(
            "verification contract escapes its trusted repository"
        ) from exc
    if git_bytes(
        root, "status", "--porcelain=v1", "--untracked-files=all"
    ):
        raise OracleError("verification candidate worktree is not clean")
    if contract_root != root and git_bytes(
        contract_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    ):
        raise OracleError(
            "trusted verification-contract worktree is not clean"
        )
    try:
        head_contract = git_bytes(
            contract_root, "show", f"HEAD:{contract_relative}"
        )
    except OracleError as exc:
        raise OracleError(
            "verification contract is not tracked in trusted HEAD"
        ) from exc
    try:
        current_contract = contract_path.read_bytes()
    except OSError as exc:
        raise OracleError("verification contract is unavailable") from exc
    if (
        current_contract != head_contract
    ):
        raise OracleError(
            "verification contract does not match trusted HEAD"
        )
    head = git_value(root, "rev-parse", "HEAD")
    tree = git_value(root, "rev-parse", "HEAD^{tree}")
    contract_head = git_value(contract_root, "rev-parse", "HEAD")
    contract_tree = git_value(contract_root, "rev-parse", "HEAD^{tree}")
    contract_sha = sha256_bytes(head_contract)
    contract, loaded_sha = load_contract(contract_path)
    if loaded_sha != contract_sha:
        raise OracleError(
            "loaded verification contract differs from trusted HEAD"
        )
    bindings, trust_failures = verifier_bindings(
        contract,
        root,
        contract_root,
    )
    binding_by_path = {row["path"]: row for row in bindings}
    with isolated_head(root, head, tree) as candidate:
        results: list[dict[str, Any]] = []
        passed = not trust_failures
        for row in contract["commands"]:
            verifier_hashes = {
                path: binding_by_path[path][
                    "protectedManifestSha256"
                ]
                for path in row["trustedVerifierPaths"]
            }
            if trust_failures:
                results.append(
                    {
                        "id": row["id"],
                        "argvSha256": sha256_bytes(
                            canonical_json(row["argv"])
                        ),
                        "trustedVerifierPaths": row[
                            "trustedVerifierPaths"
                        ],
                        "trustedVerifierManifestSha256": verifier_hashes,
                        "timeoutSeconds": row["timeoutSeconds"],
                        "passFailParser": row["passFailParser"],
                        "startedAt": None,
                        "completedAt": None,
                        "exitCode": None,
                        "timedOut": False,
                        "outputOverflow": False,
                        "stdoutSha256": None,
                        "stderrSha256": None,
                        "status": "NOT_RUN_TRUST_FAILURE",
                    }
                )
                continue
            command_result = run_argv(
                row["argv"],
                cwd=candidate,
                timeout=row["timeoutSeconds"],
                max_output_bytes=MAX_OUTPUT_BYTES,
            )
            accepted = parser_passed(
                row["passFailParser"],
                row["expectedOutput"],
                command_result,
            )
            passed = passed and accepted
            results.append(
                {
                    "id": row["id"],
                    "argvSha256": sha256_bytes(
                        canonical_json(row["argv"])
                    ),
                    "trustedVerifierPaths": row[
                        "trustedVerifierPaths"
                    ],
                    "trustedVerifierManifestSha256": verifier_hashes,
                    "timeoutSeconds": row["timeoutSeconds"],
                    "passFailParser": row["passFailParser"],
                    "startedAt": command_result["startedAt"],
                    "completedAt": command_result["completedAt"],
                    "exitCode": command_result["exitCode"],
                    "timedOut": command_result["timedOut"],
                    "outputOverflow": command_result["outputOverflow"],
                    "stdoutSha256": command_result["stdoutSha256"],
                    "stderrSha256": command_result["stderrSha256"],
                    "status": "PASSED" if accepted else "FAILED",
                }
            )
        missing: list[str] = []
        artifact_hashes: dict[str, str] = {}
        for raw in contract.get("requiredArtifacts", []):
            relative = safe_relative(raw, "required artifact")
            artifact = candidate / relative
            if artifact.is_symlink() or not artifact.is_file():
                missing.append(relative)
            else:
                artifact_hashes[relative] = sha256_file(artifact)
        passed = passed and not missing
        try:
            final_contract = contract_path.read_bytes()
        except OSError as exc:
            raise OracleError(
                "verification contract became unavailable"
            ) from exc
        if final_contract != head_contract:
            raise OracleError("verification contract changed during execution")
        dirty = run_argv(
            ["git", "-C", str(candidate), "diff", "--quiet", "--"],
            cwd=candidate,
            timeout=20,
            max_output_bytes=MAX_GIT_OUTPUT_BYTES,
        )
        overlay = git_bytes(
            candidate,
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
        )
        if (
            dirty["exitCode"] != 0
            or git_value(candidate, "write-tree") != tree
            or overlay
        ):
            raise OracleError(
                "verification command changed tracked candidate content"
            )
    if (
        git_value(root, "rev-parse", "HEAD") != head
        or git_value(root, "rev-parse", "HEAD^{tree}") != tree
        or git_bytes(
            root, "status", "--porcelain=v1", "--untracked-files=all"
        )
    ):
        raise OracleError("source candidate changed during execution")
    if (
        git_value(contract_root, "rev-parse", "HEAD") != contract_head
        or git_value(contract_root, "rev-parse", "HEAD^{tree}")
        != contract_tree
        or git_bytes(
            contract_root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        )
    ):
        raise OracleError(
            "trusted verification-contract repository changed during "
            "execution"
        )
    receipt: dict[str, Any] = {
        "version": 2,
        "kind": "itd-machine-oracle",
        "repository": str(root),
        "headSha": head,
        "tree": tree,
        "contractPath": contract_relative,
        "contractSha256": contract_sha,
        "contractSource": (
            "protected-base-head"
            if contract_root != root
            else "candidate-head"
        ),
        "contractRepository": str(contract_root),
        "contractHeadSha": contract_head,
        "contractTree": contract_tree,
        "verifierTrust": (
            "PROTECTED_BASE_CONTENT_BOUND"
            if contract_root != root and not trust_failures
            else "LOCAL_ONLY"
            if not trust_failures
            else "UNVERIFIED"
        ),
        "trustedVerifierBindings": bindings,
        "trustedVerifierFailures": trust_failures,
        "commands": results,
        "missingArtifacts": missing,
        "requiredArtifactSha256": artifact_hashes,
        "executionCheckout": "isolated-exact-head-tree",
        "credentialEnvironment": "removed-by-name",
        "rawOutputPersisted": False,
        "observedAt": now_iso(),
        "status": "PASSED" if passed else "UNVERIFIED",
    }
    receipt["receiptSha256"] = sha256_bytes(canonical_json(receipt))
    return receipt


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = json.dumps(
        receipt,
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
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Run the tracked ITD machine verification contract"
    )
    result.add_argument("--root", type=Path, default=Path.cwd())
    result.add_argument(
        "--contract",
        type=Path,
        default=Path(".itd/VERIFICATION_CONTRACT.json"),
    )
    result.add_argument(
        "--trusted-contract-root",
        type=Path,
        help=(
            "clean protected-base checkout that owns --contract; "
            "required when the contract is outside --root"
        ),
    )
    result.add_argument("--receipt", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.root.resolve()
    contract_root = (
        args.trusted_contract_root.resolve()
        if args.trusted_contract_root is not None
        else root
    )
    contract = (
        args.contract.resolve()
        if args.contract.is_absolute()
        else (contract_root / args.contract).resolve()
    )
    try:
        receipt = execute(root, contract, args.trusted_contract_root)
        if args.receipt:
            target = (
                args.receipt.resolve()
                if args.receipt.is_absolute()
                else (root / args.receipt).resolve()
            )
            write_receipt(target, receipt)
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        return 0 if receipt["status"] == "PASSED" else 1
    except OracleError as exc:
        print(
            json.dumps(
                {"status": "UNVERIFIED", "reason": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
