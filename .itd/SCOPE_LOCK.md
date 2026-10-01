# STOPRULE-STUB-1 stop-rule live binding recognises the closed contract

## Current Task

- STOPRULE-STUB-1: on a closed-contract tree (activeFollowup is exactly {unitId: '', status:
  'none', note?} and STATE.currentUnit is not in progress) `itd_stop_rule.live_policy_binding`
  returns the state NO_ACTIVE_UNIT with aligned false and raises nothing, and
  `scripts/itd_stop_rule.py --check-binding` prints NO_ACTIVE_UNIT with a WHY and FIX line and exits
  2; a broken contract is still refused; on a copy of the tracked tree carrying the
  closed-contract stub and a verified STATE.currentUnit `tests/verify_stop_rule.py` exits 0; the
  new oracle `tests/verify_stop_rule_closed_contract.py` is RED on the pre-fix code and GREEN
  after. The criterion and the verificationCommand live ONLY in `.itd-memory/GOAL.json`. Variant A
  approved by the owner on 2026-10-01 (`.itd/DECISIONS.md`).

## Allowed Change Areas

- `scripts/itd_stop_rule.py` - `live_policy_binding` (the closed-contract branch, the `state`
  field of the result, typed refusal of a non-object `activeFollowup` / `currentUnit`), the new
  helper `closed_contract` with the constants `CLOSED_FOLLOWUP_KEYS`, `LEDGER_TERMINAL_STATUSES`,
  `NO_ACTIVE_UNIT`, and the `--check-binding` output; no other function changes.
- `tests/verify_stop_rule_closed_contract.py` (new)
- `tests/verify_stop_rule.py` - only if a pinned expectation of the binding result has to name the
  new `state` field.
- `tests/run-all.sh` - register the oracle in CORE.
- `docs/VERIFICATION_LOOP.md` - the `--check-binding` paragraph.
- `CHANGELOG.md` - the Unreleased entry.
- `.itd/IMPACT_GRAPH.json` - rebuilt by `tests/build_impact_graph.py`.
- `.itd-memory/contracts/STOPRULE-STUB-1.md` (new)
- `.itd-memory/GOAL.json`, `.itd-memory/GOAL-2026-10-01.json` (archive of the finished goal),
  `.itd-memory/STATE.json`, `.itd-memory/events.jsonl` - status transitions only through the
  goal harness.
- `.itd/DECISIONS.md`, `BACKLOG.md`, `.itd/SCOPE_LOCK.md` (this file) - records.
- `.itd/ACCEPTANCE_CONTRACT.json` - the STOPRULE-STUB-1 activeFollowup and criteria
  STOPRULE-STUB-1-1-oracle, STOPRULE-STUB-1-2-ledger.

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- `scripts/itd_closure_delta.py` - variant B (a stub naming the closed unit) is rejected: the
  binding would report ALIGNED for a closed unit.
- `.itd/STOP_RULE_POLICY.json` and the frozen binding invariants
  (`EXPECTED_BINDING_INVARIANTS`).
- `machine_ready_binding`, the history verdicts and every other path of the stop rule.
- The unit criterion and verificationCommand; editing unit statuses by hand.
- Merge and push - only on the owner's explicit command.

## Review Rule

Medium tier: `/review` before the multi-file commit and a targeted independent checker from a
fresh session and a different model/provider (gpt-5.6-sol pre-PR). If the diff touches an area
outside allowed scope, pause and reclassify the task before continuing.
