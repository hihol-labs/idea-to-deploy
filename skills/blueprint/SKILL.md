---
name: blueprint
description: 'Generate project documentation set (strategic plan, architecture, implementation plan, PRD, README, guide). Planning only, no code.'
argument-hint: project idea or description
license: MIT
allowed-tools: Read Write Edit Glob Grep
context: fork
agent: architect
metadata:
  author: HiH-DimaN
  version: 1.3.1
  category: project-planning
  tags: [documentation, architecture, planning, prd]
---


# Blueprint


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- спланируй проект, создай документацию для проекта, подготовь blueprint
- спроектируй, архитектура проекта, техническое задание, ТЗ, PRD
- только планирование без кода, design the system, system design
- набор документов для разработчика, передать другому подрядчику

## Recommended model

**opus** — Generates 6 documents (or 4 in Lite). Opus produces materially better strategic plans, architecture decisions, and PRDs. Sonnet falls back to Lite mode automatically.

Set via `/model {model}` before invoking this skill, or via the project's default model in `~/.claude/settings.json`.


## Instructions

### Step -1: Detect model and select mode (Lite vs Full)

Before starting, determine which mode to use:

**Detection:**
- If running on Opus → **Full mode** (default)
- If running on Sonnet → **Lite mode** (auto-fallback)
- If running on Haiku → refuse and ask user to switch model: "Этот скилл требует Sonnet или Opus. Haiku не справится с генерацией качественных документов. Переключитесь на Sonnet (`/model sonnet`) и повторите."
- If user passes `--lite` flag in $ARGUMENTS → **Lite mode** (explicit override)
- If user passes `--full` flag → **Full mode** (explicit override)

**Mode differences:**

| Aspect | Full mode | Lite mode |
|---|---|---|
| Documents generated | 6 (STRATEGIC_PLAN + ARCHITECTURE + IMPLEMENTATION_PLAN + PRD + README + CLAUDE_CODE_GUIDE) | 4 (PROJECT_ARCHITECTURE + IMPLEMENTATION_PLAN + PRD + README) |
| Strategic plan | Required, 3+ competitors, budget, KPIs, risks | Skipped — focus on technical |
| Architecture depth | All Critical + all Important rubric checks | All Critical only |
| Implementation steps | 8–12 with time estimates | 4–6 without estimates |
| User stories required | 5+ with acceptance criteria for P0 | 3+ without explicit acceptance criteria |
| CLAUDE_CODE_GUIDE | Generated | User can run /guide separately later |

**Why this exists:** Sonnet produces lower-quality output when asked to generate the full 6-document set in one shot. Lite mode reduces scope so Sonnet can deliver something usable instead of degrading silently. The user can always run `/blueprint --full` later or `/kickstart` to fill the gaps.

Tell the user which mode you selected before proceeding:
- Full mode: silent (default behavior)
- Lite mode (auto): "Запускаю в режиме Lite (Sonnet detected). Сгенерирую 4 документа вместо 6. Для полного режима используйте Opus или явный флаг `--full`."
- Lite mode (explicit): "Запускаю в режиме Lite по вашему запросу."

In all subsequent steps where the instructions say "generate 6 documents", obey the mode: Full = 6, Lite = 4.

### Step 0: Detect Existing Documentation

Before generating, check if any project documents already exist:

```
Look for: STRATEGIC_PLAN.md, PROJECT_ARCHITECTURE.md, IMPLEMENTATION_PLAN.md, PRD.md, README.md, CLAUDE_CODE_GUIDE.md
```

**If some documents already exist:**
- List found documents to the user
- Ask: "Найдены существующие документы: [list]. Обновить их или создать заново?"
- If update → read existing docs, improve and supplement them
- If recreate → generate from scratch

**If CLAUDE_CODE_GUIDE.md exists but other docs don't (coming from route C):**
- Read the guide to understand project context
- Generate missing documents consistent with the existing guide

### Step 1: Clarify the idea
If the description is vague, ask:
- Что делает продукт? Для кого?
- Какую проблему решает?
- Бизнес-модель / монетизация?
- Предпочтительный стек? (если нет — использовать стек из CLAUDE.md)
- Ограничения (бюджет, сроки, платформа)?

### Step 1.5: Product Discovery & Feature Prioritization (NEW in v1.17.0)

After clarifying the idea, before generating documents, run a lightweight product discovery phase. This ensures that the generated documents are grounded in real priorities, not just a wishlist.

**1.5.1 — Identify features and scope**

Based on the clarified idea, list all features as a flat list. Then categorize each feature using **MoSCoW** prioritization:

| Feature | MoSCoW | Rationale |
|---------|--------|-----------|
| {feature} | **Must** / **Should** / **Could** / **Won't** | Why this priority |

**MoSCoW rules:**
- **Must** — MVP cannot ship without this. If removed, the product has no value proposition
- **Should** — Important, expected by users, but MVP can launch without it (Week 2-3 addition)
- **Could** — Nice to have, adds polish. Only if time permits
- **Won't** — Explicitly out of scope for this version. Prevents scope creep

**1.5.2 — RICE scoring for Must/Should features (Full mode only)**

For each Must and Should feature, calculate a **RICE score** to determine implementation order:

| Feature | Reach (1-10) | Impact (1-5) | Confidence (%) | Effort (person-days) | RICE Score |
|---------|-------------|-------------|---------------|---------------------|------------|
| {feature} | {R} | {I} | {C} | {E} | R×I×C/E |

- **Reach** — how many users will this affect in the first month (1=few, 10=all)
- **Impact** — how much it moves the needle for each user (1=minimal, 5=massive)
- **Confidence** — how sure you are about R, I, and E estimates (100%=measured, 50%=guess)
- **Effort** — person-days to implement (estimate based on architecture complexity)
- **RICE Score** = (Reach × Impact × Confidence) / Effort

Sort features by RICE score descending. This order feeds into IMPLEMENTATION_PLAN step ordering.

**1.5.3 — Validate with user**

Present the MoSCoW table (and RICE table in Full mode) to the user:
- "Вот приоритизация фич. Согласны? Хотите переместить что-то между категориями?"
- Wait for confirmation before proceeding to document generation
- If user disagrees, adjust priorities and re-present

**1.5.4 — Feed into documents**

The prioritization output directly shapes:
- **STRATEGIC_PLAN.md** → Section "Feature Roadmap" (new, see templates)
- **PRD.md** → P0 = Must, P1 = Should, P2 = Could. User stories ordered by RICE score
- **IMPLEMENTATION_PLAN.md** → Steps ordered by RICE score (highest-value features first)

In **Lite mode**, skip RICE (step 1.5.2) and use only MoSCoW. The MoSCoW table is still mandatory.

### Step 2: Generate 6 documents
Each document builds on the previous one. Create all files in the project root or docs/ folder.

Before writing, consult `references/document-templates.md` for the exact structure and level of detail expected in each document.

**Order:**
1. **STRATEGIC_PLAN.md** — стратегия, конкуренты, бюджет, KPIs, риски, Definition of Done
2. **PROJECT_ARCHITECTURE.md** — стек, БД (все таблицы с полями), API (все эндпоинты), Docker, auth, деплой
3. **IMPLEMENTATION_PLAN.md** — 8-12 шагов, каждый с конкретными файлами и проверками, Architectural Runway
4. **PRD.md** — user stories, функциональные требования (P0/P1/P2), kill criteria
5. **README.md** — быстрый старт за 30 секунд, стек, структура
6. **CLAUDE_CODE_GUIDE.md** — готовые промпты для каждого шага (формат /guide)

#### Step 2.1: Architecture Decision Trees (NEW in v1.18.0)

When generating PROJECT_ARCHITECTURE.md, do NOT present only one architecture. Generate **2-3 architectural variants** with trade-offs for the user to choose from:

```markdown
## Architecture Variants

### Variant A: {name} (Recommended)
- **Approach:** {description}
- **Pros:** {list}
- **Cons:** {list}
- **Best for:** {scenario}
- **Estimated complexity:** Low / Medium / High

### Variant B: {name}
- **Approach:** {description}
- **Pros:** {list}
- **Cons:** {list}
- **Best for:** {scenario}
- **Estimated complexity:** Low / Medium / High

### Variant C: {name} (if applicable)
...

### Recommendation
Вариант A рекомендуется потому что: {rationale with reference to project constraints}.
```

**When to offer variants:**
- Database choice (PostgreSQL vs MongoDB vs SQLite)
- Architecture style (monolith vs microservices vs modular monolith)
- API style (REST vs GraphQL vs gRPC)
- Auth approach (session vs JWT vs OAuth2)
- Deployment (VPS vs Kubernetes vs serverless)

**When NOT to offer variants** (obvious choice):
- Solo developer + MVP → monolith (don't waste time debating)
- Telegram bot → aiogram (don't debate frameworks)
- User explicitly specified the stack

Present variants to user and wait for choice before writing full architecture.

#### Step 2.5: Adversarial Architecture Debate (NEW in v1.18.0, Full mode only)

After the Architect generates the chosen architecture variant, invoke the **Devil's Advocate** subagent to stress-test it. This prevents anchoring bias and ensures the architecture survives scrutiny.

**Protocol:**

1. **Architect proposes** — full architecture document (from Step 2)
2. **Devil's Advocate challenges** — invoke `agents/devils-advocate.md` via Agent tool with the proposed architecture. The agent returns:
   - Strengths acknowledged
   - 3-7 challenges with alternatives and trade-offs
   - Verdict: APPROVE / APPROVE WITH CONDITIONS / REQUEST REVISION
3. **Resolution:**
   - If APPROVE → proceed with architecture as-is
   - If APPROVE WITH CONDITIONS → address the conditions, update architecture, note changes
   - If REQUEST REVISION → revise architecture based on feedback, re-present to user
4. **Document the debate** — add a section to PROJECT_ARCHITECTURE.md:

```markdown
## Architecture Decision Record (ADR)

### Debate Summary
The architecture was reviewed by Devil's Advocate agent.

**Verdict:** {APPROVE / APPROVE WITH CONDITIONS / REQUEST REVISION}

**Challenges raised:**
1. {challenge} → **Resolution:** {how addressed or why accepted}
2. {challenge} → **Resolution:** {how addressed or why accepted}
...

**Alternatives considered and rejected:**
- {alternative} — rejected because {reason}
```

**Lite mode:** Skip adversarial debate (saves tokens). User can run it manually by saying "проверь архитектуру" after /blueprint completes.

#### Step 2.6: SAFe-Inspired Patterns (NEW in v1.18.0)

Incorporate these patterns from Scaled Agile Framework where applicable:

**Definition of Done (DoD)** — add to STRATEGIC_PLAN.md:
```markdown
## Definition of Done

A feature is "Done" when:
- [ ] Code written and compiles without errors
- [ ] Unit tests pass (coverage >= {threshold}%)
- [ ] Integration tests pass (if applicable)
- [ ] Code review passed (/review score >= 8/10)
- [ ] Documentation updated (README, API docs)
- [ ] No known Critical/High security issues (/security-audit)
- [ ] Deployed to staging and manually verified
```

**Architectural Runway** — add to IMPLEMENTATION_PLAN.md:
```markdown
## Architectural Runway

Infrastructure and architecture work that must be completed BEFORE feature development:

| # | Item | Why first | Effort |
|---|------|-----------|--------|
| 1 | Database schema + migrations | All features depend on data model | 1 day |
| 2 | Auth system | Most endpoints require authentication | 1 day |
| 3 | CI/CD pipeline | Need automated testing before adding features | 0.5 day |
| 4 | Docker setup | Consistent dev environment | 0.5 day |
```

**PI Planning cadence** — add to IMPLEMENTATION_PLAN.md (for projects with >8 steps):
```markdown
## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|--------|-------|------|----------|
| Sprint 1 | Steps 1-3 | Core infrastructure + data model + auth | 1 week |
| Sprint 2 | Steps 4-6 | Core business logic + API endpoints | 1 week |
| Sprint 3 | Steps 7-9 | Frontend + integration + testing | 1 week |
| Sprint 4 | Steps 10-12 | Deployment + hardening + polish | 1 week |
```

### Step 3: Generate CLAUDE.md
Project memory file with: контекст, правила, стек, структура, статус-таблица шагов. Обязательно включить правило: «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save» (обеспечивает непрерывность между сессиями).

### Step 4: Generate .gitignore
Based on the tech stack.

### Step 5: Verify completeness
Show checklist with ✅ for each completed document.

## Examples

### Example 1: SaaS product
User says: "спланируй SaaS для управления клиниками"

Actions:
1. Clarify: тип клиник, количество пользователей, интеграции (1С, ЕМИАС?)
2. Generate 6 docs with focus on: запись пациентов, расписание врачей, медкарты
3. Architecture: PostgreSQL + FastAPI + Vue, таблицы patients/doctors/appointments/records

Result: 8 files in project root, ready to execute with `/kickstart` or manually.

### Example 2: Telegram bot
User says: "подготовь документацию для бота доставки еды"

Actions:
1. Clarify: aiogram vs grammY, платёжная система, зона доставки
2. Generate 6 docs with focus on: каталог, корзина, оплата, трекинг курьера
3. Simplified architecture: one service + bot + DB

Result: 8 files, IMPLEMENTATION_PLAN has 8 steps (bot simpler than full SaaS).

## Self-validation

Before presenting documents to user, verify:
- [ ] All 5 documents generated (strategic plan, architecture, PRD, implementation plan, README)
- [ ] Each document has all required sections per references/document-templates.md
- [ ] Architecture references the correct tech stack from user input
- [ ] PRD user stories are specific to the domain, not generic
- [ ] Implementation plan phases are ordered by dependency
- [ ] If DISCOVERY.md exists, its priorities are reflected in the plan
- [ ] No placeholder text ("TODO", "TBD", "Lorem ipsum") remains

## Troubleshooting

### User doesn't know the tech stack
Use the default stack from the global CLAUDE.md. If none defined, recommend based on project type.

### Project is too large for 12 steps
Split into phases (MVP1, MVP2). Blueprint covers only MVP1. Note deferred features in PRD "Out of scope".

### Documents contradict each other
Architecture is the source of truth. If PRD conflicts with architecture, update PRD.

## Rules

- Match the language of the user's request: if the user wrote in Russian, generate Russian docs; if English, English docs; mixed — pick the dominant one and ask if unsure
- Будь максимально конкретен: имена файлов, таблицы с полями и типами, эндпоинты с параметрами
- Не пиши абстракций типа "создай компоненты" — пиши конкретные пути
- Используй стек пользователя из CLAUDE.md когда применимо
- Каждый документ ссылается на другие
- Не генерируй код — только документацию


### Step 6: Self-validation

Before showing the final result, verify minimum quality:

**Minimum requirements for STRATEGIC_PLAN.md:**
- At least 3 competitors analyzed
- Budget estimation present
- At least 3 risks identified
- Feature Roadmap section with MoSCoW table (at least 5 features categorized)
- RICE scoring table present (Full mode only, at least 3 Must/Should features scored)

**Minimum requirements for PROJECT_ARCHITECTURE.md:**
- At least 3 database tables with fields and types
- At least 5 API endpoints with methods and paths
- Auth mechanism described (not just "JWT")
- Deployment target specified

**Minimum requirements for IMPLEMENTATION_PLAN.md:**
- At least 6 steps
- Each step has specific files listed
- Each step has verification command

**Minimum requirements for PRD.md:**
- At least 5 user stories
- P0/P1/P2 priorities assigned
- Acceptance criteria for P0 stories

If any requirement is not met, fix it before presenting to the user. If you cannot meet a requirement, explicitly warn the user:
"⚠️ Внимание: [document] не соответствует минимальным требованиям качества: [reason]. Рекомендуется использовать модель Opus для лучшего результата."
