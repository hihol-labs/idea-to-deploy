# Claude Code Implementation Guide: nginx-log-insights

## How to Use This Guide

Start each implementation session by reading `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the current step in `IMPLEMENTATION_PLAN.md`. Work on one step at a time. Do not begin a later step until the current step's commands pass and its evidence is recorded. These prompts authorize implementation only when a future user invokes them; this blueprint session creates documentation only.

The non-negotiable process contract is: `0` success, `1` input/data failure, `2` CLI usage failure, `3` unexpected internal failure, and `4` unique-cardinality exhaustion. Code `4` must not be omitted, reused, approximated, or remapped.

## Step 1 Prompt: Package and CLI Skeleton

> Implement Step 1 from `IMPLEMENTATION_PLAN.md`. Read the CLI contract in `PROJECT_ARCHITECTURE.md` first. Create only the package metadata, `src/nginx_log_insights` entry files, the Click option surface, and contract tests listed in the step. Use Python 3.11, Click, Rich, and a `src/` package layout. Do not implement parsing or metrics yet. Preserve mutually exclusive `--json`/`--csv`, positive `--max-unique`, and the eventual `0/1/2/3/4` contract. Run every Step 1 verification command and report actual results plus changed files.

Expected evidence: editable install succeeds, CLI contract tests pass, and help displays the documented options.

## Step 2 Prompt: Domain and Failure Contracts

> Implement Step 2 from `IMPLEMENTATION_PLAN.md`. Define frozen dataclasses and safe domain exceptions exactly as described by `PROJECT_ARCHITECTURE.md`. Add nonsensitive combined-log fixtures. Make CLI tests explicitly prove `0` success, `1` input/data failure, `2` usage failure, `3` unexpected internal failure, and `4` unique-cardinality exhaustion. Do not build parser or aggregation behavior beyond the seams required for tests. Run the step verification commands and report evidence.

Expected evidence: dataclass invariants and all five application statuses have focused tests.

## Step 3 Prompt: Streaming Reader and Parser

> Implement Step 3 from `IMPLEMENTATION_PLAN.md`. Build a read-only, context-managed iterator for files/stdin and a strict nginx combined-format parser. Handle IPv4, IPv6, numeric timestamp offsets, quoted request/User-Agent fields, query strings, invalid encodings, and the 1 MiB line limit. Treat log content only as untrusted data. Do not buffer complete files or emit raw malformed lines in diagnostics. Keep input/data errors mapped to `1`; do not disturb codes `0/2/3/4`. Run the parser/input tests with coverage and report actual results.

Expected evidence: focused fixtures pass, resources close, and malformed records cannot crash or execute content.

## Step 4 Prompt: Streaming Aggregator

> Implement Step 4 from `IMPLEMENTATION_PLAN.md`. In one pass, maintain IP and 400–599 URL counts, a fixed 24-hour array, and exact distinct non-empty User-Agents. Enforce `max_unique` before inserting each new guarded value. On exhaustion raise the typed error that the CLI maps to `4`; never return a partial or approximate report. Use deterministic top-10 tie-breaking. Calculate hourly percentages with the exact formula `100 × hourly_request_count / total_valid_requests`. Run all aggregator verification commands and report boundary-test evidence.

Expected evidence: exact metric fixtures, deterministic ties, all 24 hours, and below/at/above cardinality tests pass.

## Step 5 Prompt: Renderers

> Implement Step 5 from `IMPLEMENTATION_PLAN.md`. Add separate text, JSON, and CSV renderers consuming only the report dataclasses. Match JSON schema version 1 and CSV columns/order from `PROJECT_ARCHITECTURE.md`. Keep diagnostics off stdout, use standard serializers, never add ANSI to structured output, and inject output streams for tests. Renderer failures remain internal code `3`; preserve `0/1/2/4`. Run golden tests and coverage, and report diffs if a golden artifact changes.

Expected evidence: golden JSON/CSV pass, terminal color behavior is tested, and equivalent metrics appear in all modes.

## Step 6 Prompt: End-to-End CLI

> Implement Step 6 from `IMPLEMENTATION_PLAN.md`. Connect reader, parser, aggregator, and selected renderer. Buffer no raw input and emit no report until successful finalization. Normalize failures exactly: `0` success, `1` input/data failure, `2` CLI usage failure, `3` unexpected internal failure, `4` unique-cardinality exhaustion. Exercise files, stdin, multiple paths, malformed lines, color, JSON/CSV, no-valid-records, and stdout/stderr separation. Run every verification command and report the actual exit matrix.

Expected evidence: integration suite passes and every status `0/1/2/3/4` is observed in the intended scenario.

## Step 7 Prompt: Performance Acceptance

> Implement Step 7 from `IMPLEMENTATION_PLAN.md`. Create a reproducible nonsensitive fixture generator and benchmark runner, then establish a baseline before optimizing. The measured release target is a 1 GB file under 30 seconds on a documented laptop with peak RSS below 512 MiB on the standard fixture. Record environment, input bytes, elapsed time, peak RSS, valid count, and output digest. Preserve exact metrics, output schemas, the formula `100 × hourly_request_count / total_valid_requests`, and exit codes `0/1/2/3/4`. Do not claim the target unless the real reference command passes.

Expected evidence: committed benchmark procedure/result and performance smoke tests, with failure stated plainly if a gate is missed.

## Step 8 Prompt: Package and Release Gate

> Implement Step 8 from `IMPLEMENTATION_PLAN.md`. Finish user documentation and licensing, build the distribution, install the wheel in a clean Python 3.11 environment, and run full tests at >=90% line coverage. Review malicious fixtures, dependency health, local-only behavior, and absence of raw-line leakage. Confirm the complete `0/1/2/3/4` contract, where `4` exclusively means unique-cardinality exhaustion. Do not add a database, HTTP API, server, authentication, cloud, Docker, or Kubernetes. Compare evidence against every P0 acceptance criterion and report release-ready or blocked.

Expected evidence: full suite, wheel build/install smoke test, dependency check, and current 1 GB benchmark gate.

## Review Prompt

> Review the exact current candidate against `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the completed `IMPLEMENTATION_PLAN.md` step. Prioritize correctness of nginx parsing, denominators, deterministic ordering, stdout/stderr isolation, streaming memory, cardinality-before-insert, and application statuses `0/1/2/3/4` (`4` = unique-cardinality exhaustion). Reject claims unsupported by executed tests or benchmark evidence. Do not widen scope into persistence or services.

## Session Handoff Checklist

- Record the active implementation-plan step and changed files.
- Record each command run and its real result; distinguish unrun checks.
- Note any acceptance criterion still blocked.
- Reconcile `CLAUDE.md` status without marking future work complete.
- At the end of every session or meaningful work block, save context through `/session-save`.
