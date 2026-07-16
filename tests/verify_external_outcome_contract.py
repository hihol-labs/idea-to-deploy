#!/usr/bin/env python3
"""Adversarial contract proof for privacy-safe external outcome evidence."""
from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "itd_external_outcomes.py"
CONTRACT = ROOT / "docs" / "PRACTICAL_EFFECTIVENESS_CONTRACT.json"
SCHEMA = ROOT / "docs" / "external-validation" / "EXTERNAL_OUTCOME_SCHEMA.json"
REAL_INDEX = ROOT / "docs" / "evidence" / "external-outcomes" / "INDEX.json"
spec = importlib.util.spec_from_file_location("itd_external_outcomes", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("  OK   " if ok else " FAIL  ") + name + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def record(project_hex: str, operator_hex: str, verifier_hex: str,
           units: int = 10) -> dict:
    value = {
        "projectId": "proj_" + project_hex,
        "operatorId": "op_" + operator_hex,
        "repositoryClass": "external_private",
        "isMethodologyRepository": False,
        "synthetic": False,
        "fixture": False,
        "startedAt": "2026-06-14T19:30:00Z",
        "observedAt": "2026-07-15T19:30:00Z",
        "comparableUnits": units,
        "baseline": {
            "defectEscapeRate": 0.20,
            "falseCompletionRate": 0.10,
            "medianCycleMinutes": 120,
            "tokenUnitsPerVerifiedUnit": 100,
            "operatorFrictionRate": 0.20,
            "criticalRegressions": 0,
        },
        "followup": {
            "defectEscapeRate": 0.10,
            "falseCompletionRate": 0.05,
            "medianCycleMinutes": 100,
            "tokenUnitsPerVerifiedUnit": 90,
            "operatorFrictionRate": 0.10,
            "criticalRegressions": 0,
        },
        "sourceHashes": [{
            "artifactDigest": project_hex[0] * 64,
            "sha256": verifier_hex[0] * 64,
            "verifiedBy": "op_" + verifier_hex,
            "verifiedAt": "2026-07-15T19:35:00Z",
        }],
        "attestation": {
            "consent": True,
            "independentOperator": True,
            "authorAffiliated": False,
            "accurate": True,
            "recordDigest": "",
        },
        "privacy": {
            "containsPII": False,
            "containsSourceCode": False,
            "containsSecrets": False,
            "containsCustomerData": False,
        },
    }
    value["attestation"]["recordDigest"] = module.record_digest(value)
    return value


def resign(value: dict) -> None:
    value["attestation"]["recordDigest"] = module.record_digest(value)


def good_index() -> dict:
    return {
        "version": 1,
        "evidenceKind": "observed_external_outcome",
        "observedAt": "2026-07-15T19:30:00Z",
        "projects": [
            record("a1b2c3d4e5f6", "111111111111", "222222222222"),
            record("b1c2d3e4f5a6", "222222222222", "111111111111"),
            record("c1d2e3f4a5b6", "111111111111", "222222222222"),
        ],
    }


def rejected(name: str, mutate) -> None:
    value = good_index()
    mutate(value)
    result = module.evaluate(
        value, json.loads(CONTRACT.read_text(encoding="utf-8")),
        json.loads(SCHEMA.read_text(encoding="utf-8")),
        now=dt.datetime(2026, 7, 16, tzinfo=dt.timezone.utc),
    )
    check(name, not result["passed"], str(result))


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    policy = contract["externalEvidencePolicy"]
    check("schema mirrors frozen project threshold", policy["minimumIndependentProjects"] == 3)
    check("schema mirrors frozen operator threshold", policy["minimumIndependentOperators"] == 2)
    check("schema mirrors frozen unit threshold", policy["minimumComparableUnits"] == 30)
    check("schema mirrors frozen duration threshold", policy["minimumObservationDays"] == 30)
    check("schema is opt-in and forbids direct identifiers", schema["optIn"] is True
          and {"name", "email", "repositoryUrl", "repositoryPath", "sourceCode", "secret"}
          <= set(schema["privacy"]["forbiddenFields"]))
    result = module.evaluate(good_index(), contract, schema,
                             now=dt.datetime(2026, 7, 16, tzinfo=dt.timezone.utc))
    check("valid independent before/after evidence passes contract", result["passed"], str(result))

    rejected("methodology repository rejected",
             lambda x: (x["projects"][0].update(repositoryClass="methodology"), resign(x["projects"][0])))
    rejected("fixture rejected",
             lambda x: (x["projects"][0].update(fixture=True), resign(x["projects"][0])))
    rejected("synthetic record rejected",
             lambda x: (x["projects"][0].update(synthetic=True), resign(x["projects"][0])))
    rejected("author-affiliated self-report rejected",
             lambda x: (x["projects"][0]["attestation"].update(authorAffiliated=True), resign(x["projects"][0])))
    rejected("duplicate projects rejected",
             lambda x: (x["projects"][1].update(projectId=x["projects"][0]["projectId"]), resign(x["projects"][1])))
    rejected("duplicate operators below threshold rejected",
             lambda x: [row.update(operatorId="op_111111111111") or resign(row) for row in x["projects"]])
    rejected("insufficient comparable units rejected",
             lambda x: [row.update(comparableUnits=9) or resign(row) for row in x["projects"]])
    rejected("short observation rejected",
             lambda x: (x["projects"][0].update(startedAt="2026-06-20T19:30:00Z"), resign(x["projects"][0])))
    rejected("stale evidence rejected",
             lambda x: [row.update(observedAt="2025-12-01T00:00:00Z", startedAt="2025-10-01T00:00:00Z") or resign(row) for row in x["projects"]])
    rejected("evidence before freeze rejected",
             lambda x: [row.update(observedAt="2026-07-15T19:00:00Z", startedAt="2026-06-01T00:00:00Z") or resign(row) for row in x["projects"]])
    rejected("unverifiable source hash rejected",
             lambda x: (x["projects"][0]["sourceHashes"][0].update(sha256="bad"), resign(x["projects"][0])))
    rejected("self-verified provenance rejected",
             lambda x: (x["projects"][0]["sourceHashes"][0].update(verifiedBy=x["projects"][0]["operatorId"]), resign(x["projects"][0])))
    rejected("tampered record digest rejected",
             lambda x: x["projects"][0]["followup"].update(defectEscapeRate=0.01))
    rejected("PII field rejected",
             lambda x: (x["projects"][0].update(email="operator@example.invalid"), resign(x["projects"][0])))
    rejected("critical regression rejected",
             lambda x: (x["projects"][0]["followup"].update(criticalRegressions=1), resign(x["projects"][0])))
    rejected("primary metric regression rejected",
             lambda x: (x["projects"][0]["followup"].update(defectEscapeRate=0.30), resign(x["projects"][0])))

    with tempfile.TemporaryDirectory(prefix="itd-external-contract-") as td:
        root = Path(td)
        index = root / "INDEX.json"
        index.write_text(json.dumps(good_index(), indent=2) + "\n", encoding="utf-8")
        exported = root / "export.json"
        run = subprocess.run(
            [sys.executable, str(SCRIPT), "export", "--index", str(index), "--out", str(exported)],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
        check("privacy-safe validated export succeeds", run.returncode == 0 and exported.is_file(),
              (run.stdout + run.stderr)[-600:])
        export_data = json.loads(exported.read_text(encoding="utf-8")) if exported.is_file() else {}
        check("export has no forbidden direct-identifier fields",
              not module.forbidden_paths(export_data), str(module.forbidden_paths(export_data)))
        missing = subprocess.run(
            [sys.executable, str(SCRIPT), "evaluate", "--index", str(root / "missing.json")],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
        missing_out = (missing.stdout or "") + (missing.stderr or "")
        check("missing real evidence fails with WHY/FIX",
              missing.returncode != 0 and "WHY:" in missing_out and "FIX:" in missing_out, missing_out)

    check("real evidence index remains absent/pending for PE5-008", not REAL_INDEX.exists())
    print("METRICS " + json.dumps({
        "positiveContracts": 1,
        "adversarialRejections": 16,
        "privacyFields": len(schema["privacy"]["forbiddenFields"]),
        "realEvidencePresent": REAL_INDEX.exists(),
    }, sort_keys=True))
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print("ALL PASS — external outcome contract is opt-in, privacy-safe and fail-closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
