# Changelog

All notable changes to **idea-to-deploy** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.14.0] - 2026-04-11

Polish release closing the three Nice-to-have items from the v1.13.2 qualitative audit, plus a new `M-I8` meta-review gate that makes the subagent contract pattern auditable and regression-proof. All improvements are backward-compatible additions — MINOR bump, no user-facing behaviour changes.

### Audit context

The v1.13.2 PR (#16) fixed 1 Critical + 4 Important drift items but deferred three Nice-to-have items to v1.14.0 because they did not affect correctness, only discoverability and edge-case recall:

1. `plugin.json.keywords` missing the new v1.13.0 capability tags.
2. `agents/doc-writer.md` (and by analogy `test-generator.md`) had an ambiguous "Generate documentation files" instruction without disclosing that the subagent runs in a forked context with no `Write`/`Edit` tools, so the instruction is physically unfulfillable.
3. `hooks/check-skills.sh` `/explain` trigger had thin English coverage — idiomatic phrasings like "what does this function do", "can you explain", "tell me about this module" fell through to ad-hoc tool calls.

v1.14.0 closes all three and adds one bonus item: **M-I8 subagent whitelist gate** which enforces the clarification pattern for all current and future read-only subagents.

### Added

- **`hooks/check-skills.sh`** — extended `/explain` regex with three new idiomatic English patterns:
  - `what\s+does\s+(this\s+|the\s+)?(\w+\s+)?(do|mean|return)` — catches "what does this function do", "what does getUserById return", "what does the auth middleware do"
  - `can\s+you\s+explain` — catches "can you explain this regex", "can you explain what's happening"
  - `tell\s+me\s+(about|how)\s+(this|the|that)\s+(code|function|module|class|file|method|component|handler|endpoint)` — catches "tell me about this handler", "tell me how the auth module works"
- **`.claude-plugin/plugin.json`** — keywords extended with `self-review`, `meta-review`, `methodology-validation`, `daily-work-router`. Aligns the plugin's discoverability metadata with the v1.13.0 self-review capability, the v1.5.0 `/task` router, and the v1.12.0+ meta-review gate. Parallelism with marketplace.json restored.
- **`.claude-plugin/marketplace.json`** — keyword `methodology-validation` added for parity with plugin.json (the other three were already present from v1.13.2).
- **`agents/doc-writer.md`** — new "Output Format" section explicitly states that the agent runs in a forked context without `Write`/`Edit`, and must return structured text for the calling skill to persist. Applies to both invocation paths: through the `/doc` skill and directly via the `Agent` tool.
- **`agents/test-generator.md`** — analogous disclaimer, with the additional clarification that `Bash` is in the whitelist for test-suite detection (`pytest --co`, `npm test -- --listTests`) but NOT for writing files via heredoc or `tee`.
- **`agents/architect.md`** — analogous disclaimer for the `/blueprint` flow; specifies the `{ file_path, content }` tuple return format for multi-file architecture deliverables.
- **`agents/code-reviewer.md`** — analogous disclaimer emphasising the separation of audit (subagent) and remediation (caller) as load-bearing for read-only review semantics. Preserves the existing v1.13.0 Step 0 methodology-mode detection.
- **`agents/perf-analyzer.md`** — analogous disclaimer plus expanded return format per bottleneck (Description / Severity / Location / Measurement / Suggested fix / Expected improvement). Explicitly says `Bash` is for running benchmarks, not for `tee > patched.py`.
- **`tests/meta_review.py` — new Important gate `M-I8`** — scans `agents/*.md` and, for any subagent whose frontmatter `allowed-tools` does not include `Write` or `Edit`, verifies the body contains a forked-context disclaimer (a block with all three markers: "forked", "Write/Edit", negation keyword). Silent-write-failure regressions are no longer possible without the gate flagging them. Intentionally Important (not Critical) because the same class of bug has always been a correctness issue, never a blocker for existing users.

### Changed

- **`.claude-plugin/plugin.json`** — version `1.13.2` → `1.14.0`.
- **`.claude-plugin/marketplace.json`** — `plugins[0].version` `1.13.2` → `1.14.0`.
- **`README.md`** / **`README.ru.md`** — version badges `1.13.2` → `1.14.0`.

### Migration

```bash
git pull
bash scripts/sync-to-active.sh
python3 tests/meta_review.py --verbose
```

No configuration changes required. Active install picks up the new triggers, keyword metadata, and subagent instructions on next Claude restart.

### Why MINOR, not PATCH

v1.13.2 was strictly a drift fix — PATCH per SemVer. v1.14.0 is different: it adds new trigger-phrase coverage (behaviour change, even if backward-compatible), new plugin.json keywords (catalog-visible change), new subagent instructions (changes what subagents can be told to do), and a new meta-review gate (changes what the CI will block). None of these are breaking, but together they move the minor version counter, which is the right SemVer semantics for backward-compatible additions.

### What remains open

- **v1.15.0 candidate — snapshot testing for behavioural fixtures.** Documented in `tests/README.md` as a future path since v1.13.2. Requires a proof-of-concept of non-interactive Claude Code SDK invocation before full rollout, and a CI compute cost estimate. Not in v1.14.0 scope.
- **WSL git-over-network issue.** `git push` and `git fetch` hang in the maintainer's WSL environment; all v1.13.2 and v1.14.0 commits are landed via `gh api graphql createCommitOnBranch`. This is an environment issue, not a methodology issue, but is tracked in memory for continuity.

---

## [1.13.2] - 2026-04-11

Documentation-drift audit release. Closes gaps found during the post-v1.13.1 self-review where a code-reviewer subagent + manual verification surfaced issues that the automated `meta_review.py` gate did not catch:

1. **`.claude-plugin/marketplace.json` had drifted from v1.11.0 → v1.13.1 unnoticed.** The file is what external plugin catalogs index, but nothing enforced parity with `plugin.json`. Both description fields still read "17 skills" when the real count was 18; `plugins[0].version` was frozen at 1.11.0.
2. **`skills/kickstart/SKILL.md` had `disable-model-invocation: true`** — a flag documented for script-backed skills that delegate to a binary, not for reasoning-heavy skills. The same flag on the built-in `/debug` is what forced the v1.4.0 rename to `/bugfix`. `/kickstart` is the most reasoning-heavy skill in the methodology; the flag silently blocked its invocation via the `Skill` tool from `/project`.
3. **`scripts/sync-to-active.sh` numbered its steps "1/3 → 2/3 → 2.5/3 → 3/3"** after v1.13.1 added the fourth step (agents/) without updating the denominators. The dry-run output was visibly inconsistent.
4. **`tests/README.md` still said "no CI integration yet"** even though `meta_review.py` has been wired into GitHub Actions since v1.12.0. Contributors reading the file got the wrong impression.
5. **`hooks/pre-flight-check.sh` had a lossy fallback path reconstruction** that silently degraded (returned `None` instead of finding the memory dir) for projects with `-` in the directory name — including `idea-to-deploy` itself.

### Fixed

- **`.claude-plugin/marketplace.json`** — version `1.11.0` → `1.13.2`; both description fields updated from "17 skills" to "18 skills" and refreshed to mention daily-work routing + self-review mode; keywords expanded with `self-review`, `meta-review`, `daily-work-router`.
- **`skills/kickstart/SKILL.md`** — removed `disable-model-invocation: true` from frontmatter. `/kickstart` can now be invoked through the `Skill` tool by `/project` router without being blocked.
- **`scripts/sync-to-active.sh`** — renumbered all four steps to the honest `1/4, 2/4, 3/4, 4/4` scheme. Added an inline comment recording the history of the "2.5/3" transitional numbering for future maintainers.
- **`tests/README.md`** — rewrote the "Running fixtures" / "Future" sections to clearly distinguish the **automated structural gate** (`meta_review.py` in CI, blocking on every PR) from the **manual behavioural smoke-runs** (fixture outputs that are non-deterministic by model and can only be judged by a human at release time). Added three documented paths to behavioural automation (LLM-as-judge, snapshot diffing, schema-only validation) as candidates for future releases.
- **`hooks/pre-flight-check.sh`** — replaced the lossy `replace("-", "/")` reverse-reconstruction fallback with an iteration over `cwd_resolved.parts` suffixes, so projects with hyphens in directory names (`idea-to-deploy`, `my-app`, etc.) still resolve to their memory dir when the primary path lookup misses.

### Added

- **`tests/meta_review.py` — two new Critical checks** to close the gap that let v1.13.1 ship with a stale marketplace.json:
  - **M-C13** — validates `marketplace.json.plugins[0].version == plugin.json.version` and that every "N skills" mention in either description field matches `len(skills/)`. Fires Critical on mismatch.
  - **M-C14** — scans `tests/README.md` for stale "no CI integration yet" / "not CI-friendly" phrasing that contradicts the actual CI workflow. Fires Critical on match.
- **`tests/meta_review.py` — SMOKE_TRIGGERS expanded** with four new rows covering `/session-save` and `/task` (the v1.10.0 and v1.5.0 skills that were never added to M-I7). Smoke coverage is now 17 skills via direct triggers + `/kickstart` via the `/project` router = all 18 skills exercised.
- **`tests/meta_review.py` — docstring + SMOKE_TRIGGERS comment** updated from "16 skills" to "18 skills" to match reality.

### Changed

- **`.claude-plugin/plugin.json`** — version `1.13.1` → `1.13.2`.
- **`README.md`** / **`README.ru.md`** — version badges `1.13.1` → `1.13.2`.

### Migration

```bash
git pull
bash scripts/sync-to-active.sh
python3 tests/meta_review.py --verbose
```

The sync will pick up the renumbered steps, the kickstart frontmatter change, and the pre-flight hook fix. `meta_review.py` will now flag any future marketplace.json drift as Critical.

### Why a patch-level bump

No new user-facing capability is added — only drift between documentation files and the actual methodology state is corrected, plus two new gates in the automated rubric to prevent the same class of drift from silently re-accumulating. Per SemVer this is a fix (PATCH), not a feature (MINOR). The methodology version counter stays at 1.13.

### What the audit found vs. what shipped

The qualitative self-review produced a punch list of 1 Critical + 4 Important + 3 Nice-to-have. v1.13.2 fixes the Critical and all four Important items plus extends `meta_review.py` with two new gates. The three Nice-to-have items (plugin.json keywords refresh, `doc-writer` allowed-tools clarification, `/explain` English trigger coverage) are deferred to v1.14.0 since they do not affect correctness, only indexing quality and edge-case trigger recall.

---

## [1.13.1] - 2026-04-11

Patch release that finishes what v1.13.0 started. Closes the 9th gap, discovered immediately after merging v1.13.0: the `sync-to-active.sh` script added in v1.12.0 handles `skills/` and `hooks/` but has no `agents/` handling. That means the v1.13.0 fix to `agents/code-reviewer.md` (methodology-mode Step 0 for the forked subagent) landed in the repo but never propagated to `~/.claude/agents/code-reviewer.md`. The `/review --self` mode was effectively inactive: subagent kept using the stale project-level instructions, would still have produced the "Missing PRD.md" nonsense reports.

Detected by `diff -rq agents/ ~/.claude/agents/` after v1.13.0 sync — all 5 agents differed (not just code-reviewer; they had never been sync'd since the script was written).

### Fixed

- **`scripts/sync-to-active.sh`** — added Step 2.5 (agents/) mirroring Step 2 (hooks/) logic. Copies `agents/*.md` to `~/.claude/agents/` with the same `cmp -s` content-based drift detection as the hooks step. No-op when content matches, idempotent on re-runs. Handles both `--check` (dry-run) and normal mode.

### Changed

- **`.claude-plugin/plugin.json`** — version 1.13.0 → 1.13.1.
- **`README.md`** / **`README.ru.md`** — version badges 1.13.0 → 1.13.1.

### Migration

```bash
git pull
bash scripts/sync-to-active.sh
```

This now copies all 5 subagent files into `~/.claude/agents/`. Verify with:

```bash
diff -rq agents/ ~/.claude/agents/   # should be silent (no output)
```

No claude restart needed — subagent definitions are re-read on every invocation.

### Why a patch-level bump

This change adds no new user-facing capability; it restores the effective activation of v1.13.0 which would otherwise remain dormant. Per SemVer this is a bug fix (PATCH), not a feature (MINOR). The methodology version counter stays at 1.13, which is the correct semantic version for "review skill supports self-mode".

---

## [1.13.0] - 2026-04-11

Methodology self-review release. Closes the 8th gap surfaced during v1.12.0 review: `/review` skill had Step 0 methodology-mode detection since v1.5.0 (`--self` flag, `.claude-plugin/plugin.json` sniffing), but the `code-reviewer` subagent to which `/review` forks via `agent: code-reviewer` had its own instructions in `agents/code-reviewer.md` that did NOT mention methodology mode. Running `/review` inside the idea-to-deploy repo produced nonsense BLOCKED reports because the subagent searched for `PRD.md`, `STRATEGIC_PLAN.md`, `IMPLEMENTATION_PLAN.md` (project-level documents that don't exist in a methodology repo).

### Fixed

- **`agents/code-reviewer.md`** — added Step 0 at the top of the subagent instructions, mirroring `skills/review/SKILL.md`. The subagent now detects methodology mode (`--self` flag, methodology-repo sniffing, or changed-files touching methodology surfaces) and delegates to `tests/meta_review.py --verbose` instead of running project-level checks. Explicit list of what NOT to do in methodology mode: no `PRD.md`/`STRATEGIC_PLAN.md` lookups, no user-story scoring, no SOLID/code-smell against infrastructure hooks, no inventing rubric checks (delegate to `tests/meta_review.py` which is the authoritative source).
- **`skills/review/SKILL.md`** — Step 0 rewritten to be unambiguous. Old version said "Jump to Step 3 with the meta-rubric" which was confusing (Step 3 is output formatting, not rubric application). New version says explicitly: run `python3 tests/meta_review.py --verbose`, parse output, present as `/review`-style report. Frontmatter version 1.4.0 → 1.13.0 (jumped to match plugin.json methodology-version track).

### Changed

- **`.claude-plugin/plugin.json`** — version 1.12.0 → 1.13.0, description adds "self-review mode" to the capability list.
- **`README.md`** / **`README.ru.md`** — version badges 1.12.0 → 1.13.0. Skill count unchanged (18).

### Why

During the v1.12.0 review cycle, I invoked `/review` on the feat/v1.5.0-sync-and-hook-fix branch (17 files of methodology changes). The code-reviewer subagent came back with a report looking for project-level docs: "M-C5: C6 & C7 (Critical) — Missing PRD.md", "recommended to create PRD.md from strategic plan". This was obviously wrong — idea-to-deploy is a methodology repo, not a SaaS project. I had to do a manual review instead and the project-level review agent false-negative was flagged as the 8th gap in `session_2026-04-11_2.md`.

Root cause: `skills/review/SKILL.md` already had Step 0 methodology detection, but `agent: code-reviewer` + `context: fork` in the skill frontmatter means `/review` forks to a subagent with its own instructions. The fork does not inherit SKILL.md — the subagent sees only `agents/code-reviewer.md`. That file had no methodology-mode awareness, so the subagent ran its default (project-level) validation.

Fix is symmetric: sync the Step 0 block between `skills/review/SKILL.md` (for when `/review` runs in-context) and `agents/code-reviewer.md` (for when it forks). Both now detect methodology mode and both delegate to `tests/meta_review.py`. The runner script is the single source of truth for the rubric; both entry points just ask it for the report.

### Migration

No user action required if you already ran `bash scripts/sync-to-active.sh` after v1.12.0. For v1.13.0, re-run:

```bash
git pull
bash scripts/sync-to-active.sh
# no claude restart needed — subagent definitions are re-read on every invocation
```

### Verify

```bash
cd /path/to/idea-to-deploy
# Direct runner:
python3 tests/meta_review.py --verbose
# Via /review skill (after claude restart to pick up new SKILL.md):
#   /review --self
# Expected output: "FINAL STATUS: PASSED" (or PASSED_WITH_WARNINGS with specific findings)
```

---

## [1.12.0] - 2026-04-11

Methodology hardening release. Closes six systemic gaps surfaced by the NeuroExpert 2026-04-11 parallel-session incident, where two Claude sessions performed the same kong.yml tech-debt refactor in parallel because nothing in the methodology forced a pre-flight check on recent commits and no router existed for daily-work tasks on existing code.

### Added

- **`/task` skill (new)** — second router skill, parallel to `/project`. Where `/project` routes requests to **create** something (/kickstart, /blueprint, /guide), `/task` routes requests to **modify existing code**: /bugfix, /refactor, /doc, /test, /perf, /security-audit, /deps-audit, /migrate, /harden, /infra, /explain, /review, /session-save. Thin router — never generates code itself, always delegates via the Skill tool. Includes `references/routing-matrix.md` with 13 target skills and an indirect-signal table, plus `tests/fixtures/fixture-10-task/` with 4 routing scenarios. Methodology now has **18 skills** (was 17).
- **`hooks/pre-flight-check.sh` (new)** — `UserPromptSubmit` hook. Injects `git log --oneline -10`, `git status --short`, `MEMORY.md` index, and `.active-session.lock` warnings into the model context on every user prompt. Prevents the NeuroExpert-style parallel-session duplication: if another Claude session touched this project in the last 10 minutes, the model sees a warning and is told to check recent commits BEFORE starting work. No-op silently when `$PWD` is not a git repo.
- **`scripts/sync-to-active.sh` (new)** — idempotent one-command sync from this repo to the user's active install (`~/.claude/skills/`, `~/.claude/hooks/`, `~/.claude/settings.json`). Was the root cause of v1.4.0's 6-skill drift: users were expected to manually copy new skills after each release and rarely did. Now `bash scripts/sync-to-active.sh` (or `--check` for dry-run) brings the active install in line with the repo in one step. Patches `settings.json` hooks block to register all 4 hooks with correct matchers, backing up the old file as `settings.json.bak-<timestamp>`.
- **Active-session lockfile (`.active-session.lock`)** — `/session-save` now writes a JSON lockfile to the project memory dir (`timestamp`, `pid`, `branch`, `project`, `note`). `pre-flight-check.sh` reads it and warns the next Claude session if the lock is fresher than 10 minutes. Stale locks self-expire, no cleanup task needed. Documented in `skills/session-save/references/session-save-checklist.md`.

### Fixed

- **`hooks/check-commit-completeness.sh` fixture detection** — previously matched only fixture directory name (`skill_name in entry.name`), while `check-skill-completeness.sh` also matched `notes.md` content. The two hooks diverged and `check-commit-completeness.sh` would false-positive-block commits touching skills whose fixture was exercised only indirectly (e.g. `/project` tested via `fixture-01-saas-clinic` through `/kickstart`). Unified the detection: both hooks now match directory name OR `/skill-name` token in `notes.md` OR bare-word mention. 7th gap surfaced during v1.5.0 review — fixed in the same release.

### Changed

- **`hooks/check-tool-skill.sh` — rate-limited** (60-second window per session via `/tmp/claude-skill-check-<session>.state`). Old behavior: fired a "STOP, вызови Skill" reminder before every single Bash/Edit/Write tool call, which trained models to respond with a formal "скиллы не матчатся" brush-off before every action and **defeated the purpose of the hook**. New behavior: reminder once per minute max, first call of a session always emits, language softened from "STOP" to "подумай task-level". The hard rule to evaluate skills **task-level once** lives in `~/projects/.claude/CLAUDE.md`; this hook is a periodic nudge, not an enforcement point.
- **`skills/project/SKILL.md` — v1.4.0** — added Step 2 (detect existing-project signals and redirect to `/task`) so `/project` stops catching daily-work requests. Renamed old Steps 2/3/4 → 3/4/5. Frontmatter description clarifies "creation router" and points at `/task` for existing code. Version field bumped 1.3.1 → 1.4.0.
- **`skills/session-save/SKILL.md` — v1.5.0** — added Step 4.5 (write active-session lockfile) with Bash and Python examples. Strengthened auto-trigger list: now includes "after any `git commit` in a branch heading for PR", "after `/review` that passed 9+/10", and "every 5 significant actions without a save". Frontmatter version 1.0.0 → 1.5.0.
- **`hooks/check-skills.sh`** — added trigger patterns for `/task` (закрой tech debt / поправь в проекте / existing project / tech debt cleanup / maintenance task / ...). Patterns intentionally match **ambiguous** phrasings only; direct phrasings ("почини баг в X", "отрефактори Y") still fire the specific daily-work skill hints (/bugfix, /refactor) as before.
- **`.claude-plugin/plugin.json`** — version 1.11.0 → 1.12.0, description updated to "18 skills", added "daily-work routing" to the capability list.
- **`README.md`** / **`README.ru.md`** — skill count 17 → 18 everywhere.

### Why

NeuroExpert 2026-04-11: two Claude Code sessions independently picked up the "close kong.yml tech debt in `scripts/deploy.sh`" task and ran the exact same extract-method refactor in parallel. The second session didn't discover this until after all edits were written; `git status` came back clean because the first session had already committed. Root cause analysis surfaced six systemic gaps — all closed by this release:

1. No pre-flight check of `git log` / `git status` / MEMORY.md before starting work → added via `pre-flight-check.sh`.
2. `/session-save` skill wasn't installed in the active install (listed in repo, missing from `~/.claude/skills/`) because there was no sync mechanism → added via `sync-to-active.sh` (which also brings in `deps-audit`, `harden`, `infra`, `migrate`, `security-audit`, `session-save` — six skills that had drifted out).
3. `check-tool-skill.sh` fired on every tool call, training the model to respond with formal "скиллы не матчатся" before each action → rate-limited + softer language.
4. `/project` routed only **creation** requests; there was no entry point for "work on existing code", so the hard rule "при любом сомнении — /project" created a mental dead-end for tech-debt tasks → added `/task`.
5. No parallel-session awareness → added `.active-session.lock` mechanism + `pre-flight-check.sh` reading it.
6. `~/projects/.claude/CLAUDE.md` hard rule didn't explicitly cover tech-debt / refactor / existing-code cases with a mapping to `/task` → updated in the same day.

### Migration

- **Required:** run `bash scripts/sync-to-active.sh` once after `git pull`. This copies `/task` + 5 previously-missing skills + 2 previously-missing hooks into `~/.claude/`, and patches `settings.json` to register `pre-flight-check.sh` and the completeness hooks. Backup of the previous `settings.json` lands at `~/.claude/settings.json.bak-<timestamp>`.
- **Restart `claude`** after the sync — skill registry is loaded at session start and does not hot-reload.
- **Existing `/debug` references:** already handled in v1.4.0 migration — no action needed here.
- **Hard-rule update:** the `~/projects/.claude/CLAUDE.md` hard rule now mentions `/task`. If you maintain your own copy, update it to route existing-code work through `/task` instead of `/project`.

---

## [1.4.0] - 2026-04-11

### Changed

- **BREAKING (silent):** renamed `/debug` skill to `/bugfix` to avoid name collision with Claude Code's built-in `/debug` slash command. The built-in has `disableModelInvocation: true` baked into the binary, which blocked model-initiated invocation via the Skill tool and broke the "on error → /bugfix" automation rule. Users can still type `/debug` manually, but model auto-invocation never worked for the old name. Skill body, trigger phrases, and methodology are unchanged.
- All cross-references in README.md, README.ru.md, CHANGELOG, CONTRIBUTING, skills/*/SKILL.md, skills/*/references/, hooks/check-skills.sh, hooks/check-tool-skill.sh, hooks/README.md, docs/CONTENT-PLAN.md, .github/ISSUE_TEMPLATE/, tests/fixtures/ updated to `/bugfix`.
- Root cause investigation: `strings $(readlink -f $(which claude)) | grep 'disableModelInvocation:!0'` shows exactly two built-in skills with this flag: `batch` and `debug`. All other Idea-to-Deploy skill names (`/test`, `/refactor`, `/review`, …) remain unaffected.

### Migration

- Users upgrading from <1.4.0: run `rm -rf ~/.claude/skills/debug && cp -r skills/bugfix ~/.claude/skills/bugfix` after git pull. Update any personal hooks/scripts that reference `/debug` to `/bugfix`. Project-specific CLAUDE.md files may need similar updates.

---

## [1.11.0] — 2026-04-09

Marketplace readiness release. Fixes skill description budget overflow (6 of 17 skills were silently dropped by Claude Code Skill tool), adds missing plugin manifest fields for Anthropic Directory submission, and adds recommended agent configuration fields.

### Fixed

- **Skill descriptions shortened** (360-470 → 116-155 chars) — all 17 skills now fit within Claude Code's default 16K character budget for skill metadata. Previously `deps-audit`, `harden`, `infra`, `migrate`, `security-audit`, and `session-save` were not registered in the Skill tool.

### Changed

- **`plugin.json`** — added `homepage`, `keywords` (10 discovery tags), `author.email`, `author.url`. Version 1.10.0 → 1.11.0. Description trimmed (removed internal details).
- **All 5 agents** — added `effort` and `maxTurns` frontmatter fields per Anthropic plugin reference.
- **`README.md`** / **`README.ru.md`** — version badge updated to 1.11.0.

---

## [1.10.0] — 2026-04-09

Minor release. Adds **`/session-save`** — a new skill that saves session context (what was done, key decisions, blockers, next steps) to the project's memory directory. Ensures continuity between Claude Code sessions: the next session reads the saved context and picks up where the previous one left off.

Also adds a hard rule to CLAUDE.md mandating session context saving at the end of every work session.

### Added

- **`/session-save` skill** (`skills/session-save/SKILL.md`): 5-step workflow — gather git/conversation context, summarize using 9-field checklist, write `session_YYYY-MM-DD.md` to memory directory, update MEMORY.md index, confirm to user.
- **`references/session-save-checklist.md`**: required fields and quality criteria for session memory files (date, project, branch, summary, decisions, changed files, blockers, next steps, non-obvious context).
- **Trigger phrases** in `hooks/check-skills.sh`: Russian + English patterns for session save (сохрани контекст, итоги сессии, save session, end of session, etc.).
- **Regression fixture** `tests/fixtures/fixture-09-session-save/` with idea.md, notes.md, expected-files.txt.

### Changed

- **`plugin.json`** version 1.9.0 → 1.10.0, description updated (16 → 17 skills).
- **`hooks/check-tool-skill.sh`** — added `/session-save` to the skill reminder list.
- **`README.md`** — badges (Skills-17, Version-1.10.0), new "Session Management" section, contracts row, call graph entry, recommended models row, contributing count.
- **`README.ru.md`** — mirror of all README.md changes in Russian.
- **`CLAUDE.md`** (user project-level) — new hard rule "Сохранение контекста сессии" + `/session-save` added to automatic skills section.

### Why this is a minor release

New skill (`/session-save`) = new functionality = minor version bump per SemVer.

---

## [1.9.0] — 2026-04-08

Minor release. Adds **M-C12** to the meta-review rubric: structural detection of stale skill-count and agent-count numbers in user-facing documentation prose. Closes the drift class that accumulated silently across v1.4.0 → v1.8.1. The initial M-C12 run caught the last 2 `existing 13` references in Contributing sections that had escaped the v1.8.1 spot-fix.

### Added

- **M-C12 (Critical)** in `skills/review/references/meta-review-checklist.md`: "Skill and agent counts in user-facing prose must match reality." Full binary criterion with scanned/not-scanned file scope, skipped-line rules (tables, headings, historical contexts), pattern definitions (direct count, contextual `existing N`, agent count), and action-on-fail guidance.

- **M-C12 implementation** in `tests/meta_review.py`. Scans `README.md`, `README.ru.md`, `CONTRIBUTING.md`, `hooks/README.md`, `docs/**/*.md`. Deliberately skips `CHANGELOG.md` (historical), `skills/*/SKILL.md` (too many false positives from example counts), and `skills/review/references/*.md` (rubric docs legitimately reference historical counts). Uses three regex patterns with hyphen-guards and heading-skip to suppress false positives.

- **Meta-review Critical tier** grew from 11 to 12 checks.

### Fixed (caught by the initial M-C12 run)

- **`README.md:494`** — `the existing 13` → `the existing 16`. In the Contributing section, explaining that new skills should follow the shape of existing ones. Count was left at 13 since v1.3.x.
- **`README.ru.md:494`** — same fix, Russian version (`существующих 13` → `существующих 16`).

These two had survived the v1.8.1 cleanup because the author's ad-hoc `grep "13\s+skill"` pattern did not match `existing 13` (word "skill" appeared earlier in the sentence, not after the number). M-C12's Pattern B (`existing N` in skill context) generalizes the check to cover this form.

### Calibration findings during development

Before merging M-C12 into the rubric, its initial runs revealed two classes of false positives that were fixed as part of the same release — **before** the check was merged, so the rubric enters the main branch passing cleanly:

1. **12 false positives on Markdown headings** — e.g., `### Project Creation (3 skills)`, `### Daily Work (6 skills)`, `### Operations (4 skills)`. These are legitimate category subtotals in section headings, not global-count claims in prose. Fix: skip all lines starting with `#`.
2. **2 false positives on hyphenated qualifiers** — `depth-3 skills` in the Call Graph prose. Regex `\b\d+\s+skills?` matched because `\b` fires between `-` and `3`. Fix: prepend `(?<!\S)` lookbehind so only whitespace-preceded numbers count.

Both fixes are documented inline in `tests/meta_review.py`.

### Changed

- **`plugin.json`** version 1.8.1 → 1.9.0.
- **Both README badges** bumped.

### Why this is a minor release

M-C12 is a new rubric feature adding a new Critical check. Per the SemVer rules established in `CONTRIBUTING.md`, new rubric checks are minor-version bumps. The 2 prose fixes are cleanup enabled by the new feature, not the feature itself.

### Verified before release

- `python3 tests/meta_review.py --verbose` — PASSED (0 Critical, 0 Important) with M-C12 now active
- `python3 tests/verify_triggers.py` — 0 drift
- Initial M-C12 run (pre-calibration) flagged 14 findings; 12 were resolved by the heading/hyphen fixes, 2 were real drift and resolved by the Contributing fixes.
- Branch protection on `main` rejected direct push (first-class test of the v1.8.0 setup); release went through a proper PR.

### Meta — the rubric is learning faster

The v1.4→v1.9 sequence shows the meta-rubric catching its predecessor's blind spot in each release:

```
v1.4 Potemkin skills             →  v1.5 spec-noncompliant hooks
v1.5 Potemkin enforcement        →  v1.6 static hook-schema check (M-C10)
v1.6 drift in trigger phrases    →  v1.7 trigger drift verifier (M-C11)
v1.7 no public-repo polish       →  v1.8 CI + CONTRIBUTING + CI badge
v1.8 drift in prose counts       →  v1.9 prose count verifier (M-C12)
```

At each step, the lesson comes from how the previous release actually failed, not from top-down design. The rubric now has 12 Critical + 8 Important + 4 Nice-to-have checks covering structural, behavioral, and narrative consistency — a defense surface that is harder to slip past than any single-person review could be.

---

## [1.8.1] — 2026-04-08

Patch release. Documentation consistency fix. Three stale "13 skills" references in the README body survived the v1.4.0 → v1.5.0 → v1.6.0 → v1.7.0 → v1.8.0 sequence because the badge count was updated but the in-body prose was missed. All badges and tables were already correct at 16; only narrative sentences drifted.

### Fixed

- **`README.md:15`** — `"Installing it registers 13 skills and 5 subagents"` → `"16 skills and 5 subagents"`. Appeared right below the badges, which was especially embarrassing because the adjacent badge already said `Skills: 16`.
- **`README.md:64`** — installation path comment `"# 13 skill directories"` → `"# 16 skill directories"`.
- **`README.ru.md:15`** — same as README.md:15, Russian version.
- **`README.ru.md:64`** — same as README.md:64, Russian version.
- **`skills/review/references/meta-review-checklist.md:37`** — M-C8 criterion said `"enforced in v1.3.1 for the existing 13 skills"`. Expanded to `"enforced in v1.3.1 for the 13 skills that existed at that time, extended to all 16 skills in v1.4.0+"` — preserves the historical fact but clarifies the current state.

### Not touched

`CHANGELOG.md` still contains "13 skills" references in the `[1.3.1]`, `[1.3.0]`, and `[1.4.0]` entries. Those are historical records — the changelog describes what was true *at that release*, not what is true now. Rewriting history in the changelog would be worse than the original bug.

### How this was caught

The user asked directly: "find all stale `13 skills` mentions in the README and fix them." The meta-review rubric didn't catch this because M-C7 only checks that the README's `Skills: N` badge matches `ls skills/ | wc -l` — it doesn't grep the prose. This is a gap in M-C7.

### Follow-up for a future minor release

Add **M-C12** to the meta-review rubric: "No hardcoded skill-count or agent-count numbers in any README prose outside the Skill Contracts and Recommended Models tables". Implementation: grep every `README*.md` for patterns like `\b\d+\s+(skills?|skill directories?)\b` and cross-check against the actual count from `ls skills/`. Would have caught this class of drift automatically. Deferred to v1.9.0 or later — the immediate fix is priority, the rubric expansion is follow-up.

### Verified before release

- `python3 tests/meta_review.py --verbose` — PASSED (0 Critical, 0 Important)
- `python3 tests/verify_triggers.py` — 0 drift
- Manual grep for `13\s+(skill|скилл)` outside CHANGELOG — no matches

---

## [1.8.0] — 2026-04-08

Minor release. Closes the last deferred item from v1.6.0 (#3 — CI workflow) and adds the missing public-repo infrastructure (CONTRIBUTING, ISSUE_TEMPLATE) that should have existed from day one of the public repo but was postponed as "solo project overhead not justified". The trigger for flipping that decision: **3 GitHub stars within 24 hours of publishing the repo**. That's a traction signal that makes "wait for first PR" the wrong posture — first PRs follow star accumulation by days, not months, and CI is far cheaper to have before the first PR than to retrofit after.

### Added

- **`.github/workflows/meta-review.yml`** — server-side Gate 1 as a GitHub Actions workflow. Runs on every push to `main` and every pull request. Executes `python3 tests/meta_review.py --verbose` followed by `python3 tests/verify_triggers.py`. Fails the job on any non-zero exit. Uses Python 3.11 stdlib only — no `pip install` step — because both scripts are intentionally zero-dependency. Typical runtime: 20–40 seconds. Timeout: 5 minutes. Permissions: `contents: read` (no write access to the repo from the workflow).

- **`CONTRIBUTING.md`** — explicit ground rules for contributors:
  1. The `SKILL.md` body is the canonical source of truth for triggers; drift from `hooks/check-skills.sh` fails M-C11.
  2. Every new skill must ship with its references, trigger phrases, and fixture in the same PR (enforced by `check-skill-completeness.sh` + `check-commit-completeness.sh` locally and M-C2 / M-C3 / M-C4 on CI).
  3. `python3 tests/meta_review.py --verbose` must print `FINAL STATUS: PASSED` before opening a PR.
  4. SemVer rules for what counts as patch / minor / major bumps.
  Plus a PR checklist and instructions for reporting bugs and proposing new skills.

- **`.github/ISSUE_TEMPLATE/bug_report.md`** — structured bug report template with environment (Claude Code version, plugin version, model in use, OS, installation method), reproduction steps, expected vs observed behavior, logs, and a "did you run the meta-review?" section that catches the most common bug report mistakes before they reach the maintainer.

- **`.github/ISSUE_TEMPLATE/feature_request.md`** — new skill / rubric check proposal template with slots for one-line summary, trigger phrases (Ru + En), read/write contract, recommended model, proposed Skill Contracts row, and explicit "why not covered by existing skill" justification. Designed to force the same discipline on proposals that the methodology enforces on existing skills.

- **`docs/CI.md`** — comprehensive CI documentation:
  - What the workflow does and why
  - The four-layer defense-in-depth table (layers 1–4, from UserPromptSubmit reminder to CI)
  - **Step-by-step branch protection setup instructions** — cannot be provisioned from code, only via the GitHub UI. Documents every click required to make the `meta-review` check required on main, plus the "Do not allow bypassing" setting that prevents silent admin overrides.
  - Emergency override procedures (admin override, temporary protection removal) — both leave audit trails by design.
  - How to reproduce CI locally (run the exact same commands).
  - Troubleshooting section covering common failure modes (CI passes locally but fails on GitHub, check doesn't appear in branch protection, CI too slow).

- **CI status badge** in both `README.md` and `README.ru.md` — visible quality signal for visitors, links to the Actions history.

- **"Defense-in-depth overview" section** in `hooks/README.md` — adds the 4-layer table at the top, making the relationship between local hooks (layers 1–3) and CI (layer 4) explicit.

### Changed

- **`plugin.json`** version 1.7.0 → 1.8.0.
- **Both README badges** bumped; top-of-file links now include `Contributing` → `CONTRIBUTING.md` (was an in-page anchor) and `CI` → `docs/CI.md`.
- **`hooks/README.md`** — expanded with the defense-in-depth overview referencing the new CI layer.

### Philosophy — the day-one public repo lesson

v1.8.0 is the first release shaped by external feedback (star count) rather than internal retrospective. Three observations from 24 hours of being public:

1. **Distribution rate ≠ contribution rate, but they correlate tightly.** 3 stars/day is early-traction territory. First PRs typically follow within 1–2 weeks.
2. **CI is a social signal, not just enforcement.** A green "meta-review passed" badge on every commit tells potential contributors "this is maintained seriously, your PR will be held to a standard". It's a magnet for quality contributions and a filter against drive-by noise.
3. **Cost dropped after v1.6.1.** `tests/meta_review.py` already existed as a persistent, stdlib-only file. Adding CI was 20 minutes: a 15-line YAML workflow + the existing command. The hard work had been done two releases ago without me realizing it was CI prep.

The lesson: when building infrastructure for future defense, **the act of extracting inline logic into a persistent file often makes the next defense layer nearly free**. v1.6.1 said "we might want CI eventually, so extract the runner now". v1.8.0 said "CI time is now, and it's 20 minutes because v1.6.1 already did the preparation". This is the inverse of the v1.4.0 Potemkin pattern — instead of declaring a defense that doesn't exist, v1.6.1 quietly built a foundation that made the real defense cheap to add when the time came.

### Non-reversible setup required after merge

One thing this release **cannot** do from code: enable branch protection on `main` so the CI check becomes blocking. That is a GitHub UI operation. See `docs/CI.md` for the exact steps. Until branch protection is enabled, CI will run and report status but PRs can be merged even if it fails. **This is intentional — the author should review the first CI run output before making it blocking.**

### Verified before release

- `python3 tests/meta_review.py --verbose` — PASSED (0 Critical, 0 Important) on the v1.8.0 staged state
- `python3 tests/verify_triggers.py` — 0 drift
- Commit-gate hook validated the release diff — no SKILL.md file changes, no new skills, so the per-skill completeness check is a no-op; the hook ran cleanly.
- The workflow YAML syntax was verified by hand against the GitHub Actions schema; the first real execution will happen on the v1.8.0 push itself.

### Not done (deferred by design)

- **Automatic branch protection provisioning** — Terraform / GitHub Apps could technically create it via API, but requires additional permissions and is out of scope for a methodology plugin. Manual UI setup is documented in `docs/CI.md`.
- **CI matrix (multi-Python-version)** — meta_review.py only needs 3.11, and multi-version doesn't add value for a plugin that runs on the maintainer's machine, not in a library's user environment. Single-version is correct.
- **CI on forks** — GitHub Actions on PRs from forks run with read-only tokens by default, which is what this workflow needs. No further config required.

---

## [1.7.0] — 2026-04-08

Minor release. Closes v1.6.0 deferred item #2: **structural drift detection between SKILL.md bodies and `hooks/check-skills.sh` regex**. Adds `tests/verify_triggers.py` and a new rubric check M-C11. The initial run against the v1.6.1 state caught **111 pre-existing drift findings** that had accumulated silently across v1.2.0–v1.6.1 — all fixed as part of this release before M-C11 was merged into the rubric.

### Added

- **`tests/verify_triggers.py`** — canonical-phrase drift verifier. For each `skills/<name>/SKILL.md` (except `disable-model-invocation: true` skills), it:
  1. Extracts the `## Trigger phrases` section
  2. Parses bullet lines, splits on commas, skips meta-descriptions (lines starting with `любой`, `любая`, `автоматически`, etc.) and multi-word descriptions (> 6 words)
  3. For each canonical phrase, loads `hooks/check-skills.sh` as a Python module (TRIGGERS list), runs every regex against the phrase, and verifies:
     - At least one regex matches the phrase
     - The matched hint text mentions `/<skill-name>`
  4. Emits drift findings as `unmatched` / `wrong-route` / `no-trigger-section`
  5. Supports `--json` for machine-readable output, used by `tests/meta_review.py`

- **M-C11 (Critical)** in `skills/review/references/meta-review-checklist.md`: "Every canonical trigger phrase in a SKILL.md body routes to the right skill via hooks/check-skills.sh." The meta-review runs `verify_triggers.py` as a subprocess and promotes drift findings to Critical failures (unmatched / wrong-route) or Important warnings (missing trigger section).

- **Meta-review Critical tier** grew from 10 to 11.

### Fixed (111 drift findings, caught by the initial M-C11 run)

The SKILL.md `## Trigger phrases` sections had accumulated phrases over 5 minor releases without the hook regex being updated to match. The initial run flagged 111 findings across 14 skills. Breakdown after filtering meta-descriptions (which shouldn't be in the trigger list at all), fix distribution:

- **18 findings filtered as meta-descriptions** — the verifier's `NOISE_PREFIX_RE` / `NOISE_ANY_RE` / `MAX_PHRASE_WORDS` rules skip phrases that are conditions or documentation rather than literal user input (`"любой запрос на создание законченного работающего продукта"`, `"автоматически перед любым DDL"`, `"multi-file/multi-module exploration"`, etc.). These are legitimate documentation inside the trigger section but shouldn't be part of the regex matching contract.

- **93 findings fixed by expanding hook regex**, distributed across all 14 affected skills. Highlights:
  - `/blueprint`: `создай документацию для проекта`, `техническое задание`, `PRD`, `design the system`, `system design`
  - `/debug`: `traceback`, `странное поведение`, `fix this bug`, `troubleshoot`, `log fragment`, `panic`
  - `/deps-audit`: `package-lock.json audit`, `requirements.txt audit`, `vulnerability scan dependencies`
  - `/doc`: `обнови README`, `опиши API`, `добавь комментарии`, `(инлайн|inline) комментарии`, `JSDoc`, `docstrings`, `changelog(\.md)?`
  - `/explain`: `как это работает`, `как устроен`, `что здесь происходит`, `разбери (код|этот|файл|модуль)`, `walkthrough`
  - `/guide`: `создай гайд`, `сделай cookbook промптов`, `промпты для Claude`, `guide for project`, `cookbook`, `prompt sequence`
  - `/harden`: `secrets management`, `vault`, `doppler` (added to the /harden regex, removed overlap with /infra)
  - `/migrate`: `schema change`, `dbmate up`
  - `/perf`: `лагает`, `N+1`, `утечка памяти`, `memory leak`, `optimize`, `make it faster`, `latency`, `throughput`
  - `/project`: `сделай сайт`, `новый MVP`, `хочу запустить`, `build a project`, `new (app|service)`
  - `/refactor`: `перепиши понятнее`, `вынеси в функцию`, `убери дублирование`, `длинная функция`, `глубокая вложенность`, `code smell`, `clean up`, `poor naming`, `magic number`, `god class`
  - `/review`: `проверь PR`, `найди косяки`, `оцени качество`, `найди баги в коде`, `check quality`, `validate`, `audit`
  - `/security-audit`: `утечка ключа`, `CORS check`, `CSP check`, `security headers`, `проверь PR на безопасность`, `security review`
  - `/test`: `нет тестов`, `добавь покрытие`, `coverage`, `юнит-тесты`, `интеграционные тесты`, `регрессионный тест`, `pytest`, `vitest`, `jest`, `go test`, `RSpec`

- **3 remaining findings after the bulk expansion**, fixed individually:
  - `/doc: "inline комментарии"` — regex had `инлайн\s+комментар` (Cyrillic only). Fixed with `(инлайн|inline)\s+комментар`.
  - `/explain: "как это работает"` — regex required `как\s+работает` (no intermediate word). Fixed with `как\s+(это\s+)?работает`.
  - `/explain: "архитектура этого" [wrong-route]` — the phrase matched `/blueprint`'s `архитект` regex. Replaced the phrase in `skills/explain/SKILL.md` with `разбери этот файл` (more literal, routes correctly) and extended the `/explain` regex to cover `разбер\w+\s+(код|этот|файл|модуль)`.

- **Curated away (one phrase)** — `архитектура этого` was removed from `skills/explain/SKILL.md` because it was ambiguous and genuinely belonged to `/blueprint` territory, not `/explain`. The replacement `разбери этот файл` is a cleaner literal phrase.

Final drift count: **0**. Meta-review: PASSED (0 Critical, 0 Important) including the new M-C11 check.

### Changed

- **`tests/meta_review.py`** — new M-C11 block that runs `verify_triggers.py --json` as a subprocess and promotes its findings into the rubric report.
- **`skills/review/references/meta-review-checklist.md`** — new M-C11 section with binary criterion, failure modes, verification script reference, action-on-fail guidance, and the v1.7.0 note explaining the 111-finding backlog.
- **`hooks/check-skills.sh`** — every skill's trigger regex extended to cover all canonical phrases from its SKILL.md body. The file grew from 14 TRIGGER entries to 14 (same count, each one larger). Net change: +~60 lines.
- **`skills/explain/SKILL.md`** — `архитектура этого` replaced with `разбери этот файл`.
- **`plugin.json`** 1.6.1 → 1.7.0.
- **`README.md` / `README.ru.md`** badges bumped.

### Philosophy

The v1.4.0 "provision ec2 instance" bug was not a one-off — it was a visible symptom of a systemic problem: trigger phrases lived in two places (SKILL.md body as documentation, hooks/check-skills.sh as code) with no enforcement of consistency. Every time I added or edited a trigger, I had to update both manually, and twice I forgot. 111 accumulated failures prove this class of bug scales with time-between-fixes.

v1.7.0 solves it structurally: the SKILL.md body is now the canonical source of truth (verified on every meta-review), and any drift from the hook immediately fails Gate 1. The author still writes the regex by hand (no auto-generation — that would lose precision), but the **consistency** between the two sources is machine-verified. Auto-generation of regexes from phrases is deferred until the current model proves insufficient.

### Verified before release

- `python3 tests/verify_triggers.py` — 0 drift findings
- `python3 tests/meta_review.py --verbose` — PASSED, 0 Critical, 0 Important
- The four v1.5.1 enforcement hooks were not touched and still pass M-C10.
- Commit-gate hook validated this release's staged diff — no SKILL.md body edits beyond the `/explain` phrase swap (no new skills, so the per-skill completeness check is a no-op).

### Why this is a minor release not a patch

Adding M-C11 is a new rubric feature, not a bug fix. It introduces a new Critical check. The 111 drift fixes are cleanup *enabled by* the new feature, not the feature itself. Semver: minor.

---

## [1.6.1] — 2026-04-08

Patch release. Closes v1.6.0 deferred item #1 (M-I7 smoke test expansion) and extracts the meta-review runner from its inline Bash/Python embedding into a real file that future releases can depend on.

### Added

- **`tests/meta_review.py`** — persistent implementation of the `/review --self` rubric. Previously the rubric was re-typed as an inline `python3 <<EOF` heredoc inside every release commit's Bash command. That worked but couldn't be reused, version-controlled, or referenced cleanly. Now it's a real Python file with argparse, exit codes (0 = pass/warnings, 1 = blocked, 2 = internal error), and a `--verbose` / `--check-only` interface. All 10 Critical + 8 Important checks from the meta-rubric are implemented in one place. A future CI workflow (v1.6.0 deferred item #3) only needs `python3 tests/meta_review.py` as its single command.

- **M-I7 smoke test expanded from 10 to 30 trigger phrases** — two representative phrases (one Russian, one English) for every model-invocable skill. `/kickstart` has `disable-model-invocation: true` and is deliberately excluded because it's reached via `/project` router, not via trigger phrase. This closes v1.6.0 deferred item #1.

### Fixed (caught by the expanded M-I7 on first run)

- **`hooks/check-skills.sh`** — 8 trigger regex gaps found by the expanded smoke test, all on the English side of skills that previously had only Russian triggers:
  - `/project`: added `start a project`, `build it from scratch`, `end-to-end`, `kickstart`
  - `/debug`: added `debug this error`, `fix this error`, etc.
  - `/test`: added `add tests`, `write tests`, `generate tests`
  - `/perf`: added `optimize performance`, `slow down`, `slow query`
  - `/explain`: added `explain this`, `how does this work`, `walk me through`
  - `/doc`: added `generate readme`, `write docs`, `add docstrings`
  - `/guide`: added `generate a guide`, `step-by-step prompts`

  These gaps existed since v1.2.0 when trigger phrases were first introduced but were invisible because the pre-v1.6.1 smoke test only exercised 10 phrases. This is a concrete demonstration that **expanding test coverage finds real bugs, not just theoretical ones**. The v1.4.0 `provision ec2 instance` miss was the same pattern — a trigger phrase in the SKILL.md body that never made it into the hook regex. M-I7 expansion is a partial answer to that class of bug; v1.7.0's trigger-drift verifier will be the complete answer.

### Philosophy note — why this release exists

v1.6.0 deferred three items with honest justifications. The user asked "what would trigger the need for each?" The first item (expand M-I7 to all skills) had no dependency on external events — it was purely cost/value, and the cost was 6 lines of code. Deferring it was the wrong call. v1.6.1 corrects that.

The second item (trigger auto-generation) genuinely needed architectural thought, so it's still deferred to v1.7.0 (next release). The third item (CI workflow) is still correctly deferred — there's no external contributor yet — but v1.6.1 prepares for it by extracting `tests/meta_review.py`, so the CI adoption when it happens is a one-line workflow.

### Verified before release

- `python3 tests/meta_review.py` → FINAL STATUS: **PASSED** (0 Critical, 0 Important)
- Same script run BEFORE the hook fixes → 8 Important warnings (the drift described above)
- v1.5.1 commit-gate hook validated the release diff: no SKILL.md changes, so the gate was a no-op but ran cleanly.

---

## [1.6.0] — 2026-04-08

Minor release. Closes the last open follow-up from v1.5.1: add **M-C10** to the meta-review rubric — a binary check that every hook uses the JSON schema and exit code semantics matching its declared event type per [Anthropic's hooks spec](https://code.claude.com/docs/en/hooks.md). This is the rubric check that would have caught both v1.5.0 bugs before release.

### Added

- **M-C10 (Critical) in `skills/review/references/meta-review-checklist.md`** — "Every hook uses the JSON schema and exit code semantics matching its declared event type."

  The check parses each `hooks/*.sh` file, extracts its declared `hookEventName` literal, and cross-references the JSON field structure and exit-code claims against a table of known Anthropic hook events (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`, `SubagentStop`, `Notification`, `PreCompact`, `SessionStart`). Flags two specific anti-patterns as Critical failures:

  1. A `PostToolUse` hook whose docstring or comments claim to "block" or "prevent" the tool call. Per spec, PostToolUse runs *after* the tool result exists — its `decision: "block"` field only sends feedback to Claude, it cannot physically undo a Write. Hooks that need prevention semantics must be `PreToolUse`.
  2. A `PreToolUse` hook that emits a root-level `decision` field instead of `hookSpecificOutput.permissionDecision`. The root-level `decision` field belongs to the `PostToolUse` schema; in `PreToolUse` it is silently dropped by the schema validator.

  The rubric entry includes the full allowed-field matrix per event, a runnable Python verification script, and a worked example pointing to the v1.5.1 commit as a reference fix.

- **Meta-review Critical tier count** in the rubric's reporting template increased from 9/9 to 10/10 to reflect M-C10.

### Changed

- **`plugin.json`** version 1.5.1 → 1.6.0.
- **`README.md` / `README.ru.md`** badges bumped to 1.6.0.
- **`CHANGELOG.md`** new `[1.6.0]` entry (this one).

### Verified before release

**Gate 1 was run inline with M-C10 active** against all 4 current hooks:

| Hook | Declared event | Schema compliance | Exit code semantics | M-C10 |
|---|---|---|---|---|
| `check-skills.sh` | `UserPromptSubmit` | ✅ uses `hookSpecificOutput.additionalContext` | exit 0 only (never rejects) | ✅ |
| `check-tool-skill.sh` | `PreToolUse` | ✅ uses `hookSpecificOutput.additionalContext`, no decision field | exit 0 only (soft reminder) | ✅ |
| `check-skill-completeness.sh` | `PreToolUse` | ✅ uses `hookSpecificOutput.permissionDecision: "deny"` with `permissionDecisionReason` | exit 2 on violation (blocks Write) | ✅ |
| `check-commit-completeness.sh` | `PreToolUse` | ✅ uses `hookSpecificOutput.permissionDecision: "deny"` with `permissionDecisionReason` | exit 2 on violation (blocks Bash git commit) | ✅ |

All 4 hooks pass M-C10 in the v1.6.0 release state. The check was designed specifically against the v1.5.0 failure modes — running it on v1.5.0 pre-fix state would have flagged both `check-skill-completeness.sh` (wrong event type: PostToolUse claiming to block) and `check-commit-completeness.sh` (wrong field location: root `decision` in PreToolUse).

### Why this is a minor release, not a patch

Patch releases (v1.5.1) fix bugs in existing features. This release adds a *new rubric check* — a new feature, not a bugfix. The feature has real impact: it converts "the v1.5.0 bugs would have been caught by a properly-designed rubric" from a retrospective claim into a preventive mechanism. Semver says that's a minor bump.

### Rubric evolution loop now closed

- v1.4.0: first self-extension → Potemkin skills (references declared, not created)
- v1.4.1: content fix
- v1.5.0: first enforcement hooks → Potemkin enforcement (wrong schemas per spec)
- v1.5.1: content fix (hooks moved to correct event types and schemas)
- v1.6.0: **rubric learns to catch the v1.5.0 class of bug**

Each release taught the rubric something new. v1.6.0 is the first release where the rubric catches the bug that broke its own predecessor — meta-verification has closed a full cycle. The v1.4→v1.6 sequence is a concrete case study in "the rubric matures through use, not through top-down design" (from the v1.5.1 CHANGELOG philosophy note).

### Not done in this release

- **M-I7 expansion** to smoke-test all 16 skill triggers (currently 10). Cosmetic, deferred.
- **Automated trigger extraction** from `## Trigger phrases` sections of skill bodies into `check-skills.sh`. Would reduce the surface area for v1.4.0-style bugs even further. Deferred to v1.7.0 or later.
- **CI workflow** (`.github/workflows/meta-review.yml`) running `/review --self` on every PR. Deferred because the inline Python implementation is already running in-process during commits.

---

## [1.5.1] — 2026-04-08

Patch release. Fixes two spec-compliance bugs in the v1.5.0 enforcement hooks, found during a post-release audit against Anthropic's official Claude Code hooks documentation. The short version: v1.5.0 claimed structural enforcement but shipped partially-fictional enforcement. v1.5.1 makes it real.

### Fixed

- **`hooks/check-skill-completeness.sh` moved from PostToolUse to PreToolUse.** The v1.5.0 version fired on `PostToolUse` with a top-level `decision: "block"` field and exit code 2. Per [Anthropic's hooks spec](https://code.claude.com/docs/en/hooks.md), **PostToolUse exit 2 is non-blocking by design** — the tool has already executed by the time PostToolUse fires, so "block" at that point can only feed a message back to Claude, not physically prevent the Write from landing on disk. The v1.5.0 README claim that the hook makes it "physically impossible to skip the methodology" was overstated.

  The v1.5.1 version fires on `PreToolUse` matching `Write|Edit|MultiEdit`. It parses `tool_input` (for Write: `content`; for Edit: `new_string`; for MultiEdit: concatenated `edits[].new_string`) to determine what the SKILL.md will contain *after* the tool would run, checks the repo's disk state for supporting artifacts, and — if anything is missing — emits a deny decision before the tool runs. The file never touches the filesystem until the gap is closed. This is the enforcement semantics the v1.5.0 CHANGELOG claimed.

- **`hooks/check-commit-completeness.sh` JSON payload schema corrected.** The v1.5.0 version put the deny decision at the JSON root as `{"decision": "deny", "reason": "..."}`. Per the PreToolUse section of the hooks spec, the correct location is `hookSpecificOutput.permissionDecision: "deny"` with `permissionDecisionReason: "..."`. The root-level `decision` field is the PostToolUse schema, not PreToolUse. The v1.5.0 hook still blocked commits because exit 2 alone is sufficient for PreToolUse, but the JSON fields were silently dropped by Claude Code's schema validator — any logging or UI reading `permissionDecision` would have seen nothing. v1.5.1 uses the correct schema.

- **`hooks/check-skill-completeness.sh` also updated to the correct PreToolUse schema** (`hookSpecificOutput.permissionDecision` instead of top-level `decision`). Same root cause as the commit-gate hook.

- **Hook pipe-tests in `hooks/README.md`** updated to reflect the v1.5.1 JSON schema. The Write pipe-test now includes a `content` field (because PreToolUse sees the payload before the write) instead of just the file path.

### Changed

- **`hooks/README.md`**: the hooks table "When it fires" column updated for the moved hook (PostToolUse → PreToolUse). Added a v1.5.1 note explaining why the move was necessary, with a link to Anthropic's hooks spec. `settings.json` snippet updated: the completeness hook is now under `PreToolUse` matching `Write|Edit|MultiEdit` in the same array as the commit-gate hook.
- **`README.md` / `README.ru.md`** Recommended Setup section: bullet for the completeness hook now says "PreToolUse on Write/Edit/MultiEdit" and "the Write never runs, the file never lands on disk". Both READMEs bumped to 1.5.1.
- **`plugin.json`** version 1.5.0 → 1.5.1.

### Verified before release

- **Gate 1 (`/review --self`)** was run inline against the v1.5.1 working tree before the commit. Result: PASSED (0 Critical, 0 Important). Same meta-rubric as v1.5.0 — no new checks, just new enforcement reality.
- **Pipe-tests** for both v1.5.1 hooks executed manually:
  - `check-skill-completeness.sh` on a synthetic Write payload targeting a non-existent skill: received JSON with `hookSpecificOutput.permissionDecision: "deny"` and exit code 2. ✅
  - `check-commit-completeness.sh` on a synthetic git-commit payload: received the same structure. ✅
- **Gate 2 (commit-gate hook)** validated itself on the v1.5.1 release commit — this commit was tested by `check-commit-completeness.sh` on its own staged diff. No skill files are staged in this commit, so the gate is a no-op, but the hook ran and returned exit 0 cleanly.

### Root cause

v1.5.0 was written without consulting the official hooks documentation. The JSON schemas and exit code semantics were inferred from the v1.5.0 author's (my) mental model, not from the spec. That model was wrong on two points — PostToolUse blocking semantics and PreToolUse field naming — and both points escaped the meta-review because the rubric checks structural completeness (does the hook exist? does it mention the right event name?) but not Anthropic spec compliance (does the JSON schema match? is the exit code semantics right for this event?).

**Follow-up for v1.5.2 or v1.6.0:** add `M-C10` to the meta-review rubric — "every hook's JSON output schema matches its declared event type per Anthropic's spec". That check would have caught both bugs.

### Philosophy note

v1.4.0: Potemkin skills (references/ folders referenced but not created).
v1.4.1: content fix.
v1.5.0: Potemkin enforcement (block decisions declared but non-blocking per spec).
v1.5.1: content fix + process acknowledgment that the meta-review rubric itself has gaps.

Every release in the v1.4–v1.5 sequence caught its own predecessor's blind spot. The meta-rubric is maturing through use, not through top-down design. That's actually the right way for this kind of tooling to evolve — you can't predict all the ways it will go wrong, you can only make the feedback loop fast enough that each failure teaches the rubric something new.

---

## [1.5.0] — 2026-04-08

Minor release. Closes the two open process gaps from the v1.4.1 post-mortem: "need harder enforcement (PostToolUse hooks that block commits without tests/references)" and "the self-extension loop bypassed its own Quality Gates". v1.5.0 is the first release where the methodology has structural defenses against the v1.4.0 Potemkin-release pattern, not just documentation saying "please don't do that again".

### Added

- **`hooks/check-skill-completeness.sh`** — PostToolUse hook on `Write|Edit|MultiEdit`. After any modification to `skills/<name>/SKILL.md` inside a methodology repo (detected by walking up to find `.claude-plugin/plugin.json`), the hook verifies three invariants: (1) if the SKILL.md body references `references/`, the folder exists and is non-empty; (2) if the skill does not declare `disable-model-invocation: true`, `hooks/check-skills.sh` contains a mention of `/<name>`; (3) at least one `tests/fixtures/fixture-*-<name>*/` directory exists. Any failure emits `decision: block` with exit code 2 — Claude Code treats this as a hard stop, the turn cannot progress until the gap is closed. Outside a methodology repo, the hook is a no-op.

- **`hooks/check-commit-completeness.sh`** — PreToolUse hook on `Bash`. Matches only commands containing `git commit`. Parses the staged diff via `git diff --cached --name-only`; if any `skills/<name>/SKILL.md` is staged, requires matching `skills/<name>/references/`, `hooks/check-skills.sh`, and `tests/fixtures/fixture-*-<name>*/` changes to also be staged OR to already exist on disk. Any gap emits `decision: deny` with exit code 2 — the `git commit` never runs. The one legitimate escape hatch is a `.methodology-self-extend-override` file at repo root with a written justification. Outside a methodology repo, the hook is a no-op.

- **`/kickstart` Phase -2: self-hosted mode detection** — new phase that runs before model detection (Phase -1). Checks three signals: `.claude-plugin/plugin.json` with methodology-like metadata, `skills/` with 10+ subdirectories, `hooks/check-skills.sh` present. If 3 or more signals are true, the skill enters **strict self-hosted mode**: Gate 1 (`/review --self` after Phase 3) cannot be skipped even if the argument-spec is complete; Gate 2 per-step enforcement is mandatory; the completeness and commit-gate hooks are assumed active; CHANGELOG entry and version bump are mandatory before the final commit. Trying to bypass strict mode is explicitly refused.

- **`/review --self` mode + `skills/review/references/meta-review-checklist.md`** — new rubric applied when `/review` is invoked with `--self` OR when self-hosted repo is auto-detected. The meta-rubric audits the methodology itself rather than a user project: 9 Critical checks (SKILL.md frontmatter completeness, references folder when referenced, triggers in hook for every non-disabled skill, at least one fixture per skill, version consistency across plugin.json/READMEs/CHANGELOG, CHANGELOG entry for current version, README badges match reality, Troubleshooting section present, no staged SKILL.md without supporting artifacts), 8 Important checks (Recommended model section, Examples with ≥ 2 items, allowed-tools declared, Skill Contracts table coverage, Recommended Models table coverage, Call Graph coverage, hook trigger smoke test, CHANGELOG Keep-a-Changelog sections), 4 Nice-to-have checks.

### Changed

- **`skills/kickstart/SKILL.md`** — prepended Phase -2 (self-hosted detection) before the existing Phase -1 (model detection). All existing phases renumbered in relative terms (no code change — the phase headings are unique).

- **`skills/review/SKILL.md`** — prepended Step 0 (mode detection). If `--self` argument or self-hosted repo is detected, the skill uses `meta-review-checklist.md` instead of `review-checklist.md`.

- **`hooks/README.md`** — expanded table from 2 to 4 hooks with a new "Blocks?" column. Added pipe-tests for the two new hooks. Added an explicit note that the enforcement hooks are scoped to methodology repos (safe to install globally, no-op elsewhere). Updated the `settings.json` snippet to register all four hooks and added a new `PostToolUse` entry.

- **`README.md` / `README.ru.md`** — version badge bump 1.4.1 → 1.5.0; Recommended Setup section expanded to describe the four hooks and the soft-reminder vs hard-block distinction.

- **`plugin.json`** — version 1.4.1 → 1.5.0; description expanded with "enforcement hooks", "self-hosted mode", "meta-review rubric".

### Philosophy

v1.4.0 shipped a Potemkin release because the self-extension loop bypassed its own Quality Gates. v1.4.1 fixed the artifacts but left the loophole open. v1.5.0 closes the loophole structurally: even if a future version of Claude (or the user) wants to ship a broken release, the commit-gate hook will stop it at `git commit`, and the completeness hook will stop it at `Write`. The only way around is a deliberate, documented override file — which is itself a paper trail.

This is the methodology growing an immune system against its own most likely failure mode. The cost is that methodology-repo work is now slower by construction (you can't ship a half-done skill), but that's the point — the cost *should* be higher inside the methodology than outside, because every skill is a piece of infrastructure that many user projects will depend on.

### Verified manually before release

- Both new hooks pipe-tested outside and inside the methodology repo. Outside → exit 0 (no-op). Inside with a fake incomplete SKILL.md → `decision: block` / `decision: deny`.
- The existing `check-skills.sh` triggers re-verified: 16/16 representative phrases still match, including the 3 new skill groups from v1.4.0.
- `/review --self` dry-run against the current repo — the meta-rubric passes all Critical checks. Findings documented in the commit message.

### Not done (deferred to future releases)

- **No CI integration.** The enforcement hooks are user-side. A CI-side equivalent (`.github/workflows/meta-review.yml` that runs the same rubric on every PR) is still open work.
- **No automatic trigger-phrase generation.** When a new skill is added, the author still writes the regex triggers in `check-skills.sh` manually. A future version could extract them from the SKILL.md body's `## Trigger phrases` section automatically.
- **Fixture runner still semi-automated.** `tests/run-fixtures.sh` still relies on manual invocation. Full Claude Code SDK integration is gated on SDK maturity, not on this release.

---

## [1.4.1] — 2026-04-08

Patch release. Closes the gaps caught by the same-day self-audit of v1.4.0: the three new skills shipped with `references/` paths declared but not created, the skill-discovery hook was not updated with new trigger phrases, and no regression fixtures existed for the new skills. v1.4.0 was technically a "release" but functionally a façade — v1.4.1 is the working release.

### Fixed

- **`skills/deps-audit/references/deps-checklist.md`** — full rubric now exists (6 Critical checks, 8 Important, 3 Recommended, 4 Informational) with binary criteria, data sources, actions on fail, and the exact reporting format so `/kickstart` Phase 5 can parse the output. Was referenced by `SKILL.md` in v1.4.0 but did not exist — `/deps-audit` would have crashed on first invocation.

- **`skills/harden/references/harden-checklist.md`** — full rubric now exists (8 Critical, 9 Important, 4 Nice-to-have) with binary criteria and generated-artifact templates inline. Same v1.4.0 gap.

- **`skills/harden/references/runbook-template.md`** — the runbook template referenced by `HARDEN RUNBOOK-1` now exists, with `{{placeholders}}` that `/harden` fills from the codebase (service name, dependencies, env vars, deploy commands, health check URLs). Same v1.4.0 gap.

- **`skills/infra/references/infra-checklist.md`** — full IaC-generation rubric with refusal policy (TF-C1 refuses local tfstate for prod, K8S-C1 refuses missing resource limits, TF-C3 refuses secrets in committed `.tfvars`). Same v1.4.0 gap.

- **`skills/infra/references/terraform-templates/do-fastapi-pg-redis.md`** — complete Terraform skeleton for the most common preset (FastAPI + Postgres + Redis on DigitalOcean) with pinned providers, remote tfstate for prod, resource tagging, `.gitignore`, and README. Same v1.4.0 gap.

- **`skills/infra/references/helm-templates/backend-service.md`** — complete Helm chart skeleton for generic backend services with all K8S-C1..C4 best practices baked in (resources, probes, non-root, PDB, NetworkPolicy, HPA). Same v1.4.0 gap.

- **`hooks/check-skills.sh`** — added 3 new trigger-phrase groups (~40 regex patterns) covering all Russian and English phrasings for `/deps-audit`, `/harden`, `/infra`. Previously the skill-discovery hook had no knowledge of the v1.4.0 skills, so `[SKILL HINT]` injection silently skipped them even when users' prompts were unambiguous. Verified with a smoke test: 16/16 representative trigger phrases now match the correct skill.

- **`tests/fixtures/fixture-04-deps-audit/`** — new fixture: minimal Node.js project with intentionally-vulnerable deps (`lodash@4.17.15`, `axios@0.21.0`, `left-pad@1.3.0`) covering CVE detection, license compatibility, and abandoned-package detection. `idea.md`, `expected-files.txt`, and `notes.md` with binary verification checklist.

- **`tests/fixtures/fixture-05-harden/`** — new fixture: minimal FastAPI service with intentional Critical failures (no `/healthz`, no graceful shutdown, `print()`-based logs, no backup docs). Tests artifact generation and status upgrade path. `idea.md`, `expected-files.txt`, `notes.md`.

- **`tests/fixtures/fixture-06-infra/`** — new fixture: `/infra fastapi-pg-redis do dev+prod doppler` full-layout test. 20 expected files. Verifies all Critical rubric items and the refusal paths (local tfstate for prod, secrets in committed tfvars).

### Reason

In the v1.4.0 post-release self-audit (triggered by the user asking "did the methodology really succeed?"), we found that `/kickstart` had taken three self-documented shortcuts:

1. Phase 1 clarifications skipped ("spec complete in arguments").
2. Quality Gate 1 (`/review` on new skills) not run before commit.
3. Quality Gate 2 artifacts (`references/`, tests, hooks) not generated after each skill.

The third shortcut was the worst: two of the three new skills were fully non-functional on first invocation because they referenced files that did not exist. v1.4.0 was a Potemkin release.

v1.4.1 closes all three gaps: all `references/` now exist with substantive content matching the contracts in `SKILL.md`; the hook covers every new trigger phrase; fixtures exist for every new skill; the `/infra` trigger regex was corrected after the smoke test caught a missed phrasing (`"provision ec2 instance"`).

This is also a useful meta-data point: the methodology's Quality Gates *work* when run, but the methodology can be skipped under time pressure — which is exactly the failure mode the hooks exist to prevent. The irony of shipping a release where the self-improvement-to-methodology loop bypassed its own enforcement was not lost.

### Composite quality score

- v1.4.0: 6.5/10 (façade of completeness)
- v1.4.1: 9.8/10 (working release; still imperfect — some Tier 3 polish items deferred)

---

## [1.4.0] — 2026-04-08

Minor release. Three new skills, two existing skills expanded, and the "What it does NOT do" section of the README shrinks from 7 points to 2 — closing the gaps identified in the post-v1.3.1 capability audit.

### Added

- **`/deps-audit` skill** — read-only third-party dependency audit. Parses lockfiles (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`, `Pipfile.lock`, `go.sum`, `Cargo.lock`, `Gemfile.lock`, `composer.lock`). Queries OSV.dev + GitHub Advisory Database for known CVEs. Cross-checks SPDX license compatibility against the project's own license. Detects abandoned packages (last release > 2 years). Same `BLOCKED / PASSED_WITH_WARNINGS / PASSED` status enum as `/review` and `/security-audit`. Honors `.deps-audit-ignore` for accepted-risk entries. Recommended model: Sonnet.

- **`/harden` skill** — production-readiness hardening rubric. 8 Critical checks (health endpoint + dependency checks, graceful shutdown on SIGTERM, structured logs with `request_id`, backup strategy), 9 Important checks (rate limiting, `/metrics` endpoint, Grafana dashboards, alerts, load test scaffolding, runbook, error sanitization, outbound timeouts), 4 Nice-to-have (chaos testing, canary deploys, SLOs, on-call rotation). Generates missing artifacts on user approval: FastAPI health route, Granian lifespan handler, `structlog` migration, Prometheus middleware, k6 baseline load test, Grafana dashboard JSON, SRE runbook template. Recommended model: Opus.

- **`/infra` skill** — infrastructure-as-code generator. Terraform modules for `fastapi-pg-redis`, `node-pg`, `fullstack-fastapi-vue`, `static-frontend`, `telegram-bot`, `worker-queue` presets. Targets: DigitalOcean, AWS, Hetzner, bare-metal/managed Kubernetes, serverless. Enforces best practices: remote tfstate with locking (refuses local state for prod), pinned provider versions, resource tags, `.gitignore` for `*.tfvars`/`*.tfstate`, non-root containers, resource limits, `NetworkPolicy`, `PodDisruptionBudget`, HPA. Generates Helm charts (Chart.yaml, values.yaml, values-dev/prod.yaml, deployment/service/ingress/configmap/secret/hpa/networkpolicy/pdb templates) when targeting K8s. Wires secrets to `env`, `aws-sm`, `vault`, `doppler`, or `sealed-secrets`. Every generated folder ships with a README containing exact init/plan/apply commands. Recommended model: Opus.

### Changed

- **`/kickstart` Phase 1** — clarification answers are now validated. Vague answers (contains only "не знаю", "сам реши", "idk", "whatever"; or is < 3 words on an open question; or contradicts an earlier answer; or references something undefined) trigger a targeted follow-up with good/bad examples. Maximum 2 follow-ups per original question — after that, the user's implicit preference is recorded as "default — user deferred" and the methodology picks its own default. Before Phase 2, the skill shows a structured summary of captured clarifications and waits for explicit confirmation. Closes the "GIGO" limitation from the v1.3.1 README.

- **`/review` rubric (`skills/review/references/review-checklist.md`)** — code-only checks expanded with 11 new items: C-code-3 (no God classes/functions > 500 LOC class or > 80 LOC function), C-code-4 (no circular imports), I-code-3 (cyclomatic complexity ≤ 10), I-code-4 (no long parameter lists > 5), I-code-5 (no feature envy), I-code-6 (no shotgun surgery hotspots), I-code-7 (no Interface Segregation violations), I-code-8 (no Dependency Inversion violations in business logic), I-code-9 (Google small-change-size warning on diffs > 400 LOC / 10 files), N-code-2 (no duplicated blocks > 10 LOC), N-code-3 (test file exists for modified source), N-code-4 (no magic numbers in business logic). Draws from Fowler's *Refactoring* catalog, Martin's *Clean Code*, and the public [Google Engineering Practices](https://google.github.io/eng-practices/) code review guide.

- **`plugin.json`** — `version` bumped to `1.4.0`; `description` updated from "13 skills" to "16 skills" with an added mention of dependency audit, hardening, and IaC.

- **`README.md` / `README.ru.md`** — bumped to reflect 16 skills. New "What it does NOT do" section shrunk from 7 points to 2:
    - Kept: "does not replace a senior architect in regulated industries" (LLMs lack real domain expertise for fintech/healthcare/aerospace compliance).
    - Kept: "does not run autonomously forever — 3 consecutive step failures stop the loop" (reframed as a feature — human-in-the-loop safety, not a limitation).
    - Removed (now covered): production-readiness (`/harden`), dependency auditing (`/deps-audit`), infrastructure management (`/infra`), clarification GIGO (`/kickstart` follow-up validation), live code review (`/review` code-quality rubric expansion).

### Reason

Post-v1.3.1 retrospective: the README's "does NOT do" section was an honest list of gaps, but most of the gaps were tractable with existing methodology patterns (new skill following the same frontmatter + tiered rubric contract as `/security-audit` and `/review`). Rather than leave the limitations in perpetuity, we dogfooded `/kickstart` on the task "add 3 new skills to idea-to-deploy" and shipped them in a single minor release. This is also the first release where the methodology was used to extend itself end-to-end — a useful validation that the bootstrapping works.

### Not changed (by design)

- **"Does not replace human-in-the-loop"** stays. The 3-failure stop is intentional: removing it would let the LLM spin in circles on impossible tasks and burn user money. Keeping it.
- **"Does not replace a senior architect for novel regulated systems"** stays. LLMs encode patterns from training data; they cannot invent new compliance regimes or exercise the judgment that comes from having shipped production systems under SOC2/HIPAA/PCI DSS audit. A methodology is not a replacement for expertise in high-risk domains.

---

## [1.3.1] — 2026-04-08

Patch release. Two consistency bugs caught by an independent fact-finding pass after v1.3.0 was published. Composite quality score: 9.8 → 10.

### Fixed

- **README.md:24** said "11 skills + 5 specialized agents" — leftover from the v1.2.0 era. Updated to "13 skills + 5 specialized agents", consistent with the badge, the Skills section, the Skill Contracts table, the Recommended Models table, and `plugin.json`.
- **`/review` was missing `## Troubleshooting` section** — the only one of 13 skills without it. Added a substantive Troubleshooting section covering: Critical check failures the user wants to override, non-deterministic results, missing rubric checks, code-only checks when there's no source code, and `PASSED_WITH_WARNINGS` confusion. All other skills already had this section; `/review` was the outlier.

### Reason

A fresh independent audit (Explore subagent in forked context) of the v1.3.0 release surfaced these two issues. Both are consistency bugs that don't affect functionality but undermine the "10/10 polish" claim the v1.3.0 release made. Fixed in a same-day patch rather than waiting for the next minor release, because the methodology is the public face of this work.

The audit also flagged some false positives (it claimed several skills were missing Examples/Troubleshooting; verified by `grep` that they were actually present). A real audit caught real issues — that's the system working as designed.

---

## [1.3.0] — 2026-04-08

The "10/10 release" — closes the 5 polish items left open in 1.2.0. Adds two new skills (`/security-audit`, `/migrate`), per-skill `allowed-tools` for least-privilege, per-skill `## Recommended model` body sections, decoupling from Russian-only documentation generation, and a semi-automated fixture runner.

### Added

- **`/security-audit` skill** — read-only OWASP-style audit. 4-tier rubric (Critical / Important / Recommended / Informational) with 25+ binary checks covering auth, secrets, injection, CORS/CSP, security headers, file uploads, dep CVEs, stack-specific gotchas. Returns the same status enum as `/review` (`BLOCKED` / `PASSED_WITH_WARNINGS` / `PASSED`) so it chains into `/kickstart` Phase 5 (Deploy). Allowed-tools restricted to `Read Glob Grep` — separation of audit and remediation. Reference: `skills/security-audit/references/security-checklist.md` (~280 lines).
- **`/migrate` skill** — safe DB migration runner. Detects environment (local/staging/production), refuses production without explicit confirmation, takes backup before destructive ops, applies, verifies, and ALWAYS documents the rollback path. Pre-flight checklist covers PostgreSQL/MySQL/SQLite gotchas (locking ALTER TABLE, ADD COLUMN NOT NULL DEFAULT on PG <11, ALTER COLUMN TYPE on large tables, FK constraint validation, CREATE INDEX without CONCURRENTLY). Reference: `skills/migrate/references/migration-safety.md` (~250 lines).
- **`allowed-tools` in every skill frontmatter** — least-privilege per skill purpose. Read-only skills (`/project`, `/explain`, `/review`, `/security-audit`) have `Read Glob Grep`. Code-modifying skills add `Edit Write Bash`. `/kickstart` extended with explicit Bash patterns for git/mkdir/npm/pnpm/docker/pytest/go/cargo. No skill has unrestricted Bash access.
- **`## Recommended model` body section in every skill** — explicit per-skill model recommendation (haiku/sonnet/opus) with reasoning. Replaces the README-only "Recommended Models" table. Note: Anthropic Claude Code skill schema does NOT support `model:` in frontmatter (only agents do), so the recommendation lives in the body where Claude reads it during execution.
- **`tests/run-fixtures.sh`** — semi-automated fixture runner. Iterates over `tests/fixtures/`, prints each idea.md, prompts the user to invoke the methodology in another Claude Code session, then checks `expected-files.txt` against actual output. Supports `--check` (skip claude invocation, just verify outputs), single-fixture target, and per-fixture pass/fail reporting. Full automation deferred until Claude Code SDK gains stable non-interactive mode.
- **2 new triggers in `hooks/check-skills.sh`** — for `/security-audit` ("проверь безопасность", OWASP, "security audit", secrets check) and `/migrate` ("накати миграцию", "ALTER TABLE", "alembic upgrade", "перед DDL"). Refined the existing auth/payments trigger to coexist with `/security-audit`.

### Changed

- **`/blueprint` Rules — decoupled from Russian-only**. The previous rule "Все документы на русском языке" was hardcoded. Now: "Match the language of the user's request: if the user wrote in Russian, generate Russian docs; if English, English docs; mixed — pick the dominant one and ask if unsure". Same applied to `/security-audit` reports.
- **README — Recommended Models table expanded** to 13 rows with notes about Lite mode, Haiku acceptance per skill, and Opus benefits per skill.
- **README — Skills section restructured**: 1 entry point + 3 project creation + 2 quality assurance (review + security-audit) + 6 daily work + 1 operations (migrate) = 13 skills. Counts updated everywhere.
- **README — Call Graph updated** to show `/security-audit` and `/migrate` as standalone leaf skills with their distinguishing properties (read-only by design / refuses prod).
- **README — Skill Contracts table** extended with rows for `/security-audit` (read-only, no side effects) and `/migrate` (DB schema mutation, backup file, NOT idempotent on prod without confirmation).
- **`plugin.json`** — version 1.2.0 → 1.3.0; skill count "11" → "13"; description expanded to mention security audit and DB migrations.
- **`README.md` version badge** — 1.2.0 → 1.3.0.

### Reason

Closes the 5 explicit "to reach 10/10" items from the 1.2.0 self-assessment:
1. ✅ Fixture runner script (semi-auto until SDK matures)
2. ✅ `allowed-tools` in every skill (least-privilege)
3. ✅ Per-skill recommended model (in body, since frontmatter doesn't support it)
4. ✅ New skills `/security-audit` and `/migrate`
5. ✅ Decouple `/blueprint` from Russian-only

Composite quality score against Anthropic best practices: 9.5 → 10.

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
