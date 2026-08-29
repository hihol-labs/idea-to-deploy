#!/usr/bin/env python3
"""PreToolUse commit gate backed by exact-context successful review evidence.

For commits with more than two staged files, a review cache hit must match the
current repository, HEAD, staged tree/binary diff, scope and acceptance
contracts, rubric/version, and active risk tier. Legacy timestamp/tree marker
files are deliberately ignored: they carry neither verdict nor full context.

The validator itself is resolved per candidate, not per install: inside the
methodology checkout this install was synced from, the gate loads that
checkout's own itd_review_cache.py; everywhere else the installed one. See
methodology_checkout() for why, and why the install is the anchor.
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
PLUGIN_NAME = "idea-to-deploy"
CACHE_RELATIVE = Path("skills") / "review" / "scripts" / "itd_review_cache.py"
INSTALL_ROOT = Path(__file__).resolve().parents[1]
INSTALLED_CACHE_SCRIPT = INSTALL_ROOT / CACHE_RELATIVE
PROVENANCE_RELATIVE = Path(".itd-install-source.json")
GIT_PROBE_TIMEOUT_SECONDS = 5


def git_toplevel(cwd: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=str(cwd),
            capture_output=True, text=True, timeout=GIT_PROBE_TIMEOUT_SECONDS,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    if not value:
        return None
    try:
        return Path(value).resolve()
    except OSError:
        return None


def recorded_checkout() -> Path | None:
    """The checkout this install was synced from, as recorded by the install.

    The anchor has to live outside the candidate. A plugin manifest is
    self-declared, so a working directory that names itself would be trusted on
    its own word; this file is written only by scripts/sync-to-active.sh, into
    the user's install, from a real checkout -- a repository cannot put it
    there.
    """
    try:
        record = json.loads(
            (INSTALL_ROOT / PROVENANCE_RELATIVE).read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(record, dict) or record.get("plugin") != PLUGIN_NAME:
        return None
    value = record.get("checkout")
    if not isinstance(value, str) or not value:
        return None
    try:
        return Path(value).resolve()
    except OSError:
        return None


def methodology_checkout(cwd: Path) -> Path | None:
    """Return the methodology checkout being judged, or None for any other project.

    A release commit bumps the version inside the tree, so the installed
    validator resolves a different methodologyVersion than the one /review
    recorded with the checkout's own validator -- a cache miss that blocks a
    commit whose review actually passed. The candidate must be judged by the
    candidate's own validator.

    Trust is anchored in the install, not in the candidate: the git top level
    must be exactly the checkout this install was synced from, that root must
    also declare this plugin, and the validator found there must belong to that
    same root (its own install root, after symlinks are resolved, is the
    detected checkout). Anything else -- no provenance, another directory, not
    a repository, no manifest, a validator pointing outside -- falls back to
    the installed validator, which is what every other project keeps using.
    """
    source = recorded_checkout()
    if source is None:
        return None
    top = git_toplevel(cwd)
    if top is None or top != source:
        return None
    try:
        manifest = json.loads(
            (top / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(manifest, dict) or manifest.get("name") != PLUGIN_NAME:
        return None
    candidate = top / CACHE_RELATIVE
    try:
        if not candidate.is_file():
            return None
        if candidate.resolve().parents[3] != top:
            return None
    except (OSError, IndexError):
        return None
    return top


def cache_script_for(cwd: Path) -> Path:
    checkout = methodology_checkout(cwd)
    if checkout is None:
        return INSTALLED_CACHE_SCRIPT
    return checkout / CACHE_RELATIVE


def load_cache_module(cwd: Path):
    script = cache_script_for(cwd)
    loader = importlib.machinery.SourceFileLoader("itd_review_cache_gate", str(script))
    spec = importlib.util.spec_from_loader("itd_review_cache_gate", loader)
    if spec is None:
        return None
    module = importlib.util.module_from_spec(spec)
    # The hook runs from its own shebang, so the interpreter would write
    # __pycache__ next to the loaded file. When that file is the INSTALLED
    # validator, the .pyc lands inside the content-addressed runtime and the
    # next reinstall dies on "installed runtime directory inventory drifted"
    # (measured 2026-08-29). The install stays byte-exact by never producing it.
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def review_was_done(root: Path | None = None) -> bool:
    """Fail closed unless the durable cache matches the exact current context."""
    target = Path(root) if root is not None else Path.cwd()
    try:
        module = load_cache_module(target)
        return bool(module and module.cache_allows(target))
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
