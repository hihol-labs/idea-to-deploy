# SCOPE_LOCK — Q6-SETUP

## Current task
Continue the owner-approved RSI order at Q6 setup (ADVISORY v4 §§4,5,8,10). The one active unit is Q6-SETUP, medium risk. The authoritative final unit criterion is GOAL.json units[id=Q6-SETUP].criterion; do not duplicate it here.

## Allowed change areas
- benchmarks/cmp/: preregistered protocol, stdlib freeze/validate/reconcile/read-only score instrument, operator/data-source recipe.
- tests/verify_cmp_protocol.py and its normal run-all/meta-review/Windows CI registration; derived impact map.
- Q6 task/acceptance/scope/goal/state/event bookkeeping and session handoff. Harness lifecycle events and decisions remain source evidence.

## Acceptance boundary
Pre-commit acceptance establishes deterministic behavior on explicitly synthetic fixtures and compatibility with real ITD receipt/event shapes. It does not assert a real campaign exists before merge. After accepted merge, the operator initializes the actual campaign from clean merged code; the unit remains in_progress until its campaign validator and goal verifier pass.

## Exclusions
D3 statistics execution/effectiveness, reward or policy integration, automatic lineage inference, daemon/scheduler, production-model selection, unrelated route/runtime/freshness debt repairs, and subsequent plan items. No production signal is enabled by setup. Observation consumes no WIP unit.

## Evidence/previous work
Baseline: no prior CMP instrument and zero prospective pairs;37 canonical GOAL verifications in prior90d is all-unit history, not eligible-root flow. Budgets, statistical preregistration, missing/tie/exposure rules, sources and rollback live in the single protocol/task contract. REL-1.103.0 is already closed in main829ffaf; its older scope is preserved in Git history, not active here.
