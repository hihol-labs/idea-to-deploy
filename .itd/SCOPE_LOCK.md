# OTK-FAILED-ATTEMPT-1 a failed harness attempt does not block the next one

## Current Task

- OTK-FAILED-ATTEMPT-1 (seventh unit of the goal approved by the owner 2026-10-01; variant A chosen by
  the owner 2026-10-04 before activation): a failed committed-head attempt of the goal harness no longer
  appends `verification_failed` to the tracked `.itd-memory/events.jsonl`; the event goes to the
  untracked attempts journal `.itd-memory/attempts/attempts.jsonl` (self-ignoring directory), the retro
  scan counts it from both journals, and `scripts/itd_closure_delta.py` accepts the ledger-close delta of
  such a unit unchanged. The criterion and the verificationCommand live ONLY in `.itd-memory/GOAL.json`.

## Allowed Change Areas

- `skills/goal/scripts/itd_goal_verify.py` - the attempts journal helper, the `journal` parameter of
  `append_event` and the one failure call site; the module docstring line.
- `skills/retro/scripts/itd_retro_scan.py` - `failedVerifications` reads both journals; the source list.
- `tests/verify_otk_failed_attempt.py` (new), `tests/run-all.sh` (FULL, next to `verify_closure_delta`).
- `tests/verify_goal_tools.py`, `tests/verify_goal_verify_failpath.py` - the event-reading helpers read
  the attempts journal too.
- `CHANGELOG.md` (Unreleased), `BACKLOG.md` (TIER-WORDING-2 trap (b) marked as taken; the completion
  signal finding as a new P2 entry).
- `.itd/IMPACT_GRAPH.json` - rebuilt by `tests/build_impact_graph.py`.
- `.itd-memory/contracts/OTK-FAILED-ATTEMPT-1.md` (new); `.itd-memory/GOAL.json`, `.itd-memory/STATE.json`,
  `.itd-memory/events.jsonl` - status transitions only through the goal harness.
- `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md` (this file), `.itd/ACCEPTANCE_CONTRACT.json` (the
  activeFollowup and criteria of this unit).

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- `scripts/itd_closure_delta.py` (variant B was rejected by the owner) and `itd_verification_loop.py`.
- The completion signal writer `write_verify_signal` and `.claude/completion/` (BACKLOG P2 2026-10-04).
- Bounded-run attempts (`attempts[]` in GOAL.json) and the `verification_unverified` events.
- The goal reporter label `[machine_only]` (BACKLOG P2 2026-09-27, separate unit).
- The other pending units of the goal (OTK-HOST-TREE-1; one unit per session).
- Further changes to the unit criterion and verificationCommand; editing unit statuses by hand.
- Push of the branch and the PR follow the route; merge only on the owner's command.

## Review Rule

Medium tier: `/review` before the multi-file commit, machine receipt (legs `unit`, `meta-review`,
`ledger-state`, equal to the `oracleIds` of the acceptance criteria) and a targeted checker over the
residual risk the machine legs do not cover; the goal harness requires the targeted adjudication receipt
for `verified`. If the diff touches an area outside allowed scope, pause and reclassify the task.
