---
name: guide
description: 'Generate CLAUDE_CODE_GUIDE.md — step-by-step copy-paste prompts for building the project via Claude Code.'
argument-hint: project name or description
license: MIT
allowed-tools: Read Write Edit Glob Grep
metadata:
  author: HiH-DimaN
  version: 1.3.1
  category: project-planning
  tags: [prompts, cookbook, claude-code-guide]
---


# Guide


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- создай гайд, сгенерируй промпты для проекта, сделай cookbook промптов
- пошаговая инструкция для Claude, промпты для Claude Code
- guide for project, cookbook, prompt sequence
- есть документация, нужны готовые промпты к ней

## Recommended model

**opus** — Generates a long sequence of step-by-step prompts that must reference specific files and verification commands. Opus produces tighter, more accurate prompt sequences.

Set via `/model {model}` before invoking this skill, or via the project's default model in `~/.claude/settings.json`.


## Instructions

### Step 1: Read project docs
Read all existing documentation:
- CLAUDE.md, README.md, PRD.md, PROJECT_ARCHITECTURE.md, IMPLEMENTATION_PLAN.md
- Any docs/ folder contents
- package.json, pyproject.toml for tech stack

### Step 2: Break into steps
Split the project into 8-15 logical steps (each = one Claude Code session, 1-3 hours).

Before writing prompts, consult `references/prompt-patterns.md` for effective prompt structure and verification patterns.

### Step 3: Generate CLAUDE_CODE_GUIDE.md

**Structure:**
1. **ПОДГОТОВКА** — mkdir, git init, .gitignore, CLAUDE.md, first commit
2. **ШАГ 0..N** — one prompt per step, ready to copy-paste
3. **ШПАРГАЛКА** — common commands table
4. **ТАЙМЛАЙН** — estimated hours per week
5. **СОВЕТЫ** — project-specific tips

**Rules for each step prompt:**
- Start with "Прочитай CLAUDE.md"
- Reference specific doc sections (not just "docs")
- List every file to create with path and key details
- Include concrete values (table names, field types, endpoints)
- End with verification commands
- After block: update CLAUDE.md status, commit

### Step 4: Validate
Each step must produce a working state — no half-broken code between steps.

## Examples

### Example 1: Python/FastAPI project
User says: "создай гайд для проекта api-gateway"

Result: CLAUDE_CODE_GUIDE.md with 10 steps:
- Step 1: Project setup (pyproject.toml, Docker, alembic)
- Step 2: DB models (all tables from architecture doc)
- Step 3: Auth (JWT, middleware, login/register)
- ...
- Cheat sheet: `alembic upgrade head`, `pytest`, `docker-compose up`

### Example 2: Monorepo project
User says: "guide for neuroexpert"

Result: CLAUDE_CODE_GUIDE.md with 12 steps matching existing IMPLEMENTATION_PLAN, each prompt references specific sections of PROJECT_ARCHITECTURE.md.

## Rules

1. Каждый промпт в гайде должен быть copy-pasteable — пользователь копирует текст в Claude Code и получает результат без редактирования промпта
2. Один промпт = один шаг = один коммит с тестируемым результатом. Не объединяй несколько несвязанных действий в один промпт
3. Каждый шаг должен заканчиваться командами верификации (`pytest`, `curl`, `npm run build`) — шаг без проверки невалиден
4. Промпты содержат конкретные значения (имена таблиц, типы полей, эндпоинты), а не абстракции ("создай модель данных")
5. Не генерируй код внутри промптов — промпт описывает ЧТО сделать, Claude Code сам решает КАК. Исключение: конфиги и .env.example


## Self-validation

Before presenting CLAUDE_CODE_GUIDE.md, verify:
- [ ] Each step is copy-pasteable into Claude Code
- [ ] Steps follow the order from implementation plan
- [ ] All steps reference correct file paths and commands
- [ ] Pre-emptive clarifications included where skills ask questions
- [ ] Guide covers full lifecycle (not just code generation)

## Troubleshooting

### No PROJECT_ARCHITECTURE.md exists
Generate one first using `/blueprint`, then create the guide.

### Steps are too large (>3 hours each)
Split into sub-steps. A step should produce one commit with one testable result.

### Prompts are too vague
Every prompt must name specific files and values. Consult `references/prompt-patterns.md` for the good vs bad prompt comparison.

### Step 5: Offer next steps

After generating CLAUDE_CODE_GUIDE.md, tell the user:

"Гайд создан. Варианты:
1. **Ручной режим** — откройте CLAUDE_CODE_GUIDE.md и копируйте промпты по шагам
2. **Автоматический режим** — скажите 'начинай реализацию' и я выполню все шаги последовательно (перейду на маршрут А)
3. **Дополнить план** — скажите 'создай полную документацию' и я сгенерирую недостающие документы (перейду на маршрут Б)"
