# Product Requirements Document: Nginx Stream Analyzer

## 1. Purpose

Provide DevOps and SRE engineers with a fast, private, local command that turns an nginx combined access-log stream into four actionable summaries for incident triage and automation.

## 2. Goals

- Analyze a 1 GB log in under 30 seconds on a documented laptop.
- Read input once without retaining request records.
- Produce readable colored terminal output and stable JSON/CSV.
- Make malformed input, usage errors, operational failures, and unique-cardinality exhaustion distinguishable to shell automation.

## 3. Non-Goals

- Following live files indefinitely.
- Persisting, searching, correlating, or visualizing historical logs.
- Authentication, database, HTTP API, server, cloud, containers, or Kubernetes.
- Supporting arbitrary nginx `log_format` definitions in the MVP.
- Approximate cardinality or geographically enriching client IPs.

## 4. Personas and Core Scenario

The primary persona is an on-call SRE who has a local log file or an SSH/decompression pipeline. Within one command, they need to identify heavy client IPs, failing URLs, traffic shape by hour, and User-Agent diversity, then pass the same results to an automated pipeline if necessary.

## User Stories

- As a DevOps engineer, I want to stream a file or stdin through the analyzer so that I can inspect local and piped nginx logs without copying or importing them. **Priority: P0.**
- As an on-call SRE, I want the top 10 client IPs so that I can identify likely abusive or unexpectedly active clients. **Priority: P0.**
- As an on-call SRE, I want the top 10 request URLs producing 4xx/5xx responses so that I can prioritize broken routes and upstream failures. **Priority: P0.**
- As a capacity engineer, I want each hour's request percentage so that I can see the daily traffic shape. **Priority: P0.**
- As a security-minded operator, I want the unique User-Agent count and share with an explicit cardinality limit so that client diversity is visible without risking uncontrolled memory. **Priority: P0.**
- As an automation author, I want stable JSON and CSV plus distinct exit codes so that scripts can consume results safely. **Priority: P0.**
- As an operator handling noisy logs, I want malformed lines counted or rejected immediately so that data quality is visible. **Priority: P1.**
- As an operator, I want direct gzip input and custom nginx format templates so that fewer preprocessing steps are required. **Priority: P2.**

### P0 Acceptance Criteria

#### File and stdin streaming

- [ ] An omitted `INPUT` and `INPUT=-` consume stdin; a path consumes that file.
- [ ] A non-seekable stream produces the same report as the equivalent file.
- [ ] Processing does not retain raw lines or `ParsedRequest` objects after aggregation.

#### Top client IPs

- [ ] At most 10 IP rows are emitted from all valid requests.
- [ ] Counts are descending; ties are ascending by IP string.
- [ ] IPv4 and IPv6 fixture addresses parse and aggregate independently.

#### Top error URLs

- [ ] Only statuses 400–599 contribute.
- [ ] At most 10 request-target rows are emitted, with query strings retained.
- [ ] Counts are descending; ties are ascending by request-target string.

#### Hourly distribution

- [ ] Exactly 24 ordered buckets from `00` through `23` are represented.
- [ ] Each percentage uses `100 × hourly_request_count / total_valid_requests`.
- [ ] For non-empty input, unrounded percentages total approximately 100%; empty input produces 0.0 for every bucket.

#### Unique User-Agents

- [ ] Unique count uses exact string identity for every valid request's parsed User-Agent.
- [ ] Share is `100 × unique_user_agent_count / total_valid_requests`, or 0.0 for no valid requests.
- [ ] Exceeding `--max-unique-user-agents` exits 4 and never emits a knowingly partial report.

#### Output and exit contract

- [ ] Default output uses Rich color on a capable terminal and contains all four summaries.
- [ ] `--json` emits one parseable JSON object; `--csv` emits the normalized documented schema.
- [ ] JSON/CSV output contains no ANSI sequences, and `--json --csv` is rejected with exit 2.
- [ ] Exit codes are exactly 0 success, 1 operational failure, 2 usage error, 3 malformed input, and 4 unique-cardinality exhaustion.

## 6. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept one optional path or stdin and process it incrementally to EOF |
| FR-02 | Parse the supported nginx combined format, including timestamp offset, status, target, IP, and User-Agent |
| FR-03 | Report deterministic top-10 client IPs across valid requests |
| FR-04 | Report deterministic top-10 targets among 4xx/5xx responses |
| FR-05 | Report all 24 hourly request counts and percentages |
| FR-06 | Report exact unique User-Agent count/share and enforce a configurable positive limit |
| FR-07 | Render default terminal text, JSON, or CSV according to mutually exclusive options |
| FR-08 | Write report data to stdout, diagnostics to stderr, and implement exit codes 0/1/2/3/4 |

### P1 — Should ship if P0 is stable

| ID | Requirement |
|---|---|
| FR-09 | Default to skip-and-count malformed lines, then return 3 after emitting valid results |
| FR-10 | `--fail-fast` stops at the first malformed line, emits a concise diagnostic, and returns 3 |
| FR-11 | `--no-color`, `--help`, and `--version` follow the architecture contract |

### P2 — Could follow the MVP

| ID | Requirement |
|---|---|
| FR-12 | Read gzip files directly |
| FR-13 | Accept a safe declarative subset of custom nginx log formats |
| FR-14 | Optionally exclude query strings from URL grouping |

## 7. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | 1 GB known-answer fixture completes in <30 seconds on the named reference laptop |
| NFR-02 | Peak RSS remains <=256 MiB for the benchmark fixture and default cardinality limit |
| NFR-03 | Identical input/options produce byte-stable JSON and CSV apart from an optional final newline |
| NFR-04 | No network access, telemetry, persistence, shell execution, or evaluation of log content |
| NFR-05 | Package installs on Python 3.11 through pip and exposes `nginx-stream-analyzer` |
| NFR-06 | Log-derived terminal values are treated as plain text, not Rich markup |

## 8. Detailed Business Rules

- `total_valid_requests` is the denominator for both percentage metrics.
- A valid request contributes to exactly one hour bucket and one IP count.
- A valid response contributes to an error-URL count only when status is 400–599.
- Top lists contain fewer than 10 rows when fewer distinct keys exist.
- Malformed records do not contribute to any metric.
- Timestamp hours are grouped by the numeric local hour encoded in each record; no cross-timezone normalization is performed in MVP.
- Empty input is successful with empty top lists, 24 zero hour buckets, and zero User-Agent values.

## 9. Observability and Privacy

The CLI reports total, valid, and malformed line counts in every format. It emits no telemetry and stores no data. Expected errors are concise and do not include an entire potentially sensitive log line; a line number and error category are sufficient.

## 10. Dependencies and Assumptions

- Architecture and schemas are normative in `PROJECT_ARCHITECTURE.md`.
- Work order and evidence are defined in `IMPLEMENTATION_PLAN.md`.
- Combined-format fixtures accurately represent supported nginx escaping.
- The release benchmark must name its laptop; the target cannot be claimed from synthetic reasoning alone.

## 11. Release Criteria

- All P0 acceptance criteria pass on Python 3.11.
- Wheel installation and console entry-point smoke test pass in a clean environment.
- Parser/output known-answer tests pass.
- Benchmark evidence demonstrates the 1 GB / <30 second target and memory ceiling.
- Documentation describes format limitations and all exit statuses.

## 12. Kill Criteria

Pause the release if the implementation cannot meet the performance target after profiling, produces nondeterministic pipeline output, must silently approximate a required metric, or requires persistent/network infrastructure. Reduce optional scope before changing the approved local CLI architecture.

