# LEDGER-ARCHIVE-1 — ledger closure (documentation only)

The unit itself is already published and verified: PR #297 merged as `915c5b4`
(tree `b437dd24`), unit `LEDGER-ARCHIVE-1` verified by the goal harness on
2026-09-21 (`tests/verify_ledger_reconciliation.py`, 96 passed, 0 failed).
This candidate carries only the durable record the publishing session owed and
could not write from inside its own candidate tree. Review claim id:
`LEDGER-ARCHIVE-1:general-review`.

Criterion: the three decisions taken during publication and the seven route
observations measured during it are written where the methodology keeps them -
`.itd/DECISIONS.md` and `BACKLOG.md` - and this scope lock describes the
documentation candidate, not the unit.

## In scope

- `.itd/DECISIONS.md`: three appended entries, all dated 2026-09-21 - the
  commit-gate receipt built without the live-benchmark pin suite (option 1);
  the two audited `COMPLETION_BYPASS` uses and why the L2 veto was false; the
  owner route used to publish #297 and the price paid for it (no signed
  producer receipt on the published tree).
- `BACKLOG.md`: one new P1 section with seven route observations (а)-(ж), each
  with the site or the measurement it came from. Items (а) and (в) name how
  they would be nailed down; the others are recorded, not scheduled.
- `.itd/SCOPE_LOCK.md`: this file, rewritten from the unit scope to the
  documentation candidate.

## Required evidence

- `bash tests/run-all.sh --quick` ends with `DONE fails:none`.
- No file outside the three paths above is touched (`git diff --stat`).

## Declared limit

- No production code, test, oracle or fixture changes here, so no RED-first
  regression and no mutation evidence exists for this candidate by design.
- The facts recorded come from the publishing session (PR #297, its machine
  receipts under `.itd-memory/verification-loop/LEDGER-ARCHIVE-1/`, and
  `.itd-memory/HANDOFF-LEDGER-ARCHIVE-1.md`). Those artefacts are gitignored
  or already merged; they are not reproducible from this diff.

## Out of scope

Fixing any of the seven observations (а)-(ж); `tests/verify_route_metric.py`
(unit `ROUTE-REPAIR-3`, activated after this PR); `tests/verify_route_debts.py`
(unit `ROUTE-DEBTS-ORACLE-1`); the release unit `REL-1.105.0`;
`.itd-memory/STATE.json` `nextAction`, which observation (ж) records and the
harness rewrites on the next activation.
