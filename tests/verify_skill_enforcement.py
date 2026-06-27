#!/usr/bin/env python3
"""Behavioural unit test for hooks/check-tool-skill.sh (v1.24.0).

Covers the skill-enforcement counter and the new skill-active grace window
(infra fix #2). Drives the hook with synthetic PreToolUse payloads on stdin,
toggling the per-session state files, and asserts both the exit code
(0 = allow, 2 = deny / enforcement block) and the resulting counter / sentinel
state.

The headline guarantees, locked here against regression:
  * enforcement STILL blocks after MAX_IGNORES consecutive ignores
    (the "never-block" bug must never come back), and
  * a STALE skill-active sentinel does NOT suppress the block
    (one early skill must not disable enforcement for the whole session).

Run: python3 tests/verify_skill_enforcement.py
Exits non-zero if any case fails (CI-friendly).
"""
import json
import os
import subprocess
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO, "hooks", "check-tool-skill.sh")
CHECK_SKILLS = os.path.join(REPO, "hooks", "check-skills.sh")
SID = "skillenf-test-session"
TMP = tempfile.gettempdir()

IGNORES = os.path.join(TMP, "claude-skill-ignores-%s.state" % SID)
REMINDER = os.path.join(TMP, "claude-skill-check-%s.state" % SID)
ACTIVE = os.path.join(TMP, "claude-skill-active-%s.state" % SID)

# Must mirror the constants in the hook.
MAX_IGNORES = 3
TTL = 900


def _rm(*paths):
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass


def reset_state():
    _rm(IGNORES, REMINDER, ACTIVE)


def set_count(n):
    with open(IGNORES, "w") as f:
        f.write(str(n))


def read_count():
    try:
        with open(IGNORES) as f:
            return int(f.read().strip() or "0")
    except OSError:
        return 0


def allow_reminder():
    """Make should_remind() return True (no recent reminder)."""
    _rm(REMINDER)


def suppress_reminder():
    """Make should_remind() return False (reminded just now)."""
    with open(REMINDER, "w") as f:
        f.write(str(time.time()))


def set_active(age_seconds):
    with open(ACTIVE, "w") as f:
        f.write(str(time.time() - age_seconds))


def run_hook(tool, description=""):
    payload = json.dumps(
        {"tool_name": tool, "tool_input": {"description": description}}
    )
    env = dict(os.environ)
    env["CLAUDE_SESSION_ID"] = SID
    p = subprocess.run(
        ["python3", HOOK], input=payload,
        capture_output=True, text=True, env=env,
    )
    return p.returncode, (p.stdout or "")


# Each case returns (ok, detail).
def c_block_after_max_ignores():
    """REGRESSION: enforcement must still block (never-block guard)."""
    reset_state()
    set_count(MAX_IGNORES)
    rc, out = run_hook("Edit")
    return rc == 2 and "deny" in out, "rc=%d" % rc


def c_skill_resets_and_marks_active():
    reset_state()
    set_count(MAX_IGNORES)
    rc, _ = run_hook("Skill")
    fresh = os.path.exists(ACTIVE)
    return rc == 0 and read_count() == 0 and fresh, \
        "rc=%d count=%d active=%s" % (rc, read_count(), fresh)


def c_fresh_sentinel_grants_grace():
    reset_state()
    set_count(MAX_IGNORES)
    set_active(5)  # 5s old -> fresh
    rc, _ = run_hook("Edit")
    return rc == 0 and read_count() == 0, \
        "rc=%d count=%d" % (rc, read_count())


def c_stale_sentinel_still_blocks():
    """REGRESSION: an expired grace window must NOT disable enforcement."""
    reset_state()
    set_count(MAX_IGNORES)
    set_active(TTL + 100)  # older than TTL -> stale
    rc, out = run_hook("Edit")
    return rc == 2 and "deny" in out, "rc=%d" % rc


def c_bypass_marker_resets():
    reset_state()
    set_count(MAX_IGNORES)
    rc, _ = run_hook("Bash", "SKILL_BYPASS: legitimate reason")
    return rc == 0 and read_count() == 0, \
        "rc=%d count=%d" % (rc, read_count())


def c_reminder_increments():
    reset_state()
    set_count(0)
    allow_reminder()
    rc, out = run_hook("Edit")
    return rc == 0 and read_count() == 1 and "SKILL CHECK" in out, \
        "rc=%d count=%d" % (rc, read_count())


def c_rate_limited_no_increment():
    reset_state()
    set_count(1)
    suppress_reminder()
    rc, _ = run_hook("Edit")
    return rc == 0 and read_count() == 1, \
        "rc=%d count=%d" % (rc, read_count())


def _run_check_skills(prompt):
    env = dict(os.environ)
    env["CLAUDE_SESSION_ID"] = SID
    subprocess.run(
        ["python3", CHECK_SKILLS], input=json.dumps({"prompt": prompt}),
        capture_output=True, text=True, env=env,
    )


def c_e2e_trigger_prompt_opens_grace():
    """End-to-end contract: a skill-trigger prompt in check-skills.sh writes
    the sentinel that check-tool-skill.sh honours -> Edit flow not blocked."""
    reset_state()
    _run_check_skills("почини баг в users.py")  # matches /bugfix trigger
    set_count(MAX_IGNORES)
    rc, _ = run_hook("Edit")
    return rc == 0 and read_count() == 0, "rc=%d count=%d" % (rc, read_count())


def c_e2e_nontrigger_prompt_keeps_enforcement():
    """A non-methodology prompt writes no sentinel -> enforcement still blocks."""
    reset_state()
    _run_check_skills("привет, как дела")  # no trigger
    set_count(MAX_IGNORES)
    rc, out = run_hook("Edit")
    return rc == 2 and "deny" in out, "rc=%d" % rc


def _session_id_code(path):
    """Return the executable lines of `def session_id` in a hook file, stripped
    of comments, docstrings and blank lines, so two copies can be compared for
    behavioural drift regardless of surrounding comments."""
    with open(path, encoding="utf-8") as f:
        src = f.read()
    after = src.split("def session_id", 1)[1]
    body = after.split("\ndef ", 1)[0]  # up to the next top-level def
    out = []
    for raw in body.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith('"""') or s.startswith("'''"):  # one-line docstring
            continue
        out.append(s)
    return out


def c_session_id_no_drift():
    """M-1 guard: session_id() must be behaviourally identical in both hooks,
    or the sentinel paths silently stop matching."""
    a = _session_id_code(HOOK)
    b = _session_id_code(CHECK_SKILLS)
    return a == b and len(a) > 5, "tool=%d skills=%d" % (len(a), len(b))


CASES = [
    ("block after MAX_IGNORES (never-block guard)", c_block_after_max_ignores),
    ("Skill call resets counter + marks active", c_skill_resets_and_marks_active),
    ("fresh skill-active sentinel grants grace", c_fresh_sentinel_grants_grace),
    ("stale sentinel still blocks (no forever-grace)", c_stale_sentinel_still_blocks),
    ("SKILL_BYPASS in description resets", c_bypass_marker_resets),
    ("reminder increments counter below max", c_reminder_increments),
    ("rate-limited reminder does not increment", c_rate_limited_no_increment),
    ("e2e: trigger prompt opens grace window", c_e2e_trigger_prompt_opens_grace),
    ("e2e: non-trigger prompt keeps enforcement", c_e2e_nontrigger_prompt_keeps_enforcement),
    ("session_id() has no drift between hooks", c_session_id_no_drift),
]


def main():
    passed = failed = 0
    for name, fn in CASES:
        try:
            ok, detail = fn()
        except Exception as e:  # noqa: BLE001
            ok, detail = False, "exception: %r" % e
        print("%s  %-50s %s" % ("PASS" if ok else "FAIL", name, detail))
        if ok:
            passed += 1
        else:
            failed += 1
    reset_state()
    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
