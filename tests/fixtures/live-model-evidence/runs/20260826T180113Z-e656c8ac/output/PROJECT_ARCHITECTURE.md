# Project Architecture: Nginx Log Insights CLI

## Architecture Goals and Constraints

- Run locally under Python 3.11 and install through pip.
- Read a file or standard input exactly once; do not persist log records.
- Produce exact required metrics for valid records while bounding failure behavior for unique cardinality.
- Process a representative 1 GB log in under 30 seconds on a documented laptop benchmark.
- Use Click, Rich, and dataclasses; remain free and open source.
- Exclude authentication, databases, HTTP APIs, servers, cloud services, and Kubernetes.

The controlling decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the requested aggregates can be computed in one pass and persisted events would add I/O, schema, cleanup, privacy, and operational costs without improving the one-shot result. An HTTP API is incorrect because the users and pipeline consumers already have a file/stdin process boundary; a server would introduce lifecycle, concurrency, authentication, port, and deployment concerns that contradict the local one-weekend product.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended)

- **Approach:** One process connects input, parsing, aggregation, immutable result construction, and one selected renderer.
- **Pros:** Minimal overhead, simple installation, deterministic lifecycle, straightforward profiling, no intermediate storage.
- **Cons:** One CPU core performs parsing; exact User-Agent cardinality uses memory proportional to distinct values until the guard limit.
- **Best for:** The approved local CLI, 1 GB target, and one-weekend delivery.
- **Estimated complexity:** Low.

### Variant B: Multiprocessing map/reduce

- **Approach:** Split seekable files into chunks, aggregate in workers, and merge partial counters.
- **Pros:** Can use multiple CPU cores for very large seekable files.
- **Cons:** Complicates line boundaries, stdin support, deterministic errors, memory use, and packaging; merge overhead may erase gains at 1 GB.
- **Best for:** A later release with measured CPU-bound workloads well beyond the current target.
- **Estimated complexity:** Medium.

### Variant C: External sort/database-backed analysis

- **Approach:** Persist or sort parsed fields before querying aggregates.
- **Pros:** Supports repeated ad hoc queries and datasets larger than memory.
- **Cons:** Violates stateless and no-database constraints, adds disk I/O and cleanup, and cannot justify its operational surface for four fixed reports.
- **Best for:** A different historical analytics product, not this project.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because it is the only variant aligned with the pre-approved architecture, stdin behavior, $0 budget, performance target, and delivery window. Variant B remains a measurement-driven future option; Variant C is rejected.

## System Context and Data Flow

```text
nginx log file or stdin
        |
        v
 buffered text iterator
        |
        v
 combined-log parser ---- invalid record ----> diagnostics/strict failure
        |
        v
 one-pass aggregator
   | IP Counter
   | error-URL Counter
   | 24 hourly buckets
   | exact User-Agent set + hard limit
        |
        v
 Report dataclass + run metadata
        |
        +---- terminal renderer (Rich, default)
        +---- JSON renderer
        +---- CSV long-form renderer
```

Only the selected renderer runs. Diagnostic text is written to stderr; report data is written to stdout. No raw log line is written to disk by the application.

## Module and Package Design

```text
pyproject.toml
src/nginx_insights/
  __init__.py
  cli.py                 # Click command, validation, exit mapping
  models.py              # ParsedRecord, Report, RankedItem, RunMetadata dataclasses
  parser.py              # compiled combined-log parser and timestamp normalization
  aggregate.py           # one-pass counters, top-k extraction, cardinality guard
  errors.py              # typed domain failures and exit-code mapping
  renderers/
    __init__.py
    terminal.py          # Rich tables and color policy
    json_output.py       # stable JSON object
    csv_output.py        # stable long-form rows
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_renderers.py
  test_performance.py
```

### Component contracts

| Component | Input | Output | Key invariant |
|---|---|---|---|
| Input iterator | path or stdin | text lines with 1-based line number | Reads incrementally; does not call `read()` for the whole input |
| Parser | one line | `ParsedRecord` or structured parse error | Extracts IP, timestamp hour, request URL, status, User-Agent |
| Aggregator | parsed records | `Report` | Each valid request increments exactly one IP and hour bucket |
| Error URL counter | status + URL | counter update | Only status 400–599 contributes |
| Cardinality guard | User-Agent | exact distinct set or exception | Never grows beyond `max_unique_user_agents` |
| Renderer | `Report` | stdout bytes/text | Does not alter metric values or ordering |

Tie ordering for both top-10 lists is count descending, then key ascending by Unicode code point, ensuring stable output across runs.

## Data Model

There are no database tables. The complete in-memory dataclass model is:

| Dataclass | Field | Type | Meaning |
|---|---|---|---|
| `ParsedRecord` | `ip` | `str` | Client address as logged |
|  | `hour` | `int` | Local timestamp hour, 0–23 |
|  | `url` | `str` | Request-target token, preserved as logged |
|  | `status` | `int` | HTTP response status |
|  | `user_agent` | `str` | User-Agent field, including `-` if present |
| `RankedItem` | `key` | `str` | IP or URL |
|  | `count` | `int` | Matching valid requests |
|  | `rank` | `int` | 1-based rank after deterministic sorting |
| `HourlyBucket` | `hour` | `int` | Hour 0–23 |
|  | `request_count` | `int` | Valid requests in the hour |
|  | `percentage` | `float` | Hourly share rounded only at serialization |
| `RunMetadata` | `total_lines` | `int` | All input lines seen |
|  | `total_valid_requests` | `int` | Successfully parsed lines |
|  | `invalid_lines` | `int` | Rejected lines |
|  | `unique_user_agents` | `int` | Exact distinct User-Agent count |
| `Report` | `top_ips` | `tuple[RankedItem, ...]` | Up to ten IPs |
|  | `top_error_urls` | `tuple[RankedItem, ...]` | Up to ten URLs with 4xx/5xx responses |
|  | `hourly_distribution` | `tuple[HourlyBucket, ...]` | Exactly 24 buckets for non-empty valid input |
|  | `unique_user_agent_share` | `float` | Percentage of distinct User-Agent values per valid request |
|  | `metadata` | `RunMetadata` | Processing totals |

Hourly request distribution is a percentage defined by the literal formula `100 × hourly_request_count / total_valid_requests`. The unique User-Agent share is `100 × unique_user_agents / total_valid_requests`. Percentages retain full numeric precision internally and serialize rounded to two decimal places; their underlying counts are always included in JSON and CSV.

The `set[str]` of User-Agent values is the only data structure with input-dependent cardinality. Before insertion, the aggregator checks the configured maximum; exceeding it raises `UniqueCardinalityExhausted` and maps to exit code 4. This preserves exactness rather than silently switching to an approximation.

## CLI Interface

### Command

```text
nginx-insights [OPTIONS] [PATH]
```

With no `PATH`, input is read from stdin. `PATH` may name one readable regular file. The MVP accepts nginx combined access-log lines encoded as UTF-8; invalid UTF-8 follows the same policy as malformed lines.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | false | Emit RFC 4180 long-form CSV; mutually exclusive with `--json` |
| `--strict/--no-strict` | `--no-strict` | In strict mode, the first malformed line terminates with code 3; otherwise malformed lines are counted and skipped |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive hard limit for exact User-Agent cardinality; breach exits 4 |
| `--color/--no-color` | auto | Applies only to terminal output; auto enables color only on a capable TTY |
| `--version` | n/a | Print version and exit 0 |
| `--help` | n/a | Print usage and exit 0 |

### Inputs

- A positional UTF-8 nginx combined-log file, or stdin when omitted.
- Each valid line must provide remote address, local timestamp with zone, quoted request, 3-digit status, and quoted User-Agent.
- Request parsing uses the request-target token between method and protocol. A missing or structurally invalid target makes the line invalid.
- Empty input or input with zero valid requests is a data error and exits 3.

### Outputs

Default terminal output contains four sections in this order: Top 10 IPs, Top 10 4xx/5xx URLs, Hourly Request Distribution, and Unique User-Agent Share. It ends with metadata for total, valid, and invalid lines. Color never changes the text values.

JSON output is one object with schema version, both ranked arrays, 24 hourly objects, a unique-User-Agent object, and metadata:

```json
{
  "schema_version": 1,
  "top_ips": [{"rank": 1, "ip": "192.0.2.1", "count": 12}],
  "top_error_urls": [{"rank": 1, "url": "/missing", "count": 4}],
  "hourly_distribution": [{"hour": 0, "request_count": 2, "percentage": 12.5}],
  "unique_user_agents": {"count": 3, "share_percentage": 18.75},
  "metadata": {"total_lines": 16, "total_valid_requests": 16, "invalid_lines": 0}
}
```

CSV output has the fixed header `section,rank,key,count,percentage`. Rows use sections `top_ip`, `top_error_url`, `hour`, `unique_user_agents`, and `metadata`; unused cells are empty. The hour key is zero-padded `00`–`23`. CSV never contains ANSI escapes.

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Success, including valid input with no 4xx/5xx records |
| 1 | Runtime or input I/O failure, including unreadable file or broken processing stream |
| 2 | Click usage/configuration error, including conflicting formats or invalid option values |
| 3 | Input data failure: strict parse rejection or zero valid requests |
| 4 | Unique-cardinality exhaustion: the configured exact User-Agent limit would be exceeded |

Failures write a concise message to stderr and do not emit a report document to stdout.

## Error Handling and Observability

Typed exceptions (`InputError`, `ParseDataError`, and `UniqueCardinalityExhausted`) cross the domain/CLI boundary. The Click adapter owns exit-code mapping and sanitizes diagnostics so a malformed log line is not echoed in full; line number and reason are sufficient. Unexpected exceptions map to code 1 without a traceback unless a future debug flag is explicitly designed.

The product emits no telemetry. Run metadata in successful output provides the audit trail needed to judge skipped input. Tests may inspect timing and peak resident memory, but production execution does not phone home.

## Performance and Resource Strategy

- Use buffered sequential I/O and a compiled parser pattern.
- Update `collections.Counter` objects and a fixed 24-element integer list in place.
- Construct dataclasses only for parsed records and the final report; profile whether record allocation needs reduction before optimizing.
- Use `Counter.most_common()` only after ingestion, followed by explicit tie normalization.
- Cap exact User-Agent set growth through the CLI limit and exit 4 rather than risking swapping.
- Benchmark a deterministic 1 GB fixture outside the repository and report wall time, Python version, CPU, storage, and peak RSS.

Acceptance requires median wall time under 30 seconds across three warm-cache runs on the declared reference laptop. The test suite also includes a smaller continuously runnable performance smoke test; the 1 GB gate is a release check.

## Security and Privacy

Logs may contain IP addresses, URLs, and User-Agent strings. Processing remains local, raw lines are not persisted, and diagnostics avoid reproducing full records. Terminal escaping must prevent Rich markup or control sequences from log-derived keys from affecting the terminal. JSON and CSV use standard library serializers with correct escaping. The CLI never executes or dereferences URL content.

## Packaging and Deployment

Deployment is a Python wheel and source distribution published for pip installation. `pyproject.toml` declares Python `>=3.11,<4`, runtime dependencies on compatible Click and Rich releases, and a console script named `nginx-insights`. There is no Docker image, compose file, daemon, infrastructure-as-code, database migration, or server deployment.

Configuration is entirely command-line based; there are no required environment variables or secrets. Standard locale and terminal variables may influence Rich's capability detection but do not alter report values.

## Architecture Decision Record (ADR)

### ADR-001: Single-process stateless pipeline

- **Status:** Accepted and pre-approved.
- **Decision:** Use Variant A and keep parsing, aggregation, and rendering in one process.
- **Consequences:** Minimal operational surface and one-pass stdin support; performance must be achieved through efficient parsing rather than horizontal concurrency.

### ADR-002: Exact cardinality with a hard guard

- **Status:** Accepted.
- **Decision:** Store exact User-Agent strings until the configured limit; terminate with code 4 before exceeding it.
- **Consequences:** Results remain explainable and exact. Inputs above the supported cardinality boundary fail explicitly rather than yielding an approximation.

### ADR-003: Fixed combined-log grammar for MVP

- **Status:** Accepted.
- **Decision:** Support nginx combined format only in the MVP.
- **Consequences:** The parser is fast and testable; custom log formats are deferred and invalid input is visible in metadata or strict failure.

### Alternatives considered and rejected

- GoAccess integration was rejected because the product needs an independent pip-installed schema contract, not a wrapper around another executable.
- Multiprocessing was deferred until profiling demonstrates necessity.
- SQLite and other databases were rejected because every required result is computable in one pass.
- REST, GraphQL, and gRPC were rejected because there is no server use case.
- Docker and Kubernetes were rejected because pip is the required deployment boundary.
