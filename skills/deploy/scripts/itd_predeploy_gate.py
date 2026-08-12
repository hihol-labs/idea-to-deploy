#!/usr/bin/env python3
"""Pre-deploy independent review gate (U16), risk-tiered and fail-closed.

/deploy calls this before any mutating step. A deploy candidate whose derived
risk class is data-sensitive, irreversible or monetary requires a fresh
Verification Loop adjudication receipt bound to the exact candidate; a
missing, stale or invalid receipt blocks the deploy. The criterion's only
bypass class, the audited ``HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW`` record,
must carry a recorded reason AND a signature; since no signed override
channel exists yet, every override record is refused for every gated class
(strict branch, fail-closed), and it is never reported as PASSED or counted
as independent-review evidence.

Stdlib only. Quiet on success; a violation prints one typed JSON line
(``{"status": "BLOCKED", "why": ..., "fix": ...}``) and exits 2. Bare
invocation without a subcommand is a no-op (exit 0).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _host_home() -> Path | None:
    """User home from the OS account database, never from the environment.

    Route finding r53: `Path.home()` reads HOME/USERPROFILE, which are
    ambient launch-time state — starting the host with HOME pointing at an
    attacker-owned tree substituted the installed methodology (the validator
    this gate delegates to) AND the pass-record MAC key in one move, defeating
    the exact-candidate receipt gate instead of failing closed. The passwd
    entry (POSIX) or the shell32 profile-folder API (Windows) answers the
    same question from the account database, which an attacker without
    host-level control cannot edit. None means "cannot resolve", and every
    caller stays fail-closed on it.
    """
    try:
        import pwd
        entry = pwd.getpwuid(os.getuid()).pw_dir
        if entry:
            return Path(entry)
    except (ImportError, KeyError, OSError):
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            buffer = ctypes.create_unicode_buffer(260)
            # CSIDL_PROFILE = 40; SHGetFolderPathW resolves the profile
            # directory from the user token, not from the environment.
            if ctypes.windll.shell32.SHGetFolderPathW(
                    None, 40, None, 0, buffer) == 0 and buffer.value:
                return Path(buffer.value)
        except (OSError, AttributeError, ImportError):
            pass
    return None


_HOST_HOME = _host_home()

RISK_ROUTINE = "routine"
RISK_DATA_SENSITIVE = "data-sensitive"
RISK_IRREVERSIBLE = "irreversible"
RISK_MONETARY = "monetary"

GATED_CLASSES = frozenset(
    {RISK_DATA_SENSITIVE, RISK_IRREVERSIBLE, RISK_MONETARY}
)
OVERRIDE_FORBIDDEN = frozenset({RISK_IRREVERSIBLE, RISK_MONETARY})
OVERRIDE_OUTCOME = "HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW"

LABEL_ROUTINE = "routine-no-review-required"
LABEL_RECEIPT = "independent-review-receipt"

VALIDATOR_RELATIVE = Path("skills") / "_shared" / "itd_verification_loop.py"
INDEPENDENCE_RELATIVE = (
    Path("skills") / "_shared" / "itd_reviewer_independence.py"
)
# Trust anchor: the INSTALLED methodology, never the deploy candidate's own
# repository — candidate-supplied validator code must not gate itself. The
# anchor is derived from the OS account database, never from HOME (r53);
# None (unresolvable home) keeps every consumer fail-closed.
INSTALLED_ROOT_DEFAULT = (
    _HOST_HOME / ".claude" if _HOST_HOME is not None else None)

DATA_SENSITIVE_MARKERS = ("itd-domain: data-sensitive",
                          "<!-- itd:data-sensitive -->")
MONETARY_MARKERS = ("itd-domain: monetary", "<!-- itd:monetary -->")
MIGRATION_DIR_CANDIDATES = ("migrations", "db/migrations",
                            "packages/supabase/migrations")


def detect_data_sensitive(root: Path) -> bool:
    """Project-declared marker in the root CLAUDE.md (fail-open only for a
    genuinely unmarked project; explicit --data-sensitive yes overrides)."""
    try:
        text = (Path(root) / "CLAUDE.md").read_text(encoding="utf-8")
    except OSError:
        return False
    return any(marker in text for marker in DATA_SENSITIVE_MARKERS)


def detect_monetary(root: Path, env: dict | None = None) -> bool:
    import os as _os
    env = _os.environ if env is None else env
    if str(env.get("ITD_DEPLOY_MONETARY", "")).lower() in ("1", "yes",
                                                           "true"):
        return True
    try:
        text = (Path(root) / "CLAUDE.md").read_text(encoding="utf-8")
    except OSError:
        return False
    return any(marker in text for marker in MONETARY_MARKERS)


def find_migrations_dirs(root: Path) -> list[str]:
    """Relative paths of ALL populated standard migration dirs.

    All of them: a new migration in a second layout (e.g. ``db/migrations``
    next to an already-deployed ``migrations/``) must not hide behind the
    first hit (route finding r23). Relative on purpose: the results are git
    pathspecs under ``git -C <root>``, where absolute paths break on
    symlinked or relatively-addressed roots (route finding r16).
    """
    found = []
    for rel in MIGRATION_DIR_CANDIDATES:
        if _populated(Path(root) / rel):
            found.append(rel)
    return found


def _populated(directory: Path) -> bool:
    """Any file OR symlink counts — rglob does not follow directory
    symlinks, so a symlinked subtree must gate by its link entry alone;
    and a migration-directory root that is ITSELF a symlink is populated
    by definition (route findings r27/r28, fail-closed)."""
    if directory.is_symlink():
        return True
    if not directory.is_dir():
        return False
    return any(e.is_file() or e.is_symlink()
               for e in directory.rglob("*"))


def find_migrations_dir(root: Path) -> str | None:
    dirs = find_migrations_dirs(root)
    return dirs[0] if dirs else None


def pending_migrations(root: Path, explicit_dir: str | None = None) -> bool:
    """Strict presence-based: ANY populated migration directory gates.

    Local ``deploy-*`` tags were tried as a "already deployed" downgrade and
    rejected by the cross-vendor route (findings r23/r25): a locally created
    tag is not an authenticated deployed-state marker, so a downgrade built
    on it violates the fail-closed criterion. Until an authenticated
    deployed-state attestation exists (queued BACKLOG follow-up), a project
    with populated migration directories is always classified irreversible.
    """
    if find_migrations_dirs(root):
        return True
    return migrations_pending(explicit_dir)


GIT_RETRY_ATTEMPTS = 3
GIT_RETRY_BACKOFF_SECONDS = 0.05


def _run_git(argv: list[str], *, timeout: int = 60):
    """Run an IDEMPOTENT git read with a bounded retry, returning the
    CompletedProcess on the first zero-exit attempt or None.

    Route finding S2/r77: under isolation/full-suite load a git subprocess
    (`rev-parse`, `status`, `archive`, `ls-files`) transiently failed — a
    fork/exec hiccup or a non-zero exit under contention — and the gate,
    correctly fail-closed, turned that into a spurious DENY of a legitimate
    deploy. Every git call here is a read of the exact candidate, so
    retrying is safe: a GENUINE failure (not a repo, no HEAD) still fails all
    attempts and stays fail-closed, while a transient one succeeds on retry.
    This removes the false denials AND the machine-oracle non-determinism
    they caused, without weakening the fail-closed contract.
    """
    import time
    for attempt in range(GIT_RETRY_ATTEMPTS):
        try:
            completed = subprocess.run(
                argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=timeout, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            completed = None
        if completed is not None and completed.returncode == 0:
            return completed
        if attempt + 1 < GIT_RETRY_ATTEMPTS:
            time.sleep(GIT_RETRY_BACKOFF_SECONDS * (attempt + 1))
    return None                            # all attempts failed → fail-closed


def derive_candidate_digest(root: Path) -> str | None:
    """Digest of the exact deploy candidate, derived from the repository
    itself (never caller-supplied): sha256 over the HEAD commit and tree ids.
    None when the repository state cannot be read (fail-closed)."""
    import hashlib
    values = []
    for ref in ("HEAD", "HEAD^{tree}"):
        completed = _run_git(["git", "-C", str(root), "rev-parse", ref])
        if completed is None:
            return None
        try:
            values.append(completed.stdout.decode("ascii", "strict").strip())
        except (UnicodeDecodeError, AttributeError):
            return None
    payload = ("itd-predeploy-candidate-v1\n"
               f"commit:{values[0]}\ntree:{values[1]}\n")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def worktree_clean(root: Path, extra_allowed: tuple[str, ...] = ()) -> bool:
    """Fail-closed: any git error counts as dirty.

    The gate's own outputs are excluded: it writes the pass ledger — and, on
    the allow path, the deploy-input artifact the caller asked for — INTO the
    checkout, so counting them as dirt would make every post-pass re-check fail
    and turn the gate into a blanket blocker (route findings r36 and r38).
    `extra_allowed` carries the artifact path recorded with the pass; nothing
    else is excluded — a gated candidate ships the reviewed commit or nothing.

    Security (2026-08-12): the exemptions apply ONLY to UNTRACKED (`??`) paths —
    the gate's own ledger writes and the recorded deploy-input artifact are
    untracked, and an untracked file never enters `git archive HEAD`, so it
    cannot ship. A TRACKED file the repository committed under
    `.itd-memory/deploy-gate/` (or at the recorded artifact path) and then
    MODIFIED must count as dirt: exempting it directory-wide let a valid pass
    survive an edit to committed, deployable content and ship it unreviewed.
    """
    completed = _run_git(
        # `--untracked-files=all`: the default collapses an untracked
        # directory to its parent (`?? .itd-memory/`), which would hide
        # whether the only untracked content is the gate's own ledger.
        ["git", "-C", str(root), "status", "--porcelain",
         "--untracked-files=all"])
    if completed is None:
        return False
    ledger_prefix = GATE_LEDGER_DIR.as_posix() + "/"
    allowed = tuple(a for a in extra_allowed if a)
    for raw in completed.stdout.decode("utf-8", "replace").splitlines():
        code = raw[:2]
        entry = raw[3:].strip().strip('"')
        if not entry:
            continue
        path = entry.split(" -> ")[-1].strip().strip('"')
        # Only the gate's own UNTRACKED outputs are exempt; a tracked change
        # anywhere — including inside the ledger directory or at the artifact
        # path — is dirt (it is committed, deployable content).
        if code == "??" and (path.startswith(ledger_prefix) or path in allowed):
            continue
        return False
    return True


def emit_deploy_input(root: Path, dest: Path) -> str | None:
    """Materialize the exact deploy input and return its sha256.

    Route finding r30: binding the receipt to HEAD is not enough — the gate
    must also PRODUCE the artifact that gets shipped, otherwise a later
    rsync/tar of the working directory can carry ignored, unreviewed files
    into a deploy the gate just allowed. `git archive HEAD` contains exactly
    the tracked committed content of the reviewed candidate, so the emitted
    tar is the only deployable input whose hash this gate can vouch for.
    Fail-closed: any git/OS error yields None and the caller blocks.
    """
    import hashlib
    payload = _deploy_input_bytes(root)
    if payload is None:
        return None
    # Route finding r68: writing the leaf O_NOFOLLOW protects only the final
    # component — a concurrent swap of an in-checkout PARENT (e.g.
    # `.itd-memory`) to a symlink after the earlier `_relative_to_root` /
    # `is_symlink` checks made the gate follow that parent and, in the
    # existing-file branch, truncate an arbitrary host file. The artifact is
    # now written by descriptor-relative traversal from the candidate root,
    # every component `O_DIRECTORY|O_NOFOLLOW`, exactly like the ledger
    # writer, so no swapped parent can be followed.
    # r68: decide the branch LEXICALLY, never via resolve() — a symlinked
    # in-checkout parent would otherwise resolve OUTSIDE the checkout and take
    # the leaf-only path that follows that parent. The lexical relative keeps
    # such a dest on the descriptor-relative path, where O_NOFOLLOW on the
    # symlinked component refuses it.
    relative = _lexical_relative_to_root(root, dest)
    if relative is not None:
        ok = _write_bytes_norace(root, relative, payload)
    else:
        # Genuinely out-of-checkout destination is blocked by command_check
        # in production (r42); reachable only from direct/test calls.
        ok = _write_bytes_leaf_only(dest, payload)
    return hashlib.sha256(payload).hexdigest() if ok else None


def _lexical_relative_to_root(root: Path, dest: Path) -> str | None:
    """POSIX relative path of `dest` under `root` by LEXICAL normalization
    (os.path.abspath collapses `.`/`..` without following symlinks). None when
    `dest` lexically escapes the root. Used to pick the safe write path (r68).
    """
    root_abs = os.path.abspath(str(root))
    target = dest if dest.is_absolute() else Path(root) / dest
    target_abs = os.path.abspath(str(target))
    if target_abs != root_abs and not target_abs.startswith(
            root_abs + os.sep):
        return None
    rel = os.path.relpath(target_abs, root_abs)
    if rel == os.pardir or rel.startswith(os.pardir + os.sep) or rel == ".":
        return None
    return Path(rel).as_posix()


def _temp_leaf_name(leaf: str) -> str:
    import secrets
    return f".itd-tmp-{leaf}-{os.getpid()}-{secrets.token_hex(6)}"


def _atomic_write_leaf(payload: bytes, leaf: str, *, dir_fd=None,
                       dir_path: Path | None = None) -> bool:
    """Write `payload` to `leaf` by creating a FRESH temp inode (O_EXCL |
    O_NOFOLLOW) and atomically `os.replace`-ing it over the target.

    Route finding r73: an EXCL-or-verify-then-truncate on the existing target
    had a TOCTOU — a hard link created between the `nlink==1` fstat and the
    `ftruncate` let the truncate hit an aliased file. `os.replace` swaps only
    the directory entry; any hard-linked alias keeps its own untouched inode,
    so nothing outside the target name is ever truncated. Descriptor-relative
    where `dir_fd` is given (in-checkout, no swapped parent followed), plain
    path otherwise (out-of-checkout test/direct calls).
    """
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    temp = _temp_leaf_name(leaf)
    try:
        if dir_fd is not None:
            descriptor = os.open(
                temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
                0o600, dir_fd=dir_fd)
        else:
            descriptor = os.open(
                os.path.join(str(dir_path), temp),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow, 0o600)
    except OSError:
        return False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
    except OSError:
        try:
            if dir_fd is not None:
                os.unlink(temp, dir_fd=dir_fd)
            else:
                os.unlink(os.path.join(str(dir_path), temp))
        except OSError:
            pass
        return False
    try:
        if dir_fd is not None:
            os.replace(temp, leaf, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        else:
            os.replace(os.path.join(str(dir_path), temp),
                       os.path.join(str(dir_path), leaf))
    except OSError:
        try:
            if dir_fd is not None:
                os.unlink(temp, dir_fd=dir_fd)
            else:
                os.unlink(os.path.join(str(dir_path), temp))
        except OSError:
            pass
        return False
    return True


def _write_bytes_leaf_only(dest: Path, payload: bytes) -> bool:
    """Atomic-replace write for an out-of-checkout destination (r73)."""
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    if dest.is_symlink():
        return False                       # r60: never follow a symlink dest
    return _atomic_write_leaf(payload, dest.name, dir_path=dest.parent)


def _write_bytes_norace(root: Path, relative: str, payload: bytes) -> bool:
    """Write `payload` to `root/relative` with descriptor-relative no-follow
    traversal (r68). Falls back to a leaf-only no-follow open where `dir_fd`
    is unavailable (Windows), the stated limit. An existing leaf is accepted
    only as a regular file with link count 1 (r66)."""
    parts = Path(relative).parts
    if not parts:
        return False
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    supports = (os.open in getattr(os, "supports_dir_fd", set())
                and hasattr(os, "O_DIRECTORY"))

    if not supports:
        target = Path(root)
        for part in parts[:-1]:
            target = target / part
            if target.is_symlink():
                return False
            try:
                target.mkdir(exist_ok=True)
            except OSError:
                return False
        return _atomic_write_leaf(payload, parts[-1], dir_path=target)

    directory_flags = os.O_RDONLY | os.O_DIRECTORY | nofollow
    try:
        current = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return False
    try:
        for part in parts[:-1]:
            try:
                try:
                    following = os.open(part, directory_flags, dir_fd=current)
                except FileNotFoundError:
                    os.mkdir(part, 0o700, dir_fd=current)
                    following = os.open(part, directory_flags, dir_fd=current)
            except OSError:
                return False
            os.close(current)
            current = following
        return _atomic_write_leaf(payload, parts[-1], dir_fd=current)
    finally:
        try:
            os.close(current)
        except OSError:
            pass


def _deploy_input_bytes(root: Path) -> bytes | None:
    """The exact deployable input (tracked committed content), or None."""
    completed = _run_git(
        ["git", "-C", str(root), "archive", "--format=tar", "HEAD"],
        timeout=600)
    if completed is None or not completed.stdout:
        return None
    return completed.stdout


def _destination_is_tracked(root: Path, relative: str) -> bool:
    """True when the deploy-input destination is a TRACKED file (or the
    check cannot prove otherwise, fail-closed).

    Route finding r60: `--emit-deploy-input` accepted any in-checkout path,
    so a caller could name a reviewed SOURCE file and the gate would
    overwrite it with the archive while reporting ALLOWED.
    """
    completed = _run_git(
        ["git", "-C", str(root), "ls-files", "--", relative], timeout=30)
    if completed is None:
        return True                        # cannot prove untracked: fail-closed
    return bool(completed.stdout.decode("utf-8", "replace").strip())


def current_deploy_input_sha256(root: Path) -> str | None:
    """Digest of the deploy input as it stands NOW, without materializing it.

    Lets `gate_pass_is_current` bind a recorded pass to one exact artifact
    instead of to a commit whose content may have moved since.
    """
    import hashlib
    payload = _deploy_input_bytes(root)
    return None if payload is None else hashlib.sha256(payload).hexdigest()


GATE_LEDGER_DIR = Path(".itd-memory") / "deploy-gate"
GATE_LEDGER_MAX_AGE_SECONDS = 86400
# Route finding r79 (real S1 flake root cause): the wall clock is not monotone.
# On WSL2, and after any NTP step, `time.time()` can jump BACKWARD by several
# seconds between the moment a pass record's `recordedAt` is written and the
# moment this gate reads it, making the computed age transiently NEGATIVE and a
# genuinely fresh pass look invalid (observed: age −1…−6s). A record dated in
# the near future is, by definition, not stale, so a bounded negative skew is
# tolerated on the freshness LOWER bound. The staleness UPPER bound is
# unchanged, and a timestamp beyond this tolerance into the future is still
# refused (that is not ordinary drift).
GATE_CLOCK_SKEW_TOLERANCE_SECONDS = 300
# Host-owned authentication key for the pass record. It lives OUTSIDE every
# checkout on purpose: route finding r51 rejected an unsigned record, because
# anything a candidate can write, a candidate can forge. The gate mints the key
# on first use with owner-only permissions. The path is anchored at the
# account-database home (r53): a HOME-relocated launch must not be able to
# point the gate at an attacker-minted key.
GATE_MAC_KEY_PATH = (
    _HOST_HOME / ".config" / "itd" / "deploy-gate.key"
    if _HOST_HOME is not None else None)


def _gate_mac_key(create: bool = False) -> bytes | None:
    if GATE_MAC_KEY_PATH is None:
        return None
    import os
    import stat as _stat
    try:
        try:
            info = os.lstat(str(GATE_MAC_KEY_PATH))
        except FileNotFoundError:
            info = None
        if info is not None:
            # Route finding r65: the MAC key is the pass-record authorization
            # boundary. A symlinked key, a key owned by another user, or a
            # world/group-readable key lets a second local principal mint a
            # valid pass record. Accept it ONLY as a non-symlink regular file
            # owned by the effective user with no group/other bits. (POSIX;
            # on Windows lstat has no uid/mode, so the regular-file check is
            # the stated best-effort limit.)
            if _stat.S_ISLNK(info.st_mode) or not _stat.S_ISREG(info.st_mode):
                return None
            if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
                return None
            if os.name == "posix" and (info.st_mode & 0o077):
                return None
            key = GATE_MAC_KEY_PATH.read_bytes()
            return key if len(key) >= 32 else None
        if not create:
            return None
        import secrets
        GATE_MAC_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        key = secrets.token_bytes(32)
        descriptor = os.open(str(GATE_MAC_KEY_PATH), flags, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(key)
        return key
    except OSError:
        return None


def _gate_record_mac(record: dict, key: bytes) -> str:
    import hashlib
    import hmac
    payload = json.dumps({k: v for k, v in record.items() if k != "mac"},
                         ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def gate_ledger_path(root: Path, candidate_digest: str) -> Path:
    return Path(root) / GATE_LEDGER_DIR / f"{candidate_digest}.json"


def _ledger_write_refused(root: Path, target: Path) -> bool:
    """Symlinked or structurally unexpected ledger paths are never written.

    Route finding r58: the ledger lives inside the candidate checkout, so a
    reviewed repository could COMMIT `.itd-memory/deploy-gate/<digest>.json`
    (or one of its parent directories) as a symlink to a writable host file;
    the gate would then follow it and deposit a MAC-valid record at an
    attacker-selected location, where the same pass could be consumed
    outside the checkout. Every ledger path component must be a real
    directory (or absent), and the entry itself must not be a symlink or any
    other non-regular file.
    """
    probe = Path(root)
    for part in GATE_LEDGER_DIR.parts:
        probe = probe / part
        if probe.is_symlink():
            return True
        if probe.exists() and not probe.is_dir():
            return True
    if target.is_symlink():
        return True
    if target.exists() and not target.is_file():
        return True
    return False


def _write_ledger_record(target: Path, payload: str) -> bool:
    """Atomic-replace ledger write (r59/r70/r73): a raced-in symlink or a
    hard-linked alias is never followed or truncated — the record is written
    to a fresh temp inode and atomically replaced over the target name."""
    if target.is_symlink():
        return False
    return _atomic_write_leaf(payload.encode("utf-8"), target.name,
                              dir_path=target.parent)


def _ledger_write_entry(root: Path, entry_name: str, payload: str) -> bool:
    """Write one ledger entry with descriptor-relative no-follow traversal.

    Route finding r59: checking parents with lstat and then opening only the
    FINAL pathname with O_NOFOLLOW leaves a TOCTOU window — a checked parent
    directory swapped for a symlink between the check and the write redirects
    a MAC-valid record outside the checkout. On platforms with dir_fd
    support every component under the root is opened O_NOFOLLOW|O_DIRECTORY
    relative to the previous verified descriptor, so a swapped component
    fails instead of being followed. Platforms without dir_fd (Windows)
    keep the lstat pre-check + final O_NOFOLLOW open — stated limit, and
    creating symlinks there needs elevated privileges to begin with.
    """
    target = Path(root) / GATE_LEDGER_DIR / entry_name
    if _ledger_write_refused(root, target):
        return False
    supports = (os.open in getattr(os, "supports_dir_fd", set())
                and hasattr(os, "O_DIRECTORY"))
    if not supports:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        return _write_ledger_record(target, payload)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | nofollow
    try:
        current = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return False
    try:
        for part in GATE_LEDGER_DIR.parts:
            try:
                try:
                    following = os.open(part, directory_flags, dir_fd=current)
                except FileNotFoundError:
                    os.mkdir(part, 0o700, dir_fd=current)
                    following = os.open(part, directory_flags, dir_fd=current)
            except OSError:
                return False
            os.close(current)
            current = following
        return _atomic_write_leaf(payload.encode("utf-8"), entry_name,
                                  dir_fd=current)
    finally:
        try:
            os.close(current)
        except OSError:
            pass


def _relative_to_root(root: Path, target: Path) -> str | None:
    """POSIX path of `target` inside `root`, or None when it lives outside."""
    try:
        resolved = Path(target)
        if not resolved.is_absolute():
            resolved = Path(root) / resolved
        return resolved.resolve().relative_to(Path(root).resolve()).as_posix()
    except (OSError, ValueError, RuntimeError):
        # RuntimeError: resolve() on a symlink cycle (route finding r55) —
        # an unresolvable destination is out of bounds, not a crash
        return None


def record_gate_pass(root: Path, candidate_digest: str, risk_class: str,
                     deploy_input_sha256: str,
                     deploy_input_path: Path | None = None) -> bool:
    """Durably record that THIS candidate passed the gate.

    The PreToolUse hook reads this record to block mutating deploy commands
    for a gated candidate that never passed. The record is a transport, not
    the contract: it is written only on the allow path, is bound to the
    exact candidate digest, and never substitutes for the receipt itself.
    """
    import time
    try:
        target = gate_ledger_path(root, candidate_digest)
        record = {
            "kind": "itd-predeploy-gate-pass-v1",
            "candidateDigest": candidate_digest,
            "riskClass": risk_class,
            "deployInputSha256": deploy_input_sha256,
            "recordedAt": int(time.time()),
        }
        # Route finding r38: the gate's own emitted artifact is an untracked
        # file inside the checkout, so a clean-tree re-check saw the gate's
        # documented `--emit-deploy-input` output as drift and refused the pass
        # it had just written. The record names that path so the re-check can
        # exclude exactly it — and nothing else.
        if deploy_input_path is not None:
            relative = _relative_to_root(root, deploy_input_path)
            if relative:
                record["deployInputPath"] = relative
        key = _gate_mac_key(create=True)
        if key is None:
            return False
        record["mac"] = _gate_record_mac(record, key)
        return _ledger_write_entry(
            root, target.name, json.dumps(record, ensure_ascii=False))
    except OSError:
        return False


def gate_pass_is_current(root: Path) -> bool:
    """Fail-closed: only an unexpired record bound to the CURRENT candidate.

    Route finding r36 (2026-08-11): a digest+timestamp match was too weak. The
    candidate digest is derived from HEAD, so a genuine pass survived every
    later edit of the working tree — the shipped bytes were no longer the
    reviewed bytes. The record must therefore also prove:

      * the worktree is clean, exactly as the allow path required when the
        record was written (`command_check` rejects a dirty gated candidate);
      * the recorded `deployInputSha256` still equals the deploy input derived
        from the CURRENT tracked committed content, so the pass authorizes one
        exact artifact rather than "this commit, whatever it now contains";
      * the recorded risk class is one the gate actually gates.

    What this still does NOT claim: the record is an unsigned local transport,
    so a deliberately hand-written record inside the checkout remains a
    conscious bypass, not a forgery the gate can detect. Signing it through the
    same host-owned authority as the override channel is the queued BACKLOG
    follow-up; the receipt — not this record — stays the contract.
    """
    import time
    candidate_digest = derive_candidate_digest(root)
    if not candidate_digest:
        return False
    try:
        record_path = gate_ledger_path(root, candidate_digest)
        # r58: a symlinked ledger entry is never a pass — the bytes it points
        # at are not what this gate wrote into THIS checkout.
        if record_path.is_symlink() or _ledger_write_refused(
                root, record_path):
            return False
        raw = record_path.read_text(encoding="utf-8")
        record = json.loads(raw)
    except (OSError, ValueError):
        return False
    # Route finding r67: valid JSON of a non-dict type (e.g. `[]`) passed the
    # structural checks and then crashed `record.get(...)` with AttributeError
    # through the classify PreToolUse path. A non-dict record is not a pass.
    if not isinstance(record, dict):
        return False
    if (record.get("kind") != "itd-predeploy-gate-pass-v1"
            or record.get("candidateDigest") != candidate_digest):
        return False
    # Route finding r51: an unsigned record inside the checkout is forgeable by
    # anything that can write there, so a hand-written "pass" would have
    # bypassed receipt validation entirely. The MAC is keyed by a host-owned
    # secret outside every checkout; a record without a valid one is not a
    # pass. (What this still does not defend against: an attacker who already
    # owns the user's home directory and can read that key.)
    import hmac as _hmac
    key = _gate_mac_key()
    recorded_mac = record.get("mac")
    if key is None or not isinstance(recorded_mac, str) or not _hmac.compare_digest(
            recorded_mac, _gate_record_mac(record, key)):
        return False
    if record.get("riskClass") not in GATED_CLASSES:
        return False
    recorded = record.get("recordedAt")
    if type(recorded) is not int:
        return False
    age = int(time.time()) - recorded
    if not (-GATE_CLOCK_SKEW_TOLERANCE_SECONDS <= age
            <= GATE_LEDGER_MAX_AGE_SECONDS):
        return False
    recorded_artifact = record.get("deployInputPath")
    allowed = ((recorded_artifact,)
               if isinstance(recorded_artifact, str) and recorded_artifact
               else ())
    if not worktree_clean(root, extra_allowed=allowed):
        return False
    recorded_input = record.get("deployInputSha256")
    if not isinstance(recorded_input, str) or not recorded_input:
        return False
    # Route finding r48: the artifact itself is excluded from the clean-tree
    # check (the gate writes it), so nothing stopped it from being replaced
    # with arbitrary bytes AFTER a valid check. A pass may only stand while
    # the file on disk still hashes to what the gate emitted.
    #
    # The artifact hash is checked directly rather than by re-deriving
    # `git archive HEAD`: the candidate digest already pins HEAD, the
    # clean-tree check already pins the working tree to it, so re-archiving on
    # every hook invocation added cost, not a guarantee — and under load its
    # transient failures turned into fail-closed denials of legitimate
    # commands (observed 2026-08-11 while running the full suite).
    if isinstance(recorded_artifact, str) and recorded_artifact:
        return _file_sha256(Path(root) / recorded_artifact) == recorded_input
    # A record without an artifact path never authorizes a file transport;
    # for the remaining cases the deploy input must still derive identically.
    return recorded_input == current_deploy_input_sha256(root)


def _file_sha256(path: Path) -> str | None:
    import hashlib
    import os
    import stat as _stat
    digest = hashlib.sha256()
    # Route finding r65: the recorded artifact is an untracked path the
    # clean-tree check deliberately excludes, so after a valid check it could
    # be REPLACED with a symlink pointing outside the checkout and still
    # authorize shipping that path. Open O_NOFOLLOW and reject any
    # non-regular file, so the hash is only ever of the real in-checkout
    # artifact. (POSIX; Windows keeps the plain open as the stated limit.)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(str(path), flags)
    except OSError:
        return None
    try:
        if not _stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        with os.fdopen(descriptor, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def derive_risk_class(data_sensitive: bool, migrations_pending: bool,
                      monetary: bool) -> str:
    """Highest signal wins: monetary > irreversible > data-sensitive."""
    if monetary:
        return RISK_MONETARY
    if migrations_pending:
        return RISK_IRREVERSIBLE
    if data_sensitive:
        return RISK_DATA_SENSITIVE
    return RISK_ROUTINE


def evaluate_gate(risk_class: str, receipt_status: str,
                  override_record: dict | None,
                  expected_digest: str | None) -> dict:
    """Decide for one deploy candidate. Pure; no I/O.

    ``receipt_status`` is "valid" | "missing" | "invalid" from
    :func:`validate_receipt`. The decision label is never "PASSED", and
    ``reviewEvidence`` is true only on the receipt path — the override is an
    audited exception, not a review.
    """
    if risk_class not in GATED_CLASSES:
        return {
            "allowed": True, "label": LABEL_ROUTINE,
            "reviewEvidence": False, "why": "", "fix": "",
        }
    if receipt_status == "valid":
        return {
            "allowed": True, "label": LABEL_RECEIPT,
            "reviewEvidence": True, "why": "", "fix": "",
        }
    if override_record is not None:
        # The unit criterion requires the bypass to carry a recorded reason
        # AND a signature. mint-override records are structurally validated
        # but carry no cryptographic authentication, so a deployer could
        # hand-craft a matching record (route finding r17). Until a signed
        # override channel exists, every override is refused for every
        # gated class — the strict branch of the criterion.
        return _blocked(
            f"{OVERRIDE_OUTCOME} records are not accepted: no "
            "authenticated (signed) override channel exists yet, and an "
            "unsigned record is forgeable",
            "Obtain a fresh independent-review adjudication receipt for "
            "the exact deploy candidate; the signed override channel is a "
            "queued follow-up (BACKLOG).",
        )
    return _blocked(
        f"no fresh independent-review receipt for the {risk_class} deploy "
        f"candidate (receipt {receipt_status})",
        "Run the Verification Loop for the exact deploy candidate "
        "(machine -> checker -> adjudicate) and pass the adjudication "
        "receipt via --receipt.",
    )


def _blocked(why: str, fix: str) -> dict:
    return {"allowed": False, "label": "BLOCKED", "reviewEvidence": False,
            "why": why, "fix": fix}


def default_validator_argv(root: Path, receipt: Path, unit_id: str,
                           risk_tier: str,
                           installed_root: Path) -> list[str] | None:
    """Build the validator argv anchored at the INSTALLED methodology.

    None when the installed validator is absent — the caller treats that as
    an invalid receipt (fail-closed), never as permission to fall back to
    candidate-supplied code under ``root``.
    """
    validator = Path(installed_root) / VALIDATOR_RELATIVE
    if not validator.is_file():
        return None
    return [
        sys.executable, str(validator), "check",
        "--root", str(root), "--unit-id", unit_id,
        "--risk-tier", risk_tier, "--candidate-mode", "committed-head",
        # ADJUDICATED receipts minted through the ADR-007 human-adjudication
        # channel are legitimate Verification Loop adjudications; without
        # this opt-in they would fail closed forever (route finding r13).
        "--accept-adjudicated-route",
        "--receipt", str(receipt),
    ]


def validate_receipt(root: Path, receipt: Path, unit_id: str,
                     risk_tier: str,
                     validator_argv: list[str] | None = None,
                     installed_root: Path | None = None) -> str:
    """Delegate to the Verification Loop check; fail-closed on any error."""
    receipt = Path(receipt)
    if not receipt.is_file():
        return "missing"
    if validator_argv is None:
        anchor = (INSTALLED_ROOT_DEFAULT if installed_root is None
                  else Path(installed_root))
        if anchor is None:
            return "invalid"      # unresolvable trust anchor: fail-closed
        validator_argv = default_validator_argv(
            root, receipt, unit_id, risk_tier, anchor,
        )
        if validator_argv is None:
            return "invalid"
    else:
        validator_argv = list(validator_argv)
    try:
        completed = subprocess.run(
            validator_argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=300, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "invalid"
    return "valid" if completed.returncode == 0 else "invalid"


_RECORD_KEYS = frozenset({
    "outcome", "candidateDigest", "confirmedBy", "reason",
    "crossVendorUnavailability", "fallbackUnavailability",
})


def _independence_validator(installed_root: Path):
    """Import the canonical override validator from the INSTALLED
    methodology (never the candidate repository); None means fail-closed."""
    import importlib.util
    path = Path(installed_root) / INDEPENDENCE_RELATIVE
    try:
        spec = importlib.util.spec_from_file_location(
            "itd_reviewer_independence_gate", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        return None
    return module


def load_override(path: Path, expected_digest: str | None,
                  installed_root: Path | None = None) -> dict | None:
    """Load an override record through the canonical validator.

    Only a record minted by ``itd_verification_loop.py mint-override`` passes:
    the shared independence policy enforces the closed record shape, the
    override outcome literal, the exact candidate-digest binding, a non-empty
    confirmer and reason, and typed UNAVAILABLE evidence for both the
    cross-vendor and fallback routes. Anything else — including a hand-written
    ``{"outcome": ..., "candidateDigest": ...}`` stub, an unreadable file, a
    missing digest, or an unavailable policy module — is None (fail-closed).
    """
    if not expected_digest:
        return None
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    record = {k: raw[k] for k in _RECORD_KEYS if k in raw}
    anchor = (INSTALLED_ROOT_DEFAULT if installed_root is None
              else Path(installed_root))
    if anchor is None:
        return None               # unresolvable trust anchor: fail-closed
    policy = _independence_validator(anchor)
    if policy is None:
        return None
    try:
        return dict(policy.validate_human_override(record, expected_digest))
    except Exception:
        return None


def migrations_pending(migrations_dir: str | None) -> bool:
    """Recursive, symlink-aware: migration layouts often nest files in
    subdirectories (route findings r22/r27)."""
    if not migrations_dir:
        return False
    return _populated(Path(migrations_dir))


def recorded_deploy_input_path(root: Path) -> str | None:
    """Artifact path named by the CURRENT, MAC-validated pass record.

    Route finding r86: this reopened the ledger entry with a plain
    follow-symlinks read AFTER `gate_pass_is_current` had validated it, so a
    swap of the entry between the two reads could feed classify an arbitrary
    `deployInputPath` that the gate never authenticated. It now applies the
    same symlink refusal and host-owned MAC validation as
    `gate_pass_is_current`, so the path it returns is only ever from a record
    this gate authenticated. (The residual same-principal swap between two
    MAC-validated reads is the documented r73 TOCTOU limit: forging a second
    valid record needs the host-owned key.)
    """
    candidate_digest = derive_candidate_digest(root)
    if not candidate_digest:
        return None
    try:
        record_path = gate_ledger_path(root, candidate_digest)
        if record_path.is_symlink() or _ledger_write_refused(root, record_path):
            return None
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    # Route finding r88: MAC validity alone is not exact-candidate binding — a
    # previously valid MAC-signed record for ANOTHER candidate could be swapped
    # in and supply its artifact path without forging a MAC. Require the record
    # to be a gate-pass bound to the CURRENT derived digest, exactly as
    # gate_pass_is_current does.
    if (record.get("kind") != "itd-predeploy-gate-pass-v1"
            or record.get("candidateDigest") != candidate_digest):
        return None
    import hmac as _hmac
    key = _gate_mac_key()
    recorded_mac = record.get("mac")
    if key is None or not isinstance(recorded_mac, str) or not _hmac.compare_digest(
            recorded_mac, _gate_record_mac(record, key)):
        return None
    value = record.get("deployInputPath")
    if not (isinstance(value, str) and value):
        return None
    # Security (2026-08-12): MAC + candidate-digest validity is not enough — the
    # path is meaningful only from a pass that is actually CURRENT.
    # gate_pass_is_current re-enforces freshness (clock-skew bound), the gated
    # risk class, the recorded deploy-input digest AND a clean worktree (with
    # the recorded artifact exempted). A MAC/digest-valid but stale, dirty or
    # non-gated record must not supply a deploy-input path.
    if not gate_pass_is_current(root):
        return None
    return value


RISK_ESCALATION_NAME = "risk-escalation.json"


def risk_escalation_path(root: Path) -> Path:
    return Path(root) / GATE_LEDGER_DIR / RISK_ESCALATION_NAME


def _read_ledger_leaf_norace(root: Path, relative: str):
    """Read `root/relative` with descriptor-relative no-follow traversal.

    Returns ``("ok", bytes)`` for a real regular in-checkout file,
    ``("missing", None)`` when a component or the leaf is genuinely absent
    after a clean no-follow walk, and ``("poison", None)`` when ANY component
    (parent or leaf) is a symlink / the leaf is non-regular / it cannot be
    read. Route finding r80: reading only the LEAF's `is_symlink()` (the prior
    `load_risk_escalation`) let a symlinked PARENT (`.itd-memory/deploy-gate`
    or an ancestor) point at a directory without the entry — the leaf check
    passed, `exists()` was false, and a recorded operator escalation was
    silently dropped, downgrading a gated candidate to routine. This is the
    same no-follow parent traversal the ledger WRITER uses (r68). Windows
    fallback uses lexical parent-symlink checks, the stated limit."""
    import os
    import stat as _stat
    parts = Path(relative).parts
    if not parts:
        return ("poison", None)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    supports = (os.open in getattr(os, "supports_dir_fd", set())
                and hasattr(os, "O_DIRECTORY"))
    if not supports:
        target = Path(root)
        for part in parts[:-1]:
            target = target / part
            if target.is_symlink():
                return ("poison", None)
            if not target.exists():
                return ("missing", None)
        leaf = target / parts[-1]
        if leaf.is_symlink():
            return ("poison", None)
        try:
            if not leaf.exists():
                return ("missing", None)
            if not leaf.is_file():
                return ("poison", None)
            return ("ok", leaf.read_bytes())
        except OSError:
            return ("poison", None)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | nofollow
    try:
        current = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return ("poison", None)
    try:
        for part in parts[:-1]:
            try:
                following = os.open(part, directory_flags, dir_fd=current)
            except FileNotFoundError:
                return ("missing", None)
            except OSError:                  # ELOOP (symlink) or any refusal
                return ("poison", None)
            os.close(current)
            current = following
        try:
            fd = os.open(parts[-1], os.O_RDONLY | nofollow, dir_fd=current)
        except FileNotFoundError:
            return ("missing", None)
        except OSError:                      # symlinked leaf (ELOOP) etc.
            return ("poison", None)
        try:
            if not _stat.S_ISREG(os.fstat(fd).st_mode):
                os.close(fd)
                return ("poison", None)
            with os.fdopen(fd, "rb") as handle:
                return ("ok", handle.read())
        except OSError:
            try:
                os.close(fd)
            except OSError:
                pass
            return ("poison", None)
    finally:
        try:
            os.close(current)
        except OSError:
            pass


def load_risk_escalation(root: Path) -> dict:
    """Escalations a previous `check` declared for THIS checkout.

    Route finding r38: `check --data-sensitive yes` / `--migrations-dir` could
    escalate a candidate into a gated class, but the hook-facing `classify`
    recomputed risk from automatic signals only, so the mechanical hook treated
    the very same project as routine and let shipping commands through. The
    escalation is durable per checkout, so both interfaces see it.
    """
    # r58 + r80: a structurally poisoned escalation entry — a symlinked leaf
    # OR ANY symlinked PARENT, a directory, an unreadable or unparseable file —
    # must not silently DOWNGRADE the candidate to routine — the poison could
    # be exactly what hides an operator-declared escalation from the hook. Fail
    # closed by treating poison as a standing data-sensitive escalation
    # (escalate-only semantics preserved: poison can only gate, never un-gate).
    # The read walks every component no-follow (r80), so a symlinked
    # `.itd-memory/deploy-gate` ancestor pointing away from the entry is poison,
    # not a silent "missing".
    poisoned = {"kind": "itd-predeploy-risk-escalation-v1",
                "dataSensitive": True, "poisoned": True}
    status, raw = _read_ledger_leaf_norace(
        root, str(GATE_LEDGER_DIR / RISK_ESCALATION_NAME))
    if status == "missing":
        return {}
    if status != "ok" or raw is None:
        return poisoned
    try:
        record = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return poisoned
    return record if isinstance(record, dict) else poisoned


def record_risk_escalation(root: Path, *, data_sensitive: bool,
                           monetary: bool, migrations_dir: str | None) -> bool:
    """Persist an operator-declared escalation; never records a de-escalation.

    Route finding r58: a silently discarded persistence failure meant `check
    --data-sensitive yes` could validate a receipt while the hook-facing
    `classify` never saw the escalation and treated the checkout as routine.
    The caller must treat False as a BLOCKED check, and the write refuses
    symlinked/structurally poisoned ledger paths like the pass record does.
    """
    if not (data_sensitive or monetary or migrations_dir):
        return True                       # nothing to persist
    previous = load_risk_escalation(root)
    record = {
        "kind": "itd-predeploy-risk-escalation-v1",
        "dataSensitive": bool(previous.get("dataSensitive")) or data_sensitive,
        "monetary": bool(previous.get("monetary")) or monetary,
        "migrationsDir": migrations_dir or previous.get("migrationsDir"),
    }
    try:
        return _ledger_write_entry(
            root, RISK_ESCALATION_NAME, json.dumps(record, ensure_ascii=False))
    except OSError:
        return False


def merged_risk_signals(root: Path, *, data_sensitive_flag: str = "auto",
                        monetary_flag: str = "auto",
                        migrations_dir: str | None = None
                        ) -> tuple[bool, bool, bool]:
    """Automatic detection merged with declared escalation (never suppressed).

    Returns the `derive_risk_class` argument triple: data-sensitive, pending
    migrations, monetary.
    """
    declared = load_risk_escalation(root)
    data_sensitive = (detect_data_sensitive(root)
                      or data_sensitive_flag == "yes"
                      or bool(declared.get("dataSensitive")))
    monetary = (detect_monetary(root) or monetary_flag == "yes"
                or bool(declared.get("monetary")))
    declared_dir = declared.get("migrationsDir")
    pending = pending_migrations(root, migrations_dir) or pending_migrations(
        root, declared_dir if isinstance(declared_dir, str) else None)
    return data_sensitive, pending, monetary


def command_check(args: argparse.Namespace) -> int:
    root = Path(args.root)
    # r56/r58: an unresolvable root (missing directory, symlink cycle) can
    # prove nothing about the candidate — the answer is the typed BLOCKED,
    # never a crash and never a quiet routine pass.
    try:
        root_usable = root.is_dir()
    except OSError:
        root_usable = False
    if not root_usable:
        print(json.dumps({
            "status": "BLOCKED",
            "why": "the candidate root is not a resolvable directory "
                   "(missing, cyclic symlink, or unreadable), so no deploy "
                   "candidate can be derived from it",
            "fix": "Point --root at the real candidate checkout directory.",
        }, ensure_ascii=False))
        return 2
    # The trust anchor is FIXED to the installed methodology. It is
    # deliberately not configurable from the production CLI: a configurable
    # anchor is an attacker-supplied validator (route finding r11) — and it is
    # derived from the account database, not from HOME (route finding r53).
    installed_root = INSTALLED_ROOT_DEFAULT
    if installed_root is None:
        print(json.dumps({
            "status": "BLOCKED",
            "why": "the installed-methodology trust anchor cannot be "
                   "resolved from the OS account database, so no validator "
                   "or pass-record key can be trusted",
            "fix": "Run under a normal user account whose home directory "
                   "the OS can report (getpwuid / profile folder).",
        }, ensure_ascii=False))
        return 2
    try:
        inside_candidate = installed_root.resolve().is_relative_to(
            root.resolve())
    except (OSError, ValueError, RuntimeError):
        # RuntimeError: resolve() on a symlink cycle (route finding r56) —
        # an unresolvable root cannot prove containment, so fail closed
        inside_candidate = True
    if inside_candidate:
        print(json.dumps({
            "status": "BLOCKED",
            "why": "the installed methodology validator resolves INSIDE the "
                   "deploy candidate, so candidate-supplied validator code "
                   "would be gating itself (no independence)",
            "fix": "Run the gate from an installed methodology OUTSIDE the "
                   "candidate repository — the host anchor (default ~/.claude) "
                   "resolved from the account database, not a copy inside the "
                   "checkout. (r81: the anchor is fixed; there is no "
                   "--installed-root flag to point elsewhere.)",
        }, ensure_ascii=False))
        return 2
    # Detection always runs; explicit flags may only escalate a signal,
    # never suppress one the project itself declares (fail-closed merge). An
    # escalation is also persisted so the hook-facing `classify` sees the same
    # risk class the operator declared here (route finding r38). r58: a
    # persistence failure BLOCKS — otherwise the receipt validates while the
    # mechanical hook keeps treating the checkout as routine.
    if not record_risk_escalation(
        root,
        data_sensitive=args.data_sensitive == "yes",
        monetary=args.monetary == "yes",
        migrations_dir=args.migrations_dir,
    ):
        print(json.dumps({
            "status": "BLOCKED",
            "why": "the declared risk escalation could not be persisted for "
                   "the mechanical hook (ledger path is symlinked, poisoned "
                   "or unwritable), so the hook would classify this checkout "
                   "below the operator's declaration",
            "fix": "Make .itd-memory/deploy-gate a real writable directory "
                   "with no symlinked entries, then rerun the gate.",
        }, ensure_ascii=False))
        return 2
    data_sensitive, pending, monetary = merged_risk_signals(
        root,
        data_sensitive_flag=args.data_sensitive,
        monetary_flag=args.monetary,
        migrations_dir=args.migrations_dir,
    )
    risk_class = derive_risk_class(data_sensitive, pending, monetary)
    if risk_class in GATED_CLASSES and not worktree_clean(root):
        # Covers tracked content. Ignored artifacts are invisible to git by
        # design — that is why /deploy Step 0 item 5b constrains a gated
        # sync to `git archive HEAD` (tracked committed content only), so
        # changed ignored files cannot enter the deployed input either
        # (route finding r24).
        print(json.dumps({
            "status": "BLOCKED", "riskClass": risk_class,
            "why": "working tree is not clean, so the deployed TRACKED "
                   "content is not the exact reviewed HEAD candidate",
            "fix": "Commit or stash all changes so the deploy candidate is "
                   "exactly the reviewed single-parent HEAD, then rerun the "
                   "gate; ship gated deploys with `git archive HEAD` so "
                   "ignored local artifacts stay out of the deployed input.",
        }, ensure_ascii=False))
        return 2
    # Route finding r62: the digest is snapshotted BEFORE receipt validation
    # and re-derived after every subsequent step — a concurrent ref update
    # could otherwise get receipt-bound HEAD A approved while HEAD B is
    # archived and MAC-recorded as passed.
    initial_digest = derive_candidate_digest(root)
    receipt_status = "missing"
    if risk_class in GATED_CLASSES and args.receipt:
        # Gated deploys always validate at the high tier: a caller-selected
        # lower tier would accept receipts below the required
        # independent-review standard (route finding r14).
        receipt_status = validate_receipt(
            root, Path(args.receipt), args.unit_id, "high",
            installed_root=installed_root,
        )
    candidate_digest = derive_candidate_digest(root)
    if (initial_digest is None or candidate_digest is None
            or candidate_digest != initial_digest):
        print(json.dumps({
            "status": "BLOCKED", "riskClass": risk_class,
            "why": "the candidate moved while the gate was checking it "
                   "(HEAD/tree digest changed between the receipt "
                   "validation snapshot and the decision), so the receipt "
                   "no longer binds the candidate that would ship",
            "fix": "Stop concurrent ref updates in the checkout and rerun "
                   "the gate against a stable HEAD.",
        }, ensure_ascii=False))
        return 2
    override_record = None
    if args.override:
        override_record = load_override(
            Path(args.override), candidate_digest, installed_root)
        if override_record is None:
            print(json.dumps({
                "status": "BLOCKED",
                "why": "override record failed the canonical independence "
                       f"validation for the audited {OVERRIDE_OUTCOME} class "
                       "(shape, digest binding, confirmer, reason and typed "
                       "unavailability are all required)",
                "fix": "Mint it via itd_verification_loop.py mint-override "
                       "for the exact candidate digest printed by this "
                       "gate's `digest --root <repo>` subcommand; never "
                       "hand-write override records.",
            }, ensure_ascii=False))
            return 2
    decision = evaluate_gate(
        risk_class, receipt_status, override_record, candidate_digest
    )
    if not decision["allowed"]:
        print(json.dumps({
            "status": "BLOCKED", "riskClass": risk_class,
            "why": decision["why"], "fix": decision["fix"],
        }, ensure_ascii=False))
        return 2
    if risk_class in GATED_CLASSES:
        # Route finding r30: a gated class may only deploy an artifact this
        # gate itself produced. Without it the allow decision would cover
        # committed content while an arbitrary working directory (including
        # ignored, unreviewed files) is what actually ships.
        if not args.emit_deploy_input:
            print(json.dumps({
                "status": "BLOCKED", "riskClass": risk_class,
                "why": "a gated deploy candidate has no gate-produced "
                       "deploy input, so nothing binds what actually ships "
                       "to the reviewed candidate",
                "fix": "Rerun with --emit-deploy-input <path.tar> and ship "
                       "exactly that artifact; never rsync/tar the working "
                       "directory for a gated class.",
            }, ensure_ascii=False))
            return 2
        # Route finding r52: a relative destination was VALIDATED against
        # --root but WRITTEN relative to the process CWD, so the gate could
        # approve one location and emit into another. Resolve it against the
        # candidate root once, and use that path everywhere below.
        deploy_input = Path(args.emit_deploy_input)
        if not deploy_input.is_absolute():
            deploy_input = Path(root) / deploy_input
        # Route finding r42: an artifact written outside the checkout left the
        # pass record without a path, and the hook then had nothing to bind a
        # file transport to — a pass with no artifact identity is a pass that
        # authorizes shipping anything.
        relative_input = _relative_to_root(root, deploy_input)
        # Route finding r50: any path under the checkout was accepted, so
        # `--emit-deploy-input .git/HEAD` would have the gate itself overwrite
        # Git internals and still report ALLOWED.
        if relative_input is not None and (
                relative_input == ".git"
                or relative_input.startswith(".git/")):
            print(json.dumps({
                "status": "BLOCKED", "riskClass": risk_class,
                "why": "the deploy input destination points inside the Git "
                       "directory, where writing the archive would corrupt "
                       "the repository the candidate is derived from",
                "fix": "Emit the artifact to a normal path such as "
                       "--emit-deploy-input .itd-memory/deploy-input.tar.",
            }, ensure_ascii=False))
            return 2
        if relative_input is None:
            print(json.dumps({
                "status": "BLOCKED", "riskClass": risk_class,
                "why": "the deploy input destination is outside the candidate "
                       "repository, so the recorded pass could not name the "
                       "artifact the mechanical hook must enforce",
                "fix": "Emit the artifact inside the checkout, e.g. "
                       "--emit-deploy-input .itd-memory/deploy-input.tar, and "
                       "ship exactly that file.",
            }, ensure_ascii=False))
            return 2
        # Route finding r60: the destination must be gate-ownable — never a
        # symlink (whatever it resolves to) and never a TRACKED file, or the
        # gate would overwrite reviewed source content and report ALLOWED.
        try:
            destination_symlink = deploy_input.is_symlink()
        except OSError:
            destination_symlink = True
        if destination_symlink or _destination_is_tracked(
                root, relative_input):
            print(json.dumps({
                "status": "BLOCKED", "riskClass": risk_class,
                "why": "the deploy input destination is a symlink or a "
                       "tracked source file; the gate must not overwrite "
                       "reviewed candidate content with the archive",
                "fix": "Emit the artifact to an untracked regular path such "
                       "as --emit-deploy-input .itd-memory/deploy-input.tar.",
            }, ensure_ascii=False))
            return 2
        # r62: the artifact must belong to the SAME candidate the receipt
        # validated — re-derive after producing it, before recording the pass
        if derive_candidate_digest(root) != initial_digest:
            print(json.dumps({
                "status": "BLOCKED", "riskClass": risk_class,
                "why": "the candidate moved between receipt validation and "
                       "artifact production, so the emitted archive would "
                       "not be the reviewed candidate",
                "fix": "Stop concurrent ref updates in the checkout and "
                       "rerun the gate against a stable HEAD.",
            }, ensure_ascii=False))
            return 2
        emitted = emit_deploy_input(root, deploy_input)
        if emitted is None:
            print(json.dumps({
                "status": "BLOCKED", "riskClass": risk_class,
                "why": "the exact deploy input could not be produced from "
                       "the reviewed HEAD",
                "fix": "Run inside the candidate git repository with a "
                       "writable --emit-deploy-input path, then rerun.",
            }, ensure_ascii=False))
            return 2
        if derive_candidate_digest(root) != initial_digest:
            print(json.dumps({
                "status": "BLOCKED", "riskClass": risk_class,
                "why": "the candidate moved between artifact production and "
                       "pass recording, so the record would bless bytes the "
                       "receipt never covered",
                "fix": "Stop concurrent ref updates in the checkout and "
                       "rerun the gate against a stable HEAD.",
            }, ensure_ascii=False))
            return 2
        if not record_gate_pass(root, candidate_digest, risk_class, emitted,
                                deploy_input_path=deploy_input):
            print(json.dumps({
                "status": "BLOCKED", "riskClass": risk_class,
                "why": "the gate pass could not be recorded, so the "
                       "PreToolUse deploy hook cannot distinguish this "
                       "candidate from an ungated one",
                "fix": "Make .itd-memory/deploy-gate writable in the "
                       "candidate repository, then rerun the gate.",
            }, ensure_ascii=False))
            return 2
        print(json.dumps({
            "status": "ALLOWED", "riskClass": risk_class,
            "deployInput": str(deploy_input),
            "deployInputSha256": emitted,
            "deployInputSpec": "git archive --format=tar HEAD",
        }, ensure_ascii=False))
        return 0
    # Routine candidates keep the deployment floor: quiet success, no scan
    # summary and no artifact the caller did not ask for.
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pre-deploy independent review gate (U16)")
    sub = parser.add_subparsers(dest="command")
    check = sub.add_parser("check", help="gate one deploy candidate")
    check.add_argument("--root", required=True)
    check.add_argument("--data-sensitive", choices=("auto", "yes", "no"),
                       default="auto")
    check.add_argument("--migrations-dir", default=None,
                       help="pending-migrations dir; omitted = auto-scan "
                            "of the standard migration directories")
    check.add_argument("--monetary", choices=("auto", "yes", "no"),
                       default="auto")
    check.add_argument("--receipt", default=None)
    check.add_argument("--unit-id", default="DEPLOY")
    check.add_argument("--override", default=None)
    check.add_argument("--emit-deploy-input", default=None,
                       help="path for the gate-produced deploy artifact "
                            "(git archive HEAD); REQUIRED for gated classes "
                            "— its sha256 is the only shippable input the "
                            "gate vouches for")
    digest = sub.add_parser(
        "digest", help="print the derived exact-candidate digest for "
                       "mint-override binding")
    digest.add_argument("--root", required=True)
    classify = sub.add_parser(
        "classify", help="print the derived risk class and whether the "
                         "current candidate already passed the gate "
                         "(read-only; used by the PreToolUse deploy hook)")
    classify.add_argument("--root", required=True)
    # Same escalation inputs as `check`: the hook calls classify without them
    # and picks the declared escalation up from the durable record instead.
    classify.add_argument("--data-sensitive", choices=("auto", "yes", "no"),
                          default="auto")
    classify.add_argument("--monetary", choices=("auto", "yes", "no"),
                          default="auto")
    classify.add_argument("--migrations-dir", default=None)
    args = parser.parse_args(argv)
    if args.command == "digest":
        value = derive_candidate_digest(Path(args.root))
        if value is None:
            print(json.dumps({
                "status": "BLOCKED",
                "why": "candidate digest cannot be derived from the "
                       "repository HEAD",
                "fix": "Run inside a git repository with at least one "
                       "commit.",
            }, ensure_ascii=False))
            return 2
        print(value)
        return 0
    if args.command == "classify":
        root = Path(args.root)
        risk_class = derive_risk_class(*merged_risk_signals(
            root,
            data_sensitive_flag=getattr(args, "data_sensitive", "auto"),
            monetary_flag=getattr(args, "monetary", "auto"),
            migrations_dir=getattr(args, "migrations_dir", None),
        ))
        recorded = gate_pass_is_current(root)
        payload = {
            "riskClass": risk_class,
            "gated": risk_class in GATED_CLASSES,
            "gatePassRecorded": recorded,
        }
        if recorded:
            # The hook needs the artifact identity, not just a boolean: a pass
            # authorizes shipping THAT artifact, never the working tree
            # (route finding r41).
            artifact = recorded_deploy_input_path(root)
            if artifact:
                payload["deployInputPath"] = artifact
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    if args.command != "check":
        # Deployment floor: bare invocation is a quiet no-op, never a scan.
        return 0
    return command_check(args)


if __name__ == "__main__":
    sys.exit(main())
