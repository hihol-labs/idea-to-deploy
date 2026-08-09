# Scope Lock — GPG-004 push-gate unit: ADJUDICATED acceptance in the push layer

## Current Task

Extend the guarded push layer so a human-adjudicated independent review can
honestly satisfy it, and repair the live gate registry after the isolation
incident. Necessity is proven by execution (2026-08-09):

1. `validate_local_adjudication` (`skills/_shared/itd_gate_control.py:1458`)
   shells to `itd_verification_loop.py check --require-mandatory-route
   --expected-producer-keyring-sha256 …`, which requires a checker receipt
   carrying a signed phase-one clean-pass route. The producer structurally
   refuses to mint a phase-one receipt for a BLOCKED verdict
   (`itd_free_reviewer_producer.py`: "review did not return a clean pass";
   `verify_phase_one` requires `status == "PASSED"`). An honestly
   BLOCKED-then-adjudicated route (ADR-007) can therefore never pass the push
   gate: authorized pushes deadlock forever. The commit gate already accepts
   ADJUDICATED (phase A); the push layer is the remaining PASSED-only surface.
2. The live registry `~/.config/itd/gates.json` was overwritten by a
   test-fixture row (`checkout: /tmp/itd_gate_local_review_commit`, missing
   `localReviewProducerKeyringSha256`) and no longer validates — a
   test/rehearsal isolation leak (incident, DECISIONS 2026-08-09).

Design, fixed for this unit:

- New explicit opt-in flag `--accept-adjudicated-route` on the `check`
  subcommand. Default behavior is byte-preserved: `--require-mandatory-route`
  without the new flag stays PASSED-only with the signed route. With the flag:
  a PASSED outcome still requires the signed phase-one route; an ADJUDICATED
  outcome is authorized by the ADR-007 human channel instead (PASSED machine
  receipt + BLOCKED checker with exact-tree/artifact/identity validation +
  complete human adjudication bound to the checker sha256), because a signed
  clean-pass route cannot honestly exist for it.
- `validate_local_adjudication` passes the new flag; the profile doctor
  surfaces the honest route evidence (`human-adjudication` vs
  `signed-keyless-route`) without elevating the LOCAL_REVIEWED claim.
- Registry-write isolation: the guarded registry writer refuses to write a
  row whose checkout lies under the system temp directory into the live
  default registry path; tests and rehearsals write only through an explicit
  `ITD_GATE_REGISTRY` target. A RED-first isolation test reproduces the
  incident write and pins that the live registry stays byte-identical across
  the gate suites.
- Live registry repair happens only through the guarded register flow, after
  the unit commit, with a freshly minted committed-head receipt chain.

Established by execution this session: `validate_common` recomputes the
candidate context (HEAD, tree, scope/acceptance contract hashes) from the
live repository on every check, so the pre-unit receipts in
`.itd-memory/verification-loop/receipts/adf40ca3f6d504c9/` cannot authorize a
push made after any further commit. They are reused as RED-test fixtures and
as the minting procedure template only; the push-time chain is minted fresh
on the final HEAD and needs one more explicit human adjudication.

## Allowed Change Areas

- `skills/_shared/itd_verification_loop.py` — the `--accept-adjudicated-route`
  flag and its threading through `command_check`/`validate_adjudication`/
  `validate_adjudication_evidence`/`validate_checker` (the mandatory-route
  requirement site)
- `skills/_shared/itd_gate_control.py` — `validate_local_adjudication`,
  profile-doctor route-evidence surface, registry-write guard
- the guarded `itd` CLI registry writer, if it lives outside
  `itd_gate_control.py`
- new focused RED-first tests and mutation checks
  (`tests/verify_push_gate_adjudicated.py`,
  `tests/verify_gate_registry_isolation.py`) plus bounded extensions of
  `tests/verify_gate_profile_doctor.py`,
  `tests/verify_gate_registry_profiles.py`,
  `tests/verify_mandatory_keyless_review.py`, and oracle-id registration in
  the evidence-coverage mapping
- live registry repair via the guarded register flow (post-commit ops step)
- `.itd/SCOPE_LOCK.md`, `.itd/ACCEPTANCE_CONTRACT.json` (PB criteria),
  CHANGELOG/BACKLOG/HANDOFF and `.itd-memory` state records

## Forbidden Change Areas

- weakening the default: `--require-mandatory-route` without the new flag
  stays PASSED-only with the signed phase-one route
- minting phase-one receipts for BLOCKED verdicts, rewriting/downgrading/
  re-labelling checker verdicts, widening checker `acceptedVerdicts`
- `skills/_shared/itd_free_reviewer_producer.py` and the signed benchmark-leg
  surface (a single producer byte invalidates both live legs)
- `--no-verify`, environment kill-switches, direct `git push`, or manual
  edits of `~/.config/itd/gates.json` outside the guarded register flow
- treating the pre-unit receipts (`adf40ca3f6d504c9/*`) as push authorization
  after HEAD moves — fixtures/templates only
- the ladder remainder (independence class {Claude,Codex}, same-vendor
  fallback, `HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW`, reviewer cardinality,
  U12), U6, U16/U17 — separate deferred units
- push or PR before: unit commit + the "pin clean live evidence" follow-up +
  a fresh committed-head chain + a valid live registry

## Acceptance Boundary

The unit is accepted only when GPG-004-PB1..PB3 pass: RED-first tests
reproduce both deadlocks (mandatory-route-missing for an honest ADJUDICATED
receipt; the live-registry fixture write), then turn GREEN only through the
new flag and the isolation guard; mutation checks kill each guard
individually; the full quick suite stays green; and the unit commit itself
passes the commit review gate (through the ADR-007 channel if the fresh
route returns findings) without bypass. The live registry repair is a
post-commit ops gate carried by the contract doneRule, not a pre-commit
criterion: it structurally requires the committed code and a fresh
committed-head chain, and it must complete before guarded publication.
`skills/` edits burn the H4 pin — the queued "pin clean live evidence state"
follow-up restores it before `itd pr create`.
