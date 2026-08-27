# Product Requirements Document: Nginx Stream Analytics CLI

## Product Summary

The product gives DevOps/SRE engineers a fast, local summary of an nginx access-log file or stream. The MVP is free, open source, pip-installable, stateless, and completed within one weekend. `PROJECT_ARCHITECTURE.md` is the technical source of truth; this PRD is the behavioral source of truth.

## Goals

- Produce the four requested analyses from one streaming pass.
- Work well for both interactive incident response and Unix pipelines.
- Process a 1 GB representative log in under 30 seconds on the reference laptop.
- Fail explicitly when exact User-Agent cardinality cannot be tracked safely.

## Non-Goals

Authentication, persistent storage, HTTP APIs, server mode, dashboards, cloud integration, Kubernetes, distributed processing, log tail-following, arbitrary nginx format configuration, and approximate cardinality are outside MVP scope.

## User Stories

- As a SRE, I want to see the top 10 client IPs so that I can identify concentrated traffic during an incident. **Priority: P0**
- As a service owner, I want to see the top 10 URLs returning 4xx or 5xx statuses so that I can focus remediation on failing routes. **Priority: P0**
- As an on-call engineer, I want each hour's request percentage so that I can see when traffic is concentrated. **Priority: P0**
- As a capacity engineer, I want the share of unique User-Agents so that I can estimate client diversity without storing individual requests. **Priority: P0**
- As an automation engineer, I want JSON or CSV output so that I can feed results into pipelines without scraping terminal text. **Priority: P0**
- As a terminal user, I want a colored, readable default report so that I can interpret results quickly. **Priority: P0**
- As an operator, I want to tune the ranking size and exact-cardinality cap so that I can adapt resource use to my environment. **Priority: P1**
- As an operator with archived logs, I want transparent gzip input so that I can avoid manual decompression. **Priority: P2**

## Functional Requirements

### P0 — Must

#### FR-1: Input and parsing

- Accept one file path, `-`, or omitted input for stdin.
- Support nginx common and combined access-log records as declared in `PROJECT_ARCHITECTURE.md`.
- Stream input without loading it completely into memory.
- Count malformed lines and continue; exit 3 if no valid records exist.

Acceptance criteria:

- [ ] A fixture containing common and combined records produces the documented valid/malformed totals.
- [ ] File and stdin invocations produce identical report models for identical bytes.
- [ ] A malformed-only input emits no partial report and exits 3.

#### FR-2: Top client IPs

- Count valid requests by parsed client IP.
- Return 10 rows by default, sorted count descending and key ascending for ties.

Acceptance criteria:

- [ ] A fixture with ties produces deterministic lexicographic tie ordering.
- [ ] Fewer than 10 distinct IPs produces only the available rows.

#### FR-3: Top error URLs

- Count request targets only for status codes 400 through 599 inclusive.
- Return the top 10 by default using the same deterministic ordering.

Acceptance criteria:

- [ ] 399 and 600 are excluded, while 400, 499, 500, and 599 are included.
- [ ] Query strings remain part of the request target for MVP counting.

#### FR-4: Hourly distribution

- Emit buckets `00` through `23` using the hour encoded in each valid record's timestamp.
- Define each percentage with the literal formula `100 × hourly_request_count / total_valid_requests`.

Acceptance criteria:

- [ ] Exactly 24 ordered buckets are emitted for a successful report.
- [ ] Counts sum to total valid requests and unrounded percentages sum to approximately 100%, within floating-point tolerance.

#### FR-5: Unique User-Agent share

- Count exact, distinct, nonempty combined-format User-Agent strings.
- Divide by valid requests that contain a nonempty User-Agent, not all records.
- Stop without a partial report and exit 4 before exceeding the configured exact-cardinality limit.

Acceptance criteria:

- [ ] Repeated User-Agents count once in the numerator.
- [ ] Common-format records and `-` values do not enter numerator or denominator.
- [ ] A limit-plus-one fixture exits 4 and writes an actionable diagnostic to stderr.

#### FR-6: Renderers and CLI behavior

- Default to colored Rich terminal output with automatic non-TTY color suppression.
- Support mutually exclusive `--json` and `--csv` formats.
- Send report data to stdout and diagnostics to stderr.
- Implement the complete exit-code contract `0/1/2/3/4`: success, I/O error, usage error, no valid records, and unique-cardinality exhaustion respectively.

Acceptance criteria:

- [ ] JSON output parses as one document with the documented keys.
- [ ] CSV output parses with the documented normalized header.
- [ ] JSON and CSV contain no ANSI escape sequences.
- [ ] Integration tests exercise exit codes 0, 1, 2, 3, and 4.

### P1 — Should

- `--top` accepts a positive integer and defaults to 10.
- `--max-unique-user-agents` accepts a positive integer and defaults to 1,000,000.
- `--color/--no-color`, `--version`, and useful Click help are provided.

### P2 — Could

- Transparently read `.gz` input while retaining stdin and plain-file behavior.
- Add an opt-in malformed-line sample diagnostic that never contaminates stdout.

## Quality Requirements

| Attribute | Requirement |
|---|---|
| Performance | 1 GB representative log in under 30 seconds on the documented reference laptop |
| Compatibility | Python 3.11; installable through pip |
| Determinism | Stable ordering and schema for identical input/options |
| Resource safety | Streaming input and explicit User-Agent cardinality exhaustion |
| Privacy | No network access, telemetry, or persistence |
| Usability | Actionable help and errors; readable terminal default |

## Release and Kill Criteria

Release only when all P0 acceptance criteria pass, package installation is verified, and the performance target is measured. Re-scope or stop the MVP if profiling shows the mandated Python single-process design cannot reach 1 GB in under 30 seconds on the reference laptop, exact User-Agent semantics cannot be bounded without violating the contract, or supporting common/combined nginx grammar cannot be made deterministic within the weekend.

