#!/usr/bin/env python3
"""Observed efficiency telemetry is attributable without estimate laundering."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "cost-tracker.sh"


def invoke(ledger_dir: Path, payload: dict, host: str = "codex") -> dict:
    env = dict(os.environ)
    env.update({
        "TMPDIR": str(ledger_dir),
        "TEMP": str(ledger_dir),
        "TMP": str(ledger_dir),
        "ITD_HOST": host,
        "ITD_COST_CEILING_TOKENS": "2000000",
    })
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    if result.returncode != 0:
        raise AssertionError(f"cost tracker failed: {result.returncode}: {result.stderr}")
    sid = payload["session_id"]
    path = ledger_dir / f"claude-cost-{sid}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="itd-efficiency-attribution-") as td:
            base = Path(td)
            ledger_dir = base / "ledgers"
            ledger_dir.mkdir()
            project = base / "project"
            nested = project / "src" / "nested"
            nested.mkdir(parents=True)
            memory = project / ".itd-memory"
            memory.mkdir()
            (memory / "GOAL.json").write_text(json.dumps({
                "version": 1,
                "currentUnitId": "EFF-UNIT-7",
                "units": [{"id": "EFF-UNIT-7", "status": "in_progress"}],
            }), encoding="utf-8")

            first = invoke(ledger_dir, {
                "hook_event_name": "PostToolUse",
                "session_id": "attributed",
                "cwd": str(nested),
                "tool_name": "Skill",
                "tool_input": {"name": "test", "model": "gpt-5"},
                "usage": {"input_tokens": 120, "output_tokens": 30},
                "duration_ms": 1250,
            })
            row = first["observations"][-1]
            expected_dimensions = {
                "session": "attributed",
                "unit": "EFF-UNIT-7",
                "skill": "test",
                "model": "gpt-5",
                "host": "codex",
            }
            check(all(row.get(key) == value for key, value in expected_dimensions.items()),
                  f"observed row is not fully attributed: {row}")
            check(row.get("tokens") == 150 and row.get("elapsedMs") == 1250,
                  f"observed counters are wrong: {row}")
            check(row.get("measurement") == "host_observed",
                  "observed row is not provenance-labelled")
            provenance = row.get("provenance") or {}
            check(provenance.get("tokens") == "host_payload.usage"
                  and provenance.get("elapsedMs") == "host_payload.duration_ms",
                  f"host counter provenance is missing: {provenance}")
            check((provenance.get("dimensions") or {}).get("unit")
                  == ".itd-memory/GOAL.json",
                  f"unit provenance is missing: {provenance}")

            second = invoke(ledger_dir, {
                "hook_event_name": "PostToolUse",
                "session_id": "attributed",
                "cwd": str(project),
                "tool_name": "Bash",
                "tool_input": {"command": "pytest -q"},
                "skill": "test",
                "model": "gpt-5",
                "tool_response": {
                    "usage": {"total_tokens": 50},
                    "elapsed_ms": 250,
                },
            })
            buckets = [
                item for item in second.get("by_attribution") or []
                if all(item.get(key) == value for key, value in expected_dimensions.items())
            ]
            check(len(buckets) == 1, f"attribution aggregate is missing/duplicated: {buckets}")
            bucket = buckets[0]
            check(bucket.get("tokens") == 200
                  and bucket.get("elapsedMs") == 1500
                  and bucket.get("callsWithObservedUsage") == 2,
                  f"attribution aggregate is wrong: {bucket}")
            check(second["token_counters"]["observed"]["value"] == 200,
                  "observed token aggregate is wrong")
            check(second["elapsed_counters"]["valueMs"] == 1500,
                  "observed elapsed aggregate is wrong")

            estimated = invoke(ledger_dir, {
                "hook_event_name": "PostToolUse",
                "session_id": "estimate-only",
                "cwd": str(project),
                "tool_name": "Agent",
                "tool_input": {"subagent_type": "reviewer", "model": "gpt-5"},
                "estimated_tokens": 999999,
                "tool_response": {"stdout": "999999 tokens", "duration": "2s"},
            })
            check(estimated["total_tokens_kind"] == "estimate"
                  and estimated["token_counters"]["estimated"]["measurement"] == "estimate",
                  "static budget counter lost its estimate label")
            check(estimated["token_counters"]["observed"]["value"] == 0,
                  "an estimate was laundered into observed tokens")
            check(estimated["elapsed_counters"]["valueMs"] == 0,
                  "an unstructured duration was laundered into observed elapsed")
            check(not estimated.get("observations"),
                  "estimate-only call created a host-observed event")

        print(
            "PASS efficiency attribution: observed tokens/elapsed are grouped by "
            "session, unit, skill, model and host; estimates remain separate"
        )
        return 0
    except Exception as exc:
        print(f"FAIL efficiency attribution: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
