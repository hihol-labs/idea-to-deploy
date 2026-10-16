# REL-1.108.0 ledger-close

## Current Task

- REL-1.108.0 ledger-close: record the merge of PR #362, release v1.108.0 and the rollout on WSL and Windows, close
  the followup (owner 2026-10-16, "Публиковать с раскрытием"), and record the owner decision on the next unit
  GATE-OPTIN-1 (BACKLOG P1) and the Sol convergence item (BACKLOG P2).

## Allowed Change Areas

- `.itd/ACCEPTANCE_CONTRACT.json` - the followup moves to `closedFollowups`; `activeFollowup` becomes the closed-contract
  record `{unitId: "", status: "none", note}`.
- `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md` (this file), `BACKLOG.md` - records.

## Forbidden Change Areas

- `HANDOFF.md`; skills, hooks, agents, scripts, tests, live evidence and `.itd-memory/` ledgers.

## Review Rule

Records only; no shipped code changes. CI meta-review is the merge gate.
