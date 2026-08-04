# ADR-006: one fresh opposite-GPT reviewer

**Date:** 2026-08-04
**Status:** Accepted
**Review date:** 2026-09-15
**Amends:** ADR-004 and ADR-005 for the mandatory GPG-003 route. Their
exact-candidate, evidence-first, isolation, efficacy and fail-closed controls
remain in force; the three-provider fallback and two-reviewer quorum do not.

## Context

GPG-003 grew from a final independent pre-PR check into a mandatory
three-provider route with a two-reviewer quorum. The current account has no
paid Claude or Antigravity plan, and two bounded exact-candidate attempts were
blocked by Copilot output transport rather than by a candidate defect. This
made methodology availability depend on unrelated subscriptions and adapters,
delayed product work, and did not address the root cause of the earlier false
clean review: missing product-scale and business-invariant machine evidence.

The intended control is simpler. Development already runs tests and declared
machine checks. Immediately before PR publication, one model that did not
develop the candidate reviews the frozen result without inherited development
context. The exact candidate and evidence, not reviewer count, provide the
reproducible acceptance boundary.

## Decision

Keep the approved nine-point plan and amend its existing review point; do not
add a tenth point.

1. Medium, high and unknown risk require exactly one mandatory independent
   semantic review after the exact-candidate evidence-first machine oracle.
   Low risk remains machine-only where the existing policy permits it.
2. The mandatory reviewer is the opposite installed GPT model in a fresh
   session: maker `gpt-5.6-sol` selects `gpt-5.6-terra`; maker
   `gpt-5.6-terra` selects `gpt-5.6-sol`. Unknown maker provenance or a model
   outside this closed pair fails closed.
3. The reviewer receives no development history or inherited session context.
   It receives only the scrubbed self-contained exact candidate, acceptance
   contract, evidence-coverage graph and exact-tree machine receipt. Bounded
   candidates may still use the existing complete deterministic unit plus
   integration packet; no input is silently truncated.
4. One clean phase-one v2 reviewer receipt is sufficient. Findings,
   unverified contours, malformed structured output, tool use, same
   model/session, missing machine evidence, stale candidate or unavailable
   reviewer block publication. An amended candidate reruns its machine oracle
   and gets a new fresh opposite-GPT review.
5. The host remains the sealed adjudicator. It binds the reviewer result to the
   candidate, machine evidence and later PR coordinates; reviewer prose or a
   standalone `PASSED` is never acceptance evidence.
6. Anthropic, GitHub Copilot, Antigravity and paid API transports may remain as
   separately invoked optional adapters. They are not automatic fallbacks,
   quorum members or prerequisites for `LOCAL_REVIEWED`, and their absence
   cannot block unrelated product repositories.
7. The frozen generic efficacy corpus, impact-specific machine oracles,
   repository hygiene, WSL/native-Windows parity, green CI, patch release,
   dual-host installation and GPG-003 completion evidence remain required.

## Alternatives considered

### Keep the two-reviewer quorum

Rejected for the mandatory default. Two reviewers can share a missing-evidence
blind spot, while unavailable subscriptions and output adapters create an
unbounded operational gate. Additional reviews remain available when a user
explicitly asks for them.

### Keep an automatic provider fallback chain

Rejected. A fallback changes the independence and output contract during an
acceptance run and makes product publication depend on provider availability.
The selected Sol/Terra pair is explicit and testable on both supported hosts.

### Remove independent review entirely

Rejected. A fresh opposite model still supplies a valuable semantic check
after deterministic project evidence and before external publication.

## Consequences

- The mandatory route has one model call (or one bounded hierarchical review
  set) instead of a provider quorum.
- The methodology remains fail-closed, but its mandatory dependencies match
  the installed paid capabilities on this computer.
- Phase-one v3 and optional provider adapters remain readable/testable for
  compatibility, but they do not satisfy or alter the selected default route.
- GPG-003 still closes only after a new exact-candidate machine receipt, fresh
  opposite-GPT adjudication, merged implementation and patch release, and
  verified WSL/native-Windows rollout recorded as 9/9 completion evidence.
