# COMPLETION-SUPERSEDE-1 completion gate: a red superseded by a later green record

## Current Task

- COMPLETION-SUPERSEDE-1 (split from COMPLETION-FALSE-RED-1 by the owner 2026-10-02; criterion
  approved by the owner 2026-10-02 before activation): a red run of an oracle is not a red layer once
  the latest runner record of the same invocation is green; identity and outcome come from the record
  the runner writes, not from the command text. The criterion and the verificationCommand live ONLY in
  `.itd-memory/GOAL.json`.

## Allowed Change Areas

- `skills/_shared/itd_py.sh` - the opt-in `ITD_RUN_RECORD=1` block before the exec chain;
  `skills/_shared/itd_run_record.py` (new); `scripts/itd_install_runtime.py` - one line: the new shared
  file in `RUNTIME_SHARED_FILES` (required by `tests/verify_itd_runtime_install.py`).
- `hooks/completion_lib.py` - the run-record block (`match_run_record`, `counted_signals` and their
  helpers), the record attachment and the evidence line in `classify_bash`, one line in
  `compute_verdict`.
- `hooks/completion-gate.sh` - one line: the strict path judges the counted signals.
- `tests/verify_completion_supersede.py` (new), `tests/run-all.sh` - register the oracle in CORE.
- `docs/completion-gate.md` (one section), `skills/test/SKILL.md` (Step 5.5: the recorded run),
  `CHANGELOG.md` (Unreleased), `BACKLOG.md`.
- `.itd/IMPACT_GRAPH.json` - rebuilt by `tests/build_impact_graph.py`.
- `.itd-memory/contracts/COMPLETION-SUPERSEDE-1.md` (new); `.itd-memory/GOAL.json` (the criterion of
  this unit in the wording approved by the owner 2026-10-02), `.itd-memory/STATE.json`,
  `.itd-memory/events.jsonl` - status transitions only through the goal harness.
- `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md` (this file), `.itd/ACCEPTANCE_CONTRACT.json` (the
  activeFollowup and criteria of this unit).

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- `hooks/completion-signals.sh`, `outcome_from` and the text heuristics (FAIL/PASS regexes),
  `strip_expected_exit` and `DECLARED_CHECKS`; the mutation markers of
  `tests/verify_completion_adversarial_corpus.py` and `tests/verify_completion_false_red.py` must keep
  matching.
- The default launch of `skills/_shared/itd_py.sh` (no `ITD_RUN_RECORD`): byte-identical behaviour.
- `docs/templates/itd/itd_hygiene.py` (the session close does not read run records - a BACKLOG item).
- Any judgement of the supersede from the command text.
- The other pending units of the goal (one unit per session).
- Further changes to the unit criterion and verificationCommand; editing unit statuses by hand.
- Merge and push to main - only on the owner's explicit command.

## Review Rule

High tier: `/review` before the multi-file commit, a full independent fresh-session checker and
the pre-PR opposite-model review (Sol). If the diff touches an area outside allowed scope, pause and
reclassify the task before continuing.
