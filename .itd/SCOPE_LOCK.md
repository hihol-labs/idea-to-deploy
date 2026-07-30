# Scope Lock — GPG-001 global PR/API gate

## Current Task

Implement and accept the broker-bootstrap plus local/global gate-control slice
of the approved fail-closed review control plane: a deployable central broker,
official GitHub App manifest bootstrap, immutable enrollment operator, tracked
exact-candidate machine oracle, Ed25519 maker provenance, guarded Draft PR
creation, canonical GitHub ruleset management, server-check waiting,
adoption/registry/doctor diagnostics, and the centrally pinned organization
ruleset workflow for the machine check. Live App/ruleset deployment, negative
canaries, final
release publication, and global installation remain later GPG-001 slices and
are not claimed by this candidate.

## Allowed Change Areas

- global gate registry, canonical ruleset payload/drift checks, and doctor
- dedicated GitHub App manifest bootstrap and live enrollment observation
- central broker deployment, readiness, operator, and secret-file boundaries
- protected-base contract and pinned central machine-oracle workflow transport
- local Windows/WSL guarded PR creation and direct-main push guard
- Ed25519 maker-provenance creation/submission with retry-safe local evidence
- exact-current PR and expected-integration Check Run waiting
- focused broker, deployment, manifest, local gate, CLI, oracle, hook,
  workflow, release, host-adapter, and mutation tests
- adoption, CI, API reviewer, deployment, and operator documentation
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

This slice is accepted only when the focused gate/CLI/oracle/hook/workflow
suites, policy and broker regressions, host-adapter checks, and methodology
meta-review pass on the exact staged tree; secret scrubbing reports no
redaction; and a fresh different-model full checker returns an empty-finding
verdict that the high-risk Verification Loop adjudicates. Acceptance of this
slice does not complete GPG-001.
