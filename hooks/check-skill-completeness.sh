#!/usr/bin/env python3
"""
PreToolUse hook — fires BEFORE Write/Edit/MultiEdit. Detects when a
skill file (`skills/<name>/SKILL.md`) is about to be created or
modified and verifies the skill is structurally complete:

  1. If the new content references `references/<anything>`, the
     `skills/<name>/references/` folder must already exist and be
     non-empty on disk.
  2. `hooks/check-skills.sh` must contain a trigger phrase mentioning
     `/<name>` (unless the file declares `disable-model-invocation:
     true` in frontmatter — those are explicitly invoked and don't
     need trigger phrases).
  3. At least one regression fixture `tests/fixtures/fixture-*-<name>*/`
     must exist.

On any failure, the hook EMITS `hookSpecificOutput.permissionDecision:
"deny"` with a detailed reason and exits with code 2. Claude Code
treats this as a hard PreToolUse block — the Write/Edit never runs,
the file never lands on disk, Claude is told exactly what's missing.

v1.5.0 history: this hook was initially (incorrectly) a PostToolUse
hook with a top-level `decision: "block"` field. Both choices were
wrong per Anthropic's hooks spec:

- PostToolUse exit 2 is non-blocking by design (tool already ran).
- The decision field for PreToolUse is
  `hookSpecificOutput.permissionDecision`, not root-level `decision`.

v1.5.1 fixes both: the hook moved to PreToolUse, and the JSON payload
uses the correct `hookSpecificOutput.permissionDecision: "deny"`
structure. Source of truth for the JSON schema:
https://code.claude.com/docs/en/hooks.md (PreToolUse section).

This is a no-op outside the methodology repo — the hook walks up from
cwd looking for `.claude-plugin/plugin.json` and exits 0 silently if
not found.

Reads JSON on stdin:
  {"tool_name": "Write"|"Edit"|"MultiEdit",
   "tool_input": {"file_path": "...", "content"|"new_string"|"edits": ...}}
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


SKILL_PATH_RE = re.compile(r"skills/([^/]+)/SKILL\.md$")


def find_repo_root(start: Path) -> Path | None:
    """Walk up until we find .claude-plugin/plugin.json — that's the
    methodology repo root. Outside such a repo the hook is a no-op."""
    for parent in [start] + list(start.parents):
        if (parent / ".claude-plugin" / "plugin.json").exists():
            return parent
    return None


def extract_pending_content(tool_name: str, tool_input: dict) -> str:
    """Return the text that will be in the SKILL.md file AFTER the tool
    runs. For Write this is tool_input.content. For Edit/MultiEdit we
    approximate by reading the current file (if any) and looking at the
    new_string(s) — good enough to detect `references/` mentions."""
    if tool_name == "Write":
        return tool_input.get("content") or ""
    if tool_name == "Edit":
        return tool_input.get("new_string") or ""
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits") or []
        return "\n".join(e.get("new_string", "") for e in edits)
    return ""


def parse_frontmatter(text: str) -> dict:
    """Minimal YAML-like frontmatter parser — we only need a few keys."""
    fm: dict[str, str] = {}
    if not text.startswith("---\n"):
        return fm
    end = text.find("\n---\n", 4)
    if end < 0:
        return fm
    for line in text[4:end].splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip("'\"")
    return fm


def check_references(skill_dir: Path, pending_content: str, existing_body: str) -> list[str]:
    """If either the pending content or the existing body mentions
    `references/`, the folder must exist on disk and be non-empty."""
    errors: list[str] = []
    combined = (pending_content or "") + "\n" + (existing_body or "")
    if "references/" not in combined:
        return errors
    refs_dir = skill_dir / "references"
    if not refs_dir.is_dir():
        errors.append(
            f"SKILL.md references `references/` but the folder does not "
            f"exist: {refs_dir}. Create the folder and add at least one "
            f"file (e.g., a checklist) BEFORE writing the SKILL.md."
        )
        return errors
    if not any(refs_dir.iterdir()):
        errors.append(
            f"`references/` folder is empty: {refs_dir}. Add the "
            f"referenced file(s) BEFORE writing the SKILL.md."
        )
    return errors


def check_triggers(repo: Path, skill_name: str, fm: dict) -> list[str]:
    """hooks/check-skills.sh must mention /<skill-name>. Skills with
    `disable-model-invocation: true` are exempt (they're invoked
    explicitly and don't need description-based triggering)."""
    errors: list[str] = []
    if fm.get("disable-model-invocation", "").lower() == "true":
        return errors
    hook_file = repo / "hooks" / "check-skills.sh"
    if not hook_file.exists():
        errors.append("hooks/check-skills.sh is missing — cannot verify triggers")
        return errors
    text = hook_file.read_text(encoding="utf-8", errors="replace")
    if f"/{skill_name}" not in text:
        errors.append(
            f"hooks/check-skills.sh has no mention of `/{skill_name}` — "
            f"add Russian + English trigger phrases for this skill "
            f"BEFORE writing the SKILL.md."
        )
    return errors


def check_fixture(repo: Path, skill_name: str) -> list[str]:
    """At least one fixture directory must mention the skill name in
    its path OR inside its notes.md."""
    errors: list[str] = []
    fixtures = repo / "tests" / "fixtures"
    if not fixtures.is_dir():
        return errors  # no fixtures infra — not a block
    for entry in fixtures.iterdir():
        if not entry.is_dir():
            continue
        if skill_name in entry.name:
            return errors  # found by directory name
        notes = entry / "notes.md"
        if notes.exists():
            try:
                content = notes.read_text(encoding="utf-8", errors="replace")
                if re.search(
                    rf"(^|[^-a-z]){re.escape(skill_name)}([^-a-z]|$)",
                    content,
                    re.M,
                ):
                    return errors  # found by notes.md mention
            except Exception:
                pass
    errors.append(
        f"No fixture matches `tests/fixtures/fixture-*-{skill_name}*/` "
        f"or mentions `/{skill_name}` in a fixture's notes.md — add at "
        f"least one regression fixture BEFORE writing the SKILL.md "
        f"(see tests/fixtures/fixture-07-daily-work-skills for a shared "
        f"fixture pattern)."
    )
    return errors


def emit_deny(errors: list[str], skill_name: str) -> None:
    """Emit a PreToolUse deny payload with the correct Anthropic schema
    (hookSpecificOutput.permissionDecision = "deny") and exit 2."""
    reason = (
        f"[SKILL COMPLETENESS BLOCK] Skill `/{skill_name}` is incomplete "
        f"— found {len(errors)} violation(s):\n\n"
        f"WHY: the skill references required supporting artifacts that are absent or incomplete.\n"
        f"FIX: create every artifact listed below, then retry the Write/Edit.\n\n"
        + "\n".join(f"  ❌ {e}" for e in errors)
        + "\n\nThis hook closes the v1.4.0 Potemkin-release incident: "
        "skills cannot be written without their supporting artifacts "
        "(references/, trigger phrases in hooks/check-skills.sh, and "
        "at least one regression fixture). Create the missing pieces "
        "first, then retry the Write/Edit."
    )
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stderr.write(reason)
    sys.exit(2)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_name = (payload or {}).get("tool_name") or ""
    if tool_name not in {"Write", "Edit", "MultiEdit"}:
        return 0

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not file_path:
        return 0

    # Host payloads use native separators.  The contract regex is deliberately
    # POSIX-shaped, so normalize only for matching and keep the original path
    # for pathlib/filesystem operations below.
    match_path = str(file_path).replace("\\", "/")
    m = SKILL_PATH_RE.search(match_path)
    if not m:
        return 0

    skill_name = m.group(1)
    skill_file = Path(file_path)
    if not skill_file.is_absolute():
        skill_file = Path.cwd() / skill_file

    repo = find_repo_root(skill_file.parent)
    if repo is None:
        return 0

    # Pending content from the incoming tool call
    pending = extract_pending_content(tool_name, tool_input)

    # Existing body on disk (may be empty if this is a Write of a new file)
    existing_body = ""
    existing_fm: dict = {}
    if skill_file.exists():
        try:
            existing_text = skill_file.read_text(encoding="utf-8", errors="replace")
            existing_fm = parse_frontmatter(existing_text)
            existing_body = existing_text
        except Exception:
            pass

    # For Write with new file, parse frontmatter from pending content
    fm = existing_fm or parse_frontmatter(pending)

    errors: list[str] = []
    errors += check_references(skill_file.parent, pending, existing_body)
    errors += check_triggers(repo, skill_name, fm)
    errors += check_fixture(repo, skill_name)

    if errors:
        emit_deny(errors, skill_name)
        return 2  # unreachable

    return 0


if __name__ == "__main__":
    sys.exit(main())
