# Design Space Map: idea-to-deploy ↔ Dive into Claude Code

> Дата: 2026-04-21
> Версия idea-to-deploy: v1.20.3
> Источник: arxiv 2604.14228 + [VILA-Lab/Dive-into-Claude-Code](https://github.com/VILA-Lab/Dive-into-Claude-Code)
> Цель: проверить покрытие 16 архитектурных принципов Claude Code, артикулировать gap'ы, зафиксировать осознанные out-of-scope решения

---

## 1. Что это за документ

В апреле 2026 года Liu, Zhao, Shang, Shen опубликовали разбор архитектуры Claude Code: статья **«Dive into Claude Code: The Design Space of Today's and Future AI Agent Systems»** (arxiv 2604.14228) плюс репозиторий-компаньон [VILA-Lab/Dive-into-Claude-Code](https://github.com/VILA-Lab/Dive-into-Claude-Code). Авторы формализовали 13 design principles, набор anti-patterns и оси design-space (autonomy, tool integration, memory, safety, execution).

`idea-to-deploy` — это методология (harness) поверх Claude Code, и разумно сверить её решения с принципами, которые авторы выделили в самой платформе. Документ отвечает на три вопроса:

1. **Что из 16 принципов покрыто** в нашей методологии (✅).
2. **Где покрытие частичное** и чего не хватает (◐).
3. **Что осознанно оставлено out-of-scope** и почему (❌ или N/A).

Документ намеренно честный: каждый gap помечен явно, без маркетингового выравнивания. Часть gap'ов — кандидаты в будущий v1.21-scope (см. §6).

## 2. Источники

- **arxiv paper:** [`2604.14228`](https://arxiv.org/pdf/2604.14228) — Liu et al., «Dive into Claude Code», апрель 2026.
- **Репозиторий-компаньон:** [`VILA-Lab/Dive-into-Claude-Code`](https://github.com/VILA-Lab/Dive-into-Claude-Code) — расширенный разбор: 13 design principles, anti-patterns, 4 CVE-класса в pre-trust window, graduated compaction, subagent cost-model, hook/skill/plugin/MCP extensibility ladder.

Принципы в таблице ниже пронумерованы `K1–K16` — это наша внутренняя номерация для удобства ссылок, не из paper.

## 3. Методология маппинга

Для каждого принципа мы выставили один из четырёх статусов:

- ✅ **Покрыто** — в методологии есть явная реализация с документированным контрактом.
- ◐ **Частично** — покрыта часть случаев; остаётся gap, который артикулирован в §4.
- ❌ **Gap** — принцип не реализован и не замещён альтернативой. Кандидат в будущий scope.
- N/A — принцип не применим к methodology-layer (относится к платформе ниже нас).

Проверка делалась чтением актуальной структуры репозитория на `main` (коммит `df2c25e`, v1.20.3): 25 skills, 7 subagents, 13 hooks, 2 quality gates, session-memory, 3 quality tiers (structural / snapshot / behavioural).

## 4. Таблица соответствия (K1–K16)

| # | Принцип | Источник | Статус | Реализация в idea-to-deploy | Gap / комментарий |
|---|---|---|:---:|---|---|
| **K1** | Graduated trust spectrum | 13 principles | ◐ | `careful.sh`, `freeze.sh` (opt-in per session); explicit confirmation на `/deploy`, `/migrate-prod` | Нет progressive-trust модели, которая бы «раскрывалась» по мере работы с проектом (7 permission modes из Claude Code) |
| **K2** | Deny-first with human escalation | 13 principles | ✅ | `disable-model-invocation: true` на destructive skills (v1.20.1); `/deploy` и `/migrate-prod` требуют явного user confirmation | — |
| **K3** | Defense in depth + shared-failure audit | 13 principles + Anti-patterns | ✅ | 13 хуков + 2 Quality Gates + `/review` + `/security-audit` + `check-commit-completeness.sh`. CI layer (GitHub Actions) как 4-й defense tier. | Отдельный shared-failure аудит между хуками ранее не проводился — планируется в fixture-11..17 (см. ROADMAP §D tech-debt) |
| **K4** | Context-as-scarce-resource / graduated compaction | 13 principles | ❌ | Полагаемся на встроенный 5-слойный compaction Claude Code. `context-aware.sh` бросает рекомендацию `/session-save` после 40 prompts, но не управляет бюджетом. | Gap: нет явной context-budget модели на уровне методологии. Рассматривается как кандидат в v1.21 при появлении user pain signal. |
| **K5** | Append-only durable state | 13 principles | ◐ | `session_YYYY-MM-DD.md` — append-only per session. `scripts/sync-to-active.sh` делает backup rotation. | `CLAUDE.md` и `MEMORY.md` редактируются деструктивно (in-place). Read-time chain patching из paper не реализован. |
| **K6** | Reversibility-weighted risk assessment | 13 principles | ✅ | `/migrate`, `/migrate-prod`, `/deploy` требуют confirm. Read-only скиллы (`/explain`, `/advisor`, `/discover`, `/security-audit`, `/deps-audit`) проходят без friction. Контракты скиллов документируют idempotency (✅/⚠️). | — |
| **K7** | Values over rules | 13 principles | ◐ | Бинарные rubrics (`/review`, `/security-audit`, `/deps-audit`), hard-block hooks, meta-review 23 checks. | Подход сознательно rule-based — это даёт детерминизм для solo-maintainer. «Values»-подход (контекстное суждение + минимальные guardrails) не артикулирован явно; добавление потребует пересмотра философии методологии, не одного скилла. |
| **K8** | Graduated extensibility cost | Hooks/Skills/Plugins/MCP | ✅ | Используются все четыре уровня: 13 хуков (0-context reminders), 25 skills (triggered contracts), плагин-обёртка (plugin.json), субагенты для fork-isolated работы. | — |
| **K9** | Subagent summary-only returns | Anti-patterns | ✅ | 7 субагентов (architect, code-reviewer, test-generator, perf-analyzer, doc-writer, business-analyst, devils-advocate) возвращают отчёты, не raw logs. Context rot от fork'ов контролируется. | — |
| **K10** | File-based memory > vector DB | Anti-patterns | ✅ | `MEMORY.md` pointer-index + `session_*.md` + per-topic memory files. LLM читает заголовки файлов, без embeddings. | — |
| **K11** | Minimal scaffolding, maximal harness | 6 decisions | ✅ | Центральный тезис всей методологии: harness (25 skills + 7 agents + 13 hooks + 2 gates) важнее codegen'а. | — |
| **K12** | Pre-trust execution window — осознанный trade-off | Anti-patterns / 4 CVEs | ◐ | Три UserPromptSubmit хука (`pre-flight-check.sh`, `session-open-diagnostic.sh`, `context-aware.sh`) выполняются до любого trust-диалога. **Audit 2026-04-21:** все три read-only relative to project (только `git log/status`, чтение `MEMORY.md`/session/plan), запись только в `/tmp/claude-*-{session_id}.*`, без network calls, без destructive ops, таймаут 2с на git. | Отличие от CVE-класса из paper: наши хуки — user-opt-in (пользователь явно устанавливает плагин), не auto-loaded MCP. Это структурно снижает risk vs paper-described auto-MCP attack. Осознанный trade-off, не gap в strict смысле. |
| **K13** | Single execution engine | Anti-patterns | N/A | Методология — single plugin с единой surface (Claude Code API). Принцип относится к платформе ниже нас. | — |
| **K14** | Graduated autonomy levels | arxiv | ◐ | `/autopilot` (high autonomy) + обычный interactive flow (human-in-the-loop). После 3 подряд ошибок `/kickstart` останавливается и спрашивает человека. | Нет промежуточных уровней и нет явного autonomy-selector'а на входе. `/task` / `/project` роутеры не спрашивают autonomy mode — только task type. Gap не приоритетный: для реального UX улучшения нужен multi-user signal. |
| **K15** | Execution transparency / tracing | arxiv | ◐ | `/session-save` фиксирует post-hoc summary; `cost-tracker.sh` (v1.18.0) пишет per-session usage; session-memory хранит historical view. | Нет live execution trace — «какой скилл прочитал какой файл, какие tool calls сделал». Полезно для retro-анализа, но требует отдельного hook-pipeline'а. Кандидат в v1.21. |
| **K16** | On-disk checkpoints | Архитектура | ❌ | Rollback опирается на `git` (коммиты + ветки). Гитхаб-level checkpoint'ы работают для текстовых файлов. | Для non-git state (docker containers, database state, deployed services) checkpoint'ов нет. `/migrate` делает backup → /tmp; `/deploy` не делает pre-deploy snapshot. Кандидат в v1.21 для `/harden` расширения. |

## 5. Детальный разбор gap'ов

### 5.1. K1 — Graduated trust (◐)

**Paper говорит:** доверие эволюционирует во времени, а не назначается раз. 7 permission modes из Claude Code (plan → default → acceptEdits → auto → dontAsk → bypassPermissions) — это спектр.

**У нас:** `careful.sh` и `freeze.sh` — бинарные guard'ы, включаются пользователем раз и держатся до отмены. Destructive skills используют `disable-model-invocation: true` (v1.20.1) — это фиксированный deny, не graduated trust.

**Почему не критично:** методология поверх Claude Code, то есть 7 permission modes уже доступны через нижний layer. Дублирование на уровне методологии дало бы conflicting UX. Gap осмысленный, не urgent.

### 5.2. K4 — Context budgeting (❌)

**Paper говорит:** context — дефицитный ресурс, требующий 5-слойной graduated compaction (Budget Reduction → Snip → Microcompact → Context Collapse → Auto-Compact) *перед каждым* model call.

**У нас:** `context-aware.sh` (v1.18.0) считает prompts и на 40-м бросает рекомендацию `/session-save`. Это одна грубая точка, а не slope. Долгие `/kickstart` или `/autopilot` сессии могут упереться в auto-compact посередине работы.

**Что было бы нужно:**
- Hook, который измеряет текущее context usage перед heavy-cost операциями (`/kickstart`, `/autopilot`).
- Рекомендация `/session-save` до приближения к лимиту, а не фикс на 40 prompts.
- Возможно — tiered prompt injection pattern (из GSD-analysis, v1.18.0), применённый системно.

**Почему не делаем сейчас:** нет external user signal, ROADMAP v1.21 DEFERRED, см. §6.

### 5.3. K5 — Append-only durable state (◐)

**Paper говорит:** durable state не редактируется деструктивно; read-time chain patching восстанавливает актуальное view.

**У нас:**
- `session_YYYY-MM-DD.md` — append-only per session ✅
- `CLAUDE.md` — редактируется in-place (например, status table в `/kickstart`)
- `MEMORY.md` — редактируется in-place (index обновляется)
- `scripts/sync-to-active.sh` делает backup rotation в `.claude/backups/` — это компромисс

**Что было бы нужно:** заменить in-place правки patch-chain'ом (каждая модификация — новый файл `CLAUDE.md.patch-N`, reader конструирует финальное view). Это ломает UX (пользователь читает `CLAUDE.md` глазами) — gap сознательно принят.

### 5.4. K7 — Values over rules (◐)

**Paper говорит:** когда 93% permission-запросов одобряются — решение *пересмотреть границы*, а не увеличить количество предупреждений.

**У нас:** жёсткие rules:
- Binary rubrics в `/review`, `/security-audit`, `/deps-audit`
- Hard-block hooks: `check-skill-completeness.sh`, `check-commit-completeness.sh`
- Meta-review — 23 detergic checks

**Почему так:** для solo-maintainer'а детерминистичные rules дают предсказуемую quality и auditable surface. Values-подход требует LLM-рассуждения на каждом checkpoint'е — дороже по токенам и хуже воспроизводимо.

**Компромисс:** `/advisor` (v1.19.0) и `/discover` (v1.17.0) — values-oriented (контекстный анализ, без rubric'а). То есть values-layer есть, но только для read-only skills. Гибрид, не чистая rule-based модель.

### 5.5. K12 — Pre-trust execution window (◐, осознанное)

**Paper описывает 4 CVE-класса** в pre-trust window: hook/MCP выполняется до согласия пользователя и получает структурно привилегированный attack surface.

**Audit 2026-04-21:** три UserPromptSubmit хука методологии:

| Хук | Operations | Запись | Network |
|---|---|---|---|
| `pre-flight-check.sh` | `git rev-parse`, `git branch --show-current`, `git log --oneline -10`, `git status --short` (все с 2с timeout); чтение `MEMORY.md`, `.active-session.lock`, `plugin.json`, `session_*.md` | `/tmp/claude-cwd-history-{session_id}.json` | Нет |
| `session-open-diagnostic.sh` | Чтение `session_*.md`, `LAUNCH_PLAN.md`, `BACKLOG.md`, `ROADMAP_v*.md`, `MEMORY.md` | `/tmp/claude-session-diag-{session_id}.done` (sentinel) | Нет |
| `context-aware.sh` | Stdin consume только | `/tmp/claude-context-{session_id}.json` (counter state) | Нет |

Ни один не вызывает `eval`/`os.system` с user-controlled input. Таймаут на git жёсткий. State files sandbox'ятся session_id.

**Отличие от CVE-модели в paper:**
- Paper описывает auto-loaded MCP / auto-installed hooks.
- Наши хуки — user-opt-in: пользователь явно запустил `scripts/sync-to-active.sh`, чтобы их активировать. Plugin install хуки **не** устанавливает автоматически (это зафиксировано в README §"Recommended Setup").

Эта модель снижает surface risk, но не устраняет его полностью: если пользователь установит hooks в системе с compromised repo, pre-trust-выполнение всё ещё произойдёт. Mitigation: 2с timeout + read-only + no-network дают узкий window, где maximum blast radius — утечка путей проекта в `/tmp/` files.

**Статус:** осознанный trade-off, задокументирован. Не приоритетный gap.

### 5.6. K14 — Graduated autonomy levels (◐)

**Paper говорит:** агенты должны предлагать диапазон autonomy, не binary switch.

**У нас:** есть два полюса — `/autopilot` (максимум) и обычная интерактивная работа (всегда ждём user confirm на Gates). Промежуточных уровней нет.

**Почему сейчас не делаем:** добавление autonomy-selector'а на входе в `/project` / `/task` — UX friction без signal'а. Community feedback (`project_community_feedback.md`) содержит запрос на «flexible entry points», но он n=1. Ожидаем multi-point signal.

### 5.7. K15 — Execution transparency / live tracing (◐)

**Paper говорит:** code visibility + execution tracing позволяют debugging и user oversight.

**У нас:**
- `/session-save` — post-hoc summary, не live trace
- `cost-tracker.sh` — per-session usage counter
- Session memory — historical view

**Gap:** нет live execution trace вида «на шаге N скилл `/kickstart` прочитал файлы X,Y, сделал tool call Z с параметрами {...}». Полезно для retro-анализа багов в самой методологии.

**Реализация:** потребовала бы PreToolUse hook, пишущий jsonl-trace в `.claude/traces/session-{id}.jsonl`. Опциональный, не auto-enabled. Кандидат в v1.21.

### 5.8. K16 — On-disk checkpoints (❌)

**Paper говорит:** `~/.claude/file-history/<sessionId>/` — snapshot-based recovery checkpoint'ы.

**У нас:** rollback опирается на `git` целиком. Это работает для текстовых файлов и коммитов. Но:
- `/migrate` делает backup SQL → `/tmp/migrate-backup-*.sql` — это не checkpoint в snapshot-smысле.
- `/deploy` не делает pre-deploy snapshot. Если деплой сломает prod — rollback только через `git revert` + повторный деплой.
- Docker container state, running processes, deployed filesystem — git не охватывает.

**Что было бы нужно:** `/harden` расширение — pre-deploy snapshot script, возможно в составе runbook. Или отдельный `/checkpoint` skill.

## 6. Сводка

| Статус | Количество | Принципы |
|---|:---:|---|
| ✅ Покрыто | 7 | K2, K3, K6, K8, K9, K10, K11 |
| ◐ Частично | 6 | K1, K5, K7, K12, K14, K15 |
| ❌ Gap | 2 | K4, K16 |
| N/A | 1 | K13 |
| **Итого применимых** | **15** | K1–K12, K14–K16 |

Фактическое покрытие: **13 из 15 применимых** (87%) в полной или частичной форме. Два явных gap'а — **K4** (context budgeting) и **K16** (on-disk checkpoints помимо `git`) — артикулированы и являются кандидатами в будущий scope. K12 (pre-trust window) помечен ◐ как осознанный trade-off: хуки user-opt-in, а не auto-loaded MCP (см. §5.5 за деталями audit'а).

## 7. Следствия для ROADMAP

Текущее решение — **[ROADMAP v1.21 DEFERRED](../ROADMAP_v1.21.md)**: пауза code-release'ов до multi-point adoption signal.

Этот документ **не меняет** этого решения. Его роль иная:

1. **Честная позиция перед аудиторией.** Публикация paper Liu et al. задаёт language of comparison в экосистеме. Наличие DESIGN_SPACE map даёт пользователям, сравнивающим методологии, явный ответ «что покрыто, что нет».
2. **Signal-trigger map.** Если внешний пользователь придёт с pain point, который попадает в K4, K15 или K16 — у нас готовая ссылка: «это известный gap, вот причина, вот scope для v1.21». Это удовлетворяет критерий 1 из `ROADMAP_v1.21.md §"When to revisit v1.21"` (multi-point signal on same feature).
3. **Защита от cargo-cult scope creep.** K1, K7, K14 — намеренно не покрыты, не потому что забыли, а потому что философия проекта отличается. Документация этих решений предотвращает будущий соблазн «добавить, чтобы было как у всех».

**Кандидаты в v1.21 scope** (в порядке приоритета при появлении signal):

1. **K4 Context budgeting.** Highest-value gap. Реализация: hook + `/session-save` интеграция. Effort: 5–7 дней.
2. **K16 On-disk checkpoints.** В составе `/harden` или как отдельный `/checkpoint`. Effort: 3–5 дней.
3. **K15 Live execution tracing.** Опциональный trace-hook. Effort: 2–3 дня.

Ни один из пунктов не активируется без external signal.

---

**Обновление документа.** При изменении числа скиллов/хуков или появлении нового принципа в upstream paper — обновлять таблицу §4 и счётчики в §6. Если gap закрывается — статус меняется на ✅ и добавляется пометка о версии-релизе.
