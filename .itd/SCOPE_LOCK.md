# OTK-HOST-TREE-1 the harness verdict does not depend on git-ignored local files

## Current Task

- OTK-HOST-TREE-1 (eighth and last unit of the goal approved by the owner 2026-10-01; variant A chosen by
  the owner 2026-10-04 after a measurement): the goal harness runs the unit verificationCommand in a
  disposable copy of the working tree without git-ignored files (the tree is built through a temporary
  index, materialized like the machine receipt does), git-ignored inputs a command needs are declared
  with `--input` and copied with the declared-input semantics of the Verification Loop, and a directory
  outside git runs on the host with an explicit line. The criterion and the verificationCommand live ONLY
  in `.itd-memory/GOAL.json`.

## Allowed Change Areas

- `skills/goal/scripts/itd_goal_verify.py` - the isolated working-tree candidate, the `--input` option,
  the `cwd` of the single and the compound command; the module docstring and usage lines.
- `skills/goal/SKILL.md` - the isolation and `--input` paragraph of the verification step.
- `tests/verify_otk_host_tree.py` (new), `tests/run-all.sh` (next to the other goal oracles).
- `tests/verify_otk_failed_attempt.py` - only leg 6: a broken index in the repository the command runs
  from now refuses the run (the approved fail-closed rule), so the attempts-journal guard of Sol s2 is
  reached with the ledger in a broken repository and the command in a healthy one.
- `tests/verify_goal_bounded_autonomy.py` - only the `run` helper: the fixture's git-ignored
  `result.txt` is declared to the harness with `--input`, as it already is to the machine receipt.
- `CHANGELOG.md` (Unreleased), `BACKLOG.md` (TIER-WORDING-2 trap (c) marked as taken; the pnpm symlink
  limit of declared inputs as a new P2 entry).
- `.itd/IMPACT_GRAPH.json` - rebuilt by `tests/build_impact_graph.py`.
- `.itd-memory/contracts/OTK-HOST-TREE-1.md` (new); `.itd-memory/GOAL.json`, `.itd-memory/STATE.json`,
  `.itd-memory/events.jsonl` - status transitions only through the goal harness.
- `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md` (this file), `.itd/ACCEPTANCE_CONTRACT.json` (the
  activeFollowup and criteria of this unit).

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- `skills/_shared/itd_verification_loop.py` - reused as is (declared inputs, isolated checkout); the
  machine receipt route is not changed.
- `scripts/itd_closure_delta.py` and the `evidence` format of the ledger (`exit 0: ...` and the
  per-command lines are a contract of closure-delta and the goal oracles).
- Links inside declared inputs (pnpm `node_modules`) - BACKLOG, not this unit.
- The retro docs of 2026-10-04 (stashed, a separate docs PR) and the value measurement repository.
- Further changes to the unit criterion and verificationCommand; editing unit statuses by hand.
- Push of the branch and the PR follow the route; merge only on the owner's command; no sync-to-active
  until the value measurement ends.

## Review Rule

High tier: `/review` before the multi-file commit, machine receipt (legs `unit`, `meta-review`,
`ledger-state`, equal to the `oracleIds` of the acceptance criteria) and a full independent checker of a
different model (Sol); the goal harness requires the full adjudication receipt for `verified`. If the diff
touches an area outside allowed scope, pause and reclassify the task.
