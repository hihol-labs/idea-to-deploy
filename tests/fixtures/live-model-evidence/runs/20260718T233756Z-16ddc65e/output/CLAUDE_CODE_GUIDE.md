# Claude Code Guide: Nginx Log Lens

Use these prompts one at a time, in the order defined by
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Each prompt keeps a single
unit in progress, requires real command evidence, and forbids scope expansion.

## Session bootstrap

> Read `AGENTS.md`, `.itd/`, `.itd-memory/` if present, `CLAUDE.md`, `PRD.md`,
> `PROJECT_ARCHITECTURE.md`, and `IMPLEMENTATION_PLAN.md`. Identify the one
> active implementation step and its acceptance criteria. Do not implement a
> later step. Update the scope/state contracts before writing, and report the
> exact verification evidence before changing status.

## Prompt 1 — package and CLI skeleton

> Execute Implementation Plan Step 1 only. Create the Python 3.11 `src/`
> package, Click entry point, packaging configuration, and CLI contract tests.
> Do not add parsing or report behavior. Run every Step 1 verification command,
> record outputs, reconcile Idea to Deploy state, and stop.

## Prompt 2 — domain and output contracts

> Execute Step 2 only. Implement frozen dataclasses and executable JSON/CSV
> schema contracts from Architecture sections 4 and 6. Preserve schema version
> 1 and deterministic rankings. Add no renderer implementation. Run the listed
> tests and type check, record evidence, reconcile state, and stop.

## Prompt 3 — streaming parser

> Execute Step 3 only. Implement lazy file/stdin input and common/combined
> nginx parsing, including timestamps, exact request targets, statuses, missing
> User-Agent values, malformed-line counting, and fatal input errors. Add the
> specified fixtures and boundary tests. Do not aggregate or render. Verify,
> record evidence, reconcile state, and stop.

## Prompt 4 — one-pass aggregation

> Execute Step 4 only. Implement all four metrics in a single pass with fixed
> 24-hour buckets and deterministic top-10 tie ordering. Keep exact User-Agent
> semantics from the PRD. Add iterator-consumption and edge-case tests. Do not
> add presentation. Verify, record evidence, reconcile state, and stop.

## Prompt 5 — terminal renderer

> Execute Step 5 only. Implement the Rich terminal report, TTY-aware color, and
> `--no-color`. Keep all domain logic outside the renderer. Add forced-color and
> colorless snapshots and ensure redirected text is clean. Verify, record
> evidence, reconcile state, and stop.

## Prompt 6 — JSON and CSV

> Execute Step 6 only. Implement schema-versioned JSON and normalized CSV,
> mutually exclusive flags, stdout/stderr separation, and ANSI-free machine
> output. Test parsability and golden contracts. Do not alter metric semantics.
> Verify, record evidence, reconcile state, and stop.

## Prompt 7 — end-to-end failures

> Execute Step 7 only. Complete exit-code mapping and file/stdin end-to-end
> paths, including missing files, decoding failures, malformed lines, invalid
> options, and broken pipes. Preserve valid empty reports and concise stderr.
> Run integration tests, record evidence, reconcile state, and stop.

## Prompt 8 — performance gate

> Execute Step 8 only. Build a deterministic log generator and benchmark that
> records environment, wall time, throughput, and peak RSS. Run the actual 1 GB
> gate; do not estimate results. If it fails, profile and report the measured
> bottleneck without weakening the PRD. Record evidence, reconcile state, and
> stop.

## Prompt 9 — release handoff

> Execute Step 9 only after Steps 1–8 have accepted evidence. Complete release
> metadata and user documentation, run the full tests, coverage, static checks,
> build, isolated install, package validation, and reference benchmark. Do not
> publish externally unless separately authorized. Reconcile all state and
> provide a handoff with exact evidence and next action.

## Review prompt

> Review the current candidate against `PRD.md` and
> `PROJECT_ARCHITECTURE.md`. Focus on streaming behavior, exact metric
> semantics, deterministic output, ANSI/stdout contamination, untrusted log
> data, error handling, and the 1 GB performance evidence. Return severity,
> file/line evidence, reproduction, and a machine-readable verdict. Do not edit.

## Benchmark failure prompt

> The performance gate failed. Preserve output semantics and measure before
> changing anything. Profile parser, aggregation, and rendering separately on
> the documented fixture; identify the dominant cost, make one bounded change,
> and rerun identical before/after commands. Do not introduce persistence,
> multiprocessing, native extensions, or approximate cardinality without a
> specification decision.

