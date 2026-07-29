#!/usr/bin/env python3
"""Mutation tests for evidence-earned controls and bounded ablation."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills/_shared/itd_harness_controls.py"
SPEC = importlib.util.spec_from_file_location("itd_harness_controls", MODULE_PATH)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("all", "provenance", "ablation"), default="all")
    args = parser.parse_args()
    registry = json.loads((ROOT / "docs/HARNESS_CONTROL_REGISTRY.json").read_text())
    ablation = json.loads((ROOT / "docs/HARNESS_ABLATION.json").read_text())
    checks: list[tuple[str, bool]] = []
    baseline = MOD.validate_controls(ROOT, registry, ablation)
    checks.append(("current control lifecycle passes", not baseline))

    if args.phase in {"all", "provenance"}:
        mutated = copy.deepcopy(registry)
        mutated["controls"][0]["introducedBy"] = {
            "type": "model_opinion", "evidence": [], "failureClass": "unknown"
        }
        checks.append(("unearned control fails closed",
                       bool(MOD.validate_controls(ROOT, mutated, ablation))))
        mutated = copy.deepcopy(registry)
        mutated["controls"][0]["retireWhen"] = ""
        checks.append(("control without retirement condition fails closed",
                       bool(MOD.validate_controls(ROOT, mutated, ablation))))
        mutated = copy.deepcopy(registry)
        mutated["controls"][0]["reviewBy"] = "eventually"
        checks.append(("invalid review date fails closed",
                       bool(MOD.validate_controls(ROOT, mutated, ablation))))
        mutated = copy.deepcopy(registry)
        row = next(item for item in mutated["controls"]
                   if item["introducedBy"]["type"] == "repeated_independent_signals")
        row["introducedBy"]["evidence"][1]["independenceKey"] = \
            row["introducedBy"]["evidence"][0]["independenceKey"]
        checks.append(("non-independent repeated signals fail closed",
                       bool(MOD.validate_controls(ROOT, mutated, ablation))))
    mutated = copy.deepcopy(registry)
    row = next(item for item in mutated["controls"]
               if item["introducedBy"]["type"] == "repeated_independent_signals")
    row["introducedBy"]["evidence"][0]["sourceKind"] = "self_metric"
    checks.append(("control-owned self-metric cannot earn admission",
                   bool(MOD.validate_controls(ROOT, mutated, ablation))))
    mutated = copy.deepcopy(registry)
    mutated["controls"][0]["reviewBy"] = "2000-01-01"
    checks.append(("stale control review date fails closed",
                   bool(MOD.validate_controls(ROOT, mutated, ablation))))
    mutated = copy.deepcopy(registry)
    mutated["controls"][0]["undeclared"] = True
    checks.append(("undeclared control field fails closed",
                   bool(MOD.validate_controls(ROOT, mutated, ablation))))
    mutated = copy.deepcopy(registry)
    row = next(item for item in mutated["controls"]
               if item["introducedBy"]["type"] == "production_incident")
    row["introducedBy"]["evidence"] = [{
        "path": "README.md",
        "signalId": "self-asserted-incident",
        "independenceKey": "self-asserted-session",
        "sourceKind": "independent_observation",
        "contentSha256": row["introducedBy"]["evidence"][0]["contentSha256"],
    }]
    checks.append(("arbitrary file cannot self-assert a production incident",
                   bool(MOD.validate_controls(ROOT, mutated, ablation))))
    mutated = copy.deepcopy(registry)
    row = next(item for item in mutated["controls"]
               if item["introducedBy"]["type"] == "hard_external_constraint")
    row["introducedBy"]["evidence"][0]["sourceKind"] = "independent_observation"
    checks.append(("external constraint requires policy provenance",
                   bool(MOD.validate_controls(ROOT, mutated, ablation))))
    mutated = copy.deepcopy(registry)
    mutated["controls"][0]["introducedBy"]["evidence"][0]["contentSha256"] = "0" * 64
    checks.append(("control provenance is bound to evidence content",
                   bool(MOD.validate_controls(ROOT, mutated, ablation))))

    if args.phase in {"all", "ablation"}:
        mutated = copy.deepcopy(ablation)
        mutated["candidates"][0]["controlId"] = "unknown-control"
        checks.append(("orphan ablation candidate fails closed",
                       bool(MOD.validate_controls(ROOT, registry, mutated))))
        mutated = copy.deepcopy(ablation)
        mutated["candidates"][0]["disableEnv"] = {"BYPASS": "1"}
        checks.append(("disable-control drift fails closed",
                       bool(MOD.validate_controls(ROOT, registry, mutated))))
        checks.append(("enabled/disabled probes discriminate protected behavior",
                       not MOD.validate_ablation_discrimination(ROOT, ablation)))
        mutated = copy.deepcopy(ablation)
        mutated["candidates"][0]["benchmarkCommands"][0]["command"] = (
            "python3 benchmarks/harness-components/constant-score.py")
        checks.append(("non-discriminating ablation probe fails closed",
                       bool(MOD.validate_ablation_discrimination(ROOT, mutated))))

    failed = 0
    for name, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
        failed += int(not passed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
