# REL-1.107.0 ledger-close

## Current Task

- REL-1.107.0 ledger-close: record the publication and rollout of release 1.107.0 and close the followup
  (owner instruction 2026-10-14, "да, все три сделай"). No goal unit: REL-1.107.0 ran without `/goal` (ADR-012).

## Allowed Change Areas

- `.itd/ACCEPTANCE_CONTRACT.json` - the REL-1.107.0 followup moves to `closedFollowups`; `activeFollowup` becomes the
  closed-contract record `{unitId: "", status: "none", note}`.
- `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md` (this file), `BACKLOG.md` - records (BACKLOG: the review-broker
  test flake found during this ledger-close, with its root cause).

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- Any change to skills, hooks, agents, scripts, tests, the live evidence or `.itd-memory/` ledgers.
- Deleting runtime directories of earlier releases.

## Review Rule

One independent checker (gpt-5.6-sol through the free reviewer producer) on the exact committed candidate before
`itd pr create`. If the diff touches an area outside allowed scope, pause and reclassify the task before continuing.
