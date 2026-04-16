# ROADMAP v1.19 — Methodology Gaps Discovered in Real-World Session 2026-04-15/16

> Создан 2026-04-16 на основе 10+ часовой сессии мультипроектной работы
> (миграция 3 проектов Beget→Hostland + стратегический пересмотр NeuroExpert).
>
> **Цель v1.19:** закрыть 7 методологических дыр, обнаруженных когда Claude
> фактически обошёл методологию на реальной задаче.

---

## Контекст

Сессия 2026-04-15/16 включала:

1. **Миграция инфраструктуры** 3 проектов с Beget VDS (2×) на Hostland VDS (185.221.213.104) — hardening, Docker, Coolify, SSL, DNS, патчинг Telegram-ботов под прокси, восстановление БД/Minio/uploads.
2. **Стратегический пересмотр NeuroExpert** через призму модели Medvi — анализ 5 потоков выручки, выбор фокуса, составление LAUNCH_PLAN.md под цель 2M ₽/мес к декабрю.

Claude использовал `/session-save` один раз (для миграции). **Все остальные задачи выполнялись через raw Bash/Edit/Write** — несмотря на триггеры hook каждую минуту.

---

## 7 обнаруженных дыр

### 🕳️ Gap #1 — Нет скилла под «миграцию работающих prod-сервисов»

**Что было:** перенос 3 проектов с одного VDS на другой с патчингом ботов, DNS, SSL, override compose, восстановлением данных.

**Проверка по 20 скиллам v1.18.1:**
- `/migrate` — только про DB migrations (Alembic, Supabase)
- `/infra` — только Terraform/k8s/Helm/IaC (новая инфра)
- `/harden` — production-readiness для нового сервиса, не перенос
- `/project`, `/kickstart`, `/blueprint` — для новых проектов
- `/bugfix` — не подходит, это не баг
- `/refactor` — не рефакторинг кода

**Вывод:** **нет скилла для оперативной миграции работающих сервисов** между хостами.

**Предложение v1.19:**
Новый скилл **`/migrate-prod`** или переименование `/migrate` → `/migrate-db`, а `/migrate-prod` — расширенный.

Содержание `/migrate-prod`:
- Inventory source server (что работает, какие volumes/data/secrets)
- Setup target server (hardening, Docker, Coolify/Traefik/Nginx)
- DNS staging strategy (не переключать до готовности)
- Data migration (DB dumps, volumes, uploads, object storage)
- Secret rotation checklist
- Dual-run period (старый и новый работают параллельно 24-48ч)
- Cut-over DNS
- Rollback plan
- Decommission source after 7 days

### 🕳️ Gap #2 — Нет скилла под «стратегический пересмотр существующего проекта»

**Что было:** Medvi-анализ, оценка 5 потоков выручки NeuroExpert, создание LAUNCH_PLAN.md с acceptance criteria на 6 блоков работы.

**Проверка:**
- `/blueprint` — для **нового** проекта (создаёт ARCHITECTURE.md, PRD.md)
- `/project` — роутер к /kickstart/blueprint/guide для **нового**
- `/discover` — product discovery только для **нового**
- `/review` — код-ревью, не стратегия
- `/explain` — объяснение кода

**Вывод:** нет скилла для **стратегического replanning существующего проекта**.

**Предложение v1.19:**
Новый скилл **`/strategy`** или **`/replan`**.

Содержание:
- Input: существующий LAUNCH_PLAN.md (или создать от нуля) + текущие метрики + новый контекст
- Анализ: что изменилось, что выучили, KPI-gap
- Генерация: обновлённый LAUNCH_PLAN.md с новыми блоками/целями
- ADR для значимых разворотов (pivot decisions)
- BACKLOG.md обновление
- Отметка даты пересмотра для трекинга

### 🕳️ Gap #3 — Нет скилла под «советник/консалтинг-режим»

**Что было:** пользователь задавал стратегические вопросы — «где такие ниши как Medvi», «чем отличается наш рынок от GLP-1», «какой добавочный проект выбрать». Ответы — анализ без кода-выхода.

**Проверка:** ни один из 20 скиллов v1.18.1 не про advisory/стратегическое мышление без code output.

**Предложение v1.19:**
Новый скилл **`/advisor`** или **`/consult`**.

Содержание:
- Режим «только анализ и советы, не трогать код»
- Запрет на Write/Edit в рамках скилла (только Read)
- Обязательное использование Agent subagents (business-analyst, devils-advocate) для разносторонней оценки
- Output: ADVICE.md или в чат — аналитика, сравнение, рекомендации с pros/cons
- Обязательное требование: **user confirms before any implementation follows**

### 🕳️ Gap #4 — Hook advisory, а не enforcement

**Текущий `check-skills.sh`:**
- Срабатывает каждую минуту на Bash/Edit/Write
- **Просто напоминает**, не блокирует
- Claude может игнорировать и работать дальше

**В реальной сессии 2026-04-15/16** — Claude проигнорировал hook **десятки раз**, работая raw tools.

**Предложение v1.19:**
Добавить **эскалацию после N игнорирований**:
- Трекать state в `.claude/.skills-ignored-count` (per-session)
- После 3+ игнорирований подряд — hook возвращает **non-zero exit code**, блокирующий следующий Bash/Edit/Write
- Claude вынужден либо запустить скилл, либо явно обосновать обход в `SKILL_BYPASS_LOG.md`
- После обоснования счётчик обнуляется

### 🕳️ Gap #5 — Мульти-проектные сессии ломают task-level assessment

**В сессии 2026-04-15/16** работа переходила между:
- `/home/hihol/projects/neuroexpert`
- `/home/hihol/projects/skutr-docs`
- `/home/hihol/projects/jogai`
- Обратно в `/home/hihol/projects/neuroexpert`

`pre-flight-check.sh` читал контекст **текущего cwd** (последнего репо), терял общую картину. Claude каждый раз «забывал» что задача — инфраструктурная миграция, и думал что он в разных задачах.

**Предложение v1.19:**
**Context-switch detector** в `pre-flight-check.sh`:
- Детектить смену cwd между вызовами
- При смене — выводить в чат explicit warning: «🔄 Context switch: от `neuroexpert` → `skutr-docs`. Сессия мульти-проектная. Задача task-level: **миграция инфры**? Или начинаем новую задачу?»
- Вести `.claude/session-cwd-history` (last 10 switches)
- Если switches >5 за 30 мин — предлагать `/session-save` чтобы не потерять контекст

### 🕳️ Gap #6 — Session-open не имеет обязательной диагностики

**В сессии 2026-04-15/16** я начал работу без:
- Чтения предыдущих `session_*.md`
- Проверки `LAUNCH_PLAN.md` существующих проектов
- Определения «какой next actionable шаг из плана»

Просто реагировал на первое сообщение пользователя.

**Предложение v1.19:**
Новый хук **`hooks/session-open-diagnostic.sh`**:
- Срабатывает при старте сессии (UserPromptSubmit первый в session)
- Читает: `MEMORY.md`, последний `session_*.md`, `LAUNCH_PLAN.md`, `BACKLOG.md` (если есть)
- Формирует в контекст: «Прошлая сессия закончилась на X. LAUNCH_PLAN.md следующий шаг: Y. BACKLOG топ-3: Z. Какой скилл запускаешь?»
- **Блокирует первый Bash/Edit** пока не будет явного выбора скилла или обоснования raw-режима

### 🕳️ Gap #7 — Memory staleness не детектируется

**В сессии 2026-04-15/16** Claude использовал версию idea-to-deploy «v1.13.1» из `session_2026-04-11_2.md`, **не сверяясь** с актуальным `.claude-plugin/plugin.json` (v1.18.1). Разница в 5 версий за 5 дней!

**Предложение v1.19:**
**Auto-verify fact claims** в `pre-flight-check.sh`:
- При упоминании версий/файлов/путей в memory — проверять существование
- Если memory говорит «файл X:ABC», а на самом деле `git log | grep X:ABC` пусто → mark memory stale
- Warning в контекст: «⚠️ Memory упоминает v1.13.1, но CHANGELOG.md показывает v1.18.1 — используй актуальную»

---

## Приоритет реализации v1.19

| Gap | Приоритет | Effort | Impact |
|---|---|---|---|
| #4 Hook enforcement | 🔴 P0 | 1 день | Высокий — останавливает обход методологии |
| #6 Session-open diagnostic | 🔴 P0 | 1 день | Высокий — правильное начало сессии |
| #2 `/strategy` скилл | 🟡 P1 | 2 дня | Средний — закрывает большой gap |
| #5 Context-switch detector | 🟡 P1 | 0.5 дня | Средний — мульти-проектные сессии частые |
| #1 `/migrate-prod` скилл | 🟢 P2 | 2 дня | Средний — частота раз в квартал |
| #3 `/advisor` скилл | 🟢 P2 | 1 день | Низкий — можно обойтись без скилла |
| #7 Memory stale detection | 🟢 P2 | 1 день | Низкий — редкий случай |

**Общий effort v1.19:** ~8-9 дней работы.

---

## Предлагаемая последовательность реализации

### Фаза 1: Enforcement foundation (2-3 дня)
1. Gap #4 (Hook enforcement) — останавливает дальнейший обход
2. Gap #6 (Session-open diagnostic) — гарантирует правильный старт

### Фаза 2: Новые скиллы (5 дней)
3. Gap #2 (`/strategy`) — через `/blueprint` самоприменение
4. Gap #1 (`/migrate-prod`) — через `/blueprint` самоприменение
5. Gap #3 (`/advisor`) — через `/blueprint` самоприменение

### Фаза 3: Quality-of-life (1-2 дня)
6. Gap #5 (Context-switch detector)
7. Gap #7 (Memory staleness)

Каждый скилл создавать через `/blueprint` (dog-fooding) + `/review` + `/test` + `/session-save`.

---

## Критерии приёмки v1.19

- [x] Hook enforcement блокирует tool calls после 3 игнорирований — тестировано на dry-run (v1.19.0, 2026-04-16)
- [x] Session-open diagnostic срабатывает на первом UserPromptSubmit (v1.19.0, 2026-04-16)
- [x] `/strategy` создан с triggers + fixture (v1.19.0 Phase 2, 2026-04-16)
- [x] `/migrate-prod` создан с triggers + fixture (v1.19.0 Phase 2, 2026-04-16)
- [x] `/advisor` создан с triggers + fixture (v1.19.0 Phase 2, 2026-04-16)
- [x] Context-switch detector интегрирован в pre-flight (v1.19.0 Phase 3, 2026-04-16)
- [x] Memory staleness warning работает (v1.19.0 Phase 3, 2026-04-16)
- [x] README.md + README.ru.md + CHANGELOG.md обновлены (v1.19.0 Phase 1, 2026-04-16)
- [x] Marketplace.json обновлён (skill count 20 → 23) (v1.19.0, 2026-04-16)
- [ ] PR merged, sync-to-active прогнат, v1.19 задеплоена

---

## Следующая сессия в этом репо (idea-to-deploy) должна начать с

**Чтения этого файла (`ROADMAP_v1.19.md`)** и ответа на вопрос:
- Какую фазу стартуем первой?
- Используем ли dog-fooding (применяем `/blueprint` для создания каждого нового скилла)?

**Ориентир команд:**
```
cd ~/projects/idea-to-deploy
git checkout -b feat/v1.19-session-gaps
# /blueprint для первого скилла
# /review после реализации
# /test на dry-run примерах
# PR когда все gaps закрыты
```

**Контекст доступен в:**
- `~/.claude/projects/-home-hihol-projects/memory/session_2026-04-15_2.md` — основная миграция
- `~/.claude/projects/-home-hihol-projects/memory/feedback_methodology_gaps.md` — (будет создан вместе с этим ROADMAP'ом)
- `~/projects/neuroexpert/LAUNCH_PLAN.md` — пример LAUNCH_PLAN, который `/strategy` должен уметь генерировать
