---
name: task
description: 'Smart daily-work router — routes to the right implementation skill (/bugfix, /refactor, /doc, /test, /perf, /security-audit, /deps-audit, /migrate, /harden, /infra) based on what the user needs to do in an EXISTING project.'
argument-hint: one-line description of what needs to be done in the existing project
license: MIT
allowed-tools: Read
metadata:
  author: HiH-DimaN
  version: 1.18.0
  category: workflow
  tags: [router, daily-work, tech-debt, existing-code, methodology]
---

# Task


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- закрой tech debt, закрой техдолг, убери техдолг
- поправь в проекте, почини в проекте, надо поправить
- есть задача в проекте, работа в существующем коде
- надо что-то сделать в проекте, инкрементальное изменение
- existing project, work on existing, tech debt cleanup
- maintenance task, housekeeping, chore
- любой запрос на изменение уже существующего работающего кода, где тип задачи (bug/refactor/doc/test/perf) не очевиден в первой фразе

**Важно:** если пользователь сразу сказал что-то конкретное («почини баг в users.py», «отрефактори process_checkout», «добавь тесты к auth модулю»), хук поднимет сразу целевой daily-work скилл (`/bugfix`, `/refactor`, `/test` и т.д.), минуя `/task`. `/task` — для случаев когда **тип задачи неочевиден** или пользователь явно зашёл как «надо поработать над проектом».

## Recommended model

**sonnet** — Router only — asks one routing question and dispatches. No code or doc generation. Sonnet is plenty.

Set via `/model sonnet` before invoking this skill.


## Instructions

You are the single entry point for daily work on **existing** projects. Your job is to understand what the user needs and route them to the right daily-work skill.

### Step 1: Understand the request

Read what the user said: `$ARGUMENTS`. Also check:
- Current working directory (is it a git repo? what's the project?)
- Recent `git log --oneline -10` (what was being worked on)
- `MEMORY.md` from the project memory dir (if pre-flight-check hook ran, it's already in context)

If you already know the task type from the user's phrasing (e.g., explicit "отрефактори X", "почини баг Y"), skip Step 2 and go straight to Step 3 — invoke the target skill directly.

### Step 2: Determine the task type

If the user's request is ambiguous (e.g., "закрой tech debt с deploy.sh", "надо поработать над auth"), ask ONE routing question:

> «Какой тип задачи?
>
> **1) Баг** — что-то не работает, есть стек/логи/ошибка → `/bugfix`
> **2) Рефакторинг** — код работает, но хочется улучшить структуру, читаемость, вынести общую логику → `/refactor`
> **3) Производительность** — эндпоинт/запрос/алгоритм тормозит, нужен профилировщик → `/perf`
> **4) Документация** — надо обновить README, API docs, docstrings, CLAUDE.md → `/doc`
> **5) Тесты** — надо добавить покрытие, regression-тесты, fixture → `/test`
> **6) Безопасность** — проверка OWASP, CORS, auth, секреты (read-only) → `/security-audit`
> **7) Зависимости** — CVE, лицензии, заброшенные пакеты → `/deps-audit`
> **8) Миграция БД** — schema change с backup + rollback path → `/migrate`
> **9) Production hardening** — health check, logs, metrics, rate limit, runbook → `/harden`
> **10) Инфраструктура** — Terraform, K8s, Helm, secrets manager → `/infra`
> **11) Объяснить код** — разобрать архитектуру, модуль, функцию → `/explain`
> **12) Review изменений** — проверить качество PR / diff → `/review`»

**Do NOT ask this question** if:
- The user already said something specific → jump to the target skill directly
- The answer is obvious from context (e.g., `git status` shows unstaged PR changes → `/review`)
- The task is trivial (single-line fix, typo) → do it directly

### Step 3: Route to the target skill

Based on the answer (or direct inference), invoke the target skill via the Skill tool. Always tell the user why you're routing there:

> «Это похоже на рефакторинг (вынос inline-логики в отдельный модуль), вызываю `/refactor`. Если ошибся — скажи, и я переключусь.»

Routing matrix (also in `references/routing-matrix.md`):

| User signal | Target skill |
|---|---|
| Стек трейс, ошибка, crash, "не работает" | `/bugfix` |
| "Отрефактори", "упрости", "вынеси", extract method | `/refactor` |
| "Тормозит", "медленно", "bottleneck", N+1 | `/perf` |
| "Обнови README", "напиши docs", "задокументируй" | `/doc` |
| "Добавь тесты", "покрой тестами", "нет покрытия" | `/test` |
| "Проверь безопасность", "OWASP", "auth check" | `/security-audit` |
| "Проверь зависимости", "CVE", "устаревшие пакеты" | `/deps-audit` |
| "Накати миграцию", schema change, ALTER TABLE | `/migrate` |
| "Готов ли прод", health check, runbook, rate limit | `/harden` |
| "Terraform", "Helm", "k8s manifests", "provision" | `/infra` |
| "Объясни код", "как это работает", walkthrough | `/explain` |
| "Проверь PR", "оцени качество", code review | `/review` |
| "Я хочу сохранить контекст", "заканчиваем" | `/session-save` |

### Step 4: After the target skill completes

Offer next steps or close the loop:

- If the task was a bug → suggest `/test` to add a regression test, then `/review`
- If the task was a refactor → suggest `/test` to confirm behavior preserved, then `/review`
- If the task was doc update → suggest `/review`
- If the user is done for the day → suggest `/session-save`

## Examples

### Example 1: Vague tech debt request

User says: «закрой tech debt с deploy.sh и kong.yml — kong конфиг слетает при каждом rsync»

Actions:
1. Parse: «tech debt» + «slet with каждом rsync» — sounds like a structural fix, not a hunt-the-bug scenario
2. Routing inference: this is "extract inline bash → reusable script" = **refactoring**
3. Tell user: «Это рефакторинг — вынесу inline envsubst в отдельный идемпотентный скрипт и обновлю все пути, которые его вызывают. Запускаю `/refactor`.»
4. Invoke `/refactor` skill via Skill tool
5. After completion: «Сделано. Предлагаю прогнать `/review` по всем правкам.»

### Example 2: Direct skill phrasing — skip routing question

User says: «эндпоинт /users/{id}/orders тормозит»

Actions:
1. Parse: «тормозит» — direct match to /perf triggers
2. Skip routing question (it's obvious)
3. Invoke `/perf` directly via Skill tool
4. `/task` exits after Step 3

### Example 3: User has no idea what's needed

User says: «у меня NeuroExpert в проде, надо с ним что-то сделать — куча мелочей накопилась»

Actions:
1. Parse: no specific task type → ask routing question (Step 2)
2. User picks 2 (рефакторинг) and 4 (документация)
3. Tell user: «Ок, сначала рефакторинг, потом docs. Начинаю с `/refactor`. После него `/doc`.»
4. Invoke `/refactor`, wait for completion, then `/doc`

### Example 4: Obvious from context — no question

User says: «вот этот PR, проверь» + `git status` shows 12 files staged

Actions:
1. Context inference: staged PR → это `/review`
2. Skip question, invoke `/review` directly
3. Tell user: «Вижу staged diff, запускаю `/review`.»


## Self-validation

Before delegating to target skill, verify:
- [ ] Task type correctly classified from user's description
- [ ] Target skill matches the task type (bugfix → /bugfix, not /refactor)
- [ ] User's input is sufficient for the target skill (or clarification requested)
- [ ] Delegation uses Skill tool with appropriate arguments

## Troubleshooting

### User wants multiple skills in one go
Fully supported. Example: «сначала почини баг, потом напиши тест, потом проверь review». Execute sequentially via the Skill tool. After each completes, move to the next. Remember to save context between if the chain is long (`/session-save` as the last step).

### User's task doesn't match any skill in the matrix
This usually means the task is either:
- Too trivial for a skill (one-line fix) — just do it directly, skip routing
- A new project request — wrong router, redirect to `/project`
- A multi-step feature implementation — use `/kickstart` or `/blueprint` depending on whether docs exist

### User switches skill mid-way
Supported. If `/refactor` is running and the user realizes "actually this is a perf issue", let them cancel and re-invoke `/task` or the target skill directly. No cleanup needed — each daily-work skill is independent.

### User asks for something outside the matrix (e.g., "deploy this")
`/task` is for **daily work on existing code**, not operational tasks like deploy or incident response. For deploy: point them at the project's deploy documentation or `/infra`. For incident response: `/bugfix` with the incident log as input.

## Rules

- **Never do the work yourself** — `/task` is a router, always delegate to a daily-work skill via the Skill tool.
- **Never ask the routing question if the answer is obvious** — direct phrasings skip Step 2.
- **Always tell the user which skill you're routing to** — makes the routing transparent and correctable.
- **Never invoke `/project`** — `/task` is for **existing** code. If the user actually wants a new project, redirect them to `/project` explicitly and exit.
- **Never invoke `/kickstart`, `/blueprint`, or `/guide`** — those are project-creation skills, not daily-work. If the task looks like "implement this from scratch based on existing docs", redirect to `/project` → vars А/В.
- After the target skill completes, **offer** the next logical step but don't auto-chain without asking.
