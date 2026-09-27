# HANDOFF-UNTRACKED-1

## Current Task

- HANDOFF-UNTRACKED-1: `HANDOFF.md` stops being tracked by git in this repository and stays a
  local hand-over packet; the `/handoff` skill and the release and ledger-close SCOPE_LOCK
  templates no longer put `HANDOFF.md` inside a reviewed diff. Goal unit (medium). The criterion
  and the verificationCommand live ONLY in `.itd-memory/GOAL.json`.

## Allowed Change Areas

- `.gitignore` - a root-anchored `/HANDOFF.md` rule.
- `HANDOFF.md` - removed from the index only (`git rm --cached`); the local file stays. Its
  survival is a working-tree fact: proven by the machine leg `local-packet` (`test -s HANDOFF.md`)
  over the declared ignored input `HANDOFF.md`, not by the reviewed tree.
- `skills/handoff/SKILL.md` - where the packet lives and that it never enters a reviewed diff.
- `docs/RELEASE_RUNBOOK.md` - a section with the release and ledger-close SCOPE_LOCK templates.
- `tests/verify_handoff_untracked.py` (new), `tests/run-all.sh` - the oracle and its registration.
- `.itd/IMPACT_GRAPH.json` - rebuilt by `tests/build_impact_graph.py`.
- `tests/fixtures/live-model-evidence/` - only if the live pin moves (it did not: the changed
  skill file is outside the narrowed pin).
- `.itd-memory/GOAL.json`, `.itd-memory/GOAL-2026-09-27.json`, `.itd-memory/STATE.json`,
  `.itd-memory/events.jsonl` - the new goal ledger, the archive of the closed one, harness
  projections and events.
- `.itd/SCOPE_LOCK.md` (this file), `.itd/DECISIONS.md`, `BACKLOG.md` - records.

## Forbidden Change Areas

- `.itd-memory/HANDOFF-*.md` and other hand-over files; hooks, agents, other skills; README.
- The unit criterion and verificationCommand; unit statuses by hand.
- Push, PR, merge - only on the owner's explicit command.

## Review Rule

If the diff touches an area outside allowed scope, pause and reclassify the task before continuing.
