#!/usr/bin/env python3
"""itd_projects_doctor.py - read-only report of projects that drift from the installed Idea to Deploy
(INSTALL-OWNED-1).

The methodology lives in the installation (rules, hooks, skills, the .itd tools); a project holds only its own
contracts (.itd/*.json, *.md), state (.itd-memory/) and a short pointer block in CLAUDE.md / AGENTS.md. This
doctor finds what still freezes a project on an old version:

  old-rules-block   CLAUDE.md / AGENTS.md carries the copied v1.20 rules block instead of the pointer
  tool-copy         .itd/<tool>.py copied by an older /adopt (no longer run; the installed tool is)
  duplicate-hooks   .claude/settings*.json re-registers installed hooks (the user's ~/.claude/hooks/*, also
                    written as $HOME/..., %USERPROFILE%\\... or an absolute home path): they run twice and
                    re-enable hooks the owner disabled globally in ~/.claude/itd-disabled-hooks.txt
  project-hooks     .claude/hooks or project-specific hook commands in .claude/settings*.json (a relative
                    .claude/hooks/..., $CLAUDE_PROJECT_DIR/... or any non-home path)
  shadow-skill      .claude/skills/<name> with the name of an installed Idea to Deploy skill

It never changes anything. Usage:
  itd_projects_doctor.py [ROOT ...] [--depth N] [--json] [--strict]
ROOT defaults to ~/projects. A clean scan prints nothing in text mode; --json always prints the machine-readable
report (an empty one on a clean scan). Exit 0, or 1 with --strict when any finding is reported, 2 on usage errors
(--help exits 0).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

TOOLS = ("itd_hygiene.py", "itd_progress.py", "check_contract_drift.py", "itd_init_validate.py")
OLD_BLOCK_RE = re.compile(r"<!--\s*idea-to-deploy:begin\s+v1\.20\s*-->")
# A command is split into shell-like tokens first, so a quoted path keeps its spaces ("C:\Users\Jane Doe\...").
TOKEN_RE = re.compile(r"""(?:"[^"]*"|'[^']*'|[^\s"'])+""")
# The hook file name ends before shell punctuation ("~/.claude/hooks/stop.sh; echo done" names stop.sh).
HOOK_IN_TOKEN_RE = re.compile(r"(.*?)\.claude[/\\]+hooks[/\\]+([\w.@+-]+)")
HOME_PREFIXES = ("~", "$HOME", "${HOME}", "%USERPROFILE%", "%HOME%", "$env:USERPROFILE", "${env:USERPROFILE}")
PROJECT_PREFIXES = ("$CLAUDE_PROJECT_DIR", "${CLAUDE_PROJECT_DIR}", "%CLAUDE_PROJECT_DIR%", "$env:CLAUDE_PROJECT_DIR")
HOME_PATH_RE = re.compile(r"^(?:/mnt/[a-z])?(?:[a-z]:)?/(?:home|users)/[^/]+$|^/root$")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".cache", "dist", "build"}
SKILLS_DIR = Path(__file__).resolve().parent.parent


def installed_skills() -> set[str]:
    return {p.name for p in SKILLS_DIR.iterdir()
            if p.is_dir() and not p.name.startswith("_") and (p / "SKILL.md").is_file()}


def disabled_hooks() -> set[str]:
    """Hook files the owner switched off for the whole machine (scripts/sync-to-active.sh honours this list)."""
    text = _read(Path.home() / ".claude" / "itd-disabled-hooks.txt")
    return {line.split("#", 1)[0].strip().lstrip("\ufeff") for line in text.splitlines()} - {""}


def _norm(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").lower()


def _starts_with_token(prefix: str, tokens: tuple[str, ...]) -> bool:
    """True when the prefix begins with one of the tokens followed by a path separator ($HOMELESS is not $HOME)."""
    return any(prefix.startswith(t) and prefix[len(t):len(t) + 1] in ("/", "\\") for t in tokens)


def _home_prefix(prefix: str, home: str) -> bool:
    if _starts_with_token(prefix, PROJECT_PREFIXES):
        return False
    if _starts_with_token(prefix, HOME_PREFIXES):
        return True
    if prefix.startswith(("/", "\\")) or re.match(r"[A-Za-z]:[/\\]", prefix):
        path = _norm(prefix)
        return path == home or bool(HOME_PATH_RE.match(path))
    return False


def hook_refs(command: str) -> list[tuple[str, bool]]:
    """Every .claude/hooks/<name> a command runs, as (name, installed).

    Installed means the user's installation (<home>/.claude/hooks/<name>); a relative .claude/hooks/...,
    $CLAUDE_PROJECT_DIR/... or any absolute path outside a home directory is a project hook. Inside a quoted
    script ("cd ~ && ~/.claude/hooks/x.sh") the last word before the path is checked as well.
    """
    home = _norm(str(Path.home()))
    refs = []
    for token in TOKEN_RE.findall(command):
        bare = token.replace('"', "").replace("'", "")
        for match in HOOK_IN_TOKEN_RE.finditer(bare):
            prefix, name = match.group(1), match.group(2)
            refs.append((name, any(_home_prefix(c, home) for c in [prefix] + prefix.split()[-1:])))
    return refs


def installed_hook(command: str) -> str | None:
    """Name of the first user-installed hook a command runs, or None."""
    return next((name for name, installed in hook_refs(command) if installed), None)


def find_projects(root: Path, depth: int) -> list[Path]:
    found: list[Path] = []
    root = root.resolve()
    base = len(root.parts)
    for current, dirs, _files in os.walk(root):
        here = Path(current)
        if (here / ".git").exists():
            found.append(here)
        if len(here.parts) - base >= depth:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    return sorted(set(found))


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def inspect(project: Path, skills: set[str]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for name in ("CLAUDE.md", "AGENTS.md"):
        if OLD_BLOCK_RE.search(_read(project / name)):
            findings.append({"kind": "old-rules-block", "path": name,
                             "fix": "replace the block with the pointer of skills/adopt/references/claude-md-template.md"})
    for tool in TOOLS:
        if (project / ".itd" / tool).is_file():
            findings.append({"kind": "tool-copy", "path": f".itd/{tool}",
                             "fix": "unused since INSTALL-OWNED-1 (the installed tool runs); may be deleted"})
    if (project / ".claude" / "hooks").is_dir():
        findings.append({"kind": "project-hooks", "path": ".claude/hooks",
                         "fix": "project hooks override the installed ones; keep only if intended"})
    for name in ("settings.json", "settings.local.json"):
        text = _read(project / ".claude" / name)
        if text:
            try:
                data = json.loads(text)
            except ValueError:
                data = {}
            hooks = data.get("hooks") if isinstance(data, dict) else None
            if hooks:
                commands = [str(h.get("command", "")) for groups in hooks.values() if isinstance(groups, list)
                            for g in groups if isinstance(g, dict) for h in g.get("hooks", []) if isinstance(h, dict)]
                # A command can run installed and project hooks together: it then counts on both sides, and
                # every installed hook in it is checked against the disabled list.
                refs = {c: hook_refs(c) for c in commands}
                installed_names = [n for c in commands for n, inst in refs[c] if inst]
                installed = [c for c in commands if any(inst for _, inst in refs[c])]
                own = [c for c in commands
                       if not any(inst for _, inst in refs[c]) or any(not inst for _, inst in refs[c])]
                disabled = sorted(set(installed_names) & disabled_hooks())
                if installed:
                    fix = (f"{len(installed)} of {len(commands)} commands re-register installed hooks: they run twice"
                           + (f" and re-enable hooks disabled globally ({', '.join(disabled)})" if disabled else "")
                           + "; remove them from the project settings")
                    findings.append({"kind": "duplicate-hooks", "path": f".claude/{name}", "fix": fix})
                if own:
                    findings.append({"kind": "project-hooks", "path": f".claude/{name}",
                                     "fix": "project-specific hook commands run besides the installed ones; keep only if intended"})
    skill_root = project / ".claude" / "skills"
    if skill_root.is_dir():
        for entry in sorted(skill_root.iterdir()):
            if entry.is_dir() and entry.name in skills:
                findings.append({"kind": "shadow-skill", "path": f".claude/skills/{entry.name}",
                                 "fix": f"replaces the installed /{entry.name} in this project; keep only if intended"})
    return findings


def _depth(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return value


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="itd_projects_doctor.py", description=__doc__.split("\n", 1)[0])
    ap.add_argument("roots", nargs="*", type=Path)
    ap.add_argument("--depth", type=_depth, default=3)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    try:
        args = ap.parse_args(argv[1:])
    except SystemExit as exc:  # --help exits 0, a usage error 2
        return exc.code if isinstance(exc.code, int) else 2
    roots = args.roots or [Path.home() / "projects"]
    skills = installed_skills()
    report = []
    for root in roots:
        if not root.is_dir():
            print(f"itd_projects_doctor: not a directory: {root}", file=sys.stderr)
            return 2
        for project in find_projects(root, args.depth):
            findings = inspect(project, skills)
            if findings:
                report.append({"project": str(project), "findings": findings})
    if args.json:
        print(json.dumps({"projects": report, "count": sum(len(r["findings"]) for r in report)},
                         ensure_ascii=False, indent=1))
    else:
        for row in report:
            for f in row["findings"]:
                print(f"{f['kind']:16} {row['project']}/{f['path']} - {f['fix']}")
        if report:  # a clean scan stays silent
            print(f"DONE projects-with-findings={len(report)} findings={sum(len(r['findings']) for r in report)}")
    return 1 if args.strict and report else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
