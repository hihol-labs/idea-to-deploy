# Product Requirements Document: Nginx Log Lens

## 1. Summary

Nginx Log Lens lets DevOps and SRE engineers turn a local nginx access-log
stream into four actionable summaries with one command. It is a Python 3.11,
pip-installable CLI with colored terminal output by default and stable JSON/CSV
formats for pipelines. It is stateless and local: no authentication, database,
HTTP API, server, cloud, or Kubernetes.

## 2. Problem and Outcome

During an incident or capacity check, an engineer often needs to know who is
sending traffic, which routes are failing, when traffic occurs, and how diverse
the client population is. Shell one-liners are fast to start but fragile around
nginx quoting, status filters, timestamps, and repeated automation. Full log
platforms solve a much larger operational problem.

The desired outcome is a correct, repeatable answer from a file or stdin in one
local process, with 1 GB processed in under 30 seconds on a declared reference
laptop and no entire-file materialization.

## 3. Goals and Non-Goals

### Goals

- Parse nginx common and combined access-log records in a stream.
- Report top-10 IPs, top-10 4xx/5xx URLs, 24 hourly percentage buckets, and
  distinct User-Agent share.
- Offer human-friendly Rich output and pipeline-safe JSON/CSV.
- Provide deterministic ordering, explicit malformed-data behavior, and public
  exit codes `0/1/2/3/4`.
- Install through pip on Python 3.11 for $0.

### Non-Goals

- Custom nginx `log_format` configuration in MVP.
- Authentication, users, permissions beyond the local OS user, or telemetry.
- Database, saved history, HTTP API, server, dashboard, cloud, or Kubernetes.
- Remote log collection, SSH, live file following, log rotation coordination,
  or compressed-file detection.
- Approximate cardinality. If exact tracking cannot continue, the process fails
  explicitly instead of returning an estimate.

## User Stories

### US-1 — Analyze a local incident log

As an on-call SRE, I want to analyze a local nginx access log with one command,
so that I can identify traffic and error concentration during an incident.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `nginx-log-lens analyze access.log` reads the file line by line and exits `0` when at least one valid record is present.
- [ ] The report contains at most 10 client IPs ordered by count descending, then IP ascending for ties.
- [ ] The report contains at most 10 request targets with statuses 400–599, ordered by count descending, then URL ascending for ties.
- [ ] The implementation does not call whole-input `read()`/`readlines()` or retain all parsed records.

### US-2 — Pipe logs without a temporary file

As a platform engineer, I want the analyzer to read stdin, so that I can compose
it with `ssh`, `tail`, or decompression commands without new product integrations.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Omitting `INPUT` or passing `-` consumes stdin.
- [ ] The application never closes stdin.
- [ ] A valid piped stream produces the same summary as the same bytes in a file.

### US-3 — Understand hourly traffic

As an SRE, I want every local log hour expressed as a percentage of valid
requests, so that I can see temporal concentration without calculating it.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Output includes all hours `00` through `23`, including zero-count buckets.
- [ ] Each value uses exactly `100 × hourly_request_count / total_valid_requests`.
- [ ] The request timestamp's parsed timezone is retained; records are not silently converted to another zone.
- [ ] Raw counts accompany percentages so rounding is auditable.

### US-4 — Measure client diversity exactly

As an SRE, I want the share of distinct User-Agent values, so that I can judge
whether requests come from a narrow or diverse client population.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] The value is `100 × distinct_non_missing_user_agent_count / total_valid_requests`.
- [ ] Repeated User-Agent strings count once and missing `-` values count zero.
- [ ] When a new value would exceed `--max-unique-user-agents`, no partial report is written and the command exits `4`.

### US-5 — Automate analysis in pipelines

As a platform engineer, I want JSON and CSV outputs with stable schemas, so that
I can consume results without scraping colored terminal text.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `--json` writes one parseable JSON object and nothing else to stdout.
- [ ] `--csv` writes one parseable CSV header and the documented record types.
- [ ] JSON and CSV metric values equal the default report's underlying summary.
- [ ] `--json --csv` is rejected as a usage error with exit `2`.
- [ ] Machine output contains no ANSI escape codes, progress messages, or diagnostics.

### US-6 — Detect corrupt or unsupported logs

As an operator, I want visible and scriptable malformed-line handling, so that I
do not mistake a biased partial analysis for a complete one.

**Priority:** P1 (Should)

**Acceptance criteria:**

- [ ] Default mode skips malformed records, reports the rejected count on stderr, and can succeed if at least one line is valid.
- [ ] `--strict` stops at the first malformed line and exits `3`.
- [ ] A stream containing no valid request records exits `3`.
- [ ] Diagnostics do not reproduce a complete potentially sensitive log line.

### US-7 — Install and inspect the command quickly

As a developer/operator, I want a standard pip package and useful help, so that
I can begin without operating project-specific infrastructure.

**Priority:** P1 (Should)

**Acceptance criteria:**

- [ ] A clean Python 3.11 virtual environment can install the built wheel.
- [ ] `nginx-log-lens --help` and `--version` exit `0`.
- [ ] No database, network service, Docker, cloud, or Kubernetes is needed.

### US-8 — Analyze gzip input directly

As an operator, I want transparent gzip support, so that I can skip shell
decompression.

**Priority:** P2 (Could)

This is deferred; MVP users can pipe `gzip -dc` into stdin.

## 5. Functional Requirements

### P0 — Must

| ID | Requirement |
|---|---|
| FR-01 | Accept one optional file path; omission or `-` selects stdin |
| FR-02 | Parse the defined nginx common/combined grammar and timezone-aware timestamp |
| FR-03 | Count all valid requests by client IP and return deterministic top 10 |
| FR-04 | Count request targets for status 400–599 and return deterministic top 10 |
| FR-05 | Emit 24 hourly buckets using `100 × hourly_request_count / total_valid_requests` |
| FR-06 | Compute exact distinct non-missing User-Agent count and its percentage of valid requests |
| FR-07 | Abort without a report and exit `4` on exact User-Agent cardinality exhaustion |
| FR-08 | Render a colored Rich report by default, with non-color fallback |
| FR-09 | Render stable JSON or CSV when exactly one corresponding option is supplied |
| FR-10 | Count total input, valid requests, and invalid lines |
| FR-11 | Implement public exit codes `0/1/2/3/4` exactly as specified |

### P1 — Should

| ID | Requirement |
|---|---|
| FR-12 | Support `--strict` first-error termination |
| FR-13 | Enforce a line-length limit before parsing |
| FR-14 | Provide package version and complete CLI help |

### P2 — Could

| ID | Requirement |
|---|---|
| FR-15 | Open gzip files directly after MVP |
| FR-16 | Allow a configurable top-N after preserving top-10 default compatibility |

## 6. Output Contract

The canonical fields are `total_lines`, `total_valid_requests`, `invalid_lines`,
ranked IPs, ranked error URLs, 24 hourly count/percentage pairs,
`distinct_user_agents`, and `unique_user_agent_share`. One `AnalysisSummary`
supplies all renderers. Tie-breaking, schema keys, CSV header, percentage
precision, stdout/stderr separation, and encoding are defined under
`PROJECT_ARCHITECTURE.md` → `CLI Interface`.

Default terminal output may adapt to terminal width but must retain all metric
values and labels. Machine formats are stable for schema version `1`.

## 7. Exit-Code Contract

| Code | Required meaning |
|---:|---|
| `0` | Successful analysis, help, or version output |
| `1` | Input/output or unexpected operational failure |
| `2` | Command-line usage error |
| `3` | Log-data error: strict parse failure or zero valid records |
| `4` | Unique-cardinality exhaustion |

This `0/1/2/3/4` contract is normative and must appear unchanged in every
implementation guide and every end-to-end test matrix.

## 8. Non-Functional Requirements

| ID | Requirement | Evidence |
|---|---|---|
| NFR-01 | Process a reproducible 1 GB fixture in under 30 seconds on a named laptop | Benchmark command plus environment, fixture, elapsed time, and peak RSS record |
| NFR-02 | Never materialize the whole input or all records | Static review plus peak-RSS scaling test |
| NFR-03 | Run on CPython 3.11 and install through pip | Clean-venv wheel smoke test |
| NFR-04 | Deterministic results for identical bytes and options | Repeated-output digest comparison and tie fixtures |
| NFR-05 | Do not transmit or persist log contents | Dependency/network review and architecture inspection |
| NFR-06 | At least 90% line coverage with edge and error paths represented | Coverage report and test inventory |
| NFR-07 | Keep runtime dependencies to Click and Rich plus standard library/dataclasses | Locked metadata inspection |

## 9. Analytics Definitions and Edge Cases

- `total_valid_requests` is the denominator for both percentages. A malformed
  line never enters any metric.
- A status of exactly 400 or 599 is an error; 399 and 600 are not accepted into
  the error-URL metric (600 is outside the supported status invariant).
- The raw request target, including query string when present, is the URL key;
  normalization is out of scope so no semantics are silently changed.
- Common-format lines have no User-Agent and contribute to the denominator but
  not the distinct User-Agent numerator.
- Empty input, or input with only malformed lines, is a log-data error (`3`),
  so percentages never divide by zero.
- Equal counts use lexicographic key order to ensure deterministic top-10 rows.

## 10. Release Acceptance

The MVP is accepted only when:

1. Golden common/combined fixtures produce correct values for all four metrics.
2. File and stdin execution match.
3. Rich, JSON, and CSV outputs originate from equivalent summary values.
4. Tests cover exit codes `0`, `1`, `2`, `3`, and `4` without omission or remapping.
5. A clean Python 3.11 environment installs the built wheel.
6. The documented 1 GB benchmark passes under 30 seconds on the declared laptop.
7. There is no product code for authentication, storage, HTTP, server, cloud,
   or Kubernetes.

## 11. Kill Criteria

Pause and redesign rather than ship if any of the following remains true after
the one-weekend timebox:

- Supported common/combined fixtures cannot be parsed without ambiguous field extraction.
- Machine outputs disagree with the canonical summary or are contaminated by diagnostics.
- The complete exit-code contract cannot be made deterministic.
- A bounded-cardinality 1 GB reference fixture cannot run under 30 seconds on the target laptop.
- Exact analytics require a database, daemon, native extension, or paid service to meet MVP requirements.

Feature priority originates in `STRATEGIC_PLAN.md`; technical decisions are in
`PROJECT_ARCHITECTURE.md`; implementation evidence is planned in
`IMPLEMENTATION_PLAN.md`.
