# HANDOFF — S4 / U12: замер лестницы независимости — ВЫПОЛНЕНО (2026-08-13)

**Ветка:** `chore/s4-u12-ladder-measurement` от main @ 18dc762. **Юнит:** U12
(GPG-004; S4 в `.itd-memory/PLAN-CLOSEOUT-2026-08-11.md`) — работы этой
сессии завершены; остаток — PR/merge по команде пользователя и ledger-close.

## Что сделано (этой сессией, проверено)

1. **Диагноз:** `verify_independent_review_efficacy` был красным на main
   18dc762 — «wsl semantic result binding is foreign»: PR #191 (`da42644`,
   2026-08-11) изменил байты `skills/_shared/itd_free_reviewer_producer.py`
   после чеканки 2026-08-10 → `producerSha256` всех трёх подписанных ног стал
   чужим (manifest/runner sha совпадали).
2. **Перечеканка трёх ног живыми прогонами** (текущие байты продюсера):
   - WSL same-vendor (maker `gpt-5.6-terra` → reviewer `gpt-5.6-sol`, codex
     0.146.0 пин `2e863156…`): 9/9 кейсов, `attempts=1`, PASSED;
   - U12 cross-vendor (maker `opus`, anthropic-subscription → `gpt-5.6-sol`):
     9/9, `attempts=1`, PASSED;
   - Windows same-vendor (нативный `python.exe` 3.12.10 по UNC-пути репо,
     codex.exe пин `bc343ba4…`, DPAPI-ключ): кейс 1 записан, один typed
     UNAVAILABLE обрыв транспорта на кейсе 2, возобновление с подписанного
     чекпоинта (прецедент typed-exit-3 ретраев 2026-08-08) — итого 9/9,
     `attempts=1`, PASSED.
3. **Верифаер зелёный**: exit 0, `status PASSED`, `hostParityVerified true`.
   **Замер лестницы** (`u12IndependenceLadder`, общий замороженный корпус):
   sameVendor criticalHigh 1.0 / medium 1.0 / cleanFalseBlock 0.0 ==
   crossVendor 1.0 / 1.0 / 0.0 — **паритет, не превосходство**; порядок
   лестницы остаётся cross-vendor-first по correlated-blind-spots аргументу.
   Итог записан в аддендуме ADR-007 и в подписанных результатах бенчмарка.
4. **Кейсы кардинальности подтверждены возвращёнными и зелёными**:
   `structural/low-reviewer`, `structural/high-quorum`,
   `structural/duplicate-reviewer-quorum` (точный exact-equality контракт
   `minimumIndependentReviewers`, восстановление PC4) — кодовых правок не
   потребовалось.
5. `bash tests/run-all.sh --quick` → `DONE fails:none` на дереве кандидата.
6. Контракты юнита: `.itd/SCOPE_LOCK.md` переписан под U12;
   `.itd/ACCEPTANCE_CONTRACT.json` — activeFollowup `U12:general-review`
   (medium), evidence PC4/PC5 дополнены перечеканкой, добавлены криты
   `U12:general-review-1/2` (точечный дифф, остальные записи byte-for-byte).
   `.itd-memory/STATE.json` — currentUnit U12. Локальные (git-ignored)
   леджеры: `GPG-004_UNIT_PLAN.json` U12 → verified c evidence,
   `PLAN-CLOSEOUT-2026-08-11.md` S4 → ✅ DONE.

## Остаток (для принимающего)

1. Producer-маршрут U12:general-review довести до PASS (раунды c2/c5/c6 —
   реальные находки контрактной бухгалтерии, все закрыты правками кандидата;
   typed UNAVAILABLE ретраится), затем checker → adjudication → commit → PR
   через `itd pr create` (профиль local-submission/local-review).
2. Мерж PR — только по команде пользователя; после мержа — ledger-close S4
   (прецедент S2/S3) и `/session-save`.

## Пины (если понадобится перегон)

codex WSL: `/home/hihol/.npm-global/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex`
sha `2e863156ed35ecc5253b1e2f907a9143077b9f7cb51942070c61996471ff6e04`;
codex.exe Windows: `$env:APPDATA\npm\node_modules\@openai\codex\node_modules\@openai\codex-win32-x64\vendor\x86_64-pc-windows-msvc\bin\codex.exe`
sha `bc343ba420dc2e2e9f59e6fc5e5bf0aae1cd8c771fc319665241fc9c0271fddb`;
proxy-sentinel `01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`;
ключи подписи ног: `.itd-memory/verification-loop/keys/gpg003-local-producer-20260803{.key,.windows.key}`;
байты producer/runner/cases после чеканки НЕ менять — иначе перегон.
