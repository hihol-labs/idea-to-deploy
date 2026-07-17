# Harness Engineering Map: idea-to-deploy ↔ Харнес-инженерия

> Актуальность: **2026-07-16**, idea-to-deploy **v1.91.0**.
> Текущий инвентарь: 40 skills, 10 subagents, 29 hooks, 11 hard gates, 18 soft hooks.
> Источник: [Harness Engineering (walkinglabs)](https://walkinglabs.github.io/learn-harness-engineering/ru/) + для оси I — исследование Anthropic «Effective harnesses for long-running agents»
> Цель: проверить, в полной ли мере методология отражает философию, 5 принципов и инструменты харнес-инженерии; артикулировать gap'ы; зафиксировать осознанные out-of-scope решения.

<!-- harness-docs-state: docs/HARNESS_DOCS_STATE.json -->

---

## 1. Что это за документ

Учебник [«Харнес-инженерия»](https://walkinglabs.github.io/learn-harness-engineering/ru/) формализует дисциплину проектирования надёжных систем управления AI-агентами. Его центральный тезис: **задача не в том, чтобы сделать модель умнее, а в том, чтобы построить замкнутую «рабочую систему» (harness) с явными правилами и границами.** Курс выделяет 5 ключевых принципов и библиотеку готовых шаблонов (`AGENTS.md`, `feature_list.json`).

`idea-to-deploy` — это методология (harness) поверх Claude Code. Документ применяет ту же дисциплину честного маппинга, что и [`DESIGN_SPACE.md`](DESIGN_SPACE.md) (карта против «Dive into Claude Code»), и отвечает на три вопроса:

1. **Что из 5 принципов покрыто** (✅).
2. **Где покрытие частичное** и чего не хватает (◐).
3. **Что осознанно оставлено out-of-scope** и почему.

Документ намеренно честный: каждый gap помечен явно. Код-кандидаты **не реализуются вне signal-gated процесса** — см. §6 и [`ROADMAP_v1.21.md`](../ROADMAP_v1.21.md).

> **Важно про версию.** Текущие claims сверяются с `HARNESS_DOCS_STATE.json` и замороженным `HARNESS_CONFORMANCE_CONTRACT.json`; исторические версии ниже описывают происхождение механизмов, но не являются текущим score.

## 2. Источник

- **Учебник:** [walkinglabs.github.io/learn-harness-engineering/ru](https://walkinglabs.github.io/learn-harness-engineering/ru/) — 12 лекций (от режимов отказа агентов к практическим решениям), практические проекты, библиотека шаблонов.
- Принципы ниже пронумерованы `H1–H5`, шаблоны — `T1–T2`. Нумерация внутренняя.

Документ-сестра: [`DESIGN_SPACE.md`](DESIGN_SPACE.md) (16 принципов «Dive into Claude Code»). Рамки пересекаются; ссылки на `K…` указывают на строки той карты. NB: §4 (K4) в DESIGN_SPACE датирован v1.20.3 и **предшествует** хуку `context-budget.sh` (v1.21.0) — здесь оценка по бюджету контекста актуальнее.

## 3. Методология маппинга

Статусы: ✅ **покрыто** (явная реализация с контрактом) · ◐ **частично** (gap артикулирован в §5) · ❌ **gap** (не реализовано и не замещено).

Проверка текущего состояния: **40 skills, 10 subagents, 29 hooks, 11 hard gates, 18 soft hooks**, 2 Quality Gates, слой контрактов `.itd/`, host-neutral `.itd-memory/`, deterministic behavioural floor и свежий live-model evidence.

## 4. Таблица соответствия

### 4.1. Философия (мета-уровень)

| Тезис курса | Статус | Воплощение |
|---|:---:|---|
| **«Harness важнее, чем умная модель»** — замкнутая система с явными правилами и границами | ✅ | 40 public skills + 10 agents + 29 hooks + 2 Quality Gates; vendor-neutral `.itd/`/`.itd-memory/` contracts и host adapters для Claude/Codex. |
| **Харнес-инженерия как output** — методология не только *сама* харнес, но и *учит строить* харнес продукта пользователя | ✅ (v1.32.0–v1.33.0) | **Два слоя.** *Operating*: ITD = харнес над Claude Code. *Output* (порты Day-3/5): врезки проектируют харнес агента пользователя — память/контекст (`/blueprint` Step 1.6, `/security-audit` `MEM-1..7`), eval-петли (`/test`, `/harden` `EVAL-1`), Zero-Trust guardrails (`/harden` `ZT-1`, semantic gating = ASK). ADR-001: учим+аудируем, не движок |

### 4.2. 5 ключевых принципов

| # | Принцип курса | Статус | Реализация в idea-to-deploy (v1.91.0) | Evidence / комментарий |
|---|---|:---:|---|---|
| **H1** | **Ограничение поведения** | ✅ | Graduated trust policy, 11 computational hard gates, explicit invocation, permission/scope contracts и полная Claude/Codex parity. | `verify_graduated_trust.py`, `verify_all_hard_gate_host_parity.py` |
| **H2** | **Сохранение контекста** — между сессиями длинных задач | ✅ | `/session-save` → `session_*.md` + `MEMORY.md`; статус-таблица `CLAUDE.md` для resume; автосохранение на вехах; `pre-flight-check.sh` (git + `MEMORY.md` в контекст); `session-open-diagnostic.sh`; `crash-recovery.sh`. **+ v1.21.0:** `context-budget.sh` (PreToolUse — мягко тормозит unbounded-дампы в контекст) + `UNIT_CONTEXT_MANIFEST.json` (свежий ограниченный per-node контекст) | Принцип «между сессиями» — полностью. Смежный `K4` (бюджетирование *внутри* сессии) теперь **частично закрыт** `context-budget.sh` (мягкое напоминание, не жёсткая budget-модель) — улучшение vs DESIGN_SPACE §5.2 |
| **H3** | **Предотвращение преждевременного завершения** — защита от ложного успеха | ✅ | **Сильнейшая ось.** 2 Quality Gate; бинарные rubric'и `BLOCKED/PASSED`; стоп после **3 ошибок подряд**; `check-commit-completeness.sh` + `check-review-before-commit.sh` (hard-block); `stuck-detection.sh`. **+ v1.21.0 fail-closed гейты:** `ACCEPTANCE_CONTRACT.json` («done = traceable proof-checklist, не ощущение агента»; статусы `pending/passed/failed/recovery_required`); `VERIFICATION_CONTRACT.json` (`failClosed`, `RECOVERY_REQUIRED` вместо «passed» при un-run/ambiguous); **двухстадийный `/review`** (Stage A spec-compliance — «красивый код, решающий не ту задачу» → `BLOCKED`); fail-closed `/test` (passed только при реально полученном evidence); `ROOT_CAUSE.md`-гейт в `/bugfix`; `BRANCH_FINISH.md` | — |
| **H4** | **Верификация через тестирование** | ✅ | Deterministic structural/snapshot/behavioural floor плюс weekly/manual live-model benchmark без permanent-disable guard. | Fresh post-freeze transcript/output hashes и независимый replay `verify_snapshot.py`; отсутствие credential = UNVERIFIED, не PASS. |
| **H5** | **Наблюдаемость** | ✅ | Paired intent/outcome traces; estimated и host-observed token counters разделены с provenance; session/unit attribution. | Control-quality FP/FN metrics и machine-checked docs/version freshness fail closed. |

### 4.3. Библиотека шаблонов

| # | Шаблон курса | Статус | Аналог в idea-to-deploy (v1.21.0) | Комментарий |
|---|---|:---:|---|---|
| **T1** | **`AGENTS.md`** — операционный манифест/память агента | ✅ | `CLAUDE.md` (нативный эквивалент) + `agents/*.md` (10 субагентов) + **слой `.itd/`** как машиночитаемый операционный манифест: `PROJECT_CONTRACT.md`, `EXECUTION_POLICY.json`, `PERMISSION_MATRIX.md`, `DATA_POLICY.md`, `FALLBACK_POLICY.md` | Расхождение по имени закрыто в v1.84.0: `AGENTS.md`-алиас в корне репо (указатель на CLAUDE.md, кросс-тул-портируемость); `/adopt` предлагает такой же алиас проекту |
| **T2** | **`feature_list.json`** — машиночитаемый реестр «сделано/протестировано» против преждевременного завершения | ✅ | **`ACCEPTANCE_CONTRACT.json`** (v1.21.0): машиночитаемый proof-checklist критериев приёмки, выведенный из запроса пользователя, со схемой (`id/criterion/source/evidence/verificationCommand/status`) и `doneRule` **fail-closed** + **`VERIFICATION_CONTRACT.json`** (исполняемые команды верификации, `failClosed`) | **Намерение курса реализовано и усилено** (fail-closed). Отличие по форме: это per-unit контракт приёмки от запроса, а не персистентный мульти-фичный ledger проекта. Для большинства задач функционально эквивалентно (и строже). **v1.44.0 закрывает и форму**: `/goal` ведёт персистентный мульти-юнитный реестр цели `.itd-memory/GOAL.json` (schema `goal.schema.json`, валидация `validate_state.py`) поверх per-unit контрактов — прогресс долгой цели переживает смерть сессии программно |

### 4.4. Ось I: Initialization phase & handoff-readiness (первоисточник Anthropic, добавлена v1.40.0)

До v1.40.0 карта строилась только по 5 принципам walkinglabs и была **структурно слепа** к аспекту первоисточника Anthropic («Effective harnesses for long-running agents»): *инициализация — выделенная фаза первой сессии, производящая bootstrap-контракт; каждая последующая сессия обязана заканчиваться handoff-ready, потому что может умереть в любой момент.* Компенсаторная половина (context recovery на старте) была реализована давно и сильнее оригинала; проактивная половина закрыта в v1.40.0. Эта секция фиксирует ось явно, чтобы карта не показывала «остатков нет», не видя этот аспект.

| # | Элемент исследования | Статус | Воплощение |
|---|---|:---:|---|
| **I1** | **Инициализация как выделенная фаза** — первая сессия производит bootstrap, не бизнес-код | ✅ (v1.40.0) | `/kickstart` Phase 3 шаги 7–8: скаффолд `.itd/` (13 контрактов) + `.itd-memory/STATE.json` + Initialization Acceptance Checklist как гейт выхода из фазы. Brownfield: `/adopt` Step 3.5 — тот же скаффолд, **opt-in** (осознанный tradeoff v1.39.0: контракты не навязываются существующим проектам) |
| **I2** | **Запускаемое окружение** — поднять с холода одной командой | ✅ (v1.40.0) | Обязательный `commands.bootstrap` в каждом `STARTER.json` (норма в `starters/README.md`); Phase 3 checklist требует успешный прогон bootstrap с чистого клона |
| **I3** | **Проверяемый тестовый фреймворк** — ≥1 проходящий пример-тест | ✅ (v1.40.0) | `/kickstart` Phase 3.2: тест-фреймворк ставится **с одним проходящим example-тестом** (доказательство, что харнес держит вес, а не просто установлен) |
| **I4** | **Bootstrap-контракт** — start commands / current state / structure из содержимого репо | ✅ (v1.40.0) | `CLAUDE.md` (команды запуска/тестов, статус-таблица) + `.itd/PROJECT_CONTRACT.md` + `.itd-memory/STATE.json` — с v1.40.0 **скаффолдятся создателем** (`/kickstart`/`/adopt`), а не лежат шаблонами без wired-создателя (это был разрыв «декларация ↔ реальность» уровня v1.37.0) |
| **I5** | **Декомпозиция задач** с критериями приёмки | ✅ | `IMPLEMENTATION_PLAN.md` (8–12 шагов с verification per шаг) + per-unit `ACCEPTANCE_CONTRACT.json` (fail-closed — строже курса) |
| **I6** | **Git-коммит как чекпоинт** после инициализации | ✅ | Phase 3.6 initial commit + пункт checklist «everything committed» |
| **I7** | **Handoff-ready в конце каждой сессии** — чистый чекпоинт + свежий прогресс-артефакт | ✅ (soft by design, v1.40.0) | Stop-хук `handoff-readiness.sh`: computational-детект (dirty git tree + отсутствие свежего `session_*.md`) → мягкий hint «сделай `/session-save` или `/handoff`», rate-limited. По правилу §8.3 «закончил ли пользователь работу» — семантика, поэтому hint, а не deny. Компенсаторная половина — `pre-flight-check` / `session-open-diagnostic` / `crash-recovery` на старте следующей сессии |

**Дополнение v1.41.0 (контроль скоупа и проверенного завершения):** (a) **WIP=1** — явное правило в обоих CLAUDE.md-шаблонах («следующий unit — только после end-to-end верификации текущего») + `currentUnit` singular by construction + новый soft-хук `wip-gate.sh` (Edit/Write вне `SCOPE_LOCK.Allowed` при unit'е в `verifying`/`recovery_required` → hint); (b) **машиночитаемая поверхность скоупа теперь читается на входе сессии** — `pre-flight-check.sh` инжектит `currentUnit`/`nextAction`/blockers/непройденные гейты из `STATE.json`; (c) **VCR** (Verified Completion Rate = verified/activated units) считается в `itd_metrics.py` по unit-событиям `events.jsonl`, которые `/task` пишет при активации/верификации unit'а. Жёсткий deny «VCR<1.0 → нельзя активировать» сознательно НЕ реализован: «активация задачи» не существует как tool-событие, а суждение «это новая задача или фикс текущей» — семантика (§8.3: hint, не deny).

**Остаток оси закрыт в v1.44.0:** T2-кандидат «персистентный мульти-фичный реестр, переживающий сессии» активирован по второму сигналу (критерии ROADMAP): `/goal` + `.itd-memory/GOAL.json` — упорядоченный реестр юнитов цели (`id/criterion/verificationCommand/status`, schema `docs/templates/itd-memory/goal.schema.json`, fail-closed валидация в `validate_state.py`), декомпозиция с одобрением пользователя, ведение через штатный конвейер `/task` при WIP=1, unit-события в `events.jsonl` (VCR считается по цели автоматически), resume с первого не-verified юнита; `pre-flight-check.sh` инжектит «Цель: X — N/M юнитов verified» на входе каждой сессии. До v1.44.0 было реализовано per-unit (`ACCEPTANCE_CONTRACT.json`) + VCR (v1.41.0).

**v1.45.0 — «переходами управляет harness, а не агент» (последний принцип feature-lists) тоже закрыт:** `skills/goal/scripts/itd_goal_verify.py` («ОТК») — единственный писатель `verified`: сам исполняет `verificationCommand`, enforc'ит WIP=1 на активации, gate on passing (verify только из in_progress), провал держит юнит, `--recheck` демотирует регрессию, `--block` fail-closed по причине; все переходы — события `actor: "harness"`. `itd_goal_report.py` — репортёр handoff: детерминированное саммари из леджера для `/handoff`/`/session-save` (компонент «автоматический отчёт о смене»). Статус юнита `blocked` добавлен в схему (полный автомат курса: pending/in_progress/blocked/verified + skipped). Функциональное покрытие — `tests/verify_goal_tools.py` (20 проверок, оба интерпретатора + windows-verify CI). Осознанная дельта от курса остаётся одна: «passing необратим» — у нас `--recheck` честно демотирует регрессировавший verified (леджер отражает проверенную реальность).

## 5. Детальный разбор

### 5.1. H2 / бюджетирование контекста (◐ смежный, = K4) — **улучшено в v1.21.0**

Принцип «сохранение контекста между сессиями» — ✅ (session-memory образцовая). Смежный аспект — бюджет контекста *внутри* длинной сессии. В v1.21.0 добавлен **`context-budget.sh`** (PreToolUse, item 16): детектит команды, грозящие свалить в контекст большой unbounded-вывод (raw HTTP-тело, `cat` крупного файла, широкий `grep/find/rg` без лимита), и мягко рекомендует ограничить/суммировать вывод. Это soft-reminder, не жёсткая budget-модель и не slope-управление перед каждым model-call — поэтому статус смежного gap'а **◐ (улучшен с ❌), а не ✅.** Полный разбор — `DESIGN_SPACE.md §5.2`.

### 5.2. H3 / T2 — машиночитаемая защита от ложного успеха (закрыто в v1.21.0)

До v1.21.0 цель «предотвращение преждевременного завершения» достигалась через Quality Gates + бинарные rubric'и + 3-fail-stop + hard-block хуки, но **без** машиночитаемого ledger'а (это был частичный T2). v1.21.0 закрывает разрыв слоем `.itd/`:

- **`ACCEPTANCE_CONTRACT.json`** — «done» определён как traceable proof-checklist, выведенный из запроса *до* реализации. `doneRule`: unit готов, только когда каждый критерий `passed` с приложенным evidence; критерий без evidence / с un-run командой остаётся `pending` и **блокирует** (fail-closed).
- **`VERIFICATION_CONTRACT.json`** — исполняемые команды с `passFailParser`; `failClosed`: отсутствует/не запущена/неоднозначна → статус `RECOVERY_REQUIRED`, **никогда не `passed`**.
- **Двухстадийный `/review`** — Stage A spec-compliance гейт сверяет диф с `ACCEPTANCE_CONTRACT` / `UNIT_CONTEXT_MANIFEST` / `SCOPE_LOCK`; spec FAIL → `BLOCKED` независимо от качества кода.

Это и есть роль `feature_list.json` из курса, реализованная строже (fail-closed). Остаточный кандидат — персистентный мульти-фичный реестр поверх per-unit контрактов (для трекинга всех P0/P1/P2 фич проекта программно).

### 5.3. H5 / live execution tracing (✅, = K15) — закрыто в v1.21.x

Наблюдаемость была post-hoc (`cost-tracker.sh` + session-memory + `ITD_REPORT.md`). **v1.21.x добавил `execution-trace.sh`** — PreToolUse-хук, который пишет по строке JSON (`{ts, tool, target}`) на каждый tool-call в `.claude/traces/session-{id}.jsonl`. Это даёт live, реиграбельный лог «какой инструмент против чего отработал» — для отладки самой методологии и user-oversight.

Свойства, по которым это «честное» закрытие, а не галочка:
- **Zero-context:** хук ничего не инжектит в контекст модели → не тратит context-budget (не конфликтует с H2).
- **Opt-in / fail-safe:** активен только при регистрации в `settings.json` (matcher `*`), как `cost-tracker.sh`; любая ошибка → `exit 0`, сессия не ломается; `.claude/` уже в `.gitignore` → трейсы не попадают в репозиторий.
- **Прошёл харнес репозитория:** зарегистрирован в `EXEMPT` списка `verify-sync-to-active.sh`; M-C10-схема-чек (`hookEventName: PreToolUse`, без корневого verdict) — pass.

Полный разбор той же оси в рамке «Dive into Claude Code» — `DESIGN_SPACE.md §5.7 (K15)`.

### 5.4. Минорные кандидаты

- **`AGENTS.md`-алиас** (T1): тонкий алиас на `CLAUDE.md` в генерируемых проектах для кросс-тул-агентов, читающих нейтральный `AGENTS.md`. Косметика портируемости, <1 дня.
- **Персистентный `feature_list.json`** (T2): ~~проектный реестр фич поверх per-unit `ACCEPTANCE_CONTRACT`~~ — **закрыт в v1.44.0** по второму сигналу (вопрос пользователя про аналог codex `/goal`): реализован как `/goal` + `.itd-memory/GOAL.json` (мульти-юнитный реестр цели, resume между сессиями программно). См. §4.4.

## 6. Сводка

| Уровень | ✅ Покрыто | ◐ Частично | ❌ Gap |
|---|---|---|---|
| **Философия** | «harness важнее модели» | — | — |
| **5 принципов** | H1, H2, H3, H4, **H5** | — | — |
| **2 шаблона** | T1, **T2** (через `.itd/`) | — | — |
| **Ось I (Anthropic, v1.40.0)** | I1–I7 (init-фаза, bootstrap-контракт, env-boot, example-тест, декомпозиция, git-чекпоинт, handoff-readiness) + персистентный goal-ledger (`/goal` + `GOAL.json`, v1.44.0) | — | — |

**Итог: 5,0/5,0** по замороженному `HARNESS_CONFORMANCE_CONTRACT.json`: по одному баллу за H1–H5 при exit 0 всех независимых evidence-команд. Narrative этой карты не является scorer'ом; обоснование, evidence и границы вывода собраны в [`HARNESS_CONFORMANCE_REPORT.md`](HARNESS_CONFORMANCE_REPORT.md).

**Содержательных остатков по принципам и шаблонам нет.** Остаётся один минорный косметический кандидат (см. §5.4: `AGENTS.md`-алиас для кросс-тул-портируемости); персистентный мульти-фичный ledger закрыт в v1.44.0 (`/goal` + `GOAL.json`, §4.4) — это было улучшение формы, а не пробел принципов. Карта остаётся сигнал-триггер-картой на случай изменений курса или методологии.

**Обновление (v1.32.0–v1.33.0 — порты Day-3/5).** Харнес-инженерия в ITD теперь читается в **два слоя**: (1) *operating* — ITD сам является харнесом над Claude Code (это §4–§5 выше); (2) *output* — методология учит и аудирует построение харнеса *продукта пользователя*. Day-3 (Context Engineering, v1.32.0) и Day-5 (Zero-Trust + SDD, v1.33.0) добавили именно output-слой: дизайн памяти/контекста, eval-петель и zero-trust guardrails врезками в `/blueprint`·`/discover`·`/security-audit`·`/harden`·`/test`·`/review`·`/adopt`. Принцип ADR-001 неизменен: методология *проектирует и проверяет* харнес продукта, но не *является* его рантаймом (semantic gating = ASK, `agents-cli` = icebox).

**История оценки.** Ранние self-score опирались на наличие файлов и устаревающие счётчики. Текущий контур требует 11/11 behavioural hard-gate coverage, свежий live-model run с независимым oracle, measured FP/FN и freshness guard; любые missing/stale/UNVERIFIED evidence дают ноль соответствующей оси.

## 7. Следствия для ROADMAP

Документ **не меняет** решения [ROADMAP v1.21 DEFERRED](../ROADMAP_v1.21.md). Его роль:

1. **Честная позиция** для аудитории, говорящей на языке харнес-инженерии.
2. **Закрытие H5 (v1.21.x) — по явному запросу мейнтейнера**, что удовлетворяет signal-критерий ROADMAP (activated user с конкретным запросом), а не velocity ради velocity. Реализовано минимальным opt-in хуком (`execution-trace.sh`) без раздувания surface — не cargo-cult.
3. **Оставшиеся кандидаты — только косметические** (форма, не принципы), по-прежнему signal-gated:

| Кандидат | Тип | Effort | Триггер |
|---|---|:---:|---|
| ~~Персистентный `feature_list.json`~~ | T2 (форма) | — | **Активирован и закрыт в v1.44.0** по второму сигналу (вопрос пользователя про режим долгой цели) — `/goal` + `.itd-memory/GOAL.json`, см. §4.4/§5.4 |
| `AGENTS.md`-алиас в генераторах | T1 (портируемость) | <1d | Запрос на кросс-тул-портируемость |

Оставшийся кандидат не активируется без external signal (критерии — `ROADMAP_v1.21.md §"When to revisit v1.21"`); T2-строка сохранена как прецедент корректной активации по сигналу.

## 8. Классификация контролей: feedforward/feedback × computational/inferential

> Источник модели: `product-factory-os` `docs/METHODOLOGY.md` (control-harness). Перенесена как **аналитическая линза** (не механизм) — по запросу разобрать, какие из 16 хуков являются настоящими блокерами, а какие — мягкими/наблюдательными, и зафиксировать правило дизайна будущих хуков.

Курс харнес-инженерии описывает контроли по двум независимым осям:

- **Контур.** *Feedforward* — контроль действует **до/в начале** действия, формируя или ограничивая его (превентивно). *Feedback* — контроль реагирует **после** действия (коррекция или наблюдение).
- **Природа.** *Computational* — детерминированная механическая проверка (regex, счётчик, наличие файла, git-состояние); решение не зависит от суждения модели. *Inferential* — сигнал, который **интерпретирует модель** (инжектируемый хинт/контекст); хук вычисляет, *когда* подсветить, но изменение поведения зависит от того, прислушается ли модель.

Центральный принцип PFO: **computational — для блокирующих инвариантов, inferential — для семантики.** Жёсткий блок (`deny`) должен быть чисто вычислительным; если проверка требует семантического суждения — она обязана быть мягкой (hint), а не `deny`, иначе в гейт входит недетерминизм.

### 8.1. Все хуки (29) по квадрантам

| | **Computational** (детерминированный) | **Inferential** (интерпретирует модель) |
|---|---|---|
| **Feedforward** (до действия) | **Блокирующие гейты (`deny`):** `check-tool-skill` · `check-commit-completeness` · `check-review-before-commit` · `check-dod-before-commit` · `check-skill-completeness` · `pii-egress-guard` · `completion-gate` (v1.51.0) · `state-guard` (v1.76.0, c v1.78.0 гейтит и Bash-канал — single-writer гейт state-леджера; его PostToolUse-ноги валидации/heartbeat — soft) · `cost-tracker` (PreToolUse-ветка запрещает следующую дорогую попытку у budget ceiling; PostToolUse-учёт остаётся soft). **Soft-детекторы (allow + warn/hint/ask):** `careful`* · `freeze`* · `wip-gate`*** (v1.41.0) · `model-policy` (v1.91.0: advisory для weaker model; host ASK, но не hard deny, для небезопасного low-effort override) | **Формирование контекста (soft):** `check-skills` · `context-aware` · `pre-flight-check` · `session-open-diagnostic` · `context-budget` |
| **Feedback** (после действия) | **Блокирующие стоп-гейты (`block`, SubagentStop):** `narration-final` (v1.49.0) · `verdict-contract` (v1.51.0). **Наблюдаемость / учёт (soft):** `execution-trace`** · `record-agent-skill` · `risk-score` · `cross-review-precommit` (fail-open) · `handoff-readiness` (v1.40.0) · `completion-signals` · `completion-stop` (v1.51.0) | **Само-коррекция (soft):** `stuck-detection` · `crash-recovery` |

`*` `careful`/`freeze` — computational-детекторы, но **не блокируют**: оба `exit 0, permissionDecision: allow` (careful предупреждает о деструктивных командах, freeze — о правках замороженных файлов), поэтому в hard-гейты НЕ входят. `freeze` с v1.42.0 always-on, действует только при активном scope-lock state-файле (его пишут `/bugfix`/`/refactor`/`/perf`); `careful` с v1.37.0 always-on. `**` `execution-trace` — тайминг PreToolUse, но роль наблюдательная (пишет JSONL-трейс, zero-context, никогда не блокирует) → отнесён к feedback по роли. `***` `wip-gate` — детект computational, но энфорсмент **soft by design**: «новая задача или фикс текущей» — семантика, по §8.3 это hint, не deny. **11 hard-гейтов = 9 feedforward (`deny`) + 2 feedback SubagentStop (`block`)** — сверяется тестом `verify_hook_table_completeness.py` (G-005).

> **Fixture-proof self-grading (v1.59.0, ось 1 / G-003).** Метки ✅ по H1/H3 (энфорсмент) держатся не на «хук существует», а на **поведенческом доказательстве**: ровно **11 hard-гейтов** (те, что реально `deny`/`block`) — `check-review-before-commit`, `check-dod-before-commit`, `check-commit-completeness`, `check-skill-completeness`, `check-tool-skill`, `pii-egress-guard`, `narration-final`, `verdict-contract`, `completion-gate`, `state-guard`, `cost-tracker` — каждый подпёрт тестом, который **спавнит хук и проверяет реальный exit-2/block** (не doc-grep). Грид `tests/verify_harness_map_fixtures.py` держит **hard-gate coverage = 11/11**: он выводит hard-множество тем же blocking-decision-регэкспом, что и `verify_gate_taxonomy.py`, и падает, если появится новый hard-гейт без проходящего behavioural-теста — гейт не может получить ✅ без доказанного block/deny. Разведение 11 hard / 18 soft — в README (§ «Hook taxonomy»).

### 8.2. Подробно по хукам

| Хук | Событие | Контур | Природа | Энфорсмент |
|---|---|---|:---:|---|
| `check-tool-skill.sh` | PreToolUse | feedforward | computational | **blocking** — `deny` после 3 пропусков скилл-решения подряд |
| `check-commit-completeness.sh` | PreToolUse | feedforward | computational | **blocking** — `deny` commit'а без сопутствующих артефактов |
| `check-review-before-commit.sh` | PreToolUse | feedforward | computational | **blocking** — `deny` commit'а без пройденного review |
| `check-dod-before-commit.sh` | PreToolUse | feedforward | computational | **blocking** — `deny` commit'а с риск-сигналом (миграция/деньги/новый код без теста) без нужного скилла |
| `check-skill-completeness.sh` | PreToolUse | feedforward | computational | **blocking** — `deny` записи SKILL.md без artefacts (был PostToolUse-баг в v1.5.0 → исправлен в v1.5.1) |
| `freeze.sh` | PreToolUse | feedforward | computational | soft (opt-in) — предупреждает о правках замороженных файлов; `exit 0, allow` — не блокирует |
| `careful.sh` | PreToolUse | feedforward | computational | soft (v1.37.0 always-on) — предупреждает о деструктивных командах (`rm -rf`, `DROP TABLE`, `git push --force`); `exit 0, allow` — не блокирует |
| `pii-egress-guard.sh` | PreToolUse (`*`) | feedforward | computational | **blocking** — approvable external write возвращает native `ask` с exact preview/hash, и host связывает подтверждение с одним pending invocation без локального approval-ledger; missing provenance/targets или live secret дают `deny`/exit 2; read-only остаётся неблокирующим |
| `model-policy.sh` | PreToolUse (Task\|Agent) | feedforward | computational | weaker-model override даёт advisory; явный `effort=low` вне bounded low/medium mechanical `working_deadline` требует native ASK. Protected review/security/root-cause/architecture floors и evidence contours не понижаются незаметно; hard deny не добавляется |
| `check-skills.sh` | UserPromptSubmit | feedforward | inferential | soft — инжектит skill-hint; маршрут выбирает модель |
| `context-aware.sh` | UserPromptSubmit | feedforward | inferential | soft — инжектит проектный контекст |
| `pre-flight-check.sh` | UserPromptSubmit | feedforward | inferential | soft — git-статус + `MEMORY.md` в контекст для resume |
| `session-open-diagnostic.sh` | UserPromptSubmit | feedforward | inferential | soft — диагностика состояния на старте сессии |
| `context-budget.sh` | PreToolUse | feedforward | inferential | soft — мягко рекомендует ограничить unbounded-вывод |
| `cost-tracker.sh` | PreToolUse + PostToolUse | feedforward + feedback | computational | **blocking** — PreToolUse `deny` только следующей дорогой попытки у estimate ceiling; PostToolUse observed/estimated usage ledger остаётся soft |
| `execution-trace.sh` | PreToolUse | feedback | computational | soft — observability: JSONL-трейс tool-call'ов, zero-context |
| `stuck-detection.sh` | PostToolUse | feedback | inferential | soft — детект застревания → напоминание сменить подход |
| `crash-recovery.sh` | PostToolUse | feedback | inferential | soft — recovery-контекст после краша для возобновления |
| `state-guard.sh` | PreToolUse + PostToolUse (Write/Edit, Bash) | guardrail + feedback | computational | **blocking** — deny записи леджера при чужом свежем локе (single-writer, ≤2 deny; v1.76.0 Write/Edit, v1.78.0 + Bash-цель записи); soft-ноги — валидация после записи/Bash-мутации + heartbeat лока (v1.75.0) |
| `record-agent-skill.sh` | PostToolUse (Task\|Agent) | feedback | computational | soft — пишет skill-sentinel, когда review/test/security делегированы субагенту (чтобы commit-гейты это засчитали) |
| `risk-score.sh` | PostToolUse | feedback | computational | soft — оценка риск-сигнала действия (не блокирует) |
| `cross-review-precommit.sh` | PreToolUse (Bash) | feedback | computational | soft (**fail-open**) — диспетчеризует независимый cross-vendor review диффа перед commit; аддитивно к `/review`, не гейт |
| `handoff-readiness.sh` | Stop | feedback | computational | soft — systemMessage-hint «сделай `/session-save`/`/handoff`» когда ход закончился с dirty tree и без свежего `session_*.md`; rate-limited, никогда не блокирует (ось I §4.4) |
| `wip-gate.sh` | PreToolUse (Write\|Edit\|MultiEdit) | feedforward | computational | soft — hint «WIP=1: доведи верификацию текущего unit'а или переклассифицируй» при правке вне `SCOPE_LOCK.Allowed`, когда `currentUnit.status` ∈ verifying/recovery_required; молчит без `.itd-memory/` (v1.41.0, §4.4) |
| `narration-final.sh` | SubagentStop | feedback | computational | **blocking** — `block` (≤2 пинга), если субагент завершается нарративом вместо результата/вердикта (v1.49.0) |
| `verdict-contract.sh` | SubagentStop | feedback | computational | **blocking** — `block` (≤2 пинга), если review-субагент даёт прозаический вердикт без валидного JSON-блока (v1.51.0) |
| `completion-signals.sh` | PostToolUse (Bash) | feedback | computational | soft — собирает runtime-сигнал (static/test_run/app_start/side_effect/cleanup) в леджер `.claude/completion/`, возвращает красную пометку WHY+FIX при провале (v1.51.0) |
| `completion-gate.sh` | PreToolUse (Bash/PowerShell) | feedforward | computational | **blocking** — `deny` commit'а с исходным кодом при непройденном/недоказанном слое завершения; распознаёт абсолютный путь к git и global options (`-C`, `--git-dir`); деградирует в advisory только для калиброванного low/medium risk |
| `completion-stop.sh` | Stop | feedback | computational | soft — напоминание «завершение не доказано», когда ход закончился с грязным по коду деревом и не-зелёным вердиктом; rate-limited, не блокирует (v1.51.0) |

### 8.3. Что показывает линза

- **Все 11 блокирующих хуков — computational.** Девять PreToolUse-гейтов дают deterministic `deny`, два SubagentStop-гейта — deterministic `block`; inferential-суждение не является hard boundary.
- **18 soft-хуков** формируют контекст, наблюдают outcome/cost/state и дают advisory feedback. Их классификация и README-список выводятся из source и проверяются `verify_gate_taxonomy.py`.
- **Правило дизайна для будущих хуков (следствие):** новый хук, который должен *блокировать*, обязан быть computational; если проверка по сути требует семантического суждения — она должна быть мягким hint'ом (как `check-skills` или `context-budget`), а не `deny`. Inferential-блок = недетерминированный гейт, что противоречит H1/H3.

### 8.4. Наследование хуков в `context: fork` (эмпирически, v1.59.0 / G-005)

Ранее был недоказанный caveat: наследует ли форкнутый контекст (субагент через Agent/Task, `context: fork`-скилл) хуки родительской сессии. **Проверено прямым зондом:** субагент, запущенный в форкнутом контексте, сделал два Bash-вызова — и оба `PreToolUse:Bash`-хука родительской `settings.json` СРАБОТАЛИ (`careful.sh` на деструктивной команде, `check-tool-skill.sh` на мутации), доставленные как `PreToolUse:Bash hook additional context`. Вывод: **механические гейты применяются и к tool-call'ам внутри форка** — enforcement не «проваливается» на границе субагента. Отдельный (не путать) факт: форк НЕ наследует `SKILL.md` родителя (видит только `.md` бэкенд-агента) — это про наследование инструкций, а не срабатывание хуков. Оговорка для честности: это наблюдение в текущем рантайме (Claude Code, ~/.claude-хуки); контракт остаётся вендоронейтральным — если будущий рантайм перестанет прокидывать хуки в форк, деградация идёт к soft-режиму, а не к ложному «all-green» (см. `CLAUDE.md` § harness best-effort).

---

**Обновление документа.** При изменении числа скиллов/хуков, закрытии gap'а или изменении принципов курса — обновлять §4, §6 и §8 (классификацию). Если gap закрывается — статус → ✅ с пометкой о версии-релизе.

> **v1.40.0.** Добавлена ось **I** (§4.4) по первоисточнику Anthropic: init-фаза `/kickstart` Phase 3.7–3.8 и `/adopt` Step 3.5 теперь реально скаффолдят `.itd/` + `.itd-memory/STATE.json` (закрыт разрыв «шаблоны без создателя»), стартеры несут обязательный `commands.bootstrap`, добавлен Stop-хук `handoff-readiness.sh` (21-й). Счётчики §3/§8 обновлены (20 → 21 хук).

> **v1.37.0.** Устранён разрыв «декларация ↔ реальность»: хуки наблюдаемости и само-коррекции (`execution-trace`, `stuck-detection`, `crash-recovery`, `context-aware`) и guardrail `careful` физически лежали в `~/.claude/hooks/`, но **не были в наборе регистрации** `scripts/sync-to-active.sh` → де-факто молчали, хотя §8.1 числил их активными. Теперь они в каноническом наборе (always-on), а sync **мержит** ITD-события, сохраняя чужие (напр. SessionStart другого плагина). H5-наблюдаемость и Agentic-само-коррекция стали фактически, а не на бумаге. `freeze` остаётся opt-in по дизайну.
