# ROUTE-DEBTS-ORACLE-1 — ledger closure (documentation only)

The unit itself is already published and verified: PR #300 merged as `8687e90`
(head `b862a96`), unit `ROUTE-DEBTS-ORACLE-1` verified by the goal harness on
2026-09-21 (`tests/verify_route_debts.py`, exit 0). The harness transitions in
`.itd-memory/` travelled with that PR. This candidate carries only the durable
record the publishing session owed. Review claim id:
`ROUTE-DEBTS-ORACLE-1:general-review`.

Criterion: the three decisions taken during publication and the four route
observations measured during it are written where the methodology keeps them -
`.itd/DECISIONS.md` and `BACKLOG.md` - and this scope lock describes the
closure rather than the previous unit.

## In scope

- `.itd/DECISIONS.md`: one appended entry (publication decisions, route cost).
- `BACKLOG.md`: one P1 entry with four observations.
- `.itd/SCOPE_LOCK.md`: this file.

## Required evidence

- `sh skills/_shared/itd_py.sh tests/meta_review.py` exits 0.
- `bash tests/run-all.sh --quick` ends with `DONE fails:none`.

## Declared limit

- The previous scope lock was never rewritten for `ROUTE-DEBTS-ORACLE-1`; the
  unit shipped under the `ROUTE-REPAIR-3` text, which named it out of scope.
  Recorded here, not repaired retroactively.

## Out of scope

Every production module and test; the gate registry; the completion gate; the
release unit `REL-1.105.0`.
