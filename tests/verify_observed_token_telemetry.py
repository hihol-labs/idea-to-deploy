#!/usr/bin/env python3
"""Observed token counters are provenance-tagged and never mix with estimates."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "cost-tracker.sh"
passed = failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f" [{detail[:200]}]" if detail and not condition else ""))
    if condition:
        passed += 1
    else:
        failed += 1


def run(tmp: str, sid: str, payload: dict) -> dict:
    env = dict(os.environ)
    env.update({"TMPDIR": tmp, "TEMP": tmp, "TMP": tmp})
    payload = {"session_id": sid, **payload}
    subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                   capture_output=True, text=True, env=env, timeout=30)
    path = Path(tmp) / f"claude-cost-{sid}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        estimated = run(tmp, "estimated", {"tool_name": "Bash"})
        counters = estimated.get("token_counters") or {}
        check("static tool table is explicitly an estimate",
              estimated.get("total_tokens_kind") == "estimate"
              and counters.get("estimated", {}).get("measurement") == "estimate")
        check("an estimate is never copied into observed counters",
              counters.get("observed", {}).get("value") == 0
              and not estimated.get("token_observations"))

        structured = run(tmp, "structured", {
            "tool_name": "Bash",
            "usage": {"input_tokens": 120, "output_tokens": 30},
        })
        observed = structured["token_counters"]["observed"]
        check("structured host usage is recorded as observed",
              observed.get("value") == 150
              and observed.get("measurement") == "host_observed")
        check("structured observation carries exact provenance",
              observed.get("by_source") == {"host_payload.usage": 150}
              and structured["token_observations"][-1].get("provenance") == "host_payload.usage")

        agent = run(tmp, "agent", {
            "tool_name": "Agent",
            "tool_input": {"subagent_type": "reviewer", "model": "sonnet"},
            "tool_response": "<usage><subagent_tokens>187033</subagent_tokens></usage>",
        })
        check("host subagent counter is observed with source",
              agent["token_counters"]["observed"].get("value") == 187033
              and "host_tool_response.subagent_tokens" in agent["token_counters"]["observed"].get("by_source", {}))
        by_agent = agent.get("by_agent", {}).get("reviewer(sonnet)", {})
        check("per-agent attribution declares measurement and provenance",
              by_agent.get("tokens") == 187033
              and by_agent.get("measurement") == "host_observed"
              and by_agent.get("provenance") == "host_tool_response.subagent_tokens")

        forged = run(tmp, "forged", {
            "tool_name": "Bash", "estimated_tokens": 999999,
            "tool_response": {"stdout": "999999 tokens"},
        })
        check("untrusted estimate-like fields cannot become observations",
              forged["token_counters"]["observed"].get("value") == 0)

    source = HOOK.read_text(encoding="utf-8")
    check("user-facing ceiling remains labelled estimate",
          "Session cost estimate" in source)
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
