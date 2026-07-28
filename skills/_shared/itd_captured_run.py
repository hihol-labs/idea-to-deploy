#!/usr/bin/env python3
"""Validate and replay a hash-bound captured brownfield run."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any


REQUIRED_BINDINGS = {
    "candidateTree",
    "ticketSha256",
    "contextSha256",
    "taskContractSha256",
    "patchSha256",
    "machineReceiptSha256",
    "checkerReceiptSha256",
    "adjudicationReceiptSha256",
    "reviewReportSha256",
    "metricsSha256",
}

SAFE_HOST_ENVIRONMENT_KEYS = {
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
}
INSTALL_ROOT = pathlib.Path(__file__).resolve().parents[2]
CANONICAL_CAPTURE_MANIFEST = (
    INSTALL_ROOT / "docs" / "examples" / "brownfield-piv" / "manifest.json"
)
CANONICAL_CAPTURE_MANIFEST_SHA256 = (
    "170b4559643446b579e887062d4d9f769b5dd5a6717033475ebf51948cdceb7a"
)
ALLOWED_REPLAY_COMMANDS = ((
    "{python}", "-B", "-m", "unittest", "discover", "-s", "tests", "-v",
),)


class CaptureError(ValueError):
    """A fail-closed captured-run error."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_object(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureError(f"{label} is unreadable JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CaptureError(f"{label} must be a JSON object: {path}")
    return value


def is_link_or_reparse(path: pathlib.Path) -> bool:
    if path.is_symlink():
        return True
    junction_probe = getattr(path, "is_junction", None)
    try:
        if callable(junction_probe) and junction_probe():
            return True
        attributes = int(getattr(path.lstat(), "st_file_attributes", 0) or 0)
    except (FileNotFoundError, OSError):
        return False
    return bool(attributes & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)))


def portable_relative(raw: object, label: str) -> pathlib.PurePosixPath:
    if not isinstance(raw, str) or not raw:
        raise CaptureError(f"{label} must be a nonempty relative path")
    if ("\\" in raw or "\0" in raw or ":" in raw
            or any(ord(character) < 32 for character in raw)):
        raise CaptureError(f"{label} is not a canonical portable path")
    relative = pathlib.PurePosixPath(raw)
    if (relative.is_absolute() or not relative.parts
            or ".." in relative.parts or relative.as_posix() != raw):
        raise CaptureError(f"{label} must be a canonical in-root relative path")
    return relative


def safe_relative(base: pathlib.Path, raw: object, label: str,
                  *, require_file: bool = False,
                  require_dir: bool = False) -> pathlib.Path:
    relative = portable_relative(raw, label)
    candidate = base / pathlib.Path(*relative.parts)
    cursor = base
    for part in relative.parts:
        cursor = cursor / part
        if is_link_or_reparse(cursor):
            raise CaptureError(f"{label} contains a symlink/reparse component: {relative}")
    try:
        candidate.resolve(strict=False).relative_to(base.resolve())
    except ValueError as exc:
        raise CaptureError(f"{label} escapes the captured-run root: {relative}") from exc
    if require_file and not candidate.is_file():
        raise CaptureError(f"{label} is missing or not a regular file: {relative}")
    if require_dir and not candidate.is_dir():
        raise CaptureError(f"{label} is missing or not a regular directory: {relative}")
    return candidate


def require_plain_tree(root: pathlib.Path, label: str) -> list[str]:
    pending = [root]
    files: list[str] = []
    while pending:
        current = pending.pop()
        try:
            entries = list(os.scandir(current))
        except OSError as exc:
            raise CaptureError(f"{label} is not safely readable: {exc}") from exc
        for entry in entries:
            item = pathlib.Path(entry.path)
            if is_link_or_reparse(item):
                raise CaptureError(f"{label} contains a symlink/reparse artifact")
            try:
                if entry.is_dir(follow_symlinks=False):
                    pending.append(item)
                elif entry.is_file(follow_symlinks=False):
                    files.append(item.relative_to(root).as_posix())
                else:
                    raise CaptureError(
                        f"{label} contains a non-regular filesystem artifact")
            except OSError as exc:
                raise CaptureError(f"{label} changed while being inspected") from exc
    return sorted(files)


def exact_paths(rows: object, label: str) -> list[str]:
    if not isinstance(rows, list) or not rows:
        raise CaptureError(f"{label} must be a nonempty list")
    values: list[str] = []
    for raw in rows:
        relative = portable_relative(raw, label)
        values.append(relative.as_posix())
    if len(set(values)) != len(values):
        raise CaptureError(f"{label} contains duplicate paths")
    return values


def explicit_commands(rows: object) -> list[list[str]]:
    if not isinstance(rows, list) or not rows:
        raise CaptureError("replay.commands must be a nonempty list")
    commands: list[list[str]] = []
    for row in rows:
        if (not isinstance(row, list) or not row
                or not all(isinstance(item, str) and item and "\0" not in item
                           for item in row)):
            raise CaptureError("each replay command must be an explicit nonempty argv array")
        if tuple(row) not in ALLOWED_REPLAY_COMMANDS:
            raise CaptureError(
                "captured-run v1 commands must use the closed built-in unittest argv")
        commands.append(list(row))
    if tuple(tuple(command) for command in commands) != ALLOWED_REPLAY_COMMANDS:
        raise CaptureError("captured-run v1 requires the exact closed replay command set")
    return commands



def require_trusted_replay_manifest(path: pathlib.Path) -> pathlib.Path:
    """Bind code execution to the shipped, immutable capture rather than caller input."""
    supplied = path.absolute()
    canonical = CANONICAL_CAPTURE_MANIFEST.absolute()
    if supplied != canonical:
        raise CaptureError(
            "replay is allowed only for the bundled hash-pinned captured-run manifest")
    cursor = supplied
    while True:
        if is_link_or_reparse(cursor):
            raise CaptureError("trusted replay manifest has a linked/reparse ancestor")
        if cursor == INSTALL_ROOT or cursor.parent == cursor:
            break
        cursor = cursor.parent
    if cursor != INSTALL_ROOT or not supplied.is_file():
        raise CaptureError("trusted replay manifest is outside the installed methodology")
    if sha256_file(supplied) != CANONICAL_CAPTURE_MANIFEST_SHA256:
        raise CaptureError("trusted replay manifest hash does not match the shipped capture")
    return supplied


def validate_manifest(path: pathlib.Path) -> tuple[dict[str, Any], pathlib.Path]:
    manifest_path = path.resolve()
    root = manifest_path.parent
    manifest = read_object(manifest_path, "captured-run manifest")
    if manifest.get("version") != 1:
        raise CaptureError("captured-run manifest version must be 1")
    if manifest.get("externalAdoptionEvidence") is not False:
        raise CaptureError("an internal captured run cannot claim external adoption")

    schema = manifest.get("schema") or {}
    schema_path = safe_relative(root, schema.get("path"), "schema", require_file=True)
    if sha256_file(schema_path) != schema.get("sha256"):
        raise CaptureError("captured-run schema hash mismatch")
    schema_value = read_object(schema_path, "captured-run schema")
    if (schema_value.get("version") != 1
            or set(schema_value.get("requiredBindings") or []) != REQUIRED_BINDINGS):
        raise CaptureError("captured-run schema is incompatible")

    bindings = manifest.get("bindings")
    if not isinstance(bindings, dict) or set(bindings) != REQUIRED_BINDINGS:
        raise CaptureError("captured-run bindings are incomplete or contain unknown keys")
    tree = str(bindings.get("candidateTree") or "")
    if len(tree) != 40 or any(character not in "0123456789abcdef" for character in tree):
        raise CaptureError("candidateTree must be a full lowercase Git tree id")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise CaptureError("captured-run artifacts must be a nonempty path/hash map")
    for relative, expected in artifacts.items():
        artifact = safe_relative(root, relative, "artifact", require_file=True)
        if (not isinstance(expected, str) or len(expected) != 64
                or sha256_file(artifact) != expected):
            raise CaptureError(f"captured artifact hash mismatch: {relative}")

    mapping = manifest.get("bindingArtifacts")
    hash_bindings = REQUIRED_BINDINGS - {"candidateTree"}
    if not isinstance(mapping, dict) or set(mapping) != hash_bindings:
        raise CaptureError("each non-tree binding must map to one named artifact")
    if len(set(mapping.values())) != len(mapping):
        raise CaptureError("non-tree bindings must map one-to-one to named artifacts")
    for binding in hash_bindings:
        relative = mapping[binding]
        if relative not in artifacts or bindings[binding] != artifacts[relative]:
            raise CaptureError(f"binding {binding} does not match its named artifact")

    replay = manifest.get("replay")
    if not isinstance(replay, dict):
        raise CaptureError("captured replay contract is missing")
    safe_relative(root, replay.get("beforeDir"), "replay.beforeDir", require_dir=True)
    patch = safe_relative(root, replay.get("patch"), "replay.patch", require_file=True)
    if bindings["patchSha256"] != sha256_file(patch):
        raise CaptureError("replay patch is not the patchSha256-bound artifact")
    exact_paths(replay.get("baseTrackedPaths"), "replay.baseTrackedPaths")
    exact_paths(replay.get("trackedPaths"), "replay.trackedPaths")
    explicit_commands(replay.get("commands"))

    normalization = manifest.get("normalization")
    if (not isinstance(normalization, dict)
            or not isinstance(normalization.get("volatileFields"), list)
            or normalization.get("receiptSemantics") != "canonical"):
        raise CaptureError("captured-run normalization contract is missing")
    return manifest, root


def isolated_environment(boundary: pathlib.Path,
                         git_executable: pathlib.Path) -> dict[str, str]:
    profile = boundary / "profile"
    temporary = boundary / "temp"
    profile.mkdir()
    temporary.mkdir()
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in SAFE_HOST_ENVIRONMENT_KEYS
    }
    environment.update({
        "HOME": str(profile),
        "USERPROFILE": str(profile),
        "TEMP": str(temporary),
        "TMP": str(temporary),
        "TMPDIR": str(temporary),
    })
    executable_dirs = [
        str(pathlib.Path(sys.executable).resolve().parent),
        str(git_executable.parent),
    ]
    system_root = environment.get("SYSTEMROOT") or environment.get("SystemRoot")
    if system_root:
        executable_dirs.append(str(pathlib.Path(system_root) / "System32"))
    else:
        executable_dirs.extend(("/usr/bin", "/bin"))
    environment["PATH"] = os.pathsep.join(dict.fromkeys(executable_dirs))
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def run(argv: list[str], cwd: pathlib.Path, environment: dict[str, str],
        timeout: int = 120) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv, cwd=str(cwd), env=environment, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, shell=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise CaptureError(f"cannot execute replay argv {argv!r}: {exc}") from exc


def require_exit(result: subprocess.CompletedProcess[str], expected: int,
                 label: str) -> None:
    if result.returncode != expected:
        tail = (result.stdout + result.stderr).strip()[-800:]
        raise CaptureError(
            f"{label}: expected exit {expected}, got {result.returncode}: {tail}")


def materialized(command: list[str]) -> list[str]:
    return [sys.executable if item == "{python}" else item for item in command]


def require_git_state(fixture: pathlib.Path, environment: dict[str, str],
                      git_executable: str, expected_tree: str,
                      label: str) -> None:
    require_exit(run(
        [git_executable, "diff", "--quiet", "--"],
        fixture, environment), 0, f"{label} unstaged drift")
    untracked = run(
        [git_executable, "ls-files", "--others", "--"],
        fixture, environment)
    require_exit(untracked, 0, f"{label} untracked probe")
    if untracked.stdout.strip():
        raise CaptureError(f"{label} produced undeclared files")
    tree_result = run(
        [git_executable, "write-tree"], fixture, environment)
    require_exit(tree_result, 0, f"{label} Git tree")
    if tree_result.stdout.strip() != expected_tree:
        raise CaptureError(f"{label} changed the exact Git tree")


def replay_manifest(path: pathlib.Path) -> dict[str, Any]:
    path = require_trusted_replay_manifest(path)
    manifest, root = validate_manifest(path)
    replay = manifest["replay"]
    before = safe_relative(root, replay["beforeDir"], "replay.beforeDir",
                           require_dir=True)
    patch = safe_relative(root, replay["patch"], "replay.patch", require_file=True)
    commands = explicit_commands(replay["commands"])
    base_paths = exact_paths(replay["baseTrackedPaths"], "replay.baseTrackedPaths")
    tracked_paths = exact_paths(replay["trackedPaths"], "replay.trackedPaths")
    before_files = require_plain_tree(before, "replay.beforeDir")
    if sorted(base_paths) != before_files:
        raise CaptureError(
            "replay.baseTrackedPaths must equal every regular file in beforeDir")
    git_probe = shutil.which("git")
    if not git_probe:
        raise CaptureError("the trusted host Git executable is unavailable")
    git_executable = str(pathlib.Path(git_probe).resolve())

    with tempfile.TemporaryDirectory(prefix="itd-captured-replay-") as raw:
        boundary = pathlib.Path(raw)
        fixture = boundary / "project"
        shutil.copytree(before, fixture)
        environment = isolated_environment(boundary, pathlib.Path(git_executable))

        require_exit(run([git_executable, "init", "-q"], fixture, environment),
                     0, "git init")
        require_exit(run(
            [git_executable, "config", "user.email", "fixture@example.invalid"],
            fixture, environment), 0, "git email")
        require_exit(run(
            [git_executable, "config", "user.name", "ITD Capture"],
            fixture, environment), 0, "git name")
        require_exit(run(
            [git_executable, "add", "--", *base_paths],
            fixture, environment), 0, "exact base stage")
        require_exit(run(
            [git_executable, "commit", "-qm", "captured base"],
            fixture, environment), 0, "base commit")
        base_tree_result = run(
            [git_executable, "write-tree"], fixture, environment)
        require_exit(base_tree_result, 0, "base Git tree")
        base_tree = base_tree_result.stdout.strip()
        require_git_state(
            fixture, environment, git_executable, base_tree, "clean base")

        before_results = []
        for index, command in enumerate(commands):
            before_results.append(
                run(materialized(command), fixture, environment))
            require_git_state(
                fixture, environment, git_executable, base_tree,
                f"pre-patch command {index}")
        if all(result.returncode == 0 for result in before_results):
            raise CaptureError("captured patch has no observed failing pre-patch command")

        require_exit(run(
            [git_executable, "apply", "--check", str(patch)],
            fixture, environment), 0, "patch preflight")
        require_exit(run(
            [git_executable, "apply", str(patch)],
            fixture, environment), 0, "patch apply")
        require_plain_tree(fixture, "patched replay fixture")
        require_exit(run(
            [git_executable, "add", "-A", "--", *tracked_paths],
            fixture, environment), 0, "exact candidate stage")
        candidate_result = run(
            [git_executable, "write-tree"], fixture, environment)
        require_exit(candidate_result, 0, "patch-produced Git tree")
        tree = candidate_result.stdout.strip()
        if tree != manifest["bindings"]["candidateTree"]:
            raise CaptureError(
                f"patch-produced tree {tree} does not match candidateTree "
                f"{manifest['bindings']['candidateTree']}")
        require_exit(run(
            [git_executable, "diff", "--quiet", "--"],
            fixture, environment), 0, "patch-produced unstaged drift")
        untracked = run(
            [git_executable, "ls-files", "--others", "--"],
            fixture, environment)
        require_exit(untracked, 0, "patch-produced untracked probe")
        if untracked.stdout.strip():
            raise CaptureError("patch produced undeclared files")

        for index, command in enumerate(commands):
            require_exit(run(materialized(command), fixture, environment), 0,
                         f"post-patch command {index}")
            require_git_state(
                fixture, environment, git_executable, tree,
                f"post-patch command {index}")
    return {
        "status": "PASSED",
        "candidateTree": tree,
        "commands": len(commands),
        "observedPrePatchFailures": sum(
            result.returncode != 0 for result in before_results),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate/replay a captured ITD run.")
    parser.add_argument("action", choices=("validate", "replay"))
    parser.add_argument("--manifest", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "validate":
            manifest, _ = validate_manifest(args.manifest)
            result = {
                "status": "VALID",
                "candidateTree": manifest["bindings"]["candidateTree"],
                "artifacts": len(manifest["artifacts"]),
            }
        else:
            result = replay_manifest(args.manifest)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (CaptureError, OSError) as exc:
        print(json.dumps({
            "status": "FAILED",
            "why": str(exc),
            "fix": "restore the named artifact/hash or regenerate the clean replay",
        }, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
