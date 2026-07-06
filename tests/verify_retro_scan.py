#!/usr/bin/env python3
"""Functional tests for the /retro telemetry scanner (v1.46.0).

Pins the FACTS half of the self-improvement loop: itd_retro_scan.py must
aggregate events.jsonl / GOAL.json / STATE.json / bypass ledgers / cost
ledgers deterministically, count blocked units as goal backpressure, survive
empty and malformed sources, and stay consistent between markdown and --json.

Cross-platform by construction (tempfile dirs, sys.executable, --tmp-dir
override so the real system tempdir is never touched). Self-contained. Run:
  python3 tests/verify_retro_scan.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = ROOT / "skills" / "retro" / "scripts" / "itd_retro_scan.py"
PY = sys.executable

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    # ITD_COST_PER_1M_USD pinned so the derived-USD assertion is deterministic
    # regardless of the developer's environment override.
    env = {**os.environ, "PYTHONUTF8": "1", "ITD_COST_PER_1M_USD": "30"}
    return subprocess.run([PY, str(SCAN), *args], cwd=str(cwd),
                          capture_output=True, encoding="utf-8",
                          errors="replace", env=env, timeout=120)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "workspace"
        tmp = Path(td) / "ledgers"
        tmp.mkdir(parents=True)

        # project alpha: 2 activated, 1 verified (VCR 0.5), 1 regression,
        # active goal with a blocked unit and a pipe in the goal text
        mem_a = ws / "alpha" / ".itd-memory"
        write(mem_a / "events.jsonl", "\n".join(json.dumps(e) for e in [
            {"type": "unit", "name": "U-1", "decision": "activated"},
            {"type": "unit", "name": "U-1", "decision": "verified"},
            {"type": "unit", "name": "U-2", "decision": "activated"},
            {"type": "unit", "name": "U-2", "decision": "verification_failed"},
            {"type": "unit", "name": "U-1", "decision": "regressed"},
            {"type": "decision", "name": "noise", "decision": "ignored"},
        ]))
        write(mem_a / "GOAL.json", json.dumps({
            "version": 1, "goal": "ship reset | end-to-end", "status": "active",
            "createdAt": "", "updatedAt": "", "currentUnitId": "",
            "units": [
                {"id": "G-001", "criterion": "a", "verificationCommand": "x",
                 "status": "verified"},
                {"id": "G-002", "criterion": "b", "verificationCommand": "x",
                 "status": "blocked", "blockedReason": "waiting for key"},
                {"id": "G-003", "criterion": "c", "verificationCommand": "x",
                 "status": "pending"},
            ]}))
        # project beta: pending gates + blockers, no events
        mem_b = ws / "beta" / ".itd-memory"
        write(mem_b / "STATE.json", json.dumps({
            "gateResults": {"tests": "pending", "security": "passed",
                            "rootCause": "n/a", "hardening": "failed"},
            "blockers": ["need SMTP creds"]}))
        # malformed sources must not crash the scan
        write(ws / "gamma" / ".itd-memory" / "GOAL.json", "{not json")
        write(ws / "gamma" / ".itd-memory" / "events.jsonl", "also not json\n")

        # ledgers — REAL producer shapes (review finding v1.46.0):
        # check-tool-skill.sh log_bypass() writes {ts, tool, reason};
        # cost-tracker.sh persists total_tokens and never stores USD.
        write(tmp / "claude-skill-ledger-s1.jsonl", "\n".join([
            json.dumps({"ts": 1, "tool": "Bash", "reason": "hotfix, no time"}),
            json.dumps({"ts": 2, "tool": "Bash", "reason": "docs-only"}),
            json.dumps({"ts": 3, "tool": "Edit", "reason": "spike"}),
            "garbage line",
        ]))
        write(tmp / "claude-cost-abc.json", json.dumps(
            {"session_start": 1, "total_tokens": 50000, "total_calls": 9,
             "by_tool": {}, "warnings_sent": []}))
        write(tmp / "claude-cost-def.json", json.dumps(
            {"session_start": 2, "total_tokens": 16667, "total_calls": 3,
             "by_tool": {}, "warnings_sent": []}))

        # 1) markdown run
        r = run(str(ws), "--tmp-dir", str(tmp), cwd=Path(td))
        out = r.stdout
        check("scan exits 0 on mixed workspace", r.returncode == 0, r.stderr)
        check("markdown reports global VCR 0.5 (1/2 units)",
              "0.5" in out and "1/2" in out, out[:400])
        check("markdown reports regression and failed verification counts",
              "регрессий: 1" in out and "проваленных верификаций: 1" in out, out[:400])
        check("active goal listed with backpressure incl. blocked",
              "давление 2" in out and "waiting for key" in out, out[:600])
        check("goal text pipe is escaped for the table-safe output",
              "ship reset \\| end-to-end" in out, out[:600])
        check("bypass ledger aggregated by tool (real record shape)",
              "всего 3" in out and "Bash×2" in out.replace(" ", ""), out[:800])
        check("bypass/session friction metric rendered (3.0 over 1 session)",
              "1 сессий" in out and "3.0/сессия" in out, out[:800])
        check("cost derived from persisted total_tokens (real ledger shape)",
              "$2.0" in out and "2 сессий" in out and "66667 токенов" in out,
              out[:800])
        check("pending gates surfaced for beta",
              "hardening" in out and "tests" in out and "security" not in
              out.split("Незакрытые гейты")[-1][:200], out[-500:])
        check("VCR<1 project named", "alpha" in out, out[:400])

        # 2) --json consistency
        r = run(str(ws), "--tmp-dir", str(tmp), "--json", cwd=Path(td))
        try:
            data = json.loads(r.stdout)
            ok = (data["vcrGlobal"] == 0.5 and data["unitsActivated"] == 2
                  and data["regressions"] == 1 and data["bypassTotal"] == 3
                  and data["bypassByTool"] == {"Bash": 2, "Edit": 1}
                  and data["bypassSessionCount"] == 1
                  and data["bypassPerSession"] == 3.0
                  and data["costTokensTotal"] == 66667
                  and data["costUsdEstimate"] == 2.0
                  and data["projectsScanned"] == 3
                  and data["projectsBelowVcr1"] == ["alpha"]
                  and data["goalsActive"][0]["backpressure"] == 2)
        except Exception:
            ok = False
        check("--json consistent with markdown facts", ok, r.stdout[:400])

        # overlapping workspace roots must not double-count a project
        r = run(str(ws), str(ws / "alpha"), "--tmp-dir", str(tmp), "--json",
                cwd=Path(td))
        try:
            data = json.loads(r.stdout)
            ok = data["projectsScanned"] == 3 and data["unitsActivated"] == 2
        except Exception:
            ok = False
        check("overlapping workspace args deduped by resolved path", ok,
              r.stdout[:300])

        # 3) empty workspace is a clean run, not a crash
        empty = Path(td) / "empty"
        empty.mkdir()
        r = run(str(empty), "--tmp-dir", str(empty), cwd=Path(td))
        check("empty workspace: exit 0 and honest n/a",
              r.returncode == 0 and "n/a" in r.stdout, r.stdout[:300])

        # 4) missing workspace is a usage error
        r = run(str(Path(td) / "nope"), cwd=Path(td))
        check("missing workspace: exit 2", r.returncode == 2, r.stdout[:200])

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
