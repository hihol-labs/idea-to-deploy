# ADR-007 — Human adjudication of independent-review findings

- **Status:** accepted
- **Date:** 2026-08-09
- **Amends:** [ADR-006](ADR-006-single-opposite-gpt-review.md) — the mandatory
  no-bypass reviewer stays mandatory and no-bypass; this ADR adds the one
  channel it was proven to need. The vendor-neutral independence redesign
  (closed {Claude, Codex} set, same-vendor fallback,
  `HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW`) is deliberately **not** decided
  here; it belongs to the deferred ladder unit and its own ADR.
- **Unit:** GPG-004 reviewer-policy phase A (`.itd/SCOPE_LOCK.md`)

## Context

The commit review gate (`hooks/check-review-before-commit.sh` →
`skills/review/scripts/itd_review_cache.py`) accepts only a recorded
adjudication receipt whose outcome is `PASSED`, and an adjudication receipt
can only be minted when the checker verdict is in `acceptedVerdicts =
["PASSED"]` (`itd_verification_loop.py`, `validate_checker`). A BLOCKED
checker verdict is never accepted, and the methodology had no machine channel
for "a human examined the reviewer's findings and accepted them as trade-offs
or refuted them with evidence".

Execution on 2026-08-09 proved this is a deadlock, not a corner case: the
bounded-process slice was fully machine-accepted (mutations 19/19, both live
benchmark legs at host parity, machine receipt 26/26 zero-bad, H4 live-model
PASS, full run-all green), the mandatory route ran repeatedly to a verdict,
every finding was adjudicated or refuted by evidence — including one proven
false positive (the reviewer claimed a transcript was not gzip while the file
starts with the gzip magic `1f 8b`) and one accept-by-design tension
(checkpoint freshness, which *is* the resumability feature under review). The
findings could never become "clean", so the correct candidate could never be
committed. A mandatory reviewer that can produce false positives and has no
adjudication channel can block correct code forever. That is a defect of the
gate design, not of the candidate.

The two obvious non-fixes are both forbidden: bypassing the gate
(`--no-verify`, env switches) destroys the no-bypass invariant the whole goal
is built on, and re-running the route until a lucky clean PASS is
evidence-resampling.

## Decision

**Add a second honest receipt outcome, `ADJUDICATED`, minted by explicit
human adjudication of a BLOCKED checker receipt. Do not widen what the
checker itself may return or what counts as `PASSED`.**

1. `acceptedVerdicts` for checker receipts stays `["PASSED"]`. A checker
   verdict is never rewritten, downgraded or re-labelled; the BLOCKED receipt
   remains in the durable record exactly as the reviewer produced it.
2. A new adjudication path accepts (machine receipt `PASSED`) + (checker
   receipt `BLOCKED`) + **per-finding human dispositions**, and mints an
   adjudication receipt with outcome `ADJUDICATED` — honestly distinct from
   `PASSED`, never presented as a clean review.
3. Each disposition names one finding from the checker report and states:
   the class (`accepted-trade-off` | `refuted-by-evidence` | `fixed`), a
   rationale, and the evidence reference (for `refuted-by-evidence` and
   `fixed`). Minting is fail-closed: any finding without a disposition, a
   disposition that names no finding, a foreign unit, a stale or foreign
   candidate tree, or a missing explicit human confirmation refuses to mint.
4. The confirmation is a human act recorded in the receipt (who confirmed,
   when, over which exact candidate digest and which checker receipt sha).
   Dispositions and confirmation are inputs the human provides; the model
   may draft rationale text, but the mint step requires the confirmation to
   be the exact affirmative sentence naming the checker receipt sha256 —
   free-form prose, negated text, or a confirmation reused from another
   receipt never mints.
5. The commit review gate accepts `PASSED` and `ADJUDICATED` receipts. The
   receipt keeps the honest label visible: downstream consumers (PR text,
   release evidence) can and must distinguish "reviewer found nothing" from
   "reviewer's findings were humanly adjudicated".

## Consequences

- The no-bypass property is preserved: there is still no path around the
  reviewer. What changes is that the reviewer's word is no longer the *final*
  word on its own findings — the human is, with the disagreement recorded
  rather than erased.
- A false positive costs one adjudication entry instead of an infinite block.
- The audit trail becomes more honest, not less strict: previously a
  practically-forced bypass (or verdict laundering) was the only escape;
  now the escape is a signed, findings-complete, human-confirmed receipt
  that names exactly what was accepted and why.
- The parked bounded-process slice (frozen staged tree `1a9eaa240f8bd7d3`)
  becomes committable through the channel without touching its evidence.
- Risk: adjudication could degrade into rubber-stamping. Mitigations: the
  per-finding completeness requirement, the honest `ADJUDICATED` label kept
  distinct from `PASSED`, mutation tests on every minting guard, and the
  durable BLOCKED checker receipt that any later audit can re-read.
