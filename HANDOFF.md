# HANDOFF — S7: четыре долга адъюдикаций GPG-004 (2026-08-13)

## Состояние
- Ветка: `fix/s7-transport-sync-debts` (от main 6aa1d34, S6 закрыт).
- Скоуп S7 approved пользователем: 4 юнита, все с тестами; декомпозиция ниже.
- «sync-manifest __pycache__» подтверждён как ОБА sync-долга (манифест + bytecode-шум).

## Юниты (WIP=1, по порядку)
1. **S7-U1-NANINF** — СДЕЛАН, receipt в процессе. `math.isfinite(timeout)` в
   валидации `run_bounded_process` (skills/_shared/itd_free_reviewer_producer.py,
   +`import math`); тесты в tests/verify_free_reviewer_producer.py (блок «S7-U1»
   в начале main(): nan/inf/-inf → ValueError, позитив 30.0). Таргетный оракул
   зелёный: `PASSED, checks: 148`. Активирован через itd_unit_log (goal в
   STATE.json). Осталось: machine receipt (staged: producer+tests, БЕЗ
   STATE.json) → adjudicate (risk medium: machine + targeted fresh checker) →
   `check` → `itd_unit_log verified` с путём/дайджестом receipt.
2. **S7-U2-RELCWD** (standard) — Windows-wrapper: план пишет `"cwd": str(cwd)`
   (строка ~406), wrapper стартует из temp `wrapper_directory` → относительный
   cwd резолвится не от caller'а. Фикс: абсолютизировать при сборке плана
   (`str(Path(cwd).resolve())`-семантика, POSIX-тестируемо по содержимому плана).
3. **S7-U3-POSIXREAP** (HIGH) — потомок с повторным setsid() сбегает от killpg
   (`_close_process_tree`); фикс: PPID-walk reap по /proc после killpg
   (cgroup — отвергнут как избыточный). Тесты реально демонизируются
   (grandchild setsid, pid-файл, проверить kill). High → полный fresh-session
   checker другой модели.
4. **S7-U4-SYNC** (standard) — scripts/sync-to-active.sh: (a) синкать
   `.claude-plugin/plugin.json` → `~/.claude/.claude-plugin/plugin.json` +
   verify-sync поверхность (сейчас только existence-check, строка ~91);
   (b) исключить `__pycache__`/`*.pyc` из drift-скана (строки ~133-141, 197,
   250, 279-297). Тестов на скрипт нет — fixture dry-run `--check` с временным
   HOME.

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
