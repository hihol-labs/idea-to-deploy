# Changelog

All notable changes to **idea-to-deploy** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] — 2026-04-08

This release closes the gap between "great methodology on paper" and "actually used by Claude". Triggered by a 2026-04-07 production-incident retrospective where Claude (Opus 4.6) skipped the methodology entirely during a 2-hour ad-hoc hotfix. Root cause: nothing was forcing skill discovery. Fix: enforcement layer + rubric-based quality gates + better discoverability + regression fixtures.

### Added

- **Skill discovery hooks** (`hooks/`):
  - `check-skills.sh` (UserPromptSubmit) — analyzes every user prompt for ~80 Russian and English trigger phrases across 12 categories. Injects a `[SKILL HINT]` system reminder when a skill matches. Silent when no trigger fires.
  - `check-tool-skill.sh` (PreToolUse on Bash/Edit/Write/NotebookEdit) — injects a `[SKILL CHECK]` reminder before any raw tool call, asking Claude to verify a skill doesn't fit.
  - Both hooks written in Python 3 (stdlib only), Unicode-safe (Russian lowercasing works), graceful on bad input, ~50 ms overhead per prompt.
  - `hooks/README.md` — installation, settings.json snippet, pipe-tests, customization guide, case study.
- **Skill Contracts** section in main `README.md` — explicit table of inputs / outputs / side-effects / idempotency for all 11 skills.
- **Call graph** in main `README.md` — which skill can invoke which, max depth, recursion guards.
- **`tests/fixtures/`** — 3 sample project ideas with expected output snapshots for regression testing of `/blueprint` and `/kickstart`. Includes `tests/README.md` with run instructions.
- **`references/` for previously bare skills**:
  - `skills/debug/references/debugging-patterns.md` — language-specific debugging recipes (Python, JS, Go, shell).
  - `skills/test/references/test-frameworks.md` — pytest / vitest / jest / go test conventions and idioms.
  - `skills/refactor/references/refactoring-catalog.md` — Fowler-style catalog of common refactorings with before/after.
- **Sonnet-friendly mode** for `/blueprint` and `/kickstart` — auto-detected when running on Sonnet (or via explicit `--lite` flag). Lite mode generates fewer documents, looser minimum requirements, shorter prompts. Output quality remains usable on Sonnet instead of degrading silently.

### Changed

- **`/review` overhauled — score replaced with binary rubric**. The previous `score >= 7/10` gate was subjective (different model invocations gave different numbers). It is now a deterministic checklist of ~25 binary checks split into Critical / Important / Nice-to-have. The skill passes only when all Critical checks pass; warnings emitted for missed Important/Nice-to-have. Numeric score is still reported as a derived metric, but not used as a gate.
- **`skills/review/references/review-checklist.md`** rewritten as the rubric source of truth.
- **All 11 skill descriptions trimmed and rebalanced**. The previous expansion (added in commit `c8255c2` to fight matcher dilution) was over-corrected — descriptions had 10+ trigger phrases each, which dilutes the embedding match. Now: 3–5 canonical phrases in `description` (kept in TRIGGER format), full trigger list moved to a `## Trigger phrases` section in the body where Claude reads it during execution but the matcher doesn't see it.
- **All 16 frontmatter blocks**: removed nonstandard `effort: medium|high|low` field. It was never parsed by Claude Code and created a false impression of behavioral influence. `license` and `metadata` blocks retained — `license` is informational and `metadata` is acceptable per the SDK schema.
- **Plugin manifest** updated: skill count fixed (10 → 11), description expanded to mention subagents and hooks.

### Fixed

- **`README.md` skill count** — said "10 skills" in plugin manifest while listing 11 in the README skills table. Now consistently 11 + 5 subagents.

### Documentation

- New `Skill Contracts` table in README explicitly documenting each skill's interface.
- New `Call Graph` diagram showing skill invocation chains.
- New `Hooks (Recommended Setup)` section in README pointing to `hooks/README.md`.
- `CHANGELOG.md` (this file) created.

---

## [1.1.0] — 2026-04-07

### Changed

- All 11 skill descriptions and 5 subagent descriptions expanded with comprehensive Russian trigger phrases. Added explicit `TRIGGER when user says "..."` prefixes where missing. Added "ALWAYS use this for X" guidance to discourage ad-hoc fallbacks.

### Reason

Discovered during a real prod-hotfix session that the methodology was being silently skipped because trigger lists were too sparse and lacked common Russian phrasings. This release fixed the descriptions; the next release (1.2.0) added the enforcement hooks that close the loop.

---

## [1.0.0] — initial release

- 11 skills: project (router), kickstart, blueprint, guide, debug, test, refactor, perf, explain, doc, review.
- 5 subagents: architect, code-reviewer, doc-writer, perf-analyzer, test-generator.
- `references/` folders for project, kickstart, blueprint, review, guide.
- Bilingual README (English + Russian).
- Plugin packaging (`.claude-plugin/plugin.json`).
- MIT license.
