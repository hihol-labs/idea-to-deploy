# Product Requirements Document: Nginx Stream Analyzer

## 1. Purpose

Provide DevOps and SRE engineers with a fast, local, repeatable first-pass analysis of nginx access logs through a pip-installable Python 3.11 CLI. The product reports four required views in terminal, JSON, or CSV form without a service, authentication, database, or network dependency.

## 2. Goals and Non-goals

### Goals

- Process a regular 1 GB nginx access log in under 30 seconds on a documented representative laptop.
- Stream input without loading the file into memory.
- Correctly report top 10 IPs, top 10 error URLs, hourly request distribution, and unique User-Agent share.
- Provide deterministic terminal, JSON, and CSV outputs.
- Make malformed input and resource exhaustion visible through diagnostics and the complete exit-code contract.

### Non-goals

- Authentication or multi-user access.
- Database-backed history, dashboards, HTTP API, server mode, cloud hosting, Docker, or Kubernetes.
- Arbitrary nginx format-language parsing in the MVP.
- Request-body analysis, geolocation, bot classification, alerting, or log mutation.
- Approximate unique-cardinality results after the exact safety limit is reached.

## 3. Personas and Use Cases

- **On-call SRE:** receives a large log during an incident and needs traffic/error concentration and hourly shape immediately.
- **DevOps engineer:** pipes rotated or remote logs into a local command and feeds JSON/CSV into another tool.
- **Platform engineer:** needs a stable, testable alternative to bespoke shell parsing for runbooks.

## User Stories

### US-1: Analyze a file locally

As an on-call SRE, I want to analyze an nginx log file with one command so that I can identify dominant clients and failure hotspots during triage.

Priority: **P0**

Acceptance criteria:

- [ ] A valid combined-format file produces all four required metrics and exits 0.
- [ ] Processing reads incrementally rather than buffering the entire input.
- [ ] Top lists contain at most 10 entries and use deterministic tie ordering.
- [ ] A documented representative 1 GB file completes in under 30 seconds on the reference laptop.

### US-2: Pipe logs through stdin

As a DevOps engineer, I want to stream logs over stdin so that I can compose the analyzer with `ssh`, decompression, and Unix pipelines.

Priority: **P0**

Acceptance criteria:

- [ ] Omitting `INPUT` or passing `-` reads stdin.
- [ ] File and stdin inputs yield equivalent reports for identical bytes.
- [ ] A read or UTF-8 decode failure writes a diagnostic to stderr and exits 1.

### US-3: Consume JSON in automation

As a platform engineer, I want stable JSON output so that runbooks and scripts can consume metrics without scraping terminal tables.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` emits exactly one valid JSON object to stdout on success.
- [ ] The object includes a schema version, totals, ordered top lists, all 24 hourly bins, and unique User-Agent fields.
- [ ] JSON output contains no ANSI escapes or diagnostics.
- [ ] Fatal exit 3 or 4 does not leave a partial JSON object.

### US-4: Consume CSV in pipelines

As a DevOps engineer, I want stable CSV output so that I can load the report into spreadsheet and command-line data tools.

Priority: **P0**

Acceptance criteria:

- [ ] `--csv` emits a fixed header and rows with a documented section discriminator.
- [ ] Values containing commas, quotes, newlines, or formula prefixes are safely encoded according to the CSV policy.
- [ ] CSV output contains no ANSI escapes or diagnostics.
- [ ] `--csv` and `--json` together are rejected as usage error exit 2.

### US-5: Understand malformed data

As an SRE, I want malformed lines to be counted and excluded so that a few bad records do not hide valid operational signals or silently corrupt denominators.

Priority: **P0**

Acceptance criteria:

- [ ] Mixed valid/invalid input reports `invalid_line_count` and uses only valid requests in metrics.
- [ ] Non-empty input containing zero valid records exits 3 and explains the failure on stderr.
- [ ] Empty input exits 0 with zero totals, empty top lists, and zero percentages.

### US-6: Fail safely on cardinality exhaustion

As an operator, I want exact User-Agent tracking to stop at a known resource ceiling so that hostile or unusually diverse data cannot exhaust laptop memory silently.

Priority: **P0**

Acceptance criteria:

- [ ] The CLI exposes a positive `--ua-cardinality-limit` option with a documented default.
- [ ] Attempting to exceed the limit stops processing, writes a diagnostic to stderr, emits no partial success report, and exits 4.
- [ ] Repeated known User-Agent values do not consume additional cardinality slots.

### US-7: Read compressed rotations directly

As a DevOps engineer, I want optional gzip input so that I can inspect standard rotated logs without a separate decompression process.

Priority: **P1**

Acceptance criteria:

- [ ] If implemented, gzip detection/selection remains streaming and produces the same report as decompressed input.
- [ ] Until implemented, documented shell decompression into stdin is the supported path.

### US-8: Adjust ranking depth

As an analyst, I want to configure top-N so that I can expand a report after the default top-10 triage.

Priority: **P2**

Acceptance criteria:

- [ ] If implemented, the default remains 10 and invalid values are usage errors.

## 5. Functional Requirements

### P0 — Must

| ID | Requirement |
|---|---|
| FR-1 | Accept one path or stdin and parse supported common/combined nginx records incrementally. |
| FR-2 | Count all valid requests by client IP and emit at most 10 ranked IPs. |
| FR-3 | Count request URLs only for status 400–599 and emit at most 10 ranked URLs. |
| FR-4 | Emit 24 hourly bins. Each percentage uses `100 × hourly_request_count / total_valid_requests`; it is not an unscaled fraction. |
| FR-5 | Count exact distinct nonempty User-Agent values and report `100 × unique_nonempty_user_agent_count / total_valid_requests`. |
| FR-6 | Enforce exact User-Agent cardinality limit and map exhaustion to exit 4. |
| FR-7 | Render a default Rich terminal report with color only where terminal-safe. |
| FR-8 | Render versioned, deterministic JSON with no ANSI content. |
| FR-9 | Render deterministic CSV with fixed columns and safe encoding. |
| FR-10 | Count malformed records, exclude them from valid denominators, and handle all-invalid nonempty input as exit 3. |

### P1 — Should

| ID | Requirement |
|---|---|
| FR-11 | Support gzip-compressed file input without abandoning streaming behavior. |

### P2 — Could

| ID | Requirement |
|---|---|
| FR-12 | Allow a configurable ranking depth while retaining top 10 as default. |
| FR-13 | Support explicitly defined additional nginx log formats. |

## 6. Metric Definitions

- `total_lines`: every input line read.
- `total_valid_requests`: lines successfully parsed as supported nginx access records.
- `invalid_line_count`: `total_lines - total_valid_requests`.
- Top IPs: count each valid request by its parsed client IP.
- Top error URLs: count the parsed request target for valid responses with status 400–599; exclude a missing `-` request target.
- Hourly request distribution: 24 percentages using exactly `100 × hourly_request_count / total_valid_requests`; when total valid requests is zero, each value is 0.0.
- Unique User-Agent share: `100 × unique_nonempty_user_agent_count / total_valid_requests`; when total valid requests is zero, it is 0.0.
- Common-format records contain no User-Agent, so they increase the valid denominator but not the unique User-Agent numerator.

## 7. Output and Exit Contract

The command and schemas are normative in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. All output formats express the same report semantics.

| Exit | Product behavior |
|---:|---|
| `0` | Complete report emitted successfully, including empty input or mixed valid/invalid input |
| `1` | Input or runtime I/O/decoding failure |
| `2` | Invalid CLI invocation or option combination |
| `3` | Non-empty input contains no valid records |
| `4` | Unique-cardinality exhaustion |

## 8. Non-functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | Run on CPython 3.11 and install through pip. |
| NFR-2 | Process one representative 1 GB file in under 30 seconds on a documented laptop. |
| NFR-3 | Perform one streaming pass and never buffer the complete file. |
| NFR-4 | Deterministically order tied ranking entries lexicographically. |
| NFR-5 | Escape untrusted log text in terminal, JSON, and CSV renderers. |
| NFR-6 | Emit complete structured documents only; diagnostics go to stderr. |
| NFR-7 | Have no required database, service, account, network, environment variable, container, or cloud resource. |

## 9. Release Acceptance

- All P0 story acceptance criteria pass on reviewed fixtures.
- Parser cases cover IPv4, IPv6, escaped quotes, timezone offsets, missing requests, common/combined records, malformed records, and UTF-8 errors.
- Terminal, JSON, and CSV golden outputs are deterministic.
- Exit codes `0/1/2/3/4` are each exercised by an integration test.
- Wheel installation and console entry point work in a clean Python 3.11 environment.
- The benchmark evidence meets the stated target and records its machine profile.

## 10. Kill Criteria

Pause release and revisit scope if the representative benchmark remains above 30 seconds after measured optimization, exact User-Agent tracking cannot be bounded safely, or parser correctness requires supporting arbitrary configuration syntax beyond the one-weekend constraint.

## 11. Dependencies and Traceability

Architecture and public CLI details are in `PROJECT_ARCHITECTURE.md`. RICE/MoSCoW rationale is in `STRATEGIC_PLAN.md`. Work packages and verification commands are in `IMPLEMENTATION_PLAN.md`.
