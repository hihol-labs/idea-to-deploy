# Claude Code Guide: nginx-log-report

This guide provides bounded prompts for executing `IMPLEMENTATION_PLAN.md`. Run one step at a time (WIP=1). Every prompt requires the agent to read `AGENTS.md`, `.itd/` contracts, `CLAUDE.md`, the named blueprint sections, and the current repository state before editing. Never mark a step complete from narration; attach current command output and reconcile `.itd-memory/STATE.json`.

## Universal Preamble

Prefix every implementation prompt with:

> Work only on the active Idea to Deploy unit and preserve WIP=1. Read `AGENTS.md`, `.itd/SCOPE_LOCK.md`, `.itd/VERIFICATION_CONTRACT.json`, `CLAUDE.md`, `PRD.md`, and `PROJECT_ARCHITECTURE.md`. Update the scope lock before changing scope. Treat the specifications as source: if implementation pressure conflicts with them, stop and propose a spec/ADR change. Do not add a database, HTTP API, server, authentication, cloud, Docker, Kubernetes, telemetry, or persistence. Freeze and verify the exact candidate through the repository's Verification Loop before claiming completion.

## Prompt 1: Installable CLI Skeleton

> Execute only Step 1 of `IMPLEMENTATION_PLAN.md`. Create the `src/` package, Python 3.11 packaging metadata, console entry point, help/version behavior, and focused CLI tests. Do not implement parsing or metrics. Run every Step 1 command and report the real output, changed files, and unresolved evidence.

## Prompt 2: Bounded Input and Parser

> Execute only Step 2 of `IMPLEMENTATION_PLAN.md`. Implement the 64 KiB-bounded reader, strict UTF-8 policy, nginx Combined Log Format grammar/escapes, typed failures, and synthetic fixtures. Never buffer an overlong record fully and never echo a complete sensitive line. Run parser/I/O tests including malformed, overlong, escaping, Unicode, and source/line diagnostics.

## Prompt 3: Exact Streaming Aggregation

> Execute only Step 3 of `IMPLEMENTATION_PLAN.md`. Implement exact counters, 24 hourly buckets, error-status boundaries, first-seen tie behavior, User-Agent diversity semantics/rounding, and cardinality ceilings. Prove one-pass consumption. Run the early hot-path 1 GB projection before renderer work; if projected total time misses 30 seconds or memory exceeds the contract, stop and report evidence rather than redesigning silently.

## Prompt 4: JSON and CSV

> Execute only Step 4 of `IMPLEMENTATION_PLAN.md`. Implement JSON schema version 1 and the normalized CSV schema exactly as specified under `## CLI Interface`. Parse outputs structurally in tests. Prove ANSI/prose/diagnostics never contaminate stdout and errors leave no partial machine document.

## Prompt 5: Rich Terminal Output

> Execute only Step 5 of `IMPLEMENTATION_PLAN.md`. Implement the default Rich report with all requested sections, empty-state behavior, TTY-aware color, and `--no-color`. Escape all log-derived values. Do not put Rich in the per-line hot path. Verify redirected and unsafe-markup cases.

## Prompt 6: Failure Semantics

> Execute only Step 6 of `IMPLEMENTATION_PLAN.md`. Complete default/strict malformed behavior, file/read failures, resource limits, `MemoryError`, internal defects, and Ctrl-C mapping. Verify exit codes 0, 2, 3, 4, 5, 70, and 130 where testable, plus stdout/stderr isolation. Never convert unexpected failure to an empty successful report.

## Prompt 7: Performance Evidence

> Execute only Step 7 of `IMPLEMENTATION_PLAN.md`. Generate deterministic realistic and boundary fixtures outside Git, record hashes and cardinalities, run at least three benchmark repetitions, and capture phase timings plus peak RSS and environment. Profile before optimizing. Any multiprocessing, native extension, disk staging, or approximate algorithm requires a prior ADR/spec change.

## Prompt 8: Release Verification

> Execute only Step 8 of `IMPLEMENTATION_PLAN.md`. Update user documentation with observed behavior, build wheel/sdist, install the exact wheel in a clean environment, run end-to-end modes, lint, type checks, coverage, security review, and the Idea to Deploy exact-candidate Verification Loop. Reconcile all acceptance evidence and leave the next action explicit. Do not publish or push unless separately authorized.

## Review Prompt

> Review the current exact candidate against `PRD.md`, `PROJECT_ARCHITECTURE.md`, and `.itd/VERIFICATION_CONTRACT.json`. Prioritize incorrect metrics, parser ambiguity, unbounded allocation, stdout contamination, exit-code drift, and unverifiable benchmark claims. Return findings with file/line evidence; do not edit unless explicitly asked.

## Handoff Prompt

> Prepare a handoff for the active unit: current objective, exact changed files, commands actually run and outputs, failed/unverified checks, specification decisions, active Idea to Deploy state, and one next action. Do not claim completion without a current adjudication receipt.
