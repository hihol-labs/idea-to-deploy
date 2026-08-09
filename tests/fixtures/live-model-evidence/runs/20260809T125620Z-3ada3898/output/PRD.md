# Product Requirements Document: Nginx Insights CLI

## Product Definition

Nginx Insights CLI gives DevOps and SRE engineers a fast local summary of nginx combined access logs. It is a finite-stream, one-process Python 3.11 command installed with pip. It reports the four approved metric families in colored terminal text by default and supports JSON and CSV pipelines.

## Goals

- Produce exact, deterministic metrics from a file or stdin in one pass.
- Process a 1 GB representative log in under 30 seconds on the documented reference laptop.
- Require no service, credentials, persistence, network access, or paid infrastructure.
- Make human and pipeline behavior explicit enough for golden contract tests.

## Non-Goals

Authentication, databases, HTTP APIs, servers, cloud deployment, Kubernetes, dashboards, live file-following, log shipping, historical retention, arbitrary query languages, and multi-file correlation are out of scope. Custom nginx `log_format` parsing and approximate cardinality are not P0.

## User Stories

### US-1: Identify heavy client IPs

As an on-call SRE, I want the ten IPs with the most valid requests so that I can quickly spot dominant clients.

**Priority:** P0

**Acceptance criteria:**

- [ ] Counts include every valid record regardless of status.
- [ ] At most ten rows are returned, ordered by descending count then ascending IP for ties.
- [ ] IPv4 and IPv6 strings supported by the combined-log parser remain distinct keys.

### US-2: Find failing URLs

As a DevOps engineer, I want the ten request targets with the most 4xx/5xx responses so that I can focus incident investigation.

**Priority:** P0

**Acceptance criteria:**

- [ ] Status codes 400 through 599 inclusive contribute; all others do not.
- [ ] The key is the parsed request target, and counts combine 4xx and 5xx.
- [ ] Ordering is descending error count then ascending target for deterministic ties.

### US-3: See hourly traffic shape

As an SRE, I want requests grouped into 24 hourly percentage buckets so that I can recognize when load was concentrated.

**Priority:** P0

**Acceptance criteria:**

- [ ] Hours use the literal hour in each record’s timestamp without timezone conversion.
- [ ] Every hour `00`–`23` appears, including zero-count hours.
- [ ] Each percentage uses `100 × hourly_request_count / total_valid_requests`, not an unscaled fraction.

### US-4: Gauge User-Agent diversity

As a platform engineer, I want the exact share of unique nonempty User-Agent values so that I can assess client diversity.

**Priority:** P0

**Acceptance criteria:**

- [ ] The numerator is the distinct count of nonempty User-Agent values and the denominator is total valid requests.
- [ ] The displayed value is `100 × distinct_nonempty_user_agent_count / total_valid_requests`.
- [ ] Exceeding the configured exact-cardinality ceiling emits no partial report and exits with code 4.

### US-5: Use a readable terminal report

As an on-call engineer, I want a concise colored report by default so that I can scan results directly in a terminal.

**Priority:** P0

**Acceptance criteria:**

- [ ] The report includes summary counts and all four metric families.
- [ ] Color is automatically disabled when stdout is not a TTY and can be disabled explicitly.
- [ ] Log-derived strings cannot be interpreted as Rich markup.

### US-6: Feed structured automation

As a DevOps engineer, I want stable JSON and CSV modes so that I can pass results to pipeline steps without scraping terminal text.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits only valid schema-version-1 JSON on stdout.
- [ ] `--csv` emits only the fixed long-form CSV schema on stdout.
- [ ] The two flags are mutually exclusive and invalid use exits 2.

### US-7: Understand imperfect input

As an operator, I want malformed-line accounting and reliable exit codes so that I know whether a report is trustworthy.

**Priority:** P0

**Acceptance criteria:**

- [ ] Malformed lines are skipped and summarized on stderr without echoing raw lines.
- [ ] A stream containing at least one valid record may succeed even if other lines are malformed.
- [ ] The command implements the complete exit contract `0/1/2/3/4`, with code 4 reserved for unique-cardinality exhaustion.

### US-8: Read rotated gzip logs

As a DevOps engineer, I want transparent gzip input so that I can inspect common rotated files without a decompression pipeline.

**Priority:** P1

**Acceptance criteria:**

- [ ] Deferred until all P0 criteria and the 1 GB plain-text benchmark pass.
- [ ] When implemented, explicit `.gz` files produce metrics equivalent to their decompressed contents.

### US-9: Support a declared custom format

As an nginx administrator, I want to describe a custom `log_format` so that the tool can analyze installations that do not use combined format.

**Priority:** P2

**Acceptance criteria:**

- [ ] Any future design preserves the P0 combined-format default and fails closed on missing required fields.

## Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Read a finite UTF-8-with-replacement combined-log stream from one path, stdin, or `-`, line by line. |
| FR-2 | P0 | Count valid and malformed lines without retaining raw records. |
| FR-3 | P0 | Return exact top-10 client IP counts with deterministic tie order. |
| FR-4 | P0 | Return exact top-10 request targets for statuses 400–599 with deterministic tie order. |
| FR-5 | P0 | Return 24 request-count and percentage buckets using `100 × hourly_request_count / total_valid_requests`. |
| FR-6 | P0 | Return exact distinct nonempty User-Agent count and its percentage of total valid requests. |
| FR-7 | P0 | Render safe, TTY-aware Rich terminal output by default. |
| FR-8 | P0 | Render schema-version-1 JSON when `--json` is selected. |
| FR-9 | P0 | Render fixed-schema CSV when `--csv` is selected. |
| FR-10 | P0 | Enforce the `0/1/2/3/4` exit contract, where 4 means exact unique-cardinality exhaustion. |
| FR-11 | P0 | Keep data output on stdout and diagnostics on stderr. |
| FR-12 | P1 | Add transparent explicit gzip-file input after P0 acceptance. |
| FR-13 | P2 | Explore a safe declarative custom-format parser. |

## Non-Functional Requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| NFR-1 Performance | Process exactly 1,000,000,000 generated bytes in under 30 seconds on the named reference laptop. | Reproducible benchmark record with environment and exit 0 |
| NFR-2 Memory | Retain no raw lines; enforce the configurable User-Agent distinct-value ceiling. | Unit boundary tests, high-cardinality integration test, peak RSS record |
| NFR-3 Compatibility | Run on supported CPython 3.11 patch releases and install with pip. | Clean-environment build/install smoke test |
| NFR-4 Determinism | Identical input/options produce byte-stable JSON and CSV apart from no time-dependent fields. | Golden-output tests |
| NFR-5 Privacy | Perform no network requests or persistence and do not echo rejected raw lines. | Static review and integration tests |
| NFR-6 Quality | At least 90% line coverage plus focused parser, metric, CLI, and renderer tests. | Test and coverage reports |

## Output and Error Contract

The complete command, input, terminal, JSON, CSV, and exit-code definitions live under `## CLI Interface` in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) and are normative. In summary: 0 succeeds, 1 represents unexpected runtime/output failure, 2 invalid usage, 3 unreadable/no-valid input, and 4 unique-cardinality exhaustion. Machine modes never mix diagnostics or ANSI escapes into stdout.

## Prioritization Traceability

P0 maps to Must, P1 to Should, and P2 to Could in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md). Implementation follows dependency order in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), using RICE order where dependencies permit.

## Release Acceptance

- [ ] Every P0 user-story criterion passes on the frozen candidate.
- [ ] All five exit codes have end-to-end evidence, including no partial output for code 4.
- [ ] JSON and CSV match golden schemas and terminal output is safe with untrusted strings.
- [ ] A clean pip installation works on Python 3.11.
- [ ] The documented 1 GB benchmark is under 30 seconds.
- [ ] The repository’s current Verification Loop adjudication receipt accepts the exact candidate.

## Kill Criteria

Pause release and reassess if the measured Python implementation cannot meet the 1 GB/30 s target after profiling, if combined-format parsing fails representative production fixtures, or if exact aggregation routinely exhausts laptop memory below the target input size. Do not solve these failures by silently adding a database, HTTP service, cloud dependency, or approximate metric.
