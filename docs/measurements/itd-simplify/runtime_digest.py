#!/usr/bin/env python3
"""Content digest of an installed ITD runtime directory (ITD simplification baseline, ADR-016).

sha256 over the sorted lines "<relative POSIX path>\\0<sha256 of the file>\\n" of every file, so two hosts can be
compared byte for byte without trusting the directory name.

A missing, unreadable or empty root is an error (exit status 1 with the reason), never the digest of nothing; a call
without any root is a usage error (exit status 2), not an empty successful measurement.

Usage: python3 runtime_digest.py ~/.local/share/itd/runtime/<release>-<digest16> [more dirs ...]
"""
from __future__ import annotations

import hashlib
import os
import sys


def fail(error: OSError) -> None:
    raise error


def tree_digest(root: str) -> tuple[int, str]:
    if not os.path.isdir(root):
        raise SystemExit(f"not a directory: {root}")
    digest, count = hashlib.sha256(), 0
    for directory, subdirs, files in os.walk(root, onerror=fail):
        subdirs.sort()
        for name in sorted(files):
            path = os.path.join(directory, name)
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            with open(path, "rb") as handle:
                file_sha = hashlib.sha256(handle.read()).hexdigest()
            digest.update(relative.encode("utf-8") + b"\0" + file_sha.encode("ascii") + b"\n")
            count += 1
    if count == 0:
        raise SystemExit(f"no files under {root}")
    return count, digest.hexdigest()


def main(roots: list[str]) -> int:
    if not roots:
        print("usage: runtime_digest.py <runtime dir> [more dirs ...]", file=sys.stderr)
        return 2
    for root in roots:
        print(root, *tree_digest(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
