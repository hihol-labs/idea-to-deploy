#!/usr/bin/env python3
"""
PostToolUse hook — cost/token tracking (inspired by GSD v2).

Tracks tool call counts per skill/task, estimates token usage,
and warns when approaching a budget ceiling. Writes a ledger
file that can be reviewed with `cat /tmp/claude-cost-<session>.json`.

GSD v2 has per-unit cost ledger with projections and dynamic model
routing. We adapt the core idea: visibility into costs per task.

v1.18.0: Adaptation from GSD v2 cost tracking.

Reads JSON on stdin: {"tool_name": "...", "tool_input": {...}, "response": "..."}
"""
from __future__ import annotations

import json
import os
import sys
import time

# Rough token estimates per tool call type (conservative)
TOKEN_ESTIMATES = {
    "Bash": 800,
    "Read": 2000,
    "Write": 1500,
    "Edit": 1000,
    "Grep": 600,
    "Glob": 300,
    "Agent": 15000,  # subagent calls are expensive
    "Skill": 500,
    "default": 500,
}

# Approximate cost per 1M tokens (input+output blended, Opus)
COST_PER_1M_TOKENS = 30.0  # USD, rough Opus estimate
BUDGET_CEILING_TOKENS = 2_000_000  # 2M tokens = ~$60
WARNING_THRESHOLD = 0.8  # Warn at 80% of ceiling


def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def ledger_file() -> str:
    return f"/tmp/claude-cost-{session_id()}.json"


def read_ledger() -> dict:
    try:
        with open(ledger_file()) as f:
            return json.load(f)
    except Exception:
        return {
            "session_start": time.time(),
            "total_tokens": 0,
            "total_calls": 0,
            "by_tool": {},
            "warnings_sent": 0,
        }


def write_ledger(ledger: dict) -> None:
    try:
        with open(ledger_file(), "w") as f:
            json.dump(ledger, f, indent=2)
    except Exception:
        pass


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = (payload or {}).get("tool_name") or "default"

    ledger = read_ledger()
    tokens = TOKEN_ESTIMATES.get(tool, TOKEN_ESTIMATES["default"])

    ledger["total_tokens"] = ledger.get("total_tokens", 0) + tokens
    ledger["total_calls"] = ledger.get("total_calls", 0) + 1

    by_tool = ledger.get("by_tool", {})
    if tool not in by_tool:
        by_tool[tool] = {"calls": 0, "tokens": 0}
    by_tool[tool]["calls"] += 1
    by_tool[tool]["tokens"] += tokens
    ledger["by_tool"] = by_tool

    total = ledger["total_tokens"]
    cost_usd = (total / 1_000_000) * COST_PER_1M_TOKENS

    # Check budget ceiling
    should_warn = (
        total >= BUDGET_CEILING_TOKENS * WARNING_THRESHOLD
        and ledger.get("warnings_sent", 0) < 3
    )

    write_ledger(ledger)

    if should_warn:
        ledger["warnings_sent"] = ledger.get("warnings_sent", 0) + 1
        write_ledger(ledger)

        pct = int((total / BUDGET_CEILING_TOKENS) * 100)
        context = (
            f"[COST TRACKER — GSD-inspired]\n"
            f"💰 Session cost estimate: ~${cost_usd:.2f} "
            f"({total:,} tokens, {pct}% of ceiling)\n"
            f"📊 Tool calls: {ledger['total_calls']}\n\n"
            f"⚠️ Approaching budget ceiling ({pct}% of {BUDGET_CEILING_TOKENS:,} tokens).\n"
            f"Consider:\n"
            f"- Completing current task and saving session\n"
            f"- Using /session-save to checkpoint progress\n"
            f"- Starting a fresh session for remaining work\n\n"
            f"Ledger: `cat {ledger_file()}`"
        )

        out = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": context,
            }
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
