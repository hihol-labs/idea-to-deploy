#!/usr/bin/env python3
"""Behavioural proof: ОТК verify-signal + subagent/stall watchdog
(v1.89.0, GO-003 — «различимость состояний системы»).

  - itd_goal_verify.py пишет verify-сигнал (kind verify, L2, unit) при прогоне
  - record-agent-skill.sh: пустой финал субагента -> agent-сигнал outcome empty
  - agent с текстом -> outcome ok
  - find_stalls распознаёт pre без парного post за порогом

Self-contained, stdlib only. Run: python3 tests/verify_verify_signal_and_watchdog.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "hooks"))
import completion_lib as cl  # noqa: E402

OTK = REPO / "skills" / "goal" / "scripts" / "itd_goal_verify.py"
REC = REPO / "hooks" / "record-agent-skill.sh"

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        FAIL += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def signals(root):
    f = Path(root) / ".claude" / "completion" / "signals.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    # 1) ОТК verify-signal: активируем и верифицируем юнит с командой `true`
    with tempfile.TemporaryDirectory() as td:
        mem = Path(td) / ".itd-memory"
        mem.mkdir()
        goal = {"version": 1, "goal": "g", "status": "active", "currentUnitId": "",
                "units": [{"id": "V-1", "criterion": "c", "verificationCommand": "true",
                           "status": "pending"}]}
        (mem / "GOAL.json").write_text(json.dumps(goal), encoding="utf-8")
        env = dict(os.environ)
        subprocess.run([sys.executable, str(OTK), "--activate", "V-1", "--goal",
                        str(mem / "GOAL.json")], capture_output=True, text=True, timeout=30, env=env)
        r = subprocess.run([sys.executable, str(OTK), "V-1", "--goal", str(mem / "GOAL.json")],
                           capture_output=True, text=True, timeout=30, env=env)
        rows = signals(td)
        vsig = [s for s in rows if s.get("kind") == "verify"]
        check("ОТК пишет verify-сигнал", len(vsig) == 1, f"rc={r.returncode} rows={rows}")
        if vsig:
            check("verify-сигнал: L2 pass, unit V-1",
                  vsig[0].get("layer") == 2 and vsig[0].get("outcome") == "pass"
                  and vsig[0].get("unit") == "V-1", str(vsig[0]))

    # 2) agent_result_signal
    s = cl.agent_result_signal("code-reviewer", {"result": "   "})
    check("пустой финал -> outcome empty", s.get("outcome") == "empty" and s.get("kind") == "agent", str(s))
    s = cl.agent_result_signal("code-reviewer", {"result": "PASSED, no findings"})
    check("непустой финал -> outcome ok", s.get("outcome") == "ok", str(s))

    # 3) record-agent-skill пишет agent-сигнал (subprocess с stdin)
    with tempfile.TemporaryDirectory() as td:
        payload = {"session_id": "s", "cwd": td, "tool_name": "Agent",
                   "tool_input": {"subagent_type": "code-reviewer"},
                   "tool_response": {"result": ""}}
        subprocess.run([sys.executable, str(REC)], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=20)
        rows = signals(td)
        check("record-agent-skill пишет empty agent-сигнал",
              any(s.get("kind") == "agent" and s.get("outcome") == "empty" for s in rows), str(rows))

    # 4) find_stalls
    trace = [
        {"ts": "2026-07-12T10:00:00+00:00", "phase": "pre", "tool": "Bash"},
        {"ts": "2026-07-12T10:00:05+00:00", "phase": "post", "tool": "Bash", "outcome": "ok"},
        {"ts": "2026-07-12T10:01:00+00:00", "phase": "pre", "tool": "Agent"},  # без post
        {"ts": "2026-07-12T10:30:00+00:00", "phase": "pre", "tool": "Edit"},
        {"ts": "2026-07-12T10:30:01+00:00", "phase": "post", "tool": "Edit", "outcome": "ok"},
    ]
    stalls = cl.find_stalls(trace, threshold_s=600)
    check("find_stalls ловит зависший Agent",
          any(t == "Agent" for t, _ in stalls) and not any(t == "Bash" for t, _ in stalls), str(stalls))

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
