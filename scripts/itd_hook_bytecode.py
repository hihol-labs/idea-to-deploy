#!/usr/bin/env python3
"""Install-time bytecode of the installed hooks and the modules they load (plan session 6, ADR-016).

scripts/sync-to-active.sh runs this with the interpreter that runs the hooks (on a Windows target, the Windows
python.exe) after it has copied skills/ and hooks/. Every Python hook script and module of the managed directories is
compiled into checked-hash bytecode at its standard __pycache__ place, any other .pyc there is removed, and the
inventory itd-bytecode.json is written into the install root. Checked-hash bytecode carries the hash of its source,
so the interpreter and hooks/claude-dispatch.py use it only for exactly that source and compile in memory otherwise;
nothing writes .pyc at run time (the rule of 1.109.1). A .pyc is current only when it is byte for byte the bytecode
this interpreter compiles from its source, header and code object alike (review a6: a valid header in front of another
code object is replaced, never inventoried); a current file is not rewritten, so a repeated sync changes nothing.

Usage: python -B itd_hook_bytecode.py <install root, e.g. ~/.claude> [--check]
  --check writes nothing: exit 0 when the bytecode and the inventory are current, 1 with the drift otherwise.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import marshal
import os
import sys
import tempfile
from pathlib import Path

INVENTORY_FILE = "itd-bytecode.json"
INVENTORY_KIND = "itd-hook-bytecode-v1"
# hooks/ and the directories of the modules the hooks load: the egress classifier, the review cache of the DoD
# gate, the predeploy classifier, the completion and state libraries.
MANAGED_DIRS = ("hooks", "skills/_shared", "skills/review/scripts", "skills/deploy/scripts")
CHECKED_HASH_PYC = 0b11


def is_python_source(path: Path) -> bool:
    if path.suffix == ".py":
        return True
    if path.suffix != ".sh":
        return False
    try:
        with path.open("rb") as handle:
            return b"python" in handle.readline()
    except OSError:
        return False


def sources(root: Path) -> list[Path]:
    found = []
    for relative in MANAGED_DIRS:
        directory = root / relative
        if directory.is_dir():
            found.extend(path for path in directory.iterdir() if path.is_file() and is_python_source(path))
    return sorted(found)


def expected_bytecode(source: Path, data: bytes) -> bytes:
    """The checked-hash .pyc of `data` as py_compile writes it for `source`: header, source hash, code object."""
    code = compile(data, str(source), "exec", dont_inherit=True)
    return (importlib.util.MAGIC_NUMBER + CHECKED_HASH_PYC.to_bytes(4, "little") + importlib.util.source_hash(data)
            + marshal.dumps(code))


def current_bytes(pyc: Path) -> bytes | None:
    try:
        return pyc.read_bytes()
    except OSError:
        return None


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def plan(root: Path) -> tuple[list[tuple[Path, Path]], dict[Path, bytes], list[Path]]:
    """(source, bytecode) pairs, the bytecode due for each source whose .pyc is missing or differs, and the .pyc files
    nobody owns. A source that does not compile raises ValueError."""
    pairs = [(source, Path(importlib.util.cache_from_source(str(source)))) for source in sources(root)]
    stale: dict[Path, bytes] = {}
    for source, pyc in pairs:
        try:
            expected = expected_bytecode(source, source.read_bytes())
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"cannot compile {relative(root, source)}: {exc}") from exc
        if current_bytes(pyc) != expected:
            stale[source] = expected
    owned = {pyc for _, pyc in pairs}
    extra = sorted(path for relative_dir in MANAGED_DIRS
                   for path in (root / relative_dir / "__pycache__").glob("*.pyc") if path not in owned)
    return pairs, stale, extra


def inventory(root: Path, pairs: list[tuple[Path, Path]]) -> str:
    files = [{"source": relative(root, source), "sourceSha256": sha256(source),
              "bytecode": relative(root, pyc), "bytecodeSha256": sha256(pyc)} for source, pyc in pairs]
    document = {"version": 1, "kind": INVENTORY_KIND, "cacheTag": sys.implementation.cache_tag,
                "magic": importlib.util.MAGIC_NUMBER.hex(), "files": files}
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def write_atomic(path: Path, data: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".itd-bytecode-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(temporary, path)
    except BaseException:
        os.unlink(temporary)
        raise


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("-") or len(argv) > 2 or (len(argv) == 2 and argv[1] != "--check"):
        print(__doc__.strip().splitlines()[-2], file=sys.stderr)
        return 2
    root, check = Path(argv[0]).absolute(), len(argv) == 2
    if not root.is_dir():
        print(f"ERROR install root not found: {root}", file=sys.stderr)
        return 2
    try:
        pairs, stale, extra = plan(root)
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    target = root / INVENTORY_FILE
    if check:
        drift = [f"stale or missing bytecode: {relative(root, source)}" for source in stale]
        drift += [f"bytecode without a managed source: {relative(root, path)}" for path in extra]
        if not drift:
            current = target.read_text(encoding="utf-8") if target.is_file() else ""
            if current != inventory(root, pairs):
                drift.append(f"{INVENTORY_FILE} differs from the installed bytecode")
        for line in drift:
            print(f"DRIFT {line}")
        if not drift:
            print(f"OK bytecode current: {len(pairs)} files ({sys.implementation.cache_tag})")
        return 1 if drift else 0
    for source, data in stale.items():
        pyc = Path(importlib.util.cache_from_source(str(source)))
        pyc.parent.mkdir(exist_ok=True)
        write_atomic(pyc, data)
    for path in extra:
        path.unlink()
    text = inventory(root, pairs)
    if not target.is_file() or target.read_text(encoding="utf-8") != text:
        write_atomic(target, text.encode("utf-8"))
    print(f"OK bytecode: {len(pairs)} files, {len(stale)} compiled, {len(extra)} removed "
          f"({sys.implementation.cache_tag})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
