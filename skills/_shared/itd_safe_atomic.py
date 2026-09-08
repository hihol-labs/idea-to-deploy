"""Small hardened atomic replacement helper for mutable local ledgers."""
from __future__ import annotations

import os
import secrets
import json
import stat
from pathlib import Path
from contextlib import contextmanager


def _link_or_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


@contextmanager
def _posix_parent(path: Path):
    """Hold the real parent directory while operating on its leaf by dir_fd."""
    path = path.absolute()
    if not path.is_absolute() or not path.name or ".." in path.parts:
        raise RuntimeError("anchored operation needs an absolute leaf path")
    flags = os.O_RDONLY | int(getattr(os, "O_DIRECTORY", 0)) | int(getattr(os, "O_NOFOLLOW", 0))
    fd = os.open(path.anchor, flags)
    try:
        for part in path.parent.parts[1:]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd, path.name
    finally:
        os.close(fd)


@contextmanager
def _posix_namespace_parent(root: Path, relative: Path):
    """Open/create every namespace directory from one retained root fd chain."""
    if (not root.is_absolute() or ".." in root.parts or relative.is_absolute()
            or ".." in relative.parts or not relative.parts):
        raise RuntimeError("unsafe anchored namespace")
    flags = os.O_RDONLY | int(getattr(os, "O_DIRECTORY", 0)) | int(getattr(os, "O_NOFOLLOW", 0))
    fd = os.open(root.anchor, flags)
    try:
        for index, part in enumerate(root.parts[1:] + relative.parts[:-1]):
            try:
                child = os.open(part, flags, dir_fd=fd)
            except FileNotFoundError:
                if index < len(root.parts) - 1:
                    raise
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                os.fsync(fd)
                child = os.open(part, flags, dir_fd=fd)
            os.close(fd); fd = child
        yield fd, relative.name
    finally:
        os.close(fd)


def _win():
    import importlib.util
    candidate = Path(__file__).with_name("itd_safe_atomic_windows.py")
    spec = importlib.util.spec_from_file_location("itd_safe_atomic_windows", candidate)
    if spec is None or spec.loader is None:
        raise RuntimeError("Windows anchored I/O backend is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.backend()


def _private_fd(fd: int, label: str = "atomic temporary file") -> None:
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or (hasattr(os, "getuid") and info.st_uid != os.getuid())):
        raise RuntimeError(f"{label} is not private and regular")


def _snapshot_at(parent_fd: int, leaf: str, max_bytes: int,
                 *, equals: bytes | None = None) -> bytes | bool:
    before = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode):
        raise RuntimeError("snapshot is not a regular file")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = os.open(leaf, flags, dir_fd=parent_fd)
    try:
        opened = os.fstat(fd)
        fields = lambda value: (value.st_dev, value.st_ino, value.st_size,
                                value.st_mtime_ns, value.st_ctime_ns)
        if not stat.S_ISREG(opened.st_mode) or fields(opened) != fields(before):
            raise RuntimeError("snapshot changed while opening")
        if equals is not None and opened.st_size != len(equals):
            return False
        if opened.st_size > max_bytes:
            raise RuntimeError("snapshot exceeds read bound")
        chunks, size = [], 0
        while True:
            chunk = os.read(fd, min(65536, max_bytes + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > max_bytes:
                raise RuntimeError("snapshot exceeds read bound")
        if fields(os.fstat(fd)) != fields(opened) or size != opened.st_size:
            raise RuntimeError("snapshot changed during read")
        data = b"".join(chunks)
        return data == equals if equals is not None else data
    finally:
        os.close(fd)


def atomic_replace_bytes(path: Path, content: bytes) -> None:
    """Durably replace ``path`` without following or reusing a temp pathname."""
    if os.name == "nt":
        return _win().atomic_replace_bytes(path, content)
    nofollow = int(getattr(os, "O_NOFOLLOW", 0))
    with _posix_parent(path) as (parent_fd, leaf):
        tmp = None
        fd = None
        try:
            for _ in range(32):
                candidate = f".{leaf}.{secrets.token_hex(16)}.tmp"
                try:
                    fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow, 0o600, dir_fd=parent_fd)
                    tmp = candidate; break
                except FileExistsError: continue
            if fd is None or tmp is None: raise RuntimeError("could not create exclusive temporary file")
            _private_fd(fd)
            offset = 0
            while offset < len(content):
                n = os.write(fd, content[offset:])
                if n <= 0: raise OSError("atomic temporary write made no progress")
                offset += n
            os.fsync(fd); os.close(fd); fd = None
            os.replace(tmp, leaf, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            os.fsync(parent_fd); tmp = None
        finally:
            if fd is not None: os.close(fd)
            if tmp is not None:
                try: os.unlink(tmp, dir_fd=parent_fd)
                except FileNotFoundError: pass


def safe_namespace_path(root: Path, relative: Path) -> Path:
    """Resolve a relative child while rejecting existing symlink/junction hops."""
    if relative.is_absolute() or relative.drive or relative.anchor or ".." in relative.parts:
        raise RuntimeError("namespace child must be a contained relative path")
    root = root.absolute()
    if _link_or_reparse(root.lstat()) or not root.is_dir():
        raise RuntimeError("namespace root is unsafe")
    current = root
    for part in relative.parts:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if _link_or_reparse(info):
            raise RuntimeError(f"namespace contains a symlink/junction component: {current}")
    return current


def write_immutable_bytes(path: Path, content: bytes, *, root: Path) -> str:
    """Create a durable immutable child: ``created``, ``existing-same``, or ``collision``."""
    if path.is_absolute() or path.drive or path.anchor or ".." in path.parts or not path.parts:
        raise RuntimeError("immutable child must be a contained relative path")
    if os.name == "nt":
        return _win().write_immutable_bytes(path, content, root=root)
    if os.name != "nt":
        root = root.absolute()
        with _posix_namespace_parent(root, path) as (parent_fd, leaf):
            try:
                same = _snapshot_at(parent_fd, leaf, len(content), equals=content)
            except FileNotFoundError:
                pass
            else:
                return "existing-same" if same else "collision"
            temp=None; fd=None
            try:
                for _ in range(32):
                    candidate=f".{leaf}.{secrets.token_hex(16)}.tmp"
                    try:
                        fd=os.open(candidate,os.O_WRONLY|os.O_CREAT|os.O_EXCL|int(getattr(os,"O_NOFOLLOW",0)),0o600,dir_fd=parent_fd); temp=candidate; break
                    except FileExistsError: continue
                if fd is None: raise RuntimeError("could not create immutable private temporary file")
                _private_fd(fd)
                offset=0
                while offset<len(content):
                    n=os.write(fd,content[offset:])
                    if n<=0: raise OSError("immutable write made no progress")
                    offset+=n
                os.fsync(fd); os.close(fd); fd=None
                try: os.link(temp,leaf,src_dir_fd=parent_fd,dst_dir_fd=parent_fd)
                except FileExistsError:
                    same = _snapshot_at(parent_fd, leaf, len(content), equals=content)
                    return "existing-same" if same else "collision"
                os.fsync(parent_fd); os.unlink(temp,dir_fd=parent_fd); os.fsync(parent_fd); temp=None
                return "created"
            finally:
                if fd is not None: os.close(fd)
                if temp is not None:
                    try: os.unlink(temp,dir_fd=parent_fd)
                    except FileNotFoundError: pass


def read_regular_snapshot(path: Path, max_bytes: int, *, root: Path | None = None) -> bytes:
    """Bounded stable regular-file read, anchored to its held parent on POSIX."""
    if root is not None:
        path = safe_namespace_path(root, path)
    if os.name == "nt":
        return _win().read_regular_snapshot(path, max_bytes)
    with _posix_parent(path) as (parent_fd, leaf):
        return _snapshot_at(parent_fd, leaf, max_bytes)


LEDGER_SNAPSHOT_MAX_BYTES = 64 * 1024 * 1024


def read_ledger_snapshot(path: Path, max_bytes: int = LEDGER_SNAPSHOT_MAX_BYTES) -> bytes | None:
    """Anchored no-follow bounded read of one ledger file; ``None`` when absent.

    Every transition-authoritative read of GOAL.json, STATE.json, events.jsonl
    or a recovery record goes through here (Sol-a11/a12): the leaf is checked
    with lstat first, then every directory on the way and the leaf are opened
    from a held parent without following links, so a symlink, junction or FIFO
    swapped in at the path is refused instead of being read through or
    blocking.  A missing file is the only silent outcome.
    """
    path = Path(path).absolute()
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    reparse = bool(getattr(before, "st_file_attributes", 0) & 0x400)
    if stat.S_ISLNK(before.st_mode) or reparse or not stat.S_ISREG(before.st_mode):
        raise RuntimeError(f"ledger {path.name} is not a regular no-link file")
    return read_regular_snapshot(path, max_bytes)


def ledger_events(path: Path) -> list[dict]:
    """Parse events.jsonl fail-closed: one JSON object per newline-terminated line.

    A partial final record or a malformed line makes the append-only ledger
    ambiguous; authoritative readers must refuse rather than silently skip
    the record and reason from an earlier state (Sol-a12).
    """
    raw = read_ledger_snapshot(path)
    if raw is None:
        return []
    if raw and not raw.endswith(b"\n"):
        raise RuntimeError(f"{Path(path).name} has a partial final record; preserved without append")
    events: list[dict] = []
    for index, line in enumerate(raw.split(b"\n")[:-1], start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError(f"{Path(path).name} record {index} is malformed; refusing an ambiguous ledger") from exc
        if not isinstance(value, dict):
            raise RuntimeError(f"{Path(path).name} record {index} is not an object; refusing an ambiguous ledger")
        events.append(value)
    return events


def durable_append_bytes(path: Path, content: bytes, *, root: Path | None = None) -> None:
    """Append and persist canonical JSONL bytes before a dependent state write."""
    if root is not None:
        path = safe_namespace_path(root, path)
    if os.name == "nt":
        return _win().durable_append_bytes(path, content)
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise RuntimeError(f"append destination directory is unsafe: {path.parent}")
    try:
        if path.is_symlink():
            raise RuntimeError("append destination may not be a symlink")
    except OSError as exc:
        raise RuntimeError("append destination is unreadable") from exc
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
    with _posix_parent(path) as (parent_fd, leaf):
        fd = os.open(leaf, flags, 0o600, dir_fd=parent_fd)
        try:
            # The destination gets the same private-regular rule as the
            # temporaries: a hard link planted at a ledger path must never
            # redirect a trusted append into another file (Sol-a7).
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or (hasattr(os, "getuid") and info.st_uid != os.getuid())):
                raise RuntimeError("append destination is not a private regular file")
            offset=0
            while offset<len(content):
                n=os.write(fd,content[offset:])
                if n<=0: raise OSError("durable append made no progress")
                offset+=n
            os.fsync(fd)
        finally: os.close(fd)
        os.fsync(parent_fd)


@contextmanager
def open_private_lock_fd(path: Path):
    """Yield an fd for a private lock file, opened anchored and no-follow.

    The bounded cross-process STATE lock used to be taken through
    ``Path.open("a+b")`` on a reconstructed pathname (Sol-a13): a symlink,
    junction or second hard link planted at ``.STATE.write.lock`` moved both
    the lock and its initialising byte into a foreign file, while every writer
    still believed the STATE write was serialised.  The leaf is checked with
    lstat for a named refusal, then opened from a held parent without
    following links and proved regular, single-link and owned.
    """
    path = Path(path).absolute()
    try:
        before = path.lstat()
    except FileNotFoundError:
        before = None
    if before is not None and (_link_or_reparse(before) or not stat.S_ISREG(before.st_mode)):
        raise RuntimeError(f"lock {path.name} is not a regular no-link file")
    if os.name == "nt":
        with _win().open_private_lock_fd(path) as fd:
            yield fd
        return
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
    with _posix_parent(path) as (parent_fd, leaf):
        fd = os.open(leaf, flags, 0o600, dir_fd=parent_fd)
        try:
            _private_fd(fd, f"lock {path.name}")
            yield fd
        finally:
            os.close(fd)


def durable_unlink(path: Path) -> None:
    """Remove a recovery marker and persist that removal."""
    if os.name == "nt":
        return _win().durable_unlink(path)
    try:
        if path.is_symlink():
            raise RuntimeError("recovery marker may not be a symlink")
        with _posix_parent(path) as (parent_fd, leaf):
            os.unlink(leaf, dir_fd=parent_fd); os.fsync(parent_fd)
    except FileNotFoundError: return
