#!/usr/bin/env python3
"""verify_install_owned_tools.py - INSTALL-OWNED-1: the methodology code and rules live in the installation; a
project holds only its own contracts, state and a pointer block.

  1. skills/_shared/itd_tool.sh runs a project tool from the installation, never from a copy in <project>/.itd/:
     order $ITD_TEMPLATES_DIR > the source next to the helper (repository / Codex plugin) > ~/.claude/templates/itd;
     a legacy project copy only when nothing is installed (warning on stderr); unknown tools are refused.
  2. check_contract_drift.py takes --root, so the installed copy checks the current project.
  3. Nothing shipped (skills, hooks, agents, scripts, docs, templates) names a project copy .itd/<tool>.py or
     .itd/$var, in any spelling (./.itd, "$ROOT/.itd", .itd\\); only itd_tool.sh's legacy fallback may. The
     opt-in CI hygiene template runs the tool from a pinned release.
  4. /adopt copies contracts but not the .py tools, its CLAUDE.md template is a closed pointer block, and the
     Codex helper itd_adopt.py treats any idea-to-deploy marker (an older one included) as adopted.
  5. skills/_shared/itd_projects_doctor.py reports every drift kind read-only, tells installed hooks (home paths)
     from project hooks (relative, $CLAUDE_PROJECT_DIR, other paths) and prints nothing on a clean text scan.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "skills" / "_shared"
TOOLS = ("itd_hygiene.py", "itd_progress.py", "check_contract_drift.py", "itd_init_validate.py")
passed = failed = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"PASS  {label}")
    else:
        failed += 1
        print(f"FAIL  {label}" + (f" - {detail[-400:]}" if detail else ""))


def sh() -> str:
    return shutil.which("sh") or "sh"


def run(cmd: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


def fake_tool(path: Path, word: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"import sys\nprint('{word}', ' '.join(sys.argv[1:]))\n", encoding="utf-8")


def tool_runner_cases(base: Path) -> None:
    install = base / "install"
    shared = install / "skills" / "_shared"
    shared.mkdir(parents=True)
    for name in ("itd_tool.sh", "itd_py.sh"):
        shutil.copy2(SHARED / name, shared / name)
    home = base / "home"
    home.mkdir()
    project = base / "project"
    fake_tool(project / ".itd" / "itd_progress.py", "STALE")
    env = {k: v for k, v in os.environ.items() if k != "ITD_TEMPLATES_DIR"}
    env["HOME"] = str(home)
    helper = str(shared / "itd_tool.sh")

    r = run([sh(), helper, "itd_progress.py", "--x"], project, env)
    check("nothing installed: the legacy project copy runs with a warning",
          r.returncode == 0 and r.stdout.startswith("STALE --x") and "legacy project copy" in r.stderr,
          r.stdout + r.stderr)

    fake_tool(home / ".claude" / "templates" / "itd" / "itd_progress.py", "HOME")
    r = run([sh(), helper, "itd_progress.py"], project, env)
    check("the Claude installation wins over the project copy",
          r.returncode == 0 and r.stdout.startswith("HOME") and not r.stderr.strip(), r.stdout + r.stderr)

    fake_tool(install / "docs" / "templates" / "itd" / "itd_progress.py", "SOURCE")
    r = run([sh(), helper, "itd_progress.py"], project, env)
    check("the source next to the helper (repository / plugin) wins over ~/.claude",
          r.returncode == 0 and r.stdout.startswith("SOURCE"), r.stdout + r.stderr)

    fake_tool(base / "pinned" / "itd_progress.py", "PINNED")
    r = run([sh(), helper, "itd_progress.py"], project, {**env, "ITD_TEMPLATES_DIR": str(base / "pinned")})
    check("ITD_TEMPLATES_DIR wins over every other location",
          r.returncode == 0 and r.stdout.startswith("PINNED"), r.stdout + r.stderr)

    r = run([sh(), helper, "itd_hygiene.py"], base / "home", env)
    check("a tool that is installed nowhere fails closed (exit 2)",
          r.returncode == 2 and "not installed" in r.stderr, r.stdout + r.stderr)
    r = run([sh(), helper, "../evil.py"], project, env)
    check("an unknown tool name is refused (exit 2)", r.returncode == 2 and "unknown tool" in r.stderr,
          r.stdout + r.stderr)

    real = {**env, "HOME": str(home)}
    r = run([sh(), str(SHARED / "itd_tool.sh"), "check_contract_drift.py", "--selftest"], project, real)
    check("the repository helper runs the real installed checker", r.returncode == 0, r.stdout + r.stderr)


def drift_root_cases(base: Path) -> None:
    project = base / "drift-project"
    (project / ".itd").mkdir(parents=True)
    (project / ".itd" / "SCOPE_LOCK.md").write_text("# Scope\n\n- Replace this line with the task.\n",
                                                   encoding="utf-8")
    checker = ROOT / "docs" / "templates" / "itd" / "check_contract_drift.py"
    env = dict(os.environ)
    r = run([sys.executable, str(checker), "--root", str(project), "--filled"], base, env)
    check("check_contract_drift --root checks the named project, not the tool's location",
          "SCOPE_LOCK.md" in r.stdout and "TMPL" in r.stdout, r.stdout + r.stderr)
    legacy = project / ".itd" / "check_contract_drift.py"
    shutil.copy2(checker, legacy)
    r = run([sys.executable, str(legacy), "--filled"], base, env)
    check("a legacy copy inside .itd/ still checks its own project",
          "SCOPE_LOCK.md" in r.stdout and "TMPL" in r.stdout, r.stdout + r.stderr)


PROJECT_COPY_RE = re.compile(r"\.itd[/\\]+[\"']?(?:" + "|".join(map(re.escape, TOOLS)) + r"|\$\{?[A-Za-z_])")
LEGACY_FALLBACK = Path("skills/_shared/itd_tool.sh")
INSTALL_FIRST_LINES = (
    'T="skills/_shared"; for d in "$HOME/.claude/skills/_shared" "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-/nonexistent}}/skills/_shared"; do [ -f "$d/itd_tool.sh" ] && T="$d"; done',
    '[ "$T" = skills/_shared ] && C=$(ls -d "$HOME"/.codex/plugins/cache/*/idea-to-deploy/*/skills/_shared 2>/dev/null | awk -F/ \'{print $(NF-2), $0}\' | sort -k1,1V | tail -1 | cut -d" " -f2-) && [ -f "${C:-/}/itd_tool.sh" ] && T="$C"',
)
INSTALL_FIRST = "\n".join(INSTALL_FIRST_LINES)  # as written in a fenced block
INSTALL_FIRST_INLINE = "; ".join(INSTALL_FIRST_LINES)  # as written inline (checklist, adopt)
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".gz", ".zip", ".pdf", ".woff", ".woff2"}


def shipped_files() -> list[Path]:
    """Every regular file of the shipped tree, whatever its suffix (extensionless scripts included)."""
    files = [p for d in ("skills", "hooks", "agents", "scripts", "docs", ".claude-plugin", ".codex-plugin")
             for p in (ROOT / d).rglob("*")
             if (p.is_symlink() or p.is_file()) and "__pycache__" not in p.parts]
    files += [ROOT / "README.md", ROOT / "README.ru.md", ROOT / "AGENTS.md"]
    return sorted(set(files))


TOOL_TOKEN_RE = re.compile(r"([^\s\"'`=;|&()]*)itd_tool\.sh")
COMMAND_WORD_RE = re.compile(r"(?:^|[\s;&|(`])(?:sh|bash|dash|zsh|exec|command|source|\.)\s+(?:-[\w-]+\s+)*$")
TOOL_AFTER_RE = re.compile(r"\s+(?:" + "|".join(map(re.escape, TOOLS)) + r")\b")
ASSIGN_BEFORE_RE = re.compile(r"\w+=$")
ASSIGN_RE = {"T": re.compile(r"(?<![\w$])(?:export\s+)?T="), "SHD": re.compile(r"(?<![\w$])(?:export\s+)?SHD=")}
SAFE_FORMS = {"T": (INSTALL_FIRST_INLINE,) + INSTALL_FIRST_LINES, "SHD": ('SHD="$HOME/.claude/skills/_shared"',)}
SAFE_HELPER_PREFIXES = ("$HOME/.claude/skills/_shared/", "${HOME}/.claude/skills/_shared/", "~/.claude/skills/_shared/")


def _resolver_safe(text: str, var: str) -> bool | None:
    """None when the text assigns no var (any quoting, export included); else whether every assignment lies
    inside a safe resolver form."""
    starts = [m.start() for m in ASSIGN_RE[var].finditer(text)]
    if not starts:
        return None
    spans = [(m.start(), m.end()) for safe in SAFE_FORMS[var] for m in re.finditer(re.escape(safe), text)]
    return all(any(a <= pos < b for a, b in spans) for pos in starts)


def _block_resolver_safe(logical: list[tuple[int, str]], position: int, var: str) -> bool:
    """Walk up from the call inside its fenced block or paragraph to the nearest assignment of var: the inline
    form is safe by itself; the two-line form is safe only when its second line follows its first; anything else
    (a lone first line, a later reassignment) is not."""
    for index in range(position - 1, -1, -1):
        prior = logical[index][1]
        if prior.strip().startswith("```") or not prior.strip():
            return False
        safe = _resolver_safe(prior, var)
        if safe is None:
            continue
        if var == "T" and INSTALL_FIRST_INLINE not in prior:
            if prior.strip() != INSTALL_FIRST_LINES[1]:
                return False  # a lone first line never consults the Codex cache; any other assignment is foreign
            return index > 0 and logical[index - 1][1].strip() == INSTALL_FIRST_LINES[0]
        return safe
    return False


def _logical_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Join backslash continuations; each logical line keeps the number of its first physical line."""
    out, i = [], 0
    while i < len(lines):
        number, text = i + 1, lines[i]
        while text.rstrip().endswith("\\") and i + 1 < len(lines):
            i += 1
            text = text.rstrip()[:-1] + " " + lines[i].strip()
        out.append((number, text))
        i += 1
    return out


def _is_invocation(line: str, start: int, end: int) -> bool:
    """A token runs the helper when a shell command word precedes it, a tool name follows it, or a variable is
    assigned from it; a mention in prose (backticks, parentheses) is none of these."""
    before = line[:start].rstrip("\"'")
    after = line[end:].lstrip("\"'")
    return bool(COMMAND_WORD_RE.search(before) or TOOL_AFTER_RE.match(after) or ASSIGN_BEFORE_RE.search(before))


def unsafe_tool_calls(lines: list[str], label: str) -> list[str]:
    """itd_tool.sh invocations whose helper is not taken from the installation first.

    $T/ and $SHD/ paths are bound to the nearest assignment of their variable before the call - on the same line,
    or walking up the same fenced block or paragraph (a fence or a blank line ends the walk); every assignment
    there must belong to the installation-first resolver. An installation path ($HOME/~ .claude) is safe, a
    placeholder (<plugin>, <install>) is documentation, any other path (skills/_shared, ./, a project dir) is
    unsafe.
    """
    unsafe = []
    logical = _logical_lines(lines)
    for position, (number, line) in enumerate(logical):
        for match in TOOL_TOKEN_RE.finditer(line):
            where = match.group(1)
            if where.startswith("<") or not _is_invocation(line, match.start(), match.end()):
                continue
            if where.startswith(SAFE_HELPER_PREFIXES):
                continue
            var = {"$T/": "T", "$SHD/": "SHD"}.get(where)
            safe = None
            if var is not None:
                safe = _resolver_safe(line[:match.start()], var)
                if safe is None:
                    safe = _block_resolver_safe(logical, position, var)
            if not safe:
                unsafe.append(f"{label}:{number}")
    return unsafe


def project_copy_offenders(files: list[Path], root: Path = ROOT) -> tuple[list[str], list[str]]:
    """(offending lines, binary files skipped); a NUL byte marks a binary file."""
    offenders, binary = [], []
    for path in files:
        rel = path.relative_to(root)
        # A symlink ships as its link text: scan that text, never the target.
        data = os.readlink(path).encode("utf-8") if path.is_symlink() else path.read_bytes()
        if b"\0" in data:
            binary.append(str(rel))
            continue
        for number, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
            if rel == LEGACY_FALLBACK and '".itd/$name"' in line:
                continue  # the one permitted reference: the helper's own legacy fallback
            if PROJECT_COPY_RE.search(line):
                offenders.append(f"{rel}:{number}")
    return offenders, binary


def no_project_copy_calls(base: Path) -> None:
    files = shipped_files()
    nested = [ROOT / "docs" / "templates" / "github" / "itd-hygiene.yml", ROOT / "hooks" / "pre-flight-check.sh",
              ROOT / "docs" / "adr" / "ADR-015-installation-owned-methodology.md",
              ROOT / "docs" / "api-reviewer" / "RELEASE_CANDIDATE_CONTRACT.json", ROOT / ".codex-plugin" / "plugin.json"]
    check("the shipped-tree scan covers skills, hooks, scripts, plugin manifests and the whole docs tree",
          len(files) > 300 and all(p in files for p in nested), f"{len(files)} {[str(p) for p in nested if p not in files]}")
    offenders, binary = project_copy_offenders(files)
    check("nothing shipped names a project .itd/<tool>.py copy (only itd_tool.sh's legacy fallback)",
          not offenders, ", ".join(offenders))
    check("the only files the scan skips are binary media and archives",
          all(Path(p).suffix.lower() in BINARY_SUFFIXES for p in binary), ", ".join(binary))
    odd = base / "shipped-probe"
    odd.mkdir()
    (odd / "run-hygiene").write_text("#!/bin/sh\npython3 ./.itd/itd_hygiene.py close\n", encoding="utf-8")
    (odd / "notes.txt").write_text("py -3 .itd\\itd_progress.py\n", encoding="utf-8")
    (odd / "logo.png").write_bytes(b"\x89PNG\0 .itd/itd_hygiene.py")
    try:
        (odd / "tool-link").symlink_to(".itd/itd_progress.py")
        linked = True
    except OSError:  # no symlink privilege (Windows without developer mode)
        linked = False
    fake = odd / "skills" / "_shared" / "itd_tool.sh"
    fake.parent.mkdir(parents=True)
    fake.write_text('if [ -f ".itd/$name" ]; then exec sh itd_py.sh ".itd/$name"; fi\npython3 .itd/itd_hygiene.py\n',
                    encoding="utf-8")
    narrowed, _ = project_copy_offenders([fake], odd)
    check("only the helper's own legacy-fallback lines are exempt, any other .itd/<tool> reference in it is flagged",
          narrowed == ["skills/_shared/itd_tool.sh:2"], str(narrowed))
    probed, skipped = project_copy_offenders(sorted(p for p in odd.iterdir() if p.is_file() or p.is_symlink()), odd)
    expected = ["notes.txt:1", "run-hygiene:2"] + (["tool-link:1"] if linked else [])
    check("the scan reads extensionless, other-suffix and symlink entries and skips only binaries",
          probed == expected and skipped == ["logo.png"], f"{probed} {skipped}")
    probe = base / "probe.md"
    spellings = ['python ./.itd/itd_hygiene.py close', 'python "$ROOT/.itd/itd_hygiene.py"',
                 'py -3 .itd\\check_contract_drift.py', 'sh "$SHD/itd_py.sh" "${P}/.itd/itd_progress.py"',
                 'python3 .itd/$TOOL --x', 'python3 .itd/${tool}', 'python3 .itd/"$tool"', "sh .itd/'itd_progress.py'",
                 'python3 .itd/${prefix}itd_progress.py']
    missed = []
    for line in spellings:
        probe.write_text(line + "\n", encoding="utf-8")
        if not PROJECT_COPY_RE.search(probe.read_text(encoding="utf-8")):
            missed.append(line)
    check("the scan catches relative, rooted, quoted, concatenated, Windows and variable spellings", not missed,
          str(missed))
    workflow = (ROOT / "docs" / "templates" / "github" / "itd-hygiene.yml").read_text(encoding="utf-8")
    check("the CI hygiene template runs the tool from a pinned release clone",
          "ITD_REF: v" in workflow and '--branch "$ITD_REF"' in workflow
          and workflow.count('python3 "$RUNNER_TEMP/itd/docs/templates/itd/itd_hygiene.py"') == 3)
    local_first, scanned = [], 0
    for path in files:
        data = os.readlink(path).encode("utf-8") if path.is_symlink() else path.read_bytes()
        if b"\0" in data:
            continue
        scanned += 1
        local_first += unsafe_tool_calls(data.decode("utf-8", errors="replace").splitlines(),
                                         str(path.relative_to(ROOT)))
    check("every itd_tool.sh invocation in every shipped file takes the helper from the installation first",
          not local_first and scanned > 300, ", ".join(local_first) or f"scanned={scanned}")
    L1, L2 = INSTALL_FIRST_LINES
    probe = ["```bash", L1, L2, 'sh "$T/itd_tool.sh" itd_progress.py', "```", "",                   # 1-5 safe
             "```bash", 'T="skills/_shared"', 'sh "$T/itd_tool.sh" itd_progress.py', "```", "",      # 9 unsafe
             "```bash", 'sh "$T/itd_tool.sh" itd_progress.py', "```",                                # 13 unsafe
             'SHD="skills/_shared"; [ -f "$SHD/itd_py.sh" ] || SHD="$HOME/.claude/skills/_shared"; sh "$SHD/itd_tool.sh" x.py',  # 15
             'sh skills/_shared/itd_tool.sh itd_hygiene.py close',                                   # 16 unsafe
             'bash "$T/itd_tool.sh" itd_progress.py', "",                                            # 17 unsafe
             L1, L2, 'command sh "$T/itd_tool.sh" \\', '  itd_init_validate.py --selftest', "",      # 19-22 safe
             'H="skills/_shared/itd_tool.sh"; sh "$H" itd_progress.py',                             # 24 unsafe
             "the helper `skills/_shared/itd_tool.sh` runs the tools (prose, not a call)",
             "sh ~/.claude/skills/_shared/itd_tool.sh itd_progress.py",                             # 26 safe
             'sh <plugin>/skills/_shared/itd_tool.sh itd_init_validate.py --selftest', "",
             "```bash", L1, 'sh "$T/itd_tool.sh" itd_progress.py', "```", "",                       # 31 unsafe: lone first line
             "```bash", L1, L2, "T='skills/_shared'", 'sh "$T/itd_tool.sh" itd_progress.py', "```", "",  # 38 unsafe: single quotes
             "```bash", L1, L2, "export T=skills/_shared", 'sh "$T/itd_tool.sh" itd_progress.py', "```", "",  # 45 unsafe: export
             "```bash", INSTALL_FIRST_INLINE + '; sh "$T/itd_tool.sh" itd_progress.py', "```"]       # 50 safe (inline)
    check("the call-site check binds each call to the complete resolver, catching lone, quoted and export forms",
          unsafe_tool_calls(probe, "probe") == ["probe:9", "probe:13", "probe:15", "probe:16", "probe:17", "probe:24",
                                                "probe:31", "probe:38", "probe:45"],
          str(unsafe_tool_calls(probe, "probe")))
    uses = [p for p in ("session-save", "handoff", "retro", "review", "task")
            if "itd_tool.sh" not in (ROOT / "skills" / p / "SKILL.md").read_text(encoding="utf-8")]
    check("the skills that run project tools go through itd_tool.sh", not uses, ", ".join(uses))


def adopt_cases() -> None:
    source = (ROOT / "skills" / "adopt" / "scripts" / "itd_adopt.py").read_text(encoding="utf-8")
    check("itd_adopt copies the templates without the .py tools",
          'ignore=shutil.ignore_patterns("*.py"' in source)
    skill = (ROOT / "skills" / "adopt" / "SKILL.md").read_text(encoding="utf-8")
    check("adopt Step 3.5 copies contracts, not the .py tools",
          "not the `.py` tools" in skill and "plus the `.py` utilities" not in skill)
    template = (ROOT / "skills" / "adopt" / "references" / "claude-md-template.md").read_text(encoding="utf-8")
    begin, end = template.find("<!-- idea-to-deploy:begin"), template.find("<!-- idea-to-deploy:end -->")
    block = template[begin:end] if 0 <= begin < end else ""
    check("the adopt CLAUDE.md block is a closed short pointer, not a rules copy",
          block.startswith("<!-- idea-to-deploy:begin v{{VERSION}} -->") and "Hard rule" not in block
          and len(block.splitlines()) <= 20 and "минимальный путь" in block
          and template.count("<!-- idea-to-deploy:end -->") == 1,
          f"begin={begin} end={end} lines={len(block.splitlines())}")
    check("adopt (Claude) treats any idea-to-deploy marker as adopted",
          "any marker `<!-- idea-to-deploy:begin `" in skill)


def adopt_scaffold_cases(base: Path) -> None:
    """The adopt scaffold is RUN against the real template tree: every contract arrives, no .py tool does."""
    spec = importlib.util.spec_from_file_location("itd_adopt_scaffold", ROOT / "skills" / "adopt" / "scripts" / "itd_adopt.py")
    assert spec and spec.loader
    adopt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adopt)
    project = base / "adopt-scaffold"
    project.mkdir()
    args = types.SimpleNamespace(unit_id="U-001", unit_criterion="first unit", allowed_area=["src"],
                                 baseline_command="true", verification_command="true", verification_argv=["true"],
                                 trusted_verifier_path=[], timeout=300)
    result = adopt.scaffold_contracts(project, ROOT, args, "2026-10-15")
    templates = ROOT / "docs" / "templates" / "itd"
    expected = {p.relative_to(templates).as_posix() for p in templates.rglob("*")
                if p.is_file() and p.suffix != ".py" and "__pycache__" not in p.parts}
    copied = {p.relative_to(project / ".itd").as_posix() for p in (project / ".itd").rglob("*") if p.is_file()}
    tools = sorted(p for p in copied if p.endswith(".py"))
    check("itd_adopt scaffold run: every contract template copied, no .py tool, scope filled",
          result != "unchanged" and expected <= copied and not tools and expected
          and "U-001" in (project / ".itd" / "SCOPE_LOCK.md").read_text(encoding="utf-8"),
          f"result={result} missing={sorted(expected - copied)} tools={tools}")
    cold = (ROOT / "tests" / "verify_operational_cold_start.py").read_text(encoding="utf-8")
    check("the cold-start journey asserts the same after a full /adopt --apply run",
          ".itd" in cold and "*.py" in cold and "itd_tool.sh" in cold)


def adopt_marker_cases(base: Path) -> None:
    spec = importlib.util.spec_from_file_location("itd_adopt_probe", ROOT / "skills" / "adopt" / "scripts" / "itd_adopt.py")
    assert spec and spec.loader
    adopt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adopt)
    args = types.SimpleNamespace(unit_id="U-001", allowed_area=["src"], baseline_command="true",
                                 verification_command="true", verification_argv=["true"],
                                 trusted_verifier_path=[])
    results = {}
    for name, head in (("older", "<!-- idea-to-deploy:begin v1.20 -->\nold rules\n<!-- idea-to-deploy:end -->\n"),
                       ("current", (ROOT / "skills" / "adopt" / "references" / "agents-md-template.md")
                        .read_text(encoding="utf-8")),
                       ("none", "# Project notes\n")):
        project = base / f"adopt-{name}"
        project.mkdir()
        (project / "AGENTS.md").write_text(head, encoding="utf-8")
        planned = adopt.plan(project, ROOT, args)["AGENTS.md"]
        written = adopt.guidance_entry(project, ROOT)
        markers = (project / "AGENTS.md").read_text(encoding="utf-8").count("<!-- idea-to-deploy:begin ")
        results[name] = (planned, written, markers)
    check("itd_adopt.py treats an older idea-to-deploy marker as adopted and never stacks a second block",
          results["older"] == ("skip-marker-present", "unchanged", 1)
          and results["current"] == ("skip-marker-present", "unchanged", 1)
          and results["none"] == ("append-guarded-block", "appended", 1), str(results))


def doctor_cases(base: Path) -> None:
    doctor = SHARED / "itd_projects_doctor.py"
    root = base / "projects"
    clean = root / "clean"
    (clean / ".git").mkdir(parents=True)
    (clean / "CLAUDE.md").write_text("<!-- idea-to-deploy:begin v1.108 -->\npointer\n<!-- idea-to-deploy:end -->\n",
                                     encoding="utf-8")
    old = root / "old"
    (old / ".git").mkdir(parents=True)
    (old / "CLAUDE.md").write_text("<!-- idea-to-deploy:begin v1.20 -->\nrules\n<!-- idea-to-deploy:end -->\n",
                                   encoding="utf-8")
    fake_tool(old / ".itd" / "itd_hygiene.py", "STALE")
    (old / ".claude" / "skills" / "deploy").mkdir(parents=True)
    (old / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": '"C:/Python312/python.exe" -X utf8 "C:/Users/u/.claude/hooks/check-skills.sh"'},
        {"type": "command", "command": "/opt/own-guard.sh"}]}]}}), encoding="utf-8")
    home = base / "doctor-home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "itd-disabled-hooks.txt").write_text("check-skills.sh\n", encoding="utf-8")
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}

    def tree(path: Path) -> dict[str, str]:
        out = {}
        for p in sorted(path.rglob("*")):
            rel = str(p.relative_to(path))
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir"
        return out

    before = tree(root)
    r = run([sys.executable, str(doctor), str(root), "--json"], base, env)
    try:
        report = json.loads(r.stdout)
    except ValueError:
        report = {}
    kinds = {f["kind"] for row in report.get("projects", []) for f in row["findings"]}
    projects = {Path(row["project"]).name for row in report.get("projects", [])}
    check("doctor reports every drift kind on the drifted project",
          kinds == {"old-rules-block", "tool-copy", "duplicate-hooks", "project-hooks", "shadow-skill"},
          str(sorted(kinds)))
    check("doctor stays silent on a clean pointer project", projects == {"old"}, str(sorted(projects)))
    dup = [f["fix"] for row in report.get("projects", []) for f in row["findings"] if f["kind"] == "duplicate-hooks"]
    check("doctor names the globally disabled hook a project re-enables",
          bool(dup) and "check-skills.sh" in dup[0], str(dup))
    r_strict = run([sys.executable, str(doctor), str(root), "--strict"], base, env)
    r_clean = run([sys.executable, str(doctor), str(clean), "--strict"], base, env)
    check("doctor --strict: exit 1 with findings, 0 without", r_strict.returncode == 1 and r_clean.returncode == 0,
          f"{r_strict.returncode}/{r_clean.returncode}")
    check("doctor prints nothing on a clean project", r_clean.stdout == "" and r_clean.stderr == "",
          repr(r_clean.stdout + r_clean.stderr))
    check("doctor never writes: every project tree is byte-identical after all runs", tree(root) == before)
    r_json = run([sys.executable, str(doctor), str(clean), "--json"], base, env)
    check("doctor --json prints an empty machine-readable report on a clean scan",
          r_json.returncode == 0 and json.loads(r_json.stdout or "{}") == {"projects": [], "count": 0},
          r_json.stdout + r_json.stderr)
    r_help = run([sys.executable, str(doctor), "--help"], base, env)
    r_bad = run([sys.executable, str(doctor), "--depth", "x"], base, env)
    r_negative = run([sys.executable, str(doctor), str(root), "--depth", "-1"], base, env)
    check("doctor --help exits 0, a usage error (also a negative --depth) 2",
          r_help.returncode == 0 and r_bad.returncode == 2 and r_negative.returncode == 2,
          f"{r_help.returncode}/{r_bad.returncode}/{r_negative.returncode}")


def resolver_cases(base: Path) -> None:
    """The installation-first resolver line, run as written: host plugin root > ~/.claude > newest Codex plugin
    cache > the checkout; a home path with a space still resolves."""
    script = base / "install-first.sh"
    script.write_text(INSTALL_FIRST + "\nprintf '%s\\n' \"$T\"\n", encoding="utf-8")  # the fenced-block form
    project = base / "resolver-project"
    project.mkdir()
    base_env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT")}

    def resolve(home: Path, **extra: str) -> str:
        env = {**base_env, "HOME": str(home), **extra}
        return run([sh(), str(script)], project, env).stdout.strip()

    def install(path: Path) -> Path:
        (path / "skills" / "_shared").mkdir(parents=True, exist_ok=True)
        (path / "skills" / "_shared" / "itd_tool.sh").write_text("", encoding="utf-8")
        return path / "skills" / "_shared"

    home = base / "resolver-home"
    home.mkdir()
    got = {"nothing": resolve(home)}
    cache = home / ".codex" / "plugins" / "cache"
    # Lexical order would pick personal/1.99.0 (and a lone marketplace name would also mislead): the resolver
    # must pick the highest VERSION across marketplaces and digit widths.
    older = [install(cache / "personal" / "idea-to-deploy" / v) for v in ("1.9.0", "1.99.0", "1.107.0", "1.108.0")]
    older.append(install(cache / "openai-curated" / "idea-to-deploy" / "1.10.0"))
    got["codex-lexical-trap"] = resolve(home)
    codex = install(cache / "openai-curated" / "idea-to-deploy" / "1.108.1")
    got["codex-cache"] = resolve(home)
    claude = install(home / ".claude")
    got["codex+claude"] = resolve(home)
    plugin = base / "plugin root"
    got["plugin-root-env"] = resolve(home, CLAUDE_PLUGIN_ROOT=str(plugin))  # unset content: falls through
    install(plugin)
    got["claude-plugin-root"] = resolve(home, CLAUDE_PLUGIN_ROOT=str(plugin))
    got["plugin-root"] = resolve(home, PLUGIN_ROOT=str(plugin))
    spaced = base / "Jane Doe"
    spaced_codex = install(spaced / ".codex" / "plugins" / "cache" / "personal" / "idea-to-deploy" / "1.108.0")
    got["home-with-space"] = resolve(spaced)
    want = {"nothing": "skills/_shared", "codex-lexical-trap": str(older[3]), "codex-cache": str(codex),
            "codex+claude": str(claude),
            "plugin-root-env": str(claude), "claude-plugin-root": str(plugin / "skills" / "_shared"),
            "plugin-root": str(plugin / "skills" / "_shared"), "home-with-space": str(spaced_codex)}
    check("the resolver picks host plugin root > ~/.claude > highest-version Codex cache > checkout (spaces survive)",
          got == want, str({k: v for k, v in got.items() if want[k] != v}))


def preflight_helper_path(base: Path) -> None:
    """The pre-flight hook names the helper of its OWN installation, wherever the project is."""
    install = base / "pf-install"
    (install / "hooks").mkdir(parents=True)
    hook = install / "hooks" / "pre-flight-check.sh"
    shutil.copy2(ROOT / "hooks" / "pre-flight-check.sh", hook)
    project = base / "pf-project"
    (project / ".itd").mkdir(parents=True)
    for name in ("FORBIDDEN_CHANGES.md", "SCOPE_LOCK.md", "VERIFICATION_CONTRACT.json"):
        shutil.copy2(ROOT / "docs" / "templates" / "itd" / name, project / ".itd" / name)
    (project / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    for args in (["git", "init", "-q"], git + ["add", "CLAUDE.md"], git + ["commit", "-qm", "init"]):
        subprocess.run(args, cwd=str(project), capture_output=True, timeout=30)
    env = {**os.environ, "HOME": str(base / "pf-home"), "USERPROFILE": str(base / "pf-home")}
    expected = f'sh "{install.resolve() / "skills" / "_shared" / "itd_tool.sh"}" check_contract_drift.py --root . --filled'
    r = subprocess.run([sys.executable, str(hook)], cwd=str(project), env=env, input="{}", capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60)
    try:
        ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    except (ValueError, KeyError, TypeError):
        ctx = r.stdout
    check("pre-flight names the itd_tool.sh of its own installation, not of the project or ~/.claude",
          expected in ctx and f'sh "{project}' not in ctx and ".claude/skills/_shared/itd_tool.sh" not in ctx,
          ctx[-400:] + r.stderr[-200:])


def contract_dir_cases(base: Path) -> None:
    helper = SHARED / "itd_contract_dir.py"
    manifests = {
        "methodology": '{\n  "name": "idea-to-deploy",\n  "version": "1.108.0"\n}\n',
        "tabs-and-newlines": '{\t"name"\n\t:\n\t"idea-to-deploy"}',
        "nested-only": '{"name": "my-app", "author": {"name": "idea-to-deploy"}}',
        "text-only": '{"name": "my-app", "description": "\\"name\\": \\"idea-to-deploy\\""}',
        "other-case": '{"name": "Idea-To-Deploy"}',
        "malformed": '{"name": "idea-to-deploy"',
        "array": '["idea-to-deploy"]',
    }
    methodology_like = {"methodology", "tabs-and-newlines"}
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT")}
    got = {}
    for name in list(manifests) + ["no-manifest"]:
        for with_contract in (True, False):
            project = base / "contract-dir" / f"{name}-{'with' if with_contract else 'without'}"
            (project / ".claude-plugin").mkdir(parents=True)
            (project / "docs").mkdir()
            if name in manifests:
                (project / ".claude-plugin" / "plugin.json").write_text(manifests[name], encoding="utf-8")
            if with_contract:
                (project / "docs" / "SESSION_EXIT_CONTRACT.json").write_text("{}", encoding="utf-8")
            r = run([sys.executable, str(helper), "SESSION_EXIT_CONTRACT.json"], project, env)
            got[project.name] = r.stdout.strip() if r.returncode == 0 else f"rc={r.returncode}"
    expected = {k: ("docs" if k.rsplit("-", 1)[0] in methodology_like and k.endswith("-with") else ".itd") for k in got}
    check("itd_contract_dir: docs/ only for a parsed top-level name idea-to-deploy AND an existing docs contract",
          got == expected, str({k: v for k, v in got.items() if expected[k] != v}))
    r = run([sys.executable, str(helper), "../SESSION_EXIT_CONTRACT.json"], base / "contract-dir" / "methodology-with", env)
    check("itd_contract_dir refuses a contract name with a path", r.stdout.strip() == ".itd", r.stdout + r.stderr)
    r = run([sys.executable, str(helper), "SESSION_EXIT_CONTRACT.json"], ROOT, env)
    check("the methodology repository itself resolves to docs/", r.stdout.strip() == "docs", r.stdout + r.stderr)

    # The pinned resolver lines of /session-save run as written, from a separate installation, in each fixture.
    skill = (ROOT / "skills" / "session-save" / "SKILL.md").read_text(encoding="utf-8").splitlines()
    contract_line = [l for l in skill if l.startswith('CONTRACT="$(sh "$T/itd_py.sh" "$T/itd_contract_dir.py"')]
    home = base / "contract-home"
    install = home / ".claude" / "skills" / "_shared"
    install.mkdir(parents=True)
    for name in ("itd_py.sh", "itd_tool.sh", "itd_contract_dir.py"):
        shutil.copy2(SHARED / name, install / name)
    script = base / "resolver.sh"
    script.write_text("\n".join([INSTALL_FIRST] + contract_line + ['printf "%s %s\\n" "$T" "$CONTRACT"']) + "\n",
                      encoding="utf-8")
    resolved = {}
    for name in ("methodology-with", "methodology-without", "nested-only-with", "no-manifest-with"):
        r = run([sh(), str(script)], base / "contract-dir" / name, {**env, "HOME": str(home)})
        resolved[name] = r.stdout.strip().replace(str(install), "<install>")
    want = {"methodology-with": "<install> docs/SESSION_EXIT_CONTRACT.json",
            "methodology-without": "<install> .itd/SESSION_EXIT_CONTRACT.json",
            "nested-only-with": "<install> .itd/SESSION_EXIT_CONTRACT.json",
            "no-manifest-with": "<install> .itd/SESSION_EXIT_CONTRACT.json"}
    check("the pinned session-save resolver lines, run from the installation, pick the contract as AC1 states",
          len(contract_line) == 1 and resolved == want, f"lines={len(contract_line)} {resolved}")


def doctor_hook_kinds(base: Path) -> None:
    doctor = SHARED / "itd_projects_doctor.py"
    root = base / "hook-projects"
    home = base / "hook-home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "itd-disabled-hooks.txt").write_text("pre-flight-check.sh\nstop.sh\n", encoding="utf-8")
    local = root / "local"
    (local / ".git").mkdir(parents=True)
    project_commands = [".claude/hooks/custom.sh", "bash ./.claude/hooks/a.sh",
                        '"$CLAUDE_PROJECT_DIR"/.claude/hooks/guard.sh', "${CLAUDE_PROJECT_DIR}/.claude/hooks/g.sh",
                        "/opt/tools/.claude/hooks/b.sh", f"{local}/.claude/hooks/c.sh",
                        "bash -c 'cd /x && .claude/hooks/y.sh'", 'python "/srv/Jane Doe/.claude/hooks/z.sh"',
                        "$HOMELESS/.claude/hooks/x.sh", "~other/.claude/hooks/x.sh", "%USERPROFILE%backup/.claude/hooks/x.sh",
                        "$CLAUDE_PROJECT_DIRX/.claude/hooks/x.sh"]
    installed_commands = ["~/.claude/hooks/check-skills.sh", "$HOME/.claude/hooks/a.sh",
                          'bash "${HOME}/.claude/hooks/b.sh"', '"%USERPROFILE%\\.claude\\hooks\\c.sh"',
                          "/home/u/.claude/hooks/d.sh", "/mnt/c/Users/u/.claude/hooks/e.sh",
                          f'python3 "{home}/.claude/hooks/f.sh"',
                          '"C:\\Users\\Jane Doe\\.claude\\hooks\\pre-flight-check.sh"',
                          'py -3 "C:/Users/Jane Doe/.claude/hooks/g.py" --flag', 'bash -c "cd ~ && ~/.claude/hooks/h.sh"',
                          'bash -c "~/.claude/hooks/stop.sh; echo done"']
    installed = root / "installed"
    (installed / ".git").mkdir(parents=True)
    mixed = root / "mixed"
    (mixed / ".git").mkdir(parents=True)
    mixed_commands = ["~/.claude/hooks/a.sh; .claude/hooks/project.sh",
                      'bash -c "~/.claude/hooks/check-skills.sh; ~/.claude/hooks/stop.sh"']
    for project, commands in ((local, project_commands), (installed, installed_commands), (mixed, mixed_commands)):
        (project / ".claude").mkdir()
        (project / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": c} for c in commands]}]}}), encoding="utf-8")
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    r = run([sys.executable, str(doctor), str(root), "--json"], base, env)
    try:
        report = json.loads(r.stdout)
    except ValueError:
        report = {}
    found = {Path(row["project"]).name: {f["kind"]: f["fix"] for f in row["findings"]}
             for row in report.get("projects", [])}
    check("doctor: relative, $CLAUDE_PROJECT_DIR and non-home hook paths are project hooks, not duplicates",
          set(found.get("local", {})) == {"project-hooks"}, str(found.get("local")))
    check("doctor: ~, $HOME, %USERPROFILE%, absolute and spaced quoted home paths are re-registered installed hooks",
          set(found.get("installed", {})) == {"duplicate-hooks"}
          and found["installed"]["duplicate-hooks"].startswith(f"{len(installed_commands)} of {len(installed_commands)}"),
          str(found.get("installed")))
    mixed_found = found.get("mixed", {})
    check("doctor: a command running installed and project hooks counts on both sides, every installed hook named",
          set(mixed_found) == {"duplicate-hooks", "project-hooks"}
          and mixed_found["duplicate-hooks"].startswith("2 of 2") and "stop.sh" in mixed_found["duplicate-hooks"],
          str(mixed_found))
    fix = found.get("installed", {}).get("duplicate-hooks", "")
    check("doctor names disabled hooks behind a spaced quoted home path and before shell punctuation",
          "(pre-flight-check.sh, stop.sh)" in fix and "stop.sh;" not in fix, fix)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="itd-install-owned-") as td:
        base = Path(td).resolve()
        tool_runner_cases(base)
        drift_root_cases(base)
        doctor_cases(base)
        doctor_hook_kinds(base)
        contract_dir_cases(base)
        preflight_helper_path(base)
        resolver_cases(base)
        no_project_copy_calls(base)
        adopt_marker_cases(base)
        adopt_scaffold_cases(base)
    adopt_cases()
    print(f"{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
