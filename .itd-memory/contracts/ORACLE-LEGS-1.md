# Task Contract — ORACLE-LEGS-1 machine receipt: the legs must cover the oracleIds of the unit

- **Root cause:** `skills/_shared/itd_verification_loop.py machine` never read the acceptance
  contract. The coverage rule "every `reviewEvidence.oracleIds` entry of the active unit's criteria
  is a run id of the machine receipt" lived only in the Sol producer
  (`itd_review_evidence.coverage_matrix`: "<criterion> oracle <id> is missing"), so a receipt minted
  without such a leg was rejected after the mint and after a reviewer run had been paid for
  (TIER-WORDING-2, committed-head p1; BACKLOG P2 2026-10-01 item (d)).
- **Fix (criterion and implementation notes approved by the owner 2026-10-03 before activation):**
  `assert_oracle_legs_declared` runs in `command_machine` after the candidate is fixed and before
  the declared inputs are sealed and the first leg runs.
  - The contract is read from the candidate tree (`git cat-file blob <reviewedTree>:.itd/ACCEPTANCE_CONTRACT.json`),
    so the check sees the same bytes the producer later reviews, not the checkout.
  - Checked only when the claim equals the open `activeFollowup.unitId` (`followup_is_closed` false).
    Criteria are selected by the shared `itd_review_evidence.active_criteria` (the producer's
    selector), in any status; criteria without `reviewEvidence` are skipped; a declared but
    malformed `reviewEvidence`/`oracleIds` refuses with the producer's `_string_list` rule (Sol s1). A follow-up
    without `reviewPolicy` is checked too (/review r1 finding 2, see DECISIONS).
  - The producer's rules (`itd_review_evidence.py`) are compiled from the source bytes, not imported:
    a `__pycache__` entry that still matches size and mtime is never run (Sol s3).
  - Every missing pair is named in one `UNVERIFIED` refusal (`<criterion> oracle <id> is missing`),
    exit 1, no receipt written, no leg run. Malformed explicit ownership refuses the same way.
  - Not checked (mint as before): a `:general-review` claim, a foreign unit, a closed follow-up, a
    candidate tree without the contract, a contract that is not valid JSON (the producer reports it).
- **Verification Standards:** the unit verificationCommand exits 0; the new oracle
  `tests/verify_machine_oracle_legs.py` is RED on `d8dfed2` (18 failed, 7 passed of 25, sha256 459f983fb7f8626c; log
  `.itd-memory/verification-loop/reports/ORACLE-LEGS-1-red-first.log`) and GREEN after (25 passed);
  `tests/verify_verification_loop.py` (121/0) and `tests/verify_review_evidence.py` stay green;
  `tests/run-all.sh --quick` clean. Medium route - `/review`, targeted checker, Sol pre-PR.
- **Exclusions:** `itd_review_evidence.py` and the producer's own coverage check (kept as the
  second line), the receipt format, leg execution, other subcommands, other units of the goal.
