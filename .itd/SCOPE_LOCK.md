# Scope Lock — HE-001 harness lifecycle and trust

## Current Task

Implement the approved Harness Engineering improvements as one medium-risk
PIV-lite unit: evidence-earned control provenance and retirement, a bounded
ablation pilot, MCP/tool prompt-trust inventory, and a common hook-output
conformance contract.

## Allowed Change Areas

- lifecycle/provenance and ablation contracts under `docs/`
- tool capability/trust templates and their validators
- `/adopt`, `/security-audit`, and `/retro` instructions needed to consume the
  contracts without adding a second state plane
- hook output policy/registry and focused behavioral conformance tests
- Harness Engineering map, contracts documentation, changelog/version metadata,
  host-adapter documentation, and test registration required for consistency
- `.itd/` and `.itd-memory/` task/evidence records for `HE-001`

## Forbidden Change Areas

- literal “every mistake becomes a rule” behavior that bypasses ITD's threshold
  of two independent signals or one production incident
- automatic MCP/tool installation, trust, update, permission grant, or external
  write
- a new runtime, daemon, lifecycle skill, state plane, unbounded Ralph loop, or
  additional completion authority
- blanket claims that all hooks/skills have ablation coverage
- weakening WIP=1, exact-candidate binding, Verification Loop risk routing,
  maker/checker separation, or human merge/retirement authority
- adding hooks merely to enforce the new metadata

## Acceptance Boundary

The feature is accepted only when closed-schema mutation tests prove the new
metadata cannot be bypassed, selected hooks demonstrate silent success and
actionable failure, tool/MCP prompt trust fails visibly when unknown, the
project's adapter/meta/quick regressions pass, and a fresh targeted checker
accepts the exact staged candidate through the existing Verification Loop.
