# ORACLE-LEGS-1 machine receipt: the legs must cover the oracleIds of the unit

## Current Task

- ORACLE-LEGS-1 (fourth unit of the goal approved by the owner 2026-10-01; criterion and its
  implementation notes approved by the owner 2026-10-03 before activation):
  `skills/_shared/itd_verification_loop.py machine`, minting for the claim equal to the active
  follow-up unit, refuses before running any leg when a `reviewEvidence.oracleIds` entry of that
  unit's acceptance criteria is not among the `--command` leg ids; the refusal names the criterion and
  the missing oracle. The criterion and the verificationCommand live ONLY in `.itd-memory/GOAL.json`.

## Allowed Change Areas

- `skills/_shared/itd_verification_loop.py` - the leg check called from `command_machine` before the
  first leg and its module loader for `itd_review_evidence`.
- `tests/verify_machine_oracle_legs.py` (new), `tests/run-all.sh` - register the oracle in CORE.
- `docs/VERIFICATION_LOOP.md` (one paragraph), `CHANGELOG.md` (Unreleased), `BACKLOG.md` (P2 item (d)
  of the TIER-WORDING-2 traps marked as taken by this unit).
- `.itd/IMPACT_GRAPH.json` - rebuilt by `tests/build_impact_graph.py`.
- `.itd-memory/contracts/ORACLE-LEGS-1.md` (new); `.itd-memory/GOAL.json`, `.itd-memory/STATE.json`,
  `.itd-memory/events.jsonl` - status transitions only through the goal harness.
- `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md` (this file), `.itd/ACCEPTANCE_CONTRACT.json` (the
  activeFollowup and criteria of this unit).

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- `skills/_shared/itd_review_evidence.py` and `skills/_shared/itd_free_reviewer_producer.py`: the
  coverage check of the producer stays as it is (the new check runs earlier, it does not replace it).
- The receipt format, the leg execution and every other subcommand of the Verification Loop.
- The other pending units of the goal (one unit per session).
- Further changes to the unit criterion and verificationCommand; editing unit statuses by hand.
- Push of the branch and the PR follow the route; merge only on the owner's command.

## Review Rule

Medium tier: `/review` before the multi-file commit, a targeted fresh-session checker and the pre-PR
opposite-model review (Sol). If the diff touches an area outside allowed scope, pause and reclassify
the task before continuing.
