#!/usr/bin/env python3
"""Collect harness-efficiency metrics across an idea-to-deploy workspace.

PFO plugin-native port (Wave 2, item 17). Lets the methodology be improved by
numbers, not impressions. Scans every `*/.itd-memory/STATE.json` under a workspace
directory and aggregates pass-rates, blocked/failed counts, and artifact debt.
Ported and adapted from product-factory-os `scripts/pfo_metrics.py`.

Usage:
  python3 scripts/itd_metrics.py path/to/workspace          # JSON to stdout
  python3 scripts/itd_metrics.py path/to/workspace --markdown
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEPLOY_READY = "READY_FOR_DEPLOY"
DEPLOYED = "DEPLOYED"


import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "_shared"))
import itd_unit_lifecycle as LIFECYCLE  # noqa: E402


def unit_vcr(workspace: Path) -> dict:
    """Verified Completion Rate по ЖИЗНЕННЫМ ЦИКЛАМ юнитов.

    Семантика больше не дублируется здесь: единственный источник правды —
    skills/_shared/itd_unit_lifecycle.py (S10-LEDGER). Считать по множеству
    имён было неверно: один id принадлежит разным юнитам разных леджеров, а
    `blocked` — легитимный терминал, не промах верификации.
    """
    keys = ("unitsBlocked", "unitsOpen", "unitsWip", "unitsExcluded",
            "unattributedEvents")
    total = {"unitsActivated": 0, "unitsVerified": 0, "vcr": None}
    total.update({k: 0 for k in keys})
    activated = verified = denominator = 0
    mems = list(sorted(workspace.glob("*/.itd-memory")))
    own = workspace / ".itd-memory"
    if own.is_dir():
        mems.append(own)
    for mem in mems:
        lc = LIFECYCLE.build(mem)
        activated += lc["lifecyclesTotal"]
        verified += lc["lifecyclesVerified"]
        denominator += lc["lifecyclesTotal"] - lc["lifecyclesExcluded"] - lc["lifecyclesWip"]
        # Счётчики дрейфа обязаны доходить до вызывающего, а не оставаться
        # внутри (ревьюер 2026-08-17, spec-compliance): без них потребитель не
        # видит ни неатрибутированных строк, ни открытых циклов.
        total["unitsBlocked"] += lc["lifecyclesBlocked"]
        total["unitsOpen"] += lc["lifecyclesOpen"]
        total["unitsWip"] += lc["lifecyclesWip"]
        total["unitsExcluded"] += lc["lifecyclesExcluded"]
        total["unattributedEvents"] += lc["unattributedEvents"]
    total["unitsActivated"] = activated
    total["unitsVerified"] = verified
    total["vcr"] = round(verified / denominator, 3) if denominator else None
    return total

def collect(workspace: Path) -> dict:
    projects: list[dict] = []
    for state_path in workspace.glob("*/.itd-memory/STATE.json"):
        try:
            projects.append(json.loads(state_path.read_text(encoding="utf-8")))
        except Exception:
            continue

    def gate_passes(item: dict) -> int:
        return sum(1 for v in item.get("gateResults", {}).values() if v == "passed")

    def gate_total(item: dict) -> int:
        return sum(1 for v in item.get("gateResults", {}).values() if v not in ("", "n/a"))

    total_pass = sum(gate_passes(p) for p in projects)
    total_gates = sum(gate_total(p) for p in projects)

    return {
        "projectCount": len(projects),
        "deployReadyCount": sum(1 for p in projects if p.get("currentStage") == DEPLOY_READY),
        "deployedCount": sum(1 for p in projects if p.get("currentStage") == DEPLOYED),
        "blockedCount": sum(1 for p in projects if p.get("blockers")),
        "failedGateCount": sum(len(p.get("failedValidations", [])) for p in projects),
        "verificationEvents": sum(len(p.get("verificationHistory", [])) for p in projects),
        "gatePassRate": round(total_pass / total_gates, 3) if total_gates else None,
        "openArtifactDebt": sum(len(p.get("artifacts", [])) for p in projects),
        **unit_vcr(workspace),
    }


def as_markdown(m: dict) -> str:
    rows = "\n".join(f"| {k} | {v} |" for k, v in m.items())
    return f"# idea-to-deploy workspace metrics\n\n| Metric | Value |\n|---|---|\n{rows}\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect idea-to-deploy workspace metrics.")
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--markdown", action="store_true", help="emit a Markdown table instead of JSON")
    args = parser.parse_args()

    metrics = collect(args.workspace)
    print(as_markdown(metrics) if args.markdown else json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
