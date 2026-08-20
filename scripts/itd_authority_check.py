#!/usr/bin/env python3
"""Byte-parity check of a review-authority snapshot against the repository.

LPD002-A8. The pre-PR producer runs from a snapshot OUTSIDE the repository
(`~/.cache/itd-review-authority/<id>/`) and does `sys.path.insert(HERE)`, so it
judges candidates with the snapshot's OWN modules. A snapshot minted before a
gate change silently judges with the OLD gate (measured on R5: the pre-R5
snapshot would have reproduced the exact circle R5 removed). This check makes
the drift visible and fail-closed BEFORE a producer receipt is trusted:

  python3 scripts/itd_authority_check.py --snapshot ~/.cache/itd-review-authority/<id>

Exit 0 - every snapshot module and policy file is byte-identical to
`skills/_shared/` in the repository (quiet success). Exit 1 - at least one
file diverges or is missing; each divergence prints path + WHY + FIX. Exit 2 -
input problems (missing snapshot dir, not a repository). No arguments is a
usage error, never an implicit scan. Signing material (`*.key`,
`producer-keyring.json`, `__pycache__`) is deliberately exempt: keys are
snapshot-local by design and carry no gate behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

EXEMPT_SUFFIXES = (".key",)
EXEMPT_NAMES = {"producer-keyring.json", "__pycache__"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", required=True, type=Path,
                        help="authority snapshot directory")
    parser.add_argument("--repo", type=Path, default=Path("."),
                        help="repository root (default: cwd)")
    args = parser.parse_args(argv)
    snapshot = args.snapshot.expanduser()
    shared = args.repo / "skills" / "_shared"
    if not snapshot.is_dir():
        print(f"ERROR {snapshot}: snapshot directory does not exist | "
              "FIX: pass the minted authority directory")
        return 2
    if not shared.is_dir():
        print(f"ERROR {shared}: not a repository root | "
              "FIX: run from the repository or pass --repo")
        return 2
    divergent = 0
    compared = 0
    for entry in sorted(snapshot.iterdir()):
        if entry.name in EXEMPT_NAMES or entry.suffix in EXEMPT_SUFFIXES:
            continue
        if not entry.is_file():
            continue
        counterpart = shared / entry.name
        if not counterpart.is_file():
            divergent += 1
            compared += 1
            print(f"DIVERGED {entry.name}: present in the snapshot but absent "
                  "from skills/_shared | WHY: the producer would judge with a "
                  "module the reviewed tree does not carry | FIX: re-mint the "
                  "snapshot from the merged main")
            continue
        compared += 1
        if sha256(entry) != sha256(counterpart):
            divergent += 1
            print(f"DIVERGED {entry.name}: snapshot bytes differ from "
                  "skills/_shared | WHY: the snapshot freezes gate behavior at "
                  "minting time - a candidate would be judged by the OLD gate | "
                  "FIX: re-mint the snapshot from the merged main "
                  "(copy skills/_shared modules and policies; keep the signing "
                  "key and keyring unchanged)")
    # The other direction: a module or policy added to skills/_shared after
    # minting would be invisible to a snapshot-only walk - the producer would
    # judge WITHOUT it while parity claimed byte-identity (checker r2 finding).
    snapshot_names = {e.name for e in snapshot.iterdir() if e.is_file()}
    for counterpart in sorted(shared.iterdir()):
        if not counterpart.is_file():
            continue
        if counterpart.suffix not in (".py", ".json"):
            continue
        if counterpart.name in EXEMPT_NAMES:
            continue
        if counterpart.name not in snapshot_names:
            divergent += 1
            print(f"MISSING {counterpart.name}: present in skills/_shared but "
                  "absent from the snapshot | WHY: the producer would judge "
                  "without a module the reviewed gate carries | FIX: re-mint "
                  "the snapshot from the merged main")
    if compared == 0 and divergent == 0:
        print(f"ERROR {snapshot}: nothing comparable found | FIX: point "
              "--snapshot at a minted authority directory")
        return 2
    return 1 if divergent else 0


if __name__ == "__main__":
    sys.exit(main())
