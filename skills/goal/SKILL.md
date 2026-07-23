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
  version: 1.84.0
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
  Для opt-in автономного прогона он дополнительно делает `--seal` утверждённого
  oracle, ведёт `attempts[]`, ограничивает attempts/wall-clock, принимает
  host-сигнал `--budget-exhausted --budget-kind tokens` и завершает typed stop
  с exit `3` вместо бесконечного retry.
- **`itd_goal_report.py`** — репортёр handoff: детерминированное саммари ИЗ
  леджера (прогресс, обратное давление, таблица юнитов, первое действие
  принимающей сессии, хвост событий). `/handoff` и `/session-save` вставляют
  вывод как есть; модель добавляет прозу ВОКРУГ, но не меняет цифры.

Резолв пути (работает и в репо методологии, и в целевом проекте):

```bash
GT="skills/goal/scripts"; [ -f "$GT/itd_goal_verify.py" ] || GT="$HOME/.claude/skills/goal/scripts"
SHD="skills/_shared"; [ -f "$SHD/itd_py.sh" ] || SHD="$HOME/.claude/skills/_shared"
```

Обе строки резолва вставляй в НАЧАЛО каждого shell-вызова с командами ниже
(шелл-состояние между вызовами не живёт). Запуск python-скриптов — только
`sh "$SHD/itd_py.sh" …` (НЕ голый `python3`: на Windows Git Bash это
WindowsApps-шим — live-инцидент 2026-07-11).

Пока python доступен (через `itd_py.sh`) — статусы юнитов руками НЕ
редактируются. Ручной фоллбэк (та же семантика: evidence обязателен, событие в
events.jsonl, fail-closed причины) — только если python недоступен совсем;
скажи об этом явно.

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
   - `riskTier` — для adaptive bounded-run: `low|medium|high`, фиксируется
     вместе с oracle и определяет цену checker'а;
   - `status: pending`.
   Размер юнита — одна сессия или меньше (иначе дели дальше).
3. **Покажи декомпозицию пользователю и жди явного approve** (глобальное правило
   «Plan before code»). Правки/переупорядочивание — до записи.
4. После approve запиши `GOAL.json` (поля по schema: `version`, `goal`,
   `status: active`, `createdAt`/`updatedAt` UTC ISO, `currentUnitId: ""`,
   `units[]`) и провалидируй:

```bash
sh "$SHD/itd_py.sh" scripts/validate_state.py "$PROJECT_ROOT/.itd-memory/GOAL.json" 2>/dev/null \
  || sh "$SHD/itd_py.sh" -c "import json;json.load(open('$PROJECT_ROOT/.itd-memory/GOAL.json'))"
```

(вне репо методологии валидатор недоступен — тогда хотя бы JSON-parse; схему
держи в голове по образцу `GOAL.example.json`).

#### Opt-in: bounded autonomous run envelope

Добавляй `runPolicy` **только** когда пользователь явно просит AFK/headless /
нативное автопродолжение. Обычный `/goal` остаётся без envelope и работает как
раньше:

```json
{
  "runPolicy": {
    "mode": "bounded_autonomous",
    "maxAttemptsPerUnit": 3,
    "maxWallClockSecondsPerUnit": 14400,
    "maxTokensPerSession": 100000,
    "freezeVerification": true,
    "requireApproach": true,
    "requireIndependentReview": false,
    "enforceObservedTokens": true,
    "verificationStrategy": "adaptive",
    "maxCheckpointBytes": 4096
  }
}
```

До первой активации, **после пользовательского approve и записи ledger**, ОТК
замораживает policy + `criterion` + `verificationCommand` для всех юнитов:

```bash
sh "$SHD/itd_py.sh" "$GT/itd_goal_verify.py" --seal
```

`--activate` откажет без seal. После seal изменение oracle/policy блокирует
прогон; не «пересиливай» fingerprint. Создай новый утверждённый юнит. Исключение
только для реально исчерпанного бюджета: человек повышает **именно тот** лимит,
который исчерпан, после чего `--activate --reason "human approved …"` фиксирует
reapproval. При `verificationStrategy: adaptive` каждый юнит обязан иметь
запечатанный `riskTier`: `low` использует только machine gates, `medium` —
targeted checker для остаточного риска, `high` — полный независимый checker.
`requireIndependentReview: true` остаётся совместимым override и требует полный
checker для всех юнитов.

`maxTokensPerSession` исполняется host/cost-tracker'ом. При
`enforceObservedTokens: true` каждая verification-попытка передаёт накопленный
счётчик `--tokens-used N`; достижение ceiling останавливает юнит ДО запуска
verificationCommand. Внешний stop без численного наблюдения не принимается:

```bash
sh "$SHD/itd_py.sh" "$GT/itd_goal_verify.py" --budget-exhausted G-00X \
  --budget-kind tokens --budget-observed 100000 \
  --reason "host token ceiling reached"
```

### Step 2: Ведение — один юнит за раз (WIP=1)

Цикл, пока есть `pending`-юниты и пользователь не остановил:

1. **Активируй** следующий юнит через ОТК:
   `sh "$SHD/itd_py.sh" "$GT/itd_goal_verify.py" --activate G-00X` — скрипт сам проверит
   WIP=1 (откажет, пока другой юнит in_progress), выставит `currentUnitId` и
   запишет событие `activated` (actor: harness). Если ведётся `STATE.json` —
   юнит цели И ЕСТЬ `currentUnit` (unit-механика v1.41: один и тот же юнит,
   не два учёта).
2. **Прогони через штатный конвейер**: юнит = обычная задача → `/task`
   (фича → Step 3f: scope → короткий план → код → `/test` → `/review` → коммит
   по правилам репо; баг → `/bugfix`; и т.д.). `/goal` не дублирует конвейер —
   только скоуп юнита на входе и учёт на выходе.
3. **Верифицируй через ОТК**: `sh "$SHD/itd_py.sh" "$GT/itd_goal_verify.py" G-00X` —
   скрипт исполняет `verificationCommand` и при exit 0 сам переводит юнит в
   `verified` с `evidence` и событием (VCR в `itd_metrics.py` начинает
   считаться по цели автоматически). Агент `verified` руками НЕ ставит.
   Провал → юнит остаётся `in_progress`, чини в рамках конвейера; **не
   открывай следующий** (и ОТК не даст — WIP=1).
   Для bounded-run каждая попытка обязана назвать новый подход, передать
   host-token meter и приложить adjudicated Verification Loop receipt, когда
   запечатанный режим юнита равен `targeted` или `full`. Receipt создаётся по
   `docs/VERIFICATION_LOOP.md` для claim id, равного `G-00X`: machine producer
   исполняет тот же `verificationCommand`, checker связывает exact prompt/report,
   а adjudicator проверяет risk route и текущий candidate:

   ```bash
   sh "$SHD/itd_py.sh" "$GT/itd_goal_verify.py" G-00X \
     --approach "заменил polling на event wait" \
     --tokens-used 42000 \
     --verification-receipt ".itd-memory/verification-loop/receipts/<candidate>/G-00X-adjudication.json"
   ```

   ОТК пишет `{approach, verificationCommand, outcome, evidence,
   observedTokens, checkerMode, verificationReceipt}` в `attempts[]`. Красный
   machine run и отсутствующий/невалидный checker всё равно расходуют попытку
   как `failed`/`unverified`, но receipt обязателен только для перехода в
   `verified`. Для
   `machine_only` полный второй анализ запрещён как лишняя стоимость; для
   `targeted` checker читает только непокрытые машиной claims/риски. Exit `3` / `stopReason:
   budget_exhausted` — жёсткий конец текущего autonomous run: не повторяй
   автоматически и не активируй следующий юнит.
4. **Blocked — внешний блокер**: `--block G-00X --reason "ждём ключ от
   заказчика"` (fail-closed: без причины откажет); разблокировка —
   `--activate G-00X`. **Skip — только по явному решению пользователя**:
   `status: skipped` + непустой `skippedReason` (валидатор отвергнет пустой).
5. Между юнитами — инкрементальный `/session-save` (verified-юнит = значимая
   смена состояния); в его срез вставь компактную дельту ≤4 КБ:
   `sh "$SHD/itd_py.sh" "$GT/itd_goal_report.py" --compact`. Полный report
   оставь для диагностики, не переноси его между раундами по умолчанию.

#### Opt-in: `working_deadline` для повседневного unit

Профиль включается **явно для конкретного low/medium-risk unit**. Unknown/high
risk не входят в daily-профиль и остаются на strict/release path:

```bash
sh "$SHD/itd_py.sh" "$GT/itd_goal_verify.py" --activate G-00X \
  --work-profile working_deadline
```

Host запускает монотонный таймер одновременно с успешной активацией и передаёт
наблюдаемое время в секундах. До следующей дорогой попытки и перед ОТК-прогоном
обязательно выполняется deadline check. На soft boundary нужны все четыре поля
checkpoint — ничего не выдумывается харнесом:

```bash
sh "$SHD/itd_py.sh" "$GT/itd_goal_verify.py" --deadline-check G-00X \
  --elapsed-seconds 1800 \
  --checkpoint-ready "что готово" \
  --checkpoint-blocker "блокер или none" \
  --checkpoint-remainder "остаток" \
  --checkpoint-estimate "оценка"
```

- `<1800s` — только сохраняется монотонное host-observation;
- `1800…2699s` — полный checkpoint обязателен один раз;
- `>=2700s` — exit `3`, status `recovery_required`, typed
  `budget_exhausted` с observed/limit evidence. `currentUnitId` сохраняется как
  WIP-backpressure; partial work не становится verified. Возобновление —
  только после полного дешёвого checkpoint (его можно дописать тем же
  `--deadline-check`, не снимая stop) и новой явной команды
  `--activate G-00X --reason "…"`, которая начинает новый observed cycle.

ОТК-прогон активного profile-unit также требует актуальный
`--elapsed-seconds`; при hard boundary verificationCommand не запускается.
Успешный verified-unit ставит durable handoff barrier. После того как результат
реально показан пользователю и пришёл новый host/user turn, адаптер фиксирует
provenance:

```bash
sh "$SHD/itd_py.sh" "$GT/itd_goal_verify.py" --ack-handoff G-00X \
  --reason "result returned; new user turn continued the goal"
```

До acknowledgement следующий unit не активируется. Это дешёвый handoff, не
автоматический explicit session close. Канонические thresholds и инварианты
берутся из `skills/_shared/WORKING_DEADLINE_POLICY.json`, а не дублируются в
host adapter.

#### Автономный прогон (headless / AFK / долгий юнит) — anti-early-stop (v1.50.0)

Когда юниты гонятся без пользователя у руля (headless-запуск, AFK-блок,
долгий одиночный юнит), добавь себе в рабочий контекст напоминание
(vendor-canonical снипет Fable 5-эры):

> You are operating autonomously. The user is not watching in real time and
> cannot answer questions mid-task, so asking "Want me to…?" / "Shall I…?"
> will block the work. For reversible actions that follow from the original
> request, proceed without asking. Before ending your turn, check your last
> paragraph: if it is a plan, an analysis, a question, or a promise about work
> you have not done ("I'll…", "далее проверю…"), do that work now with tool
> calls. End your turn only when the unit is verified or you are blocked on
> input only the user can provide.

Это профилактика того же класса дефекта, который `hooks/narration-final.sh`
ловит постфактум (нарратив-финал). Границы не отменяются: необратимые /
data-sensitive действия по-прежнему требуют человека — автономность
распространяется только на обратимые шаги внутри скоупа юнита.

**Host-native continuation, не новый runtime.** После approve + `--seal` адаптер
может привязать текущую цель к нативному goal/automation механизму хоста. Каждый
re-entry выполняет ровно один WIP-юнит: прочитать `GOAL.json` → продолжить
`currentUnitId`/первый pending → `/task` → checker по sealed risk tier → ОТК. Продолжать
можно только при `in_progress|pending`; `verified`, `blocked`,
`recovery_required` и `budget_exhausted` уходят в human triage. Manual fallback — обычное «продолжай
цель», поэтому исчезновение host-фичи теряет автопробуждение, но не state.

Это разрешение относится к **явно запущенной пользователем bounded goal** и
только к обратимым изменениям в её scope. Периодические фоновые scheduler'ы
по-прежнему read-only; push/merge/deploy/денежные и иные необратимые действия
остаются на human gate.

### Step 3: Закрытие цели

Все юниты `verified`/`skipped` → покажи финальный срез (юниты + evidence),
поставь `status: done`, `updatedAt`, `currentUnitId: ""`. Отказ от цели —
`status: abandoned` (юниты не трогай — история). Предложи `/session-save`.

### Опциональный 5/5 evaluator — только для измерения эффективности

Когда пользователь просит доказать эффективность loop, а не просто завершить
цель, собери контракт `docs/templates/itd-memory/five-star-eval.schema.json` и
запусти:

```bash
sh "$SHD/itd_py.sh" "$GT/itd_goal_score.py" \
  --input .itd-memory/experiments/<run>/FIVE_STAR_EVAL.json --json
```

Пять баллов бинарны: quality, efficiency, memory, understanding, integrity.
Пороговые значения зашиты в evaluator, поэтому эксперимент не может повысить
собственный балл ослаблением config. `FIVE_STAR` требует одновременно: ≥5
чистых parity-пар, frozen oracle до запусков, recall ≥95%, precision ≥90%,
relative quality lift ≥20%, median time/tokens ≤1.5×, high-risk time ≤2×,
повторы −50%, context growth ≤10%, checkpoint ≤4096 B, immediate и 24h quiz
≥80%, 0 critical unknown/cognitive surrender/extra rounds after DoD. Любой
провал даёт non-zero exit с `path + WHY + FIX`; отсутствие `--input` — тихий
no-op. Infrastructure error аннулирует integrity, а не маскируется повтором.

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
- [ ] Bounded-run: policy + oracle запечатаны `--seal` после approve; каждая
      попытка имеет approach, observed tokens, sealed checkerMode и typed stop.
- [ ] Handoff использует `--compact`; полный event/history report не переносится
      между раундами без диагностической необходимости.
- [ ] Оценка 5/5, если заявлена, получена только exit 0 `itd_goal_score.py`, а
      не субъективным усреднением.

## Troubleshooting

### Цель не декомпозируется в проверяемые юниты
Критерии выходят небинарными («сделать лучше») → это признак, что цель —
исследование, а не поставка. Предложи `/advisor`/`/grill-me` для уточнения
цели, ledger не заводи.

### GOAL.json разъехался с реальностью
(юнит verified, а тест уже падает) — `sh "$SHD/itd_py.sh" "$GT/itd_goal_verify.py"
--recheck G-00X`: скрипт перепрогонит команду и при провале сам демотирует юнит в
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
- **Bounded means bounded** — exit 3 / `budget_exhausted` останавливает host
  continuation; возобновление только после явного повышения исчерпанного лимита.
- **Oracle immutable** — bounded criterion/verificationCommand фиксируются
  `--seal`; реализация не меняет собственный экзамен.
