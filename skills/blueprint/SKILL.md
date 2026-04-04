---
name: blueprint
description: Generate complete project documentation set (6 files) — strategic plan, architecture, implementation plan, PRD, README, Claude Code guide. Planning only, no code. Use when user says "спланируй проект", "создай документацию для проекта", "подготовь blueprint", or needs project planning without coding.
argument-hint: project idea or description
license: MIT
effort: high
metadata:
  author: HiH-DimaN
  version: 1.0.0
  category: project-planning
  tags: [documentation, architecture, planning, prd]
---


# Blueprint

## Instructions

### Step 1: Clarify the idea
If the description is vague, ask:
- Что делает продукт? Для кого?
- Какую проблему решает?
- Бизнес-модель / монетизация?
- Предпочтительный стек? (если нет — использовать стек из CLAUDE.md)
- Ограничения (бюджет, сроки, платформа)?

### Step 2: Generate 6 documents
Each document builds on the previous one. Create all files in the project root or docs/ folder.

Before writing, consult `references/document-templates.md` for the exact structure and level of detail expected in each document.

**Order:**
1. **STRATEGIC_PLAN.md** — стратегия, конкуренты, бюджет, KPIs, риски
2. **PROJECT_ARCHITECTURE.md** — стек, БД (все таблицы с полями), API (все эндпоинты), Docker, auth, деплой
3. **IMPLEMENTATION_PLAN.md** — 8-12 шагов, каждый с конкретными файлами и проверками
4. **PRD.md** — user stories, функциональные требования (P0/P1/P2), kill criteria
5. **README.md** — быстрый старт за 30 секунд, стек, структура
6. **CLAUDE_CODE_GUIDE.md** — готовые промпты для каждого шага (формат /guide)

### Step 3: Generate CLAUDE.md
Project memory file with: контекст, правила, стек, структура, статус-таблица шагов.

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

## Troubleshooting

### User doesn't know the tech stack
Use the default stack from the global CLAUDE.md. If none defined, recommend based on project type.

### Project is too large for 12 steps
Split into phases (MVP1, MVP2). Blueprint covers only MVP1. Note deferred features in PRD "Out of scope".

### Documents contradict each other
Architecture is the source of truth. If PRD conflicts with architecture, update PRD.

## Rules

- Все документы на русском языке
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
