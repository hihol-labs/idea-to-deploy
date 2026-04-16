---
name: autopilot
description: 'Auto-pipeline: runs the full methodology chain (discover → blueprint → kickstart → review → test) with minimal human intervention. Inspired by GSD auto mode.'
argument-hint: project idea or description (same as /kickstart)
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash Skill
context: fork
disable-model-invocation: true
metadata:
  author: HiH-DimaN
  version: 1.18.0
  category: workflow
  tags: [autopilot, auto-mode, pipeline, full-lifecycle, gsd-inspired]
---


# Autopilot


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- автопилот, запусти всё, сделай от начала до конца
- полный автопилот, автоматический режим
- autopilot, auto mode, run everything, full auto
- от идеи до деплоя автоматически, hands-free
- запусти pipeline целиком, весь конвейер


## Recommended model

**opus** — Full pipeline requires deep reasoning across multiple phases. Sonnet can run Lite mode (skip /discover, shorter /blueprint).

Set via `/model {model}` before invoking this skill, or via the project's default model in `~/.claude/settings.json`.


## Instructions

### Step 0: Pre-flight validation

Before starting the pipeline:

1. **Check model** — Opus → Full mode, Sonnet → Lite mode, Haiku → refuse
2. **Check working directory** — must be empty or a git repo without uncommitted changes
3. **Collect input** — the user MUST provide at minimum:
   - **What** — what the product does (one sentence)
   - **Who** — target users
   - **Stack** — preferred tech stack (or "выбери сам")

If any of these are missing, ask ONCE. Do not proceed without all three.

4. **Confirm the pipeline plan** with the user:

```
🚀 Autopilot pipeline:
  Phase 1: /discover — market analysis, competitors, personas, prioritization
  Phase 2: /blueprint — architecture, PRD, implementation plan
  Phase 3: /kickstart — code generation, tests, deployment
  Phase 4: /review — code review + meta-review
  Phase 5: /test — test coverage verification

Estimated: 15-30 min depending on complexity.
Proceed? (да/нет)
```

Wait for explicit confirmation before proceeding.

### Step 1: Discovery phase

Invoke `/discover` with the user's input:
- Pass What/Who/Why from user
- Use `--full` mode on Opus, `--lite` on Sonnet
- Wait for DISCOVERY.md to be generated
- **Checkpoint:** Run `/session-save` after this phase

**On error:** Report to user, ask if they want to skip and proceed to /blueprint

### Step 2: Blueprint phase

Invoke `/blueprint` with DISCOVERY.md as input:
- /blueprint Step 1.5 auto-detects DISCOVERY.md
- Wait for all 5 documents (strategic plan, architecture, PRD, implementation plan, README)
- **Checkpoint:** Run `/session-save` after this phase

**On error:** Report to user, ask if they want to retry or skip

### Step 3: Kickstart phase

Invoke `/kickstart` with the generated plans:
- /kickstart auto-detects architecture + implementation plan
- This is the longest phase — code generation, tests, deployment config
- **Checkpoint:** Run `/session-save` after each kickstart sub-phase (Phase 2, 3, 4)

**On error:** This is the most error-prone phase. Report to user with specific error. Do NOT auto-retry more than once.

### Step 4: Review phase

Invoke `/review` on the generated code:
- Must score 8+/10 to proceed
- If <8: fix issues automatically, re-review (max 2 iterations)
- **Checkpoint:** Run `/session-save` after review

**On score <8 after 2 iterations:** Report to user, list remaining issues, ask for guidance

### Step 5: Test verification

Invoke `/test` to verify test coverage:
- Ensure tests pass
- Ensure minimum coverage thresholds
- **Final checkpoint:** Run `/session-save` with full pipeline summary

### Step 6: Pipeline complete

Report to user:

```
✅ Autopilot pipeline complete!

Phase 1: /discover — DISCOVERY.md ✅
Phase 2: /blueprint — 5 documents ✅
Phase 3: /kickstart — code + tests + deploy ✅
Phase 4: /review — score X/10 ✅
Phase 5: /test — X tests passing ✅

Total files: N
Total commits: N
Branch: feature/...

Next steps:
- Review generated code
- Push to remote: `git push -u origin <branch>`
- Create PR: `gh pr create`
```


## Examples

### Example 1: Full autopilot for a SaaS project
User says: "Автопилот: сделай CRM для стоматологии. Стек: FastAPI + Vue + PostgreSQL. Аудитория: администраторы клиник."

Actions:
1. Confirm pipeline plan with user
2. /discover → DISCOVERY.md (TAM/SAM/SOM, 5 конкурентов, 3 персоны, RICE)
3. /session-save checkpoint
4. /blueprint → 5 документов (strategic plan, architecture, PRD, implementation plan, README)
5. /session-save checkpoint
6. /kickstart → code + tests + docker-compose + nginx
7. /session-save checkpoint
8. /review → score 9/10
9. /test → 24 tests passing
10. Final /session-save with full summary

### Example 2: Lite autopilot for a Telegram bot
User says: "autopilot: Telegram bot for gym class scheduling. Stack: Python + aiogram + SQLite."

Actions (Lite mode — Sonnet):
1. Confirm pipeline plan (note: Phase 1 skipped in Lite)
2. /blueprint Lite → 5 shorter documents
3. /session-save checkpoint
4. /kickstart → bot code + tests + Dockerfile
5. /session-save checkpoint
6. /review → score 8/10, 1 iteration fix
7. /test → 12 tests passing
8. Final report


## Lite mode (Sonnet)

Skip Phase 1 (/discover). Start directly from /blueprint with user's input.
/blueprint runs in Lite mode (shorter documents).
/kickstart runs normally.
/review and /test run normally.


## Rules

- NEVER proceed to the next phase if the current phase failed
- ALWAYS checkpoint with /session-save between phases (crash resilience)
- ALWAYS ask for user confirmation before starting the pipeline
- If any phase takes longer than expected, report progress to the user
- The user can interrupt at any time — respect interruptions immediately
- Do not combine phases — run them sequentially for clarity
- Each phase should be a separate skill invocation, not inline execution
- Match the language of the user's original request


## Self-validation

Before reporting pipeline complete, verify:
- [ ] DISCOVERY.md exists (Full mode only)
- [ ] Architecture + PRD + Implementation plan exist
- [ ] Code compiles / lints without errors
- [ ] Tests pass
- [ ] /review score >= 8/10
- [ ] /session-save was called at least once

If any check fails, report which phases succeeded and which need attention.


## Troubleshooting

**Pipeline stalls at a phase.**
Check if the skill requires user input. Some skills (/discover) ask clarifying questions. In autopilot mode, provide reasonable defaults but note what was assumed.

**User wants to skip a phase.**
Allowed. Mark the phase as "skipped" and proceed. The final report should note skipped phases.

**Context window filling up.**
This is the biggest risk for autopilot. After each phase, the context grows significantly. If the context-aware hook fires a warning, recommend the user restart with `/kickstart` directly (skip discovery/blueprint) in a fresh session.

**Model downgrade mid-pipeline.**
If the user switches to Sonnet mid-pipeline, auto-switch to Lite mode for remaining phases. Warn that quality may be lower.
