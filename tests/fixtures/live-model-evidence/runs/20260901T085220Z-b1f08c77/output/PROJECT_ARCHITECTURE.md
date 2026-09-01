# Project Architecture: nginx-stream-insights

## Architecture Summary

The product is one installable Python 3.11 process with a linear data path:

```text
file path or stdin
        |
        v
buffered text iterator -> nginx parser -> streaming aggregator -> result snapshot
                                                               -> Rich terminal renderer
                                                               -> JSON renderer
                                                               -> normalized CSV renderer
```

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is wrong because the required outputs can be accumulated during one scan and the product must retain no logs or state. An HTTP API is wrong because the operator already has the file or byte stream locally; a server would add authentication, lifecycle, networking, and security work without improving the four required analyses.

One process is also the correct architecture: parsing and aggregation are CPU-local operations, counters are cheap to update, and multiprocessing would add serialization, ordering, and cross-platform complexity before measurement proves it necessary.

## Architecture Decision

### Selected: single-process streaming pipeline

- **Approach:** Click owns the command boundary; a buffered iterator feeds a pure parser; valid records update a single aggregator; one selected renderer emits the final snapshot.
- **Advantages:** one pass, predictable lifecycle, easy stdin support, minimal dependencies, deterministic tests, and no operational footprint.
- **Trade-off:** exact unique User-Agent counting can grow with cardinality, so it is explicitly bounded and fails closed with exit code 4.
- **Complexity:** Low.

### Considered: external Unix pipeline

- **Approach:** compose `awk`, `sort`, `uniq`, and related tools for each metric.
- **Advantages:** no package installation on many systems.
- **Rejected because:** repeated scans and format-specific scripts produce fragile, inconsistent parsing and no unified JSON/CSV or exit-code contract.

### Considered: embedded analytical engine

- **Approach:** load or query logs through SQLite/DuckDB or a dataframe.
- **Advantages:** flexible ad hoc queries.
- **Rejected because:** adds storage/query machinery, undermines strict streaming memory behavior, and exceeds the fixed four-metric requirement.

The selected architecture is pre-approved by the product brief. No database, API-style, authentication, or deployment variants are offered because those components are explicitly out of scope.

## CLI Interface

### Command

```text
nginx-stream-insights [OPTIONS] [INPUT]
```

`INPUT` is an optional nginx access-log path. Omit it or pass `-` to read stdin. Exactly one report is written to stdout; diagnostics go to stderr.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit exactly one UTF-8 JSON object; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit UTF-8 RFC 4180-compatible normalized rows; mutually exclusive with `--json` |
| `--no-color` | flag, false | Disable ANSI styling in terminal mode; JSON and CSV never contain ANSI escapes |
| `--max-unique-user-agents INTEGER` | default `1000000` | Positive hard ceiling for exact unique User-Agent values; crossing it stops processing with exit 4 |
| `--version` | flag | Print version and exit 0 without reading input |
| `--help` | flag | Print Click-generated help and exit 0 |

### Input contract

- UTF-8 text with replacement disabled; invalid encoding is an input/read failure.
- One nginx combined-log record per physical line: remote address, remote user, timestamp with offset, request, status, body bytes, referrer, and User-Agent.
- Input is consumed incrementally through a buffered text iterator and is never fully loaded.
- Empty lines and syntactically invalid records are malformed. They increment `malformed_lines` and are excluded from every metric denominator.
- Status is an integer from 100 through 599. Request target is preserved as logged; an unparsable request field makes the line malformed.
- The hour comes from the timestamp encoded in the record. Offset normalization is not performed in MVP; buckets are labeled `00` through `23` in log-local time.

### Output contract

Every mode represents the same snapshot:

- `total_lines`, `total_valid_requests`, and `malformed_lines`.
- `top_ips`: at most 10 entries ordered by request count descending, then IP ascending.
- `top_error_urls`: at most 10 targets whose status is 400–599, ordered by error count descending, then URL ascending.
- `hourly_request_distribution`: all 24 hour buckets in ascending hour order. Each value is a percentage defined exactly as `100 × hourly_request_count / total_valid_requests`; when there are no valid requests, all percentages are `0.0`.
- `unique_user_agents`: exact count of distinct parsed User-Agent strings.
- `unique_user_agent_share_percent`: percentage defined as `100 × unique_user_agents / total_valid_requests`; when there are no valid requests it is `0.0`.

Terminal mode uses Rich headings and tables, applying color only when enabled and appropriate for stdout. JSON uses numeric counts and percentages, arrays for ranked results, and an object keyed by two-digit hour for hourly values. CSV uses the stable columns `metric,rank,key,count,percentage`; scalar and hourly rows leave inapplicable fields empty. Percentages are rounded to two decimal places only at serialization time; aggregation retains integer counts.

### Exit-code contract

| Code | Meaning | Output behavior |
|---:|---|---|
| `0` | Success; malformed lines may have been counted | Complete report on stdout; warnings, if any, on stderr |
| `1` | Input/read failure, including missing file, permissions, I/O, or invalid UTF-8 | No partial machine-readable report; concise diagnostic on stderr |
| `2` | CLI usage error, including conflicting flags or invalid option values | Click usage diagnostic on stderr |
| `3` | No valid requests were parsed | Complete zero-valued report on stdout plus diagnostic on stderr |
| `4` | Unique-cardinality exhaustion: the configured exact User-Agent ceiling was exceeded | No partial report; diagnostic on stderr identifying the ceiling |

Codes are fixed as `0/1/2/3/4`; renderers must not remap exceptions independently.

## Component Responsibilities

| Component | Responsibility | Explicit non-responsibility |
|---|---|---|
| `cli.py` | Validate Click arguments, select input and renderer, translate typed failures to exit codes | Parse log lines or calculate metrics |
| `parser.py` | Convert one physical line to `AccessRecord` or a structured malformed result | Read files, print, or hold aggregate state |
| `models.py` | Define immutable dataclasses and result types | Business logic |
| `aggregator.py` | Update counters and exact User-Agent set; finalize deterministic top 10 and percentages | Terminal/JSON/CSV formatting |
| `renderers/terminal.py` | Rich human output | Machine schema |
| `renderers/json.py` | Stable JSON object | ANSI styling |
| `renderers/csv.py` | Stable normalized CSV rows | Multiple incompatible tables |
| `errors.py` | Typed input and cardinality failures with exit mapping | Swallow failures |

## Data Model

No persistent tables exist. The in-memory dataclasses are:

| Dataclass | Field | Type | Constraint |
|---|---|---|---|
| `AccessRecord` | `remote_addr` | `str` | Non-empty parsed token |
|  | `timestamp` | `datetime` | Timezone-aware value parsed from the log |
|  | `request_target` | `str` | Non-empty target from request field |
|  | `status` | `int` | 100–599 |
|  | `user_agent` | `str` | Exact logged value, including `-` if present |
| `RankedCount` | `key` | `str` | IP or request target |
|  | `count` | `int` | Positive |
| `AnalysisResult` | `total_lines` | `int` | Non-negative |
|  | `total_valid_requests` | `int` | Non-negative and not greater than total lines |
|  | `malformed_lines` | `int` | `total_lines - total_valid_requests` |
|  | `top_ips` | `tuple[RankedCount, ...]` | Length 0–10, deterministic order |
|  | `top_error_urls` | `tuple[RankedCount, ...]` | Length 0–10, deterministic order |
|  | `hourly_counts` | `tuple[int, ...]` | Exactly 24 non-negative values |
|  | `unique_user_agents` | `int` | Non-negative, at most configured ceiling |

Runtime aggregation state consists of two `Counter[str]` instances, one 24-element integer list, one bounded `set[str]`, and scalar line counters. Memory is proportional to distinct IPs, distinct error URLs, and distinct User-Agents rather than total request count. The User-Agent set has an explicit ceiling; performance validation must document memory behavior for the other cardinalities.

## Parsing and Aggregation Invariants

1. Each physical line increments `total_lines` exactly once.
2. A line either produces one valid `AccessRecord` or increments `malformed_lines`, never both.
3. Every valid record increments its IP counter and one hourly bucket.
4. Only statuses 400–599 increment the error-URL counter.
5. User-Agent membership is checked before insertion; exceeding the configured number of unique values raises a typed exhaustion error.
6. `sum(hourly_counts) == total_valid_requests` at finalization.
7. Ranking ties are broken lexicographically so output is repeatable across runs.

## Package and File Layout

```text
pyproject.toml
src/nginx_stream_insights/
  __init__.py
  cli.py
  parser.py
  models.py
  aggregator.py
  errors.py
  renderers/
    __init__.py
    terminal.py
    json.py
    csv.py
tests/
  fixtures/
  test_cli.py
  test_parser.py
  test_aggregator.py
  test_renderers.py
  test_performance.py
```

The console script `nginx-stream-insights` maps to `nginx_stream_insights.cli:main`.

## Performance Architecture

- Process input exactly once using the file iterator's buffering.
- Compile parser machinery once, outside the line loop.
- Keep `datetime` and dataclass construction minimal; benchmark parsing before considering safe specialization.
- Never invoke Rich or serialize per record.
- Use `Counter.most_common` followed by deterministic tie handling at finalization; do not repeatedly sort during ingestion.
- Benchmark an independently generated representative 1 GB log with warmed filesystem assumptions documented, three measured runs, wall time, Python version, CPU, storage type, and peak RSS.
- Acceptance is the slowest of the three measured runs under 30 seconds on the documented laptop.

The target is a release gate, not an architectural claim that Python will meet it without measurement.

## Error Handling and Observability

The CLI catches only known boundary errors and converts them to the fixed exit contract. Unexpected exceptions yield exit 1 with a concise message by default; tracebacks are reserved for development tests, not normal operator output. Diagnostics include the input source, failing line number for encoding/read/parser summaries where safe, malformed count, and configured cardinality ceiling. Raw log lines and full User-Agent values are not echoed in errors to reduce accidental sensitive-data exposure.

## Security and Privacy

- Logs are untrusted input; parsing is non-evaluating and applies a maximum physical line length to prevent pathological allocations.
- The process makes no network calls and stores no logs or analytics after exit.
- Output can contain IPs and URLs; documentation warns users to treat reports as operationally sensitive.
- Formula injection is mitigated in CSV keys beginning with `=`, `+`, `-`, or `@` by safe prefixing and documented escaping.
- File descriptors are managed with context managers; stdin is not closed by the application.
- Dependencies are pinned by compatible ranges and audited before release.

## Authentication, Persistence, API, and Deployment

- **Authentication:** none. There is no remote trust boundary or multi-user service; filesystem permissions and the invoking OS user govern log access.
- **Persistence/database:** none. Results live only for the process lifetime, so there are no tables, migrations, indexes, or database environment variables.
- **HTTP API:** none. The complete interface is the CLI contract above, so there are no endpoints, request bodies, ports, CORS rules, or tokens.
- **Deployment:** a pure-Python wheel/sdist installed with pip. There is no container, `docker-compose`, cloud resource, daemon, or Kubernetes manifest.
- **Configuration:** CLI options only. MVP defines no environment variables or configuration files, preventing hidden behavior changes in pipelines.

These absences are deliberate requirements, not deferred architectural gaps.

## Testing Strategy

| Layer | Evidence |
|---|---|
| Parser unit tests | Valid combined lines, quoting, IPv4/IPv6, status boundaries, offsets, malformed and overlong lines |
| Aggregator property tests | Counter totals, error filtering, 24-hour sum invariant, ties, unique ceiling |
| Renderer golden tests | ANSI-free JSON/CSV, stable fields/order/rounding, terminal output with forced no-color |
| CLI integration tests | File/stdin parity, option conflicts, stderr separation, exit codes `0/1/2/3/4` |
| Performance test | Representative 1 GB fixture under 30 seconds with peak RSS recorded |
| Installation smoke test | Clean Python 3.11 environment, wheel installation, help/version invocation |

## Architecture Decision Record

### ADR-001: Local stateless CLI

- **Status:** Accepted by the supplied product brief.
- **Decision:** Use one local Python process and a one-pass in-memory aggregator; expose terminal, JSON, and CSV output at the command boundary.
- **Consequences:** no service operations or persistence; exact cardinalities require bounded memory policy; repeated analyses rescan input.
- **Rejected alternatives:** GoAccess for a different report experience; Elastic/Logstash for excessive operations and retention; AWStats for batch reporting; shell pipelines for fragile repeated parsing.

### ADR-002: Exact unique User-Agent share with fail-closed ceiling

- **Status:** Accepted.
- **Decision:** Track exact distinct User-Agent strings until a configurable hard ceiling; stop with exit 4 when another unique value would exceed it.
- **Consequences:** reported shares are exact when successful and never silently approximate; adversarial cardinality cannot cause unbounded growth past the ceiling.

### ADR-003: One normalized CSV schema

- **Status:** Accepted.
- **Decision:** Encode all report sections as rows under `metric,rank,key,count,percentage`.
- **Consequences:** pipelines consume one table and distinguish sections by `metric`; some cells are intentionally empty.

`PRD.md` defines the observable requirements, and `IMPLEMENTATION_PLAN.md` maps these decisions to planned files and verification commands.
