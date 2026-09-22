# REL-1.105.0 - ledger closure

The release itself is published: PR #302 merged as `97cc1290` (head `7b16082`, tree
`1918b00e`), release `v1.105.0` on that commit, runtime `1.105.0-8ee73e60de632900`
installed on WSL and Windows. The unit was `blocked` on 2026-09-22 by a test-only Windows
defect and re-activated after `WIN-TESTQUOTE-1` merged as `70016a32` (PR #303). Unit
`REL-1.105.0` (high) is `in_progress` in `.itd-memory/GOAL.json`: the criterion and the
sealed verificationCommand live ONLY there and are not restated here. Review claim ids:
`REL-1.105.0`, `REL-1.105.0:general-review`.

This candidate, staged over `origin/main` `70016a32`, is the ledger-close package the release
owed, frozen BEFORE the native canaries and the harness verification run on it (DECISIONS
2026-09-10 and 2026-09-22, decision 4): the installed proof and the goal verification bind
this staged tree. `tests/` is not part of the installed runtime inventory, so the fix merged
by #303 leaves runtime `1.105.0-8ee73e60de632900` valid.

## In scope

- `.itd/DECISIONS.md`: appended entries (publication decisions, route cost, the
  WIN-TESTQUOTE-1 detour).
- `BACKLOG.md`: one P1 entry with five route observations.
- `.itd/SCOPE_LOCK.md`: this file. `HANDOFF.md`: checkpoints.
- Harness transitions written by `itd_goal_verify.py` on this candidate:
  `.itd-memory/GOAL.json`, `STATE.json`, `events.jsonl`; the acceptance followup of
  the unit flipping to `closed` with its closure evidence.
- Git-ignored host inputs `.itd-memory/host-inputs/REL-1.105.0/` (native canaries
  `native-<Host>-<label>/`, `REL-1.105.0-native-<Host>-<label>/`, `INSTALLED.json`).

## Required evidence

- `tests/verify_route_debts.py --installed-proof .itd-memory/host-inputs/REL-1.105.0/INSTALLED.json` exits 0 on the host.
- The unit's sealed verificationCommand exits 0 end to end inside the goal harness
  (`itd_goal_verify.py REL-1.105.0 --verification-receipt <adjudication>`).
- `sh skills/_shared/itd_py.sh tests/meta_review.py` exits 0; `bash tests/run-all.sh --quick`
  ends with `DONE fails:none`.

## Declared limits

- The sealed verificationCommand keeps the three weaknesses recorded on the release
  candidate (quick-mirror leg without `pipefail`, tag leg checking only the immediate
  first parent, conformance-report place anchored by `endswith`); they are BACKLOG P2
  2026-09-22 and are not repaired here. The owner-signed `accepted-trade-off`
  dispositions of 2026-09-22 cover them for this unit's review claims.
- Native canaries are recorded on this staged candidate, not on the clean merged main:
  after ROUTE-REPAIR-2 an empty staged diff is refused and the canary validator checks
  the adjudication in staged mode (BACKLOG P1 2026-09-22, observation д).

## Out of scope

Every production module and test; the sealed oracle; the gate registry beyond
re-registration for publication; the completion gate; any other unit.
