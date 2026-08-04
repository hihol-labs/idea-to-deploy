#!/usr/bin/env python3
"""PreToolUse checkpoint reminder for the mandatory independent review.

For a sensitive staged candidate, this hook reminds the orchestrator that
`/review` and `/cross-review` must converge on
`itd_free_reviewer_producer.py` before PR publication. The hook itself never
egresses code, launches a reviewer, writes review evidence, or authorizes a
commit/PR; exact-candidate Verification Loop adjudication owns enforcement.

The reminder is always enabled for sensitive commits, including Agent Teams
and linked worktrees, because it is read-only and has no credential surface.
Reads JSON on stdin: {"tool_name":"Bash","tool_input":{"command":"..."}}
Any detector error returns zero without manufacturing review evidence.
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
            f.write("# Mandatory independent-review checkpoint\n\n")
            f.write("- repo: %s\n" % root)
            f.write("- trigger: sensitive staged paths (migration/money/auth)\n")
            f.write("- Reminder only; Verification Loop evidence is still required.\n\n")
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
        "## Mandatory independent review UNAVAILABLE in this hook\n\n"
        "This checkpoint cannot mint review evidence. Run `/review` or\n"
        "`/cross-review`; both use one isolated Sol -> Terra / Terra -> Sol\n"
        "producer and require Verification Loop adjudication.\n",
    )
    _cleanup(promptf)


def _cleanup(promptf: str) -> None:
    try:
        os.remove(promptf)
    except OSError:
        pass


def main() -> int:
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

    staged = git(["diff", "--cached", "--name-only"])
    if not staged:
        return 0
    paths = staged.splitlines()
    if not any(MIGRATION_RE.search(p) or MONEY_AUTH_RE.search(p) for p in paths):
        return 0
    emit_context(
        "[independent-review] sensitive staged paths detected. Before PR "
        "publication run /review or /cross-review; both must use the canonical "
        "Sol -> Terra / Terra -> Sol keyless producer and Verification Loop "
        "adjudication. This reminder is not review evidence."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
