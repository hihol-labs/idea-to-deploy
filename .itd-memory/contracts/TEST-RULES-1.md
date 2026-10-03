# Task Contract — TEST-RULES-1 /test Step 5.5: unique mutation marker and escaped fixtures

- **Root cause:** two route traps had no rule in `/test` Step 5.5 (refute pass).
  (1) A mutation marker that repeats in the mutated file makes the mutant land on the first copy or
  not apply at all, so the run proves nothing: on STOPRULE-STUB-1 the same `activeFollowup` type
  check sat in `machine_ready_binding` too and the mutant did not apply (BACKLOG P2 2026-10-01, trap
  (c) of the STOPRULE-STUB-1 list; DECISIONS 2026-10-01 STOPRULE-STUB-1 ledger-close, lesson 3).
  (2) On TIER-WORDING-2 the file-write tool decoded escape sequences, so invisible characters of
  oracle fixtures (U+00A0, U+3164, curly quotes) landed in the file as the characters themselves and
  had to be restored by a script (BACKLOG P2 2026-10-01, TIER-WORDING-2 trap f).
- **Scope:** two bullets in `skills/test/SKILL.md` Step 5.5 - the unique-marker rule (`count == 1`
  checked by the mutation helper before applying) and the escaped-fixture rule (escape sequences
  written by a script, the written bytes read back with Python); the new doc-contract oracle
  `tests/verify_test_skill_rules.py` (bullet-scoped: each rule is read from the one Step 5.5 bullet
  that names it) wired into `tests/run-all.sh` and `.github/workflows/meta-review.yml`.
- **Verification Standards:** the unit verificationCommand exits 0; the oracle is RED on the
  pre-edit bytes of main dec2218 (0 passed, 8 failed; log
  `.itd-memory/verification-loop/reports/TEST-RULES-1-red-first.log`, sha256 5d9bb9d644e66b67) and
  GREEN after (8/0); 10 mutations of the skill text and the wiring on isolated copies are lethal
  (the helper refuses a marker with count != 1), the unmutated control copy is green;
  `tests/verify_refute_fleet.py` stays green (19/0); `tests/verify_runall_drift.py` 121/0;
  `tests/meta_review.py` PASSED; `tests/build_impact_graph.py --check` exit 0; low route - `/review`
  before the multi-file commit, machine-only adjudication with receipt legs `unit`, `meta-review`,
  `ledger-state` (equal to the `oracleIds` of the acceptance criteria).
- **Exclusions:** a shared mutation-helper module in code, the completion-gate supersede rule for a
  one-off red (BACKLOG P2 item b), the other steps of `/test`; the other pending units of the goal.
