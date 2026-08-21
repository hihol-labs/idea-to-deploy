# Claude Code Implementation Guide: Nginx Stream Analyzer

Use these prompts in order, one step per session or reviewable change. Before each step, read `CLAUDE.md`, `PROJECT_ARCHITECTURE.md`, `PRD.md`, and the matching section of `IMPLEMENTATION_PLAN.md`. Update the spec first if behavior must change.

The non-negotiable exit-code contract in every step is: `0` = successful complete report (including empty input), `1` = operational I/O or unexpected internal failure, `2` = invalid CLI usage, `3` = non-empty input with zero valid records, `4` = unique-cardinality exhaustion. Code `4` must never be omitted, remapped, or converted into a partial success.

## Step 1 Prompt — Package and Contracts

> Implement Step 1 from `IMPLEMENTATION_PLAN.md`. Create only the package skeleton, `pyproject.toml`, frozen dataclasses, named `0/1/2/3/4` exit constants, and CLI help/version/option-contract tests. Use Python 3.11, Click, Rich, and dataclasses. Do not add a database, API, server, auth, cloud, Docker, or Kubernetes. Run the listed verification commands and record actual results; stop if they fail.

Expected evidence: editable install succeeds, help/version run, contract tests pass.

## Step 2 Prompt — Parser

> Implement Step 2 from `IMPLEMENTATION_PLAN.md`. Parse only the documented nginx combined-log grammar into `AccessRecord`; return typed parse failures and never print from the parser. Add the exact fixtures and edge cases listed in the plan, including IPv4/IPv6, invalid UTF-8 replacement, malformed requests, and status validation. Do not read entire files. Run parser tests and branch coverage.

Expected evidence: parser tests and ≥90% parser branch coverage pass.

## Step 3 Prompt — Aggregation

> Implement Step 3 from `IMPLEMENTATION_PLAN.md`. Build one-pass exact counters, 24 hour buckets, an exact User-Agent set, invalid-line accounting, and a total unique-key budget checked before insertion. Hourly percentage must be `100 × hourly_request_count / total_valid_requests`. Unique User-Agent share uses the same valid-request denominator. Deterministic exhaustion maps to exit `4` and emits no partial complete report. Run aggregation and coverage tests.

Expected evidence: boundary, tie, percentage, zero-total, and exhaustion tests pass.

## Step 4 Prompt — Renderers

> Implement Step 4 from `IMPLEMENTATION_PLAN.md`. Render the immutable report as escaped Rich text, schema-versioned JSON, and one-header normalized CSV. JSON/CSV must contain no ANSI escapes; text must honor TTY detection, `--no-color`, and `NO_COLOR`. Preserve deterministic ordering and keep diagnostic text out of renderers. Run golden/schema/no-ANSI tests.

Expected evidence: golden JSON/CSV and deterministic renderer tests pass.

## Step 5 Prompt — CLI Integration

> Implement Step 5 from `IMPLEMENTATION_PLAN.md`. Wire file/stdin input, parser, accumulator, report, and selected renderer through Click without duplicating domain logic. Keep report bytes on stdout and diagnostics on stderr. Explicitly prove `0` success, `1` operational failure, `2` usage error, `3` all-invalid non-empty data, and `4` unique-cardinality exhaustion. Handle broken pipes concisely. Run integration tests and JSON parsing verification.

Expected evidence: file/stdin parity and independent tests for exits `0/1/2/3/4` pass.

## Step 6 Prompt — Correctness Hardening

> Implement Step 6 from `IMPLEMENTATION_PLAN.md`. Add cross-module invariant and parameterized edge-case tests. Prove hour counts sum to total valid requests, non-empty hourly percentages total 100% within declared tolerance, rankings never exceed 10, machine stdout remains parseable, and every exit in `0/1/2/3/4` is preserved. Do not weaken assertions or lower coverage to get green results.

Expected evidence: complete suite and ≥90% core branch coverage pass.

## Step 7 Prompt — Performance

> Implement Step 7 from `IMPLEMENTATION_PLAN.md`. Add a deterministic streaming benchmark generator, a benchmark recorder, and a CI-safe smoke test. Generate 1,073,741,824 bytes without retaining the fixture in process memory. Record machine context, elapsed wall time, peak RSS, line count, and cardinalities. Profile before optimizing and preserve exact report semantics and exits `0/1/2/3/4`.

Expected evidence: smoke test passes and the declared reference laptop processes 1 GB in under 30 seconds.

## Step 8 Prompt — Release

> Implement Step 8 from `IMPLEMENTATION_PLAN.md`. Finalize README, changelog, license, package metadata, clean-wheel installation verification, and release documentation. Document supported grammar, JSON/CSV schemas, `100 × hourly_request_count / total_valid_requests`, known limits, and all exits `0/1/2/3/4` with code `4` defined as unique-cardinality exhaustion. Run build, full suite, clean install, and the acceptance benchmark; report actual evidence only.

Expected evidence: build succeeds, tests pass, clean Python 3.11 wheel starts, and benchmark meets target.

## Review Checklist for Every Step

- Scope matches exactly one implementation step (WIP=1).
- Product code depends on no service or persistent store.
- Parsing, aggregation, rendering, and orchestration remain separated.
- No complete input file or raw log lines are retained.
- Tests demonstrate the behavior changed in the step.
- The exit contract remains `0/1/2/3/4`, with `4` for unique-cardinality exhaustion.
- Verification output is current and failures are recorded rather than narrated away.
- Documentation and `.itd-memory/STATE.json` are reconciled before handoff.
