# Project Architecture: nginx-stream-report

## Architecture Goals and Constraints

The architecture is a single local Python 3.11 process with a streaming input loop and bounded aggregate state. The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct because each invocation analyzes an explicit immutable input and emits a complete report: persistence would add lifecycle, privacy, migration, and I/O costs without serving the required use cases. An HTTP API would add a server, authentication, network exposure, deployment, and concurrency concerns to a tool whose users already work in terminals and pipelines. Neither is needed to meet the report or performance contract.

Other fixed constraints are: Click, Rich, dataclasses, pip installation, $0 budget, no auth, no cloud, no Kubernetes, and one-weekend delivery.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** one process parses each line, updates aggregate state, finalizes percentages/rankings, and renders once.
- **Pros:** lowest overhead, simple tests, natural stdin support, bounded state except exact cardinality set, one artifact.
- **Cons:** CPU work is single-process; exact unique counting grows with distinct User-Agents until the configured cap.
- **Best for:** the approved 1 GB local log workflow.
- **Estimated complexity:** Low.

### Variant B: Multiprocessing chunk map/reduce

- **Approach:** split seekable files into chunks, aggregate in workers, merge partial reports.
- **Pros:** can use multiple cores for very large files.
- **Cons:** cannot split stdin naturally; byte-boundary parsing, merge logic, serialization, and process startup threaten weekend scope.
- **Best for:** future multi-gigabyte workloads after profiling proves CPU saturation.
- **Estimated complexity:** Medium.

### Variant C: External Unix-tool pipeline

- **Approach:** compose `awk`, `sort`, and `uniq` scripts.
- **Pros:** minimal packaging and good availability.
- **Cons:** fragile quoting/parsing, locale-dependent behavior, multiple passes and external sorts, inconsistent cross-platform output.
- **Best for:** one-off exploratory commands, not a supported product.
- **Estimated complexity:** Low initially, high maintenance.

### Recommendation

Variant A is selected because the architecture choice is pre-approved and directly satisfies stdin streaming, pip distribution, performance, and one-weekend constraints. Variant B is a future optimization only if benchmark evidence demands it.

## Component Model

```text
file path / stdin
       |
       v
 InputSource -> CombinedLogParser -> StreamingAggregator -> ReportFinalizer
                         |                    |                    |
                         v                    v                    v
                  malformed count     counters + UA set    Report dataclasses
                                                                  |
                                             +--------------------+------------------+
                                             v                    v                  v
                                      RichRenderer         JsonRenderer       CsvRenderer
```

| Module | Responsibility | Key contract |
|---|---|---|
| `src/nginx_stream_report/cli.py` | Click command, option validation, error-to-exit mapping | No analysis logic |
| `input.py` | stdin/file opening and decoding | Iterable of text lines; never reads whole file |
| `parser.py` | nginx combined-format parsing | `ParsedRequest` or classified malformed result |
| `models.py` | immutable dataclasses | Stable internal report schema |
| `aggregator.py` | one-pass counters and cardinality guard | Bounded counters; explicit UA cap failure |
| `report.py` | top-10 ordering and percentage calculation | Deterministic ties and zero-input behavior |
| `renderers/rich_text.py` | colored terminal report | Color auto/always/never; no ANSI when disabled |
| `renderers/json_output.py` | JSON serialization | One UTF-8 JSON document |
| `renderers/csv_output.py` | normalized CSV serialization | Header plus deterministic section rows |

## Data Model and Streaming Invariants

There are no database tables. The complete in-memory dataclass model is:

| Dataclass | Fields | Invariants |
|---|---|---|
| `ParsedRequest` | `client_ip: str`, `timestamp: datetime`, `method: str`, `url: str`, `protocol: str`, `status: int`, `bytes_sent: int | None`, `user_agent: str` | Timestamp is timezone-aware; status is 100–599; `-` bytes maps to `None` |
| `AggregateState` | `total_valid_requests: int`, `malformed_lines: int`, `ip_counts: Counter[str]`, `error_url_counts: Counter[str]`, `hour_counts: list[int]`, `unique_user_agents: set[str]` | `hour_counts` has 24 slots; error URLs include only 400–599; set size never exceeds cap |
| `RankedItem` | `key: str`, `count: int`, `rank: int` | Ordering is count descending then key ascending; at most 10 per ranking |
| `HourlyBucket` | `hour: int`, `count: int`, `percentage: float` | hour is 0–23; percentage formula is `100 × hourly_request_count / total_valid_requests` |
| `Report` | `total_valid_requests: int`, `malformed_lines: int`, `top_ips: tuple[RankedItem, ...]`, `top_error_urls: tuple[RankedItem, ...]`, `hourly_distribution: tuple[HourlyBucket, ...]`, `unique_user_agents: int`, `unique_user_agent_share: float` | Share is `100 × unique_user_agents / total_valid_requests`; empty input returns zero values without division |

Memory is `O(U_ip + U_error_url + U_user_agent + 24)`. The unique User-Agent set is exact up to `--max-unique-user-agents`; crossing the limit aborts with exit code `4` before inserting another value. IP and error-URL counters remain potentially high-cardinality; the 1 GB benchmark must measure worst-case fixtures, and a future bounded heavy-hitter algorithm requires a versioned contract change because it would make rankings approximate.

## Parsing Contract

The MVP supports the standard nginx combined log format:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

- Input is UTF-8 with `errors="replace"`; a replacement character is data, not a crash.
- The request field is split into method, URL, and protocol; an nginx `"-"` request is malformed for metric purposes.
- URL ranking uses the request-target exactly as logged, including query string, so behavior is reproducible. Query normalization is a future option.
- 4xx/5xx means status codes 400 through 599 inclusive.
- Hour buckets use the local hour in each timezone-aware nginx timestamp.
- Malformed lines are counted and skipped. With `--strict`, the first malformed line terminates with code `3`.
- Top-10 ties sort lexicographically by key after count descending.

## CLI Interface

### Commands

The installed console script exposes one command:

```text
nginx-stream-report [OPTIONS] [INPUT]
```

`INPUT` is an nginx access-log path. If omitted or `-`, lines are read from stdin. Exactly one report is produced per invocation.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit normalized CSV; mutually exclusive with `--json` |
| `--color [auto|always|never]` | `auto` | Applies only to terminal text; rejected with JSON/CSV if non-default |
| `--strict` | flag, false | Fail on first malformed input line instead of counting and skipping |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive exact-cardinality cap; exhaustion maps to exit code `4` |
| `--version` | flag | Print version and exit `0` |
| `--help` | flag | Print help and exit `0` |

### Inputs

- A regular UTF-8 text file, `-`, or stdin.
- Streaming is mandatory: no `read()`, `readlines()`, or full-file materialization.
- Gzip autodetection is a P1 extension; MVP users may pipe `gzip -dc access.log.gz`.

### Outputs

Default text consists of a summary followed by four labeled tables/values. Color is emitted only when `--color always` or `--color auto` detects a TTY.

JSON schema:

```json
{
  "total_valid_requests": 0,
  "malformed_lines": 0,
  "top_ips": [{"rank": 1, "ip": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"rank": 1, "url": "/missing", "count": 1}],
  "hourly_distribution": [{"hour": 0, "count": 0, "percentage": 0.0}],
  "unique_user_agents": 0,
  "unique_user_agent_share": 0.0
}
```

The real `hourly_distribution` always contains 24 items ordered `0..23`. Percentages are rounded to two decimal places for serialization; computation uses unrounded values.

CSV uses columns `section,rank,key,count,percentage`. It contains ranked rows for `top_ips` and `top_error_urls`, 24 rows for `hourly_distribution`, and summary rows for totals and User-Agent share. Fields are RFC 4180 quoted by Python's `csv` module. stdout contains only the selected report; diagnostics go to stderr.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Report emitted successfully, including empty input or skipped malformed lines in non-strict mode |
| `1` | Unexpected internal error |
| `2` | CLI usage or option validation error |
| `3` | Input error: missing/unreadable file, decoding/stream failure, or malformed line under `--strict` |
| `4` | Unique-cardinality exhaustion: distinct User-Agents would exceed the configured cap |

## Error Handling and Observability

Known errors become concise stderr messages prefixed with `error:` and contain no traceback. A traceback is reserved for development diagnostics, never normal CLI output. A successful non-strict run reports `malformed_lines`; stderr remains quiet so pipeline consumers need only parse stdout. Broken pipes are handled without a traceback and use the platform-normal successful shutdown behavior where feasible.

## Security and Privacy

Processing is local and read-only. The program makes no network calls and writes no persistent data. Logs may contain IP addresses, URLs, referrers, and User-Agents; documentation warns users that stdout may therefore contain sensitive operational data. Input text is never interpreted as terminal markup: Rich rendering escapes or treats values as plain text. URLs beginning with spreadsheet formula characters remain safely CSV-quoted, though downstream spreadsheet importers must apply their own formula-injection protections.

## Packaging and Deployment

Distribution is a pure-Python wheel and source distribution built from `pyproject.toml`, with a `src/` layout and the `nginx-stream-report` console entry point. Deployment means `python -m pip install nginx-stream-report` into a Python 3.11 environment. There is no Docker, daemon, system service, environment-variable contract, remote deployment, staging environment, or Kubernetes manifest because those contradict the local CLI scope.

Runtime dependencies are constrained compatible versions of Click and Rich. Development dependencies include pytest, coverage support, Ruff, mypy, and a build frontend. Release artifacts must be tested in a fresh virtual environment before publication; publication itself requires explicit human approval.

## Performance Design

- Compile the parser once and reuse it.
- Process one line and update counters immediately.
- Keep only counters and the exact User-Agent set, never parsed request lists.
- Finalize sorting only after EOF; use `heapq.nsmallest`/equivalent bounded selection if profiling shows full sorting matters.
- Benchmark with `/usr/bin/time -v nginx-stream-report --json fixture.log > /dev/null` after a warm-up, recording Python version, CPU, storage, fixture hash/shape, elapsed time, and maximum RSS.
- Acceptance: a 1 GB representative fixture finishes in under 30 seconds on the recorded laptop with peak RSS no greater than 256 MiB.

## Testing Strategy

| Layer | Coverage |
|---|---|
| Parser unit tests | valid combined lines, spaces/quotes, `-` bytes, IPv4/IPv6, timezone offsets, malformed fields |
| Aggregator unit tests | 4xx/5xx filtering, exact counts, 24 buckets, cardinality boundary |
| Report unit tests | deterministic top-10 ties, empty input, formulas and rounding |
| CLI integration tests | file/stdin, TTY color policy, JSON/CSV schemas, stderr separation, exit codes `0/1/2/3/4` |
| Property tests (optional P1) | arbitrary malformed text never crashes parser |
| Performance test | generated 1 GB corpus, elapsed time and RSS gate on reference hardware |

## Architecture Decision Records

### ADR-001: Select a single-process streaming pipeline

- **Status:** Accepted (pre-approved product decision).
- **Decision:** Use Variant A and keep parsing, aggregation, and rendering in one local process.
- **Consequences:** stdin works naturally and implementation is small; CPU parallelism is deferred until measurement justifies complexity.

### ADR-002: Use exact User-Agent cardinality with an explicit cap

- **Status:** Accepted.
- **Decision:** Track a set for exact unique share and abort with exit code `4` before exceeding the user-configurable cap.
- **Consequences:** results are exact within the supported envelope; exhaustion is visible rather than silently approximate.

### ADR-003: Normalize heterogeneous CSV sections

- **Status:** Accepted.
- **Decision:** Use `section,rank,key,count,percentage` rows rather than multiple incompatible tables.
- **Consequences:** one valid CSV stream is pipeline-friendly, though consumers filter by section.

No in-session adversarial review was performed; the benchmark explicitly delegates that activity to a separate external harness session.

