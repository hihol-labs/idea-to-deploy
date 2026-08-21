# Project Architecture: Nginx Stream Analyzer

## 1. Context and Constraints

The product is a local Python 3.11 command-line program for one-shot analysis of nginx combined access logs. It must process a 1 GB input in under 30 seconds on a declared laptop, remain pipeline-friendly, cost $0, and be deliverable in one weekend.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the four reports need only one-pass counters and sets, persistence creates cleanup and privacy obligations, and retaining raw traffic data adds no MVP value. An HTTP API is incorrect because the target interaction is local files/stdin and shell pipelines; a server would add lifecycle, binding, authentication, concurrency, and deployment concerns without improving the required workflow.

There is no authentication: the process has only the invoking user's filesystem permissions. There is no Docker, cloud, server, or Kubernetes deployment. Distribution is a pip-installable package and wheel.

## 2. Architecture Decision

The approved architecture is a single process with layered modules:

```text
file path / stdin
       |
       v
 line iterator -> nginx parser -> valid request dataclass
       |                 |                |
       |                 +-> invalid count|
       v                                  v
 input errors                    streaming accumulator
                                           |
                                           v
                                  immutable report model
                                   /       |       \
                               Rich      JSON      CSV
```

This is the obvious fit for a solo, one-weekend CLI: process startup is cheap, data does not cross process boundaries, and parsing/aggregation/rendering remain independently testable. Multi-process parsing is deferred because coordination and merge overhead are not justified until profiling shows CPU saturation and a measurable benefit.

## 3. Component Boundaries

| Module | Responsibility | Must not do |
|---|---|---|
| `src/nginx_stream_analyzer/cli.py` | Click command, option validation, input/output selection, exit mapping | Parse nginx syntax or calculate metrics |
| `src/nginx_stream_analyzer/parser.py` | Convert one supported log line into `AccessRecord` or a typed parse failure | Read whole files or print |
| `src/nginx_stream_analyzer/models.py` | Frozen dataclasses for parsed records, counters, and report rows | Perform I/O |
| `src/nginx_stream_analyzer/aggregate.py` | Update streaming counters and enforce cardinality budget | Format terminal/JSON/CSV output |
| `src/nginx_stream_analyzer/report.py` | Finalize ordering, percentages, and stable report model | Open input files |
| `src/nginx_stream_analyzer/renderers/text.py` | Rich terminal tables and summaries | Emit ANSI codes when color is disabled |
| `src/nginx_stream_analyzer/renderers/json.py` | Stable JSON object | Add display-only strings |
| `src/nginx_stream_analyzer/renderers/csv.py` | Stable long-form CSV rows | Emit multiple incompatible header blocks |
| `src/nginx_stream_analyzer/errors.py` | Typed operational errors and exit-code constants | Swallow unexpected defects |

## 4. Data Model and Streaming State

There are no database tables. The in-memory structures are complete and intentionally ephemeral:

| Dataclass/state | Fields and types | Invariant |
|---|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `method: str`, `url: str`, `protocol: str`, `status: int`, `bytes_sent: int | None`, `user_agent: str` | Created only from a valid supported log line |
| `AnalysisState` | `ip_counts: Counter[str]`, `error_url_counts: Counter[str]`, `hour_counts: list[int]` of length 24, `user_agents: set[str]`, `total_valid_requests: int`, `invalid_lines: int` | Counts update once per line; cardinality checked before insertion |
| `RankedRow` | `key: str`, `count: int`, `percentage: float | None` | Rankings sort by count descending, then key ascending |
| `AnalysisReport` | `top_ips: tuple[RankedRow, ...]`, `top_error_urls: tuple[RankedRow, ...]`, `hourly_distribution: tuple[RankedRow, ...]`, `unique_user_agent_count: int`, `unique_user_agent_share: float`, `total_valid_requests: int`, `invalid_lines: int` | Immutable renderer input |

Hourly request distribution for hour `h` is the percentage `100 × hourly_request_count / total_valid_requests`. Unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`. When `total_valid_requests` is zero, both percentage families are `0.0`, and the run follows the data-validity exit contract below.

To avoid accidental unbounded growth, the implementation defines one total unique-key budget across IPs, error URLs, and User-Agents (initial default: 5,000,000 distinct retained keys, configurable only through an internal constant in MVP). Before adding a new unique key, the accumulator checks the budget. Exhaustion stops processing and exits `4`; it never emits a misleading partial success report.

## 5. Parsing Contract

MVP input is nginx's standard combined log format with a quoted request and User-Agent. Parsing is line-oriented and locale-independent. The timestamp offset is honored while the hourly bucket uses the hour as recorded in the log entry, preserving the operational meaning of the source log.

- Blank and malformed lines increment `invalid_lines` and processing continues.
- Status must be a three-digit integer from 100 through 599.
- A request equal to `"-"` is invalid because URL and method cannot be derived.
- The URL ranking uses the request target exactly as logged, including query string.
- Error URLs include status codes 400–599 only.
- Byte count `-` maps to `None` and is not otherwise aggregated.
- Input is decoded as UTF-8 with replacement for invalid byte sequences so a single bad byte cannot terminate a large run.

If at least one valid record exists, malformed records are reported as metadata but do not change exit code `0`. If the input is non-empty and has zero valid records, exit code `3` applies.

## CLI Interface

### Command

```text
nginx-stream-analyzer [OPTIONS] [INPUT]
```

`INPUT` is a path to a regular log file. Omit it or pass `-` to read stdin. At most one input is analyzed per invocation.

### Options

| Option | Meaning | Default/validation |
|---|---|---|
| `--json` | Emit one JSON document | Mutually exclusive with `--csv` |
| `--csv` | Emit long-form CSV | Mutually exclusive with `--json` |
| `--no-color` | Disable Rich color in text mode | JSON/CSV are always color-free |
| `--version` | Print package version and exit | Exit `0` |
| `--help` | Print Click help and exit | Exit `0` |

The `NO_COLOR` environment variable and a non-TTY output also disable ANSI color. There are no product-specific environment variables.

### Outputs

Text mode prints: input summary, top 10 IPs, top 10 4xx/5xx URLs, all 24 hourly percentages (including zero hours), and unique User-Agent count/share. Ties in top-10 sections are deterministic: count descending, key ascending.

JSON schema:

```json
{
  "schema_version": 1,
  "total_valid_requests": 0,
  "invalid_lines": 0,
  "top_ips": [{"ip": "string", "count": 0}],
  "top_error_urls": [{"url": "string", "count": 0}],
  "hourly_distribution": [{"hour": 0, "request_count": 0, "percentage": 0.0}],
  "unique_user_agents": {"count": 0, "percentage": 0.0}
}
```

CSV uses one header and a normalized schema:

```text
schema_version,section,key,count,percentage
```

Rows use sections `top_ip`, `error_url`, `hour`, `unique_user_agents`, and `summary`. Percentage is empty where not applicable. JSON and CSV go to stdout; diagnostics go to stderr.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Analysis completed successfully; empty input also yields a valid empty report |
| `1` | Input/output operational failure, such as unreadable input, broken file, or write failure |
| `2` | CLI usage error, including an invalid option or `--json` with `--csv` |
| `3` | Data-format failure: non-empty input contained zero valid supported log records |
| `4` | Unique-cardinality exhaustion: the configured distinct-key budget was exceeded |

Unexpected internal defects are not remapped to a success or data error; Click reports the failure and the process returns `1` after a concise diagnostic in normal mode.

## 7. Algorithm and Performance

The input is consumed exactly once. Each valid record performs constant-time average counter/set updates. For `n` lines and `u` distinct retained keys, time is `O(n + u log 10)` (effectively `O(n + u)`), and memory is `O(u)` bounded by the cardinality budget plus fixed 24-hour state. Final top-10 values use `heapq.nlargest` or `Counter.most_common` followed by deterministic tie ordering; the implementation must not sort all raw requests or retain log lines.

The performance acceptance fixture is exactly documented with size, line count, unique cardinalities, storage medium, Python version, and laptop CPU/RAM. The target is wall-clock under 30 seconds for 1 GB after one warm-up run; correctness hashes belong in test evidence, not user-facing product output.

## 8. Packaging and Runtime

- `pyproject.toml` declares Python `>=3.11,<4`, Click, and Rich.
- Console entry point: `nginx-stream-analyzer = nginx_stream_analyzer.cli:main`.
- Build artifacts are a source distribution and universal Python wheel.
- No daemon, port, process supervisor, migration, database, container, or remote service exists.
- Supported platforms are Linux and macOS for MVP; Windows is best-effort until CI coverage is added.

## 9. Security and Privacy

Log contents are untrusted data, never shell commands or Rich markup. Renderers escape terminal markup and use serialization libraries to quote JSON/CSV. The tool makes no network calls and retains no data after process exit. It follows symlinks under the invoking user's filesystem permissions and never writes beside the input unless the shell redirects stdout. Diagnostics avoid echoing entire log lines or User-Agent values.

## 10. Test Architecture

| Layer | Evidence |
|---|---|
| Parser unit tests | Valid combined lines, escaping, IPv4/IPv6, timestamps, malformed requests/statuses, invalid bytes |
| Aggregation unit tests | 4xx/5xx boundary values, ties, 24 buckets, exact percentages, cardinality exhaustion |
| Renderer contract tests | JSON schema, single-header CSV, no ANSI in machine formats, stable order |
| CLI integration tests | File/stdin parity, option exclusion, stderr/stdout separation, exits `0/1/2/3/4` |
| Performance test | Generated 1 GB fixture and peak-memory/cardinality record on reference laptop |

## 11. Architecture Decision Records

### ADR-001: Single-process layered CLI

**Status:** Accepted from the approved project constraints. A single process minimizes delivery and operational complexity while preserving module boundaries for testing.

### ADR-002: Exact streaming counters with a hard cardinality budget

**Status:** Accepted. Exact metrics are preferable for incident triage, but exact distinct values cannot be memory-constant; explicit exhaustion with exit `4` is safer than an undocumented approximate result.

### ADR-003: Stable normalized CSV

**Status:** Accepted. A single long-form table is composable in shell, spreadsheet, and analytics tools, unlike separate CSV sections with changing headers.

Relevant alternatives remain GoAccess for interactive local reports, Elastic-based stacks for persisted search, AWStats for historical web analytics, and `grep`/`awk` for bespoke one-offs. They are product alternatives, not hidden runtime dependencies.
