# Project Architecture: nginx-logtop

## Architecture Summary

The selected design is an installable Python 3.11 package exposing one Click command, `nginx-logtop`. A single process opens one input stream at a time, parses each line into a dataclass, and updates bounded aggregators. After end-of-input it renders exactly one of three presentation formats. There is no background worker, network listener, or persisted state.

The governing decision is: **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because this product computes an ephemeral summary in one pass and makes no promise of history, query, or sharing; storage would add I/O, schema lifecycle, privacy exposure, and operating burden without helping the required metrics. An HTTP API is incorrect because the user and data are already on the same machine, pipeline integration is served by stdin/stdout and exit codes, and a server would introduce authentication, binding, deployment, and lifecycle problems explicitly outside scope.

## Architecture Decision and Alternatives

### Selected: single-process streaming pipeline

- **Approach:** synchronous iterator pipeline with isolated parser, aggregation, and renderer modules.
- **Why selected:** the stack and operational constraints are pre-approved; all required aggregates fit a one-pass model; a single process minimizes copies, coordination, and weekend delivery risk.
- **Complexity:** Low.

### Considered and rejected

| Alternative | Benefit | Reason rejected |
|---|---|---|
| Multiprocessing parser/aggregation | Potential CPU parallelism | IPC, partition merge logic, input ordering, and duplicated cardinality state add complexity before profiling proves need |
| Embedded SQLite | Queryable intermediate results | Violates statelessness and adds disk I/O/schema lifecycle for no required query |
| Logstash/Elastic service pipeline | Retention and rich analysis | Violates local CLI, $0 operational budget, and one-weekend scope |
| Shell pipeline | No install step | Quoted nginx fields, cross-platform behavior, error reporting, and stable machine schemas are too fragile |

No interactive architecture choice remains: the obvious single-process variant was explicitly approved. No adversarial review is represented in this document; that review is reserved for a separate external session.

## Component Boundaries

```text
file path(s) / stdin
        |
        v
 InputSource iterator  -> I/O error -> exit 1
        |
        v
 NginxLineParser       -> invalid-line counter -> exit 3 if no valid records
        |
        v
 AccessRecord dataclass
        |
        v
 StreamingAggregator  -> unique-UA ceiling -> exit 4
        |
        v
 Report dataclasses
        |
        +---- TextRenderer (Rich; default)
        +---- JsonRenderer (stdlib json)
        `---- CsvRenderer (stdlib csv)
                       |
                       v
                    stdout
```

| Module | Responsibility | Must not do |
|---|---|---|
| `nginx_logtop/cli.py` | Click command, option validation, stream orchestration, exception-to-exit mapping | Parse log grammar or calculate metrics |
| `nginx_logtop/input.py` | Open stdin/files as text iterators and attach source/line metadata | Buffer a complete file |
| `nginx_logtop/parser.py` | Convert one supported line into `AccessRecord` or a typed parse failure | Render output or exit the process |
| `nginx_logtop/models.py` | Dataclasses and domain exceptions | I/O or global mutable state |
| `nginx_logtop/aggregate.py` | Update counters and exact User-Agent set; finalize deterministic report records | Know Rich/JSON/CSV presentation details |
| `nginx_logtop/renderers/text.py` | Human-readable Rich tables | Emit machine-contract JSON/CSV |
| `nginx_logtop/renderers/json.py` | Stable JSON document | Add ANSI or locale-specific formatting |
| `nginx_logtop/renderers/csv.py` | Stable tidy CSV rows | Create multiple ambiguous streams/files |

## Technology Stack

| Layer | Choice | Contract |
|---|---|---|
| Runtime | CPython 3.11+ | Supported release baseline is 3.11 |
| CLI | Click | One command; usage mistakes map to exit `2` |
| Terminal | Rich | Color on a TTY by default, controllable with explicit options |
| Data | `dataclasses`, `collections.Counter`, `set` | In-memory state only; no database |
| Serialization | `json`, `csv` | Standard-library deterministic machine output |
| Packaging | `pyproject.toml`, `src/` layout | Console script `nginx-logtop` |
| Tests | pytest | Unit, integration, golden output, and benchmark tests |

## Data Model and In-Memory State

There are no database tables. The generic blueprint database template is intentionally inapplicable. These are the complete transient records instead:

### `AccessRecord`

| Field | Python type | Constraint / meaning |
|---|---|---|
| `client_ip` | `str` | Non-empty source token; IPv4/IPv6 text is preserved |
| `timestamp` | `datetime` | Parsed nginx timestamp with its numeric UTC offset |
| `method` | `str` | Non-empty request method, or `"-"` for nginx's missing request marker |
| `request_target` | `str` | Original request target token |
| `url_path` | `str` | Path used for URL ranking; query and fragment excluded |
| `protocol` | `str` | HTTP protocol token or `"-"` |
| `status` | `int` | Integer in `100..599` |
| `bytes_sent` | `int | None` | Non-negative integer; nginx `-` becomes `None` |
| `user_agent` | `str` | Quoted combined-log User-Agent; `-` is a valid literal category |
| `source` | `str` | File path or `<stdin>` for diagnostics only |
| `line_number` | `int` | One-based positive line number for diagnostics |

### `AggregationState`

| Field | Python type | Bound / invariant |
|---|---|---|
| `total_valid_requests` | `int` | Starts at zero; increments once per valid record |
| `invalid_lines` | `int` | Starts at zero; increments per rejected non-empty line |
| `ip_counts` | `Counter[str]` | Exact counts; cardinality is naturally bounded by input |
| `error_url_counts` | `Counter[str]` | Updated only for status `400..599` |
| `hour_counts` | `list[int]` | Exactly 24 counters indexed `0..23` using the timestamp's logged offset |
| `unique_user_agents` | `set[str]` | Exact values, bounded by `max_unique_user_agents` |
| `max_unique_user_agents` | `int` | Positive configured ceiling; default `1_000_000` |

### Final report records

`RankedCount(rank: int, value: str, count: int, percentage: float)`, `HourlyShare(hour: int, count: int, percentage: float)`, and `Report(total_valid_requests: int, invalid_lines: int, top_ips: tuple[RankedCount, ...], top_error_urls: tuple[RankedCount, ...], hourly_distribution: tuple[HourlyShare, ...], unique_user_agents: int, unique_user_agent_share_percent: float)` are immutable final values. Ranking is descending count then ascending key; only ten ranked entries are emitted. Percentages are numeric values rounded only during rendering.

## Log Parsing Contract

- MVP accepts nginx Combined Log Format: `$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"`.
- Input is decoded as UTF-8 with strict error handling. A decode failure is a data-format error under exit `3`, never silently replaced.
- The parser is anchored to the complete line and respects quoted request, referer, and User-Agent fields.
- Blank or malformed lines increment `invalid_lines` and processing continues. A concise diagnostic is written to stderr at the end; individual bad lines are not echoed, avoiding accidental log-data leakage.
- If at least one record is valid, invalid lines do not change a successful exit. If none are valid, exit `3`.
- URL error ranking covers both 4xx and 5xx (`400..599`) together. It uses the parsed request path without query or fragment; an unparseable/missing request token uses `-`.
- Hourly request distribution uses 24 hour-of-day buckets (`00` through `23`) from each log timestamp in its recorded offset. Each percentage is exactly `100 × hourly_request_count / total_valid_requests`.
- Unique User-Agent share is `100 × distinct_user_agent_count / total_valid_requests`. It is an exact percentage; if a new distinct value would exceed the configured ceiling, processing stops with exit `4` rather than estimating.

## CLI Interface

### Command and invocation

```text
nginx-logtop [OPTIONS] [INPUTS]...
```

With no `INPUTS`, the command reads stdin. One or more paths are processed in argument order as a logical stream. `-` explicitly selects stdin and may appear at most once. The MVP reads uncompressed text; gzip support is a P1 feature.

### Options

| Option | Type / default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one JSON object; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit one tidy CSV document; mutually exclusive with `--json` |
| `--color / --no-color` | auto by TTY | Force or suppress ANSI styling; machine formats never contain ANSI |
| `--max-unique-user-agents INTEGER` | `1_000_000` | Positive exact-cardinality ceiling; exhaustion exits `4` |
| `--version` | flag | Print package version and exit `0` |
| `--help` | flag | Print Click help and exit `0` |

### Inputs

- UTF-8 nginx Combined Log Format from regular files or stdin.
- Streams are read line by line; seekability is not required.
- A missing, unreadable, or non-regular named input fails with exit `1` and a concise stderr message.

### Outputs

- stdout contains only the selected report format; diagnostics go to stderr.
- Default text: title/summary plus four Rich sections. When output is not a TTY, color is disabled unless forced.
- JSON: one object with `schema_version`, `total_valid_requests`, `invalid_lines`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`. Ranked entries contain `rank`, `value`, `count`, and `percentage`; `user_agents` contains `unique_count` and `share_percent`.
- CSV: one header `section,rank,key,count,percentage`, followed by `top_ip`, `top_error_url`, `hour`, and `user_agents` rows. For the User-Agent summary, `key=unique`, `count` is distinct count, and `percentage` is its share. Unused `rank` values are empty.
- Empty input produces no report and exit `3`.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Report completed successfully (also help/version) |
| `1` | Operational failure: input open/read failure, broken non-pipeline output, or unexpected internal runtime failure |
| `2` | CLI usage error from invalid options/arguments or mutually exclusive formats |
| `3` | Input/data-format failure: invalid UTF-8, empty input, or no valid combined-log records |
| `4` | Unique-cardinality exhaustion: exact User-Agent set would exceed `--max-unique-user-agents` |

SIGINT follows conventional shell behavior (Click maps the interruption rather than presenting it as one of the product's report outcomes). A downstream closed pipe is treated as successful pipeline termination when no other failure occurred; other output failures use `1`.

## Output Determinism

- Counts sort descending, then keys sort by Unicode code point ascending.
- All 24 hourly rows are present, including zero-count hours.
- JSON keys and array order are stable; JSON ends with one newline.
- CSV uses RFC 4180-compatible quoting through Python's `csv` module and `\n` record terminators.
- Percentage values use a documented fixed precision of two decimal places in text/CSV and JSON numeric values; tests use the unrounded counts as the source of truth.
- Text snapshots strip or disable ANSI. Machine formats never depend on locale or terminal width.

## Performance and Resource Model

The input file is never loaded as a whole. Runtime is expected O(n + k log 10), where n is valid lines and k is unique keys finalized for ranking; exact counters and the User-Agent set make memory O(unique IPs + unique error paths + unique User-Agents). `Counter.most_common` may inspect all keys at finalization, but output remains top ten.

The release gate is a generated, reproducible 1 GB combined-log fixture processed in under 30 seconds on a documented laptop. The benchmark records Python version, CPU, memory, storage, command, wall time, and peak RSS. The implementation should first meet correctness, then profile parser allocations, URL splitting, and counter updates. No concurrency is added without evidence that it improves the same gate.

## Error Handling and Security

- Domain exceptions (`InputError`, `DataFormatError`, `UniqueCardinalityExhausted`) carry safe context and are mapped centrally in `cli.py`.
- Diagnostics name a source and aggregate invalid count but do not echo full log lines, referers, User-Agents, or query strings.
- Input is data only; it is never evaluated, interpolated into a shell command, or used as an output path.
- Rich markup is escaped for log-derived values.
- Symlinks may be read as ordinary user-selected paths; special devices/directories are rejected except stdin.
- Dependencies are pinned by compatible bounds in packaging and checked before release.

## Packaging and Deployment

Deployment means installing a local package with `pip` or preferably `pipx`. There is no container, Docker Compose file, service manager, cloud environment, Kubernetes manifest, environment-variable contract, authentication mechanism, secret, database migration, or HTTP endpoint. Configuration is entirely explicit CLI input. This absence is an architectural constraint, not missing documentation.

Target package layout:

```text
pyproject.toml
src/nginx_logtop/
  __init__.py
  cli.py
  input.py
  parser.py
  models.py
  aggregate.py
  renderers/
    __init__.py
    text.py
    json.py
    csv.py
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_cli.py
  test_performance.py
```

## Architecture Acceptance Checklist

- One streaming pass produces all four metrics without retained state.
- The terminal, JSON, and CSV outputs are presentations of the same finalized report.
- The literal database/API decision remains enforced.
- The exact hourly formula and User-Agent share definition are tested on golden data.
- Exit codes `0/1/2/3/4`, especially unique-cardinality exhaustion code `4`, are integration-tested.
- The documented 1 GB performance gate passes before release.
