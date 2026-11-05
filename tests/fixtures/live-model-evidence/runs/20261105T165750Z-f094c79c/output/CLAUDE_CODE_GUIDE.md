# Claude Code Guide: Nginx Lens

These are future execution prompts for [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), not work performed in this planning session. Read [CLAUDE.md](CLAUDE.md), [PRD.md](PRD.md), [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) and [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) first. Agent instructions are centralized in CLAUDE.md; this file contains task prompts and acceptance reminders.

## Shared Acceptance Contract

Preserve exit codes **0/1/2/3/4**: 0 successful processing/help/version, 1 I/O or runtime failure, 2 usage error, 3 interruption, 4 unique-cardinality exhaustion.

Code 4 means unique-cardinality exhaustion; never silently approximate, truncate, or remap it.

Hourly percentage is `100 × hourly_request_count / total_valid_requests`. UA share is 100 times distinct nonmissing UAs over valid requests containing nonmissing UAs; zero denominator means 0.0. Use a single local Python 3.11 process with Click, Rich and dataclasses. Do not add auth, persistence, HTTP, cloud or Kubernetes. Test commands must actually run before reporting success. No implementation step is complete yet.

## Prompt 1: Package Skeleton

“Execute step 1 only. Create pyproject.toml, src/nginx_lens/__init__.py, cli.py, models.py and tests/test_cli.py. Configure the nginx-lens console command and dev dependencies including pytest, pytest-cov and build. Verify help/version and invalid-option behavior with the exact step commands. Record actual results; do not claim metrics are implemented.”

## Prompt 2: Reader and Parser

“Execute step 2 after step 1 passes. Implement reader.py and parser.py against the architecture's combined grammar. Add synthetic fixtures and reader/parser tests for escaping, timezone validation, IPv6, malformed UTF-8, oversized bounded draining and final newline behavior. Run the step suite. Retain only one bounded input record at a time.”

## Prompt 3: Aggregation

“Execute step 3. Implement aggregate.py and model updates with exact IP/error-path/UA state, UTC buckets, deterministic ties and all denominators. Test small hand-counted fixtures and atomic shared-cardinality preflight before any mutation. Run tests/test_aggregate.py; code 4 must preserve exactness by refusing the report.”

## Prompt 4: Exports

“Execute step 4. Implement JSON/CSV in render.py and connect CLI processing. Match architecture fields, CSV header and row ordering exactly. Add expected fixtures and round-trip escaping tests. Run tests/test_exports.py and the fixture JSON command; diagnostics belong on stderr.”

## Prompt 5: Terminal Output

“Execute step 5. Add Rich tables to render.py and tests/test_terminal.py. Show all four metrics and valid/invalid totals. Escape markup and control characters. Verify TTY color, redirected output, --no-color and NO_COLOR using the step's commands.”

## Prompt 6: Failure Semantics

“Execute step 6. Finish cli.py/reader.py error boundaries and subprocess tests/test_process.py. Exercise the complete 0/1/2/3/4 contract, SIGINT/SIGTERM, broken pipe, missing file, invalid flags, all-invalid input and resource exhaustion. Processing failure must emit no aggregate report; output failure can leave partial output but returns 1. Run process and CLI tests.”

## Prompt 7: Performance

“Execute step 7. Create benchmarks/run.py, the corpus correctness test and benchmarks/RESULTS.md. Run the full coverage suite and the documented decimal-1-GB benchmark for text/JSON/CSV. Record environment, corpus statistics, cache conditions, wall times and peak RSS. Target under 30 seconds for each run; profile failures and block release rather than relabeling them.”

## Prompt 8: Release Readiness

“Execute step 8. Create LICENSE and tests/test_distribution.py. Validate a locally built wheel in a fresh Python 3.11 venv outside the checkout. Reconcile docs, run distribution and full suites, and record actual review/dependency findings. Do not publish, deploy, push or invent external reviewer evidence. Apply separately supplied adversarial findings before release if required.”

## Handoff

At each significant milestone, update the step table in CLAUDE.md and save continuity with the repository-local session-save skill. Keep failed/unrun checks explicit. The external harness runs the adversarial reviewer after this blueprint session; no inline review or DEVILS_ADVOCATE_REVIEW.md is generated here.
