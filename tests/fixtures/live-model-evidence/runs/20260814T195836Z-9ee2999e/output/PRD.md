# Product Requirements Document: nginx-stream-report

## Product Summary

`nginx-stream-report` gives DevOps and SRE engineers a fast local summary of nginx combined access logs. It is a Python 3.11 CLI installed through pip, reads a file or stdin as a stream, and emits colored terminal text by default or stable JSON/CSV for pipelines.

## Problem Statement

During incidents and routine checks, operators often need a small set of aggregate answers before a full observability stack is available or justified. Ad hoc shell pipelines are hard to validate and reuse; hosted or persistent analytics systems cost time and infrastructure. The product closes that gap with a fixed, exact, local report.

## Goals and Success Measures

- Correctly report top 10 IPs, top 10 error URLs, hourly percentages, and unique User-Agent share.
- Process a representative 1 GB log in under 30 seconds on documented laptop hardware.
- Preserve a stable terminal/JSON/CSV and exit-code contract.
- Install and run locally with Python 3.11 and no external service.
- Keep MVP budget at $0 and deliverable in one weekend.

## Non-Goals

- Authentication, database storage, historical query, HTTP API, server mode, web UI, cloud deployment, or Kubernetes.
- Replacing a full observability platform.
- Real-time file following (`tail -f`) in MVP.
- Arbitrary nginx log-format configuration in MVP.
- Silent approximate results when exact cardinality exceeds capacity.

## User Stories

### US-1: Analyze a local log

As an on-call SRE, I want to pass an nginx access-log path to one command so that I can see the dominant clients and failures immediately.

**Priority:** P0

**Acceptance criteria:**

- [ ] A readable combined-format file produces all four report sections and exits `0`.
- [ ] Top IPs contain at most 10 values ordered by count descending and value ascending for ties.
- [ ] An unreadable or absent path produces no report, diagnoses the input failure on stderr, and exits `1`.

### US-2: Analyze a pipeline stream

As a platform engineer, I want to pipe decompressed or filtered logs through stdin so that the tool composes with existing Unix workflows.

**Priority:** P0

**Acceptance criteria:**

- [ ] Omitting `INPUT` and using `INPUT=-` both read stdin.
- [ ] Identical file and stdin bytes produce equivalent reports.
- [ ] The process consumes input incrementally rather than loading the entire stream.

### US-3: Locate failing URLs

As an incident responder, I want the top 10 request URLs producing 4xx/5xx responses so that I can focus debugging on the largest failure sources.

**Priority:** P0

**Acceptance criteria:**

- [ ] Only statuses 400 through 599 contribute to the error-URL ranking.
- [ ] Counts combine identical request targets and use deterministic tie ordering.
- [ ] Successful and redirect responses do not affect this ranking.

### US-4: Understand hourly load shape

As an SRE, I want request volume by local log hour as percentages so that I can spot concentration and quiet periods.

**Priority:** P0

**Acceptance criteria:**

- [ ] The report always represents hours 00 through 23 in order.
- [ ] Each value uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] Empty input reports 0.0% for every hour without division errors.

### US-5: Quantify client diversity

As a capacity investigator, I want the share of unique User-Agents so that I can quickly distinguish concentrated from diverse client traffic.

**Priority:** P0

**Acceptance criteria:**

- [ ] The report includes the exact unique User-Agent count.
- [ ] Share is `100 × unique_user_agents / total_valid_requests`, or `0.0` for no valid requests.
- [ ] A `-` User-Agent is consistently counted as one unknown value.

### US-6: Automate with JSON

As a platform engineer, I want a deterministic JSON report so that scripts can consume metrics without scraping terminal tables.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits one valid JSON object matching schema version 1 and exits `0` on success.
- [ ] JSON stdout contains no ANSI sequences or prose.
- [ ] Failures emit no partial JSON document.

### US-7: Export CSV

As an operations analyst, I want CSV output so that I can load the report into spreadsheets and standard command-line tools.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--csv` emits the header `section,key,count,percentage` and rows for every report section.
- [ ] Values containing delimiters or quotes round-trip through a standards-compliant CSV parser.
- [ ] `--csv --json` is rejected as a usage error with exit `2`.

### US-8: Fail safely at the memory boundary

As an operator, I want the command to stop explicitly if exact distinct-value tracking exceeds its declared capacity so that it never produces plausible but incomplete results.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--max-unique` applies independently to IP, error-URL, and User-Agent distinct values.
- [ ] Exceeding any ceiling emits a concise stderr diagnostic, no partial structured report, and exit `4`.
- [ ] The tool never substitutes an approximate count without a future explicit feature contract.

### US-9: Control terminal styling

As an operator capturing text output, I want `--no-color` and automatic terminal detection so that saved reports contain no escape codes.

**Priority:** P1

**Acceptance criteria:**

- [ ] `--no-color` disables ANSI styling in text mode.
- [ ] Redirected text output is uncolored by default.

### US-10: Read gzip files directly

As an operator with rotated logs, I want direct gzip input so that I do not need a separate decompression process.

**Priority:** P1

**Acceptance criteria:**

- [ ] A future `--gzip` or suffix-detected mode streams decompression without extracting a temporary file.
- [ ] Plain input behavior and all exit codes remain unchanged.

### US-11: Configure alternate log formats

As an nginx administrator with a custom format, I want to define field mapping so that I can use the same reports.

**Priority:** P2

**Acceptance criteria:** Deferred until a safe grammar and validation contract are specified.

## Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-1 | Accept one optional local input path, with omitted path or `-` meaning stdin |
| FR-2 | Parse nginx combined-format records and count skipped malformed lines by default |
| FR-3 | `--fail-on-malformed` stops at the first malformed line with exit `3` |
| FR-4 | Compute deterministic top 10 client IPs |
| FR-5 | Compute deterministic top 10 URLs by 4xx/5xx count |
| FR-6 | Compute 24 hourly percentages using `100 × hourly_request_count / total_valid_requests` |
| FR-7 | Compute unique User-Agent count and percentage share |
| FR-8 | Render colored Rich terminal text by default when appropriate |
| FR-9 | Support mutually exclusive `--json` and `--csv` outputs |
| FR-10 | Enforce a positive per-category `--max-unique` ceiling and exit `4` on exhaustion |
| FR-11 | Implement complete exit codes `0/1/2/3/4` exactly as specified in architecture |

### P1 — Should ship after P0

| ID | Requirement |
|---|---|
| FR-12 | Provide `--no-color` and automatic non-terminal color suppression |
| FR-13 | Stream gzip-compressed input directly |

### P2 — Could ship later

| ID | Requirement |
|---|---|
| FR-14 | Support explicitly configured nginx log-field mappings |
| FR-15 | Offer an opt-in approximate heavy-hitter mode with visibly distinct semantics |

## Output and Error Contract

`PROJECT_ARCHITECTURE.md` section `CLI Interface` is normative for commands, options, schemas, stdout/stderr separation, and exits. In summary: `0` success, `1` input/I/O failure, `2` usage error, `3` strict malformed-data failure, and `4` unique-cardinality exhaustion. A successful empty stream is exit `0`. Structured output is never partial on failure.

## Non-Functional Requirements

| ID | Requirement | Evidence |
|---|---|---|
| NFR-1 | Process a representative 1 GB fixture in under 30 seconds | Repeatable benchmark with hardware, Python version, wall time, throughput, RSS |
| NFR-2 | Memory does not scale with input bytes | Streaming test plus peak-RSS comparison across equal-cardinality fixture sizes |
| NFR-3 | Support Python 3.11 | Clean-environment install and test run |
| NFR-4 | Deterministic output | Golden tests and repeated-run byte comparison for JSON/CSV |
| NFR-5 | Preserve untrusted data as data | Control-sequence tests; standard JSON/CSV serializers; no shell execution |
| NFR-6 | Zero network and persistent-service dependency | Dependency review and offline smoke test |

## Release Acceptance

- All P0 story criteria pass in a clean Python 3.11 environment.
- Full unit/integration suite passes with at least 90% branch coverage for parser, aggregation, and renderers.
- Wheel installation and console entry point pass a clean-environment smoke test.
- The documented 1 GB benchmark completes in under 30 seconds on the reference laptop.
- Tests explicitly exercise exits `0`, `1`, `2`, `3`, and `4`.
- README and CLI help describe the same options and limitations.

## Kill Criteria

Pause release and revisit architecture if the fixed 1 GB benchmark remains at or above 30 seconds after measured optimization, if peak memory cannot be bounded under the exact-cardinality contract, or if ordinary combined-format samples cannot be parsed reliably without expanding MVP into a general ingestion framework. Do not resolve a kill criterion by silently weakening exactness or adding a forbidden service.

