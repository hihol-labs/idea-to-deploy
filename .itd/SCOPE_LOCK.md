# LEDGER-ARCHIVE-1

Active unit of the goal ledger `.itd-memory/GOAL.json`, low risk, verified by
the goal harness on 2026-09-20 (`tests/verify_ledger_reconciliation.py`,
91 passed, 0 failed) and re-verified by it on 2026-09-21 at 96 passed, 0 failed,
after the oracle was extended for three reviewer findings (no production
change between the two runs). This candidate publishes it. Review claim id:
`LEDGER-ARCHIVE-1:general-review`.

Criterion: `itd_unit_lifecycle.attribute` does not trust an explicit event
`ledger` label that names a ledger which does not own the unit. When exactly
one ledger in the memory directory owns the unit id the event is attributed to
that owner; otherwise it is counted as unattributed. A label naming an owning
ledger, and the `STATE` pseudo-ledger, keep their current behaviour.

## In scope

- `skills/_shared/itd_unit_lifecycle.py`: `attribute()` only. Owners are
  computed before the label is read, with a guard on a non-string ledger name.
  New reasons: `explicit-stale-sole-owner`, `explicit-not-owner`. The date
  window is not applied to a false label.
- `tests/verify_ledger_reconciliation.py`: new RED-first section A2 (6 checks
  red before the fix), plus two repairs of checks that were red on `main`
  since 2026-09-03 and kept the unit's own verification command from exiting
  0: the "event before STATE" order check now cuts the whole branch up to the
  next anchor instead of the first `return 0`; the live "blocked >= 1" check
  is replaced by the invariant "no lifecycle lies under a ledger that does
  not own its unit", with manifest pairs excluded. Oracle 80/3 -> 91/0,
  then 96/0 with the reviewer-round additions (reason asserted, non-string
  label, closed `backfill` segment).
- `CHANGELOG.md`: one `[Unreleased]` entry that discloses the scope extension.
- `BACKLOG.md`: the 2026-09-03 red-oracle debt marked closed; one new P2 entry
  (reconciliation manifest is not consulted for `explicit-not-owner`).
- `.itd/DECISIONS.md`: one appended entry - the goal is extended to 4 units
  (`ROUTE-DEBTS-ORACLE-1` before `REL-1.105.0`), approved by the owner.
- `.itd-memory/GOAL.json`, `.itd-memory/STATE.json`, `.itd-memory/events.jsonl`:
  harness-written bookkeeping - unit activated and verified, two appended
  units, two harness events.
- `tests/fixtures/live-model-evidence/**`: the live-model benchmark evidence
  re-recorded on this tree (run `20260920T204351Z-15e8fcfa`). The fix touches
  `skills/_shared/itd_unit_lifecycle.py`, which is inside the content-pinned
  methodology surface, so the committed evidence must be re-pinned or Gate 1
  fails. Evidence only; no benchmark code or oracle is changed.
- `.itd/SCOPE_LOCK.md`: this file.

## Required evidence

- `sh skills/_shared/itd_py.sh tests/verify_ledger_reconciliation.py` exits 0.
- The quick mirror `bash tests/run-all.sh --quick` ends with `DONE fails:none`.
- Unit statuses in `GOAL.json` were written by the harness (`actor: harness`
  events), not by hand.

## Declared limit

- Mutation kills (8) and the live-directory measurement (13 PE5-era
  lifecycles re-attributed to `GOAL-2026-09-20.json`; `lifecyclesVerified` 18,
  `unattributedEvents` 0, `vcr` 1.0 unchanged) were run by the maker on the
  gitignored live memory directory and are not reproducible from the diff.
- Callers of `attribute()` in `itd_metrics` / `itd_retro_scan` were not
  re-read line by line; they are covered by `tests/verify_retro_scan.py` and
  the unit-log oracle in the quick mirror.
- The owner's approval of the 4-unit goal was given in the session and is
  recorded in `.itd/DECISIONS.md`, not provable from the diff.

## Out of scope

`tests/verify_route_debts.py` (red on `main`, unit `ROUTE-DEBTS-ORACLE-1`);
`tests/verify_route_metric.py` (unit `ROUTE-REPAIR-3`, not activated); using
the reconciliation manifest for `explicit-not-owner` rows (BACKLOG P2); the
release unit `REL-1.105.0`; any production change outside `attribute()`.
