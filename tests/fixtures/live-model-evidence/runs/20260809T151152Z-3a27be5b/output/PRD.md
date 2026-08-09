# Product Requirements Document: StreamSift

## 1. Summary

StreamSift is a local Python 3.11 CLI for DevOps/SRE engineers who need an immediate, trustworthy summary of nginx access logs without deploying an analytics stack. It streams one input, computes four fixed operational views, and writes either colored terminal text, JSON, or CSV.

This PRD is the behavioral source of truth. Architecture details live in `PROJECT_ARCHITECTURE.md`; delivery sequencing lives in `IMPLEMENTATION_PLAN.md`.

## 2. Problem and Outcome

During triage, operators often have a large nginx log but no ready dashboard. Full observability stacks take time and persistence; ad hoc shell commands are error-prone and difficult to standardize. The desired outcome is a pip-installable command that provides a deterministic answer in under 30 seconds for a representative 1 GB log on a documented laptop, never uploads or persists the log, and can be consumed by people or pipelines.

## 3. Goals and Non-Goals

### Goals

- Stream a file or stdin without retaining raw records.
- Report top 10 IPs, top 10 URLs with 4xx/5xx responses, 24 hourly percentage buckets, and unique User-Agent share.
- Make terminal output readable and pipeline formats stable.
- Handle malformed data, I/O failure, usage errors, and cardinality exhaustion predictably.
- Install through pip and run on Python 3.11 at $0 infrastructure cost.

### Non-Goals

- Authentication, accounts, authorization, or multi-tenancy.
- Database, persistent index, cache, history, or incremental resume.
- HTTP API, daemon, server, GUI, cloud service, Docker, or Kubernetes.
- Log tail-follow mode, multiple simultaneous files, arbitrary nginx format configuration, geo-IP, bot classification, or approximate cardinality in MVP.
- Replacement for a long-term observability platform.

## User Stories

### US-1 — Analyze a large local log

As an on-call SRE, I want to analyze an nginx log with one command so that I can identify concentrated clients and failures during triage.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `streamsift access.log` reads the file line by line and emits a default terminal report.
- [ ] The report contains no more than 10 IP rows ordered by request count descending, then IP ascending.
- [ ] The tool does not retain raw lines or full parsed-record collections.
- [ ] A representative 1 GB supported-format input completes in under 30 seconds on the documented reference laptop.

### US-2 — Find failing request targets

As an application operator, I want the most frequent URLs returning client or server errors so that I can prioritize investigation.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Only statuses 400 through 599 inclusive contribute to `top_error_urls`.
- [ ] At most 10 targets are emitted, ordered by error count descending, then complete request target ascending.
- [ ] The count includes both 4xx and 5xx responses and excludes all other statuses.
- [ ] The query string remains part of the target for MVP counting.

### US-3 — Understand traffic by hour

As an SRE, I want hourly request percentages so that I can see temporal concentration at a glance.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Output contains buckets `00` through `23`, including zero-count hours.
- [ ] Every percentage uses `100 × hourly_request_count / total_valid_requests` and is serialized to two decimal places.
- [ ] The sum of hourly counts equals `total_valid_requests`.
- [ ] Hour is interpreted from the hour and numeric offset written in each log record.

### US-4 — Measure User-Agent diversity

As a DevOps engineer, I want the share of unique User-Agents so that I can quickly gauge client diversity and possible automation.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] The numerator is the count of distinct nonempty User-Agent strings; `-` is excluded.
- [ ] The denominator is `total_valid_requests`.
- [ ] The output includes both exact distinct count and percentage rounded to two decimals.
- [ ] A repeated User-Agent increments the request denominator but not the distinct numerator.

### US-5 — Consume results in automation

As a platform engineer, I want JSON or CSV output so that I can feed the summary into scripts and CI jobs.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `--json` emits exactly one valid JSON document conforming to schema version 1.
- [ ] `--csv` emits the normalized `metric,dimension,count,percentage` schema.
- [ ] The two options are mutually exclusive and misuse exits `2`.
- [ ] Results go to stdout; warnings and errors go only to stderr; pipeline modes never contain ANSI escapes.

### US-6 — Fail safely on hostile cardinality

As an operator, I want a bounded-memory guard so that a high-cardinality log cannot consume the machine uncontrollably.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `--max-cardinality` accepts a positive integer and governs new distinct IP, error-URL, and User-Agent insertions.
- [ ] The limit is checked before insertion and never yields a partial success payload.
- [ ] Exhaustion writes an actionable stderr message and exits `4`.
- [ ] Invalid limit syntax/value is a CLI usage error and exits `2`.

### US-7 — Control malformed-data handling

As an incident responder, I want tolerant and strict modes so that I can choose between partial visibility and fail-fast validation.

**Priority:** P1 (Should)

**Acceptance criteria:**

- [ ] Default mode skips malformed nonblank lines and reports `malformed_lines`.
- [ ] `--strict` stops at the first malformed nonblank line and exits `3` without a results payload.
- [ ] Input with zero valid requests exits `3`.

### US-8 — Read compressed logs directly

As an operator, I want direct gzip input so that I do not need a separate decompression pipeline.

**Priority:** P1 (Should; post-MVP)

**Acceptance criteria:**

- [ ] A future explicitly selected gzip option streams decompressed text without extracting a file.
- [ ] Corrupt compressed input maps to runtime input failure `1`.

### US-9 — Choose a different ranking size

As an analyst, I want a configurable top-N value so that I can broaden or narrow results.

**Priority:** P2 (Could)

**Acceptance criteria:**

- [ ] A future positive option changes both ranked lists consistently.
- [ ] The default remains 10 and output schemas remain compatible.

## 5. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Accept one optional input path; missing path or `-` means stdin |
| FR-2 | P0 | Parse the supported nginx combined-log grammar into typed records |
| FR-3 | P0 | Update all metric state in one traversal of valid records |
| FR-4 | P0 | Rank top IPs and error URLs deterministically, capped at 10 |
| FR-5 | P0 | Emit 24 hourly buckets using the specified percentage formula |
| FR-6 | P0 | Emit exact distinct User-Agent count and share |
| FR-7 | P0 | Select exactly one of terminal, JSON, or CSV renderers |
| FR-8 | P0 | Enforce unique-cardinality limit before new-key insertion |
| FR-9 | P0 | Implement the complete exit-code contract `0/1/2/3/4` |
| FR-10 | P1 | Support tolerant default parsing and `--strict` fail-fast mode |
| FR-11 | P1 | Stream gzip input after MVP if the performance gate remains satisfied |
| FR-12 | P2 | Permit configurable top-N without schema breakage |

## 6. Metric Definitions

| Metric | Definition |
|---|---|
| Top 10 IPs | Count every valid request by exact parsed client IP; sort count descending, IP ascending |
| Top 10 error URLs | Count exact request targets only when status is 400–599; sort count descending, target ascending |
| Hourly request distribution | For each local log-record hour `h`, calculate `100 × hourly_request_count / total_valid_requests`; emit all 24 hours |
| Unique User-Agent share | `100 × distinct_nonempty_user_agent_count / total_valid_requests`; also emit the exact distinct count |

Percentages are computed from integer state after streaming and rounded to two decimal places only for output. Rankings and counts never depend on locale.

## 7. Input, Output, and Exit Contract

Input and renderer schemas are normative in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`.

| Exit | Contract |
|---:|---|
| `0` | Successful analysis with at least one valid request and complete output |
| `1` | Input/output runtime failure |
| `2` | CLI usage or option-validation error |
| `3` | Log-data failure: strict malformed record or no valid requests |
| `4` | Unique-cardinality exhaustion |

No failure exit may emit a partial JSON/CSV document as if it were successful.

## 8. Non-Functional Requirements

- **Performance:** representative 1 GB supported-format log in under 30 seconds on a recorded laptop configuration.
- **Memory:** no growth proportional to total line count; state is bounded by the configured aggregate distinct-cardinality cap.
- **Compatibility:** Python 3.11; pip wheel/sdist; Linux and macOS are primary MVP environments.
- **Privacy:** no telemetry, networking, persistence, or log-content exfiltration.
- **Safety:** treat every field as untrusted display data; escape Rich markup/control sequences and serialize through standard JSON/CSV libraries.
- **Testability:** pure parser/aggregation functions, deterministic sorting, golden CLI fixtures, opt-in benchmark.
- **Usability:** default color only when stdout is a TTY; help describes input, formats, strictness, cardinality, and exits.

## 9. Analytics and Telemetry

There is no product telemetry. Release metrics are collected only from local automated tests and manually invoked benchmarks; no log data or usage event leaves the machine.

## 10. Dependencies and Assumptions

- Users have Python 3.11 and pip/pipx-compatible installation.
- Input follows the documented combined grammar; custom nginx `log_format` is not inferred.
- The performance target is evaluated against representative line lengths and cardinalities, not a trivial repeated line.
- Click and Rich remain open-source and compatible with Python 3.11.

## 11. Release Criteria

- Every P0 acceptance criterion passes.
- JSON and CSV golden outputs and all five exit-code paths pass integration tests.
- Performance and peak-memory evidence satisfy the stated gates on the reference laptop.
- Packaging installs in a clean Python 3.11 environment.
- User-facing help and planning documents agree on semantics.

## 12. Kill Criteria

Stop or re-scope the MVP before release if, after profiling, supported-format 1 GB processing cannot meet 30 seconds on the reference laptop; if exact aggregation cannot be bounded with a clear exit `4`; if malformed data can produce misleading successful results; or if fulfilling the four metrics requires a database, HTTP service, paid dependency, or persistent upload. Gzip and configurable top-N may be cut without blocking MVP.

