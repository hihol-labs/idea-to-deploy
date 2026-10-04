#!/usr/bin/env python3
"""verify_goal_verify_failpath.py - the failure path of the goal harness (GOALVERIFY-FAILPATH-1).

Defect: RSI-DEBT-3 (cd9979c) taught itd_goal_verify.py to record a compound
`A && B` verificationCommand one line per top-level command, and that branch
returns (evidence, rc) without ever binding `output`. The failure path still
ends with `print(decisive_line(output))`, so every failed compound command
died with `UnboundLocalError: ... 'output'` and a traceback instead of the
decisive `FAILED <unit> stays in_progress` report (live: TIER-WORDING-2 route).

The oracle pins the failure path by behaviour, for every way a command can
fail:

  1. compound, second leg fails  -> FAILED line, both legs in the evidence,
     the failing leg is the decisive (last) line, exit 1, no traceback,
     unit stays in_progress, a `verification_failed` event is written;
  2. compound, first leg fails   -> the short-circuited leg is not reported;
  3. single command fails        -> the output's own last line stays decisive;
  4. no POSIX sh on PATH         -> the refusal stays decisive, exit 1.

RED on the pre-fix code (cases 1-2 raise), GREEN after.
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "goal", "scripts", "itd_goal_verify.py")

fails = []


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + ((" " + detail) if (detail and not cond) else ""))
    if not cond:
        fails.append(name)


def make_ledger(tmp, unit_id, command):
    mem = os.path.join(tmp, ".itd-memory")
    os.makedirs(mem, exist_ok=True)
    goal = {
        "version": 1, "goal": "failure-path probe", "status": "active",
        "createdAt": "2026-10-02T00:00:00Z", "updatedAt": "2026-10-02T00:00:00Z",
        "currentUnitId": unit_id,
        "units": [{"id": unit_id, "criterion": "probe",
                   "verificationCommand": command, "status": "in_progress"}],
    }
    with open(os.path.join(mem, "GOAL.json"), "w", encoding="utf-8") as f:
        json.dump(goal, f, ensure_ascii=False)
    return mem


def run_verify(tmp, unit_id, env=None):
    return subprocess.run([sys.executable, SCRIPT, unit_id], cwd=tmp, env=env,
                          capture_output=True, encoding="utf-8", errors="replace",
                          timeout=60)


def read_unit(mem):
    with open(os.path.join(mem, "GOAL.json"), encoding="utf-8") as f:
        return json.load(f)["units"][0]


def failed_events(mem, unit_id):
    # A failed attempt goes to the untracked attempts journal (OTK-FAILED-ATTEMPT-1); the
    # tracked events.jsonl is read too, so a regression back into it is still counted.
    out = []
    for path in (os.path.join(mem, "events.jsonl"), os.path.join(mem, "attempts", "attempts.jsonl")):
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                if event.get("name") == unit_id and event.get("decision") == "verification_failed":
                    out.append(event)
    return out


def last_line(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[-1] if lines else ""


def common(name, r, mem, unit_id):
    check(f"{name}-exit-1", r.returncode == 1, f"rc={r.returncode} err={r.stderr[-300:]!r}")
    check(f"{name}-no-traceback",
          "Traceback" not in r.stderr and "UnboundLocalError" not in r.stderr,
          f"stderr={r.stderr[-300:]!r}")
    check(f"{name}-failed-line", f"FAILED {unit_id} stays in_progress" in r.stdout,
          f"stdout={r.stdout[-300:]!r}")
    unit = read_unit(mem)
    check(f"{name}-stays-in-progress", unit["status"] == "in_progress",
          f"status={unit['status']}")
    check(f"{name}-failed-event", len(failed_events(mem, unit_id)) == 1,
          f"events={failed_events(mem, unit_id)!r}")


# 1. compound: the second leg fails
with tempfile.TemporaryDirectory() as tmp:
    command = "echo leg-one-ok && sh -c 'echo leg-two-boom; exit 4'"
    mem = make_ledger(tmp, "F-1", command)
    r = run_verify(tmp, "F-1")
    common("compound-second", r, mem, "F-1")
    check("compound-second-per-leg-evidence",
          "echo leg-one-ok: exit 0" in r.stdout and "exit 4" in r.stdout
          and "leg-two-boom" in r.stdout, f"stdout={r.stdout[-400:]!r}")
    decisive = last_line(r.stdout)
    check("compound-second-decisive-is-failing-leg",
          "exit 4" in decisive and "leg-two-boom" in decisive, f"last={decisive!r}")

# 2. compound: the first leg fails, the second never ran
with tempfile.TemporaryDirectory() as tmp:
    command = "sh -c 'echo leg-one-boom; exit 5' && echo leg-two-never"
    mem = make_ledger(tmp, "F-2", command)
    r = run_verify(tmp, "F-2")
    common("compound-first", r, mem, "F-2")
    decisive = last_line(r.stdout)
    check("compound-first-decisive-is-failing-leg",
          "exit 5" in decisive and "leg-one-boom" in decisive, f"last={decisive!r}")
    check("compound-first-short-circuit-unreported",
          "echo leg-two-never:" not in r.stdout, f"stdout={r.stdout[-400:]!r}")

# 3. single command keeps its own decisive line
with tempfile.TemporaryDirectory() as tmp:
    mem = make_ledger(tmp, "F-3", "sh -c 'echo single-boom; exit 3'")
    r = run_verify(tmp, "F-3")
    common("single", r, mem, "F-3")
    check("single-decisive-line", last_line(r.stdout) == "single-boom",
          f"last={last_line(r.stdout)!r}")
    check("single-evidence", "exit 3: single-boom" in r.stdout, f"stdout={r.stdout[-300:]!r}")

# 4. no POSIX sh on PATH keeps the refusal decisive (POSIX hosts only: on
#    Windows the harness falls back to Git Bash by absolute path by design)
if os.name != "nt":
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as empty_bin:
        mem = make_ledger(tmp, "F-4", "echo never-runs")
        env = dict(os.environ)
        env["PATH"] = empty_bin
        r = run_verify(tmp, "F-4", env=env)
        common("no-sh", r, mem, "F-4")
        check("no-sh-decisive-line", last_line(r.stdout).startswith("no POSIX sh on PATH"),
              f"last={last_line(r.stdout)!r}")
else:
    print("skip no-sh (Windows: Git Bash fallback by absolute path)")

print()
print(f"DONE fails:{len(fails)}" + ((" " + ",".join(fails)) if fails else ""))
sys.exit(1 if fails else 0)
