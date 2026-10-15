# BROKER-SKEW-CLOCK-1 ledger-close + EXTOUT-CLOCK-1

## Current Task

- BROKER-SKEW-CLOCK-1 ledger-close: record the merge of PR #358 and close the followup (owner 2026-10-15,
  "да, закрой и мержи когда CI зеленый").

## Allowed Change Areas

- `.itd/ACCEPTANCE_CONTRACT.json` - the followup moves to `closedFollowups`; `activeFollowup` becomes the closed-contract
  record `{unitId: "", status: "none", note}`.
- `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md` (this file) - records.
- `tests/verify_external_outcome_contract.py` - the export fixture dated relative to today (EXTOUT-CLOCK-1): its fixed
  2026-07-15 dates went stale against maxExternalOutcomeAgeDays 90 on 2026-10-14 and turned CI red on every branch.
- `CHANGELOG.md` - one entry for that fix.

## Forbidden Change Areas

- `HANDOFF.md`; skills, hooks, agents, scripts, other tests, live evidence and `.itd-memory/` ledgers.

## Review Rule

One independent checker (gpt-5.6-sol) on the exact committed candidate before `itd pr create`.
