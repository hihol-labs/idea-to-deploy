# Scope Lock — S9: pre-PR candidate of fix/s9-harness-debts

## Current Task

Publish branch `fix/s9-harness-debts` (S9) from main `e3131c9`. Four harness
debts of one class, each an independently reviewed unit with its own contract
under `.itd-memory/contracts/` and its own Verification Loop adjudication
receipt before its commit. The claim rides riskTier **medium**: every unit is a
bounded correctness fix inside tooling this repository already exercises, none
changes the trust model, the maker/checker separation, or what any verifier
accepts. Sealed in the acceptance contract `activeFollowup` (unitId `S9`).

Unit order is **U4 → U3 → U2 → U1**, chosen on a fact rather than a preference:
`METHODOLOGY_TREE_ROOTS` (`tests/verify_live_model_benchmark.py:25-29`) covers
`skills/`, `agents/` and `hooks/`, so U1, U2 and U3 each burn the live-evidence
pin, while U4 lives in `scripts/` and does not. Running U4 first also repairs
the very transport this branch is delivered through. One live re-record runs at
the very end, on a clean tree, after the last edit inside the pinned zone.

The route reviews each unit as its own parent->HEAD candidate; the whole-branch
candidate is structurally unreducible (durable decision, 2026-08-14).

## Candidate composition (allowed zones)

- `scripts/itd.py`, `tests/verify_itd_cli.py` — **S9-U4-PRCREATE**:
  `create_draft_pr` derived its push decision from PR existence, so a branch
  already delivered by an attempt that timed out after its push was pushed
  again; the no-op push feeds the guarded pre-push hook an empty update stream,
  which `scripts/itd_pre_push.py:55` rejects fail-closed. New helper
  `remote_branch_head` resolves the remote head with
  `git ls-remote --heads origin refs/heads/<branch>` and the absent-PR path
  skips the push when it already equals local `HEAD`. `parse_updates` is NOT
  relaxed and `pr_view` stays before the push — see the contract's Exclusions.
- `hooks/record-agent-skill.sh`, `hooks/completion-gate.sh`,
  `docs/templates/itd/itd_hygiene.py` and their oracles — **S9-U3-LEDGER**:
  agent-delegation telemetry rows are written without `producer`, so the strict
  completion evaluation fails to parse the ledger. Fix the writer and teach the
  evaluator to skip layer-0 telemetry rows instead of failing closed on them.
  `.claude/completion/signals.jsonl` is evidence and is never edited.
  The zone was widened while implementing the unit, and the widening is
  declared rather than silent: the identical strict check lives twice — in the
  commit gate (`hooks/completion-gate.sh`) and in the explicit-close evaluator
  (`docs/templates/itd/itd_hygiene.py`), both reading the same ledger. Fixing
  only the first would have left `/session-save --close` failing closed on the
  same rows, which is a half-fix, not a bounded one. `hooks/completion_lib.py`
  was in the originally declared zone and turned out NOT to need a change:
  giving `append_signal` a default producer would forge provenance for any
  writer that forgot to sign, so each writer signs itself instead.
- `skills/_shared/itd_gate_control.py`,
  `tests/verify_gate_profile_doctor.py` — **S9-U2-DOCTOR**: extend the
  `validate_local_adjudication` route-label contract past `str | None` so the
  local-review profile doctor can surface `routeIndependence`, moving the
  doctor entry past `routeEvidence`-only. Callable contract and doctor stub
  change together in one bounded change.
- `skills/_shared/itd_free_reviewer_producer.py`,
  `tests/verify_free_reviewer_producer.py` — **S9-U1-COMMITTED-HEAD**: the
  producer reads `git diff --cached` only, so an already-committed candidate
  cannot be routed. Teach it `--candidate-mode committed-head`, binding
  parent->HEAD with the same exact tree/diff the machine receipt uses, mirroring
  `skills/_shared/itd_verification_loop.py:251-261, 1830-1855, 2131-2133`.
- `tests/fixtures/live-model-evidence/**` — **S9-RERECORD**: one fresh live H4
  run, because U1/U2/U3 move the methodology tree pin by construction. Recorded
  on the clean committed tree; by construction it attests the PARENT tree of
  its own evidence commit (precedent PR #193/#195/#199/#201/#205).
- `.itd/ACCEPTANCE_CONTRACT.json` — `activeFollowup` rotated from the closed
  `S8` to `S9` at riskTier medium, impact classes correctness, error-handling,
  repository-hygiene, security.
- `.itd-memory/contracts/S9-*.md` — one root-cause contract per unit.
- `BACKLOG.md` — the four items closed by S9, and any residual deliberately
  recorded rather than fixed inside a scoped unit.
- `.itd/SCOPE_LOCK.md` — this file.
- `HANDOFF.md`, `.itd-memory/STATE.json` (force-added ledger) — the S9 context
  packet carried over from main uncommitted, and the unit ledger as it advances
  U4 -> U3 -> U2 -> U1 -> RERECORD, each recorded verified with its receipt
  digest. Ledger commits are separate from evidence commits: staging
  `STATE.json` breaks the dirty-state pin of the record itself.

## Units added after this scope was first sealed

None yet. Any unit opened after this seal — because the mandatory route or a
frozen oracle rejected the branch as it then stood — is listed here with its
files, its commit and the reason it was opened, so the candidate declares its
real composition rather than a stale prefix of it.

## What a reviewer judges inside recorded live evidence

`tests/fixtures/live-model-evidence/runs/**` is a RECORDING of what the
model-under-test produced while the benchmark drove it. The generated
`output/*.md` documents, the `run-report.json` and the `transcript.jsonl.gz`
are observations, not this candidate's specification, and the maker may not
edit their content: rewriting a recorded run to read better is evidence
forgery, which the frozen `evidence-replay` oracle exists to prevent.

Therefore, inside that directory the reviewable properties are exactly:

- freshness — the recorded `methodologyTreeSha256` and the other source pins
  equal the reviewed tree's actual pins, and `latest.json` points at this run;
- integrity — the transcript is a complete run (matched items, a terminal
  `turn.completed`) and `run-report.json` agrees with it;
- hygiene — no secret, token, or credential survives into the recording.

Statements *inside* a generated document (its requirements, its architecture
choices, its error-handling promises) are the model's output under test. They
are graded by the benchmark's own scoring, not re-litigated as if this
candidate proposed them. A defect found there is a finding about the
model-under-test, to be recorded in `BACKLOG.md`, never a reason to alter the
recording. Commands the model ran inside the disposable adopted project
(which has no `.git` by construction, so `git status` there exits 128) are
likewise part of the recording, not a provenance failure of this candidate.

## Forbidden change areas

- Any production or test code NOT listed above — in particular the transport,
  the auth/rollout provenance checks, the other reviewers (Gemini,
  Antigravity, Copilot), `DISABLED_TOOL_FEATURES`, and the frozen efficacy
  case corpus.
- `.claude/completion/signals.jsonl` — the completion ledger is the evidence
  U3 is diagnosed from, not an input to repair.
- `.itd-memory/verification-loop/keys/`, host-owned inputs under
  `.itd-memory/host-inputs/`, and any archived prior evidence.
- Loosening any check to make a gate pass. In particular `parse_updates` keeps
  rejecting an empty pre-push update stream: U4 stops the caller from producing
  one, it does not teach the guard to accept one.
