# ADR-005: Evidence-first deep independent review

**Date:** 2026-08-03
**Status:** Accepted, quorum requirement amended by ADR-006
**Review date:** 2026-09-15

## Context

The independent-review transport could prove that a fresh different model saw
the exact candidate, yet still return a false clean result when the acceptance
packet did not contain executable evidence for product-scale, reconciliation,
rounding, generated-artifact freshness, or repository-hygiene risks. A later
production review of an unrelated report change found export cardinality above
the Excel row limit, an omitted transaction class, rounding drift, a stale
generated client, and repository-only tooling files after an earlier reviewer
had reported `PASSED`.

The A29 GPG-003 Terra review also found a concrete orchestration defect: a clean
integration response could erase a blocking unit finding. The methodology had
strong provenance and isolation controls, but no release gate measuring blocker
recall, missing-evidence detection, finding retention, or false blocks.

## Decision

Keep the approved nine-point plan and strengthen its existing review, oracle,
merge-gate, security, preflight and canary points. Do not add a tenth point.

1. Every active acceptance criterion declares a closed `reviewEvidence` mapping
   from generic impact classes to exact-tree machine-oracle IDs. The active
   `reviewPolicy` declares all required impact classes. Missing, failed,
   duplicate, foreign-tree or uncovered evidence is `UNVERIFIED` before model
   dispatch.
2. The isolated machine oracle is the read-only explorer. It runs declared
   project/domain probes in disposable exact-candidate checkouts, with the
   Verification Loop's bounded shell-free transport and no reviewer secrets.
   The semantic reviewer receives the frozen acceptance, machine and coverage
   graph; it cannot replace a missing oracle with prose.
3. The host is the sealed adjudicator for aggregation. It deterministically
   unions every unit, integration and reviewer finding/unverified contour.
   Later clean output cannot remove earlier negative evidence.
4. High and unknown risk require at least two clean independent provider/model/
   session identities. The ordered keyless route continues after the first
   clean pass only to satisfy this quorum. `BLOCKED` and `UNVERIFIED` remain
   terminal; typed `UNAVAILABLE` alone advances. Phase-one receipt v3 seals the
   complete reviewer list, attempt ledger, per-reviewer prompt/report bundle and
   host union. Receipt v2 remains valid only for the earlier single-reviewer
   policy.
5. Impact classes are domain-neutral. The initial closed vocabulary includes
   bounded output, correctness, reconciliation, numerical stability,
   generated-artifact freshness, scale, performance, compatibility, security,
   error handling, host parity and repository hygiene. Projects map their own
   concrete oracles to these classes instead of adding product-specific rules
   to the methodology.
6. A frozen generic efficacy corpus is a release gate. Deterministic mutations
   measure missing-evidence rejection and finding retention. Separately, a real
   no-tools keyless reviewer sees semantic candidates without their hidden
   expected-fault labels; the replay verifier reconstructs every prompt and
   binds the current producer/manifest hashes, model, transport, distinct
   sessions and host runtime. Fresh WSL and native-Windows reports must each
   achieve 100% critical/high blocker detection, at least 90% medium detection
   and at most 10% false blocks on clean controls. The local receipts retain the
   methodology's honest-host limitation and do not claim provider attestation.
7. Merge readiness additionally requires an evidence-complete exact candidate,
   clean checkout/generation/typecheck where declared, repository hygiene, a
   non-Draft PR, current live coordinates and a route-bound adjudication.
8. Every escaped blocker is converted to a sanitized generic regression case.
   Thresholds and the frozen corpus change only through a versioned, reviewed
   methodology update; reviewer narration cannot alter them.

## Alternatives considered

### Only improve the reviewer prompt

Rejected. A prompt cannot manufacture production-scale data, generated-client
freshness, reconciliation totals or exact export bounds that were never
measured and attached.

### Give a model unrestricted repository/production tools

Rejected. It increases secret, mutation and prompt-injection exposure and makes
the result less reproducible. Required exploration belongs in declared isolated
machine oracles; external production evidence must be sanitized and hash-bound.

### Majority vote without evidence coverage

Rejected. Multiple reviewers can share the same blind spot. Quorum is useful
only after the evidence graph is complete and host union is non-erasable.

## Consequences

- High/unknown review costs up to two provider calls (or two hierarchical
  review sets) and blocks when a second independent transport is unavailable.
- Projects must make business invariants, data profiles and operational bounds
  executable instead of relying on reviewer intuition.
- Existing acceptance contracts remain readable; evidence-first enforcement is
  activated explicitly by `activeFollowup.reviewPolicy`.
- GPG-003 and the refined 9/9 plan cannot close until fresh exact-candidate
  adjudication, merge/release evidence and clean installed-host proof exist on
  both WSL and native Windows.
