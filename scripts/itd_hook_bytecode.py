#!/usr/bin/env python3
"""Install-time bytecode of the installed hooks and the modules they load (plan session 6, ADR-016).

scripts/sync-to-active.sh runs this with the interpreter that runs the hooks (on a Windows target, the Windows
python.exe) after it has copied skills/ and hooks/. Every Python hook script and module of the managed directories is
compiled into checked-hash bytecode at its standard __pycache__ place, any other .pyc there is removed, and the
inventory itd-bytecode.json is written into the install root. Checked-hash bytecode carries the hash of its source,
so the interpreter and hooks/claude-dispatch.py use it only for exactly that source and compile in memory otherwise;
nothing writes .pyc at run time (the rule of 1.109.1). A file that is already valid is not rewritten, so a repeated
sync changes nothing.

Usage: python -B itd_hook_bytecode.py <install root, e.g. ~/.claude> [--check]
  --check writes nothing: exit 0 when the bytecode and the inventory are current, 1 with the drift otherwise.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import py_compile
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


def valid_bytecode(pyc: Path, source: bytes) -> bool:
    try:
        header = pyc.read_bytes()[:16]
    except OSError:
        return False
    return (len(header) == 16 and header[:4] == importlib.util.MAGIC_NUMBER
            and int.from_bytes(header[4:8], "little") == CHECKED_HASH_PYC
            and header[8:16] == importlib.util.source_hash(source))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def plan(root: Path) -> tuple[list[tuple[Path, Path]], list[Path], list[Path]]:
    """(source, bytecode) pairs, the pairs whose bytecode is missing or stale, and the .pyc files nobody owns."""
    pairs = [(source, Path(importlib.util.cache_from_source(str(source)))) for source in sources(root)]
    stale = [source for source, pyc in pairs if not valid_bytecode(pyc, source.read_bytes())]
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


def write_atomic(path: Path, text: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".itd-bytecode-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
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
    pairs, stale, extra = plan(root)
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
    for source in stale:
        try:
            py_compile.compile(str(source), cfile=importlib.util.cache_from_source(str(source)), doraise=True,
                               invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)
        except py_compile.PyCompileError as exc:
            print(f"ERROR cannot compile {relative(root, source)}: {exc.msg}", file=sys.stderr)
            return 1
    for path in extra:
        path.unlink()
    text = inventory(root, pairs)
    if not target.is_file() or target.read_text(encoding="utf-8") != text:
        write_atomic(target, text)
    print(f"OK bytecode: {len(pairs)} files, {len(stale)} compiled, {len(extra)} removed "
          f"({sys.implementation.cache_tag})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
