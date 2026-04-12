# Конкурентный анализ: idea-to-deploy vs рынок Claude Code плагинов

> Дата: 2026-04-12
> Версия idea-to-deploy: v1.16.3
> Цель: понять позиционирование, найти gaps для усиления, определить стратегию дистанцирования

---

## 1. Конкуренты

| Проект | GitHub | Stars | Лицензия | Фокус |
|---|---|---|---|---|
| **gstack** (Garry Tan / YC) | [garrytan/gstack](https://github.com/garrytan/gstack) | ~70K | MIT | Виртуальная команда: CEO, Designer, Eng Manager, QA |
| **BMAD Method** | [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) | ~44K | MIT | Agile AI framework с BA/PM discovery |
| **claude-code-skills** (levnikolaevich) | [levnikolaevich/claude-code-skills](https://github.com/levnikolaevich/claude-code-skills) | 379 | MIT | 7 плагинов, 136 скиллов, Agile pipeline |
| **AI-DLC** (TheBushidoCollective) | [TheBushidoCollective/ai-dlc](https://github.com/TheBushidoCollective/ai-dlc) | 0 | - | 13 ролей-"шляп", DAG execution, quality gates |
| **Claude Buddy** (rsts-dev) | rsts-dev/claude-buddy (404, closed?) | 11 | MIT | 7-step TDD lifecycle (Foundation→Docs) |

---

## 2. Сводная матрица возможностей

| Возможность | **idea-to-deploy** | **gstack** | **BMAD** | **claude-code-skills** | **AI-DLC** | **Claude Buddy** |
|---|---|---|---|---|---|---|
| **Скиллов** | 18 | ~30 | 15 | **136** | 13 ролей | 7 |
| **Субагентов** | 5 | - | 9 | - | 13 "шляп" | 12 персон |
| **Project scaffolding** | /kickstart, /blueprint | - | /product-brief | project-bootstrap | Plan Together | /buddy:foundation |
| **Daily work router** | **/task** | - | - | - | - | - |
| **Code review** | /review + **meta-review** | /review + auto-fix | - | audit suite | Reviewer hat | - |
| **Security audit** | /security-audit | /cso (OWASP+STRIDE) | - | security auditor | Red/Blue Team | - |
| **Deps audit (CVE/licenses)** | **/deps-audit** | - | - | - | - | - |
| **DB migrations** | **/migrate** | - | - | - | - | - |
| **Infra-as-code** | **/infra** (TF/Helm/K8s) | - | - | - | - | - |
| **Production hardening** | **/harden** | - | - | - | - | - |
| **Session persistence** | /session-save + lockfile | /learn | YAML status | - | Bolt recovery | - |
| **Self-review (meta)** | **23 gates, 3-tier** | - | - | - | quality-gate.sh | - |
| **Browser automation** | - | **Chromium stealth** | - | - | - | - |
| **Parallel sessions** | lockfile warning | **Conductor (10-15)** | "Party Mode" | - | Agent Teams | - |
| **Product discovery** | - | /office-hours | **BA + PM agents** | - | Plan Together | /buddy:spec |
| **Design/UX pipeline** | - | **/design-html/shotgun/review** | UX Designer | - | Designer hat | - |
| **Safety guardrails** | hooks (soft+hard) | **/careful, /freeze, /guard** | - | - | backpressure gates | - |
| **MCP серверы** | - | - | - | **3 MCP** | - | - |
| **Приоритизация фич** | - | - | **MoSCoW** | - | - | - |

---

## 3. Уникальные преимущества idea-to-deploy

Эти возможности **не реализованы ни у одного из 5 конкурентов**:

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

### 4.1. Product discovery (CRITICAL gap)
**Кто лучше:** BMAD (BA + PM агенты, MoSCoW, 4 фазы discovery)

Наш /blueprint начинает с "у пользователя уже есть идея". Нет фазы market analysis, competitive research, user persona definition, feature prioritization.

**Рекомендация:** Новый скилл `/discover` или расширение Phase 0 в /blueprint:
- Market analysis (TAM/SAM/SOM)
- Competitor scanning
- User personas
- Feature prioritization (MoSCoW → RICE)
- Value proposition canvas

### 4.2. Design/UX pipeline (MEDIUM gap)
**Кто лучше:** gstack (полный pipeline: consultation → shotgun → HTML → review)

У нас нет ничего для дизайна. /kickstart генерирует код, но не wireframes и не design tokens.

**Рекомендация:** Новый скилл `/design` или интеграция с Canva MCP (уже доступен в toolset).

### 4.3. Browser automation (LOW gap)
**Кто лучше:** gstack (Chromium stealth, cookie import, parallel tabs)

Не критично для нашего позиционирования "от идеи до деплоя" — browser automation это QA-инструмент.

### 4.4. Safety guardrails (MEDIUM gap)
**Кто лучше:** gstack (/careful, /freeze, /guard — предупреждение перед деструктивными командами)

У нас есть hard-blocking hooks, но нет явного "freeze" режима для ограничения scope.

**Рекомендация:** 2 новых хука: `/careful` (warn before rm -rf, DROP, force-push) и `/freeze` (restrict edits to one directory).

### 4.5. Параллельные сессии (LOW gap)
**Кто лучше:** gstack (Conductor — 10-15 реальных спринтов)

У нас lockfile + warning. Достаточно для solo-developer, но не для team.

---

## 5. Что можно адаптировать

| Приоритет | Идея | Источник | Что добавляет | Усилие |
|---|---|---|---|---|
| **HIGH** | Product discovery фаза (BA-агент + приоритизация) | BMAD | Закрывает самый слабый этап конвейера | 1 новый скилл + 1 субагент |
| **HIGH** | MoSCoW/RICE приоритизация в /blueprint | BMAD | Структурированный output требований | Расширение существующего скилла |
| **MED** | Safety guardrails (/careful, /freeze) | gstack | Защита от деструктивных ошибок | 2 новых хука |
| **MED** | Helper pattern (общий helpers.md) | BMAD | Экономия 70-85% токенов на references | Рефактор references/ |
| **MED** | Расширенные аудиты (dead code, observability) | claude-code-skills | Глубже /security-audit | Расширение скилла |
| **LOW** | Red/Blue Team для security | AI-DLC | Adversarial testing | Расширение /security-audit |
| **LOW** | Design tokens / wireframes | gstack | UX в pipeline | 1 новый скилл |

---

## 6. Стратегия дистанцирования (positioning)

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
- **Messaging:** "136 скиллов без роутера = cognitive overload. 19 скиллов с /task = правильный скилл за 10 секунд"

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

### РЕАЛИЗОВАНО в v1.17.0–v1.17.2 (2026-04-12)

Все 6 пунктов из конкурентного анализа реализованы в одном цикле:

| # | Что | Источник | PR | Статус |
|---|---|---|---|---|
| 1 | `/discover` скилл + BA-субагент | BMAD | #25 | ✅ Done |
| 2 | MoSCoW/RICE в /blueprint Step 1.5 | BMAD | #25 | ✅ Done |
| 3 | Safety guardrails (careful + freeze) | gstack | #25, #26 | ✅ Done (автоматические) |
| 4 | Shared helpers pattern | BMAD | #25 | ✅ Done |
| 5 | Extended security audits (dead code, observability, concurrency) | claude-code-skills | #25 | ✅ Done |
| 6 | Red/Blue Team mode (--redblue) | AI-DLC | #25 | ✅ Done |
| 7 | ## Rules во всех 19 скиллах | Anthropic compliance | #27 | ✅ Done |

### Оставшиеся future consideration

- **Design/UX pipeline** — Canva MCP integration для wireframes и design tokens. Не критично для core methodology.
- **Parallel sessions enhancement** — gstack Conductor (10-15 спринтов). Наш lockfile warning достаточен для solo-developer, но не для team.
