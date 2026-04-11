# Manual verification — fixture 10 (/task router)

The `/task` skill is a **thin router**: it never generates code itself. It reads the user's request, optionally asks ONE routing question, then invokes the target daily-work skill via the Skill tool. This fixture verifies routing accuracy, not the target skills' behavior.

## /task — Scenario A: ambiguous tech debt

User says: «у меня NeuroExpert в проде, надо закрыть tech debt с deploy.sh — kong.yml слетает при rsync»

- [ ] `/task` reads the request and recognizes «tech debt» as a routing trigger
- [ ] Router analyzes the description: «rsync сносит kong.yml», «inline envsubst в deploy.sh» → structural improvement, not bug hunt
- [ ] Router **infers** the target: `/refactor` (extract-method), does NOT ask the 12-option routing question
- [ ] Router tells the user: «Это рефакторинг — вынесу inline envsubst в отдельный идемпотентный скрипт. Запускаю /refactor.»
- [ ] Router invokes `/refactor` via the Skill tool
- [ ] After `/refactor` completes, router offers the next step (e.g., «Теперь `/review`?»)

## /task — Scenario B: direct skill phrasing

User says: «эндпоинт `/users/{id}/orders` тормозит, профилируй»

- [ ] `/task` detects the direct `/perf` trigger («тормозит», «профилируй»)
- [ ] Skips the routing question entirely
- [ ] Invokes `/perf` directly via Skill tool
- [ ] Reports: «Прямой match на /perf, запускаю без роутинг-вопроса.»

## /task — Scenario C: multi-step chain

User says: «есть задача: сначала отрефактори process_checkout, потом добавь тесты, потом сделай review»

- [ ] `/task` parses the ordered chain: refactor → test → review
- [ ] Executes sequentially, not in parallel
- [ ] Between each step, briefly confirms completion and readiness to proceed
- [ ] If the chain is long (>3 skills), offers `/session-save` as the last step
- [ ] Does NOT create its own aggregate report — each sub-skill reports independently

## /task — Scenario D: out of scope (new project request)

User says: «хочу новый проект — CRM для фитнес-клубов»

- [ ] `/task` recognizes this as **creation**, not maintenance
- [ ] Does NOT run any daily-work skill
- [ ] Tells the user: «Это запрос на создание нового проекта, `/task` не подходит. Переключаюсь на `/project` — он спросит про тип цикла и дальше запустит `/kickstart` / `/blueprint` / `/guide`.»
- [ ] Invokes `/project` via Skill tool
- [ ] Exits

## /task — Guard rails

- [ ] NEVER invokes `/project`, `/kickstart`, `/blueprint`, `/guide` except in Scenario D (new-project redirect)
- [ ] NEVER generates code itself — only routes
- [ ] NEVER asks the routing question twice in a row (if user gave a direct phrasing, trust it)
- [ ] NEVER chains more than 3 skills without offering `/session-save`

## Cross-reference with `check-skill-completeness.sh`

`/task` skill satisfies all 3 Quality Gate 2 requirements:

1. ✅ `references/routing-matrix.md` exists and is non-empty
2. ✅ `hooks/check-skills.sh` contains trigger phrases for `/task` (added in the same commit)
3. ✅ `tests/fixtures/fixture-10-task/` exists with `idea.md`, `notes.md`, `expected-files.txt`

## Expected report after a Scenario A run

The router itself produces no artifacts. The downstream skill (`/refactor` in Scenario A) produces its own report per its own spec (e.g., `refactor-diff.patch`). The router adds ONE line to the response: the routing decision it made and why.

Example:
```
Routed: /refactor (inferred from: inline envsubst → extract-method, «tech debt»
phrasing, no error/crash symptoms → not /bugfix)
```
