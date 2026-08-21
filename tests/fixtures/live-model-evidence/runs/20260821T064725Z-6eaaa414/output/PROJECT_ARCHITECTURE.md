# Project Architecture: nginx Stream Analytics CLI

## Context and Constraints

The product is a local Python 3.11 executable for DevOps/SRE analysis of nginx combined access logs. It must be pip-installable, cost $0, fit a one-weekend delivery, and process 1 GB in under 30 seconds on a documented laptop baseline. It has no authentication, database, HTTP API, server, cloud, or Kubernetes component.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the requested results can be derived in one pass, persistence would add disk I/O, lifecycle, privacy, and schema-management costs, and users already possess the source log. An HTTP API is incorrect because this is a local diagnostic and pipeline utility: a listener, protocol, auth boundary, and service operations would add risk without improving the approved use cases.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** one Python process reads each line, parses it, updates bounded aggregators, finalizes one report, and renders it.
- **Pros:** lowest operational complexity, no intermediate storage, composable, straightforward performance profiling.
- **Cons:** one machine and one core-bound parsing path; exact unique cardinality must be bounded.
- **Best for:** local incident triage and shell pipelines up to the stated 1 GB target.
- **Estimated complexity:** Low.

### Variant B: Multi-process chunk aggregation

- **Approach:** split seekable files into byte ranges, parse in workers, merge partial counters.
- **Pros:** can use multiple CPU cores for large regular files.
- **Cons:** complicated line-boundary handling, unavailable for stdin, higher memory, merge overhead, and weekend risk.
- **Best for:** later performance work only if measurement proves parsing is CPU-bound.
- **Estimated complexity:** Medium.

### Variant C: SQLite-backed batch analysis

- **Approach:** ingest normalized rows and query aggregates.
- **Pros:** flexible ad hoc follow-up queries and persisted history.
- **Cons:** violates stateless/no-database scope, duplicates the source log, increases I/O and privacy exposure.
- **Best for:** a different historical-analysis product.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the product decisions already require a single-process, stateless local CLI. Variant B is retained only as a measured future optimization path; Variant C is rejected.

## System Context and Data Flow

```text
nginx log file or stdin
          |
          v
  Input reader (text, UTF-8 policy)
          |
          v
 CombinedLogParser -> ParseResult / malformed counter
          |
          v
 StreamingAggregator
   | IP Counter
   | error-URL Counter (status 400..599)
   | 24 hourly buckets
   | exact User-Agent set with hard ceiling
          |
          v
       Report dataclass
      /        |        \
 Rich text   JSON       CSV
```

Only aggregate state is retained. Memory is `O(unique_ips + unique_error_urls + unique_user_agents + 24)` up to the configured hard cardinality ceiling; it is independent of total line count. The ceiling applies before memory becomes unsafe. Exact unique User-Agent share is therefore either exact or the process exits with code 4—never silently approximate.

## Component Design

| Module | Responsibility | Main contracts |
|---|---|---|
| `src/nginx_stream_analytics/cli.py` | Click command, option validation, renderer selection, exit mapping | `main(...) -> None` via Click |
| `src/nginx_stream_analytics/input.py` | Open file or stdin as a non-owning/owning text stream | `open_input(path) -> TextIO` |
| `src/nginx_stream_analytics/parser.py` | Parse one combined-log line without retaining it | `parse_line(str) -> LogRecord | None` |
| `src/nginx_stream_analytics/models.py` | Immutable dataclasses for record, counters, rows, report | `LogRecord`, `RankedItem`, `HourlyShare`, `Report` |
| `src/nginx_stream_analytics/aggregate.py` | Update counters, enforce cardinality ceiling, finalize deterministic top 10 | `Aggregator.consume(record)`, `finalize()` |
| `src/nginx_stream_analytics/render_text.py` | Rich terminal tables and diagnostics | `render(report, console)` |
| `src/nginx_stream_analytics/render_json.py` | Stable JSON document | `render(report, stream)` |
| `src/nginx_stream_analytics/render_csv.py` | Stable long-form CSV rows | `render(report, stream)` |
| `src/nginx_stream_analytics/errors.py` | Typed operational failures and exit-code mapping | exception classes |

`models.py` is dependency-free. Parser and aggregator depend only on models/errors. Renderers consume the finalized report and never reparse input. CLI is the composition root.

## Data Contracts

### Input grammar

MVP accepts nginx combined log lines equivalent to:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

Required parsed fields are client IP string, timestamp with numeric offset, request target, integer status, and User-Agent string. The URL metric uses the request target exactly as logged, including query string; the request method/protocol do not form part of the key. Statuses 400–599 contribute to the error-URL counter. Blank or nonmatching lines are malformed.

Timestamps are bucketed by the hour (`00` through `23`) as represented in each log record's timestamp; the MVP does not normalize across offsets. Hourly request distribution is a percentage calculated with the literal formula `100 × hourly_request_count / total_valid_requests`. Empty hours are included as `0.0`; output rounds percentages to two decimal places while retaining integer counts.

Unique User-Agent share is `(unique_user_agent_count × 100) / total_valid_requests`, reported to two decimals. The metric counts the literal User-Agent field, including `"-"` as one value. A report with zero valid requests is not emitted as success.

### Deterministic ranking

Top lists are sorted by descending count, then lexicographically ascending key for ties, and truncated to 10 items. This makes terminal, JSON, CSV, and tests reproducible.

### Internal dataclasses

| Dataclass | Fields |
|---|---|
| `LogRecord` | `ip: str`, `timestamp: datetime`, `target: str`, `status: int`, `user_agent: str` |
| `RankedItem` | `value: str`, `count: int` |
| `HourlyShare` | `hour: int`, `request_count: int`, `percentage: float` |
| `Report` | `total_lines: int`, `total_valid_requests: int`, `malformed_lines: int`, `top_ips: tuple[RankedItem, ...]`, `top_error_urls: tuple[RankedItem, ...]`, `hourly_distribution: tuple[HourlyShare, ...]`, `unique_user_agent_count: int`, `unique_user_agent_share_percent: float` |

There are no database tables or migrations. These transient dataclasses are the complete application data model and are discarded on process exit.

## CLI Interface

### Command

```text
nginx-stream-report [OPTIONS] [INPUT]
```

`INPUT` is an optional path to a regular nginx access-log file. Omit it or pass `-` to read stdin. Exactly one input stream is processed per invocation.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one JSON object; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit one CSV document; mutually exclusive with `--json` |
| `--max-unique INTEGER` | positive integer, `2000000` | Hard ceiling for each exact unique-key collection; exhaustion returns 4 |
| `--encoding TEXT` | string, `utf-8` | Input decoder; decoding is strict |
| `--color / --no-color` | auto by default | Controls Rich color for text only; JSON/CSV never contain ANSI |
| `--version` | flag | Print package version and exit 0 |
| `--help` | flag | Print usage and exit 0 |

`--json` and `--csv` are rejected together by Click with exit code 2. Diagnostics go to stderr; report data goes to stdout. No partial JSON or CSV is written on failure: aggregation completes successfully before rendering begins.

### Output contracts

Default text contains four labeled sections plus totals/malformed-line diagnostics. Color is enabled only for a capable terminal unless explicitly overridden.

JSON uses this stable top-level shape:

```json
{
  "summary": {"total_lines": 0, "total_valid_requests": 0, "malformed_lines": 0},
  "top_ips": [{"ip": "string", "count": 0}],
  "top_error_urls": [{"url": "string", "count": 0}],
  "hourly_distribution": [{"hour": "00", "request_count": 0, "percentage": 0.0}],
  "user_agents": {"unique_count": 0, "unique_share_percent": 0.0}
}
```

CSV is a single long-form table with header `section,key,count,percentage`. Ranking rows use sections `top_ip` and `top_error_url`; hourly rows use `hour`; the User-Agent summary uses `unique_user_agents`. Inapplicable numeric cells are empty. RFC 4180 quoting is delegated to Python's `csv` module.

### Exit-code contract

| Code | Meaning |
|---:|---|
| 0 | Successful report, or successful `--help`/`--version` |
| 1 | Operational input/output failure: missing/unreadable file, decoding error, broken read, or write failure other than normal closed-pipe handling |
| 2 | CLI usage error: invalid option/value or conflicting output flags |
| 3 | Data error: input completed but contained zero valid requests |
| 4 | Unique-cardinality exhaustion: an IP, error-URL, or User-Agent exact-cardinality ceiling would be exceeded |

A downstream closed pipe is handled quietly as successful termination when no other error occurred, matching normal Unix pipeline behavior.

## Failure and Malformed-Data Policy

Malformed lines are skipped and counted. If at least one valid request exists, a complete report is emitted with the malformed count and exit code 0. If none exists, stdout remains empty, a diagnostic is written to stderr, and exit code 3 is returned. Resource exhaustion never degrades to approximate results; it returns code 4. Python tracebacks are hidden for expected operational errors.

## Performance and Resource Design

- Read line-by-line using buffered text I/O; never call `read()` or `readlines()` for the dataset.
- Compile the parsing expression once and avoid creating unused field objects.
- Keep 24 fixed hourly counters and hash-based exact counters/sets for other metrics.
- Use `heapq.nsmallest`/bounded selection or equivalent deterministic selection at finalization rather than sorting the input.
- Benchmark end-to-end wall-clock time, peak RSS, valid-line count, and bytes processed on a generated-but-declared performance fixture that matches the grammar.
- The acceptance baseline records CPU, RAM, OS, storage, Python patch version, input bytes, and command so “under 30 seconds” is reproducible.

## Security and Privacy

Logs may contain personal data in IPs, URLs, referers, and User-Agents. Processing stays local, no telemetry or network call exists, and no temporary copy is created. Output may still be sensitive and inherits the destination's permissions. Input is treated as untrusted data: no shell execution, format-string interpretation, HTML rendering, or Rich markup parsing is applied to log values. Cardinality limits mitigate memory denial of service.

Authentication is intentionally absent: the process has exactly the invoking user's local file and stdout/stderr permissions. Adding an application credential would not create a meaningful boundary for a local CLI.

## Packaging and Deployment

The package uses `pyproject.toml` with a console-script entry point named `nginx-stream-report`, declares Python `>=3.11,<4`, and depends on compatible Click and Rich versions. Deployment means installing into a virtual environment or isolated CLI environment with pip. There is no container, Docker Compose file, daemon, hosted deployment target, cloud resource, or Kubernetes manifest because none is needed for a local process.

## Configuration

All behavior is explicit CLI input. No required environment variables or configuration files exist. Locale and terminal capability may influence Rich presentation only; JSON and CSV remain stable UTF-8 outputs.

## Architecture Decision Records

### ADR-001: Single-process stateless aggregation

- **Status:** Accepted by the user-provided project constraints.
- **Decision:** Select Variant A and retain only bounded aggregate state.
- **Consequences:** Minimal operation and privacy exposure; exact high-cardinality inputs can terminate with code 4.

### ADR-002: CLI-only interaction

- **Status:** Accepted by the user-provided project constraints.
- **Decision:** Use Click with text, JSON, and CSV renderers; expose no API or server.
- **Consequences:** Excellent local composability; remote/multi-user access is out of scope.

### ADR-003: Exact metrics with fail-closed cardinality

- **Status:** Accepted for MVP.
- **Decision:** Never silently replace exact results with approximation; stop with exit code 4 at the limit.
- **Consequences:** Results are trustworthy; highly adversarial logs may require rerunning with a safely chosen larger ceiling on capable hardware.

No adversarial or independent architecture review was run in this blueprint session; that review is reserved for the external harness.
