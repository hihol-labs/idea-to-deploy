# Scope Lock

## Current Task

- GLV2-CI-001: refresh live-methodology evidence and make PR #355 CI green, authorized by the owner on 2026-10-13.

## Allowed Change Areas

- `tests/OUT_OF_MIRROR.json`
- `tests/fixtures/live-model-evidence/`
- `tests/ROOT_CAUSE-PR355-ci.md`
- `.itd/SCOPE_LOCK.md`
- `.itd/ACCEPTANCE_CONTRACT.json`
- `.itd/IMPACT_GRAPH.json`

## Verification

Run the canonical live-methodology benchmark through native Codex with explicit Astra model; preserve old runs and bounded negative evidence. Run the unchanged evidence oracle, drift guard on both hosts, result-verifier self-test, cumulative quick regression, independent exact-candidate review and guarded publication. Both GitHub CI checks must pass on the updated head.

## Forbidden Change Areas

Graph implementation, optional policy and sealed study stay unchanged. Do not repeat Graph actors, judges or scoring. No Claude CLI, paid API fallback, weakened freshness checks, fabricated evidence, merge or production deployment. Preserve previously accepted GLV2-001 and owner adjudication in commit 0890d18 and local receipts.
