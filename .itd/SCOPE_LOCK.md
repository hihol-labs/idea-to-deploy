# CLOSURE-DELTA-1 closure records are the only delta after verification

## Current Task

- CLOSURE-DELTA-1: a new stdlib tool `scripts/itd_closure_delta.py` proves that the diff between
  the verified tree of a unit (`candidate.reviewedTree` of its adjudication receipt) and a later
  tree touches only closure records, and exits non-zero otherwise; the new oracle
  `tests/verify_closure_delta.py` covers accepted deltas and rejected mutations. The criterion and
  the verificationCommand live ONLY in `.itd-memory/GOAL.json`.

## Allowed Change Areas

- `scripts/itd_closure_delta.py` (new)
- `tests/verify_closure_delta.py` (new)
- `tests/run-all.sh` - register the oracle.
- `.itd/IMPACT_GRAPH.json` - rebuilt by `tests/build_impact_graph.py`.
- `.itd-memory/contracts/CLOSURE-DELTA-1.md` (new)
- `.itd-memory/GOAL.json`, `.itd-memory/STATE.json`, `.itd-memory/events.jsonl` - status
  transitions only through the goal harness.
- `.itd/DECISIONS.md`, `BACKLOG.md`, `.itd/SCOPE_LOCK.md` (this file) - records.
- `.itd/ACCEPTANCE_CONTRACT.json` - the CLOSURE-DELTA-1 activeFollowup and criteria
  CLOSURE-DELTA-1-1-oracle, CLOSURE-DELTA-1-2-ledger (evidence-first review coverage).

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- The goal harness, the review cache, the Verification Loop and adjudication code; skills, hooks,
  agents. Wiring the tool into the review cache or the ledger-close route is a separate unit.
- The unit criterion and verificationCommand; editing unit statuses by hand.
- Merge and push - only on the owner's explicit command.

## Review Rule

A `/review` pass before the multi-file commit. If the diff touches an area outside allowed scope,
pause and reclassify the task before continuing.
