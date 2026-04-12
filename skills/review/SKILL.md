---
name: review
description: 'Validate project documentation and code via binary rubric. Checks consistency between PRD, architecture, plan, and code.'
argument-hint: project path or specific document to review
license: MIT
allowed-tools: Read Glob Grep
context: fork
agent: code-reviewer
report_only: true
metadata:
  author: HiH-DimaN
  version: 1.13.0
  category: quality-assurance
  tags: [validation, quality-check, review, consistency, solid, code-smells, methodology-review]
---

# Review


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- проверь документацию, проверь код, проверь архитектуру, проверь PR
- валидация проекта, ревью, code review, review project
- найди косяки, оцени качество, найди баги в коде
- check quality, validate, audit
- автоматически перед коммитом >2 файлов

You are a quality validator for project documentation and code. Your job is to find gaps, inconsistencies, and missing pieces BEFORE implementation begins.

## Recommended model

**opus** — Cross-document validation requires holding all 6 documents in working memory simultaneously and checking ~25 rubric items. Opus is recommended; the code-reviewer subagent fork is also Sonnet-capable.

Set via `/model {model}` before invoking this skill, or via the project's default model in `~/.claude/settings.json`.


## Instructions

### Step 0: Detect review mode (v1.13.0)

Before anything else, determine whether this is a **methodology self-review** or a **regular project review**. The two modes use different rubrics and different runners — mixing them produces nonsense reports.

Methodology self-review is active when ANY of:

1. `$ARGUMENTS` contains `--self`, `--target methodology`, "meta-review", "self-review", «проверь методологию», «review the methodology repo», or similar explicit marker.
2. `pwd` (or the path in `$ARGUMENTS`) contains `.claude-plugin/plugin.json` with `"name": "idea-to-deploy"`, AND a populated `skills/` directory, AND `hooks/check-skills.sh`.
3. The current git diff (or the path under review) touches `skills/*/SKILL.md`, `hooks/*.sh`, `.claude-plugin/plugin.json`, or `tests/meta_review.py` — i.e. methodology surfaces, not project surfaces.

**If methodology self-review is active:**

```bash
cd <repo_root>
python3 tests/meta_review.py --verbose
```

The script implements the full three-tier rubric from `references/meta-review-checklist.md` (same Critical/Important/Nice-to-have structure as project review). Parse its output:

- `FINAL STATUS: PASSED` → report `PASSED`
- `FINAL STATUS: PASSED_WITH_WARNINGS` → report `PASSED_WITH_WARNINGS` with the Important findings
- `FINAL STATUS: BLOCKED` → report `BLOCKED` with the Critical findings and offer fixes (Step 4)

Do NOT run the project-level rubric (Steps 1-2 below) in methodology mode — it would look for `PRD.md` / `STRATEGIC_PLAN.md` / `IMPLEMENTATION_PLAN.md` which don't exist in a methodology repo and produce false-negative BLOCKED reports. This was the v1.12.0 "8th gap" incident: the code-reviewer subagent ignored this Step 0 because it had its own instructions that didn't mention methodology mode. Fixed in v1.13.0 by syncing `agents/code-reviewer.md` with the same Step 0 logic — the subagent now detects and delegates the same way.

**If regular project review is active:** proceed to Step 1 below with the standard rubric.

### Step 1: Detect what to review

Read available project files:
- STRATEGIC_PLAN.md
- PROJECT_ARCHITECTURE.md
- IMPLEMENTATION_PLAN.md
- PRD.md
- README.md
- CLAUDE_CODE_GUIDE.md
- CLAUDE.md
- Source code (if exists)

If  specifies a file or path, focus on that. Otherwise review everything available.

### Step 2: Run the binary rubric

**Read `references/review-checklist.md`** — it is the single source of truth for what to check. The rubric is split into three tiers:

- **Tier 1 (Critical)** — checks C1–C12 (and C-code-1 … C-code-4 when source code exists). Failure of any single Critical check sets gate status to `BLOCKED`.
- **Tier 2 (Important)** — checks I1–I9 (and I-code-1 … I-code-9). Failures produce warnings but the gate passes (`PASSED_WITH_WARNINGS`).
- **Tier 3 (Nice-to-have)** — checks N1–N4 (and N-code-1 … N-code-4). Failures are informational only.

**New in v1.4.0:** the code-only rubric now includes SOLID violations (God class, long parameter list, feature envy, Interface Segregation, Dependency Inversion), cyclomatic complexity > 10, Fowler code smells (shotgun surgery, magic numbers, duplication), and Google Engineering Practices (small change size). Full definitions live in `references/review-checklist.md` under "Code-quality checks".

For each check:
1. Read the referenced files (PROJECT_ARCHITECTURE.md, PRD.md, IMPLEMENTATION_PLAN.md, CLAUDE_CODE_GUIDE.md, CLAUDE.md, source code).
2. Apply the binary criterion exactly as written in the rubric.
3. Mark ✅ (pass), ❌ (fail), or ⚠️ (partial — only for Important tier).
4. Capture a one-line `→ reason` annotation when failing.

Do NOT invent your own criteria. If the rubric does not cover something, note it in the "Additional observations" section but do not let it affect gate status.

### Step 3: Generate report

Output the report in **exactly** the format specified at the bottom of `references/review-checklist.md` (`## Reporting format` section). The format is parseable so other skills (`/kickstart` Quality Gate 1) can consume it.

The summary table is mandatory:

```markdown
| Tier | Pass | Total | Status |
|---|---|---|---|
| Critical | X | 12 | ✅/❌ |
| Important | Y | 9 | ✅/⚠️ |
| Nice-to-have | Z | 4 | ✅/ℹ️ |
```

The derived score (0–10) is computed as:
```
score = ((Critical_pass / Critical_total) * 0.6
       + (Important_pass / Important_total) * 0.3
       + (Nice_pass / Nice_total) * 0.1) * 10
```
and is reported as **informational only** — never used for gating.

### Step 4: Offer fixes

For each Critical failure (and optionally each Important warning), ask:
"Хотите, чтобы я исправил [check_id]: [reason]?"

If user agrees, fix the documents directly. Then re-run only the previously-failing checks to confirm the fix. Do not re-run the entire rubric — that's wasteful.

## Quality Gate

The gate status is **deterministic** — same documents always produce the same status:

| Status | Meaning | Caller behavior |
|---|---|---|
| `BLOCKED` | At least one Critical check failed | `/kickstart` Quality Gate 1 refuses to proceed; user must fix or override |
| `PASSED_WITH_WARNINGS` | All Critical pass, at least one Important fail | `/kickstart` proceeds but shows warnings to user |
| `PASSED` | All Critical and Important pass (Nice-to-have may fail) | `/kickstart` proceeds silently |

**Changed in v1.2.0:** the previous `score >= 7/10` gate has been removed because score values varied between model invocations on the same input. The binary rubric is deterministic.

## Examples

### Example 1: Missing endpoints
User runs: /review
You find: PRD has "user can reset password" but architecture has no /api/auth/reset endpoint.
Report: Critical issue — missing endpoint for password reset story.
Fix: Add POST /api/auth/reset-password to architecture with request/response format.

### Example 2: Inconsistent naming
Architecture says table "clients", implementation plan says "customers", code has "users".
Report: Critical issue — inconsistent entity naming across documents.
Fix: Standardize to one name across all documents.

## Troubleshooting

### A Critical check fails but the user insists the project is fine
The rubric is deterministic — if a Critical check fails, there's a real gap between what the documents promise and what they deliver. Do not soften the status to please the user. Instead:
1. Re-read the failing check criterion from `references/review-checklist.md`
2. Re-verify against the actual document content
3. If the check is truly inapplicable (e.g., C2 database check on a no-DB CLI tool), the rubric explicitly allows the "no database" justification path — verify the document has that justification, then the check passes
4. If the user wants to override anyway, return `BLOCKED` and let them invoke `/kickstart` with explicit `--skip-review` (not currently supported, but a future flag) — never silently downgrade the status

### Two consecutive runs give different results
This should not happen with the binary rubric. If it does, the cause is almost always:
- A document was edited between runs
- The rubric's source files have additions (e.g., a new fixture appeared)
- A source code file was added/removed (affects code-only checks)

Diff the `references/review-checklist.md` against what was used in the previous run.

### Rubric check is missing a case I care about
Add it to `references/review-checklist.md` in the appropriate tier (Critical / Important / Nice-to-have). Choose Important by default — Critical checks block deploys, so the bar should be high. Document the new check's binary criterion explicitly, not as a vague guideline.

### Code-only checks fail because there's no source code yet
That's expected. The rubric's code-only checks (C-code-1, C-code-2, I-code-1, I-code-2, N-code-1) are skipped when no source files exist. Report status is computed only over the doc-level checks. This is documented in `references/review-checklist.md` — verify it's accurate.

### Status is `PASSED_WITH_WARNINGS` but the user wants it to pass cleanly
The Important warnings are real issues — fix them, don't hide them. Each warning has a `→ reason` annotation showing what to add or change. Apply the fix, re-run only that check, status becomes `PASSED`.
