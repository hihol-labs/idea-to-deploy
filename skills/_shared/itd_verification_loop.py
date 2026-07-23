#!/usr/bin/env python3
"""Proof-carrying, risk-tiered Verification Loop for Idea to Deploy.

The model is not a trust root.  This producer executes machine oracles, binds
their output to the exact staged candidate, turns a durable reviewer report
into a provenance-bearing checker receipt, and deterministically adjudicates
the two.  Receipt files are diagnostic until an adjudication receipt validates
against the *current* candidate.

No arguments is a quiet no-op so global installations remain safe.  The module
is importable by /goal and /review cache consumers.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import importlib.util
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


INSTALL_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = Path(__file__).with_name("VERIFICATION_LOOP_POLICY.json")
REVIEW_CACHE_PATH = INSTALL_ROOT / "skills" / "review" / "scripts" / "itd_review_cache.py"
RECEIPT_VERSION = 1
ALLOWED_VERDICTS = {"PASSED", "PASSED_WITH_WARNINGS", "BLOCKED", "UNVERIFIED", "FAILED"}
RISK_TIERS = {"low", "medium", "high", "unknown"}
CHECKER_MODES = {"targeted", "full"}
FENCED_JSON_RE = re.compile(r"```json\s*(.*?)```", re.I | re.S)
CHECKOUT_PROBE_TIMEOUT_SECONDS = 60
MACHINE_RUN_FIELDS = frozenset({
    "id", "command", "commandSha256", "shell", "startedAt", "completedAt",
    "timeoutSeconds", "executionMode", "executedTree", "exitCode",
    "stdoutSha256", "stderrSha256",
})


class LoopError(ValueError):
    def __init__(self, why: str, fix: str) -> None:
        super().__init__(why)
        self.why = why
        self.fix = fix


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.is_file() else "missing"


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise LoopError(f"{label} is unreadable: {path}: {exc}",
                        f"Repair or regenerate {path} through the Verification Loop producer.") from exc
    if not isinstance(value, dict):
        raise LoopError(f"{label} is not a JSON object: {path}",
                        "Use the machine-readable receipt schema, not prose.")
    return value


def load_policy() -> tuple[dict[str, Any], str]:
    policy = read_json(POLICY_PATH, "Verification Loop policy")
    routes = policy.get("riskRoutes") or {}
    invariants = policy.get("invariants") or {}
    expected = {
        "low": ("machine_only", False),
        "medium": ("targeted", True),
        "high": ("full", True),
        "unknown": ("full", True),
    }
    malformed = (policy.get("version") != 1
                 or policy.get("id") != "verification-loop-v1"
                 or policy.get("defaultEnabled") is not True
                 or policy.get("acceptedVerdicts") != ["PASSED"]
                 or policy.get("candidateHashAlgorithm") != "sha256"
                 or type(policy.get("maxReceiptAgeSeconds")) is not int
                 or policy.get("maxReceiptAgeSeconds", 0) <= 0
                 or type(policy.get("maxAttemptsPerCandidate")) is not int
                 or not 1 <= policy.get("maxAttemptsPerCandidate", 0) <= 5)
    for risk, (mode, required) in expected.items():
        route = routes.get(risk) or {}
        malformed = malformed or route.get("checkerMode") != mode \
            or route.get("checkerRequired") is not required
    threat = policy.get("threatModel") or {}
    malformed = malformed or (
        threat.get("trustRoot") != "honest-host-orchestrator"
        or threat.get("externalClaimsWithoutHostEvidence") != "UNVERIFIED"
        or "malicious-same-os-principal" not in (threat.get("nonGuarantees") or [])
        or "cryptographic-model-identity-attestation" not in
        (threat.get("nonGuarantees") or []))
    required_invariants = {
        "makerNarrationMayMintAcceptedVerdict": False,
        "harnessExecutesVerificationCommands": True,
        "machineExecutionMode": "isolated-staged-tree",
        "machineOutputRetention": "hashes-only",
        "undeclaredIgnoredInputsEnterMachineOracle": False,
        "immutableReceiptPublicationRequired": True,
        "exactCandidateBindingRequired": True,
        "candidateChangeInvalidatesReceipts": True,
        "plainTextCheckerEvidenceAccepted": False,
        "majorityVoteIsEvidence": False,
        "missingRequiredChecker": "UNVERIFIED",
        "externalOutcomeClaimsRequireExternalEvidence": True,
        "samePrincipalByzantineResistanceClaimed": False,
    }
    malformed = malformed or any(invariants.get(k) != v
                                 for k, v in required_invariants.items())
    if malformed:
        raise LoopError("Verification Loop policy is malformed or weakened",
                        "Restore the frozen risk routes and trust invariants before accepting receipts.")
    return policy, sha256_file(POLICY_PATH)


def _review_cache_module():
    spec = importlib.util.spec_from_file_location("itd_loop_review_cache", REVIEW_CACHE_PATH)
    if spec is None or spec.loader is None:
        raise LoopError("exact-context producer cannot be loaded",
                        "Restore skills/review/scripts/itd_review_cache.py.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def repository_root(root: Path | str) -> Path:
    try:
        return Path(_review_cache_module().repository_root(root)).resolve()
    except LoopError:
        raise
    except Exception as exc:
        raise LoopError(f"repository context is unavailable: {exc}",
                        "Run the Verification Loop inside a valid Git repository.") from exc


def candidate_context(root: Path | str, risk_tier: str) -> dict[str, str]:
    risk = str(risk_tier or "unknown").lower()
    if risk not in RISK_TIERS:
        raise LoopError(f"invalid risk tier: {risk!r}",
                        "Use low, medium, high or unknown.")
    try:
        return dict(_review_cache_module().build_context(root, risk))
    except Exception as exc:
        if isinstance(exc, LoopError):
            raise
        raise LoopError(f"exact candidate could not be computed: {exc}",
                        "Repair Git/index/contracts and retry on one immutable candidate.") from exc


def candidate_digest(context: dict[str, Any]) -> str:
    return "sha256:" + sha256_bytes(canonical(context))


def assert_checkout_matches_candidate(repo: Path, context: dict[str, Any]) -> str:
    """Prove the control-plane checkout still has the index-derived candidate.

    The review key is the staged tree. Unstaged tracked or non-ignored inputs
    make that key ambiguous and fail closed. Ignored project files are allowed
    in the control-plane checkout because the machine oracle never executes
    there: ``isolated_candidate`` materializes only the staged Git tree.
    """
    dirty = subprocess.run(
        ["git", "diff", "--quiet", "--"], cwd=str(repo),
        timeout=CHECKOUT_PROBE_TIMEOUT_SECONDS)
    if dirty.returncode not in (0, 1):
        raise LoopError("working-tree comparison failed",
                        "Repair Git and retry against one immutable candidate.")
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=str(repo), capture_output=True, timeout=CHECKOUT_PROBE_TIMEOUT_SECONDS)
    if untracked.returncode != 0:
        raise LoopError("untracked-file comparison failed",
                        "Repair Git and retry against one immutable candidate.")
    if dirty.returncode == 1 or bool(untracked.stdout):
        raise LoopError(
            "working tree differs from the staged candidate",
            "Stage the intended files or remove unstaged/untracked inputs before verification.",
        )
    executed_tree = str(_review_cache_module().git(repo, "write-tree")).strip()
    if executed_tree != context.get("reviewedTree"):
        raise LoopError("executed tree does not match reviewedTree",
                        "Freeze and rerun the exact staged candidate.")
    return executed_tree


@contextlib.contextmanager
def isolated_candidate(repo: Path, context: dict[str, Any]):
    """Materialize only the staged tree in a disposable local Git checkout.

    ``--shared`` is intentional: an index tree is normally unreachable from
    HEAD, so the disposable repository needs read-only access to the source
    object database. No source working-tree file (ignored or otherwise) is
    copied. The temporary checkout is local even when ``repo`` is a WSL UNC
    path, which also gives native Windows tools a valid current directory.
    """
    with tempfile.TemporaryDirectory(prefix="itd-verification-candidate-") as td:
        candidate = Path(td) / "candidate"
        clone = subprocess.run(
            ["git", "clone", "--shared", "--no-checkout", "--quiet",
             str(repo), str(candidate)],
            capture_output=True, timeout=CHECKOUT_PROBE_TIMEOUT_SECONDS,
        )
        if clone.returncode != 0:
            raise LoopError(
                "isolated candidate checkout could not be created",
                "Repair Git object access and retry; do not fall back to the source checkout.",
            )
        tree = str(context.get("reviewedTree") or "")
        materialized = subprocess.run(
            ["git", "-C", str(candidate), "read-tree", "--reset", "-u", tree],
            capture_output=True, timeout=CHECKOUT_PROBE_TIMEOUT_SECONDS,
        )
        if materialized.returncode != 0:
            raise LoopError(
                "staged tree could not be materialized in isolation",
                "Keep the staged Git objects available and retry the exact candidate.",
            )
        executed_tree = str(_review_cache_module().git(candidate, "write-tree")).strip()
        if executed_tree != tree:
            raise LoopError(
                "isolated checkout tree does not match reviewedTree",
                "Stop verification; repair Git materialization before retrying.",
            )
        overlays = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=str(candidate), capture_output=True,
            timeout=CHECKOUT_PROBE_TIMEOUT_SECONDS,
        )
        if overlays.returncode != 0 or overlays.stdout:
            raise LoopError(
                "isolated candidate contains an unexpected pre-oracle overlay",
                "Recreate the disposable checkout from the staged tree.",
            )
        yield candidate


def assert_isolated_candidate(candidate: Path, expected_tree: str) -> None:
    """Reject an oracle that modified tracked content or the isolated index."""
    dirty = subprocess.run(
        ["git", "diff", "--quiet", "--"], cwd=str(candidate),
        timeout=CHECKOUT_PROBE_TIMEOUT_SECONDS,
    )
    if dirty.returncode not in (0, 1):
        raise LoopError("isolated candidate comparison failed",
                        "Treat the machine result as UNVERIFIED and retry cleanly.")
    current_tree = str(_review_cache_module().git(candidate, "write-tree")).strip()
    if dirty.returncode == 1 or current_tree != expected_tree:
        raise LoopError(
            "machine oracle mutated the isolated staged candidate",
            "Repair the oracle so it leaves tracked candidate inputs unchanged.",
        )


def input_snapshot(path: Path, relative: str) -> dict[str, Any]:
    """Return a deterministic manifest for one declared non-Git oracle input."""
    if path.is_symlink():
        raise LoopError(f"declared input is a symlink: {relative}",
                        "Use a real project-local file/directory so isolation cannot escape.")
    if path.is_file():
        return {"path": relative, "kind": "file", "sha256": sha256_file(path),
                "fileCount": 1}
    if not path.is_dir():
        raise LoopError(f"declared input is not a regular file/directory: {relative}",
                        "Declare only stable project-local files or directories.")
    entries: list[dict[str, str]] = []
    for child in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        child_rel = child.relative_to(path).as_posix()
        if child.is_symlink():
            raise LoopError(f"declared input contains a symlink: {relative}/{child_rel}",
                            "Materialize symlink targets inside the declared input snapshot.")
        if child.is_dir():
            entries.append({"kind": "directory", "path": child_rel})
        elif child.is_file():
            entries.append({"kind": "file", "path": child_rel,
                            "sha256": sha256_file(child)})
        else:
            raise LoopError(f"declared input contains a special file: {relative}/{child_rel}",
                            "Use only regular files/directories as oracle inputs.")
    return {"path": relative, "kind": "directory",
            "sha256": sha256_bytes(canonical(entries)),
            "fileCount": sum(1 for entry in entries if entry["kind"] == "file")}


def declared_inputs(repo: Path, raw_inputs: list[str], policy: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve and seal explicit ignored/untracked inputs without broad overlays."""
    manifests: list[dict[str, Any]] = []
    seen: list[Path] = []
    receipt_dir = receipt_root(repo, policy)
    git_dir = (repo / ".git").resolve()
    for raw in raw_inputs:
        candidate = Path(raw)
        candidate = candidate if candidate.is_absolute() else repo / candidate
        resolved = candidate.resolve()
        try:
            relative = resolved.relative_to(repo).as_posix()
        except ValueError as exc:
            raise LoopError(f"declared input escapes the repository: {raw}",
                            "Declare a project-local input path.") from exc
        if resolved == git_dir or git_dir in resolved.parents:
            raise LoopError("the Git database cannot be a declared input",
                            "Declare only the minimal external data needed by the oracle.")
        if resolved == receipt_dir or receipt_dir in resolved.parents:
            raise LoopError("Verification Loop evidence cannot be its own machine input",
                            "Keep oracle inputs outside the receipt directory.")
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative], cwd=str(repo),
            capture_output=True, timeout=CHECKOUT_PROBE_TIMEOUT_SECONDS,
        )
        if tracked.returncode == 0:
            raise LoopError(f"declared input is already tracked in the staged tree: {relative}",
                            "Remove redundant --input; tracked candidate files are materialized automatically.")
        if any(resolved == prior or resolved in prior.parents or prior in resolved.parents for prior in seen):
            raise LoopError(f"declared inputs overlap: {relative}",
                            "Declare each external input exactly once without parent/child overlap.")
        manifests.append(input_snapshot(resolved, relative))
        seen.append(resolved)
    return sorted(manifests, key=lambda item: str(item["path"]))


def copy_declared_inputs(repo: Path, candidate: Path,
                         manifests: list[dict[str, Any]]) -> None:
    """Copy the already-sealed input snapshot into the disposable checkout."""
    for manifest in manifests:
        relative = str(manifest["path"])
        source = repo / relative
        if input_snapshot(source, relative) != manifest:
            raise LoopError(f"declared input changed before snapshot copy: {relative}",
                            "Freeze the input and retry verification.")
        destination = candidate / relative
        if destination.exists() or destination.is_symlink():
            raise LoopError(f"declared input collides with the staged tree: {relative}",
                            "Track the file or choose a non-overlapping external input.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, symlinks=False)
        else:
            shutil.copy2(source, destination)


def validate_declared_inputs(repo: Path, manifests: Any) -> None:
    if not isinstance(manifests, list):
        raise LoopError("machine declared-input manifest is malformed",
                        "Regenerate the machine receipt through the harness.")
    canonical_repo = repo.resolve()
    for manifest in manifests:
        if not isinstance(manifest, dict) or not str(manifest.get("path") or ""):
            raise LoopError("machine declared-input entry is malformed",
                            "Regenerate the machine receipt through the harness.")
        relative = str(manifest["path"])
        resolved = (canonical_repo / relative).resolve()
        try:
            resolved.relative_to(canonical_repo)
        except ValueError as exc:
            raise LoopError("machine declared input escapes the repository",
                            "Discard the malformed receipt.") from exc
        if input_snapshot(resolved, relative) != manifest:
            raise LoopError(f"declared machine input is missing or changed: {relative}",
                            "Restore/freeze the exact input or rerun machine verification.")


def verification_shell(command: str, repo: Path) -> tuple[list[str] | str, str | None, str] | None:
    """Return the native host shell transport for an explicit oracle command."""
    if os.name == "nt":
        # cmd.exe rejects a UNC current directory and silently falls back to
        # C:\Windows. Start there explicitly, then pushd maps the UNC path for
        # this short-lived process.
        native = f'pushd "{repo}" && {command}'
        start = os.environ.get("SystemRoot", r"C:\Windows")
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        # A list argv makes Python encode the inner quotes as \"; cmd.exe does
        # not treat backslash as a quote escape. Pass the exact native command
        # line string while keeping shell=False (the default).
        return (f'"{comspec}" /d /c {native}', start, comspec)
    sh = shutil.which("sh")
    return ([sh, "-c", command], str(repo), sh) if sh else None


def seal_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    value = dict(payload)
    value.pop("receiptSha256", None)
    value["receiptSha256"] = sha256_bytes(canonical(value))
    return value


def receipt_digest_valid(receipt: dict[str, Any]) -> bool:
    expected = str(receipt.get("receiptSha256") or "")
    value = dict(receipt)
    value.pop("receiptSha256", None)
    return len(expected) == 64 and expected == sha256_bytes(canonical(value))


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    """Atomically publish immutable JSON without exposing a partial final file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise LoopError(f"stale evidence transaction exists: {tmp}",
                        "Remove only the unlinked .tmp transaction after confirming its owner is gone.") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            if os.name == "nt":
                # Windows rename is atomic and refuses an existing target;
                # unlike hard links, it is supported by WSL UNC/SMB shares.
                os.rename(tmp, path)
            else:
                os.link(tmp, path)
        except FileExistsError as exc:
            raise LoopError(f"immutable evidence already exists: {path}",
                            "Use the next automatically allocated attempt; never overwrite evidence.") from exc
    except Exception:
        raise
    finally:
        tmp.unlink(missing_ok=True)


def receipt_root(repo: Path, policy: dict[str, Any]) -> Path:
    path = (repo / str(policy["receiptDirectory"])).resolve()
    try:
        path.relative_to(repo)
    except ValueError as exc:
        raise LoopError("receipt directory escapes the repository",
                        "Use the project-local .itd-memory/verification-loop directory.") from exc
    return path


def inside(path: Path, parent: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(parent.resolve())
    except ValueError as exc:
        raise LoopError(f"{label} escapes {parent}",
                        f"Place {label} under the durable Verification Loop directory.") from exc
    return resolved


def default_path(repo: Path, policy: dict[str, Any], unit_id: str,
                 kind: str, context: dict[str, Any], attempt: int | None = None,
                 identity: str | None = None) -> Path:
    digest = candidate_digest(context).split(":", 1)[1][:16]
    safe_unit = re.sub(r"[^A-Za-z0-9_.-]+", "-", unit_id).strip("-") or "unit"
    suffix = f"-a{attempt}" if attempt is not None else (f"-{identity}" if identity else "")
    return receipt_root(repo, policy) / "receipts" / digest / f"{safe_unit}-{kind}{suffix}.json"


def _attempt_directory(repo: Path, policy: dict[str, Any], context: dict[str, Any],
                       unit_id: str, risk: str) -> Path:
    digest = candidate_digest(context).split(":", 1)[1]
    safe_unit = re.sub(r"[^A-Za-z0-9_.-]+", "-", unit_id).strip("-") or "unit"
    claim_hash = sha256_bytes(f"{unit_id}\0{risk}".encode("utf-8"))[:16]
    return receipt_root(repo, policy) / "attempts" / digest / f"{safe_unit}-{risk}-{claim_hash}"


def _ledger_entry_digest_valid(entry: dict[str, Any]) -> bool:
    expected = str(entry.get("entrySha256") or "")
    value = dict(entry)
    value.pop("entrySha256", None)
    return len(expected) == 64 and expected == sha256_bytes(canonical(value))


def _read_attempt_entries(directory: Path, *, context: dict[str, Any], unit_id: str,
                          risk: str, policy_sha: str) -> list[tuple[Path, dict[str, Any]]]:
    entries: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(directory.glob("attempt-*.json")) if directory.is_dir() else []:
        match = re.fullmatch(r"attempt-([1-9][0-9]*)\.json", path.name)
        if not match:
            raise LoopError(f"attempt ledger contains an invalid entry: {path}",
                            "Preserve the append-only ledger and escalate for recovery.")
        entry = read_json(path, "attempt ledger entry")
        number = int(match.group(1))
        if (entry.get("version") != 1
                or entry.get("attempt") != number
                or entry.get("candidateDigest") != candidate_digest(context)
                or entry.get("unitId") != unit_id
                or entry.get("riskTier") != risk
                or entry.get("policySha256") != policy_sha
                or not _ledger_entry_digest_valid(entry)):
            raise LoopError(f"attempt ledger entry is invalid or belongs to another claim: {path}",
                            "Do not repair history in place; preserve evidence and escalate.")
        entries.append((path, entry))
    actual = [int(entry["attempt"]) for _, entry in entries]
    expected = list(range(1, len(entries) + 1))
    if actual != expected:
        raise LoopError(f"attempt ledger is non-contiguous: {actual}",
                        "Do not renumber or delete attempts; escalate for recovery.")
    return entries


def process_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        query_limited_information = 0x1000
        still_active = 259
        handle = ctypes.windll.kernel32.OpenProcess(query_limited_information, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == still_active
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


@contextlib.contextmanager
def reserve_attempt(repo: Path, policy: dict[str, Any], context: dict[str, Any],
                    unit_id: str, risk: str, policy_sha: str,
                    requested: int | None):
    """Serialize and monotonically allocate one durable candidate/claim attempt."""
    directory = _attempt_directory(repo, policy, context, unit_id, risk)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / ".allocate.lock"
    for acquisition in range(2):
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="ascii") as handle:
                handle.write(f"{os.getpid()}\n")
                handle.flush()
                os.fsync(handle.fileno())
            break
        except FileExistsError as exc:
            try:
                owner = int(lock.read_text(encoding="ascii").strip())
                owner_alive = process_alive(owner)
            except (OSError, ValueError):
                owner_alive = (dt.datetime.now().timestamp() - lock.stat().st_mtime) < 60
            if acquisition == 0 and not owner_alive:
                lock.unlink(missing_ok=True)
                continue
            raise LoopError("another adjudication is allocating this attempt",
                            "Wait for the current honest-host adjudication to finish, then retry.") from exc
    try:
        entries = _read_attempt_entries(
            directory, context=context, unit_id=unit_id, risk=risk, policy_sha=policy_sha)
        attempt = len(entries) + 1
        if requested is not None and requested != attempt:
            raise LoopError(
                f"non-monotonic attempt requested: {requested}; next durable attempt is {attempt}",
                "Omit --attempt and let the harness allocate the next attempt.",
            )
        if attempt > policy["maxAttemptsPerCandidate"]:
            raise LoopError("attempt budget exhausted",
                            "Stop the loop and mark RECOVERY_REQUIRED; do not add another agent vote.")
        yield attempt, directory / f"attempt-{attempt}.json"
    finally:
        lock.unlink(missing_ok=True)


def validate_attempt_entry(repo: Path, policy: dict[str, Any], context: dict[str, Any],
                           unit_id: str, risk: str, policy_sha: str, attempt: int,
                           receipt_path: Path, receipt: dict[str, Any]) -> None:
    directory = _attempt_directory(repo, policy, context, unit_id, risk)
    entries = _read_attempt_entries(
        directory, context=context, unit_id=unit_id, risk=risk, policy_sha=policy_sha)
    if attempt > len(entries):
        raise LoopError("adjudication is absent from the durable attempt ledger",
                        "Use only receipts minted by the monotonic harness adjudicator.")
    entry_path, entry = entries[attempt - 1]
    ledger_ref = receipt.get("attemptLedger") or {}
    expected_entry_rel = entry_path.relative_to(repo).as_posix()
    expected_receipt_rel = receipt_path.relative_to(repo).as_posix()
    if (ledger_ref.get("entryPath") != expected_entry_rel
            or ledger_ref.get("sequence") != attempt
            or entry.get("receiptPath") != expected_receipt_rel
            or entry.get("receiptFileSha256") != sha256_file(receipt_path)):
        raise LoopError("adjudication and append-only attempt ledger do not match",
                        "Discard copied/overwritten evidence and use the original minted receipt.")


def make_attempt_entry(repo: Path, receipt_path: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "version": 1,
        "createdAt": now_iso(),
        "candidateDigest": receipt["candidateDigest"],
        "unitId": receipt["unitId"],
        "riskTier": receipt["riskTier"],
        "policySha256": receipt["policySha256"],
        "attempt": receipt["attempt"],
        "receiptPath": receipt_path.relative_to(repo).as_posix(),
        "receiptFileSha256": sha256_file(receipt_path),
    }
    entry["entrySha256"] = sha256_bytes(canonical(entry))
    return entry


def parse_time(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except Exception as exc:
        raise LoopError(f"receipt timestamp is invalid: {value!r}",
                        "Regenerate the receipt through the harness.") from exc


def ensure_fresh(receipt: dict[str, Any], policy: dict[str, Any]) -> None:
    created = parse_time(str(receipt.get("createdAt") or ""))
    age = (dt.datetime.now(dt.timezone.utc) - created).total_seconds()
    if age < -300 or age > policy["maxReceiptAgeSeconds"]:
        raise LoopError(f"receipt is stale or future-dated ({int(age)} seconds)",
                        "Rerun verification/checker on the current candidate.")


def parse_report(text: str) -> dict[str, Any]:
    objects: list[dict[str, Any]] = []
    for match in FENCED_JSON_RE.finditer(text):
        try:
            value = json.loads(match.group(1))
        except Exception:
            continue
        if isinstance(value, dict):
            objects.append(value)
    try:
        whole = json.loads(text)
        if isinstance(whole, dict):
            objects.append(whole)
    except Exception:
        pass
    for value in reversed(objects):
        verdict = str(value.get("verdict") or "").upper()
        if verdict in ALLOWED_VERDICTS and isinstance(value.get("findings"), list):
            if "unverified" not in value:
                value["unverified"] = []
            if isinstance(value.get("unverified"), list):
                return value
    raise LoopError("checker report has no valid verdict/findings/unverified JSON block",
                    "Finish the review report with the canonical vendor-neutral verdict block.")


def relative_artifact(repo: Path, path: Path, allowed: Path, label: str) -> str:
    resolved = inside(path, allowed, label)
    if not resolved.is_file():
        raise LoopError(f"{label} is missing: {resolved}",
                        f"Persist the complete {label} before minting a receipt.")
    return resolved.relative_to(repo).as_posix()


def validate_common(receipt: dict[str, Any], *, kind: str, repo: Path,
                    risk: str, unit_id: str, policy: dict[str, Any],
                    policy_sha: str) -> None:
    if receipt.get("version") != RECEIPT_VERSION or receipt.get("kind") != kind:
        raise LoopError(f"expected {kind} receipt version {RECEIPT_VERSION}",
                        "Regenerate the receipt through itd_verification_loop.py.")
    if not receipt_digest_valid(receipt):
        raise LoopError("receipt digest is invalid", "Discard the edited/forged receipt and rerun the producer.")
    if receipt.get("policySha256") != policy_sha:
        raise LoopError("receipt policy binding is stale",
                        "Regenerate receipts after a Verification Loop policy change.")
    if str(receipt.get("unitId") or "") != unit_id:
        raise LoopError("receipt belongs to another unit", "Use receipts produced for the active unit.")
    if str(receipt.get("riskTier") or "") != risk:
        raise LoopError("receipt risk tier does not match adjudication",
                        "Recreate evidence under the current risk route.")
    current = candidate_context(repo, risk)
    assert_checkout_matches_candidate(repo, current)
    if receipt.get("candidate") != current \
            or receipt.get("candidateDigest") != candidate_digest(current):
        raise LoopError("receipt does not match the exact current candidate",
                        "Any candidate change invalidates evidence; rerun verifier/checker.")
    ensure_fresh(receipt, policy)
    producer = receipt.get("producer") or {}
    if producer.get("id") != "itd-verification-loop" or producer.get("role") == "maker":
        raise LoopError("receipt producer provenance is invalid",
                        "Only the harness verifier/checker producer may mint receipts.")
    if not re.fullmatch(r"[0-9a-f]{32}", str(receipt.get("producerRunId") or "")):
        raise LoopError("receipt producer run id is invalid",
                        "Regenerate unique immutable evidence through the harness.")
    assurance = receipt.get("assurance") or {}
    if (assurance.get("trustRoot") != "honest-host-orchestrator"
            or assurance.get("class") != "integrity-and-process"
            or assurance.get("samePrincipalByzantineResistance") is not False):
        raise LoopError("receipt assurance boundary is missing or overstated",
                        "Regenerate the receipt with the canonical honest-orchestrator threat model.")


def validate_machine(receipt: dict[str, Any], *, repo: Path, risk: str,
                     unit_id: str, policy: dict[str, Any], policy_sha: str) -> None:
    validate_common(receipt, kind="machine-verification", repo=repo, risk=risk,
                    unit_id=unit_id, policy=policy, policy_sha=policy_sha)
    runs = receipt.get("runs")
    validate_declared_inputs(repo, receipt.get("declaredInputs"))
    if not isinstance(runs, list) or not runs:
        raise LoopError("machine receipt has no command runs", "Execute at least one declared oracle command.")
    for run in runs:
        if (not isinstance(run, dict) or not str(run.get("command") or "")
                or not str(run.get("shell") or "")
                or len(str(run.get("commandSha256") or "")) != 64
                or len(str(run.get("stdoutSha256") or "")) != 64
                or len(str(run.get("stderrSha256") or "")) != 64
                or run.get("executionMode") != "isolated-staged-tree"
                or type(run.get("exitCode")) is not int):
            raise LoopError("machine command evidence is malformed", "Rerun the oracle through the harness producer.")
        unexpected_fields = set(run) - MACHINE_RUN_FIELDS
        if unexpected_fields:
            raise LoopError(
                "machine command evidence contains non-schema fields: "
                + ", ".join(sorted(unexpected_fields)),
                "Keep only the closed run schema with stdout/stderr hashes and rerun the producer.",
            )
        if run.get("executedTree") != receipt.get("candidate", {}).get("reviewedTree"):
            raise LoopError("machine command ran against a different tree",
                            "Rerun with a checkout exactly matching the staged candidate.")
        if run["commandSha256"] != sha256_bytes(str(run["command"]).encode("utf-8")):
            raise LoopError("machine command hash is invalid", "Discard the edited receipt and rerun verification.")
    expected = "PASSED" if all(run["exitCode"] == 0 for run in runs) else "FAILED"
    if receipt.get("verdict") != expected:
        raise LoopError("machine verdict contradicts command exit codes",
                        "A failing command cannot be narrated into PASSED.")


def validate_checker(receipt: dict[str, Any], *, repo: Path, risk: str,
                     unit_id: str, policy: dict[str, Any], policy_sha: str,
                     required_mode: str) -> None:
    validate_common(receipt, kind="checker", repo=repo, risk=risk,
                    unit_id=unit_id, policy=policy, policy_sha=policy_sha)
    mode = str(receipt.get("checkerMode") or "")
    if receipt.get("inspectedTree") != receipt.get("candidate", {}).get("reviewedTree"):
        raise LoopError("checker was not observed on the exact reviewed tree",
                        "Rerun the checker with a checkout identical to the staged candidate.")
    if required_mode == "full" and mode != "full":
        raise LoopError("full checker evidence is required", "Run a different-session, different-model/provider checker.")
    if required_mode == "targeted" and mode not in {"targeted", "full"}:
        raise LoopError("targeted checker evidence is required", "Run a focused checker for uncovered claims/risks.")
    provenance = receipt.get("provenance") or {}
    maker = provenance.get("maker") or {}
    checker = provenance.get("checker") or {}
    identity_fields = ("provider", "model", "session")
    if (not all(isinstance(maker.get(k), str) and maker[k].strip() for k in identity_fields)
            or not all(isinstance(checker.get(k), str) and checker[k].strip()
                       for k in identity_fields)):
        raise LoopError(
            "maker/checker identity is incomplete",
            "Record host-observed provider, model and session provenance for both roles.",
        )
    maker_identity = {key: maker[key].strip() for key in identity_fields}
    checker_identity = {key: checker[key].strip() for key in identity_fields}
    if checker_identity["session"] == maker_identity["session"]:
        raise LoopError("checker reused the maker session", "Use a fresh checker context.")
    if mode == "full" and (checker_identity["provider"] == maker_identity["provider"]
                           and checker_identity["model"] == maker_identity["model"]):
        raise LoopError("full checker is not model/provider-independent",
                        "Use a different model or provider; otherwise remain UNVERIFIED.")
    artifacts = receipt.get("artifacts") or {}
    for name in ("report", "prompt"):
        item = artifacts.get(name) or {}
        path = (repo / str(item.get("path") or "")).resolve()
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise LoopError(f"checker {name} artifact is missing or changed",
                            "Preserve the exact durable checker inputs and regenerate the receipt.")
    if receipt.get("verdict") not in policy["acceptedVerdicts"]:
        raise LoopError(f"checker verdict is {receipt.get('verdict')}, not accepted",
                        "Resolve findings and run a fresh checker; do not downgrade the verdict.")


def validate_adjudication_evidence(receipt: dict[str, Any], *, repo: Path, risk: str,
                                   unit_id: str, policy: dict[str, Any],
                                   policy_sha: str) -> None:
    dependencies = receipt.get("dependencies") or {}
    machine_ref = dependencies.get("machine") or {}
    machine_path = (repo / str(machine_ref.get("path") or "")).resolve()
    if not machine_path.is_file() or sha256_file(machine_path) != machine_ref.get("sha256"):
        raise LoopError("machine receipt dependency is missing or changed", "Rerun and re-adjudicate the current candidate.")
    machine = read_json(machine_path, "machine receipt")
    validate_machine(machine, repo=repo, risk=risk, unit_id=unit_id,
                     policy=policy, policy_sha=policy_sha)
    if machine.get("verdict") != "PASSED":
        raise LoopError("machine verification failed", "Fix the candidate and rerun the oracle.")
    route = policy["riskRoutes"][risk]
    checker_ref = dependencies.get("checker")
    if route["checkerRequired"]:
        if not isinstance(checker_ref, dict):
            raise LoopError("required checker receipt is missing", "Remain UNVERIFIED until the risk-tier checker completes.")
        checker_path = (repo / str(checker_ref.get("path") or "")).resolve()
        if not checker_path.is_file() or sha256_file(checker_path) != checker_ref.get("sha256"):
            raise LoopError("checker receipt dependency is missing or changed", "Run a fresh checker and re-adjudicate.")
        checker = read_json(checker_path, "checker receipt")
        validate_checker(checker, repo=repo, risk=risk, unit_id=unit_id,
                         policy=policy, policy_sha=policy_sha,
                         required_mode=route["checkerMode"])
    elif checker_ref is not None:
        raise LoopError("low-risk machine-only route contains a checker receipt",
                        "Remove the unnecessary checker cost and adjudicate machine evidence only.")


def validate_adjudication(root: Path | str, receipt_path: Path | str,
                          risk_tier: str, unit_id: str) -> dict[str, Any]:
    policy, policy_sha = load_policy()
    repo = repository_root(root)
    risk = str(risk_tier or "unknown").lower()
    resolved_receipt = inside(Path(receipt_path), receipt_root(repo, policy), "adjudication receipt")
    receipt = read_json(resolved_receipt, "adjudication receipt")
    validate_common(receipt, kind="adjudication", repo=repo, risk=risk,
                    unit_id=unit_id, policy=policy, policy_sha=policy_sha)
    if receipt.get("outcome") != "PASSED":
        raise LoopError("adjudication outcome is not PASSED",
                        "Resolve failed/unverified evidence and re-adjudicate.")
    attempt = receipt.get("attempt")
    if type(attempt) is not int or not 1 <= attempt <= policy["maxAttemptsPerCandidate"]:
        raise LoopError("adjudication attempt is outside the bounded policy",
                        "Stop after the approved attempt budget and escalate RECOVERY_REQUIRED.")
    validate_attempt_entry(repo, policy, receipt["candidate"], unit_id, risk, policy_sha,
                           attempt, resolved_receipt, receipt)
    validate_adjudication_evidence(receipt, repo=repo, risk=risk, unit_id=unit_id,
                                   policy=policy, policy_sha=policy_sha)
    return receipt


def command_machine(args: argparse.Namespace) -> int:
    policy, policy_sha = load_policy()
    repo = repository_root(args.root)
    risk = args.risk_tier
    context = candidate_context(repo, risk)
    executed_tree = assert_checkout_matches_candidate(repo, context)
    input_manifests = declared_inputs(repo, args.input, policy)
    commands: list[tuple[str, str]] = []
    for raw in args.command:
        ident, sep, command = raw.partition("=")
        if not sep or not ident.strip() or not command.strip():
            raise LoopError(f"invalid --command value: {raw!r}", "Use --command id=executable command.")
        commands.append((ident.strip(), command.strip()))
    runs: list[dict[str, Any]] = []
    with isolated_candidate(repo, context) as execution_repo:
        copy_declared_inputs(repo, execution_repo, input_manifests)
        for ident, command in commands:
            started = now_iso()
            shell_transport = verification_shell(command, execution_repo)
            if shell_transport is None:
                stdout, stderr, rc = b"", b"native verification shell is unavailable", 127
                shell_name = "unavailable"
            else:
                shell_argv, shell_cwd, shell_name = shell_transport
                try:
                    proc = subprocess.run(shell_argv, cwd=shell_cwd,
                                          capture_output=True, timeout=args.timeout)
                    stdout, stderr, rc = proc.stdout or b"", proc.stderr or b"", proc.returncode
                except subprocess.TimeoutExpired as exc:
                    stdout = exc.stdout or b""
                    stderr = (exc.stderr or b"") + f"\ntimeout after {args.timeout}s".encode()
                    rc = 124
            runs.append({
                "id": ident,
                "command": command,
                "commandSha256": sha256_bytes(command.encode("utf-8")),
                "shell": shell_name,
                "startedAt": started,
                "completedAt": now_iso(),
                "timeoutSeconds": args.timeout,
                "executionMode": "isolated-staged-tree",
                "executedTree": executed_tree,
                "exitCode": rc,
                "stdoutSha256": sha256_bytes(stdout),
                "stderrSha256": sha256_bytes(stderr),
            })
        assert_isolated_candidate(execution_repo, executed_tree)
        validate_declared_inputs(execution_repo, input_manifests)
    verdict = "PASSED" if runs and all(run["exitCode"] == 0 for run in runs) else "FAILED"
    # A verification command must not mutate the candidate it is proving.
    assert_checkout_matches_candidate(repo, context)
    receipt = seal_receipt({
        "version": RECEIPT_VERSION,
        "kind": "machine-verification",
        "createdAt": now_iso(),
        "unitId": args.unit_id,
        "riskTier": risk,
        "candidate": context,
        "candidateDigest": candidate_digest(context),
        "policySha256": policy_sha,
        "producer": {"id": "itd-verification-loop", "role": "machine-verifier", "host": platform.system()},
        "producerRunId": secrets.token_hex(16),
        "assurance": {"class": "integrity-and-process", "trustRoot": "honest-host-orchestrator",
                      "samePrincipalByzantineResistance": False},
        "declaredInputs": input_manifests,
        "runs": runs,
        "verdict": verdict,
    })
    output = (Path(args.output).resolve() if args.output else
              default_path(repo, policy, args.unit_id, "machine", context,
                           identity=receipt["receiptSha256"][:16]))
    output = inside(output, receipt_root(repo, policy), "machine receipt")
    write_json_exclusive(output, receipt)
    print(output.as_posix())
    return 0 if verdict == "PASSED" else 1


def command_checker(args: argparse.Namespace) -> int:
    policy, policy_sha = load_policy()
    repo = repository_root(args.root)
    risk = args.risk_tier
    context = candidate_context(repo, risk)
    inspected_tree = assert_checkout_matches_candidate(repo, context)
    root = receipt_root(repo, policy)
    report_rel = relative_artifact(repo, Path(args.report), root / "reports", "checker report")
    prompt_rel = relative_artifact(repo, Path(args.prompt_file), root / "prompts", "checker prompt")
    report_path, prompt_path = repo / report_rel, repo / prompt_rel
    verdict = parse_report(report_path.read_text(encoding="utf-8", errors="replace"))
    checker = {"provider": args.checker_provider.strip(),
               "model": args.checker_model.strip(),
               "session": args.checker_session.strip()}
    maker = {"provider": args.maker_provider.strip(),
             "model": args.maker_model.strip(),
             "session": args.maker_session.strip()}
    receipt = seal_receipt({
        "version": RECEIPT_VERSION,
        "kind": "checker",
        "createdAt": now_iso(),
        "unitId": args.unit_id,
        "riskTier": risk,
        "candidate": context,
        "candidateDigest": candidate_digest(context),
        "policySha256": policy_sha,
        "producer": {"id": "itd-verification-loop", "role": "semantic-checker", "host": platform.system()},
        "producerRunId": secrets.token_hex(16),
        "assurance": {"class": "integrity-and-process", "trustRoot": "honest-host-orchestrator",
                      "samePrincipalByzantineResistance": False},
        "inspectedTree": inspected_tree,
        "checkerMode": args.mode,
        "provenance": {"maker": maker, "checker": checker},
        "artifacts": {
            "report": {"path": report_rel, "sha256": sha256_file(report_path)},
            "prompt": {"path": prompt_rel, "sha256": sha256_file(prompt_path)},
        },
        "verdict": str(verdict["verdict"]).upper(),
        "findings": verdict["findings"],
        "unverified": verdict["unverified"],
    })
    output = (Path(args.output).resolve() if args.output else
              default_path(repo, policy, args.unit_id, "checker", context,
                           identity=receipt["receiptSha256"][:16]))
    output = inside(output, root, "checker receipt")
    write_json_exclusive(output, receipt)
    # Validate independence immediately; a non-PASS report remains durable but cannot gate.
    validate_checker(receipt, repo=repo, risk=risk, unit_id=args.unit_id,
                     policy=policy, policy_sha=policy_sha,
                     required_mode=policy["riskRoutes"][risk]["checkerMode"])
    print(output.as_posix())
    return 0


def dependency(repo: Path, root: Path, path: Path, label: str) -> dict[str, str]:
    resolved = inside(path, root, label)
    if not resolved.is_file():
        raise LoopError(f"{label} is missing: {resolved}", f"Create {label} before adjudication.")
    return {"path": resolved.relative_to(repo).as_posix(), "sha256": sha256_file(resolved)}


def command_adjudicate(args: argparse.Namespace) -> int:
    policy, policy_sha = load_policy()
    repo = repository_root(args.root)
    risk = args.risk_tier
    context = candidate_context(repo, risk)
    root = receipt_root(repo, policy)
    machine_path = Path(args.machine).resolve()
    machine = read_json(machine_path, "machine receipt")
    validate_machine(machine, repo=repo, risk=risk, unit_id=args.unit_id,
                     policy=policy, policy_sha=policy_sha)
    if machine.get("verdict") != "PASSED":
        raise LoopError("machine verification failed", "Repair the candidate before semantic review/adjudication.")
    route = policy["riskRoutes"][risk]
    dependencies: dict[str, Any] = {"machine": dependency(repo, root, machine_path, "machine receipt")}
    if route["checkerRequired"]:
        if not args.checker:
            raise LoopError("required checker receipt is missing",
                            "Run the risk-tier checker or remain UNVERIFIED.")
        checker_path = Path(args.checker).resolve()
        checker = read_json(checker_path, "checker receipt")
        validate_checker(checker, repo=repo, risk=risk, unit_id=args.unit_id,
                         policy=policy, policy_sha=policy_sha,
                         required_mode=route["checkerMode"])
        dependencies["checker"] = dependency(repo, root, checker_path, "checker receipt")
    elif args.checker:
        raise LoopError("low-risk machine-only route must not spend a checker",
                        "Adjudicate the machine receipt without --checker.")
    assert_checkout_matches_candidate(repo, context)
    with reserve_attempt(repo, policy, context, args.unit_id, risk, policy_sha,
                         args.attempt) as (attempt, entry_path):
        output = (Path(args.output).resolve() if args.output
                  else default_path(repo, policy, args.unit_id, "adjudication", context, attempt))
        output = inside(output, root, "adjudication receipt")
        if output.exists():
            # Recover the only safe crash window: a complete immutable receipt
            # was linked, but its append-only ledger entry was not yet linked.
            receipt = read_json(output, "orphaned adjudication receipt")
            validate_common(receipt, kind="adjudication", repo=repo, risk=risk,
                            unit_id=args.unit_id, policy=policy, policy_sha=policy_sha)
            expected_ledger = {
                "entryPath": entry_path.relative_to(repo).as_posix(),
                "sequence": attempt,
            }
            if (receipt.get("outcome") != "PASSED"
                    or receipt.get("attempt") != attempt
                    or receipt.get("attemptLedger") != expected_ledger
                    or receipt.get("dependencies") != dependencies):
                raise LoopError("orphaned adjudication does not match the pending transaction",
                                "Preserve the conflicting evidence and escalate for manual recovery.")
            validate_adjudication_evidence(
                receipt, repo=repo, risk=risk, unit_id=args.unit_id,
                policy=policy, policy_sha=policy_sha)
        else:
            receipt = seal_receipt({
                "version": RECEIPT_VERSION,
                "kind": "adjudication",
                "createdAt": now_iso(),
                "unitId": args.unit_id,
                "riskTier": risk,
                "candidate": context,
                "candidateDigest": candidate_digest(context),
                "policySha256": policy_sha,
                "producer": {"id": "itd-verification-loop", "role": "adjudicator", "host": platform.system()},
                "producerRunId": secrets.token_hex(16),
                "assurance": {"class": "integrity-and-process", "trustRoot": "honest-host-orchestrator",
                              "samePrincipalByzantineResistance": False},
                "attempt": attempt,
                "attemptLedger": {
                    "entryPath": entry_path.relative_to(repo).as_posix(),
                    "sequence": attempt,
                },
                "checkerMode": route["checkerMode"],
                "dependencies": dependencies,
                "outcome": "PASSED",
            })
            write_json_exclusive(output, receipt)
        entry = make_attempt_entry(repo, output, receipt)
        write_json_exclusive(entry_path, entry)
        validate_adjudication(repo, output, risk, args.unit_id)
    print(output.as_posix())
    return 0


def command_check(args: argparse.Namespace) -> int:
    validate_adjudication(args.root, args.receipt, args.risk_tier, args.unit_id)
    return 0


def fail(exc: LoopError) -> int:
    print(json.dumps({"status": "UNVERIFIED", "why": exc.why, "fix": exc.fix},
                     ensure_ascii=False, sort_keys=True))
    return 1


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Risk-tiered proof-carrying Verification Loop")
    sub = p.add_subparsers(dest="action")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, default=Path.cwd())
    common.add_argument("--unit-id", required=True)
    common.add_argument("--risk-tier", choices=sorted(RISK_TIERS), required=True)
    machine = sub.add_parser("machine", parents=[common])
    machine.add_argument("--command", action="append", required=True, help="id=command")
    machine.add_argument(
        "--input", action="append", default=[],
        help="explicit ignored/untracked file or directory copied and hash-bound into the isolated oracle")
    machine.add_argument("--timeout", type=int, default=600)
    machine.add_argument("--output")
    checker = sub.add_parser("checker", parents=[common])
    checker.add_argument("--mode", choices=sorted(CHECKER_MODES), required=True)
    checker.add_argument("--report", required=True)
    checker.add_argument("--prompt-file", required=True)
    checker.add_argument("--maker-provider", required=True)
    checker.add_argument("--maker-model", required=True)
    checker.add_argument("--maker-session", required=True)
    checker.add_argument("--checker-provider", required=True)
    checker.add_argument("--checker-model", required=True)
    checker.add_argument("--checker-session", required=True)
    checker.add_argument("--output")
    adjudicate = sub.add_parser("adjudicate", parents=[common])
    adjudicate.add_argument("--machine", required=True)
    adjudicate.add_argument("--checker")
    adjudicate.add_argument(
        "--attempt", type=int,
        help="optional assertion of the next durable attempt; allocation is automatic")
    adjudicate.add_argument("--output")
    check = sub.add_parser("check", parents=[common])
    check.add_argument("--receipt", required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list:
        return 0
    args = parser().parse_args(args_list)
    try:
        if args.action == "machine":
            if args.timeout <= 0:
                raise LoopError("timeout must be positive", "Use a finite positive command timeout.")
            return command_machine(args)
        if args.action == "checker":
            return command_checker(args)
        if args.action == "adjudicate":
            return command_adjudicate(args)
        if args.action == "check":
            return command_check(args)
        raise LoopError("a Verification Loop action is required", "Use machine, checker, adjudicate or check.")
    except LoopError as exc:
        return fail(exc)


if __name__ == "__main__":
    raise SystemExit(main())
