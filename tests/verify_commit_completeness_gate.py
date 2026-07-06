#!/usr/bin/env python3
"""Behavioural deny/allow test for hooks/check-commit-completeness.sh
(hard gate #3, unit G-003).

This gate had NO test that actually drove it to `deny` — it was referenced
only structurally (verify_hook_depth), so its HARNESS_MAP ✅ was a
doc-vs-enforcement claim, not a proven block. This test spawns the hook as a
subprocess against a real temp methodology repo and asserts a real exit-2
deny (and an exit-0 allow once the gap is filled).

The gate fires only inside a methodology repo (detected by walking up to
`.claude-plugin/plugin.json`) on a `git commit` whose staged diff adds a
`skills/<name>/SKILL.md` that mentions `references/` without staging the
supporting artifacts.

Run: python3 tests/verify_commit_completeness_gate.py
Exits non-zero if any case fails (CI-friendly).
"""
import json
import os
import subprocess
import tempfile
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO, "hooks", "check-commit-completeness.sh")


def _sh(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def make_meth_repo():
    d = tempfile.mkdtemp(prefix="commitcomplete-")
    _sh(["git", "init", "-q"], d)
    _sh(["git", "config", "user.email", "t@t"], d)
    _sh(["git", "config", "user.name", "t"], d)
    # methodology-repo marker the gate walks up to find
    os.makedirs(os.path.join(d, ".claude-plugin"))
    with open(os.path.join(d, ".claude-plugin", "plugin.json"), "w") as f:
        f.write('{"name":"x","version":"0.0.0"}\n')
    _sh(["git", "add", ".claude-plugin/plugin.json"], d)
    _sh(["git", "commit", "-qm", "base"], d)
    return d


def stage_skill(d, with_support):
    skdir = os.path.join(d, "skills", "foo")
    os.makedirs(skdir, exist_ok=True)
    with open(os.path.join(skdir, "SKILL.md"), "w") as f:
        f.write("---\nname: foo\n---\n\nSee references/checklist.md for details.\n")
    _sh(["git", "add", "skills/foo/SKILL.md"], d)
    if with_support:
        # add the referenced file, the trigger wiring, and a fixture
        os.makedirs(os.path.join(skdir, "references"), exist_ok=True)
        with open(os.path.join(skdir, "references", "checklist.md"), "w") as f:
            f.write("- a checklist\n")
        _sh(["git", "add", "skills/foo/references/checklist.md"], d)
        fxdir = os.path.join(d, "tests", "fixtures", "fixture-foo")
        os.makedirs(fxdir, exist_ok=True)
        with open(os.path.join(fxdir, "notes.md"), "w") as f:
            f.write("triggers /foo\n")
        _sh(["git", "add", "tests/fixtures/fixture-foo/notes.md"], d)
        # touch the trigger wiring the gate looks for
        hookdir = os.path.join(d, "hooks")
        os.makedirs(hookdir, exist_ok=True)
        with open(os.path.join(hookdir, "check-skills.sh"), "w") as f:
            f.write("# foo trigger\n")
        _sh(["git", "add", "hooks/check-skills.sh"], d)


def run_gate(d):
    payload = json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}})
    return subprocess.run(["python3", HOOK], input=payload, cwd=d,
                          capture_output=True, text=True).returncode


def main():
    passed = failed = 0

    def check(name, cond):
        nonlocal passed, failed
        print("%s  %s" % ("PASS" if cond else "FAIL", name))
        if cond:
            passed += 1
        else:
            failed += 1

    # 1. SKILL.md mentioning references/ staged WITHOUT support -> DENY (exit 2)
    d = make_meth_repo()
    try:
        stage_skill(d, with_support=False)
        rc = run_gate(d)
        check("incomplete skill commit -> DENY (exit 2)", rc == 2)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # 2. Same but WITH the supporting artifacts staged -> ALLOW (exit 0)
    d = make_meth_repo()
    try:
        stage_skill(d, with_support=True)
        rc = run_gate(d)
        check("complete skill commit -> ALLOW (exit 0)", rc == 0)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # 3. Outside a methodology repo -> no-op ALLOW (exit 0)
    d = tempfile.mkdtemp(prefix="commitcomplete-nonmeth-")
    try:
        _sh(["git", "init", "-q"], d)
        _sh(["git", "config", "user.email", "t@t"], d)
        _sh(["git", "config", "user.name", "t"], d)
        skdir = os.path.join(d, "skills", "foo")
        os.makedirs(skdir)
        with open(os.path.join(skdir, "SKILL.md"), "w") as f:
            f.write("See references/x.md\n")
        _sh(["git", "add", "skills/foo/SKILL.md"], d)
        check("non-methodology repo -> no-op ALLOW (exit 0)", run_gate(d) == 0)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
