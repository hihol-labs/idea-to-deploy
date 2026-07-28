#!/usr/bin/env python3
"""Create hash-bound, fail-closed fresh-session Git worktrees."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from typing import Any


PACKET_KIND = "fresh-session-unit-packet"
SESSION_KIND = "fresh-session-worktree"
SESSION_DIR = ".itd-session"
PACKET_ARTIFACT = f"{SESSION_DIR}/unit-packet.json"
STATE_ARTIFACT = f"{SESSION_DIR}/parent-state-snapshot.json"
SESSION_ARTIFACT = f"{SESSION_DIR}/session.json"
FULL_PACKET_FIELDS = {
    "version",
    "kind",
    "unitId",
    "baseCommit",
    "allowedPaths",
    "mutableResources",
    "sharedMutableResources",
    "parentState",
}
OPTIONAL_PACKET_FIELDS = {"makerSession"}
RESOURCE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
UNIT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
OID_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SESSION_PATTERN = re.compile(r"^[0-9a-f]{32}$")
OBJECT_FILE_MAX_BYTES = 512 * 1024
SAFE_HOST_ENVIRONMENT_KEYS = {
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "WINDIR",
}


class IsolationError(ValueError):
    """An actionable fail-closed isolation error."""

    def __init__(self, why: str, fix: str) -> None:
        super().__init__(why)
        self.why = why
        self.fix = fix


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def manifest_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def is_link_or_reparse(path: pathlib.Path) -> bool:
    try:
        if path.is_symlink():
            return True
        junction_probe = getattr(path, "is_junction", None)
        if callable(junction_probe) and junction_probe():
            return True
        attributes = int(getattr(path.lstat(), "st_file_attributes", 0) or 0)
    except (FileNotFoundError, OSError):
        return False
    return bool(
        attributes
        & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    )


def require_no_link_components(path: pathlib.Path, label: str) -> None:
    absolute = path.absolute()
    current = pathlib.Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if not os.path.lexists(current):
            continue
        if is_link_or_reparse(current):
            raise IsolationError(
                f"{label} contains a symlink or reparse component: {current}",
                f"Use a regular, physically contained path for {label}.",
            )


def regular_file(path: pathlib.Path, label: str) -> pathlib.Path:
    require_no_link_components(path, label)
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        raise IsolationError(
            f"{label} is unavailable: {path}: {exc}",
            f"Restore a readable regular file for {label}.",
        ) from exc
    if not stat.S_ISREG(mode):
        raise IsolationError(
            f"{label} is not a regular file: {path}",
            f"Replace {label} with a regular file.",
        )
    return path.resolve()


def load_object_bytes(path: pathlib.Path, label: str) -> tuple[dict[str, Any], bytes]:
    fd: int | None = None
    try:
        require_no_link_components(path, label)
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > OBJECT_FILE_MAX_BYTES:
            raise IsolationError(
                f"{label} is not a bounded regular file: {path}",
                f"Restore {label} as a regular JSON file no larger than "
                f"{OBJECT_FILE_MAX_BYTES} bytes.",
            )
        flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
        flags |= int(getattr(os, "O_NOFOLLOW", 0))
        fd = os.open(path, flags)
        opened = os.fstat(fd)
        if (
            not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
        ):
            raise IsolationError(
                f"{label} changed while opening: {path}",
                f"Restore the exact stable regular file for {label}.",
            )
        chunks: list[bytes] = []
        remaining = OBJECT_FILE_MAX_BYTES + 1
        while remaining:
            chunk = os.read(fd, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        require_no_link_components(path, label)
        current = path.lstat()
        if (
            len(raw) > OBJECT_FILE_MAX_BYTES
            or is_link_or_reparse(path)
            or (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            )
            != (
                current.st_dev,
                current.st_ino,
                current.st_size,
                current.st_mtime_ns,
            )
        ):
            raise IsolationError(
                f"{label} changed while reading or exceeds its size limit: {path}",
                f"Restore the exact stable bounded regular file for {label}.",
            )
        value = json.loads(raw.decode("utf-8"))
    except IsolationError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IsolationError(
            f"{label} is not readable bounded UTF-8 JSON: {path}: {exc}",
            f"Restore a valid JSON object for {label}.",
        ) from exc
    finally:
        if fd is not None:
            os.close(fd)
    if not isinstance(value, dict):
        raise IsolationError(
            f"{label} must contain a JSON object",
            f"Replace {label} with a JSON object.",
        )
    return value, raw


def portable_relative(raw: object, label: str) -> pathlib.PurePosixPath:
    if not isinstance(raw, str) or not raw:
        raise IsolationError(
            f"{label} must be a nonempty project-relative path",
            f"Use canonical forward-slash relative paths for {label}.",
        )
    if (
        "\\" in raw
        or ":" in raw
        or "\0" in raw
        or any(ord(character) < 32 for character in raw)
    ):
        raise IsolationError(
            f"{label} is not a canonical portable path: {raw!r}",
            f"Remove drive prefixes, backslashes, controls, and NUL from {label}.",
        )
    relative = pathlib.PurePosixPath(raw)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {".", ".."} for part in relative.parts)
        or relative.as_posix() != raw
    ):
        raise IsolationError(
            f"{label} is not a canonical contained relative path: {raw!r}",
            f"Use a normalized project-relative path without dot segments for {label}.",
        )
    return relative


def safe_project_path(
    root: pathlib.Path,
    raw: object,
    label: str,
    *,
    require_existing_file: bool = False,
) -> pathlib.Path:
    relative = portable_relative(raw, label)
    candidate = root.joinpath(*relative.parts)
    require_no_link_components(candidate, label)
    try:
        candidate.resolve(strict=False).relative_to(root.resolve())
    except ValueError as exc:
        raise IsolationError(
            f"{label} escapes the canonical repository: {relative.as_posix()}",
            f"Use a path physically contained by {root}.",
        ) from exc
    if require_existing_file:
        regular_file(candidate, label)
    return candidate


def safe_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in SAFE_HOST_ENVIRONMENT_KEYS
    }
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return environment


def git(
    root: pathlib.Path,
    *arguments: str,
    timeout: int = 120,
) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=str(root),
            env=safe_environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise IsolationError(
            f"Git command could not run: git {' '.join(arguments)}: {exc}",
            "Restore a working Git executable and retry with a new absent target.",
        ) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-800:]
        raise IsolationError(
            f"Git command failed: git {' '.join(arguments)}: {detail}",
            "Repair the Git repository or packet and retry with a new absent target.",
        )
    return result.stdout.strip()


def canonical_git_root(raw: pathlib.Path) -> pathlib.Path:
    require_no_link_components(raw, "root")
    try:
        root = raw.resolve(strict=True)
    except OSError as exc:
        raise IsolationError(
            f"root is unavailable: {raw}: {exc}",
            "Use the canonical top-level directory of a regular Git worktree.",
        ) from exc
    if not root.is_dir():
        raise IsolationError(
            f"root is not a directory: {root}",
            "Use the canonical top-level directory of a Git worktree.",
        )
    top = pathlib.Path(git(root, "rev-parse", "--show-toplevel")).resolve()
    if top != root:
        raise IsolationError(
            f"root is not the canonical Git top-level: {root}",
            f"Retry with --root {top}.",
        )
    return root


def full_commit(root: pathlib.Path, raw: object) -> str:
    if not isinstance(raw, str) or OID_PATTERN.fullmatch(raw) is None:
        raise IsolationError(
            "baseCommit must be a full lowercase 40-character Git commit id",
            "Regenerate the packet from an exact Git commit.",
        )
    resolved = git(root, "rev-parse", "--verify", f"{raw}^{{commit}}")
    if resolved != raw:
        raise IsolationError(
            f"baseCommit does not resolve to itself: {raw}",
            "Regenerate the packet from the intended exact commit.",
        )
    return raw


def exact_string_list(
    raw: object,
    label: str,
    *,
    minimum: int,
) -> list[str]:
    if not isinstance(raw, list) or len(raw) < minimum:
        raise IsolationError(
            f"{label} must be a list with at least {minimum} item(s)",
            f"Declare the complete {label} list explicitly.",
        )
    if not all(isinstance(item, str) and item for item in raw):
        raise IsolationError(
            f"{label} must contain only nonempty strings",
            f"Remove malformed entries from {label}.",
        )
    if len(set(raw)) != len(raw):
        raise IsolationError(
            f"{label} contains duplicates",
            f"Deduplicate {label}.",
        )
    return list(raw)


def validate_allowed_paths(
    root: pathlib.Path,
    base: str,
    raw: object,
) -> list[str]:
    paths = exact_string_list(raw, "allowedPaths", minimum=1)
    validated: list[str] = []
    for value in paths:
        relative = portable_relative(value, "allowedPaths")
        normalized = relative.as_posix()
        safe_project_path(
            root,
            normalized,
            "allowedPaths",
            require_existing_file=True,
        )
        tracked = git(
            root,
            "ls-tree",
            "-r",
            "--name-only",
            base,
            "--",
            f":(literal){normalized}",
        ).splitlines()
        if tracked != [normalized]:
            raise IsolationError(
                f"allowed path is not one exact tracked file at baseCommit: {normalized}",
                "Declare only regular tracked files from the exact packet base.",
            )
        validated.append(normalized)
    return validated


def validate_resources(raw: object) -> list[str]:
    resources = exact_string_list(raw, "mutableResources", minimum=1)
    if any(RESOURCE_PATTERN.fullmatch(item) is None for item in resources):
        raise IsolationError(
            "mutableResources contains a non-portable resource name",
            "Use lowercase alphanumeric resource names with dot, underscore, or hyphen.",
        )
    return resources


def validate_packet(
    root: pathlib.Path,
    packet: dict[str, Any],
    packet_raw: bytes,
    *,
    bound_state_raw: bytes | None = None,
) -> dict[str, Any]:
    fields = set(packet)
    if not FULL_PACKET_FIELDS.issubset(fields):
        missing = sorted(FULL_PACKET_FIELDS - fields)
        raise IsolationError(
            f"closed packet is missing required fields: {missing}",
            "Regenerate the packet with the packet command.",
        )
    unknown = fields - FULL_PACKET_FIELDS - OPTIONAL_PACKET_FIELDS
    if unknown:
        raise IsolationError(
            f"closed packet contains unknown fields: {sorted(unknown)}",
            "Remove undeclared fields or regenerate the packet.",
        )
    if packet.get("version") != 1 or packet.get("kind") != PACKET_KIND:
        raise IsolationError(
            "packet version or kind is unsupported",
            "Regenerate the packet with this runner.",
        )
    unit_id = packet.get("unitId")
    if not isinstance(unit_id, str) or UNIT_PATTERN.fullmatch(unit_id) is None:
        raise IsolationError(
            "unitId is missing or malformed",
            "Use a stable portable work-unit id.",
        )
    maker_session = packet.get("makerSession")
    if (
        maker_session is not None
        and (
            not isinstance(maker_session, str)
            or SESSION_PATTERN.fullmatch(maker_session) is None
        )
    ):
        raise IsolationError(
            "makerSession is malformed",
            "Use a 32-character lowercase hexadecimal maker session id.",
        )
    base = full_commit(root, packet.get("baseCommit"))
    allowed_paths = validate_allowed_paths(root, base, packet.get("allowedPaths"))
    shared = packet.get("sharedMutableResources")
    if not isinstance(shared, list):
        raise IsolationError(
            "sharedMutableResources must be an explicit list",
            "Declare an empty list; shared mutable fallback is forbidden.",
        )
    if shared:
        raise IsolationError(
            f"shared mutable resources are forbidden: {shared!r}",
            "Provide exclusive mutableResources and an empty sharedMutableResources list.",
        )
    resources = validate_resources(packet.get("mutableResources"))
    parent_state: dict[str, Any] | None = None
    state_raw: bytes
    state_sha: str
    binding = packet.get("parentState")
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
        raise IsolationError(
            "parentState must be a closed path/sha256 binding",
            "Regenerate the packet from canonical parent state.",
        )
    if binding.get("path") != ".itd-memory/STATE.json":
        raise IsolationError(
            "parentState.path must be .itd-memory/STATE.json",
            "Bind the canonical parent-owned ITD state.",
        )
    if (
        not isinstance(binding.get("sha256"), str)
        or SHA_PATTERN.fullmatch(binding["sha256"]) is None
    ):
        raise IsolationError(
            "parentState.sha256 must be a lowercase SHA-256 digest",
            "Regenerate the packet from canonical parent state.",
        )
    if bound_state_raw is not None:
        try:
            parent_state = json.loads(bound_state_raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IsolationError(
                f"bound parent state snapshot is invalid: {exc}",
                "Restore the exact read-only parent state snapshot.",
            ) from exc
        if not isinstance(parent_state, dict):
            raise IsolationError(
                "bound parent state snapshot must contain an object",
                "Restore the exact read-only parent state snapshot.",
            )
        state_raw = bound_state_raw
    else:
        state_path = safe_project_path(
            root,
            binding["path"],
            "parent state",
            require_existing_file=True,
        )
        parent_state, state_raw = load_object_bytes(state_path, "parent state")
    state_sha = sha256_bytes(state_raw)
    if state_sha != binding["sha256"]:
        raise IsolationError(
            "parent state changed after the packet was created",
            "Reconcile canonical state and regenerate the unit packet.",
        )
    current = parent_state.get("currentUnit")
    if (
        not isinstance(current, dict)
        or current.get("id") != unit_id
        or current.get("status") not in {"in_progress", "recovery_required"}
    ):
        raise IsolationError(
            "parent state does not bind the packet unit as active",
            "Activate exactly this WIP=1 unit, then regenerate the packet.",
        )
    return {
        "unitId": unit_id,
        "baseCommit": base,
        "allowedPaths": allowed_paths,
        "mutableResources": resources,
        "makerSession": maker_session,
        "packetRaw": packet_raw,
        "packetSha256": sha256_bytes(packet_raw),
        "parentState": parent_state,
        "parentStateRaw": state_raw,
        "parentStateSha256": state_sha,
    }


def target_path(raw: pathlib.Path, root: pathlib.Path) -> pathlib.Path:
    target = raw.absolute()
    require_no_link_components(target.parent, "worktree parent")
    if not target.parent.is_dir():
        raise IsolationError(
            f"worktree parent does not exist: {target.parent}",
            "Create a regular parent directory and retry with an absent target.",
        )
    if os.path.lexists(target):
        raise IsolationError(
            f"worktree target already exists: {target}",
            "Use a new absent worktree target; existing paths are never reused.",
        )
    resolved_parent = target.parent.resolve()
    resolved_target = resolved_parent / target.name
    if resolved_target == root or root in resolved_target.parents:
        raise IsolationError(
            "worktree target must not be inside the canonical parent worktree",
            "Use an absent sibling directory outside the parent worktree.",
        )
    common_raw = pathlib.Path(git(root, "rev-parse", "--git-common-dir"))
    common = (
        common_raw
        if common_raw.is_absolute()
        else root / common_raw
    ).resolve()
    if resolved_target == common or common in resolved_target.parents:
        raise IsolationError(
            "worktree target must not be inside the Git common directory",
            "Use an absent sibling directory outside Git metadata.",
        )
    return resolved_target


def write_new_read_only(path: pathlib.Path, raw: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = None
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        path.chmod(0o444)
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise IsolationError(
            f"cannot create read-only artifact {path}: {exc}",
            "Repair permissions and retry with a new absent worktree target.",
        ) from exc


def replace_read_only(path: pathlib.Path, raw: bytes) -> None:
    temporary: pathlib.Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=str(path.parent),
        )
        temporary = pathlib.Path(name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o444)
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise IsolationError(
            f"cannot atomically replace read-only artifact {path}: {exc}",
            "Repair permissions without editing the existing artifact and retry.",
        ) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def create_namespaces(
    session_root: pathlib.Path,
    resources: list[str],
    session_id: str,
) -> dict[str, dict[str, object]]:
    namespace_root = session_root / "namespaces"
    namespace_root.mkdir(mode=0o700)
    namespaces: dict[str, dict[str, object]] = {}
    for resource in resources:
        directory = namespace_root / resource
        directory.mkdir(mode=0o700)
        namespaces[resource] = {
            "resource": resource,
            "sessionId": session_id,
            "id": f"{resource}:{session_id}",
            "exclusive": True,
            "shared": False,
        }
    return namespaces


def cleanup_created_worktree(root: pathlib.Path, target: pathlib.Path) -> str | None:
    problems: list[str] = []
    try:
        git(root, "worktree", "remove", "--force", str(target))
    except IsolationError as exc:
        problems.append(exc.why)
    if os.path.lexists(target):
        try:
            if is_link_or_reparse(target):
                target.unlink()
            else:
                shutil.rmtree(target)
        except OSError as exc:
            problems.append(f"filesystem cleanup failed: {exc}")
    try:
        git(root, "worktree", "prune")
    except IsolationError as exc:
        problems.append(exc.why)
    return "; ".join(problems) or None


def packet_command(arguments: argparse.Namespace) -> dict[str, Any]:
    root = canonical_git_root(arguments.root)
    unit_id = arguments.unit_id
    if UNIT_PATTERN.fullmatch(unit_id) is None:
        raise IsolationError(
            "unit id is malformed",
            "Use a stable portable work-unit id.",
        )
    base = full_commit(root, arguments.base_commit or git(root, "rev-parse", "HEAD"))
    allowed_paths = validate_allowed_paths(root, base, arguments.allow)
    resources = validate_resources(arguments.resource)
    state_path = safe_project_path(
        root,
        ".itd-memory/STATE.json",
        "parent state",
        require_existing_file=True,
    )
    state, state_raw = load_object_bytes(state_path, "parent state")
    current = state.get("currentUnit")
    if (
        not isinstance(current, dict)
        or current.get("id") != unit_id
        or current.get("status") not in {"in_progress", "recovery_required"}
    ):
        raise IsolationError(
            "canonical parent state does not bind this unit as active",
            "Activate exactly this WIP=1 unit before creating its packet.",
        )
    packet: dict[str, Any] = {
        "version": 1,
        "kind": PACKET_KIND,
        "unitId": unit_id,
        "baseCommit": base,
        "allowedPaths": allowed_paths,
        "mutableResources": resources,
        "sharedMutableResources": [],
        "parentState": {
            "path": ".itd-memory/STATE.json",
            "sha256": sha256_bytes(state_raw),
        },
    }
    if arguments.maker_session:
        if SESSION_PATTERN.fullmatch(arguments.maker_session) is None:
            raise IsolationError(
                "maker session is malformed",
                "Use a 32-character lowercase hexadecimal maker session id.",
            )
        packet["makerSession"] = arguments.maker_session
    output = arguments.output.absolute()
    require_no_link_components(output.parent, "packet output parent")
    if not output.parent.is_dir():
        raise IsolationError(
            f"packet output parent does not exist: {output.parent}",
            "Create a regular output parent and retry.",
        )
    if os.path.lexists(output):
        raise IsolationError(
            f"packet output already exists: {output}",
            "Use a new absent packet output path.",
        )
    raw = canonical_bytes(packet)
    write_new_read_only(output, raw)
    return {
        "status": "prepared",
        "packet": str(output),
        "packetSha256": sha256_bytes(raw),
        **packet,
    }


def prepare_command(arguments: argparse.Namespace) -> dict[str, Any]:
    root = canonical_git_root(arguments.root)
    packet, packet_raw = load_object_bytes(arguments.packet, "unit packet")
    validated = validate_packet(root, packet, packet_raw)
    target = target_path(arguments.worktree, root)
    state_hash_before = validated["parentStateSha256"]
    created = False
    try:
        git(
            root,
            "worktree",
            "add",
            "--detach",
            str(target),
            validated["baseCommit"],
        )
        created = True
        target_root = pathlib.Path(
            git(target, "rev-parse", "--show-toplevel")
        ).resolve()
        if target_root != target:
            raise IsolationError(
                "Git created a worktree with an unexpected top-level",
                "Remove the partial target and retry outside aliases or links.",
            )
        if git(target, "rev-parse", "HEAD") != validated["baseCommit"]:
            raise IsolationError(
                "isolated worktree HEAD does not equal packet baseCommit",
                "Remove the partial target and retry from the exact packet base.",
            )
        session_root = target / SESSION_DIR
        session_root.mkdir(mode=0o700)
        session_id = validated["makerSession"] or uuid.uuid4().hex
        namespaces = create_namespaces(
            session_root,
            validated["mutableResources"],
            session_id,
        )
        packet_artifact = target / PACKET_ARTIFACT
        state_artifact = target / STATE_ARTIFACT
        session_artifact = target / SESSION_ARTIFACT
        write_new_read_only(packet_artifact, validated["packetRaw"])
        write_new_read_only(state_artifact, validated["parentStateRaw"])
        git_dir_raw = pathlib.Path(git(target, "rev-parse", "--git-dir"))
        git_dir = (
            git_dir_raw if git_dir_raw.is_absolute() else target / git_dir_raw
        ).resolve()
        common_raw = pathlib.Path(git(target, "rev-parse", "--git-common-dir"))
        common_dir = (
            common_raw if common_raw.is_absolute() else target / common_raw
        ).resolve()
        candidate_tree = git(
            target,
            "rev-parse",
            f"{validated['baseCommit']}^{{tree}}",
        )
        session: dict[str, Any] = {
            "version": 1,
            "kind": SESSION_KIND,
            "unitId": validated["unitId"],
            "sessionId": session_id,
            "packetSha256": validated["packetSha256"],
            "parentStateSha256": sha256_bytes(validated["parentStateRaw"]),
            "stateOwner": "parent",
            "baseCommit": validated["baseCommit"],
            "candidateTree": candidate_tree,
            "worktreeRoot": str(target),
            "worktreeGitDir": str(git_dir),
            "gitCommonDir": str(common_dir),
            "packet": PACKET_ARTIFACT,
            "parentStateSnapshot": STATE_ARTIFACT,
            "mutableNamespaces": namespaces,
            "namespaceManifestSha256": sha256_bytes(manifest_bytes(namespaces)),
            "sharedMutableFallbacks": 0,
            "completionEvidence": False,
            "externalAdoptionEvidence": False,
            "fixtureCompatibility": False,
            "syntheticParentState": False,
            "createdAt": utc_now(),
            "makerSession": session_id,
        }
        current_state_path = root / ".itd-memory" / "STATE.json"
        _, current_state_raw = load_object_bytes(
            current_state_path,
            "parent state",
        )
        state_hash_after = sha256_bytes(current_state_raw)
        if state_hash_after != state_hash_before:
            raise IsolationError(
                "canonical parent state changed while preparing the worktree",
                "Discard the partial target, reconcile state, and generate a new packet.",
            )
        write_new_read_only(session_artifact, canonical_bytes(session))
        return session
    except Exception as exc:
        cleanup_problem = (
            cleanup_created_worktree(root, target) if created else None
        )
        if isinstance(exc, IsolationError):
            why = exc.why
            fix = exc.fix
        else:
            why = f"unexpected preparation failure: {exc}"
            fix = "Inspect the repository and retry with a new absent target."
        if cleanup_problem:
            why = f"{why}; partial cleanup also failed: {cleanup_problem}"
            fix = (
                f"Manually inspect only the newly created target {target} and "
                "the repository worktree registry before retrying."
            )
        raise IsolationError(why, fix) from exc


def contained_artifact(
    worktree: pathlib.Path,
    raw: object,
    expected: str,
    label: str,
) -> pathlib.Path:
    if raw != expected:
        raise IsolationError(
            f"{label} path drifted from {expected}",
            "Restore the original session artifact paths.",
        )
    path = safe_project_path(
        worktree,
        raw,
        label,
        require_existing_file=True,
    )
    if path.stat().st_mode & 0o222:
        raise IsolationError(
            f"{label} is writable: {path}",
            "Restore the read-only session artifact before finalization.",
        )
    return path


def validate_namespaces(
    worktree: pathlib.Path,
    session: dict[str, Any],
    resources: list[str],
) -> None:
    session_id = session.get("sessionId")
    if not isinstance(session_id, str) or SESSION_PATTERN.fullmatch(session_id) is None:
        raise IsolationError(
            "sessionId is malformed",
            "Restore the original successful session artifact.",
        )
    namespaces = session.get("mutableNamespaces")
    if not isinstance(namespaces, dict) or set(namespaces) != set(resources):
        raise IsolationError(
            "mutable namespace keys do not equal packet resources",
            "Restore the exact session-scoped namespace manifest.",
        )
    for resource in resources:
        value = namespaces.get(resource)
        expected = {
            "resource": resource,
            "sessionId": session_id,
            "id": f"{resource}:{session_id}",
            "exclusive": True,
            "shared": False,
        }
        if value != expected:
            raise IsolationError(
                f"mutable namespace identity drifted for {resource}",
                "Restore the exact exclusive resource-plus-session namespace.",
            )
        directory = worktree / SESSION_DIR / "namespaces" / resource
        require_no_link_components(directory, "mutable namespace")
        if not directory.is_dir():
            raise IsolationError(
                f"mutable namespace directory is missing: {resource}",
                "Restore the exclusive namespace directory.",
            )
    if session.get("namespaceManifestSha256") != sha256_bytes(
        manifest_bytes(namespaces)
    ):
        raise IsolationError(
            "namespace manifest hash mismatch",
            "Restore the original namespace manifest.",
        )


def finalize_command(arguments: argparse.Namespace) -> dict[str, Any]:
    worktree = canonical_git_root(arguments.root)
    expected_session_path = worktree / SESSION_ARTIFACT
    session_path = (
        arguments.session.absolute()
        if arguments.session is not None
        else expected_session_path
    )
    if session_path.resolve(strict=False) != expected_session_path.resolve(strict=False):
        raise IsolationError(
            "session artifact must be the worktree-local .itd-session/session.json",
            "Finalize the exact contained session artifact created by prepare.",
        )
    session, _ = load_object_bytes(session_path, "session artifact")
    if session_path.stat().st_mode & 0o222:
        raise IsolationError(
            "session artifact is writable",
            "Restore the original read-only session artifact before finalization.",
        )
    if set(session) - {
        "version",
        "kind",
        "unitId",
        "sessionId",
        "packetSha256",
        "parentStateSha256",
        "stateOwner",
        "baseCommit",
        "candidateTree",
        "worktreeRoot",
        "worktreeGitDir",
        "gitCommonDir",
        "packet",
        "parentStateSnapshot",
        "mutableNamespaces",
        "namespaceManifestSha256",
        "sharedMutableFallbacks",
        "completionEvidence",
        "externalAdoptionEvidence",
        "fixtureCompatibility",
        "syntheticParentState",
        "createdAt",
        "makerSession",
        "finalizedAt",
    }:
        raise IsolationError(
            "session artifact contains unknown fields",
            "Restore the exact successful session artifact.",
        )
    if (
        session.get("version") != 1
        or session.get("kind") != SESSION_KIND
        or session.get("stateOwner") != "parent"
        or session.get("sharedMutableFallbacks") != 0
        or session.get("completionEvidence") is not False
        or session.get("externalAdoptionEvidence") is not False
        or session.get("fixtureCompatibility") is not False
        or session.get("syntheticParentState") is not False
    ):
        raise IsolationError(
            "session safety invariants are missing or weakened",
            "Restore the original successful session artifact.",
        )
    if pathlib.Path(str(session.get("worktreeRoot") or "")).resolve() != worktree:
        raise IsolationError(
            "session worktreeRoot does not bind this canonical worktree",
            "Finalize only inside the worktree that created the session.",
        )
    packet_path = contained_artifact(
        worktree,
        session.get("packet"),
        PACKET_ARTIFACT,
        "packet artifact",
    )
    state_path = contained_artifact(
        worktree,
        session.get("parentStateSnapshot"),
        STATE_ARTIFACT,
        "parent state snapshot",
    )
    _, state_raw = load_object_bytes(state_path, "parent state snapshot")
    packet, packet_raw = load_object_bytes(packet_path, "packet artifact")
    validated = validate_packet(
        worktree,
        packet,
        packet_raw,
        bound_state_raw=state_raw,
    )
    if (
        sha256_bytes(packet_raw) != session.get("packetSha256")
        or sha256_bytes(state_raw) != session.get("parentStateSha256")
    ):
        raise IsolationError(
            "packet or parent-state snapshot hash mismatch",
            "Restore the exact read-only session artifacts.",
        )
    if (
        validated["unitId"] != session.get("unitId")
        or validated["baseCommit"] != session.get("baseCommit")
    ):
        raise IsolationError(
            "session identity does not match its packet",
            "Restore the original packet/session pair.",
        )
    expected_maker_session = validated["makerSession"] or session.get("sessionId")
    if (
        session.get("sessionId") != expected_maker_session
        or session.get("makerSession") != expected_maker_session
    ):
        raise IsolationError(
            "session maker identity does not match its hash-bound packet",
            "Restore the exact packet-bound maker session and its namespaces.",
        )
    validate_namespaces(worktree, session, validated["mutableResources"])
    git_dir_raw = pathlib.Path(git(worktree, "rev-parse", "--git-dir"))
    git_dir = (
        git_dir_raw if git_dir_raw.is_absolute() else worktree / git_dir_raw
    ).resolve()
    common_raw = pathlib.Path(git(worktree, "rev-parse", "--git-common-dir"))
    common = (
        common_raw if common_raw.is_absolute() else worktree / common_raw
    ).resolve()
    if (
        pathlib.Path(str(session.get("worktreeGitDir") or "")).resolve() != git_dir
        or pathlib.Path(str(session.get("gitCommonDir") or "")).resolve() != common
    ):
        raise IsolationError(
            "session Git identity does not match this linked worktree",
            "Finalize only the exact linked worktree from the successful session.",
        )
    changed_raw = git(
        worktree,
        "diff",
        "--cached",
        "--name-only",
        "-z",
        session["baseCommit"],
        "--",
    )
    changed = {item for item in changed_raw.split("\0") if item}
    if not changed.issubset(set(validated["allowedPaths"])):
        raise IsolationError(
            f"staged candidate changed paths outside packet scope: {sorted(changed)}",
            "Unstage out-of-scope changes or generate a new reviewed packet.",
        )
    session["candidateTree"] = git(worktree, "write-tree")
    session["finalizedAt"] = utc_now()
    replace_read_only(session_path, canonical_bytes(session))
    return session


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Fail-closed fresh-session Git worktree isolation",
    )
    subcommands = command.add_subparsers(dest="command", required=True)

    packet = subcommands.add_parser("packet")
    packet.add_argument("--root", type=pathlib.Path, default=pathlib.Path.cwd())
    packet.add_argument("--unit-id", required=True)
    packet.add_argument("--base-commit")
    packet.add_argument("--allow", action="append", required=True)
    packet.add_argument("--resource", action="append", required=True)
    packet.add_argument("--maker-session")
    packet.add_argument("--output", type=pathlib.Path, required=True)

    prepare = subcommands.add_parser("prepare")
    prepare.add_argument("--root", type=pathlib.Path, required=True)
    prepare.add_argument("--packet", type=pathlib.Path, required=True)
    prepare.add_argument("--worktree", type=pathlib.Path, required=True)

    finalize = subcommands.add_parser("finalize")
    finalize.add_argument("--root", type=pathlib.Path, required=True)
    finalize.add_argument("--session", type=pathlib.Path)
    return command


def main() -> int:
    arguments = parser().parse_args()
    try:
        if arguments.command == "packet":
            result = packet_command(arguments)
        elif arguments.command == "prepare":
            result = prepare_command(arguments)
        else:
            result = finalize_command(arguments)
    except IsolationError as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "why": exc.why,
                    "fix": exc.fix,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
