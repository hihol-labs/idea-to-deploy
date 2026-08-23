# Scope Lock — LPD003-AMEND / амендмент G0 по adversarial-ревью

## Current Task

LPD003-AMEND (low, учётный): записать в репо четыре поправки adversarial-ревью
к обоснованию вердикта GATE G0 (вердикт устоял — APPROVE WITH CONDITIONS) и
вторую метрику GENG-C-EXP. Код не меняется.

## Allowed Change Areas

- `.itd/DECISIONS.md` — одна append-запись «2026-08-23 — Амендмент G0».
- `BACKLOG.md` — пункт GENG-C-EXP: поправка формулировки + вторая метрика.
- `.itd-memory/STATE.json` (ledger-close GENG-S05 -> verified, активация
  LPD003-AMEND), `.itd-memory/events.jsonl`, `.itd-memory/contracts/LPD003-AMEND.md`,
  `.itd/SCOPE_LOCK.md`.

## Forbidden Change Areas

- Любой код: `skills/`, `hooks/`, `tests/`, `scripts/`, `.itd/*.json`.
- LAUNCH_PLAN, CHANGELOG, ADR — не трогаются (следующий юнит LPD-003-1 правит
  их вместе с кодом).
