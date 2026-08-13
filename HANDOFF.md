# HANDOFF — S6-SCRUBBER: residual-credential detector precision (in progress, 2026-08-13)

Активный юнит: `S6-SCRUBBER` (STATE.currentUnit, riskTier high, WIP=1).
База кандидата: main `84742fb`. Ветка: `fix/s6-scrubber-precision`.
Контракт юнита: `.itd-memory/contracts/S6-SCRUBBER.md`; рабочий чеклист:
`.itd-memory/HANDOFF-S6-SCRUBBER.md`; scope: `.itd/SCOPE_LOCK.md`.

## Суть изменения

1. **Детектор** (`skills/_shared/itd_external_reviewer.py`):
   `RESIDUAL_CREDENTIAL_RE` получил value-capture (`quoted`/`bare`/
   `continued`); `contains_residual_credential` пропускает значение, которое
   ЦЕЛИКОМ является одним код-выражением (`_BENIGN_EXPRESSION_RE`: dotted
   call, subscript, `${…}`/`$(…)`/`$var`; хвостовые backtick'и прозы
   срезаются). Инцидентные FP-классы U16 — token-именованная переменная,
   присвоенная из `tokens[position]`, и проза, цитирующая такую строку, —
   больше не рубят маршрут. Смешанное
   значение остаётся flagged (fail-closed). Сознательно НЕ через
   SAFE_REFERENCE_PATTERNS.
2. **Producer** (`skills/_shared/itd_free_reviewer_producer.py`):
   `_safe_review_text` гоняет три детектора по SCRUBBED-тексту — как broker
   и `build_candidate`; нейтрализованный секрет уезжает ревьюеру уже
   редактированным, ненейтрализуемая форма (password-присваивание с bare
   значением `abcd#efgh2026` — scrub рвётся на `#`, детектор нет)
   по-прежнему отказывает.
3. **Тесты**: новый RED-first `tests/verify_scrubber_precision.py`
   (30 checks после находок r5/r6 маршрута — кавычные call-lookalike и
   expression-wrapper TP добавлены; каждый benign-пропуск с TP-антипарой;
   зарегистрирован в
   CORE); `tests/verify_free_reviewer_producer.py` перепинен на новый
   контракт (144 checks).

## Статус верификации (последние прогоны этой сессии)

- `verify_scrubber_precision` 23/23; `verify_free_reviewer_producer` 144;
  `verify_review_broker` 741; `verify_api_reviewer` 80; broker-primitives
  160; curl-transport 14; external-reviewer-release PASSED.
- quick-сьют: единственный красный — `verify_independent_review_efficacy`
  (сожжённый `producerSha256`-пин: правка producer жжёт все три подписанные
  ноги по построению).
- **Все три ноги перечеканены** (ретраев не потребовалось; политика A21
  соблюдена): wsl 9/9 attempts=1 (observedAt 2026-08-13T15:09:04Z);
  u12-cross-vendor 9/9 attempts=1 (15:14:29Z, maker
  `claude-fable-5`/anthropic-subscription → reviewer gpt-5.6-sol); windows
  9/9 через powershell-interop (драйвер scratchpad/win-leg-s6.ps1, UNC-репо,
  нативный python.exe 3.12, codex.exe пин `bc343ba4…`, DPAPI-ключ
  `.windows.key`). `verify_independent_review_efficacy` с host-pin: PASSED,
  hostParityVerified true, criticalHigh/medium 1.0, cleanFalseBlock 0.0 на
  обоих хостах.
- **Маршрут ревью пройден**: 9 producer-раундов (r1-r4 — бухгалтерия
  маршрута: self-hosting guard → снапшот a10; проза с формой присваивания;
  unitId и критерии юнита в контракте; r5/r6 — реальные находки детектора,
  закрыты RED-first; r7/r9 — консистентность документов; r8 — чистый PASS
  findings 0). Checker + adjudication receipt
  `receipts/<candidate>/S6-SCRUBBER-general-review-adjudication-a*.json`,
  review-cache record PASSED.

## Остаток маршрута

1. Коммит 1 (при вето completion-гейта на live-benchmark пине —
   `COMPLETION_BYPASS` ровно на этот документированный inherent-красный) →
   live re-record на чистом committed-дереве (`--require-evidence`) →
   коммит 2.
2. PR (`itd pr create`; при no-op-push дефекте pre-push хука — обход через
   `gh pr create`, прецедент S2) → CI → мерж ТОЛЬКО по команде владельца →
   ledger-close (`itd_unit_log verified` после фактического exit 0).

## Ключи и пины (проверены этой сессией)

- Подпись ног: `.itd-memory/verification-loop/keys/
  gpg003-local-producer-20260803{.key,.windows.key}` (Ed25519; .windows —
  DPAPI-блоб, раннер принимает его напрямую на Windows).
- codex WSL `2e863156…` (~/.npm-global/…/@openai/codex/node_modules/
  @openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex);
  codex.exe `bc343ba4…`; proxy `01ba4719…` (sha256 пустой строки).
- Keyring host-pin: `.itd-memory/host-inputs/
  GPG-003_REVIEW_EFFICACY_KEYRING.sha256`.
