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


def unit_vcr(workspace: Path) -> dict:
    """Verified Completion Rate = verified units / activated units.

    v1.41.0. Source of truth: `*/.itd-memory/events.jsonl` lines with
    `type: "unit"` — `decision: "activated"` opens a unit, `decision:
    "verified"` closes it with passing verification (convention documented in
    docs/templates/itd-memory/events.example.jsonl; /task writes these events
    on unit start / verified finish). Counted by distinct unit `name` so
    re-activation after RECOVERY_REQUIRED doesn't inflate the denominator.
    VCR is null when no unit events exist yet.
    """
    activated: set[str] = set()
    verified: set[str] = set()
    for events_path in workspace.glob("*/.itd-memory/events.jsonl"):
        try:
            lines = events_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except Exception:
                continue
            if evt.get("type") != "unit":
                continue
            name = str(evt.get("name") or "")
            if not name:
                continue
            decision = str(evt.get("decision") or "").lower()
            if decision == "activated":
                activated.add(name)
            elif decision == "verified":
                verified.add(name)
    # Units verified without a recorded activation still count as activated —
    # a verified unit was by definition active at some point.
    activated |= verified
    return {
        "unitsActivated": len(activated),
        "unitsVerified": len(verified),
        "vcr": round(len(verified) / len(activated), 3) if activated else None,
    }


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
