#!/usr/bin/env python3
"""Behavioural unit test for the mandatory-review checkpoint reminder.

The hook itself is a read-only reminder (always exit 0); it never mints review
evidence. Sensitive commits always receive the canonical-route reminder.

Each case spins up a throwaway git repo, stages synthetic files, and runs the
hook with a JSON payload on stdin. PATH is stripped of reviewer CLIs so a
regression cannot perform an external call.

Run: python3 tests/verify_cross_review_precommit.py
Exits non-zero if any case fails (CI-friendly).
"""
import json
import os
import shutil
import subprocess
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO, "hooks", "cross-review-precommit.sh")

# Minimal PATH: coreutils/git/python3/bash/setsid live here; codex (in
# ~/.npm-global/bin) deliberately does NOT, so the worker degrades to engine=none.
SAFE_PATH = "/usr/local/bin:/usr/bin:/bin"

REMIND = "remind"       # expect explicit isolated-review reminder
SKIP = "skip"           # expect no egress, hook silent


def _sh(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def make_repo():
    d = tempfile.mkdtemp(prefix="xreview-")
    _sh(["git", "init", "-q"], d)
    _sh(["git", "config", "user.email", "t@t"], d)
    _sh(["git", "config", "user.name", "t"], d)
    return d


def stage(repo, path, content="x\n"):
    full = os.path.join(repo, path)
    os.makedirs(os.path.dirname(full) or repo, exist_ok=True)
    with open(full, "w") as f:
        f.write(content)
    _sh(["git", "add", path], repo)
    return path


def run_hook(repo, command="git commit -m x", env_overrides=None):
    payload = json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": command, "description": ""}}
    )
    env = {
        "PATH": SAFE_PATH,
        "HOME": os.environ.get("HOME", repo),
        "TMPDIR": tempfile.mkdtemp(prefix="xreview-tmp-"),
        # Inject a dummy engine via the override so the detached worker never
        # fires a real (paid) external call during testing — /bin/false exists
        # and exits non-zero, so run_engine reports "unavailable" deterministically
        # (and resolve_engine never reaches its desktop/PATH discovery).
        "CROSS_REVIEW_CODEX_BIN": "/bin/false",
        "CROSS_REVIEW_GEMINI_BIN": "/bin/false",
    }
    if env_overrides:
        env.update(env_overrides)
    p = subprocess.run(
        ["python3", HOOK], input=payload, cwd=repo,
        capture_output=True, text=True, env=env,
    )
    shutil.rmtree(env["TMPDIR"], ignore_errors=True)
    acted = "canonical OpenAI -> Anthropic -> Gemini" in (p.stdout or "")
    return p.returncode, (REMIND if acted else SKIP), p.stdout


# --- cases: builder(repo) -> (command, env_overrides, expected_action) --------
def c_optin_env_migration(repo):
    stage(repo, "db/migrations/001_init.sql")
    return "git commit -m x", {"CROSS_REVIEW_EGRESS_OK": "1"}, REMIND


def c_optin_marker_auth(repo):
    # marker file at repo root opts in (auditable, per-repo)
    open(os.path.join(repo, ".cross-review-egress-ok"), "w").close()
    stage(repo, "src/auth/login.py")
    return "git commit -m x", {}, REMIND


def c_default_sensitive(repo):
    # no marker/env is needed: this is a local reminder, not egress
    stage(repo, "db/migrations/001_init.sql")
    return "git commit -m x", {}, REMIND


def c_optin_nonsensitive(repo):
    # opted in, but the staged path is not correctness-critical -> skip
    stage(repo, "README.md")
    return "git commit -m x", {"CROSS_REVIEW_EGRESS_OK": "1"}, SKIP


def c_non_commit(repo):
    # not a commit at all -> no-op
    stage(repo, "db/migrations/001_init.sql")
    return "git status", {"CROSS_REVIEW_EGRESS_OK": "1"}, SKIP


def c_off_switch(repo):
    # a caller flag cannot suppress the mandatory-route checkpoint
    stage(repo, "db/migrations/001_init.sql")
    return "git commit -m x", {"ITD_CROSS_REVIEW": "0"}, REMIND


def c_agent_teams_disabled(repo):
    # reminder is safe in multi-agent mode because it never sends the diff
    stage(repo, "db/migrations/001_init.sql")
    return ("git commit -m x",
            {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}, REMIND)


def c_agent_teams_override(repo):
    # Agent Teams on, but explicit CROSS_REVIEW_ALLOW_AGENT_TEAMS=1 -> dispatch
    stage(repo, "db/migrations/001_init.sql")
    return ("git commit -m x",
            {"CROSS_REVIEW_EGRESS_OK": "1",
             "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
             "CROSS_REVIEW_ALLOW_AGENT_TEAMS": "1"},
            REMIND)


def c_payments_path(repo):
    open(os.path.join(repo, ".cross-review-egress-ok"), "w").close()
    stage(repo, "app/billing/payment_service.ts")
    return "git commit -m x", {}, REMIND


def c_amp_chain_commit(repo):
    # commit reached via && chain still triggers
    stage(repo, "prisma/schema.prisma")
    return "git add -A && git commit -m x", {"CROSS_REVIEW_EGRESS_OK": "1"}, REMIND


CASES = [
    ("opt-in(env) + migration -> REMIND", c_optin_env_migration),
    ("opt-in(marker) + auth -> REMIND", c_optin_marker_auth),
    ("sensitive default -> REMIND", c_default_sensitive),
    ("opted-in but non-sensitive path -> SKIP", c_optin_nonsensitive),
    ("not a commit -> SKIP", c_non_commit),
    ("caller off-switch cannot bypass reminder", c_off_switch),
    ("Agent Teams mode -> REMIND", c_agent_teams_disabled),
    ("Agent Teams + override -> REMIND", c_agent_teams_override),
    ("opt-in + payments path -> REMIND", c_payments_path),
    ("commit via && chain -> REMIND", c_amp_chain_commit),
]


def main():
    passed = failed = 0
    for name, builder in CASES:
        repo = make_repo()
        try:
            command, env_over, expected = builder(repo)
            rc, action, _stderr = run_hook(repo, command, env_over)
            ok = (rc == 0) and (action == expected)
            print("%s  %-50s rc=%d action=%-8s expected=%s" % (
                "PASS" if ok else "FAIL", name, rc, action, expected))
            passed += ok
            failed += not ok
        finally:
            shutil.rmtree(repo, ignore_errors=True)
    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
