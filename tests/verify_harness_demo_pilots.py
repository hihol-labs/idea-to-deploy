#!/usr/bin/env python3
"""Fail-closed verifier for serial real-project Harness Demo pilot episodes."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "harness-demo-pilots" / "INDEX.json"
LOOP = ROOT / "skills" / "_shared" / "itd_verification_loop.py"


class PilotError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PilotError(message)


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing or linked JSON: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PilotError(f"invalid JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )


def git(cwd: Path, *args: str) -> str:
    result = run(["git", *args], cwd)
    require(result.returncode == 0, f"git {' '.join(args)} failed at {cwd}: {result.stderr}")
    return result.stdout.strip()


def inside(root: Path, raw: str, label: str) -> Path:
    candidate = Path(raw)
    candidate = candidate if candidate.is_absolute() else root / candidate
    resolved = candidate.resolve()
    require(resolved.is_relative_to(root), f"{label} escapes worktree: {resolved}")
    require(resolved.is_file() and not resolved.is_symlink(), f"{label} is missing/linked")
    return resolved


def dependency(worktree: Path, adjudication: dict[str, Any],
               kind: str) -> tuple[Path, dict[str, Any]]:
    entry = (adjudication.get("dependencies") or {}).get(kind) or {}
    path = inside(worktree, str(entry.get("path") or ""), f"{kind} receipt")
    require(entry.get("sha256") == sha256(path), f"{kind} receipt hash mismatch")
    return path, load_json(path)


def validate_namespaces(packet: dict[str, Any], session: dict[str, Any]) -> None:
    resources = packet.get("mutableResources")
    namespaces = session.get("mutableNamespaces")
    session_id = session.get("sessionId")
    require(isinstance(resources, list) and resources, "mutableResources must be non-empty")
    require(isinstance(namespaces, dict) and set(namespaces) == set(resources),
            "mutable namespace keys must exactly match packet resources")
    for resource in resources:
        row = namespaces.get(resource) or {}
        require(row == {
            "exclusive": True,
            "id": f"{resource}:{session_id}",
            "resource": resource,
            "sessionId": session_id,
            "shared": False,
        }, f"invalid exclusive namespace for {resource}")
    manifest = hashlib.sha256(json.dumps(
        namespaces, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    require(session.get("namespaceManifestSha256") == manifest,
            "namespace manifest hash mismatch")


def validate_episode(row: dict[str, Any], expected_episode: str | None) -> tuple[Path, Path]:
    required = {
        "episode", "status", "externalAdoptionEvidence", "unitId", "sessionId",
        "repository", "projectRoot", "worktreeRoot", "packet", "packetSha256",
        "sessionArtifact", "sessionArtifactSha256", "parentStateSnapshot",
        "parentStateSnapshotSha256", "adjudicationReceipt", "riskTier",
        "baseCommit", "candidateTree", "allowedPaths",
    }
    require(required <= set(row), f"pilot row missing fields: {sorted(required - set(row))}")
    if expected_episode is not None:
        require(row["episode"] == expected_episode, "selected episode label mismatch")
    require(row["status"] == "passed", "pilot status must be passed")
    require(row["externalAdoptionEvidence"] is False,
            "internal pilot cannot claim external adoption")
    require(row["riskTier"] in {"medium", "high"}, "pilot risk tier is invalid")

    project = Path(row["projectRoot"]).resolve()
    require(project == Path(git(project, "rev-parse", "--show-toplevel")).resolve(),
            "projectRoot must be the canonical Git top-level")
    remote = git(project, "remote", "get-url", "origin")
    require(remote.rstrip("/") == str(row["repository"]).rstrip("/"),
            "pilot repository remote mismatch")
    common_raw = Path(git(project, "rev-parse", "--git-common-dir"))
    common = (common_raw if common_raw.is_absolute() else project / common_raw).resolve()

    worktree = Path(row["worktreeRoot"]).resolve()
    require(worktree != project
            and worktree == Path(git(worktree, "rev-parse", "--show-toplevel")).resolve(),
            "worktreeRoot must be a distinct canonical linked worktree")
    worktree_common_raw = Path(git(worktree, "rev-parse", "--git-common-dir"))
    worktree_common = (
        worktree_common_raw if worktree_common_raw.is_absolute()
        else worktree / worktree_common_raw
    ).resolve()
    require(worktree_common == common, "worktree does not belong to declared project")

    packet_path = inside(worktree, row["packet"], "packet")
    session_path = inside(worktree, row["sessionArtifact"], "session artifact")
    state_path = inside(worktree, row["parentStateSnapshot"], "parent state snapshot")
    packet, session, state = map(load_json, (packet_path, session_path, state_path))
    packet_hash, session_hash, state_hash = map(sha256, (packet_path, session_path, state_path))
    require(row["packetSha256"] == packet_hash, "packet hash mismatch")
    require(row["sessionArtifactSha256"] == session_hash, "session hash mismatch")
    require(row["parentStateSnapshotSha256"] == state_hash, "parent state hash mismatch")
    require(packet.get("unitId") == row["unitId"]
            and packet.get("baseCommit") == row["baseCommit"]
            and packet.get("allowedPaths") == row["allowedPaths"]
            and packet.get("sharedMutableResources") == []
            and packet.get("makerSession") in {None, row["sessionId"]}
            and (packet.get("parentState") or {}).get("sha256") == state_hash,
            "packet/index identity is inconsistent")
    require(session.get("unitId") == row["unitId"]
            and session.get("sessionId") == row["sessionId"]
            and session.get("baseCommit") == row["baseCommit"]
            and session.get("candidateTree") == row["candidateTree"]
            and session.get("packetSha256") == packet_hash
            and session.get("parentStateSha256") == state_hash
            and session.get("stateOwner") == "parent"
            and session.get("sharedMutableFallbacks") == 0
            and session.get("externalAdoptionEvidence") is False
            and session.get("completionEvidence") is False
            and session.get("fixtureCompatibility") is False
            and session.get("syntheticParentState") is False,
            "session/index isolation identity is inconsistent")
    require((state.get("currentUnit") or {}).get("id") == row["unitId"]
            and (state.get("currentUnit") or {}).get("status") == "in_progress",
            "parent state snapshot must bind the in-progress pilot unit")
    require(Path(session.get("worktreeRoot") or "").resolve() == worktree,
            "session worktreeRoot mismatch")
    git_dir_raw = Path(git(worktree, "rev-parse", "--git-dir"))
    git_dir = (git_dir_raw if git_dir_raw.is_absolute() else worktree / git_dir_raw).resolve()
    require(Path(session.get("worktreeGitDir") or "").resolve() == git_dir,
            "session worktreeGitDir mismatch")
    validate_namespaces(packet, session)

    receipt_path = inside(worktree, row["adjudicationReceipt"], "adjudication receipt")
    checked = run([
        sys.executable, str(LOOP), "check", "--root", str(worktree),
        "--unit-id", row["unitId"], "--risk-tier", row["riskTier"],
        "--receipt", str(receipt_path),
    ], ROOT)
    require(checked.returncode == 0,
            f"adjudication check failed: {checked.stdout}{checked.stderr}")
    adjudication = load_json(receipt_path)
    require(adjudication.get("outcome") == "PASSED", "adjudication is not PASSED")
    _, machine = dependency(worktree, adjudication, "machine")
    declared = {
        item.get("path"): item.get("sha256")
        for item in (machine.get("declaredInputs") or [])
        if isinstance(item, dict)
    }
    require(declared.get(packet_path.relative_to(worktree).as_posix()) == packet_hash
            and declared.get(session_path.relative_to(worktree).as_posix()) == session_hash
            and declared.get(state_path.relative_to(worktree).as_posix()) == state_hash,
            "machine receipt does not bind all isolation artifacts")
    candidate = machine.get("candidate") or {}
    require(candidate.get("baseCommit") == row["baseCommit"]
            and candidate.get("reviewedTree") == row["candidateTree"],
            "machine candidate does not match index")
    _, checker = dependency(worktree, adjudication, "checker")
    maker = (checker.get("provenance") or {}).get("maker") or {}
    reviewer = (checker.get("provenance") or {}).get("checker") or {}
    require(checker.get("unitId") == row["unitId"]
            and checker.get("verdict") == "PASSED"
            and Path((checker.get("candidate") or {}).get("repository") or "").resolve()
            == worktree
            and maker.get("session") == row["sessionId"]
            and session.get("makerSession") == row["sessionId"]
            and reviewer.get("session")
            and reviewer.get("session") != row["sessionId"],
            "checker provenance is not independent and worktree-bound")
    return project, common


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", choices=("A", "B", "C"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    evidence = load_json(INDEX)
    require(evidence.get("version") == 1, "pilot index version must be 1")
    episodes = evidence.get("episodes")
    require(isinstance(episodes, list), "episodes must be a list")
    selected = [row for row in episodes
                if isinstance(row, dict)
                and (args.episode is None or row.get("episode") == args.episode)]
    require(len(selected) == (1 if args.episode else 3),
            "selected episode count is incomplete or duplicated")
    roots: list[Path] = []
    common_dirs: list[Path] = []
    for row in selected:
        root, common = validate_episode(row, args.episode)
        roots.append(root)
        common_dirs.append(common)
    if args.episode is None:
        require(len({row["episode"] for row in selected}) == 3,
                "full pilot set must contain A, B, and C")
        require(len({row["unitId"] for row in selected}) == 3
                and len({row["sessionId"] for row in selected}) == 3
                and len(set(roots)) == 3 and len(set(common_dirs)) == 3,
                "full pilot set must use three distinct projects, units, and sessions")
    mutation_guards = 0
    if args.self_test:
        require(args.episode is not None,
                "--self-test requires one selected --episode")
        mutations = (
            ("externalAdoptionEvidence", True),
            ("packetSha256", "0" * 64),
            ("sessionId", "forged-session"),
            ("adjudicationReceipt", ".itd-memory/missing-adjudication.json"),
            ("candidateTree", "0" * 40),
            ("allowedPaths", ["scripts/adoption_check.py", "../escape"]),
        )
        for field, value in mutations:
            forged = copy.deepcopy(selected[0])
            forged[field] = value
            try:
                validate_episode(forged, args.episode)
            except PilotError:
                mutation_guards += 1
            else:
                raise PilotError(f"mutation guard failed for {field}")
    print(json.dumps({
        "status": "PASSED",
        "episodes": [row["episode"] for row in selected],
        "externalAdoptionEvidence": False,
        "mutationGuards": mutation_guards,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PilotError as exc:
        print(json.dumps({"status": "FAILED", "why": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
