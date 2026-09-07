# Product Requirements Document: nginx-stream-insights

## Product Summary

`nginx-stream-insights` is a local Python 3.11 CLI that lets DevOps and SRE engineers turn an nginx access-log stream into four reliable operational summaries without running a service or retaining log data. The product accepts a file or stdin, renders colored terminal text by default, and supports JSON or CSV for automation.

## Goals

- Produce top 10 client IPs and top 10 URLs whose responses are 4xx/5xx.
- Report a 24-hour request distribution as percentages using `100 × hourly_request_count / total_valid_requests`.
- Report the percentage share of distinct, nonempty User-Agents among valid requests that contain a User-Agent.
- Process a representative 1 GB input in under 30 seconds on the documented laptop.
- Provide deterministic text, JSON, CSV, diagnostics, and exit behavior.

## Non-Goals

- Authentication, authorization, accounts, or multi-user isolation.
- A database, saved history, ingestion daemon, HTTP API, server, or dashboard.
- Cloud deployment, containers, or Kubernetes.
- General-purpose log query language, correlation across files, or live tail-follow mode in MVP.
- Approximate cardinality presented as an exact answer.

## User Stories

- As a on-call SRE, I want to pipe an nginx access log into one command so that I can see the top 10 client IPs during an incident. Priority: P0.
- As a DevOps engineer, I want the top 10 URLs ranked by their combined 4xx/5xx response counts so that I can identify failing routes. Priority: P0.
- As a SRE, I want hourly request distribution expressed as a percentage so that I can identify traffic concentration without calculating it manually. Priority: P0.
- As a platform engineer, I want the share of unique User-Agents so that I can assess client diversity and suspicious automation. Priority: P0.
- As a runbook author, I want stable JSON and CSV output so that the result can feed `jq`, spreadsheets, and CI jobs. Priority: P0.
- As a terminal user, I want readable colored tables that disable color when redirected so that interactive and pipeline output both remain clean. Priority: P0.
- As an automation owner, I want distinct exit codes for I/O, usage, parse, and cardinality failures so that a pipeline can respond correctly. Priority: P0.
- As an advanced operator, I want to choose a top-N value so that I can inspect more than the default ten entries. Priority: P1.
- As an nginx operator, I want custom format-template support so that nonstandard deployments can be analyzed. Priority: P1.
- As an archive analyst, I want direct gzip input so that I can skip a decompression pipe. Priority: P2.

## P0 Functional Requirements

### FR-1: Streaming input

The CLI shall read one optional path or stdin (`-` or omitted) line by line without loading the complete input. It shall support the nginx combined and common profiles. Total accounting shall satisfy `total_lines = valid_requests + malformed_lines`.

Acceptance criteria:

- [ ] A regular file and identical stdin content produce identical structured results.
- [ ] A fixture larger than the configured read buffer is processed correctly.
- [ ] No implementation path calls an unbounded whole-file read.
- [ ] An unreadable input produces exit 1 and a stderr diagnostic.

### FR-2: Top client IPs

Count the client IP of every valid request. Return at most 10 by default, ordered by count descending and IP string ascending for ties.

Acceptance criteria:

- [ ] Golden fixtures produce exact counts and deterministic tie ordering.
- [ ] Fewer than ten distinct IPs yields only available entries.
- [ ] Malformed lines do not affect counts.

### FR-3: Top error URLs

Count request targets only where status is 400–599. Return at most 10 by default, ordered by count descending and URL ascending for ties. Preserve the logged path and query; exclude method and protocol.

Acceptance criteria:

- [ ] Both 4xx and 5xx rows are counted; 1xx/2xx/3xx rows are excluded.
- [ ] Query strings remain part of distinct URL keys.
- [ ] Golden fixtures verify deterministic ranking.

### FR-4: Hourly distribution

Count valid requests in buckets `00` through `23` using the hour and offset as logged, without timezone conversion. For every bucket, calculate the percentage with the literal formula `100 × hourly_request_count / total_valid_requests`.

Acceptance criteria:

- [ ] All 24 hours appear in JSON, CSV, and text, including zero-count hours.
- [ ] Counts sum to `total_valid_requests`.
- [ ] Percentages are calculated as percentages, not unscaled fractions, and total approximately 100% subject to display rounding.

### FR-5: Unique User-Agent share

Track exact distinct, nonempty User-Agent strings and calculate `100 × distinct_nonempty_user_agents / valid_requests_with_user_agent`. If the denominator is zero, return `0.0`. Stop with exit 4 if the configured exact-cardinality ceiling would be exceeded.

Acceptance criteria:

- [ ] Duplicate strings count once and case remains significant.
- [ ] Missing/empty User-Agent fields are excluded from numerator and denominator.
- [ ] Crossing the configured limit emits no misleading completed result and exits 4.

### FR-6: Output modes

Default output shall be Rich-colored terminal text when stdout is a TTY. `--json` emits one schema-versioned JSON document. `--csv` emits long-form RFC 4180-compatible rows with columns `metric,rank,key,count,percentage`. JSON and CSV are mutually exclusive and never contain ANSI sequences.

Acceptance criteria:

- [ ] Text snapshots cover TTY color and redirected no-color behavior.
- [ ] JSON parses with a standard parser and matches the schema in `PROJECT_ARCHITECTURE.md`.
- [ ] CSV parses with Python's `csv` module and has the documented header.
- [ ] Diagnostics use stderr and never corrupt structured stdout.

### FR-7: Process contract

All user-visible failures shall map to the complete exit-code contract:

| Code | Required behavior |
|---:|---|
| `0` | Analysis and selected output completed |
| `1` | Input I/O or interruption failure |
| `2` | Invalid CLI usage/configuration |
| `3` | Input read successfully but no valid request parsed |
| `4` | Unique-cardinality exhaustion |

Acceptance criteria:

- [ ] CLI integration tests exercise all codes `0/1/2/3/4`.
- [ ] Expected user failures do not print tracebacks.
- [ ] Usage errors are handled by Click and map to 2.

### FR-8: Performance

On the documented reference laptop and dataset profile, a 1 GB log shall complete in under 30 seconds. The benchmark must include representative successful, error, and malformed lines and record peak memory.

Acceptance criteria:

- [ ] Three benchmark runs are recorded, with the median below 30 seconds.
- [ ] The benchmark metadata states CPU, RAM, storage, OS, and Python patch version.
- [ ] Profiling confirms line parsing/aggregation is streaming and terminal rendering occurs only after aggregation.

## P1 Requirements

- `--top N` accepts 1–1000 and changes both ranked lists while retaining deterministic ordering.
- A future custom format-template parser may map named fields into the same `LogRecord`; it must not weaken the built-in profile behavior.

## P2 Requirements

- Direct `.gz` input may be added if it preserves streaming and the same I/O exit semantics.

## Output Definitions

- **Valid request:** a line matching the chosen profile whose timestamp, request, and status fields parse successfully.
- **Error URL:** the request target of a valid row with integer status from 400 through 599 inclusive.
- **Hourly request distribution:** 24 percentage values based on valid requests and computed by `100 × hourly_request_count / total_valid_requests`.
- **Unique User-Agent share:** percentage of distinct nonempty User-Agent strings over valid rows containing a nonempty User-Agent.
- **Malformed line:** any input line that cannot form a valid `LogRecord`; it is skipped and counted.

## Quality Attributes

| Attribute | Requirement |
|---|---|
| Performance | Representative 1 GB input in <30 s on reference laptop |
| Correctness | Golden fixtures for parsing, counts, formulas, ties, and formats |
| Determinism | Same bytes and options yield the same JSON/CSV ordering |
| Memory safety | Streaming input and explicit exact User-Agent ceiling |
| Privacy | No network access, telemetry, persistence, or raw-log copies |
| Portability | Supported on Python 3.11 through standard pip installation |

## Dependencies and Constraints

The production dependency set is Click and Rich on Python 3.11; domain structures use `dataclasses`. Standard-library `json`, `csv`, `collections`, `datetime`, and buffered I/O provide the remainder. The budget is $0 and the delivery window is one weekend.

## Release Criteria

- All P0 acceptance criteria pass from a clean installation.
- The performance benchmark meets the target with recorded environment metadata.
- CLI help, README examples, structured schemas, and exit codes agree.
- No product code adds a database, API, server, cloud, or Kubernetes dependency.

## Kill Criteria

Pause release and re-scope if Python cannot meet the 1 GB/30 s target after profiling and bounded optimization, if exact User-Agent tracking cannot fail safely at its configured ceiling, or if JSON/CSV cannot maintain deterministic backward-compatible shapes. Any proposed persistent or networked architecture requires a new product decision rather than silent scope expansion.

