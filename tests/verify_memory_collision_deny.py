#!/usr/bin/env python3
"""verify_memory_collision_deny.py - a Write over a fresh session memory file is refused
(MEMORY-COLLISION-DENY-1).

Defect: hooks/state-guard.sh (v1.84.0 P8) only *warned* when a Write was about
to replace an existing, fresh `session_*.md` memory file, and the warning was
shown once per (session, file). The Write still went through: on the
TIER-WORDING-2 route the previous session's memory file was overwritten and had
to be restored from the harness backup (BACKLOG P2 2026-10-01, item e).

The oracle drives the hook end to end through main() (stdin payload, exit code,
JSON decision) and pins:

  1. Write over a fresh existing session file -> deny (exit 2), and the reason
     names the next free suffix of that day (`_2`, skipping taken ones);
  2. the legacy private `memory/` directory is protected the same way;
  3. Edit of that file, a shell append to it, a Write to a new session file,
     a Write over a stale (older than the window) one and a Write to a
     non-session file all pass (exit 0, no deny);
  4. the refusal spends the existing per-session deny budget shared with the
     ledger gate: after two refusals the third Write passes with a warning.

RED on the pre-fix hook (cases 1, 2 and 4 pass through with a warning), GREEN after.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "state-guard.sh")

fails = []


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + ((" " + detail) if (detail and not cond) else ""))
    if not cond:
        fails.append(name)


def touch(path, content="memo", age_seconds=0):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    if age_seconds:
        ts = time.time() - age_seconds
        os.utime(path, (ts, ts))
    return path


def run_hook(env, cwd, sid, tool, tool_input):
    payload = {"hook_event_name": "PreToolUse", "session_id": sid, "cwd": cwd,
               "tool_name": tool, "tool_input": tool_input}
    res = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                         capture_output=True, encoding="utf-8", errors="replace",
                         timeout=30, env=env)
    try:
        out = json.loads(res.stdout or "{}").get("hookSpecificOutput") or {}
    except ValueError:
        out = {}
    return res.returncode, out


def denied(rc, out):
    return rc == 2 and out.get("permissionDecision") == "deny"


def passed(rc, out):
    return rc == 0 and out.get("permissionDecision") != "deny"


def main():
    with tempfile.TemporaryDirectory(prefix="itd-memcol-deny-") as tmp:
        hooktmp = os.path.join(tmp, "hooktmp")
        os.makedirs(hooktmp)
        env = dict(os.environ)
        env.pop("ITD_STATE_GUARD", None)
        env["HOME"] = env["USERPROFILE"] = os.path.join(tmp, "nohome")
        # deny-budget and warning sentinels live in tempfile.gettempdir(): keep them hermetic
        env["TMPDIR"] = env["TEMP"] = env["TMP"] = hooktmp

        proj = os.path.join(tmp, "proj")
        mem = os.path.join(proj, ".itd-memory")
        day = os.path.join(mem, "session_2026-10-03.md")
        touch(day)
        tag = f"{os.getpid()}-{int(time.time() * 1000)}"

        # 1. Write over a fresh existing session file -> deny naming the next free suffix
        rc, out = run_hook(env, proj, f"w1-{tag}", "Write", {"file_path": day, "content": "new"})
        reason = out.get("permissionDecisionReason") or ""
        check("Write over a fresh session file is denied", denied(rc, out), f"rc={rc} out={out}")
        check("deny reason names the next free suffix _2",
              "session_2026-10-03_2.md" in reason, reason[:200])

        touch(os.path.join(mem, "session_2026-10-03_2.md"))
        rc, out = run_hook(env, proj, f"w2-{tag}", "Write", {"file_path": day, "content": "new"})
        reason = out.get("permissionDecisionReason") or ""
        check("next free suffix skips a taken _2 and names _3",
              denied(rc, out) and "session_2026-10-03_3.md" in reason
              and "session_2026-10-03_2.md" not in reason, reason[:200])
        rc, out = run_hook(env, proj, f"w3-{tag}", "Write",
                           {"file_path": os.path.join(mem, "session_2026-10-03_2.md")})
        reason = out.get("permissionDecisionReason") or ""
        check("Write over a suffixed fresh file names the day's next free suffix _3",
              denied(rc, out) and "session_2026-10-03_3.md" in reason, reason[:200])

        # 2. legacy private memory/ directory
        legacy = touch(os.path.join(tmp, "nohome", ".claude", "projects", "p", "memory",
                                    "session_2026-10-03.md"))
        rc, out = run_hook(env, proj, f"w4-{tag}", "Write", {"file_path": legacy})
        check("legacy memory/ session file is protected the same way",
              denied(rc, out) and "session_2026-10-03_2.md"
              in (out.get("permissionDecisionReason") or ""), f"rc={rc}")

        # 3. what must pass
        rc, out = run_hook(env, proj, f"p1-{tag}", "Edit",
                           {"file_path": day, "old_string": "memo", "new_string": "memo2"})
        check("Edit of a fresh session file passes", passed(rc, out), f"rc={rc} out={out}")
        rc, out = run_hook(env, proj, f"p2-{tag}", "Bash",
                           {"command": f"printf 'checkpoint\\n' >> '{day}'"})
        check("a shell append to a fresh session file passes", passed(rc, out), f"rc={rc} out={out}")
        rc, out = run_hook(env, proj, f"p3-{tag}", "Write",
                           {"file_path": os.path.join(mem, "session_2026-10-03_9.md")})
        check("Write to a new session file passes silently",
              passed(rc, out) and not out.get("additionalContext"), f"rc={rc} out={out}")
        stale = touch(os.path.join(mem, "session_2026-09-01.md"), age_seconds=8 * 3600)
        rc, out = run_hook(env, proj, f"p4-{tag}", "Write", {"file_path": stale})
        check("Write over a stale session file passes", passed(rc, out), f"rc={rc} out={out}")
        notes = touch(os.path.join(mem, "notes.md"))
        rc, out = run_hook(env, proj, f"p5-{tag}", "Write", {"file_path": notes})
        check("Write to a non-session file in the memory dir passes", passed(rc, out),
              f"rc={rc} out={out}")

        # 4. shared per-session deny budget (MAX_DENIES = 2, same budget as the ledger gate)
        sid = f"b1-{tag}"
        r1 = run_hook(env, proj, sid, "Write", {"file_path": day})
        r2 = run_hook(env, proj, sid, "Write", {"file_path": day})
        r3 = run_hook(env, proj, sid, "Write", {"file_path": day})
        check("first two Writes of one session are denied", denied(*r1) and denied(*r2),
              f"{r1[0]} {r2[0]}")
        check("the third Write passes with a warning once the budget is spent",
              passed(*r3) and bool(r3[1].get("additionalContext")), f"rc={r3[0]} out={r3[1]}")

        with open(os.path.join(mem, ".active-session.lock"), "w", encoding="utf-8") as f:
            json.dump({"timestamp": time.time(), "session": "other-owner", "pid": 1,
                       "branch": "parallel", "project": proj, "note": "probe"}, f)
        sid = f"b2-{tag}"
        r1 = run_hook(env, proj, sid, "Write",
                      {"file_path": os.path.join(mem, "STATE.json"), "content": "{}"})
        r2 = run_hook(env, proj, sid, "Write", {"file_path": day})
        r3 = run_hook(env, proj, sid, "Write", {"file_path": day})
        check("a ledger refusal and a memory refusal share one budget",
              denied(*r1) and denied(*r2) and passed(*r3), f"{r1[0]} {r2[0]} {r3[0]}")

    print(f"\n{'FAILED' if fails else 'PASSED'}: {len(fails)} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
