# Project Architecture: Nginx Stream Analyzer

## Context and Decision

The product is a local Python 3.11 command-line utility. The selected architecture is one installable package and one operating-system process. Its data path is:

```text
file path or stdin
       |
       v
line iterator -> nginx parser -> metric accumulator -> immutable result -> one renderer
                                   |                       |-> Rich terminal
                                   |                       |-> JSON stdout
                                   |                       `-> CSV stdout
                                   `-> counters + bounded cardinality guard
```

The binding decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is wrong because the requested reports are computed in one pass, persistence adds latency and operational burden, and local logs may contain sensitive identifiers. An HTTP API is wrong because there is no remote client, multi-user state, or long-running service requirement; stdin/stdout and exit codes already provide the correct automation boundary.

## Goals and Quality Attributes

- Process representative 1 GB input in under 30 seconds on a documented laptop.
- Read incrementally; never load the complete log or retain individual parsed requests.
- Produce deterministic terminal, JSON, and CSV results from one normalized result model.
- Remain installable with pip and runnable on Python 3.11.
- Fail predictably with the complete `0/1/2/3/4` exit-code contract.
- Keep logs local and make no network calls.

## CLI Interface

### Commands

The console entry point is `nginx-stream-analyzer` with one analysis command:

```text
nginx-stream-analyzer [OPTIONS] [INPUT]
```

`INPUT` is an optional file path. If omitted or `-`, bytes are read from stdin. Exactly one input stream is processed per invocation.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit long-form CSV; mutually exclusive with `--json` |
| `--encoding` | text, `utf-8` | Decode input with strict error handling |
| `--max-unique-user-agents` | integer, `1000000` | Positive exact-cardinality safety limit |
| `--color/--no-color` | tri-state auto | Default auto enables color only on a TTY; terminal mode only |
| `--version` | flag | Print version and exit 0 |
| `--help` | flag | Print usage and exit 0 |

Unknown options, conflicting format flags, invalid positive integers, or an invalid argument count are usage errors.

### Inputs

- Plain-text nginx access logs in supported common or combined format.
- One logical record per line.
- Timestamps include a numeric UTC offset; hours are grouped by the logged local hour (`00`–`23`) without timezone conversion.
- Malformed lines are skipped and counted. A stream with no valid records is a data error.
- Response status values 400–599 contribute to the error-URL report.
- Query strings remain part of the request target, because removing them would silently merge distinct logged URLs in the MVP.

### Outputs

Default terminal output has four labeled sections and a processing summary. Ranks use descending count with the string key ascending as a deterministic tie-breaker. Empty top lists are rendered explicitly. Hours `00` through `23` are always present.

Hourly request distribution is a percentage defined by the literal formula `100 × hourly_request_count / total_valid_requests`. Percentages are rounded to two decimal places only at presentation time.

Unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`, where an absent User-Agent in common format is normalized to a single sentinel value. The output also exposes numerator and denominator.

JSON is UTF-8 with this stable top-level shape:

```json
{
  "summary": {"valid_requests": 0, "malformed_lines": 0, "unique_user_agents": 0, "unique_user_agent_share_percent": 0.0},
  "top_ips": [{"ip": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"url": "/missing", "count": 1}],
  "hourly_request_distribution": [{"hour": "00", "count": 0, "percentage": 0.0}]
}
```

CSV always includes `report,rank,key,count,percentage`. Top-list rows use `report=top_ips|top_error_urls`; hour rows use `report=hourly_request_distribution`; one summary row uses `report=unique_user_agent_share`, `count` for unique values, and `percentage` for the share. CSV and JSON stdout contain no decorations; diagnostics go to stderr.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Success, including streams with some skipped malformed lines when at least one record is valid |
| `1` | Input I/O or decoding failure, including missing/unreadable files |
| `2` | Click usage error, such as conflicting flags or an invalid option value |
| `3` | Data error: input contains no valid nginx records |
| `4` | Unique-cardinality exhaustion: distinct User-Agents exceed `--max-unique-user-agents` |

On nonzero exit, stdout is empty and a concise diagnostic is written to stderr.

## Component Design

| Component | Planned path | Responsibility |
|---|---|---|
| CLI adapter | `src/nginx_stream_analyzer/cli.py` | Click command, input ownership, renderer selection, exception-to-exit mapping |
| Input adapter | `src/nginx_stream_analyzer/input.py` | File/stdin text iteration and decoding errors |
| Parser | `src/nginx_stream_analyzer/parser.py` | Convert one common/combined line into `AccessRecord` or a malformed result |
| Models | `src/nginx_stream_analyzer/models.py` | Dataclasses `AccessRecord`, `RankedCount`, `HourlyBucket`, `AnalysisResult` |
| Aggregator | `src/nginx_stream_analyzer/aggregate.py` | Counters, 24 hourly buckets, exact User-Agent set and limit |
| Terminal renderer | `src/nginx_stream_analyzer/renderers/terminal.py` | Rich tables and TTY-aware color |
| JSON renderer | `src/nginx_stream_analyzer/renderers/json_output.py` | Stable serialization only |
| CSV renderer | `src/nginx_stream_analyzer/renderers/csv_output.py` | Stable long-form rows only |
| Errors | `src/nginx_stream_analyzer/errors.py` | Typed I/O, data, and cardinality exceptions |

The parser is pure and has no output concerns. The aggregator consumes records and retains only `Counter` maps, 24 integer buckets, an exact User-Agent set, and scalar totals. Renderers accept the same `AnalysisResult`, preventing format-specific metric drift.

## Data Model

There are no database tables, schemas, migrations, indexes, or persisted records. In-memory dataclasses are:

| Dataclass | Fields |
|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `method: str`, `target: str`, `protocol: str`, `status: int`, `user_agent: str` |
| `RankedCount` | `key: str`, `count: int`, `rank: int` |
| `HourlyBucket` | `hour: int`, `count: int`, `percentage: float` |
| `AnalysisResult` | `valid_requests: int`, `malformed_lines: int`, `top_ips: tuple[RankedCount, ...]`, `top_error_urls: tuple[RankedCount, ...]`, `hourly: tuple[HourlyBucket, ...]`, `unique_user_agents: int`, `unique_user_agent_share_percent: float` |

## Parsing Contract

The parser recognizes nginx common and combined access records, including quoted request and User-Agent fields and `-` sentinels. It validates the timestamp, request triple, integer status in `100..599`, and required IP/target fields. It does not attempt recovery inside a malformed line. Parsing must avoid catastrophic regex behavior; a compiled, anchored expression plus explicit field conversion is acceptable only after representative profiling.

## Streaming and Performance

- Iterate in text-buffered chunks supplied by Python's file object; do not call `read()` without a size or `readlines()`.
- Update counters per valid record and discard the record immediately.
- Select top 10 only after EOF with `heapq.nsmallest`/bounded ranking or `Counter.most_common`, with deterministic tie resolution.
- Track exact User-Agent values until the configured cap; crossing it stops processing and exits 4 rather than returning an estimate as exact.
- Benchmark wall time and peak resident memory with a deterministic 1 GB corpus. The performance test is a release gate, not a unit test.

Counter maps can still grow with unique IPs/URLs; this is an accepted exactness trade-off for the 1 GB target. If profiling finds adversarial cardinality problematic, a future explicit limit must have its own documented failure code/contract rather than silent eviction.

## API, Authentication, and Network Boundaries

There are zero HTTP endpoints and no REST, GraphQL, gRPC, socket, or plugin API. There is no authentication or authorization flow because there are no users, accounts, remote requests, or privileged actions. OS file permissions are the trust boundary. The process makes no outbound network connections and never writes input log content to persistent storage.

## Configuration and Environment

All behavior is controlled by explicit CLI options. No environment variables, `.env` file, secrets, or credentials are required. Locale must not affect JSON/CSV numeric formatting or ordering. The process uses the local terminal capability only to decide default color.

## Deployment and Packaging

Deployment means building a Python wheel/sdist and installing it with pip into a Python 3.11 environment. `pyproject.toml` declares Click and Rich runtime dependencies and the console script. Docker, docker-compose, servers, cloud resources, and Kubernetes are intentionally absent: they add startup, image maintenance, and distribution complexity without improving a local pip-installed CLI.

## Architecture Alternatives

The user-approved single-process package is selected; no decision pause is required.

| Alternative | Benefit | Rejection reason |
|---|---|---|
| Multiprocessing parser | Potential CPU parallelism | Ordering, IPC, and cross-platform complexity are premature before profiling; one weekend scope |
| SQLite-backed aggregation | Bounds some Python object growth and enables queries | Violates statelessness, adds disk I/O and cleanup, retains sensitive derived data |
| Go implementation | Likely higher throughput and a static binary | Violates the approved Python 3.11/Click/Rich stack |
| Service/API architecture | Remote reuse | Explicitly out of scope and creates security/operations work with no user need |

## Security and Privacy

- Treat every log field as untrusted data; Rich/CSV/JSON renderers must escape it and terminal output must neutralize control characters.
- Do not evaluate, interpolate as markup, or open logged URLs.
- Open only the path explicitly supplied; never traverse directories or follow includes.
- Avoid echoing full malformed records in diagnostics because they can contain identifiers.
- Never create temporary copies of input or telemetry.

## Testing Strategy

- Parser table tests for common/combined, IPv4/IPv6, escaping, timestamps, malformed records, and status boundaries.
- Aggregator tests for ranking, ties, 24 buckets, the exact percentage formula, sentinel User-Agent, and limit crossing.
- Renderer golden/schema tests proving identical semantics and absence of ANSI in JSON/CSV.
- Click integration tests for stdin/file paths, mutual exclusion, stderr/stdout, and every exit code `0/1/2/3/4`.
- Packaging smoke test in a clean Python 3.11 environment.
- Reproducible 1 GB benchmark for time and peak memory.

## Architecture Decision Record (ADR)

### ADR-001: Local single-process streaming CLI

- **Status:** Accepted (pre-approved product decision)
- **Decision:** Use one Python process with iterator-based parsing, aggregation, and pluggable output renderers.
- **Consequences:** Minimal operations and straightforward pipelines; exact high-cardinality maps are the primary memory risk and must be measured/guarded.

### ADR-002: No persistence and no HTTP API

- **Status:** Accepted
- **Decision:** Apply **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- **Consequences:** No migrations, endpoints, auth, deployment service, or retained analysis; each invocation recomputes results.

### Review Boundary

No Devil’s Advocate or independent architecture review was performed in this blueprint session. The external benchmark owns that separate review and its artifact.

