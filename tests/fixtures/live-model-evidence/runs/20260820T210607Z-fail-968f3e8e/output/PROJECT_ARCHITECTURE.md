# Project Architecture: nginx-stream-report

## Architecture Summary

The selected architecture is an installable Python 3.11 package with a single Click command and a synchronous, one-pass processing pipeline:

```text
file path(s) or stdin
        |
        v
text line reader -> combined-log parser -> streaming accumulator -> immutable report
                                                              |-> Rich terminal renderer
                                                              |-> JSON renderer
                                                              `-> CSV renderer
```

The literal decision is: **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add ingestion time, disk amplification, schema/migration work, cleanup semantics, and operational state without helping a one-shot report. An HTTP API would add a server lifecycle, network attack surface, authentication questions, concurrency, and deployment burden while the intended users already work in shells and pipelines. The input is local, the result is computed once, and persistence or remote access is not a requirement.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** synchronous line reader, parser, accumulator, and renderer in one Python process.
- **Pros:** simplest install and debugging model; no IPC; deterministic ordering; natural stdin support; one-weekend feasible.
- **Cons:** CPU work is single-core; exact distinct values require memory proportional to their cardinality until the configured guard is reached.
- **Best for:** local one-shot analysis up to the stated 1 GB target.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunk parser (Rejected for MVP)

- **Approach:** split seekable files into byte ranges, aggregate in workers, merge partial counters.
- **Pros:** can use multiple cores for very large regular files.
- **Cons:** complicates line boundaries, stdin, ordering, errors, packaging, and performance diagnosis; process startup and merging may erase gains.
- **Best for:** multi-gigabyte workloads after profiling proves parsing CPU-bound.
- **Estimated complexity:** Medium.

### Variant C: Embedded analytical database (Rejected)

- **Approach:** ingest rows into SQLite or DuckDB and execute aggregation queries.
- **Pros:** flexible ad-hoc queries and reusable data.
- **Cons:** violates stateless/no-database scope, adds ingestion and temporary-storage costs, and does not improve the fixed report contract.
- **Best for:** exploratory analytics with persistence requirements that this project does not have.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the architecture decision is pre-approved, its boundaries align exactly with the product, and it minimizes delivery and operational risk. Variants B and C remain explicit rejected alternatives, not latent MVP scope.

## Technology Stack

| Area | Technology | Contract |
|---|---|---|
| Runtime | CPython 3.11 | Supported interpreter floor and benchmark runtime |
| CLI | Click | Commands/options, help, and usage errors |
| Terminal | Rich | Tables and color only in default terminal mode |
| Models | Standard-library dataclasses | Parsed entries and report values |
| Aggregation | `collections.Counter`, fixed 24-element counts, guarded `set` | Exact metrics in one pass |
| Serialization | Standard `json` and `csv` | No machine output from Rich |
| Tests | pytest, Click `CliRunner` | Unit and end-to-end CLI contracts |
| Packaging | PEP 621 `pyproject.toml` | pip wheel/sdist and console entry point |

Runtime dependencies are limited to Click and Rich. Dataclasses and serialization primitives come from Python 3.11.

## Module Boundaries

```text
src/nginx_stream_report/
  __init__.py       package version surface
  cli.py            Click boundary, stream ownership, error-to-exit mapping
  parser.py         nginx combined-log grammar and ParsedEntry creation
  models.py         ParsedEntry, RankedItem, HourBucket, AnalysisReport
  aggregate.py      one-pass counters and unique-cardinality guard
  renderers.py      terminal, JSON, and CSV projections
  errors.py         typed operational/data/cardinality failures
tests/
  fixtures/         small, reviewed log fixtures only
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_cli.py
  test_performance.py
```

Dependencies point inward: `cli` composes parser, aggregator, and renderers; renderers consume report models and never parse; parser never renders or owns files. No module writes product state.

## Data Model and Metric Semantics

### ParsedEntry

| Field | Type | Meaning |
|---|---|---|
| `client_ip` | `str` | First nginx remote-address field, preserved as parsed |
| `timestamp` | timezone-aware `datetime` | Timestamp from `[dd/Mon/yyyy:HH:mm:ss ±zzzz]` |
| `request_target` | `str` | Target token from the quoted request line; query string is preserved |
| `status` | `int` | Three-digit HTTP response status |
| `user_agent` | `str` | Quoted User-Agent field, including `-` as a literal observed value |

The accepted MVP grammar is nginx's conventional combined format. Quoted fields honor backslash-escaped quote/backslash sequences. The request target is extracted from `METHOD SP TARGET SP HTTP/VERSION`; malformed request lines make the whole input line invalid.

### AnalysisReport

| Field | Type | Semantics |
|---|---|---|
| `total_lines` | non-negative integer | All physical lines read |
| `valid_requests` | non-negative integer | Successfully parsed lines |
| `invalid_lines` | non-negative integer | Lines rejected by the parser |
| `top_ips` | list of `{value,count}` | Highest request counts across valid requests, maximum 10 |
| `top_error_urls` | list of `{value,count}` | Highest counts where `400 <= status <= 599`, maximum 10 |
| `hourly_distribution` | 24 `{hour,count,percentage}` entries | Hour `00` through `23` from the timestamp as encoded in the log |
| `unique_user_agents` | non-negative integer | Count of distinct observed User-Agent strings across valid requests |
| `unique_user_agent_share` | decimal percentage | `100 × unique_user_agents / total_valid_requests`, or `0.0` when no valid request exists |

For every hourly bucket, percentage is defined by the literal formula `100 × hourly_request_count / total_valid_requests`. The timestamp's encoded local hour is used without timezone conversion so a standard single-host log retains its operational day shape. Mixed-offset input is accepted but buckets remain wall-clock hours; this limitation is surfaced in documentation.

Top lists sort by descending count and then ascending UTF-8/Unicode string value for deterministic ties. They contain fewer than 10 entries when fewer distinct values exist. Percentages are serialized as numbers rounded to two decimal places using one shared rounding function; the sum can differ slightly from 100 due to rounding.

## Streaming and Resource Model

Each input is opened as a text stream with UTF-8 decoding and `errors="replace"`, then processed line by line. Stdin is never closed by application code. Multiple paths, if supplied, are processed in command-line order as one logical dataset. `-` means stdin and may appear at most once.

Memory use is:

- `O(number_of_distinct_IPs + number_of_distinct_error_targets + number_of_distinct_User-Agents)` for exact counters/sets;
- constant for hourly buckets and scalar counts;
- independent of total line count when cardinalities are stable.

Because exact User-Agent cardinality can be adversarially high, `--max-unique-user-agents` defaults to `1_000_000`. Before inserting a value that would exceed the limit, processing stops without emitting a partial report and exits 4. The error on stderr names the configured limit, not the rejected log contents. Approximate cardinality is outside MVP scope.

The performance acceptance baseline is a documented laptop, local uncompressed file, warm or cold-cache status recorded, terminal rendering excluded from the timed scan where appropriate, and a representative 1 GB combined-format fixture. The requirement is wall-clock time under 30 seconds.

## CLI Interface

### Command

```text
nginx-stream-report [OPTIONS] [INPUTS]...
```

With no `INPUTS`, the command reads stdin. Each input is a local nginx access-log path; `-` explicitly selects stdin. The MVP reads uncompressed text. A future `--gzip` option is a Should priority, not part of the initial command contract.

### Options

| Option | Behavior |
|---|---|
| `--json` | Emit exactly one JSON object to stdout |
| `--csv` | Emit one RFC 4180-compatible CSV stream to stdout |
| `--strict` | Treat the first malformed line as a data-quality failure (exit 3); emit no report |
| `--max-unique-user-agents INTEGER` | Positive limit, default `1000000`; exhaustion exits 4 |
| `--no-color` | Disable color in terminal mode |
| `--version` | Print version and exit 0 |
| `--help` | Print usage and exit 0 |

`--json` and `--csv` are mutually exclusive and cannot be combined. `--no-color` affects only default terminal mode. Machine formats never contain ANSI escapes. Diagnostics go only to stderr; a successfully produced report goes only to stdout.

### Default terminal output

Rich prints a compact summary followed by tables for top IPs, error targets, hourly distribution, and User-Agent statistics. Color is enabled only when stdout is a TTY and `NO_COLOR` is absent; `--no-color` always wins. An invalid-line warning appears on stderr after a permissive run.

### JSON output

The JSON object uses the `AnalysisReport` field names above. Ranked values use objects with `rank`, `value`, and `count`; hourly entries use `hour`, `count`, and `percentage`. Output is UTF-8, ends with one newline, and uses JSON numbers rather than formatted percent strings.

### CSV output

CSV has the fixed header:

```text
metric,rank,key,count,percentage
```

Rows appear in this order: `summary` rows (`total_lines`, `valid_requests`, `invalid_lines`, `unique_user_agents`, `unique_user_agent_share`), `top_ip`, `top_error_url`, and 24 `hourly_distribution` rows. Unused cells are empty. CSV quoting is delegated to Python's `csv` module and output uses `\r\n` record endings.

### Exit codes

| Code | Meaning | Output behavior |
|---:|---|---|
| `0` | Report completed successfully, including permissive runs with some invalid lines | Report on stdout; optional warning on stderr |
| `1` | Operational failure such as missing/unreadable input or broken output stream | No promised report; concise diagnostic on stderr |
| `2` | Click usage error, invalid option value, or conflicting options | Usage/help diagnostic on stderr |
| `3` | Data-quality failure: strict-mode malformed line or zero valid requests | No report; line-number/count diagnostic on stderr |
| `4` | Unique-cardinality exhaustion | No partial report; configured-limit diagnostic on stderr |

For multiple files, displayed line locations use `path:line`; stdin uses `<stdin>:line`. On any nonzero exit, no complete machine-readable report is promised. Broken pipe is handled as an operational termination without a traceback.

## Error Handling and Trust Boundaries

Log content is untrusted data. It is never evaluated, interpolated into a shell command, or rendered as Rich markup. Terminal cells escape/control or sanitize control characters. Diagnostics do not echo complete malformed lines or User-Agent values. Files are opened read-only and paths are supplied directly by the user.

Permissive mode counts malformed lines and continues. If at least one line is valid, it exits 0 and emits a report plus a stderr warning. If no valid request exists, it exits 3. Strict mode exits 3 at the first malformed line. File/decoder/output failures map to 1, option errors to 2, and the dedicated cardinality guard to 4.

## Persistence, API, Authentication, and Deployment

- **Database:** none. There are no tables, schemas, migrations, caches, or retained results.
- **HTTP API:** none. There are no endpoints, ports, request bodies, server processes, or network calls.
- **Authentication/authorization:** none, because there is no remote boundary or multi-user service. Local filesystem permissions govern log access.
- **Environment:** only standard `NO_COLOR` is observed. There are no secrets or required `.env` variables.
- **Docker/Kubernetes/cloud:** none required or delivered. A container would complicate local file/stdin access without improving pip installation.
- **Deployment:** build wheel and source distribution, validate metadata, install the wheel into a clean Python 3.11 virtual environment, and publish to a Python package index when release authorization exists.

## Testing and Observability

Tests cover parser grammar and escaping, malformed input, deterministic ties, all-error/no-error logs, 24 hourly buckets, percentage rounding, User-Agent cardinality boundaries, multiple files, stdin, each renderer, stdout/stderr separation, and all exit codes. Property-style cases may generate log lines locally, but committed fixtures remain small and reviewable.

The CLI emits no telemetry. User-visible observability consists of elapsed wall time measured externally, report counters, and concise stderr diagnostics. Performance tests are marked so the 1 GB benchmark is opt-in rather than part of every unit-test run.

## Architecture Decision Records

### ADR-001: Single-process synchronous pipeline

- **Status:** Accepted (pre-approved).
- **Decision:** Use Variant A.
- **Reason:** Fixed aggregation, local inputs, weekend scope, and a single-process requirement outweigh hypothetical parallel speedup.
- **Revisit when:** measured 1 GB performance cannot meet target after profiling without changing semantics.

### ADR-002: Exact metrics with explicit cardinality failure

- **Status:** Accepted.
- **Decision:** Keep exact counters and a guarded exact User-Agent set; exit 4 on exhaustion.
- **Reason:** Silent approximation would violate a pipeline contract, while an explicit limit makes memory failure deterministic.
- **Revisit when:** a future requirement explicitly accepts an approximate share with an error bound.

### ADR-003: Separate renderers over a stable report model

- **Status:** Accepted.
- **Decision:** All formats consume the same completed `AnalysisReport`.
- **Reason:** Prevents terminal/JSON/CSV semantic drift and ensures no partial machine document is written before successful analysis.

No adversarial or independent review is recorded here; that review is explicitly delegated to the external benchmark harness in a separate session.
