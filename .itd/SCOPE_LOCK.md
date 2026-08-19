# Scope Lock — R4 (LPD-002): мелкое трение инструментов маршрута

## Current Task

Пять независимых мелких трений, измеренных ретро 2026-08-18
(E4+E7+E8+E11 -> P5+P6+P7+P11). Четвёртый пункт плана
`.itd-memory/LPD-002_UNIT_PLAN.json` (approved владельцем 2026-08-18), riskTier
**low** (`checkerMode machine_only`, `checkerRequired false`,
`minimumIndependentReviewers 0`), WIP=1. Pre-PR claim противоположным вендором
обязателен как всегда.

## Корень (измерен на текущем коде, не предположен)

1. **(a)** `tests/verify_independent_review_efficacy.py:726` требовал
   `--expected-keyring-sha256-file`, а `host_keyring()` жёстко сверял путь с
   `.itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256`. Весь
   `.itd-memory/` gitignored (`.gitignore:11`), файл не tracked -> в
   изолированном machine-worktree оракул падал независимо от значения, и
   efficacy не входил ни в одну машинную квитанцию S11. Побочный эффект
   argparse: `--expected-keyring-sha256 <hex>` молча разбирался как аббревиатура
   файлового флага и падал с «pin path is not the host contract».
2. **(b)** `tests/run-independent-review-efficacy.py:394` объявлял
   `--max-transport-attempts` (int, default 1), а `:410` отвергал всё, кроме 1
   («retry bound is invalid»), хотя цикл умеет N. `:599`
   `args.checkpoint.unlink(missing_ok=True)` — успешный прогон стирал след
   пройденного корпуса.
3. **(c)** `skills/task/scripts/itd_unit_log.py:194-204` не знал про `riskTier`:
   поле дописывалось руками в STATE на S10, S11 и на всех R1-R3.
4. **(d)** Свежий чекер написал `"PASS"` вместо `"PASSED"` -> квитанция
   `UNVERIFIED`, ревью прогнано заново (E8). Канон
   (`ALLOWED_VERDICTS`, `skills/_shared/itd_verification_loop.py:40`) нигде не
   выдавался чекеру буквальным шаблоном: в `docs/templates/` файла не было.
5. **(e)** `itd_retro_scan.py:419` считал `unitsVerifiedNoActivation` = 1, и
   факт «Аномалия учёта» кричал в каждом ретро, не называя строку.

## Candidate composition (allowed zones)

- `tests/verify_independent_review_efficacy.py` — взаимоисключающая пара
  `--expected-keyring-sha256-file` / `--expected-keyring-sha256` (ровно одна
  обязательна), `parse_caller_pin` (те же 64 строчных hex), `resolve_keyring`
  -> `(keyring, "host-pin"|"caller-pin")`, поле `keyringAuthorization` в
  отчёте; `verify_runner_flags()` — проверки (b).
- `tests/run-independent-review-efficacy.py` — флаг `--max-transport-attempts`
  удалён, граница = константа `TRANSPORT_ATTEMPT_BOUND = 1`;
  `finalize_checkpoint(path)` переименовывает чекпоинт в `<path>.done` вместо
  удаления, имя маркера уходит в итоговый JSON.
- `skills/task/scripts/itd_unit_log.py` — `RISK_TIERS`, обязательный
  `--risk-tier` у `activate` (отказ ДО события и до записи STATE), запись
  `riskTier` в `STATE.currentUnit`; `skills/task/SKILL.md` — вызов Step 3.5.
- `docs/templates/CHECKER_PROMPT.md` — новый шаблон с буквальным блоком
  вердикта и отвергаемой формой рядом; ссылка из `docs/VERIFICATION_LOOP.md`.
- `skills/_shared/itd_unit_lifecycle.py` — `_explained()`,
  `unexplained_no_activation()`, счётчик `lifecyclesNoActivationUnexplained`;
  `skills/retro/scripts/itd_retro_scan.py` — поле
  `unitsVerifiedNoActivationUnexplained` и честная формулировка факта.
- Оракулы: `tests/verify_unit_log.py` (c), `tests/verify_verification_loop.py`
  (d), `tests/verify_ledger_reconciliation.py` (e; заодно все его вызовы
  `activate` объявляют тир, а чтение лога больше не роняет оракул трейсбеком).
- `.itd/VERIFICATION_CONTRACT.json` — команда `independent-review-efficacy`
  переведена на форму-значение (иначе efficacy по-прежнему не входит в
  квитанцию). `tests/run-all.sh` НЕ трогается: на хосте остаётся host-owned пин
  и fail-closed без него.
- `tests/verify_gate_registry_binding.py` — пин команды efficacy: обе формы
  принимаются, но ровно одна; форма-значение сверяется с sha256 tracked
  keyring'а (устаревший пин красил бы каждую машинную квитанцию).
- `tests/verify_independent_review_efficacy.py` — `load_module` компилирует
  прочитанные байты вместо `spec.loader.exec_module`: кэш байткода той же
  длины давал вердикт о СТАРОМ коде (измерено на мутации в этой сессии);
  гарантия закреплена `verify_source_loading()`.
- Документы: `.itd/DECISIONS.md` (запись R4), `.itd/GPG-004_A16_TRANSPORT.md`
  (флага больше нет — граница константой), `CHANGELOG.md`, `BACKLOG.md`.
- `.itd/ACCEPTANCE_CONTRACT.json` — критерии `LPD002-R4-*`, ротация
  `activeFollowup` `LPD002-R3` -> `LPD002-R4`;
  `.itd-memory/contracts/LPD002-R4.md`; `.itd-memory/LPD-002_UNIT_PLAN.json` —
  статус пункта R4 и `oracleAmendments`.
- С delivery-коммитом R4 едут отметки закрытия R3 в `STATE.json` и
  `LPD-002_UNIT_PLAN.json` (отдельный ledger-close коммит не проходит
  evidence-first продюсера — HANDOFF-S10 §17.11, решение владельца; тот же
  шаблон, что R1 -> R2 -> R3).
- Перечеканки на итоговом дереве отдельными коммитами: три подписанные
  efficacy-ноги (`benchmarks/independent-review-efficacy/results/*.json`,
  `u12-cross-vendor-wsl.json`) — их `runnerSha256` пинит правку (b); и
  live-model-benchmark (`skills/` меняется -> `methodology_tree_sha256`).

## Явно вне скоупа

- Расширение `--max-transport-attempts` до 1..3 — прямо отвергнуто
  `.itd/DECISIONS.md:214` и `:447`; выбран противоположный ход (флаг удалён).
- `checker --dry-run` (мини-валидатор вердикта из P7) — новая поверхность в
  `itd_verification_loop.py`, в критерий (d) не входит, остаётся в BACKLOG.
- Пересмотр самого механизма пинов (`runnerSha256`, `methodology_tree_sha256`)
  — класс «live-benchmark pin friction» в BACKLOG, отдельная работа.
- `tests/run-all.sh` и host-owned профиль запуска efficacy — не ослабляются.
- Пункты R5-R6 плана — каждый отдельной сессией, WIP=1.

## Принцип

Инструмент не обещает того, чего не делает: флаг, принимающий одно значение,
удаляется, а не расширяется; риск-тир объявляется тем же вызовом, который
открывает цикл; ожидаемый дайджест можно передать значением, но отчёт честно
называет, насколько сильна выбранная авторизация; объяснённая историческая
строка перестаёт считаться аномалией, оставаясь видимой.
