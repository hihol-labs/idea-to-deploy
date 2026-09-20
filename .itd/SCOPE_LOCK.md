# GOAL-TRANSITION-2026-09-20

No unit is active. This candidate is goal-level bookkeeping decided by the
owner on 2026-09-20: the PE5 goal is closed as `abandoned`, its ledger is
archived, and a new goal ledger is opened for internal work.

The diff contains no executable change: no code, no test, no hook, no skill,
no agent, no contract that a gate executes.

## In scope

- `.itd-memory/GOAL-2026-09-20.json`: the former `GOAL.json`, byte-identical
  except `status` (`active` -> `abandoned`), `updatedAt`, and a new
  `abandonedReason`. Units are untouched; `PE5-008` and `PE5-009` stay `blocked`.
- `.itd-memory/GOAL.json`: a new active goal with two `pending` low-risk units,
  `LEDGER-ARCHIVE-1` and `ROUTE-REPAIR-3`, both approved by the owner.
- `.itd/DECISIONS.md`: one appended entry recording the decision and its known
  limit.
- `BACKLOG.md`: two appended P2 entries.
- `.itd/SCOPE_LOCK.md`: this file.

## Required evidence

- Both ledger files pass `scripts/validate_state.py`.
- The archived ledger differs from its predecessor only in the three fields
  named above.
- No unit of the archived ledger changed status, evidence or receipt.

## Declared limit

- Events labelled `"ledger": "GOAL.json"` are attributed by name to the new
  ledger until `LEDGER-ARCHIVE-1` lands. The maker measured on a copy of the
  ledger files that `itd_unit_lifecycle.build` counters are identical before
  and after; `events.jsonl` is unchanged by this candidate, so it is not in
  the diff.
- The owner's approval of the two units was given in the session and is
  recorded in `.itd/DECISIONS.md`, not provable from the diff.

## Out of scope

Any code change, including the attribution fix itself; `STATE.json`;
`events.jsonl`; the release unit for 1.105.0; GitHub issue #165.
