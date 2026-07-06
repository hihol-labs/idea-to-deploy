#!/usr/bin/env python3
"""Behavioural deny/allow test for hooks/check-skill-completeness.sh
(hard gate #4, unit G-003).

Like check-commit-completeness, this gate had no test that actually drove it
to `deny` — only a structural reference (verify_worktree_hook_safety), so its
HARNESS_MAP ✅ was unproven. This test spawns the hook (PreToolUse on
Write/Edit) against a real temp methodology repo and asserts a real exit-2
deny (and an exit-0 allow).

The gate fires inside a methodology repo (walks up to
`.claude-plugin/plugin.json`) when a Write/Edit to `skills/<name>/SKILL.md`
has pending content that references `references/` while the folder is absent
(or is missing trigger phrases / a fixture).

Run: python3 tests/verify_skill_completeness_gate.py
Exits non-zero if any case fails (CI-friendly).
"""
import json
import os
import subprocess
import tempfile
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO, "hooks", "check-skill-completeness.sh")


def make_meth_repo():
    d = tempfile.mkdtemp(prefix="skillcomplete-")
    os.makedirs(os.path.join(d, ".claude-plugin"))
    with open(os.path.join(d, ".claude-plugin", "plugin.json"), "w") as f:
        f.write('{"name":"x","version":"0.0.0"}\n')
    os.makedirs(os.path.join(d, "skills", "foo"))
    return d


def run_gate(d, content):
    fp = os.path.join(d, "skills", "foo", "SKILL.md")
    payload = json.dumps({
        "tool_name": "Write",
        "tool_input": {"file_path": fp, "content": content},
    })
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

    # 1. content references `references/` but the folder is absent -> DENY
    d = make_meth_repo()
    try:
        content = ("---\nname: foo\ndisable-model-invocation: true\n---\n\n"
                   "See references/checklist.md for the rubric.\n")
        check("SKILL.md referencing missing references/ -> DENY (exit 2)",
              run_gate(d, content) == 2)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # 2. complete content (no refs mention, trigger-exempt, no fixtures) -> ALLOW
    d = make_meth_repo()
    try:
        content = ("---\nname: foo\ndisable-model-invocation: true\n---\n\n"
                   "A self-contained skill body with no external references.\n")
        check("complete SKILL.md -> ALLOW (exit 0)", run_gate(d, content) == 0)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # 3. references/ mention WITH the folder present and non-empty -> ALLOW
    d = make_meth_repo()
    try:
        refs = os.path.join(d, "skills", "foo", "references")
        os.makedirs(refs)
        with open(os.path.join(refs, "checklist.md"), "w") as f:
            f.write("- rubric\n")
        content = ("---\nname: foo\ndisable-model-invocation: true\n---\n\n"
                   "See references/checklist.md for the rubric.\n")
        check("SKILL.md with references/ present -> ALLOW (exit 0)",
              run_gate(d, content) == 0)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # 4. outside a methodology repo -> no-op ALLOW (exit 0)
    d = tempfile.mkdtemp(prefix="skillcomplete-nonmeth-")
    try:
        os.makedirs(os.path.join(d, "skills", "foo"))
        content = "See references/x.md\n"
        check("non-methodology repo -> no-op ALLOW (exit 0)",
              run_gate(d, content) == 0)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
