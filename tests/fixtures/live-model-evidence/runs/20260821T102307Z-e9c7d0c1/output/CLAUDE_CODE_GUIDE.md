# Claude Code Implementation Guide: Nginx Stream Analytics CLI

Use this guide after the blueprint is approved. Work on one `IMPLEMENTATION_PLAN.md` step at a time, update the durable specifications before changing behavior, and do not add a database, HTTP API, server, authentication, cloud, Docker, or Kubernetes.

## Shared Contract for Every Implementation Session

- Read `STRATEGIC_PLAN.md`, `PROJECT_ARCHITECTURE.md`, `PRD.md`, `IMPLEMENTATION_PLAN.md`, and `CLAUDE.md` before editing.
- Preserve Python 3.11, Click, Rich, dataclasses, pip packaging, and the single-process streaming design.
- Treat hourly distribution as a percentage computed by `100 × hourly_request_count / total_valid_requests`.
- Preserve exact UA share and the configured exact-cardinality ceiling.
- Preserve the complete exit-code contract in every step: `0` success; `1` unexpected internal error; `2` usage, invalid options, or unreadable input; `3` no valid input records; `4` unique-cardinality exhaustion. Code `4` must never be omitted or remapped.
- Add or update tests with each behavior. Never claim performance without running the documented benchmark on the exact candidate.
- Do not implement P1/P2 while a P0 acceptance criterion is incomplete.

## Prompt 1 — Package and CLI foundation

Implement Step 1 from `IMPLEMENTATION_PLAN.md`. Create only the specified package metadata, package initializer, CLI skeleton, and CLI tests. Ensure pip installation creates `nginx-stream-analytics`; help and version exit `0`; invalid `--json --csv` exits `2`. Keep analysis behavior unimplemented and explicit. Run the step verification commands and report changed files and observed results.

## Prompt 2 — Domain and failure contracts

Implement Step 2. Define frozen/immutable result dataclasses where practical and a small domain exception hierarchy. Build the named fixtures and hand-calculate their expected result before writing aggregation code. Extend CLI tests so `0/1/2/3/4` are explicit expected values; code `4` means unique-cardinality exhaustion. Run only relevant tests, then the existing suite.

## Prompt 3 — Combined-format parser

Implement Step 3. Parse nginx combined records incrementally and extract only client IP, local hour, request target, status, and User-Agent. Compile parsing machinery once, tolerate invalid UTF-8 through replacement, and classify malformed lines without hiding programmer errors. Do not shell out, instantiate Rich objects per line, or read an entire stream. Cover all parser cases named in the plan and run coverage.

## Prompt 4 — Streaming aggregation

Implement Step 4 using one pass. Maintain counters and an exact User-Agent set. Output at most 10 IPs and 10 error URLs, using descending count and lexicographic tie-breaks. Emit all 24 hours and compute each percentage with `100 × hourly_request_count / total_valid_requests`. Abort without a result as soon as unique cardinality exceeds the limit; this eventually maps to exit `4`. Prove boundary and one-over-boundary behavior in tests.

## Prompt 5 — JSON and CSV renderers

Implement Step 5 from the immutable result model only; renderers must not recalculate metrics. JSON must be a single schema-versioned object. CSV must use `schema_version,metric,rank,key,count,share_pct`, RFC-compatible quoting, formula-injection protection, and all 24 hour rows. Prove deterministic output and no ANSI/progress/diagnostics on stdout.

## Prompt 6 — Rich terminal renderer

Implement Step 6. Create four readable Rich tables and a scan summary. Treat all values from logs as untrusted display data, escape them safely, and make color TTY-aware with explicit override support. Do not change machine schemas. Add snapshot/assertion coverage for forced color, no color, long fields, and markup-like input.

## Prompt 7 — CLI integration

Implement Step 7. Wire path/stdin opening, parsing, aggregation, and renderer selection. Keep stdout exclusively for the selected report and stderr for diagnostics. Enforce `0` success, `1` internal failure, `2` usage/option/input-open failure, `3` empty or all-malformed input, and `4` unique-cardinality exhaustion. Mixed valid/malformed data exits `0` with honest counts. Exercise every code in Click integration tests and compare the golden fixture end to end.

## Prompt 8 — Benchmark and release gate

Implement Step 8. Generate a deterministic representative 1 GB fixture, capture reference system details, warm once, run three complete analyses, and record the median elapsed time plus peak RSS. The under-30-second assertion includes file read, parse, aggregate, and output generation. Profile before optimizing, preserve semantics with regression tests, build wheel/sdist, and run the full suite with coverage. Do not weaken the target or replace exact metrics with approximate ones.

## Review Prompt

Review the exact candidate against the P0 stories in `PRD.md`, all decisions in `PROJECT_ARCHITECTURE.md`, and the active implementation step. Look specifically for whole-file reads, repeated scans, incorrect `4xx/5xx` bounds, missing zero-hour rows, unscaled percentage fractions, unstable ties, ANSI leakage, stdout diagnostics, CSV injection, and incomplete `0/1/2/3/4` mappings. Report evidence and file locations; do not modify code during review.

## Handoff Template

At the end of each step, record:

1. Step number and acceptance criteria completed.
2. Files changed and any deliberate deviations from the blueprint.
3. Commands actually run and observed outcomes.
4. Current performance evidence, if the benchmark was run.
5. Remaining risk or explicit blocker.
6. Next single implementation step.

At the end of every session or meaningful block of work, save context through `/session-save`.

