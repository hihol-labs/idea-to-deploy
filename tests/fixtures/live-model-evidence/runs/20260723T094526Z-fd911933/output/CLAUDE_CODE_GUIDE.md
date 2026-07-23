# Claude Code Guide: Nginx Stream Analytics CLI

## How to Use This Guide

Run one prompt at a time and preserve WIP=1. Before each step, read [CLAUDE.md](CLAUDE.md), the named sections of [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), and the matching step in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Do not report a step complete without the listed commands' current output and reconciled project state.

These prompts authorize only the named implementation step. They do not authorize deployment, publishing packages, widening scope, or changing output semantics without first updating the PRD and architecture.

## Prompt 1: Package and CLI Contract

```text
Implement STEP 1 from IMPLEMENTATION_PLAN.md only. Create the Python 3.11 package metadata, console entry point, minimal Click command, and CLI contract tests. Preserve the CLI options and exit semantics in PROJECT_ARCHITECTURE.md section 7. Do not implement parsing or reports. Run the step's verification commands, record exact output, update the STEP 1 row in CLAUDE.md, and stop.
```

## Prompt 2: Models and Parser

```text
Implement STEP 2 from IMPLEMENTATION_PLAN.md only. Create the dataclasses, supported nginx combined-format parser, representative hand-auditable fixture, and parameterized parser tests. Treat log fields as untrusted. Cover IPv4, IPv6, escaping, request targets, timezone offsets, status bounds, invalid UTF-8, and malformed lines. Run the exact STEP 2 verification, update CLAUDE.md status, and stop.
```

## Prompt 3: Streaming Aggregation

```text
Implement STEP 3 from IMPLEMENTATION_PLAN.md only. Compute all four PRD metrics in one pass with exact User-Agent semantics and deterministic top-10 ties, including more than ten equally counted keys. Never retain complete input or couple aggregation to Click/Rich. Add boundary and empty-input tests. Run the listed tests and branch-coverage command, update CLAUDE.md, and stop.
```

## Prompt 4: JSON Output

```text
Implement STEP 4 from IMPLEMENTATION_PLAN.md only. Follow JSON schema version 1 in PROJECT_ARCHITECTURE.md exactly, including all 24 hour rows, ranking order, empty semantics, and no ANSI bytes. Add a hand-reviewed golden JSON fixture. Run JSON parsing and focused tests, attach output, update CLAUDE.md, and stop.
```

## Prompt 5: CSV Output

```text
Implement STEP 5 from IMPLEMENTATION_PLAN.md only. Follow the normalized six-column CSV schema in PROJECT_ARCHITECTURE.md. Use the standard csv module, cover commas/quotes/newlines, and neutralize spreadsheet formula prefixes without corrupting ordinary values. Add golden and round-trip tests. Run STEP 5 verification, update CLAUDE.md, and stop.
```

## Prompt 6: Rich Text Output

```text
Implement STEP 6 from IMPLEMENTATION_PLAN.md only. Build the default Rich report and visibly escape terminal control/bidi characters before escaping Rich markup. Implement TTY-aware color, --no-color, and NO_COLOR; JSON/CSV behavior must remain unchanged. Test control-sequence and markup injection plus redirected output. Run focused verification, update CLAUDE.md, and stop.
```

## Prompt 7: I/O and Error Semantics

```text
Implement STEP 7 from IMPLEMENTATION_PLAN.md only. Complete binary line-by-line file/stdin processing with explicit per-line UTF-8 decode policy, bounded lenient diagnostics, strict first-error behavior, expected exit codes, empty input, and broken-pipe handling. Do not read the whole file or echo sensitive full lines in errors. Run all STEP 7 commands, update CLAUDE.md, and stop.
```

## Prompt 8: Performance Evidence

```text
Implement STEP 8 from IMPLEMENTATION_PLAN.md only. Create deterministic exact-size typical and high-cardinality benchmark generators, a CI-sized performance regression test, and docs/BENCHMARK.md. Run the representative 1 GiB command on the current laptop and record hardware, OS, Python, cache policy, file hash/size, cardinalities, elapsed time, and peak RSS. Microbenchmark parser choices and profile before optimizing. Do not weaken correctness or silently approximate. Update CLAUDE.md and stop.
```

## Prompt 9: Release Quality

```text
Implement STEP 9 from IMPLEMENTATION_PLAN.md only. Reconcile README with actual behavior, add the Python 3.11 CI workflow and installed-package smoke test, then run lint, typing, full tests/coverage, build checks, and clean-wheel installation. Do not publish or tag. Freeze the exact candidate for verification under the repository Idea to Deploy contract, record the adjudication evidence, update CLAUDE.md, and stop.
```

## Review Prompt

```text
Review the current exact candidate against PRD.md, PROJECT_ARCHITECTURE.md, and all completed implementation steps. Focus on nginx parsing correctness, deterministic schemas, streaming behavior, high-cardinality memory, Rich/control-sequence injection, CSV formula injection, stdout/stderr separation, and exit codes. Report findings by severity with file/line evidence. Do not edit during review.
```

## Recovery Prompt

```text
The active step failed verification. Preserve WIP=1. Record the exact failing command/output and classify the smallest root cause. Change only files in the active step's scope, add or tighten a regression test, rerun that step's complete verification, and leave the state RECOVERY_REQUIRED if any required command remains unverified.
```
