# Product Requirements Document: nginx-log-insights

## Product Summary

`nginx-log-insights` is a local Python 3.11 command-line tool that converts nginx combined access logs into four incident-oriented summaries. It serves DevOps/SRE users who want an immediate answer without deploying a storage or visualization stack.

## Problem Statement

During incidents, useful nginx facts are trapped in large text files. One-off shell pipelines are fragile around quoting, malformed records, deterministic ordering, and multiple simultaneous metrics. Full observability stacks solve a wider problem but require time, services, storage, and budget. The product must offer a trustworthy middle ground: a fast, stateless, local command with a stable automation contract.

## Goals

- Process a 1 GB nginx combined access log in under 30 seconds on a documented laptop.
- Compute all four approved metrics in one streaming pass.
- Provide clear colored terminal output by default and deterministic JSON/CSV for pipelines.
- Bound exact high-cardinality state and fail explicitly rather than silently approximating.
- Install through pip and require no external service or configuration.

## Non-Goals

- Authentication or multi-user access control.
- A database, retained history, indexing, or cross-run state.
- An HTTP API, UI, server, daemon, cloud integration, or Kubernetes deployment.
- General-purpose log search, alerting, dashboards, or nginx configuration management.
- Automatic format inference or approximate metrics in the MVP.

## User Stories

### US-1: Stream input safely

As an on-call engineer, I want to analyze one or more log files or stdin without loading them into memory, so that I can inspect large and live-produced inputs locally.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] With one or more readable combined-format files, every line is visited once and all files contribute to one report.
- [ ] With no path or with the single path `-`, input is read from stdin.
- [ ] The implementation does not seek or retain raw records and demonstrates bounded raw-input memory on the 1 GB benchmark.
- [ ] Malformed lines are skipped, counted, and excluded from metric denominators.
- [ ] Unreadable input or a run with zero valid requests exits `1` without a partial report.

### US-2: Identify highest-volume clients

As an SRE, I want the ten client IPs with the most valid requests, so that I can spot dominant or suspicious traffic sources.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] The report contains at most ten distinct IP values with exact counts.
- [ ] Results sort by count descending and IP ascending for equal counts.
- [ ] IPv4 and IPv6 input fixtures are counted without DNS lookup.
- [ ] A guarded IP structure that would exceed `--max-unique` exits `4`.

### US-3: Find failing routes

As a service owner, I want the ten request URLs producing the most 4xx/5xx responses, so that I can prioritize broken or abused routes.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Only valid records with status `400` through `599` contribute to URL counts.
- [ ] The request target, including its query string, is the URL key in MVP.
- [ ] Results contain at most ten URLs, sorted by count descending and URL ascending for ties.
- [ ] A guarded error-URL structure that would exceed `--max-unique` exits `4`.

### US-4: Understand hourly traffic shape

As an on-call engineer, I want requests distributed across all 24 log-record hours, so that I can recognize traffic concentration and quiet periods.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] The report includes hours `00` through `23`, including zero-count hours.
- [ ] Each percentage uses the exact formula `100 × hourly_request_count / total_valid_requests`.
- [ ] The hour comes from the timestamp as encoded with its log offset and is not silently normalized.
- [ ] Counts sum to `total_valid_requests`; rounding is presentation-only.

### US-5: Measure User-Agent diversity

As a platform engineer, I want the percentage share of unique User-Agent values, so that I can quickly estimate client diversity or automation concentration.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] The numerator is the exact count of distinct, non-empty User-Agent strings from valid requests.
- [ ] The percentage is `100 × unique_user_agent_count / total_valid_requests`.
- [ ] Both the count and percentage are emitted in every output mode.
- [ ] A User-Agent set that would exceed `--max-unique` exits `4` without an approximate or partial result.

### US-6: Consume human and machine outputs

As a platform engineer, I want terminal, JSON, and CSV renderings with stable process statuses, so that the same tool works interactively and in automation.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Default output is a readable Rich report, with ANSI color only when stdout is a terminal or color is explicitly enabled.
- [ ] `--json` emits one valid JSON document conforming to schema version 1.
- [ ] `--csv` emits the normalized documented header and deterministic row order.
- [ ] `--json` and `--csv` together are rejected as usage error `2`.
- [ ] Structured stdout never contains color codes, progress text, or diagnostics.
- [ ] Integration tests exercise the complete `0/1/2/3/4` application exit-code contract.

### US-7: Read gzip logs directly

As an SRE, I want to read `.gz` access logs directly, so that I can avoid a separate decompression pipeline.

Priority: **P1 (Should)**

Acceptance criteria:

- [ ] Gzip input is detected only by an explicit option or `.gz` suffix, not guessed from arbitrary streams.
- [ ] Decompression errors map to input/data failure `1`.

### US-8: Parse custom nginx formats

As a platform owner, I want to map a custom nginx log format, so that the analyzer works with installations that do not use `combined`.

Priority: **P1 (Should)**

Acceptance criteria:

- [ ] A documented format specification maps required semantic fields without executing user input.
- [ ] Missing required fields are rejected before streaming begins.

### US-9: Choose ranking depth

As an analyst, I want to choose a top-N value, so that I can inspect a wider ranked set when needed.

Priority: **P2 (Could)**

Acceptance criteria:

- [ ] A future `--top` option accepts a bounded positive integer while preserving the default of 10.

## Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept plain-text nginx combined logs from files and stdin, sequentially and in one pass. |
| FR-02 | Parse remote address, timestamp/hour, request method and target, status, and User-Agent; count malformed lines. |
| FR-03 | Produce exact top-10 IP counts with deterministic ties. |
| FR-04 | Produce exact top-10 request-target counts for statuses 400–599 with deterministic ties. |
| FR-05 | Produce all 24 hourly counts and percentages using `100 × hourly_request_count / total_valid_requests`. |
| FR-06 | Produce exact unique non-empty User-Agent count and its percentage of valid requests. |
| FR-07 | Render terminal text by default and stable JSON/CSV on mutually exclusive flags. |
| FR-08 | Enforce `--max-unique` independently for guarded IP, error-URL, and User-Agent structures. |
| FR-09 | Honor exit codes `0` success, `1` input/data, `2` usage, `3` internal, `4` unique-cardinality exhaustion. |
| FR-10 | Send reports only to stdout and diagnostics only to stderr; never emit a partial report after failure. |

### P1 — Should follow MVP

| ID | Requirement |
|---|---|
| FR-11 | Read gzip-compressed log files directly. |
| FR-12 | Support explicitly configured nginx formats after a safe mapping design is accepted. |

### P2 — Could add

| ID | Requirement |
|---|---|
| FR-13 | Allow bounded configurable top-N ranking, retaining 10 as default. |
| FR-14 | Offer an explicitly labeled approximate-cardinality mode for inputs that exceed exact-memory constraints. |

## Output Contract

The canonical field names and CLI options are defined under `PROJECT_ARCHITECTURE.md` → `## CLI Interface`. JSON has `schema_version: 1`; breaking field or semantic changes require a new schema version. CSV uses `schema_version,metric,rank,key,count,percentage`. Text wording may improve, but it must contain the same counts and percentages.

All metrics use valid parsed requests as their population. Top lists contain fewer than ten rows when fewer distinct values qualify. Deterministic tie-breaking makes fixture output repeatable.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | Process a reproducible 1 GB valid combined log in < 30 seconds on the documented reference laptop | Timed release benchmark with environment and peak RSS recorded |
| NFR-02 | Stream raw input with no full-file buffering | Memory-profile small and 1 GB inputs; source review of reader boundary |
| NFR-03 | Support Python 3.11 and install via pip wheel | Clean virtual-environment build/install/command smoke test |
| NFR-04 | Keep peak RSS < 512 MiB on the standard fixture | `/usr/bin/time -v` or platform-equivalent measurement |
| NFR-05 | Achieve >= 90% line coverage with all P0 branches exercised | pytest coverage report plus golden CLI tests |
| NFR-06 | Make no network calls and retain no log data after exit | Dependency/source review and network-isolated test run |
| NFR-07 | Handle untrusted log content without execution or unsafe diagnostic disclosure | Malicious fixture tests and security review |

## Dependencies and Constraints

- Python 3.11, Click, Rich, dataclasses, and standard-library modules.
- pip-installable source distribution and wheel.
- $0 cash budget and one-weekend MVP delivery.
- Local process only; no authentication, database, HTTP API, server, cloud, or Kubernetes.
- Architecture and detailed schemas are owned by `PROJECT_ARCHITECTURE.md`; implementation sequencing is owned by `IMPLEMENTATION_PLAN.md`.

## Release Acceptance

Release requires all P0 story criteria, a clean wheel install, all `0/1/2/3/4` exits under integration test, deterministic output fixtures, and a passing 1 GB performance run under the documented reference conditions. P1 and P2 omissions do not block MVP release.

## Kill Criteria

Stop or redesign the MVP rather than ship if any of these remains true after the one-weekend timebox:

- A valid 1 GB reference log cannot complete under 30 seconds after profiler-guided optimization.
- Exact aggregation cannot stay under 512 MiB on the standard fixture without violating metric semantics.
- Combined-format parsing cannot meet correctness fixtures without silently accepting ambiguous records.
- Structured outputs or `0/1/2/3/4` statuses cannot remain deterministic enough for pipelines.
- Delivery requires adding a paid service, database, server, cloud, or Kubernetes component.

The response to a kill criterion is an explicit product/architecture decision, not an undocumented requirement relaxation.
