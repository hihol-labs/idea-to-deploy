#!/usr/bin/env python3
"""Gate: cost-tracker ledger isolation + context sensor (v1.71.0, retro 2026-07-09).

P1 (боевой инцидент, amnesia-lab): the ledger must be keyed by
payload["session_id"], so parallel subagents do NOT pool into one ledger and
inherit a false HARD ceiling from their neighbours (a subagent with ~183k own
tokens was halted by a "2,000,700 tokens" ASK). Red on pre-v1.71.0 code
exactly at t3 (neighbour ceiling isolation).

P2: transcript-size context sensor — a ONE-TIME hint at >= 60% of the context
window (transport of the v1.70.0 /handoff rule), off below the threshold and
disableable via ITD_CONTEXT_HANDOFF_PCT=0.

Self-contained:  python3 tests/verify_cost_tracker.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "cost-tracker.sh"

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def run_hook_proc(tmp: str, payload: dict, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    # Isolate the ledger dir on every OS (tempfile honours TMPDIR/TEMP/TMP).
    env["TMPDIR"] = env["TEMP"] = env["TMP"] = tmp
    env.pop("CLAUDE_SESSION_ID", None)
    env.setdefault("ITD_COST_CEILING_TOKENS", "2000000")
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, timeout=30,
    )


def run_hook(tmp: str, payload: dict, extra_env: dict | None = None) -> str:
    return run_hook_proc(tmp, payload, extra_env).stdout


def ledger(tmp: str, sid: str) -> dict:
    p = Path(tmp) / f"claude-cost-{sid}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    check("hook exists", HOOK.is_file(), str(HOOK))

    with tempfile.TemporaryDirectory() as tmp:
        # t1: payload sid keys the ledger file
        run_hook(tmp, {"session_id": "agentA", "tool_name": "Bash"})
        la = ledger(tmp, "agentA")
        check("t1: ledger keyed by payload session_id", la.get("total_tokens", 0) > 0, str(la))

        # t2: a second agent gets its OWN ledger; A is not touched
        run_hook(tmp, {"session_id": "agentB", "tool_name": "Read"})
        lb = ledger(tmp, "agentB")
        la2 = ledger(tmp, "agentA")
        check("t2: parallel agents do not pool", lb.get("total_calls") == 1 and la2 == la,
              f"B={lb.get('total_calls')} A_before={la} A_after={la2}")

        # t3 (P1 regression, red pre-v1.71.0): a neighbour at 199% of the
        # ceiling must NOT trip the HARD ASK for a fresh agent.
        big = {"session_start": 0, "total_tokens": 3_990_000, "total_calls": 1635,
               "by_tool": {}, "warnings_sent": 0, "hard_fired_at_tokens": 0}
        (Path(tmp) / "claude-cost-hog.json").write_text(json.dumps(big), encoding="utf-8")
        out = run_hook(tmp, {"session_id": "fresh", "tool_name": "Bash"})
        check("t3: neighbour ceiling does not leak to a fresh agent",
              "HARD CEILING" not in out and ledger(tmp, "fresh").get("total_calls") == 1, out[:120])

        # t4: no payload sid, no env → shared day-anchor fallback still works
        run_hook(tmp, {"tool_name": "Bash"})
        anchor = Path(tmp) / "claude-skill-session-anchor"
        tok = anchor.read_text(encoding="utf-8").strip() if anchor.is_file() else ""
        check("t4: day-anchor fallback preserved", bool(tok) and ledger(tmp, tok).get("total_calls", 0) >= 1, tok)

        # t5: context sensor fires ONCE at >= 60% of the window
        transcript = Path(tmp) / "tr.jsonl"
        transcript.write_bytes(b"x" * int(0.65 * 200_000 * 4))
        p = {"session_id": "ctx", "tool_name": "Bash", "transcript_path": str(transcript)}
        out1 = run_hook(tmp, p)
        out2 = run_hook(tmp, p)
        check("t5a: hint fires at >=60%", "CONTEXT SENSOR" in out1 and "/handoff" in out1, out1[:120])
        check("t5b: hint is one-time per ledger", "CONTEXT SENSOR" not in out2, out2[:120])

        # t6: below the threshold — no hint
        small = Path(tmp) / "tr-small.jsonl"
        small.write_bytes(b"x" * int(0.30 * 200_000 * 4))
        out = run_hook(tmp, {"session_id": "ctx2", "tool_name": "Bash", "transcript_path": str(small)})
        check("t6: silent below threshold", "CONTEXT SENSOR" not in out, out[:120])

        # t7: sensor disableable via env
        out = run_hook(tmp, {"session_id": "ctx3", "tool_name": "Bash", "transcript_path": str(transcript)},
                       extra_env={"ITD_CONTEXT_HANDOFF_PCT": "0"})
        check("t7: ITD_CONTEXT_HANDOFF_PCT=0 disables sensor", "CONTEXT SENSOR" not in out, out[:120])

        # t8: weird sid stays filesystem-safe (no crash, sanitized filename)
        out = run_hook(tmp, {"session_id": "we/ird:sid", "tool_name": "Bash"})
        safe = [p.name for p in Path(tmp).glob("claude-cost-we_ird_sid.json")]
        check("t8: sid sanitized for filename", len(safe) == 1, str(safe))

        # t9 (review finding, red pre-fix): legacy Windows codepage must not
        # crash the hook while it emits the Cyrillic/emoji context hint.
        proc = run_hook_proc(
            tmp,
            {"session_id": "ctx-legacy", "tool_name": "Bash", "transcript_path": str(transcript)},
            extra_env={"PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252"},
        )
        check("t9: legacy encoding does not crash the hook",
              proc.returncode == 0 and "Traceback" not in (proc.stderr or ""),
              f"rc={proc.returncode} stderr={proc.stderr[:120]}")

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
