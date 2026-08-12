# Product Requirements Document: nginx-insights

## Product Summary

`nginx-insights` lets DevOps/SRE engineers analyze a local nginx Common or Combined access log with one Python 3.11 command. It streams one file or stdin and reports top IPs, error-producing URL paths, hourly traffic percentages, and exact User-Agent diversity in Rich text, JSON, or CSV.

## Goals

- Produce correct, deterministic four-part diagnostics without infrastructure or retained data.
- Fit shell and automation workflows with stdin, stdout, stderr, and stable exit contracts.
- Process a documented 1 GB reference log in under 30 seconds on a laptop.
- Install through pip and deliver within one weekend at $0 cost.

## Non-Goals

- Authentication, accounts, database, retention, HTTP API, server, cloud, Docker, or Kubernetes.
- Live tailing, dashboards, alerts, IP enrichment, bot filtering, multiple input operands, gzip decoding, or custom nginx `log_format` in MVP.
- Replacing fleet-scale tools such as Elastic/Kibana.

## User Stories

### US-1: Identify busiest clients

As an on-call SRE, I want the top 10 client IPs by valid request count so that I can spot concentrated traffic.

**Priority:** P0

**Acceptance criteria:**

- [ ] Every valid Common/Combined record increments exactly one client IP.
- [ ] Output contains at most 10 IPs ordered by count descending, then IP text ascending for ties.
- [ ] Counts are identical in text, JSON, and CSV modes.

### US-2: Find failing URL paths

As a service owner, I want the top 10 URL paths returning 4xx or 5xx responses so that I can prioritize broken routes and upstream failures.

**Priority:** P0

**Acceptance criteria:**

- [ ] Only status codes 400–599 contribute.
- [ ] Query strings and fragments are removed before path aggregation.
- [ ] Output contains at most 10 paths ordered by count descending, then path ascending for ties.

### US-3: See hourly request distribution

As an SRE, I want all 24 hourly request buckets as percentages so that I can recognize traffic concentration across the day.

**Priority:** P0

**Acceptance criteria:**

- [ ] Each valid record contributes to the local wall-clock hour encoded by its nginx timestamp.
- [ ] The calculation uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] All hours `00` through `23` appear in order, including zero-count buckets.
- [ ] Percentages use total valid requests only and display to two decimal places.

### US-4: Measure User-Agent diversity safely

As a platform engineer, I want the share of distinct non-empty User-Agents so that I can estimate client diversity without unbounded failure.

**Priority:** P0

**Acceptance criteria:**

- [ ] The share is `100 × distinct_nonempty_user_agent_count / total_valid_requests`.
- [ ] Common-format records with no User-Agent remain valid but do not add a distinct value.
- [ ] A new value beyond the configured ceiling stops processing, emits no partial report, and exits 4.

### US-5: Use the report interactively

As an on-call engineer, I want readable colored terminal tables by default so that I can scan results quickly.

**Priority:** P0

**Acceptance criteria:**

- [ ] Text is the default and shows summary, both top-10 lists, 24 hourly buckets, and User-Agent share.
- [ ] Color appears only on an interactive TTY and can be disabled with `--no-color` or `NO_COLOR`.
- [ ] Untrusted log fields cannot inject Rich markup or terminal control sequences.

### US-6: Compose with pipelines

As a DevOps engineer, I want stable JSON and CSV output so that I can feed results to `jq`, spreadsheets, or CI jobs.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` matches the schema in `PROJECT_ARCHITECTURE.md` and never includes ANSI escapes.
- [ ] `--csv` emits `report,rank,key,count,percentage` followed by rows in the documented fixed order.
- [ ] `--json` and `--csv` together are rejected with exit 2.

### US-7: Diagnose imperfect inputs

As an automation author, I want malformed lines and failures to have deterministic behavior so that jobs can branch reliably.

**Priority:** P1

**Acceptance criteria:**

- [ ] Malformed/blank lines are skipped and counted when at least one valid record exists.
- [ ] An input with zero valid records exits 3 and produces no report.
- [ ] The public exit mapping is exactly `0/1/2/3/4` as defined below.

### US-8: Analyze compressed and custom formats

As a platform engineer, I want native gzip and custom `log_format` support so that fewer preprocessing steps are needed.

**Priority:** P2

**Acceptance criteria:**

- [ ] Deferred until all P0/P1 release gates pass; shell decompression is documented for MVP.

## Functional Requirements

### P0 — Must

| ID | Requirement |
|---|---|
| FR-01 | Accept one optional `INPUT` path; omitted or `-` means stdin |
| FR-02 | Parse standard nginx Common and Combined lines in a streaming pass |
| FR-03 | Count invalid lines without including them in any metric or denominator |
| FR-04 | Produce deterministic top-10 IP and 4xx/5xx normalized-path rankings |
| FR-05 | Produce 24 hourly percentages using `100 × hourly_request_count / total_valid_requests` |
| FR-06 | Produce exact distinct non-empty User-Agent count and percentage with a configured ceiling |
| FR-07 | Render TTY-aware Rich text by default and stable JSON/CSV on request |
| FR-08 | Preserve the complete `0/1/2/3/4` exit-code contract |

### P1 — Should

| ID | Requirement |
|---|---|
| FR-09 | Expose skipped-line count in every output format |
| FR-10 | Honor `--no-color` and conventional `NO_COLOR` |
| FR-11 | Build wheel and sdist and verify clean Python 3.11 installation |

### P2 — Could

| ID | Requirement |
|---|---|
| FR-12 | Read gzip files natively |
| FR-13 | Parse a user-specified nginx `log_format` template |

## CLI and Exit-Code Requirements

The canonical syntax, options, and output schemas are specified under `## CLI Interface` in `PROJECT_ARCHITECTURE.md`. The exit codes are:

| Code | Requirement |
|---:|---|
| `0` | Successful report, help, or version |
| `1` | Runtime or input I/O failure |
| `2` | Usage/configuration error |
| `3` | Zero valid records in the completed input stream |
| `4` | Unique-cardinality exhaustion; no partial report |

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | Python 3.11 and pip-installable | Clean virtual-environment smoke test |
| NFR-02 | Median processing time for the documented 1 GB fixture is under 30 seconds on the documented laptop | Performance test protocol from architecture |
| NFR-03 | Input is processed line-by-line; source lines are not retained | Code review plus memory test |
| NFR-04 | Machine formats are deterministic UTF-8 with no ANSI | Golden tests under fixed locale |
| NFR-05 | No network calls, telemetry, persistence, or log mutation | Static review and network-disabled integration test |
| NFR-06 | Parser/aggregator core has at least 90% line coverage | Coverage gate |
| NFR-07 | Errors are concise on stderr while stdout stays report/schema-only | CLI integration tests |

## Release Acceptance

Release requires all P0 stories, the complete exit-code matrix, clean pip installation, golden fixtures for Common/Combined and each renderer, the no-network/no-persistence boundary, and the 1 GB performance gate. P1 skipped-line diagnostics and packaging are included in the weekend plan because they materially reduce operational ambiguity.

## Kill Criteria

Pause and re-scope if profiling cannot bring the single-process candidate under the performance target, if supported nginx formats cannot be parsed without material ambiguity, or if exact User-Agent handling cannot fail safely at a documented ceiling. Do not silently add persistence, parallel services, or approximation to rescue the schedule.

## Traceability

| Requirement group | Architecture | Delivery evidence |
|---|---|---|
| FR-01–FR-03 | CLI Interface; Data Model and Algorithms | Plan steps 2, 3, and 7 |
| FR-04–FR-06 | Aggregation state | Plan steps 4 and 7 |
| FR-07 | Outputs | Plan steps 5, 6, and 7 |
| FR-08 | Exit codes | Plan steps 2 and 7 |
| NFR-01–NFR-07 | Packaging, Security, Performance | Plan steps 1, 7, and 8 |
