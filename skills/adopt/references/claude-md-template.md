<!--
Canonical CLAUDE.md block for projects adopted into the idea-to-deploy methodology.

/adopt appends everything between the BEGIN and END markers to the project's CLAUDE.md (or writes the whole file
if CLAUDE.md is absent). Re-running /adopt detects any idea-to-deploy marker and does nothing - idempotent.

The block is a POINTER, not a copy of the rules (INSTALL-OWNED-1): the rules, hooks, skills and .itd tools live in
the installation (~/.claude for Claude Code, the plugin for Codex), so updating the installation updates every
project. Never paste methodology rules into a project file - a copy freezes that project on an old version.
-->

<!-- idea-to-deploy:begin v{{VERSION}} -->
## Idea to Deploy

Проект работает по методологии Idea to Deploy из глобальной установки (`~/.claude`: хуки, скиллы, глобальный
`CLAUDE.md`; для Codex - `~/.codex/AGENTS.md` и плагин). Действует минимальный путь по умолчанию (ADR-012):

- Обычную работу делай напрямую: пойми задачу, сделай, напиши или поправь тесты, прогони набор, покажи результат.
- Скиллы - по прямой просьбе или когда скилл явно сокращает работу; план - коротко и только для большой задачи.
- Подтверждение обязательно перед необратимым или внешним: деплой, миграции и прод-данные, деньги, push/PR, удаление.
- Секреты не выводить и не отправлять наружу; тесты к новому коду и прогон набора перед коммитом.

Подключено {{ADOPTED_AT}} через `/adopt`. Контракты проекта - в `.itd/`, состояние - в `.itd-memory/`.
<!-- idea-to-deploy:end -->
