# Claude Code Implementation Guide: nginx-stream-report

## Purpose

Use this guide in later implementation sessions, one step at a time. It turns `IMPLEMENTATION_PLAN.md` into bounded prompts without changing the specification. Product code does not exist as part of this blueprint.

Before every step, read `PRD.md`, the referenced architecture sections, the current repository status, and tests. Preserve the approved architecture: local Python 3.11, Click, Rich, dataclasses, pip installation, one synchronous process, no database, no HTTP API, no authentication, no server, no cloud, and no Kubernetes.

The public exit codes are immutable: `0` success; `1` I/O or unexpected runtime failure; `2` CLI usage error; `3` input data/format failure; `4` unique-cardinality exhaustion. The exact lowercase condition name `unique-cardinality exhaustion` must remain associated with code 4 in implementation, tests, and documentation.

## Working Protocol

For each prompt:

1. Keep WIP at one implementation-plan step.
2. Add or update tests before completing behavior.
3. Run every verification command named for the step.
4. Do not claim performance without a recorded benchmark.
5. Reconcile `PRD.md` first if requested behavior changes.
6. Stop on a failed acceptance check and report the evidence; do not weaken the contract.
7. Commit only when the step is independently green and reviewable.

## Prompt 1 — Package Skeleton and Quality Baseline

```text
Implement only Step 1 of IMPLEMENTATION_PLAN.md. Read PRD.md and
PROJECT_ARCHITECTURE.md sections 1, 3, CLI Interface, and 10 first. Create the
pyproject-based Python 3.11 src-layout package, Click console entry point, and
the help/version/option-validation tests specified in the plan. Do not add
analysis logic, persistence, network behavior, containers, or deployment
assets. Run the Step 1 installation, pytest, Ruff, and mypy commands. Report
changed files and real command results; leave later steps untouched.
```

Expected evidence: an editable install, working `nginx-report --help`, option-validation tests, Ruff, and mypy all succeed.

## Prompt 2 — Models, Errors, and Fixtures

```text
Implement only Step 2 of IMPLEMENTATION_PLAN.md on top of the verified Step 1
candidate. Create the dataclasses, typed error taxonomy, synthetic log
fixtures, and contract tests. Freeze all public exit meanings 0/1/2/3/4; Click
owns usage code 2 and the domain exhaustion error owns code 4. Use no real or
sensitive logs. Run only the named Step 2 tests and static checks, then report
the exact results and changed files.
```

Expected evidence: model invariants and every exit-code mapping are executable tests.

## Prompt 3 — Combined-Log Parser

```text
Implement only Step 3 of IMPLEMENTATION_PLAN.md. Follow the parsing grammar in
PROJECT_ARCHITECTURE.md and the FR-2 acceptance criteria in PRD.md. Use one
compiled parser, extract only fields required by LogRecord, preserve the
request target, and never echo a complete bad line in diagnostics. Add the
specified parser boundary tests, then run the Step 3 verification commands.
Do not implement aggregation or renderers yet.
```

Expected evidence: valid and invalid fixture cases pass with source/line-safe diagnostics.

## Prompt 4 — Streaming Aggregation

```text
Implement only Step 4 of IMPLEMENTATION_PLAN.md. Add the streaming analyzer and
aggregate state for exact IP counts, 4xx/5xx URL counts, all 24 hourly rows,
and distinct nonempty User-Agent values. Calculate hourly percentage as
100 × hourly_request_count / total_valid_requests. Enforce the UA ceiling
before inserting an over-limit value and fail with code 4 without a partial
report. Prove line iteration with a stream that rejects read/readlines. Add all
named tests and run the Step 4 verification commands.
```

Expected evidence: formula, tie, empty-input, malformed-line, streaming, and exhaustion tests pass.

## Prompt 5 — Terminal Renderer

```text
Implement only Step 5 of IMPLEMENTATION_PLAN.md. Build the Rich terminal
renderer from an immutable Report snapshot. Include totals and all four
required summaries, deterministic order, TTY-aware color, and --no-color.
Escape or disable Rich markup for log-derived values. Add stable content tests
that do not depend on terminal width or incidental ANSI bytes. Run the Step 5
verification commands and report actual output status.
```

Expected evidence: renderer tests and a manual no-color fixture invocation succeed.

## Prompt 6 — JSON and CSV Renderers

```text
Implement only Step 6 of IMPLEMENTATION_PLAN.md. Follow the exact JSON and CSV
schemas in PROJECT_ARCHITECTURE.md. JSON must use schema_version 1. CSV must
use section,rank,key,count,percentage and neutralize spreadsheet-formula cell
prefixes without altering terminal or JSON data. Machine output goes only to
stdout and diagnostics only to stderr. Wire mutually exclusive selection,
add all named tests, and run every Step 6 verification command.
```

Expected evidence: standard parsers consume both formats and schema tests pass exactly.

## Prompt 7 — End-to-End Exit Contract

```text
Implement only Step 7 of IMPLEMENTATION_PLAN.md. Complete centralized exception
mapping and integration tests for success 0, I/O/runtime 1, Click usage 2,
strict data failure 3, and cardinality exhaustion 4. Cover stdin, empty input,
invalid UTF-8, warning suppression, non-TTY output, normal broken-pipe handling,
and absence of expected-error tracebacks. No failed analysis may emit a
partial report. Run the full Step 7 test, coverage, Ruff, and mypy commands.
```

Expected evidence: every code in `0/1/2/3/4` is observed in an integration test and source coverage is at least 90%.

## Prompt 8 — Performance, Packaging, and Release Evidence

```text
Implement only Step 8 of IMPLEMENTATION_PLAN.md. Create the deterministic
streaming benchmark generator and small performance smoke test, update README
only to match implemented reality, build sdist and wheel, and verify a clean
wheel install. Generate a 1 GB synthetic log outside the repository, record
its exact bytes and key cardinalities, run at least three timed analyses, and
record median wall time plus peak RSS in BENCHMARK.md. Run the complete suite,
static checks, build, and package checks. Do not claim the under-30-second gate
unless the recorded median actually meets it.
```

Expected evidence: all release checks pass, package contents are clean, and benchmark claims are backed by the recorded environment and runs.

## Final Acceptance Prompt

```text
Review the exact completed candidate against every P0 criterion in PRD.md and
the release gate in IMPLEMENTATION_PLAN.md. Run the complete tests, coverage,
Ruff, mypy, wheel build/check, clean-wheel smoke test, and recorded 1 GB
benchmark. Confirm terminal/JSON/CSV consistency and codes 0/1/2/3/4. Report
failures as blockers; do not change scope, suppress failures, or substitute a
standalone PASSED statement for command evidence.
```

## Guardrails for Future Changes

- Change the PRD and reconcile architecture/tests before changing public behavior.
- Version the JSON schema for a breaking machine-output change.
- Keep CSV columns stable unless a versioning mechanism is first specified.
- Never introduce approximation silently; expose a new explicit contract if exactness changes.
- Never add a database or network service without revisiting ADR-002 and the product scope.

