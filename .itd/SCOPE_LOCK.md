# Scope Lock — GENG-STRATEGY: formalize the approved Graph Contract Layer amendments (docs-only)

## Current Task

Single advisory/planning unit (opened 2026-08-10 after GPG-004 closed and
v1.96.0 shipped): formalize the three user-approved amendments to the GENG
Graph Contract Layer plan (project memory `project_geng_plan_amendments.md`,
approved 2026-08-07) as durable repo docs. No code, no gates, no skill/hook
surface touched.

## Allowed zones

- `docs/adr/ADR-009-graph-contract-layer.md` (new decision record)
- `BACKLOG.md` (new "P1 — GENG" section + Last reviewed date)
- `.itd/SCOPE_LOCK.md` (this contract, rewritten for the unit)

Nothing else. `.itd/DECISIONS.md` (untracked journal) received the paired
durable entry 2026-08-10.

## Acceptance (this unit)

1. ADR records variant B invariants (no owned runtime; human authorizes exact
   graphDigest; Verification Loop is the sole completion authority;
   durability = `.itd-memory` + receipts) and the three amendments:
   numbering (ADR-009; ADR-008 stays reserved for the reviewer-independence
   ladder ADR per `.itd/DECISIONS.md` 2026-08-09), GENG-004 entry gated on a
   dedicated Codex isolated-transport stability check, incremental proof
   graph as a separate GENG-003 exit criterion.
2. User approved the formalization (AskUserQuestion, 2026-08-10); /review ran
   before commit (PASSED_WITH_WARNINGS, both Important findings fixed in the
   candidate).
3. Machine oracle: `tests/meta_review.py` green (docs-vs-code consistency,
   Critical = 0) on the exact committed-head candidate.

## Risk tier

low — docs-only additive planning artifacts; no executable surface, no
schema, no gate semantics changed. Route per verification-loop-v1: machine
evidence, no independent checker (machine_only).

## Out of scope

The GENG-000…010 program text (enters the repo as a /goal unit ledger when
GENG-000 starts), any GENG code, LAUNCH_PLAN.md (locked to the vibe-coding
enrichment scope), ledger-drift housekeeping (G-001/PE5-015).
