# Project Architecture: nginx-insights

## Context and Decision

The product is a local Python 3.11 CLI that incrementally consumes nginx access-log lines and emits a bounded report. The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema lifecycle, disk amplification, cleanup, and operational state when the desired answer can be computed in one pass. An HTTP API would add a listening service, authentication and network threat surface without improving the local incident-triage workflow. In-memory counters are sufficient, guarded by an explicit unique-cardinality limit; the process exits after emitting one report and retains nothing.

## Goals and Non-Goals

Goals are deterministic parsing, one-pass aggregation, useful terminal output, stable pipeline schemas, and measured processing of a 1 GB representative log in under 30 seconds on a documented laptop.

Non-goals are authentication, persistence, an HTTP server/API, cloud deployment, Kubernetes, dashboards, arbitrary query language, distributed processing, and a general nginx configuration parser.

## Architecture Variants

### Variant A: Single-process streaming CLI (selected)

- **Approach:** one Python process iterates over input, parses each line into a dataclass, updates counters, then renders once.
- **Pros:** smallest operational surface, deterministic behavior, no IPC or persistence, fits one-weekend scope.
- **Cons:** CPU work is limited to one core; exact counters consume memory proportional to distinct keys.
- **Best for:** local bounded files and piped streams up to the validated envelope.
- **Estimated complexity:** Low.

### Variant B: Local analytical database

- **Approach:** ingest records into SQLite or DuckDB and query summaries.
- **Pros:** flexible follow-up queries and spill-to-disk behavior.
- **Cons:** violates the approved no-database constraint, adds ingestion/storage cost and cleanup, and is unnecessary for fixed reports.
- **Best for:** exploratory multi-query analysis, which is outside this product.
- **Estimated complexity:** Medium.

### Variant C: Multiprocess parser/aggregator

- **Approach:** split seekable files into chunks, parse in workers, and merge partial counters.
- **Pros:** may use multiple cores on very large files.
- **Cons:** complicates stdin, chunk boundaries, error ordering, memory bounds, and cross-platform behavior.
- **Best for:** workloads shown by benchmarks to exceed a single core after MVP profiling.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the product decisions pre-approve the obvious single-process design, it supports both files and stdin uniformly, and it minimizes delivery and operational risk. Variants B and C are recorded only as rejected alternatives, not deferred MVP commitments.

## System Structure

```text
file path / stdin
       |
       v
 Input iterator  --> line number / read errors
       |
       v
 nginx parser    --> ParseResult(valid record | rejected reason)
       |
       v
 Aggregator      --> Summary dataclasses + cardinality guard
       |
       v
 terminal | JSON | CSV renderer
       |
       v
 stdout data; stderr diagnostics; process exit code
```

Suggested package layout:

```text
pyproject.toml
src/nginx_insights/
  __init__.py
  cli.py
  parser.py
  models.py
  aggregate.py
  output.py
  errors.py
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_output.py
  test_cli.py
  test_performance.py
```

Responsibilities are intentionally separated: `cli.py` owns arguments and process boundaries; `parser.py` owns syntax; `aggregate.py` owns metric semantics and limits; `output.py` owns serialization only.

## CLI Interface

### Command

```text
nginx-insights [OPTIONS] [INPUT]
```

`INPUT` is a plain-text nginx access-log path. If omitted or `-`, input is read from stdin. Exactly one report is produced at EOF. The MVP does not tail, decompress, open URLs, or traverse directories.

### Options

| Option | Meaning | Default/validation |
|---|---|---|
| `--json` | Emit one JSON document | Mutually exclusive with `--csv` |
| `--csv` | Emit normalized CSV rows | Mutually exclusive with `--json` |
| `--top INTEGER` | Number of rows in ranked sections | `10`; integer `>=1` |
| `--strict` | Stop at the first malformed non-empty line | Off; otherwise reject and continue |
| `--max-unique INTEGER` | Maximum distinct values retained in any guarded dimension | `1000000`; integer `>=1` |
| `--encoding TEXT` | Input text encoding | `utf-8`; decoding is strict |
| `--no-color` | Disable ANSI styling in terminal mode | Color otherwise follows terminal capability |
| `--version` | Print version and exit | No input opened |
| `--help` | Print usage and exit | No input opened |

### Input contract

The MVP accepts nginx common and combined access-log lines. Required parsed fields are remote address, timestamp (including offset), request target, status, and User-Agent when present. A common-format line has no User-Agent and contributes no User-Agent value but remains a valid request. The request target is the raw path/query token from the request line; method and protocol are parsed but not used for ranking.

Blank lines are ignored and are neither valid nor rejected. In default mode, malformed non-empty lines are counted as rejected and processing continues. In `--strict` mode, the first malformed line is a data error. Unreadable input or invalid text encoding is an input error. No entire input record is retained after its counters are updated.

### Output contract

Terminal mode prints a summary and four Rich tables. JSON and CSV write data only to stdout and never contain ANSI escapes; diagnostics go to stderr.

The JSON schema has top-level keys `schema_version`, `source`, `total_valid_requests`, `rejected_lines`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `unique_user_agents`. Ranked rows contain `rank`, the dimension value, and `count`. Hour rows contain `hour`, `request_count`, and `percentage`. `unique_user_agents` contains `unique_count`, `requests_with_user_agent`, and `share_percentage`.

CSV uses the header `schema_version,section,rank,key,count,percentage`. Rows are distinguished by `section`: `summary`, `top_ip`, `top_error_url`, `hour`, and `unique_user_agents`. Non-applicable cells are empty. CSV follows RFC 4180 quoting through Python's `csv` module.

Ranking is count descending, then key ascending for deterministic ties. All 24 hours (`00` through `23`) are emitted, including zero-count buckets. Percentages are rounded to two decimal places for display/serialization; counts remain authoritative.

### Exit-code contract

| Code | Meaning |
|---:|---|
| `0` | Report completed successfully; rejected lines may be nonzero in non-strict mode |
| `1` | Runtime/internal failure or output write failure |
| `2` | CLI usage error, including invalid or conflicting options |
| `3` | Input/data error: cannot read/decode input, strict malformed line, or zero valid requests |
| `4` | Unique-cardinality exhaustion: a guarded distinct-key set would exceed `--max-unique` |

No partial JSON or CSV document is emitted on codes 2, 3, or 4. The CLI validates/open-checks first and aggregates before serializing. If stdout fails mid-write, code 1 is returned and the downstream consumer must discard partial bytes.

## Domain Model and Metric Semantics

`AccessRecord` is a frozen dataclass with `remote_addr: str`, `timestamp: datetime`, `request_target: str`, `status: int`, and `user_agent: str | None`. `Summary` contains totals plus immutable report rows. Parse failures carry line number and a bounded reason, never the full potentially sensitive log line by default.

- **Top IPs:** count `remote_addr` across all valid requests.
- **Top error URLs:** count `request_target` only where `400 <= status <= 599`.
- **Hourly distribution:** bucket by the hour (`00`–`23`) written in the nginx timestamp, preserving the log's represented local hour. Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- **Unique User-Agent share:** `100 × unique_nonempty_user_agent_count / total_valid_requests`. Common-format requests and combined-format `"-"` User-Agents remain in the denominator but do not add a distinct value. With zero valid requests, no percentages are invented and exit code 3 is returned.

The aggregator guards distinct IP, error-URL, and User-Agent maps independently with `--max-unique`. Crossing any guard stops processing with code 4. Exact results are preferred over hidden sampling or approximate sketches.

## Parsing Design

Compile the parser once. Parse quoted request and User-Agent fields without splitting naïvely on spaces. Validate the timestamp using the nginx form `%d/%b/%Y:%H:%M:%S %z`, status as an integer from 100 through 599, and request as either the nginx `"-"` sentinel or a three-token request line. A `"-"` request has target `-` and is still valid if all other required fields are valid.

Malformed reasons are stable categories such as `field_count`, `timestamp`, `request`, and `status`; this supports tests without exposing raw logs. The parser supports IPv4, IPv6, and non-IP remote-address tokens because nginx may log upstream-derived values; ranking does not perform DNS or network validation.

## State and Storage

There are no database tables, migrations, files written by the application, caches, or retained sessions. State exists only as counters and scalar totals inside one process and is released at exit. This deliberate absence replaces the generic database schema portion of the template: no table or field design is applicable.

Memory complexity is `O(U_ip + U_error_url + U_user_agent + 24)`, bounded by the configured cardinality guard. Input size does not otherwise determine memory use.

## API, Authentication, and Network Boundaries

There are no HTTP endpoints, request/response bodies, listening sockets, authentication flows, accounts, or authorization roles. The operating-system user's permission to read `INPUT` is the only access boundary. This deliberate absence replaces the generic endpoint/auth template because exposing an API would contradict the approved product.

The tool performs no outbound network calls and no telemetry. Log content is untrusted data, never a command, template, or terminal markup; Rich rendering must escape/control text rather than interpret it.

## Configuration and Environment

There are no required environment variables or `.env` file. Behavior is controlled by CLI options so runs are explicit and reproducible. Standard locale or terminal variables may affect the host terminal, but they are not application configuration and must not change JSON/CSV encoding or schema.

## Packaging and Deployment

`pyproject.toml` declares Python `>=3.11,<4`, runtime dependencies on Click and Rich, and a console entry point `nginx-insights = nginx_insights.cli:main`. A wheel and source distribution are the deployment artifacts; installation is `python -m pip install nginx-insights` or from a local wheel.

There is no Docker image, Compose file, server process, cloud target, or Kubernetes manifest. Docker would add startup and filesystem-mount friction to a local pip-installable utility without improving its guarantees.

## Performance and Observability

The hot path performs one line read, one parse, and bounded counter updates. It does not construct a list of records, repeatedly compile patterns, sort before EOF, or log per valid line. Only final distinct-key maps are sorted with `heapq.nsmallest`/equivalent deterministic top-k selection where profiling supports it.

Performance acceptance uses a deterministic 1 GB representative corpus containing IPv4/IPv6, mixed status classes, escaped/long agents, and a controlled malformed fraction. Record wall-clock time and peak RSS on a named laptop with caches and command documented. A progress bar is not part of MVP because it adds overhead and pollutes stderr in automation.

Diagnostics at completion state source, valid count, and rejected count in terminal mode. Structured modes carry those counts in data. Errors are concise, carry no traceback unless a developer/debug path is explicitly added later, and do not echo full sensitive lines.

## Testing Strategy

- Parser unit tests cover common/combined, IPv4/IPv6, quoting, `-`, malformed timestamps/status/request, and encoding boundaries.
- Aggregation tests cover all metrics, 24 hours, exact formula/rounding, deterministic ties, missing User-Agent, and each cardinality guard.
- Renderer golden/structural tests validate ANSI behavior, JSON schema/types, CSV quoting/header, and stdout/stderr separation.
- Click integration tests exercise stdin/file equivalence, options, broken/missing input, empty data, and every exit code 0/1/2/3/4.
- The performance test is separately marked and records the 1 GB benchmark; ordinary CI uses a smaller representative corpus.

## Architecture Decision Records

### ADR-001: Select a one-process iterator pipeline

**Status:** Accepted by product brief. **Decision:** Variant A. **Consequences:** simplest pip/stdin workflow and deterministic behavior; one-core throughput and cardinality-bounded exact maps define the operating envelope.

### ADR-002: Reject database and HTTP API

**Status:** Accepted by product brief. **Decision:** retain no durable data and expose only the CLI. **Consequences:** zero service operations and $0 infrastructure; repeated questions require rerunning the command.

### ADR-003: Fail rather than approximate on excessive cardinality

**Status:** Accepted. **Decision:** stop with exit code 4 before exceeding a distinct-key ceiling. **Consequences:** pipeline callers can distinguish capacity failure, and reported top values/share remain exact.

No adversarial review is recorded here; that review is intentionally delegated to the external benchmark session.

