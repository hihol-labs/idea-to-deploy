---
name: task
description: 'Smart daily-work router — routes to the right implementation skill (/bugfix, /refactor, /doc, /test, /perf, /security-audit, /deps-audit, /migrate, /harden, /infra) based on what the user needs to do in an EXISTING project.'
argument-hint: one-line description of what needs to be done in the existing project
license: MIT
allowed-tools: Read
metadata:
  effort: low
  side_effect: read-only
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.19.0
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
- реализуй фичу, добавь функциональность, новая фича в существующем проекте
- implement feature, add a feature, feature in existing project
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

### Step 1a: Legacy-project detection (v1.20.0)

**Before** asking the routing question, check whether this project has been adopted into the methodology. Read from `$PROJECT_ROOT`:

1. Does `CLAUDE.md` exist in the repo root AND contain the marker `<!-- idea-to-deploy:begin`?
2. Does any plan document exist — `LAUNCH_PLAN.md`, `STRATEGIC_PLAN.md`, or `PROJECT_ARCHITECTURE.md`?
3. Does `.claude/settings.json` exist with a `hooks` section referencing our hook script names?

**If ALL THREE are absent** (no adoption marker, no plan docs, no project-level hooks) → this is a legacy project that was never onboarded. Pause routing and tell the user:

> «Этот проект ещё не адоптирован в методологию idea-to-deploy (нет `CLAUDE.md`, нет plan-документов, нет хуков в `.claude/settings.json`).
>
> Рекомендую сначала запустить `/adopt` — это займёт ~30 секунд и включит методологию в проекте (canonical `CLAUDE.md`, регистрация хуков, bootstrap memory dir, voice-chain в `/strategy` или `/blueprint`). Потом вернусь к твоей задаче.
>
> Запустить `/adopt` сейчас? (да / нет, хочу сразу task)»

- **«да»** → invoke `Skill(/adopt)`. After `/adopt` completes (including its voice-chain to `/strategy` or `/blueprint` if the user wants plan docs), resume Step 2 of `/task` with the original request.
- **«нет»** → skip Step 1a forever for this conversation and continue with Step 2 as usual. User autonomy wins; the methodology guides, not enforces.

**Do NOT** treat Step 1a as blocking. If any of the three checks fails inconclusively (e.g., `CLAUDE.md` exists but without our marker — user may have their own), err toward NOT suggesting `/adopt`; the prompt noise is worse than a missed adoption.

### Step 1b: Process-cost classification (v1.21 — PFO port)

Before routing, classify the task's **process-cost tier** so the methodology scales to the risk — see `skills/_shared/helpers.md` §6:

- **trivial** (typo, rename, one-liner, obvious cause) → do it directly, skip the routing question and the contract/gate machinery.
- **standard** (normal change in one module) → route to the target skill; it applies `SCOPE_LOCK` + spec-compliance + fail-closed verify + `/review`/`/test`.
- **high-risk** (the target is `migrate`/`migrate-prod`/`deploy`/`infra`/`autopilot`, or the change touches production data, schema, auth, payments, or security) → apply the full `.itd/` contract set + permission matrix + branch-finish + **explicit user approval** before acting.

State the tier in one line when you route ("это standard-задача → /refactor"). When unsure between two tiers, pick the higher one.

**Cost-awareness (v1.31.0 — New-SDLC port):** for a **high-risk** tier or a heavy
target (`/kickstart`, `/autopilot`, long `/perf`/`/bugfix` sweeps) note that
`hooks/cost-tracker.sh` keeps a per-session token/USD ledger and will ASK at the
budget ceiling — set `ITD_COST_CEILING_TOKENS` (and `ITD_COST_PER_1M_USD`) per project
to make the ceiling meaningful, and `/session-save` will attach the cost snapshot at
wrap-up. This is a one-line nudge, not a gate — never block routing on it. (Token
economics is the OpEx lever for agent-heavy products; see ADR-001 — accounting rides
the existing hook, we don't build our own collector.)

**Micro-path — regression cadence for tiny tasks (v1.66.0, retro-2026-07-08 P4):**
for a **standard**-tier task of **≤1–2 units** with a small diff, per-unit
verification stays MANDATORY (the unit's own verification command goes green
before anything else starts), but the **cumulative regression suite runs ONCE as
a final full pass** instead of after every unit. Evidence: the measured cost of
after-every-unit regression on a micro-task was ×3.5 wall-clock and ×7 tool calls
at zero difference in verified-completion rate. Classify by unit count, not by
feel: 3+ units, cross-module effects, or any high-risk signal → back to
after-every-unit regression (see `skills/_shared/helpers.md` §6).

### Step 1c: Read the module-quality queue (when present)

If `.itd/QUALITY.json` exists, read it before fixing scope. Prefer the executable
view (**`itd_hygiene.py quality`**) so stale or evidence-less grades cannot look
authoritative:

```bash
HY=".itd/itd_hygiene.py"; [ -f "$HY" ] || HY="$HOME/.claude/templates/itd/itd_hygiene.py"
SHD="skills/_shared"; [ -f "$SHD/itd_py.sh" ] || SHD="$HOME/.claude/skills/_shared"
sh "$SHD/itd_py.sh" "$HY" quality --root .
```

Surface the lowest-grade module and its first priority in the routing context.
It is the default maintenance priority, not permission to override an explicit
user task: if the user asked for another module, keep their scope and record the
lower-grade finding as backlog. Missing `.itd/QUALITY.json` is a soft no-op for
pre-adoption projects; an invalid/stale ledger is a visible quality warning.

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
> **12) Review изменений** — проверить качество PR / diff → `/review`
> **13) Новая фича в существующем проекте** — добавить функциональность (не баг, не рефакторинг) → **feature-конвейер** (Step 3f)»

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
| "Реализуй фичу X", "добавь функциональность", "сделай в проекте новое …" | **feature-конвейер** (Step 3f) |
| "Я хочу сохранить контекст", "заканчиваем" | `/session-save` |

### Step 3f: Feature pipeline — новая функциональность в brownfield (v1.42.0)

The daily-work case the matrix used to miss: implementing a NEW feature in an
existing project is neither `/bugfix` nor `/refactor`, and `/kickstart` is
forbidden here. For this route `/task` acts as the pipeline conductor — it does
not write the code "as a router", it walks the standard chain around the
implementation:

1. **Scope first.** If `.itd/` exists — fill `SCOPE_LOCK.md` (Current Task +
   Allowed/Forbidden Change Areas) and open a unit per Step 3.5. Without
   `.itd/` — state the scope in one message (files/modules to touch, what is
   explicitly out of scope).
1b. **Task Contract (Sprint Contract per-задача, v1.88.0).** До первой
   правки кода зафиксируй контракт юнита в
   `.itd-memory/contracts/<unit-id>.md` по шаблону
   `docs/templates/itd/TASK_CONTRACT.md`: Scope / Verification Standards /
   Exclusions (Verification = verificationCommand юнита или его
   эквивалент). Генератор и оценщик согласуют контракт ДО старта: ОТК
   исполняет Verification, DoD-гейт на git commit даёт advisory-строку,
   если у активного юнита контракта нет (не блокирует). Один экран, не
   спецификация. Без `.itd-memory/` — шаг пропускается молча.
2. **Plan → approve.** For anything beyond ~1 file: a short plan (steps, files,
   verification per step) and explicit user approval before code (global rule
   «Plan before code»). For a large/risky feature offer `/grill-me` on the plan
   first.
2a. **Deployment baseline — дефолтная планка (v1.89.0, GO-005).** Даже БЕЗ
   явного Task Contract каждая feature-задача применяет этот deployment-floor
   (замер A/B сет-4: агент без контракта промахивался именно здесь — 3.5/6):
   - **Exit-семантика**: CLI/скрипт возвращает ненулевой код при найденной
     проблеме и 0 при чистоте; «нашёл, но exit 0» — дефект.
   - **Diff-scoped / no-op по умолчанию**: инструмент проверки работает по
     переданному срезу (`--files`), без аргументов — no-op, а не полный скан
     живого репо.
   - **Actionable-вывод**: на нарушении — путь + строка + WHY + FIX-подсказка,
     не голое «ERROR».
   - **Тихий успех**: при отсутствии находок — без шум-сводки в stdout.
   - **Zero-dep, если так задано**: не тянуть пакеты/AST, если задача просила
     stdlib.
   - **Самопроба**: прогнать на позитивной И негативной фикстуре, показать
     фактические exit-коды.
   Явный Task Contract (шаг 1b) переопределяет/дополняет планку; при его
   отсутствии планка — и есть контракт по умолчанию.

3. **Implement** — surgical edits inside the declared scope; the normal gates
   stay armed (wip-gate, careful, DoD). **Producer-first rule** (retro
   2026-07-04, класс «assumed producer shape» — 2 Important в одном ревью):
   если фича ЧИТАЕТ файл/леджер/формат, который пишет другой код — сначала
   прочитай код продюсера (реальные имена полей/форм), и тесты сей реальными
   образцами продюсера, а не предположенной формой.
4. **Verify** — `/test` for new code (fail-closed: evidence required; for
   projects without a test runner use the project's declared verification —
   lint/build/domain checks from `.itd/VERIFICATION_CONTRACT.json` or
   CLAUDE.md).
5. **`/review`** before any multi-file commit (mandatory floor), then commit
   per the project's branch/PR rules; `/session-save` at the block end.

Tier note (Step 1b): a feature is **standard** by default; escalate to
**high-risk** when it touches prod data, schema, auth, payments, or security.

Stall-resilience: when any step here dispatches a subagent (the routed skill's
verify/review agents, an Explore/refute agent) and it **stalls** — watchdog
timeout, autocompact death, empty return — the recovery is **automatic**: spawn a
fresh narrow agent scoped to the smallest useful slice, do not stop to ask
«resume or retry?». This is the shared rule in `skills/_shared/helpers.md` §9,
not a per-skill judgement call.

### Step 3.5: Unit bookkeeping — WIP=1 (v1.41.0; писатель — харнес, v1.85.0; only when `.itd-memory/` exists)

If `$PROJECT_ROOT/.itd-memory/STATE.json` exists, keep the machine-readable
scope surface honest around the routing. Переходами unit-статусов управляет
скрипт `skills/task/scripts/itd_unit_log.py` — **не пиши JSON в
STATE.json/events.jsonl руками** (диагноз G-004, retro 2026-07-11: ручная
запись теряла activation-события — 4 юнита verified без activated, слепой VCR).

Резолв путей (в начале каждого shell-вызова; python — только через запускатель):

```bash
TT="skills/task/scripts"; [ -f "$TT/itd_unit_log.py" ] || TT="$HOME/.claude/skills/task/scripts"
SHD="skills/_shared"; [ -f "$SHD/itd_py.sh" ] || SHD="$HOME/.claude/skills/_shared"
```

1. **Before activating** — read `STATE.json.currentUnit`. If its `status` is
   `verifying` / `recovery_required` (unfinished unit) → do NOT silently start
   the new unit. Tell the user: «Текущий unit `<id>` не доведён до verified
   (<status>). WIP=1: сначала доводим его верификацию, или осознанно
   закрываем/переклассифицируем?» Proceed only after an explicit choice.
   (Скрипт продублирует WIP=1 fail-closed — но спросить пользователя обязан ты.)
2. **On activation** —
   `sh "$SHD/itd_py.sh" "$TT/itd_unit_log.py" activate U-<next> --goal "<one-line task>"`
   — скрипт сам выставит `currentUnit` (атомарно) и запишет событие
   `activated` (actor: harness).
3. **On verified completion** (the target skill's verification passed with
   evidence) —
   `sh "$SHD/itd_py.sh" "$TT/itd_unit_log.py" verified U-<id> --evidence "<вывод проверки>"`
   — verified без evidence или без парного activation-события скрипт отклонит
   (осознанная реконсиляция истории: `backfill-activation U-<id> --note "…"`).
   These events feed `itd_metrics.py` VCR (verified/activated) and the
   `wip-gate.sh` hook.

Skip this step entirely when there is no `.itd-memory/` — do not create it
from `/task` (that's `/adopt` / `/kickstart` territory).

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
