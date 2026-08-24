# Scope Lock — LPD003-1 / run-all перестаёт быть входом по умолчанию

## Current Task

LPD003-1 (medium): три измеренных дефекта машинного слоя (замер GATE G0):

- D1 false-red: host-owned вход недостижим в изолированном дереве продюсера
  (`.itd-memory/` git-ignored) -> печаталось как FAIL сьюта (34 прогона).
- D2: красный прогон доигрывается до конца (128 из 859 минут).
- D3: полный прогон — вход по умолчанию для любой правки (82% машинного слоя);
  targeted-профиля по `.itd/IMPACT_GRAPH.json` не было.

## Allowed Change Areas

- `tests/run-all.sh` — парсер флагов, класс BLOCKED, `--fail-fast`,
  `--targeted`, строка MIRROR-COVERAGE.
- `scripts/itd_regression_select.py` (новый) — селектор по карте. Периметр сужен
  решением владельца 2026-08-24 (`.itd/DECISIONS.md`): публичных входов,
  называющих читаемый файл, нет — удаление `--graph` входит в этот скоуп, а
  не является его расширением.
- `.itd/IMPACT_PATTERNS.json` (новый) — правила для путей, которые нельзя
  перечислить узлами.
- `tests/verify_targeted_regression.py` (новый) — оракул с мутациями.
- `.itd/IMPACT_GRAPH.json` — регенерация генератором (не ручная правка).
- Документация/леджер: `docs/CI.md`, `docs/WORKING_DEADLINE_MODE.md`,
  `BACKLOG.md`, `CHANGELOG.md`, `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md`,
  `.itd/ACCEPTANCE_CONTRACT.json`, `.itd-memory/{STATE.json,contracts/LPD003-1.md}`.
  Контракт приёмки внесён в список 2026-08-24: у юнита не было НИ ОДНОГО
  критерия `LPD003-1-*`, а `activeFollowup` указывал на закрытый юнит
  `PRG-004` (`riskTier: high`) — тринадцать заходов продюсера шли по чужой
  политике ревью. Это бухгалтерия юнита, а не расширение его предмета.

## Forbidden Change Areas

- Поведение существующих сьютов и гейтов (`skills/`, `hooks/`) — targeted не
  ослабляет ни один гейт: приёмка остаётся за Verification Loop, PR/релиз
  идут полным прогоном.
- Ремонт сьютов вне зеркала (`verify_operating_loops_release` и др.) — они
  зафиксированы в BACKLOG как отдельный юнит.
- LPD-003-2/3/4 (корни live-улики, правила остановки, консолидация сьютов).
