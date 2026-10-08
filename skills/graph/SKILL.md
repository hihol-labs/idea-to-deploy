---
name: graph
description: 'Graph Lite — turn ONE task into an explicit agent graph (jobs, arrows, shared state, a checker separate from the writer, a human terminal), get the owner to approve the exact graph digest, run it through the host workflow runtime (or node by node when the host has none) and keep every node output as a file under .itd-memory/graph-runs/<run-id>/. Default-off, read-only nodes, explicit invocation only; a measured exception to ADR-012 (ADR-013). Shipped template: module-neighbour-check — four defect classes (owner, money, dedup, time) over a whole money/access module.'
argument-hint: 'module-neighbour-check --module <path> [--task "<text>"] | --from <graph.json> | <task text to design a graph for>'
license: MIT
allowed-tools: Read Glob Grep Bash Write Agent Workflow
disable-model-invocation: true
metadata:
  effort: medium
  side_effect: memory-write
  explicit_invocation: true
  author: HiH-DimaN
  version: 1.107.0
  category: workflow
  tags: [graph, graph-engineering, workflow, fan-out, checker, human-gate, adr-013]
---

# Graph (Graph Lite)

## Trigger phrases

- `/graph` — only an explicit call. The skill carries `disable-model-invocation: true`
  and is never auto-routed: default-off is the point of ADR-013.
- `/graph module-neighbour-check --module <путь>`, `/graph построй граф проверки модуля`
- `/graph design a task graph`, `/graph --from graph.json`

## Recommended model

**Opus/default** для проектирования графа и диалога с владельцем (решение, нужен ли
граф вообще, какие узлы и где человеческий гейт — это рассуждение). Узлы графа
наследуют модель сессии: `model` в `agent()` не задаётся. Если владелец хочет
удешевить прогон, дешевле делать охотников, а не скептика — скептик и есть качество.

## Instructions

Graph engineering здесь — **не рантайм и не замена маршрута**. Это один явный граф
на одну задачу, записанный файлами: спроектировал -> владелец утвердил точный
digest -> хост исполнил -> каждый узел лёг файлом -> человек решил. Инварианты
ADR-009 сохранены: предложение графа не есть разрешение; утверждается точный
`graphDigest`; изменённый граф аннулирует утверждение; все узлы read-only; человек —
единственный терминальный узел; `verified` граф не ставит. Скрипт
`skills/graph/scripts/itd_graph.py` — детерминированная половина скилла; модель не
вызывает, исходники не правит, в сеть не ходит.

### Шаг 0. Резолв путей

```bash
GT="skills/graph/scripts"; [ -f "$GT/itd_graph.py" ] || GT="$HOME/.claude/skills/graph/scripts"
SHD="skills/_shared"; [ -f "$SHD/itd_py.sh" ] || SHD="$HOME/.claude/skills/_shared"
```

Обе строки — в начало каждого shell-вызова (состояние шелла между вызовами не живёт).
Python — только через `sh "$SHD/itd_py.sh" "$GT/itd_graph.py" …` (не голый `python3`:
на Windows Git Bash это WindowsApps-шим).

### Шаг 1. Нужен ли граф (правило наименьшего графа)

Граф оправдан, когда у работы несколько шагов, несколько источников, параллельные
ветки, проверки, риск или аппрув. Одна функция, один файл, одна проверка — графа не
надо: скажи это одной фразой и остановись, каталог прогона не создавай. Это
правило из первоисточника («smallest graph that raises quality»), а не формальность.

### Шаг 2. Проектирование (`init`)

Каталог прогона: `.itd-memory/graph-runs/<run-id>/`. `run-id` — одно имя из латиницы, цифр,
`.`, `_`, `-`, первый символ — буква или цифра; это и проверяет скрипт. Рекомендуемый вид
`YYYY-MM-DD-<slug>` — договорённость для удобства, скрипт её не требует.

Шаблон для денег и доступа (единственный поставляемый):

```bash
sh "$SHD/itd_py.sh" "$GT/itd_graph.py" init .itd-memory/graph-runs/2026-10-07-billing-limits \
  --template module-neighbour-check --module packages/shared/src/billing/limits.ts \
  --project "$PWD" --task "R-10: тарифы и срок подписки"
```

Граф шаблона (алмаз): четыре охотника по классам `owner` (владелец или пустой id),
`money` (валюта и сумма), `dedup` (дедупликация и идемпотентность), `time` (границы
времени) читают ВЕСЬ модуль параллельно -> `skeptic` (role checker) пытается
опровергнуть каждую находку, по умолчанию «опровергнуто» -> `synth` снимает дубли,
ранжирует, готовит строку для журнала утечек -> `human`. Это ровно тот пробел, что
показал замер ADR-012: 8 из 16 посеянных дефектов лежали в соседних функциях модуля, и
diff-ревью их не видит по построению.

Свой граф: напиши `graph.json` (та же схема: `nodes` с `id/role/kind/purity/inputs/
outputs/schema/prompt`, `edges` парами, `schemas`, `state`, `task`) и подай
`init <run-dir> --from graph.json`. Валидатор примет только DAG с одним человеческим
терминалом, read-only узлами, отдельным checker-узлом (`checks` ⊆ его входящих рёбер)
и промптами, в которых явно написано `read-only`.

Покажи владельцу граф словами: таблица узлов (id, роль, что читает, что возвращает),
стрелки, общее состояние, где человеческий гейт, и `graphDigest`. Проверка:

```bash
sh "$SHD/itd_py.sh" "$GT/itd_graph.py" validate .itd-memory/graph-runs/<run-id>
```

### Шаг 3. Утверждение (`approve`)

Жди явного «да / approve». Молчание, «ну ок посмотрим», утверждение другого digest —
не утверждение. Сам за владельца не утверждай.

```bash
sh "$SHD/itd_py.sh" "$GT/itd_graph.py" approve .itd-memory/graph-runs/<run-id> \
  --digest <graphDigest из validate> --by "<имя владельца>"
```

Любая правка `graph.json` после этого даёт `approval-stale`: `emit-*` и `record`
откажут, пока владелец не утвердит новый digest.

### Шаг 4. Исполнение (`emit-workflow` | `emit-serial`)

**Хост с Workflow tool (Claude Code):**

```bash
sh "$SHD/itd_py.sh" "$GT/itd_graph.py" emit-workflow .itd-memory/graph-runs/<run-id>
```

Передай напечатанный скрипт в Workflow tool **дословно** (`script`), не редактируя:
владелец утвердил именно этот граф, правка руками — неутверждённый граф. Эта
инструкция и есть opt-in на Workflow tool для данного прогона. Скрипт исполняет
слои графа: внутри слоя узлы идут параллельно, между слоями барьер (нижний узел
читает ВСЕ выходы верхних), узел без выхода бросает ошибку — прогон красный, не
зелёный. Каждый узел идёт как субагент типа `Explore`: у него нет Edit, Write и
NotebookEdit. Возвращённый JSON `{graphDigest, nodes}` запиши как есть в
`.itd-memory/graph-runs/<run-id>/result.json`.

**Read-only проверяется по факту.** `approve` сохраняет git-состояние проекта (каталога,
где лежит `.itd-memory/`): HEAD и каждый изменённый или неотслеживаемый путь с хэшем
содержимого. `record` сравнивает его с текущим и отказывает при любой разнице: узел что-то
изменил, или кто-то правил проект во время прогона. Пока прогон открыт, проект не трогай.
Вне проверки по построению: git-ignored файлы, `.itd-memory/`, телеметрия харнеса в
`.claude/completion/` и `.claude/traces/`, всё вне проекта и сеть. Graph Lite — не
песочница: read-only узла — контракт, который скрипт подкрепляет, но не гарантирует.
Проект не под git утвердить нельзя.

**Хост без Workflow tool (Codex, отказ инструмента, упавший прогон):**

```bash
sh "$SHD/itd_py.sh" "$GT/itd_graph.py" emit-serial .itd-memory/graph-runs/<run-id>
```

Тот же граф — последовательным планом по слоям. Каждый узел — один свежий read-only
субагент (Agent, `subagent_type` Explore; на хосте без него — самый ограниченный
read-only агент) с промптом узла плюс `UPSTREAM OUTPUTS (JSON)` его
входов; ответ — JSON по схеме узла. Собери `result.json` руками. Узел без ответа не
пропускается: такой прогон не записывается. Серийный путь — первоклассный, не
аварийный (инвариант best-effort харнеса: фича хоста переносит контракт, а не
является им).

### Шаг 5. Запись (`record`)

```bash
sh "$SHD/itd_py.sh" "$GT/itd_graph.py" record .itd-memory/graph-runs/<run-id> \
  --result .itd-memory/graph-runs/<run-id>/result.json --runtime workflow   # или serial
```

Скрипт проверяет digest результата против утверждённого, наличие выхода у каждого
агентного узла, отсутствие чужих узлов и соответствие каждого выхода схеме узла
(закрытое подмножество JSON-схемы: `type`, `properties`, `required`, `items`, `enum`).
Затем атомарно пишет `nodes/<id>.md` на каждый узел и `receipt.json` (digest графа,
runtime, sha256 и размер каждого файла узла). Повторная запись и каталог с остатками
прерванного прогона (`nodes/` без `receipt.json`, состояние `partial`) отказывают:
перепрогон — новый каталог.

Все команды принимают только каталог вида `<проект>/.itd-memory/graph-runs/<run-id>`
без символьных ссылок; id узла — один безопасный компонент пути (`[a-z0-9-]`), так что
файл узла не выходит за каталог прогона. `close` и `status` перед закрытием сверяют
утверждение и каждый файл узла с `receipt.json`: подменённый, удалённый или лишний
файл даёт `receipt-mismatch` и отказ.

### Шаг 6. Человеческий терминал (`close`)

Покажи владельцу `summary`, таблицу находок (`file:line`, класс, severity, origin,
status) и подготовленную `journalLine`. Решение по каждой находке — его. Закрой:

```bash
sh "$SHD/itd_py.sh" "$GT/itd_graph.py" close .itd-memory/graph-runs/<run-id> \
  --decision "<решение владельца>" --by "<имя владельца>"
```

`decision.json` закрывает прогон; второе закрытие отказывает. Строку в
`docs/LEAK_JOURNAL.md` проекта вносит человек (или ты по его явной команде) — скилл
журнал не трогает. Прогон упомяни в `/session-save`: по ADR-013 каждый прогон —
точка данных замера, и шаблон остаётся default-off до выигрыша A/B.

### Состояние прогона

`status <run-dir>` печатает `designed | approved | approval-stale | recorded |
receipt-stale | closed` и digest. Что делает скрипт при любом отказе — печатает
`REFUSED: <причина>` и ничего не пишет (exit 2); невалидный граф — exit 1 с кодами
правил `G01…G12`.

## Examples

### Example 1: проверка модуля биллинга перед отчётом по задаче (neuroexpert)

```
/graph module-neighbour-check --module packages/shared/src/billing/limits.ts --task "R-10 тарифы"
```

-> `init` печатает граф и digest `d9ca…`; владелец: «да» -> `approve` ->
`emit-workflow` -> Workflow tool: 4 охотника параллельно, скептик, синтезатор ->
`record --runtime workflow` -> владельцу: 2 подтверждённые находки (`limits.ts:41`
пустая валюта, `limits.ts:88` граница 24 ч), 3 опровергнуты -> владелец: «первую в
журнал и в задачу, вторую не трогаем» -> `close`.

### Example 2: граф не нужен

```
/graph проверь, что slugifyLatin обрезает по maxLen
```

-> «Одна функция, один тест: граф не поднимет качество, достаточно теста. Каталог
прогона не создаю.»

### Example 3: свой граф из файла

`/graph --from docs/graphs/release-readiness.json` -> `init --from` -> валидатор
отказывает по `G09` (нет checker-узла) -> правишь граф -> `init` снова.

## Self-validation

- [ ] Граф оправдан (несколько шагов/источников/веток/проверок/аппрув), иначе отказ.
- [ ] `graph.json` лежит под `.itd-memory/graph-runs/<run-id>/`, `validate` — `VALID`.
- [ ] Владелец утвердил digest явно; `approval.json` совпадает с текущим digest.
- [ ] Скрипт Workflow передан дословно; или серийный план исполнен узел за узлом.
- [ ] `receipt.json` есть, `nodes/<id>.md` — на каждый агентный узел, `status` = `recorded`.
- [ ] Владелец получил summary и находки с `file:line`; `decision.json` записан им.
- [ ] Ни одной правки исходников, ни одной git-мутации, журнал утечек не трогал.

## Troubleshooting

| Симптом | Причина | Что делать |
|---|---|---|
| `REFUSED: approval is stale` | `graph.json` изменён после утверждения | показать новый digest владельцу, `approve` заново |
| `REFUSED: result has no output for node(s)` | узел упал, пропущен или вернул пусто | прогон красный; перезапустить узел (серийно) и собрать `result.json` целиком |
| Workflow tool недоступен или отклонён | хост без рантайма графов (Codex) или отказ пользователя | `emit-serial`, узлы через Agent по слоям |
| `agent()` вернул `null` | субагент пропущен или умер | скрипт бросает ошибку по построению — не «чинить» скрипт руками, повторить прогон |
| `node --check` ругается на `return` | у Workflow-скрипта тело исполняется внутри async-функции | это норма; проверка синтаксиса — только в тесте с обёрткой |
| `python3: мусор вместо вывода` (Windows) | WindowsApps-шим | запускать только через `itd_py.sh` |
| `INVALID … G09` | нет checker-узла или он проверяет сам себя | писатель и проверяющий — разные узлы; `checks` ⊆ входящих |
| `REFUSED: run directory must be …/.itd-memory/graph-runs/<run-id>` | каталог прогона вне `.itd-memory/graph-runs/` или за символьной ссылкой | создать прогон в `.itd-memory/graph-runs/<run-id>` проекта |
| `REFUSED: node output does not match its schema` | узел вернул JSON не по своей схеме (нет поля, чужое значение enum, не тот тип) | перезапустить этот узел; руками выход не «поправлять» |
| `REFUSED: nodes/ already exists without a receipt` | остатки прерванного прогона (`status` = `partial`) | перепрогон в новом каталоге; старый не трогать |
| `REFUSED: the project changed between approve and record` | узел изменил проект, или проект правили во время прогона | прогон недостоверен: откатить чужие правки, новый каталог и новый прогон |
| `REFUSED: … changed git submodule or nested repository` | в проекте изменён submodule или вложенный репозиторий, его содержимое не хэшируется | закоммитить или очистить его до `approve`; прогон начинается и заканчивается без него |
| `REFUSED: … is not a git work tree` | проект прогона не под git | `/graph` работает только в git-проекте: read-only проверяется по его состоянию |
| `REFUSED: … cannot be re-approved` | у прогона уже есть `nodes/`, `receipt.json` или `decision.json` | записанный прогон неизменен: новый граф — новый каталог |
| `status` = `decision-invalid` | `decision.json` повреждён или не от этого графа | прогон не закрыт: разобраться, кто менял файл; новый прогон |
| `status` = `receipt-mismatch`, `close` отказывает | файл узла изменён, удалён или добавлен после `record` | прогон недостоверен: новый каталог и новый прогон |

## Rules

- `/graph` MUST be invoked explicitly (`disable-model-invocation: true`): нет
  автороутинга, нет подсказок хуков, default-off до выигрыша замера (ADR-013).
- `/graph` MUST write the graph to `.itd-memory/graph-runs/<run-id>/graph.json`
  BEFORE running anything, print the digest, and STOP until the owner approves that digest.
- `/graph` MUST refuse to run a graph whose digest differs from the approved one.
- `/graph` MUST keep every node read-only: no Edit/Write to project sources, no git
  mutation, no deploy, no egress; the only writes are files under the run directory.
  The script backs this contract (Explore agent type, git-state check at `record`) but
  is not a sandbox: ignored files, `.itd-memory/` and network use are not detected.
- `/graph` MUST keep the human as the terminal node; `close` records the decision — the
  skill never accepts its own findings.
- `/graph` MUST degrade to the serial plan when the host has no Workflow tool; a
  missing node output is a refused `record`, never a green run.
- `/graph` MUST record one file per node under `nodes/` plus `receipt.json`.
- `/graph` MUST NOT mint `verified`, replace `/review`, `/test`, the Verification Loop
  or any human gate (deploy, push, PR, migration, money).
- `/graph` MUST NOT add nodes that mutate state in this version (`purity: read-only`
  is enforced by the validator).
- `/graph` MUST NOT re-use an approval after the graph changed, and MUST NOT become
  default-on without a won A/B measurement of the same kind as `~/projects/itd-value-exp`.
