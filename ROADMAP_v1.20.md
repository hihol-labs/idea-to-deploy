# ROADMAP v1.20 — Legacy Project Adoption Gap

> **Status:** ✅ **CLOSED** — shipped in v1.20.0 on 2026-04-17.
>
> Создан 2026-04-16 после merge PR #42 (`/deploy` + `check-review-before-commit.sh`).
> Обнаружен в обсуждении: методология применяется неравномерно на проектах,
> которые изначально не создавались через `/kickstart` или `/blueprint`.
>
> **Цель v1.20:** закрыть Gap #8 — дать способ «адоптировать» любой
> существующий legacy-проект в методологию одной командой.
>
> **Результат v1.20.0:** скилл `/adopt` реализован со strict-minimal scope
> (CLAUDE.md append-with-marker, `.claude/settings.json` merge, memory dir
> bootstrap, voice-chain в `/strategy` или `/blueprint`). Без reverse-engineering
> plan-документов — план генерируется отдельным скиллом с user input.

---

## Контекст

После v1.19.0 методология покрывает полный lifecycle для проектов, **созданных
с нуля** через `/kickstart`/`/blueprint` — скаффолд кладёт `CLAUDE.md`,
memory dir, plan-документы, hooks активны, роутинг работает.

Но реальная практика: большая часть работы — это **существующий код**, который
был написан до появления методологии (или без неё). Когда пользователь
скачивает `idea-to-deploy` и открывает такой legacy-проект в Claude Code —
методология применяется только частично:

1. **Скиллы из плагина доступны**, но без `CLAUDE.md` в корне проекта Claude не
   знает правила жёсткого роутинга («Шаг 1 — выбор скилла task-level»,
   «коммитить >2 файлов без `/review` запрещено»).
2. **Hooks** (`check-skills.sh`, `check-tool-skill.sh`, `check-review-before-commit.sh`)
   не зарегистрированы в `~/.claude/settings.json` у нового пользователя после
   `/plugin install` — это сознательный дизайн Anthropic (README.md:337),
   но для legacy-проекта означает «soft reminders не приходят».
3. **Memory dir** (`~/.claude/projects/<hash>/`) пуст — нет `MEMORY.md`,
   нет session_*.md; Claude стартует «без памяти», не видит прошлых решений.
4. **Plan-документы** (`STRATEGIC_PLAN.md`, `LAUNCH_PLAN.md`,
   `IMPLEMENTATION_PLAN.md`) отсутствуют — скиллы типа `/review` и `/task`
   теряют половину контекста, на который они рассчитаны.

Результат: пользователь видит методологию как **«набор скиллов»**, а не как
**«методологию, которая ведёт его за руку»**. Это снижает ценностное
предложение и тормозит community adoption — первое впечатление от инструмента
на существующем проекте слабее, чем на новом.

---

## ✅ Gap #8 — [CLOSED v1.20.0] Способ адоптировать методологию в legacy-проект

**Что происходит сейчас:** чтобы включить методологию в существующем проекте,
пользователю нужно **вручную**:
- написать `CLAUDE.md` в корне с правилами роутинга (копипаста из чужого проекта)
- создать `.claude/settings.json` и зарегистрировать хуки
- создать memory dir через первый ручной `/session-save`
- опционально запустить `/strategy` или `/blueprint` для retrofit-плана

Каждый из этих шагов требует знания того, что он вообще нужен — новый
пользователь не знает. Барьер высокий, путь неочевидный.

**Проверка по существующим скиллам v1.19.0:**
- `/project` — роутер для **новых** проектов (A/B/C)
- `/kickstart` — пишет scaffold **с нуля**, перезапишет существующий код
- `/blueprint` — генерирует plan-документы **с нуля** (для нового проекта)
- `/guide` — ожидает уже готовые plan-документы на входе
- `/strategy` — предполагает что `LAUNCH_PLAN.md` уже есть
- `/task` — роутер daily-work, но **не умеет бутстрапить** методологию

**Вывод:** **нет скилла, который за один вызов включает методологию в любом
legacy-проекте** без перезаписи существующего кода.

---

## Предложение v1.20: скилл `/adopt` — минимальная адоптация

### Scope (strict minimum — никакого reverse-engineering)

`/adopt` делает **только three things**, ни больше, ни меньше:

1. **Пишет `CLAUDE.md` в корень проекта** (или merge-добавляет блок, если
   файл уже существует и не упоминает idea-to-deploy).
   Содержимое — шаблонные правила роутинга на скиллы + обязательность
   `/review` перед коммитом + обязательность `/session-save` в конце работы.
   **Не генерирует** домен-специфичный контент (стек, архитектуру, KPI) —
   это ответственность `/strategy`/`/blueprint`, запускается отдельно.

2. **Создаёт `./.claude/settings.json`** (или merge-добавляет в существующий)
   с регистрацией hooks из плагина: `check-skills.sh`, `check-tool-skill.sh`,
   `check-review-before-commit.sh`, `pre-flight-check.sh`,
   `session-open-diagnostic.sh`. Project-level settings означает, что хуки
   активны **только в этом проекте** — не требует изменения `~/.claude/`.

3. **Бутстрапит memory dir** — вызывает `/session-save` с reverse-engineered
   «нулевым» контекстом (текущая ветка, `git log -5`, список файлов в корне,
   detected stack из манифестов), чтобы `MEMORY.md` появился и
   `pre-flight-check.sh` имел что грузить в следующей сессии.

После всех трёх шагов `/adopt` **голосом** спрашивает пользователя:

> «Хочешь сгенерировать plan-документы для этого проекта? (да / нет)»

- **«да»** + есть код + есть даже минимальный `README.md` → chain в `/strategy`
  (генерирует `LAUNCH_PLAN.md` на основе текущего состояния).
- **«да»** + проекта фактически нет (пустой репо, нет `README.md`) → chain
  в `/blueprint` (генерирует plan с нуля, ретроспективно).
- **«нет»** → готово, `/adopt` завершается.

Пользователь **не печатает команды вручную** — слышит вопрос, отвечает
словами, Claude делает следующий вызов сам. Это стандартный паттерн
роутинга, как в `/project` → `/kickstart`/`/blueprint`/`/guide`.

### Что `/adopt` НЕ делает (явный non-scope)

- **Не** reverse-engineer'ит `STRATEGIC_PLAN.md`/`PROJECT_ARCHITECTURE.md`
  из кода — это рискованно (галлюцинации), это задача `/strategy`.
- **Не** перезаписывает существующий `CLAUDE.md`, если он уже содержит
  idea-to-deploy-блок — только дописывает недостающее.
- **Не** трогает `~/.claude/settings.json` (user-level) — работает только
  project-level, чтобы не влиять на другие проекты пользователя.
- **Не** меняет код проекта — никаких edits в `src/`, никаких import'ов,
  никаких новых зависимостей.

### Триггер-фразы

- адоптируй, подключи методологию, подключи idea-to-deploy
- включи методологию, примени методологию, bootstrap methodology
- onboard this project, adopt methodology, enable methodology
- добавь CLAUDE.md, добавь хуки, настрой этот проект под методологию
- этот проект без методологии, подключи к idea-to-deploy

---

## Приоритет реализации v1.20

| Gap | Приоритет | Effort | Impact |
|---|---|---|---|
| #8 `/adopt` скилл (минимальный) | 🔴 P0 | 1-2 дня | **Очень высокий** — разблокирует адопшен на legacy-проектах, снижает friction нового пользователя |

**Общий effort v1.20:** ~1-2 дня работы.

---

## Предлагаемая последовательность реализации

### Фаза 1: Скилл `/adopt` (1-2 дня)

1. Написать `skills/adopt/SKILL.md` (dog-fooding через `/blueprint` или вручную).
2. Создать `skills/adopt/references/` с шаблонами:
   - `claude-md-template.md` — canonical CLAUDE.md для проекта, адоптированного в методологию
   - `project-settings-template.json` — `.claude/settings.json` с registrations хуков
3. Добавить триггер в `hooks/check-skills.sh` для фраз выше.
4. Создать `tests/fixtures/fixture-17-adopt/expected-snapshot.json` с required_files:
   `CLAUDE.md`, `.claude/settings.json`, `MEMORY.md` (в memory dir).
5. Обновить counts (24 → 25 skills) в README{.,ru.}md + `plugin.json` + `marketplace.json` + docs/promotion/*.
6. Обновить `/task` router чтобы на обнаружении legacy-признаков (нет CLAUDE.md + нет LAUNCH_PLAN.md) предлагать `/adopt` первым.
7. `/review` + PR + sync-to-active + merge.

---

## Критерии приёмки v1.20

- [ ] `/adopt` создан с `SKILL.md`, `references/`, trigger в `check-skills.sh`, fixture-17-adopt
- [ ] Минимальный `/adopt` (без reverse-engineering) — пишет только `CLAUDE.md` + `.claude/settings.json` + bootstraps memory dir
- [ ] В конце `/adopt` голосом спрашивает про plan-документы и **автоматически** (без ручного ввода команд) chain'ит в `/strategy` или `/blueprint` по голосовому ответу
- [ ] `/adopt` не перезаписывает существующий `CLAUDE.md` с idea-to-deploy-блоком (идемпотентен)
- [ ] `/adopt` не трогает `~/.claude/settings.json` (только project-level)
- [ ] Meta-review PASSED (включая M-C12 skill count 24→25, M-C16 category subtotals, M-I2 2 examples для `/adopt`)
- [ ] README{.,ru.}md описывает `/adopt` в секции Entry Points или Workflow
- [ ] В `/task` router добавлен branch: если legacy-признаки — предложить `/adopt` до routing в daily-work
- [ ] sync-to-active прогнат, v1.20 задеплоена

---

## Следующая сессия в этом репо должна начать с

**Чтения этого файла (`ROADMAP_v1.20.md`)** и запуска `/blueprint` для `/adopt`
(dog-fooding — используем методологию, чтобы спроектировать новый скилл).

**Ориентир команд:**

```
cd ~/projects/idea-to-deploy
git checkout -b feat/adopt-skill
# /blueprint для /adopt — получаем PROJECT_ARCHITECTURE.md для скилла
# написание skills/adopt/SKILL.md + references/ + trigger + fixture
# /review
# PR → CI → merge
# sync-to-active.sh
```

**Контекст доступен в:**
- `ROADMAP_v1.19.md` — предыдущие 7 gap'ов и паттерн реализации
- `skills/strategy/SKILL.md` — как spawn'ить скилл, который работает с
  существующим проектом (pattern для `/adopt` → `/strategy` chain)
- `skills/session-save/SKILL.md` — как bootstrap'ить memory dir
- Обсуждение дизайна `/adopt` — в чате сессии 2026-04-16 (после merge PR #42)
