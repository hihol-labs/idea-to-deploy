# Scope Lock — S3-ADVOCATE: real devils-advocate phase in the live benchmark

## Current Task

Close unit S3-ADVOCATE (S3 in PLAN-CLOSEOUT-2026-08-11; BACKLOG live-model
fixture-hardening defect): the recorded benchmark run substituted the Devil's
Advocate subagent invocation with an inline self-critique because headless
transports cannot spawn Claude-native subagents (`claude -p` is currently
401-blocked by account review; `codex exec` has no subagent mechanism). The
fix keeps the benchmark headless-reproducible: after the snapshot oracle
passes, the harness runs the REAL `agents/devils-advocate.md` definition in a
SECOND fresh session of the same transport (codex `--ephemeral` / claude
`--no-session-persistence` = isolated context, the subagent semantics), and
the review artifact is validated, archived and hash-bound into the run report.
`/blueprint`'s in-session Devil's Advocate step stays as designed for
interactive use; this unit changes only the benchmark scenario.

## Allowed zones

- `tests/run-live-model-benchmark.py` — ADVOCATE_* constants,
  `advocate_prompt()`, the phase-2 block in `run()` (after the snapshot
  oracle; fail-closed on missing agent, exhausted time/byte budget, non-zero
  exit, missing/insubstantial artifact), artifact archiving + hashing, the
  `devilsAdvocate` report block, and blueprint-only `attemptCount`/
  `recoveryTriggered` (the phase entry stays in `attempts[]` solely for exact
  transcript segment coverage, marked `"phase": "devils-advocate"`).
- `tests/verify_live_model_benchmark.py` — `verify_evidence` (runs only under
  `--require-evidence`, as CI invokes it): blueprint/advocate attempt split,
  exactly-one-phase-last check, archived-hash set = required ∪ {advocate
  artifact}, and five fail-closed advocate checks (mode, agent digest pinned
  to the current tree, artifact retained + hash-pinned, substantive review).
- `tests/fixtures/fixture-03-cli-tool/live-prompt.md` — the self-critique
  paragraph is replaced: the adversarial review is phase 2, run by the
  harness; inline substitution and reviewer claims are forbidden in-session.
- `tests/fixtures/live-model-evidence/latest.json` and the new
  `tests/fixtures/live-model-evidence/runs/20260813T090330Z-64df7624/` — the re-recorded
  evidence (second commit of this unit, run on the clean committed tree per
  DECISIONS 2026-08-13).
- `BACKLOG.md` — the live-model fixture-hardening item closes with pointers
  (second commit).
- `.itd/SCOPE_LOCK.md`, `.itd/ACCEPTANCE_CONTRACT.json`,
  `.itd-memory/STATE.json` — this unit's contracts and the currentUnit
  advance from ledger-closed S2-FLAKE.

## Out of scope (honest limits)

- Claude-native subagent transport in headless mode: blocked externally (401
  account review); when it returns, the anthropic path of the same phase-2
  machinery applies unchanged.
- The other two recorded-run defects of the BACKLOG item (fail-open
  self-validation visible in the transcript; no originating user request in
  the capture) are addressed only to the extent the new prompt/verifier
  contract covers them; anything residual stays in the BACKLOG item history.
- `/blueprint` skill behaviour and its interactive Devil's Advocate step.

## Two-commit acceptance contract (inherent, not an oversight)

This candidate (commit 1: runner/verifier/prompt/contracts) is EXPECTED to
fail CI's `--require-evidence` replay in isolation, and no single-commit
candidate can avoid that: the evidence is source-pinned to the exact runner/
verifier/prompt bytes that recorded it, so re-recorded evidence cannot precede
the code change; and the dirty-state pin (DECISIONS 2026-08-13) forbids
recording evidence while that code change is uncommitted. The unit is
therefore accepted at the PR head after commit 2 (the re-recorded evidence on
the clean committed tree), exactly as the merged PR #193 precedent
(3d4f282 -> 42c168f). Commit 1's own machine oracles are the static harness
contract (`verify_live_model_benchmark` without the flag, 39/39 green on this
candidate) and `tests/meta_review.py`; the operator evidence that the new
replay checks are fail-closed is the exact 10-FAIL run against the old
evidence.

## Commit topology of the recorded evidence (for reviewers of commit 2)

Commit 1 of this unit (`2a8da716de83`) carries the ENTIRE advocate code
change (runner phase 2, prompt, verifier). The evidence run
20260813T090330Z-64df7624 was recorded on that commit's clean tree, so its
`source.revision` = `2a8da716de83` IS the post-code-change commit: the exact
runner/prompt/verifier bytes it pins are the new advocate implementation
(machine-checked — the replay's `source pin matches: benchmarkRunner /
liveVerifier / livePrompt` checks compare the recorded pins against the
CURRENT files and pass 107/107 on this candidate). Commit 2 (this diff, whose
git base is naturally commit 1) adds only the generated evidence plus
BACKLOG/scope documentation; per the dirty-state pin it cannot itself be the
recorded revision, and per the two-commit contract above the evidence can
never cite a commit that does not yet exist.

## Machine-oracle shape

Exact-candidate oracles: `tests/verify_live_model_benchmark.py` (static
harness contract, no flag — the CI-only `--require-evidence` replay goes
green with the re-recorded evidence of commit 2) and `tests/meta_review.py`.
Operator evidence: against the OLD evidence, `--require-evidence` fails on
exactly the new advocate contract (10 FAIL) — the checks are fail-closed,
not decorative.
