#!/usr/bin/env python3
"""Strict route of /bugfix, /test and /refactor (ITD-PLAN-S8, ADR-016 session 8).

The strict steps - the edit-scope freeze, the mandatory ROOT_CAUSE.md, the Step 5.5 mutation refute pass - live in
each skill's references/strict.md and run only on the strict route. Step 0 of every SKILL.md picks the route with
one identical command: `strict` when the project's CLAUDE.md, .claude/CLAUDE.md or AGENTS.md declares
`itd-route: strict` / `<!-- itd:strict -->` or `itd-domain: data-sensitive` / `<!-- itd:data-sensitive -->` in the
first 8 KB (case-insensitive), `minimal` otherwise - also when the project has .itd/ and .itd/SCOPE_LOCK.md.

  [1] the route command runs as written (extracted from the SKILL.md files) on project fixtures;
  [2] the minimal path writes no freeze state, no ROOT_CAUSE.md and runs no mutation;
  [3] the strict files carry the steps, and the freeze they write is the one hooks/freeze.sh reads and then lifted;
  [4] descriptions in the Agent Skills form, texts at most 500 lines, no positional placeholders, wiring.

Self-contained, stdlib only, cross-platform (Git Bash through ITD_BASH on Windows). Run:
  python3 tests/verify_strict_route.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("bugfix", "test", "refactor")
SKILL_MD = {"bugfix": ROOT / "skills" / "bugfix" / "SKILL.md", "test": ROOT / "skills" / "test" / "SKILL.md",
            "refactor": ROOT / "skills" / "refactor" / "SKILL.md"}
STRICT_MD = {"bugfix": ROOT / "skills" / "bugfix" / "references" / "strict.md",
             "test": ROOT / "skills" / "test" / "references" / "strict.md",
             "refactor": ROOT / "skills" / "refactor" / "references" / "strict.md"}
FREEZE_HOOK = ROOT / "hooks" / "freeze.sh"
PROFILES = ROOT / "docs" / "project-profiles.md"
RUN_ALL = ROOT / "tests" / "run-all.sh"
WORKFLOWS = (ROOT / ".github" / "workflows" / "meta-review.yml", ROOT / ".github" / "workflows" / "windows-verify.yml")
ORACLE = "verify_strict_route"

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("ok   " + name)
    else:
        FAILED += 1
        print("FAIL " + name + (("  - " + detail) if detail else ""))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def skill(name: str) -> str:
    return read(SKILL_MD[name])


def strict(name: str) -> str:
    return read(STRICT_MD[name])


def section(text: str, heading: str) -> str:
    """The body under a `### <heading>` line up to the next `##`/`###` heading."""
    m = re.search(r"^###\s+" + re.escape(heading) + r".*$", text, re.M)
    if not m:
        return ""
    rest = text[m.end():]
    e = re.search(r"^#{2,3}\s", rest, re.M)
    return rest[: e.start()] if e else rest


def route_command(text: str) -> str:
    body = section(text, "Step 0: Route")
    m = re.search(r"```bash\n(.*?)\n```", body, re.S)
    return m.group(1).strip() if m else ""


def frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    out: dict[str, str] = {}
    for line in (m.group(1).splitlines() if m else []):
        k, sep, v = line.partition(":")
        if sep and not line.startswith(" "):
            out[k.strip()] = v.strip().strip("'\"")
    return out


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=60, check=True)


def shell(script: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    # Git Bash on Windows (ITD_BASH, as the sync tests), sh elsewhere
    bash = os.environ.get("ITD_BASH") or shutil.which("sh") or "sh"
    return subprocess.run([bash, "-c", script], cwd=str(cwd), env=env or dict(os.environ), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=60)


def route_of(cmd: str, project: Path, cwd: Path | None = None) -> str:
    res = shell(cmd, cwd or project)
    return res.stdout.strip() if res.returncode == 0 else f"rc={res.returncode} {res.stderr.strip()[:120]}"


def project(base: Path, name: str, files: dict[str, str], repo: bool = False) -> Path:
    root = base / name
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body.encode("utf-8"))
    root.mkdir(parents=True, exist_ok=True)
    if repo:
        git(root, "init", "-q")
    return root


def part_route(base: Path) -> str:
    print("[1] the route command")
    cmds = {name: route_command(skill(name)) for name in SKILLS}
    check("each SKILL.md has a Step 0 route command", all(cmds.values()),
          ", ".join(n for n, c in cmds.items() if not c))
    check("the route command is identical in the three skills", len(set(cmds.values())) == 1)
    cmd = cmds["bugfix"]
    if not cmd:
        return ""
    plain = "# Project\n\nOrdinary rules.\n"
    pad = "x" * 70 + "\n"
    cases = [
        ("no CLAUDE.md, AGENTS.md", {}, "minimal"),
        ("ordinary project with .itd/ and .itd/SCOPE_LOCK.md",
         {"CLAUDE.md": plain, "AGENTS.md": "Treat .itd/ as the contract.\n", ".itd/SCOPE_LOCK.md": "# scope\n",
          ".itd/ACCEPTANCE_CONTRACT.json": "{}\n"}, "minimal"),
        ("itd-route: strict in CLAUDE.md", {"CLAUDE.md": plain + "itd-route: strict\n"}, "strict"),
        ("<!-- itd:strict --> in .claude/CLAUDE.md", {".claude/CLAUDE.md": "<!-- itd:strict -->\n" + plain}, "strict"),
        ("<!-- itd:strict--> without a space", {"CLAUDE.md": "<!-- itd:strict-->\n"}, "strict"),
        ("itd-domain: data-sensitive in AGENTS.md", {"AGENTS.md": "itd-domain: data-sensitive\n"}, "strict"),
        ("<!-- itd:data-sensitive --> in CLAUDE.md", {"CLAUDE.md": "<!-- itd:data-sensitive -->\n"}, "strict"),
        ("case-insensitive marker", {"CLAUDE.md": "ITD-Route:   STRICT\n"}, "strict"),
        ("marker at the end of a file without a newline", {"CLAUDE.md": plain + "itd-route: strict"}, "strict"),
        ("itd-route: strictly is not the marker", {"CLAUDE.md": "itd-route: strictly\n"}, "minimal"),
        ("itd-route: strict-mode is not the marker", {"CLAUDE.md": "itd-route: strict-mode\n"}, "minimal"),
        ("itd-route: minimal", {"CLAUDE.md": "itd-route: minimal\n"}, "minimal"),
        ("itd-profile: brownfield only", {"CLAUDE.md": "itd-profile: brownfield\n"}, "minimal"),
        ("a prefix before the key is not the marker", {"CLAUDE.md": "not-itd-route: strict\n"}, "minimal"),
        ("a prefix before the domain key is not the marker", {"AGENTS.md": "xitd-domain: data-sensitive\n"}, "minimal"),
        ("bare itd:strict in prose is not the marker", {"CLAUDE.md": "We may add itd:strict later.\n"}, "minimal"),
        ("the key inside a sentence is not the marker", {"CLAUDE.md": "Set itd-route: strict in CLAUDE.md.\n"}, "minimal"),
        ("an indented marker line with CRLF", {"CLAUDE.md": "# P\r\n\r\n  itd-route: strict\r\n"}, "strict"),
        ("a marker split across two files does not join",
         {"CLAUDE.md": plain + "itd-route: stri", ".claude/CLAUDE.md": "ct\n"}, "minimal"),
        ("marker inside the first 8 KB", {"CLAUDE.md": pad * 100 + "itd-route: strict\n"}, "strict"),
        ("marker after the first 8 KB is not read", {"CLAUDE.md": pad * 120 + "itd-route: strict\n"}, "minimal"),
    ]
    for i, (label, files, want) in enumerate(cases):
        got = route_of(cmd, project(base, f"p{i}", files))
        check(f"route: {label} -> {want}", got == want, got)
    root = project(base, "repo", {"CLAUDE.md": "itd-route: strict\n", "src/app/CLAUDE.md": plain}, repo=True)
    got = route_of(cmd, root, cwd=root / "src" / "app")
    check("route from a subdirectory of a repository reads the root files -> strict", got == "strict", got)
    root = project(base, "repo-plain", {"CLAUDE.md": plain, "src/CLAUDE.md": "itd-route: strict\n"}, repo=True)
    got = route_of(cmd, root, cwd=root / "src")
    check("a marker in a subdirectory file does not count -> minimal", got == "minimal", got)
    return cmd


def part_minimal() -> None:
    print("[2] the minimal path")
    bugfix, test, refactor = skill("bugfix"), skill("test"), skill("refactor")
    for name, text in (("bugfix", bugfix), ("refactor", refactor), ("test", test)):
        check(f"{name}: SKILL.md writes no freeze state", "claude-freeze" not in text)
        step0 = section(text, "Step 0: Route")
        check(f"{name}: Step 0 names references/strict.md and --strict",
              "references/strict.md" in step0 and "--strict" in step0)
    sentences = [s for s in re.split(r"(?<=[.;])\s+|\n", bugfix) if "ROOT_CAUSE" in s]
    loose = [s for s in sentences if "strict route" not in s.lower() and "no root_cause.md" not in s.lower()]
    check("bugfix: every ROOT_CAUSE.md sentence in SKILL.md is the strict route (or says no ROOT_CAUSE.md)",
          bool(sentences) and not loose, "; ".join(loose)[:200])
    check("bugfix: SKILL.md does not scaffold the ROOT_CAUSE template", "docs/templates/ROOT_CAUSE" not in bugfix)
    heads = re.findall(r"^### (Step \d+: [^\n]+)$", bugfix, re.M)
    want = ["Step 0: Route", "Step 1: Reproduce", "Step 2: Locate", "Step 3: Find the cause", "Step 4: Fix",
            "Step 5: Regression test"]
    check("bugfix: the minimal path is route, reproduce, locate, cause, fix, regression test and suite",
          len(heads) == len(want) and all(h.startswith(w) for h, w in zip(heads, want)), str(heads))
    step3 = section(bugfix, "Step 3: Find the cause").lower()
    check("bugfix: the cause is one sentence with evidence, fail-closed",
          "one sentence with evidence" in step3 and "fail-closed" in step3)
    step5 = section(bugfix, "Step 5: Regression test").lower()
    check("bugfix: Step 5 keeps a red-to-green regression test and runs the whole suite",
          "fails on the old code" in step5 and "whole test suite" in step5)
    check("test: SKILL.md has no Step 5.5 and no mutation run",
          not re.search(r"^###\s+Step\s+5\.5", test, re.M) and "ITD_RUN_RECORD" not in test
          and "mutation marker" not in test.lower())
    step6 = section(test, "Step 6: Mark")
    check("test: the session marker for the DoD gate stays on the minimal path (both temp dirs)",
          '"/tmp/claude-test-done-' in step6 and '"$tmpd/claude-test-done-' in step6)


def freeze_hook(session: str, path: str, base_env: dict[str, str]) -> str:
    env = {**base_env, "PYTHONUTF8": "1", "CLAUDE_SESSION_ID": session}
    res = subprocess.run([sys.executable, str(FREEZE_HOOK)],
                         input=json.dumps({"tool_name": "Edit", "tool_input": {"file_path": path}}),
                         capture_output=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    if not res.stdout.strip():
        return ""
    try:
        return (json.loads(res.stdout).get("hookSpecificOutput") or {}).get("additionalContext") or ""
    except ValueError:
        return "<BADJSON>" + res.stdout[:100]


def bash_blocks(text: str) -> list[str]:
    return [b.strip() for b in re.findall(r"```bash\n(.*?)\n```", text, re.S)]


def part_strict(base: Path) -> None:
    print("[3] the strict route")
    b, r, t = strict("bugfix"), strict("refactor"), strict("test")
    check("strict.md exists in the three skills", all((b, r, t)))
    sections = ("Summary", "Reproduction", "Evidence", "Fix Hypothesis", "Regression Test", "Constraints")
    check("bugfix strict: ROOT_CAUSE.md with its six sections, fail-closed",
          "ROOT_CAUSE.md" in b and all(f"**{s}**" in b for s in sections) and "fail-closed" in b)
    step55 = re.search(r"^###\s+Step\s+5\.5", t, re.M)
    check("test strict: the Step 5.5 refute pass with the recorded mutation run, marker and fixture rules",
          bool(step55) and "ITD_RUN_RECORD=1" in t and "exactly once" in t and "escape sequences" in t)
    for name, text, target in (("bugfix", b, "/path/to/bug/directory"), ("refactor", r, "/path/to/refactor/directory")):
        blocks = bash_blocks(text)
        write = [x for x in blocks if "tee " in x and "claude-freeze-" in x]
        lift = [x for x in blocks if "rm -f" in x and "claude-freeze-" in x]
        check(f"{name} strict: one freeze block and one lift block", len(write) == 1 and len(lift) == 1)
        if len(write) != 1 or len(lift) != 1:
            continue
        session = f"s8-{name}-{uuid.uuid4().hex[:8]}"
        scope = (base / f"scope-{name}").as_posix()
        if os.name == "nt":
            # Git Bash maps /tmp to the user temp dir whatever TEMP says, and python3 there is often the Store
            # stub, so both copies are one file in the real temp dir - the one the hook reads first
            ptmp = Path(tempfile.gettempdir())
            env = {**os.environ, "CLAUDE_SESSION_ID": session}
        else:
            # the platform temp dir apart from /tmp, so each of the two copies is checked on its own
            ptmp = base / f"ptmp-{name}"
            ptmp.mkdir()
            env = {**os.environ, "CLAUDE_SESSION_ID": session, "TMPDIR": str(ptmp), "TEMP": str(ptmp), "TMP": str(ptmp)}
        res = shell(write[0].replace(target, scope), base, env)
        written = [d for d in (ptmp, Path("/tmp")) if (d / f"claude-freeze-{session}.state").exists()]
        warn_out = freeze_hook(session, (base / "elsewhere" / "x.py").as_posix(), env)
        quiet_in = freeze_hook(session, scope + "/a.py", env)
        check(f"{name} strict: the written freeze makes hooks/freeze.sh warn outside the scope",
              res.returncode == 0 and warn_out != "" and quiet_in == "", res.stderr[:120] + warn_out[:80])
        check(f"{name} strict: the freeze state is written to both temp dirs",
              ptmp in written if os.name == "nt" else len(written) == 2, str(written))
        res = shell(lift[0], base, env)
        after = freeze_hook(session, (base / "elsewhere" / "x.py").as_posix(), env)
        left = [d for d in (ptmp, Path("/tmp")) if (d / f"claude-freeze-{session}.state").exists()]
        check(f"{name} strict: the lift block removes the state and the hook falls silent",
              res.returncode == 0 and after == "" and not left, f"{after[:80]} {left}")
        for d in left:
            (d / f"claude-freeze-{session}.state").unlink(missing_ok=True)


def part_texts() -> None:
    print("[4] descriptions, sizes, placeholders, wiring")
    for name in SKILLS:
        desc = frontmatter(skill(name)).get("description", "")
        check(f"{name}: description says what, then 'Use when'",
              bool(desc) and "Use when " in desc and not desc.startswith("Use when"), desc[:80])
        check(f"{name}: description at most 1024 characters, no angle brackets",
              0 < len(desc) <= 1024 and "<" not in desc and ">" not in desc, str(len(desc)))
        files = [SKILL_MD[name], *sorted(SKILL_MD[name].parent.joinpath("references").glob("*.md"))]
        long = [f"{f.name}={len(read(f).splitlines())}" for f in files if len(read(f).splitlines()) > 500]
        check(f"{name}: SKILL.md and references at most 500 lines", not long, ", ".join(long))
        both = skill(name) + strict(name)
        hits = re.findall(r"\$(?:[0-9]|ARGUMENTS\[)", both)
        check(f"{name}: no positional $N placeholder (the host substitutes it)", not hits, str(hits))
    profiles = read(PROFILES)
    check("docs/project-profiles.md documents itd-route: strict", "itd-route: strict" in profiles)
    check("wired into tests/run-all.sh", ORACLE in read(RUN_ALL))
    for yml in WORKFLOWS:
        check(f"wired into {yml.name}", ORACLE + ".py" in read(yml))


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="itd-strict-route-"))
    try:
        part_route(base)
        part_minimal()
        part_strict(base)
        part_texts()
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print(("PASSED" if not FAILED else "FAILED") + f": {PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
