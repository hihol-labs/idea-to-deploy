# Task Contract — GOALVERIFY-FAILPATH-1 clean failure path of the goal harness

- **Root cause:** RSI-DEBT-3 (cd9979c) taught `skills/goal/scripts/itd_goal_verify.py` to record
  a compound `A && B` verificationCommand one line per top-level command; that branch binds
  `evidence, rc = run_compound_verification(...)` and never binds `output`, while the failure path
  (since v1.45.0) ends with `print(decisive_line(output))`. Every failed compound command
  therefore died with `UnboundLocalError: cannot access local variable 'output'` and a traceback
  after the `FAILED` line (live: the TIER-WORDING-2 route, BACKLOG P2 2026-10-01 item a).
- **Scope:** the compound branch of `cmd_verify` binds `output = evidence`, so the decisive line
  of a failed chain is the per-command record of the command that stopped it (`&&`
  short-circuits, so it is the last line). The single-command and no-sh branches are unchanged.
- **Verification Standards:** the unit verificationCommand exits 0; the new oracle
  `tests/verify_goal_verify_failpath.py` is RED on the pre-fix bytes of 65867c2 (2 failed, 25
  passed: both compound cases raise; log
  `.itd-memory/verification-loop/reports/GOALVERIFY-FAILPATH-1-red-first.log`, sha256
  49039f9c0b9caaf9) and GREEN after; mutations of the fix (`output = ""`, the first leg instead of
  the record) are lethal; `tests/verify_goal_tools.py` and `tests/verify_goal_verify_shell.py`
  stay green; `tests/build_impact_graph.py --check` exit 0; low route - `/review` before the
  multi-file commit, machine-only adjudication with receipt legs `unit`, `meta-review`,
  `ledger-state` (equal to the `oracleIds` of the acceptance criteria).
- **Exclusions:** `run_compound_verification`, `decisive_line`, the evidence format of the
  ledger and every success path of the harness; the other six units of the goal.
