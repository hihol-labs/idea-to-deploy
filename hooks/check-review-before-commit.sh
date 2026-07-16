#!/usr/bin/env python3
"""PreToolUse commit gate backed by exact-context successful review evidence.

For commits with more than two staged files, a review cache hit must match the
current repository, HEAD, staged tree/binary diff, scope and acceptance
contracts, rubric/version, and active risk tier. Legacy timestamp/tree marker
files are deliberately ignored: they carry neither verdict nor full context.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path


GIT_COMMIT_RE = re.compile(r"(^|\s|;|&&|\|\|)git\s+commit(\s|$)")
MAX_FILES_WITHOUT_REVIEW = 2
CACHE_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills" / "review" / "scripts" / "itd_review_cache.py"
)


def load_cache_module():
    loader = importlib.machinery.SourceFileLoader("itd_review_cache_gate", str(CACHE_SCRIPT))
    spec = importlib.util.spec_from_loader("itd_review_cache_gate", loader)
    if spec is None:
        return None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def review_was_done() -> bool:
    """Fail closed unless the durable cache matches the exact current context."""
    try:
        module = load_cache_module()
        return bool(module and module.cache_allows(Path.cwd()))
    except Exception:
        return False


def staged_file_count() -> int:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return 0
        return len([line for line in result.stdout.splitlines() if line.strip()])
    except Exception:
        return 0


def emit_deny(count: int) -> None:
    msg = (
        f"[REVIEW GATE] Коммит заблокирован: {count} файлов в staging, "
        f"но нет успешного /review для exact current context.\n\n"
        f"WHY: cache должен совпадать по repository, base/tree, binary diff, "
        f"scope/acceptance contracts, rubric/version и risk tier; "
        f"BLOCKED/UNVERIFIED и legacy marker не удовлетворяют gate.\n"
        f"FIX: запусти /review для текущего staged candidate и запиши его "
        f"машиночитаемый verdict через itd_review_cache.py.\n"
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
    raise SystemExit(2)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool = (payload or {}).get("tool_name") or ""
    tool_input = (payload or {}).get("tool_input") or {}
    if tool != "Bash":
        return 0
    command = tool_input.get("command") or ""
    if not GIT_COMMIT_RE.search(command):
        return 0
    count = staged_file_count()
    if count <= MAX_FILES_WITHOUT_REVIEW:
        return 0
    if review_was_done():
        return 0
    emit_deny(count)
    return 2


if __name__ == "__main__":
    sys.exit(main())
