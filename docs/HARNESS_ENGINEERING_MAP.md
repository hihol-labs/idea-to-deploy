# Harness Engineering Map: idea-to-deploy ↔ Харнес-инженерия

> Дата: 2026-06-22
> Версия idea-to-deploy: **v1.21.0** (`main` = `1e95ddb`)
> Источник: [Harness Engineering (walkinglabs)](https://walkinglabs.github.io/learn-harness-engineering/ru/)
> Цель: проверить, в полной ли мере методология отражает философию, 5 принципов и инструменты харнес-инженерии; артикулировать gap'ы; зафиксировать осознанные out-of-scope решения.

---

## 1. Что это за документ

Учебник [«Харнес-инженерия»](https://walkinglabs.github.io/learn-harness-engineering/ru/) формализует дисциплину проектирования надёжных систем управления AI-агентами. Его центральный тезис: **задача не в том, чтобы сделать модель умнее, а в том, чтобы построить замкнутую «рабочую систему» (harness) с явными правилами и границами.** Курс выделяет 5 ключевых принципов и библиотеку готовых шаблонов (`AGENTS.md`, `feature_list.json`).

`idea-to-deploy` — это методология (harness) поверх Claude Code. Документ применяет ту же дисциплину честного маппинга, что и [`DESIGN_SPACE.md`](DESIGN_SPACE.md) (карта против «Dive into Claude Code»), и отвечает на три вопроса:

1. **Что из 5 принципов покрыто** (✅).
2. **Где покрытие частичное** и чего не хватает (◐).
3. **Что осознанно оставлено out-of-scope** и почему.

Документ намеренно честный: каждый gap помечен явно. Код-кандидаты **не реализуются вне signal-gated процесса** — см. §6 и [`ROADMAP_v1.21.md`](../ROADMAP_v1.21.md).

> **Важно про версию.** Эта карта составлена по **v1.21.0**, где PFO-порт добавил слой контрактов `.itd/` и набор fail-closed гейтов. Это заметно повысило покрытие по сравнению с тем, что было до v1.21.0 (особенно по принципам H2, H3 и шаблону `feature_list.json`).

## 2. Источник

- **Учебник:** [walkinglabs.github.io/learn-harness-engineering/ru](https://walkinglabs.github.io/learn-harness-engineering/ru/) — 12 лекций (от режимов отказа агентов к практическим решениям), практические проекты, библиотека шаблонов.
- Принципы ниже пронумерованы `H1–H5`, шаблоны — `T1–T2`. Нумерация внутренняя.

Документ-сестра: [`DESIGN_SPACE.md`](DESIGN_SPACE.md) (16 принципов «Dive into Claude Code»). Рамки пересекаются; ссылки на `K…` указывают на строки той карты. NB: §4 (K4) в DESIGN_SPACE датирован v1.20.3 и **предшествует** хуку `context-budget.sh` (v1.21.0) — здесь оценка по бюджету контекста актуальнее.

## 3. Методология маппинга

Статусы: ✅ **покрыто** (явная реализация с контрактом) · ◐ **частично** (gap артикулирован в §5) · ❌ **gap** (не реализовано и не замещено).

Проверка — чтением `main` (`1e95ddb`, v1.21.0): **33 skills, 10 subagents, 15 hooks, 2 Quality Gates**, слой контрактов `.itd/` (`docs/templates/itd/`), session-memory, 3 уровня качества (structural / snapshot / behavioural), бинарные rubric'и `/review` · `/security-audit` · `/deps-audit`.

## 4. Таблица соответствия

### 4.1. Философия (мета-уровень)

| Тезис курса | Статус | Воплощение |
|---|:---:|---|
| **«Harness важнее, чем умная модель»** — замкнутая система с явными правилами и границами | ✅ | **Дословно центральный тезис методологии**: 33 skills + 10 agents + 15 hooks + 2 Quality Gates + слой контрактов `.itd/` поверх Claude Code. Codegen — следствие harness'а (ср. `K11`) |

### 4.2. 5 ключевых принципов

| # | Принцип курса | Статус | Реализация в idea-to-deploy (v1.21.0) | Gap / комментарий |
|---|---|:---:|---|---|
| **H1** | **Ограничение поведения** — явные правила и границы | ✅ | Per-skill `allowed-tools`; `disable-model-invocation: true` на `/deploy` · `/migrate` · `/migrate-prod` · `/github-workflow` · `/tool-sync`; deny-first + явный user-confirm на деструктивных операциях; read-only скиллы (`/advisor`, `/security-audit`, `/deps-audit`, `/explain`, `/discover`, `/grill-me`, `/market-scan`, `/mcp-docs`); opt-in `careful.sh` / `freeze.sh`; `check-tool-skill.sh`. **+ v1.21.0 `.itd/`:** `PERMISSION_MATRIX.json/.md`, `FORBIDDEN_CHANGES.md`, `SCOPE_LOCK.md`, `TOOL_CAPABILITY_REGISTRY.json`, `EXECUTION_POLICY.json` — границы стали машиночитаемыми | Минор: нет *graduated trust* (= `K1` ◐), но как «явные правила и границы» — покрыто полностью |
| **H2** | **Сохранение контекста** — между сессиями длинных задач | ✅ | `/session-save` → `session_*.md` + `MEMORY.md`; статус-таблица `CLAUDE.md` для resume; автосохранение на вехах; `pre-flight-check.sh` (git + `MEMORY.md` в контекст); `session-open-diagnostic.sh`; `crash-recovery.sh`. **+ v1.21.0:** `context-budget.sh` (PreToolUse — мягко тормозит unbounded-дампы в контекст) + `UNIT_CONTEXT_MANIFEST.json` (свежий ограниченный per-node контекст) | Принцип «между сессиями» — полностью. Смежный `K4` (бюджетирование *внутри* сессии) теперь **частично закрыт** `context-budget.sh` (мягкое напоминание, не жёсткая budget-модель) — улучшение vs DESIGN_SPACE §5.2 |
| **H3** | **Предотвращение преждевременного завершения** — защита от ложного успеха | ✅ | **Сильнейшая ось.** 2 Quality Gate; бинарные rubric'и `BLOCKED/PASSED`; стоп после **3 ошибок подряд**; `check-commit-completeness.sh` + `check-review-before-commit.sh` (hard-block); `stuck-detection.sh`. **+ v1.21.0 fail-closed гейты:** `ACCEPTANCE_CONTRACT.json` («done = traceable proof-checklist, не ощущение агента»; статусы `pending/passed/failed/recovery_required`); `VERIFICATION_CONTRACT.json` (`failClosed`, `RECOVERY_REQUIRED` вместо «passed» при un-run/ambiguous); **двухстадийный `/review`** (Stage A spec-compliance — «красивый код, решающий не ту задачу» → `BLOCKED`); fail-closed `/test` (passed только при реально полученном evidence); `ROOT_CAUSE.md`-гейт в `/bugfix`; `BRANCH_FINISH.md` | — |
| **H4** | **Верификация через тестирование** — сквозные проверки и саморефлексия | ✅ | `/test` после каждого шага; **3 уровня качества** методологии (structural / snapshot / behavioural); `tests/fixtures/` (25 фикстур) + `run-fixtures.sh`; `meta-review.yml` в CI; `/review` · `/security-audit` · `/deps-audit`; `/harden` (k6 load-tests); `/browser-check` (Playwright runtime). **+ v1.21.0:** TDD evidence-гейт (red→green) в `/test`; fail-closed верификация | — |
| **H5** | **Наблюдаемость** — отладка и мониторинг во время выполнения | ✅ | **Post-hoc:** `cost-tracker.sh` (per-session usage), `/session-save` (summary), `session-open-diagnostic.sh`, `ITD_REPORT.md`, session-memory. **+ Live (v1.21.x): `execution-trace.sh`** — PreToolUse-хук пишет по строке JSON (`{ts, tool, target}`) на каждый tool-call в `.claude/traces/session-{id}.jsonl` | **Закрыто (= `K15`).** Live execution trace «скилл X прочитал Y, сделал tool-call Z» теперь есть: zero-context (ничего не инжектит), opt-in (как `cost-tracker.sh`), `.claude/` в `.gitignore`, fail-safe |

### 4.3. Библиотека шаблонов

| # | Шаблон курса | Статус | Аналог в idea-to-deploy (v1.21.0) | Комментарий |
|---|---|:---:|---|---|
| **T1** | **`AGENTS.md`** — операционный манифест/память агента | ✅ | `CLAUDE.md` (нативный эквивалент) + `agents/*.md` (10 субагентов) + **слой `.itd/`** как машиночитаемый операционный манифест: `PROJECT_CONTRACT.md`, `EXECUTION_POLICY.json`, `PERMISSION_MATRIX.md`, `DATA_POLICY.md`, `FALLBACK_POLICY.md` | Расхождение только по имени: `CLAUDE.md` — корректный идиом Claude Code. Минор-кандидат: `AGENTS.md`-алиас для кросс-тул-портируемости |
| **T2** | **`feature_list.json`** — машиночитаемый реестр «сделано/протестировано» против преждевременного завершения | ✅ | **`ACCEPTANCE_CONTRACT.json`** (v1.21.0): машиночитаемый proof-checklist критериев приёмки, выведенный из запроса пользователя, со схемой (`id/criterion/source/evidence/verificationCommand/status`) и `doneRule` **fail-closed** + **`VERIFICATION_CONTRACT.json`** (исполняемые команды верификации, `failClosed`) | **Намерение курса реализовано и усилено** (fail-closed). Отличие по форме: это per-unit контракт приёмки от запроса, а не персистентный мульти-фичный ledger проекта. Для большинства задач функционально эквивалентно (и строже). Кандидат-улучшение: персистентный проектный `feature_list.json` поверх per-unit контрактов |

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
- **Персистентный `feature_list.json`** (T2): проектный реестр фич поверх per-unit `ACCEPTANCE_CONTRACT`, чтобы `/deploy` мог программно проверить «все P0 имеют passing-тест». 3–5 дней.

## 6. Сводка

| Уровень | ✅ Покрыто | ◐ Частично | ❌ Gap |
|---|---|---|---|
| **Философия** | «harness важнее модели» | — | — |
| **5 принципов** | H1, H2, H3, H4, **H5** | — | — |
| **2 шаблона** | T1, **T2** (через `.itd/`) | — | — |

**Итог:** философия харнес-инженерии воплощена **в полной мере** — `idea-to-deploy` является образцовым примером самой дисциплины. На **v1.21.x**: **все 5 принципов** покрыты полностью (H1–H5; наблюдаемость закрыта live-трейсингом `execution-trace.sh`). Оба шаблона курса покрыты: `AGENTS.md` → `CLAUDE.md` + `.itd/`-манифест; `feature_list.json` → `ACCEPTANCE_CONTRACT.json` + `VERIFICATION_CONTRACT.json` (fail-closed, строже оригинала).

**Содержательных остатков по принципам и шаблонам нет.** Остаются лишь минорные косметические кандидаты (см. §5.4: `AGENTS.md`-алиас для кросс-тул-портируемости; персистентный мульти-фичный `feature_list.json` поверх per-unit `ACCEPTANCE_CONTRACT`) — это улучшения формы, а не пробелы принципов. Карта остаётся сигнал-триггер-картой на случай изменений курса или методологии.

## 7. Следствия для ROADMAP

Документ **не меняет** решения [ROADMAP v1.21 DEFERRED](../ROADMAP_v1.21.md). Его роль:

1. **Честная позиция** для аудитории, говорящей на языке харнес-инженерии.
2. **Закрытие H5 (v1.21.x) — по явному запросу мейнтейнера**, что удовлетворяет signal-критерий ROADMAP (activated user с конкретным запросом), а не velocity ради velocity. Реализовано минимальным opt-in хуком (`execution-trace.sh`) без раздувания surface — не cargo-cult.
3. **Оставшиеся кандидаты — только косметические** (форма, не принципы), по-прежнему signal-gated:

| Кандидат | Тип | Effort | Триггер |
|---|---|:---:|---|
| Персистентный `feature_list.json` | T2 (форма) | 3–5d | Нужен программный gate «все P0 фичи протестированы» перед `/deploy` |
| `AGENTS.md`-алиас в генераторах | T1 (портируемость) | <1d | Запрос на кросс-тул-портируемость |

Ни один не активируется без external signal (критерии — `ROADMAP_v1.21.md §"When to revisit v1.21"`).

---

**Обновление документа.** При изменении числа скиллов/хуков, закрытии gap'а или изменении принципов курса — обновлять §4 и §6. Если gap закрывается — статус → ✅ с пометкой о версии-релизе.
