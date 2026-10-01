# Task Contract — TIER-WORDING-2 strict-class tier independent of goal wording on a path-list scope

- **Scope:** `skills/_shared/itd_risk_classes.py`: the goal text stops being a strict-class source
  when the first line of the Current Task opens with the unit being activated (`names_unit`,
  unchanged) AND every non-blank line of the Allowed Change Areas is one list item of the
  TIER-SOURCE-1 grammar (`_TEST_ITEM_RE`, unchanged) holding exactly one path that is a test path
  (`is_test_path`, unchanged) or one concrete file (`is_file_path`, new: the same ASCII set, no `*`
  or `?`, no `..` anywhere, a last segment with a non-empty stem and an extension of the closed set
  `_FILE_EXTS`) AND the SCOPE_LOCK keeps the plain layout (`plain_scope_layout`, added after
  /review r1 and redesigned after checker c1: every item `hooks/wip-gate.sh` reads - `gate_items`
  mirrors its reader - is a line of the section the strict reader read, and no ATX or setext
  heading only starts with a scope title). `path_list` / `path_list_scope` replace `tests_only_scope` in
  `match_strict_class` and `exempt_goal_hit`. `skills/task/scripts/itd_unit_log.py`: the
  `riskTierExempt` reason and the printed line name "a list of paths" for a scope that is not
  tests-only (a tests-only scope keeps its reason), and the unit-binding hint is printed for a
  path list. Owner decision 2026-10-01 (variant A); it supersedes the 2026-09-26 rule "a scope
  with a non-test path keeps the goal as a source". New oracle `tests/verify_tier_wording.py`
  (run-all CORE); `tests/verify_tier_source.py` re-pins five former floor cases (mixed-scope,
  lookalike-testdata, lookalike-contest, lookalike-docs, openapi-spec-not-a-test) as path lists.
  Docs: ADR-011 amendment 2026-10-01, `skills/task/SKILL.md` Step 3.5, CHANGELOG Unreleased,
  BACKLOG P1 status.
- **Verification Standards:** the unit verificationCommand exits 0 on the candidate tree; the new
  oracle is RED on the pre-fix matcher (recorded: `FAILED: 87 failed (212 passed)`, no crash,
  `.itd-memory/verification-loop/reports/TIER-WORDING-2-red-first.log`) and GREEN after;
  `--mutations` of both tier oracles are all lethal, including the pre-fix bytes of `90c4a16`;
  `tests/build_impact_graph.py --check` exit 0; `tests/run-all.sh --quick` last line
  `DONE fails:none`; medium route - `/review` before the multi-file commit and a targeted
  fresh-session different-provider checker (gpt-5.6-sol) before the PR, adjudicated receipt under
  claim `TIER-WORDING-2`.
- **Exclusions:** the strict classes of `PROPORTIONALITY_POLICY.json`; binding the tier to the real
  diff at `verified` (variant B, a separate high unit); `hooks/wip-gate.sh` and the shared section
  reader (BACKLOG P2 2026-09-26); STOPRULE-STUB-1; an extensionless file name such as `Dockerfile`
  (lexically a directory name - such a scope keeps the goal, so `extensionless-file-in-scope`
  stays a floor case); Windows CI wiring of the new suite.
- **Known host condition (not this unit):** `tests/verify_risk_tier_default.py` check
  `methodology-repo-has-no-policy-file` is red on the canonical checkout because of a local
  git-ignored `.itd/COMPLETION_POLICY.json` (dated 2026-09-12); it is red before this change too
  and green on any exact-candidate copy, which carries tracked files only.
