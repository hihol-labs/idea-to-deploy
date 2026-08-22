# Task Contract — GENG-S03

## Scope
Reconciliation учёта (план GE 2 Final §2, строка S03): LAUNCH_PLAN.md (Block I
статус, строка о LPD-002/GENG), BACKLOG.md (статус-нота секции P1 GENG),
.itd/DECISIONS.md (append: решения владельца 2026-08-21/22 + результат S02),
.itd-memory/STATE.json (рукой — только nextAction; currentUnit/events меняет штатный писатель itd_unit_log.py при activate/verified GENG-S03). Плюс леджер юнита
(ACCEPTANCE не трогается — критериев юнит не добавляет), CHANGELOG [Unreleased].

## Verification Standards
- tests: verify_ledger_reconciliation, verify_state_hardening,
  verify_feature_ledger{,_completeness}, verify_goal_tools, verify_unit_log —
  все зелёные;
- diff содержит ТОЛЬКО учёт: ни одной строки в hooks/, skills/ (кроме нуля),
  tests/, scripts/;
- Verification Loop machine receipt по exact candidate, adjudicate low.

## Exclusions
Переписывание секции GENG BACKLOG (S06, после ADR-010); любые правки кода/
гейтов; GOAL.json (расхождений нет); активация GENG-пула юнитов (S07).
