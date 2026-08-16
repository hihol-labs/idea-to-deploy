# S9-U2-DOCTOR — the doctor cannot surface the route's independence level

**Unit:** `S9-U2-DOCTOR` · riskTier **medium** · branch `fix/s9-harness-debts`
**Impact classes:** correctness, error-handling, repository-hygiene

## Root cause

`itd_verification_loop.py check --accept-adjudicated-route` prints BOTH labels
of the validated route:

```json
{"outcome": "PASSED", "routeIndependence": "cross-vendor"}
```

(`skills/_shared/itd_verification_loop.py:2041-2047`; the level comes from the
signed phase-one route, and is `null` when the producer minted none.)

`validate_local_adjudication` in `skills/_shared/itd_gate_control.py` read only
`outcome` and its contract returned `str | None` — a single route-evidence
label. The independence level was therefore discarded at the boundary, and
`profile_doctor_entry` could only ever report `routeEvidence`. An operator
reading the doctor could see THAT a signed route backed the local-review
profile, but not how independent the maker/reviewer pair actually was — the
one property that distinguishes a cross-vendor review from a same-vendor one.

## Scope

- `skills/_shared/itd_gate_control.py`:
  - the contract becomes `dict[str, str] | None`, carrying `routeEvidence` and,
    when present, `routeIndependence`;
  - `independence_levels()` loads the closed class from its single source of
    truth (`skills/_shared/itd_reviewer_independence.py:53`) lazily by path, so
    this module keeps no import-time dependency on the policy module and no
    second copy of the level names that could drift;
  - `profile_doctor_entry` surfaces `routeIndependence` next to
    `routeEvidence`, without touching the claim.
- `tests/verify_gate_profile_doctor.py` — the stub and the assertions move to
  the new contract together with it, plus new coverage of the drop rules.

## Exclusions

- **The claim is not lifted.** A profile stays `LOCAL_REVIEWED` regardless of
  which independence level it reports. The label is evidence for a human, not
  an input to the gate.
- **The level is never fabricated.** It is reported only when the check printed
  a member of the closed class. A pre-batch receipt, an ADJUDICATED outcome
  with no signed route, an empty string, a non-string, or an unknown level all
  report nothing. An unavailable or malformed policy module reports an empty
  class, so the label is dropped rather than trusted.
- **`reviewer_independence_level` hardening is NOT in this unit.** The open
  BACKLOG item about requiring the shared family to be a member of the closed
  class before labeling a same-family pair is a separate change to the policy
  module; this unit only stops discarding the level the policy already
  computed.
- **No claim-order, registry, or broker change.** App-backed profiles are
  untouched.

## Verification standards

- RED-first: the existing doctor assertion
  `adjudicated route evidence is labelled honestly without a claim lift` fails
  against the new contract before the suite is migrated — the stub pinned the
  old `str` return.
- Mutation: neutralizing the closed-class filter so the level is never attached
  turns the two new level assertions red; relaxing it to "any non-empty string"
  turns the forged-level assertion red (`fully-independent` is not in the
  class). Restoring returns the suite to green.
- Coverage: `tests/verify_gate_profile_doctor.py` 32 -> 44 checks, including
  both closed-class levels reported as themselves, five forged/absent variants
  dropped, a non-object payload yielding no label at all, and an independence
  level being unable to survive a non-passing outcome.
