# Project Architecture: nginx-stream-insights

## 1. Context and Quality Attributes

The product is a local Python 3.11 CLI that performs one pass over nginx access-log lines and emits four aggregates. Its priorities, in order, are correctness, stable pipeline contracts, predictable failure behavior, streaming memory use, and throughput of 1 GB in under 30 seconds on a documented laptop.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the required results can be derived during a single pass, persistence would add writes, cleanup, schema management, and privacy risk, and no cross-run queries are required. An HTTP API is incorrect because the operator already has local files or stdin, pipeline composition is a core requirement, and a listening service would introduce lifecycle, security, authentication, and deployment work with no product benefit.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** one Python process reads one line at a time, parses it, updates in-memory counters, then renders once at end-of-stream.
- **Pros:** one pass, deterministic state, simple error handling, low I/O, no inter-process serialization, weekend-sized implementation.
- **Cons:** one CPU core and exact unique User-Agent tracking can consume memory on adversarial input.
- **Best for:** local files and stdin up to the target 1 GB, with an explicit unique-cardinality guard.
- **Estimated complexity:** Low.

### Variant B: Unix pipeline of specialized commands

- **Approach:** independent parser/aggregator processes communicate through text or JSON Lines.
- **Pros:** composable and individually replaceable stages.
- **Cons:** repeated parsing or serialization, more process failure modes, harder atomic output, and slower end-to-end execution.
- **Best for:** experimentation with individual transformations, not the packaged v1 command.
- **Estimated complexity:** Medium.

### Variant C: Multiprocess file chunking

- **Approach:** split seekable files at newline boundaries, aggregate chunks in workers, and merge partial results.
- **Pros:** can use multiple CPU cores on very large regular files.
- **Cons:** cannot naturally accelerate stdin, complicates byte boundaries and error ordering, increases peak memory and testing scope, and is unnecessary before measurement.
- **Best for:** a future version only if profiling proves parsing is CPU-bound and the target is missed.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the user pre-approved the obvious single-process architecture and the one-weekend, $0, stdin-friendly scope values simple deterministic streaming over speculative parallelism.

## 3. Component Model

```text
file(s) / stdin
       |
       v
 Input iterator ---- read/open errors --------------------+
       |                                                  |
       v                                                  v
 CombinedLogParser -- malformed count --> AggregationState
       | valid AccessRecord                               |
       +------------------------------------------------->|
                                                          v
                                                AnalysisResult
                                                          |
                                     +--------------------+-------------------+
                                     v                    v                   v
                              Rich terminal          JSON renderer       CSV renderer
```

| Module | Responsibility | Key public structures/functions |
|---|---|---|
| `src/nginx_stream_insights/cli.py` | Click command, option validation, input lifecycle, exception-to-exit mapping | `main()` |
| `src/nginx_stream_insights/parser.py` | Compile and apply v1 combined-log pattern; parse timestamp/status safely | `parse_line(str) -> AccessRecord | None` |
| `src/nginx_stream_insights/models.py` | Immutable domain and result contracts | `AccessRecord`, `AnalysisResult`, `RankedCount`, `HourlyBucket` dataclasses |
| `src/nginx_stream_insights/aggregate.py` | Update counters and enforce unique-cardinality limit | `StreamingAggregator.consume()`, `.finish()` |
| `src/nginx_stream_insights/input.py` | Iterate stdin or one or more files without buffering the corpus | `iter_lines()` |
| `src/nginx_stream_insights/renderers.py` | Terminal, JSON, and normalized CSV serialization | `render_terminal`, `render_json`, `render_csv` |
| `src/nginx_stream_insights/errors.py` | Typed expected failures carrying public exit semantics | `InputFailure`, `CardinalityExhausted` |

Dependencies flow inward: `cli` may depend on all modules; renderers depend only on models; aggregation depends on models/errors; parser and input do not depend on Click or Rich. No module retains raw log lines after a record is consumed.

## 4. Data Model and Algorithms

### Parsed record

`AccessRecord` contains only aggregation inputs:

| Field | Type | Rule |
|---|---|---|
| `client_ip` | `str` | nginx remote address token, non-empty |
| `timestamp` | timezone-aware `datetime` | parsed from `[day/month/year:hour:minute:second offset]` |
| `request_target` | `str` | target token from quoted request line; includes query string in v1 |
| `status` | `int` | three-digit status from 100 through 599 |
| `user_agent` | `str` | quoted field; `-` means missing and is excluded from the unique set |

### Streaming state

- `total_lines` and `malformed_lines`: integer diagnostics.
- `total_valid_requests`: denominator for all request-share calculations.
- `ip_counts: Counter[str]`: exact counts for all observed client IPs.
- `error_url_counts: Counter[str]`: exact counts only when `400 <= status <= 599`.
- `hour_counts: list[int]`: fixed 24 slots, using the hour represented in each log timestamp.
- `unique_user_agents: set[str]`: exact non-missing values until the configured limit.

Top lists sort by descending count and then ascending UTF-8 string value for deterministic ties, returning at most 10 entries. Hourly request distribution has 24 buckets (`00` through `23`), including zeros, and each percentage is calculated using the literal formula `100 × hourly_request_count / total_valid_requests`. Percentages are serialized with two decimal places in terminal/CSV and as JSON numbers derived from the same calculation.

The unique User-Agent share is `100 × unique_non_missing_user_agent_count / total_valid_requests`. It measures diversity relative to valid requests, not the percentage of requests belonging to rare agents. Missing (`-`) values remain in the request denominator but not the distinct numerator. If adding a new value would exceed the cardinality limit, processing stops without partial stdout and exits `4`.

### Database, API, auth, and durable schema

There are no database tables, migrations, indexes, API endpoints, request bodies, authentication flows, sessions, or stored user records. These absences implement the selected architecture rather than leaving unspecified work. Input files are opened read-only; results exist only in process memory and stdout/stderr.

## CLI Interface

### Command

```text
nginx-insights [OPTIONS] [INPUT...]
```

With no `INPUT`, or with a single `-`, the command reads standard input. One or more explicit paths are read sequentially as one logical dataset. Mixing `-` with file paths is rejected as usage error `2` to prevent ambiguous blocking and ordering.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one UTF-8 JSON object and no terminal styling |
| `--csv` | flag, false | Emit normalized RFC 4180-compatible CSV and no terminal styling |
| `--no-color` | flag, false | Disable Rich color in terminal mode; invalid with `--json` or `--csv` |
| `--max-unique-user-agents INTEGER` | positive integer, `1000000` | Stop with exit `4` before storing a distinct value beyond the limit |
| `--encoding TEXT` | `utf-8` | Input decoding; invalid codec names are usage error `2`, decoding failures are input error `3` |
| `--version` | flag | Print package version and exit `0` |
| `--help` | flag | Print Click help and exit `0` |

`--json` and `--csv` are mutually exclusive. Top-N is fixed at 10 in v1.

### Inputs

- Uncompressed text files and stdin are P0.
- Gzip files detected by `.gz` suffix are P1 and opened as text streams; stdin is never guessed as compressed.
- The v1 accepted format is nginx combined log format with quoted request, referrer, and User-Agent fields.
- Blank and non-matching lines are malformed. Mixed valid/malformed input succeeds but reports counts to stderr; a dataset with zero valid records exits `3` and emits no report.

### Outputs

Terminal mode renders a title, processing summary, top-IP table, top error-URL table, 24-hour table, and User-Agent summary. Rich uses color for headings and 4xx/5xx emphasis when the output stream supports it; `--no-color` forces plain text.

JSON schema:

```json
{
  "schema_version": 1,
  "summary": {"total_lines": 0, "valid_requests": 0, "malformed_lines": 0},
  "top_ips": [{"ip": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"url": "/missing", "count": 1}],
  "hourly_distribution": [{"hour": 0, "count": 1, "percentage": 100.0}],
  "user_agents": {"unique_count": 1, "share_percentage": 100.0}
}
```

The real `hourly_distribution` array always contains 24 entries. Key order is stable for snapshots but consumers must rely on names, not object order.

CSV schema is `metric,rank,key,count,percentage`. Top-list rows use `metric` values `top_ip` and `top_error_url`, with rank/count populated and percentage empty. Hour rows use `hourly_requests`, a zero-padded hour in `key`, count and percentage populated, and rank empty. The final `unique_user_agents` row contains unique count and share percentage. CSV quoting is delegated to Python's `csv` module.

Diagnostics go to stderr only. JSON and CSV stdout never contain warnings, progress, or ANSI escapes.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Successful help/version request or completed analysis with at least one valid record |
| `1` | Unexpected internal error or stdout write failure |
| `2` | Click usage/configuration error, including conflicting options or invalid limits |
| `3` | Input failure: unreadable/undecodable source, truncated gzip stream, or zero valid records |
| `4` | Unique-cardinality exhaustion: the distinct non-missing User-Agent limit would be exceeded |

Expected failures produce a concise single diagnostic without a traceback. Unexpected failures may show a traceback only when a future explicit debug option is enabled.

## 6. Error Handling and Resource Limits

Output is buffered as the small final report, not streamed incrementally, so a failed analysis never emits a plausible partial result. Files are opened one at a time and closed deterministically. Lines are iterated lazily; only counters and distinct keys remain in memory.

Exact IP and URL counters are not hard-capped in v1 because silently dropping keys would corrupt required top-10 results. The 1 GB acceptance fixture must include realistic cardinality and a separate adversarial-cardinality test. The explicit User-Agent guard addresses the most likely unbounded dimension and provides a distinguishable automation failure.

Broken pipe/output errors map to `1`; input-open or decoding errors map to `3`. Malformed individual lines are recoverable unless all lines are malformed. Keyboard interruption follows Click's conventional abort behavior and maps to `1` for the documented public contract.

## 7. Performance Design

- Compile the parser pattern once per process.
- Use one line read, one parse, and constant-time average counter updates per valid record.
- Avoid per-line dataclass creation if profiling shows it is material; this is an allowed internal optimization only if parser/aggregator contracts stay testable.
- Defer sorting to end-of-stream and use `heapq.nsmallest`/equivalent bounded selection where benchmarks justify it.
- Never retain raw lines, rendered fragments, or per-request objects.
- Benchmark from a warm local filesystem with wall time, peak RSS, Python version, CPU model, and fixture checksum recorded by the test harness.

Complexity is O(n) processing time plus O(I + E + U) memory for unique IPs, error URLs, and User-Agents. The 24 hour buckets are O(1).

## 8. Security and Privacy

Log fields are untrusted data, never format strings or terminal markup. Rich rendering must escape/disable markup for IPs, URLs, and User-Agents. CSV relies on correct quoting; cells beginning with `=`, `+`, `-`, or `@` are prefixed with a single quote to reduce spreadsheet formula injection risk while JSON preserves raw values. Paths are user-selected and opened read-only. The tool performs no network calls, telemetry, shell execution, dynamic imports, or persistence.

Error messages expose the source path and line counts but not raw log content, which can contain personal data. Documentation reminds users that stdout reports still contain IPs and URLs and should be handled under the same policy as source logs.

## 9. Packaging and Deployment

`pyproject.toml` defines the Python `>=3.11` requirement, Click and Rich runtime dependencies, a `src/` package layout, and the `nginx-insights` console-script entry point. Distribution is a pure-Python wheel and source distribution installable with pip. There is no container image, Docker Compose file, daemon, deployment target, cloud resource, Kubernetes manifest, environment variable, or runtime service.

Configuration is intentionally command-line-only. This prevents hidden environment-dependent behavior in pipelines. Development tooling may be configured in `pyproject.toml` but cannot change runtime semantics.

## 10. Architecture Decision Records

### ADR-001: Exact single-pass aggregation

- **Status:** Accepted (pre-approved by product brief).
- **Decision:** Use Variant A, a single-process exact streaming aggregation.
- **Consequences:** Simple stdin support and deterministic output; memory grows with distinct exact keys, guarded explicitly for User-Agents.

### ADR-002: No database and no API

- **Status:** Accepted (constraint).
- **Decision:** Keep all state in memory for one invocation and expose only the CLI contract.
- **Consequences:** Zero operational infrastructure and no cross-run history; users needing history should select a different product category.

### ADR-003: Exactness before approximate sketches

- **Status:** Accepted for v1.
- **Decision:** Fail with code `4` when exact User-Agent cardinality cannot be maintained within the configured limit; do not silently switch to approximation.
- **Consequences:** Pipeline consumers can trust successful results and distinguish resource exhaustion.

### Debate status

No adversarial or independent review was performed in this session. Per the benchmark contract, the external harness runs the actual Devil's Advocate agent separately; this document does not pre-empt or simulate its findings.

## 11. Test Boundaries

Unit tests cover valid and malformed parsing, timezone/hour extraction, status boundaries, deterministic tie ordering, percentage math, cardinality exhaustion, and escaping. Integration tests invoke the installed Click command against fixtures and stdin, assert stdout/stderr separation, all three formats, and the complete exit-code contract. Performance testing is a separately marked benchmark using a generated representative 1 GB fixture so normal unit tests remain fast.

Product behavior is specified in `PRD.md`; build sequencing and verification commands are in `IMPLEMENTATION_PLAN.md`.
