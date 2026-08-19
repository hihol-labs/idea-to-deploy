# Claude Code Implementation Guide: Nginx Log Lens

## How to Use This Guide

Execute one prompt at a time in order. Before each step, read
`PROJECT_ARCHITECTURE.md`, `PRD.md`, and the matching section of
`IMPLEMENTATION_PLAN.md`. Do not begin the next step until the listed checks
pass and the status table in `CLAUDE.md` is updated.

This is a CLI-only, single-process project. Never add authentication, a
database, HTTP API, server, cloud service, Docker, or Kubernetes. Preserve the
complete exit-code contract in every implementation: `0` success, `1` input or
I/O failure, `2` CLI usage error, `3` nonempty input with no valid records, and
`4` unique-cardinality exhaustion. Never omit or remap code 4.
The complete contract is `0/1/2/3/4`. Code `4` means unique-cardinality
exhaustion.

## Prompt 1 — Package Foundation

> Implement Step 1 from `IMPLEMENTATION_PLAN.md`. Create only the specified
> packaging, package, model, error, CLI-shell, and smoke-test files. Use Python
> 3.11, Click, Rich, frozen dataclasses, and a `src/` layout. Do not implement
> parsing or metrics yet. Run the three Step 1 verification commands and report
> their actual results. Update Step 1 status in `CLAUDE.md` only after they pass.

## Prompt 2 — Combined-Format Parser

> Implement Step 2 from `IMPLEMENTATION_PLAN.md` and FR-01 through FR-03 from
> `PRD.md`. Use a precompiled parser, preserve quoted fields, parse timestamp
> offsets, and return a typed malformed result without per-line logging. Add all
> named fixtures and focused parser tests. Run pytest, Ruff, and mypy exactly as
> specified before updating project status.

## Prompt 3 — Ranked Metrics

> Implement Step 3. Add one-pass aggregation for valid/malformed totals, top
> client IPs, and only 4xx/5xx request targets. Ties must sort by key ascending
> after count descending. Do not add renderers or CLI exception mapping. Run all
> Step 3 checks and retain exact metric semantics from `PRD.md`.

## Prompt 4 — Hourly and User-Agent Metrics

> Implement Step 4. Emit all 24 hour buckets and calculate each percentage with
> the exact formula `100 × hourly_request_count / total_valid_requests`. Add the
> exact unique User-Agent count/share and apply `--max-unique` semantics to each
> guarded distinct-key collection. Crossing the limit must raise the dedicated
> condition that later maps to exit 4. Run the specified metric tests and type
> checks.

## Prompt 5 — Renderers

> Implement Step 5 with separate Rich, JSON, and CSV modules consuming one
> frozen `Report`. Do not parse or recalculate metrics in a renderer. Ensure
> deterministic order, no ANSI in machine output, two-decimal presentation, and
> safe textual CSV cells. Add reconciliation and golden tests; never regenerate
> goldens without reviewing the semantic diff. Run all Step 5 checks.

## Prompt 6 — CLI Contract

> Implement Step 6 and the exact `CLI Interface` contract in
> `PROJECT_ARCHITECTURE.md`. Support path/stdin, mutually exclusive `--json` and
> `--csv`, `--top`, and `--max-unique`. Assert all codes: 0 success, 1 I/O, 2
> usage, 3 malformed-only input, 4 unique-cardinality exhaustion. Failures write
> only diagnostics to stderr and never partial reports to stdout. Run the
> integration and explicit code-4 checks.

## Prompt 7 — Quality Closure

> Implement Step 7. Build a table-driven exit-code oracle for the complete
> `0/1/2/3/4` contract and end-to-end reconciliation across terminal, JSON, and
> CSV. Trace every P0 acceptance criterion to a test. Run the full suite with
> coverage at least 90%, Ruff, and mypy; fix causes, not checks.

## Prompt 8 — Performance Proof

> Implement Step 8 without committing a generated 1 GB file. Create a
> deterministic streaming fixture generator and a benchmark runner that records
> machine profile, elapsed time, peak RSS, size, and exit status. Run the
> benchmark on the declared reference laptop. Optimize only a measured hotspot
> if elapsed time is not below 30 seconds or RSS exceeds 256 MiB, then rerun the
> full correctness suite.

## Prompt 9 — Distribution Handoff

> Implement Step 9. Reconcile `README.md` with actual behavior, including the
> exact `0/1/2/3/4` exit contract and code 4 meaning unique-cardinality
> exhaustion. Build and check wheel/sdist, install the wheel into a clean Python
> 3.11 environment, and smoke-test file, stdin, JSON, and CSV paths. Do not
> publish. Record evidence and update `CLAUDE.md` only after checks pass.

## Cross-Step Guardrails

- Keep input iteration streaming; never call `read()` without a bounded size or
  materialize all lines.
- Treat logged strings as data, never shell syntax or Rich markup.
- Keep metric calculation in `aggregate.py` and formatting in renderer modules.
- Do not weaken a test, cardinality limit, performance fixture, or acceptance
  criterion to obtain a passing result.
- If behavior changes, update `PRD.md` first and reconcile architecture and plan
  before code.
- At the end of each session or meaningful work block, save context with
  `/session-save`.
