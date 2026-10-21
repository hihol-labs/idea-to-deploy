# Product Requirements Document: nginx-stream-report

## 1. Product Summary

`nginx-stream-report` is a Python 3.11 command-line tool that streams a local nginx combined access log and emits four operational views without a server or persistent state: top client IPs, top error-producing URLs, hourly traffic distribution, and unique User-Agent share. Default output is colored terminal text; JSON and CSV support automation.

## 2. Problem Statement

DevOps and SRE engineers need fast answers from large access logs during incident triage and routine diagnosis. Full observability stacks are often unavailable or disproportionate, while ad hoc shell pipelines duplicate parsing work and produce inconsistent results. The product must analyze a 1 GB file in under 30 seconds on a documented laptop while remaining installable with pip and costing $0 to operate.

## 3. Goals and Non-Goals

### Goals

- Analyze supported logs in a single streaming pass.
- Produce correct, deterministic, explainable metrics.
- Work naturally with a file path and stdin.
- Offer human-readable colored output and stable JSON/CSV output.
- Fail explicitly for invalid invocation, I/O problems, unusable input, or unsafe unique cardinality.

### Non-Goals

- Authentication, authorization, a database, an HTTP API, or a server.
- Cloud, Kubernetes, hosted dashboards, log shipping, or cross-run history.
- Arbitrary nginx format autodetection in the MVP.
- Approximate unique cardinality or silent sampling.
- Replacing centralized observability for fleet-wide analysis.

## User Stories

- As a on-call SRE, I want to see the top-10 client IPs from a large nginx log so that I can identify concentrated traffic during an incident.
- As a DevOps engineer, I want to see the top-10 request URLs ranked by 4xx/5xx response count so that I can identify broken or attacked endpoints.
- As a platform engineer, I want a 24-hour request percentage distribution so that I can recognize traffic concentration by logged local hour.
- As a pipeline author, I want JSON and CSV modes with stable schemas and exit codes so that I can automate downstream checks.
- As a security-conscious operator, I want the unique User-Agent share to be exact and memory-bounded so that adversarial cardinality cannot silently degrade or exhaust my laptop.
- As an engineer using shell pipes, I want stdin to behave like file input so that I can analyze decompressed or filtered streams.

## 5. Functional Requirements

### P0 — Must Ship

#### FR-1: Input and Parsing

The CLI shall accept one file path, `-`, or omitted input for stdin. It shall parse standard nginx combined access-log records incrementally and count malformed lines without retaining input records.

Acceptance criteria:

- [ ] A supported file and the same bytes via stdin produce identical report data.
- [ ] A malformed line increments `malformed_lines` and does not affect any metric.
- [ ] An empty input or input with no valid records emits no report and exits `3`.
- [ ] An unreadable file exits `1` with a concise stderr diagnostic.

#### FR-2: Top Client IPs

The report shall include at most 10 client IPs ordered by request count descending and IP string ascending for ties.

Acceptance criteria:

- [ ] IPv4 and IPv6 source tokens in valid records are counted.
- [ ] A fixture with more than 10 IPs returns exactly the expected first 10.
- [ ] Reordering equal-count source records does not change output ordering.

#### FR-3: Top Error URLs

The report shall include at most 10 request targets ranked by the combined number of responses with status `400` through `599`. The request target includes the logged query string.

Acceptance criteria:

- [ ] Statuses 399 and 600 do not contribute; 400, 499, 500, and 599 do.
- [ ] Successful-only URLs are absent from this ranking.
- [ ] Ties use request-target string ascending.

#### FR-4: Hourly Request Distribution

The report shall include all buckets `00` through `23`. Each bucket percentage uses exactly `100 × hourly_request_count / total_valid_requests` and is rounded to two decimal places for presentation.

Acceptance criteria:

- [ ] All 24 buckets appear even when their request count is zero.
- [ ] Hour is derived from the timestamp as logged, without timezone conversion.
- [ ] Known fixtures produce expected counts and percentages using the stated formula.
- [ ] JSON percentages are numbers; text/CSV show two decimal places.

#### FR-5: Unique User-Agent Share

The report shall contain the exact number of distinct User-Agent strings and `100 × distinct_user_agent_count / total_valid_requests`, rounded to two decimal places. `"-"` is a valid literal User-Agent category.

Acceptance criteria:

- [ ] Repeated identical User-Agents count once in the numerator.
- [ ] Crossing `--max-unique-user-agents` emits no partial report and exits `4`.
- [ ] The implementation does not substitute approximation or sampling.

#### FR-6: Output Formats

Default output shall be a Rich terminal report. `--json` shall emit the schema-versioned JSON shape in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md); `--csv` shall emit its documented long-form CSV schema.

Acceptance criteria:

- [ ] `--json` output parses as exactly one JSON document.
- [ ] `--csv` output parses with the standard Python CSV reader and has the fixed header.
- [ ] JSON and CSV contain no ANSI escape sequences and no diagnostics.
- [ ] `--json --csv` exits `2`.
- [ ] Redirected default text is uncolored; `--no-color` disables color on a terminal.

#### FR-7: Complete Process Contract

The CLI shall implement the complete exit-code contract: `0` success, `1` input/runtime I/O failure, `2` usage error, `3` no valid records, and `4` unique-cardinality exhaustion.

Acceptance criteria:

- [ ] Integration tests exercise and assert each of `0/1/2/3/4`.
- [ ] Fatal diagnostics go to stderr and do not corrupt stdout machine output.

#### FR-8: Performance

The command shall process a representative 1 GB log in under 30 seconds on a documented laptop and use one sequential pass.

Acceptance criteria:

- [ ] The benchmark records fixture-generation parameters, checksum, hardware, OS, Python patch version, wall time, and peak RSS.
- [ ] The measured wall time is below 30 seconds.
- [ ] Source inspection/tests confirm the input stream is not materialized or reread.

### P1 — Should Ship Next

- Transparently read a `.gz` path while preserving the same report and exit-code contracts.
- Add a benchmark comparison across representative low/high cardinality fixtures.

### P2 — Could Ship Later

- Allow `--top N` while keeping `10` as the default.
- Support a user-supplied nginx `log_format` grammar through a separately specified interface.

## 6. Output Semantics

Top lists are deterministic. Counts are integers. Percentages are computed from all and only valid records. Malformed lines are visible in the summary but excluded from every denominator. If input produces no error responses, `top_error_urls` is empty rather than populated with zero-count URLs.

The CSV schema is intentionally long-form to represent heterogeneous report sections without multiple files. JSON includes `schema_version: 1` to allow deliberate future evolution.

## 7. Quality Attributes

| Attribute | Requirement |
|---|---|
| Performance | 1 GB in under 30 seconds on the reference laptop |
| Memory | Streaming records; explicit unique-UA ceiling and exit `4` |
| Determinism | Stable tie-breaking and fixed 24-hour ordering |
| Portability | Python 3.11; local pip installation |
| Privacy | No network access, telemetry, persistence, or content echo in default diagnostics |
| Accessibility | Color is non-semantic and suppressible; redirected output remains readable |
| Testability | Pure parser/aggregation functions and golden renderer contracts |

## 8. Release Acceptance

Release requires a clean-environment pip install, passing automated tests, an exercised `0/1/2/3/4` exit-code matrix, valid JSON/CSV golden outputs, and benchmark evidence below the performance threshold. User-facing behavior must agree across this PRD, [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), CLI help, and [README.md](README.md).

## 9. Kill Criteria

Do not ship the claimed MVP if the 1 GB target is missed after profiling, machine formats are unstable or contaminated by diagnostics, exact User-Agent cardinality is unbounded, or common supported-format logs cannot be parsed reliably. Re-scope the supported format or performance claim rather than adding prohibited infrastructure.
