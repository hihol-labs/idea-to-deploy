#!/usr/bin/env python3
"""itd_contract_dir.py - print where a checkout keeps a contract: `docs` in the Idea to Deploy methodology
repository, `.itd` in every other project (INSTALL-OWNED-1).

The methodology repository is recognized by its parsed .claude-plugin/plugin.json: a JSON object whose top-level
"name" is "idea-to-deploy". A missing, unreadable or malformed manifest, a nested or differently cased name, or
any other value means `.itd`. With contract names, `docs` is printed only when every named file exists under
docs/ of that repository (the docs contract is used only when it exists), otherwise `.itd`. Read-only.

Usage: itd_contract_dir.py [--root DIR] [CONTRACT_NAME ...]   (default root: the current directory)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

METHODOLOGY_NAME = "idea-to-deploy"


def is_methodology(root: Path) -> bool:
    try:
        manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(manifest, dict) and manifest.get("name") == METHODOLOGY_NAME


def contract_dir(root: Path, contracts: list[str] | tuple[str, ...] = ()) -> str:
    if not is_methodology(root):
        return ".itd"
    for name in contracts:  # plain file names only; anything else is not a contract of this repository
        if not name or "/" in name or "\\" in name or not (root / "docs" / name).is_file():
            return ".itd"
    return "docs"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="itd_contract_dir.py", description=__doc__.split("\n", 1)[0])
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("contracts", nargs="*")
    args = ap.parse_args(argv[1:])
    print(contract_dir(args.root, args.contracts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
