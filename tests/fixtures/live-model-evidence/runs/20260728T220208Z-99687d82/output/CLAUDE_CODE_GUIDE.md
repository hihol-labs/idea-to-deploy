# Claude Code Guide: Nginx Log Lens

## Purpose

This guide turns each step in `IMPLEMENTATION_PLAN.md` into a bounded,
verification-first prompt. Use one prompt at a time, preserve WIP=1, and do
not move forward until the current step’s commands produce evidence.

Before every prompt, read `CLAUDE.md`, `.itd/SCOPE_LOCK.md`,
`PROJECT_ARCHITECTURE.md`, `PRD.md`, and the named implementation step.
Architecture and PRD are durable specifications: change them before changing
an agreed behavior.

## Shared Prompt Preamble

> Work only on STEP N from `IMPLEMENTATION_PLAN.md`. Keep WIP=1. First inspect
> the current repository and restate the files in scope. Preserve the CLI,
> output schema, metric semantics, exit codes, and exclusions in
> `PROJECT_ARCHITECTURE.md` and `PRD.md`. Do not add a database, HTTP API,
> server, authentication, cloud service, Docker runtime requirement, or
> Kubernetes. Implement the smallest complete vertical slice. Run every
> verification command named by the step, report the actual outputs, and do
> not call the step complete without current evidence.

## Prompt 1: Package and CLI Contracts

> Execute STEP 1. Create only `pyproject.toml`,
> `src/nginx_log_lens/__init__.py`, `src/nginx_log_lens/cli.py`, and
> `tests/test_cli_contract.py` unless a specification change is first
> documented. Freeze command naming, arguments, options, help, and usage
> errors. Do not add analysis logic. Verify editable installation, help, and
> the focused test file.

## Prompt 2: Domain Models and Failures

> Execute STEP 2. Define the dataclasses and error hierarchy from
> `PROJECT_ARCHITECTURE.md`. Keep domain modules independent of Click and Rich.
> Encode invariants and the zero-valid-request UA-share rule in tests. Run the
> focused model tests and compile check.

## Prompt 3: Streaming Input and Parser

> Execute STEP 3. Implement incremental file/stdin reading and the exact MVP
> combined-log grammar. Use 64 KiB binary chunks, cap physical lines at 1 MiB,
> and implement the specified linear state machine and escape rules. Do not
> read the whole stream or use a regex vulnerable to catastrophic
> backtracking. Treat log values as untrusted data. Add the specified fixtures,
> parser tests, and both deterministic benchmark profiles. Report focused test
> timings.

## Prompt 4: Exact Aggregation

> Execute STEP 4. Implement all four metrics in one pass with exact counters,
> deterministic tie ordering, fixed 24-hour output, and the normative UA-share
> denominator. Do not introduce approximate sketches or renderer concerns.
> Run focused tests and the step’s coverage threshold. Before any renderer
> work, run the early 1 GB representative gate (<30 seconds and <256 MB) and
> the near-unique safety measurement; preserve actual evidence.

## Prompt 5: Rich Text Renderer

> Execute STEP 5. Render the immutable report with Rich and escape all
> log-derived values. Keep no-color output stable for golden tests and ensure
> no presentation code changes metric semantics. Run the text-renderer tests
> and the manual no-color command.

## Prompt 6: JSON and CSV Renderers

> Execute STEP 6. Implement exactly JSON schema version 1 and the normalized
> CSV header from `PROJECT_ARCHITECTURE.md`. Keep stdout data-only, preserve
> deterministic ordering, emit the CSV schema-version row and exact normative
> row sequence, quote through the standard CSV library, and finish each format
> with one newline. Run golden tests and JSON parsing validation.

## Prompt 7: End-to-End CLI

> Execute STEP 7. Connect existing components without duplicating their logic.
> Implement renderer selection, stdout/stderr separation, all exit mappings,
> partial-malformed behavior, and quiet broken-pipe handling. Add the complete
> end-to-end matrix and run focused plus manual JSON tests.

## Prompt 8: Performance and Robustness

> Execute STEP 8. Create a deterministic fixture generator and benchmark
> harness; do not commit the 1 GB artifact. Record exact hardware, Python,
> storage, seed, fixture hash, three runs, median, and peak RSS. Profile before
> optimizing and retain failed evidence. Do not weaken exactness or the target
> silently. Run robustness tests and the benchmark.

## Prompt 9: Package Release Readiness

> Execute STEP 9 only after steps 1–8 are verified. Complete user
> documentation and release metadata, build sdist/wheel, validate artifacts,
> install the wheel in isolation, run the full suite at ≥90% product-code
> coverage, and smoke-test the installed console command. Reconcile project
> state and list any unmet acceptance criterion instead of declaring success.

## Review Prompt

> Review the exact staged candidate against `PRD.md`,
> `PROJECT_ARCHITECTURE.md`, and the active implementation step. Prioritize
> incorrect metric semantics, parser hangs, unbounded input buffering,
> high-cardinality memory behavior, stdout contamination, unsafe terminal/CSV
> rendering, exit-code drift, and packaging failures. Cite file and line for
> every finding. Re-run the required machine oracle before accepting.

## Performance Decision Prompt

> The 1 GB benchmark missed its target. Preserve the results, profile the same
> candidate and fixture, identify measured hot paths, and propose bounded
> optimizations within Python 3.11/Click/Rich/dataclasses. Compare expected
> gains and semantic risks. Do not switch language, add parallelism,
> approximate counters, persistence, or services without first updating the
> architecture decision and obtaining explicit approval.

## Session Handoff

At the end of each significant work block, record the active step, exact
candidate, commands run, results, changed files, blockers, and next action.
Never infer completion from prose; preserve the current verification receipt.
