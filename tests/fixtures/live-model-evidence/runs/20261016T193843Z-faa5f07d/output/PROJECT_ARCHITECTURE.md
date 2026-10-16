# Project Architecture: nginx-log-top

## Context and Goals

The product is a local Python 3.11 CLI that converts a stream of nginx access-log lines into four aggregate reports. It must process a representative 1 GB log in less than 30 seconds on the documented reference laptop, remain useful in Unix pipelines, and require no runtime service.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the reports need only one-pass counters, persistence would add I/O and operations without improving the requested result, and the source log remains the system of record. An HTTP API is incorrect because the users are local operators and scripts, while a server would add lifecycle, security, authentication, and deployment concerns explicitly outside scope.

## Architecture Variants

### Variant A: Single-process exact stream aggregation (Recommended)

- **Approach:** parse each line once and update in-memory counters and an exact bounded set of User-Agent strings.
- **Pros:** simplest behavior, deterministic metrics, natural stdin support, low operational cost.
- **Cons:** exact cardinality can consume memory; one CPU core bounds throughput.
- **Best for:** the approved one-weekend local CLI and 1 GB target.
- **Estimated complexity:** Low.

### Variant B: Multi-process chunk aggregation

- **Approach:** seekable files are split across workers; partial counters and unique sets are merged.
- **Pros:** can use multiple cores for large static files.
- **Cons:** does not naturally support stdin/follow mode, boundary handling is error-prone, merging exact sets can spike memory, and complexity threatens the delivery window.
- **Best for:** a future measured performance shortfall on multi-gigabyte seekable files.
- **Estimated complexity:** Medium.

### Variant C: Persistent indexed analysis

- **Approach:** ingest records into SQLite or a search system before querying.
- **Pros:** repeated ad-hoc queries and history become possible.
- **Cons:** violates the no-database constraint, duplicates the source of truth, adds storage and ingestion overhead.
- **Best for:** a different product requiring retained exploration.
- **Estimated complexity:** High relative to this MVP.

### Recommendation

Variant A is selected because it satisfies every approved feature with the fewest moving parts. Variant B is retained only as a performance contingency backed by profiling; Variant C is rejected.

## System Structure

```text
file(s) / stdin / followed file
            |
       Input iterator
            |
    nginx line parser -------- malformed counter + bounded diagnostics
            |
      AggregateState
      /    |     |     \
 IP count errors hours unique UAs
      \    |     |     /
        Report model
       /      |      \
 Rich text   JSON    CSV
```

The process holds no raw-line collection. A parsed `AccessRecord` is consumed and discarded before the next line. Counters are proportional to distinct IPs and error URLs; the exact User-Agent set is bounded by `--max-unique-user-agents` and fails explicitly on exhaustion.

## Component Boundaries

| Module | Responsibility | Must not do |
|---|---|---|
| `cli.py` | Click command, option validation, stream lifecycle, exit mapping | Parse log syntax or format reports |
| `inputs.py` | Open text files/stdin, deterministic file order, follow behavior | Aggregate records |
| `parser.py` | Convert a supported line into `AccessRecord` or structured parse failure | Print or terminate the process |
| `models.py` | Dataclasses for records, counters, and report values | Perform I/O |
| `aggregate.py` | One-pass updates, top-10 sorting, percentages, cardinality cap | Know output format |
| `renderers/text.py` | Rich terminal report | Emit machine formats |
| `renderers/json.py` | Versioned JSON document | Add ANSI escapes |
| `renderers/csv.py` | Rectangular CSV rows | Add ANSI escapes |
| `errors.py` | Typed domain errors and exit-code mapping | Catch programmer errors silently |

## Data Model

No database tables or migrations exist. Runtime dataclasses are:

| Dataclass | Fields | Notes |
|---|---|---|
| `AccessRecord` | `remote_addr: str`, `timestamp: datetime`, `request_target: str`, `status: int`, `user_agent: str` | Immutable normalized fields needed by aggregation |
| `AggregateState` | `valid: int`, `malformed: int`, `ip_counts: Counter[str]`, `error_url_counts: Counter[str]`, `hour_counts: list[int]`, `unique_user_agents: set[str]` | `hour_counts` always has 24 slots |
| `RankedItem` | `rank: int`, `key: str`, `count: int`, `percentage: float` | Common top-list output item |
| `Report` | `schema_version: int`, totals, two ranked lists, hourly buckets, `unique_user_agents: int`, `unique_user_agent_share: float` | Renderer-neutral immutable result |

Top-list ties sort by descending count and then ascending key, ensuring reproducible JSON/CSV. URL aggregation uses the request target as logged, including its query string; method and protocol are excluded. Error URLs include status codes 400–599.

Hourly request distribution has 24 buckets and uses the hour encoded in each valid log timestamp. Each percentage is exactly `100 × hourly_request_count / total_valid_requests`; if there are no valid requests, no report is produced and exit code 3 applies. Unique User-Agent share is `100 × distinct_nonempty_user_agents / total_valid_requests`; `"-"` is treated as empty, not as a unique agent.

## Parsing Contract

MVP input accepts nginx combined-log records and the common-log subset where User-Agent is absent. Parsing operates on one physical UTF-8 line at a time with `errors="replace"`; a malformed line increments `malformed` and may produce a bounded stderr diagnostic in verbose mode. Numeric status must be 100–599 and timestamps must match nginx's bracketed timestamp syntax.

If at least one record is valid, malformed lines do not prevent a report. If every nonempty line is malformed, processing ends with exit code 3. File-open/read errors use code 2. Broken-pipe termination is quiet and successful when the downstream pipeline closes normally.

## CLI Interface

### Commands

```text
nginx-log-top [OPTIONS] [PATH]...
nginx-log-top --help
nginx-log-top --version
```

With no `PATH`, input is stdin. One or more paths are read sequentially in argument order. `-` explicitly denotes stdin and may appear at most once. `--follow` requires exactly one regular file and continues waiting for appended complete lines until interrupted.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit one JSON object to stdout |
| `--csv` | false | Emit one RFC 4180-compatible CSV table to stdout |
| `--follow`, `-f` | false | Follow one growing regular file; incompatible with stdin and multiple paths |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive hard cap for the exact distinct set |
| `--color [auto|always|never]` | `auto` | Applies only to terminal text |
| `--verbose` | false | Emit bounded malformed-line diagnostics to stderr |
| `--version` | n/a | Print version and exit 0 |
| `--help` | n/a | Print help and exit 0 |

`--json` and `--csv` are mutually exclusive. Invalid option combinations are Click usage failures.

### Inputs

- UTF-8 text from stdin or local file paths; undecodable bytes are replaced.
- Nginx combined format and common-format subset as defined under Parsing Contract.
- No network locations, compressed files, database handles, or configuration service in the MVP.

### Outputs

- Default: four Rich tables plus valid/malformed totals on stdout. ANSI styling follows `--color` and terminal detection.
- JSON: one UTF-8 object with `schema_version: 1`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`.
- CSV: header `section,rank,key,count,percentage`; summary and metric rows share this schema. Empty rank/percentage fields are empty strings.
- Diagnostics: plain text on stderr. JSON/CSV stdout never contains ANSI or diagnostics.

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Report completed successfully, or a downstream pipe closed normally |
| 1 | Unexpected internal error |
| 2 | CLI usage, path, permission, or input I/O error |
| 3 | Input contained no valid records |
| 4 | unique-cardinality exhaustion: the configured distinct User-Agent cap would be exceeded |

This `0/1/2/3/4` contract is stable and applies to text, JSON, and CSV modes.

## Performance and Resource Budget

- Read through buffered text I/O; never call `read()` for an entire input.
- Parse once and update counters in O(1) expected time per valid line.
- Select top ten with `heapq.nlargest` or `Counter.most_common`, then apply deterministic tie ordering.
- Keep diagnostic samples bounded (default maximum 20 when verbose).
- Measure a representative 1 GB fixture after a warm-up run using wall-clock time and peak RSS; acceptance is less than 30 seconds on the recorded laptop specification.
- Treat the User-Agent cap as a correctness boundary: never silently switch to approximate results.

## Security and Privacy

The process makes no network calls and creates no persistent data. Log content is untrusted data: terminal output is escaped by Rich, CSV uses the standard library writer, and JSON uses the standard encoder. Input values are never evaluated or interpolated into shell commands. Diagnostics avoid echoing full log lines by default because URLs and User-Agents may contain sensitive values.

## Packaging and Deployment

The deployment target is a user's local Python 3.11 environment. A PEP 517 package defined by `pyproject.toml` exposes the `nginx-log-top` console script and is installable with `pip install .` or, after release, `pip install nginx-log-top`. Runtime dependencies are Click and Rich; no Docker image, daemon, cloud resource, or Kubernetes manifest is supplied.

There are no environment variables required for correct operation. CLI options are the only runtime configuration, keeping runs replayable.

## Architecture Decision Records

### ADR-001: Exact single-process streaming

- **Status:** Accepted by product brief.
- **Decision:** Use Variant A with counters and a bounded exact User-Agent set.
- **Reason:** It is the shortest path to deterministic answers within a weekend and supports stdin naturally.
- **Consequence:** Unique-cardinality exhaustion is explicit code 4; parallelism is deferred unless a benchmark proves it necessary.

### ADR-002: No persistence or service boundary

- **Status:** Accepted by product brief.
- **Decision:** Keep logs as the source of truth; provide only a local CLI.
- **Reason:** Both persistence and a server add cost and risk without serving the requested workflows.
- **Consequence:** Historical comparison and remote querying are out of scope.

### ADR-003: Stable machine schemas

- **Status:** Accepted.
- **Decision:** Version JSON and keep CSV rectangular with deterministic ordering.
- **Reason:** Shell and CI consumers require reproducible output.
- **Consequence:** Breaking schema changes require a new schema version and migration note.

No Devil's Advocate review is recorded here; that independent review is intentionally performed by the external harness in a separate session.

