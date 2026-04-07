---
name: guide
description: Generate a CLAUDE_CODE_GUIDE.md — step-by-step copy-paste prompts for building the project from scratch via Claude Code. Includes preparation, steps, cheat sheet, and timeline. TRIGGER when user says "создай гайд", "сгенерируй промпты для проекта", "сделай cookbook промптов", "пошаговая инструкция для Claude", "промпты для Claude Code", "guide for project", "cookbook", or already has documentation/PRD and needs ready-to-paste prompts to drive Claude through implementation. Assumes /blueprint output already exists or will be created.
argument-hint: project name or description
license: MIT
effort: high
metadata:
  author: HiH-DimaN
  version: 1.0.0
  category: project-planning
  tags: [prompts, cookbook, claude-code-guide]
---


# Guide

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
