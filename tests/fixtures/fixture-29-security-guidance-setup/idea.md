# Fixture 29 — /security-guidance-setup

Интеграция официального Anthropic-плагина security-guidance
(anthropics/claude-code, free, ships в claude-plugins-official) в жизненный цикл
idea-to-deploy без вендоринга кода и без потери гейтов.

## Context

Проекту нужна shift-left / realtime безопасность: ловить уязвимости прямо когда
Claude пишет код, ревью на коммите. Проверяется read-only оркестратор/интеграция:
скилл детектит установлен ли upstream-плагин (`claude plugin list`, `claude plugin
details`, `claude --version`, `python3 --version`), запускает/печатает проверенную
команду install, маппит 3 слоя плагина на жизненный цикл (kickstart/task/bugfix/
refactor → realtime warnings + diff-review; migrate/harden/deploy → agentic commit/
push-ревью) и НЕ трогает гейты методологии. Файлы проекта не меняются, код upstream
не копируется.

## Input prompt

Хочу чтобы Claude сам ловил уязвимости на лету пока пишет код — как включить
security-guidance?

## Expected behavior

- Распознаёт shift-left/realtime-security потребность → /security-guidance-setup.
- Детект (read-only): `claude --version` (≥ v2.1.144), `python3 --version` (≥ 3.8),
  `claude plugin list | grep security-guidance`, `claude plugin details
  security-guidance`. Плагин ships default-on — ВЕРИФИЦИРОВАТЬ, а не предполагать;
  если не активен — сказать об этом, НЕ заявлять что активен.
- Запускает/печатает проверенный CLI install: `claude plugin install
  security-guidance@claude-plugins-official`; рестарт Claude Code (хуки грузятся на
  старте); для слоёв 2–3 нужен рабочий API-path.
- Механизм описывается по факту upstream-репо 2.0.0: 3 слоя (pattern-warnings на
  Edit/Write/MultiEdit/NotebookEdit; LLM diff-ревью на Stop; агентский commit/push-
  ревью кросс-файловых уязвимостей) + хуки SessionStart/UserPromptSubmit/PostToolUse
  (Edit|Write|MultiEdit|NotebookEdit)/PostToolUse Bash(git commit|push)/Stop + ~25
  паттернов + env-var конфиг. НЕ выдуманные инструменты.
- Атрибуция к Anthropic / официальному плагину; first-party код (нет стандартного
  OSS SPDX, Commercial Terms) НЕ вендорится в репо.
- Lifecycle-fit: kickstart/task/bugfix/refactor → слои 1–2 ловят injection/XSS/
  secrets как пишется код; review → слой 2 как pre-review гигиена; security-audit →
  КОМПЛЕМЕНТ (continuous shift-left под on-demand аудитом); migrate/harden/deploy →
  слой 3 agentic ревью на коммитах, трогающих схему/auth/прод.
- Coexistence: DoD/review pre-commit гейт (PreToolUse, блокирует) + post-commit
  security-ревью плагина (PostToolUse, async) = defense-in-depth, не дубль; для
  мульти-агентных/shared-worktree — `ENABLE_STOP_REVIEW=0` (совет upstream); гейты
  (`/review`, `/test`, DoD) и строка-решение остаются явными.
- /security-audit подаётся как КОМПЛЕМЕНТ, не замена.
- Файлы не создаются и не меняются.

## Fixture status

`pending` — snapshot-стаб (тот же бакет, что fixture-15-advisor,
fixture-21-mcp-docs, fixture-26-caveman, fixture-27-context-mode-setup,
fixture-28-seo-setup): read-only, detect/advise stdout-вывод. Полная автоматизация —
Phase 2.
