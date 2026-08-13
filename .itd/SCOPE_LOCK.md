# Scope Lock — U17: opt-in advisory design-provenance reviewer in /blueprint

## Current Task

Close unit U17 (GPG-004; S5 in `.itd-memory/PLAN-CLOSEOUT-2026-08-11.md`),
the last pending unit of the GPG-004 plan: an opt-in, advisory provenance
reviewer runs ON TOP of the Devil's Advocate debate in /blueprint and records
the provenance of each architectural claim. Sealed criterion: it is
explicitly NOT a gate — its absence never blocks, and its findings never turn
into an acceptance verdict. Verified by fixture runs showing an advisory
report plus an unchanged gate outcome (`cannotWeaken`).

## Candidate composition (allowed zones)

- `skills/blueprint/SKILL.md` — new sub-step 2.5b «Design Provenance Review
  (opt-in, advisory — GPG-004 U17)» inside the Step 2.5 adversarial debate
  protocol: opt-in via user request or `ITD_DESIGN_PROVENANCE=1`, writes
  `DESIGN_PROVENANCE.md` (`## Claim:` + `- Source:` + `- Reference:`), runs
  the structure check, and states the non-gate invariants verbatim.
- `skills/blueprint/scripts/itd_design_provenance.py` — new stdlib-only
  advisory validator: exit 0 on findings, clean report, absent report and
  malformed report; JSON output with `advisory: true`, actionable
  path+line+why+fix notes, no verdict-shaped field, never the acceptance
  token; quiet no-op without arguments; read-only.
- `tests/verify_blueprint_provenance_reviewer.py` — the sealed U17
  verificationCommand: RED first (rc=2, file absent), now green — 77 checks
  covering the skill text invariants, five fixture runs, read-only proof,
  and the unchanged-gate sweep (no hook or gate script references the
  reviewer).
- `tests/fixtures/blueprint-provenance/{sourced,unsourced,malformed}.md`.
- `tests/run-all.sh` — CORE registration of the new verifier.
- `.itd/SCOPE_LOCK.md`, `.itd/ACCEPTANCE_CONTRACT.json`,
  `.itd-memory/STATE.json` — unit contracts (activeFollowup
  `U17:general-review`, low tier; currentUnit U17).
- Follow-up commit of this same unit: `tests/fixtures/live-model-evidence/**`
  — re-recorded live benchmark evidence (see below).

## Two-commit acceptance (inherent, precedent PR #193/#195)

`verify_live_model_benchmark --require-evidence` (CI Gate 1) pins
`methodologyTreeSha256` over skills/hooks/agents and requires a clean
recorded working tree. Editing `skills/blueprint/SKILL.md` therefore burns
the recorded evidence BY CONSTRUCTION: source-pinned live evidence cannot
predate the code it pins. Commit 1 lands the feature with the old evidence
honestly red under `--require-evidence` (default-mode verifier and the quick
suite stay green); the live benchmark is then re-recorded on the clean
committed tree and commit 2 re-pins the evidence. Neither commit weakens the
oracle.

## Out of scope (honest limits)

- No new skill/agent/hook; counts unchanged. devils-advocate untouched.
- The reviewer never writes receipts and never appears in Verification Loop,
  review-cache, or any hook — enforced by the verifier's gate sweep.
- `.itd-memory/GPG-004_UNIT_PLAN.json` and `PLAN-CLOSEOUT-2026-08-11.md`
  are git-ignored local ledgers (updated locally; never committed).
  `.itd-memory/STATE.json` is git-tracked and part of this candidate.
- Scrubber precision (S6) and other queue items untouched.

## Machine-oracle shape

`u17-verifier=python3 tests/verify_blueprint_provenance_reviewer.py` plus
`quick-suite=bash tests/run-all.sh --quick`. Risk tier: low (sealed in
GPG-004_UNIT_PLAN) — machine-only adjudication per ADR-003/verification
profiles; no independent checker is required for this tier.

Base for the candidate: main `ef15e97` (merge of PR #198).
