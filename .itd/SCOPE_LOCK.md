# COMPLETION-FALSE-RED-1 completion gate without false red layers

## Current Task

- COMPLETION-FALSE-RED-1 (narrowed by the owner 2026-10-02, option A after the stop rule
  REDESIGN_OR_DISCARD): the declared exit 2 of `scripts/itd_stop_rule.py --check-binding` in one literal
  form with proof of execution is not a red test layer; other forms and codes still block. The criterion
  and the verificationCommand live ONLY in `.itd-memory/GOAL.json`; the split unit COMPLETION-SUPERSEDE-1
  (pending) carries the mutation-run and supersede classes.

## Allowed Change Areas

- `hooks/completion_lib.py` - the `DECLARED_CHECKS` block (`strip_expected_exit`,
  `_has_conditional_operator`) and two lines in `classify_bash`.
- `tests/verify_completion_false_red.py` (new), `tests/run-all.sh` - register the oracle in CORE.
- `docs/completion-gate.md` (one section), `CHANGELOG.md` (Unreleased), `BACKLOG.md`.
- `.itd/IMPACT_GRAPH.json` - rebuilt by `tests/build_impact_graph.py`.
- `.itd-memory/contracts/COMPLETION-FALSE-RED-1.md` (new); `.itd-memory/GOAL.json` (narrowed criterion of
  this unit and the new pending unit COMPLETION-SUPERSEDE-1 - owner decision 2026-10-02),
  `.itd-memory/STATE.json`, `.itd-memory/events.jsonl` - status transitions only through the goal harness.
- `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md` (this file), `.itd/ACCEPTANCE_CONTRACT.json` (the
  activeFollowup and criteria of this unit).

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- `hooks/completion-gate.sh`, `hooks/completion-signals.sh`, `skills/test/SKILL.md` - unchanged in the
  narrowed unit; the mutation markers of `tests/verify_completion_adversarial_corpus.py` must keep matching.
- `outcome_from` and the text heuristics (FAIL/PASS regexes); `docs/templates/itd/itd_hygiene.py`
  (it does not read the new annotations - a BACKLOG item, not this unit).
- The other pending units of the goal, including COMPLETION-SUPERSEDE-1 (one unit per session).
- Further changes to the unit criterion and verificationCommand (beyond the owner narrowing of 2026-10-02); editing unit statuses by hand.
- Merge and push to main - only on the owner's explicit command.

## Review Rule

High tier: `/review` before the multi-file commit, a full independent fresh-session checker and
the pre-PR opposite-model review (Sol). If the diff touches an area outside allowed scope, pause and
reclassify the task before continuing.
