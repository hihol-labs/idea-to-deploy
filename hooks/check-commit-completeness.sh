#!/usr/bin/env python3
"""
PreToolUse hook on Bash — fires before every Bash invocation. If the
command contains `git commit`, verify the staged diff is internally
consistent: any change to `skills/<name>/SKILL.md` must ship alongside

  1. At least one staged change under `skills/<name>/references/`
     (if the SKILL.md body references `references/` at all), OR an
     explicit justification marker in the commit message.
  2. At least one staged change to `hooks/check-skills.sh` OR the skill
     must already have matching triggers in the current hook file.
  3. At least one staged change under `tests/fixtures/` that mentions
     the skill name, OR a pre-existing fixture must already mention it.

If any gap is found, the hook BLOCKS the Bash call by exiting with
code 2 and a `decision: deny` payload. The commit never runs.

This is the answer to: "the self-extension loop bypassed its own
Quality Gates, leading to the v1.4.0 Potemkin release". It makes the
commit itself the enforcement point — a shortcut is no longer possible.

The hook is a no-op for any Bash command that is not `git commit`.

v1.5.1 fix: the JSON payload now uses the correct PreToolUse schema
per https://code.claude.com/docs/en/hooks.md — the deny decision lives
at `hookSpecificOutput.permissionDecision`, not at the root as in
v1.5.0. Exit 2 alone already blocks the tool call, but the malformed
JSON in v1.5.0 meant the `permissionDecision` field was silently
dropped by Claude Code's schema validator. Both layers of the block
are now correct.

Reads JSON on stdin:
  {"tool_name": "Bash", "tool_input": {"command": "git commit ..."}}
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


GIT_COMMIT_RE = re.compile(r"(^|\s|;|&&|\|\|)git\s+commit(\s|$)")


def find_repo_root(start: Path) -> Path | None:
    for parent in [start] + list(start.parents):
        if (parent / ".claude-plugin" / "plugin.json").exists():
            return parent
    return None


def staged_files(repo: Path) -> list[str]:
    """Return the list of files that are currently staged for commit."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def skill_touched(files: list[str]) -> dict[str, list[str]]:
    """Return {skill_name: [staged_files_under_skill_dir]}."""
    out: dict[str, list[str]] = {}
    for f in files:
        m = re.match(r"skills/([^/]+)/", f)
        if m:
            out.setdefault(m.group(1), []).append(f)
    return out


def needs_references(repo: Path, skill_name: str) -> bool:
    """Does the staged SKILL.md body mention `references/`?"""
    path = repo / "skills" / skill_name / "SKILL.md"
    if not path.exists():
        return False
    try:
        return "references/" in path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False


def hook_has_trigger(repo: Path, skill_name: str) -> bool:
    path = repo / "hooks" / "check-skills.sh"
    if not path.exists():
        return False
    try:
        return f"/{skill_name}" in path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False


def fixture_exists(repo: Path, skill_name: str) -> bool:
    """Return True if ANY fixture satisfies the skill.

    Matches if the fixture directory name contains the skill name OR if
    the fixture's `notes.md` mentions the skill as a `/skill-name` token.
    Keep this in sync with `check-skill-completeness.sh::check_fixture`
    (v1.5.0 fix: the two hooks previously diverged, causing false commit
    blocks on skills exercised only by fixture content, e.g. /project
    routed through fixture-01-saas-clinic via /kickstart).
    """
    fixtures = repo / "tests" / "fixtures"
    if not fixtures.is_dir():
        return False
    for entry in fixtures.iterdir():
        if not entry.is_dir():
            continue
        if skill_name in entry.name:
            return True
        notes = entry / "notes.md"
        if notes.exists():
            try:
                content = notes.read_text(encoding="utf-8", errors="replace")
                if re.search(
                    rf"(^|[^-a-z])/{re.escape(skill_name)}([^-a-z]|$)",
                    content,
                    re.M,
                ):
                    return True
                # Also match bare word form (`project` without leading `/`)
                # for compatibility with older fixtures that don't use the
                # slash prefix. Matches check-skill-completeness.sh logic.
                if re.search(
                    rf"(^|[^-a-z]){re.escape(skill_name)}([^-a-z]|$)",
                    content,
                    re.M,
                ):
                    return True
            except Exception:
                pass
    return False


def is_disable_model_invocation(repo: Path, skill_name: str) -> bool:
    path = repo / "skills" / skill_name / "SKILL.md"
    if not path.exists():
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:2000]
        return re.search(r"disable-model-invocation\s*:\s*true", head) is not None
    except Exception:
        return False


def override_exists(repo: Path) -> bool:
    """Return True if the methodology self-extend override file exists."""
    return (repo / ".methodology-self-extend-override").exists()


def validate(repo: Path) -> list[str]:
    """Return a list of violations, empty if commit is allowed."""
    if override_exists(repo):
        return []  # explicit override — documented reason in the file

    files = staged_files(repo)
    if not files:
        return []
    touched = skill_touched(files)
    # Filter out _shared — it's a library, not a skill
    touched = {k: v for k, v in touched.items() if not k.startswith("_")}
    errors: list[str] = []

    staged_set = set(files)
    hooks_staged = any(f.startswith("hooks/check-skills.sh") for f in files)
    fixtures_staged_names = {
        f for f in files if f.startswith("tests/fixtures/")
    }

    for skill, _skill_files in touched.items():
        # Rule 1: references
        if needs_references(repo, skill):
            has_refs_staged = any(
                f.startswith(f"skills/{skill}/references/") for f in files
            )
            refs_dir = repo / "skills" / skill / "references"
            refs_exist_on_disk = refs_dir.is_dir() and any(refs_dir.iterdir())
            if not (has_refs_staged or refs_exist_on_disk):
                errors.append(
                    f"[/{skill}] SKILL.md mentions `references/` but no file "
                    f"under skills/{skill}/references/ is staged AND the folder "
                    f"does not exist on disk — create the references first"
                )

        # Rule 2: triggers (skipped for disable-model-invocation skills)
        if not is_disable_model_invocation(repo, skill):
            if not (hooks_staged or hook_has_trigger(repo, skill)):
                errors.append(
                    f"[/{skill}] hooks/check-skills.sh has no mention of "
                    f"`/{skill}` AND no hook change is staged — add trigger "
                    f"phrases before committing"
                )

        # Rule 3: fixture
        fixture_matches_staged = any(
            skill in f for f in fixtures_staged_names
        )
        if not (fixture_matches_staged or fixture_exists(repo, skill)):
            errors.append(
                f"[/{skill}] no fixture under tests/fixtures/ mentions this "
                f"skill AND none is staged — add at least an idea.md + "
                f"expected-files.txt + notes.md fixture before committing"
            )

    return errors


def emit_deny(errors: list[str]) -> None:
    msg = (
        "[COMMIT COMPLETENESS BLOCK] Коммит остановлен хуком "
        "check-commit-completeness.\n\n"
        "Обнаружены незакрытые пункты Quality Gate 2 "
        "(инцидент v1.4.0):\n\n"
        + "\n".join(f"  ❌ {e}" for e in errors)
        + "\n\nЗакрой все пункты и повтори `git commit`. Хук не обойти "
        "флагом — это его задача. Единственный legitimate escape — "
        "файл `.methodology-self-extend-override` в корне репо с "
        "письменным обоснованием."
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
    if tool != "Bash":
        return 0
    cmd = ((payload.get("tool_input") or {}).get("command")) or ""
    if not GIT_COMMIT_RE.search(cmd):
        return 0

    repo = find_repo_root(Path.cwd())
    if repo is None:
        return 0

    errors = validate(repo)
    if errors:
        emit_deny(errors)
        return 2  # unreachable

    return 0


if __name__ == "__main__":
    sys.exit(main())
