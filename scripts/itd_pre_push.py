#!/usr/bin/env python3
"""Global Git pre-push UX guard for registered ITD repositories."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

# Preserve the closed runtime even when this entrypoint is called without -B.
sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SHARED = ROOT / "skills" / "_shared"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SHARED))

import itd_gate_control as gate  # noqa: E402
import itd_machine_oracle as machine  # noqa: E402


MAX_STDIN_BYTES = 1024 * 1024
MAX_RECEIPT_BYTES = 4 * 1024 * 1024
ZERO_SHA = "0" * 40
MACHINE_EXECUTOR = machine.execute


class PushBlocked(RuntimeError):
    pass


def git_root() -> Path:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PushBlocked("Git repository identity is unavailable") from exc
    if completed.returncode != 0 or len(completed.stdout) > 32768:
        raise PushBlocked("Git repository identity is unavailable")
    try:
        return Path(completed.stdout.decode("utf-8").strip()).resolve()
    except UnicodeError as exc:
        raise PushBlocked("Git repository path is not UTF-8") from exc


def parse_updates(raw: bytes) -> list[dict[str, str]]:
    if not raw or len(raw) > MAX_STDIN_BYTES or b"\x00" in raw:
        raise PushBlocked("pre-push update stream is empty or invalid")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise PushBlocked("pre-push update stream is not UTF-8") from exc
    if not 1 <= len(lines) <= 1000:
        raise PushBlocked("pre-push update count is outside its bound")
    updates: list[dict[str, str]] = []
    for line in lines:
        fields = line.split()
        if (
            len(fields) != 4
            or not gate.SHA_RE.fullmatch(fields[1].lower())
            or not gate.SHA_RE.fullmatch(fields[3].lower())
            or not fields[0]
            or not fields[2].startswith("refs/")
        ):
            raise PushBlocked("pre-push update coordinates are invalid")
        updates.append(
            {
                "localRef": fields[0],
                "localSha": fields[1].lower(),
                "remoteRef": fields[2],
                "remoteSha": fields[3].lower(),
            }
        )
    return updates


def protected_ref(value: str) -> bool:
    return (
        value in {"refs/heads/main", "refs/heads/master"}
        or value.startswith("refs/heads/release/")
    )


def load_machine_receipt(path: Path) -> dict[str, Any]:
    if not path.is_absolute() or not path.is_file():
        raise PushBlocked("guarded push machine receipt is unavailable")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PushBlocked("guarded push machine receipt is unreadable") from exc
    if not raw or len(raw) > MAX_RECEIPT_BYTES:
        raise PushBlocked("guarded push machine receipt size is invalid")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PushBlocked("guarded push machine receipt is invalid JSON") from exc
    if not isinstance(value, dict):
        raise PushBlocked("guarded push machine receipt is not an object")
    unsigned = dict(value)
    supplied = unsigned.pop("receiptSha256", None)
    calculated = hashlib.sha256(gate.canonical_json(unsigned)).hexdigest()
    if (
        supplied != calculated
        or value.get("version") != 2
        or value.get("kind") != "itd-machine-oracle"
        or value.get("status") != "PASSED"
        or value.get("executionCheckout") != "isolated-exact-head-tree"
        or value.get("verifierTrust")
        not in {"LOCAL_ONLY", "PROTECTED_BASE_CONTENT_BOUND"}
        or value.get("trustedVerifierFailures") != []
        or not isinstance(value.get("trustedVerifierBindings"), list)
        or not value["trustedVerifierBindings"]
        or not any(
            isinstance(row, dict)
            and row.get("objectKind") == "tree"
            and row.get("status") in {"LOCAL_ONLY", "MATCHED"}
            for row in value["trustedVerifierBindings"]
        )
        or not gate.SHA_RE.fullmatch(str(value.get("headSha", "")).lower())
        or not gate.SHA_RE.fullmatch(str(value.get("tree", "")).lower())
        or not isinstance(value.get("commands"), list)
        or not value["commands"]
        or any(
            not isinstance(row, dict) or row.get("status") != "PASSED"
            for row in value["commands"]
        )
    ):
        raise PushBlocked(
            "guarded push receipt is stale, malformed, or did not pass"
        )
    return value


def current_head(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PushBlocked("current Git HEAD is unavailable") from exc
    if completed.returncode != 0 or len(completed.stdout) > 256:
        raise PushBlocked("current Git HEAD is unavailable")
    try:
        head = completed.stdout.decode("ascii").strip().lower()
    except UnicodeError as exc:
        raise PushBlocked("current Git HEAD is invalid") from exc
    if not gate.SHA_RE.fullmatch(head):
        raise PushBlocked("current Git HEAD is invalid")
    return head


def execute_fresh_machine_oracle(root: Path) -> dict[str, Any]:
    try:
        value = MACHINE_EXECUTOR(
            root,
            root / ".itd" / "VERIFICATION_CONTRACT.json",
        )
    except (machine.OracleError, OSError, UnicodeError) as exc:
        raise PushBlocked(
            "fresh guarded-push machine oracle did not complete"
        ) from exc
    if (
        not isinstance(value, dict)
        or value.get("version") != 2
        or value.get("kind") != "itd-machine-oracle"
        or value.get("status") != "PASSED"
        or value.get("executionCheckout") != "isolated-exact-head-tree"
        or not gate.SHA_RE.fullmatch(
            str(value.get("headSha", "")).lower()
        )
        or not gate.SHA_RE.fullmatch(str(value.get("tree", "")).lower())
    ):
        raise PushBlocked("fresh guarded-push machine oracle did not pass")
    return value


def machine_evidence_binding(value: dict[str, Any]) -> dict[str, Any] | None:
    """Return the stable command/trust evidence that a fresh run must match."""
    commands = value.get("commands")
    if not isinstance(commands, list) or any(
        not isinstance(row, dict) for row in commands
    ):
        return None
    command_fields = (
        "id",
        "argvSha256",
        "trustedVerifierPaths",
        "trustedVerifierManifestSha256",
        "timeoutSeconds",
        "passFailParser",
        "exitCode",
        "timedOut",
        "outputOverflow",
        "runtimeSha256",
        "status",
    )
    return {
        "contractPath": value.get("contractPath"),
        "contractSha256": value.get("contractSha256"),
        "contractSource": value.get("contractSource"),
        "contractRepository": value.get("contractRepository"),
        "contractHeadSha": value.get("contractHeadSha"),
        "contractTree": value.get("contractTree"),
        "verifierTrust": value.get("verifierTrust"),
        "trustedVerifierBindings": value.get("trustedVerifierBindings"),
        "trustedVerifierFailures": value.get("trustedVerifierFailures"),
        "commands": [
            {field: row.get(field) for field in command_fields}
            for row in commands
        ],
        "missingArtifacts": value.get("missingArtifacts"),
        "requiredArtifactSha256": value.get("requiredArtifactSha256"),
        "executionCheckout": value.get("executionCheckout"),
    }


def configured_registry_path() -> Path:
    """The registry path as configured, WITHOUT resolving symlinks.

    gate.registry_path() resolves the path, so a dangling symlink there would resolve to its missing target
    and look absent. Absence must be judged on the entry the owner configured; the same default as
    gate.live_default_registry_path(), unresolved.
    """
    configured = os.environ.get("ITD_GATE_REGISTRY")
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
        return base / "ITD" / "gates.json"
    return Path.home() / ".config" / "itd" / "gates.json"


def read_registry_file(configured: Path) -> dict[str, Any]:
    """Open the registry ONCE, non-blocking, and validate the opened descriptor, not the path.

    A type check on the path and a later open are two operations: between them the entry can be swapped (a
    FIFO would hang the open, a redirect would validate different bytes than those loaded). Here the only open
    is non-blocking, the regular-file requirement is checked with fstat on that descriptor, and exactly the
    bytes read from it are parsed and validated. A missing target (a dangling symlink) is not absence.
    """
    flags = (
        os.O_RDONLY
        | int(getattr(os, "O_NONBLOCK", 0))
        | int(getattr(os, "O_NOCTTY", 0))
        | int(getattr(os, "O_BINARY", 0))
    )
    try:
        descriptor = os.open(configured, flags)
    except OSError as exc:
        raise PushBlocked(
            "the ITD gate registry exists but cannot be opened; repair it before pushing"
        ) from exc
    limit = gate.MAX_HTTP_RESPONSE_BYTES
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise PushBlocked(
                "the ITD gate registry path is not a regular file; repair it before pushing"
            )
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining > 0:
            try:
                chunk = os.read(descriptor, remaining)
            except OSError as exc:
                raise PushBlocked(
                    "the ITD gate registry cannot be read; repair it before pushing"
                ) from exc
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if not raw or len(raw) > limit:
        raise PushBlocked("the ITD gate registry size is invalid; repair it before pushing")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PushBlocked("the ITD gate registry JSON is invalid; repair it before pushing") from exc
    try:
        return gate.validate_registry(value)
    except gate.GateError as exc:
        raise PushBlocked(
            "the ITD gate registry exists but is not a valid registry; repair it before pushing"
        ) from exc


def enforce(
    remote_url: str,
    raw_updates: bytes,
    *,
    environment: dict[str, str] | None = None,
    registry: dict[str, Any] | None = None,
    root: Path | None = None,
) -> None:
    updates = parse_updates(raw_updates)
    # GATE-OPTIN-1: the gate protects the repositories REGISTERED in gates.json (`itd gate register-profile`).
    # A non-GitHub remote and a machine with no registry at all push freely and silently; a GitHub repository
    # missing from an existing registry pushes freely with one advisory line on stderr. A registry path that
    # exists but cannot be read still fails closed: it may hide registrations.
    try:
        repository = gate.github_repository_from_remote(remote_url)
    except gate.GateError:
        return
    if registry is None:
        # Absence means exactly ENOENT from lstat: no entry at the registry path at all (a fresh machine) -
        # nothing to protect, nothing to say. Any other entry or outcome - a directory, a dangling symlink, a
        # denied stat or read, invalid content - may hide registrations and fails closed.
        configured = configured_registry_path()
        try:
            os.lstat(configured)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise PushBlocked(
                "the ITD gate registry path cannot be inspected; repair it before pushing"
            ) from exc
        registry = read_registry_file(configured)
    matches = [
        row
        for row in registry["repositories"]
        if row["repository"].casefold() == repository.casefold()
    ]
    if not matches:
        print(
            f"ITD: {repository} is not registered in the ITD gate - pushing without "
            "local review (register it with `itd gate register-profile` to require one).",
            file=sys.stderr,
        )
        return
    protected = [
        row["remoteRef"] for row in updates if protected_ref(row["remoteRef"])
    ]
    if protected:
        raise PushBlocked(
            "direct push to protected branch is forbidden: "
            + ", ".join(sorted(protected))
        )
    environment = environment if environment is not None else os.environ
    if environment.get("ITD_GUARDED_PR_PUSH") != "1":
        raise PushBlocked(
            "registered repository pushes must use `itd pr create`"
        )
    for name in (
        "ITD_MAKER_VENDOR",
        "ITD_MAKER_MODEL",
        "ITD_MAKER_SESSION",
    ):
        value = environment.get(name, "")
        if (
            not value
            or len(value) > 200
            or "\r" in value
            or "\n" in value
        ):
            raise PushBlocked(
                "guarded push maker provenance is missing or invalid"
            )
    actual_root = (root or git_root()).resolve()
    if actual_root != Path(matches[0]["checkout"]).resolve():
        raise PushBlocked(
            "registered checkout differs from the active Git repository"
        )
    local_review = (
        registry.get("version") == 2
        and matches[0].get("protectionProfile") == "local-review"
    )
    if local_review:
        expected_head = current_head(actual_root)
        if any(
            row["localSha"] in {ZERO_SHA}
            or row["localSha"] != expected_head
            for row in updates
        ):
            raise PushBlocked(
                "pushed commit does not equal the exact reviewed HEAD"
            )
        require_profile_review(registry, matches[0], actual_root)
        return
    receipt_raw = environment.get("ITD_MACHINE_RECEIPT", "")
    receipt = load_machine_receipt(Path(receipt_raw))
    expected_head = str(receipt["headSha"]).lower()
    if any(
        row["localSha"] in {ZERO_SHA}
        or row["localSha"] != expected_head
        for row in updates
    ):
        raise PushBlocked(
            "pushed commit does not equal the exact machine receipt HEAD"
        )
    require_profile_review(registry, matches[0], actual_root)
    if Path(str(receipt.get("repository", ""))).resolve() != actual_root:
        raise PushBlocked(
            "machine receipt repository differs from the active checkout"
        )
    fresh = execute_fresh_machine_oracle(actual_root)
    if (
        str(fresh["headSha"]).lower() != expected_head
        or str(fresh["tree"]).lower()
        != str(receipt["tree"]).lower()
        or machine_evidence_binding(fresh)
        != machine_evidence_binding(receipt)
    ):
        raise PushBlocked(
            "fresh machine oracle differs from the guarded-push receipt"
        )


def require_profile_review(
    registry: dict[str, Any], entry: dict[str, Any], root: Path
) -> None:
    if registry.get("version") != 2:
        return
    if entry.get("protectionProfile") != "local-review":
        return
    if Path(str(entry.get("checkout", ""))).resolve() != root.resolve():
        raise PushBlocked("local-review checkout differs from active repository")
    try:
        inspection = gate.profile_doctor_entry(entry)
    except gate.GateError as exc:
        raise PushBlocked(
            f"local independent review is unavailable: {exc.reason}"
        ) from exc
    if (
        inspection.get("status") != "LOCAL_REVIEWED"
        or inspection.get("drift") != []
    ):
        raise PushBlocked("current exact local independent review is not valid")


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 2:
        print(
            "BLOCKED: pre-push requires remote name and URL. "
            "FIX: reinstall the ITD global Git hooks.",
            file=sys.stderr,
        )
        return 1
    del arguments[0]
    try:
        raw = sys.stdin.buffer.read(MAX_STDIN_BYTES + 1)
        enforce(arguments[0], raw)
    except (PushBlocked, gate.GateError) as exc:
        print(
            f"BLOCKED: {exc}. FIX: use `itd pr create` or repair "
            "`itd gate doctor --all` findings.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
