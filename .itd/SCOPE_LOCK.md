# PRODUCER-FALLBACK-LEDGER-1 ledger-close

## Current Task

- PRODUCER-FALLBACK-LEDGER-1 ledger-close: record the merge of PR #360 and its rollout, close the followup (owner
  2026-10-15, "да, сделай оба и мержи когда CI зеленый").

## Allowed Change Areas

- `.itd/ACCEPTANCE_CONTRACT.json` - the followup moves to `closedFollowups`; `activeFollowup` becomes the closed-contract
  record `{unitId: "", status: "none", note}`.
- `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md` (this file) - records.

## Forbidden Change Areas

- `HANDOFF.md`; skills, hooks, agents, scripts, tests, live evidence and `.itd-memory/` ledgers.

## Review Rule

One independent checker (gpt-5.6-sol) on the exact committed candidate before `itd pr create`.
