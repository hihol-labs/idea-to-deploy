# SCOPE_LOCK — LPD003-4 (открыт 2026-08-27)

## Предмет
Консолидация сьютов `tests/verify_*.py` по impact-карте: слияние пар с
идентичным множеством покрытия внутри зеркала run-all, без потери покрытия.

## Разрешённые области
- Пять хранителей (принимают проверки доноров): `tests/verify_signal_attribution.py`,
  `tests/verify_observed_token_telemetry.py`, `tests/verify_otel_export.py`,
  `tests/verify_no_bare_python3.py`, `tests/verify_goal_tools.py`.
- Пять доноров (удаляются после переноса проверок): `tests/verify_completion_ledger.py`,
  `tests/verify_cost_tracker.py`, `tests/verify_otel_semconv.py`,
  `tests/verify_py_launcher_encoding.py`, `tests/verify_work_deadline_runtime.py`.
- `tests/run-all.sh` — ТОЛЬКО удаление имён доноров из CORE/FULL.
- `tests/verify_runall_drift.py` — оракул консолидации: доноры отсутствуют,
  хранители привязаны в карте, замер сверен с деревом.
- `docs/VERIFICATION_CONTRACT.json` — только замена/удаление ссылок на доноров.
- `.github/workflows/*.yml` — только замена шагов доноров на шаги хранителей.
- `tests/verify_verification_profiles.py` — ТОЛЬКО числовой floor количества
  сьютов в проверке полноты (стейл-пин 151 при факте 150 после консолидации);
  семантика полноты не меняется.
- `.itd/IMPACT_GRAPH.json` — регенерация генератором (руками не редактируется).
- `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/DECISIONS.md`, `.itd-memory/STATE.json`,
  `.itd-memory/measurements/LPD003-4-consolidation.json` (замер, git add -f),
  `BACKLOG.md` (только записи, порождённые/закрываемые юнитом) — бухгалтерия.
- `.itd-memory/GOAL.json` — ТОЛЬКО замена пути удалённого донора на хранителя
  в verificationCommand юнита PE5-011 (находка чекера claim1: живая ссылка на
  удалённый файл ломала бы recheck не по делу).

## Запрещено
- Терять или ослаблять ЛЮБУЮ донорскую проверку при переносе (перенос — это
  перенос, не переписывание; допустимы только переименования от коллизий имён
  и снятие дублей импортов).
- Трогать 26 внезеркальных сьютов и обе группы идентичного покрытия с их
  участием — это решение N7.
- Трогать флейк-пару `verify_ledger_reconciliation` / `verify_harness_map_fixtures`.
- Менять генератор карты (`tests/build_impact_graph.py`) и движок профилей
  (`skills/_shared/itd_verification_profiles.py`).
- Любая правка `skills/`, `hooks/`, `agents/` — вне предмета юнита.

## Примечание о направлении слияний
Хранитель в каждой паре выбран по внешним ссылкам: имя, на которое ссылаются
контракты (`HARNESS_CONFORMANCE_CONTRACT`, `PRACTICAL_EFFECTIVENESS_CONTRACT`,
`QUALITY.json`, `gen_phase2_contracts.py`, snapshot-фикстуры), остаётся жить;
удаляется имя, на которое ссылаются только исторические записи (CHANGELOG,
ретро) — исторические упоминания не переписываются.
