# Claude Code Implementation Guide: nginx-report

## How to Use This Guide

Execute one prompt at a time in the order shown. Before each step, read `PRD.md`, the cited section of `PROJECT_ARCHITECTURE.md`, and the matching step in `IMPLEMENTATION_PLAN.md`. Keep WIP at one step, add tests with behavior, and record verification evidence before moving on. Do not implement a database, HTTP API, server, authentication, cloud service, Docker requirement, or Kubernetes resource.

The non-negotiable exit-code contract in every step is: `0` success (including empty input); `1` input/output or unexpected runtime failure; `2` Click usage error; `3` non-empty input containing zero valid requests; `4` unique-cardinality exhaustion. Code `4` means unique-cardinality exhaustion and must not be omitted or remapped. All nonzero exits produce no report on stdout.

## Prompt 1 — Packaging and CLI Contract

> Implement STEP 1 from `IMPLEMENTATION_PLAN.md`. Create only the package skeleton, dependency/build metadata, console entry point, Click options, and contract tests named there. Do not emit placeholder or synthetic report values. Match `PROJECT_ARCHITECTURE.md` under `## CLI Interface`, including mutual exclusion and ranges. Preserve the exact `0/1/2/3/4` exit contract, with `4` reserved for unique-cardinality exhaustion. Run every STEP 1 verification command, report failures honestly, and update step status only with evidence.

## Prompt 2 — Models and Parser

> Implement STEP 2 from `IMPLEMENTATION_PLAN.md`. Use immutable dataclasses and a one-line-at-a-time combined-log parser. Follow the input grammar, UTC timestamp handling, verbatim request-target rule, optional User-Agent rule, and 1 MiB line bound in `PROJECT_ARCHITECTURE.md`. Fixtures must be labeled synthetic test data. Do not add aggregation or rendering. Preserve the exact `0/1/2/3/4` exit contract, with `4` reserved for unique-cardinality exhaustion. Run the parser and compile verification commands and record their outputs.

## Prompt 3 — Streaming Aggregation

> Implement STEP 3 from `IMPLEMENTATION_PLAN.md`. Aggregate without retaining raw records. Implement exact top IP/error-target counts, deterministic ties, 24 UTC buckets, and User-Agent distinct share. Hourly percentages must use the literal formula `100 × hourly_request_count / total_valid_requests`. Enforce `--max-unique` independently for IP, error target, and User-Agent before inserting a new key. Do not silently approximate. Preserve the exact `0/1/2/3/4` exit contract, with `4` meaning unique-cardinality exhaustion. Run the listed aggregation and coverage checks.

## Prompt 4 — JSON and CSV

> Implement STEP 4 from `IMPLEMENTATION_PLAN.md`. Render only an already-built `Report`; do not recompute metrics. Match JSON schema version 1 and the normalized CSV header/row contract exactly. Make ordering deterministic, include all 24 hours, use the standard serializers, and keep ANSI/warnings out of stdout. Preserve the exact `0/1/2/3/4` exit contract, with `4` reserved for unique-cardinality exhaustion. Run renderer tests and validate the golden JSON.

## Prompt 5 — Rich Text

> Implement STEP 5 from `IMPLEMENTATION_PLAN.md`. Build the four human-readable report sections and summary using Rich. Escape every log-derived value, apply color only for a TTY, and honor `--no-color` plus `NO_COLOR`. Keep text display precision at two decimals without changing internal values. Preserve the exact `0/1/2/3/4` exit contract, with `4` reserved for unique-cardinality exhaustion. Run the step's tests and redirected-output ANSI check.

## Prompt 6 — End-to-end CLI and Failures

> Implement STEP 6 from `IMPLEMENTATION_PLAN.md`. Wire file/stdin streams, parsing, aggregation, and one selected renderer. Buffer only the final bounded report so any failure leaves stdout empty. Map success to `0`, I/O/runtime failure to `1`, usage failure to `2`, non-empty zero-valid parsing to `3`, and unique-cardinality exhaustion to `4`; do not omit or remap code `4`. Expected failures get concise stderr diagnostics without tracebacks. Add file/stdin parity and explicit end-to-end tests for every exit code, then run all listed checks.

## Prompt 7 — Performance Evidence

> Implement STEP 7 from `IMPLEMENTATION_PLAN.md`. Add a deterministic, explicitly synthetic benchmark generator and opt-in performance test. Measure a 1 GB representative log on documented hardware, recording wall time, CPU time, peak RSS, Python version, and cardinalities in `docs/PERFORMANCE.md`. Profile before optimizing and do not change public schemas for speed. Separately prove that a tiny cardinality limit exits `4` with empty stdout. Preserve the full `0/1/2/3/4` contract. Run the exact benchmark commands and retain truthful evidence.

## Prompt 8 — Package Hardening

> Implement STEP 8 from `IMPLEMENTATION_PLAN.md`. Add and satisfy lint/type rules, package metadata, license inclusion, dependency audit, wheel build, and fresh Python 3.11 install smoke tests. Do not weaken checks or add network/runtime infrastructure. The installed wheel must retain the exact exit codes `0/1/2/3/4`, where `4` means unique-cardinality exhaustion. Run every listed verification command against the candidate.

## Prompt 9 — Release Reconciliation

> Execute STEP 9 from `IMPLEMENTATION_PLAN.md`. Reconcile the README, PRD, architecture, schemas, tests, package metadata, and benchmark record so the specification remains the source of truth. If behavior differs, update the spec deliberately before accepting code. Run the complete suite, static checks, wheel/fresh-install checks, and verify all blueprint documents exist. Confirm explicit end-to-end evidence for `0/1/2/3/4`; code `4` must still mean unique-cardinality exhaustion. Do not call the project complete without current exact-candidate evidence.

## Cross-step Review Checklist

- No raw input collection such as `read()`, `readlines()`, or whole-file `splitlines()` exists in the processing path.
- Parser/aggregator modules do not import Click or Rich.
- JSON and CSV are deterministic and contain no ANSI or stderr text.
- Terminal-derived strings are safely escaped.
- The exact hourly formula is `100 × hourly_request_count / total_valid_requests`.
- Empty input succeeds; non-empty all-invalid input exits `3`.
- Unique-cardinality exhaustion exits `4` before inserting the over-limit key and never produces an approximate report.
- No authentication, database, HTTP API, server, cloud, or Kubernetes behavior has entered scope.
