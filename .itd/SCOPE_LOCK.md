# REL-1.106.0 ledger-close

## Current Task

REL-1.106.0 ledger-close - record the publication and rollout of release 1.106.0, revert the
fourth amendment of the unit command, run the goal harness ОТК on this candidate, close the
followup and the goal.

Unit `REL-1.106.0` (high) shipped as PR #315 (squash `f3e0f42`, tree `30f62a28`, CI Gate 1 +
windows-verify pass), tag and GitHub release `v1.106.0` on `f3e0f42`, rollout on WSL and Windows.
This candidate is staged over `f3e0f42`. The criterion and the verificationCommand live ONLY in
`.itd-memory/GOAL.json`.

## Allowed Change Areas

- `.itd-memory/GOAL.json` - the last leg of the REL-1.106.0 verificationCommand back to its
  2026-09-26 form (owner decision 2026-09-27); status transitions only through the goal harness.
- `.itd-memory/STATE.json`, `.itd-memory/events.jsonl` - goal harness projections and events.
- `.itd/ACCEPTANCE_CONTRACT.json` - the REL-1.106.0 followup moves to `closedFollowups` after the
  harness marks the unit verified.
- `.itd/DECISIONS.md`, `BACKLOG.md`, `HANDOFF.md`, `.itd/SCOPE_LOCK.md` (this file) - records.
- `.itd-memory/host-inputs/REL-1.106.0/` (git-ignored, host-owned): native canaries on this
  candidate and `INSTALLED.json`.

## Required

- Native canaries on WSL and Windows recorded on this staged candidate; `INSTALLED.json` accepted
  by `tests/verify_route_debts.py --installed-proof`.
- The whole verificationCommand exits 0 on this candidate as one machine run; independent review
  and adjudication for the claim `REL-1.106.0`; the goal harness marks the unit verified with that
  receipt.
- A `/review` pass before the multi-file commit; merge, push and any further release action only
  on the owner's explicit command.

## Forbidden

- Any change to skills, hooks, agents, scripts, tests or the other nine legs of the unit command.
- Editing unit statuses by hand; deleting runtime directories of earlier releases.
