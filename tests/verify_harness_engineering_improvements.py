#!/usr/bin/env python3
"""Focused oracle for the HE-001 Harness Engineering improvements."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TESTS = (
    "verify_harness_control_lifecycle.py",
    "verify_tool_trust_inventory.py",
    "verify_hook_output_contract.py",
)


def main() -> int:
    failed = 0
    for test in TESTS:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tests" / test)],
            cwd=str(ROOT), text=True, encoding="utf-8", errors="replace")
        if result.returncode:
            failed += 1
    print(f"HE-001 checks={len(TESTS)} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
