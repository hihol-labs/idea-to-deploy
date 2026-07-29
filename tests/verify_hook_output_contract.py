#!/usr/bin/env python3
"""Behavioral and mutation tests for quiet-success/actionable-failure hooks."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "itd_harness_controls", ROOT / "skills/_shared/itd_harness_controls.py")
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def main() -> int:
    contract = json.loads((ROOT / "docs/HOOK_OUTPUT_CONTRACT.json").read_text())
    baseline = MOD.validate_hook_output(ROOT, contract)
    checks: list[tuple[str, bool]] = [
        ("pilot hooks are silent on success and actionable on findings", not baseline)
    ]
    mutated = copy.deepcopy(contract)
    mutated["defaults"]["failureRequiredMarkers"] = []
    checks.append(("missing WHY/FIX requirement fails closed",
                   bool(MOD.validate_hook_output(ROOT, mutated, execute=False))))
    mutated = copy.deepcopy(contract)
    del mutated["pilot"][0]["noiseControl"]["persistentRateLimit"]
    checks.append(("missing noise-control posture fails closed",
                   bool(MOD.validate_hook_output(ROOT, mutated, execute=False))))
    mutated = copy.deepcopy(contract)
    mutated["defaults"]["findingShape"] = "any-json"
    checks.append(("non-host-recognized JSON shape fails closed",
                   bool(MOD.validate_hook_output(ROOT, mutated, execute=False))))
    failed = 0
    for name, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name}"
              + (f"  — {'; '.join(baseline)}" if not passed and baseline else ""))
        failed += int(not passed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
