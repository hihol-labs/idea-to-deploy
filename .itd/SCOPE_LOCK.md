# Scope Lock — U12: measured independence ladder + re-signed efficacy legs

## Current Task

Close unit U12 (GPG-004; S4 in `.itd-memory/PLAN-CLOSEOUT-2026-08-11.md`):
measure the reviewer-independence ladder — same-vendor versus cross-vendor
detection rate — over the SAME frozen seeded-defect corpus, and record the
outcome in the benchmark and in ADR-007. The unit also confirms that the
reviewer-cardinality canaries (low-reviewer / high-quorum /
duplicate-reviewer-quorum, the exact-equality `minimumIndependentReviewers`
contract) are restored and green — they already live in
`tests/verify_independent_review_efficacy.py` (PC4 restoration), so this
candidate contains NO code change for them, only the recorded confirmation.

Root cause of the red verifier on main 18dc762: PR #191 (`da42644`) changed
the bytes of `skills/_shared/itd_free_reviewer_producer.py` after the
2026-08-10 recordings, so `producerSha256` in all three signed semantic
results became foreign (manifest and runner hashes still matched). The remedy
is live re-signing of the three legs with the current producer bytes — the
same remedy class as after PR #188 (R1 scrub), a known precedent.

## Candidate composition (allowed zones)

- `benchmarks/independent-review-efficacy/results/wsl.json` — re-signed live
  same-vendor leg (maker `gpt-5.6-terra` → reviewer `gpt-5.6-sol`, codex
  0.146.0 pin `2e863156…`, 9/9 cases `attempts=1`).
- `benchmarks/independent-review-efficacy/results/u12-cross-vendor-wsl.json`
  — re-signed live cross-vendor leg (maker `opus`, anthropic-subscription →
  reviewer `gpt-5.6-sol`, 9/9 `attempts=1`).
- `benchmarks/independent-review-efficacy/results/windows.json` — re-signed
  live Windows leg (native `python.exe` 3.12.10 over the UNC repo path,
  codex.exe pin `bc343ba4…`, DPAPI signing key; case 1 recorded, one typed
  UNAVAILABLE transport drop on case 2, resumed from the signed checkpoint —
  accepted typed-exit-3 retry precedent of 2026-08-08; 9/9 `attempts=1`).
- `docs/adr/ADR-007-human-adjudication-of-independent-review.md` — addendum
  «U12: the independence ladder is measured, not asserted» with the measured
  rates and the honest parity conclusion.
- `HANDOFF.md` — S4 transfer packet (diagnosis, exact re-record commands,
  pins); superseded stale v1.96.0 release packet.
- `.itd/ACCEPTANCE_CONTRACT.json` — activeFollowup → `U12:general-review`
  (medium tier).
- `.itd/SCOPE_LOCK.md` — this file.
- `.itd-memory/STATE.json` — currentUnit S3-ADVOCATE (verified, closed) →
  U12 (in_progress → verified on close).

No producer/runner/manifest byte changes: `skills/_shared/*`, `tests/*` and
`benchmarks/independent-review-efficacy/cases.json` are untouched — the
signatures bind to their current committed bytes.

## Measured outcome (the point of the unit)

`tests/verify_independent_review_efficacy.py` exit 0 on this tree:
`status PASSED`, `hostParityVerified true`, `u12IndependenceLadder`:
sameVendor criticalHigh 1.0 / medium 1.0 / cleanFalseBlock 0.0;
crossVendor 1.0 / 1.0 / 0.0. Parity, not superiority: the ladder order
stays cross-vendor-first on the correlated-blind-spots argument; the
cross-vendor leg is recorded, deliberately not thresholded against the
same-vendor leg.

## Out of scope (honest limits)

- The 9-case corpus cannot surface correlated same-vendor blind spots; the
  addendum says so explicitly instead of overclaiming.
- `.itd-memory/GPG-004_UNIT_PLAN.json` and `PLAN-CLOSEOUT-2026-08-11.md` are
  git-ignored ledger files — updated locally (U12 → verified, S4 → DONE),
  not part of the committed candidate.
- Residual scrubber precision work (S6) and the other PLAN-CLOSEOUT queue
  items are untouched.

## Machine-oracle shape

`oracle=sh skills/_shared/itd_py.sh tests/verify_independent_review_efficacy.py
--expected-keyring-sha256-file
.itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256` — the
host-owned keyring pin is a declared input (host-provisioned, git-ignored),
plus `bash tests/run-all.sh --quick` green on the same tree
(`DONE fails:none`, 2026-08-13).

Base for the candidate: main `18dc7620520f7ab2eb6666120c91b7a4bb49d44d`.
