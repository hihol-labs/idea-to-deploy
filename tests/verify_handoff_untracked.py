#!/usr/bin/env python3
"""verify_handoff_untracked.py — HANDOFF-UNTRACKED-1: HANDOFF.md stays out of reviewed diffs.

REL-1.106.0 (BACKLOG P2 2026-09-27): a committed HANDOFF.md is always one step behind its own
commit - a file inside a commit cannot record the review of that commit. The independent reviewer
found exactly that in rel4, rel5 and pub3 (stop rule REDESIGN_OR_DISCARD on rel5, ADR-007 on pub3).
Owner decision (goal approved 2026-09-27): the root HANDOFF.md is a local hand-over packet, not a
tracked file; release and ledger-close scopes do not list it.

Contract of this oracle:

  1. The root `HANDOFF.md` is not in the git index of this repository. Whether the local file
     survived is a working-tree property: `git rm --cached` and a deletion give byte-identical
     commits, and a clean checkout (CI, isolated oracle run) never has the file. So the oracle
     proves what the tree can carry - the instructions prescribe `git rm --cached` with the local
     file kept and no document tells to delete it (checks in [3]). The survival of the local
     packet itself is proven outside this oracle, by the machine leg `local-packet` over the
     declared ignored input `HANDOFF.md` of the Verification Loop receipt.
  2. `.gitignore` carries the root-anchored rule `/HANDOFF.md`: the root file is ignored, a
     `HANDOFF.md` in any subdirectory (fixture outputs of the /handoff skill) is not.
  3. `skills/handoff/SKILL.md` has the section «Где живёт пакет» that keeps the packet local:
     it names `.gitignore`, says the packet never enters a reviewed diff, and `git add -f` occurs
     exactly once in the whole skill - inside the canonical prohibition phrase (whitespace
     normalized, so a re-wrap is safe; a rewording of the prohibition is a deliberate oracle change);
     no line outside that section tells to commit or stage `HANDOFF.md`.
  4. `docs/RELEASE_RUNBOOK.md` has the section «SCOPE_LOCK релизного и ledger-close юнита» with
     exactly two fenced templates (release, ledger-close); neither lists HANDOFF in its Allowed
     Change Areas; both list `HANDOFF.md` and the owner-command rule in Forbidden Change Areas and
     carry a `## Review Rule` section with the /review pass.
  These are structural text guards; the meaning of the prose is left to review.
  5. The oracle is registered in tests/run-all.sh.

RED on the pre-fix tree (fde64c2): every check above fails there.
Run: sh skills/_shared/itd_py.sh tests/verify_handoff_untracked.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "handoff" / "SKILL.md"
RUNBOOK = ROOT / "docs" / "RELEASE_RUNBOOK.md"
SKILL_HEADING = "### Где живёт пакет"
RUNBOOK_HEADING = "## SCOPE_LOCK релизного и ledger-close юнита"
TEMPLATE_TITLES = ("# REL-X.Y.Z", "# REL-X.Y.Z ledger-close")
FENCE = re.compile(r"^ {0,3}(```|~~~)")
COMMIT_WORDS = re.compile(r"коммит|commit|git add", re.IGNORECASE)
FORCE_PROHIBITION = "не добавляй в коммит, даже через `git add -f`"
UNTRACK_KEEPS_LOCAL = "`git rm --cached HANDOFF.md` (локальный файл остаётся)"
REMOVE_CMD = re.compile(r"(?<![\w-])(?:git\s+)?rm(?P<opts>(?:\s+-[\w-]+)*)\s+HANDOFF\.md")

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        fails.append(name)
        print(f"  FAIL {name}" + (f" - {detail}" if detail else ""))


def git(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True, env=env)


RULE_LINE = re.compile(r"^(?P<source>.*):(?P<line>\d*):(?P<pattern>.*)\t")
NESTED = ("docs/HANDOFF.md", "tests/fixtures/fixture-18-handoff/HANDOFF.md")


def ignore_rule(path: str, env: dict | None = None) -> tuple[str, str] | None:
    """(source, pattern) of the deciding ignore rule, ("", "") when none matches, None on a git
    failure. `-v` names the source, so a host-global exclude cannot pass for the repository rule."""
    found = git("check-ignore", "-v", "-n", "--no-index", "--", path, env=env)
    match = RULE_LINE.match(found.stdout) if found.returncode in (0, 1) else None
    return (match["source"], match["pattern"]) if match else None


def repo_ignores(rule: tuple[str, str] | None) -> bool:
    return bool(rule) and rule[0] == ".gitignore" and not rule[1].startswith("!")


def handoff_untracked(env: dict | None = None) -> tuple[bool, int]:
    """True only when git answers (exit 0) with an empty index match; a git failure is False."""
    listed = git("ls-files", "-z", "--", "HANDOFF.md", env=env)
    return listed.returncode == 0 and not listed.stdout, listed.returncode


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def section(text: str, heading: str) -> list[str]:
    """Lines of the section opened by `heading` up to the next heading of the same or higher
    level outside a code fence; empty when the heading is absent."""
    lines = text.splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    try:
        start = lines.index(heading)
    except ValueError:
        return []
    out: list[str] = []
    in_fence = False
    for line in lines[start + 1:]:
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and line.startswith("#"):
            hashes = len(line) - len(line.lstrip("#"))
            if hashes <= level and line[hashes:hashes + 1] == " ":
                break
        out.append(line)
    return out


def fenced_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in lines:
        if FENCE.match(line):
            if current is None:
                current = []
            else:
                blocks.append(current)
                current = None
        elif current is not None:
            current.append(line)
    return blocks


def subsection(block: list[str], heading: str) -> str:
    return "\n".join(section("\n".join(block), heading))


def main() -> int:
    print("[1] root HANDOFF.md is not tracked")
    probe = git("rev-parse", "--is-inside-work-tree")
    check("git-worktree", probe.returncode == 0, probe.stderr.strip())
    untracked, rc = handoff_untracked()
    check("handoff-not-in-index", probe.returncode == 0 and untracked,
          f"HANDOFF.md is in the index or git failed (rc {rc}): git rm --cached HANDOFF.md")
    broken, broken_rc = handoff_untracked(dict(os.environ, GIT_DIR=str(ROOT / "no-such-git-dir")))
    check("index-check-fails-closed", not broken and broken_rc != 0,
          f"a git failure must not read as untracked (rc {broken_rc})")

    print("[2] root-anchored ignore rule")
    rules = [ln.strip() for ln in read(ROOT / ".gitignore").splitlines()]
    check("gitignore-root-rule", "/HANDOFF.md" in rules, "add the line /HANDOFF.md to .gitignore")
    root_rule = ignore_rule("HANDOFF.md")
    check("root-handoff-ignored", root_rule == (".gitignore", "/HANDOFF.md"),
          f"git check-ignore -v HANDOFF.md must name .gitignore:/HANDOFF.md, got {root_rule}")
    with tempfile.TemporaryDirectory(prefix="handoff-exclude-") as tmp:
        excludes = Path(tmp) / "global-excludes"
        excludes.write_text("HANDOFF.md\n", encoding="utf-8")
        hostile = dict(os.environ, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.excludesFile",
                       GIT_CONFIG_VALUE_0=str(excludes))
        for label, env in (("", None), ("global-exclude:", hostile)):
            for nested in NESTED:
                rule = ignore_rule(nested, env)
                check(f"nested-not-ignored:{label}{nested}", rule is not None and not repo_ignores(rule),
                      f"the repository rule must stay anchored to the root, got {rule}")
        check("global-exclude-seen", ignore_rule(NESTED[0], hostile) not in (None, ("", "")),
              "the hostile host setup did not take effect, the parity check is vacuous")

    print("[3] /handoff keeps the packet local")
    skill = "\n".join(section(read(SKILL), SKILL_HEADING))
    check("skill-section", bool(skill.strip()), f"missing {SKILL_HEADING!r} in {SKILL}")
    for token in (".gitignore", "отревьюенн"):
        check(f"skill-names:{token}", token in skill)
    whole = " ".join(read(SKILL).split())
    check("skill-forbids-force-add",
          whole.count("git add -f") == 1 and FORCE_PROHIBITION in " ".join(skill.split()),
          f"`git add -f` must occur once in {SKILL.name}, inside {FORCE_PROHIBITION!r}")
    check("skill-untrack-keeps-local", UNTRACK_KEEPS_LOCAL in " ".join(skill.split()),
          f"the section must prescribe {UNTRACK_KEEPS_LOCAL!r}, not a deletion")
    destructive = [m.group(0) for doc in (read(SKILL), read(RUNBOOK))
                   for m in REMOVE_CMD.finditer(doc) if "--cached" not in m.group("opts").split()]
    check("no-destructive-remove", not destructive, f"deletes the local packet: {destructive[:2]}")
    section_lines = set(section(read(SKILL), SKILL_HEADING))
    stray = [ln.strip() for ln in read(SKILL).splitlines()
             if ln not in section_lines and "HANDOFF.md" in ln and COMMIT_WORDS.search(ln)]
    check("skill-no-commit-instruction", not stray, f"outside the section: {stray[:2]}")

    print("[4] release and ledger-close SCOPE_LOCK templates")
    runbook = section(read(RUNBOOK), RUNBOOK_HEADING)
    check("runbook-section", bool(runbook), f"missing {RUNBOOK_HEADING!r} in {RUNBOOK}")
    blocks = fenced_blocks(runbook)
    titles = tuple(b[0].strip() if b else "" for b in blocks)
    check("runbook-two-templates", titles == TEMPLATE_TITLES, f"got {titles}")
    for block in blocks:
        title = block[0].strip() if block else "?"
        allowed = subsection(block, "## Allowed Change Areas")
        forbidden = subsection(block, "## Forbidden Change Areas")
        check(f"template-allowed:{title}", bool(allowed.strip()) and "handoff" not in allowed.lower(),
              "Allowed Change Areas is empty or lists HANDOFF")
        check(f"template-forbids:{title}", "`HANDOFF.md`" in forbidden,
              "Forbidden Change Areas must name `HANDOFF.md`")
        check(f"template-owner-command:{title}", "owner's explicit command" in forbidden,
              "Forbidden Change Areas must keep merge/push on the owner's explicit command")
        check(f"template-review-rule:{title}", "/review" in subsection(block, "## Review Rule"),
              "a `## Review Rule` section with the /review pass is required")

    print("[5] registration")
    check("run-all-registered", "verify_handoff_untracked" in read(ROOT / "tests" / "run-all.sh"))

    print(f"{'PASSED' if not fails else 'FAILED'}: {len(fails)} failed")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
