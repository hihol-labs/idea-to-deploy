# Claude Code Guide: Nginx Log Lens

## How to use this guide
Implementation has not started. Run one prompt at a time, inspect the result and execute its verification commands from [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Use [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) as the interface source, [PRD.md](PRD.md) for acceptance, [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) for scope, [README.md](README.md) for usage and [CLAUDE.md](CLAUDE.md) for session rules. These prompts authorize future local implementation only when a developer starts that phase.

## Contract carried by every prompt
Python 3.11, Click, Rich, dataclasses; local single process, file/stdin, exact capped streaming aggregates. No authentication, database, HTTP API, server, cloud or Kubernetes. No raw-log diagnostics, telemetry or network ingestion. Preserve deterministic schemas and the complete exit-code contract **0/1/2/3/4**: 0 success/help/version; 1 I/O/runtime failure; 2 invalid usage; 3 no valid requests; 4 resource failure as specified below.

Exit code 4 means unique-cardinality exhaustion.

Hourly percentages use `100 × hourly_request_count / total_valid_requests`. UA share uses `100 × unique_user_agent_count / total_valid_requests`. Do not substitute approximate counters, remap exit 4, silently truncate input or emit partial reports on pre-render failure. Add meaningful tests and actually run the specified suite. Report failures plainly and update the spec before changing behavior.

## Prompt 1: Package and CLI contract
> Implement only step 1 of IMPLEMENTATION_PLAN.md. Read the architecture's CLI Interface first. Create pyproject.toml, src/nginx_log_lens/__init__.py, cli.py, models.py and tests/test_cli.py. Register the console entry point; validate input/options and expose help/version. Follow the shared 0/1/2/3/4 contract above. Run the step's install and tests; report real results and keep future steps pending.

## Prompt 2: Reader and parser
> Implement only step 2. Create reader.py, parser.py, tests/test_reader.py, tests/test_parser.py and the combined fixture. Follow exact framing, strict UTF-8, nginx escape, timestamp, status, IP and query-stripping rules. Test oversized lines and malformed input without exposing raw records. Preserve the shared exit contract. Run the specified parser/reader tests and record results.

## Prompt 3: Rankings with bounds
> Implement only step 3 in aggregate.py and tests/test_rankings.py. Count every valid IP and only 4xx/5xx URL errors; rank exact totals with lexical ties. Guard each dimension before inserting a new key; exhaustion must propagate to code 4. Test eleven-key rankings, boundary statuses, repeated keys at capacity, and independent cap failures. Run step verification.

## Prompt 4: Hours and User-Agents
> Implement only step 4 in aggregate.py, models.py and tests/test_metrics.py. Keep source-offset hour buckets sorted by UTC instant, use the required percentage formula, and compute exact UA cardinality with missing UAs excluded only from the numerator. Enforce independent hour/UA caps and code 4. Test DST, A/A/B, no valid input and all-missing UAs; run step verification.

## Prompt 5: Output formats
> Implement only step 5 in render.py and tests/test_render.py. Follow the exact JSON/CSV schemas and deterministic ordering from CLI Interface. Use Rich literal rendering, neutralize terminal controls in text, and respect TTY/NO_COLOR/--no-color. Machine output must be parseable and ANSI-free. Verify numeric types, CSV round trips and empty errors. Run step tests, preserving all five exit codes.

## Prompt 6: End-to-end behavior
> Implement only step 6 in cli.py, tests/test_cli.py and tests/test_pipeline.py. Connect reading, parsing, aggregation and post-EOF rendering. Verify every exit in 0/1/2/3/4, each independent cap, file/stdin equivalence and stdout/stderr separation. Map broken pipes and output failures to 1, without traceback. Run step verification and record evidence rather than claiming readiness from code inspection.

## Prompt 7: Benchmark
> Implement only step 7. Create benchmarks/generate.py, benchmarks/run.py, benchmarks/RESULTS.md and tests/test_benchmark_fixture.py with the interfaces in the plan. Generate a local synthetic decimal-1-GB fixture within the architecture envelope; measure complete-command wall time and peak RSS for three runs. Record actual platform and fixture cardinalities. Exercise bounded failures separately. Preserve 0/1/2/3/4; do not call performance passed unless measurements meet the target. Run the step's verification commands.

## Prompt 8: Local release candidate
> Implement only step 8. Add MIT LICENSE, package verification and build extras; reconcile README, PRD, plan and guide against actual results. Run the full branch-coverage suite, build the wheel and test its isolated installation. Verify text/JSON/CSV and the full 0/1/2/3/4 contract. Record unresolved failures; do not publish, push, deploy or upload logs. Save continuity with /session-save. Product completion requires the documented release gates, not this planning document.

## Review and handoff
Before any implementation commit, run the full applicable suite and record the result. Keep WIP=1 and step status current in CLAUDE.md. The external harness owns the separate adversarial architecture review; no such review has run in this blueprint session. Future implementation review and security checks are still pending. Any publication or external action needs separate approval.
