#!/usr/bin/env python3
"""
PreToolUse hook on Bash — OPT-IN, NON-BLOCKING cross-vendor second opinion at
commit (idea-to-deploy v1.34.0).

Fires before `git commit`. When the repo has OPTED IN to external egress AND the
staged diff touches a correctness-critical / sensitive path (migrations, money,
auth, secrets), it emits a reminder to run the canonical `/cross-review`
workflow. It never shells out to a tool-capable CLI: a pre-commit process cannot
prove a no-tools/no-secret sandbox or trustworthy maker provenance.

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
  • NO AUTOMATED CLI EGRESS. Codex/Gemini remain host-native advisory
    alternatives, invoked explicitly by an isolated host workflow.
  • AUTO-DISABLED in a linked/secondary worktree (the index may hold another
    agent's staged work) — unconditional. Also disabled when the Agent Teams flag
    (CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1) is set, UNLESS overridden with
    CROSS_REVIEW_ALLOW_AGENT_TEAMS=1 (for machines that run Agent Teams as their
    default and still want the background review).
  • SCRUB before egress (same patterns as pii-egress-guard.sh). If a live
    credential survives scrubbing, the diff is NOT sent — it degrades to a note.
  • Findings are NOTES, not a gate. This hook MUST NOT write the
    /tmp/claude-review-done-* sentinel — that belongs to /review.

Disable entirely (even when opted in): ITD_CROSS_REVIEW=0.
Reads JSON on stdin: {"tool_name":"Bash","tool_input":{"command":"..."}}

Fail-open: ANY error path -> exit 0 (allow, never block).
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

GIT_COMMIT_RE = re.compile(r"(^|[ ;&|])git\s+commit(\s|$)")

# --- sensitive-path signals (mirror check-dod-before-commit.sh) ---------------
MIGRATION_RE = re.compile(r"(^|/)migrations?/|\.sql$|schema\.prisma$|(^|/)alembic/", re.I)
MONEY_AUTH_RE = re.compile(
    r"(payment|payout|billing|invoice|\bbank\b|\bwallet\b|"
    r"\bauth(?:n|z|entication|orization)?\b|oauth|\bjwt\b|\blogin\b|"
    r"\bpasswords?\b|passwd|\bsecrets?\b|\btokens?\b|\bcredentials?\b|crypto)",
    re.I,
)

def load_shared_sanitizer():
    """Load the one canonical sanitizer; missing shared code means no egress."""
    candidates = [
        Path(__file__).resolve().parents[1] / "skills/_shared/itd_external_reviewer.py",
        Path.home() / ".claude/skills/_shared/itd_external_reviewer.py",
    ]
    plugin_root = os.environ.get("PLUGIN_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        candidates.insert(0, Path(plugin_root) / "skills/_shared/itd_external_reviewer.py")
    for candidate in candidates:
        if not candidate.is_file():
            continue
        spec = importlib.util.spec_from_file_location("itd_external_reviewer_shared", candidate)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    return None


SHARED_SANITIZER = load_shared_sanitizer()

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
    if SHARED_SANITIZER is None:
        return ""
    return SHARED_SANITIZER.scrub(text)[0]


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


def run_worker(promptf: str, notes: str) -> None:
    """Compatibility entry point: never launches a tool-capable external CLI."""
    append(
        notes,
        "## External second opinion UNAVAILABLE\n\n"
        "Automated Codex/Gemini CLI egress is disabled because this hook cannot\n"
        "prove a no-tools/no-secret sandbox or complete cost telemetry.\n"
        "Run `/cross-review` through an isolated host workflow; either way\n"
        "the mandatory `/review` still applies.\n",
    )
    _cleanup(promptf)


def _cleanup(promptf: str) -> None:
    try:
        os.remove(promptf)
    except OSError:
        pass


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
    # The CONCRETE hazard is a linked/secondary worktree (the index may hold
    # another agent's staged work) — that skip below is UNCONDITIONAL. The Agent
    # Teams FLAG alone is a weaker proxy: on a machine where Agent Teams is the
    # default it would disable the hook permanently, so it is overridable with an
    # explicit CROSS_REVIEW_ALLOW_AGENT_TEAMS=1 (you thereby accept that an
    # in-process parallel agent's staged change could ride along in the diff).
    if (os.environ.get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS") == "1"
            and os.environ.get("CROSS_REVIEW_ALLOW_AGENT_TEAMS") != "1"):
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
    emit_context(
        "[cross-review] sensitive staged paths detected; automated Codex/Gemini "
        "CLI egress is disabled. Run the canonical /cross-review workflow for an "
        "isolated advisory review (NON-BLOCKING; does NOT satisfy /review)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
