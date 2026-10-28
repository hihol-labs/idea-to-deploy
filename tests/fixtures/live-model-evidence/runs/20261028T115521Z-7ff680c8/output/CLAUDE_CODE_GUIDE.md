# Claude Code Implementation Guide: nginx-stream-report

## Purpose

Use this guide to execute `IMPLEMENTATION_PLAN.md` one step at a time. `PRD.md` is the durable behavior specification and `PROJECT_ARCHITECTURE.md` is the technical source of truth. Do not implement a database, HTTP API, authentication, server, cloud resource, or Kubernetes configuration.

## Global Execution Contract

For every prompt below:

1. Read the named blueprint sections before editing.
2. Preserve WIP=1 and implement only the current step.
3. Add or update tests with production code, then run the listed verification commands.
4. Report exact commands and outcomes; never claim an unrun test passed.
5. Use this exit contract everywhere: `0` success, `1` unexpected internal failure, `2` usage/option error, `3` input/read/parse processing failure, `4` unique-cardinality exhaustion.
6. The lowercase failure label for code 4 is: unique-cardinality exhaustion.
7. Never emit partial JSON or CSV after a fatal error.
8. Do not commit, push, publish, or create a PR unless the user explicitly requests and confirms the external action.

## Prompt 1 — Package Scaffold

> Implement Step 1 from `IMPLEMENTATION_PLAN.md`. Create `pyproject.toml`, `src/nginx_stream_report/__init__.py`, the minimal Click entry point in `src/nginx_stream_report/cli.py`, and CLI smoke tests. Use Python 3.11, Click, Rich, dataclasses, and a src layout. Run every Step 1 verification command and report results. Do not add metric behavior yet.

## Prompt 2 — Models and Errors

> Implement Step 2 from `IMPLEMENTATION_PLAN.md`. Read the data model and failure sections of `PROJECT_ARCHITECTURE.md`. Add typed dataclasses and domain failures, with CLI tests that explicitly cover the complete `0/1/2/3/4` mapping, including code 4 for unique-cardinality exhaustion. Run the Step 2 checks and stop if they fail.

## Prompt 3 — Parser

> Implement Step 3 from `IMPLEMENTATION_PLAN.md`. Build the supported nginx combined-log parser and focused fixtures/tests. Parse only the required fields, compile parsing machinery once, preserve timestamp offsets, and classify malformed lines without retaining input. Run parser tests and coverage; do not implement aggregation or rendering.

## Prompt 4 — Streaming Aggregation

> Implement Step 4 from `IMPLEMENTATION_PLAN.md`. Build one-pass exact aggregators for top IPs, 4xx/5xx URLs, 24 hourly buckets, and unique User-Agents. Hourly percentage must use `100 × hourly_request_count / total_valid_requests`. Enforce the User-Agent ceiling before unsafe growth and map it to code 4. Test deterministic ties, empty/all-invalid input, status boundaries, percentage totals, and exhaustion.

## Prompt 5 — Structured Renderers

> Implement Step 5 from `IMPLEMENTATION_PLAN.md`. Add deterministic JSON schema version 1 and normalized CSV with `section,key,count,percentage`. Both formats must be ANSI-free and semantically match the report dataclasses. Add escaping and ordering tests, run all Step 5 checks, and do not modify metric semantics.

## Prompt 6 — Text UI and CLI

> Implement Step 6 from `IMPLEMENTATION_PLAN.md`. Add Rich text output, file/stdin reading, mutually exclusive `--json` and `--csv`, TTY-aware color, `--no-color`, `--max-unique-user-agents`, and the complete failure mapping. Test file/stdin equivalence and every code in `0/1/2/3/4`. Expected failures write concise stderr and fatal failures emit no partial report.

## Prompt 7 — Integration and Quality

> Implement Step 7 from `IMPLEMENTATION_PLAN.md`. Add end-to-end semantic comparisons across text, JSON, and CSV; configure and run coverage, Ruff, and mypy; and inspect for unrequested network, subprocess, persistence, or file-write behavior. Fix in-scope findings and report exact verification evidence.

## Prompt 8 — Performance

> Implement Step 8 from `IMPLEMENTATION_PLAN.md`. Add a deterministic benchmark-log generator and a small automated performance regression. Generate the 1 GB fixture outside Git, measure wall time and peak RSS on the reference laptop, and record the environment and results in `docs/PERFORMANCE.md`. Profile before optimizing and preserve exact PRD semantics. Do not claim the under-30-second target without a measured run.

## Prompt 9 — Release Candidate

> Implement Step 9 from `IMPLEMENTATION_PLAN.md`. Update usage documentation, run the complete test/lint/type suite, build the distributions, validate metadata, install the wheel in a fresh Python 3.11 environment, and smoke-test text, JSON, and CSV. Prepare a local release candidate only. Do not publish, push, or create a release.

## Final Verification Prompt

> Audit the implementation against every P0 acceptance criterion in `PRD.md`, the exact CLI contract in `PROJECT_ARCHITECTURE.md`, and the Definition of Done in `STRATEGIC_PLAN.md`. Run—not merely list—the full suite and the documented benchmark. Produce a concise evidence table with criterion, command, and observed result. Mark anything unverified explicitly and do not weaken the specification to make the audit pass.

