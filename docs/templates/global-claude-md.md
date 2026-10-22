<!-- ITD:BEGIN methodology - managed by scripts/sync-to-active.sh from docs/templates/global-claude-md.md of the idea-to-deploy repo: edit that file, not this copy. Sync replaces only the block between the ITD:BEGIN/ITD:END markers and keeps everything outside it (personal data). -->
# idea-to-deploy - общие правила для всех проектов

idea-to-deploy (ITD) - методология по умолчанию для каждого проекта на этой машине, нового и существующего. Проектные
`CLAUDE.md` и `AGENTS.md`, контракты `.itd/` и гейты, которые проект включил сам, имеют приоритет над этим блоком,
кроме раздела "Всегда обязательно": его проект может только ужесточить, но не ослабить и не отменить.

## Штатный режим: минимальный маршрут

- Пойми задачу, сделай, напиши или поправь тесты, прогони набор тестов, покажи результат с цифрами.
- План и согласование - коротко и только для большой фичи или неясной задачи.
- Скиллы - по прямой просьбе пользователя или когда скилл явно сокращает работу. Для обычной работы не нужны строка
  о выборе скилла, пометки об обходе, маршрут через `/task`, обязательный `/review`, раунд cross-review, цели `/goal`
  и контракты `.itd/`.
- WIP=1: одна задача за раз; находки вне задачи - в BACKLOG, а не в текущий дифф.

## Когда включается strict

Strict-маршрут - контракты и гейты проекта, его проверки и одно независимое ревью финального кандидата. Он обязателен,
когда работа касается:
- критичных механизмов самого ITD: хуки, trust policy, pre-push, CI, runtime установки;
- strict-проекта: проект сам включил контракты `.itd/` и гейты (например, invoices) или объявил
  `itd-domain: data-sensitive` (изменение сначала моделируется только на чтение, "до/после" - человеку, затем
  подтверждение и изменение); такой проект не понижается до минимального маршрута;
- денег, доступа (auth, секреты, права), деплоя, миграций и прод-данных, внешних действий.

## Всегда обязательно

1. **Подтверждение человека** перед необратимым или внешним: деплой, миграции и изменения прод-данных, деньги,
   push/PR/отправка наружу, удаление.
2. **Секреты** не выводить и не отправлять наружу.
3. **Тесты** к новому коду и прогон набора перед коммитом. Написать тест - не значит прогнать: готово только после
   зеленого прогона; коммит при красном слое останавливает completion-gate (осознанный обход -
   `COMPLETION_BYPASS: <причина>`, причина пишется в `.itd-memory/events.jsonl`).
4. **Grounded progress claims.** Before reporting progress, audit each claim against a tool result from this
   session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly.
   Report outcomes faithfully: if tests fail, say so with the output; if a step was skipped, say that; when
   something is done and verified, state it plainly without hedging.
5. **Память**: `/session-save` в конце значимого блока работы или по просьбе (`/session-save --close` - явное
   закрытие сессии); решения - в `.itd/DECISIONS.md`; работа не уместится в ~60% контекста - `/handoff`.

## Harness-native features - best-effort invariant

The harness ships vendor-specific tools (typed tool-calls, chips, artifacts, background agents, transcript search):
- A harness feature may TRANSPORT a contract, never BE the contract: no gate, no `verified` transition, no handoff
  may depend on a specific tool-call; the contract stays vendor-neutral (text/JSON in the transcript, files in the
  repo), and a feature that disappears degrades to that path, never to a false "all green".
- Egress (anything leaving the machine) goes through the secret scrubber AND explicit human confirmation;
  background/scheduled agents are read-only reporters - never commit, push or edit unattended.

## Где скиллы

- Плагин `hihol-labs/idea-to-deploy`: 41 skills + 10 agents + 31 hooks в `~/.claude/skills/`, `~/.claude/agents/`,
  `~/.claude/hooks/` (Codex - тот же плагин). Частые входы: `/project` - новый проект, `/task` - выбор скилла для
  задачи, `/bugfix`, `/test`, `/review`, `/deploy` и `/migrate` (с подтверждением), `/session-save`, `/handoff`,
  `/goal` - цель на несколько сессий.
- Подробности - в самих скиллах и в документах репо методологии (`docs/completion-gate.md`,
  `docs/harness-best-effort.md`, `docs/project-profiles.md`), а не в этом блоке.
<!-- ITD:END methodology -->
