# TIER-WORDING-2 strict-class tier independent of goal wording on a path-list scope

## Current Task

- TIER-WORDING-2: for scopes that are not tests-only the strict-class tier no longer depends on
  the wording of the unit goal: synthetic pairs (a template goal vs a detailed description
  containing a strict word) over the same non-test Allowed Change Areas get one tier, while a
  strict-class path or keyword inside the Allowed Change Areas still forces high; the new oracle
  `tests/verify_tier_wording.py` is RED on the pre-fix matcher and GREEN after, and
  `tests/verify_tier_source.py` and `tests/verify_risk_tier_default.py` stay green. The criterion
  and the verificationCommand live ONLY in `.itd-memory/GOAL.json`. Rule approved by the owner on
  2026-10-01 (variant A, `.itd/DECISIONS.md`).

## Allowed Change Areas

- `skills/_shared/itd_risk_classes.py` - the path-list predicate (`is_file_path`, `path_list`,
  `gate_items`, `plain_scope_layout`, `path_list_scope`) and its use in `match_strict_class` /
  `exempt_goal_hit`; `is_test_path`, `tests_only`, `names_unit`, the section reader and the
  keyword/path matching are not changed.
- `skills/task/scripts/itd_unit_log.py` - the reason text of `riskTierExempt` and the hint for a
  path-list scope that is not bound to the unit.
- `tests/verify_tier_wording.py` (new)
- `tests/verify_tier_source.py` - re-pin of the floor cases whose scope is now a path list, and
  the docstring that describes them.
- `tests/run-all.sh` - register the oracle in CORE.
- `docs/adr/ADR-011-default-risk-tier-low.md` - amendment 2026-10-01.
- `skills/task/SKILL.md` - Step 3.5 text of the exemption.
- `CHANGELOG.md` - the Unreleased entry.
- `.itd/IMPACT_GRAPH.json` - rebuilt by `tests/build_impact_graph.py`.
- `.itd-memory/contracts/TIER-WORDING-2.md` (new)
- `.itd-memory/GOAL.json`, `.itd-memory/STATE.json`, `.itd-memory/events.jsonl` - status
  transitions only through the goal harness.
- `.itd/DECISIONS.md`, `BACKLOG.md`, `.itd/SCOPE_LOCK.md` (this file) - records.
- `.itd/ACCEPTANCE_CONTRACT.json` - the TIER-WORDING-2 activeFollowup and criteria
  TIER-WORDING-2-1-oracle, TIER-WORDING-2-2-ledger.
- Live-model benchmark evidence pin - only if Gate 1 requires a re-record after the `skills/`
  change, through the documented re-record route.

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- `skills/_shared/PROPORTIONALITY_POLICY.json` - the strict classes, their keywords and paths.
- `hooks/wip-gate.sh` and the section reader shared with it (BACKLOG P2 2026-09-26 stays a
  separate unit); the matcher only mirrors the hook's reader read-only (`gate_items`).
- Binding the tier to the real diff at `verified` (variant B - a separate high unit by the owner's
  decision).
- STOPRULE-STUB-1 (BACKLOG P1 2026-10-01).
- The unit criterion and verificationCommand; editing unit statuses by hand.
- Merge and push - only on the owner's explicit command.

## Review Rule

Medium tier: `/review` before the multi-file commit and a targeted independent checker from a
fresh session and a different model/provider (gpt-5.6-sol pre-PR). If the diff touches an area
outside allowed scope, pause and reclassify the task before continuing.
