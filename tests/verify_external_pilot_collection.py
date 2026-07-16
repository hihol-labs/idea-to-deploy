#!/usr/bin/env python3
"""Adversarial proof for the local external-pilot raw ledger and aggregator."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "itd_external_pilot.py"
OUTCOMES = ROOT / "scripts" / "itd_external_outcomes.py"
CONTRACT = ROOT / "docs" / "PRACTICAL_EFFECTIVENESS_CONTRACT.json"
SCHEMA = ROOT / "docs" / "external-validation" / "EXTERNAL_OUTCOME_SCHEMA.json"
RAW_SCHEMA = ROOT / "docs" / "external-validation" / "PILOT_UNIT_SCHEMA.json"
FAILURES: list[str] = []


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


outcomes = load_module("itd_external_outcomes", OUTCOMES)


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("  OK   " if ok else " FAIL  ") + name + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], cwd=str(ROOT), capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=30,
    )


def append(ledger: Path, phase: str, comparison: str, start: str, finish: str,
           defects: int, false_completions: int, tokens: int, friction: int) -> subprocess.CompletedProcess[str]:
    return run(
        "append", "--ledger", str(ledger), "--phase", phase,
        "--comparison-id", comparison, "--started-at", start,
        "--finished-at", finish, "--verified", "--defect-escapes", str(defects),
        "--false-completions", str(false_completions), "--token-units", str(tokens),
        "--friction-events", str(friction), "--critical-regressions", "0",
    )


def main() -> int:
    schema = json.loads(RAW_SCHEMA.read_text(encoding="utf-8"))
    check("raw schema is local-only and pseudonymous", schema["privacy"]["localOnly"] is True
          and set(schema["pseudonymousIdPatterns"]) == {"projectId", "operatorId", "comparisonId"})
    no_args = run()
    check("no-argument invocation is a quiet no-op", no_args.returncode == 0 and not no_args.stdout and not no_args.stderr)
    generated = run("new-id", "--kind", "comparison")
    check("new-id emits a valid pseudonym", generated.returncode == 0
          and re.fullmatch(r"cmp_[a-f0-9]{12}\n", generated.stdout) is not None, generated.stdout)

    with tempfile.TemporaryDirectory(prefix="itd-external-pilot-") as td:
        root = Path(td)
        ledger = root / "units.jsonl"
        missing_consent = run(
            "init", "--ledger", str(ledger), "--project-id", "proj_a1b2c3d4e5f6",
            "--operator-id", "op_111111111111", "--repository-class", "external_private",
            "--started-at", "2026-06-14T19:30:00Z",
        )
        check("enrollment fails closed without consent", missing_consent.returncode != 0
              and "WHY:" in missing_consent.stdout and "FIX:" in missing_consent.stdout)
        init = run(
            "init", "--ledger", str(ledger), "--project-id", "proj_a1b2c3d4e5f6",
            "--operator-id", "op_111111111111", "--repository-class", "external_private",
            "--started-at", "2026-06-14T19:30:00Z", "--consent",
        )
        check("consented pilot initializes silently", init.returncode == 0 and not init.stdout, init.stdout)
        check("enrollment never overwrites an existing ledger", run(
            "init", "--ledger", str(ledger), "--project-id", "proj_a1b2c3d4e5f6",
            "--operator-id", "op_111111111111", "--repository-class", "external_private",
            "--started-at", "2026-06-14T19:30:00Z", "--consent",
        ).returncode != 0)

        rows = [
            ("baseline", "cmp_aaaaaaaaaaaa", "2026-06-14T20:00:00Z", "2026-06-14T22:00:00Z", 1, 1, 100, 1),
            ("followup", "cmp_aaaaaaaaaaaa", "2026-07-15T17:00:00Z", "2026-07-15T18:30:00Z", 0, 0, 80, 0),
            ("baseline", "cmp_bbbbbbbbbbbb", "2026-06-15T20:00:00Z", "2026-06-15T23:00:00Z", 0, 0, 120, 0),
            ("followup", "cmp_bbbbbbbbbbbb", "2026-07-15T17:30:00Z", "2026-07-15T19:30:00Z", 0, 0, 90, 0),
        ]
        for row in rows:
            result = append(ledger, *row)
            check(f"append {row[0]} {row[1]}", result.returncode == 0 and not result.stdout,
                  result.stdout + result.stderr)
        duplicate = append(ledger, *rows[0])
        check("duplicate phase/comparison is rejected", duplicate.returncode != 0
              and "WHY:" in duplicate.stdout and "FIX:" in duplicate.stdout)

        aggregate = root / "aggregate.json"
        aggregated = run("aggregate", "--ledger", str(ledger), "--out", str(aggregate))
        data = json.loads(aggregate.read_text(encoding="utf-8")) if aggregate.is_file() else {}
        check("paired units aggregate deterministically", aggregated.returncode == 0
              and data.get("comparableUnits") == 2
              and data.get("baseline", {}).get("defectEscapeRate") == 0.5
              and data.get("followup", {}).get("tokenUnitsPerVerifiedUnit") == 85.0,
              str(data))
        check("aggregate contains no prohibited direct identifiers", not outcomes.forbidden_paths(data),
              str(outcomes.forbidden_paths(data)))

        self_attest = run(
            "attest", "--ledger", str(ledger), "--aggregate", str(aggregate),
            "--verified-by", "op_111111111111", "--verified-at", "2026-07-15T19:35:00Z",
            "--out", str(root / "bad-record.json"), "--consent", "--independent-operator",
            "--not-author-affiliated", "--accurate",
        )
        check("self-verification is rejected", self_attest.returncode != 0
              and "verifier must differ" in self_attest.stdout)

        record_path = root / "record.json"
        attested = run(
            "attest", "--ledger", str(ledger), "--aggregate", str(aggregate),
            "--verified-by", "op_222222222222", "--verified-at", "2026-07-15T19:35:00Z",
            "--out", str(record_path), "--consent", "--independent-operator",
            "--not-author-affiliated", "--accurate",
        )
        record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else {}
        check("independent attestation produces a replayable record", attested.returncode == 0
              and record.get("attestation", {}).get("recordDigest") == outcomes.record_digest(record),
              attested.stdout + attested.stderr)
        policy = outcomes.policy_from(json.loads(CONTRACT.read_text(encoding="utf-8")))
        issues = outcomes.validate_record(
            record, json.loads(SCHEMA.read_text(encoding="utf-8")), policy,
            dt.datetime(2026, 7, 16, tzinfo=dt.timezone.utc),
        ) if record else ["record missing"]
        check("attested record satisfies per-project frozen validation", not issues, str(issues))

        tampered = json.loads(aggregate.read_text(encoding="utf-8"))
        tampered["followup"]["medianCycleMinutes"] = 1
        aggregate.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
        replay = run(
            "attest", "--ledger", str(ledger), "--aggregate", str(aggregate),
            "--verified-by", "op_222222222222", "--verified-at", "2026-07-15T19:35:00Z",
            "--out", str(root / "tampered.json"), "--consent", "--independent-operator",
            "--not-author-affiliated", "--accurate",
        )
        check("tampered aggregate cannot be attested", replay.returncode != 0
              and "does not replay" in replay.stdout)

        poisoned = root / "poisoned.jsonl"
        poisoned.write_text(ledger.read_text(encoding="utf-8")
                            + '{"recordType":"unit","email":"pilot@example.invalid"}\n',
                            encoding="utf-8")
        rejected = run("aggregate", "--ledger", str(poisoned), "--out", str(root / "poisoned.json"))
        check("PII-shaped raw fields fail with line plus WHY/FIX", rejected.returncode != 0
              and "prohibited fields" in rejected.stdout and "WHY:" in rejected.stdout
              and "FIX:" in rejected.stdout, rejected.stdout)

        unpaired = root / "unpaired.jsonl"
        unpaired.write_text("\n".join(ledger.read_text(encoding="utf-8").splitlines()[:2]) + "\n",
                            encoding="utf-8")
        unpaired_result = run("aggregate", "--ledger", str(unpaired), "--out", str(root / "x.json"))
        check("unpaired comparison fails closed", unpaired_result.returncode != 0
              and "unpaired comparison IDs" in unpaired_result.stdout)

    source = SCRIPT.read_text(encoding="utf-8")
    check("collector has no network client", not re.search(r"\b(requests|urllib|httpx|socket)\b", source))
    print("METRICS " + json.dumps({
        "positivePairs": 2,
        "privacyRejections": 1,
        "independentAttestations": 1,
        "networkClients": 0,
    }, sort_keys=True))
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print("ALL PASS — external pilot collection is paired, privacy-safe and independently attestable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
