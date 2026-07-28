#!/usr/bin/env python3
"""Adversarial verifier for the fail-closed fresh-session worktree kit."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills" / "_shared" / "itd_fresh_session_worktree.py"
CONTRACT = ROOT / "docs" / "templates" / "itd" / "FRESH_SESSION_WORKTREE_CONTRACT.json"


class VerificationError(AssertionError):
    """A deterministic verifier failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def run(
    argv: list[str],
    cwd: pathlib.Path,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    try:
        return subprocess.run(
            argv,
            cwd=str(cwd),
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VerificationError(f"cannot run {argv!r}: {exc}") from exc


def checked(
    argv: list[str],
    cwd: pathlib.Path,
    label: str,
) -> subprocess.CompletedProcess[str]:
    result = run(argv, cwd)
    if result.returncode != 0:
        raise VerificationError(
            f"{label} failed with {result.returncode}: "
            f"{(result.stdout + result.stderr).strip()[-1000:]}"
        )
    return result


def git(root: pathlib.Path, *arguments: str) -> str:
    return checked(["git", *arguments], root, f"git {' '.join(arguments)}").stdout.strip()


def git_path(root: pathlib.Path, *arguments: str) -> pathlib.Path:
    value = pathlib.Path(git(root, *arguments))
    return (value if value.is_absolute() else root / value).resolve()


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def write_json(path: pathlib.Path, value: object) -> None:
    path.write_text(canonical(value) + "\n", encoding="utf-8")


def read_json(path: pathlib.Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} must contain an object")
    return value


def read_only(path: pathlib.Path) -> bool:
    return stat.S_ISREG(path.stat().st_mode) and not (path.stat().st_mode & 0o222)


def verify_bounded_object_reader(root: pathlib.Path) -> None:
    spec = importlib.util.spec_from_file_location("itd_fresh_session_runner", RUNNER)
    require(spec is not None and spec.loader is not None, "cannot import runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    oversized = root / "oversized-object.json"
    oversized.write_bytes(b" " * (module.OBJECT_FILE_MAX_BYTES + 1))
    try:
        module.load_object_bytes(oversized, "oversized object")
    except module.IsolationError:
        pass
    else:
        raise VerificationError("oversized session object was accepted")

    racing = root / "racing-object.json"
    racing.write_text("{}\n", encoding="utf-8")
    replacement = root / "racing-replacement.json"
    replacement.write_text('{"replacement":true}\n', encoding="utf-8")
    original_read = module.os.read
    replaced = False

    def replace_during_read(fd: int, size: int) -> bytes:
        nonlocal replaced
        chunk = original_read(fd, size)
        if not replaced:
            os.replace(replacement, racing)
            replaced = True
        return chunk

    module.os.read = replace_during_read
    try:
        try:
            module.load_object_bytes(racing, "racing object")
        except module.IsolationError:
            pass
        else:
            raise VerificationError("session object replacement race was accepted")
    finally:
        module.os.read = original_read


def remove_worktree(repository: pathlib.Path, worktree: pathlib.Path) -> None:
    if worktree.exists():
        checked(
            ["git", "worktree", "remove", "--force", str(worktree)],
            repository,
            f"remove worktree {worktree}",
        )
    checked(["git", "worktree", "prune"], repository, "prune worktrees")


def runner(
    command: str,
    arguments: list[str],
    cwd: pathlib.Path,
) -> subprocess.CompletedProcess[str]:
    return run([sys.executable, str(RUNNER), command, *arguments], cwd)


def expect_failed(
    result: subprocess.CompletedProcess[str],
    label: str,
) -> dict[str, Any]:
    require(result.returncode != 0, f"{label} unexpectedly succeeded")
    require(not result.stdout.strip(), f"{label} emitted a successful stdout artifact")
    try:
        error = json.loads(result.stderr)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"{label} did not emit actionable JSON: {result.stderr}") from exc
    require(
        error.get("status") == "FAILED"
        and isinstance(error.get("why"), str)
        and error["why"]
        and isinstance(error.get("fix"), str)
        and error["fix"],
        f"{label} failure is not actionable",
    )
    return error


def assert_failed_prepare(
    repository: pathlib.Path,
    packet: pathlib.Path,
    target: pathlib.Path,
    label: str,
) -> None:
    result = runner(
        "prepare",
        [
            "--root",
            str(repository),
            "--packet",
            str(packet),
            "--worktree",
            str(target),
        ],
        repository,
    )
    expect_failed(result, label)
    require(
        not os.path.lexists(target),
        f"{label} left a failed worktree target behind",
    )
    listing = git(repository, "worktree", "list", "--porcelain")
    require(str(target) not in listing, f"{label} left a Git worktree registration behind")


def create_repository(root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, str]:
    repository = root / "main"
    repository.mkdir()
    checked(["git", "init", "-q"], repository, "git init")
    git(repository, "config", "user.email", "fixture@example.invalid")
    git(repository, "config", "user.name", "ITD Fixture")
    (repository / "tracked.txt").write_text("base\n", encoding="utf-8")
    (repository / "other.txt").write_text("other\n", encoding="utf-8")
    git(repository, "add", "tracked.txt", "other.txt")
    git(repository, "commit", "-qm", "base")
    state_path = repository / ".itd-memory" / "STATE.json"
    state_path.parent.mkdir()
    write_json(
        state_path,
        {
            "version": 1,
            "currentUnit": {
                "id": "HDX-008",
                "status": "in_progress",
                "riskTier": "high",
            },
            "wip": 1,
        },
    )
    return repository, state_path, git(repository, "rev-parse", "HEAD")


def create_packet(
    repository: pathlib.Path,
    output: pathlib.Path,
) -> dict[str, Any]:
    created = runner(
        "packet",
        [
            "--root",
            str(repository),
            "--unit-id",
            "HDX-008",
            "--allow",
            "tracked.txt",
            "--resource",
            "database",
            "--resource",
            "cache",
            "--maker-session",
            "a" * 32,
            "--output",
            str(output),
        ],
        repository,
    )
    require(
        created.returncode == 0,
        f"packet command failed: {(created.stdout + created.stderr).strip()}",
    )
    result = json.loads(created.stdout)
    packet = read_json(output)
    require(
        set(packet)
        == {
            "version",
            "kind",
            "unitId",
            "baseCommit",
            "allowedPaths",
            "mutableResources",
            "sharedMutableResources",
            "parentState",
            "makerSession",
        },
        "packet command did not create the closed v1 packet shape",
    )
    require(
        result.get("packetSha256") == sha256(output)
        and packet["makerSession"] == "a" * 32
        and packet["parentState"]["sha256"]
        == sha256(repository / ".itd-memory" / "STATE.json")
        and read_only(output),
        "packet is not hash-bound and read-only",
    )
    return packet


def verify_positive_cycle(
    root: pathlib.Path,
    repository: pathlib.Path,
    state_path: pathlib.Path,
    packet_path: pathlib.Path,
    base: str,
) -> pathlib.Path:
    worktree = root / "isolated"
    state_before = state_path.read_bytes()
    prepared = runner(
        "prepare",
        [
            "--root",
            str(repository),
            "--packet",
            str(packet_path),
            "--worktree",
            str(worktree),
        ],
        repository,
    )
    require(
        prepared.returncode == 0,
        f"prepare failed: {(prepared.stdout + prepared.stderr).strip()}",
    )
    session = json.loads(prepared.stdout)
    session_path = worktree / ".itd-session" / "session.json"
    packet_artifact = worktree / ".itd-session" / "unit-packet.json"
    state_artifact = worktree / ".itd-session" / "parent-state-snapshot.json"
    require(read_json(session_path) == session, "stdout/session artifact drift")
    require(state_path.read_bytes() == state_before, "prepare mutated canonical parent state")
    require(
        git(worktree, "rev-parse", "HEAD") == base
        and git(repository, "rev-parse", "HEAD") == base
        and git_path(worktree, "rev-parse", "--git-common-dir")
        == git_path(repository, "rev-parse", "--git-common-dir"),
        "worktree is not detached from the exact base in the same repository",
    )
    require(
        session.get("stateOwner") == "parent"
        and session.get("sharedMutableFallbacks") == 0
        and session.get("completionEvidence") is False
        and session.get("externalAdoptionEvidence") is False
        and session.get("fixtureCompatibility") is False
        and session.get("syntheticParentState") is False,
        "session weakened parent ownership or evidence boundaries",
    )
    require(
        session.get("packetSha256") == sha256(packet_artifact)
        and packet_artifact.read_bytes() == packet_path.read_bytes()
        and session.get("parentStateSha256") == sha256(state_artifact)
        and state_artifact.read_bytes() == state_before,
        "session artifacts are not exact hash-bound copies",
    )
    require(
        all(read_only(path) for path in (packet_artifact, state_artifact, session_path)),
        "session artifacts are not regular read-only files",
    )
    session_id = session.get("sessionId")
    require(
        isinstance(session_id, str)
        and len(session_id) == 32
        and all(character in "0123456789abcdef" for character in session_id),
        "session id is not 32 lowercase hex",
    )
    require(
        session_id == read_json(packet_path).get("makerSession")
        and session.get("makerSession") == session_id,
        "prepare did not preserve the hash-bound maker session identity",
    )
    resources = ["database", "cache"]
    namespaces = session.get("mutableNamespaces")
    require(
        isinstance(namespaces, dict) and set(namespaces) == set(resources),
        "namespace resources are not exact",
    )
    for resource in resources:
        require(
            namespaces[resource]
            == {
                "resource": resource,
                "sessionId": session_id,
                "id": f"{resource}:{session_id}",
                "exclusive": True,
                "shared": False,
            },
            f"namespace identity drifted for {resource}",
        )
        require(
            (worktree / ".itd-session" / "namespaces" / resource).is_dir(),
            f"namespace directory is missing for {resource}",
        )
    require(
        session.get("namespaceManifestSha256")
        == hashlib.sha256(canonical(namespaces).encode("utf-8")).hexdigest(),
        "namespace manifest is not hash-bound",
    )

    (worktree / "tracked.txt").write_text("candidate\n", encoding="utf-8")
    git(worktree, "add", "tracked.txt")
    expected_tree = git(worktree, "write-tree")
    alternate_index = root / "alternate.index"
    previous_index = os.environ.get("GIT_INDEX_FILE")
    os.environ["GIT_INDEX_FILE"] = str(alternate_index)
    try:
        git(worktree, "read-tree", base)
        finalized = runner(
            "finalize",
            ["--root", str(worktree), "--session", str(session_path)],
            worktree,
        )
    finally:
        if previous_index is None:
            os.environ.pop("GIT_INDEX_FILE", None)
        else:
            os.environ["GIT_INDEX_FILE"] = previous_index
    require(
        finalized.returncode == 0,
        f"finalize failed: {(finalized.stdout + finalized.stderr).strip()}",
    )
    final_session = json.loads(finalized.stdout)
    require(
        final_session.get("candidateTree") == expected_tree
        and read_json(session_path) == final_session
        and final_session.get("finalizedAt")
        and read_only(session_path),
        "finalize did not atomically bind the staged candidate tree",
    )
    return worktree


def verify_legacy_packet_denial(
    root: pathlib.Path,
    repository: pathlib.Path,
    base: str,
) -> None:
    lookalike = {
        "unitId": "HDX-FIXTURE",
        "baseCommit": base,
        "allowedPaths": ["tracked.txt"],
        "sharedMutableResources": [],
    }
    lookalike_path = root / "legacy-lookalike.json"
    write_json(lookalike_path, lookalike)
    assert_failed_prepare(
        repository,
        lookalike_path,
        root / "legacy-denied-with-canonical-state",
        "legacy packet outside exact regression fixture",
    )

    fixture = root / "fixture-main"
    fixture.mkdir()
    checked(["git", "init", "-q"], fixture, "fixture git init")
    git(fixture, "config", "user.email", "fixture@example.invalid")
    git(fixture, "config", "user.name", "ITD Fixture")
    (fixture / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(fixture, "add", "tracked.txt")
    git(fixture, "commit", "-qm", "base")
    fixture_base = git(fixture, "rev-parse", "HEAD")
    packet = {
        "unitId": "HDX-FIXTURE",
        "baseCommit": fixture_base,
        "allowedPaths": ["tracked.txt"],
        "sharedMutableResources": [],
    }
    packet_path = root / "legacy-packet.json"
    write_json(packet_path, packet)
    assert_failed_prepare(
        fixture,
        packet_path,
        root / "legacy-denied-direct-cli",
        "direct exact-fixture lookalike",
    )


def verify_prepare_refutations(
    root: pathlib.Path,
    repository: pathlib.Path,
    state_path: pathlib.Path,
    packet: dict[str, Any],
) -> None:
    cases: list[tuple[str, dict[str, Any]]] = []
    unknown = dict(packet)
    unknown["undeclared"] = True
    cases.append(("unknown-field", unknown))
    shared = dict(packet)
    shared["sharedMutableResources"] = ["database:shared"]
    cases.append(("shared-resource", shared))
    stale = json.loads(json.dumps(packet))
    stale["parentState"]["sha256"] = "0" * 64
    cases.append(("stale-state", stale))
    invalid_base = dict(packet)
    invalid_base["baseCommit"] = "0" * 40
    cases.append(("invalid-base", invalid_base))
    traversal = dict(packet)
    traversal["allowedPaths"] = ["../escape"]
    cases.append(("traversal", traversal))
    absolute = dict(packet)
    absolute["allowedPaths"] = ["/absolute"]
    cases.append(("absolute", absolute))
    injection = dict(packet)
    injection["allowedPaths"] = ["tracked.txt;touch SHOULD_NOT_EXIST"]
    cases.append(("injection", injection))
    duplicate_resource = dict(packet)
    duplicate_resource["mutableResources"] = ["database", "database"]
    cases.append(("duplicate-resource", duplicate_resource))
    reserved_resource = dict(packet)
    reserved_resource["mutableResources"] = ["database:shared"]
    cases.append(("invalid-resource", reserved_resource))
    malformed_maker = dict(packet)
    malformed_maker["makerSession"] = "not-a-session"
    cases.append(("malformed-maker-session", malformed_maker))

    for index, (label, value) in enumerate(cases):
        path = root / f"bad-{index}.json"
        write_json(path, value)
        assert_failed_prepare(
            repository,
            path,
            root / f"denied-{index}",
            label,
        )
    require(
        not (repository / "SHOULD_NOT_EXIST").exists()
        and not (root / "SHOULD_NOT_EXIST").exists(),
        "packet text was interpreted by a shell",
    )

    existing = root / "existing"
    existing.mkdir()
    existing_result = runner(
        "prepare",
        [
            "--root",
            str(repository),
            "--packet",
            str(root / "packet.json"),
            "--worktree",
            str(existing),
        ],
        repository,
    )
    expect_failed(existing_result, "existing target")
    require(existing.is_dir(), "existing target was destructively removed")

    packet_link = root / "packet-link.json"
    try:
        packet_link.symlink_to(root / "packet.json")
    except OSError:
        packet_link = pathlib.Path()
    if packet_link:
        assert_failed_prepare(
            repository,
            packet_link,
            root / "denied-packet-link",
            "packet symlink",
        )

    real_state = root / "state-real.json"
    shutil.copyfile(state_path, real_state)
    state_bytes = state_path.read_bytes()
    try:
        state_path.unlink()
        state_path.symlink_to(real_state)
        symlink_packet = json.loads(json.dumps(packet))
        symlink_packet["parentState"]["sha256"] = hashlib.sha256(state_bytes).hexdigest()
        symlink_packet_path = root / "state-link-packet.json"
        write_json(symlink_packet_path, symlink_packet)
        assert_failed_prepare(
            repository,
            symlink_packet_path,
            root / "denied-state-link",
            "parent state symlink",
        )
    finally:
        state_path.unlink(missing_ok=True)
        state_path.write_bytes(state_bytes)

    symlink_parent = root / "worktree-parent-link"
    real_parent = root / "real-parent"
    real_parent.mkdir()
    try:
        symlink_parent.symlink_to(real_parent, target_is_directory=True)
    except OSError:
        symlink_parent = pathlib.Path()
    if symlink_parent:
        assert_failed_prepare(
            repository,
            root / "packet.json",
            symlink_parent / "denied",
            "worktree parent symlink",
        )


def verify_post_create_cleanup(
    root: pathlib.Path,
    repository: pathlib.Path,
    state_path: pathlib.Path,
    packet: dict[str, Any],
) -> None:
    conflict_dir = repository / ".itd-session"
    conflict_dir.mkdir()
    (conflict_dir / "tracked-blocker.txt").write_text("block\n", encoding="utf-8")
    git(repository, "add", ".itd-session/tracked-blocker.txt")
    git(repository, "commit", "-qm", "tracked session-dir collision")
    collision = json.loads(json.dumps(packet))
    collision["baseCommit"] = git(repository, "rev-parse", "HEAD")
    collision["parentState"]["sha256"] = sha256(state_path)
    collision_path = root / "collision.json"
    write_json(collision_path, collision)
    assert_failed_prepare(
        repository,
        collision_path,
        root / "denied-post-create",
        "post-create artifact collision",
    )


def verify_finalize_refutations(
    root: pathlib.Path,
    repository: pathlib.Path,
    packet_path: pathlib.Path,
) -> None:
    out_of_scope = root / "out-of-scope"
    prepared = runner(
        "prepare",
        [
            "--root",
            str(repository),
            "--packet",
            str(packet_path),
            "--worktree",
            str(out_of_scope),
        ],
        repository,
    )
    require(prepared.returncode == 0, "cannot prepare out-of-scope finalize fixture")
    (out_of_scope / "other.txt").write_text("changed\n", encoding="utf-8")
    git(out_of_scope, "add", "other.txt")
    denied = runner("finalize", ["--root", str(out_of_scope)], out_of_scope)
    expect_failed(denied, "out-of-scope finalize")
    require(
        read_json(out_of_scope / ".itd-session" / "session.json").get("finalizedAt")
        is None,
        "failed finalize mutated the durable session artifact",
    )
    remove_worktree(repository, out_of_scope)

    maker_tampered = root / "maker-tampered"
    prepared = runner(
        "prepare",
        [
            "--root",
            str(repository),
            "--packet",
            str(packet_path),
            "--worktree",
            str(maker_tampered),
        ],
        repository,
    )
    require(prepared.returncode == 0, "cannot prepare maker-session tamper fixture")
    session_path = maker_tampered / ".itd-session" / "session.json"
    session_path.chmod(0o644)
    session = read_json(session_path)
    session["makerSession"] = "b" * 32
    write_json(session_path, session)
    session_path.chmod(0o444)
    denied = runner("finalize", ["--root", str(maker_tampered)], maker_tampered)
    expect_failed(denied, "tampered maker session finalize")
    remove_worktree(repository, maker_tampered)

    tampered = root / "tampered"
    prepared = runner(
        "prepare",
        [
            "--root",
            str(repository),
            "--packet",
            str(packet_path),
            "--worktree",
            str(tampered),
        ],
        repository,
    )
    require(prepared.returncode == 0, "cannot prepare tamper fixture")
    packet_artifact = tampered / ".itd-session" / "unit-packet.json"
    packet_artifact.chmod(0o644)
    packet_artifact.write_text("{}\n", encoding="utf-8")
    packet_artifact.chmod(0o444)
    denied = runner("finalize", ["--root", str(tampered)], tampered)
    expect_failed(denied, "tampered packet finalize")
    external = runner(
        "finalize",
        ["--root", str(tampered), "--session", str(packet_path)],
        tampered,
    )
    expect_failed(external, "external session artifact")
    remove_worktree(repository, tampered)


def verify() -> dict[str, Any]:
    require(RUNNER.is_file(), "fresh-session runner is missing")
    contract = read_json(CONTRACT)
    session_properties = contract.get("sessionSchema", {}).get("properties", {})
    require(
        "fixtureCompatibility" not in contract
        and session_properties.get("fixtureCompatibility") == {"const": False}
        and session_properties.get("syntheticParentState") == {"const": False},
        "production contract still permits legacy or synthetic fixture sessions",
    )
    with tempfile.TemporaryDirectory(prefix="itd-fresh-session-") as raw:
        root = pathlib.Path(raw)
        verify_bounded_object_reader(root)
        repository, state_path, base = create_repository(root)
        packet_path = root / "packet.json"
        packet = create_packet(repository, packet_path)
        positive = verify_positive_cycle(
            root,
            repository,
            state_path,
            packet_path,
            base,
        )
        verify_legacy_packet_denial(root, repository, base)
        verify_prepare_refutations(root, repository, state_path, packet)
        remove_worktree(repository, positive)
        verify_finalize_refutations(root, repository, packet_path)
        verify_post_create_cleanup(root, repository, state_path, packet)
        require(
            state_path.is_file()
            and read_json(state_path)["currentUnit"]["id"] == "HDX-008",
            "adversarial checks damaged canonical parent state",
        )
    return {
        "status": "PASSED",
        "positiveCycles": 1,
        "prepareRefutations": 16,
        "finalizeRefutations": 4,
        "postCreateCleanup": "PASSED",
        "boundedObjectReader": "PASSED",
        "sharedMutableFallbacks": 0,
    }


def main() -> int:
    try:
        result = verify()
    except VerificationError as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "why": str(exc),
                    "fix": "Repair the fail-closed worktree kit and rerun this verifier.",
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
