# TIER-SOURCE-1 - tests-only scope: the goal text stops forcing a strict class

Unit `TIER-SOURCE-1` of the goal TIER-SOURCE-1 -> REL-1.106.0 (`.itd-memory/GOAL.json`), risk tier
`medium`. Source: `BACKLOG.md` P1 2026-09-25 and `docs/retros/RETRO-PILOT-LOW-1.md` observations 1-2.
The criterion lives in `.itd-memory/GOAL.json` and is not restated here. The rule and the rejected
alternative are in `.itd/DECISIONS.md` 2026-09-26.

## Current Task

TIER-SOURCE-1: when every path in the Allowed Change Areas of a unit's `.itd/SCOPE_LOCK.md` is a test path, the
strict-class matcher ignores the goal text, provided the Current Task opens with the unit
being activated; strict-class paths and keywords inside the areas still
force `high`; a mixed or pathless scope keeps the goal as a source.

## Allowed Change Areas

- `skills/_shared/itd_risk_classes.py` - test-path predicate, tests-only scope check,
  goal exemption in `match_strict_class`, `exempt_goal_hit` for the audit note.
- `skills/task/scripts/itd_unit_log.py` - `activate` prints and records `riskTierExempt`.
- `skills/goal/scripts/itd_goal_verify.py` - the STATE projection drops `riskTierExempt`
  like `riskTierMatch` and `riskTierForced`.
- `skills/task/SKILL.md`, `docs/templates/itd/SCOPE_LOCK.md` (unit id in Current Task),
  `docs/adr/ADR-011-default-risk-tier-low.md` (amendment), `CHANGELOG.md` (`[Unreleased]`).
- `tests/verify_tier_source.py` (new), `tests/run-all.sh`, `.itd/IMPACT_GRAPH.json`.
- `tests/fixtures/live-model-evidence/` - re-record on the final tree (pin of the methodology tree).
- Ledger and records: `.itd-memory/GOAL.json`, `.itd-memory/GOAL-2026-09-26.json`,
  `.itd-memory/STATE.json`, `.itd-memory/events.jsonl`, `.itd-memory/contracts/TIER-SOURCE-1.md`,
  `.itd/SCOPE_LOCK.md`, `.itd/DECISIONS.md`, `.itd/ACCEPTANCE_CONTRACT.json`, `BACKLOG.md`.

## Forbidden Change Areas

- `skills/_shared/PROPORTIONALITY_POLICY.json` (its SHA-256 is pinned by `WORKING_DEADLINE_POLICY.json`
  and both benchmark corpora; the exemption is documented in the module, ADR-011 and `/task`).
- Tier decision by paths only for non-test scopes (rejected alternative).
- Checking a goal unit's criterion with the strict matcher at `/goal --activate` (separate BACKLOG item).
- Other pilot findings (stale `.pyc` in `/test` Step 5.5, low-route friction).
- The release itself (unit `REL-1.106.0`).

## Verification

- `sh skills/_shared/itd_py.sh tests/verify_tier_source.py && sh skills/_shared/itd_py.sh tests/verify_risk_tier_default.py`
  (unit verificationCommand); `tests/verify_tier_source.py --mutations` lethal; RED on the
  pre-fix bytes of `06bee64`.
- `sh skills/_shared/itd_py.sh tests/meta_review.py`, `bash tests/run-all.sh --quick` -> `DONE fails:none`.
- `/review` medium: machine receipt, targeted fresh-session checker, adjudication.
