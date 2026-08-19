# Claude Code Implementation Guide: nginx-log-insights

## How to Use This Guide

Run one prompt at a time in order, with WIP=1. Before each step, read
`AGENTS.md`, `.itd/SCOPE_LOCK.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the
matching section of `IMPLEMENTATION_PLAN.md`. A step is complete only after its
listed commands actually pass and the repository's evidence state is updated.
These prompts describe future implementation work; this blueprint session does
not implement product code.

Every prompt is governed by this complete exit-code contract:

| Code | Meaning |
|---:|---|
| `0` | Successful report/help/version |
| `1` | Input/output failure |
| `2` | CLI usage or option/configuration error |
| `3` | Parse/validation failure or no valid requests |
| `4` | Unique-cardinality exhaustion; no partial report |

Never omit, remap, or downgrade code 4. stdout contains only a successful
report; failures write concise diagnostics to stderr.

## Prompt 1: Package and Test Skeleton

```text
Implement only Step 1 of IMPLEMENTATION_PLAN.md. Create pyproject.toml,
src/nginx_log_insights/__init__.py, src/nginx_log_insights/cli.py, and
tests/test_package.py. Use Python 3.11, Click, Rich, a src layout, and a pip
console script named nginx-log-insights. Keep behavior limited to a truthful
help/version surface; do not stub fake analytics output. Run the three Step 1
verification commands and record real results. Preserve exit codes 0 success,
1 I/O, 2 usage/config, 3 parse/validation, and 4 unique-cardinality exhaustion
as the fixed contract for later steps.
```

Expected evidence: editable install, package test, and help output succeed.

## Prompt 2: Combined-Log Parser and Models

```text
Implement only Step 2 of IMPLEMENTATION_PLAN.md. Add the exact dataclasses from
PROJECT_ARCHITECTURE.md to models.py and a precompiled standard nginx combined-
log parser to parser.py. Add deterministic valid/invalid fixtures and parser
tests. Parse numeric-offset timestamps and status 100-599; retain request target
and User-Agent literally. Diagnostics may identify a line number but must not
echo a whole source line. Run the Step 2 commands. Do not add aggregation,
renderers, database, API, server, or custom nginx-format support.
```

Expected evidence: parser tests and parser-specific coverage gate pass.

## Prompt 3: Streaming Aggregation

```text
Implement only Step 3 of IMPLEMENTATION_PLAN.md. Build StreamingAggregator in
aggregate.py using one-pass exact counters, 24 hourly buckets, and a User-Agent
set. Error URLs include statuses 400-599. Ranking is count descending then key
ascending. Calculate hourly percentage exactly as
100 × hourly_request_count / total_valid_requests and keep it unrounded until
serialization. Calculate UA share on the 0-100 percentage scale. Enforce the
shared max-unique-keys boundary before insertion and raise a typed exhaustion
error that will map to exit code 4. Run all Step 3 verification commands.
```

Expected evidence: golden aggregation, formula, tie, and exhaustion-boundary
tests pass.

## Prompt 4: CLI and Complete Exit Matrix

```text
Implement only Step 4 of IMPLEMENTATION_PLAN.md. Complete file/stdin incremental
orchestration and Click options --json, --csv, --max-unique-keys, --strict, and
--no-color. Reject --json with --csv. Implement and test exactly: 0 success,
help, version; 1 input/output failure; 2 CLI usage or option/configuration
error; 3 strict parse failure or no valid requests; 4 unique-cardinality
exhaustion. Code 4 must remain distinct and must produce no partial report.
Default tolerant parsing skips malformed lines and counts them. Run the Step 4
commands and show the real exit-matrix results.
```

Expected evidence: file/stdin parity and all five exit-code paths pass.

## Prompt 5: Safe Rich Terminal Output

```text
Implement only Step 5 of IMPLEMENTATION_PLAN.md. Add the terminal renderer and
renderer selection. Show valid/invalid totals, top IPs, top error URLs, 24
hourly buckets, and unique User-Agent count/share. Use color only for a TTY and
when --no-color is absent. Disable Rich markup for every log-derived value and
do not rely on color alone for meaning. Preserve the exact exit contract
0/1/2/3/4. Run the Step 5 commands.
```

Expected evidence: semantic terminal tests, markup-safety checks, and a manual
no-color golden invocation pass.

## Prompt 6: JSON and CSV Output

```text
Implement only Step 6 of IMPLEMENTATION_PLAN.md. Add the JSON top-level schema
and CSV section,rank,key,count,percentage schema exactly as documented in
PROJECT_ARCHITECTURE.md. Both encoders must use UTF-8, stable ordering,
two-decimal rendered percentages, and zero ANSI escapes. Use standard-library
encoders. Broken stdout writes map to exit 1. Preserve 0 success, 1 I/O,
2 usage/config, 3 parse/validation, and 4 unique-cardinality exhaustion. Run
the Step 6 commands and parse the generated machine output in tests.
```

Expected evidence: JSON/CSV schema, semantic parity, ordering, and broken-pipe
tests pass.

## Prompt 7: Correctness and Privacy Hardening

```text
Implement only Step 7 of IMPLEMENTATION_PLAN.md. Add security and integration
tests for markup/control characters, shell-like text, diagnostic redaction,
file/stdin parity, renderer semantic parity, deterministic ties, and hourly
percentage invariants. Reach at least 90% project-code line coverage without
broad exclusions. Compile all source/tests. Do not add telemetry or network
calls. Confirm the complete 0/1/2/3/4 contract remains tested, especially code
4 for unique-cardinality exhaustion. Run the listed commands and record actual
evidence.
```

Expected evidence: full suite, coverage threshold, and compile check pass.

## Prompt 8: Reproducible Performance Gate

```text
Implement only Step 8 of IMPLEMENTATION_PLAN.md. Create the deterministic
fixture generator, benchmark runner, small performance smoke test, and
BENCHMARK.md protocol. Fixture generation must be outside the timed interval.
Measure an installed wheel against a representative 1 GiB combined log, record
machine/OS/Python metadata, wall time, and peak RSS, and validate output after
timing. Do not claim the under-30-second target unless measured. Profile before
optimizing; do not replace exact aggregation with approximation or remove exit
code 4. Run every Step 8 verification command.
```

Expected evidence: smoke test passes and the named-machine benchmark records a
real result below 30 seconds, or the step remains openly incomplete.

## Prompt 9: Release Candidate

```text
Implement only Step 9 of IMPLEMENTATION_PLAN.md. Update README.md and CLAUDE.md,
add CHANGELOG.md, build wheel and sdist, validate metadata, install the wheel in
a clean temporary Python 3.11 environment, and run the golden JSON command.
Document the full exit table: 0 success/help/version, 1 I/O, 2 usage/config,
3 parse/validation/no valid requests, 4 unique-cardinality exhaustion. Then
freeze the exact candidate and execute the machine oracle and risk-tier checker
required by the active Idea to Deploy verification contract. Accept completion
only from a current revalidated adjudication receipt. Run all Step 9 commands.
```

Expected evidence: distributions validate, clean-wheel smoke test succeeds, all
tests pass, and the current exact-candidate verification receipt is accepted.

## Recovery Rules

If a verification command fails, keep the current step active, record the
failure and smallest evidence-backed hypothesis, apply a scoped correction, and
rerun the failing command plus relevant regression checks. Do not skip ahead,
weaken an acceptance criterion, modify the protected verifier, or describe a
failed/unrun check as passed. Any scope expansion first updates `PRD.md`,
`PROJECT_ARCHITECTURE.md`, `.itd/SCOPE_LOCK.md`, and canonical state.

