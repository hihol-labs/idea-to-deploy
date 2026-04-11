#!/usr/bin/env python3
"""
Meta-review runner — inline implementation of `/review --self` for the
idea-to-deploy methodology repo.

Runs the binary rubric from `skills/review/references/meta-review-checklist.md`
against the current working tree and exits non-zero on BLOCKED status.

This is the persistent version of the inline Python block that v1.4.0-v1.6.0
runs embedded in git-commit commands. Moving it into a real file gives us:

1. A single source of truth for the rubric implementation (instead of
   re-typing it every release).
2. A drop-in entry point for a future CI workflow (`.github/workflows/
   meta-review.yml`), which is the v1.6.0-deferred item #3. If/when that
   need arises (see CHANGELOG [1.6.1] for the detection criteria), the
   workflow's only step is `python3 tests/meta_review.py`.
3. Coverage expansion for M-I7 — the smoke test now exercises every one
   of the 18 skills, not just a representative subset of 10. This closes
   the v1.6.0-deferred item #1.

Usage:
    python3 tests/meta_review.py              # run full rubric, exit non-zero on BLOCKED
    python3 tests/meta_review.py --verbose    # also list Important (warn) failures
    python3 tests/meta_review.py --check-only # exit 0/1, no human-readable output

Exit codes:
    0 — PASSED or PASSED_WITH_WARNINGS
    1 — BLOCKED (at least one Critical failure)
    2 — internal error (rubric file missing, etc.)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# Representative Russian + English trigger phrases per skill, used by the
# M-I7 smoke test. At least one phrase per skill — add more here when new
# skills are added to the methodology.
SMOKE_TRIGGERS: list[tuple[str, str]] = [
    # (phrase, expected skill slug)
    ("новый проект", "project"),
    ("start a project", "project"),
    ("почини баг", "bugfix"),
    ("debug this error", "bugfix"),
    ("напиши тесты", "test"),
    ("add tests", "test"),
    ("отрефактори", "refactor"),
    ("refactor this", "refactor"),
    ("объясни код", "explain"),
    ("explain how this works", "explain"),
    ("сгенери документацию", "doc"),
    ("generate readme", "doc"),
    ("проверь документацию", "review"),
    ("code review", "review"),
    ("тормозит", "perf"),
    ("optimize performance", "perf"),
    ("спланируй проект", "blueprint"),
    ("blueprint architecture", "blueprint"),
    ("сгенерируй гайд", "guide"),
    ("claude code guide", "guide"),
    ("проверь безопасность", "security-audit"),
    ("security audit", "security-audit"),
    ("накати миграцию", "migrate"),
    ("apply migration", "migrate"),
    ("проверь зависимости", "deps-audit"),
    ("dependency audit", "deps-audit"),
    ("подготовь к продакшену", "harden"),
    ("production readiness", "harden"),
    ("сгенерируй terraform", "infra"),
    ("helm chart", "infra"),
    # New in v1.13.2: session-save and task routers get their own smoke rows
    # so every skill with a direct trigger is exercised end-to-end.
    ("сохрани сессию", "session-save"),
    ("save session", "session-save"),
    ("закрой tech debt", "task"),
    ("tech debt cleanup", "task"),
    # /kickstart has no standalone trigger — it is reached via the /project
    # router. The "kickstart" keyword in the project regex routes to
    # /project, not /kickstart directly. Deliberately not in this list.
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def find_repo_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / ".claude-plugin" / "plugin.json").exists():
            return parent
    raise SystemExit("error: not inside an idea-to-deploy repo (no .claude-plugin/plugin.json found)")


def read_frontmatter(path: Path) -> tuple[dict, str]:
    if not path.exists():
        return {}, ""
    text = path.read_text(encoding="utf-8", errors="replace")
    fm: dict[str, str] = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            for line in text[4:end].splitlines():
                if ":" in line and not line.lstrip().startswith("#"):
                    k, _, v = line.partition(":")
                    fm[k.strip()] = v.strip().strip("'\"")
            body = text[end + 5:]
    return fm, body


def load_hook_module(hook_path: Path):
    """check-skills.sh is a .sh file by convention but actually Python —
    load it as a module so the TRIGGERS list is introspectable."""
    tmp = Path("/tmp") / f"_cs_import_{hook_path.stem}.py"
    shutil.copy(hook_path, tmp)
    spec = importlib.util.spec_from_file_location("_cs_import", tmp)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {hook_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# Rubric checks
# --------------------------------------------------------------------------

class Report:
    def __init__(self) -> None:
        self.critical: list[str] = []
        self.important: list[str] = []
        self.nice: list[str] = []

    def crit(self, check: str, msg: str) -> None:
        self.critical.append(f"{check}: {msg}")

    def imp(self, check: str, msg: str) -> None:
        self.important.append(f"{check}: {msg}")

    def info(self, check: str, msg: str) -> None:
        self.nice.append(f"{check}: {msg}")

    @property
    def status(self) -> str:
        if self.critical:
            return "BLOCKED"
        if self.important:
            return "PASSED_WITH_WARNINGS"
        return "PASSED"


def run_rubric(repo: Path) -> Report:
    r = Report()

    plugin_json = repo / ".claude-plugin" / "plugin.json"
    plugin = json.loads(plugin_json.read_text(encoding="utf-8"))
    plugin_ver = plugin["version"]

    skills_dir = repo / "skills"
    skills = sorted([p.name for p in skills_dir.iterdir() if p.is_dir()])

    hook_file = repo / "hooks" / "check-skills.sh"
    hook_text = hook_file.read_text(encoding="utf-8") if hook_file.exists() else ""

    readme_en = (repo / "README.md").read_text(encoding="utf-8")
    readme_ru = (repo / "README.ru.md").read_text(encoding="utf-8")
    changelog = (repo / "CHANGELOG.md").read_text(encoding="utf-8")

    # --- M-C5: version consistency ---
    if f"Version-{plugin_ver}" not in readme_en:
        r.crit("M-C5", f"README.md badge does not match plugin.json version {plugin_ver}")
    if f"Version-{plugin_ver}" not in readme_ru:
        r.crit("M-C5", f"README.ru.md badge does not match plugin.json version {plugin_ver}")

    # --- M-C6: CHANGELOG entry for current version ---
    if f"[{plugin_ver}]" not in changelog:
        r.crit("M-C6", f"CHANGELOG.md has no [{plugin_ver}] entry")

    # --- M-C7: badge counts match reality ---
    skills_badge = re.search(r"Skills-(\d+)-green", readme_en)
    if not skills_badge or int(skills_badge.group(1)) != len(skills):
        actual = skills_badge.group(1) if skills_badge else "?"
        r.crit("M-C7", f"README.md Skills badge is {actual}, actual count is {len(skills)}")

    fixtures_dir = repo / "tests" / "fixtures"

    # --- Per-skill checks (M-C1, M-C2, M-C3, M-C4, M-C8 + M-I1..M-I4) ---
    for skill in skills:
        sd = skills_dir / skill
        fm, body = read_frontmatter(sd / "SKILL.md")

        # M-C1: required frontmatter
        for field in ("name", "description", "license"):
            if field not in fm:
                r.crit("M-C1", f"/{skill} missing frontmatter field '{field}'")

        # M-C2: references folder if referenced
        if "references/" in body:
            refs = sd / "references"
            if not refs.is_dir() or not any(refs.iterdir()):
                r.crit("M-C2", f"/{skill} mentions `references/` but folder is missing or empty")

        # M-C3: trigger in hook (unless disable-model-invocation)
        if fm.get("disable-model-invocation", "").lower() != "true":
            if f"/{skill}" not in hook_text:
                r.crit("M-C3", f"/{skill} has no mention in hooks/check-skills.sh")

        # M-C4: at least one fixture
        found = any(skill in p.name for p in fixtures_dir.iterdir() if p.is_dir())
        if not found:
            for p in fixtures_dir.iterdir():
                if not p.is_dir():
                    continue
                notes = p / "notes.md"
                if notes.exists() and re.search(
                    rf"(^|[^-a-z]){re.escape(skill)}([^-a-z]|$)",
                    notes.read_text(encoding="utf-8", errors="replace"),
                    re.M,
                ):
                    found = True
                    break
        if not found:
            r.crit("M-C4", f"/{skill} has no matching fixture")

        # M-C8: Troubleshooting section
        if "## Troubleshooting" not in body:
            r.crit("M-C8", f"/{skill} missing ## Troubleshooting section")

        # M-I1: Recommended model section
        if "## Recommended model" not in body:
            r.imp("M-I1", f"/{skill} missing ## Recommended model section")

        # M-I2: at least 2 examples
        if body.count("### Example") < 2:
            r.imp("M-I2", f"/{skill} has fewer than 2 examples")

        # M-I3: allowed-tools declared
        if "allowed-tools" not in fm:
            r.imp("M-I3", f"/{skill} missing allowed-tools in frontmatter")

        # M-I4: in README Skill Contracts
        if f"`/{skill}`" not in readme_en:
            r.imp("M-I4", f"/{skill} not in README.md")

    # --- M-I7: hook trigger smoke test (expanded to cover all 16 skills) ---
    try:
        hook_module = load_hook_module(hook_file)
        for phrase, expected in SMOKE_TRIGGERS:
            lp = phrase.lower()
            hits = [hint for pat, hint in hook_module.TRIGGERS if re.search(pat, lp)]
            if not any(expected in h.lower() for h in hits):
                r.imp("M-I7", f"phrase '{phrase}' does not route to /{expected}")
    except Exception as e:
        r.imp("M-I7", f"could not load hook module: {e}")

    # --- M-C12: prose skill/agent count consistency (v1.9.0) ---
    # Scan user-facing documentation prose for hardcoded skill or agent
    # counts that don't match reality. This catches the class of bug that
    # accumulated silently across v1.4.0 → v1.8.1: badges and tables were
    # updated when the count changed, but narrative sentences like
    # "registers 13 skills" or "the existing 13" drifted unnoticed because
    # M-C7 only checks the badge against `ls skills/`.
    #
    # Scope: README.md, README.ru.md, CONTRIBUTING.md, hooks/README.md,
    # docs/**/*.md. Deliberately NOT scanned:
    #   - CHANGELOG.md (historical entries legitimately mention old counts)
    #   - skills/*/SKILL.md (too many false positives from examples)
    #   - skills/review/references/*.md (rubric docs legitimately mention
    #     historical counts for context)
    #
    # Skipped lines:
    #   - Markdown table rows (start with `|`)
    #   - Lines with version markers (`v1.x.y`) or historical phrases
    #     ("at that time", "existed", "era", "initially", "before")
    try:
        actual_skills_n = len([p for p in (repo / "skills").iterdir() if p.is_dir()])
        agents_dir = repo / "agents"
        actual_agents_n = 0
        if agents_dir.is_dir():
            actual_agents_n = len(
                [p for p in agents_dir.iterdir() if p.is_file() and p.suffix == ".md"]
            )

        doc_paths: list[Path] = [
            repo / "README.md",
            repo / "README.ru.md",
            repo / "CONTRIBUTING.md",
            repo / "hooks" / "README.md",
        ]
        docs_dir = repo / "docs"
        if docs_dir.is_dir():
            doc_paths.extend(docs_dir.rglob("*.md"))

        # Pattern A: "N skill(s)", "N скилл(ов)", "N skill directories", etc.
        # `(?<!\S)` requires the number to be preceded by whitespace or start
        # of line — prevents false positives on hyphenated qualifiers like
        # "depth-3 skills" where "3" is part of "depth-3", not a count.
        skill_direct_re = re.compile(
            r"(?<!\S)(\d+)\s+(skills?|skill\s+director\w+|скилл\w*|скилл\w*\s+директор\w+|папк\w*\s+скилл\w+)\b",
            re.IGNORECASE,
        )
        # Pattern B: "existing N" / "существующих N" — only counts when the
        # same line also mentions "skill"/"скилл" (context required).
        skill_ctx_re = re.compile(
            r"\b(?:existing|current|last)\s+(\d+)\b|\bсуществующ\w+\s+(\d+)\b",
            re.IGNORECASE,
        )
        # Pattern C: "N agent(s)", "N субагент(ов)", etc. Same hyphen guard.
        agent_direct_re = re.compile(
            r"(?<!\S)(\d+)\s+(agents?|subagents?|агент\w*|субагент\w*)\b",
            re.IGNORECASE,
        )

        table_line_re = re.compile(r"^\s*\|")
        heading_line_re = re.compile(r"^\s*#")
        historical_re = re.compile(
            r"(v\d+\.\d+|at\s+that\s+time|existed\s+at|era\b|legacy\b|initially\b|"
            r"was\s+enforced|изначально|тогда\s+существов|на\s+момент)",
            re.IGNORECASE,
        )
        line_mentions_skill_re = re.compile(r"skill|скилл", re.IGNORECASE)
        line_mentions_agent_re = re.compile(r"agent|агент|субагент", re.IGNORECASE)

        for doc in doc_paths:
            if not doc.exists():
                continue
            rel = doc.relative_to(repo)
            text = doc.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                if table_line_re.match(line):
                    continue
                if heading_line_re.match(line):
                    # Markdown headings legitimately list category subtotals
                    # like "### Project Creation (3 skills)". M-C12 is for
                    # global-count drift in narrative prose, not for
                    # category counts in headings.
                    continue
                if historical_re.search(line):
                    continue

                line_has_skill_word = bool(line_mentions_skill_re.search(line))
                line_has_agent_word = bool(line_mentions_agent_re.search(line))

                # Pattern A — direct skill count
                for m in skill_direct_re.finditer(line):
                    n = int(m.group(1))
                    if n != actual_skills_n:
                        r.crit(
                            "M-C12",
                            f"{rel}:{lineno}: '{m.group(0)}' but actual skill count is {actual_skills_n}",
                        )

                # Pattern B — contextual "existing N" (requires skill word on the same line)
                if line_has_skill_word:
                    for m in skill_ctx_re.finditer(line):
                        n_str = m.group(1) or m.group(2)
                        if not n_str:
                            continue
                        n = int(n_str)
                        if n != actual_skills_n:
                            r.crit(
                                "M-C12",
                                f"{rel}:{lineno}: '{m.group(0)}' in skill context but actual is {actual_skills_n}",
                            )

                # Pattern C — direct agent count
                for m in agent_direct_re.finditer(line):
                    n = int(m.group(1))
                    if n != actual_agents_n:
                        r.crit(
                            "M-C12",
                            f"{rel}:{lineno}: '{m.group(0)}' but actual agent count is {actual_agents_n}",
                        )
    except Exception as e:
        r.imp("M-C12", f"could not run prose-count check: {e}")

    # --- M-C11: trigger drift verifier (v1.7.0) ---
    # Delegate to tests/verify_triggers.py via subprocess. Each canonical
    # phrase in every SKILL.md `## Trigger phrases` section must match a
    # regex in hooks/check-skills.sh and route to the right skill.
    try:
        verify_script = repo / "tests" / "verify_triggers.py"
        if verify_script.exists():
            result = subprocess.run(
                ["python3", str(verify_script), "--json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            data = json.loads(result.stdout) if result.stdout else {"drift_count": 0, "findings": []}
            for f in data.get("findings", []):
                if f.get("kind") == "no-trigger-section":
                    r.imp("M-C11", f"/{f['skill']}: {f['detail']}")
                else:
                    r.crit("M-C11", f"/{f['skill']}: {f['detail']}")
    except Exception as e:
        r.imp("M-C11", f"could not run verify_triggers.py: {e}")

    # --- M-C15: hook count consistency in README narrative (v1.16.2) ---
    # M-C12 covers skill / agent counts in narrative prose, but NOT hook
    # counts. The v1.16.2 audit found that README.md said "two enforcement
    # scripts" and "All four hooks fire live" when the real count was 5
    # (pre-flight-check.sh was added in v1.5.0 but never propagated to
    # the README hook section). M-C15 closes this hole.
    #
    # Pattern: scan README.md, README.ru.md, hooks/README.md for any
    # narrative mention of "N hooks" / "N hook" / "N скриптов-энфорсеров"
    # / "N enforcement scripts" / "N script" — must match actual count
    # of hooks/*.sh files. Skipped: lines inside markdown tables, lines
    # with version markers (historical mentions are legitimate).
    try:
        actual_hooks_n = 0
        hooks_dir_check = repo / "hooks"
        if hooks_dir_check.is_dir():
            actual_hooks_n = len(list(hooks_dir_check.glob("*.sh")))

        hook_count_doc_paths: list[Path] = [
            repo / "README.md",
            repo / "README.ru.md",
            repo / "hooks" / "README.md",
            repo / "CONTRIBUTING.md",
        ]

        # English number words 1-9
        en_words = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9,
        }
        # Russian number words (root forms) 1-9
        ru_words = {
            "один": 1, "одного": 1, "одно": 1, "одна": 1,
            "два": 2, "двух": 2, "две": 2,
            "три": 3, "трёх": 3, "трех": 3,
            "четыре": 4, "четырёх": 4, "четырех": 4,
            "пять": 5, "пяти": 5,
            "шесть": 6, "шести": 6,
            "семь": 7, "семи": 7,
            "восемь": 8, "восьми": 8,
            "девять": 9, "девяти": 9,
        }

        # Hook context words: must appear on the same line as the count
        hook_ctx = re.compile(
            r"\b(hook|hooks|скрипт|скрипты|скриптов|"
            r"enforcement\s+script|enforcement\s+scripts|"
            r"скрипт-?энфорсер|скрипта-?энфорсер|скриптов-?энфорсер|"
            r"хук|хуки|хука|хуков)\b",
            re.IGNORECASE,
        )
        # Numeric "N hooks" / "N скриптов" / "N hook"
        hook_num_re = re.compile(
            r"(?<!\S)(\d+)\s+(?:hooks?|скрипт\w*|hook\b|хук\w*)",
            re.IGNORECASE,
        )
        # English word + hooks
        hook_en_word_re = re.compile(
            r"\b(one|two|three|four|five|six|seven|eight|nine)\s+"
            r"(?:hooks?|enforcement\s+scripts?|hook\b)",
            re.IGNORECASE,
        )
        # Russian word + хук/скрипт
        hook_ru_word_re = re.compile(
            r"\b(один|одного|одна|одно|два|двух|две|"
            r"три|трёх|трех|четыре|четырёх|четырех|"
            r"пять|пяти|шесть|шести|семь|семи|восемь|восьми|девять|девяти)\s+"
            r"(?:хук\w*|скрипт\w*)",
            re.IGNORECASE,
        )
        # "All N hooks" / "Все N хуков" — covered by hook_num_re

        for doc in hook_count_doc_paths:
            if not doc.exists():
                continue
            rel = doc.relative_to(repo)
            for lineno, line in enumerate(
                doc.read_text(encoding="utf-8", errors="replace").splitlines(),
                1,
            ):
                if line.lstrip().startswith("|"):
                    continue  # markdown table
                if line.lstrip().startswith("#"):
                    continue  # heading
                if re.search(r"v\d+\.\d+", line):
                    continue  # version marker — historical mention
                if not hook_ctx.search(line):
                    continue  # no hook context

                # Pattern A: numeric "N hooks"
                for m in hook_num_re.finditer(line):
                    n = int(m.group(1))
                    if n != actual_hooks_n:
                        r.crit(
                            "M-C15",
                            f"{rel}:{lineno}: '{m.group(0)}' but actual hook count is {actual_hooks_n}",
                        )

                # Pattern B: English number word "four hooks"
                for m in hook_en_word_re.finditer(line):
                    n = en_words.get(m.group(1).lower())
                    if n is not None and n != actual_hooks_n:
                        r.crit(
                            "M-C15",
                            f"{rel}:{lineno}: '{m.group(0)}' (={n}) but actual hook count is {actual_hooks_n}",
                        )

                # Pattern C: Russian number word "четыре хука"
                for m in hook_ru_word_re.finditer(line):
                    n = ru_words.get(m.group(1).lower())
                    if n is not None and n != actual_hooks_n:
                        r.crit(
                            "M-C15",
                            f"{rel}:{lineno}: '{m.group(0)}' (={n}) but actual hook count is {actual_hooks_n}",
                        )
    except Exception as e:
        r.imp("M-C15", f"could not run hook-count check: {e}")

    # --- M-I10: fixture snapshot schema presence + validity (v1.15.0) ---
    # Phase 1 of behavioural automation — every fixture under tests/fixtures/
    # must have an `expected-snapshot.json` file, either `status: active`
    # (fully bootstrapped, validated by `tests/verify_snapshot.py`) or
    # `status: pending` (stub, deferred to a later release). Missing or
    # malformed snapshot = Important finding.
    #
    # See tests/README.md for the Phase 1 workflow. Phase 2 (v1.16.0
    # candidate) will add non-interactive execution via `claude -p`, at
    # which point pending stubs will need to be flipped to active.
    if fixtures_dir.is_dir():
        required_snapshot_fields = {
            "$schema_version",
            "fixture_type",
            "skill_under_test",
            "status",
            "description",
        }
        allowed_statuses = {"active", "pending"}

        for fd in sorted(fixtures_dir.iterdir()):
            if not fd.is_dir():
                continue
            snap_path = fd / "expected-snapshot.json"
            if not snap_path.is_file():
                r.imp(
                    "M-I10",
                    f"tests/fixtures/{fd.name}: missing expected-snapshot.json "
                    f"— Phase 1 snapshot validation requires at least a "
                    f"`status: pending` stub",
                )
                continue
            try:
                snap = json.loads(snap_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                r.crit(
                    "M-I10",
                    f"tests/fixtures/{fd.name}/expected-snapshot.json: "
                    f"invalid JSON ({e})",
                )
                continue
            missing = required_snapshot_fields - set(snap.keys())
            if missing:
                r.imp(
                    "M-I10",
                    f"tests/fixtures/{fd.name}/expected-snapshot.json: "
                    f"missing required fields: {sorted(missing)}",
                )
            status_val = snap.get("status", "")
            if status_val not in allowed_statuses:
                r.imp(
                    "M-I10",
                    f"tests/fixtures/{fd.name}/expected-snapshot.json: "
                    f"status='{status_val}' not in {sorted(allowed_statuses)}",
                )

    # --- M-I9: caller-skill tool superset over delegated subagent (v1.14.1) ---
    # When a skill delegates to a subagent via frontmatter `agent: X`, there
    # are three contract-consistent patterns:
    #
    #   Pattern A: subagent is read-only, skill has Write/Edit
    #     → subagent returns structured text, skill persists it.
    #     Examples: /blueprint → architect, /perf → perf-analyzer.
    #
    #   Pattern B: skill AND subagent both read-only, skill is report_only
    #     → entire chain produces stdout reports, nothing is written.
    #     Example: /review → code-reviewer (audit output to user).
    #     Requires explicit `report_only: true` in skill frontmatter.
    #
    #   Pattern C: subagent has Write/Edit itself
    #     → subagent writes files directly in its forked context.
    #     Currently no such agent exists (all 5 are read-only by design),
    #     but the gate permits this for forward compatibility.
    #
    # Anything outside these three patterns is a bug. Critical findings:
    #   - M-I9a: `agent: X` refers to non-existent agent (typo / rename miss)
    #   - M-I9b: both read-only + missing `report_only: true` → silent write
    #     failures when the skill tries to persist subagent output
    agents_tools: dict[str, str] = {}
    if agents_dir.is_dir():
        for agent_md in sorted(agents_dir.glob("*.md")):
            fm_a, _ = read_frontmatter(agent_md)
            agents_tools[agent_md.stem] = fm_a.get("allowed-tools", "")

    write_tool_re = re.compile(r"\b(?:Write|Edit|MultiEdit)\b")
    for skill in skills:
        sd = skills_dir / skill
        fm, _ = read_frontmatter(sd / "SKILL.md")
        agent_ref = fm.get("agent", "").strip()
        if not agent_ref:
            continue
        # Strip inline comments in frontmatter value (the `#` case)
        agent_ref = agent_ref.split("#", 1)[0].strip().strip('"').strip("'")
        if not agent_ref:
            continue
        if agent_ref not in agents_tools:
            r.crit(
                "M-I9a",
                f"/{skill}: frontmatter `agent: {agent_ref}` points to "
                f"non-existent subagent. Available: {sorted(agents_tools)}",
            )
            continue

        agent_has_write = bool(write_tool_re.search(agents_tools[agent_ref]))
        skill_has_write = bool(write_tool_re.search(fm.get("allowed-tools", "")))

        # Parse report_only flag, stripping inline comments
        report_only_raw = fm.get("report_only", "false")
        report_only_value = report_only_raw.split("#", 1)[0].strip().lower()
        skill_is_report_only = report_only_value == "true"

        if agent_has_write:
            continue  # Pattern C
        if skill_has_write:
            continue  # Pattern A
        if skill_is_report_only:
            continue  # Pattern B
        r.crit(
            "M-I9b",
            f"/{skill}: delegates to read-only subagent `{agent_ref}` "
            f"(allowed-tools: {agents_tools[agent_ref]!r}) but has no Write/Edit itself "
            f"and no `report_only: true` in frontmatter. Either add Write/Edit to "
            f"the skill (if it must persist subagent output) or add "
            f"`report_only: true` to formally declare the skill produces only "
            f"stdout reports.",
        )

    # --- M-I8: subagent contract — read-only agents must declare it (v1.14.0) ---
    # Any `agents/*.md` whose `allowed-tools` frontmatter does NOT include
    # Write/Edit must say so EXPLICITLY in its body — otherwise the model
    # running inside that forked subagent context will try to write files,
    # fail silently (tools unavailable), and the calling skill gets nothing.
    #
    # The fix (added in v1.14.0 for doc-writer and test-generator) is an
    # "Output Format" section that tells the subagent to return text to
    # the caller. This gate makes the pattern mandatory for all future
    # read-only subagents — register a regression test for the clarification.
    #
    # A passing disclaimer contains ALL THREE markers on any line within
    # the body:
    #   1) the phrase "forked" (forked subagent/context)
    #   2) the word "Write" or "Edit" (references the missing tool)
    #   3) a negation marker ("NOT", "not have", "without", "cannot")
    #
    # This is intentionally loose — we want the disclaimer present, not
    # to enforce exact wording.
    agents_dir = repo / "agents"
    if agents_dir.is_dir():
        write_edit_re = re.compile(r"\bWrite\b|\bEdit\b")
        disclaimer_re = re.compile(
            r"forked.*(?:Write|Edit).*(?:NOT|not\s+have|without|cannot)|"
            r"(?:NOT|not\s+have|without|cannot).*(?:Write|Edit).*forked|"
            r"forked\s+subagent\s+context.*(?:NOT|do\s+not|without).*(?:Write|Edit)",
            re.IGNORECASE | re.DOTALL,
        )
        # Simpler check: a single block with all three markers
        def has_disclaimer(body: str) -> bool:
            # Look for a block (paragraph or bold line) that mentions
            # "forked" + "Write" (or Edit) + a negation within 500 chars
            for block in re.split(r"\n\s*\n", body):
                if "forked" in block.lower() and write_edit_re.search(block):
                    if re.search(r"\bNOT\b|not\s+have|without|cannot|do\s+not", block, re.IGNORECASE):
                        return True
            return False

        for agent_md in sorted(agents_dir.glob("*.md")):
            fm, body = read_frontmatter(agent_md)
            tools = fm.get("allowed-tools", "")
            has_write = bool(re.search(r"\bWrite\b", tools))
            has_edit = bool(re.search(r"\bEdit\b", tools))
            if has_write or has_edit:
                # Agent can write files itself — no disclaimer required.
                continue
            if not has_disclaimer(body):
                r.imp(
                    "M-I8",
                    f"agents/{agent_md.name}: read-only subagent (no Write/Edit in allowed-tools) "
                    f"but body has no forked-context disclaimer — silent write failures will result",
                )

    # --- M-C13: marketplace.json consistency with plugin.json (v1.13.2) ---
    # The community plugin catalog (.claude-plugin/marketplace.json) is a
    # separate file from plugin.json and is what external crawlers read. It
    # silently drifted from v1.11.0 → v1.13.1 because nothing enforced parity.
    # This check catches: (1) version mismatch, (2) wrong skill count in any
    # of the description fields.
    marketplace_json = repo / ".claude-plugin" / "marketplace.json"
    if marketplace_json.exists():
        try:
            mp = json.loads(marketplace_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            r.crit("M-C13", f"marketplace.json is not valid JSON: {e}")
            mp = None
        if mp is not None:
            plugins = mp.get("plugins", [])
            if not plugins:
                r.crit("M-C13", "marketplace.json has no plugins array entry")
            else:
                entry = plugins[0]
                mp_version = entry.get("version", "")
                if mp_version != plugin_ver:
                    r.crit(
                        "M-C13",
                        f"marketplace.json plugins[0].version is '{mp_version}', "
                        f"but plugin.json version is '{plugin_ver}'",
                    )
                # Skill count must match in BOTH description fields —
                # marketplace-level and plugin-level.
                skill_count_re = re.compile(r"(\d+)\s+skills?", re.IGNORECASE)
                mp_desc_top = mp.get("description", "")
                mp_desc_plugin = entry.get("description", "")
                for label, desc in (
                    ("marketplace.description", mp_desc_top),
                    ("plugins[0].description", mp_desc_plugin),
                ):
                    m = skill_count_re.search(desc)
                    if m and int(m.group(1)) != len(skills):
                        r.crit(
                            "M-C13",
                            f"marketplace.json {label} claims {m.group(1)} skills, "
                            f"actual count is {len(skills)}",
                        )
    else:
        r.imp("M-C13", ".claude-plugin/marketplace.json not found — plugin catalogs cannot index this plugin")

    # --- M-C14: tests/README.md CI formulation (v1.13.2) ---
    # Before v1.13.2, tests/README.md said "no CI integration yet" despite
    # meta_review.py being wired into GitHub Actions. Contributors reading
    # the file got the wrong impression and may have skipped local runs on
    # the assumption CI had no coverage. Fail fast if the stale phrasing
    # creeps back in.
    tests_readme = repo / "tests" / "README.md"
    if tests_readme.exists():
        tr_text = tests_readme.read_text(encoding="utf-8")
        stale_patterns = [
            r"no\s+CI\s+integration\s+yet",
            r"not\s+CI[- ]friendly",
        ]
        for pat in stale_patterns:
            if re.search(pat, tr_text, re.IGNORECASE):
                r.crit(
                    "M-C14",
                    f"tests/README.md contains stale '{pat}' phrasing — meta_review runs in CI since v1.12.0",
                )

    # --- M-C10: hook schema + exit code compliance ---
    events_spec = {
        "PreToolUse":       {"perm_decision_required": True,  "may_block": True},
        "PostToolUse":      {"perm_decision_required": False, "may_block": False},
        "UserPromptSubmit": {"perm_decision_required": False, "may_block": True},
        "Stop":             {"perm_decision_required": False, "may_block": True},
        "SubagentStop":     {"perm_decision_required": False, "may_block": True},
        "Notification":     {"perm_decision_required": False, "may_block": False},
        "PreCompact":       {"perm_decision_required": False, "may_block": False},
        "SessionStart":     {"perm_decision_required": False, "may_block": False},
    }
    for hook in sorted((repo / "hooks").glob("*.sh")):
        text = hook.read_text(encoding="utf-8")
        events = sorted(set(re.findall(r'"hookEventName"\s*:\s*"([A-Za-z]+)"', text)))
        if len(events) != 1:
            # Some hooks (check-skills.sh) emit one event from a helper — allow inference
            if len(events) == 0 and "UserPromptSubmit" in text:
                events = ["UserPromptSubmit"]
            if len(events) != 1:
                r.crit("M-C10", f"{hook.name}: ambiguous event type ({events})")
                continue
        event = events[0]
        if event not in events_spec:
            r.crit("M-C10", f"{hook.name}: unknown event '{event}'")
            continue
        if event == "PreToolUse":
            if re.search(r'(?<!permission)[\'"]decision[\'"]\s*:', text):
                r.crit("M-C10", f"{hook.name} (PreToolUse): uses root 'decision' instead of hookSpecificOutput.permissionDecision")
        if event == "PostToolUse":
            claims_block = re.search(
                r"prevent.*tool|block.*tool\s+call|stop.*write.*from\s+landing|physically\s+prevent",
                text,
                re.IGNORECASE,
            )
            has_disclaimer = re.search(
                r"non-?blocking|already\s+ran|cannot\s+undo|after\s+the\s+tool",
                text,
                re.IGNORECASE,
            )
            if claims_block and not has_disclaimer:
                r.crit("M-C10", f"{hook.name} (PostToolUse): docstring claims to block, but PostToolUse is non-blocking per spec")
        if event == "UserPromptSubmit":
            if "permissionDecision" in text:
                r.crit("M-C10", f"{hook.name} (UserPromptSubmit): uses permissionDecision, which is PreToolUse schema")

    return r


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Run the idea-to-deploy meta-review rubric")
    parser.add_argument("--verbose", "-v", action="store_true", help="list Important failures too")
    parser.add_argument("--check-only", action="store_true", help="no output, just exit code")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    repo = find_repo_root(here)

    try:
        report = run_rubric(repo)
    except Exception as e:
        print(f"error running rubric: {e}", file=sys.stderr)
        return 2

    if not args.check_only:
        print(f"=== META-REVIEW (idea-to-deploy @ {repo}) ===")
        print(f"Critical ({len(report.critical)}):")
        for e in report.critical:
            print(f"  ❌ {e}")
        if args.verbose or report.important:
            print(f"Important ({len(report.important)}):")
            for e in report.important:
                print(f"  ⚠️  {e}")
        print()
        print(f"FINAL STATUS: {report.status}")

    return 0 if report.status != "BLOCKED" else 1


if __name__ == "__main__":
    sys.exit(main())
