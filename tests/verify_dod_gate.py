#!/usr/bin/env python3
"""Behavioural unit test for hooks/check-dod-before-commit.sh (v1.23.0).

Spins up throwaway git repos, stages synthetic files, toggles skill
sentinels, runs the hook with a git-commit payload on stdin, and asserts
the exit code (0 = allow, 2 = deny / DoD block).

Run: python3 tests/verify_dod_gate.py
Exits non-zero if any case fails (CI-friendly).
"""
import json
import os
import shutil
import subprocess
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO, "hooks", "check-dod-before-commit.sh")
SID = "dodgate-test-session"


def _sh(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def _sentinel(skill):
    return os.path.join(tempfile.gettempdir(), "claude-%s-done-%s" % (skill, SID))


def set_sentinels(*skills):
    for s in skills:
        with open(_sentinel(s), "w") as f:
            f.write(str(int(time.time())))


def clear_sentinels():
    for s in ("test", "migrate", "security-audit"):
        try:
            os.remove(_sentinel(s))
        except OSError:
            pass


def make_repo():
    d = tempfile.mkdtemp(prefix="dodgate-")
    _sh(["git", "init", "-q"], d)
    _sh(["git", "config", "user.email", "t@t"], d)
    _sh(["git", "config", "user.name", "t"], d)
    return d


def write(repo, path, content="x\n"):
    full = os.path.join(repo, path)
    os.makedirs(os.path.dirname(full) or repo, exist_ok=True)
    with open(full, "w") as f:
        f.write(content)
    return path


def stage(repo, path, content="x\n"):
    write(repo, path, content)
    _sh(["git", "add", path], repo)


def run_hook(repo, command="git commit -m x", description=""):
    payload = json.dumps(
        {"tool_name": "Bash",
         "tool_input": {"command": command, "description": description}}
    )
    env = dict(os.environ)
    env["CLAUDE_SESSION_ID"] = SID
    p = subprocess.run(
        ["python3", HOOK], input=payload, cwd=repo,
        capture_output=True, text=True, env=env,
    )
    return p.returncode


# Each case: (name, builder) where builder(repo) returns expected_exit_code.
def c_migration_blocks(repo):
    clear_sentinels()
    stage(repo, "db/migrations/001_init.sql")
    return 2


def c_migration_allowed_with_sentinels(repo):
    clear_sentinels()
    set_sentinels("migrate", "test")
    stage(repo, "db/migrations/001_init.sql")
    return 0


def c_schema_prisma_blocks(repo):
    clear_sentinels()
    stage(repo, "prisma/schema.prisma")
    return 2


def c_payments_blocks(repo):
    clear_sentinels()
    stage(repo, "src/auth/config.yaml")  # auth path, non-source ext -> security only
    return 2


def c_payments_allowed_with_sentinel(repo):
    clear_sentinels()
    set_sentinels("security-audit")
    stage(repo, "src/auth/config.yaml")
    return 0


def c_new_source_no_test_blocks(repo):
    clear_sentinels()
    stage(repo, "src/util.py")
    return 2


def c_new_source_with_test_allowed(repo):
    clear_sentinels()
    stage(repo, "src/util.py")
    stage(repo, "tests/test_util.py")
    return 0


def c_modified_source_no_test_allowed(repo):
    # narrowness: only BRAND-NEW source triggers /test, not modifications
    clear_sentinels()
    write(repo, "src/existing.py", "old\n")
    _sh(["git", "add", "src/existing.py"], repo)
    _sh(["git", "commit", "-qm", "seed"], repo)
    write(repo, "src/existing.py", "old\nnew line\n")
    _sh(["git", "add", "src/existing.py"], repo)
    return 0


def c_docs_only_allowed(repo):
    clear_sentinels()
    stage(repo, "README.md")
    return 0


def c_new_shell_script_allowed(repo):
    # .sh excluded from source-ext -> no /test requirement, no self-block
    clear_sentinels()
    stage(repo, "scripts/deploy.sh")
    return 0


def c_bypass_marker_allows(repo):
    clear_sentinels()
    stage(repo, "db/migrations/001_init.sql")
    return 0  # via SKILL_BYPASS in Bash description


def c_non_commit_noop(repo):
    clear_sentinels()
    stage(repo, "db/migrations/001_init.sql")
    return 0  # git status, not commit


def c_authentication_dir_blocks(repo):
    # \bauth(n|z|entication|orization)?\b must catch "authentication"
    clear_sentinels()
    stage(repo, "src/authentication/handler.yaml")
    return 2


def c_author_dir_allowed(repo):
    # ...but must NOT false-positive on "author"
    clear_sentinels()
    stage(repo, "src/author/profile.yaml")
    return 0


def c_agent_memory_blocks(repo):
    # MEMORY_RE: agent long-term memory writer w/o /security-audit -> BLOCK
    clear_sentinels()
    stage(repo, "src/agent/agent_memory_store.py")
    return 2


def c_agent_memory_allowed_with_sentinel(repo):
    # new .py also triggers /test (new-source rule); both sentinels clear it
    clear_sentinels()
    set_sentinels("security-audit", "test")
    stage(repo, "src/agent/agent_memory_store.py")
    return 0


def c_vector_store_blocks(repo):
    clear_sentinels()
    stage(repo, "app/rag/vector_store.ts")
    return 2


def c_system_prompt_blocks(repo):
    clear_sentinels()
    stage(repo, "prompts/system_prompt.yaml")
    return 2


def c_memory_word_no_false_positive(repo):
    # ordinary file that merely contains "memory" must NOT trip MEMORY_RE
    clear_sentinels()
    stage(repo, "docs/memory-usage-notes.md")
    return 0


CASES = [
    ("migration without skills -> BLOCK", c_migration_blocks, "git commit -m x"),
    ("migration with migrate+test -> allow", c_migration_allowed_with_sentinels, "git commit -m x"),
    ("schema.prisma without skills -> BLOCK", c_schema_prisma_blocks, "git commit -m x"),
    ("payments/auth without security-audit -> BLOCK", c_payments_blocks, "git commit -m x"),
    ("payments/auth with security-audit -> allow", c_payments_allowed_with_sentinel, "git commit -m x"),
    ("authentication dir -> BLOCK (security)", c_authentication_dir_blocks, "git commit -m x"),
    ("author dir -> allow (no false-positive)", c_author_dir_allowed, "git commit -m x"),
    ("new source file no test -> BLOCK", c_new_source_no_test_blocks, "git commit -m x"),
    ("new source file with test -> allow", c_new_source_with_test_allowed, "git commit -m x"),
    ("modified source (not new) no test -> allow", c_modified_source_no_test_allowed, "git commit -m x"),
    ("docs-only change -> allow", c_docs_only_allowed, "git commit -m x"),
    ("new shell script -> allow (excluded)", c_new_shell_script_allowed, "git commit -m x"),
    ("SKILL_BYPASS in description -> allow", c_bypass_marker_allows, "git commit -m x"),
    ("non-commit bash -> no-op allow", c_non_commit_noop, "git status"),
    ("agent memory store no skill -> BLOCK", c_agent_memory_blocks, "git commit -m x"),
    ("agent memory store with security-audit -> allow", c_agent_memory_allowed_with_sentinel, "git commit -m x"),
    ("vector store no skill -> BLOCK", c_vector_store_blocks, "git commit -m x"),
    ("system prompt file no skill -> BLOCK", c_system_prompt_blocks, "git commit -m x"),
    ("memory word doc -> allow (no false-positive)", c_memory_word_no_false_positive, "git commit -m x"),
]


def main():
    passed = 0
    failed = 0
    for name, builder, command in CASES:
        repo = make_repo()
        try:
            expected = builder(repo)
            desc = "SKILL_BYPASS: test bypass" if "BYPASS" in name else ""
            got = run_hook(repo, command, desc)
            ok = got == expected
            print("%s  %-48s expected=%d got=%d" % (
                "PASS" if ok else "FAIL", name, expected, got))
            if ok:
                passed += 1
            else:
                failed += 1
        finally:
            shutil.rmtree(repo, ignore_errors=True)
    clear_sentinels()
    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
