#!/usr/bin/env python3
"""Collect a real paired diagnostics micro-pilot without inventing human labels."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
import tempfile
import time
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNNER = ROOT / "skills" / "_shared" / "itd_incremental_diagnostics.py"


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json_atomic(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            descriptor = -1
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        try:
            directory_descriptor = os.open(path.parent, os.O_RDONLY)
        except OSError:
            directory_descriptor = -1
        if directory_descriptor >= 0:
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def observed_run(argv: list[str], cwd: pathlib.Path
                 ) -> tuple[subprocess.CompletedProcess[bytes], int]:
    started = time.monotonic_ns()
    completed = subprocess.run(
        argv, cwd=str(cwd), capture_output=True, shell=False, timeout=30)
    elapsed = max(0, round((time.monotonic_ns() - started) / 1_000_000))
    return completed, elapsed


def collect(pairs: int) -> dict[str, Any]:
    if pairs < 30 or pairs > 100:
        raise ValueError("paired pilot requires 30..100 observations")
    started_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    runs: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="itd-diagnostics-pilot-") as raw:
        fixture = pathlib.Path(raw)
        changed = fixture / "changed.py"
        probe = fixture / "probe.py"
        probe.write_text(
            "import pathlib,sys\n"
            "value=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')\n"
            "if 'BROKEN' in value:\n"
            "    print('known-broken-sentinel')\n"
            "    raise SystemExit(1)\n"
            "raise SystemExit(0)\n",
            encoding="utf-8")
        contract_path = fixture / "diagnostics.json"
        command = [sys.executable, "-B", str(probe), changed.name]
        contract = {
            "version": 1,
            "id": "itd-diagnostics-pilot-v1",
            "enabled": True,
            "advisory": True,
            "completionEvidence": False,
            "measurement": "host-observed",
            "timeoutSeconds": 5,
            "cooldownSeconds": 0,
            "cacheTtlSeconds": 0,
            "cachePath": ".itd-memory/diagnostics/cache.json",
            "telemetryPath": ".itd-memory/diagnostics/telemetry.jsonl",
            "commands": [command],
        }
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        command_hash = digest(json.dumps(
            command, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

        for number in range(1, pairs + 1):
            pair_id = f"pair-{number:03d}"
            changed.write_text(
                f"# {pair_id}\nstatus = 'BROKEN'\n", encoding="utf-8")
            baseline, baseline_ms = observed_run(command, fixture)
            if baseline.returncode != 1:
                raise RuntimeError(f"{pair_id} baseline did not observe the known issue")
            runs.append({
                "pairId": pair_id,
                "arm": "baseline",
                "latencyMs": baseline_ms,
                "exitCode": baseline.returncode,
                "stdoutSha256": digest(baseline.stdout),
                "stderrSha256": digest(baseline.stderr),
                "commandSha256": command_hash,
                "completionEvidence": False,
            })

            treatment_argv = [
                sys.executable, "-B", str(RUNNER), "run",
                "--root", str(fixture), "--contract", str(contract_path),
                "--changed", str(changed),
            ]
            treatment, treatment_ms = observed_run(treatment_argv, fixture)
            if treatment.returncode != 0:
                raise RuntimeError(f"{pair_id} treatment runner failed")
            result = json.loads(treatment.stdout.decode("utf-8"))
            rows = result.get("results") or []
            if (result.get("status") != "completed" or len(rows) != 1
                    or rows[0].get("exitCode") != 1):
                raise RuntimeError(f"{pair_id} treatment did not emit the known issue")
            runs.append({
                "pairId": pair_id,
                "arm": "treatment",
                "latencyMs": treatment_ms,
                "runnerDurationMs": result["durationMs"],
                "status": result["status"],
                "cacheKey": result["cacheKey"],
                "completionEvidence": False,
                "emissions": [{
                    "id": f"{pair_id}:known-broken-sentinel",
                    "diagnosticId": "known-broken-sentinel",
                    "exitCode": rows[0]["exitCode"],
                    "stdoutSha256": rows[0]["stdoutSha256"],
                    "stderrSha256": rows[0]["stderrSha256"],
                    "proposedLabel": "actionable",
                    "humanLabel": None,
                }],
            })
    return {
        "version": 1,
        "status": "awaiting-human-labels",
        "externalAdoptionEvidence": False,
        "measurement": "host-observed",
        "baseline": "same project checks without incremental diagnostics",
        "treatment": "same project checks with the opt-in incremental profile",
        "startedAt": started_at,
        "completedAt": dt.datetime.now(
            dt.timezone.utc).replace(microsecond=0).isoformat(),
        "environment": {
            "platform": platform.system(),
            "pythonImplementation": platform.python_implementation(),
            "pythonVersion": platform.python_version(),
            "runnerSha256": digest(RUNNER.read_bytes()),
            "probe": "deterministic-known-broken-sentinel-v1",
        },
        "labeledRuns": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect paired diagnostic observations.")
    parser.add_argument("--pairs", type=int, default=30)
    parser.add_argument("--observations", type=pathlib.Path, required=True)
    parser.add_argument("--label-packet", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        observations = collect(args.pairs)
        write_json_atomic(args.observations, observations)
        observation_hash = digest(args.observations.read_bytes())
        treatment = [
            row for row in observations["labeledRuns"] if row["arm"] == "treatment"
        ]
        packet = {
            "version": 1,
            "status": "awaiting-human-decision",
            "observationsPath": args.observations.as_posix(),
            "observationsSha256": observation_hash,
            "question": (
                "Are all 30 known-broken-sentinel emissions actionable? "
                "Approve only if each correctly identifies the seeded BROKEN state."),
            "emissionIds": [row["emissions"][0]["id"] for row in treatment],
            "proposedBulkLabel": "actionable",
            "decision": None,
        }
        write_json_atomic(args.label_packet, packet)
        print(json.dumps({
            "status": "COLLECTED",
            "pairs": args.pairs,
            "emissions": len(treatment),
            "observationsSha256": observation_hash,
        }, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError,
            json.JSONDecodeError) as exc:
        print(json.dumps({
            "status": "FAILED",
            "why": str(exc),
            "fix": "repair the collector/runner; never synthesize missing observations",
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
