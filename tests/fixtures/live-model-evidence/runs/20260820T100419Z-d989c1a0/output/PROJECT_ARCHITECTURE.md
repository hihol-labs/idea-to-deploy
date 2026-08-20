# Project Architecture: nginx-log-insights

## Architecture Summary

The approved design is a single Python 3.11 process with a one-pass pipeline:

```text
file(s) / stdin
      |
      v
line reader -> nginx parser -> validated LogRecord -> streaming Aggregator
                                                   |-> IP counts
                                                   |-> error-URL counts
                                                   |-> 24 hourly buckets
                                                   `-> unique User-Agent set
                                                              |
                                                              v
                                                immutable Report dataclass
                                                              |
                                            text | JSON | CSV renderer -> stdout
```

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the command produces an immediate aggregate, requires no history between runs, and must retain no user log data. An HTTP API is incorrect because the target workflow is local incident analysis and Unix pipelines; a server would introduce lifecycle, security, networking, and deployment burdens without advancing any approved requirement.

One input line is parsed and discarded before the next line. Aggregate counters and exact unique-value sets persist only for the process lifetime. Runtime grows linearly with line count; memory grows with distinct IPs, error URLs, and User-Agents until the configured guard is reached.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Approved and Recommended)

- **Approach:** A modular Python package executes parsing, aggregation, and rendering in one process and one pass.
- **Pros:** Minimal operational surface, no serialization overhead, straightforward profiling, local-only data handling, and one-weekend feasibility.
- **Cons:** Exact high-cardinality sets consume memory; Python throughput must be measured carefully.
- **Best for:** Local analysis of nginx logs up to the specified laptop-scale target.
- **Estimated complexity:** Low.

### Variant B: Unix-stage multiprocess pipeline

- **Approach:** Separate reader/parser, aggregation, and output worker processes communicate over pipes or queues.
- **Pros:** Potential CPU parallelism and isolated stages.
- **Cons:** Ordering and shutdown complexity, serialization overhead, larger test surface, and no evidence that parsing is CPU-bound enough to justify it.
- **Best for:** A later version whose profiler proves a parallelizable bottleneck.
- **Estimated complexity:** Medium.

### Variant C: Embedded analytical database

- **Approach:** Load records into an embedded engine and issue aggregate queries.
- **Pros:** Flexible ad hoc queries and disk-backed grouping.
- **Cons:** Violates the approved no-database constraint, increases I/O and dependencies, retains data, and expands scope beyond four fixed metrics.
- **Best for:** Historical or exploratory analytics, which are outside this product.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the user has pre-approved the obvious single-process architecture and because it most directly satisfies local, stateless, $0, one-weekend delivery. Variants B and C are documented only to make the trade-off replayable; neither is part of the implementation plan.

## CLI Interface

### Commands

The installed console entry point is `nginx-log-insights` with one analysis command:

```text
nginx-log-insights [OPTIONS] [PATHS]...
```

With no `PATHS`, the command reads standard input. A path of `-` also means standard input and may appear at most once. Multiple file paths are read sequentially and aggregated into one report. Directories and URLs are rejected.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit normalized CSV rows; mutually exclusive with `--json` |
| `--log-format` | choice, `combined` | MVP accepts `combined`; reserved values must not be silently guessed |
| `--max-unique` | integer, `5000000` | Maximum distinct values allowed in each guarded IP, error-URL, or User-Agent structure; must be >= 1 |
| `--encoding` | text, `utf-8` | Input decoding; invalid byte sequences are malformed records rather than crashes |
| `--color/--no-color` | tri-state, auto | Default auto-enables color only when stdout is a terminal; structured modes never contain ANSI codes |
| `--version` | flag | Print package version and exit |
| `--help` | flag | Print usage and exit |

### Inputs

- Plain-text nginx access logs from regular local files or stdin.
- MVP grammar: nginx `combined` format, including quoted request and User-Agent fields.
- Timestamps are interpreted from each record's numeric UTC offset. The hourly bucket is the hour encoded in the log timestamp, `00` through `23`; inputs from different offsets are not normalized to a common zone.
- Blank or malformed lines are skipped and counted. A run with no valid records is an input/data failure.
- The implementation never seeks, loads a whole file, or stores raw lines after parsing.

### Outputs

All successful modes contain `total_lines`, `total_valid_requests`, `malformed_lines`, top 10 IPs, top 10 error URLs, 24 hourly buckets, and the unique User-Agent share. Rankings sort by descending count and then ascending key for deterministic ties.

Hourly request distribution is a percentage calculated for every hour with the literal formula `100 × hourly_request_count / total_valid_requests`. The 24 displayed percentages are derived from unrounded counts; presentation rounding must not change stored counts.

Unique User-Agent share is `100 × distinct_nonempty_user_agent_count / total_valid_requests`. The numerator counts exact, non-empty User-Agent strings among valid requests. The report also includes the numerator so consumers can audit the percentage.

Default text output uses Rich tables and color only when allowed by terminal detection. JSON writes one UTF-8 object with this stable shape:

```json
{
  "schema_version": 1,
  "summary": {
    "total_lines": 0,
    "total_valid_requests": 0,
    "malformed_lines": 0
  },
  "top_ips": [{"ip": "192.0.2.1", "count": 10}],
  "top_error_urls": [{"url": "/missing", "count": 3}],
  "hourly_distribution": [{"hour": 0, "count": 2, "percentage": 20.0}],
  "user_agents": {"unique_count": 4, "percentage": 40.0}
}
```

CSV uses columns `schema_version,metric,rank,key,count,percentage`. It emits summary rows, ranked `top_ip` and `top_error_url` rows, 24 `hourly_request` rows, and one `unique_user_agent` row. RFC 4180-compatible quoting is handled by Python's `csv` module. Diagnostics go to stderr; stdout contains only the selected report format.

### Exit Codes

| Code | Meaning | Examples |
|---:|---|---|
| `0` | Success | Report emitted; `--help`; `--version` |
| `1` | Input/data failure | File unreadable, invalid encoding name, no valid requests, read failure |
| `2` | CLI usage failure | Invalid option, conflicting `--json --csv`, invalid `--max-unique` |
| `3` | Unexpected internal failure | Invariant violation or unhandled renderer/aggregation error |
| `4` | Unique-cardinality exhaustion | Any guarded exact distinct-value structure would exceed `--max-unique` |

Click's normal usage errors are normalized to `2`. Expected domain exceptions map once at the command boundary to `1` or `4`; all other exceptions produce a concise stderr diagnostic and `3`. Partial reports are never emitted after failure.

## Components and Responsibilities

| Module | Responsibility | Key types/functions |
|---|---|---|
| `src/nginx_log_insights/cli.py` | Click command, option validation, exception-to-exit mapping | `main()` |
| `src/nginx_log_insights/models.py` | Immutable records and report structures | `LogRecord`, `RankedCount`, `HourlyBucket`, `Report` dataclasses |
| `src/nginx_log_insights/parser.py` | Parse and validate one combined-format line | `parse_combined_line()` |
| `src/nginx_log_insights/inputs.py` | Open files/stdin and yield decoded lines | `iter_lines()` |
| `src/nginx_log_insights/aggregate.py` | Update exact counters and 24 buckets; enforce cardinality | `Aggregator.add()`, `Aggregator.report()` |
| `src/nginx_log_insights/renderers/text.py` | Rich terminal report | `render_text()` |
| `src/nginx_log_insights/renderers/json.py` | Stable JSON schema | `render_json()` |
| `src/nginx_log_insights/renderers/csv.py` | Normalized CSV schema | `render_csv()` |
| `src/nginx_log_insights/errors.py` | Typed domain errors | `InputError`, `CardinalityLimitError` |

Dependencies point inward: renderers and CLI consume domain dataclasses; parser and aggregator do not import Click or Rich. Renderer functions write to an injected text stream for testability.

## Data Model and Streaming State

There are no database tables, migrations, ORM entities, database files, or indexes. The following in-memory structures are the complete ephemeral data model:

| Structure | Type | Fields/content | Constraint |
|---|---|---|---|
| `LogRecord` | frozen dataclass | `ip: str`, `timestamp: datetime`, `method: str`, `url: str`, `status: int`, `user_agent: str` | Created only from a valid parsed line |
| IP counter | `dict[str, int]` or `Counter[str]` | client IP -> request count | Distinct keys <= `max_unique` |
| Error URL counter | `dict[str, int]` or `Counter[str]` | URL -> count for status 400–599 | Distinct keys <= `max_unique` |
| Hour buckets | fixed `list[int]` length 24 | request count by encoded log hour | Index 0–23; O(1) fixed memory |
| User-Agent set | `set[str]` | exact non-empty User-Agent strings | Distinct values <= `max_unique` |
| Run totals | integers | total lines, valid requests, malformed lines | Non-negative; lines = valid + malformed |

The top 10 lists are computed at finalization with `heapq.nsmallest`/`nlargest` or an equivalent `O(U log 10)` deterministic selection, where `U` is distinct keys. The implementation must avoid sorting all keys unless benchmark evidence shows it remains within targets.

## Parsing Contract

- Parse the documented nginx combined format without `str.split()` assumptions across quoted fields.
- Extract the request method and URL; the URL is the request-target token, preserving query strings in MVP rankings.
- Count statuses `400` through `599` as error requests.
- Accept IPv4, IPv6, and non-empty nginx remote-address tokens without DNS lookup.
- Parse timestamps with their explicit numeric offset and validate hour range.
- Treat missing fields, invalid status/timestamp/request quoting, decode errors, and overlong lines as malformed. The line-size safety limit is 1 MiB.
- Never execute, resolve, fetch, or interpret content from a log field.

## Failure, Resource, and Security Boundaries

- Input is untrusted data. Paths are opened read-only; log values are never used as format strings, shell fragments, or filesystem paths.
- Exact cardinality is guarded before insertion. Crossing the ceiling stops the run with code `4`; the tool does not downgrade silently to an approximate answer.
- SIGINT is handled as process interruption and must not emit a partial report; it does not alter the documented application exit-code meanings.
- Diagnostics must not echo complete raw lines, since logs may contain credentials or personal data in URLs and headers.
- Structured output is serialized with standard library encoders to prevent injection and quoting errors.
- No telemetry, network calls, or automatic uploads are permitted.

## Performance and Capacity

The acceptance workload is a reproducibly generated 1 GB combined-format log on a documented laptop profile. The target is wall-clock time under 30 seconds. Verification records Python version, CPU, storage, input size, elapsed time, peak RSS, valid-line count, and output digest.

Design tactics:

- One pass over buffered text input; no raw-record accumulation.
- Compile the parser once, avoid per-line schema allocation beyond `LogRecord`, and profile whether direct aggregate updates can safely bypass an intermediate object.
- Fixed 24-element hour array.
- Delayed rendering after aggregation; no progress UI on stdout.
- Exact dictionaries/sets capped by `--max-unique`; memory behavior is measured at representative and exhaustion cardinalities.

The 30-second goal is a release gate. If Python cannot meet it after measured optimization, the product decision must be revisited rather than quietly relaxing the requirement.

## Configuration and Environment

The CLI is option-driven and requires no environment variables, `.env` file, secrets, or configuration service. Standard process environment such as locale and terminal capability may influence Click/Rich display behavior only; output mode, encoding, and color can be fixed through command-line options for reproducibility.

## Authentication and Authorization

Not applicable. The command runs with the invoking user's local filesystem permissions, opens only user-selected input, and has no identity store, session, token, multi-user boundary, or remote action. Adding authentication would falsely imply a service boundary that does not exist.

## API Contract

There are no HTTP, REST, GraphQL, gRPC, or other network endpoints. The complete public integration boundary is the CLI under `## CLI Interface`, including stdin/stdout/stderr, file inputs, output schemas, and exit codes. Network listeners and clients are forbidden in the MVP.

## Deployment and Distribution

Distribution is a source distribution and universal Python wheel built from `pyproject.toml`, published to a public Python package index at $0 cost when release authorization exists. Users install with `python3.11 -m pip install nginx-log-insights` and invoke the console entry point. A clean virtual environment is the deployment target. Docker, Docker Compose, cloud resources, Kubernetes manifests, servers, and system daemons are intentionally absent because they add no value to a local CLI.

Supported release environments are Python 3.11 on current Linux and macOS; Windows behavior is best-effort until CI coverage is added. Dependency versions use lower bounds plus compatible upper bounds, and the wheel contains no platform-specific binary.

## Testing Strategy

- Parser unit fixtures cover valid IPv4/IPv6, quoting, offsets, 4xx/5xx statuses, malformed lines, decoding, and maximum line length.
- Aggregator unit tests cover exact counts, deterministic ties, all 24 hours, zero buckets, unique User-Agent definition, and each cardinality boundary.
- Renderer golden tests validate text without ANSI, JSON schema/types, CSV quoting/row order, and absence of diagnostics on stdout.
- Click integration tests exercise files, stdin, multiple files, option conflicts, and every exit code `0/1/2/3/4`.
- Packaging smoke tests install the wheel into a clean Python 3.11 virtual environment.
- A benchmark fixture validates 1 GB under 30 seconds and captures peak RSS on the reference laptop.

## Architecture Decision Records

### ADR-001: Single-process one-pass architecture

- **Status:** Accepted by the pre-approved product decision.
- **Decision:** Use Variant A and preserve module boundaries inside one process.
- **Consequences:** Low operational complexity and direct Unix integration; exact unique values require guarded memory.

### ADR-002: Exact metrics with fail-closed cardinality

- **Status:** Accepted.
- **Decision:** Report exact counts and percentages until a configured unique ceiling would be crossed, then exit `4` without partial output.
- **Consequences:** Pipeline consumers never mistake approximation for exact data; adversarial high-cardinality inputs can terminate a run explicitly.

### ADR-003: No persistence or network interface

- **Status:** Accepted by explicit constraint.
- **Decision:** Keep only ephemeral process memory and expose only the CLI contract.
- **Consequences:** Zero service budget and minimal security surface; no historical queries or remote access.

No adversarial or independent architecture review is recorded here. That review is explicitly outside this session and is owned by the external harness.
