# Project Architecture: `nginx-top`

## 1. Context and Constraints

`nginx-top` is a local Python 3.11 CLI that reads nginx combined access logs, produces four summaries, and exits. The approved architectural decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema management, cleanup, and I/O without benefiting a one-shot report whose source is already an append-only log. An HTTP API would add a resident process, network security, lifecycle management, and serialization surface while the target users already work in terminals and pipelines. Streaming locally minimizes setup, cost, and exposure of potentially sensitive IP and User-Agent data.

### Quality attributes

- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Never load the complete log or retain complete request records.
- Produce deterministic output for identical input and options.
- Count malformed lines explicitly; exclude them from metrics.
- Bound unique-key growth and fail with a specific exit code rather than risking uncontrolled memory use.
- Emit no ANSI escape sequences in JSON or CSV.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** one Python process performs read → parse → aggregate → rank → render.
- **Pros:** minimal overhead, deterministic failure semantics, straightforward stdin support, easy pip distribution.
- **Cons:** limited to one CPU core in the MVP; exact cardinality consumes memory proportional to distinct values.
- **Best for:** local one-off analysis up to the stated 1 GB target.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunk parsing

- **Approach:** split regular files into byte ranges, parse in workers, and merge partial counters.
- **Pros:** potential multicore throughput.
- **Cons:** complex newline boundaries, counter merge memory spikes, unsuitable for stdin, harder deterministic diagnostics.
- **Best for:** multi-gigabyte regular files after profiling proves CPU parsing is the bottleneck.
- **Estimated complexity:** High.

### Variant C: External sort and shell pipeline

- **Approach:** parse fields then delegate grouping/ranking to operating-system tools.
- **Pros:** can spill to disk and reuse optimized utilities.
- **Cons:** platform-dependent, multiple passes/processes, weaker pip-only experience, fragile CSV/JSON integration.
- **Best for:** environments with strict memory limits and standardized Unix tooling.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the product decisions explicitly favor an obvious single-process, stateless CLI and a one-weekend delivery. Variant B remains a post-MVP option only if measurement shows Variant A cannot meet the performance target.

## 3. Component Model

```text
file path or stdin
        |
        v
  InputSource (text iterator)
        |
        v
  CombinedLogParser ----invalid----> Diagnostics counter
        |
      LogRecord dataclass
        |
        v
  StreamingAggregator
    | IP counts
    | error URL counts
    | 24 hourly counts
    | User-Agent set + cardinality guard
        |
        v
  ReportSnapshot dataclass
        |
        +----> Rich text renderer
        +----> JSON renderer
        +----> normalized CSV renderer
```

Only the compact parsed fields required by aggregation live for one iteration. The aggregator retains counters keyed by distinct IPs and error URLs, a 24-element hourly counter, and a set of unique User-Agent strings. The configured cardinality ceiling prevents unbounded growth.

## 4. Planned Source Layout

```text
pyproject.toml
src/nginx_top/
  __init__.py
  cli.py
  errors.py
  models.py
  input.py
  parser.py
  aggregate.py
  report.py
  renderers/
    __init__.py
    terminal.py
    json.py
    csv.py
tests/
  unit/
  integration/
  performance/
  fixtures/
```

| Module | Responsibility |
|---|---|
| `cli.py` | Click command, option validation, orchestration, exception-to-exit mapping |
| `input.py` | UTF-8 text iteration from one file or stdin (`-`), with I/O error normalization |
| `parser.py` | Precompiled parser for the supported combined-log grammar and timestamp normalization |
| `models.py` | Frozen `LogRecord`, `RankedItem`, and `ReportSnapshot` dataclasses |
| `aggregate.py` | Stateful single-pass counters, exact User-Agent set, limits, deterministic snapshot |
| `report.py` | Shared percentages, ordering, and serializer-neutral report schema |
| `renderers/*` | Presentation only; no metric calculation |
| `errors.py` | Typed operational and cardinality exceptions |

## 5. Data Contracts

### Supported input grammar

The MVP supports the conventional nginx combined access-log shape:

```text
remote_addr - remote_user [local_time] "METHOD target PROTOCOL" status bytes "referer" "user_agent"
```

- Input is UTF-8 text; decoding errors are invalid lines, not replacement characters.
- `remote_addr` accepts the logged token, including IPv4 or IPv6 text; the MVP does not perform DNS lookup.
- `local_time` must include a numeric UTC offset. The hour bucket is the hour as recorded in the log's local timestamp, from `00` through `23`.
- `target` is ranked exactly as logged, including query strings. Normalizing query strings is out of scope.
- Error URLs include status codes 400–599 only.
- A lone `-` User-Agent is treated as missing: the request remains valid but contributes no unique User-Agent value.
- Blank and malformed lines increment `invalid_lines` and do not contribute to `total_valid_requests` or any percentage denominator.

### Domain records

| Dataclass | Field | Type | Invariant |
|---|---|---|---|
| `LogRecord` | `remote_addr` | `str` | Non-empty |
|  | `timestamp` | `datetime` | Timezone-aware |
|  | `target` | `str` | Non-empty request target |
|  | `status` | `int` | 100–599 |
|  | `user_agent` | `str \| None` | `None` for logged `-` |
| `RankedItem` | `value` | `str` | IP or URL label |
|  | `count` | `int` | Positive |
| `ReportSnapshot` | `total_lines` | `int` | Valid + invalid |
|  | `total_valid_requests` | `int` | Non-negative |
|  | `invalid_lines` | `int` | Non-negative |
|  | `top_ips` | `tuple[RankedItem, ...]` | At most 10 |
|  | `top_error_urls` | `tuple[RankedItem, ...]` | At most 10 |
|  | `hourly_percentages` | `tuple[float, ...]` | Exactly 24 entries |
|  | `unique_user_agents` | `int` | Non-negative |
|  | `unique_user_agent_share_percent` | `float` | Non-negative |

Ties in ranked reports sort by count descending and then label ascending. Percentages are rounded only by renderers; JSON numeric values use four decimal places of precision.

Hourly request distribution is a percentage computed for every hour with the literal formula `100 × hourly_request_count / total_valid_requests`. If `total_valid_requests` is zero, all 24 percentages are `0.0`.

Unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`. Missing User-Agent values do not increase the numerator. If there are no valid requests, the share is `0.0`.

### JSON schema

The top-level object has stable keys: `schema_version`, `source`, `summary`, `top_ips`, `top_error_urls`, `hourly_request_distribution`, and `user_agents`. Ranked arrays contain `{value, count}` objects; the hourly array contains `{hour, request_count, percentage}` objects for all 24 hours; diagnostics expose `total_lines`, `total_valid_requests`, and `invalid_lines`.

### CSV schema

CSV writes one header and normalized rows with columns:

```text
schema_version,report,rank,key,count,percentage
```

`report` is one of `summary`, `top_ip`, `top_error_url`, `hour`, or `user_agent`. Non-applicable cells are empty. The fixed schema permits a single stdout stream while retaining all four reports and diagnostics.

## CLI Interface

### Command

```text
nginx-top [OPTIONS] INPUT
```

`INPUT` is exactly one path or `-` for stdin. The tool reads once and writes one report to stdout. Diagnostics and errors go to stderr so machine output remains parseable.

### Options

| Option | Meaning | Default / validation |
|---|---|---|
| `--json` | Emit the versioned JSON object | Mutually exclusive with `--csv` |
| `--csv` | Emit normalized CSV rows | Mutually exclusive with `--json` |
| `--color / --no-color` | Force or suppress terminal color | Auto: color only when stdout is a TTY; invalid with machine modes if forced on |
| `--max-unique INTEGER` | Maximum distinct values allowed in any guarded set/counter | `1_000_000`; positive integer |
| `--version` | Print version and exit | No input processing |
| `--help` | Print usage and exit | Click-standard behavior |

Default output is Rich terminal text with a summary, two top-10 tables, a 24-hour distribution, and User-Agent statistics. JSON and CSV output never contain ANSI color escapes. An empty input is a successful empty report. A non-empty input with zero valid records exits with code 3 after emitting diagnostics and no report.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Successful report, including a truly empty input |
| `1` | Operational failure: input open/read error, decode failure at stream level, broken output other than normal downstream pipe closure, or unexpected internal error |
| `2` | CLI usage error: invalid option/value, missing input, conflicting output flags |
| `3` | Data error: non-empty input contains zero valid log records |
| `4` | Unique-cardinality exhaustion: a configured distinct-value ceiling would be exceeded |

Invalid lines mixed with valid records do not change a successful exit code; their count is always reported. A normal broken pipe caused by a downstream consumer closing early is treated as successful termination.

## 7. Processing and Resource Model

For each line, the parser either increments invalid diagnostics or yields one frozen record. The aggregator updates the IP counter, optional error-URL counter, one hourly bucket, and optional User-Agent set. At end of stream, `heapq.nsmallest`/equivalent bounded selection produces ten deterministic leaders without sorting all keys.

- Time complexity: `O(n + u log 10)`, where `n` is lines and `u` is distinct ranked keys.
- Memory complexity: `O(i + e + a)`, where `i`, `e`, and `a` are distinct IPs, error URLs, and User-Agents, each guarded by `--max-unique`.
- The cardinality check occurs before inserting a new key. Crossing any ceiling raises the typed exhaustion error and maps to exit code 4.
- No temporary files or persistent state are created.

## 8. Security and Privacy

- Treat log content as untrusted data: never evaluate it, expand escapes into control sequences, or construct shell commands from it.
- Rich text must escape markup/control characters from IP, URL, and User-Agent values.
- JSON and CSV use standard-library encoders.
- Do not send logs, derived values, or telemetry over a network.
- Error messages show the source name and line number but do not echo a complete malformed line by default.
- Reject non-regular special file paths where platform behavior could block unexpectedly; stdin remains explicitly supported.

Authentication is intentionally absent because there is no service, account, privilege boundary, or network listener. Access control is inherited from local filesystem permissions and the invoking operating-system user.

## 9. Deployment and Configuration

Deployment is a pip-installed wheel with the `nginx-top` console entry point, supporting Python 3.11. There is no Docker image, compose stack, cloud target, daemon, or Kubernetes manifest. Runtime behavior is configured only through CLI options; there are no required environment variables or secrets.

Release artifacts are an sdist and wheel built from `pyproject.toml`. The release gate installs the wheel into a clean virtual environment, runs `nginx-top --version`, integration fixtures for all formats, and the documented performance benchmark.

## 10. Observability

The CLI exposes per-run diagnostics in every output mode: source label, total lines, valid requests, invalid lines, and elapsed seconds. It does not emit telemetry. Optional benchmark instrumentation records peak RSS in the test harness, not the product output contract.

## 11. Architecture Decision Record

### ADR-001: Select a single-process streaming CLI

- **Status:** Accepted from the pre-approved product and architecture brief.
- **Decision:** Use Variant A and the literal constraint **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- **Consequences:** minimal install/operation cost and local data handling; exact distinct-value memory must be guarded; horizontal scaling and retained queries are out of scope.
- **Rejected:** database-backed analytics, a resident HTTP service, Kubernetes, and a multiprocess MVP.

### Review boundary

No Devil's Advocate or independent adversarial review was performed in this blueprint session. The external harness owns that fresh-session review and any resulting artifact; this document does not pre-empt its verdict.

