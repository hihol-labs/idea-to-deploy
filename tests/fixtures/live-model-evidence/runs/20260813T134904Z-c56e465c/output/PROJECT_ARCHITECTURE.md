# Project Architecture: Nginx Stream Insights

## 1. Context and Constraints

The product is an installable Python 3.11 command-line application for local nginx combined access logs. It performs one streaming pass and holds aggregate counters only. The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add schema, I/O, cleanup, migrations, and persistent sensitive log data without helping a one-shot top-10 report. An HTTP API would add a server lifecycle, network exposure, authentication questions, and deployment burden when users already have the local file or stdin stream. Keeping input and results inside one process directly supports the $0 budget, privacy, pip installation, and one-weekend delivery.

The target is to process 1 GB in under 30 seconds on a documented laptop. This is an acceptance target to benchmark, not a guaranteed consequence of Python.

## 2. Architecture Decision

### Selected: Single-process streaming pipeline

```text
file path / stdin
        |
        v
 buffered text reader -> combined-log parser -> aggregate state -> finalized report
                                |                       |
                                v                       v
                         malformed count       text | JSON | CSV renderer
                                |                       |
                                +-------- stderr       stdout
```

One process reads each line once, parses only required fields, updates counters, finalizes derived percentages after EOF, and invokes exactly one renderer. Rich is isolated to terminal rendering so machine formats remain plain and deterministic.

### Alternatives considered and rejected

| Alternative | Benefit | Why rejected for this product |
|---|---|---|
| SQLite-backed batch analyzer | Persistent queries and bounded application memory | Adds disk amplification, schema/migrations, and persistence contrary to the approved stateless design |
| Multiprocess parser | Potential CPU parallelism | Chunk boundaries, ordering, merge cost, stdin behavior, and IPC complexity are unjustified before a measured bottleneck |
| Hosted/API service | Central access and shared dashboards | Explicitly out of scope; introduces auth, server, network, cloud, and privacy concerns |
| External `sort` pipelines | Can exploit optimized Unix tools | Requires multiple passes/processes and weakens cross-platform output/error contracts |

This is an obvious architecture choice under the pre-approved constraints, so no unresolved variant remains for selection. No adversarial review is recorded in this document; that review belongs to the separate external session.

## 3. Component Boundaries

| Module | Responsibility | Key interfaces |
|---|---|---|
| `src/nginx_stream_insights/cli.py` | Click command, option validation, stream ownership, exception-to-exit mapping | `main()` |
| `src/nginx_stream_insights/parser.py` | Compile and apply combined-log grammar; return typed records or parse failures | `parse_line(str) -> AccessRecord` |
| `src/nginx_stream_insights/models.py` | Immutable parsed records and finalized report structures | `AccessRecord`, `Report`, `RankedItem`, `HourlyBucket` |
| `src/nginx_stream_insights/aggregate.py` | Increment counters, enforce unique-key cap, produce deterministic rankings and metrics | `Aggregator.consume(record)`, `Aggregator.finalize()` |
| `src/nginx_stream_insights/render_text.py` | Rich terminal tables, metadata, color policy | `render_text(report, console)` |
| `src/nginx_stream_insights/render_json.py` | Stable JSON object to stdout | `render_json(report, stream)` |
| `src/nginx_stream_insights/render_csv.py` | Stable long-form CSV rows to stdout | `render_csv(report, stream)` |
| `src/nginx_stream_insights/errors.py` | Domain exception types and exit-code mapping | `InputError`, `ParseThresholdError`, `CardinalityError` |

Dependencies point inward: renderers and CLI depend on models; parsing and aggregation never depend on Click or Rich. No module retains raw lines after processing.

## 4. Streaming Data Model

There are no database tables. The complete in-memory state is:

| Field | Type | Meaning and bound |
|---|---|---|
| `total_lines` | `int` | All input lines seen |
| `total_valid_requests` | `int` | Successfully parsed records |
| `malformed_lines` | `int` | Rejected records |
| `ip_counts` | `dict[str, int]` | Requests per IP; unique keys count toward the configured global cap |
| `error_url_counts` | `dict[str, int]` | 4xx/5xx responses per normalized request target; unique keys count toward cap |
| `hour_counts` | `list[int]` of length 24 | Valid requests indexed by log-local hour `00`–`23` |
| `user_agent_counts` | `dict[str, int]` | Requests per exact User-Agent string; unique keys count toward cap |

`AccessRecord` contains only `client_ip: str`, `timestamp: datetime`, `request_target: str`, `status: int`, and `user_agent: str`. The parser accepts nginx combined-log lines, preserves the timestamp’s numeric UTC offset, takes the URL/request-target token from the quoted request field, and does not percent-decode it. A missing request or User-Agent marker (`-`) is retained as the literal marker so totals remain auditable.

The global cardinality usage is the sum of distinct keys newly inserted across the three dictionaries. Before inserting a new key, the aggregator checks `--max-unique`; exceeding it aborts with exit code `4`. This makes failure deterministic, though actual bytes per key remain input-dependent and must be benchmarked.

### Metric definitions

- Top IPs: descending valid-request count, then IP string ascending; first 10 by default.
- Error URLs: requests whose status is 400–599, descending count, then URL ascending; first 10 by default.
- Hourly request distribution: all 24 hours, each percentage calculated as `100 × hourly_request_count / total_valid_requests`. When there are zero valid requests, all percentages are `0.0` and the run follows the parse/empty-input rules below.
- Unique User-Agent share: `100 × distinct_user_agent_count / total_valid_requests`; `0.0` when there are zero valid requests. “Unique” means exact, case-sensitive User-Agent strings after parsing, including `-`.

## CLI Interface

### Commands

The installed command is `nginx-stream-insights` and has one analysis command:

```text
nginx-stream-insights [OPTIONS] [INPUT]
```

`INPUT` is an optional path. When omitted or exactly `-`, bytes are read from stdin. Input must be UTF-8; invalid byte sequences are input errors rather than silently replaced data.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | off | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | off | Emit RFC 4180-compatible long-form CSV; mutually exclusive with `--json` |
| `--no-color` | off | Disable terminal colors; color also disables automatically for non-TTY stdout |
| `--strict` | off | Stop on the first malformed line with exit code `3`; otherwise skip and count malformed lines |
| `--top INTEGER` | `10` | Number of IP and error-URL ranking rows; integer >= 1 |
| `--max-unique INTEGER` | `1000000` | Maximum combined distinct IP, error-URL, and User-Agent keys; integer >= 1 |
| `--version` | n/a | Print version and exit `0` |
| `--help` | n/a | Print help and exit `0` |

### Outputs

Normal report data is written only to stdout. Diagnostics are written only to stderr.

- Text: Rich title/summary followed by top-IP table, top error-URL table, 24 hourly rows with percentages, and User-Agent uniqueness summary. Color follows TTY policy.
- JSON: object with `schema_version`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`. Counts are integers and shares/percentages are JSON numbers.
- CSV: header `schema_version,metric,key,count,percentage`, followed by deterministic sections `summary`, `top_ip`, `error_url`, `hour`, and `user_agent_share`. Non-applicable cells are empty.

Machine-readable output is atomic with respect to domain failures: build it only after successful finalization, so exit `3` or `4` cannot leave a partial JSON/CSV document. Rankings and section order are deterministic.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Analysis completed; malformed lines may have been skipped in non-strict mode and are disclosed |
| `1` | Unexpected internal error |
| `2` | CLI usage or input I/O/encoding error, including missing/unreadable file and invalid option combination |
| `3` | Log-data failure: strict malformed line, or no valid requests after processing non-empty input |
| `4` | Unique-cardinality exhaustion: inserting another distinct tracked key would exceed `--max-unique` |

An empty input is a successful empty report (`0`); a non-empty input with no valid records is a data failure (`3`). Click usage errors are normalized to `2`.

## 6. Parser and Error Policy

The grammar targets nginx’s combined format:

```text
remote_addr - remote_user [time_local] "request" status body_bytes_sent "http_referer" "http_user_agent"
```

The parser uses one precompiled regular expression with bounded, explicit quoted-field handling. It validates timestamp, status as an integer from 100–599, and the request line shape. It does not resolve DNS, inspect bodies, or infer missing fields. Malformed lines increment `malformed_lines`; `--strict` converts the first parse failure into exit `3` with the 1-based line number and a concise reason on stderr. Diagnostics never echo an entire raw line, limiting accidental log-data exposure.

## 7. Performance and Resource Design

- Open path input with a large buffered reader; consume stdin without seeking.
- Parse and aggregate in one pass, O(number of lines) time.
- Keep O(Uip + Uerror_url + Uua + 24) state, capped by `--max-unique`.
- Use `Counter.most_common` or `heapq.nlargest` only during finalization; benchmark both on realistic cardinality before choosing.
- Avoid `datetime` construction if an indexed timestamp parse is measurably faster while preserving validation and timezone correctness.
- Never create Rich objects in the line loop.
- Benchmark from a generated-once, representative 1 GB fixture outside timed setup; record Python version, OS, CPU, storage, command, elapsed time, and peak RSS.

The performance gate is median wall time under 30 seconds across three warm-cache runs on the named reference laptop, with each result also recorded. Correctness and the cardinality guard cannot be disabled for the benchmark.

## 8. Security and Privacy

No authentication is needed because there is no service, account, privilege boundary, or remote interface. The process reads a user-selected local stream and writes a report. It makes no network calls and sends no telemetry. Paths are handled through Python APIs, never shell interpolation. Error text is bounded and avoids raw log lines. Spreadsheet formula injection is mitigated in CSV keys beginning with `=`, `+`, `-`, or `@` by prefixing a single quote; the JSON and text values remain faithful.

Logs may contain personal data. The tool keeps only in-memory counters for the process lifetime, does not persist input or aggregates, and documents that stdout redirection creates a user-managed file.

## 9. Packaging, Configuration, and Deployment

The package uses a `src/` layout and PEP 621 metadata in `pyproject.toml`, with a console-script entry point. Runtime dependencies are pinned to compatible major ranges for Click and Rich; development dependencies are optional. Installation is local through pip from a wheel, source checkout, or later public package.

Deployment means installing the wheel into a Python 3.11 environment. There is no Docker image, Compose file, daemon, database, migration, `.env`, HTTP port, cloud resource, or Kubernetes manifest. There are no environment variables in the MVP; command-line options are the complete configuration surface. This is intentional, not missing infrastructure.

## 10. Test Architecture

| Layer | Coverage |
|---|---|
| Parser unit tests | Valid combined lines, timezone offsets, escaped quotes, `-` fields, malformed status/timestamp/request, invalid UTF-8 |
| Aggregator unit tests | Counts, status boundary 399/400/599/600 rejection, stable ties, formula accuracy, empty totals, cardinality boundary |
| Renderer golden tests | Text without color, canonical JSON schema, RFC-compatible CSV and injection mitigation |
| CLI integration tests | File/stdin parity, option conflicts, TTY policy, stderr separation, complete `0/1/2/3/4` mapping |
| Property tests or generated cases | Count conservation and hourly percentages summing to approximately 100% for non-empty valid input |
| Performance test | Representative 1 GB fixture, three timed runs, peak RSS, no correctness shortcuts |

## 11. Repository Layout

```text
pyproject.toml
src/nginx_stream_insights/
  __init__.py
  cli.py
  parser.py
  models.py
  aggregate.py
  errors.py
  render_text.py
  render_json.py
  render_csv.py
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_cli.py
  test_performance.py
scripts/
  generate_benchmark_log.py
```

## 12. Architecture Acceptance

The architecture is accepted for implementation when [PRD.md](PRD.md) remains the behavioral source, every step in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) preserves streaming operation, and the final clean-environment test proves pip installation, output schemas, exit codes, and the performance target. Any future proposal for persistence or a network service is a new product scope, not an internal refactor.
