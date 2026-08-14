# Scope Lock — S7-EVIDENCE: pre-PR candidate of fix/s7-transport-sync-debts

## Current Task

Publish branch fix/s7-transport-sync-debts (S7): four GPG-004 adjudication
debts closed as verified units on HEAD's ancestry (S7-U1 non-finite timeout,
S7-U2 relative Windows-wrapper cwd, S7-U3 POSIX descendant reap — riskTier
high, S7-U4 sync manifest + bytecode drift), plus the evidence commit that
re-signs the three efficacy legs on the final producer bytes. This claim
(S7-EVIDENCE:general-review) rides riskTier high — it publishes security
containment changes and replaces signed efficacy evidence. Sealed in
`.itd-memory/contracts/S7-EVIDENCE.md` and the acceptance contract
activeFollowup.

## Candidate composition (allowed zones)

- `benchmarks/independent-review-efficacy/results/wsl.json`,
  `windows.json`, `u12-cross-vendor-wsl.json` — round-2 re-signed legs on
  the final tree; round-1 red run archived (never discarded) in
  `.itd-memory/efficacy-evidence/s7-round1/`.
- `BACKLOG.md` — the reviewer false-positive class entry produced by the
  round-1 red (declared candidate content, not drive-by).
- `HANDOFF.md` — recovered re-mint parameters (key locations, codex pins,
  maker/reviewer pairing rules).
- `.itd/ACCEPTANCE_CONTRACT.json` — activeFollowup rotated to
  S7-EVIDENCE:general-review with the four-oracle coverage matrix
  (meta-review, producer-oracle, sync-oracle, efficacy).
- `.itd/SCOPE_LOCK.md` — this file.
- `.itd-memory/STATE.json` (force-added ledger) — currentUnit
  S7-EVIDENCE verified, riskTier high.

- `tests/run-live-model-benchmark.py`, `tests/verify_live_model_benchmark.py`
  — bounded provenance fix from the r3 route finding (2026-08-14): the prose
  reason claimed "bounded recovery" whenever attempts[] had a devils-advocate
  phase entry, contradicting recoveryTriggered; the verifier now enforces
  reason/flag agreement.
- `tests/fixtures/live-model-evidence/**` — the declared second commit of the
  two-commit acceptance: any methodology change burns the benchmark tree pin
  by construction, so a fresh live run is recorded on the clean committed
  tree and added as fixtures. By that same construction the recorded run
  attests the PARENT tree of the evidence commit, never the evidence commit
  itself (precedent PR #193/#195/#199/#201).

## Forbidden change areas

- Any production code (`skills/`, `scripts/`, `hooks/`, `tests/` logic) —
  the four code units are already committed and adjudicated on this branch;
  this candidate is evidence + bookkeeping only.
- `.itd-memory/verification-loop/keys/`, host-owned inputs, the archived
  round-1 evidence.
