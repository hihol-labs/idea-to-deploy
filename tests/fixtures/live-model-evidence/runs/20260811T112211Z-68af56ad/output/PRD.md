# Product Requirements Document: Nginx Stream Insights

## 1. Purpose

Nginx Stream Insights gives DevOps and SRE engineers a fast, local, reproducible summary of nginx combined access logs. It turns files or stdin into four fixed operational views without requiring a database, server, account, or network connection.

## 2. Goals and Non-Goals

### Goals

- Process logs in a single streaming pass and target 1 GB in under 30 seconds on a documented laptop.
- Report the top 10 IPs, top 10 request URLs with 4xx/5xx responses, hourly request distribution, and unique User-Agent share.
- Offer colored terminal text by default and stable JSON/CSV for pipelines.
- Bound exact high-cardinality state and expose machine-actionable failures.
- Install with pip and run on Python 3.11.

### Non-goals

- Authentication, authorization, accounts, or multi-user behavior.
- Database storage, retained history, dashboards, or scheduled ingestion.
- HTTP API, server process, cloud deployment, Docker requirement, or Kubernetes.
- Arbitrary queries, real-time tail-follow mode, geo-IP enrichment, bot detection, or custom nginx formats in the MVP.
- Replacement of GoAccess, Elastic/Kibana, AWStats, or shell tools outside this focused workflow.

## 3. Users and Primary Scenarios

- An on-call engineer summarizes a rotated log during an incident and reads colored tables.
- A DevOps engineer pipes decompressed or remote-command output into stdin and captures JSON.
- A platform engineer exports normalized CSV into an existing analysis pipeline.
- A security-conscious operator analyzes logs locally and confirms that no data is retained or transmitted.

## User Stories

### US-1 — Analyze a file or stdin

As an on-call SRE, I want to stream an nginx access log from a path or stdin so that I can inspect traffic without loading the file into another service.

**Priority:** P0

**Acceptance criteria:**

- [ ] With one or more readable files, records are processed in argument order and no complete input is loaded into memory.
- [ ] With no path, or with `-`, the command reads stdin; `-` may occur at most once.
- [ ] At least one valid combined-format record produces a report and exit 0 even when some other lines are malformed.
- [ ] Unreadable input, fatal decode/read failure, or an input containing zero valid records writes a concise diagnostic to stderr and exits 3.
- [ ] stdout contains report data only; diagnostics are isolated on stderr.

### US-2 — Identify dominant clients

As an SRE investigating load, I want the top 10 client IPs so that I can identify concentrated traffic sources.

**Priority:** P0

**Acceptance criteria:**

- [ ] Every valid record increments its exact client-IP count.
- [ ] At most 10 rows are emitted, ordered by descending count then ascending IP text for ties.
- [ ] Text, JSON, and CSV represent the same IP/count pairs.

### US-3 — Identify error-producing URLs

As an application operator, I want the top 10 URLs by 4xx/5xx response count so that I can focus triage on failing request targets.

**Priority:** P0

**Acceptance criteria:**

- [ ] Only status codes 400 through 599 contribute.
- [ ] The request target is counted exactly as logged, including query strings.
- [ ] 4xx and 5xx counts are combined per URL.
- [ ] At most 10 rows are emitted, ordered by descending error count then ascending URL for ties.

### US-4 — Understand traffic by hour

As a capacity engineer, I want the request share for each hour so that I can see the daily traffic shape in the analyzed input.

**Priority:** P0

**Acceptance criteria:**

- [ ] All 24 wall-clock hours `00` through `23` are represented in JSON and CSV, including zero-count hours.
- [ ] The hour is taken from each record's logged local timestamp without timezone normalization.
- [ ] Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] Counts sum exactly to `total_valid_requests`; percentages are derived only after the stream completes.

### US-5 — Measure User-Agent uniqueness

As an SRE checking client diversity, I want the share of unique User-Agent values so that I can compare distinct clients strings with total request volume.

**Priority:** P0

**Acceptance criteria:**

- [ ] The report includes `unique_user_agent_count`, `total_valid_requests`, and share percentage.
- [ ] Share is `100 × unique_user_agent_count / total_valid_requests`.
- [ ] A syntactically valid literal `-` User-Agent is counted as an observed value.
- [ ] No division by zero occurs because a zero-valid-record input exits 3 without a report.

### US-6 — Use reports in terminals and pipelines

As a DevOps engineer, I want human-readable text plus JSON and CSV so that the same tool works interactively and in automation.

**Priority:** P0

**Acceptance criteria:**

- [ ] Default text contains four labeled sections and totals; color is automatic for TTYs and absent from redirected output.
- [ ] `--json` emits the versioned JSON schema from `PROJECT_ARCHITECTURE.md` and no ANSI escapes.
- [ ] `--csv` emits the documented `metric,key,count,percentage` schema with correct quoting and no ANSI escapes.
- [ ] `--json` and `--csv` together are rejected with exit 2.
- [ ] Machine outputs are deterministic for identical inputs and options.

### US-7 — Fail safely on excessive distinct data

As a platform engineer, I want an explicit distinct-key ceiling so that an adversarial or unusual log cannot consume memory without a predictable failure.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--max-unique` defaults to 1,000,000 and applies separately to IPs, error URLs, and User-Agents.
- [ ] Existing keys continue to update at the ceiling.
- [ ] Inserting a new key beyond a dimension's ceiling emits no partial report, names the dimension on stderr, and exits 4.
- [ ] Zero or negative limits are rejected as usage errors with exit 2.
- [ ] The tool never silently samples, evicts, truncates, or approximates a required metric.

### US-8 — Read gzip input directly

As an operator working with rotated logs, I want direct gzip input so that I can avoid an external decompression command.

**Priority:** P1

**Acceptance criteria:**

- [ ] A post-MVP option or suffix contract opens gzip content as a stream.
- [ ] Decompression errors map to exit 3.
- [ ] Peak memory remains bounded by streaming and aggregation state.

### US-9 — Configure nonstandard nginx formats

As a platform owner with a custom log format, I want an explicit format configuration so that I can use the same reports.

**Priority:** P2

This is deferred until the combined-format grammar and output schemas are stable.

## 5. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept ordered file paths and stdin according to the CLI contract. |
| FR-02 | Parse nginx combined-format records and count malformed lines. |
| FR-03 | Produce exact top-10 IP and 4xx/5xx URL aggregates with deterministic ties. |
| FR-04 | Produce 24 hourly counts and percentages using `100 × hourly_request_count / total_valid_requests`. |
| FR-05 | Produce exact unique User-Agent count and share. |
| FR-06 | Render default Rich text, versioned JSON, and normalized CSV. |
| FR-07 | Enforce `--max-unique` independently for all distinct-key dimensions. |
| FR-08 | Implement the full exit-code contract `0/1/2/3/4` without remapping code 4. |
| FR-09 | Keep stdout data-only and stderr diagnostic-only. |
| FR-10 | Provide pip package metadata and a `nginx-insight` console command. |

### P1 — Should ship after MVP

- FR-11: stream gzip-compressed input with identical output semantics.
- FR-12: publish wheels and source distributions through an automated release workflow if the project is publicly released.

### P2 — Could ship later

- FR-13: user-supplied nginx log-format grammar with validation.
- FR-14: optional additional exact metrics that do not change the default report.

## 6. Output and Calculation Contract

The canonical JSON and CSV shapes and tie-breaking rules are defined in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. Text is a presentation of the same report model, not a separate calculation path.

- `total_valid_requests` counts only successfully parsed records.
- `invalid_line_count` counts blank or malformed records skipped during otherwise successful processing.
- Error URLs combine all 4xx and 5xx statuses.
- Hourly distribution uses the logged hour and the formula `100 × hourly_request_count / total_valid_requests`.
- Unique User-Agent share uses `100 × unique_user_agent_count / total_valid_requests`.
- Percentages may be rounded for display, but integer numerators and denominators remain authoritative and are included in machine output.

## 7. Complete Exit-Code Contract

| Code | Contract |
|---:|---|
| `0` | Successful report or successful informational command |
| `1` | Unexpected runtime or output failure |
| `2` | Invalid command usage or option configuration |
| `3` | Input/read/decode/data failure, including zero valid records |
| `4` | Unique-cardinality exhaustion in IP, error-URL, or User-Agent state |

Code 4 is reserved for unique-cardinality exhaustion and must not be omitted, reused, or remapped by wrappers or renderers.

## 8. Non-Functional Requirements

| Area | Requirement |
|---|---|
| Performance | Representative 1 GB file completes in under 30 seconds on the documented laptop profile. |
| Memory | Single-pass operation; no raw record retention; default-limit benchmark target ≤512 MiB peak RSS. |
| Determinism | Identical bytes and options produce equivalent report values and stable ordering. |
| Compatibility | Python 3.11; installable from a wheel/sdist with pip. |
| Privacy | No network activity, telemetry, persistence, or input retention. |
| Safety | Treat all log fields as untrusted and escape terminal/JSON/CSV output correctly. |
| Testability | Parser, aggregator, renderers, and CLI error mappings are independently testable. |

## 9. Release Acceptance

The MVP is accepted when all P0 story criteria pass, package installation and console invocation work in a clean Python 3.11 environment, the complete `0/1/2/3/4` contract is covered by CLI integration tests, and the documented 1 GB benchmark satisfies the time target without exceeding the declared cardinality boundary. Verification must apply to the exact candidate under the repository's Idea to Deploy contract.

## 10. Kill Criteria

Pause or revise the release if:

- The representative 1 GB benchmark cannot meet 30 seconds after measurement-driven parser optimization.
- Required exact aggregates cannot fit within the documented laptop memory envelope for representative inputs.
- JSON/CSV schemas cannot represent all four metrics without ambiguity.
- Supporting real-world combined logs would require silently accepting materially ambiguous records.

Do not respond to a kill criterion by silently approximating metrics, dropping records, or introducing a database/service outside the approved scope.

## 11. Traceability

The roadmap and business constraints live in `STRATEGIC_PLAN.md`; component, schema, parsing, and CLI details live in `PROJECT_ARCHITECTURE.md`; build sequencing and verification live in `IMPLEMENTATION_PLAN.md`.

