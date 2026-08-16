# Claude Code Implementation Guide: nginx-stream-stats

## How to Use This Guide

Execute one prompt at a time, in order, with WIP=1. Before editing, read [PRD.md](PRD.md), the relevant [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) sections, and the corresponding [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) step. Do not implement behavior that changes the specification silently.

Every prompt must preserve and test the full exit contract: `0` success; `1` operational I/O or unexpected internal failure; `2` invalid CLI invocation; `3` log data/format failure; `4` unique-cardinality exhaustion. Code 4 must never be omitted or remapped.

The hourly distribution formula is exactly `100 × hourly_request_count / total_valid_requests`. Unique User-Agent share is exact, not approximate.

## Prompt 1 — Package Skeleton

Implement Step 1 only. Create the Python 3.11 `pyproject.toml`, `src/nginx_stream_stats` package, Click console entry point, and verification configuration named in the plan. Keep runtime dependencies to Click and Rich. Add help/version and usage-error tests, run the Step 1 commands, and report changed files plus command outcomes. Do not implement parsing or metrics yet.

## Prompt 2 — Domain and Error Contracts

Implement Step 2 only. Add frozen dataclasses and typed domain exceptions exactly as specified in architecture section 4. Add invariant tests and explicit CLI mapping tests for all `0/1/2/3/4` categories, including code 4 for `CardinalityLimitError`. Run the Step 2 checks and stop after evidence.

## Prompt 3 — Streaming Parser

Implement Step 3 only. Parse nginx combined format one line at a time with strict UTF-8 expectations, escaped quoted fields, bounded request splitting, timezone-aware timestamps, and typed parse errors. Do not retain raw lines or call unbounded `read()`/`readlines()`. Add the named fixtures/tests and run the Step 3 checks.

## Prompt 4 — Ranked and Hourly Metrics

Implement Step 4 only. Add deterministic IP and status-400–599 URL counters, 24 logged-hour buckets, and finalization. Use `100 × hourly_request_count / total_valid_requests` exactly; do not describe or implement an unscaled fraction. Break count ties by key ascending and round only in renderers. Add hand-calculated tests and run Step 4 checks.

## Prompt 5 — User-Agent Cardinality

Implement Step 5 only. Add exact distinct User-Agent tracking up to the positive configured limit. A new distinct value beyond the limit must raise `CardinalityLimitError`, emit no approximate result, and map to exit 4. Compute share as `100 × unique_user_agent_count / total_valid_requests`. Test duplicates, exact boundary, and boundary + 1, then run Step 5 checks.

## Prompt 6 — Three Renderers

Implement Step 6 only. Create Rich terminal, stable JSON, and tidy CSV renderers over the same immutable report. Escape log-derived terminal text, keep ANSI out of JSON/CSV, use standard encoders, and match architecture schemas/precision. Add semantic parity and parser round-trip tests; run Step 6 checks.

## Prompt 7 — Complete CLI

Implement Step 7 only. Wire file/stdin streaming, strict/lenient behavior, mutually exclusive output modes, stdout/stderr separation, and typed failures. Prove the complete exit mapping: 0 success, 1 operational/internal, 2 invocation, 3 data/format, 4 unique-cardinality exhaustion. Code 4 cannot fall through the code-1 handler. Run all Step 7 commands.

## Prompt 8 — Performance Gate

Implement Step 8 only. Create a deterministic exact-1-GB fixture generator and opt-in benchmark without checking generated data into the repository. Record machine and Python details, generator arguments, wall time, and peak RSS. The acceptance target is under 30 seconds. Profile before optimizing and preserve all output/exit contracts. Run Step 8 commands and report evidence without generalizing beyond the measured machine.

## Prompt 9 — Release Readiness

Implement Step 9 only. Replace README planning caveats with verified install/use instructions, build sdist/wheel, inspect metadata, install in a clean Python 3.11 environment, and run the full test, 90% coverage, lint, typing, JSON smoke, and benchmark gates. Confirm all `0/1/2/3/4` scenarios still pass. Do not publish externally unless separately authorized.

## Completion Checklist for Every Prompt

- [ ] Only the active step's files and necessary spec corrections changed.
- [ ] New behavior has executable tests.
- [ ] Stdout remains report-only and stderr diagnostic-only.
- [ ] No database, HTTP API, auth, service, network, cloud, or Kubernetes was added.
- [ ] Relevant verification commands ran and their outcomes were recorded.
- [ ] If behavior changed, PRD/architecture changed first.
- [ ] The next step is explicit, but not started.
