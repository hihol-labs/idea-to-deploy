# Product Requirements Document: Nginx Stream Analyzer

## Product Summary

Nginx Stream Analyzer gives DevOps and SRE engineers a fast local summary of nginx access logs. It is a pip-installable Python 3.11 CLI, processes a file or stdin in one streaming pass, and emits colored terminal output by default or stable JSON/CSV for automation.

The product specification in this PRD and `PROJECT_ARCHITECTURE.md` is the source of truth. Behavioral changes begin here before implementation changes.

## Problem Statement

During incidents and exploratory troubleshooting, engineers often need a handful of high-value metrics before they know whether a larger observability system is warranted. Existing dashboards may be unavailable; ad-hoc shell pipelines are brittle; full analytics stacks are excessive. Engineers need a zero-setup, privacy-preserving tool that handles gigabyte-scale logs and has trustworthy pipeline semantics.

## Goals

- Report top 10 client IPs by valid request count.
- Report top 10 request targets among 4xx/5xx responses.
- Report request count and percentage for every local logged hour `00`–`23`.
- Report exact unique User-Agent count and its share of valid requests.
- Support readable terminal, JSON, and CSV outputs from identical results.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Provide stable error handling for shell automation.

## Non-Goals

- Authentication, accounts, permissions, or multi-tenancy.
- Database, saved history, indexing, search, or dashboards.
- HTTP API, daemon, server, remote ingestion, or network access.
- Cloud, container, or Kubernetes deployment.
- Real-time tail-follow mode, multiple-input joins, arbitrary nginx `log_format`, or approximate metrics in MVP.

## User Stories

### US-1: Analyze a local file

As an on-call SRE, I want to analyze an nginx access-log file with one command so that I can identify likely traffic sources and failing routes quickly.

Priority: P0

Acceptance criteria:

- [ ] A readable supported log exits 0 and displays all four required reports.
- [ ] Top-IP and error-URL lists contain at most 10 rows with deterministic tie ordering.
- [ ] The process reads incrementally and does not load the entire file.

### US-2: Pipe logs through stdin

As a platform engineer, I want to pipe log records into the CLI so that I can compose it with local shell tools without temporary files.

Priority: P0

Acceptance criteria:

- [ ] Omitting `INPUT` or passing `-` consumes stdin.
- [ ] The same records produce semantically identical results from stdin and a file.
- [ ] Input failures leave stdout empty and write a diagnostic to stderr.

### US-3: Locate error-heavy URLs

As a service owner, I want URLs ranked by 4xx/5xx count so that I can focus remediation on the largest error sources.

Priority: P0

Acceptance criteria:

- [ ] Only statuses 400–599 increment error-URL counts.
- [ ] Query strings remain part of the logged target.
- [ ] Results sort by count descending, then URL ascending.

### US-4: Understand hourly traffic shape

As an SRE, I want every hour’s request percentage so that I can see when traffic was concentrated.

Priority: P0

Acceptance criteria:

- [ ] Output contains exactly 24 hour buckets from `00` through `23`.
- [ ] Each percentage uses `100 × hourly_request_count / total_valid_requests`.
- [ ] Percentages are rounded to two decimals only when rendered.
- [ ] Buckets use the hour and offset written in the log without host-time conversion.

### US-5: Measure User-Agent diversity safely

As an incident responder, I want the exact share of unique User-Agents so that I can gauge client diversity without receiving a silent estimate.

Priority: P0

Acceptance criteria:

- [ ] Output includes unique count, valid-request count, and percentage share.
- [ ] Missing User-Agent values normalize to one documented sentinel.
- [ ] Exceeding the configured cardinality cap stops processing with exit code 4 and no partial stdout.

### US-6: Consume structured results

As an automation author, I want JSON or CSV output so that I can feed results into pipeline steps reliably.

Priority: P0

Acceptance criteria:

- [ ] `--json` matches the schema in `PROJECT_ARCHITECTURE.md` and contains no ANSI escapes.
- [ ] `--csv` contains the documented header and long-form rows with no ANSI escapes.
- [ ] `--json` and `--csv` are mutually exclusive and conflict exits 2.
- [ ] Structured and terminal modes expose the same counts and percentages.

### US-7: Diagnose imperfect logs

As an operator, I want malformed records counted and skipped so that a few corrupt lines do not erase a useful analysis.

Priority: P0

Acceptance criteria:

- [ ] Mixed valid/malformed input exits 0, reports the malformed count, and calculates metrics only from valid records.
- [ ] Input with zero valid records exits 3 and emits no report on stdout.
- [ ] Diagnostics do not echo full raw log records.

### US-8: Read compressed archives directly

As an operator, I want transparent gzip input so that I can analyze rotated logs without a separate decompression process.

Priority: P1

Acceptance criteria:

- [ ] Deferred until all P0 acceptance criteria and the performance gate pass.
- [ ] When implemented, gzip and equivalent plain input produce the same metrics.

### US-9: Supply a custom nginx format

As an advanced nginx administrator, I want to describe a custom `log_format` so that nonstandard logs can be analyzed.

Priority: P2

Acceptance criteria:

- [ ] Not part of the one-weekend MVP.
- [ ] Any later design must preserve streaming and explicit validation.

## Functional Requirements

### P0 — Must

| ID | Requirement |
|---|---|
| FR-1 | Accept one file path, `-`, or omitted input for stdin. |
| FR-2 | Parse supported nginx common and combined lines; skip and count malformed lines. |
| FR-3 | Count valid requests by client IP and return the deterministic top 10. |
| FR-4 | Count request targets for statuses 400–599 and return the deterministic top 10. |
| FR-5 | Return 24 hourly count/percentage buckets using `100 × hourly_request_count / total_valid_requests`. |
| FR-6 | Return exact User-Agent cardinality and `100 × unique_user_agent_count / total_valid_requests`. |
| FR-7 | Render Rich terminal text by default and strict JSON/CSV on request. |
| FR-8 | Enforce mutually exclusive output flags and exit codes `0/1/2/3/4`. |
| FR-9 | Abort with code 4 before returning partial output when the User-Agent cap is exceeded. |

### P1 — Should

| ID | Requirement |
|---|---|
| FR-10 | Transparently read gzip-compressed file input. |

### P2 — Could

| ID | Requirement |
|---|---|
| FR-11 | Parse a safely specified custom nginx log format. |
| FR-12 | Offer opt-in approximate cardinality as a separately labeled metric and contract. |

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 | Representative 1 GB log completes in <30 seconds | Recorded benchmark on defined reference laptop |
| NFR-2 | Memory is independent of line count except exact distinct IP/URL/User-Agent keys | Peak RSS benchmark plus source review |
| NFR-3 | Python 3.11 compatibility | CI/test environment and clean install smoke test |
| NFR-4 | No network access or persistent application data | Dependency/source inspection and runtime test |
| NFR-5 | Deterministic output for identical input/options | Repeated golden tests |
| NFR-6 | Untrusted fields cannot inject terminal markup/control behavior | Escaping tests with adversarial fixtures |

## Output and Error Contract

`PROJECT_ARCHITECTURE.md` owns the canonical command, JSON/CSV shapes, and full exit-code table. In summary: 0 success, 1 input I/O/decoding failure, 2 usage error, 3 no valid records, and 4 unique-cardinality exhaustion. Nonzero exits produce no partial stdout.

## Dependencies and Assumptions

- Python 3.11 is present before pip installation.
- Logs are plain text in supported common/combined format for MVP.
- Laptop performance is measured against a named reference machine and deterministic corpus.
- Logged timestamps, not machine timezone, define hourly buckets.

## Release Acceptance

The MVP releases only when every P0 acceptance criterion passes, the package installs through pip, the full `0/1/2/3/4` CLI contract is covered, structured outputs validate, and the documented 1 GB benchmark completes under 30 seconds. P1/P2 items cannot delay release.

## Kill Criteria

Pause and re-evaluate if measured optimized performance remains at or above 30 seconds, exact tracking cannot be made safe under the documented cardinality policy, or common/combined parsing is not deterministic. Do not add infrastructure to obscure a failed local CLI premise.

