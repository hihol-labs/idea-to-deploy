# Claude Code Implementation Guide: nginx-insight

Use this guide after the blueprint is accepted. Execute one step at a time, keep WIP=1, and treat `PRD.md` plus `PROJECT_ARCHITECTURE.md` as the source of truth. Do not implement deferred P2 features while completing the MVP.

## Global Contract for Every Prompt

- Runtime and stack: Python 3.11, Click, Rich, dataclasses, pip packaging.
- Architecture: one local process, streaming and stateless; no database, HTTP API, server, cloud, or Kubernetes.
- Metrics: exact top-10 IPs, exact top-10 4xx/5xx URLs, 24 hourly percentages using `100 × hourly_request_count / total_valid_requests`, and unique User-Agent count/share.
- Output: colored terminal by default, plus mutually exclusive `--json` and `--csv`.
- Exit codes: `0/1/2/3/4` map respectively to success, input/I/O failure, usage error, log-data failure, and unique-cardinality exhaustion.
- Never emit partial JSON/CSV on failure. Keep report data on stdout and diagnostics on stderr.
- For each step, add tests first where practical, run the stated checks, and stop if the evidence fails.

## Prompt 1: Package and CLI

> Implement Step 1 of `IMPLEMENTATION_PLAN.md`. Read `PRD.md` and `PROJECT_ARCHITECTURE.md` first. Create the Python 3.11 package, Click console entry point, dependency metadata, help/version behavior, option validation, and typed error boundary. Do not implement parsing or reports yet. Test mutual exclusion of `--json` and `--csv`. Run the focused tests and report changed files and evidence.

## Prompt 2: Parser and Models

> Implement Step 2 of `IMPLEMENTATION_PLAN.md`. Add dataclasses and a parser for standard nginx combined format. Parse an offset-aware timestamp, request target, status, client IP, and User-Agent; return explicit malformed reasons without retaining raw lines. Add focused fixtures and tests for valid, quoted, timezone, and malformed cases. Do not add renderers.

## Prompt 3: Streaming Inputs

> Implement Step 3 of `IMPLEMENTATION_PLAN.md`. Iterate files and stdin sequentially with buffered UTF-8 decoding; never read a whole input into memory. Add default skip/count behavior, bounded diagnostic samples, and `--strict` code-3 behavior. Prove path order, stdin, I/O failure, decoding failure, and stdout/stderr separation in tests.

## Prompt 4: Aggregation

> Implement Step 4 of `IMPLEMENTATION_PLAN.md`. Compute all four exact views in one pass. Use deterministic count-descending/key-ascending top-ten ordering. Produce 24 buckets and calculate each with `100 × hourly_request_count / total_valid_requests`. Enforce `--max-unique` before adding a new aggregate key. Test boundary statuses, ties, timezone offsets, empty buckets, User-Agent share, and code 4 without partial output.

## Prompt 5: Terminal Output

> Implement Step 5 of `IMPLEMENTATION_PLAN.md`. Build the Rich renderer with four clear sections and a processed/malformed summary. Color only compatible TTY output unless disabled; safely render untrusted log-derived strings. Add stable tests for semantic content and prove redirected output has no ANSI sequences.

## Prompt 6: JSON and CSV

> Implement Step 6 of `IMPLEMENTATION_PLAN.md`. Add versioned JSON and normalized RFC 4180 CSV exactly as specified under `PROJECT_ARCHITECTURE.md` → `CLI Interface`. Use standard encoders, include all 24 hourly buckets, keep percentages semantically consistent, and emit no styling. Add round-trip parser tests and golden semantic comparisons.

## Prompt 7: Acceptance and Exit Codes

> Implement Step 7 of `IMPLEMENTATION_PLAN.md`. Add end-to-end tests for all P0 stories and assert the full `0/1/2/3/4` contract: success, input/I/O failure, usage error, log-data failure, unique-cardinality exhaustion. Verify failed machine-output runs produce zero report bytes and diagnostics remain on stderr. Do not remap code 4.

## Prompt 8: Performance and Release

> Implement Step 8 of `IMPLEMENTATION_PLAN.md`. Build a reproducible representative 1 GB benchmark whose generation is outside timing, record the reference environment, profile before optimizing, and meet the under-30-second target. Build wheel/sdist, install the wheel into a clean Python 3.11 environment, run all checks, update README, then use the Idea to Deploy Verification Loop on the exact staged candidate. Do not claim completion without current adjudication evidence.

## Handoff Checklist

- [ ] P0 acceptance criteria and complete suite pass on Python 3.11.
- [ ] Terminal, JSON, and CSV values agree.
- [ ] Exit codes `0/1/2/3/4` are exercised, including code 4 for unique-cardinality exhaustion.
- [ ] The installed artifact meets the documented 1 GB performance target.
- [ ] No database, server, network, authentication, cloud, or Kubernetes component was introduced.
- [ ] Project state, test evidence, and next action are recorded for handoff.
