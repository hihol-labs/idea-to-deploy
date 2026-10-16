# GATE-OPTIN-1 ledger-close

## Current Task

- GATE-OPTIN-1 ledger-close: record the merge of PR #364, the rollout on WSL and Windows (runtime, registries) and the
  first pushes through the opt-in gate; close the followup.

## Allowed Change Areas

- `.itd/ACCEPTANCE_CONTRACT.json` - the followup moves to `closedFollowups`; `activeFollowup` becomes the closed-contract
  record `{unitId: "", status: "none", note}`.
- `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md` (this file), `BACKLOG.md` - records.

## Forbidden Change Areas

- `HANDOFF.md`; skills, hooks, agents, scripts, tests, live evidence and `.itd-memory/` ledgers.

## Review Rule

Records only; one general-review checker (gpt-5.6-sol) on the exact candidate, then `itd pr create`.
