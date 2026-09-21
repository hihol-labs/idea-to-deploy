# Project Architecture: nginx-stream-report

## Context and Constraints

The product is a Python 3.11 CLI installed through pip and run locally by DevOps/SRE engineers. It consumes nginx common or combined access logs without retaining individual records. The target is a representative 1 GB file in under 30 seconds on a documented laptop, with a $0 cash budget and one-weekend delivery.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the four reports require only per-key counters, 24 hourly buckets, and a guarded set of User-Agent values; persistence would add writes, schema, setup, and cleanup without product value. An HTTP API is incorrect because input and output are local files/pipes, there are no remote users or long-lived jobs, and a server would introduce lifecycle, authentication, network, and deployment obligations that the approved scope excludes.

## Architecture Variants

### Variant A: Single-process streaming CLI (Selected)

- **Approach:** one process reads one line at a time, parses it into an immutable dataclass, updates in-memory aggregates, then renders once at end-of-stream.
- **Pros:** minimal setup, no intermediate storage, deterministic pipeline behavior, easiest pip distribution.
- **Cons:** exact unique cardinality consumes memory up to its explicit ceiling; one CPU-bound process.
- **Best for:** local one-shot and piped analysis up to the approved workload.
- **Estimated complexity:** Low.

### Variant B: Unix-tool composition

- **Approach:** ship separate parser and metric commands connected by pipes.
- **Pros:** composable and independently reusable stages.
- **Cons:** more public contracts, serialization overhead, harder cross-metric one-pass processing.
- **Best for:** users building custom processing graphs.
- **Estimated complexity:** Medium.

### Variant C: Local multiprocessing chunks

- **Approach:** split seekable files, aggregate chunks in workers, and merge summaries.
- **Pros:** potential CPU scaling on large static files.
- **Cons:** does not naturally support stdin/follow mode, complicates line boundaries and exact cardinality merging, exceeds one-weekend scope.
- **Best for:** future workloads that fail measured single-process performance targets.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the architecture is pre-approved, the four metrics share the same parsed record, and a single pass minimizes I/O and serialization. Variants B and C remain explicit rejected alternatives rather than MVP extension points.

## Component Model

```text
file path / stdin / followed file
              |
              v
        Input iterator  ---- I/O error ----> exit 1
              |
              v
       nginx line parser ---- malformed ---> skip + count
              |                    |          (or exit 3 in --strict)
              v
       AccessRecord dataclass
              |
              v
      StreamingAggregator ---- UA ceiling --> exit 4
      | IP Counter
      | error-URL Counter
      | 24 hourly buckets
      | guarded UA set
              |
              v
          Report dataclasses
              |
       +------+------+ 
       v             v             v
   Rich text       JSON           CSV
```

Dependencies point inward: `cli.py` coordinates; `inputs.py`, `parser.py`, and `aggregate.py` implement processing; `models.py` carries typed values; `renderers/` depends only on report models. No component writes product state to disk.

## Repository Layout

```text
pyproject.toml
src/nginx_stream_report/
  __init__.py
  cli.py
  inputs.py
  parser.py
  models.py
  aggregate.py
  errors.py
  renderers/
    __init__.py
    terminal.py
    json_output.py
    csv_output.py
tests/
  fixtures/
    common.log
    combined.log
    malformed.log
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_cli.py
  test_performance.py
scripts/
  generate_benchmark_log.py
```

## Data Model and Algorithms

`AccessRecord` is a frozen dataclass containing `client_ip: str`, `timestamp: datetime`, `request_target: str`, `status: int`, and `user_agent: str | None`. The parser supports nginx common and combined formats, strips a query string from the aggregation key only when `--strip-query` is set, and never retains the raw line after processing.

`StreamingAggregator` maintains:

- `Counter[str]` for client IP request counts;
- `Counter[str]` for request targets whose status is 400–599;
- a fixed list of 24 integer buckets keyed by the hour in each log entry's recorded offset;
- `set[str]` for exact non-null User-Agent values, guarded by `--max-unique-user-agents`;
- scalar `total_lines`, `total_valid_requests`, and `malformed_lines` counters.

Top 10 lists are selected with `heapq.nlargest` using the deterministic key `(count, inverse lexical key)` semantics represented in tests; final display order is count descending then key ascending. Hourly request distribution is a percentage: `100 × hourly_request_count / total_valid_requests`. All 24 hours are emitted, including zero-count buckets. If there are no valid requests, metric rendering is not attempted and exit code 3 is returned.

Unique User-Agent share is `100 × unique_non_null_user_agent_count / total_valid_requests`. Missing `"-"` User-Agent values contribute to valid requests but not to the unique numerator. Before inserting a new value, the aggregator checks the configured ceiling; exceeding it stops processing and returns exit code 4 rather than risking uncontrolled memory growth.

## Persistence, API, Authentication, and Deployment

### Database

There are no database tables, migrations, indexes, caches, or retained per-request rows. In-memory dataclasses and collections are process-local and discarded on exit. This is an intentional architecture constraint, not deferred infrastructure.

### HTTP API

There are no endpoints, request bodies, response bodies, sockets, or server lifecycle. The complete external interface is the CLI contract below.

### Authentication

There is no authentication or authorization flow because the process accesses only resources already readable by the invoking operating-system user. File permissions and shell pipeline permissions are the trust boundary. The CLI does not elevate privileges or ingest credentials.

### Deployment

The deployment unit is a Python wheel/sdist installed with pip into a Python 3.11 environment. There is no Docker image, Compose file, cloud runtime, daemon, Kubernetes manifest, or staging service. Release verification uses a clean local virtual environment and the console entry point.

## CLI Interface

### Command

```text
nginx-stream-report [OPTIONS] [INPUT]
```

`INPUT` is a path to a readable nginx access log. If omitted or `-`, bytes are read from standard input. The process reads incrementally and does not load the full input. `--follow` requires a regular file path and waits for appended lines until interrupted; a normal interrupt after at least one report interval exits 0, while interruption before any report produces no partial structured object and exits 1.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | off | Emit exactly one UTF-8 JSON object; mutually exclusive with `--csv` |
| `--csv` | off | Emit UTF-8 CSV with the schema below; mutually exclusive with `--json` |
| `--follow` | off | Continue reading appended lines; valid only for a path |
| `--strict` | off | Treat the first malformed non-empty line as a parse failure |
| `--strip-query` / `--keep-query` | keep | Remove or retain query strings in URL aggregation keys |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive exact-cardinality ceiling; breach exits 4 |
| `--color` / `--no-color` | auto | Control color for text only; auto means terminal detection |
| `--version` | n/a | Print package version and exit 0 |
| `--help` | n/a | Print Click help and exit 0 |

### Inputs

- UTF-8 nginx common or combined access-log lines, tolerating replacement decoding for isolated invalid bytes while counting a line malformed if fields cannot be parsed.
- Regular files, `-`, and stdin pipes are supported.
- Empty lines are ignored and counted neither valid nor malformed.
- Compressed files, custom `log_format` definitions, multiple simultaneous inputs, and remote URLs are out of scope.

### Outputs

Default text contains a summary and four Rich tables. ANSI styling is emitted only when color is enabled. Diagnostics go to stderr; report data goes to stdout.

JSON uses this stable top-level shape:

```json
{
  "summary": {"total_lines": 0, "total_valid_requests": 0, "malformed_lines": 0},
  "top_ips": [{"ip": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"url": "/missing", "count": 1}],
  "hourly_distribution": [{"hour": 0, "request_count": 0, "percentage": 0.0}],
  "user_agents": {"unique_count": 0, "share_percentage": 0.0}
}
```

CSV begins with `section,rank,key,count,percentage`. Ranked sections use `top_ip` or `top_error_url`; hourly rows use `hour` with keys `00` through `23`; the unique summary uses `user_agent_unique`. Empty percentage cells are blank, not zero. RFC 4180 quoting is applied by Python's `csv` module.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Report emitted successfully, even if some lines were skipped in non-strict mode |
| `1` | Input/output failure, including unreadable input or broken output other than an expected closed pipe |
| `2` | Click usage error or invalid option combination/value |
| `3` | Log-data failure: strict malformed line, or end-of-stream with zero valid requests |
| `4` | Unique-cardinality exhaustion: a new User-Agent would exceed the configured ceiling |

This `0/1/2/3/4` contract is exhaustive for the MVP. A closed downstream pipe is handled quietly according to standard CLI convention and does not print a traceback.

## Performance and Resource Contract

- Single pass, O(number of lines) time.
- No retained `AccessRecord` collection and no second read.
- Fixed 24-bucket hourly storage; IP and error-URL maps grow with observed keys; User-Agent growth is hard-limited.
- The 1 GB / 30 s acceptance run uses a generated representative combined log on a documented laptop, with warm/cold-cache conditions recorded.
- Benchmark output records elapsed time, peak RSS, valid line count, Python version, processor, storage type, and command options.
- Performance tests are separately marked so routine unit tests remain fast.

## Error Handling and Observability

Expected failures raise typed domain exceptions mapped once in `cli.py`; users do not see tracebacks unless a future debug option is explicitly introduced. Non-strict malformed lines increment a counter and the final stderr warning reports their count. Structured stdout stays machine-parseable. No telemetry, log upload, or local history is created.

## Security and Privacy

Input is untrusted text, never evaluated as code, interpolated into a shell, or used as a path except for the explicit `INPUT` argument. Rich markup is escaped before display. CSV cells are data and are quoted; documentation warns spreadsheet consumers that leading formula characters remain potentially active in spreadsheet applications. Output may contain IPs, URLs, and User-Agents, so operators are responsible for access control and redaction when sharing reports. The tool makes no network connections.

## Architecture Decision Records

### ADR-001: Select single-process streaming

- **Status:** Accepted by the product brief.
- **Decision:** Use Variant A and keep records ephemeral.
- **Consequences:** Simple local operation and one-pass metrics; cardinality must be guarded and measured performance may later force algorithmic optimization.

### ADR-002: Exact unique User-Agent count with a hard ceiling

- **Status:** Accepted.
- **Decision:** Prefer exact results until a configurable ceiling is reached, then fail with code 4.
- **Consequences:** Semantics stay clear; high-cardinality input cannot silently degrade accuracy or exhaust memory.

### ADR-003: Stable structured output contracts

- **Status:** Accepted.
- **Decision:** JSON emits one object and CSV uses a normalized multi-section schema; neither contains ANSI escapes.
- **Consequences:** Pipelines can validate output, while schema changes require an explicit product-contract revision.

No adversarial review is claimed here. Per the benchmark protocol, an external fresh-session Devil's Advocate review occurs after this workflow exits.

