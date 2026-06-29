#!/usr/bin/env python3
"""
PreToolUse hook on Bash — OPT-IN, NON-BLOCKING cross-vendor second opinion at
commit (idea-to-deploy v1.34.0).

Fires before `git commit`. When the repo has OPTED IN to external egress AND the
staged diff touches a correctness-critical / sensitive path (migrations, money,
auth, secrets), it dispatches a BACKGROUND cross-vendor review of the scrubbed
diff (codex -> gemini) and writes findings to a notes file. It then returns
IMMEDIATELY with exit 0 — it NEVER blocks the commit.

This is the "continuous" companion to the on-demand /cross-review skill, and the
deliberate OPPOSITE of check-dod-before-commit.sh: the DoD gate BLOCKS (deny);
this one only ADVISES (fail-open, never a gate). It reuses the DoD gate's
risk-signal paths as the trigger surface, nothing more.

Design constraints (see docs/adr/ADR-002-cross-review-opt-in-precommit.md):
  • DEFAULT-OFF. Egress to a third-party model (OpenAI Codex / Google Gemini)
    happens ONLY when explicitly opted in, via either:
      - env  CROSS_REVIEW_EGRESS_OK=1            (per-machine), or
      - a  .cross-review-egress-ok  marker file at the repo root. The marker is
        detected by PRESENCE in the working tree, so it can be local/untracked
        (e.g. listed in .git/info/exclude) and never enter a commit or PR —
        nothing lands in the reviewed repo. Committing it is reserved for a
        deliberate team-wide opt-in, not the default.
  • ASYNC. The external CLI (8-30s, can hang under a flaky VPN) runs in a
    detached child (os.fork + setsid); the hook itself returns in well under its
    5s registration timeout.
  • AUTO-DISABLED in multi-agent / shared-worktree mode (Agent Teams, linked
    worktree) — "which diff?" is undefined when concurrent agents share a tree,
    and we must never egress another agent's uncommitted code.
  • SCRUB before egress (same patterns as pii-egress-guard.sh). If a live
    credential survives scrubbing, the diff is NOT sent — it degrades to a note.
  • Findings are NOTES, not a gate. This hook MUST NOT write the
    /tmp/claude-review-done-* sentinel — that belongs to /review.

Disable entirely (even when opted in): ITD_CROSS_REVIEW=0.
Reads JSON on stdin: {"tool_name":"Bash","tool_input":{"command":"..."}}

Fail-open: ANY error path -> exit 0 (allow, never block).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

GIT_COMMIT_RE = re.compile(r"(^|[ ;&|])git\s+commit(\s|$)")

# --- sensitive-path signals (mirror check-dod-before-commit.sh) ---------------
MIGRATION_RE = re.compile(r"(^|/)migrations?/|\.sql$|schema\.prisma$|(^|/)alembic/", re.I)
MONEY_AUTH_RE = re.compile(
    r"(payment|payout|billing|invoice|\bbank\b|\bwallet\b|"
    r"\bauth(?:n|z|entication|orization)?\b|oauth|\bjwt\b|\blogin\b|"
    r"\bpasswords?\b|passwd|\bsecrets?\b|\btokens?\b|\bcredentials?\b|crypto)",
    re.I,
)

# --- scrub patterns (value, replacement) — same coverage as pii-egress-guard --
SCRUB_SUBS = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----.*?"
                r"-----END (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----", re.S),
     "[REDACTED-PRIVATE-KEY]"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "[REDACTED-AWS-KEY]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "[REDACTED-GH-TOKEN]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), "[REDACTED-SLACK-TOKEN]"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}"), "[REDACTED-GOOGLE-KEY]"),
    (re.compile(r"\b[rs]k_live_[A-Za-z0-9]{16,}"), "[REDACTED-STRIPE-KEY]"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"), "[REDACTED-ANTHROPIC-KEY]"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}"), "[REDACTED-KEY]"),
    (re.compile(r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._\-]{20,}"), r"\1[REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[REDACTED-EMAIL]"),
    (re.compile(r"(?i)(password|passwd|api[_-]?key|secret|token)(\s*[=:]\s*)[^\s\"'&]{6,}"),
     r"\1\2[REDACTED]"),
]
# Belt-and-suspenders: high-confidence secrets that must NOT survive scrub.
RESIDUAL_SECRET_RE = re.compile(
    r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{36,}\b|"
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----|"
    r"\bsk-ant-[A-Za-z0-9_\-]{20,}|\b[rs]k_live_[A-Za-z0-9]{16,}|"
    r"\bxox[baprs]-[A-Za-z0-9-]{10,}"
)

REVIEW_PROMPT_HEAD = (
    "You are an INDEPENDENT second-opinion reviewer. The following diff was "
    "written and already self-reviewed by a different AI. Find what that reviewer "
    "likely MISSED: correctness bugs, security issues, missed edge cases, broken "
    "error handling. Return a short ranked list: file:line + the concrete problem "
    "+ a fix. Be concise. If you find nothing real, say so.\n"
    "--- DIFF (secrets/PII already redacted) ---\n"
)


def git(args: list) -> str:
    try:
        res = subprocess.run(["git"] + args, capture_output=True, text=True, timeout=5)
        return res.stdout.strip() if res.returncode == 0 else ""
    except Exception:
        return ""


def scrub(text: str) -> str:
    for pat, repl in SCRUB_SUBS:
        text = pat.sub(repl, text)
    return text


def write_notes_header(notes: str, root: str) -> None:
    try:
        with open(notes, "w", encoding="utf-8") as f:
            f.write("# Cross-review (background, opt-in pre-commit)\n\n")
            f.write("- repo: %s\n" % root)
            f.write("- trigger: sensitive staged paths (migration/money/auth)\n")
            f.write("- NON-BLOCKING and NOT a substitute for /review (the mandatory floor).\n\n")
    except OSError:
        pass


def emit_context(msg: str) -> None:
    """Non-blocking PreToolUse output: inject a context note, no permission
    decision (so the commit and all other hooks proceed untouched). Carries the
    hookEventName the harness expects for a PreToolUse hook."""
    out = {"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "additionalContext": msg}}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


def append(notes: str, text: str) -> None:
    try:
        with open(notes, "a", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass


def run_engine(cmd: list, promptf: str):
    """Return (stdout, ok). ok=False on missing CLI, non-zero exit, timeout, or
    empty output — all treated as 'engine unavailable'."""
    try:
        with open(promptf, "r", encoding="utf-8") as f:
            res = subprocess.run(cmd, stdin=f, capture_output=True, text=True, timeout=120)
        out = (res.stdout or "").strip()
        return out, (res.returncode == 0 and bool(out))
    except Exception:
        return "", False


def run_worker(promptf: str, notes: str) -> None:
    """Detached child: detect engine, run it, append findings. Degrade honestly."""
    engine = "codex" if shutil.which("codex") else (
        "gemini" if shutil.which("gemini") else "none")

    if engine == "codex":
        out, ok = run_engine(["codex", "exec", "-"], promptf)
        if ok:
            append(notes, "## Findings (engine: codex)\n\n%s\n" % out)
            _cleanup(promptf)
            return
        engine = "gemini" if shutil.which("gemini") else "none"

    if engine == "gemini":
        out, ok = run_engine(["gemini", "-p", "-"], promptf)
        if ok:
            append(notes, "## Findings (engine: gemini)\n\n%s\n" % out)
            _cleanup(promptf)
            return

    append(
        notes,
        "## External second opinion UNAVAILABLE\n\n"
        "No external cross-vendor model produced findings (codex/gemini missing,\n"
        "out of quota, or timed out). The cross-vendor property is NOT present.\n"
        "For a native red-team pass, run `/cross-review` in-session; either way\n"
        "the mandatory `/review` still applies.\n",
    )
    _cleanup(promptf)


def _cleanup(promptf: str) -> None:
    try:
        os.remove(promptf)
    except OSError:
        pass


def dispatch(promptf: str, notes: str) -> None:
    """Fork a detached child to run the (slow) external review; parent returns."""
    try:
        pid = os.fork()
    except OSError:
        # No fork (shouldn't happen on Linux/WSL/macOS) — skip background work
        # rather than block synchronously on a 120s external call.
        return
    if pid == 0:
        # Child: fully detach so a hung CLI never ties to the parent/terminal.
        try:
            os.setsid()
            devnull = os.open(os.devnull, os.O_RDWR)
            for fd in (0, 1, 2):
                try:
                    os.dup2(devnull, fd)
                except OSError:
                    pass
            run_worker(promptf, notes)
        finally:
            os._exit(0)
    # Parent: reap nothing (child is in its own session); return immediately.


def main() -> int:
    if os.environ.get("ITD_CROSS_REVIEW") == "0":
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if (payload or {}).get("tool_name") != "Bash":
        return 0
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    if not GIT_COMMIT_RE.search(cmd):
        return 0

    if git(["rev-parse", "--is-inside-work-tree"]) != "true":
        return 0
    root = git(["rev-parse", "--show-toplevel"])
    if not root:
        return 0

    # opt-in (DEFAULT-OFF) — env override OR committed marker file.
    enabled = (
        os.environ.get("CROSS_REVIEW_EGRESS_OK") == "1"
        or os.path.exists(os.path.join(root, ".cross-review-egress-ok"))
    )
    if not enabled:
        return 0

    # auto-disable in multi-agent / shared-worktree mode.
    if os.environ.get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS") == "1":
        return 0
    gd, gcd = git(["rev-parse", "--git-dir"]), git(["rev-parse", "--git-common-dir"])
    if gd and gcd and os.path.realpath(gd) != os.path.realpath(gcd):
        return 0

    staged = git(["diff", "--cached", "--name-only"])
    if not staged:
        return 0
    paths = staged.splitlines()
    if not any(MIGRATION_RE.search(p) or MONEY_AUTH_RE.search(p) for p in paths):
        return 0

    diff = git(["diff", "--cached"])
    if not diff:
        return 0
    scrubbed = scrub(diff)
    if not scrubbed:
        return 0

    notes = os.path.join(
        tempfile.gettempdir(),
        "claude-cross-review-%d-%d.md" % (int(time.time()), os.getpid()),
    )

    # Residual live-credential check — do NOT egress if a secret survived scrub.
    if RESIDUAL_SECRET_RE.search(scrubbed):
        write_notes_header(notes, root)
        append(
            notes,
            "## Cross-review SKIPPED — residual credential after scrub\n\n"
            "A high-confidence secret survived redaction, so the diff was NOT sent\n"
            "to any external model. Rotate/remove the credential, then run\n"
            "`/cross-review` manually if you still want a second opinion.\n",
        )
        emit_context(
            "[cross-review] residual secret after scrub -> external review SKIPPED "
            "(fail-safe). Note: %s" % notes
        )
        return 0

    # Write the prompt to a temp file (never via env, which has a size cap a
    # large diff would blow), then dispatch the detached worker.
    try:
        fd, promptf = tempfile.mkstemp(prefix="claude-cross-review-prompt-", suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(REVIEW_PROMPT_HEAD)
            f.write(scrubbed)
    except OSError:
        return 0

    write_notes_header(notes, root)
    try:
        dispatch(promptf, notes)
    except Exception:
        # Fail-open: a background-dispatch failure must never block the commit.
        pass

    emit_context(
        "[cross-review] sensitive staged paths -> dispatched BACKGROUND cross-vendor "
        "review. Findings will land in: %s (NON-BLOCKING; does NOT satisfy the "
        "mandatory /review)." % notes
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
