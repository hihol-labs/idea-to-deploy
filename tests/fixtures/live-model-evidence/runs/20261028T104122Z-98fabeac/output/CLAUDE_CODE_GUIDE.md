# Claude Code Implementation Guide: nginx-stream-insights

## How to Use This Guide

Execute one implementation step at a time, in order, using `IMPLEMENTATION_PLAN.md` as the checklist and `PROJECT_ARCHITECTURE.md` as the interface authority. Do not implement deferred features. For each step: add tests, run the listed verification, update `CLAUDE.md` only from observed results, then request review before committing or moving on.

Every prompt below preserves the complete exit contract `0/1/2/3/4`: 0 success, 1 input I/O/decode failure, 2 CLI usage error, 3 strict parse failure, and 4 unique-cardinality exhaustion.

## Prompt 1 — Package Skeleton

> Implement Step 1 from `IMPLEMENTATION_PLAN.md`. Read `PRD.md` and `PROJECT_ARCHITECTURE.md` first. Create only the package skeleton, dataclasses, Click help/version behavior, and their tests. Use Python 3.11, Click, Rich, dataclasses, src layout, and pip packaging. Preserve the `0/1/2/3/4` exit contract in public documentation even though only help/success and usage are exercised here. Run all Step 1 verification commands and report actual outputs; do not claim later steps complete.

## Prompt 2 — Parser

> Implement Step 2 only. Create a streaming-compatible parser for the documented nginx `common` and `combined` formats. Treat log text as untrusted data; cover IPv4, IPv6, timezone offsets, escaped quoting, missing User-Agent, malformed timestamp, and malformed status. Do not add arbitrary format DSLs. Run `python3.11 -m pytest tests/unit/test_parser.py` and report the observed result.

## Prompt 3 — Aggregation

> Implement Step 3 only. Compute all metrics in one pass with deterministic top-10 ties. Hourly percentage must use exactly `100 × hourly_request_count / total_valid_requests`. Implement exact unique User-Agent share, zero-input behavior, configurable cardinality guards, and the code-4 failure path for unique-cardinality exhaustion. Do not silently approximate. Run the Step 3 tests and report measured results.

## Prompt 4 — Terminal Output

> Implement Step 4 only. Build the Rich renderer for all four report sections plus valid/invalid totals. Escape log-derived strings. Auto-enable color only for a TTY, honor `--color/--no-color`, and keep machine formats out of scope for this step. Add renderer tests and run their exact verification command.

## Prompt 5 — JSON and CSV

> Implement Step 5 only. Follow the exact JSON keys and CSV long-form header in `PROJECT_ARCHITECTURE.md`. Use standard serializers, schema versioning, deterministic order, no ANSI escapes, and tests for escaping and empty reports. Do not invent a database or API. Run both renderer test files.

## Prompt 6 — CLI Integration

> Implement Step 6 only. Wire file/stdin streaming, parser, aggregator, and renderers in Click. Keep stdout for reports and stderr for diagnostics. Test the entire `0/1/2/3/4` exit-code contract without remapping: 0 report success, 1 I/O or decode failure, 2 usage error, 3 strict parse failure, 4 unique-cardinality exhaustion. Test mutual exclusion of `--json` and `--csv`, strict/skip policy, and cardinality failure. Run all listed integration and pipe checks.

## Prompt 7 — Quality and Performance

> Implement Step 7 only. Add deterministic fixture generation outside Git, a benchmark that records environment and peak RSS, a small normal-suite scaling test, 90% coverage enforcement, and build validation. Run the full coverage command. Then generate and benchmark a 1 GB fixture against the under-30-second requirement. Report actual time, throughput, memory, and environment; a failed target remains failed evidence.

## Prompt 8 — Release Candidate Documentation

> Implement Step 8 only. Replace planning examples with verified installation, schemas, limits, exit codes, and measured benchmark data. Run the full test/build/install smoke sequence from the plan. Do not publish, push, open a PR, or deploy without explicit human approval. Update the status table only for commands that actually passed.

## Review Checklist for Every Step

- Scope matches exactly one plan step (WIP=1).
- New behavior has focused tests that were actually run.
- Streaming input is retained; whole-file reads are forbidden.
- Machine outputs contain no Rich markup or ANSI codes.
- Exact counts never degrade silently under cardinality pressure.
- The `0/1/2/3/4` contract remains stable.
- No secrets, logs, or telemetry leave the local machine.
- Progress claims cite command output from the current session.

