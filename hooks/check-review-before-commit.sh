#!/usr/bin/env python3
"""
PreToolUse hook on Bash — fires before every Bash invocation.
If the command is `git commit` and more than 2 files are staged,
checks if /review was called in this session.

Tracking: when the Skill tool is called with skill="review",
the PostToolUse hook (or this hook on Skill calls) writes a marker
file. This hook reads the marker before allowing commit.

Marker file: /tmp/claude-review-done-{session_id}

If /review was NOT called and >2 files staged → BLOCK with deny.

This enforces the CLAUDE.md rule:
"Коммитить более 2 файлов без предварительного /review запрещено"
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


GIT_COMMIT_RE = re.compile(r"(^|\s|;|&&|\|\|)git\s+commit(\s|$)")
MAX_FILES_WITHOUT_REVIEW = 2
REVIEW_FRESHNESS_SECONDS = 900  # 15 min — post-/review commit window


def get_session_id() -> str:
    return os.environ.get("CLAUDE_SESSION_ID") or str(os.getppid())


def _sentinel_dirs() -> list:
    """Platform temp + literal /tmp. The /review skill writes from bash
    (Git-Bash /tmp == %TEMP%; WSL /tmp == /tmp), this hook may run under
    Windows python (where "/tmp" means C:\\tmp) — read all of them."""
    dirs = []
    for d in (tempfile.gettempdir(), "/tmp"):
        if d and d not in dirs:
            dirs.append(d)
    return dirs


def review_marker_paths() -> list:
    sid = get_session_id()
    return [Path(d) / f"claude-review-done-{sid}" for d in _sentinel_dirs()]


TREE_TOKEN_RE = re.compile(r"^tree:([0-9a-f]{40})$")


def staged_tree_hash() -> str | None:
    """Deterministic hash of the exact staged content, via `git write-tree`.

    `git write-tree` serialises the current index to a tree object and prints
    its SHA-1; it moves no ref and is idempotent (git dedups the tree), so it
    is a read-only fingerprint of *what would be committed*. Two properties
    make it the right binding key for the review sentinel:

    - **Foreign-project immunity**: project B's staged tree differs from
      project A's, so A's sentinel cannot unblock a commit in B.
    - **Staleness immunity**: if the staged content changes after /review
      (files edited or re-staged), the tree hash changes and the old
      sentinel no longer matches — the review is correctly re-required.

    Returns None if git cannot compute it (not a repo / git error); callers
    treat that as "no binding available".
    """
    try:
        result = subprocess.run(
            ["git", "write-tree"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        h = result.stdout.strip()
        return h if re.fullmatch(r"[0-9a-f]{40}", h) else None
    except Exception:
        return None


def review_was_done() -> bool:
    """True only if a fresh /review sentinel is bound to the CURRENT staged
    tree (`tree:<git-write-tree>`).

    v1.59.0 diff-binding (this hook's core tightening): a sentinel counts
    only when its content is `tree:<sha>` and `<sha>` equals the tree that
    *this* commit would write. A stale sentinel (content changed since
    /review) or a cross-project sentinel (different tree) no longer passes —
    closing the "any fresh sentinel unblocks any commit" hole documented in
    PR #56's era. Bare-timestamp sentinels (the pre-v1.59.0 format) are NOT
    accepted, so a legacy or hand-touched marker cannot wildcard the gate.

    Match is by *content*, not session id, which keeps the cross-session /
    PID-mismatch tolerance (the /review skill and this hook may run under
    different PIDs) — we simply require the content to prove it reviewed the
    exact change being committed.

    Fail-CLOSED on unknown tree: if `git write-tree` cannot compute the
    current tree, we return False (deny) rather than accept an unverifiable
    sentinel. `git write-tree` succeeds for any valid repo with a readable
    index (it returns HEAD's tree even when nothing is staged), so this
    branch fires only on a genuine git fault — corrupted index, `.git`
    permission error, missing git binary, or the 5s timeout. Accepting a
    fresh tree:-bound sentinel there would re-open the very wildcard this
    binding closes (a foreign `tree:<other-repo-hash>` would pass), so the
    safe direction is to deny and make the user re-run /review after the git
    fault clears. (A repo so broken that write-tree fails cannot commit
    anyway.) Non-git-repo cwd never reaches here: staged_file_count() fails
    closed to 0 and main() short-circuits before this runs.
    """
    import glob
    import time

    current = staged_tree_hash()
    if current is None:
        return False  # cannot fingerprint the tree → no sentinel is verifiable
    cutoff = time.time() - REVIEW_FRESHNESS_SECONDS
    for d in _sentinel_dirs():
        for path in glob.glob(os.path.join(d, "claude-review-done-*")):
            try:
                if os.path.getmtime(path) <= cutoff:
                    continue
                content = Path(path).read_text().strip()
            except OSError:
                continue
            m = TREE_TOKEN_RE.match(content)
            if not m:
                continue  # legacy bare-timestamp / malformed → never a wildcard
            if m.group(1) == current:
                return True
    return False


def staged_file_count() -> int:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return 0
        return len([l for l in result.stdout.splitlines() if l.strip()])
    except Exception:
        return 0


def emit_deny(count: int) -> None:
    msg = (
        f"[REVIEW GATE] Коммит заблокирован: {count} файлов в staging, "
        f"но /review не был вызван в этой сессии.\n\n"
        f"WHY: multi-file staged diff требует свежего независимого review, "
        f"а session-bound marker отсутствует.\n"
        f"FIX: запусти /review для текущего diff и затем повтори git commit.\n\n"
        f"Правило: коммитить >2 файлов без /review запрещено (CLAUDE.md).\n\n"
        f"Действия:\n"
        f"  1. Запусти /review для проверки изменений\n"
        f"  2. После /review повтори git commit\n"
    )
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": msg,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stderr.write(msg)
    sys.exit(2)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = (payload or {}).get("tool_name") or ""
    tool_input = (payload or {}).get("tool_input") or {}

    # Only check Bash commands. The /review marker file
    # /tmp/claude-review-done-{session} is written by the /review skill
    # itself at Step 5 — NOT by this hook. The Skill tool is an internal
    # harness construct and does not route through PreToolUse hooks, so
    # we cannot detect `/review` invocations from here.
    if tool != "Bash":
        return 0

    cmd = tool_input.get("command") or ""
    if not GIT_COMMIT_RE.search(cmd):
        return 0

    # Check staged file count
    count = staged_file_count()
    if count <= MAX_FILES_WITHOUT_REVIEW:
        return 0  # small commit, no review needed

    # Check if /review was done
    if review_was_done():
        return 0  # review was called, allow commit

    # Block!
    emit_deny(count)
    return 2  # unreachable


if __name__ == "__main__":
    sys.exit(main())
