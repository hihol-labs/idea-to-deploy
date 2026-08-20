# Claude Code Implementation Guide: Nginx Stream Analyzer

## 1. How to Use This Guide

Run one implementation step per session, in the order in `IMPLEMENTATION_PLAN.md`. Before each step, read `PROJECT_ARCHITECTURE.md`, the matching PRD requirements, and the step’s exact file/check list. Do not implement deferred P1/P2 scope while a P0 step is active. Update specifications first if required behavior changes.

The invariant exit contract in every step is: `0` complete success, `1` input/runtime failure, `2` CLI usage error, `3` non-empty input with no valid records, and `4` unique-cardinality exhaustion. Code 4 means exact unique User-Agent tracking reached its configured safety ceiling; it must stop safely and must not produce a partial report.

## 2. Global Implementation Prompt

> Implement exactly one numbered step from `IMPLEMENTATION_PLAN.md` for the local Python 3.11 nginx streaming CLI. Read `PROJECT_ARCHITECTURE.md`, `PRD.md`, and `STRATEGIC_PLAN.md` first. Preserve the single-process streaming architecture, no database, no HTTP API/server/auth/cloud/Kubernetes, and pip installation. Use Click, Rich, and dataclasses. Do not buffer the input file. Keep stdout for complete report data and stderr for diagnostics. Preserve exit codes 0/1/2/3/4, where 4 is unique-cardinality exhaustion. Add the specified tests and run every verification command for the active step. Stop after that step and report changed files and actual test results.

## 3. Step Prompts

### Step 1 — Package skeleton and contracts

> Execute Step 1 from `IMPLEMENTATION_PLAN.md`. Create only the package metadata, console entry point, domain/error contracts, CLI option declarations, and their tests. Freeze JSON/CSV/report field names from `PROJECT_ARCHITECTURE.md`. Ensure Click owns usage errors as exit 2 and define domain errors for exit 1, 3, and 4 without yet inventing parser behavior. Verify editable install, help, version, and `tests/test_cli.py`.

### Step 2 — Streaming parser

> Execute Step 2 from `IMPLEMENTATION_PLAN.md`. Implement incremental UTF-8 file/stdin input and compiled parsers for the documented nginx common/combined formats. Parse the logged timezone-aware timestamp; do not convert hours to local machine time. Count malformed records transparently. Add reviewed fixtures and edge-case parser tests. Do not implement rendering or deferred formats.

### Step 3 — Aggregation

> Execute Step 3 from `IMPLEMENTATION_PLAN.md`. Build the one-pass aggregator and orchestration service. Error URLs include statuses 400–599. Emit deterministic top-10 ordering by count descending and key ascending. Hourly request distribution must be a percentage using exactly `100 × hourly_request_count / total_valid_requests`. Track exact nonempty User-Agents up to the configured limit; the next distinct value raises the failure mapped to exit 4. Add focused tests for boundaries and zero denominators.

### Step 4 — Terminal output

> Execute Step 4 from `IMPLEMENTATION_PLAN.md`. Implement only the Rich terminal renderer against the immutable Report dataclass. Escape all untrusted log values, honor `--no-color`, and keep golden tests color-free and deterministic. Do not let styling alter metrics or structured output contracts.

### Step 5 — JSON output

> Execute Step 5 from `IMPLEMENTATION_PLAN.md`. Implement `--json` using the exact versioned schema in `PROJECT_ARCHITECTURE.md`. Emit no ANSI content or stderr diagnostics on stdout. Ensure failure exits 1/2/3/4 cannot leave partial JSON. Add schema and golden tests and validate output with `python -m json.tool`.

### Step 6 — CSV output

> Execute Step 6 from `IMPLEMENTATION_PLAN.md`. Implement the fixed `schema_version,section,key,count,percentage` CSV contract with the standard CSV writer. Apply and test the documented spreadsheet-formula safety policy. Keep output deterministic, ANSI-free, and parseable. Do not alter JSON or terminal semantics.

### Step 7 — End-to-end exit behavior

> Execute Step 7 from `IMPLEMENTATION_PLAN.md`. Wire and test the full exit-code contract: 0 success, 1 input/runtime failure, 2 usage error, 3 non-empty all-invalid input, 4 unique-cardinality exhaustion. Empty input is exit 0 with a zero report; mixed input is exit 0 with invalid counts. Codes 3 and 4 emit diagnostics on stderr and no partial success report in any format. Exercise file and stdin paths.

### Step 8 — Performance and release

> Execute Step 8 from `IMPLEMENTATION_PLAN.md`. Add only benchmark/test/release-support artifacts, not product features. Generate the 1 GB corpus outside the repository, capture reference machine and peak RSS details, and verify elapsed time under 30 seconds. Run the complete suite, coverage, build metadata check, clean wheel install, help/version smoke tests, and all five exit-code paths. Do not claim the performance gate from a smaller extrapolated sample.

## 4. Review Checklist for Every Step

- Scope matches exactly one active step and its P0 requirements.
- Input processing stays incremental and single-process.
- No database, HTTP endpoint, server, authentication, cloud, Docker, or Kubernetes dependency appears.
- Output ordering and schemas are deterministic.
- Untrusted log text is encoded/escaped by the target renderer.
- `0/1/2/3/4` semantics remain intact; code 4 is unique-cardinality exhaustion.
- The step’s verification commands actually ran and their outcomes are recorded.
- Documentation changes accompany any approved contract change before implementation changes.

## 5. Session Handoff

At the end of each session or meaningful work block, save context through `/session-save`. Record the active step, files changed, commands run with results, unresolved risks, and the exact next action. Do not mark a step done from narration alone.
