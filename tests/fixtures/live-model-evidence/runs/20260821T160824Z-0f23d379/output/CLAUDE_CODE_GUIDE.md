# Claude Code Implementation Guide: Nginx Stream Analyzer

## How to Use This Guide

Run one prompt at a time in order and preserve WIP=1. Before each step, read `PRD.md`, the named architecture sections, `.itd/SCOPE_LOCK.md`, and `.itd/VERIFICATION_CONTRACT.json`. Do not expand scope. After implementation, freeze and verify the exact candidate using the repository’s current Idea to Deploy acceptance route.

Every prompt inherits this non-negotiable exit-code contract: `0` = successful complete output; `1` = strict malformed-log or analysis-invariant failure; `2` = CLI usage error; `3` = input/output system error; `4` = unique-cardinality exhaustion. Code `4` must remain distinct in implementation, tests, terminal mode, JSON mode, and CSV mode.

The hourly request percentage must use the literal formula `100 × hourly_request_count / total_valid_requests`; it is never an unscaled fraction. Do not implement product code from this blueprint session itself—these are future-session prompts.

## Prompt 1: Package and CLI Contract

> Implement only Step 1 of `IMPLEMENTATION_PLAN.md`. Create the Python 3.11 `src/` package, pip metadata, console entry point, Click options, domain error skeleton, and CLI contract tests. Follow `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. Preserve stdout/stderr separation and the full exit codes `0/1/2/3/4`; code 4 means unique-cardinality exhaustion. Do not implement parsing or reports yet. Run the exact Step 1 verification commands, record evidence, update the active Idea to Deploy state, and stop.

## Prompt 2: Models and Parser

> Implement only Step 2 of `IMPLEMENTATION_PLAN.md`. Add the specified dataclasses, combined-log parser, fixtures, and parser tests. Parse remote IP, logged timestamp hour, request target, status, and User-Agent. Treat logs as untrusted data and never echo raw malformed lines in errors. Preserve exit codes `0/1/2/3/4`, including code 4 reserved for unique-cardinality exhaustion. Run Step 2 verification, record evidence, reconcile state, and stop.

## Prompt 3: Streaming Aggregation

> Implement only Step 3 of `IMPLEMENTATION_PLAN.md`. Add a one-pass accumulator with exact top-10 IPs, exact top-10 400–599 URLs, all 24 hourly buckets, and exact unique User-Agent count within independent per-dimension limits. Use `100 × hourly_request_count / total_valid_requests` for hourly percentages and `100 × unique_user_agent_count / total_valid_requests` for User-Agent share, with zero-denominator behavior from the architecture. Enforce the cap before inserting a new key. Exhaustion must emit no partial success report and must be code 4. Test every dimension and the entire `0/1/2/3/4` mapping. Run Step 3 verification, record evidence, reconcile state, and stop.

## Prompt 4: Streaming I/O and Diagnostics

> Implement only Step 4 of `IMPLEMENTATION_PLAN.md`. Connect file/stdin line iteration, strict/non-strict malformed handling, sanitized diagnostics, and exception-to-exit mapping. Never load the whole input. Map success to 0, data/invariant failure to 1, usage to 2, I/O to 3, and unique-cardinality exhaustion to 4. Add file/stdin parity and all-code tests. Run Step 4 verification, record evidence, reconcile state, and stop.

## Prompt 5: Rich Terminal Output

> Implement only Step 5 of `IMPLEMENTATION_PLAN.md`. Create the Rich renderer for summary counts, both top-10 rankings, 24 hourly buckets, and User-Agent diversity. Escape untrusted values, auto-detect TTY color, honor `NO_COLOR`, and keep machine modes ANSI-free. Retain `0/1/2/3/4`; code 4 is unique-cardinality exhaustion. Run Step 5 verification, record evidence, reconcile state, and stop.

## Prompt 6: JSON and CSV Output

> Implement only Step 6 of `IMPLEMENTATION_PLAN.md`. Create deterministic renderers exactly matching the JSON and CSV schemas under `PROJECT_ARCHITECTURE.md` `## CLI Interface`. Add golden fixtures, schema/quoting tests, and reconciliation across formats. Warnings stay on stderr. On exit 4, emit no partial JSON/CSV success artifact. Verify all exit codes `0/1/2/3/4` in both formats. Run Step 6 verification, record evidence, reconcile state, and stop.

## Prompt 7: Correctness and Packaging QA

> Implement only Step 7 of `IMPLEMENTATION_PLAN.md`. Add invariants, adversarial rendering fixtures, quality tooling, package builds, clean-wheel installation, and README examples. Do not add runtime features. Require at least 90% statement coverage and test exact mappings for `0/1/2/3/4`, with code 4 exclusively identifying unique-cardinality exhaustion. Run Step 7 verification, record evidence, reconcile state, and stop.

## Prompt 8: Performance and Handoff

> Implement only Step 8 of `IMPLEMENTATION_PLAN.md`. Add deterministic benchmark generation and a runner that records environment, input identity, elapsed time, throughput, and peak RSS. Measure before optimizing. Prove 1 GB completes in under 30 seconds on the named reference laptop while output stays exact and hourly percentages still use `100 × hourly_request_count / total_valid_requests`. Run the complete suite and codes `0/1/2/3/4`; code 4 remains unique-cardinality exhaustion. Freeze the exact candidate and use the project’s current verification contract and risk-tier checker. Record evidence, reconcile state, and stop.

## Cross-Step Review Checklist

- Scope remains a local Python 3.11 CLI: no auth, database, HTTP API, server, cloud, or Kubernetes.
- Input is streamed once; no complete-file buffering or hidden persistence exists.
- Top rankings, hourly values, and User-Agent values reconcile across terminal, JSON, and CSV.
- Machine output is deterministic and stdout is never contaminated by diagnostics or ANSI sequences.
- Sensitive log values are not echoed in diagnostics and Rich markup is neutralized.
- Exact aggregation stops explicitly at the configured unique limit; it never silently drops or approximates.
- Tests exercise success 0, data failure 1, usage 2, I/O 3, and unique-cardinality exhaustion 4.
- The 1 GB target is accepted only from recorded execution on the documented reference laptop.
