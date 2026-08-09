# ADR-003: external reviewers are checker transports, not completion authorities

**Date:** 2026-07-28
**Status:** Superseded for pre-PR routing by ADR-004; retained for the optional
paid API adapter
**Supersedes:** the provider-order and native-fallback portions of ADR-002;
ADR-002's default-off egress and local non-blocking decision remain active.

> Historical scope: the decisions below now apply only to the separately
> configured paid API adapter. ADR-004 owns every default pre-PR review path.

## Context

The legacy `/cross-review` chain depended on locally authorized Codex/Gemini
CLIs and fell back to a native self-review. That kept development moving but
could not guarantee an external opinion and could blur `UNAVAILABLE` into a
plausible-looking review. ITD now has a stronger exact-candidate Verification
Loop, so adding a separate GPT gate would create conflicting acceptance planes.

Automated egress also remains a governance decision. Pattern redaction cannot
recognize proprietary logic or customer data by meaning, and a paid provider can
be unavailable because of network, quota, billing, or model retirement.

## Decision

ITD exposes one provider-neutral external-checker transport:

- managed OpenAI Responses API (`gpt-5.6-sol` default) for automated egress;
- Codex CLI and Gemini CLI retained as host-native alternatives, but excluded
  from automated evidence until a no-tools/no-secret sandbox and complete cost
  telemetry are enforceable.

The policy routes by host-observed maker provider/model/session and risk. It
prefers a different vendor, may accept a different model from the same vendor
where the Verification Loop permits it, and never lets the same model/provider
satisfy a high/unknown full checker.

Local `/cross-review` remains explicit opt-in and advisory. Provider or policy
failure is typed `UNAVAILABLE` or `UNVERIFIED` and does not stop development.
For protected pull requests, the same transport is fail-closed only through a
machine → checker → adjudication → check Verification Loop. The gate requires
eligible evidence, not a particular provider.

The transport uses one sanitizer and rejects incomplete coverage, binaries,
unsafe paths, oversize diffs, residual credentials, invalid/contradictory
verdicts, stale candidates, incomplete provenance, and exhausted budgets. It
does not silently truncate. Raw HTTP requests/responses and the API key are
never persisted.

## Consequences

- API availability improves without deleting Codex/Gemini alternatives; their
  current CLI form remains advisory rather than protected evidence.
- A GPT review of GPT-authored code is labelled same-vendor; an exact same-model
  review cannot satisfy high/unknown risk.
- PR merge liveness depends on at least one eligible reviewer. Outages remain
  visible and can be handled only through GitHub's audited administrative
  bypass, never by manufacturing PASS.
- The protected CI environment must own `OPENAI_API_KEY`, a separate maker
  provenance HMAC key, and branch-protection configuration. Unsigned labels or
  dispatch strings are rejected, and fork code is never executed while either
  secret is present.
- Pricing is dated telemetry in policy, not a permanent methodology promise.
  Observed token use and cost are budgeted and measured.

## Rollout

1. Deterministic fake-transport and mutation suite.
2. Default-off shadow fixture with live outcomes explicitly `UNOBSERVED`.
3. Opt-in live shadow runs measuring availability, latency, cost, unique
   actionable findings, false positives, and base-review duplication.
4. Protected CI environment for selected high/unknown-risk repositories.
5. Broader adoption only after measured value exceeds nuisance and merge-delay
   costs.
