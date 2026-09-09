# HANDOFF — REL-1.104.0 (релиз 1.104.0 + нативная раскатка + installed-proof + ledger-close)

Дата: 2026-09-09. Ветка релиза: `chore/release-1.104.0` (от origin/main `22d6468`).
Юнит `REL-1.104.0` активирован в `GOAL.json` (high risk) и остаётся `in_progress`
до installed-proof. Предыдущий юнит `RSI-ROUTE-P1` закрыт (PR #274 `eb6d61c`,
ledger-close #275 `22d6468`).

Релиз обязателен как разблокировка: установленная review-authority сейчас -
до-фиксовый продюсер 1.103.1, поэтому смерженные исправления RSI-DEBT-1 (#272)
и RSI-ROUTE-P1 (#274) в реальном маршруте ещё не работают.

## План (WIP=1)
1. Релиз 1.104.0: бамп 10 мест (plugin.json x2, marketplace, docs-state, README x2,
   conformance, rc-contract, release-oracle VERSION, CHANGELOG) - СДЕЛАНО.
   Оракулы: `meta_review` PASSED; `run-all --quick` последняя строка
   `DONE fails: verify_reviewer_provider_freshness`; версия 10/10 мест.
   Ревью: machine receipt (unit `REL-1.104.0`, risk high) -> чекер свежей сессии ->
   adjudicate -> `itd_review_cache.py record` -> commit -> re-pin live-model
   ОТДЕЛЬНЫМ коммитом на чистом дереве -> `itd pr create` -> CI -> merge ->
   `gh release create v1.104.0 --target <ПОЛНЫЙ merge sha>`.
2. Раскатка: `bash scripts/sync-to-active.sh`;
   `CLAUDE_HOME=/mnt/c/Users/Дмитрий/.claude bash scripts/sync-to-active.sh`;
   WSL: `python3 -I scripts/itd_install_cli.py --apply --replace-existing` +
   `itd_install_git_hooks.py --apply --replace-existing`;
   Windows: то же из Windows-python через powershell, из Windows source-копии;
   Codex cache: `bash .itd-memory/refresh_codex_caches.sh all` (+ проверить
   `codex plugin list --marketplace personal --json` version 1.104.0).
   Старые content-addressed runtime-каталоги НЕ удалять - это rollback-артефакты.
3. Installed-proof `.itd-memory/host-inputs/REL-1.104.0/INSTALLED.json` (schema v2:
   version=2, release, runtimeSha256, hosts[Linux,Windows]); на каждом хосте
   machine receipt unit `REL-1.104.0:deployment-canary` risk low с командой
   `native=<sys.executable> -I -B tests/verify_route_debts.py --native-test-log <log>`,
   adjudicate, снапшоты в host-inputs, revalidationLog = вывод `--native-proof`,
   cliWrapper/prePushWrapper/adapters rows. Валидатор:
   `tests/verify_route_debts.py` (`validate_native_record` / `validate_native_canary` /
   `installed_proof`). Образец предыдущего цикла:
   `.itd-memory/host-inputs/ROUTE-DEBTS/INSTALLED.json`.
4. ОТК (одной строкой): `sh skills/_shared/itd_py.sh skills/goal/scripts/itd_goal_verify.py REL-1.104.0 --verification-receipt <adjudicated receipt>` - гоняет весь `verificationCommand`.
5. Ledger-close PR с новой ветки от main: строки acceptance-контракта
   `REL-1.104.0-1-version` и `REL-1.104.0-3-mirror` в `passed`, STATE/GOAL/events,
   DECISIONS/BACKLOG. Затем `/goal` -> следующий юнит `RSI-DEBT-2` (отдельная сессия).

## Порядок после этого юнита (решение владельца 2026-09-09)
`REL-1.104.0` -> `RSI-DEBT-2` -> `RSI-DEBT-3`, по одному юниту на сессию. Затем ОТДЕЛЬНЫМ
юнитом разделение учёта на две цели: внутреннее качество (закрывается сразу после этих трёх)
и внешняя валидация (остаётся открытой до реальных операторов). Пороги adoption переезжают
дословно, планка не меняется, старый леджер остаётся историей. Обоснование и отвергнутая
альтернатива - `.itd/DECISIONS.md`, запись 2026-09-09 «the goal ledger is split in two».
Юнит разделения НЕ заводится заранее: его критерий и оракул проектируются в его собственной
сессии, иначе в замороженный леджер попадёт наспех придуманная проверка.

## Ловушки маршрута, замеренные в этом цикле
- `bash tests/run-all.sh --quick` по построению выходит 1 (единственный допустимый
  красный - `verify_reviewer_provider_freshness`). Запускать ТОЛЬКО в форме критерия
  с `| tail -1 | grep -qx '...'; rc=$?; echo "EXIT: $rc"; test "$rc" -eq 0` (статус пайплайна
  сохраняется: завершающий `echo` сам по себе сделал бы составную команду успешной при
  упавшем grep): иначе completion-gate пишет
  красный runtime-сигнал, а вытеснить его можно лишь зелёным прогоном с тем же
  нормализованным ключом команды.
- `skills/task/scripts/itd_unit_log.py activate` пишет STATE и событие, но НЕ трогает
  `GOAL.json` (ни `currentUnitId`, ни статус юнита) - валидатор сразу ловит
  «WIP=1 violated». Для юнита цели активировать через
  `skills/goal/scripts/itd_goal_verify.py <unit> --activate`.
