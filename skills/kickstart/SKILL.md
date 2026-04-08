---
name: kickstart
description: 'Generate a complete project from idea — architecture, plans, docs, code, tests, deploy. Full lifecycle, one shot. TRIGGER when user says "создай проект", "новый проект", "запили проект целиком", "от идеи до деплоя". Usually invoked via /project router. See `## Trigger phrases` in body for full list.'
argument-hint: project idea or description
disable-model-invocation: true
allowed-tools: "Read Write Edit Glob Grep Bash(git:*) Bash(mkdir:*) Bash(npm:*) Bash(pnpm:*) Bash(docker:*) Bash(pytest:*) Bash(go:*) Bash(cargo:*)"
license: MIT
metadata:
  author: HiH-DimaN
  version: 1.4.0
  category: project-creation
  tags: [scaffolding, mvp, full-lifecycle, deployment]
---


# Kickstart


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- хочу проект, новый проект, создай проект, запили проект, сделай проект целиком
- от идеи до деплоя, полный цикл, end-to-end проект
- start a project, build it from scratch, end-to-end
- любой запрос на создание законченного работающего продукта

## Recommended model

**opus** — Generates an entire project end-to-end. Opus is strongly recommended; Sonnet falls back to Lite mode automatically. Haiku is refused at Phase -1.

Set via `/model {model}` before invoking this skill, or via the project's default model in `~/.claude/settings.json`.


## Instructions

### Phase -1: Detect model and select mode (Lite vs Full)

Before starting, determine which mode to use:

**Detection:**
- If running on Opus → **Full mode** (default, recommended)
- If running on Sonnet → **Lite mode** (auto-fallback) and warn the user
- If running on Haiku → refuse: "Этот скилл генерирует целый проект и требует Sonnet или Opus. Haiku не справится. Переключитесь (`/model sonnet` или `/model opus`)."
- If user passes `--lite` flag → **Lite mode** (explicit)
- If user passes `--full` flag → **Full mode** (explicit)

**Mode differences:**

| Aspect | Full mode | Lite mode |
|---|---|---|
| Documentation phase | 7 documents (Phase 2) | 4 documents (skip strategic plan + delegate guide to /guide later) |
| Implementation plan | 8–12 steps with time estimates | 4–6 steps without estimates |
| Quality Gate 1 (review rubric) | All Critical + all Important must pass | All Critical only (Important warnings allowed) |
| Quality Gate 2 (per-step) | Strict — code must match architecture, tests must pass | Relaxed — tests must pass, architecture-mismatch only warned |
| Deployment phase | Full (Docker + nginx + healthcheck + verify) | Simplified (one platform of user's choice, basic config) |

Tell the user which mode you selected:
- Full: silent (default)
- Lite (auto): "⚠️ Запускаю в режиме Lite (Sonnet detected). Качество планирования ниже, чем в Full на Opus. Если можете — переключитесь на Opus и повторите. Иначе продолжаю в Lite."
- Lite (explicit): "Запускаю в Lite по вашему запросу."

In all subsequent phases, obey the mode setting.

### Phase 0: Detect Existing Documentation

Before starting, check if project documentation already exists:

```
Look for these files in the current directory and docs/:
- STRATEGIC_PLAN.md
- PROJECT_ARCHITECTURE.md
- IMPLEMENTATION_PLAN.md
- PRD.md
- CLAUDE_CODE_GUIDE.md
- CLAUDE.md
```

**If ALL core documents exist (ARCHITECTURE + IMPLEMENTATION_PLAN + PRD):**
- Tell the user: "Обнаружена существующая документация. Пропускаю фазы планирования и перехожу к реализации."
- Run /review on existing documents
- If status is `PASSED` or `PASSED_WITH_WARNINGS` → skip to Phase 3 (Scaffolding) or Phase 4 (Implementation) if project is already scaffolded; show warnings if any
- If status is `BLOCKED` → show the failing Critical checks, ask: "Документация не проходит критические проверки. Исправить автоматически или хотите скорректировать вручную?"

**If SOME documents exist (partial documentation):**
- Tell the user which documents found and which are missing
- Ask: "Дополнить недостающие документы или начать с нуля?"
- If supplement → generate only missing documents, then proceed
- If from scratch → proceed normally from Phase 1

**If NO documents exist:**
- Proceed normally from Phase 1

**If project code already exists (src/, app/, package.json with dependencies):**
- Tell the user: "Обнаружен существующий код. Проверяю состояние проекта."
- Read CLAUDE.md status table if exists
- Find the last completed step
- Ask: "Последний завершённый шаг: [N]. Продолжить с шага [N+1]?"
- Resume from that step

### Phase 1: Ideation and Research

1. **Clarify the idea** — ask 3-5 key questions if vague (see `references/phase-checklist.md`)

2. **Validate each clarifying answer before proceeding** — new in v1.4.0. Vague answers upstream become vague plans downstream (GIGO). Apply this check to every user answer:

   **Mark an answer as VAGUE if any of these apply:**
   - Contains only: "может быть", "не знаю", "всё равно", "на твоё усмотрение", "сам реши", "idk", "whatever", "doesn't matter"
   - Is < 3 words for an open-ended question (acceptable for yes/no)
   - Contradicts a previous answer in the same session
   - References something that doesn't exist ("use our existing DB" when no DB was mentioned before)

   **When an answer is VAGUE, ask a targeted follow-up with examples:**

   > "Ваш ответ на [вопрос] размытый. Мне нужна конкретика, чтобы не сгенерировать мусорный план. Приведу примеры:
   >
   > ❌ Плохо: «сам реши какую БД»
   > ✅ Хорошо: «PostgreSQL, потому что нужны транзакции и JSONB для полей конфига»
   > ✅ Хорошо: «SQLite — данных мало, простой single-user app»
   > ✅ Хорошо: «не знаю — задай наводящие вопросы и подскажи что лучше для моего кейса»
   >
   > Переформулируйте, пожалуйста."

   If the user explicitly says "не знаю, подскажи" — that's a VALID answer. Switch to advisor mode: ask 2-3 narrow technical questions to extract their actual constraints (data volume, concurrency, team familiarity, budget), then propose a default with reasoning.

   Maximum 2 follow-ups per original question. If the user still won't commit, record their preference as "default — user deferred" in `CLAUDE.md` and pick the methodology's default. Do not loop indefinitely.

3. **Pre-generation review** — after all clarifying questions are answered, before Phase 2:
   - Summarize the captured clarifications in a short structured block:
     ```
     - Project type: ...
     - Users / scale: ...
     - Auth: ...
     - Data model hints: ...
     - Deployment target: ...
     - Budget / deadline: ...
     ```
   - Ask: "Вот как я понял задачу. Всё верно? (да / поправь такой-то пункт)"
   - Wait for explicit confirmation before generating docs.
   - This is a lightweight sanity check, NOT a full `/review` — it's on clarifications (text), not on documents (which don't exist yet).

4. **Competitive analysis** — outline existing solutions and differentiators

5. **Define MVP scope** — cut to the smallest valuable product

### Phase 2: Documentation Generation
Create these files in order:

1. **STRATEGIC_PLAN.md** — strategy, competitors, budget, KPIs, risks
2. **PRD.md** — user stories, requirements (P0/P1/P2), kill criteria
3. **PROJECT_ARCHITECTURE.md** — stack, DB schema (all tables), API (all endpoints), Docker, auth
4. **IMPLEMENTATION_PLAN.md** — 8-12 steps with specific files and verification
5. **CLAUDE.md** — project context, rules, status table
6. **README.md** — quick start, stack, structure
7. **CLAUDE_CODE_GUIDE.md** — generate using /guide skill

Consult `references/phase-checklist.md` for quality gates each document must pass.

### Phase 3: Project Scaffolding
1. **Initialize** — directory structure, package.json / pyproject.toml, configs
2. **Tooling** — linter, formatter, testing framework
3. **Base files** — entry points, routes, models, types
4. **Environment** — .env.example with all variables
5. **Docker** — Dockerfile + docker-compose.yml
6. **Git** — .gitignore, initial commit

### Phase 4: Implementation
Follow IMPLEMENTATION_PLAN.md phase by phase:
1. Implement each task from the current step
2. **After each completed feature** — invoke /test to generate tests for the new code
3. Run code-review after each significant feature
4. If a test or review finds issues — fix before moving to the next step
5. Commit after each passing step: "step-N: description"
6. Update CLAUDE.md status table (step N ✅)
7. Update docs if architecture changes

### Phase 5: Deployment
1. **Ask the user:** "Куда деплоим? (Docker + VPS / Vercel / Railway / другое)"
2. Based on the answer:
   - **Docker + VPS:** Create Dockerfile for each service, docker-compose.yml, nginx.conf, .env.example. Provide deployment commands:
     ```
     docker-compose build && docker-compose up -d
     curl http://YOUR_IP/api/health
     ```
   - **Vercel:** Create vercel.json, configure environment variables, run `vercel deploy`
   - **Railway / Render / Fly.io:** Create platform-specific config, Procfile if needed
3. Create health-check endpoint (`/api/health` → 200 OK)
4. Verify deployment: all services running, health check passes, main user flow works
5. Update README.md with deployment instructions for the chosen platform

## Examples

### Example 1: Full SaaS project
User says: "создай проект — платформа для онлайн-курсов"

Actions:
1. Clarify: видеохостинг свой или YouTube? Оплата — ЮKassa или Stripe?
2. Generate 7 documents (strategic plan through guide)
3. Scaffold: FastAPI + Vue + PostgreSQL + Redis
4. Implement 10 steps: auth → courses → lessons → video → payments → dashboard
5. Deploy via Docker + Nginx

Result: Working deployed MVP with auth, course management, payments.

### Example 2: Simple bot
User says: "новый проект — Telegram бот для записи к парикмахеру"

Actions:
1. Simplified flow: 5 documents (no complex architecture)
2. Scaffold: aiogram + PostgreSQL
3. Implement 6 steps: bot setup → calendar → booking → notifications → admin → deploy

Result: Working bot with booking, calendar, and admin notifications.

## Troubleshooting

### User wants everything at once
Remind: MVP first. List what's in scope and what's deferred. Show the timeline.

### Tech stack conflict with CLAUDE.md
Ask the user. Their project may require a different stack than the global default.

### Build fails after scaffolding
Check: missing dependencies, wrong versions, TypeScript strict mode issues. Fix before proceeding to Phase 4.

## Rules

- Ask before making major tech stack decisions
- Prefer the user's known stack from CLAUDE.md when applicable
- Keep MVP minimal — ship fast, iterate later
- Every phase ends with a working state
- Update IMPLEMENTATION_PLAN.md with progress as you go


### Quality Gate 1: Plan Review (after Phase 2, before Phase 3)

**Automatic validation:**
1. Run /review automatically on generated documents
2. Read the status from the report:
   - `BLOCKED` → fix the failing Critical checks automatically (or ask user if multiple), then re-run /review on those checks
   - `PASSED_WITH_WARNINGS` → continue, but include warnings in the user summary
   - `PASSED` → continue silently
3. Do NOT proceed past this gate if status remains `BLOCKED` after one fix attempt — escalate to the user

**User approval (MANDATORY):**
4. Show the user a summary of the generated plan:
   - Project type and tech stack
   - Database tables count and main entities
   - API endpoints count and main routes
   - Implementation steps count and estimated timeline
   - Review status (`PASSED` / `PASSED_WITH_WARNINGS`) + warning list if any
   - Derived score (informational)
5. Ask: "Вот план проекта. Всё устраивает или хотите что-то изменить?"
6. Wait for explicit user approval before proceeding to Phase 3
7. If user requests changes — apply them, re-run /review, show updated plan

Do NOT proceed to scaffolding without user confirmation.

### Quality Gate 2: Step-by-Step Code Review (during Phase 4)

After EACH implementation step:

1. **Verify working code:**
   - No syntax errors (file parses correctly)
   - No import errors (all dependencies resolved)
   - Application starts without crashes

2. **Run /test** — generate and execute tests for new code

3. **Code vs Architecture check:**
   - New models match database schema in PROJECT_ARCHITECTURE.md
   - New endpoints match API spec in PROJECT_ARCHITECTURE.md
   - Naming is consistent with existing code
   - No hardcoded values that should be in .env

4. **Decision:**
   - All checks pass → commit, update CLAUDE.md status, proceed to next step
   - Tests fail → fix and re-test (max 3 attempts)
   - Architecture mismatch → fix code OR update architecture doc (ask user which)
   - 3 consecutive failures → STOP and ask user for guidance

5. **Step summary** — after each step show:
   - What was implemented
   - Tests: X passed, Y failed
   - Files created/modified
   - Next step preview

This ensures every step is verified before moving forward. No accumulated technical debt.
