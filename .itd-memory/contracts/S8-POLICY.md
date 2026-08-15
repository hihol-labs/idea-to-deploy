# Task Contract — S8-POLICY

## Scope
A closed acceptance followup must stop pinning the review coverage matrix; the
S8 followup is closed on that basis. Files: `skills/_shared/itd_review_evidence.py`,
`tests/verify_independent_review_efficacy.py`, `.itd/ACCEPTANCE_CONTRACT.json`,
`BACKLOG.md`, `.itd-memory/STATE.json`.

## Verification Standards
- `python3 -I tests/verify_independent_review_efficacy.py
  --expected-keyring-sha256-file .itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256`
  -> exit 0 with the five new `structural/{closed,open}-followup-*` cases PASS.
- Mutation: reverting the early return turns `closed-followup-verified` RED.
- `python3 -I tests/verify_free_reviewer_producer.py` -> exit 0.
- `sh skills/_shared/itd_py.sh tests/meta_review.py` -> PASSED.
- `bash tests/run-all.sh` -> `DONE fails:none`.
- Fresh-session checker, mode full, own mutation + non-closed-status probe.

## Exclusions
- No verifier accepts more input than before; only WHEN the matrix applies changes.
- An OPEN followup keeps every criterion (pinned by two tests).
- Live evidence under `tests/fixtures/live-model-evidence/` untouched.
