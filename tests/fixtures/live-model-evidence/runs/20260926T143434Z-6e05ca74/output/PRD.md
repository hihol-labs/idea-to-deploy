# Product Requirements Document: nginx-stream-report

## 1. Product Summary

`nginx-stream-report` is a local Python 3.11 CLI that gives DevOps/SRE engineers a fast, reproducible summary of nginx combined access logs. It processes a file or stdin in one pass and reports top client IPs, top error-producing URLs, hourly request distribution, and unique User-Agent share. The default is a colored terminal report, with JSON and CSV for automation.

## 2. Problem Statement

During incident response and routine checks, operators often need a small set of answers before a centralized log platform is available or justified. Shell one-liners are quick but inconsistent, fragile around quoting, and difficult to turn into a stable pipeline contract. Full analytics stacks are excessive for a local, one-off scan. The product fills that gap without storing or transmitting logs.

## 3. Goals and Non-Goals

### Goals

- Analyze a 1 GB representative nginx log in under 30 seconds on a documented laptop.
- Read input incrementally from one file or stdin.
- Produce exact, deterministic required metrics and stable machine formats.
- Install through pip on Python 3.11.
- Make malformed input and resource exhaustion visible through stderr and exit codes.

### Non-Goals

- Authentication, accounts, telemetry, or multi-user behavior.
- Database storage, historical browsing, HTTP APIs, servers, cloud deployment, or Kubernetes.
- Live tail/follow, multiple-file merge, dashboards, alerting, geolocation, bot detection, or arbitrary nginx format configuration in the MVP.
- Silent approximation of rankings or unique cardinality.

## User Stories

- As a SRE, I want to stream an nginx access log from a file or stdin so that I can analyze an incident without copying data into another system.
- As an on-call engineer, I want the top 10 client IPs and top 10 URLs producing 4xx/5xx responses so that I can identify traffic sources and failing routes quickly.
- As a platform engineer, I want hourly request distribution expressed as percentages so that I can see the traffic shape independent of file size.
- As a security-minded operator, I want the count and share of unique User-Agent values so that I can spot unusually diverse or repetitive clients.
- As an automation author, I want stable JSON and CSV outputs so that downstream tools do not scrape decorated terminal text.
- As a pipeline owner, I want distinct exit codes for usage, I/O, malformed data, and unique-cardinality exhaustion so that automation can react correctly.

## 5. Functional Requirements

### P0 — Must Ship

#### FR-1: Input streaming

Accept one optional positional input. A path reads that file; omitted input or `-` reads stdin. Iterate line by line and never materialize the complete input.

Acceptance criteria:

- [ ] A valid regular file and equivalent stdin produce equivalent metric values.
- [ ] An empty readable stream returns a zero report and exit 0.
- [ ] A test stream that forbids `read()` and `readlines()` still succeeds.
- [ ] A missing or unreadable path reports to stderr and exits 1 without a traceback.

#### FR-2: Supported parsing and data quality

Parse nginx combined-log records containing client address, timestamp with zone, quoted request, status, and quoted User-Agent. Default mode skips malformed lines, counts them, and shows rate-limited warnings; strict mode stops at the first malformed line.

Acceptance criteria:

- [ ] IPv4 and IPv6 address strings, query strings, timezone-bearing timestamps, and three-digit statuses 100–999 parse correctly.
- [ ] Invalid UTF-8 exits 3.
- [ ] `--strict` on a malformed line exits 3, identifies source and line, and emits no partial report.
- [ ] Default mode counts every invalid line, displays at most the first five line warnings plus a suppression summary, and can still exit 0.

#### FR-3: Top 10 client IPs

Count every valid request by exact client-address string and return at most ten values sorted by count descending, then address ascending for ties.

Acceptance criteria:

- [ ] Fewer than ten distinct addresses returns all of them; more than ten returns exactly ten.
- [ ] Tied counts have stable lexical ordering across runs and formats.
- [ ] Counts include all valid response statuses.

#### FR-4: Top 10 error URLs

Count request targets only when status is from 400 through 599 inclusive. Preserve query strings and return at most ten targets sorted by count descending, then target ascending.

Acceptance criteria:

- [ ] Status 399 and 600 do not count; 400 and 599 do count.
- [ ] The request target excludes HTTP method and protocol.
- [ ] `/path?a=1` and `/path?a=2` are distinct keys.

#### FR-5: Hourly request distribution

Return all 24 log-local wall-clock hours. Each percentage is calculated using the literal formula `100 × hourly_request_count / total_valid_requests`; when `total_valid_requests` is zero, every percentage is `0.0`.

Acceptance criteria:

- [ ] Output contains hours `00` through `23` in order even when some counts are zero.
- [ ] Counts sum to `total_valid_requests`.
- [ ] Unrounded internal percentages sum to 100 for nonempty input within floating-point tolerance.
- [ ] Presented percentages are rounded to two decimal places consistently in all formats.

#### FR-6: Unique User-Agent share and exhaustion

Count distinct nonempty User-Agent strings. Share is `100 × unique_nonempty_user_agent_count / total_valid_requests`, or `0.0` for no valid requests. `-` and empty values are excluded from distinct count. Before a new distinct value exceeds `--max-unique-user-agents`, stop with exit 4.

Acceptance criteria:

- [ ] Repeated identical values count once and case differences remain distinct.
- [ ] Empty and `-` values do not enter the set but their requests remain in the denominator.
- [ ] At the configured ceiling analysis succeeds; the next distinct value exits 4.
- [ ] Exhaustion writes a concise stderr diagnostic and no partial report.

#### FR-7: Terminal output

Default output uses Rich to display valid/invalid totals and the four required summaries. Color is enabled only for a capable TTY and can be disabled with `--no-color`.

Acceptance criteria:

- [ ] All four labeled summaries and totals are present.
- [ ] Redirected output and `--no-color` contain no ANSI escapes.
- [ ] Log-derived strings cannot inject Rich markup.

#### FR-8: JSON and CSV output

`--json` and `--csv` are mutually exclusive. They emit the versioned schemas specified in `PROJECT_ARCHITECTURE.md` and never contain ANSI escapes. Diagnostics remain on stderr.

Acceptance criteria:

- [ ] JSON parses with a standard JSON parser and contains schema version 1 and all required keys.
- [ ] CSV parses with Python's `csv.DictReader` and has exactly `section,rank,key,count,percentage` columns.
- [ ] CSV formula-like values are neutralized without changing terminal or JSON values.
- [ ] Selecting both formats exits 2.

#### FR-9: Exit behavior

The complete contract is: `0` successful report, `1` I/O or unexpected runtime failure, `2` CLI usage error, `3` input data/format failure, and `4` unique-cardinality exhaustion.

Acceptance criteria:

- [ ] Integration tests exercise all codes `0/1/2/3/4`.
- [ ] Expected errors contain no Python traceback.
- [ ] Reports go to stdout and diagnostics go to stderr.

### P1 — Should Ship

- Warning rate limiting and an exact invalid-line total.
- Deterministic benchmark generator and environment-stamped benchmark record.
- Linux and macOS verification from the same wheel where practical.

### P2 — Could Ship Later

- Transparent gzip file input; stdin decompression already works through shell composition.
- Common-log-format parsing with an explicitly unavailable User-Agent metric.
- Multiple input files with an unambiguous source and ordering contract.
- Configurable top-N after preserving top-10 defaults and schema compatibility.

## 6. Output Contract Summary

Terminal, JSON, and CSV represent the same report snapshot. Rankings use deterministic tie ordering. Machine output is data-only on stdout. The JSON and CSV field-level schemas and examples in `PROJECT_ARCHITECTURE.md` are normative; changes require a schema-version decision and updates to tests and this PRD.

## 7. Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 | Process 1 GB in under 30 s on the recorded reference laptop | Median of at least three timed runs with fixture/environment metadata |
| NFR-2 | Streaming I/O | Guard stream rejects bulk-read methods; memory profile recorded |
| NFR-3 | Python 3.11 and pip installation | Fresh-environment wheel smoke test |
| NFR-4 | Deterministic output | Repeat runs and shuffled tie fixtures compare equal where ordering is specified |
| NFR-5 | Test quality | At least 90% line coverage of `src/`, plus Ruff and mypy passing |
| NFR-6 | Privacy | No network calls, telemetry, persistent data, or full-line error echo |
| NFR-7 | Cost | No paid service or runtime infrastructure |

## 8. Dependencies and Assumptions

- Python 3.11 is installed and the operator can install a package into an environment.
- Input uses nginx combined format and is readable as strict UTF-8.
- The log timestamp's hour is the reporting timezone; timestamps are not normalized across zones.
- Exact aggregation memory depends on distinct IP, error-target, and User-Agent counts; the performance fixture must disclose these cardinalities.
- Click and Rich licenses remain compatible with open-source distribution.

## 9. Release and Kill Criteria

Release requires all P0 acceptance checks, an installable wheel, static checks, at least 90% source coverage, and recorded evidence that the 1 GB target is met. Stop or re-scope the weekend MVP if meeting the performance target requires persistence, distributed processing, hidden approximation, paid infrastructure, or removal/remapping of the exit-code contract.

## 10. Traceability

Architecture details and output schemas live in `PROJECT_ARCHITECTURE.md`. Build order and verification commands live in `IMPLEMENTATION_PLAN.md`. Product strategy, prioritization, risks, and Definition of Done live in `STRATEGIC_PLAN.md`. Any behavior change begins here, then reconciles those documents before code changes.
