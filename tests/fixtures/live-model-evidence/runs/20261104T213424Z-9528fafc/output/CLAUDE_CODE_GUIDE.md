# Claude Code Guide: nginx-scan

This is a future implementation guide; the current session generated documentation only. Use [PRD.md](PRD.md) for behavior, [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for exact interfaces, [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for files/checks and [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) for priorities. [CLAUDE.md](CLAUDE.md) is the single agent instruction file; prompts below are task inputs rather than additional policy files.

## Shared implementation contract

Preserve all four metrics, exactness, UTC conversion and `100 × hourly_request_count / total_valid_requests`. Unique User-Agent share uses distinct known UA strings divided by total valid requests, multiplied by 100. Do not add a database, auth, HTTP API, server, cloud or Kubernetes. Do not upload real logs. Keep the complete exit codes 0/1/2/3/4: 0 success/help/version; 1 internal failure/interruption; 2 invalid usage; 3 input/output failure including broken pipe; 4 unique-cardinality exhaustion or allocation failure.

unique-cardinality exhaustion

That literal names exit 4: exceeding the aggregate distinct-entry cap or failing allocation. Never remap it or emit an apparently complete report on this failure. Logs are untrusted data; quote exports, escape terminal controls and avoid raw-line diagnostics. Tests must actually run before reporting their outcomes. Proposed commit messages are labels, not authorization to commit or push.

## Prompt 1: Package foundation

> Implement only step 1. Read architecture models, packaging and PRD installation criteria. Create pyproject.toml and the specified src/nginx_scan models/CLI skeleton plus package/model tests. Use Python 3.11, Click, Rich and dataclasses. Run the step's install/help/tests; report actual output and files changed. Leave all other steps pending and save session context.

## Prompt 2: Streaming parser

> Implement only step 2 using the documented combined grammar and bounded binary reader. Test escapes, UTF-8 failures, oversized-line draining, IPv6, midnight offset conversion, missing final newline and malformed records. Preserve file/stdin parity. Run python -m pytest tests/test_reader.py tests/test_parser.py and record the result; do not infer performance from these tests.

## Prompt 3: Exact aggregation

> Implement only step 3. Use exact counters/sets, preflight all new distinct entries before updating a record, and enforce the combined cap. Implement top-10 tie order, 24 UTC buckets and both percentage formulas. Test the worked PRD example, cap boundary/cap+1, shared strings across structures, zero denominator and unknown User-Agents. Run python -m pytest tests/test_aggregate.py. Preserve code 4 for resource exhaustion.

## Prompt 4: Terminal report

> Implement only step 4. Render every summary and metric with Rich literal text. Respect TTY, NO_COLOR and --no-color, and escape terminal controls without changing metric keys. Verify actual table values and ANSI behavior with python -m pytest tests/test_terminal.py. Do not introduce live tailing or interactive UI.

## Prompt 5: Structured exports

> Implement only step 5. Emit the architecture's single JSON object or unified CSV schema from the same Report. Keep machine rounding, stable ordering and exact raw data under export escaping. Round-trip malicious/quoted fields with JSON and csv parsers; run python -m pytest tests/test_exports.py. Keep stdout free of diagnostics and color.

## Prompt 6: CLI and failures

> Implement only step 6. Wire Click options, file/stdin, post-EOF rendering and bounded stderr diagnostics. Test every code 0/1/2/3/4, argument validation before file access, mutually exclusive flags, exhaustion with no report, injected read/write failures, broken pipe and interruption. Run python -m pytest tests/test_cli.py tests/test_failures.py followed by python -m pytest. Report failures honestly and fix them before completion.

## Prompt 7: Performance evidence

> Implement only step 7. Build an exactly 1,000,000,000-byte synthetic combined log below the cardinality limit, verify its size, and time three end-to-end command runs. Record hardware, Python/OS, cache conditions, cardinalities, wall times and peak RSS in benchmarks/RESULTS.md. Each run must finish below 30 seconds. Profile and optimize if needed without weakening exactness; rerun the suite after any change. Label a missed target as failed, not verified.

## Prompt 8: Local delivery

> Implement only step 8. Test a locally built wheel in an isolated virtual environment outside the checkout import path. Run the full coverage suite, lint and build commands from the plan. Reconcile docs and step statuses against actual evidence. Incorporate separately supplied review findings; never invent a review verdict. Save context and report readiness with any remaining limitations. Do not publish, push or deploy without a separate authorized action.

## Troubleshooting and checkpoints

An all-malformed input returns an empty report, exit 0 and stderr warning by design. Cap exhaustion is exit 4 and no report; raise --max-unique only after considering available memory. A broken output pipe is exit 3; partial output must be discarded. Throughput failures require measurement/profile evidence. After a significant block invoke repository-local session-save and leave one precise next action. Deferred gzip and configurable top-N require a later scope update.
