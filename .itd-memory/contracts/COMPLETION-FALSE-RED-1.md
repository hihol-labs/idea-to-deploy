# Task Contract — COMPLETION-FALSE-RED-1 completion gate without false red layers

- **Root cause:** the completion signals judge one Bash call as one outcome keyed by its command
  text. `outcome_from` reads the LAST echoed `EXIT: N` as authoritative, so the designed exit 2 of
  `scripts/itd_stop_rule.py --check-binding` (`NO_ACTIVE_UNIT` / not aligned) echoed before a green
  aggregate turned the whole call red; `_layer_status` keeps the latest run PER COMMAND TEXT, so a
  red of a one-off command (RED-first copy in the scratchpad, a heredoc mutation patch, a compound
  probe) can never be repeated or overwritten and outlives every later green run of the same oracle;
  the strict path (`runtime_evidence_status`) counts every red of the session. There was no way to
  declare a mutation run, whose red is the expected result. COMPLETION_BYPASS was needed on four of
  five commits of TIER-WORDING-2 and STOPRULE-STUB-1 (BACKLOG P2 2026-10-01 items a/b; P2
  2026-09-23 item a).
- **Scope (narrowed by the owner 2026-10-02 after the stop rule REDESIGN_OR_DISCARD on Sol s1-s6):**
  only the declared exit 2 of `scripts/itd_stop_rule.py --check-binding`. `completion_lib` cuts the
  `EXIT: 2` line before `outcome_from` in exactly one literal form
  `sh skills/_shared/itd_py.sh scripts/itd_stop_rule.py --check-binding; echo "EXIT: $?"` when the script
  proved it ran (exactly one `BINDING <STATE>` line before the only `EXIT: N` line) and the hook,
  rerunning the script with its own interpreter in the project root, got the same code and BINDING line, there is no `&&`/`||` and no second `$?`; the signal carries `expected_exit`. The expected red
  of a mutation run and the supersede of a one-off red moved to COMPLETION-SUPERSEDE-1 (execution
  evidence, not command text). The gate and the signals hook are unchanged.
- **Verification Standards:** the unit verificationCommand exits 0; the new oracle
  `tests/verify_completion_false_red.py` is RED on the hooks of 9a7ce8e (5 failed, 39 passed; log
  `.itd-memory/verification-loop/reports/COMPLETION-FALSE-RED-1-red-first.log`, sha256
  f8d0fbd836ec2a2c) and GREEN after (44 passed); `--mutations` kills 11 of 11 mutants;
  `tests/verify_completion_gate.py` and `tests/verify_completion_adversarial_corpus.py` stay green; high
  route - `/review`, full independent checker, Sol pre-PR.
- **Exclusions:** `outcome_from` and its regexes, every veto of the gate, the strict path, the signals
  hook, any form other than the literal, COMPLETION-SUPERSEDE-1 scope.
