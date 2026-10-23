# Product Requirements Document: nginx-top

## 1. Product Summary

`nginx-top` gives DevOps/SRE engineers a fast local summary of nginx combined access logs. It reads one or more files or stdin in a single pass and reports top client IPs, top error-producing URLs, hourly traffic distribution, and exact unique User-Agent share. Default output is colored terminal text; JSON and CSV support pipelines.

## 2. Problem Statement

During incident response and routine host inspection, engineers need a small set of traffic signals before a full observability stack is available or justified. Existing choices are either fragile one-off shell pipelines or operationally broad tools. The product must make this analysis repeatable without moving logs off the local machine or creating persistent infrastructure.

## 3. Goals and Success Criteria

- Compute all four required metrics from a representative 1 GB log in under 30 seconds on a documented laptop.
- Preserve equivalent metric values across text, JSON, and CSV renderers.
- Run locally with Python 3.11 and install through pip.
- Make skipped malformed input and fatal conditions visible through diagnostics and stable exit codes.
- Keep cash cost at $0 and scope feasible for one weekend.

## 4. Non-Goals

- Authentication, accounts, roles, database, HTTP API, web UI, server, cloud service, or Kubernetes.
- Persistent history, alerting, tail-follow mode, remote log collection, or multi-host correlation.
- Arbitrary nginx `log_format` definitions in the MVP.
- Approximate distinct counting or silently truncated unique User-Agent results.
- Replacement for a full SIEM or observability platform.

## User Stories

- As a SRE, I want to see the top 10 client IPs so that I can quickly identify dominant or suspicious sources.
- As an on-call engineer, I want to see the top 10 URLs by combined 4xx/5xx response count so that I can prioritize broken routes.
- As a platform engineer, I want hourly request distribution expressed as `100 × hourly_request_count / total_valid_requests` so that I can understand the traffic shape without manual arithmetic.
- As a DevOps engineer, I want the exact count and share of unique User-Agents so that I can assess client diversity while being warned if exact cardinality exceeds a safe limit.
- As an automation author, I want JSON and CSV output with stable schemas so that I can feed results into scripts without parsing colored text.
- As an operator validating log quality, I want strict malformed-line handling so that corrupt input can fail a pipeline predictably.
- As a privacy-conscious engineer, I want analysis to stay local so that access logs are not uploaded to another service.

## 6. Functional Requirements

### P0 — Must

#### FR-001: Stream sources

Read zero or more input arguments line by line. Zero arguments or one `-` reads stdin; multiple file paths are combined sequentially into one analysis. Do not load an entire input into memory.

**Acceptance criteria:**

- [ ] A file and the same bytes on stdin produce equivalent metrics.
- [ ] Multiple files produce one aggregate with correct source count.
- [ ] An unreadable file emits a concise stderr diagnostic, no partial structured report, and exits 1.
- [ ] Mixing `-` with file paths is rejected with exit 2.

#### FR-002: Parse supported nginx combined format

Extract client IP text, timezone-aware timestamp, request target, numeric status, and User-Agent. Default mode counts and skips malformed lines; strict mode terminates on the first malformed line.

**Acceptance criteria:**

- [ ] Conventional combined-format IPv4 and IPv6-text samples parse correctly.
- [ ] Quoted referrer/User-Agent fields and numeric timezone offsets are handled.
- [ ] Default output reports total, valid, and malformed line counts.
- [ ] `--strict` identifies source and line number without echoing the full record and exits 3.

#### FR-003: Top 10 client IPs

Count valid records by client IP and return at most 10 entries ordered by count descending and then IP text ascending.

**Acceptance criteria:**

- [ ] Every valid record contributes exactly once.
- [ ] Ties are deterministic across repeated runs and output formats.
- [ ] Fewer than 10 distinct IPs produce no padding rows.

#### FR-004: Top 10 error URLs

For valid records with status 400–599 inclusive, count the request target and return at most 10 entries ordered by count descending and then target ascending.

**Acceptance criteria:**

- [ ] Statuses 399 and 600 do not contribute; 400 and 599 do.
- [ ] Query strings remain part of the exact request-target key.
- [ ] A valid request field of `-` does not create a URL ranking entry.
- [ ] Ties are deterministic.

#### FR-005: Hourly request distribution

Return all 24 log-local hour buckets. Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests` and is `0.0` when there are no valid requests.

**Acceptance criteria:**

- [ ] Every valid record contributes to exactly one 0–23 bucket using its timestamp's encoded timezone offset.
- [ ] All 24 buckets are present in every output format.
- [ ] Non-empty bucket percentages total approximately 100% subject only to display rounding.
- [ ] Empty valid input yields 24 zero-count, zero-percent buckets.

#### FR-006: Exact unique User-Agent share

Report the number of distinct User-Agent strings and `100 × unique_user_agent_count / total_valid_requests`. Empty valid input yields count 0 and share `0.0`.

**Acceptance criteria:**

- [ ] Repeated identical strings count once and distinct strings count separately.
- [ ] The same count/share appears in text, JSON, and CSV.
- [ ] No approximate result is labeled exact.

#### FR-007: Cardinality safety

`--max-unique-user-agents` is a positive integer with default 1,000,000. Exceeding it stops analysis before output and signals unique-cardinality exhaustion.

**Acceptance criteria:**

- [ ] Exactly the configured number of distinct strings is accepted.
- [ ] The next distinct string emits a concise stderr error, produces no partial report, and exits 4.
- [ ] Zero and negative limits are usage errors with exit 2.

#### FR-008: Rich terminal output

Default output shows the four metrics and diagnostics in readable Rich sections. Color is automatic on capable TTYs, can be forced off, and never appears in redirected structured output.

**Acceptance criteria:**

- [ ] `--no-color` contains no ANSI color sequences.
- [ ] Log-derived Rich markup/control-like content is displayed as data, not interpreted markup.
- [ ] JSON and CSV never contain Rich styling.

#### FR-009: JSON output

`--json` emits one valid JSON document with `top_ips`, `top_error_urls`, `hourly_distribution`, `user_agents`, and `diagnostics`.

**Acceptance criteria:**

- [ ] Standard-library `json.load` parses stdout.
- [ ] Counts and percentages are numeric values, not formatted strings.
- [ ] Output ordering and keys are stable and documented.

#### FR-010: CSV output

`--csv` emits the header `metric,rank,key,count,percentage` and deterministic long-form metric rows.

**Acceptance criteria:**

- [ ] Standard-library `csv.DictReader` parses stdout.
- [ ] Empty fields are empty and quoting is RFC-compatible through the standard library.
- [ ] Spreadsheet formula-triggering values are neutralized.
- [ ] JSON and CSV flags cannot be combined and misuse exits 2.

#### FR-011: Complete process contract

The CLI implements exit codes `0/1/2/3/4`: 0 success, 1 I/O/operational failure, 2 usage error, 3 malformed input in strict mode, and 4 unique-cardinality exhaustion.

**Acceptance criteria:**

- [ ] Integration tests exercise all five codes.
- [ ] Each fatal nonzero condition writes diagnostics to stderr.
- [ ] Fatal conditions do not emit a partial JSON or CSV document.

### P1 — Should

#### FR-012: Strict validation mode

`--strict` makes the first malformed line fatal with source and line number. This is P1 as a feature but its exit behavior is part of the P0 process contract once enabled.

#### FR-013: Conventional terminal behavior

Treat an ordinary downstream pipe close as a clean termination, use stdout only for results, and provide concise `--help`/`--version` output.

### P2 — Could

- Read `.gz` inputs directly while retaining stdin behavior.
- Accept a small curated set of named nginx formats.
- Allow `--top N` while keeping 10 as the default and documented benchmark case.

## 7. Output Definitions

Top IP means highest request count among valid lines. Top error URL means highest combined count of 4xx and 5xx statuses. Hourly distribution is a percentage of all valid requests, not an unscaled fraction. Unique User-Agent share is distinct User-Agent strings divided by valid requests and multiplied by 100; it is a diversity indicator and may be greater than a conventional “share of sessions” interpretation only as constrained by distinct count never exceeding request count.

All ties are stable by key ascending. Percentages retain full precision in the domain model and are rounded only at rendering: text/CSV to two decimals and JSON to at most six decimal places.

## 8. Quality Attributes

| Attribute | Requirement |
|---|---|
| Performance | Representative 1 GB input completes in <30 s on the named reference laptop |
| Memory | Peak RSS ≤512 MiB for benchmark input within the default UA ceiling |
| Compatibility | CPython 3.11 on Linux and macOS |
| Correctness | ≥90% line coverage plus integration tests for every exit code and renderer |
| Determinism | Identical input/options yield identical non-colored JSON/CSV bytes |
| Privacy | No networking or telemetry; diagnostics do not reproduce full log records |
| Accessibility | `--no-color` available; meaning never depends on color alone |

## 9. Dependencies and Constraints

- Runtime dependencies: Click and Rich; domain models use dataclasses.
- Distribution: pip-compatible wheel and source distribution.
- Cash budget: $0; delivery: one weekend.
- No authentication, database, HTTP API, server, cloud, container requirement, or Kubernetes.
- Supported input in MVP: conventional nginx combined format only.

## 10. Release Acceptance

Release requires a clean Python 3.11 virtual-environment install, green unit/integration/static checks, all output formats parse successfully, all five exit codes have integration evidence, and a measured representative 1 GB run under 30 seconds on the documented laptop. The benchmark file may be generated locally and must not be committed.

## 11. Kill Criteria

- The one-process Python implementation cannot meet 1 GB/<30 s after measurement-guided optimization within the weekend.
- The documented default User-Agent ceiling exceeds the 512 MiB peak RSS target on representative data.
- Real required inputs cannot be represented by the declared combined-format contract without building a general format language.
- Scope pressure requires a database, server, remote collection, or hosted UI for the MVP.

Crossing a kill criterion triggers an explicit product/architecture re-scope; it does not permit silent weakening of correctness, privacy, or exit semantics.

