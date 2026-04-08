# Changelog

All notable changes to **idea-to-deploy** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
