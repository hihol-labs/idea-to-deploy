# HANDOFF — S5 / U17: design-provenance reviewer — ЗАКРЫТ; план GPG-004 ЗАКРЫТ (2026-08-13)

**U17 закрыт целиком**: [PR #199] merged как `5b9537f` (base `ef15e97`), CI
green. Fresh post-merge на merged main: sealed verificationCommand
`python3 tests/verify_blueprint_provenance_reviewer.py` exit 0
(`ALL CHECKS COMPLETED`) и quick `DONE fails:none`. STATE/events/acceptance →
verified (ledger-close). **GPG-004 план закрыт: 17/17 юнитов verified**
(леджер `GPG-004_UNIT_PLAN.json` → status `done`).

## Что вошло (запись выполненного)

1. **Фича** (`56325d0`): opt-in advisory sub-step 2.5b «Design Provenance
   Review» в /blueprint поверх Devil's Advocate (opt-in: запрос пользователя
   или `ITD_DESIGN_PROVENANCE=1`); `DESIGN_PROVENANCE.md` — `## Claim:` +
   `- Source: user-requirement|measured-evidence|external-doc|
   model-assumption` + `- Reference:`; stdlib-валидатор
   `skills/blueprint/scripts/itd_design_provenance.py`. Инварианты
   `cannotWeaken` доказаны верифаером (RED-first rc=2 → green):
   advisory никогда не блокирует (exit 0 на находках/чистом/отсутствующем/
   битом отчёте; quiet no-op без аргументов; read-only), никакого
   acceptance-evidence (нет verdict-поля, acceptance-токен не эмитится),
   gate-outcome неизменен (свип: ни один хук/гейт не ссылается на ревьюер).
2. **Live re-pin** (`b655943`): правка skills/blueprint/SKILL.md жжёт
   methodology-tree пин по построению → двухкоммитный acceptance (прецедент
   PR #193/#195): re-record на чистом committed-дереве, ран
   `20260813T134904Z-c56e465c`, `--require-evidence` 107/0. Коммит 1 шёл с
   COMPLETION_BYPASS ровно на этот задокументированный inherent-красный.
3. **CI-фикс** (`a01380e`): `verify_snapshot --all` требует
   `expected-snapshot.json` в каждой папке tests/fixtures/ — добавлен
   pending-container стаб (конвенция live-model-evidence).
4. **Маршрут** (low tier, sealed): machine receipt + adjudication без
   checker — `c589dd3c86d21c14/a1` (staged) и `d5868d05163a63d2/a1`
   (committed-head, для PR-гейта). Профиль local-submission/local-review
   перерегистрировался на каждую новую голову.

## Дальше (за пределами GPG-004)

По PLAN-CLOSEOUT: S6 (точность скраббера; правка жжёт efficacy-ноги →
перечеканка), S7 (долги адъюдикаций), S8 (пин дерева + A19), S9 (harness-
фиксы: doctor label, completion-ledger schema, no-op-push дефект pre-push
хука — воспроизведён в S4 и S5), S10 (дрейф леджера). После S10 —
стратегические треки (GENG-000…010 через /goal по ADR-009).
