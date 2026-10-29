---
name: task
description: 'Routes daily work in an existing project to the right skill - /bugfix, /refactor, /test, /doc, /perf, /security-audit, /deps-audit, /migrate, /harden, /infra, /explain, /review - or does a small feature directly: understand, change, test, run the suite. Use when the task type is not obvious from the request, when the user wants to work on an existing project, close tech debt or add a feature to existing code.'
argument-hint: one-line description of what needs to be done in the existing project [--strict]
license: MIT
allowed-tools: Read Edit Glob Grep Bash Skill
metadata:
  effort: low
  side_effect: local-write
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.110.0
  category: workflow
  tags: [router, daily-work, tech-debt, existing-code, methodology]
---

# Task

## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. The hook `hooks/check-skills.sh`
also uses this list - keep them in sync.

- закрой tech debt, закрой техдолг, убери техдолг
- поправь в проекте, почини в проекте, надо поправить
- есть задача в проекте, работа в существующем коде
- надо что-то сделать в проекте, инкрементальное изменение
- existing project, work on existing, tech debt cleanup
- maintenance task, housekeeping, chore
- реализуй фичу, добавь функциональность, новая фича в существующем проекте
- implement feature, add a feature, feature in existing project
- любой запрос на изменение уже существующего работающего кода, где тип задачи (bug/refactor/doc/test/perf) не очевиден в первой фразе

**Важно:** если пользователь сразу сказал что-то конкретное («почини баг в users.py», «отрефактори process_checkout»,
«добавь тесты к auth модулю»), сразу поднимается целевой скилл (`/bugfix`, `/refactor`, `/test` и т.д.), минуя
`/task`. `/task` - для случаев, когда **тип задачи неочевиден**, или для новой фичи в существующем коде.

## Recommended model

**sonnet** - a router: one routing question at most, then a dispatch or a small direct change.

## Instructions

You are the entry point for daily work on **existing** projects: understand what the user needs, route it to the
right skill, or do a small feature directly.

### Step 0: Route - minimal or strict

From the project root, check whether the project declares the strict route - a line `itd-route: strict` or
`itd-domain: data-sensitive` by itself, or the comment `<!-- itd:strict -->` / `<!-- itd:data-sensitive -->`:

```bash
( cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" && for f in CLAUDE.md .claude/CLAUDE.md AGENTS.md; do head -c 8192 "$f" 2>/dev/null; echo; done ) | grep -Eiq '^[[:space:]]*(itd-route:[[:space:]]*strict|itd-domain:[[:space:]]*data-sensitive)[[:space:]]*$|<!--[[:space:]]*itd:(strict|data-sensitive)[[:space:]]*-->' && echo strict || echo minimal
```

Take the **strict route** when it prints `strict`, when the arguments contain `--strict`, or when the task falls in a
strict class of the global rules or touches security (ITD's own critical mechanisms, money, access and secrets,
security, deploy, migrations, production data, external actions):
read `references/strict.md` now and run its steps together with the steps below - process-cost classification, the
PIV-lite feature pipeline with `/test`, `/review` and adjudication, and the WIP=1 unit bookkeeping. Otherwise this is
the **minimal path** - Steps 1-4, no unit ledger, no adjudication. The `.itd/` directory alone does not make a project
strict; the marker is described in the methodology's `docs/project-profiles.md`. A project that opted into Graph Lite
(ADR-014) runs S5 of `references/strict.md` before final validation on either route.

### Step 1: Understand the request

Read what the user said: `$ARGUMENTS`. Also check:
- the current directory (a git repo? which project?) and `git log --oneline -10` (what was being worked on);
- the project continuity, when present: `.itd-memory/continuity/<topic>.md` of the topic being continued (next
  action, state, decisions, blockers); the history in `.itd-memory/HISTORY.md` only when needed.

If the task type is already clear from the phrasing («отрефактори X», «почини баг Y»), skip Step 2 and route
directly (Step 3). A trivial task (typo, rename, one-liner with an obvious cause) - do it directly, no routing.

**Not adopted?** If neither `CLAUDE.md` nor `AGENTS.md` holds a `<!-- idea-to-deploy:begin` marker, do not stop the
routing: add one line to the final report - «проект не адоптирован; `/adopt` запишет указатель и команды проекта».

### Step 2: Determine the task type

If the request is ambiguous («закрой tech debt с deploy.sh», «надо поработать над auth»), ask ONE routing question:

> «Какой тип задачи?
>
> **1) Баг** - что-то не работает, есть стек/логи/ошибка → `/bugfix`
> **2) Рефакторинг** - код работает, но хочется улучшить структуру, читаемость, вынести общую логику → `/refactor`
> **3) Производительность** - эндпоинт/запрос/алгоритм тормозит, нужен профилировщик → `/perf`
> **4) Документация** - надо обновить README, API docs, docstrings, CLAUDE.md → `/doc`
> **5) Тесты** - надо добавить покрытие, regression-тесты, fixture → `/test`
> **6) Безопасность** - проверка OWASP, CORS, auth, секреты (read-only) → `/security-audit`
> **7) Зависимости** - CVE, лицензии, заброшенные пакеты → `/deps-audit`
> **8) Миграция БД** - schema change с backup + rollback path → `/migrate`
> **9) Production hardening** - health check, logs, metrics, rate limit, runbook → `/harden`
> **10) Инфраструктура** - Terraform, K8s, Helm, secrets manager → `/infra`
> **11) Объяснить код** - разобрать архитектуру, модуль, функцию → `/explain`
> **12) Review изменений** - проверить качество PR / diff → `/review`
> **13) Новая фича в существующем проекте** - добавить функциональность (не баг, не рефакторинг) → Step 3f»

**Do NOT ask** when the user already said something specific, when the answer is obvious from context (`git status`
shows a staged diff and the user says «проверь» → `/review`), or when the task is trivial (do it directly).

### Step 3: Route to the target skill

Invoke the target skill via the Skill tool and say in one line why:

> «Это похоже на рефакторинг (вынос inline-логики в отдельный модуль), вызываю `/refactor`. Если ошибся - скажи,
> и я переключусь.»

Routing matrix (details and implicit signals in `references/routing-matrix.md`):

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
| "Реализуй фичу X", "добавь функциональность", "сделай в проекте новое …" | Step 3f |
| "Я хочу сохранить контекст", "заканчиваем" | `/session-save` |

`/migrate`, `/deploy`, `/infra` and anything touching production data, money or access are strict-class tasks:
`references/strict.md` applies to them and the user confirms before anything irreversible or external.

Stall-resilience: when a routed skill dispatches a subagent and it **stalls** (watchdog timeout, autocompact death,
empty return), spawn a fresh narrow agent on the smallest useful slice instead of asking «resume or retry?» - the
shared rule in `skills/_shared/helpers.md` §9.

### Step 3f: A new feature in existing code

Neither `/bugfix` nor `/refactor`, and `/kickstart` is for new projects. On the minimal path do it directly:

1. **Scope** - say in one message which files/modules change and what is out of scope.
2. **Plan** - short, and only for a large or unclear feature; then wait for the user's approval. A small or one-file
   feature needs no plan ceremony. For a large or risky plan offer `/grill-me` first.
3. **Implement** - surgical edits inside the declared scope. If the feature reads a file, ledger or format another
   piece of code writes, read that producer first and test against its real output shape.
4. **Test** - write or fix the tests for the new code (the project's framework and conventions), then run the
   project's suite. Without a test runner use the project's own checks (lint, build). Show the result with numbers;
   a red run is reported, never hidden.
5. **Finish** - commit per the project's branch rules when the user asks. `/test` or `/review` on request or when
   they clearly save work; neither is a mandatory floor on the minimal path.

On the strict route the feature goes through the PIV-lite pipeline of `references/strict.md` (S3) instead - Plan →
Implement → Validate → Review: Task Contract, plan approval, `/test`, `/review` and adjudication before the unit is
marked verified.

### Step 4: After the target skill completes

Offer the next logical step without auto-chaining: a regression test after a bug fix if the skill did not add one,
`/review` before a larger merge, `/session-save` at the end of a significant block of work.

## Examples

### Example 1: Vague tech debt request

User says: «закрой tech debt с deploy.sh и kong.yml - kong конфиг слетает при каждом rsync»

1. Parse: a structural fix, not a hunt-the-bug scenario → **refactoring** (extract inline bash into a reusable script)
2. Tell the user: «Это рефакторинг - вынесу inline envsubst в отдельный идемпотентный скрипт. Запускаю `/refactor`.»
3. Invoke `/refactor` via the Skill tool; after it completes, report the result with the suite numbers.

### Example 2: Direct skill phrasing - skip the routing question

User says: «эндпоинт /users/{id}/orders тормозит» → direct match to `/perf`; invoke it without a question.

### Example 3: User has no idea what's needed

User says: «у меня проект в проде, надо с ним что-то сделать - куча мелочей накопилась» → ask the routing question;
the user picks 2 (рефакторинг) and 4 (документация) → «Ок, сначала `/refactor`, потом `/doc`.» Run them in order.

### Example 4: A one-file feature on the minimal path

User says: «добавь в CLI флаг --json для вывода отчета»

1. Step 0 prints `minimal`; one file and its test change - no plan ceremony.
2. Implement the flag, add a test for the JSON output, run the suite: «тесты: 48 passed, 0 failed».
3. Report the change and the numbers; offer `/review` only if the user wants it.

## Self-validation

- [ ] Step 0 printed the route; the strict steps ran only on the strict route
- [ ] Task type classified from the user's words; the target skill matches it (bug → `/bugfix`, not `/refactor`)
- [ ] The user's input is sufficient for the target skill, or a clarification was asked
- [ ] A direct feature has tests for the new code and a suite run with numbers in the report

## Troubleshooting

### User wants multiple skills in one go
Fully supported: «сначала почини баг, потом напиши тест». Run them sequentially via the Skill tool; save context
with `/session-save` at the end of a long chain.

### The task doesn't match any skill in the matrix
Too trivial for a skill - do it directly. A new project - redirect to `/project`. A feature - Step 3f.

### User switches skill mid-way
Supported: let them cancel and re-invoke `/task` or the target skill directly; each daily-work skill is independent.

### User asks for an operational task (e.g. "deploy this")
`/task` is for daily work on existing code. For deploy: the project's deploy documentation or `/deploy` (with the
user's confirmation); for incident response: `/bugfix` with the incident log as input.

## Rules

- **Route, or do a small feature directly** - every other task type goes to its daily-work skill via the Skill tool.
- **Never ask the routing question if the answer is obvious** - direct phrasings skip Step 2.
- **Always tell the user which skill you're routing to** - routing stays transparent and correctable.
- **Never invoke `/project`, `/kickstart`, `/blueprint` or `/guide`** - those create projects; redirect the user to
  `/project` explicitly if that is what they want.
- **Tests for new code and a suite run** before reporting a feature done - the global rule, on both routes.
- After the target skill completes, **offer** the next step; don't auto-chain without asking.
