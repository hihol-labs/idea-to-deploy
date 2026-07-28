# Scope Lock — API-001 verifiable external reviewer

## Current Task

Implement all nine approved API-reviewer recommendations as one high-risk
PIV-lite unit. The reviewer must be a provider-neutral checker transport inside
the existing Verification Loop, never a parallel completion authority.

## Allowed Change Areas

- shared reviewer policy, adapter, schema, sanitizer, routing, telemetry, and
  exact-candidate receipt integration under `skills/_shared/`
- `/cross-review` orchestration and documentation needed to consume the shared
  transport while preserving local advisory/fail-open semantics
- GitHub Actions and deterministic helpers that enforce valid independent
  evidence before merge without making one provider a permanent dependency
- focused fixtures/tests for egress, schema, limits, degradation, provenance,
  candidate binding, routing, cost budgets, CI behavior, and host parity
- ADR, Verification Loop, host-adapter, CI, README, changelog, and version
  metadata needed to describe and release the behavior
- `.itd/` and `.itd-memory/` task/evidence records for this exact unit

## Forbidden Change Areas

- weakening the existing machine oracle, exact staged-tree binding, WIP=1,
  immutable receipt, risk-route, or maker/checker separation rules
- treating same-model same-provider review as a high/unknown-risk checker
- treating API/CLI errors, schema errors, partial coverage, truncation, missing
  consent, missing provenance, or budget exhaustion as `PASSED`
- mandatory use of one named provider when another policy-eligible checker can
  produce valid evidence
- silent diff truncation, raw secret/diff persistence, API-key persistence, or
  automatic external egress without explicit repository/organization consent
- executing pull-request code with repository API secrets
- a new lifecycle skill, second state plane, owned scheduler, automatic merge,
  branch-protection mutation, publishing, deployment, or direct cache edits

## Acceptance Boundary

Local review remains advisory and fail-open with an explicit typed availability
status (`UNAVAILABLE` for transport failure, `UNVERIFIED` for invalid or
insufficient evidence). Merge acceptance is fail-closed on the absence of policy-eligible,
exact-candidate checker evidence, not on the outage of a particular provider.
The final candidate must pass the focused API-reviewer oracle, host-adapter
parity, methodology meta-review, quick regression, full regression, and a
fresh high-risk Verification Loop adjudication.
