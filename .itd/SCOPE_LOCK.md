# LEDGER-HORIZON-1: the ledger hook stops warning about units closed before the event journal, the ITD-PLAN-S13 closure

## Current Task

- LEDGER-HORIZON-1: `hooks/validate_state_core.py`, function `reconcile_goal_with_events` - a verified goal unit with
  no unit event at all and a `verifiedAt` strictly before the first record of `events.jsonl` (the journal horizon) is
  not a warning. The criteria and their verification commands live only in `.itd/ACCEPTANCE_CONTRACT.json`
  (LEDGER-HORIZON-1-AC1..AC3); this file references them and does not restate them.
- Start from merged main `f8763a59` (PR #392). WIP=1: ITD-PLAN-S13 is verified in this candidate by the ADR-016 closure
  convention; this unit is the only open one.
- Risk tier high: the diff changes a shipped hook (the state validator used by `state-guard.sh` and
  `scripts/validate_state.py`). Owner confirmations: push, PR, merge, the gate registry update.

## Allowed Change Areas

- `hooks/validate_state_core.py` - `reconcile_goal_with_events`, the docstring of `_last_unit_events`, and the new
  helpers it needs: `_scan_unit_events` (the tail read of `_last_unit_events` plus a whole-journal flag;
  `_last_unit_events` keeps its return value), `_parse_utc`, `_events_horizon`, `EVENTS_HEAD_BYTES` and the
  `datetime` import.
- `tests/verify_state_hardening.py` - new scenarios and mutants next to the existing GOAL reconciliation checks
  (block C2; `tests/verify_ledger_reconciliation.py` tests lifecycle accounting, not this function).
- `tests/fixtures/live-model-evidence/` - live evidence re-recorded on the candidate pin.
- `CHANGELOG.md` (Unreleased), `.itd/IMPACT_GRAPH.json` and `docs/HARNESS_DOCS_STATE.json` only if mechanically
  regenerated.
- Ledgers: `.itd-memory/STATE.json` and `.itd-memory/events.jsonl` through `itd_unit_log.py` only,
  `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/DECISIONS.md`, `BACKLOG.md`, this file.

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- Synthetic unit events for the archived goal units (owner decision 2026-09-20: accepted evidence is immutable);
  edits of `.itd-memory/GOAL-*.json`.
- `reconcile_with_events` (STATE reconciliation), other hooks, skills, agents, trust policy and hook registrations;
  unit statuses by hand.
- The installed runtime: rollout is REL-1.110.6, a separate session.
- Push, PR, merge and changes of the global configuration without the owner's explicit confirmation.

## Review Rule

One opposite-GPT review of the final candidate after a PASSED committed-head machine receipt; its one receipt under
the bare unit id is accepted by the commit cache, the pre-push gate, `itd pr create` and the closure. If the diff
touches an area outside the allowed scope, pause and reclassify the task before continuing.

## Declared limits

- The horizon is the first record of the journal file; a journal trimmed from the head would move the horizon and
  silence absences older than the new first record. The journal is append-only today; trimming is not in scope.
- The installed hook keeps warning until REL-1.110.6 is released and rolled out.
