# G-003 ledger-close - publication decisions, route cost, deferred findings

Documentation-only closure of unit `G-003` (HOOKS-TIER-EXIT-1, medium), which shipped as
PR #307 (squash `5e3d8c3`, head `8ed8d49`, CI Gate 1 + windows-verify pass) and is
`verified` by the goal harness in `.itd-memory/GOAL.json` (goal PROPORTIONALITY-DEFAULT,
3/5). Review claim id: `G-003:general-review`, risk tier `medium` (the tier of the current
unit). No production module, hook, skill, script or test changes.

The next unit `G-004` is activated by the goal harness OUTSIDE this candidate: the
activation (`GOAL.json`, `STATE.json`, `events.jsonl`) travels with the G-004 branch, as
with the ROUTE-REPAIR-3 activation after #298.

## In scope

- `.itd/DECISIONS.md`: one appended entry "2026-09-24: G-003 - публикация owner-маршрутом
  и цена маршрута" - PR #307 went through the owner route after producer rounds PUB1b..PUB5
  (all BLOCKED, 4/2/2/3/1 distinct findings; PUB1 was a launch error, UNVERIFIED); cost 22 fresh checkers and 5 producer rounds, four receipt re-binds via
  `--recheck`, one `regressed` transition from a dirty-tree recheck.
- `BACKLOG.md`: a P2 section on the open PUB5 finding - importing `tier_exempt` from the
  four advisory hooks writes `__pycache__` next to the installed helper - with a ready fix
  (`sys.dont_write_bytecode` around the import, pattern of `hooks/completion-gate.sh`) and
  the oracle leg that would catch it (run without `PYTHONDONTWRITEBYTECODE`, which
  `tests/verify_hook_tier_exit.py` currently sets and thereby masks the write).
- `BACKLOG.md`: a section "Отложено для /retro" with three route-cost candidates:
  a cheaper path for `PASSED_WITH_WARNINGS` with only minor doc fixes; `meta_review` exit 0
  on Important findings (P2 G-003 (b)); `--recheck` on a dirty tree demoting to `regressed`
  (P2 G-003 (a)).
- `.itd/SCOPE_LOCK.md`: this file, describing the closure instead of the G-003 unit.

## Out of scope

- Applying the bytecode fix or the oracle leg (a future unit; recorded, not implemented).
- Any change to hooks, skills, scripts, tests, the goal ledger or the acceptance contract.
- Implementing any of the `/retro` candidates.

## Verification

- `sh skills/_shared/itd_py.sh tests/meta_review.py --verbose` - FINAL STATUS PASSED.
- `sh skills/_shared/itd_py.sh scripts/validate_state.py .itd-memory/GOAL.json .itd-memory/STATE.json` - OK.
- Targeted fresh-session checker over the factual claims of the two documents.
