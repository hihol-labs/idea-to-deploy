# Scope Lock — R1: redaction is not a finding (producer review scrub contract)

## Current Task

Retro R1 (2026-08-10, user-approved): `_safe_review_text()` in the free
reviewer producer treated ANY scrubber redaction as a blocking finding, so a
public `*@users.noreply.github.com` address sitting in the plugin manifests
blocked every candidate whose diff context touched them (route findings
r33-r35 — three reproductions on unit U16). Fix the contract: the reviewer
receives the SCRUBBED text; only a detector hit (high-confidence secret,
residual credential, high-entropy token) refuses the route, fail-closed.

## Allowed zones

- `skills/_shared/itd_free_reviewer_producer.py` — `_safe_review_text` only:
  drop `redactions or clean != text` from the refuse condition, return
  `clean` instead of `text`.
- `tests/verify_free_reviewer_producer.py` — regression tests in both
  directions (see Acceptance).
- `benchmarks/independent-review-efficacy/results/{wsl,windows,
  u12-cross-vendor-wsl}.json` — the three signed efficacy legs re-minted
  over the patched producer (its bytes are bound by `producerSha256`).
- `.itd/SCOPE_LOCK.md` (this contract).
- **Visible amendment (user decision A, 2026-08-10):**
  `.itd/ACCEPTANCE_CONTRACT.json` — the stale GPG-004 evidence-first
  `activeFollowup` block is REMOVED. GPG-004 has been verified and merged
  (126a1f0) for two days; the leftover `"status": "in_progress"` follow-up
  forced every later review route to carry GPG-004 ladder evidence
  (`active unit and machine evidence differ` on this very candidate). R1 is
  an ordinary retro bugfix reviewed through the standard semantic route
  (high tier, cross-vendor); no new evidence-first unit is opened.
  `.itd-memory/STATE.json` — unit bookkeeping via `itd_unit_log.py`
  (R1-SCRUB activated, riskTier high).
- **Visible amendment 3 (CI Gate 1 replay + route r6 findings, 2026-08-11):**
  `tests/fixtures/live-model-evidence/latest.json` and
  `tests/fixtures/live-model-evidence/runs/20260810T230942Z-b733757e/` —
  a fresh live H4 benchmark run. CI's replay step
  (`verify_live_model_benchmark --require-evidence`) pins the methodology
  tree hash, so ANY candidate touching `skills/_shared/` must carry a fresh
  H4 run pinned to its own tree (release v1.96.0 precedent); PR #188's
  Gate 1 failed on exactly this before the run was added. The run's
  transcript is a `blueprint` generation benchmark BY DESIGN (fixture-03 is
  the frozen H4 corpus — it evidences methodology-tree freshness, not R1
  semantics), and `transcript.jsonl.gz` is genuine gzip on disk (magic
  `1f8b`); reviewers see its DECODED text through the declared-only
  transparent representation, which also makes total review bytes exceed
  the raw diff byte count. The run was minted on the clean committed tree
  (empty status pin); one failed sample (missing guide literal) and one
  superseded dirty-pinned sample stay as untracked local artifacts in the
  main checkout, recorded in session memory.
- **Visible amendment 2 (independent route finding r2, 2026-08-10):**
  `skills/_shared/itd_external_reviewer.py` —
  `contains_high_confidence_secret` additionally checks per-line
  whitespace-collapsed variants. The route correctly showed that R1 widens
  the pre-existing whitespace-split hole in one composite case (split
  credential + redactable contact in the same candidate: the old
  any-redaction refusal blocked it by accident). Detection-only, line-scoped,
  never rewrites reviewer text; lives in the scrubber (loaded live) so the
  signed efficacy legs' producerSha256 binding stays intact.

## Acceptance (this slice)

1. A redacted contact detail no longer refuses the route and reaches the
   reviewer as `[REDACTED-EMAIL]`; surrounding candidate text intact.
2. Fail-closed unchanged, mutation-tested: OpenAI-style key, AWS access key,
   high-entropy blob, and a secret smuggled in front of
   `@users.noreply.github.com` all still refuse
   (`verify_free_reviewer_producer` 134 checks green).
3. All three efficacy legs re-minted with live model runs and signed by the
   host key `gpg003-local-producer-20260803`:
   wsl parity (terra→sol) PASSED, windows parity (terra→sol, native Windows
   python via WSL interop + DPAPI envelope) PASSED, u12 cross-vendor
   (opus→sol) PASSED. `verify_independent_review_efficacy` PASSED with
   hostParityVerified true, detection 1.0/1.0, cleanFalseBlockRate 0.0 both
   hosts. Honesty note: the first wsl parity run recorded 2/4 clean cases
   as PASSED_WITH_WARNINGS (pure reviewer variance — all 9 promptSha256
   byte-identical to the previous leg, so the fix did not perturb reviewer
   inputs); one full restart-from-zero was performed per the runner's
   documented anomaly policy (fresh checkpoint, every case re-run, no
   per-case resampling) and recorded as it came.
4. Full `tests/run-all.sh --quick` green.

## Risk tier

high — the change sits on the secret-scrubbing boundary of the independent
review route.

## Out of scope

Reviewing arbitrary private contact details beyond redaction (the redacted
text already never leaves); R3 (ceremonial SKILL_BYPASS) — separate slice;
snapshot `a7` mint and the U16 route — operational steps after this merges;
narrowing the `producerSha256` binding granularity (retro R2) — separate
decision.

## Closure (2026-08-11)

Merged as PR #188 (`a2ce0a3`, implementation commit `0715a6a`). All four
acceptance items verified on the merged `main`, read-only, in this checkout:

1./2. `verify_free_reviewer_producer` — 140 checks PASSED,
   `liveExternalCalls: 0`, `paidApiCalls: 0` (redaction reaches the reviewer
   scrubbed; the four mutation cases still refuse fail-closed).
3. `verify_independent_review_efficacy --expected-keyring-sha256-file
   .itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256` — PASSED,
   `hostParityVerified: true`, wsl and windows both
   `criticalHighDetection 1.0 / mediumDetection 1.0 / cleanFalseBlockRate 0.0`,
   u12 cross-vendor ladder 1.0/1.0/0.0, evidence source
   `real-keyless-model-reports`.
4. `tests/run-all.sh --quick` — `DONE fails:none`.

Ledger: `STATE.json` records R1-SCRUB `verified` (riskTier high) via
`itd_unit_log.py`. The activation event was written 2026-08-10T21:43:44Z
(`evt-unit-1786398224`) inside the isolated worktree
`.claude/worktrees/r1-producer-scrub`, so the main-checkout ledger needed an
explicit `backfill-activation` reconciliation before the pair could close —
recorded as `actor: harness-reconciliation`, not as a fresh activation.

Next operational steps (separate units, not this slice): mint snapshot `a7`
over the patched producer + scrubber, run the U16 route with it, then R3.
