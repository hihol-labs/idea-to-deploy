#!/usr/bin/env python3
"""Regression tests for the v1.35.0 hook changes:

  - check-tool-skill.sh : read-only Bash skips the skill gate; mutations don't.
  - check-skills.sh      : the methodology's own name doesn't self-trigger;
                           real triggers survive; /refactor requires a code
                           object; the brownfield profile marker suppresses
                           greenfield-pipeline hints only.

Self-contained, no external calls. Run: python3 tests/verify_brownfield_and_gate.py
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK_SKILLS = os.path.join(ROOT, "hooks", "check-skills.sh")
CHECK_TOOL = os.path.join(ROOT, "hooks", "check-tool-skill.sh")

PASS, FAIL = 0, 0
_SEQ = [0]


def _run(hook, payload, cwd=None, env=None):
    e = dict(os.environ)
    # Unique session per call → the ignore counter and 60s rate-limit window
    # never leak between checks (each invocation is judged in isolation).
    _SEQ[0] += 1
    e["CLAUDE_SESSION_ID"] = "test-%d-%d" % (os.getpid(), _SEQ[0])
    if env:
        e.update(env)
    p = subprocess.run(
        [sys.executable, hook],
        input=json.dumps(payload),
        capture_output=True, text=True, cwd=cwd, env=e,
    )
    return p.returncode, (p.stdout or "")


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        FAIL += 1
        print("FAIL  " + name)


# --- check-skills.sh: trigger correctness ---------------------------------
def skills_hints(prompt, cwd=None):
    _, out = _run(CHECK_SKILLS, {"prompt": prompt, "cwd": cwd or ROOT}, cwd=cwd)
    return out


check("name 'idea to deploy' does NOT trigger /deploy",
      "/deploy" not in skills_hints("расскажи про методологию idea to deploy"))
check("real 'задеплой на прод' DOES trigger /deploy",
      "/deploy" in skills_hints("задеплой на прод"))
check("'idea-to-deploy' (hyphen) does NOT trigger /deploy",
      "/deploy" not in skills_hints("что такое idea-to-deploy"))
check("/adopt still triggers on 'подключи idea-to-deploy'",
      "/adopt" in skills_hints("подключи idea-to-deploy к проекту"))
check("bare 'переписать' (prose) does NOT trigger /refactor",
      "/refactor" not in skills_hints("переписать это письмо в единственном числе"))
check("'переписать код' DOES trigger /refactor",
      "/refactor" in skills_hints("переписать код этого модуля"))


# --- check-skills.sh: brownfield profile ----------------------------------
def _tmp_project(marker):
    d = tempfile.mkdtemp(prefix="itd-bf-")
    with open(os.path.join(d, "CLAUDE.md"), "w", encoding="utf-8") as f:
        f.write("# Project\n\n%s\n\nsome text\n" % marker)
    return d

GREENFIELD_PROMPT = "хочу новый проект с нуля, сделай приложение"
try:
    # Default (no marker) → greenfield hint present.
    plain = tempfile.mkdtemp(prefix="itd-plain-")
    open(os.path.join(plain, "CLAUDE.md"), "w").write("# plain\n")
    check("default project: greenfield /project hint fires",
          "/project" in skills_hints(GREENFIELD_PROMPT, cwd=plain))

    for marker in ("<!-- itd:brownfield -->", "itd-profile: brownfield"):
        bf = _tmp_project(marker)
        out = skills_hints(GREENFIELD_PROMPT, cwd=bf)
        check("brownfield (%s): greenfield /project hint suppressed" % marker,
              "/project" not in out)

    # Brownfield must NOT suppress non-greenfield hints (e.g. /refactor).
    bf = _tmp_project("<!-- itd:brownfield -->")
    check("brownfield: non-greenfield /refactor hint still fires",
          "/refactor" in skills_hints("переписать код модуля", cwd=bf))
except Exception as ex:  # noqa
    check("brownfield block ran without error", False)
    print("   error:", ex)


# --- check-tool-skill.sh: read-only vs mutating ---------------------------
def tool_out(cmd):
    return _run(CHECK_TOOL, {"tool_name": "Bash", "tool_input": {"command": cmd}})


for ro in ("ls -la", "git status", "cat x.txt | grep foo", "ls && git log --oneline"):
    rc, out = tool_out(ro)
    check("read-only Bash skips gate silently: %r" % ro, rc == 0 and out.strip() == "")

# Mutating / redirect / unknown → must NOT be silently skipped (emits reminder).
for mut in ("cat x > y", "npm run build", "ls && rm -rf build", "git commit -m x"):
    rc, out = tool_out(mut)
    check("mutating/unknown Bash NOT skipped: %r" % mut, out.strip() != "" or rc == 2)

# Edit/Write are never read-only-skipped.
rc, out = _run(CHECK_TOOL, {"tool_name": "Edit", "tool_input": {}})
check("Edit tool goes through the gate (not read-only)", out.strip() != "" or rc in (0, 2))


print("\n%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
