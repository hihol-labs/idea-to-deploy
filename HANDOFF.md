# HANDOFF — S6-SCRUBBER: residual-credential detector precision — ЗАКРЫТ (2026-08-13)

**S6 закрыт целиком**: [PR #201] merged как `300fcab` (base `84742fb`), CI
green (Gate 1 + windows-verify). Post-merge fresh evidence на merged main:
verify_scrubber_precision 30 PASSED, verify_review_broker 741,
verify_free_reviewer_producer 144, verify_independent_review_efficacy PASSED
(hostParityVerified true), quick `DONE fails:none`. Юнит `S6-SCRUBBER` →
verified в STATE (evidence полный, adjudication receipts
c231e0239981f339/a1 и 95bbe377e5b8daea/a1).

## Что вошло

1. **Детектор** (`afe8748`): value-capture в `RESIDUAL_CREDENTIAL_RE`;
   значение, целиком являющееся одним код-выражением, — не литеральный
   секрет. Грамматика узкая после двух реальных находок маршрута: кавычные
   значения — только `$`-интерполяции (r5); `${…}` — имя+опциональный
   подскрипт, `$(…)` — голое имя команды, аргументы/индексы — без `#` и
   пробелов (r6, wrapper-smuggling). Каждый пропуск — с TP-антипарой:
   RED-first `tests/verify_scrubber_precision.py`, 30 checks, CORE.
2. **Producer**: детекторы по SCRUBBED-тексту (паритет с broker/
   build_candidate, контракт «redaction is not a finding»); ненейтрализуемый
   зазор (`#` в bare-значении) — fail-closed. producer-сьют перепинен (144).
3. **Три efficacy-ноги** перечеканены живьём на финальных байтах: wsl 9/9,
   u12 cross-vendor 9/9 (maker claude-fable-5), windows 9/9 (powershell-
   interop); ретраев не было (A21).
4. **Live re-record** (`fb71ba0`): ран 20260813T164516Z-916e7a92,
   `--require-evidence` 107/0; конвенции evidence-корпуса вписаны в
   SCOPE_LOCK (transparent .jsonl.gz textconv, fixture-03 = nginx-CLI
   бенчмарк, известная tail-truncation рекордера).

## Уроки маршрута (для retro)

- Тесты/доки про детектор обязаны сами проходить детектор: runtime-сборка
  строк; scrub-редакция калечит кавычки в диффе → ревьюер видит «битый»
  Python (r5-blocker класс).
- Ревьюеру нужны конвенции корпуса в scope-lock — иначе 3 FP-находки об
  evidence-файлах (gzip/textconv, содержимое бенчмарк-транскрипта,
  tail-truncation).
- `itd_unit_log activate` не пишет riskTier в STATE.currentUnit → cache-
  контекст unknown, record fail-closed отказывает; дописывать при активации
  (known follow-up).
- verify_review_broker: один транзиентный ранний крах в изолированном
  чекауте (5с, пустой stdout, S2-класс) — зелёный на повторе; follow-up.
- itd pr create дотолкал push через гейт, но упал на PR-lookup из-за
  персистентного TLS-флейка к api.github.com → PR создан gh-фоллбэком
  (прецедент S2), реестр перерегистрирован register-profile'ом заранее.

## Очередь (next)

BACKLOG follow-ups: benchmark provenance polish, sync-manifest gap,
bounded-process transport hardening, ledger drift, matcher category wording,
S9 stale-head pre-push, riskTier в itd_unit_log activate. GENG-000 стартует
через /goal (план ADR-009, memory geng_program_plan + правки
project_geng_plan_amendments).
