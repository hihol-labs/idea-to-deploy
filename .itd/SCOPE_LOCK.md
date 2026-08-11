# Scope Lock — U-PRODUCER-LEGIBILITY: two byte totals in one reviewer prompt

## Current Task

Fix a legibility defect in the free-reviewer producer. Every reviewer prompt
embeds `packet["candidate"]` verbatim. Its `diffBytes` / `diffSha256` measure
the git-native staged candidate diff and are the provenance identity of the
candidate. Whenever the review representation is not that same byte string —
the canonical transparent diff (`itd-canonical-transparent-diff-v1`) or the
no-renames re-diff — every review byte offset, unit range and coverage claim
is measured over a *different* object with a *different* total. Nothing in the
prompt said so, so a correct reviewer that reconciles unit coverage against the
candidate binding finds two irreconcilable totals and blocks.

Observed on the live run `U-NTFS-DIRSIZE-terra-r4`: `verdict=BLOCKED`,
`findings=[]`, sole unverified entry — «The unit review byte ranges cover
141147 bytes, but the candidate declares diffBytes=116095; complete
exact-candidate unit coverage cannot be reconciled from the supplied
evidence.» The candidate under review was sound; the prompt was not legible.

The fix is prompt text only. No hash, binding, plan, receipt, policy or
partition changes: a single shared helper states which total governs review
coverage, and the three prompt builders emit it.

## Allowed zones

- `skills/_shared/itd_free_reviewer_producer.py` (new
  `_review_representation_note` helper; one emitting line added to each of
  `review_prompt`, `_unit_review_prompt`, `_integration_review_prompt`)
- `tests/verify_free_reviewer_producer.py` (regression coverage for the
  hierarchical and the direct transparent route)
- `.itd/SCOPE_LOCK.md` (this contract, rewritten for the unit)
- `.itd/ACCEPTANCE_CONTRACT.json` (`activeFollowup.unitId` retargeted;
  criteria AC1–AC9 appended)
- `tests/fixtures/live-model-evidence/**` (re-minted live-model evidence:
  `latest.json` plus one new immutable run directory). Nothing here is edited
  by hand. `tests/verify_live_model_benchmark.py` pins the content hash of the
  whole methodology tree — `AGENTS.md`, `.codex-plugin`, `.claude-plugin`,
  `skills`, `agents`, `hooks`, `docs/templates/itd*`,
  `docs/HOST_ADAPTER_CONTRACT.md`, `docs/host-adapters.json` — and this unit
  changes a file inside `skills/`. The pin therefore has to be re-observed by a
  fresh live run; carrying the stale pin forward would be exactly the
  "stale SHA/base into success" move that `.itd/FORBIDDEN_CHANGES.md` forbids.

Explicitly out of scope: the review broker and its policy, the candidate
partition, receipt or artifact schemas, reviewer routing, and the live-model
benchmark runner, verifier, fixture and oracle themselves — the evidence is
re-observed by running the unmodified runner, never by editing a pin.

## Acceptance (this unit)

1. All three prompt builders state the governing total and the rule that
   review coverage is reconciled against the review representation, never
   against `candidate.diffBytes`.
2. The regression test is bound to the defect, not to the wording shape:
   removing the emitting line makes the targeted suite fail, and the governing
   total is read as an exact delimited number rather than as a substring, so an
   emitted digits-superset (141147 → 1411470) no longer satisfies the check.
3. The two changed code files (`skills/_shared/itd_free_reviewer_producer.py`
   and `tests/verify_free_reviewer_producer.py`) are additions-only: nothing
   is removed or rewritten there, so no existing binding, hash or partition
   can shift, and the redaction-scrub contract merged in PR #188 is preserved
   verbatim. This contract file and `.itd/ACCEPTANCE_CONTRACT.json` are
   deliberately rewritten — retargeting the scope lock and `activeFollowup`
   at this unit is the unit own bookkeeping, authorized by the Allowed
   zones above, and is not covered by the additions-only claim. The re-minted
   files under `tests/fixtures/live-model-evidence/` are likewise outside that
   claim: `latest.json` is replaced wholesale by the runner and the run
   directory is new, so neither is an edit to reviewed code.
4. The helper is fail-closed: an absent or non-integer representation total
   raises `FreeReviewError("UNVERIFIED", …)` instead of emitting an unbound
   prompt.
5. The note is trusted framing placed ahead of all untrusted material; the
   trusted output contract remains the final instruction in every prompt.
6. Unit and integration prompts still fit `MAX_UNIT_PROMPT_BYTES` /
   `MAX_INTEGRATION_PROMPT_BYTES` on the oversized transparent fixture.
7. The whole review contour is green on this host.
8. The live-model evidence is re-observed on this exact candidate tree by the
   unmodified runner: `tests/verify_live_model_benchmark.py --require-evidence`
   passes, which requires the recorded `sourcePins.methodologyTree` to equal the
   tree hash computed live, the candidate to be a real external headless run
   that exited zero, and the deterministic snapshot oracle — not the model's
   self-report — to return PASS.

## Risk tier

high — inherited from the active review policy. The producer is the surface
that carries every candidate to an independent reviewer; a wrong statement
here would mislead every future review rather than one candidate. The change
itself is additive prompt text with no effect on any hash or partition.
