# TIER-SOURCE-1 ledger-close - followup closure, publication record, route cost

Closure of unit `TIER-SOURCE-1` (medium), which shipped as PR #313 (squash `1937063`, head
`8c3da22`, CI Gate 1 + windows-verify pass) and is `verified` by the goal harness in
`.itd-memory/GOAL.json`. The goal TIER-SOURCE-1 -> REL-1.106.0 stays `active` at 1/2; no unit is
activated by this closure. Documentation and ledger records only: no skill, hook, script, test
or oracle changes.

## Current Task

TIER-SOURCE-1 ledger-close: move the followup to `closedFollowups`, record the publication of
#313 and the route cost, point `nextAction` at REL-1.106.0.

## Allowed Change Areas

- `.itd/ACCEPTANCE_CONTRACT.json` - the TIER-SOURCE-1 followup moves to `closedFollowups`
  (`closed`, `closedAt`, `closureEvidence`); `activeFollowup` becomes `none`. Both TIER-SOURCE-1
  criteria stay `passed`.
- `.itd-memory/STATE.json` - `nextAction` describes the free WIP slot and the next unit.
- `.itd/DECISIONS.md` - one appended entry: the publication of #313, the route (c1/c2 BLOCKED,
  stop rule, owner decision, PUB1/PUB2 BLOCKED, PUB3 PASSED) and its cost (16 targeted
  checkers, 3 producer rounds, 3 `COMPLETION_BYPASS`).
- `BACKLOG.md` - a status note on the P1 2026-09-25 item: the tests-only part is closed, the
  non-test part stays open.
- `.itd/SCOPE_LOCK.md` - this file.

## Forbidden Change Areas

- `.itd-memory/GOAL.json` and `.itd-memory/events.jsonl` - unit transitions belong to the goal
  harness; REL-1.106.0 is activated only after this closure merges.
- Any change to `skills/`, `hooks/`, `scripts/`, `tests/` or the installed copy.
- Fixing the open BACKLOG items - recorded, not implemented.

## Verification

- `sh skills/_shared/itd_py.sh scripts/validate_state.py .itd-memory/GOAL.json .itd-memory/STATE.json` - OK.
- `sh skills/_shared/itd_py.sh tests/meta_review.py --verbose` - FINAL STATUS PASSED.
- `/review` over the factual claims of the records against the merged tree and the checker reports.
