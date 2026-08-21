#!/usr/bin/env python3
"""Materialize the closed, content-bound runtime used by global ITD wrappers."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MANIFEST = ".itd-runtime.json"
RUNTIME_KIND = "itd-installed-runtime-v1"
MAX_RUNTIME_FILE_BYTES = 4 * 1024 * 1024
MAX_RUNTIME_BYTES = 16 * 1024 * 1024
RELEASE_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
)
CODEX_RELEASE_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:\+codex\.([a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?))?$"
)

RUNTIME_SHARED_FILES = (
    "EXTERNAL_REVIEW_POLICY.json",
    "EXTERNAL_REVIEW_VERDICT_SCHEMA.json",
    "GATE_DEPLOYMENT_PROFILES.json",
    "OPERATING_LOOP_POLICY.json",
    "OPERATING_LOOP_RECIPES.json",
    "PROPORTIONALITY_POLICY.json",
    "REVIEW_BROKER_POLICY.json",
    "REVIEW_BROKER_POLICY.schema.json",
    "REVIEW_BROKER_RUNTIME.schema.json",
    "VERIFICATION_LOOP_POLICY.json",
    "WORKING_DEADLINE_POLICY.json",
    "itd_captured_run.py",
    "itd_diagnostics_pilot.py",
    "itd_external_reviewer.py",
    "itd_external_write_gate.py",
    "itd_free_reviewer_producer.py",
    "itd_fresh_session_worktree.py",
    "itd_gate_control.py",
    "itd_harness_controls.py",
    "itd_incremental_diagnostics.py",
    "itd_operating_loops.py",
    "itd_review_broker.py",
    "itd_review_broker_primitives.py",
    "itd_review_evidence.py",
    "itd_reviewer_independence.py",
    "itd_semantic_navigation.py",
    "itd_unit_lifecycle.py",
    "itd_verification_loop.py",
    "itd_verification_profiles.py",
)
RUNTIME_SKILL_FILES = (
    # itd_verification_loop loads this module by absolute path when it
    # reconstructs and revalidates exact candidate context.  It is therefore
    # part of the executable gate closure even though it is not under
    # skills/_shared.
    "skills/review/scripts/itd_review_cache.py",
)
RUNTIME_FILES = (
    ".codex-plugin/plugin.json",
    ".claude-plugin/plugin.json",
    "scripts/itd.py",
    "scripts/itd_pre_push.py",
    "scripts/itd_machine_oracle.py",
    *(f"skills/_shared/{name}" for name in RUNTIME_SHARED_FILES),
    *RUNTIME_SKILL_FILES,
)


class RuntimeInstallError(RuntimeError):
    pass


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def default_runtime_parent() -> Path:
    if os.name == "nt":
        base = Path(
            os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))
        )
        return (base / "ITD" / "runtime").resolve()
    return (Path.home() / ".local" / "share" / "itd" / "runtime").resolve()


def _safe_relative(relative: str) -> bool:
    path = PurePosixPath(relative)
    return (
        bool(relative)
        and not path.is_absolute()
        and ".." not in path.parts
        and "\\" not in relative
    )


def _read_regular(path: Path, label: str) -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        raise RuntimeInstallError(f"{label} is missing or unreadable") from exc
    if path.is_symlink() or not stat.S_ISREG(info.st_mode):
        raise RuntimeInstallError(f"{label} is not a regular file")
    if info.st_size > MAX_RUNTIME_FILE_BYTES:
        raise RuntimeInstallError(f"{label} exceeds the runtime file bound")
    try:
        value = path.read_bytes()
    except OSError as exc:
        raise RuntimeInstallError(f"{label} is unreadable") from exc
    if len(value) != info.st_size:
        raise RuntimeInstallError(f"{label} changed while it was read")
    return value


def _source_bytes(source_root: Path) -> dict[str, bytes]:
    raw_root = source_root.expanduser()
    if raw_root.is_symlink():
        raise RuntimeInstallError("runtime source root may not be a symlink")
    try:
        root = raw_root.resolve(strict=True)
    except OSError as exc:
        raise RuntimeInstallError("runtime source root is unavailable") from exc
    values: dict[str, bytes] = {}
    total = 0
    for relative in RUNTIME_FILES:
        if not _safe_relative(relative):
            raise RuntimeInstallError("runtime inventory contains an unsafe path")
        cursor = root
        for part in PurePosixPath(relative).parts[:-1]:
            cursor /= part
            if cursor.is_symlink():
                raise RuntimeInstallError(
                    f"runtime source ancestor is a symlink: {relative}"
                )
        value = _read_regular(root / relative, f"runtime source {relative}")
        total += len(value)
        if total > MAX_RUNTIME_BYTES:
            raise RuntimeInstallError("runtime source exceeds the total byte bound")
        values[relative] = value
    return values


def _manifest_version(raw: bytes, *, host: str) -> str:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeInstallError(f"{host} runtime manifest is invalid") from exc
    version = value.get("version") if isinstance(value, dict) else None
    name = value.get("name") if isinstance(value, dict) else None
    if name != "idea-to-deploy" or not isinstance(version, str):
        raise RuntimeInstallError(f"{host} runtime manifest is invalid")
    expression = CODEX_RELEASE_RE if host == "Codex" else RELEASE_RE
    match = expression.fullmatch(version)
    if match is None:
        raise RuntimeInstallError(f"{host} runtime version is not trusted")
    return ".".join(match.groups()[:3])


def _runtime_manifest(values: dict[str, bytes]) -> dict[str, Any]:
    codex = _manifest_version(
        values[".codex-plugin/plugin.json"], host="Codex"
    )
    claude = _manifest_version(
        values[".claude-plugin/plugin.json"], host="Claude"
    )
    if codex != claude:
        raise RuntimeInstallError("Codex/Claude runtime release identities differ")
    files = [
        {"path": relative, "bytes": len(values[relative]),
         "sha256": sha256_bytes(values[relative])}
        for relative in RUNTIME_FILES
    ]
    unsigned: dict[str, Any] = {
        "version": 1,
        "kind": RUNTIME_KIND,
        "release": codex,
        "files": files,
    }
    return {**unsigned, "runtimeSha256": sha256_bytes(canonical_json(unsigned))}


def _validated_runtime_parent(path: Path) -> Path:
    parent = path.expanduser().absolute()
    for candidate in (parent, *parent.parents):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise RuntimeInstallError("runtime parent is unreadable") from exc
        junction = getattr(candidate, "is_junction", None)
        if candidate.is_symlink() or (callable(junction) and junction()):
            raise RuntimeInstallError(
                f"runtime parent ancestor is redirected: {candidate}"
            )
        if not stat.S_ISDIR(info.st_mode):
            raise RuntimeInstallError(
                f"runtime parent ancestor is not a directory: {candidate}"
            )
    return parent


def runtime_plan(
    *, source_root: Path = ROOT, runtime_parent: Path | None = None,
) -> tuple[dict[str, object], dict[str, bytes], dict[str, Any]]:
    values = _source_bytes(Path(source_root))
    manifest = _runtime_manifest(values)
    parent = _validated_runtime_parent(
        Path(runtime_parent or default_runtime_parent())
    )
    target = parent / (
        f"{manifest['release']}-{str(manifest['runtimeSha256'])[:16]}"
    )
    result: dict[str, object] = {
        "status": "PREVIEW",
        "runtimeRoot": str(target),
        "runtimeManifest": str(target / RUNTIME_MANIFEST),
        "runtimeSha256": manifest["runtimeSha256"],
        "release": manifest["release"],
    }
    return result, values, manifest


def validate_runtime(
    runtime_root: Path, expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_root = runtime_root.expanduser()
    if raw_root.is_symlink():
        raise RuntimeInstallError("installed runtime root may not be a symlink")
    root = raw_root.resolve(strict=True)
    manifest_path = root / RUNTIME_MANIFEST
    raw = _read_regular(manifest_path, "installed runtime manifest")
    if len(raw) > MAX_RUNTIME_FILE_BYTES:
        raise RuntimeInstallError("installed runtime manifest is oversized")
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeInstallError("installed runtime manifest is invalid") from exc
    if not isinstance(manifest, dict) or set(manifest) != {
        "version", "kind", "release", "files", "runtimeSha256",
    }:
        raise RuntimeInstallError("installed runtime manifest schema is invalid")
    files = manifest.get("files")
    if (
        manifest.get("version") != 1
        or manifest.get("kind") != RUNTIME_KIND
        or not isinstance(manifest.get("release"), str)
        or not isinstance(files, list)
        or [row.get("path") for row in files if isinstance(row, dict)]
        != list(RUNTIME_FILES)
    ):
        raise RuntimeInstallError("installed runtime manifest content is invalid")
    unsigned = {key: manifest[key] for key in (
        "version", "kind", "release", "files",
    )}
    if sha256_bytes(canonical_json(unsigned)) != manifest.get("runtimeSha256"):
        raise RuntimeInstallError("installed runtime aggregate digest is invalid")
    if expected is not None and manifest != expected:
        raise RuntimeInstallError("installed runtime differs from the source plan")
    declared_paths = set(RUNTIME_FILES) | {RUNTIME_MANIFEST}
    declared_directories: set[str] = set()
    for relative in declared_paths:
        parent = PurePosixPath(relative).parent
        while parent != PurePosixPath("."):
            declared_directories.add(parent.as_posix())
            parent = parent.parent
    actual_paths: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise RuntimeInstallError("installed runtime contains a symlink")
        if path.is_dir():
            if relative not in declared_directories:
                raise RuntimeInstallError(
                    "installed runtime directory inventory drifted"
                )
        elif path.is_file():
            actual_paths.add(relative)
        else:
            raise RuntimeInstallError("installed runtime contains a special file")
    if actual_paths != declared_paths:
        raise RuntimeInstallError("installed runtime file inventory drifted")
    for row in files:
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256"}:
            raise RuntimeInstallError("installed runtime file row is invalid")
        value = _read_regular(root / row["path"], f"runtime {row['path']}")
        if len(value) != row["bytes"] or sha256_bytes(value) != row["sha256"]:
            raise RuntimeInstallError(f"installed runtime file drifted: {row['path']}")
    return manifest


def _write_file(path: Path, value: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def install_runtime(
    *, source_root: Path = ROOT, runtime_parent: Path | None = None,
    apply: bool,
) -> dict[str, object]:
    result, values, manifest = runtime_plan(
        source_root=source_root, runtime_parent=runtime_parent
    )
    if not apply:
        target = Path(str(result["runtimeRoot"]))
        if target.exists():
            validate_runtime(target, manifest)
        return result
    target = Path(str(result["runtimeRoot"]))
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _validated_runtime_parent(parent)
    if target.exists():
        validate_runtime(target, manifest)
        return {**result, "status": "REUSED"}
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.new-", dir=parent))
    try:
        for relative in RUNTIME_FILES:
            _write_file(staging / relative, values[relative], 0o400)
        manifest_bytes = json.dumps(
            manifest, ensure_ascii=False, indent=2, sort_keys=True
        ).encode("utf-8") + b"\n"
        _write_file(staging / RUNTIME_MANIFEST, manifest_bytes, 0o400)
        validate_runtime(staging, manifest)
        _validated_runtime_parent(parent)
        try:
            os.rename(staging, target)
        except FileExistsError:
            validate_runtime(target, manifest)
            return {**result, "status": "REUSED"}
        validate_runtime(target, manifest)
        return {**result, "status": "INSTALLED"}
    except RuntimeInstallError:
        raise
    except OSError as exc:
        raise RuntimeInstallError("runtime snapshot could not be published") from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
