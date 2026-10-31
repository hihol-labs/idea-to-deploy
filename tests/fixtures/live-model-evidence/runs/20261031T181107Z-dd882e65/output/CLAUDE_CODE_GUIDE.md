# Claude Code Implementation Guide: nginx-log-report

## How to Use This Guide

Run one prompt at a time in order. Before each step, read `PRD.md`, the cited architecture section, and the current git diff. Keep WIP at one step, add tests with each behavior, run the listed verification, and update the status table in `CLAUDE.md`. Do not introduce a database, HTTP API, server, cloud service, container deployment, authentication, or Kubernetes.

The command contract is fixed: `0` success, `1` operational I/O failure, `2` usage error, `3` no valid records, and `4` unique-cardinality exhaustion. Preserve `0/1/2/3/4` in implementation, tests, and user documentation.

## Prompt 1 — Package Skeleton

> Implement Step 1 from `IMPLEMENTATION_PLAN.md`. Create only the package metadata, importable skeleton, console entry point, and basic Click tests. Use Python 3.11, a `src` layout, Click, Rich, dataclasses, and pytest. Run the three Step 1 checks and report their actual results. Do not implement parsing or metrics yet.

## Prompt 2 — Parser and Models

> Implement Step 2 from `IMPLEMENTATION_PLAN.md` using the data contract in `PROJECT_ARCHITECTURE.md`. Add frozen dataclasses and a compiled nginx combined-log parser. Treat log text as untrusted data, do not retain irrelevant fields, and never echo a whole malformed line. Add the listed fixtures and edge-case tests, then run both Step 2 checks.

## Prompt 3 — Streaming Aggregation

> Implement Step 3 from `IMPLEMENTATION_PLAN.md`. Update exact counters in a single pass and retain no list of records. Rankings sort count descending then key ascending. Emit all 24 hours and calculate each percentage using `100 × hourly_request_count / total_valid_requests`. Enforce the configured exact User-Agent ceiling before inserting a new distinct value and raise the typed error that later maps to code 4. Add boundary tests and run both Step 3 checks.

## Prompt 4 — Rich Terminal Output

> Implement Step 4 from `IMPLEMENTATION_PLAN.md`. Render four labeled sections plus valid/malformed totals. Values from logs must be plain text, never Rich markup. Auto-detect TTY color and honor explicit color options. Add snapshot/contract tests, run Step 4 verification, and confirm redirected default output contains no ANSI escapes.

## Prompt 5 — JSON and CSV

> Implement Step 5 from `IMPLEMENTATION_PLAN.md` exactly as specified by `PROJECT_ARCHITECTURE.md`. Use standard serializers, stable ordering, JSON schema versioning, and the CSV header `metric,rank,key,count,percentage`. Ensure stdout contains only the payload and no ANSI escapes. Add schema, escaping, and parity tests and run Step 5 verification.

## Prompt 6 — CLI Integration

> Implement Step 6 from `IMPLEMENTATION_PLAN.md`. Support finite file input, stdin, `-`, and follow mode for regular files. Map exceptions to the complete exit contract: 0 success, 1 I/O, 2 usage, 3 no valid records, 4 unique-cardinality exhaustion. Never emit a partial JSON/CSV document on failure. Add end-to-end tests for every code and stream path and run Step 6 verification.

## Prompt 7 — Performance Evidence

> Implement Step 7 from `IMPLEMENTATION_PLAN.md` without committing the generated 1 GB file. Add deterministic generation, a CI-sized resource test, and `docs/PERFORMANCE.md`. Run the small test and then the 1 GB timed command on the reference laptop. Record observed wall time and peak RSS. If it misses 30 seconds, profile first and propose the smallest evidence-based optimization; do not add multiprocessing, persistence, or native extensions speculatively.

## Prompt 8 — Release Readiness

> Implement Step 8 from `IMPLEMENTATION_PLAN.md`. Reconcile README examples and exit codes with the tested CLI, run the entire suite with coverage, build artifacts, install the wheel in a fresh environment, and smoke-test the console command. Report exact command outcomes. Keep the step incomplete if any check is red or the measured 1 GB run exceeds 30 seconds.

## Review Checklist

- Input is streamed and raw records are not accumulated.
- 4xx and 5xx both contribute to error URL ranking.
- All 24 hourly buckets exist and use the specified percentage formula.
- Unique User-Agent counting is exact up to its configured ceiling.
- Terminal, JSON, and CSV results agree on the same `Report` model.
- Machine output contains no diagnostics or ANSI sequences.
- Exit codes remain exactly `0/1/2/3/4`; code `4` is not folded into code `1`.
- Tests cover malformed, empty, all-invalid, high-cardinality, I/O, and deterministic-tie cases.
- The clean wheel works on Python 3.11.
- The measured target is 1 GB in under 30 seconds on documented reference hardware.

## Session Continuity

At the end of every session or meaningful block, update `CLAUDE.md` with completed checks and use `/session-save`. Never mark a step complete from narration alone; attach the executed test or benchmark result.
