# Claude Code Implementation Guide

This is a future implementation guide, not implemented code. Read [architecture](PROJECT_ARCHITECTURE.md), [PRD](PRD.md), [strategy](STRATEGIC_PLAN.md), [plan](IMPLEMENTATION_PLAN.md), and [project instructions](CLAUDE.md) first. Work one step at a time; update the specification before changing behavior. The current session creates documentation only.

## Invariants for every prompt
Keep Python 3.11, Click, Rich, dataclasses, local pip installation and a single process. No persistence, auth, API, server, cloud or Kubernetes. No full-file loading. Exact counters and UA set obey independent caps; abort without a report when exhausted.

Preserve complete exit codes: 0 success/help/version; 1 IO/output/runtime failure; 2 invalid usage; 3 invalid log data; 4 unique-cardinality exhaustion.

Hourly percentage is `100 × hourly_request_count / total_valid_requests`. UA percentage is `100 × unique_user_agents / total_valid_requests`, excluding missing UAs from the numerator only. Never substitute approximations. All commands below are future checks; no product tests were run while preparing this blueprint.

## Step prompts
1. **Package:** “Execute plan step 1 only. Add pyproject.toml, entry point and errors. Test help and option conflicts before wiring input. Run the step commands; report observed results. Preserve codes 0/1/2/3/4.”
2. **Models:** “Execute step 2. Define dataclasses and hand-calculated combined-log fixtures with ties, missing UA, UTC rollover and empty data. Run model tests. Keep output schema aligned with CLI Interface.”
3. **Parser:** “Execute step 3. Add bounded line reader and combined parser, escaped-field handling, strict UTF-8, IP/time/status validation and query stripping. Test long-line draining and stdin ownership. Run parser and reader tests.”
4. **Aggregation:** “Execute step 4. Implement exact counters, 24 UTC buckets, deterministic top ten, and UA set. Test late winners and each collection at cap and cap+1. Verify code 4 with stdout empty; do not catch it as generic code 1.”
5. **Terminal:** “Execute step 5. Wire CLI, malformed-line handling and Rich rendering with literal escaped data. Test color behavior and codes 0/1/2/3/4 end to end. Run terminal and CLI tests.”
6. **Exports:** “Execute step 6. Add schema-versioned JSON and unified long-form CSV per architecture. Test quoting, numeric percentages, stdout/stderr separation, and broken pipes. Compare with golden report and run export tests.”
7. **Performance:** “Execute step 7. Create fixed-seed benchmark generator and runner accepting the documented flags. Measure full 1 GB runs for all formats, three repeats, with laptop details, cache state and RSS. Record actual results; profile failures without relaxing exactness.”
8. **Readiness:** “Execute step 8. Run the full suite and coverage, build a wheel and smoke-test an isolated local installation including all five exit codes. Update README and status only from evidence. Stop before publication, push or deployment.”

## Evidence and failure handling
Each step uses its plan verification commands and relevant tests. Full readiness commands: `python -m pytest --cov=nginx_lens --cov-branch --cov-fail-under=90`, `python -m build`, `python -m pytest tests/test_install.py`. Dependencies and these test files are planned work. Never treat a written test or a benchmark estimate as a passed run. For failures record command, observed error and next fix; do not mark the step complete.

## Session handoff
Save continuity using the repository-local session-save skill after a significant block. Record changed files, actual tests, remaining work, and next step. External adversarial review is handled separately by the harness; do not fabricate a review artifact or verdict. See [README](README.md) for intended operator usage.
