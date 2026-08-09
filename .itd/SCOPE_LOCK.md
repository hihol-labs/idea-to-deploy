# Scope Lock — GPG-004 ladder remainder: reviewer independence policy

## Current Task

Ladder remainder of GPG-004 (compressed plan agreed 2026-08-09, phase after A
and after the accepted push-gate slice): make reviewer independence an
explicit, honest, machine-checked policy instead of a hard-coded Sol/Terra
convention.

1. **Closed vendor independence class {Claude (anthropic), Codex (openai)}**
   for the maker/reviewer pair. Live proof of necessity: an honest anthropic
   maker today dead-ends with typed UNAVAILABLE "maker is not a supported
   Sol/Terra model" (`select_openai_reviewer_model`,
   `require_opposite_openai_model` in
   `skills/_shared/itd_free_reviewer_producer.py`) — cross-vendor review for
   an anthropic maker is structurally impossible, so authorized work made by
   Claude can never obtain the mandatory independent review.
2. **Flagged same-vendor-different-model fallback** — selectable only after
   the cross-vendor route returns a typed unavailability; every receipt and
   claim surface carries the honest `same-vendor-different-model` label,
   never silently, never for a same-model pair, and it never upgrades the
   recorded independence claim.
3. **HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW** — explicit audited human override
   class for "no independent route available at all": bound to the exact
   candidate digest, recorded under its own honest label, never counted as an
   independent review by any downstream gate.
4. **Reviewer cardinality** — restore the `minimumIndependentReviewers`
   contract and the removed `low-reviewer` / `high-quorum` structural cases
   in the efficacy suite; quorum deduplicates by provider/model/session
   identity.
5. **U12 measurement** — measure the ladder: same-vendor vs cross-vendor
   reviewer legs over the frozen seeded benchmark corpus, published as signed
   host-derived evidence, recorded honestly whatever the result.

## Slicing (fixed for this unit)

- **PC-S1 (contracts, this session):** BACKLOG delta, this scope lock,
  `GPG-004-PC1..PC5` in `.itd/ACCEPTANCE_CONTRACT.json`, plan approval. No
  code.
- **PC-S2 (RED-first, after plan approval):** policy module + tests outside
  the frozen producer; RED tests pin today's anthropic-maker UNAVAILABLE
  dead-end, the cardinality gaps, and the missing override class.
- **PC-S3 (producer batch, separate explicit approval):** ALL producer edits
  for PC1/PC2/PC5 land as ONE batch; both signed benchmark legs are re-run
  exactly once after the batch (a single producer byte invalidates both
  legs). This is the most expensive slice of the unit and starts only on its
  own explicit user approval.
- The unit commit is one combined candidate (PC-S2 + PC-S3) so
  `coverage_matrix` sees every active criterion passed before the commit
  review — same pattern as the accepted phase-A combined slice.

## Allowed Change Areas

- new policy module for the independence class and its threading through the
  reviewer selection surface (`skills/_shared/itd_free_reviewer_producer.py`
  ONLY inside the approved PC-S3 batch)
- `skills/_shared/itd_verification_loop.py`,
  `skills/_shared/itd_gate_control.py` — honest label surfaces
  (independence level, override class) without changing gate defaults
- new focused RED-first tests
  (`tests/verify_reviewer_independence_policy.py`) plus bounded extensions of
  `tests/verify_independent_review_efficacy.py` (cardinality cases + U12),
  `tests/verify_mandatory_keyless_review.py`, and oracle-id registration in
  the evidence-coverage mapping
- amendment 2026-08-09 (after the legs were minted): ONE broker-suite fixture
  line in `tests/verify_review_broker.py` — the foreign-maker negative
  fixture moves from the out-of-class provider `forged-maker` to a
  class-member but still foreign `anthropic-subscription/opus` identity,
  because the closed class refuses to label out-of-class pairs at mint time
  and a producer-byte fix would burn all three freshly signed legs; the
  fixture's downstream intent (maker claim must match signed PR provenance;
  no Check Run, no token spend) is unchanged
- a new ADR for the independence policy if the design departs from ADR-006/7
- `.itd/SCOPE_LOCK.md`, `.itd/ACCEPTANCE_CONTRACT.json` (PC criteria),
  CHANGELOG/BACKLOG/HANDOFF and `.itd-memory` state records

## Forbidden Change Areas

- any producer byte outside the explicitly approved PC-S3 batch; piecemeal
  producer edits (each byte invalidates both signed benchmark legs)
- same-model maker/reviewer pairs; silent fallback selection; recording
  HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW as PASSED, ADJUDICATED or any form of
  independent review; widening checker `acceptedVerdicts`
- weakening `--require-mandatory-route` defaults, the ADR-007 channel, or the
  push-gate/registry-isolation behavior accepted in PB1..PB3
- `--no-verify`, environment kill-switches, direct `git push`, manual edits
  of `~/.config/itd/gates.json` outside the guarded register flow
- U6 (installed-skill parity), U16 (pre-deploy), U17 (design-stage) — separate
  deferred units; the completion-gate and fixture-hardening BACKLOG candidates
  recorded 2026-08-09 — separate bounded fixes
- push or PR before: unit acceptance + the "pin clean live evidence state"
  follow-up (skills/ edits burn the H4 content pin) + a fresh committed-head
  chain

## Acceptance Boundary

The unit remainder is accepted only when GPG-004-PC1..PC5 pass: RED-first
tests reproduce the anthropic-maker dead-end, the silent-fallback and
label-laundering mutations, the missing override class and the cardinality
gaps, then turn GREEN only through the policy; mutation checks kill each
guard individually; both signed benchmark legs revalidate after the single
PC-S3 batch; the U12 comparison is recorded as signed host-derived numbers;
the full quick suite stays green; and the unit commit passes the commit
review gate (through the ADR-007 channel if the fresh route returns findings)
without bypass. GOAL/STATE closure of GPG-004 additionally requires the /goal
pass over the unit's verificationCommands after this remainder lands.
