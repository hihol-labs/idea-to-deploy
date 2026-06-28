#!/usr/bin/env python3
"""
PreToolUse hook on Bash — Definition-of-Done gate (v1.23.0, Layer 1).

Fires before every Bash invocation. If the command is , it
inspects the staged diff for HIGH-RISK signals and BLOCKS the commit
(decision: deny, exit 2) when the matching idea-to-deploy skill was NOT
run in this session:

  migration / schema / DDL   -> requires /migrate AND /test
  payments / auth / secrets  -> requires /security-audit
  agent context / memory     -> requires /security-audit
  brand-new source file with
    no test file staged       -> requires /test

This GENERALISES check-review-before-commit.sh (which owns the
">2 files -> /review" rule) to the other risk signals. The >2-files rule
is intentionally NOT duplicated here.

Skill completion is detected via the same sentinel convention /review
uses: each skill writes /tmp/claude-<skill>-done-<session> at its final
step (see skills/{test,migrate,security-audit}/SKILL.md). A sentinel
counts as present if the exact-session file exists OR any fresh one
(< 15 min) exists, searched in both /tmp and the platform temp dir for
cross-platform robustness.

Escape hatch (narrow, logged): include  in the commit
message. The signal set is deliberately NARROW to avoid alarm fatigue —
ordinary edits never trip this gate.

Reads JSON on stdin: {"tool_name": "Bash", "tool_input": {"command": "..."}}
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time

GIT_COMMIT_RE = re.compile(r"(^|\s|;|&&|\|\|)git\s+commit(\s|$)")
SENTINEL_FRESHNESS_SECONDS = 900  # 15 min

# --- risk-signal patterns (matched against staged file PATHS only) ---
MIGRATION_RE = re.compile(r"(^|/)migrations?/|\.sql$|schema\.prisma$|(^|/)alembic/", re.I)
MONEY_AUTH_RE = re.compile(
    r"(payment|payout|billing|invoice|\bbank\b|\bwallet\b|"
    r"\bauth(?:n|z|entication|orization)?\b|oauth|\bjwt\b|\blogin\b|"
    r"\bpasswords?\b|passwd|\bsecrets?\b|\btokens?\b|\bcredentials?\b|crypto)",
    re.I,
)
# --- agent context / long-term memory files (Day-3 context-engineering, v1.32.0) ---
# Files that feed an AI/agent context window or its durable memory: an unreviewed
# write here is a context-integrity / memory-poisoning surface (review C-code-7).
# Async/out-of-band memory writers especially must not land unreviewed (ADR-001).
# Scoped to AGENT memory/context artifacts; ordinary docs/config never match.
MEMORY_RE = re.compile(
    r"(^|/)(agent[_-]?memory|long[_-]?term[_-]?memory|memor(?:y|ies)[_-]?store|"
    r"vector[_-]?(?:store|db)|embeddings?[_-]?store|context[_-]?(?:store|window)|"
    r"system[_-]?prompts?|prompt[_-]?templates?|rag[_-]?(?:index|pipeline)|"
    r"retriev(?:er|al))[\w./-]*\.(py|js|jsx|ts|tsx|go|rb|java|rs|json|ya?ml|toml)$",
    re.I,
)

# Source extensions whose BRAND-NEW files should ship with a test.
# Shell/infra scripts deliberately excluded — rarely unit-tested here,
# and excluding them keeps the gate from blocking its own hook commits.
SOURCE_EXT_RE = re.compile(
    r"\.(py|js|jsx|ts|tsx|go|rb|java|rs|php|c|cc|cpp|cs|kt|kts|swift|scala|ex|exs)$",
    re.I,
)
TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|spec|__tests__)/|\.(test|spec)\.|(^|/)test_|_test\.", re.I
)


def session_id() -> str:
    # Mirrors check-review-before-commit.sh: the getppid() fallback is
    # unreliable across hook spawns, but sentinel_present()'s fresh-glob
    # fallback (any matching sentinel < 15 min) is the real cross-session
    # mechanism — an exact session match is a fast-path bonus, not required.
    return os.environ.get("CLAUDE_SESSION_ID") or str(os.getppid())


def sentinel_present(skill: str) -> bool:
    """True if a claude-<skill>-done sentinel exists for this session, or
    any fresh one (< 15 min). Searches /tmp and the platform temp dir."""
    sid = session_id()
    dirs = []
    for d in ("/tmp", tempfile.gettempdir()):
        if d and d not in dirs:
            dirs.append(d)
    cutoff = time.time() - SENTINEL_FRESHNESS_SECONDS
    for d in dirs:
        exact = os.path.join(d, "claude-%s-done-%s" % (skill, sid))
        if os.path.exists(exact):
            return True
        for p in glob.glob(os.path.join(d, "claude-%s-done-*" % skill)):
            try:
                if os.path.getmtime(p) > cutoff:
                    return True
            except OSError:
                continue
    return False


def staged_entries() -> list:
    """Return [(status, path)] for staged entries (status A/M/D/R...)."""
    try:
        res = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True, text=True, timeout=5,
        )
        if res.returncode != 0:
            return []
        out = []
        for line in res.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                out.append((parts[0].strip(), parts[-1].strip()))
        return out
    except Exception:
        return []


def required_skills(entries: list) -> dict:
    """Map required skill -> human reason, from staged risk signals."""
    paths = [p for _s, p in entries]
    req = {}

    if any(MIGRATION_RE.search(p) for p in paths):
        req["migrate"] = "изменение схемы/миграции БД в staged diff"
        req.setdefault("test", "изменение схемы/миграции требует тестов")

    if any(MONEY_AUTH_RE.search(p) for p in paths):
        req["security-audit"] = "затронуты платежи/auth/секреты (путь файла)"

    if any(MEMORY_RE.search(p) for p in paths):
        req.setdefault(
            "security-audit",
            "AI-агент: файл контекста/долговременной памяти (context-integrity)",
        )

    new_src = [
        p for s, p in entries
        if s.startswith("A") and SOURCE_EXT_RE.search(p) and not TEST_PATH_RE.search(p)
    ]
    has_test = any(TEST_PATH_RE.search(p) for p in paths)
    if new_src and not has_test:
        req.setdefault("test", "новый код-файл без парного теста: %s" % new_src[0])

    return req


def emit_deny(missing: dict) -> None:
    lines = "\n".join("  ❌ /%s — %s" % (s, r) for s, r in missing.items())
    msg = (
        "[DoD GATE] Коммит заблокирован: рисковые изменения без нужного скилла.\n\n"
        + lines
        + "\n\nДействия:\n"
        "  1. Запусти нужный скилл (он отметит выполнение), затем повтори git commit.\n"
        "  2. Осознанный обход: добавь 'SKILL_BYPASS: <причина>' в поле description Bash-вызова коммита.\n\n"
        "Гейт узкий (миграции / деньги / новый код без теста) — это не шум, "
        "а Definition of Done. См. CHANGELOG v1.23.0."
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
    if (payload or {}).get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input") or {}
    cmd = tool_input.get("command") or ""
    if not GIT_COMMIT_RE.search(cmd):
        return 0
    # Explicit bypass only via the human-visible Bash `description` field —
    # never the raw command string, which can carry a crafted "SKILL_BYPASS:"
    # in a path or commit message (mirrors check-tool-skill.sh). When used,
    # check-tool-skill.sh records it in the per-session bypass ledger.
    if "SKILL_BYPASS:" in (tool_input.get("description") or ""):
        return 0

    entries = staged_entries()
    if not entries:
        return 0
    req = required_skills(entries)
    missing = {s: r for s, r in req.items() if not sentinel_present(s)}
    if missing:
        emit_deny(missing)
        return 2  # unreachable
    return 0


if __name__ == "__main__":
    sys.exit(main())
