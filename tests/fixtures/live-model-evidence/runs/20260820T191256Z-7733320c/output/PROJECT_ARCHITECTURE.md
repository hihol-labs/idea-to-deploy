# Project Architecture: Nginx Stream Analytics CLI

## Architecture Drivers

- Local Python 3.11 CLI for DevOps/SRE users, installable with pip.
- Single pass over file or stdin; target 1 GB in under 30 seconds on a documented laptop.
- Four exact metrics: top-10 IPs, top-10 URLs with 4xx/5xx responses, hourly request percentages, and unique User-Agent share.
- Colored terminal output plus deterministic JSON and CSV.
- $0 budget and one-weekend scope.
- No authentication, database, HTTP API, server, cloud, or Kubernetes.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended and approved)

- **Approach:** one Python process performs input → parse → aggregate → render. It retains counters and bounded distinct sets, never raw records.
- **Pros:** simplest packaging and operation, low I/O overhead, private by default, easy stdin composition.
- **Cons:** exact aggregation memory grows with unique keys until the cardinality guardrail; one CPU core is the initial performance envelope.
- **Best for:** local incident triage and CI/shell pipelines.
- **Estimated complexity:** Low.

### Variant B: Shell pipeline around specialized commands

- **Approach:** compose `awk`, `sort`, and `uniq` per metric.
- **Pros:** no Python package; familiar Unix primitives.
- **Cons:** repeated scans/sorts, quoting and format fragility, inconsistent JSON/CSV, poor cross-platform tests.
- **Best for:** one-off exploration with a known fixed format.
- **Estimated complexity:** Low initially, Medium to maintain.

### Variant C: Persistent analytics stack

- **Approach:** ingest logs into GoAccess or Logstash/Elastic/Kibana and query dashboards.
- **Pros:** history, broad queries, visualization.
- **Cons:** violates local/stateless/$0 operational goals; materially exceeds a weekend.
- **Best for:** durable multi-host observability, which is outside this product.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the product decisions already favor a single-process, private, one-shot CLI. The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is wrong because the required report is derived once from the supplied stream, persistence creates lifecycle and privacy work, and no cross-run query is required. An HTTP API is wrong because the users already work in terminals and pipelines, there is no remote consumer or multi-user state, and a server would add authentication, ports, deployment, and operational failure modes without product value.

## Component Model

```text
file path ─┐
           ├─> InputReader ─> NginxParser ─> Aggregator ─> Report ─┬─> RichRenderer
stdin ─────┘                  │                 │                   ├─> JsonRenderer
                              └─ malformed      └─ guardrails       └─> CsvRenderer
                                   count              │
                                                      └─ exit 4 on exhaustion
```

Suggested package boundaries:

| Path | Responsibility |
|---|---|
| `src/nginx_stream_analytics/cli.py` | Click command, option validation, exception-to-exit mapping |
| `src/nginx_stream_analytics/input.py` | Binary buffered file/stdin iteration |
| `src/nginx_stream_analytics/parser.py` | Supported nginx combined-format parser |
| `src/nginx_stream_analytics/models.py` | `LogRecord`, `Report`, ranked-item dataclasses |
| `src/nginx_stream_analytics/aggregate.py` | Counters, top-10 selection, hourly percentages, cardinality guard |
| `src/nginx_stream_analytics/render/terminal.py` | Rich terminal output |
| `src/nginx_stream_analytics/render/json.py` | Stable JSON document |
| `src/nginx_stream_analytics/render/csv.py` | Stable long-form CSV rows |
| `tests/` | unit, CLI, golden, integration, and performance tests |

Dependencies point inward: CLI and renderers depend on dataclass contracts; the parser and aggregator do not depend on Click or Rich.

## Data and Streaming Model

Each valid line yields a transient `LogRecord(client_ip: str, timestamp: datetime, request_target: str, status: int, user_agent: str)`. The aggregator retains:

- `Counter[str]` for IP request counts;
- `Counter[str]` for request targets whose status is 400–599;
- fixed 24-element integer array for hours 00–23;
- `set[str]` for distinct non-empty User-Agent values, capped by a declared cardinality limit;
- scalar totals for input, valid, malformed, error, and non-empty User-Agent-bearing requests.

No raw line or record remains after aggregation. Rankings sort by count descending and key ascending, making ties deterministic. URL grouping uses the parsed request target exactly as logged (path plus query string when present); documentation may later add a normalization option, but MVP does not silently normalize.

Hourly request distribution is a percentage for each hour, using the literal formula `100 × hourly_request_count / total_valid_requests`. When `total_valid_requests` is zero, no report is emitted and exit code 3 is returned; division by zero is never represented.

Unique User-Agent share is `100 × distinct_non_empty_user_agents / total_valid_requests`. This intentionally measures distinct agent strings as a share of valid requests, may be far below 100%, and treats a missing/empty User-Agent as non-unique input while retaining it in the denominator. If the distinct set would exceed the documented ceiling, processing stops with exit code 4 rather than producing an approximate or incomplete metric.

### Database Contract

There is no database and therefore no tables, fields, migrations, indexes, credentials, or persistence lifecycle. The in-memory structures above are runtime implementation details, not tables. This is an explicit exception to generic web-project templates and follows the approved stateless constraint.

### HTTP API and Authentication Contract

There are no HTTP endpoints, request/response bodies, listening ports, sessions, tokens, users, roles, or authentication flow. Local filesystem permissions and shell pipeline controls are the trust boundary. Adding authentication would imply a server or protected persistent resource that does not exist.

## CLI Interface

### Command

```text
nginx-log-report [OPTIONS] [INPUT]
```

`INPUT` is an optional path to one nginx access-log file. Omitted or `-` means stdin. Exactly one source is processed per invocation.

### Options

| Option | Contract |
|---|---|
| `--json` | Emit one UTF-8 JSON object to stdout; mutually exclusive with `--csv` |
| `--csv` | Emit UTF-8 RFC 4180-compatible long-form CSV to stdout; mutually exclusive with `--json` |
| `--no-color` | Disable ANSI styling in terminal mode; color is already disabled when stdout is not a TTY |
| `--max-unique INTEGER` | Positive distinct-key safety ceiling; applies before adding a new distinct IP, URL, or User-Agent and has a documented safe default |
| `--version` | Print version and exit 0 |
| `--help` | Print usage and exit 0 |

### Inputs

- UTF-8/ASCII-compatible nginx combined access-log lines, read as buffered bytes and decoded per parsed field.
- A line is valid only when client IP, timestamp/hour, quoted request, integer status, and quoted User-Agent can be parsed.
- Blank and malformed lines increment `malformed_lines` and do not enter any numerator or denominator.
- File and stdin are never read twice and are never written.

### Outputs

- **Terminal:** four labeled Rich tables plus valid/malformed totals. Rankings contain at most 10 rows; hourly output contains hours 00–23 with count and percentage.
- **JSON:** object keys `schema_version`, `source`, `totals`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `unique_user_agents`. Ranked entries contain `rank`, key, and `count`; percentage fields are JSON numbers rounded only for presentation.
- **CSV:** header `metric,rank,key,count,percentage`; multiple row types share one stream. Totals use metric-specific keys. Hours are keys `00` through `23`.
- Data goes to stdout. Diagnostics go to stderr. JSON and CSV contain no ANSI escapes and are deterministic for identical input.

### Exit Codes

| Code | Meaning |
|---:|---|
| 0 | Report generated successfully; malformed lines may have been skipped and are disclosed |
| 1 | Input or I/O failure, including nonexistent/unreadable file or interrupted read |
| 2 | CLI usage error, including conflicting formats or invalid option values |
| 3 | No valid nginx records were found, so report metrics are undefined |
| 4 | Unique-cardinality exhaustion: adding another distinct tracked IP, error URL, or User-Agent would exceed `--max-unique` |

No partial JSON/CSV report is written for exit 1, 2, 3, or 4. Render only after successful full aggregation.

## Performance and Capacity

- Complexity is O(n + u log 10), effectively O(n), where n is lines and u is distinct ranked keys.
- Input is buffered and processed once; report sorting uses `heapq.nsmallest`/equivalent bounded selection rather than sorting raw records.
- Memory is O(unique IPs + unique error URLs + unique User-Agents), bounded operationally by `--max-unique`; fixed hourly storage is O(1).
- The benchmark fixture must be generated locally without committing 1 GB. Record file size, line count, wall time, peak RSS, CPU, Python version, and laptop CPU/RAM.
- The release gate is <30 seconds for 1 GB on that declared reference laptop. No universal hardware claim is implied.

## Error Handling and Observability

Expected domain exceptions (`InputError`, `NoValidRecords`, `CardinalityExhausted`) map once at the CLI boundary. Unexpected exceptions produce a concise non-secret diagnostic and exit 1; tracebacks are reserved for a developer-only environment during testing, not a public flag in MVP. Metrics in the report disclose valid and malformed line counts. The tool has no telemetry or network egress.

## Security and Privacy

Logs may contain IPs, URLs, query values, and User-Agent strings. The tool does not transmit or persist them. Output escaping must prevent log text from being interpreted as Rich markup or terminal control sequences. Input paths are opened read-only, decompression and shell commands are not invoked, and CSV cells use the standard library writer to prevent structural injection (consumer spreadsheet formula interpretation is documented). Resource exhaustion is controlled through line-length and unique-cardinality limits.

## Packaging and Deployment

The deployment unit is a pip-installable wheel with a `nginx-log-report` console script and `Requires-Python >=3.11`. Runtime dependencies are Click and Rich; dataclasses and CSV/JSON support come from the standard library. There is no Dockerfile, Compose topology, daemon, cloud deployment, or Kubernetes manifest. A clean virtual-environment install and `pipx` installation are the supported deployment paths.

There are no required environment variables. Locale, terminal width, and TTY capability may affect Rich layout but never JSON/CSV semantics. Reproducible tests pin development dependencies separately from the minimal runtime declaration.

## Architecture Decision Record (ADR)

### ADR-001: One process and exact bounded aggregation

- **Status:** Accepted by pre-approved product decision.
- **Decision:** Use the recommended single-process pipeline, exact counts, deterministic top-10 output, and fail-closed cardinality ceiling.
- **Alternatives rejected:** shell composition is fragile; persistent analytics introduces forbidden infrastructure; approximate cardinality would weaken the explicit unique-share contract.
- **Consequences:** simple operation and reliable schemas; high-cardinality inputs can intentionally terminate with exit 4.

### Review status

No Devil's Advocate or independent architecture review was run in this blueprint session. The external harness owns that review and its artifact; this document does not substitute an inline self-critique or a reviewer verdict.

## Test Strategy

- Parser table tests cover valid combined lines, IPv4/IPv6, escaped quotes, missing fields, malformed status/timestamp, and long lines.
- Aggregator tests cover rankings, deterministic ties, only 400–599 URL inclusion, all 24 hourly percentages, empty User-Agent handling, and guardrail boundaries.
- CLI tests cover file/stdin, mutually exclusive flags, stdout/stderr separation, no ANSI in machine formats, and every exit code 0/1/2/3/4.
- Golden files lock JSON and CSV schemas and a stable no-color terminal layout.
- A generated 1 GB performance fixture gates the documented reference environment.
- Wheel installation smoke test validates the console entry point in a clean Python 3.11 virtual environment.

See [PRD.md](PRD.md) for behavior and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for delivery order.
