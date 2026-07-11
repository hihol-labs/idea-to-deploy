#!/usr/bin/env python3
"""
PreToolUse hook — /careful safety guardrail (inspired by gstack).

Fires before Bash tool calls. Detects destructive commands
(rm -rf, DROP TABLE, git push --force, git reset --hard, etc.)
and injects a warning into Claude's context asking for explicit
user confirmation before proceeding.

Does NOT block (exit 0, permissionDecision: allow) — it's a
soft guardrail that adds friction, not a hard gate. The user
can disable it by removing the hook from settings.json.

v1.17.0: Always active inside methodology repos (detected via
.claude-plugin/plugin.json). No opt-in needed — safety is automatic.
Outside methodology repos: opt-in via CAREFUL_MODE=1 env var or
state file (backward-compatible with manual activation).

Reads JSON on stdin: {"tool_name": "Bash", "tool_input": {"command": "..."}}
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

# Patterns that match destructive commands
DESTRUCTIVE_PATTERNS = [
    # File deletion — precision matters (live 2026-07-03: `rm -f file` was
    # mislabeled "rm -rf"; the two differ by a whole directory tree).
    # Recursive delete (with or without -f) — the truly dangerous class:
    (r"\brm\s+(-[a-zA-Z]*r|--recursive)\b", "rm -r (recursive delete)"),
    # Plain force delete WITHOUT recursion — real but milder, label honestly:
    (r"\brm\s+(-[a-zA-Z]*f(?![a-zA-Z]*r)|--force)\b(?!.*(-[a-zA-Z]*r\b|--recursive))", "rm -f (force delete, non-recursive)"),
    # Database destruction
    (r"\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX)\b", "DROP TABLE/DATABASE (irreversible data loss)"),
    (r"\bTRUNCATE\s+TABLE\b", "TRUNCATE TABLE (deletes all rows)"),
    (r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)", "DELETE FROM without WHERE (deletes all rows)"),
    # Git destructive operations
    (r"\bgit\s+push\s+[^|]*--force\b", "git push --force (overwrites remote history)"),
    (r"\bgit\s+push\s+[^|]*-f\b", "git push -f (overwrites remote history)"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard (discards uncommitted changes)"),
    (r"\bgit\s+clean\s+[^|]*-f", "git clean -f (deletes untracked files)"),
    (r"\bgit\s+checkout\s+--\s+\.", "git checkout -- . (discards all changes)"),
    # The force-delete flag is CASE-SENSITIVE: under the file-global
    # re.IGNORECASE the old pattern made `-D` swallow the harmless `-d`
    # (soft delete of an already-merged branch) and even
    # `gh pr merge --delete-branch` — 3 false positives in one day
    # (retro 2026-07-04, finding #1). (?-i:) is scoped to the SHORT flags
    # only, so `GIT BRANCH -D` still matches (review I1: a whole-pattern
    # (?-i:) regressed uppercase keywords) and combined forms -Df/-fD/-df/-fd
    # are covered (any d+f combo forces delete). Long flags stay
    # case-insensitive via the global flag. Soft `-d`/`--delete` alone and
    # `--delete-branch` stay unmatched.
    (r"\bgit\s+branch\s+(?:(?-i:-D|-[dD][fF]|-[fF][dD])\b|"
     r"--delete\s+--force\b|--force\s+--delete\b)",
     "git branch -D / --delete --force (force-deletes branch)"),
    # Docker destruction
    (r"\bdocker\s+(system\s+prune|volume\s+rm|rmi\s+-f)", "docker destructive command"),
    # Process killing
    (r"\bkill\s+-9\b|\bkillall\b|\bpkill\b", "process kill signal"),
    # System-level danger
    (r"\bchmod\s+777\b", "chmod 777 (world-writable permissions)"),
    (r"\b(curl|wget)\s+[^|]*\|\s*(sudo\s+)?bash", "pipe to bash (remote code execution risk)"),
]


def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def find_methodology_repo() -> bool:
    """Return True if cwd is inside a methodology repo."""
    cwd = os.path.abspath(os.getcwd())
    for parent in [cwd] + list(_parents(cwd)):
        if os.path.isfile(os.path.join(parent, ".claude-plugin", "plugin.json")):
            return True
    return False


def _parents(path: str):
    """Yield parent directories up to root."""
    while True:
        parent = os.path.dirname(path)
        if parent == path:
            break
        yield parent
        path = parent


def is_active() -> bool:
    """Check if /careful mode is active for this session.

    Always active inside methodology repos (auto-detected).
    Outside: opt-in via env var or state file.
    """
    # Auto-active inside methodology repos
    if find_methodology_repo():
        return True
    # Check env var
    if os.environ.get("CAREFUL_MODE") == "1":
        return True
    # Check session state file (set when user says /careful) — both temp dirs
    for d in (tempfile.gettempdir(), "/tmp"):
        try:
            with open(os.path.join(d, f"claude-careful-{session_id()}.state")) as f:
                if f.read().strip() == "active":
                    return True
        except Exception:
            continue
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = (payload or {}).get("tool_name") or ""
    if tool != "Bash":
        return 0

    if not is_active():
        return 0

    command = ((payload or {}).get("tool_input") or {}).get("command") or ""
    if not command:
        return 0

    # v1.84.0 (слабый сигнал №2, FP 2026-07-04: текст «GIT BRANCH -D» в теле
    # commit -m дал ложное предупреждение): содержимое -m/--message — цитируемая
    # проза, не команда; вырезаем ПЕРЕД матчингом. Отображаемый command не
    # меняется. Покрытые формы (important ревью #156): `-m '…'`, `-m'…'`,
    # `--message=…`, и heredoc-идиома `-m "$(cat <<'EOF' … EOF)"` (конвенция
    # коммитов этого же харнеса). Executable-heredoc (`bash <<EOF …`) НЕ
    # вырезается — там содержимое исполняется.
    scan_target = re.sub(
        r"""(-m|--message)(\s+|=|)("?\$\(\s*cat\s+<<-?\s*(['"]?)(\w+)\4.*?\n\5\b\s*\)"?)""",
        r"\1\2<msg>", command, flags=re.S)
    scan_target = re.sub(
        r"""(-m|--message)(\s+|=|)(['"])(?:\\.|(?!\3).)*\3""",
        r"\1\2\3<msg>\3", scan_target, flags=re.S)

    # Check all patterns
    warnings = []
    for pattern, description in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, scan_target, re.IGNORECASE):
            warnings.append(description)

    if not warnings:
        return 0

    warning_list = "\n".join(f"  - {w}" for w in warnings)
    context = (
        f"[/careful SAFETY WARNING] Destructive command detected:\n"
        f"{warning_list}\n\n"
        f"Command: `{command[:200]}{'...' if len(command) > 200 else ''}`\n\n"
        f"BEFORE executing this command, you MUST:\n"
        f"1. Explain to the user WHAT this command does and WHY it's dangerous\n"
        f"2. Ask for EXPLICIT confirmation: 'Эта команда {warnings[0]}. Продолжить?'\n"
        f"3. Only proceed if the user confirms\n\n"
        f"If the user has already confirmed this specific action in this conversation, proceed."
    )

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
