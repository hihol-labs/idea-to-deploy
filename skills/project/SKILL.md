---
name: project
description: Smart project creation router — determines the best workflow based on user needs and guides through the entire process. Single entry point for all project creation scenarios. TRIGGER when user says "хочу проект", "новый проект", "создай проект", "создать приложение", "сделай сервис", "сделай сайт", "стартуем проект", "начнём проект", "новый MVP", "проект с нуля", "хочу запустить", "build a project", or any request that involves creating a new application/site/service from scratch. ALWAYS prefer this router over going directly into code — it asks 1–2 questions and picks /kickstart, /blueprint, or /guide.
argument-hint: project idea or description
license: MIT
effort: medium
metadata:
  author: HiH-DimaN
  version: 1.0.0
  category: project-creation
  tags: [router, workflow, project-creation, methodology]
---

# Project

You are the single entry point for all project creation. Your job is to understand what the user needs and route them to the right workflow.

## Instructions

### Step 1: Understand the request

Read what the user said: $ARGUMENTS

### Step 2: Determine the scenario

Ask the user ONE question to determine their scenario:

"Какой вариант вам подходит?

**А) Полный цикл** — от идеи до работающего задеплоенного проекта. Я спланирую, напишу код, протестирую и задеплою.

**Б) Только планирование** — создам 6 документов (стратегия, архитектура, план, PRD, README, гайд). Код писать не буду. Подходит если хотите сначала согласовать план или отдать другому разработчику.

**В) У меня уже есть документация** — создам пошаговый гайд с промптами для Claude Code на основе ваших документов."

### Step 3: Route to the right workflow

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

### Step 4: After completion — offer next steps

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
