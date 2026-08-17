# Project Architecture: nginx-stream-stats

## Architecture Summary

The product is a single Python 3.11 process with a pull-based pipeline:

```text
file path or stdin
        |
        v
line iterator -> combined-log parser -> streaming aggregator -> immutable report
                                                            |
                                          +-----------------+----------------+
                                          v                 v                v
                                      Rich text           JSON             CSV
```

Each input line is parsed once. Valid records update in-memory counters;
malformed records update a rejection count or stop processing in strict mode.
Only the final report is rendered, so input size does not determine retained
raw-log memory. The implementation never persists input or aggregates.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the command produces
an ephemeral summary, must start instantly, has no cross-run query requirement,
and has a $0/no-service constraint. An HTTP API is incorrect because the users
already possess local files or streams, need shell composition, and should not
operate a server, network boundary, authentication flow, or exposed port merely
to summarize them.

The architecture is intentionally a single-process modular CLI. The user has
pre-approved that obvious choice, so no unresolved architecture selection is
left in this document.

## CLI Interface

### Command

```text
nginx-stream-stats [OPTIONS] [INPUT]
```

`INPUT` is one nginx access-log path. If omitted or `-`, bytes are read from
standard input. The command never follows or tails a file; live streaming is
provided by a producer such as `tail -F access.log | nginx-stream-stats` and the
report is emitted when the stream closes or the process receives an interrupt.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit long-form RFC 4180 CSV; mutually exclusive with `--json` |
| `--strict` | flag, false | Stop at the first malformed non-empty line with exit code 3 |
| `--max-cardinality INTEGER` | positive integer, `250000` | Maximum exact distinct keys retained in each of the IP, error-URL, and User-Agent aggregators; exhaustion exits 4 |
| `--color / --no-color` | auto | Force or suppress color for text only; auto enables color only on a TTY |
| `--version` | flag | Print the installed version and exit 0 |
| `-h, --help` | flag | Print help and exit 0 |

Click owns syntactic validation, mutual exclusion, positive integer validation,
unknown options, and help formatting. JSON and CSV always ignore Rich styling
and write UTF-8 data to stdout.

### Inputs

- Supported MVP format: nginx **combined** access log, one record per line.
- Input is consumed incrementally as binary lines and decoded as UTF-8. A decode
  error is a malformed line in lenient mode and a data error in strict mode.
- Blank lines are malformed lines, not valid requests.
- `remote_addr` is counted as the client IP exactly as logged; proxy trust and
  `X-Forwarded-For` interpretation are outside scope.
- A valid request must contain a parseable request line, HTTP status `100..599`,
  and nginx timestamp with numeric UTC offset.
- The URL key is the request-target path with its query string removed. Absolute
  form is reduced to its path; an empty path becomes `/`. Percent encoding and
  trailing slashes are not rewritten.
- An absent User-Agent represented by `"-"` is counted as the literal unknown
  bucket `-`, preserving what nginx recorded.
- Gzip files are a P1 extension. In the P0 MVP, decompression is composed through
  stdin, for example `gzip -dc access.log.gz | nginx-stream-stats --json`.

### Outputs

The report includes `total_lines`, `total_valid_requests`, `malformed_lines`,
`top_ips`, `top_error_urls`, `hourly_request_distribution`,
`unique_user_agent_count`, and `unique_user_agent_share_percent`.

- `top_ips`: at most 10 `{ip, count}` entries over all valid requests.
- `top_error_urls`: at most 10 `{url, count}` entries considering only statuses
  400–599 and grouping 4xx and 5xx together.
- `hourly_request_distribution`: 24 ordered entries (`00` through `23`) in the
  local hour encoded in each log timestamp. Each percentage is exactly
  `100 × hourly_request_count / total_valid_requests`. With zero valid requests,
  processing fails with exit code 3, so there is no zero-denominator report.
- `unique_user_agent_share_percent` is
  `100 × unique_user_agent_count / total_valid_requests`. It is a diversity
  ratio, may exceed neither 100%, nor silently switch to an estimate.
- Percentages are numeric and rounded to six decimal places at serialization;
  computations retain full floating-point precision until that boundary.
- Top lists sort by count descending, then key ascending by Unicode code point,
  giving deterministic ties. Hour buckets always sort ascending.

Default text uses a summary plus three Rich tables and prints malformed-line
warnings to stderr. JSON has this stable shape:

```json
{
  "schema_version": 1,
  "total_lines": 120,
  "total_valid_requests": 118,
  "malformed_lines": 2,
  "top_ips": [{"ip": "192.0.2.1", "count": 30}],
  "top_error_urls": [{"url": "/login", "count": 7}],
  "hourly_request_distribution": [
    {"hour": "00", "request_count": 3, "percentage": 2.542373}
  ],
  "unique_user_agent_count": 12,
  "unique_user_agent_share_percent": 10.169492
}
```

CSV uses one header and long-form rows so heterogeneous metrics remain one
valid stream:

```text
schema_version,section,key,count,percentage
1,summary,total_valid_requests,118,
1,top_ip,192.0.2.1,30,
1,top_error_url,/login,7,
1,hour,00,3,2.542373
1,summary,unique_user_agent_count,12,
1,summary,unique_user_agent_share_percent,,10.169492
```

Summary rows also include `total_lines` and `malformed_lines`; all 24 hour rows
are emitted. CSV quoting is delegated to Python's `csv` module.

### Exit codes

| Code | Meaning | Examples |
|---:|---|---|
| `0` | Success | Report emitted, `--help`, or `--version` |
| `1` | Unexpected runtime or output failure | Broken internal invariant, unexpected exception, non-pipe stdout write failure |
| `2` | CLI usage/configuration error | Unknown option, conflicting formats, invalid cardinality limit |
| `3` | Input or log-data error | File cannot be opened/read, strict malformed line, or zero valid requests |
| `4` | Unique-cardinality exhaustion | Any exact distinct IP, error-URL, or User-Agent counter would exceed `--max-cardinality` |

A normal downstream pipe close is treated as successful termination without a
traceback. No final report is emitted after codes 3 or 4. Diagnostics go to
stderr and machine-readable stdout remains empty on failure.

## Architectural Decisions

### ADR-001: Single-process streaming pipeline

- **Decision:** One process, one reader, one parser, one aggregator, one renderer.
- **Why:** The workload is sequential text ingestion; IPC and merge logic would
  add overhead and nondeterminism within a one-weekend budget.
- **Rejected:** Multiprocessing chunks, because stdin is not seekable and chunk
  boundaries complicate quoted records and exact merges; microservices, because
  there is no networked product.

### ADR-002: Exact bounded counters

- **Decision:** Python dictionaries/sets retain exact counts, with a per-domain
  `--max-cardinality` ceiling and fail-closed exit code 4.
- **Why:** Top-10 and unique-share results remain exact while memory consumption
  is explicitly bounded.
- **Rejected:** HyperLogLog or sketches, because approximate output would change
  the metric contract; external sort, because it adds temporary persistence and
  extra passes.

### ADR-003: Shared report model, isolated renderers

- **Decision:** Aggregation creates one report dataclass consumed by text, JSON,
  and CSV renderers.
- **Why:** Metric semantics and ordering are tested once, while presentation
  remains format-specific and stdout stays deterministic.
- **Rejected:** Updating Rich tables while reading, because it couples terminal
  refresh costs to input size and does not work for pipeline formats.

### ADR-004: No database and no API/authentication

- **Decision:** No schema, migrations, persistence, HTTP endpoints, sockets,
  accounts, sessions, API keys, or authentication mechanism exist.
- **Why:** The process operates on caller-authorized local input and exits. OS
  file permissions and shell execution permissions are the correct trust
  boundary. Adding auth without a server or multi-user resource would create
  false complexity rather than security.

## Module and Package Structure

```text
pyproject.toml
src/nginx_stream_stats/
  __init__.py          package version surface
  cli.py               Click command, option validation, error-to-exit mapping
  models.py            LogRecord, RankedCount, HourBucket, AnalysisReport
  parser.py            combined-format line parser and ParseError
  aggregator.py        bounded exact counters and report finalization
  inputs.py            stdin/file/gzip stream ownership
  errors.py            typed usage, input, data, cardinality, runtime errors
  renderers/
    __init__.py
    text.py             Rich terminal output
    json.py             stable JSON schema v1
    csv.py              stable long-form CSV schema v1
tests/
  fixtures/
  unit/
  integration/
  performance/
```

Dependency direction is `cli -> inputs/parser/aggregator -> models`, with
renderers depending only on models. Parser and aggregator do not import Click
or Rich. Renderer modules never inspect raw log lines.

## Domain Model

All models use standard-library dataclasses with type annotations.

| Dataclass | Fields | Invariants |
|---|---|---|
| `LogRecord` | `ip: str`, `timestamp: datetime`, `method: str`, `url_path: str`, `protocol: str`, `status: int`, `user_agent: str` | Parsed only from a valid combined-format line; timestamp is timezone-aware |
| `RankedCount` | `key: str`, `count: int` | `count > 0` |
| `HourBucket` | `hour: int`, `request_count: int`, `percentage: float` | hour 0–23; percentage 0–100 |
| `AnalysisReport` | totals, tuples of ranked counts, 24 hour buckets, UA count/share, `schema_version: int = 1` | `total_valid_requests > 0`; malformed + valid equals total lines |

The mutable `StreamingAggregator` is an internal accumulator, not an output
model. Its state is three bounded cardinality collections, a fixed 24-element
integer list, and scalar totals. Finalization creates immutable tuples in the
report.

## Data Storage and Database

There are no database tables, files, caches, migrations, or retained
aggregates. Raw input is never copied to disk. This intentionally overrides
generic application templates that ask for three tables: fabricating tables
would violate the product's central constraint. Memory is released when the
process exits.

## HTTP API and Authentication

There are no HTTP endpoints, request/response bodies, ports, server lifecycle,
users, roles, tokens, cookies, or auth flow. The complete public interface is
the `## CLI Interface` contract above. Authorization is inherited from the
local operating system: if the invoking user can read the input and execute
the binary, the command may analyze it.

## Processing Semantics

For every binary line:

1. Increment `total_lines`.
2. Decode and parse the combined-log record.
3. On parse failure, increment `malformed_lines`; continue unless `--strict`.
4. Before inserting a new key, check that domain's cardinality ceiling. If it
   would be exceeded, raise the typed cardinality error mapped to code 4.
5. Increment IP count and the timestamp's hour bucket.
6. For status 400–599, increment the normalized error-URL count.
7. Insert the User-Agent into the exact set and increment valid total.

Finalization selects top entries with deterministic ordering. Initial
implementation may sort distinct keys because this cost is bounded by the
cardinality option; profiling may replace it with `heapq.nsmallest` while
preserving ordering. No renderer can alter metric values.

## Error Handling and Observability

- Expected failures are typed exceptions translated once in `cli.py` to codes
  2, 3, or 4 and a concise stderr diagnostic.
- Unexpected exceptions map to code 1. Tracebacks are hidden by default and
  enabled only through a developer environment variable.
- Lenient mode reports malformed count but never logs raw malformed lines,
  preventing accidental leakage of tokens or query strings.
- Progress output is absent because it would contaminate pipelines and add hot
  path overhead. Benchmark instrumentation belongs in tests, not production.

## Configuration and Environment Variables

All user-facing runtime configuration is explicit CLI input. There is no `.env`
file and no secret configuration.

| Variable | Default | Purpose |
|---|---|---|
| `NO_COLOR` | unset | Industry convention honored by text renderer to disable color |
| `NGINX_STREAM_STATS_DEBUG` | unset | Developer-only: when `1`, show unexpected exception traceback on stderr |

Environment variables never change metric semantics or output schemas.

## Packaging and Deployment

- Build backend: Hatchling or Setuptools configured only in `pyproject.toml`;
  select one during Step 1 and keep the dependency set minimal.
- Console entry point: `nginx-stream-stats = nginx_stream_stats.cli:main`.
- Runtime dependencies: compatible Click 8.x and Rich 13.x/14.x ranges pinned
  with safe lower and upper bounds after clean-environment testing.
- Target: local pip installation on Python 3.11 for Linux and macOS; Windows is
  best-effort for MVP because nginx log generation is usually Unix-hosted.
- Distribution: source distribution and universal pure-Python wheel.
- No Dockerfile, `docker-compose.yml`, service unit, cloud resource, or
  Kubernetes manifest is created. Containerization adds no value to a local
  pip CLI and would weaken the under-30-second startup-to-result workflow.

## Performance and Resource Contract

- Required benchmark: representative 1 GB combined log completes in less than
  30 seconds on a documented laptop using file input and text redirected to a
  file or `/dev/null`.
- Only one raw line and one `LogRecord` are live at a time; raw input is O(1)
  memory. Aggregate memory is O(distinct IPs + distinct error URLs + distinct
  User-Agents), hard-bounded per domain by `--max-cardinality`.
- Parsing avoids per-line Rich calls and datetime objects beyond fields needed
  for hour extraction. The implementation may parse the two-digit hour directly
  after validation if profiling demonstrates a material gain.
- Benchmark gates record elapsed wall time and peak RSS. A synthetic fixture
  must resemble real field lengths and cardinality; repeated one-line fixtures
  are invalid evidence.

## Security and Privacy Boundaries

Log content is untrusted data. It must never become a format string, terminal
markup instruction, file path, shell command, or executable expression. Rich
rendering disables markup for log-derived values; JSON/CSV use standard
encoders. The tool makes no network calls, writes no log-derived files, and
does not echo malformed raw records in diagnostics. Operators remain
responsible for access-log retention and terminal/pipeline destinations.

## Verification Strategy

- Unit tests cover valid and malformed combined records, IPv4/IPv6, escaping,
  timestamps, URL normalization, status boundaries, cardinality limits,
  deterministic ties, and formulas.
- CLI integration tests cover file/stdin parity, TTY/color behavior, clean
  stdout, JSON schema, CSV round-trip, broken pipe, and codes `0/1/2/3/4`.
- Property tests are optional P2; a fixed adversarial corpus is P0.
- The performance test is opt-in locally, mandatory for release, and records
  its machine baseline.

Implementation steps and exact verification commands are specified in
`IMPLEMENTATION_PLAN.md`; product acceptance is specified in `PRD.md`.
