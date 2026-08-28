# SCOPE_LOCK — REL1101 (открыт 2026-08-28)

## Предмет
N9, последний пункт плана `.itd-memory/PLAN-REMAINING-2026-08-23.md` (блок 3).
Релиз накопленного между `v1.100.1` и `d296f82` — PR #226-#244 — по
`docs/RELEASE_RUNBOOK.md`, ровно три предмета:

1. **Релиз v1.101.0.** Номер выбран владельцем 2026-08-28 по semver: MINOR,
   потому что цикл добавил обратно-совместимые входы (`run-all.sh --targeted`,
   `--fail-fast`, advisory-правило остановки) и не удалил ни одной поверхности,
   существовавшей в `v1.100.1` (флаги `--graph`/`--root`/`--rules` принадлежат
   `scripts/itd_regression_select.py`, которого в `v1.100.1` не было —
   проверено `git cat-file -e v1.100.1:scripts/itd_regression_select.py`).
2. **Rollout WSL + native Windows** с hash-проверкой (как v1.98.0/v1.99.0).
3. **`/retro` по сессии 2026-08-23** — долг из плана; факты из харнеса,
   предложения evidence-gated, мерж — человек.

## Разрешённые области
- Девять live-пинов версии: `.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`,
  бейджи `README.md` и `README.ru.md`, `docs/HARNESS_DOCS_STATE.json`
  (`pluginVersion`), заголовок `docs/HARNESS_CONFORMANCE_REPORT.md`,
  `docs/api-reviewer/RELEASE_CANDIDATE_CONTRACT.json`, `VERSION` в
  `tests/verify_external_reviewer_release.py`.
- `CHANGELOG.md`: `[Unreleased]` -> `[1.101.0] - 2026-08-28` плюс записи по
  ещё не описанным PR цикла (#234, #235, #237, #239, #240, #241, #243).
- Улика live-бенчмарка: перечеканка **строго на чистом коммитнутом дереве**
  (`benchmarks/`, записи прогонов) — отдельным коммитом после бампа.
- Леджерная бухгалтерия юнита: `.itd-memory/STATE.json`,
  `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md`,
  `.itd-memory/PLAN-REMAINING-2026-08-23.md` (отметка закрытия плана).
- Артефакты `/retro` в его штатных путях (отчёт-факты + предложения).

## Явно вне скоупа
- Любая правка поведения скиллов/хуков/гейтов: релиз не вносит логики, он
  публикует уже смерженное и отревьюенное.
- «Починка» `verify_operating_loops_release` бампом версии: по N7 это
  candidate-bound оракул, зелёный только на своём пиненном кандидате; он
  остаётся вне зеркала с записью в `tests/OUT_OF_MIRROR.json`. Подгон его под
  новый номер версии — ложный ремонт и запрещён.
- Открытие следующих юнитов (SURFACE_TREADMILL, BACKLOG P1, PE5-008/009):
  только отдельным решением владельца после закрытия N9.
- Правка `tests/verify_itd_runtime_install.py` (там `1.100.0` — синтетическая
  фикстура, не live-пин) и исторических упоминаний версии в
  `.itd/ACCEPTANCE_CONTRACT.json`.

## Правило остановки
Два BLOCKED подряд на любой ревью-серии кандидата — стоп и решение владельца
(подтверждено владельцем в первом сообщении сессии). Для чисто бухгалтерских
record-кандидатов действует standing-решение N6 (owner-маршрут публикации с
честной записью); релизный кандидат идёт полным маршрутом.

## Предыдущий скоуп
N8 (GENG-C-EXP) закрыт: PR #243 (`9d49c78`) + ledger-close #244 (`d296f82`).
