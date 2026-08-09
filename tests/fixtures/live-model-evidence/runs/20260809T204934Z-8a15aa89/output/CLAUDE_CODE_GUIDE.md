# Claude Code Implementation Guide: Nginx Log Lens

## How to Use This Guide

Run one prompt at a time in the order shown. Before each step, read
`PROJECT_ARCHITECTURE.md`, `PRD.md`, and the matching section of
`IMPLEMENTATION_PLAN.md`. Do not advance because code merely looks complete;
run the named verification and record actual results. Update specifications
first if behavior must change.

Every prompt is bound to this public exit-code contract:

| Code | Meaning |
|---:|---|
| `0` | Successful analysis, help, or version |
| `1` | Operational input/output/internal failure |
| `2` | CLI usage error |
| `3` | Strict parsing failure or no valid records |
| `4` | Unique-cardinality exhaustion |

The mapping is exactly `0/1/2/3/4`. Code `4` means unique-cardinality
exhaustion; never omit, approximate, reuse, or remap it.

## Prompt 1 — Package Skeleton and CLI Contract

```text
Implement only Step 1 from IMPLEMENTATION_PLAN.md. Create pyproject.toml,
src/nginx_log_lens/__init__.py, src/nginx_log_lens/cli.py,
src/nginx_log_lens/errors.py, and tests/test_cli_contract.py. Use Python 3.11,
Click, Rich, dataclasses, and a src layout. Expose nginx-log-lens and the
analyze subcommand. Validate that --json and --csv are mutually exclusive and
that --max-unique-user-agents is positive. Define ExitCode values 0, 1, 2, 3,
and 4 exactly as the guide table specifies. Do not add analysis behavior,
database, API, server, Docker, cloud, or Kubernetes. Run all Step 1 verification
commands and report concrete results plus changed files.
```

## Prompt 2 — Domain Models and Parser

```text
Implement only Step 2 from IMPLEMENTATION_PLAN.md. Read the parsing and model
contracts in PROJECT_ARCHITECTURE.md. Create frozen dataclasses in models.py,
the finite common/combined nginx grammar in parser.py, synthetic fixtures, and
tests/test_parser.py. Preserve timezone offsets; handle quoted escapes; support
missing User-Agent; validate statuses and maximum line length; sanitize errors
without echoing full records. Do not materialize input or guess custom formats.
Do not change the 0/1/2/3/4 mapping; code 4 remains unique-cardinality
exhaustion. Run the Step 2 pytest, Ruff, and type checks and report evidence.
```

## Prompt 3 — Core Aggregations

```text
Implement only Step 3 from IMPLEMENTATION_PLAN.md in aggregate.py and its tests.
Consume an iterable exactly once. Count all valid requests by IP, count raw
request targets only for statuses 400 through 599, and return stable top-10
rows ordered by count descending then key ascending. Emit all 24 hour buckets
and compute every percentage with the literal formula
100 × hourly_request_count / total_valid_requests. Keep raw counts and never
recalculate metrics in renderers. Do not change exit codes 0/1/2/3/4; code 4
still means unique-cardinality exhaustion. Run and report every Step 3 check.
```

## Prompt 4 — User-Agent Exactness Boundary

```text
Implement only Step 4 from IMPLEMENTATION_PLAN.md. Track distinct non-missing
User-Agent strings exactly and compute
100 × distinct_non_missing_user_agent_count / total_valid_requests. Before a
new value exceeds --max-unique-user-agents, raise
UniqueCardinalityExhausted, emit no partial report, and have cli.py exit 4 with
a concise sanitized stderr error. Test repeated, missing, at-limit, and
over-limit cases. Preserve the full mapping: 0 success, 1 operational, 2 usage,
3 log-data, 4 unique-cardinality exhaustion. Run the listed tests, including a
real process exit assertion.
```

## Prompt 5 — Rich Terminal Output

```text
Implement only Step 5 from IMPLEMENTATION_PLAN.md. Add the renderer package and
Rich renderer, consuming only AnalysisSummary. Display totals plus top IPs,
top error URLs, 24 hourly buckets, and User-Agent diversity. Support --no-color
and non-TTY output; do not encode meaning only in color. Add deterministic
fixed-width tests and ANSI-stripped semantic assertions. Do not recalculate
percentages and preserve exit codes 0/1/2/3/4, with code 4 reserved for
unique-cardinality exhaustion. Run all Step 5 verification commands.
```

## Prompt 6 — JSON and CSV Output

```text
Implement only Step 6 from IMPLEMENTATION_PLAN.md. Add JSON schema version 1,
the documented key order, and CSV header
record_type,rank,key,count,percentage with all specified record types. Both
renderers must consume the same immutable AnalysisSummary as Rich. Machine
stdout must contain no ANSI, warning, progress, or traceback text; diagnostics
remain on stderr. Add schema/read-back/equivalence tests and six-decimal
percentage assertions. Keep the exact 0/1/2/3/4 mapping, including 4 for
unique-cardinality exhaustion. Run and report Step 6 checks.
```

## Prompt 7 — Input Handling and Exit Matrix

```text
Implement only Step 7 from IMPLEMENTATION_PLAN.md. Complete file and stdin
ownership, lenient invalid-line counting, --strict behavior, zero-valid-record
failure, and sanitized diagnostics. Map success/help/version to 0, operational
I/O/internal failures to 1, Click usage failures to 2, strict/no-valid log-data
failures to 3, and exact User-Agent cardinality exhaustion to 4. Add
process-level tests that actually observe each of 0/1/2/3/4 and assert no
partial stdout for failure 4. Run all Step 7 checks and report real results.
```

## Prompt 8 — Quality, Package, and Benchmark

```text
Implement only Step 8 from IMPLEMENTATION_PLAN.md. Add end-to-end tests, a
deterministic configurable fixture generator, and a benchmark runner that
records hardware, OS, Python, storage context, bytes, line count, all key
cardinalities, elapsed time, throughput, and peak RSS. Configure Ruff, mypy,
pytest, and at least 90% line coverage. Build a wheel and smoke-test that exact
wheel in a clean temporary Python 3.11 environment. Verify the 1 GB under
30-second target without hiding memory use. Include tests for exit codes
0/1/2/3/4; code 4 remains unique-cardinality exhaustion. Report measurements,
not predictions.
```

## Prompt 9 — Release Handoff

```text
Implement only Step 9 from IMPLEMENTATION_PLAN.md. Update README.md from actual
behavior and measured results; create CHANGELOG.md, the selected permissive
LICENSE, and docs/RELEASE_CHECKLIST.md. Verify the wheel's --help, golden flow,
all three renderers, and the complete 0/1/2/3/4 exit matrix. Explicitly confirm
that code 4 means unique-cardinality exhaustion. Run the entire pytest, Ruff,
mypy, packaging, clean-wheel smoke, and benchmark gates. Update CLAUDE.md status
only from evidence. Do not publish a package, push, or create a release unless
the user separately authorizes that external action.
```

## Cross-Step Guardrails

- WIP is one numbered step; do not combine later scope into the current step.
- Do not add authentication, persistence, HTTP endpoints, servers, cloud, or Kubernetes.
- Do not use `read()`, `readlines()`, or a list of every parsed record.
- Keep metric math in aggregation and formatting in renderers.
- Never log full malformed records or send log data over a network.
- Treat a benchmark target as unverified until the recorded command passes.
- At the end of a meaningful block, reconcile status with actual test evidence.
