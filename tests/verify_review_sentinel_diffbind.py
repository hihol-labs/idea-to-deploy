#!/usr/bin/env python3
"""Behavioural test for the v1.59.0 DIFF-BINDING of the /review gate
(hooks/check-review-before-commit.sh + its two sentinel writers).

Before v1.59.0 the gate unblocked a >2-file `git commit` on ANY fresh
`claude-review-done-*` sentinel (bare timestamp), so a stale review or a
sentinel from an unrelated project wildcarded the gate (documented hole,
PR #56 era). v1.59.0 binds the sentinel to `tree:<git-write-tree>` — the
SHA of the exact staged content — and the gate accepts it only when it
equals the tree the pending commit would write.

Asserts (each is a real block/deny exercise, not a doc grep):
  1. No sentinel, 3 staged  -> DENY (exit 2).
  2. Foreign/stale tree sentinel (wrong hash), fresh -> DENY.
  3. Legacy bare-timestamp sentinel, fresh -> DENY (no wildcard anymore).
  4. Sentinel bound to the current staged tree -> ALLOW (exit 0).
  5. Staleness: matching sentinel, then stage another file (tree changes)
     -> the old sentinel no longer matches -> DENY.
  6. <=2 staged files -> ALLOW regardless (below the review threshold).
  7. record-agent-skill.sh writes a tree-bound review sentinel for the
     code-reviewer subagent, and the gate then ALLOWS (end-to-end).
  8. Both writers are wired to the binding: /review SKILL.md uses
     `git write-tree` + `tree:`, and record-agent-skill.sh emits `tree:`.

Run: python3 tests/verify_review_sentinel_diffbind.py
Exits non-zero if any case fails (CI-friendly).
"""
import glob
import json
import os
import subprocess
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEW_HOOK = os.path.join(REPO, "hooks", "check-review-before-commit.sh")
REC_HOOK = os.path.join(REPO, "hooks", "record-agent-skill.sh")
SKILL_MD = os.path.join(REPO, "skills", "review", "SKILL.md")
SID = "diffbind-test-session"

SENTINEL_DIRS = []
for _d in ("/tmp", tempfile.gettempdir()):
    if _d and _d not in SENTINEL_DIRS:
        SENTINEL_DIRS.append(_d)


def clear_sentinels():
    for d in SENTINEL_DIRS:
        for p in glob.glob(os.path.join(d, "claude-review-done-*")):
            try:
                os.remove(p)
            except OSError:
                pass


def write_sentinel(content):
    for d in SENTINEL_DIRS:
        try:
            with open(os.path.join(d, "claude-review-done-%s" % SID), "w") as f:
                f.write(content)
        except OSError:
            pass


def _sh(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def make_repo(n):
    d = tempfile.mkdtemp(prefix="diffbind-")
    _sh(["git", "init", "-q"], d)
    _sh(["git", "config", "user.email", "t@t"], d)
    _sh(["git", "config", "user.name", "t"], d)
    # baseline commit so `git write-tree` reflects real staged deltas
    with open(os.path.join(d, "base.txt"), "w") as f:
        f.write("base\n")
    _sh(["git", "add", "base.txt"], d)
    _sh(["git", "commit", "-qm", "base"], d)
    for i in range(n):
        with open(os.path.join(d, "f%d.txt" % i), "w") as f:
            f.write("x%d\n" % i)
        _sh(["git", "add", "f%d.txt" % i], d)
    return d


def staged_tree(repo):
    r = subprocess.run(["git", "write-tree"], cwd=repo,
                       capture_output=True, text=True)
    return r.stdout.strip()


def run_gate(repo):
    payload = json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}})
    env = dict(os.environ)
    env["CLAUDE_SESSION_ID"] = SID
    return subprocess.run(["python3", REVIEW_HOOK], input=payload, cwd=repo,
                          capture_output=True, text=True, env=env).returncode


def run_record(repo):
    payload = json.dumps({"tool_name": "Agent",
                          "tool_input": {"subagent_type": "code-reviewer"}})
    env = dict(os.environ)
    env["CLAUDE_SESSION_ID"] = SID
    subprocess.run(["python3", REC_HOOK], input=payload, cwd=repo,
                   capture_output=True, text=True, env=env)


def sentinel_content():
    for d in SENTINEL_DIRS:
        p = os.path.join(d, "claude-review-done-%s" % SID)
        if os.path.exists(p):
            with open(p) as f:
                return f.read().strip()
    return None


def main():
    passed = failed = 0

    def check(name, cond):
        nonlocal passed, failed
        print("%s  %s" % ("PASS" if cond else "FAIL", name))
        if cond:
            passed += 1
        else:
            failed += 1

    import shutil
    repo = make_repo(3)
    try:
        # 1. no sentinel -> deny
        clear_sentinels()
        check("no sentinel, 3 staged -> DENY", run_gate(repo) == 2)

        # 2. foreign/wrong tree -> deny
        clear_sentinels()
        write_sentinel("tree:" + "a" * 40)
        check("foreign tree sentinel -> DENY", run_gate(repo) == 2)

        # 3. legacy bare timestamp -> deny (no wildcard)
        clear_sentinels()
        import time
        write_sentinel(str(int(time.time())))
        check("legacy bare-timestamp sentinel -> DENY", run_gate(repo) == 2)

        # 4. matching tree -> allow
        clear_sentinels()
        write_sentinel("tree:" + staged_tree(repo))
        check("sentinel bound to current staged tree -> ALLOW", run_gate(repo) == 0)

        # 5. staleness: stage another file, old sentinel no longer matches
        with open(os.path.join(repo, "extra.txt"), "w") as f:
            f.write("more\n")
        _sh(["git", "add", "extra.txt"], repo)
        check("staged tree changed after review -> DENY (stale)", run_gate(repo) == 2)

        # 6. <=2 staged -> allow regardless
        repo2 = make_repo(2)
        try:
            clear_sentinels()
            check("<=2 staged files -> ALLOW (below threshold)", run_gate2(repo2) == 0)
        finally:
            shutil.rmtree(repo2, ignore_errors=True)

        # 7. end-to-end: record-agent-skill writes bound sentinel -> allow
        repo3 = make_repo(3)
        try:
            clear_sentinels()
            before = run_gate3(repo3)
            run_record(repo3)
            after = run_gate3(repo3)
            check("record-agent-skill: gate DENIES before agent", before == 2)
            check("record-agent-skill: gate ALLOWS after code-reviewer", after == 0)
            check("record-agent-skill sentinel is tree-bound",
                  (sentinel_content() or "").startswith("tree:"))
        finally:
            shutil.rmtree(repo3, ignore_errors=True)
    finally:
        shutil.rmtree(repo, ignore_errors=True)

    # 8. FAIL-CLOSED on unknown tree (regression guard for the review fix):
    #    when git can't fingerprint the tree (staged_tree_hash() -> None),
    #    a fresh FOREIGN tree:-bound sentinel must NOT unblock. Load the hook
    #    module and stub staged_tree_hash to simulate a git fault.
    import importlib.util
    import importlib.machinery
    # .sh extension: importlib can't infer a loader, so name a SourceFileLoader
    loader = importlib.machinery.SourceFileLoader("chk_review", REVIEW_HOOK)
    spec = importlib.util.spec_from_loader("chk_review", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    clear_sentinels()
    write_sentinel("tree:" + "a" * 40)  # foreign, fresh, well-formed
    orig = mod.staged_tree_hash
    try:
        mod.staged_tree_hash = lambda: None  # simulate git write-tree failure
        os.environ["CLAUDE_SESSION_ID"] = SID
        check("git-fault (tree=None) + foreign sentinel -> NOT done (fail-closed)",
              mod.review_was_done() is False)
    finally:
        mod.staged_tree_hash = orig
    clear_sentinels()

    # 9. both writers wired to binding (source assertions)
    with open(SKILL_MD, encoding="utf-8") as f:
        skill_src = f.read()
    check("/review SKILL.md computes git write-tree",
          "git write-tree" in skill_src and "tree:$tree" in skill_src)
    with open(REC_HOOK, encoding="utf-8") as f:
        rec_src = f.read()
    check("record-agent-skill.sh emits tree-bound review sentinel",
          "write-tree" in rec_src and 'return "tree:' in rec_src)

    clear_sentinels()
    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


# run_gate variants bound to specific repos (cwd differs per case)
def run_gate2(repo):
    return run_gate(repo)


def run_gate3(repo):
    return run_gate(repo)


if __name__ == "__main__":
    raise SystemExit(main())
