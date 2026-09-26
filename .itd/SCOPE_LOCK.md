# G-005 ledger-close - goal closure, publication decisions, route cost, deferred findings

Closure of unit `G-005` (PILOT-LOW-1, medium), which shipped as PR #311 (squash `3a6b594`, head
`867c0a7`, CI Gate 1 + windows-verify pass) and is `verified` by the goal harness in
`.itd-memory/GOAL.json`, and of goal PROPORTIONALITY-DEFAULT at 5/5. Review claim id:
`G-005:general-review`, risk tier `medium`. No production module, hook, skill, script or oracle
changes.

## In scope

- `.itd-memory/GOAL.json`: goal `status` `active` -> `done`, `updatedAt` (all five units are
  `verified`; no unit status changes).
- `.itd-memory/STATE.json`: `nextAction` describes the closed goal and the free WIP slot.
- `.itd/ACCEPTANCE_CONTRACT.json`: the G-005 follow-up moves to `closedFollowups` (`closed`,
  `closedAt`, `closureEvidence`); `activeFollowup` becomes `none`. The G-005 criteria stay `passed`.
- `.itd/DECISIONS.md`: one appended entry - the owner-route publication of #311 with its cost
  (8 targeted checkers, producer rounds PUB1..PUB3, bypasses), the PUB3 dispositions, and a
  clarification of the earlier PILOT-LOW-1 token-metric entry (append-only, not rewritten).
- `BACKLOG.md`: a P1 section (stale `.pyc` can hand a mutant the previous mutant's verdict in
  `/test` Step 5.5 mutation runs) and a P2 section with the G-005 route findings (a) completion
  signals, (b) medium-route order, (c) PASSED_WITH_WARNINGS series on prose, (d) `activeMinutes`
  over one merged timeline.
- `docs/retros/RETRO-PILOT-LOW-1.md`: the sentence on cache reads (PUB3 finding 2).
- `.itd/SCOPE_LOCK.md`: this file.

## Out of scope

- Fixing the BACKLOG findings - recorded, not implemented.
- Any change to `skills/`, `hooks/`, `scripts/`, tests, the measurement tools or the pilot ledger.

## Verification

- `sh skills/_shared/itd_py.sh scripts/validate_state.py .itd-memory/GOAL.json .itd-memory/STATE.json` - OK.
- `sh skills/_shared/itd_py.sh tests/meta_review.py --verbose` - FINAL STATUS PASSED.
- Targeted fresh-session checker over the factual claims of the documents.
