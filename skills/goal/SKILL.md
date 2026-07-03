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
  version: 1.45.0
  category: workflow
  tags: [goal, long-running, units, wip, resume, brownfield, ledger]
---

# Goal

## Trigger phrases

- долгая цель, режим цели, поставь цель, ставлю цель
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

### Инструменты харнеса (v1.45.0) — переходами управляет харнес, не агент

Рядом со скиллом лежат два stdlib-скрипта (в репо — `skills/goal/scripts/`,
после установки — `~/.claude/skills/goal/scripts/`):

- **`itd_goal_verify.py`** — «ОТК»: `--activate` (pending/blocked → in_progress,
  WIP=1 enforced), verify по умолчанию (САМ исполняет `verificationCommand` и
  единственный пишет `verified`+`evidence`; провал — юнит остаётся
  `in_progress`), `--recheck` (регрессия демотирует verified → in_progress),
  `--block --reason "…"` (fail-closed). Каждый переход — unit-событие в
  `events.jsonl` с `actor: "harness"`.
- **`itd_goal_report.py`** — репортёр handoff: детерминированное саммари ИЗ
  леджера (прогресс, обратное давление, таблица юнитов, первое действие
  принимающей сессии, хвост событий). `/handoff` и `/session-save` вставляют
  вывод как есть; модель добавляет прозу ВОКРУГ, но не меняет цифры.

Резолв пути (работает и в репо методологии, и в целевом проекте):

```bash
GT="skills/goal/scripts"; [ -f "$GT/itd_goal_verify.py" ] || GT="$HOME/.claude/skills/goal/scripts"
```

Пока `python3` доступен — статусы юнитов руками НЕ редактируются. Ручной
фоллбэк (та же семантика: evidence обязателен, событие в events.jsonl,
fail-closed причины) — только если python3 недоступен; скажи об этом явно.

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

1. **Активируй** следующий юнит через ОТК:
   `python3 "$GT/itd_goal_verify.py" --activate G-00X` — скрипт сам проверит
   WIP=1 (откажет, пока другой юнит in_progress), выставит `currentUnitId` и
   запишет событие `activated` (actor: harness). Если ведётся `STATE.json` —
   юнит цели И ЕСТЬ `currentUnit` (unit-механика v1.41: один и тот же юнит,
   не два учёта).
2. **Прогони через штатный конвейер**: юнит = обычная задача → `/task`
   (фича → Step 3f: scope → короткий план → код → `/test` → `/review` → коммит
   по правилам репо; баг → `/bugfix`; и т.д.). `/goal` не дублирует конвейер —
   только скоуп юнита на входе и учёт на выходе.
3. **Верифицируй через ОТК**: `python3 "$GT/itd_goal_verify.py" G-00X` —
   скрипт исполняет `verificationCommand` и при exit 0 сам переводит юнит в
   `verified` с `evidence` и событием (VCR в `itd_metrics.py` начинает
   считаться по цели автоматически). Агент `verified` руками НЕ ставит.
   Провал → юнит остаётся `in_progress`, чини в рамках конвейера; **не
   открывай следующий** (и ОТК не даст — WIP=1).
4. **Blocked — внешний блокер**: `--block G-00X --reason "ждём ключ от
   заказчика"` (fail-closed: без причины откажет); разблокировка —
   `--activate G-00X`. **Skip — только по явному решению пользователя**:
   `status: skipped` + непустой `skippedReason` (валидатор отвергнет пустой).
5. Между юнитами — инкрементальный `/session-save` (verified-юнит = значимая
   смена состояния); в его срез вставь вывод
   `python3 "$GT/itd_goal_report.py"`.

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
- [ ] Переходы статусов сделаны `itd_goal_verify.py` (руками `verified` не
      ставился; ручной фоллбэк — только без python3, и это озвучено).
- [ ] `verified` ставится только после фактического прогона команды, с `evidence`.
- [ ] `skipped` — только с непустым `skippedReason`; `blocked` — с `blockedReason`.
- [ ] Unit-события (`activated`/`verified`) записаны в `events.jsonl`.
- [ ] Открыт максимум один юнит (WIP=1); гейты конвейера не обойдены.
- [ ] Для handoff/session-save использован вывод `itd_goal_report.py`, не пересказ.

## Troubleshooting

### Цель не декомпозируется в проверяемые юниты
Критерии выходят небинарными («сделать лучше») → это признак, что цель —
исследование, а не поставка. Предложи `/advisor`/`/grill-me` для уточнения
цели, ledger не заводи.

### GOAL.json разъехался с реальностью
(юнит verified, а тест уже падает) — `python3 "$GT/itd_goal_verify.py" --recheck
G-00X`: скрипт перепрогонит команду и при провале сам демотирует юнит в
`in_progress` с событием `regressed`. Ledger отражает ПРОВЕРЕННОЕ состояние,
не желаемое.

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
- **Харнес, не агент** — статусы юнитов меняет `itd_goal_verify.py`;
  саммари для handoff генерирует `itd_goal_report.py`.
- **WIP=1** — следующий юнит только после verified/skipped текущего.
- **Evidence-gated** — `verified` без прогона `verificationCommand` не бывает.
- **Не гейт** — `/review`, `/test`, DoD и все хуки работают как обычно.
- **Тонкий слой** — конвейер юнита = штатный `/task`-маршрут, не собственный.
- **Fail-closed skip** — `skipped` требует `skippedReason`.
- **Match the user's language** для всего вывода.
