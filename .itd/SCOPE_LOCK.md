# Scope Lock — R6 (LPD-002): карта воздействия как данные + два оракула

## Current Task

Шестой и ПОСЛЕДНИЙ пункт плана `.itd-memory/LPD-002_UNIT_PLAN.json`
(approved владельцем 2026-08-18), riskTier **medium** (`checkerMode targeted`,
`checkerRequired true`, `minimumIndependentReviewers 1`, независимость требует
другой сессии, но НЕ другой модели/провайдера; контуры `static + targeted`),
WIP=1. Источник: LPD-001 M3 (оставлен при пересмотре плана). Бриф пункта —
`.itd-memory/LPD-002_R6_BRIEF.md`.

## Корень (измерен на текущем коде, не предположен)

`impact_closure` (`skills/_shared/itd_verification_profiles.py:112` до правки)
УЖЕ принимает `impactGraph` и `impactKnown` и обходит граф BFS. Чего нет:
(1) самой карты «путь исходника -> сьюты» как данных в репозитории; (2) машинной
проверки её полноты; (3) машинной проверки пропорциональности. Ручной список в
LPD-001 прямо отвергнут как источник ошибок U9/U10; масштаб на 2026-08-19:
151 `tests/verify_*.py`, 18 `skills/_shared/*.py`, 30 `hooks/*.sh` — ручная
карта устареет на следующем сьюте, поэтому полнота обязана быть машинной.

## Candidate composition (allowed zones)

- `skills/_shared/itd_verification_profiles.py` — поле запроса
  `impactGraphPath` (взаимоисключимо с inline `impactGraph`; `impactKnown:false`
  карту не читает), загрузчик документа карты (`schemaVersion 1`, `universe`,
  `generated`, `declared`), слияние `generated ∪ declared`, операция
  `impact-audit` (`audit_impact_graph`: полнота — `unattachedSuites`,
  `orphanOwned`, `staleNodes`, `staleTargets`; пропорциональность —
  `saturatedNodes`, `maxClosure < fullSet`). Обход графа — прежний BFS,
  вынесенный в `walk_closure` без изменения семантики. Нового движка нет
  (ADR-001).
- `.itd/IMPACT_GRAPH.json` — **НОВЫЙ**, сама карта как данные (tracked;
  `.itd/` скрыт только локальным `.git/info/exclude`, поэтому `git add -f`).
- `tests/build_impact_graph.py` — **НОВЫЙ** генератор секции `generated` из
  tracked-дерева (`git ls-files`): прямое ребро в один шаг — литеральный путь,
  `"a" / "b"`-конкатенация, Python `import`/`from … import`, уникальный
  basename (.py/.sh/.ps1/.json) и stem >= 8 для `.py`; `--check` = дрейф карты.
- `tests/verify_verification_profiles.py` — оракул пункта (57 -> 103 проверок):
  карта как данные, аудит PASS на живом дереве, `impactKnown:false` -> strict,
  5 мутаций данных + 4 мутанта движка, `--check` FRESH. Правило
  взаимоисключения `impactGraph`/`impactGraphPath` проверяется ДО раннего
  выхода по `impactKnown:false` (находка cross-vendor ревьюера PUB1), при этом
  неизвестный impact карту по-прежнему не читает — обе стороны покрыты.
  По находке PUB3 (security) добавлено containment: `root` обязан быть
  существующей директорией, `impactGraphPath` обязан резолвиться ВНУТРИ root
  (`escapes the declared root` -> fail-closed), узлы/цели графа — только
  repo-relative без `..` и без абсолютных путей (`outside the repository
  root` -> fail-closed); `root` сам обязан быть рабочим репозиторием или
  директорией внутри него (`escapes the working repository`), а containment
  узлов/целей проверяется ПО РАЗРЕШЁННОМУ пути — симлинк внутри репо не
  протаскивает внешний файл мимо аудита (находки sec-чекера r1). По находке
  PUB4: цели графа обязаны быть сьютами (`nonSuiteTargets` -> FAIL — покрытие
  владеемого исходника через промежуточный не-сьют больше не отмывает
  `orphanOwned`), а оракул проверяет, что карта TRACKED git'ом, не остаток в
  worktree. По находкам PUB6: universe-паттерны (`suites`/`owned`) обязаны
  быть root-relative глобами без `..` и без абсолютных путей (иначе аудит
  глобил бы вне root и падал необработанным ValueError вместо fail-closed
  DecisionError), а `impact-audit` зовёт `reject_ambiguous_graph` — оба
  источника графа сразу отвергаются и в аудите, не только в select.
  По находкам PUB7: path-backed карта подчиняется контракту аудита и в
  `select` (`validate_path_graph`: containment узлов/целей по разрешённому
  пути + цель обязана матчить universe.suites — иначе fail-closed ДО обхода),
  а `resolve_root` требует, чтобы движок был запущен из корня репозитория
  (`.git` существует) — произвольный cwd границей не является.
  По находкам PUB8: NUL-байт в любом пути/паттерне (узел, цель, карта, root,
  universe) -> fail-closed `DecisionError`, а не сырой ValueError из
  Path.resolve; импорты генератора парсятся ast (реальные имена, алиас
  НИКОГДА не фабрикует ребро; `import a, b` резолвит все модули); запись R6
  в CHANGELOG перенесена из ошибочно датированной секции [1.98.0] в
  [Unreleased]. Ложная находка PUB8 про
  `.itd-memory/LPD-002_UNIT_PLAN.json` отклонена фактом: ребро создаёт текст
  СЬЮТА, ссылающийся на файл (см. правило генератора), а не файл, ссылающийся
  на сьют — `verify_review_evidence.py` называет план, поэтому ребро одно, и
  `--check` даёт FRESH. Оракул 86 -> 103 (пять escape-проверок; мутантные карты пишутся внутрь root во
  временный каталог `.itd/tmp-impact-oracle-<pid>/`, который удаляется в
  `finally`; корректность НЕ зависит от его git-ignore статуса — локальный
  `.git/info/exclude` не версионируется).
- `tests/verify_completion_policy_calibration.py` — закрытие НАСТОЯЩЕЙ дыры,
  найденной RED-прогоном аудита: `hooks/completion-stop.sh` не имел ни одного
  прямого сьюта (8 -> 11 проверок: напоминание при грязном коде и красной
  улике, kill switch, тишина при `stop_hook_active`). **Факт для ревьюера:**
  файлы `hooks/*.sh` этого репозитория — Python-программы с шебангом
  `#!/usr/bin/env python3` (так их исполняет и харнес); сьюты запускают их как
  `[sys.executable, <hook>]` — тот же приём, что существующий `run_gate` для
  `completion-gate.sh` в этом же файле. Запуск через `bash` был бы ошибкой.
- Документация: `docs/WORKING_DEADLINE_MODE.md` (раздел «Карта воздействия как
  данные»), `skills/task/SKILL.md` (одно предложение), `CHANGELOG.md`
  `[Unreleased]` (R6), `BACKLOG.md` (регистрация долгов A8/A9 из сессии R5 и
  измеренного предела «ребро — прямой шаг»).
- Леджер юнита: `.itd/ACCEPTANCE_CONTRACT.json` (критерии `LPD002-R6-*`,
  `activeFollowup` -> `LPD002-R6`), `.itd-memory/contracts/LPD002-R6.md`,
  `.itd-memory/STATE.json` (activate `LPD002-R6`, riskTier medium),
  `.itd/DECISIONS.md` (durable-записи R6 + запись R5 из прошлой сессии, которая
  локально не была закоммичена), `.itd-memory/LPD-002_UNIT_PLAN.json`
  (отметка закрытия R5 + активация R6 — тот же шаблон, что R1 -> … -> R5).

## Записанные улики в дифе — это НЕ авторский код кандидата

Правка `skills/` инвалидирует live-evidence пин
(`tests/verify_live_model_benchmark.py`, `METHODOLOGY_TREE_ROOTS`); три
подписанные efficacy-ноги R6 НЕ трогает (их пин — `producerSha256` самого
`itd_free_reviewer_producer.py` плюс раннер и манифест; проверено прямым
прогоном `verify_independent_review_efficacy.py` на дереве R6: PASSED).
Перечеканка live-evidence приедет отдельным коммитом ветки: файлы под
`tests/fixtures/live-model-evidence/` — НАБЛЮДЕНИЕ за поведением внешней
модели, записанное дословно; кандидат их не пишет и не проектирует. В
частности `tests/fixtures/live-model-evidence/runs/*/output/*.md`
(PRD, PROJECT_ARCHITECTURE, IMPLEMENTATION_PLAN и т. д.) — документы,
СГЕНЕРИРОВАННЫЕ внешней моделью под тестом (fixture-03-cli-tool); их
содержание (например, раскладка exit-кодов в PROJECT_ARCHITECTURE.md) судится
snapshot-оракулом бенчмарка, а не ревью кандидата: находка об их содержании —
находка о модели, не о кандидате, и «исправить» её можно только фальсификацией
улики.
`transcript.jsonl.gz` на диске — настоящий gzip; ревьюер видит его прозрачным
представлением продюсера.

**Устаревшие промежуточные записи удалены из дерева PR осознанно
(постоянная политика ветки, не разовый акт).** Каждый reviewed-коммит,
менявший `skills/`, требует свежей live-записи; `latest.json` всегда
ссылается только на ФИНАЛЬНУЮ, и каждая превзойдённая директория
`tests/fixtures/live-model-evidence/runs/…` удаляется из дерева PR
последующим кандидатом. Причина измерена: прозрачное представление
нескольких декодированных транскриптов (~150-190 KB JSONL каждый)
превышает иерархический предел ревью-юнитов (`maxReviewUnits 16 ×
maxRawDiffBytes 80000`, отказ `hierarchical review unit coverage is
invalid` на PUB5). Удалённые записи остаются в истории ветки (их
коммиты: `3063488`, `58c41b9`, `f5b8755`, `5c9efb8`) и в квитанциях
маршрута. Инвариант после каждого удаления: live-пин 108/0 и
`verify_tree_pin_debris` PASSED, ни один tracked-файл не ссылается на
удалённый run-id.

## Явно вне скоупа

- **Перевод `tests/run-all.sh` на карту** (пропорциональный запуск сьютов по
  замыканию). Критерий пункта — данные + два оракула; потребитель карты —
  отдельное решение владельца после релиза LPD-002.
- **Рёбра исходник -> исходник** в `generated`: измерено и отвергнуто
  (транзитивный stem-матчинг насыщает 148/151 сьютов на узел). Предел записан
  в `BACKLOG.md` с кандидатом (точные рёбра по Python-импортам).
- **Долг A5** (класс `ledger-close` и файл плана) — отдельный коммит/юнит, не
  этот дифф.
- Скраббер, подписи, ключи, кэш ревью, модель доверия maker/checker, новые
  вендоры и транспорты ревьюера (`outOfScope` плана).
- Остальные долги (A1-A4, A6-A7; 50 пунктов старше LPD-002) — решение владельца
  2026-08-19: следующей сессией, не здесь.

## Принцип

Карта — данные, которые можно перегенерировать и проверить, а не мнение
автора о том, что на что влияет. Полнота и пропорциональность — свойства,
которые движок ДОКАЗЫВАЕТ на живом дереве при каждом прогоне оракула; карта,
устаревшая на один сьют, видна немедленно и чинится одной командой.
