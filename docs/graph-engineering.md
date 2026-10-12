# Graph engineering и idea-to-deploy: карта терминов (ADR-013)

> Источник: Greg Isenberg, «Why Graph Engineering will 10x your Claude/Codex» (2026-08-03,
> youtube JWhICz1QR8M). Видео концептуальное, кода в нем нет; этот документ - карта «что из
> этого в ITD уже есть, что добавил [ADR-013](adr/ADR-013-graph-lite-measured-exception.md),
> чего нет и почему».

## Словарь видео

| Термин | Смысл по видео |
|---|---|
| prompt engineering | как лучше спросить модель |
| context engineering | как дать модели лучшую информацию |
| graph engineering | как спроектировать работу ВОКРУГ модели: jobs + arrows + state вместо одного длинного чата |
| job (узел) | одна ограниченная работа: один вход, один выход |
| arrow (ребро) | зависимость: выход одного узла - вход другого; ребро есть только там, где реально движутся данные |
| state | общая запись того, что система уже знает |
| knowledge graph | как связана информация (сущности, отношения, время, провенанс) |
| agent graph | как движется работа: planner -> researchers (параллельно) -> skeptic -> synthesizer -> human |
| уровень 1 / 2 / 3 | вручную на доске / Claude Code или Codex, каждый шаг пишет свой файл / LangGraph, AutoGen, n8n |

Правила из видео: граф только для работы с несколькими шагами, источниками, параллельными
ветками, проверками, рисками или аппрувами; пишущий отдельно от проверяющего (модель,
оценивающая свой ответ, завышает уверенность); сначала нарисовать и прогнать руками,
фреймворк - когда структура доказала себя; наименьший граф, который поднимает качество;
человеческий гейт там, где ошибка дорогая; ловушка - раздутые графы.

## Coding graph видео и маршрут ITD

Видео: plan -> edit -> review the diff -> run tests -> check the UI -> hunt edge cases ->
human approves the PR. Узел за узлом это уже маршрут ITD:

| Узел видео | В ITD |
|---|---|
| planner | `/task`, `/blueprint`, агенты `architect` / `Plan` |
| researchers (параллельно) | `business-analyst`, `researcher`, `/market-scan`, `/mcp-docs` |
| skeptic | `devils-advocate`, `/grill-me` |
| writer | `/bugfix`, `/refactor`, `/kickstart` |
| checker (другая модель) | `code-reviewer`, `security-reviewer`, `/review`, `/cross-review` (gpt-5.6-sol) |
| run tests / hunt edge cases | `/test`, completion-gate (тесты реально прогнаны, иначе не done) |
| check the UI | `/browser-check`, `ux-reviewer` |
| human approves | гейты push/PR/deploy/migrate/money, `pii-egress-guard`, `check-predeploy-gate` |
| state | контракты `.itd/`, `.itd-memory/` (STATE, GOAL, events), квитанции Verification Loop |
| «каждый шаг пишет свой файл» (уровень 2) | артефакты `/blueprint`, `HANDOFF.md`, session-файлы памяти, `.itd-memory/verification-loop/` |

Итого ITD - graph engineering уровня 2 по классификации видео: граф задачи зашит в маршрут и
хуки, каждый шаг оставляет файл, человек стоит на необратимых действиях. Чего не было: ЯВНОГО
графа одной задачи как объекта (нарисовать, утвердить, исполнить, сравнить два прогона) и
хостового рантайма графов (Workflow tool Claude Code) как транспорта.

## Что добавил ADR-013: `/graph` (Graph Lite)

- Явный граф одной задачи файлами: `.itd-memory/graph-runs/<run-id>/graph.json` ->
  `approval.json` (владелец утверждает точный digest) -> `nodes/<id>.md` + `receipt.json` ->
  `decision.json` (человек). Скрипт - `skills/graph/scripts/itd_graph.py`, скилл -
  `skills/graph/SKILL.md`.
- Транспорт: `emit-workflow` печатает скрипт Workflow tool (параллель внутри слоя, барьер
  между слоями, узел без выхода бросает ошибку); `emit-serial` - тот же граф последовательно
  для хоста без рантайма. Фича хоста переносит контракт, не является им (ADR-001,
  best-effort инвариант `docs/harness-best-effort.md`).
- Default-off: `disable-model-invocation: true`, вызов только `/graph`. Узлы read-only по контракту: агент Explore без инструментов правки и проверка
  git-состояния проекта при записи; это не песочница. Граф
  не ставит `verified` и не заменяет ни один гейт.
- Шаблон `module-neighbour-check` - под измеренный пробел ADR-012 (8 из 16 посеянных
  дефектов в соседних функциях модуля не нашла ни одна ветка замера): 4 охотника по классам
  (владелец, валюта и сумма, дедуп, время) -> скептик -> синтезатор -> человек.
- Правило решения до прогона (ADR-013 п.6): default-on только при выигрыше >= 0.25 по
  поимке дефектов соседних функций при медиане времени <= 3.0 против проверки по классам
  одним агентом.

## Чего нет и почему

| Нет | Почему |
|---|---|
| рантайм или планировщик графов в ITD | ADR-001, ADR-009: исполнение - хосту, ITD - контракты и файлы |
| кэш узловых квитанций (GENG-B) | GATE G0 2026-08-22: медиана экономии 0 мин/юнит на 134 юнитах |
| кворум параллельных ревьюеров (GENG-C) | GENG-C-EXP 2026-08-28: ложных PASSED не снимает |
| узлы с мутациями, граф на несколько сессий | вне этой версии; сначала замер шаблона |
| knowledge graph | другая задача (память, RAG); `/obsidian-export` дает граф заметок, не графовую БД |
| триггеры хуков на «graph engineering» | скилл opt-in по ADR-012; подсказка хука - это opt-out |

## Когда звать `/graph`, а когда нет

Звать: задача про деньги или доступ, где надо прочитать весь модуль по классам; ревью, где
нужны несколько независимых взглядов и скептик; любая работа с параллельными ветками и
дорогой ошибкой. Не звать: одна функция, один тест, одна правка - граф не поднимет качество
(правило наименьшего графа), обычный минимальный путь ADR-012 дешевле.

## Conditional contract-first v2

The source implementation adds contract-boundary-check: contracts and integration explorers, then checker, then human. Synthesis is deterministic (synthesis.json), not another model call. Common task/contracts/function inventory reach every node. IDs are immutable; every proposal gets one contract/reachability assessment; unknown survives and same-line independent claims remain separate.

Authorize a project policy once, after reviewing its exact contents. Get the template fingerprint with `python3 -I skills/graph/scripts/itd_graph_policy.py template-digest`. Write `.itd/GRAPH_POLICY.json` with exactly: version=1, enabled=true, project=absolute root, template=contract-boundary-check, templateSha256=that fingerprint, allowedModules=[relative globs], sensitivePaths=[relative globs], boundaries=[{id,paths:[relative globs]}], maxRuns=1..32, maxAgentNodes=3, maxSeconds=1..3600, expiresAt=UTC ISO. No project is opted in implicitly.

`digest --project ROOT` prints the canonical policy digest; after owner approval, `authorize --project ROOT --digest SHA --by OWNER` records .itd/GRAPH_AUTHORIZATION.json. Changing policy or template invalidates that authorization. This record assumes an honest host; it is not cryptographic protection against the same OS principal.

The task conductor writes `.itd-memory/graph-request.json` with exactly version=1, unitId=current unit, module=tracked relative path, task=original request, functions=[qualified function names], contracts=[{id,requirement}], changedFiles=[tracked relative paths]. An optional unresolved object needs findingId,reason,counterexample and at least two distinct evidence entries {path,sha256}. Evidence bytes are revalidated. An active STATE unit, when present, must match the request.

`prepare --project ROOT --request .itd-memory/graph-request.json --session NATIVE_SESSION` returns a decision. graph selects the approved native plan; recorded reuses validated existing evidence; single retains the ordinary workflow. Execute graph layers with fresh read-only native subagents via emit-serial/emit-workflow and record the unedited JSON. Never silently repeat completed nodes or substitute another graph.

A sensitive path must cross at least two owner-declared boundaries, or there must be a concrete evidence dispute. Counts and names alone are not behavioral proof; the map is project-maintained, not a learned production classifier. The UserPromptSubmit hook supplies the same authorized plan when configuration and a current request exist. The hook cannot call a model; the host/task conductor performs native orchestration. Other safety and completion gates remain intact.

Fresh evaluation uses semantic matching for every proposed match, opaque IDs, native provenance, monotonic/boot-bound costs and clean/ordinary cases. See docs/measurements/graph-v2/PROTOCOL.json. The source is usable by project opt-in; installation/publication/global enablement is a separate operation.
