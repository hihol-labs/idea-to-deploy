---
name: review
description: 'Validate quality of project documentation and code via deterministic binary rubric. Checks consistency between PRD, architecture, plan, and code. TRIGGER when user says "проверь документацию", "проверь код", "ревью", "review project", or before any commit touching more than 2 files. Returns BLOCKED / PASSED_WITH_WARNINGS / PASSED. See `## Trigger phrases` in body for full list.'
argument-hint: project path or specific document to review
license: MIT
context: fork
agent: code-reviewer
metadata:
  author: HiH-DimaN
  version: 1.2.0
  category: quality-assurance
  tags: [validation, quality-check, review, consistency]
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

## Instructions

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

- **Tier 1 (Critical)** — checks C1–C12 (and C-code-1, C-code-2 when source code exists). Failure of any single Critical check sets gate status to `BLOCKED`.
- **Tier 2 (Important)** — checks I1–I9 (and I-code-1, I-code-2). Failures produce warnings but the gate passes (`PASSED_WITH_WARNINGS`).
- **Tier 3 (Nice-to-have)** — checks N1–N4 (and N-code-1). Failures are informational only.

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
