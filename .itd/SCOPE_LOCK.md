# Scope Lock — S6-SCRUBBER: residual-credential detector precision

## Current Task

Close unit S6-SCRUBBER (queue position after S5/U17; source BACKLOG.md:166,
incident U16 2026-08-11): a bounded precision fix of the residual-credential
detector — ordinary parser code (a token-named variable assigned from
`tokens[position]`) and prose quoting such a line verbatim must stop
refusing review routes — plus
alignment of the free-reviewer producer onto scrubbed-text detection, and
the forced live re-mint of the three signed efficacy legs whose
`producerSha256` pin the producer edit burns. riskTier: high (the change
narrows a security detector), sealed in STATE.currentUnit and
`.itd-memory/contracts/S6-SCRUBBER.md`.

## Candidate composition (allowed zones)

- `skills/_shared/itd_external_reviewer.py` — value-capture groups
  (`quoted`/`bare`/`continued`) in `RESIDUAL_CREDENTIAL_RE`;
  `_BENIGN_EXPRESSION_RE` (a value that is PURELY one code expression —
  dotted call, subscript, `${…}`/`$(…)`/`$var` — is not a literal
  credential; trailing prose backticks stripped); filtering loop in
  `contains_residual_credential`. NOT via SAFE_REFERENCE_PATTERNS (masking
  hides literal call-arguments from the other detectors and masked spans
  are restored verbatim into outgoing text).
- `skills/_shared/itd_free_reviewer_producer.py` — `_safe_review_text`
  detectors run on `clean`, matching broker/`build_candidate` and the
  route's own «redaction is not a finding» contract.
- `tests/verify_scrubber_precision.py` — new RED-first verifier (30 checks
  after the r5/r6 route findings grew the corpus: quoted call-lookalike and
  expression-wrapper true positives):
  FP corpus with true-positive antipair per exclusion; producer clean-text
  contract; end-to-end fail-closed proof.
- `tests/verify_free_reviewer_producer.py` — re-pins to the new contract:
  neutralisable credentials redacted+proceed; the unneutralisable shape (a
  password-named assignment whose bare value `abcd#efgh2026` carries `#`,
  where scrub stops and the detector does not) refuses; no-reply smuggling
  asserts neutralisation before egress.
- `tests/run-all.sh` — CORE registration.
- `benchmarks/independent-review-efficacy/results/*.json` — three legs
  re-minted live on the final producer bytes (wsl + u12 cross-vendor on
  WSL; windows via powershell interop). Retries only on typed exit 3 from
  the signed checkpoint; resampling a reviewer miss is forbidden (A21).
- Bookkeeping: `BACKLOG.md`, `HANDOFF.md`, `.itd-memory/STATE.json`,
  `.itd-memory/HANDOFF-S6-SCRUBBER.md`, `.itd-memory/contracts/S6-SCRUBBER.md`,
  `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md`, `.itd/ACCEPTANCE_CONTRACT.json`.
- Follow-up commit of this same unit (two-commit acceptance below):
  `tests/fixtures/live-model-evidence/**` — the re-recorded live benchmark
  run replacing the burned pin (latest.json + one new run directory).
  Corpus conventions a reviewer needs to validate it: (a) the run records
  the METHODOLOGY BENCHMARK on `fixture-03-cli-tool` — an nginx-log-analysis
  CLI project — so its transcript legitimately documents a /blueprint +
  devils-advocate run over that fixture, not this unit's diff; (b)
  `transcript.jsonl.gz` is genuine gzip on disk (magic 1f 8b) and appears as
  plaintext JSONL in the review diff only because of the declared-only
  `.jsonl.gz` transparent-review textconv (a GPG-001 invariant) — the
  run-report's transcriptGzipSha256 binds the compressed bytes and is
  machine-verified by `verify_live_model_benchmark --require-evidence`
  (107/0 on this run); (c) the recorder's tail-truncation of the final
  in-progress item is a known recorded artefact
  (`tests/ROOT_CAUSE-live-model-benchmark-partial-output.md`) — completion
  is proven by the machine-verified run-report, not by the transcript tail.

## Two-commit acceptance (inherent, precedent PR #193/#195/#199)

Edits under `skills/_shared/` burn the live-model benchmark's
`methodologyTreeSha256` by construction. Commit 1 lands the fix with the old
evidence honestly red under `--require-evidence` (COMPLETION_BYPASS names
exactly this documented inherent red); the benchmark is then re-recorded on
the clean committed tree and commit 2 re-pins the evidence. Neither commit
weakens the oracle.

## Out of scope (honest limits)

- No weakening of scrub(), SAFE_REFERENCE_PATTERNS, the high-confidence or
  entropy detectors; every benign exclusion carries a literal antipair.
- Frozen benchmark cases/thresholds untouched (`manifestSha256` stable).
- No new skill/agent/hook; counts unchanged.
- The queued BACKLOG follow-ups (matcher category wording, benchmark
  provenance polish, sync-manifest gap, …) untouched.

## Machine-oracle shape

`s6-verifier=python3 tests/verify_scrubber_precision.py` +
`producer=python3 tests/verify_free_reviewer_producer.py` +
`efficacy=python3 tests/verify_independent_review_efficacy.py
--expected-keyring-sha256-file
.itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256` +
`quick-suite=bash tests/run-all.sh --quick`. Risk tier: high — full fresh
adjudicated independent review of the exact staged candidate before commit.

Base for the candidate: main `84742fb` (merge of PR #200).

## Closure (2026-08-13)

PR #201 merged as `300fcab` (base `84742fb`; commits `afe8748` fix +
`fb71ba0` live evidence re-pin — run `20260813T164516Z-916e7a92`,
`--require-evidence` 107/0), CI green (Gate 1 + windows-verify). Fresh
post-merge evidence on merged main: verify_scrubber_precision 30 PASSED,
verify_review_broker 741, verify_free_reviewer_producer 144,
verify_independent_review_efficacy PASSED (hostParityVerified true), quick
`DONE fails:none`. Unit `S6-SCRUBBER` is `verified` in STATE; acceptance
activeFollowup closed (adjudication receipts `c231e0239981f339/a1` and
`95bbe377e5b8daea/a1`; 14 producer rounds, two real detector findings —
quoted call-lookalike r5, expression-wrapper smuggling r6 — closed
RED-first and shipped in the final grammar).

This ledger-close candidate stages exactly three tracked files:
`HANDOFF.md`, `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/SCOPE_LOCK.md`, plus
the force-added `.itd-memory/STATE.json`; it carries its own machine
receipt and adjudicated route bound to its own staged tree.
