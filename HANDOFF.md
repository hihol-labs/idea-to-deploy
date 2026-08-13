# HANDOFF — S7: четыре долга адъюдикаций GPG-004 (2026-08-13)

## Состояние
- Ветка: `fix/s7-transport-sync-debts` (от main 6aa1d34, S6 закрыт).
- Скоуп S7 approved пользователем: 4 юнита, все с тестами; декомпозиция ниже.
- «sync-manifest __pycache__» подтверждён как ОБА sync-долга (манифест + bytecode-шум).

## Юниты (WIP=1) — 4/4 кода готово
1. **S7-U1-NANINF** — DONE, коммит 219f6c8. `math.isfinite(timeout)` в
   валидации `run_bounded_process`; тесты nan/inf/-inf + позитив.
2. **S7-U2-RELCWD** — DONE, коммит 64f68a2. Helper `wrapper_plan_cwd`
   (abspath, не resolve) анкерит относительный cwd на caller'е до temp-хопа.
3. **S7-U3-POSIXREAP** (high) — DONE, коммит 298dc24. Pre-kill PPID-walk
   снапшот `/proc` в `_close_process_tree` + SIGKILL сбежавших; тест реально
   демонизирует setsid-грандчайлда. Residual (double-fork orphan, /proc-only,
   PID-reuse) задекларирован в docstring и BACKLOG.
4. **S7-U4-SYNC** — код готов, unit verified (receipt f370b6f5), НЕ закоммичен:
   ждёт general-review клейма. sync-to-active.sh синкает
   `.claude-plugin/plugin.json` (add + drift, dry-run aware) и исключает
   `__pycache__`/`*.pyc` из drift-скана; verify-sync-to-active.sh полицит
   манифест; новый оракул tests/verify_sync_manifest.py (9 checks: dry-run,
   apply-mode install, re-run unchanged, bytecode-not-drift) в run-all CORE;
   BACKLOG: три пункта закрыты.

## Ключевые решения (уже в .itd/DECISIONS.md, последняя запись)
- Efficacy-леги ре-минтятся ОДИН раз на финальном S7-дереве перед PR;
  per-unit регрессия = run-all зелёный за вычетом одного tree-bound
  `verify_independent_review_efficacy` («producerSha256 foreign» — ожидаемо
  при любой правке producer'а). Гейт PR остаётся полным.
- Прогон bfivnldkv: run-all на U1-дереве — единственный FAIL именно этот.

## Ловушки (из session-файла S6, не переоткрывать)
- `itd pr create` делает draft-PR; coverage-матрица требует machine receipt;
  снапшот producer'а держать вне репо; committed-head валидация — через
  staged-дифф; completion-signals hook мисклассифицирует (его FIX-подсказки —
  шум, корневую причину искать самому); riskTier у `itd_unit_log activate`
  флага НЕТ — activate пишет только id/goal/status/startedAt, а review-cache
  читает СТРУКТУРНОЕ поле STATE.currentUnit.riskTier (иначе context
  riskTier=unknown и гейт красный): после activate добавь поле руками
  json-round-trip'ом, значение из enum high/low/medium/unknown («standard»
  НЕ значение — маппится в medium). Прецедент: S6 high, U17 low. Укус №3.
- review-гейт биндит exact staged diff: любой новый staged файл (включая
  claude-review-*.md отчёт — он НЕ в .gitignore) инвалидирует record;
  порядок: финализируй staged-набор → mint receipts → record → commit без
  промежуточных git add.
- Прямой запуск verify_independent_review_efficacy требует
  `--expected-keyring-sha256-file` (run-all подставляет сам; host-owned pin).

## Финиш-чеклист S7 (после U4)
ре-минт 3 efficacy-ног (wsl, windows, u12-cross-vendor — Windows-нога с
Windows-хоста!) → полный run-all зелёный → /review + adjudication → PR
(draft) → BACKLOG: снять 4 закрытых пункта → ledger-close → /session-save --close.
