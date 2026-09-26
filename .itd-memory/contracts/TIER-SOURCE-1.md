# Task Contract: TIER-SOURCE-1 - tests-only scope: the goal text stops forcing a strict class

## Scope
- `skills/_shared/itd_risk_classes.py`: `is_test_path(token)` - an ASCII token in `[A-Za-z0-9_./*?-]` (no `\`) without a
  `..` segment, with a directory segment `tests`, `test` or `__tests__`, or a code file named
  `test_*.py`, `*_test.*`, `*.test.*`, `*.spec.*`, `conftest.py`; `tests_only(areas)` - every
  non-blank line matches the whitelist grammar `_TEST_ITEM_RE` (one `-`/`*`/`+`/`1.`/`1)` item, one
  path, an optional `(new)`/`(updated)`, spaces or tabs only) and names a test path (owner decision 2026-09-26 after REDESIGN_OR_DISCARD);
  `names_unit` - the first line of the Current Task opens with the unit id (a stale scope may
  raise a tier, never lower it); `match_strict_class` ignores the goal (keywords and paths) under
  both conditions; `exempt_goal_hit` returns the goal hit that was set aside.
- `skills/task/scripts/itd_unit_log.py activate`: prints the set-aside hit and records
  `riskTierExempt{class,match,reason}` in `STATE.currentUnit`; tier is not raised.
- `skills/goal/scripts/itd_goal_verify.py`: the STATE projection drops `riskTierExempt`.
- Docs: `skills/task/SKILL.md`, ADR-011 amendment, SCOPE_LOCK template, CHANGELOG `[Unreleased]`.
- `tests/verify_tier_source.py` (new, in `tests/run-all.sh`, in `.itd/IMPACT_GRAPH.json`).

## Verification Standards
- `sh skills/_shared/itd_py.sh tests/verify_tier_source.py && sh skills/_shared/itd_py.sh tests/verify_risk_tier_default.py`
  (unit verificationCommand): synthetic pilot-style pairs (template + docstring vs a detailed
  description with a strict word) give one tier on a tests-only scope, both through
  `match_strict_class` and end to end through `itd_unit_log.py activate`; a money, auth or secrets
  path and a strict keyword inside a tests-only scope stay `high`; a mixed scope, a pathless scope,
  no SCOPE_LOCK and a `..` escape keep the goal as a source.
- RED on the pre-fix bytes (`06bee64`), GREEN after; `--mutations` - every mutation lethal.
- `tests/meta_review.py` clean; `bash tests/run-all.sh --quick` -> `DONE fails:none`.
- `/review` medium: machine receipt + targeted fresh-session checker + adjudication.

## Root cause
- `match_strict_class` treated the goal text as an unconditional source, so on a tests-only scope
  the tier followed the wording of the module description (RETRO-PILOT-LOW-1 obs. 1-2), not the change.

## Exclusions
- `PROPORTIONALITY_POLICY.json` (hash-pinned; no change); tier by paths only for non-test scopes; strict check of a goal unit's
  criterion at `/goal --activate`; other pilot findings; the release (REL-1.106.0).
- Pilot project code as fixtures - all fixtures are synthetic.
