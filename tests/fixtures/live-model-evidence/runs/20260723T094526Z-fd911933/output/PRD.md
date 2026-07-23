# Product Requirements Document: Nginx Stream Analytics CLI

## 1. Product Summary

Nginx Stream Analytics CLI is a local Python 3.11 tool for DevOps and SRE engineers. It reads a conventional nginx combined access log from a file or stdin, processes it without loading the whole file, and reports traffic/error distributions in terminal text, JSON, or CSV. It does not authenticate users, retain data, expose a server, or require infrastructure.

## 2. Problem and Outcome

During incident triage and ad hoc analysis, engineers often need a small set of answers from a large log but do not want to deploy an analytics stack or maintain fragile shell parsing. The product succeeds when one installable command returns trustworthy, composable results locally and processes a representative 1 GB file in under 30 seconds on a documented laptop.

## 3. Goals

- Provide the four required reports from valid combined-format nginx logs.
- Support interactive humans and shell pipelines without separate services.
- Preserve privacy through local, stateless operation.
- Define deterministic, testable output and error contracts.
- Deliver a releasable MVP in one weekend at $0 infrastructure/software cost.

## 4. Non-Goals

- Authentication or multi-user access control.
- Database, history, saved reports, dashboards, or search.
- HTTP API, daemon, web UI, server, cloud, containers, or Kubernetes.
- Live file-following/tailing in MVP; streaming means incremental processing of stdin or a file to EOF.
- Arbitrary custom nginx `log_format` parsing in MVP.
- GeoIP, bots, latency percentiles, bandwidth totals, or approximate counts in MVP.

## User Stories

### US-1: Analyze traffic sources

As an on-call SRE, I want the ten client IPs with the most requests so that I can identify dominant sources during an incident.

Priority: P0

Acceptance criteria:

- [ ] At most ten entries are returned with request counts.
- [ ] Results sort by descending count and then ascending IP token for ties.
- [ ] IPv4 and IPv6 fixture values are handled.
- [ ] Fewer than ten distinct IPs produces no padding rows.

### US-2: Find error hotspots

As an on-call SRE, I want the ten request URLs producing the most 4xx and 5xx responses so that I can prioritize broken or failing routes.

Priority: P0

Acceptance criteria:

- [ ] Only status codes 400–599 inclusive contribute.
- [ ] At most ten full logged request targets and counts are returned.
- [ ] Results sort by descending count and then ascending URL for ties.
- [ ] Successful and redirect responses do not affect this ranking.

### US-3: See hourly traffic shape

As a platform engineer, I want requests grouped into 24 hourly buckets so that I can spot traffic peaks and gaps.

Priority: P0

Acceptance criteria:

- [ ] Every hour `00` through `23` is emitted in order, including zero-count hours.
- [ ] Each record uses its parsed timestamp and numeric timezone offset without host-timezone conversion.
- [ ] The sum of hourly counts equals the count of valid requests.

### US-4: Measure User-Agent diversity

As a DevOps engineer, I want the exact share of distinct User-Agent values among valid requests so that I can quickly assess client diversity.

Priority: P0

Acceptance criteria:

- [ ] Unique count is exact and treats the complete unescaped field as the identity.
- [ ] Share equals `unique_count / total_valid_requests` and is between 0 and 1.
- [ ] Empty input reports unique count `0` and share `0.0`.

### US-5: Read an interactive report

As an engineer working in a terminal, I want readable colored tables by default so that I can scan results quickly.

Priority: P0

Acceptance criteria:

- [ ] Default TTY output labels all four required reports and summary counts.
- [ ] Log-derived strings cannot inject Rich markup.
- [ ] Redirection, `--no-color`, or `NO_COLOR` removes ANSI escapes.

### US-6: Compose machine output

As an automation engineer, I want versioned JSON and normalized CSV so that I can feed analysis into pipelines.

Priority: P0

Acceptance criteria:

- [ ] `--json` produces exactly one valid schema-versioned JSON document on stdout.
- [ ] `--csv` produces one valid CSV table containing all report sections.
- [ ] JSON and CSV contain no ANSI sequences and diagnostics never contaminate stdout.
- [ ] Supplying both flags is rejected with usage exit code 2.

### US-7: Understand bad input

As an SRE, I want malformed-line counts and an optional strict mode so that I know whether the report is complete enough to trust.

Priority: P1

Acceptance criteria:

- [ ] Lenient mode skips malformed lines, reports their count, and keeps diagnostics bounded.
- [ ] `--strict` stops on the first malformed line and exits 2.
- [ ] Expected errors do not expose a traceback or echo complete sensitive lines by default.

### US-8: Support custom formats later

As a platform engineer with a custom nginx `log_format`, I want a field mapping option so that I can analyze non-combined logs.

Priority: P2

Acceptance criteria:

- [ ] Deferred until the combined-format MVP and benchmark are accepted.
- [ ] Any design retains deterministic semantics for the four required reports.

## 6. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Read UTF-8 text incrementally from one file path or stdin (`-`/omitted input); never call a whole-file read API. |
| FR-2 | P0 | Parse the supported conventional nginx combined format into typed records, including IPv6, numeric timezone offsets, quoted values, and request fields. |
| FR-3 | P0 | Count valid requests per IP and return deterministic top 10. |
| FR-4 | P0 | Count request targets whose statuses are 400–599 and return deterministic top 10. |
| FR-5 | P0 | Produce all 24 hourly counts plus exact distinct User-Agent count and share. |
| FR-6 | P0 | Render Rich text by default with safe TTY/color behavior. |
| FR-7 | P0 | Render the architecture's JSON schema version 1 or normalized CSV schema version 1 when selected. |
| FR-8 | P1 | Support lenient malformed-line accounting and `--strict` first-error failure. |
| FR-9 | P2 | Support explicitly configured custom nginx log formats after MVP. |

## 7. Non-Functional Requirements

| ID | Requirement | Evidence |
|---|---|---|
| NFR-1 Performance | Process the deterministic typical-cardinality 1 GiB valid log in <30.0 seconds and <512 MiB peak RSS on documented laptop hardware. | `/usr/bin/time -v` record with CPU, OS, Python, file hash/size, cardinalities, cache policy, elapsed time, peak RSS |
| NFR-2 Streaming | Peak memory must not scale with total line count when key cardinality is held constant. | Compare peak RSS on same-cardinality 100 MiB and 1 GiB fixtures; document ratio and overhead |
| NFR-3 Determinism | Equal input and version produce byte-stable JSON/CSV output. | Golden fixture comparisons across repeated runs |
| NFR-4 Safety/privacy | No network access or persistence; untrusted values cannot become terminal markup or unsafe spreadsheet formulas. | Static review plus adversarial renderer tests |
| NFR-5 Compatibility | Package installs and runs on CPython 3.11 through pip. | Clean-venv wheel installation and CLI smoke test |
| NFR-6 Quality | Parser and aggregation modules achieve at least 90% branch coverage; full suite passes. | Coverage report and test log |
| NFR-7 Resource envelope | Process the specified 1 GiB high-cardinality profile (250k IPs, 250k error URLs, 1M UAs) without uncontrolled OOM and below 2 GiB peak RSS; report time separately. | Generator parameters plus `/usr/bin/time -v` evidence and average key lengths |

## 8. Output Contract

- Stdout contains only the selected report format.
- Stderr contains bounded diagnostics and expected error messages.
- Exit `0`: successful report, including empty input and lenient malformed skips.
- Exit `2`: invalid CLI use, unreadable input, decoding failure, or strict parse failure.
- Exit `1`: unexpected internal error.
- Machine schemas and sorting are defined in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) section 7 and require an explicit schema-version change if broken.

## 9. Analytics Definitions

- **Top IPs:** request count per parsed client IP token over valid records.
- **Top error URLs:** count per complete logged request target where status is 400–599 inclusive.
- **Hourly distribution:** request count by `timestamp.hour` from each record's parsed numeric offset, with 24 fixed buckets.
- **Unique User-Agent share:** exact distinct complete User-Agent values divided by the number of valid records; `0.0` on empty input.
- **Malformed line:** any nonblank input line that is invalid UTF-8 or does not satisfy the supported grammar or field constraints.

## 10. Dependencies and Constraints

- Python 3.11, Click, Rich, and standard-library dataclasses.
- pip-installable wheel/source distribution.
- $0 cash/infrastructure budget and one-weekend delivery.
- Single local process; no authentication, database, HTTP API, server, cloud, Docker requirement, or Kubernetes.

## 11. Release Acceptance

The MVP is accepted only when every P0 user-story criterion passes, required machine outputs match golden files, clean installation succeeds, and current benchmark evidence meets NFR-1. P1 malformed-input behavior should ship in the weekend target; if deferred, it must be explicitly recorded and must not weaken valid-input correctness.

## 12. Kill Criteria

- The correct implementation remains at or above 30.0 seconds for 1 GiB after profiling on the agreed baseline.
- The typical profile exceeds 512 MiB peak RSS, or the specified high-cardinality profile exceeds 2 GiB/uncontrollably OOMs, and no one-weekend mitigation preserves exact semantics.
- Real combined-format fixtures show the parser contract is too narrow to be operationally useful within weekend scope.
- Stable JSON and CSV contracts cannot represent all four reports without incompatible ambiguity.

Any kill result needs reproducible commands and recorded evidence; a hunch is insufficient.

## 13. Traceability

Priorities derive from [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md). Module, security, data, and schema decisions are authoritative in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md). Work order and verification commands are in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
