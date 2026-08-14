# Scope Lock — S8: pre-PR candidate of fix/s8-contract-pin-a19

## Current Task

Publish branch fix/s8-contract-pin-a19 (S8) from main 50677ce. Four code
units, two evidence units and one contract unit, each closed as verified with
its own Verification Loop adjudication receipt before its commit. The claim
rides riskTier high: it changes reviewer-isolation classification, replaces
signed efficacy evidence, and re-declares the coverage matrix that gates
publication. Sealed in `.itd-memory/contracts/S8-*.md` and in the acceptance
contract `activeFollowup` (unitId `S8`, five criteria S8-1..S8-5).

Unlike the S7 candidate, this one is NOT evidence-only: the code units are
part of it, because they were never published. The route reviews the whole
branch against main.

## Candidate composition (allowed zones)

- `.itd/VERIFICATION_CONTRACT.json` — S8-U1: the `independent-review-efficacy`
  entry regains the required `--expected-keyring-sha256-file` host input.
  `trustedVerifierPaths` deliberately unchanged (the pin is git-ignored and
  every trusted path must be a tracked clean blob).
- `tests/verify_quick_regression.py` — S8-U1: the CORE aggregator declares
  host inputs (`HOST_INPUT_ARGS`: `args` and `requiredFiles` separately) and
  reports a missing one as a failure. This is the actual `itd_hygiene close`
  blocker, reached via SESSION_EXIT_CONTRACT -> docs/VERIFICATION_CONTRACT.json.
- `tests/verify_machine_oracle.py`, `tests/verify_gate_registry_binding.py`
  — S8-U1 anti-drift: the aggregator table must match `run-all.sh` by name,
  flag and path value, and the contract entry must keep the flag while never
  declaring the git-ignored pin as a trusted verifier path.
- `tests/verify_live_model_benchmark.py`, `tests/run-live-model-benchmark.py`
  — S8-U2: the methodology tree pin excludes exactly what Git ignores, in the
  verifier AND in the producer that writes the pin, and raises when Git cannot
  answer. Both copies are in scope by construction: changing one alone
  desynchronizes recorded evidence from its own verifier.
- `tests/verify_tree_pin_debris.py` (new), `tests/run-all.sh` — S8-U2: the
  behavioural oracle for the above, registered in CORE.
- `skills/_shared/itd_free_reviewer_producer.py`,
  `tests/verify_free_reviewer_producer.py` — S8-U3 (BACKLOG A19): a Codex
  error ITEM is a typed transport failure, not a reviewer tool call; the
  code-mode-disabled advisory is recognized as the denylist working; the
  refusal names the observed item types and stays fail-closed.
- S8-U4-CRLF, same two files: the advisory exemption must accept only a
  PRINTABLE one-line message. Two independent-review rounds found two holes in
  the narrowing — an LF-only test let CR through, a line-splitting test let NUL
  through — so the predicate is now `advisory.isprintable()`, which is false
  for every C0/C1 control and Unicode separator alike.
- `benchmarks/independent-review-efficacy/results/{wsl,windows,u12-cross-vendor-wsl}.json`
  — S8-EVIDENCE: the three signed legs re-minted live, because
  `verify_independent_review_efficacy.py:343` pins the producer bytes S8-U3
  changed.
- `tests/fixtures/live-model-evidence/**` — S8-RERECORD: a fresh live H4 run,
  because the S8-U2 producer edit burned the runner/adapter source pins and
  the S8-U3 edit moved the methodology tree pin. Recorded on the clean
  committed tree; by construction it attests the PARENT tree of its own
  evidence commit (precedent PR #193/#195/#199/#201).
- `.itd/ACCEPTANCE_CONTRACT.json` — S8-FOLLOWUP: `activeFollowup` rotated to
  `S8` with the five-criterion coverage matrix (gate-registry-binding,
  machine-oracle, tree-pin-debris, producer-oracle, efficacy,
  evidence-replay). It adds `generated-artifact-freshness` and `host-parity`
  to the S7 impact set and drops none.
- `BACKLOG.md` — items closed by S8 (A19, the H4 tree-pin debris) and items
  deliberately recorded rather than fixed inside a scoped unit.
- `.itd/SCOPE_LOCK.md` — this file.
- `.itd-memory/STATE.json` (force-added ledger) — the unit ledger as it
  advanced through S8-U1 → S8-U2 → S8-U3 → S8-EVIDENCE → S8-RERECORD →
  S8-FOLLOWUP → S8-U4-CRLF, each recorded verified with its receipt digest.

## Forbidden change areas

- Any production or test code NOT listed above — in particular the transport,
  the auth/rollout provenance checks, the other reviewers (Gemini,
  Antigravity, Copilot), `DISABLED_TOOL_FEATURES`, and the frozen efficacy
  case corpus.
- `.itd-memory/verification-loop/keys/`, host-owned inputs under
  `.itd-memory/host-inputs/`, and any archived prior evidence.
- Loosening any check to make a gate pass: the S8 findings were closed by
  fixing the code or by recording the residual in BACKLOG, never by widening
  what a verifier accepts.
