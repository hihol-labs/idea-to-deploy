#!/usr/bin/env python3
"""Content digest of an installed ITD runtime directory (ITD simplification baseline, ADR-016).

sha256 over the sorted lines "<relative POSIX path>\\0<sha256 of the file>\\n" of every file, so two hosts can be
compared byte for byte without trusting the directory name.

A missing, unreadable or empty root is an error (exit status 1 with the reason), never the digest of nothing.

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


if __name__ == "__main__":
    for root in sys.argv[1:]:
        print(root, *tree_digest(root))
