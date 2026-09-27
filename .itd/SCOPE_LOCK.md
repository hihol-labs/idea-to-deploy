# HANDOFF-UNTRACKED-1 ledger-close

## Current Task

- HANDOFF-UNTRACKED-1 ledger-close: record the publication of unit HANDOFF-UNTRACKED-1 (PR #317,
  squash `54878b3`, tree `3009c901`), re-verify the unit with the goal harness on this candidate,
  record the route cost and the open minor findings. The criterion and the verificationCommand live
  ONLY in `.itd-memory/GOAL.json`.

## Allowed Change Areas

- `.itd-memory/GOAL.json`, `.itd-memory/STATE.json`, `.itd-memory/events.jsonl` - status
  transitions only through the goal harness.
- `.itd/DECISIONS.md`, `BACKLOG.md`, `.itd/SCOPE_LOCK.md` (this file) - records.

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- Any change to skills, hooks, agents, scripts, tests or the unit command.
- Editing unit statuses by hand.
- Merge and push - only on the owner's explicit command.

## Review Rule

A `/review` pass before the multi-file commit. If the diff touches an area outside allowed scope,
pause and reclassify the task before continuing.
