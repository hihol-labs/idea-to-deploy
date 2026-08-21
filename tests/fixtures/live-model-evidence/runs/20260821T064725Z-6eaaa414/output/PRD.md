# Product Requirements Document: nginx Stream Analytics CLI

## Product Summary

`nginx-stream-report` is a local Python 3.11 CLI that streams one nginx combined access log from a file or stdin and reports top client IPs, error-associated URLs, hourly traffic share, and unique User-Agent share. Default output is colored terminal text; JSON and CSV provide deterministic pipeline contracts.

## Problem

During incident response and deployment verification, DevOps/SRE engineers often have the access log but not a prepared dashboard. Existing platforms require setup and persistence; ad hoc shell pipelines are hard to validate and reuse. Users need a fast, local, privacy-preserving answer with stable automation semantics.

## Goals and Success Measures

- Process a 1 GB grammar-valid input in under 30 seconds on a documented laptop baseline.
- Retain only bounded aggregate state, never the full input.
- Produce four correct views from one pass.
- Provide stable Rich text, JSON, CSV, stderr, and exit-code behavior.
- Install through pip and run on Python 3.11 at $0 infrastructure cost.

## Non-Goals

- Authentication or multi-user access.
- Database, history, search index, or stored dashboard.
- HTTP API, server, cloud service, or Kubernetes deployment.
- Log shipping, alerting, tail-follow mode, or distributed ingestion.
- Universal nginx format autodetection in MVP.

## User Stories

### US-01: Analyze a local log file

As an on-call SRE, I want to pass an nginx access-log path so that I can get a useful incident summary without deploying services.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `nginx-stream-report access.log` reads the file line-by-line and emits one complete terminal report.
- [ ] The process does not retain raw records or create a database/temp copy.
- [ ] A missing or unreadable file emits a concise stderr diagnostic, no report, and exits 1.

### US-02: Analyze piped logs

As a platform engineer, I want to pipe a log into stdin so that I can compose analysis with local Unix tools.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Omitting `INPUT` or passing `-` consumes stdin.
- [ ] Output data is written only to stdout and diagnostics only to stderr.
- [ ] A normal downstream closed pipe terminates quietly.

### US-03: Identify dominant clients and failing URLs

As an SRE, I want the top 10 IPs and the top 10 URL targets associated with 4xx/5xx responses so that I can spot traffic concentration and failure hotspots.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Top IP counts include every valid request.
- [ ] Error-URL counts include statuses 400–599 and exclude all other statuses.
- [ ] Each list contains at most 10 items sorted by count descending, then key ascending for ties.
- [ ] URL keys preserve the logged request target, including query strings.

### US-04: Understand temporal and client diversity

As a DevOps engineer, I want hourly distribution and unique User-Agent share so that I can understand when traffic occurs and how diverse clients are.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Output contains all 24 local log-time buckets from `00` through `23` with counts.
- [ ] Each hourly percentage uses exactly `100 × hourly_request_count / total_valid_requests`, is not an unscaled fraction, and is displayed to two decimal places.
- [ ] Unique User-Agent count uses literal field values and the share is `(unique_count × 100) / total_valid_requests` to two decimals.
- [ ] Percentages are derived only from valid requests.

### US-05: Read a safe colored terminal report

As an on-call engineer, I want readable colored tables by default so that I can scan the result quickly.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] A capable TTY receives four clearly labeled Rich sections plus valid/malformed totals.
- [ ] Redirected output is ANSI-free by default, and `--no-color` always disables color.
- [ ] Log-derived values are treated as text and cannot inject Rich markup.

### US-06: Consume JSON or CSV in a pipeline

As a platform engineer, I want `--json` and `--csv` so that automation can consume the same report without scraping text.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `--json` emits one valid object matching the architecture schema and no ANSI bytes.
- [ ] `--csv` emits a parseable table with header `section,key,count,percentage` and no ANSI bytes.
- [ ] Both formats contain metric values equivalent to the text report.
- [ ] Passing `--json --csv` emits Click usage help to stderr and exits 2.
- [ ] A failure emits no partial JSON or CSV document.

### US-07: Distinguish bad data from bad invocation

As an automation author, I want stable exit codes and malformed-line accounting so that my pipeline can react correctly.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Exit codes are: 0 success, 1 operational I/O/decoding failure, 2 usage error, 3 zero valid requests, and 4 unique-cardinality exhaustion.
- [ ] Malformed lines are skipped and counted when at least one valid record exists.
- [ ] Completed input with zero valid requests emits no report and exits 3.
- [ ] Crossing an exact unique-key ceiling emits no report and exits 4 rather than returning approximate data.

### US-08: Read a rotated gzip log

As an SRE, I want to read a `.gz` access log directly so that I do not need a separate decompression command.

**Priority:** P1 (Should)

**Acceptance criteria:**

- [ ] Explicit gzip input streams through decompression without writing a temporary expanded file.
- [ ] Corrupt gzip data follows exit code 1.

### US-09: Change the ranking size

As an analyst, I want to choose a top-N value so that I can inspect more or fewer ranked entries.

**Priority:** P2 (Could)

**Acceptance criteria:**

- [ ] A future positive `--top` option applies consistently to IP and error-URL lists.
- [ ] The default remains 10.

## Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept one combined-log file, stdin by omission, or stdin by `-` |
| FR-02 | Parse IP, timestamp/offset, target, status, and User-Agent; count malformed lines |
| FR-03 | Produce deterministic top-10 IP and 4xx/5xx URL lists |
| FR-04 | Produce 24 hourly counts and percentage shares using the specified percentage formula |
| FR-05 | Produce exact unique User-Agent count and percentage share |
| FR-06 | Render safe Rich text by default and stable JSON/CSV on request |
| FR-07 | Enforce a positive configurable unique-cardinality ceiling and exit 4 on exhaustion |
| FR-08 | Implement the complete 0/1/2/3/4 exit-code contract |
| FR-09 | Expose `--help`, `--version`, `--encoding`, and color controls |

### P1 — Should ship after MVP

| ID | Requirement |
|---|---|
| FR-10 | Stream gzip-compressed file input without temporary expansion |

### P2 — Could ship later

| ID | Requirement |
|---|---|
| FR-11 | Configurable top-N with default 10 |
| FR-12 | Explicit named parser profiles for additional nginx formats |

## Output Requirements

The authoritative schemas and CLI option table are in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. Text output may evolve cosmetically within semantic versioning, but labels and metric meanings remain clear. JSON property names and CSV headers are compatibility contracts. Numeric JSON percentages are numbers, not percent-sign strings.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | 1 GB under 30 seconds on documented laptop baseline | End-to-end benchmark with recorded environment |
| NFR-02 | Streaming memory independent of line count except bounded unique keys | Peak-RSS benchmark plus code review of input path |
| NFR-03 | Python 3.11 and pip installability | Clean virtualenv wheel-install smoke test |
| NFR-04 | At least 90% coverage for parser/aggregation/rendering | pytest coverage gate |
| NFR-05 | No network calls, telemetry, persistence, or raw-log copy | Dependency/source inspection and integration tests |
| NFR-06 | Deterministic output for the same records | Golden tests including tie cases |
| NFR-07 | Untrusted log fields cannot control terminal markup | Adversarial rendering tests |

## Analytics Definitions

- `total_lines`: every physical input line read.
- `total_valid_requests`: lines matching the supported grammar and field constraints.
- `malformed_lines`: `total_lines - total_valid_requests`.
- Top IP: count of valid requests grouped by literal parsed client IP.
- Top error URL: count of valid requests with status 400–599 grouped by literal request target.
- Hourly request distribution: 24 percentages using `100 × hourly_request_count / total_valid_requests`.
- Unique User-Agent share: `100 × unique_user_agent_count / total_valid_requests`.

## Dependencies and Assumptions

- Input follows nginx combined format; custom formats are not silently guessed.
- The documented benchmark laptop has enough memory for the configured cardinality ceiling.
- Click and Rich versions compatible with Python 3.11 are available during installation.
- The CLI has only the local permissions of the invoking user.

## Release Criteria

- All P0 acceptance criteria and clean-install tests pass.
- Text, JSON, and CSV agree on a shared golden fixture.
- Tests explicitly observe exit codes 0, 1, 2, 3, and 4.
- The benchmark meets the target and records enough context to reproduce it.
- No P1/P2 feature or Won't item blocks the MVP.

## Kill Criteria

Pause release and redesign if the 1 GB / 30 second target remains unmet after profiling and bounded optimization, if exact unique-cardinality exhaustion cannot be detected before unsafe memory growth, if malformed input can produce plausible but incorrect metrics, or if machine output cannot remain stable without buffering raw records. A database, HTTP service, or cloud backend is not an acceptable workaround within this product.
