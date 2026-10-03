# TEST-RULES-1 /test Step 5.5: unique mutation marker and escaped fixtures

## Current Task

- TEST-RULES-1 (sixth unit of the goal approved by the owner 2026-10-01; criterion checked against
  `skills/test/SKILL.md` Step 5.5 and approved by the owner 2026-10-03 before activation):
  Step 5.5 states two rules - a mutation marker occurs exactly once in the mutated file and the
  mutation helper checks that before applying the mutant; fixtures with non-ASCII or invisible
  characters are written as escape sequences by a script because the file-write tool decodes them.
  The new oracle `tests/verify_test_skill_rules.py` checks both rules in the skill text. The
  criterion and the verificationCommand live ONLY in `.itd-memory/GOAL.json`.

## Allowed Change Areas

- `skills/test/SKILL.md` - two bullets in Step 5.5, nothing else in the skill.
- `tests/verify_test_skill_rules.py` (new), `tests/run-all.sh` (FULL, next to
  `verify_refute_fleet`), `.github/workflows/meta-review.yml` (one step after the refute-fleet step).
- `CHANGELOG.md` (Unreleased), `BACKLOG.md` (P2 item (f) of the TIER-WORDING-2 traps and the
  unique-marker lesson marked as taken).
- `.itd/IMPACT_GRAPH.json` - rebuilt by `tests/build_impact_graph.py`.
- `.itd-memory/contracts/TEST-RULES-1.md` (new); `.itd-memory/GOAL.json`, `.itd-memory/STATE.json`,
  `.itd-memory/events.jsonl` - status transitions only through the goal harness.
- `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md` (this file), `.itd/ACCEPTANCE_CONTRACT.json` (the
  activeFollowup and criteria of this unit).

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- `tests/verify_refute_fleet.py` and the other steps of `skills/test/SKILL.md`.
- A mutation helper in code (the rule is a /test instruction; no shared helper module is added).
- The completion gate and its supersede rule (BACKLOG P2 item (b) stays open).
- The other pending units of the goal (one unit per session).
- Further changes to the unit criterion and verificationCommand; editing unit statuses by hand.
- Push of the branch and the PR follow the route; merge only on the owner's command.

## Review Rule

Low tier: `/review` before the multi-file commit and machine-only adjudication (receipt legs `unit`,
`meta-review`, `ledger-state`). If the diff touches an area outside allowed scope, pause and
reclassify the task before continuing.
