# Scope Lock — GPG-004 reviewer-policy unit, phase A: human adjudication channel

## Current Task

Build the machine channel that lets a human adjudicate independent-review
findings, so that a BLOCKED checker verdict whose findings are all explicitly
dispositioned by the human can mint a gate-satisfying receipt with the honest
outcome `ADJUDICATED`. Necessity is proven by execution (2026-08-09): the
bounded-process slice is fully machine-accepted (mutations 19/19, both live
benchmark legs host-parity, machine receipt 26/26, H4 PASS, full run-all
green) yet permanently blocked at the commit review gate, because the gate
accepts only a recorded `PASSED` adjudication receipt and the mandatory
reviewer returned BLOCKED on findings that were adjudicated or refuted by
evidence (including a proven gzip false positive). A mandatory no-bypass
reviewer without an adjudication channel can deadlock correct code forever.

Producer files are not touched in this phase, so the signed benchmark legs
(bound to the producer file sha) remain valid. WIP=1: the bounded-process
slice stays parked verified-and-uncommitted on frozen staged tree
`1a9eaa240f8bd7d3` and commits through this channel as the next step.

The deferred remainder of the reviewer-policy work (closed vendor set
{Claude, Codex}, same-vendor-different-model fallback, honest independence
class, `HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW`, reviewer cardinality and its
benchmark cases, U12 measurement) is a separate backlog unit and is out of
scope here.

## Allowed Change Areas

- `skills/_shared/itd_verification_loop.py` — the `ADJUDICATED` receipt
  outcome: minting that requires a BLOCKED checker receipt plus complete
  per-finding human dispositions with rationale and explicit human
  confirmation; fail-closed validation of that receipt
- `skills/review/scripts/itd_review_cache.py` — accepting the new receipt
  outcome at the commit review gate with its honest label
- `hooks/check-review-before-commit.sh` — only as far as its flow or wording
  must name the new outcome
- new focused tests for the channel (RED-first) and mutation checks that kill
  each minting guard
- `docs/adr/ADR-007-human-adjudication-of-independent-review.md`
- `.itd/SCOPE_LOCK.md`, `.itd/ACCEPTANCE_CONTRACT.json` (phase-A criteria),
  CHANGELOG/BACKLOG/HANDOFF and `.itd-memory` state records

## Forbidden Change Areas

- `skills/_shared/itd_free_reviewer_producer.py`,
  `skills/_shared/itd_review_evidence.py`, the efficacy benchmark corpus,
  runner, verifier or signed legs, and any semantics of the parked
  bounded-process slice (a single producer byte invalidates both live legs)
- widening the checker `acceptedVerdicts` beyond `["PASSED"]`, or rewriting,
  downgrading or re-labelling a checker verdict: the checker receipt stays
  BLOCKED in its own record; adjudication is a separate receipt that
  references it
- minting `ADJUDICATED` while any checker finding lacks a human disposition
  (`accepted-trade-off` / `refuted-by-evidence` / `fixed`), a rationale, or
  the explicit human confirmation; no default or model-authored dispositions
- `--no-verify`, environment kill-switches, or any second review authority
  beside Verification Loop
- the ladder scope listed above as deferred
- unstaging or moving the frozen slice index (tree `1a9eaa240f8bd7d3`)
  except at the slice's own commit step
- push or PR without an explicit user command

## Acceptance Boundary

Phase A is accepted only when: RED-first tests reproduce today's deadlock (a
BLOCKED checker receipt with fully-dispositioned findings cannot satisfy the
gate); the channel converts exactly that state into an `ADJUDICATED` receipt
only in the presence of complete per-finding human dispositions and explicit
confirmation; mutation checks kill every minting guard (uncovered finding,
foreign unit, stale/foreign candidate, verdict rewrite, missing
confirmation); the full `tests/run-all.sh` stays green; a fresh independent
route reviews the exact phase-A candidate and any findings are adjudicated
through the channel itself; and the phase-A commit passes
`hooks/check-review-before-commit.sh` without bypass. The bounded-process
slice then commits through the same channel as its own next step (separate
acceptance: fresh H4, machine receipt, fresh route on the moved tree).
