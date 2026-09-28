# Task Contract — CLOSURE-DELTA-1 closure records are the only delta after verification

- **Scope:** `scripts/itd_closure_delta.py --receipt <adjudication receipt> --tree <tree-ish>`
  (stdlib): verified tree = `candidate.reviewedTree` of a PASSED receipt. The etalon comes from
  the harness (owner decision 2026-09-29): the reviewed tree is extracted into a temporary copy,
  its own `skills/goal/scripts/itd_goal_verify.py` performs the verify transition of the receipt's
  unit (tier `low`, command `exit 0`), and the candidate's GOAL.json, STATE.json and appended
  events must equal what the harness wrote after normalizing only timestamps (not before the reviewed
  tree's `updatedAt` minus a 60 s clock-skew allowance), event id/transaction, evidence, riskTier and
  the receipt binding; `handoffState` is never normalized (the harness writes it only for deadline
  units); the receipt's `candidate.riskTier` must be the reviewed unit's tier. Other records keep their rules: the move of the
  unit's `activeFollowup` to the end of `closedFollowups` in `.itd/ACCEPTANCE_CONTRACT.json`,
  whole UTF-8 lines appended at the end of `.itd/DECISIONS.md`, whole UTF-8 lines inserted into
  `BACKLOG.md` (owner decision 2026-09-28); ledger records change only for a unit verified in the
  later GOAL.json; the later ledger passes `scripts/validate_state.py` of the reviewed tree. Any
  other path, add, delete or mode change is rejected. Exit 0 silent / 1 violation with path + WHY +
  FIX / 2 input error (also: reviewed tree without STATE.json; a deadline or sealed unit, refused by
  the tool itself before the substitution; a harness run over `ITD_CLOSURE_DELTA_TIMEOUT` seconds,
  default 600, or one that cannot start); no arguments - quiet no-op. New oracle `tests/verify_closure_delta.py` in run-all.
- **Verification Standards:** the unit verificationCommand exits 0; the oracle is RED on a
  detached worktree of `ed47135` and GREEN after; it drives one real transition of the goal
  harness in a temporary repository whose tree carries the harness and validator of this checkout
  (producer-first); `tests/build_impact_graph.py --check` exit 0; `tests/run-all.sh --quick` last
  line `DONE fails:none` except the known calendar-red `verify_harness_docs_freshness`; medium
  route - `/review`, targeted fresh checker, adjudication receipt, mandatory pre-PR reviewer.
- **Exclusions:** receipt integrity (that is `itd_verification_loop.py check`); wiring into the
  review cache / ledger-close route / RELEASE_RUNBOOK; `.itd/SCOPE_LOCK.md` stays outside the
  closure delta; working-deadline and sealed (bounded) units and goal ledgers without a STATE
  mirror (the harness cannot replay them in a copy - exit 2, recorded in BACKLOG).
