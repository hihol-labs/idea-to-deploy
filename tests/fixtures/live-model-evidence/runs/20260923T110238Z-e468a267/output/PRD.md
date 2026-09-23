# Product Requirements Document: nginx-stream-insights

## 1. Product Summary

`nginx-stream-insights` lets DevOps and SRE users summarize nginx access logs locally in one streaming pass. It reports the top 10 client IPs, top 10 URLs by combined 4xx/5xx count, a 24-hour request distribution, and the share of unique non-missing User-Agent values. Default output is colored terminal text; JSON and CSV are stable pipeline formats.

## User Stories

- As a SRE, I want to stream a large nginx log through one local command so that I can triage traffic without deploying infrastructure.
  - **Priority:** P0
  - **Acceptance criteria:**
    - [ ] A file or stdin is processed line by line without loading the corpus into memory.
    - [ ] A representative 1 GB fixture completes in under 30 seconds on the recorded reference laptop.
    - [ ] No database, HTTP service, network call, or durable application state is created.

- As an on-call engineer, I want the top 10 client IPs and top 10 failing URLs so that I can identify noisy sources and error hotspots.
  - **Priority:** P0
  - **Acceptance criteria:**
    - [ ] IP counts include all valid requests and return at most 10 rows.
    - [ ] URL counts include statuses 400 through 599 only and return at most 10 rows.
    - [ ] Ties are ordered by ascending key after descending count.

- As a capacity engineer, I want request volume expressed by hour so that I can see daily traffic concentration.
  - **Priority:** P0
  - **Acceptance criteria:**
    - [ ] Output contains all hours 00 through 23, including zero-count hours.
    - [ ] Each percentage uses `100 × hourly_request_count / total_valid_requests`.
    - [ ] The timestamp's logged hour and offset are parsed without conversion to the machine's local timezone.

- As a platform engineer, I want exact User-Agent diversity with a resource guard so that successful results remain trustworthy on unusual logs.
  - **Priority:** P0
  - **Acceptance criteria:**
    - [ ] The unique count excludes the missing marker `-`.
    - [ ] Share is `100 × unique_non_missing_user_agent_count / total_valid_requests`.
    - [ ] Crossing the configured exact-cardinality limit emits no report and exits `4`.

- As an automation author, I want JSON and CSV output with fixed exit codes so that scripts can consume results without scraping terminal text.
  - **Priority:** P0
  - **Acceptance criteria:**
    - [ ] `--json` emits one parseable schema-versioned object and `--csv` emits the documented normalized columns.
    - [ ] Machine stdout contains no ANSI codes, progress, or diagnostics.
    - [ ] Exit codes are exactly `0/1/2/3/4` with the meanings defined in this PRD.

- As an operator with archived logs, I want to read `.gz` files directly so that I do not need a separate decompression step.
  - **Priority:** P1
  - **Acceptance criteria:**
    - [ ] A `.gz` path is decompressed as a stream, not expanded to disk or memory.
    - [ ] Corrupt/truncated gzip data exits `3` without partial stdout.

- As a power user, I want configurable top-N and custom nginx log formats so that the tool can cover specialized installations.
  - **Priority:** P2
  - **Acceptance criteria:**
    - [ ] These capabilities remain deferred until the fixed v1 format and top-10 contract meet launch gates.

## 3. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept one or more uncompressed file paths or stdin as one logical dataset and read them lazily. Reject mixing `-` with paths. |
| FR-02 | Return at most 10 IPs ranked by valid-request count, with deterministic tie ordering. |
| FR-03 | Return at most 10 request targets ranked by the count of statuses 400–599, with query strings retained. |
| FR-04 | Return 24 hourly count/percentage buckets using `100 × hourly_request_count / total_valid_requests`. |
| FR-05 | Return exact distinct non-missing User-Agent count and its percentage of valid requests; enforce a positive configurable distinct-value limit. |
| FR-06 | Render colored Rich terminal output by default, with automatic capability detection and `--no-color`. |
| FR-07 | Render schema-versioned JSON with summary, top lists, 24 hourly buckets, and User-Agent metrics. |
| FR-08 | Render CSV columns `metric,rank,key,count,percentage` with safe quoting and formula-injection mitigation. |
| FR-09 | Apply the complete exit-code contract: `0` success; `1` unexpected runtime/output failure; `2` usage/configuration error; `3` input/read/decode failure or zero valid records; `4` unique-cardinality exhaustion. |
| FR-10 | Count malformed lines; continue when at least one line is valid, report diagnostics on stderr, and fail with `3` when none are valid. |
| FR-11 | Parse documented nginx combined-log timestamps, status, request target, IP, and User-Agent without executing or interpreting field content. |
| FR-12 | Install through pip on Python 3.11 and expose the `nginx-insights` console command. |

### P1 — Should ship after P0 is stable

| ID | Requirement |
|---|---|
| FR-13 | Stream `.gz` path inputs and map corrupt/truncated streams to exit `3`. |

### P2 — Could ship later

| ID | Requirement |
|---|---|
| FR-14 | Permit an explicit top-N value while retaining 10 as the default. |
| FR-15 | Support selected named nginx `log_format` profiles or an explicit format description. |

## 4. Input Contract

The P0 grammar is nginx combined log format:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

The parser accepts IPv4/IPv6 address tokens and any request method, extracts the request target from the quoted request field, validates status 100–599, and parses the numeric timezone offset. A missing request (`"-"`), invalid timestamp/status, blank line, or structurally incomplete record is malformed. Custom formats are not guessed.

## 5. Output Contract

Terminal output prioritizes scanability and may use labels, tables, and color. JSON uses `schema_version: 1` and the structure defined in `PROJECT_ARCHITECTURE.md`. CSV always uses `metric,rank,key,count,percentage`. Percentages are calculated once from integer counts and serialized as numbers; presentation rounding does not change counts or denominators.

Warnings and diagnostics go only to stderr. If processing cannot produce a valid complete result, stdout is empty. Results are deterministic for identical input, options, package version, and Python version.

## 6. Non-Functional Requirements

| ID | Requirement | Acceptance measure |
|---|---|---|
| NFR-01 | Throughput | Representative 1 GB file completes in <30 seconds on documented reference laptop |
| NFR-02 | Streaming | Raw lines and per-request records are not retained after aggregation |
| NFR-03 | Memory safety | User-Agent distinct values stop at configured limit with exit `4`; benchmark records peak RSS |
| NFR-04 | Correctness | Golden fixtures produce exact counts, deterministic ranks, and correct 24-hour percentages |
| NFR-05 | Portability | Clean pip install and tests pass on Python 3.11 |
| NFR-06 | Pipeline safety | JSON/CSV stdout is parseable, UTF-8, ANSI-free, and separate from stderr |
| NFR-07 | Security | No network, subprocess, dynamic code, persistence, or terminal-markup interpretation of log data |
| NFR-08 | Maintainability | At least 90% line coverage for package code and typed component boundaries |

## 7. Scope Exclusions

The v1 product has no authentication, database, HTTP API, server mode, cloud dependency, Kubernetes, dashboard, stored history, tail/follow mode, remote log retrieval, approximate metrics, enrichment/geolocation, or generalized query language. It does not replace centralized observability platforms.

## 8. Success Metrics and Release Gate

Release requires all P0 acceptance criteria, all golden/contract tests, a clean-wheel smoke test in all three output modes, and a recorded passing 1 GB benchmark. At least one fixture must include malformed lines, non-ASCII URLs/User-Agents, tied rankings, all status-class boundaries, missing User-Agent, and multiple timezone offsets.

## 9. Kill Criteria

Pause release and make a separately approved scope or technology decision when any condition holds:

- A profiled, contract-correct single-process implementation cannot meet 1 GB in under 30 seconds on the reference laptop.
- Exact metrics exceed acceptable laptop memory on representative data even with the User-Agent guard.
- Real target logs cannot be handled without a general-purpose `log_format` parser.
- Stable JSON/CSV contracts cannot be maintained without breaking the terminal-oriented design.

Do not resolve a kill criterion by silently approximating results or introducing forbidden infrastructure.

## 10. Traceability

Architecture and schemas are in `PROJECT_ARCHITECTURE.md`; the eight implementation steps and their verification commands are in `IMPLEMENTATION_PLAN.md`; strategic priorities and RICE rationale are in `STRATEGIC_PLAN.md`; execution prompts are in `CLAUDE_CODE_GUIDE.md`.
