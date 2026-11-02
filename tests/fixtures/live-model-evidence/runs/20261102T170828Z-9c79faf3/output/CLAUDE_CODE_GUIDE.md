# Claude Code Implementation Guide: nginx-stream-insights

This guide translates `IMPLEMENTATION_PLAN.md` into bounded prompts for future implementation sessions. It does not authorize publishing, pushing, deploying, or changing the approved architecture. Start each session by reading `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the named step.

## Working Protocol

1. Work on only one numbered step at a time.
2. Before editing, restate the step’s scope, files, exclusions, and verification commands.
3. Add or update tests with production code; run the named tests rather than claiming they should pass.
4. Preserve stdout for report data and stderr for diagnostics.
5. If a behavior needs to change, update the specification before implementation.
6. End with changed files, commands actually run, outcomes, and the next step; run `/session-save` at the end of a significant work block.

## Global CLI Contract

Every implementation prompt below inherits this complete contract:

- `0`: successful analysis/output, including empty input;
- `1`: input I/O or unexpected runtime I/O failure;
- `2`: CLI usage/configuration error;
- `3`: non-empty input with no valid records;
- `4`: unique-cardinality exhaustion.

The literal failure condition for code 4 is `unique-cardinality exhaustion`; never omit it, silently approximate it, or remap it to code 1 or 3.

## Prompt 1 — Package Skeleton

> Implement only Step 1 of `IMPLEMENTATION_PLAN.md`. Create the Python 3.11 `src/` package, Click entry point, build metadata, and help/version tests. Do not implement parsing or metrics yet. Keep dependencies to Click, Rich, and test/build tooling. Preserve the global `0/1/2/3/4` contract as a design boundary even though this step exercises only help/version success and Click usage error. Run every Step 1 verification command and report exact outcomes. Do not publish or push.

Expected evidence: editable install succeeds, tests pass, and `nginx-stream-insights --help` exits 0.

## Prompt 2 — Models and Parser

> Implement only Step 2. Follow the parser/domain contracts in `PROJECT_ARCHITECTURE.md` and FR-02 in `PRD.md`. Add dataclasses and pure common/combined parsers with domain-specific malformed results; no printing, process exits, persistence, or raw-line logging. Cover IPv4/IPv6, quoting, logged timezone/hour, request target, status validation, placeholders, and malformed input. Keep the CLI `0/1/2/3/4` contract intact; the orchestrator, not the parser, will map failures. Run the Step 2 verification command and report evidence.

Expected evidence: focused parser suite passes with both valid formats and malformed cases.

## Prompt 3 — Streaming Aggregation

> Implement only Step 3. Stream file/stdin lines and update one canonical aggregation state without retaining raw records. Implement deterministic IP and 4xx/5xx URL rankings, all 24 hour buckets, `100 × hourly_request_count / total_valid_requests`, and exact non-empty User-Agent cardinality/share. Enforce the configured ceiling before adding a value that exceeds it. Preserve `0/1/2/3/4`, especially code 4 for unique-cardinality exhaustion. Run all Step 3 verification commands.

Expected evidence: input and aggregation suites pass; coverage output is recorded; formula, tie, empty, and ceiling tests exist.

## Prompt 4 — Text CLI

> Implement only Step 4. Wire Click, input, parser, aggregator, and Rich renderer. Text is the default; color must be disabled for `--no-color` or non-TTY stdout. Keep data on stdout and diagnostics on stderr. Implement exactly: 0 success/empty, 1 input or runtime I/O failure, 2 usage error, 3 non-empty input with no valid records, 4 unique-cardinality exhaustion. Mixed valid/malformed input succeeds and displays the malformed count. Run the focused tests and manual fixture command from Step 4.

Expected evidence: assertions cover streams and each exit code; no ANSI bytes appear with `--no-color`.

## Prompt 5 — JSON and CSV

> Implement only Step 5. Serialize the existing `Report`; do not recalculate metrics in renderers. JSON must emit one document with `schema_version`; CSV must use `metric,rank,key,count,percentage`. Enforce mutual exclusion of `--json` and `--csv` as exit 2. Pin ordering, escaping, schemas, and semantic parity in golden tests. Preserve all meanings in `0/1/2/3/4`, including 4 for unique-cardinality exhaustion. Run every Step 5 command.

Expected evidence: renderer/CLI tests pass and JSON validates with `python -m json.tool`.

## Prompt 6 — Follow and Controls

> Implement only Step 6. Add validated `--top`, `--max-unique-user-agents`, and regular-file-only `--follow`. Follow mode must avoid busy spinning, process appended complete lines, and stop cleanly on interruption. Invalid combinations return 2. Cardinality ceiling returns 4; preserve the rest of `0/1/2/3/4`. Use temporary files and bounded test waits so the test suite cannot hang. Run the focused Step 6 suite.

Expected evidence: follow tests complete deterministically and option boundary tests pass.

## Prompt 7 — Performance Gate

> Implement only Step 7. Add a deterministic synthetic log generator, benchmark runner, end-to-end tests, and benchmark documentation. Do not commit a 1 GB file. Record environment, command, wall time, peak RSS, and output counts. First run correctness and then measure the specified 1 GB workload; profile before optimizing. Optimizations may not change formulas, schemas, ordering, or exit codes `0/1/2/3/4` (4 remains unique-cardinality exhaustion). Report the measured result honestly if the 30-second target fails.

Expected evidence: full suite and coverage gate pass, and benchmark output records the target comparison on the named laptop.

## Prompt 8 — Packaging and Readiness

> Implement only Step 8. Finish user documentation and packaging, build a wheel, install it in a fresh temporary Python 3.11 environment, and smoke-test all output modes plus `0/1/2/3/4`. Ensure docs call code 4 unique-cardinality exhaustion. Run the complete test, wheel smoke, and performance commands. Prepare release notes but do not publish, push, or deploy without explicit human approval.

Expected evidence: wheel build/install smoke test, complete green suite, coverage result, and benchmark result are recorded.

## Review Checklist for Every Step

- Scope matches one implementation-plan step and no forbidden service/persistence feature appeared.
- New behavior has tests and the relevant test commands actually ran.
- Metrics use integer source counts and deterministic tie-breaking.
- No raw access-log line, secret, or local path leaks into normal diagnostics.
- Machine-output schema changes are specification-first and intentional.
- Status is not marked complete if any required verification failed or was skipped.

