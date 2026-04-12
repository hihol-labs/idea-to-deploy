# Конкурентный анализ: idea-to-deploy vs рынок Claude Code плагинов

> Дата: 2026-04-12 (обновлено: GSD добавлен как 6-й конкурент)
> Версия idea-to-deploy: v1.17.2
> Цель: понять позиционирование, найти gaps для усиления, определить стратегию дистанцирования

---

## 1. Конкуренты

| Проект | GitHub | Stars | Лицензия | Фокус |
|---|---|---|---|---|
| **gstack** (Garry Tan / YC) | [garrytan/gstack](https://github.com/garrytan/gstack) | ~70K | MIT | Виртуальная команда: CEO, Designer, Eng Manager, QA |
| **BMAD Method** | [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) | ~44K | MIT | Agile AI framework с BA/PM discovery |
| **claude-code-skills** (levnikolaevich) | [levnikolaevich/claude-code-skills](https://github.com/levnikolaevich/claude-code-skills) | 379 | MIT | 7 плагинов, 136 скиллов, Agile pipeline |
| **AI-DLC** (TheBushidoCollective) | [TheBushidoCollective/ai-dlc](https://github.com/TheBushidoCollective/ai-dlc) | 0 | - | 13 ролей-"шляп", DAG execution, quality gates |
| **GSD** (glittercowboy / TACHES) | [gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done) + [gsd-2](https://github.com/gsd-build/gsd-2) | **51K** (v1) + 5.5K (v2) | MIT | Spec-driven dev, anti-methodology: discuss→research→plan→execute→verify |
| **Claude Buddy** (rsts-dev) | rsts-dev/claude-buddy (404, closed?) | 11 | MIT | 7-step TDD lifecycle (Foundation→Docs) |

---

## 2. Сводная матрица возможностей

| Возможность | **idea-to-deploy** | **GSD** | **gstack** | **BMAD** | **claude-code-skills** | **AI-DLC** | **Claude Buddy** |
|---|---|---|---|---|---|---|---|
| **Скиллов** | **20** | 7 команд | ~30 | 15 | **136** | 13 ролей | 7 |
| **Субагентов** | 7 | 5 (researcher, planner, plan-checker, executor, verifier) | - | 9 | - | 13 "шляп" | 12 персон |
| **Project scaffolding** | /kickstart, /blueprint | /gsd-new-project | - | /product-brief | project-bootstrap | Plan Together | /buddy:foundation |
| **Daily work router** | **/task** | /gsd-next (auto-detect) | - | - | - | - | - |
| **Code review** | /review + **meta-review** | /gsd-verify-work | /review + auto-fix | - | audit suite | Reviewer hat | - |
| **Security audit** | /security-audit + Red/Blue | - | /cso (OWASP+STRIDE) | - | security auditor | Red/Blue Team | - |
| **Deps audit (CVE/licenses)** | **/deps-audit** | - | - | - | - | - | - |
| **DB migrations** | **/migrate** | - | - | - | - | - | - |
| **Infra-as-code** | **/infra** (TF/Helm/K8s) | - | - | - | - | - | - |
| **Production hardening** | **/harden** | - | - | - | - | - | - |
| **Session persistence** | /session-save + lockfile | **SQLite state machine + crash recovery** | /learn | YAML status | - | Bolt recovery | - |
| **Self-review (meta)** | **23 gates, 3-tier** | quality gates (4 типа) | - | - | - | quality-gate.sh | - |
| **Context management** | - | **свежий контекст на задачу, tiered injection (-65% токенов)** | - | - | - | - | - |
| **Cost/token tracking** | - | **per-unit ledger, budget ceiling, dynamic model routing** | - | - | - | - | - |
| **Crash recovery** | lockfile warning | **PID liveness, forensics synthesis, exponential backoff** | - | - | - | Bolt recovery | - |
| **Autonomous mode** | - | **/gsd auto (state machine до milestone)** | - | - | - | - | - |
| **Stuck detection** | - | **sliding-window диагностика зацикливания** | - | - | - | - | - |
| **Git isolation** | ветка на фичу (ручная) | **worktree per milestone, squash merge** | - | - | - | - | - |
| **Multi-runtime** | Claude Code only | **14 рантаймов** (Claude, Gemini, Copilot, Cursor...) | Claude Code | Claude Code | Claude Code | Claude Code | Claude Code |
| **Headless/CI mode** | POC (`claude -p`) | **`gsd headless` + `gsd headless query`** | - | - | - | - | - |
| **Browser automation** | - | - | **Chromium stealth** | - | - | - | - |
| **Parallel sessions** | lockfile warning | - | **Conductor (10-15)** | "Party Mode" | - | Agent Teams | - |
| **Product discovery** | **/discover** (TAM/SAM/SOM, RICE) | - | /office-hours | **BA + PM agents** | - | Plan Together | /buddy:spec |
| **Design/UX pipeline** | - | - | **/design-html/shotgun/review** | UX Designer | - | Designer hat | - |
| **Safety guardrails** | hooks (careful + freeze) | - | /careful, /freeze, /guard | - | - | backpressure gates | - |
| **MCP серверы** | - | MCP credential collection | - | - | **3 MCP** | - | - |
| **Приоритизация фич** | **/discover** (MoSCoW + RICE) | - | - | **MoSCoW** | - | - | - |

---

## 3. Уникальные преимущества idea-to-deploy

Эти возможности **не реализованы ни у одного из 6 конкурентов**:

### 3.1. Self-improving methodology
- `meta_review.py` — 23 автоматизированных проверки (14 Critical + 9 Important)
- CI gate на каждый PR в main — drift невозможен
- 4 итерации self-improvement loop в v1.13.2→v1.16.3: каждый найденный drift порождал новый gate

### 3.2. Three-tier behavioural testing
1. **Structural** — meta_review.py, 23 checks, $0 cost
2. **Snapshot** — verify_snapshot.py, deterministic schema validation
3. **Behavioural** — run-fixture-headless.sh, `claude -p` end-to-end, 3 fixtures

### 3.3. Operations stack (/deps-audit + /migrate + /infra + /harden)
Полный production lifecycle. Ни один конкурент не покрывает все 4 аспекта: аудит зависимостей, безопасные миграции, infrastructure-as-code, production hardening.

### 3.4. Daily work router /task
Единый entry point → автороутинг на 12 типов задач. У конкурентов пользователь сам выбирает из десятков/сотен скиллов.

---

## 4. Слабые места idea-to-deploy (gaps vs конкуренты)

### 4.1. Product discovery — ~~CRITICAL gap~~ ✅ ЗАКРЫТ (v1.17.0)
**Было:** BMAD лучше (BA + PM агенты, MoSCoW, 4 фазы discovery)
**Решение:** `/discover` скилл + BA-субагент + MoSCoW/RICE в /blueprint

### 4.2. Context management (CRITICAL gap — NEW)
**Кто лучше:** GSD (свежий контекст на каждую единицу работы, tiered prompt injection с -65% токенов)

У нас нет управления контекстным окном. Длинные сессии деградируют — context rot. GSD решает это spawn'ом свежих подагентов с чистым 200K-окном и pre-loaded dispatch prompt.

**Рекомендация:** Адаптировать context-aware подход:
- Tiered prompt injection (минимальный контекст для задачи)
- Рекомендация fresh context при длинных сессиях
- Dispatch prompt pattern для субагентов

### 4.3. Cost/token tracking (HIGH gap — NEW)
**Кто лучше:** GSD v2 (per-unit ledger, budget ceiling, dynamic model routing по сложности)

У нас нет отслеживания расходов. Пользователь не знает сколько стоит каждая задача.

**Рекомендация:** Hook для трекинга токенов/стоимости по задачам, бюджетный потолок.

### 4.4. Crash recovery (HIGH gap — NEW)
**Кто лучше:** GSD v2 (lock-файлы, PID liveness detection, forensics synthesis из tool calls, exponential backoff)

У нас только `.active-session.lock` + warning. При crash теряется весь контекст.

**Рекомендация:** Расширить /session-save для auto-save при crash detection. Forensics synthesis из git log + tool call history.

### 4.5. Autonomous mode (HIGH gap — NEW)
**Кто лучше:** GSD v2 (`/gsd auto` — state machine работает до завершения milestone без вмешательства)

У нас нет auto mode. Каждое действие требует ручного вызова скилла.

**Рекомендация:** Auto-pipeline: /discover → /blueprint → /kickstart → /review → /test как одна команда.

### 4.6. Design/UX pipeline (MEDIUM gap)
**Кто лучше:** gstack (полный pipeline: consultation → shotgun → HTML → review)

У нас нет ничего для дизайна. /kickstart генерирует код, но не wireframes и не design tokens.

**Рекомендация:** Новый скилл `/design` или интеграция с Canva MCP (уже доступен в toolset).

### 4.7. Stuck detection (MEDIUM gap — NEW)
**Кто лучше:** GSD v2 (sliding-window диагностика зацикленных агентов)

У нас нет детекции зацикливания. Агент может бесконечно повторять одни и те же действия, сжигая токены.

**Рекомендация:** Hook для детекции повторяющихся паттернов в tool calls.

### 4.8. Git worktree isolation (MEDIUM gap — NEW)
**Кто лучше:** GSD v2 (worktree per milestone, sequential slice commits, squash merge в main)

У нас ручное создание веток. GSD автоматизирует git isolation.

**Рекомендация:** Auto-worktree в /kickstart и /task для изоляции работы.

### 4.9. Headless/CI mode (MEDIUM gap — NEW)
**Кто лучше:** GSD v2 (`gsd headless [cmd]` + `gsd headless query` для JSON-снапшота)

У нас POC с `claude -p`, но не продакшен-ready CI интеграция.

**Рекомендация:** Расширить headless fixtures до полноценного CI pipeline.

### 4.10. Safety guardrails — ~~MEDIUM gap~~ ✅ ЗАКРЫТ (v1.17.0–v1.17.1)
**Было:** gstack лучше (/careful, /freeze, /guard)
**Решение:** careful (always-on) + freeze (auto-scoped) hooks

### 4.11. Browser automation (LOW gap)
**Кто лучше:** gstack (Chromium stealth, cookie import, parallel tabs)

Не критично для нашего позиционирования "от идеи до деплоя" — browser automation это QA-инструмент.

### 4.12. Параллельные сессии (LOW gap)
**Кто лучше:** gstack (Conductor — 10-15 реальных спринтов)

У нас lockfile + warning. Достаточно для solo-developer, но не для team.

### 4.13. Multi-runtime support (LOW gap — NEW)
**Кто лучше:** GSD v1 (14 рантаймов: Claude, Gemini, Copilot, Cursor, Windsurf и др.)

Мы работаем только в Claude Code. Расширение на другие IDE — потенциал роста аудитории, но не приоритет.

---

## 5. Что можно адаптировать

### Волна 1 — реализовано в v1.17.0–v1.17.2

| # | Идея | Источник | Статус |
|---|---|---|---|
| 1 | Product discovery (/discover + BA-агент) | BMAD | ✅ Done |
| 2 | MoSCoW/RICE в /blueprint | BMAD | ✅ Done |
| 3 | Safety guardrails (careful + freeze) | gstack | ✅ Done |
| 4 | Shared helpers pattern | BMAD | ✅ Done |
| 5 | Extended security audits | claude-code-skills | ✅ Done |
| 6 | Red/Blue Team (--redblue) | AI-DLC | ✅ Done |

### Волна 2 — адаптации из GSD (v1.18.0)

| # | Приоритет | Идея | Источник | Что добавляет | Усилие |
|---|---|---|---|---|---|
| 7 | **CRITICAL** | Context-aware sessions (tiered prompt injection, fresh context рекомендация) | GSD | Борьба с context rot, экономия токенов | Новый хук + рефактор dispatch |
| 8 | **HIGH** | Cost/token tracking (ledger по задачам, budget ceiling) | GSD v2 | Прозрачность расходов, бюджетный контроль | Новый хук + файл-трекер |
| 9 | **HIGH** | Crash recovery (auto-save, forensics synthesis) | GSD v2 | Устойчивость к сбоям, восстановление контекста | Расширение /session-save |
| 10 | **HIGH** | Auto-pipeline (/discover → /blueprint → /kickstart → /review → /test) | GSD auto | Hands-free execution для полного цикла | Новый скилл /autopilot |
| 11 | **MED** | Stuck detection (sliding-window диагностика зацикливания) | GSD v2 | Предотвращение сжигания токенов | Новый хук |
| 12 | **MED** | Git worktree isolation (auto-worktree per milestone) | GSD v2 | Чистый main, лёгкий rollback | Расширение /kickstart и /task |
| 13 | **MED** | Headless CI pipeline (расширение fixtures до production CI) | GSD v2 | Полноценная CI интеграция | Расширение tests/ |

### Future consideration

| Приоритет | Идея | Источник |
|---|---|---|
| **LOW** | Design/UX pipeline (Canva MCP) | gstack |
| **LOW** | Multi-runtime support (14 IDE) | GSD v1 |
| **LOW** | Parallel sessions enhancement (Conductor) | gstack |

---

## 6. Стратегия дистанцирования (positioning)

### vs GSD (51K stars, spec-driven execution engine)
- **GSD** = "execution engine с context management" (решает одну проблему гениально — context rot)
- **idea-to-deploy** = "full lifecycle methodology" (от идеи до production с self-validation)
- **Наше преимущество:** полный pipeline (discovery → blueprint → code → ops → deploy), operations stack, self-improving gates, product discovery
- **Их преимущество:** context management, crash recovery, cost tracking, autonomous mode, 14 рантаймов, 51K stars
- **Ключевой инсайт:** GSD и idea-to-deploy **комплементарны**, не взаимозаменяемы. GSD = КАК выполнять эффективно, idea-to-deploy = ЧТО делать от идеи до продакшена
- **Messaging:** "GSD: spec → code. idea-to-deploy: idea → production. GSD — двигатель. idea-to-deploy — весь автомобиль"

### vs gstack (70K stars, celebrity-driven)
- **gstack** = "виртуальная команда разработки" (ролевой подход)
- **idea-to-deploy** = "полный production pipeline с self-validation"
- **Наше преимущество:** operations stack (migrate/harden/infra), self-improving gates, behavioural testing
- **Их преимущество:** дизайн, browser automation, имя Garry Tan
- **Messaging:** "gstack даёт вам команду. idea-to-deploy даёт вам процесс, который проверяет сам себя"

### vs BMAD (44K stars, agile framework)
- **BMAD** = "agile planning framework" (сильный discovery, слабый execution)
- **idea-to-deploy** = "execution + ops" (migrate, harden, infra — того, что у BMAD нет)
- **Наше преимущество:** весь post-planning lifecycle, self-validation
- **Их преимущество:** product discovery, BA/PM агенты, MoSCoW
- **Messaging:** "BMAD планирует. idea-to-deploy планирует И деплоит"

### vs claude-code-skills (379 stars, 136 скиллов)
- **claude-code-skills** = "модульный супермаркет скиллов" (quantity)
- **idea-to-deploy** = "curated pipeline с роутером и self-validation" (quality)
- **Наше преимущество:** /task router, meta-review, coherent methodology
- **Их преимущество:** масштаб (136 скиллов), 3 MCP сервера, multi-model review
- **Messaging:** "136 скиллов без роутера = cognitive overload. 20 скиллов с /task = правильный скилл за 10 секунд"

### vs AI-DLC (0 stars, academic)
- **AI-DLC** = "теоретически правильный DAG pipeline" (overengineered)
- **idea-to-deploy** = "battle-tested methodology" (23 gates, 10/10 on 3 tiers, 24 PRs merged)
- **Наше преимущество:** production-proven, community adoption, marketplace-ready
- **Их преимущество:** DAG модель, Red/Blue Team
- **Messaging:** "13 ролей для одного бага — перебор. /bugfix решает за 1 вызов"

### vs Claude Buddy (11 stars, TDD)
- Не конкурент по масштабу. Закрытый исходный код. 4 домена (React/JHipster/MuleSoft/generic).
- Интересная идея TDD-first pipeline, но слишком узкий scope.

---

## 7. Roadmap — что реализовано и что осталось

### Волна 1: РЕАЛИЗОВАНО в v1.17.0–v1.17.2 (2026-04-12)

Адаптации из BMAD, gstack, claude-code-skills, AI-DLC:

| # | Что | Источник | PR | Статус |
|---|---|---|---|---|
| 1 | `/discover` скилл + BA-субагент | BMAD | #25 | ✅ Done |
| 2 | MoSCoW/RICE в /blueprint Step 1.5 | BMAD | #25 | ✅ Done |
| 3 | Safety guardrails (careful + freeze) | gstack | #25, #26 | ✅ Done (автоматические) |
| 4 | Shared helpers pattern | BMAD | #25 | ✅ Done |
| 5 | Extended security audits (dead code, observability, concurrency) | claude-code-skills | #25 | ✅ Done |
| 6 | Red/Blue Team mode (--redblue) | AI-DLC | #25 | ✅ Done |
| 7 | ## Rules во всех 19 скиллах | Anthropic compliance | #27 | ✅ Done |

### Волна 2: PLANNED — адаптации из GSD (v1.18.0)

| # | Что | Источник | Приоритет | Статус |
|---|---|---|---|---|
| 8 | Context-aware sessions (tiered injection, fresh context) | GSD | CRITICAL | 🔲 Planned |
| 9 | Cost/token tracking (ledger + budget ceiling) | GSD v2 | HIGH | 🔲 Planned |
| 10 | Crash recovery (auto-save + forensics) | GSD v2 | HIGH | 🔲 Planned |
| 11 | Auto-pipeline (/autopilot: discover→deploy) | GSD auto | HIGH | 🔲 Planned |
| 12 | Stuck detection (sliding-window) | GSD v2 | MEDIUM | 🔲 Planned |
| 13 | Git worktree isolation (auto per milestone) | GSD v2 | MEDIUM | 🔲 Planned |
| 14 | Headless CI pipeline (production-ready) | GSD v2 | MEDIUM | 🔲 Planned |

### Future consideration

- **Design/UX pipeline** — Canva MCP integration для wireframes и design tokens. Не критично для core methodology.
- **Multi-runtime support** — GSD поддерживает 14 рантаймов. Потенциал для расширения аудитории.
- **Parallel sessions enhancement** — gstack Conductor (10-15 спринтов). Наш lockfile warning достаточен для solo-developer, но не для team.
