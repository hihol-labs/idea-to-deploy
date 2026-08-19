# Scope Lock — R5 (LPD-002): класс ledger-close кандидата

## Current Task

Пятый пункт плана `.itd-memory/LPD-002_UNIT_PLAN.json` (approved владельцем
2026-08-18), riskTier **high** (`checkerMode full`, `checkerRequired true`,
`minimumIndependentReviewers 1`, независимость требует другой сессии И другой
модели/провайдера), WIP=1. Источник: retro 2026-08-18 E1 -> P1;
первоисточник дефекта — `.itd-memory/HANDOFF-S10-LEDGER.md` §17.11-17.12.

## Корень (измерен на текущем коде, не предположен)

`skills/_shared/itd_review_evidence.py:69` `evidence_first_policy()` возвращает
`None`, как только followup закрыт (`followup_is_closed`, :51), а
`coverage_matrix` (:103) на `None`-политике отдаёт `None`.
`skills/_shared/itd_free_reviewer_producer.py:1240` кладёт `evidenceCoverage` в
пакет только `if evidence_coverage is not None` -> в промпт ревьюера уходит
`EVIDENCE_COVERAGE=null`.

Отсюда неразрешимый круг, замеренный на S10:

- followup закрыт -> покрытия нет -> ревьюер даёт **BLOCKED high**: «политика
  требует покрытия correctness/error-handling/repository-hygiene/security»;
- followup открыт при том же close-дифе -> **BLOCKED**: «STATE и контракт
  расходятся».

Ни одно положение не пропускает ledger-close коммит. Цена обхода: `STATE` в
`main` систематически отстаёт на один юнит, отметки закрытия едут «зайцем» в
чужом delivery-коммите — включая delivery-коммит самого R5.

## Candidate composition (allowed zones)

- `skills/_shared/itd_review_evidence.py` — точное определение класса
  `ledger-close`: `LEDGER_STATE_PATH`, `CLOSING_FOLLOWUP_FIELDS`,
  `ledger_close_policy()`; вынесенная общая валидация политики
  (`_validated_policy`); необязательный именованный аргумент `candidate` у
  `coverage_matrix()` (без него РЕШЕНИЕ политики прежнее: закрытый followup
  отпускает матрицу, открытый требует своего покрытия); постоянное поле
  `coverageSource` в матрице (`active-unit` | `closed-unit-inherited`) —
  форма матрицы меняется всегда, и это осознанно.
- `skills/_shared/itd_free_reviewer_producer.py` — `freeze_packet` собирает
  факты кандидата (пути дифа из `_staged_file_records`, путь контракта
  относительно корня, base-версия контракта через `_git_blob`) и передаёт их в
  `coverage_matrix`; общий хелпер `_closing_coverage_note()` рендерит строку
  `closing commit: coverage inherited from the delivered unit <id>` во ВСЕХ
  трёх поверхностях, где дампится покрытие: `review_prompt` (плоский путь,
  которым судился ledger-close на S10), `_unit_review_prompt`,
  `_integration_review_prompt`.
- `tests/verify_review_evidence.py` — **НОВЫЙ**, первый прямой оракул модуля
  (до R5 он покрыт лишь косвенно через
  `tests/verify_independent_review_efficacy.py:289/304/315/342`).
- `tests/verify_free_reviewer_producer.py` — рендер строки во всех трёх
  промптах, отсутствие строки на обычном кандидате, `minimum_reviewer_count`
  на унаследованном покрытии.
- `tests/run-all.sh` — регистрация `verify_review_evidence` в списке `CORE`
  (список ведётся руками, сьюта там не было).
- `.itd/DECISIONS.md` — две durable-записи: (1) строка наследования идёт во все
  три поверхности промпта, а не только в unit-промпт; (2) close-класс
  клампится к `minimumIndependentReviewers >= 1` — сила маршрута не
  ослабляется.
- `.itd/ACCEPTANCE_CONTRACT.json` — критерии `LPD002-R5-*`, ротация
  `activeFollowup` `LPD002-R4` -> `LPD002-R5`;
  `.itd-memory/contracts/LPD002-R5.md`; `.itd-memory/LPD-002_UNIT_PLAN.json` —
  статус пункта R5 и `oracleAmendments`; `CHANGELOG.md`, `BACKLOG.md`.
- С delivery-коммитом R5 едут отметки закрытия R4 в `STATE.json` и
  `LPD-002_UNIT_PLAN.json` (тот же шаблон R1 -> R2 -> R3 -> R4; обход
  HANDOFF-S10 §17.11 снимается только ПОСЛЕ мержа R5, отдельным решением
  владельца).
- Перечеканка на итоговом дереве отдельным коммитом: live-model-benchmark
  (`skills/` входит в `METHODOLOGY_TREE_ROOTS`).

## Явно вне скоупа

- **Расширение класса за букву критерия.** Класс — ровно
  `.itd-memory/STATE.json` **и** контракт, изменённый только в
  `activeFollowup.status` / `activeFollowup.closedAt` (оба файла обязательны и
  обе строки дифа обязаны иметь статус `M`: переход контракта и есть закрытие,
  а леджер закрытие правит, а не создаёт и не уничтожает). Реальный close этого
  плана трогает ещё `.itd-memory/LPD-002_UNIT_PLAN.json` -> кандидат из класса
  выпадает и судится как раньше. Это осознанный выбор владельца (2026-08-19):
  буква approved-критерия, разрыв зафиксирован находкой в `BACKLOG.md` и
  проверяется догфудингом после мержа.
- **Ослабление продюсера ради прохождения ledger-close** — отвергнуто планом
  как Гудхарт (`designDecisions`). Диф вне точного состава класса судится
  ровно как сегодня.
- Скраббер, подписи, ключи, кэш ревью, модель доверия maker/checker, новые
  вендоры и транспорты ревьюера (`outOfScope` плана).
- Пункт R6 (карта impact-графа) — отдельная сессия, WIP=1.
- Догфудинг close-коммитом самого R5 — решение владельца ПОСЛЕ мержа, не
  действие агента внутри этого юнита.

## Принцип

Гейт распознаёт класс кандидата, а не ослабляет требование. Закрытие юнита
несёт нулевой код, поэтому его покрытие — это покрытие уже доставленного
юнита, названное ревьюеру явно; а число независимых ревьюеров при этом не
падает ни на одного. Любой байт вне точного состава класса возвращает
кандидата на обычный маршрут.
