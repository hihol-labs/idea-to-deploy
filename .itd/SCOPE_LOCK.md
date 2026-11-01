# INSTALLED-PROOF-DISPATCH-1 ledger-close

## Current Task

- INSTALLED-PROOF-DISPATCH-1 ledger-close: record the publication (PR #382 -> main ec52318) and the green installed-proof
  OTK of release 1.110.0 on WSL and Windows, mark the unit verified through `itd_unit_log.py`, close its followup and
  the BACKLOG P1 item. Closure by the ADR-016 convention (`docs/RELEASE_RUNBOOK.md` «Конвенция закрытия»): the merge
  tree equals the reviewed tree of the accepted receipt, no new model round, the owner signs the closure delta.
- Start from merged main `ec52318c9abe2808c78ed72307c22dacf8093d5c`. The closure commit rides the next program PR
  (plan rule 5).

## Allowed Change Areas

- `.itd-memory/STATE.json`, `.itd-memory/events.jsonl` - status transitions only through `itd_unit_log.py`.
- `.itd/ACCEPTANCE_CONTRACT.json` - the followup moves to `closedFollowups` after the unit is marked verified.
- `.itd/DECISIONS.md`, `BACKLOG.md`, `.itd/SCOPE_LOCK.md` (this file) - records.
- `.itd-memory/host-inputs/REL-1.110.0/`, `.itd-memory/host-inputs/INSTALLED-PROOF-DISPATCH-1/` (git-ignored,
  host-owned) - native canaries, `INSTALLED.json`, OTK observations.

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- Any change to skills, hooks, agents, scripts, tests or the legs of the unit command.
- Editing unit statuses by hand; deleting runtime directories of earlier releases.
- Merge and push - only on the owner's explicit command.

## Review Rule

The closure convention of ADR-016 replaces a model round for this delta; the next program PR reviews it as part of its
candidate. If the diff touches an area outside allowed scope, pause and reclassify the task before continuing.
