# Scope Lock — GPG-001 global PR/API gate

## Current Task

Implement and accept the executable broker slice of the approved fail-closed
global review control plane: exact GitHub candidate acquisition, maker-aware
API dispatch, budget settlement, App Check Run publication, durable receipt
orchestration with crash recovery, and bounded HTTP webhook service. Local preflight, GitHub
deployment/rulesets, doctor, canaries, and release remain later GPG-001 slices
and are not claimed by this candidate.

## Allowed Change Areas

- review-broker orchestration and HTTP service
- complete GitHub candidate acquisition and canonical diff construction
- maker-aware Responses API dispatch and primary-usage budget settlement
- exact App Check Run preparation/publication/observation, durable review or
  typed failure evidence, and interrupted-publication recovery
- focused orchestration, service, policy, and primitive regression tests
- `.itd/` and `.itd-memory/` task/evidence records for `GPG-001`

## Forbidden Change Areas

- storing API/App private keys in the repository, plugin cache, prompts, logs,
  receipts, Windows user environment, or WSL shell profiles
- executing candidate code in any process that can read reviewer credentials
- allowing CLI/OAuth reviewers, a caller-supplied status, `neutral`, `skipped`,
  API outage, zero balance, stale SHA/base, oversized input, unknown maker, or
  missing oracle to satisfy the required cloud gate
- silently truncating a candidate or accepting a same-name check from an
  unbound GitHub integration
- weakening WIP=1, exact-candidate binding, maker/checker separation,
  App-bound checks, human merge authority, or existing Verification Loop gates
- editing the installed plugin cache instead of publishing and installing a
  new ITD release

## Acceptance Boundary

This slice is accepted only when the focused orchestration/server suites,
policy and primitive regressions, and methodology meta-review pass on the exact
staged tree; secret scrubbing reports no redaction; and a fresh different-model
full checker returns an empty-finding verdict that the high-risk Verification
Loop adjudicates. Acceptance of this slice does not complete GPG-001.
