---
name: project
description: 'Smart project CREATION router — routes to /kickstart, /blueprint, or /guide based on user scenario. For work on EXISTING code, use /task instead.'
argument-hint: project idea or description
license: MIT
allowed-tools: Read
metadata:
  author: HiH-DimaN
  version: 1.4.0
  category: project-creation
  tags: [router, workflow, project-creation, methodology]
---

# Project


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- хочу проект, новый проект, создай проект, создать приложение
- сделай сервис, сделай сайт, стартуем проект, начнём проект
- новый MVP, проект с нуля, хочу запустить
- build a project, start a project, new app, new service
- любой запрос на создание нового приложения/сайта/сервиса с нуля

You are the single entry point for all project **creation**. Your job is to understand what the user needs and route them to the right workflow.

**Important boundary (v1.4.0):** `/project` is for **new** projects — "от идеи до deploy" or "есть идея, нужен план". If the user wants to work on an **existing** codebase (tech debt, bug, refactor, add a feature, update docs, run review), use `/task` instead — it's the router for daily work on existing code. If a `/project` invocation receives a request that's clearly about an existing repo (user mentions current files, stack traces, recent commits, tech debt, «почини X в проекте»), redirect to `/task` in Step 2 without running /kickstart/blueprint/guide.

## Recommended model

**sonnet** — Router only — asks one routing question and dispatches. No code or doc generation. Sonnet is plenty.

Set via `/model {model}` before invoking this skill, or via the project's default model in `~/.claude/settings.json`.


## Instructions

### Step 1: Understand the request

Read what the user said: $ARGUMENTS

### Step 2: Check if this is actually an existing-project task

Before asking the routing question, scan `$ARGUMENTS` and the current context for **existing-project signals**:

- Mentions of specific files, modules, directories (e.g., `deploy.sh`, `apps/web/`)
- Stack traces, error messages, log fragments
- Phrases like «tech debt», «почини в проекте», «отрефактори», «обнови docs», «добавь тест к»
- Current cwd is a non-empty git repo with commits (run `git log --oneline -3` mentally)

If ANY of these match → **redirect to `/task`** and exit:

> «Похоже, задача по существующему коду, не по созданию нового проекта. Переключаюсь на `/task` — он знает про 12 daily-work скиллов (bugfix/refactor/doc/test/perf/review/...) и выберет правильный.»

Invoke `/task` via the Skill tool and stop. Do NOT ask the А/Б/В routing question when the task is clearly daily-work.

### Step 3: Determine the creation scenario

Only reached if Step 2 did NOT redirect. Ask the user ONE question:

"Какой вариант вам подходит?

**А) Полный цикл** — от идеи до работающего задеплоенного проекта. Я спланирую, напишу код, протестирую и задеплою.

**Б) Только планирование** — создам 6 документов (стратегия, архитектура, план, PRD, README, гайд). Код писать не буду. Подходит если хотите сначала согласовать план или отдать другому разработчику.

**В) У меня уже есть документация** — создам пошаговый гайд с промптами для Claude Code на основе ваших документов."

### Step 4: Route to the right creation workflow

Based on the answer:

**А) Полный цикл** → Execute /kickstart with the user's project description.

This will:
1. Ask clarifying questions about the project
2. Generate all documentation (STRATEGIC_PLAN, ARCHITECTURE, PLAN, PRD, README, GUIDE, CLAUDE.md)
3. Scaffold the project structure
4. Implement step by step (with automatic /test after each feature)
5. Deploy

Tell the user: "Начинаю полный цикл. Сейчас задам несколько вопросов, потом создам документацию и начну писать код."

**Б) Только планирование** → Execute /blueprint with the user's project description.

This will:
1. Ask clarifying questions
2. Generate 6 documents + CLAUDE.md + .gitignore
3. Stop without writing code

Tell the user: "Создаю документацию. После завершения вы сможете: просмотреть и скорректировать план, отдать другому разработчику, или сказать 'начинай реализацию' — и я продолжу по маршруту А."

**В) Есть документация** → Execute /guide with the project name.

This will:
1. Read existing docs (CLAUDE.md, PROJECT_ARCHITECTURE.md, IMPLEMENTATION_PLAN.md)
2. Generate CLAUDE_CODE_GUIDE.md with copy-paste prompts

Tell the user: "Читаю вашу документацию и создаю пошаговый гайд. Каждый шаг — готовый промпт, который можно скопировать и вставить в Claude Code."

### Step 5: After completion — offer next steps

**After А (полный цикл):** "Проект готов и задеплоен. Что дальше? Могу: добавить фичу, написать тесты (/test), проверить безопасность (security-guidance), оптимизировать (/perf)."

**After Б (планирование):** "Документация готова. Варианты: 'начинай реализацию' (перейду к маршруту А), 'создай гайд' (перейду к маршруту В), или скорректируйте документы вручную."

**After В (гайд):** "Гайд создан. Откройте CLAUDE_CODE_GUIDE.md и копируйте промпты по одному шагу. Или скажите 'начинай с шага 1' — и я буду выполнять шаги последовательно."

## Examples

### Example 1: Vague idea
User says: "хочу сделать сервис для репетиторов"

Actions:
1. Ask the routing question (А/Б/В)
2. User picks А → run /kickstart
3. Kickstart asks: тип репетиторов, функции, оплата, стек
4. Full cycle executes

### Example 2: Need approval first
User says: "мне нужно сначала план показать заказчику"

Actions:
1. Skip routing question — clearly scenario Б
2. Run /blueprint
3. Generate 6 documents
4. User reviews and shares with client

### Example 3: Existing project
User says: "у меня есть PROJECT_ARCHITECTURE.md, сделай гайд"

Actions:
1. Skip routing question — clearly scenario В
2. Run /guide
3. Generate CLAUDE_CODE_GUIDE.md from existing docs

## Troubleshooting

### User doesn't know which scenario to pick
Recommend А (full cycle) — it includes planning anyway. User can stop after documentation phase if they want.

### User wants to switch scenarios mid-way
Fully supported. The skills auto-detect existing documentation:

- **Б → А**: User says "начинай реализацию" → run /kickstart. It will detect existing docs, validate with /review, skip to scaffolding/implementation.
- **В → А**: User says "начинай реализацию" → run /kickstart. It will detect existing guide and docs, supplement if needed, then implement.
- **В → Б**: User says "создай полную документацию" → run /blueprint. It will detect existing guide and generate missing docs consistent with it.

No work is lost when switching. Existing documents are reused, not regenerated.

### Project is too complex for one pass
Suggest splitting into MVP phases. /blueprint first, then /kickstart for Phase 1 only.
