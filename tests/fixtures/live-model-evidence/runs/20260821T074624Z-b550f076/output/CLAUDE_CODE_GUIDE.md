# Claude Code Implementation Guide: nginx-stream-stats

## 1. How to Use This Guide

This is a sequence of implementation prompts, not product code. Start each session by reading `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the relevant section of `IMPLEMENTATION_PLAN.md`. Work on one numbered step at a time, preserve WIP=1, run the named verification, and record evidence before advancing.

The architecture and PRD are the source of truth. Do not add a database, HTTP API, server, authentication, Docker, cloud, Kubernetes, telemetry, or retained state. Do not reinterpret percentages, ranking ties, stdout/stderr boundaries, output schemas, or malformed-line behavior.

## 2. Non-negotiable Exit Contract

Every prompt below includes this same mapping and no implementation may omit or remap code 4:

| Code | Required meaning |
|---:|---|
| `0` | Successful complete report, help, or version |
| `1` | EOF with zero valid requests |
| `2` | Invalid CLI usage or configuration |
| `3` | Input I/O, unexpected internal/runtime, or non-UA resource failure |
| `4` | Unique-cardinality exhaustion |

For codes 1, 2, 3, and 4, stdout must contain no partial report. Malformed lines alone do not fail a run containing at least one valid request.

## Prompt 1: Package Skeleton and CLI Contract

```text
Implement only Step 1 of IMPLEMENTATION_PLAN.md.

Read CLAUDE.md, PRD.md, and PROJECT_ARCHITECTURE.md first. Create the Python 3.11 pyproject package, Click console entry point, initial CLI argument/options, version exposure, typed error model, and focused package/CLI tests. Direct runtime dependencies are Click and Rich. Validate --json/--csv mutual exclusion and a positive --max-unique-user-agents value.

Preserve the full exit contract: 0 successful report/help/version; 1 EOF with no valid requests; 2 invalid usage/configuration; 3 input I/O, unexpected internal/runtime, or non-UA resource failure; 4 unique-cardinality exhaustion. Define the mapping centrally even where later behavior is not implemented yet; do not emit fake reports or claim later steps work.

Do not create parsing, aggregation, renderers, a database, an API, a server, auth, Docker, cloud, or Kubernetes. Run every Step 1 verification command and report changed files, actual results, and remaining limitations. Stop after Step 1.
```

## Prompt 2: Domain Models and Parser

```text
Implement only Step 2 of IMPLEMENTATION_PLAN.md on top of a verified Step 1.

Create the frozen/slotted domain dataclasses and the one-line common/combined nginx parser exactly as PROJECT_ARCHITECTURE.md specifies. Compile format machinery once, retain no input-line collection, parse timezone-aware timestamps, extract only the request target, validate three-digit status 100..599, and represent unavailable User-Agent as None. Add small, reviewable fixtures and parser tests for normal, boundary, malformed, special-character, IPv4, and IPv6-token cases.

Preserve the full exit contract: 0 success; 1 EOF with no valid requests; 2 invalid usage/configuration; 3 I/O/internal/runtime/non-UA resource failure; 4 unique-cardinality exhaustion. This step may define typed parse failures but must not change CLI meanings or map malformed individual lines to an application failure.

Do not implement aggregate or renderer behavior. Run the Step 2 verification and report evidence. Stop after Step 2.
```

## Prompt 3: Streaming Aggregation and Metrics

```text
Implement only Step 3 of IMPLEMENTATION_PLAN.md on top of verified Steps 1-2.

Build the one-pass aggregator and immutable report construction. Count valid/skipped/total lines, every valid client IP, URLs only for 400..599, and a fixed set of 24 hour-of-day buckets. Implement top-10 ordering as descending count then ascending exact key. Calculate each hourly percentage with exactly: 100 × hourly_request_count / total_valid_requests. Calculate unique User-Agent share with the present-UA denominator documented in PROJECT_ARCHITECTURE.md.

Keep exact User-Agent values only up to the configured ceiling. Before an insertion that would exceed it, raise the typed code-4 failure. Do not emit an approximate result. Preserve all codes: 0 success; 1 no valid requests; 2 usage/config; 3 I/O/internal/runtime/non-UA resource; 4 unique-cardinality exhaustion.

Add focused aggregate/metric tests including status boundaries, deterministic ties, every hour, no errors, absent User-Agent, exact ceiling, and over-ceiling behavior. Run Step 3 verification and stop.
```

## Prompt 4: Safe Rich Terminal Renderer

```text
Implement only Step 4 of IMPLEMENTATION_PLAN.md.

Render the immutable report with Rich: line-accounting summary, top IPs, top error URLs, all 24 hourly counts/percentages, and unique User-Agent count/share. Rendering must never recalculate domain metrics. Treat every IP, URL, and other log-derived value as plain untrusted text; do not interpret Rich markup. Implement automatic TTY color plus explicit --color/--no-color and prove redirected auto output contains no ANSI.

Preserve exit codes without omission: 0 complete report/help/version; 1 no valid requests; 2 usage/configuration; 3 I/O/internal/runtime/non-UA resource failure; 4 unique-cardinality exhaustion. Failure paths emit no partial report.

Add and run the Step 4 renderer/CLI tests, including markup-like input and color modes. Stop after Step 4.
```

## Prompt 5: JSON and CSV Renderers

```text
Implement only Step 5 of IMPLEMENTATION_PLAN.md.

Create JSON schema_version 1 and the exact rectangular CSV contract in PROJECT_ARCHITECTURE.md. Both must serialize the same immutable report as terminal mode, write only the report to stdout, contain no ANSI, use UTF-8, and correctly escape hostile/special text. CSV must use the standard csv module and end with a newline. Add reviewed golden fixtures, parse-back tests, and metric-equivalence checks across formats.

Preserve the exact 0/1/2/3/4 mapping: 0 success; 1 no valid requests; 2 usage/config; 3 I/O/internal/runtime/non-UA resource failure; 4 unique-cardinality exhaustion. Do not omit/remap 4 or serialize partial failures.

Run all Step 5 checks and stop after reporting actual evidence.
```

## Prompt 6: End-to-End I/O and Failure Semantics

```text
Implement only Step 6 of IMPLEMENTATION_PLAN.md.

Complete buffered file/stdin processing and stream ownership. Aggregate fully before rendering so failures cannot corrupt terminal, JSON, or CSV output. Continue past malformed lines and expose their count when at least one valid request exists. Keep diagnostics on stderr. Exercise missing files, read/runtime failures, empty/all-invalid input, option errors, exact cardinality exhaustion, mixed valid/invalid input, stdin, and output atomicity through subprocess-level tests.

The required codes are: 0 successful complete report/help/version; 1 EOF with zero valid requests; 2 invalid CLI usage/configuration; 3 input I/O, unexpected internal/runtime, or non-UA resource failure; 4 unique-cardinality exhaustion. Code 4 is mandatory and exclusive to the configured exact User-Agent limit. Do not emit a partial report for 1/2/3/4.

Handle downstream closure without a traceback, then run all Step 6 checks and report the complete exit-code matrix. Stop after Step 6.
```

## Prompt 7: Correctness, Security, and Wheel Gates

```text
Implement only Step 7 of IMPLEMENTATION_PLAN.md.

Review the complete candidate against PRD P0 criteria and PROJECT_ARCHITECTURE.md. Strengthen tests with ANSI/control sequences, Rich markup, CSV quoting/formula-like values, JSON control characters, non-seekable input, deterministic repeat runs, and sensitive malformed text. Do not duplicate production formulas as the only oracle. Build wheel/sdist, install the wheel in a fresh Python 3.11 environment, smoke-test the console script, and inspect runtime dependencies.

Prove the entire 0/1/2/3/4 contract: 0 success; 1 no valid requests; 2 usage/config; 3 I/O/internal/runtime/non-UA resource; 4 unique-cardinality exhaustion. No code may catch code 4 and convert it to 3.

Do not run a deployment or introduce infrastructure. Execute every Step 7 verification and report failures honestly. Stop after Step 7.
```

## Prompt 8: Performance and Release Evidence

```text
Implement only Step 8 of IMPLEMENTATION_PLAN.md after Steps 1-7 are verified.

Create an opt-in, correctness-bound performance gate and deterministic synthetic benchmark generator. Do not commit a 1 GB fixture or label generated data as real. Freeze the exact candidate, record the reference laptop/OS/Python/input/cache procedure, and measure wall time plus peak RSS while also comparing the report with independently known expected metrics. The gate is a representative 1 GB input in under 30 seconds. Profile and optimize only measured hot paths without changing public semantics.

Re-run the full suite and demonstrate exit codes 0/1/2/3/4: success; no valid requests; usage/config; I/O/internal/runtime/non-UA resource; unique-cardinality exhaustion. Code 4 must remain distinct. Update user-facing documentation/help to match actual CLI schemas, formulas, limitations, and failures.

Do not claim the performance target from estimates or a smaller extrapolation. Report exact commands and whether each gate passed, then stop for release review.
```

## 11. Per-Step Completion Report

Use this structure after every prompt:

```text
Step: <N and name>
Scope changed: <paths>
Acceptance criteria addressed: <PRD IDs>
Verification run: <commands and outcomes>
Exit-code checks: 0=<result>, 1=<result>, 2=<result>, 3=<result>, 4=<result or not applicable yet>
Known gaps: <truthful list>
Next action: <next numbered step, or blocked reason>
```

A “should pass” statement is not verification. If a command fails, keep the step active, diagnose within its scope, and rerun it; do not advance or weaken the test.
