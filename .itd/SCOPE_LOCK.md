# GOALVERIFY-FAILPATH-1 clean failure path of the goal harness

## Current Task

- GOALVERIFY-FAILPATH-1: when a compound verificationCommand fails,
  `skills/goal/scripts/itd_goal_verify.py` prints the decisive line `FAILED <unit> stays
  in_progress` with the per-leg evidence and exits 1 without a traceback (no `UnboundLocalError`
  on `output`); the single-command and no-sh failure paths keep their output; the new oracle
  `tests/verify_goal_verify_failpath.py` is RED on the pre-fix code and GREEN after. The criterion
  and the verificationCommand live ONLY in `.itd-memory/GOAL.json`. First unit of the goal "route
  traps of TIER-WORDING-2", approved by the owner on 2026-10-01 (`.itd/DECISIONS.md`).

## Allowed Change Areas

- `skills/goal/scripts/itd_goal_verify.py` - `cmd_verify`, the compound branch binds `output`;
  no other function changes.
- `tests/verify_goal_verify_failpath.py` (new)
- `tests/run-all.sh` - register the oracle in CORE.
- `CHANGELOG.md` - the Unreleased entry (added after `/review` r1 minor 2).
- `.itd/IMPACT_GRAPH.json` - rebuilt by `tests/build_impact_graph.py`.
- `.itd-memory/contracts/GOALVERIFY-FAILPATH-1.md` (new)
- `.itd-memory/GOAL.json` (the new goal ledger), `.itd-memory/GOAL-2026-10-01-stoprule.json`
  (archive of the finished goal), `.itd-memory/STATE.json`, `.itd-memory/events.jsonl` - status
  transitions only through the goal harness.
- `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md` (this file) - records.
- `.itd/ACCEPTANCE_CONTRACT.json` - the GOALVERIFY-FAILPATH-1 activeFollowup and criteria
  GOALVERIFY-FAILPATH-1-1-oracle, GOALVERIFY-FAILPATH-1-2-ledger.

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- `run_compound_verification`, `decisive_line`, the ledger evidence format and every success
  path of the harness.
- The other six units of the goal (one unit per session).
- The unit criterion and verificationCommand; editing unit statuses by hand.
- Merge and push - only on the owner's explicit command.

## Review Rule

Low tier: `/review` before the multi-file commit and machine-only adjudication (no independent
checker). If the diff touches an area outside allowed scope, pause and reclassify the task before
continuing.
