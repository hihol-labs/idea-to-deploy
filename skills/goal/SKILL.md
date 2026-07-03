---
name: goal
description: 'Long-goal mode — decompose a goal that spans multiple sessions into ordered verifiable units in .itd-memory/GOAL.json (user approval required), then drive them ONE at a time through the standard /task pipeline (WIP=1, evidence-gated verified). Resumable: a fresh session continues from the first non-verified unit instead of re-deriving the plan. Brownfield-first; NOT a gate — never bypasses /review, /test, or the DoD.'
argument-hint: the goal text (empty = resume the active .itd-memory/GOAL.json)
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash Skill
metadata:
  effort: medium
  side_effect: memory-write
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.44.0
  category: workflow
  tags: [goal, long-running, units, wip, resume, brownfield, ledger]
---

# Goal

## Trigger phrases

- долгая цель, режим цели, поставь цель
- декомпозируй цель, цель на несколько сессий
- продолжай цель, вернись к цели, работаем к цели
- goal mode, long-running goal, multi-session goal
- decompose the goal, goal ledger, goal.json

## Recommended model

**Opus/default для декомпозиции** (Step 1 — выделить проверяемые юниты из
размытой цели — это рассуждение, не механика). Ведение юнитов (Step 2) идёт
моделью штатного конвейера `/task` — `/goal` там только бухгалтер.

## Instructions

Режим долгой цели: цель, которая не помещается в одну сессию, становится
**машиночитаемой** — упорядоченный список проверяемых юнитов в
`.itd-memory/GOAL.json` (schema: `docs/templates/itd-memory/goal.schema.json`,
образец: `GOAL.example.json`). Каждый юнит проходит штатный конвейер, прогресс
переживает смерть сессии программно.

> **`/goal` — тонкий слой, не оркестратор** (ADR-001). Он НЕ добавляет гейтов и
> НЕ обходит существующие: `/review`, `/test`, DoD-прекоммит и wip-gate работают
> как обычно внутри каждого юнита. Главный кейс — brownfield; скилл не входит в
> подавляемый greenfield-список. Для greenfield-цели «с нуля до деплоя» есть
> `/autopilot`.

### Step 0: Resume-check (всегда первым)

Проверь `$PROJECT_ROOT/.itd-memory/GOAL.json`:

- **Есть и `status: active`** → это RESUME. Не пересоздавай и не
  ре-декомпозируй. Покажи срез («Цель: X — N/M юнитов verified, текущий G-k»),
  возьми первый юнит со статусом `in_progress`, иначе первый `pending`, и иди в
  Step 2. Если пользователь дал НОВУЮ цель при активной старой — спроси явно:
  закрыть старую (`done`/`abandoned`) или продолжить её.
- **Есть и `status: done|abandoned`** → сообщи и, если дана новая цель, заведи
  новый ledger (старый можно переименовать в `GOAL-YYYY-MM-DD.json` для истории).
- **Нет** → Step 1.

### Step 1: Декомпозиция + одобрение (без записи до approve)

1. Сформулируй цель одним проверяемым предложением (из `$ARGUMENTS` + контекста).
2. Разбей на **упорядоченный** список юнитов. Каждый юнит:
   - `id` — `G-001`, `G-002`, … (уникальные, стабильные);
   - `criterion` — бинарный критерий («возвращает 200 и шлёт письмо», не
     «улучшить auth»);
   - `verificationCommand` — исполняемая команда проверки (тест, curl, скрипт);
   - `status: pending`.
   Размер юнита — одна сессия или меньше (иначе дели дальше).
3. **Покажи декомпозицию пользователю и жди явного approve** (глобальное правило
   «Plan before code»). Правки/переупорядочивание — до записи.
4. После approve запиши `GOAL.json` (поля по schema: `version`, `goal`,
   `status: active`, `createdAt`/`updatedAt` UTC ISO, `currentUnitId: ""`,
   `units[]`) и провалидируй:

```bash
python3 scripts/validate_state.py "$PROJECT_ROOT/.itd-memory/GOAL.json" 2>/dev/null \
  || python3 -c "import json;json.load(open('$PROJECT_ROOT/.itd-memory/GOAL.json'))"
```

(вне репо методологии валидатор недоступен — тогда хотя бы JSON-parse; схему
держи в голове по образцу `GOAL.example.json`).

### Step 2: Ведение — один юнит за раз (WIP=1)

Цикл, пока есть `pending`-юниты и пользователь не остановил:

1. **Активируй** следующий юнит: `status: in_progress`, `currentUnitId: <id>`,
   `updatedAt`; событие в `.itd-memory/events.jsonl`
   (`{"type":"unit","name":"G-002","decision":"activated","evidence":"<criterion>"}` —
   формат `events.example.jsonl`). Если ведётся `STATE.json` — юнит цели И ЕСТЬ
   `currentUnit` (unit-механика v1.41: один и тот же юнит, не два учёта).
2. **Прогони через штатный конвейер**: юнит = обычная задача → `/task`
   (фича → Step 3f: scope → короткий план → код → `/test` → `/review` → коммит
   по правилам репо; баг → `/bugfix`; и т.д.). `/goal` не дублирует конвейер —
   только скоуп юнита на входе и учёт на выходе.
3. **Верифицируй**: выполни `verificationCommand`, зафиксируй фактический вывод.
   Прошла → `status: verified`, `verifiedAt`, `evidence` (короткая решающая
   строка вывода), unit-событие `decision: "verified"` в events.jsonl (VCR в
   `itd_metrics.py` начинает считаться по цели автоматически). Не прошла —
   юнит остаётся `in_progress`, чини в рамках конвейера; **не открывай
   следующий** (wip-gate это же и подсказывает).
4. **Skip — только по явному решению пользователя**: `status: skipped` +
   непустой `skippedReason` (fail-closed: валидатор отвергнет пустой).
5. Между юнитами — инкрементальный `/session-save` (verified-юнит = значимая
   смена состояния).

### Step 3: Закрытие цели

Все юниты `verified`/`skipped` → покажи финальный срез (юниты + evidence),
поставь `status: done`, `updatedAt`, `currentUnitId: ""`. Отказ от цели —
`status: abandoned` (юниты не трогай — история). Предложи `/session-save`.

## Examples

### Example 1: Новая цель (brownfield)
User: «Поставь цель: self-serve сброс пароля работает end-to-end на проде»

Actions:
1. Step 0: `GOAL.json` нет → декомпозиция: G-001 endpoint+email, G-002
   token expiry/single-use, G-003 rate-limit — каждый с pytest-командой.
2. Показывает список, ждёт approve. После approve пишет `GOAL.json`.
3. Активирует G-001 → `/task` Step 3f → `/test` + `/review` →
   `pytest tests/test_reset.py -v` → «2 passed» → `verified` + событие в
   events.jsonl → предлагает G-002.

### Example 2: Resume после смерти сессии
User: «продолжай цель»

Actions:
1. Step 0: `GOAL.json` есть, `active`, 1/3 verified, `currentUnitId: G-002`
   (pre-flight уже показал это в срезе состояния).
2. Сообщает «Цель: … — 1/3 verified, текущий G-002», продолжает G-002 с места
   конвейера. Ничего не пересоздаёт.

### Example 3: Новая цель при активной старой
User: «поставь цель: мигрировать на Postgres 17» (при active-цели про reset)

Actions:
1. Step 0 видит активную цель → спрашивает: закрыть текущую (done? abandoned?)
   или новая подождёт. Без явного ответа ledger не трогает.

## Self-validation

Перед выводом убедись:
- [ ] Существующий active-`GOAL.json` НЕ пересоздан (resume-путь).
- [ ] Декомпозиция показана пользователю и получен явный approve ДО записи.
- [ ] У каждого юнита бинарный `criterion` и исполняемая `verificationCommand`.
- [ ] `verified` ставится только после фактического прогона команды, с `evidence`.
- [ ] `skipped` — только с непустым `skippedReason`.
- [ ] Unit-события (`activated`/`verified`) записаны в `events.jsonl`.
- [ ] Открыт максимум один юнит (WIP=1); гейты конвейера не обойдены.

## Troubleshooting

### Цель не декомпозируется в проверяемые юниты
Критерии выходят небинарными («сделать лучше») → это признак, что цель —
исследование, а не поставка. Предложи `/advisor`/`/grill-me` для уточнения
цели, ledger не заводи.

### GOAL.json разъехался с реальностью
(юнит verified, а тест уже падает) — прогони `verificationCommand` заново; если
падает, верни `in_progress`, событие в events.jsonl, чини штатно. Ledger
отражает ПРОВЕРЕННОЕ состояние, не желаемое.

### Пользователь хочет параллелить юниты
Не параллель: WIP=1 — принцип методологии (v1.41), wip-gate подсветит. Если
юниты по-настоящему независимы — это, возможно, две цели: два ledger'а нельзя
(один GOAL.json) — заведи вторую целью ПОСЛЕ закрытия первой или объедини.

### Greenfield-проект «с нуля»
Для полного цикла идея→деплой есть `/autopilot` (discover → blueprint →
kickstart → review → test). `/goal` — для brownfield-целей над существующим
кодом.

## Rules

- **Resume, never recreate** — активный `GOAL.json` не перезаписывается.
- **Approve перед записью** — декомпозиция без одобрения не сохраняется.
- **WIP=1** — следующий юнит только после verified/skipped текущего.
- **Evidence-gated** — `verified` без прогона `verificationCommand` не бывает.
- **Не гейт** — `/review`, `/test`, DoD и все хуки работают как обычно.
- **Тонкий слой** — конвейер юнита = штатный `/task`-маршрут, не собственный.
- **Fail-closed skip** — `skipped` требует `skippedReason`.
- **Match the user's language** для всего вывода.
