# idea-to-deploy - общие правила для всех проектов (Codex)

idea-to-deploy (ITD) - методология по умолчанию для каждого проекта в этой установке Codex, нового и существующего:
плагин `idea-to-deploy` включен, его хуки просматриваются и доверяются через `/hooks`. Проектные `AGENTS.md`,
контракты `.itd/`, состояние `.itd-memory/` и гейты, которые проект включил сам, имеют приоритет над этими правилами,
кроме раздела "Всегда обязательно": его проект может только ужесточить, но не ослабить и не отменить. Тот же смысл,
что у управляемого блока `~/.claude/CLAUDE.md` (`docs/templates/global-claude-md.md` в репо idea-to-deploy).

## Штатный режим: минимальный маршрут

- Пойми задачу, сделай, напиши или поправь тесты, прогони набор тестов, покажи результат с цифрами.
- План и согласование - коротко и только для большой фичи или неясной задачи.
- Скиллы плагина - по прямой просьбе пользователя или когда скилл явно сокращает работу. Для обычной работы не нужны
  выбор lifecycle-скилла перед каждой правкой, маршрут через `task`, обязательное ревью перед коммитом, раунд
  cross-review, цели `goal`, контракты `.itd/` и Verification Loop.
- WIP=1: одна задача за раз; находки вне задачи - в BACKLOG, а не в текущий дифф.

## Когда включается strict

Strict-маршрут - контракты и гейты проекта, его проверки (`.itd/VERIFICATION_CONTRACT.json`, Verification Loop:
замороженный кандидат, машинный оракул, проверка по риск-тиру) и одно независимое ревью финального кандидата. Он
обязателен, когда работа касается:
- критичных механизмов самого ITD: хуки, trust policy, pre-push, CI, runtime установки;
- strict-проекта: проект сам включил контракты `.itd/` и гейты (например, invoices) или объявил
  `itd-domain: data-sensitive` (изменение сначала моделируется только на чтение, "до/после" - человеку, затем
  подтверждение и изменение); такой проект не понижается до минимального маршрута;
- денег, доступа (auth, секреты, права), деплоя, миграций и прод-данных, внешних действий.

В strict-маршруте завершение принимается только по текущей перепроверенной квитанции adjudication; проза или
отдельный вердикт `PASSED` не доказательство. Необъявленные неотслеживаемые и игнорируемые файлы в оракул не входят;
нужный вход вне Git объявляется явно с хешем содержимого.

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
5. **Память**: скилл `session-save` в конце значимого блока работы или по просьбе (`session-save --close` - явное
   закрытие сессии); решения - в `.itd/DECISIONS.md`; работа не уместится в ~60% контекста - скилл `handoff`.

## Harness-native features - best-effort invariant

The harness ships vendor-specific tools (typed tool-calls, chips, artifacts, background agents, transcript search):
- A harness feature may TRANSPORT a contract, never BE the contract: no gate, no `verified` transition, no handoff
  may depend on a specific tool-call; the contract stays vendor-neutral (text/JSON in the transcript, files in the
  repo), and a feature that disappears degrades to that path, never to a false "all green".
- Egress (anything leaving the machine) goes through the secret scrubber AND explicit human confirmation;
  background/scheduled agents are read-only reporters - never commit, push or edit unattended.

## Где скиллы

Скиллы, агенты и хуки - в плагине `idea-to-deploy` (тот же набор, что у Claude Code); подробности - в самих скиллах и
в документах репо методологии, а не здесь. Неподключенный проект подключается скиллом `adopt` только по просьбе
пользователя: сначала осмотр и план, запись - после разрешения.

Product Factory OS на этой машине - legacy: не загружать и не подключать без явной просьбы пользователя.
