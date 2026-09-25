# G-004 ledger-close - publication decisions, route cost, deferred findings

Documentation-only closure of unit `G-004` (HOOKS-AUTOINSTALL-1, medium), which shipped as PR #309
(squash `60f5801`, head `dc415b3`, CI Gate 1 + windows-verify pass) and is `verified` by the goal
harness in `.itd-memory/GOAL.json` (goal PROPORTIONALITY-DEFAULT, 4/5). Review claim id:
`G-004:general-review`, risk tier `medium`. No production module, hook, skill, script or oracle
changes.

## In scope

- `.itd/DECISIONS.md`: two appended entries - the hooks offer as the final step of `/adopt` and
  `/project` (with the rejected alternatives), and the owner-route publication of #309 with its cost
  (code-reviewer + 17 targeted checkers, producer rounds PUB1..PUB3) and the PUB3 dispositions.
- `BACKLOG.md`: a P2 section with the three open PUB3 findings (symlink-swap race, user-level dedup
  by script name, narrow `BAD_TEMPLATES`), a P3 section for the stale "all three skips" sentence of
  `/adopt` (found by the ledger-close checker c1, not by PUB3), and a "Отложено для /retro (итог
  G-004)" section with three route-cost candidates.
- `tests/fixtures/fixture-17-adopt/notes.md`: the Scenario B checklist follows the Step 7 offer
  (PUB3 finding 4).
- `.itd/SCOPE_LOCK.md`: this file.

## Out of scope

- Fixing the PUB3 findings (a)-(c) - recorded, not implemented.
- Any change to `skills/`, `hooks/`, `scripts/`, the oracle, the goal ledger or the acceptance contract.

## Verification

- `sh skills/_shared/itd_py.sh tests/meta_review.py --verbose` - FINAL STATUS PASSED.
- `sh skills/_shared/itd_py.sh tests/verify_hooks_autoinstall.py` - green (the fixture notes are not read by it).
- Targeted fresh-session checker over the factual claims of the documents.
