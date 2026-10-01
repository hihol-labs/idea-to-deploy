# Task Contract — STOPRULE-STUB-1 stop-rule live binding recognises the closed contract

- **Scope:** `scripts/itd_stop_rule.py`, `live_policy_binding`: when `activeFollowup` of the
  acceptance contract is exactly the closed-contract record that `scripts/itd_closure_delta.py`
  writes (`{unitId: "", status: "none", note?}`, the same key set as its `FOLLOWUP_EMPTY_KEYS`,
  `note` of any type as there - review r1 and checker c1) and
  `STATE.currentUnit` is absent or carries a terminal status of the unit lifecycle (the same set as
  `itd_unit_lifecycle.TERMINALS`), the binding returns `state: NO_ACTIVE_UNIT`, `aligned: false`,
  empty unit ids and zero criteria, instead of raising. Every result gains a `state` field
  (`ALIGNED`, `ROUTE_DEFECT` or `NO_ACTIVE_UNIT`). `--check-binding` prints `BINDING
  NO_ACTIVE_UNIT` with a WHY and a FIX line and exits 2 (no review may start). Any other shape keeps
  the existing refusal: an empty unit id with another status, missing status or extra keys, a
  blank unit id, and the closed record while `STATE.currentUnit` is in progress or has no status.
  Owner decision 2026-10-01, variant A; variant B (closure-delta accepts a stub naming the closed
  unit) is rejected because the binding would report ALIGNED for a closed unit.
- **Verification Standards:** the unit verificationCommand exits 0; the new oracle
  `tests/verify_stop_rule_closed_contract.py` is RED on the pre-fix bytes of 58ded36 (recorded) and
  GREEN after, with `--mutations` all lethal; on a copy of the tracked tree carrying the closed
  record and a verified `STATE.currentUnit` `tests/verify_stop_rule.py` exits 0;
  `tests/verify_closure_delta.py` stays green; `tests/build_impact_graph.py --check` exit 0;
  `tests/run-all.sh --quick` last line `DONE fails:none`; medium route - `/review` before the
  multi-file commit, a targeted fresh-session checker, gpt-5.6-sol before the PR; machine receipt
  legs named `unit`, `meta-review`, `ledger-state` (they must equal the `oracleIds` of the
  acceptance criteria).
- **Exclusions:** `scripts/itd_closure_delta.py`; the stop-rule policy and its frozen binding
  invariants; `machine_ready_binding` and the history verdicts; the aggregate
  `tests/verify_route_debts.py` is not in the unit command (between units only - checked on main
  after the ledger-close and recorded in the closure evidence).
