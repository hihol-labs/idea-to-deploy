# Project Architecture: Nginx Stream Analyzer

## Architecture Drivers

- Local Python 3.11 CLI, installable with pip.
- Stateless, single-pass streaming of a file or stdin.
- Four exact report families: top IPs, error URLs, hourly distribution, and unique User-Agent share.
- Colored human output plus stable JSON and CSV output.
- Performance target: process 1 GB in under 30 seconds on a documented laptop benchmark.
- $0 budget and one-weekend delivery.

The governing boundary is: **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add write amplification, lifecycle management, schema migration, and residual data while none of the requested results needs history between runs. An HTTP API would add a server, authentication and authorization questions, ports, request lifecycle concerns, and deployment work while the users and integrations already operate in terminals and pipelines. Keeping both absent reduces risk and preserves local-data privacy.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended)

- **Approach:** Click constructs an immutable run configuration; one reader yields lines; one parser emits typed records; one aggregator updates in-memory counters; one renderer emits the selected format.
- **Pros:** One pass, low operational complexity, easy pip installation, deterministic ownership of errors.
- **Cons:** Exact cardinality is bounded by available memory; CPU work is confined to one process.
- **Best for:** The approved local 1 GB / 30 s scope.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunk parsing

- **Approach:** Split seekable files into byte ranges, parse in workers, then merge partial aggregates.
- **Pros:** Can use multiple CPU cores for large seekable files.
- **Cons:** Complex boundary handling, merge overhead, different stdin path, higher peak memory, and a larger test surface.
- **Best for:** Multi-gigabyte files after profiling proves parsing is CPU-bound.
- **Estimated complexity:** Medium.

### Variant C: External sort and spill files

- **Approach:** Spill keys or partial counters to disk and merge them with external sorting.
- **Pros:** Supports exact results beyond a fixed in-memory cardinality.
- **Cons:** Disk amplification, cleanup and permissions risks, slower common path, and loss of stateless no-artifact simplicity.
- **Best for:** Exact analysis of adversarial-cardinality data larger than laptop memory.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the product decisions explicitly approve an obvious single-process architecture and a weekend implementation. The cardinality guard makes its main failure mode explicit. Variants B and C remain post-MVP options only if measured evidence invalidates Variant A.

## Component Design

```text
file path ─┐
           ├─> LineReader ─> NginxParser ─> StreamAggregator ─> ReportSnapshot
stdin ─────┘        │              │               │                  │
                    └─ I/O error    └─ invalid line └─ cap error       ├─ RichRenderer
                                                                       ├─ JsonRenderer
                                                                       └─ CsvRenderer
```

| Component | Planned path | Responsibility |
|---|---|---|
| CLI adapter | `src/nginx_stream_analyzer/cli.py` | Options, source selection, format selection, exception-to-exit mapping |
| Configuration | `src/nginx_stream_analyzer/config.py` | Frozen dataclass for validated run settings |
| Reader | `src/nginx_stream_analyzer/reader.py` | Buffered UTF-8 text iteration from file or stdin |
| Parser | `src/nginx_stream_analyzer/parser.py` | Supported combined-format line to `AccessRecord` or invalid result |
| Models | `src/nginx_stream_analyzer/models.py` | `AccessRecord`, ranked entries, hourly entry, report snapshot |
| Aggregator | `src/nginx_stream_analyzer/aggregate.py` | Counters, top-10 selection, percentages, cardinality enforcement |
| Renderers | `src/nginx_stream_analyzer/renderers/` | Terminal, JSON, and CSV serialization with one semantic model |
| Error taxonomy | `src/nginx_stream_analyzer/errors.py` | Typed operational, parse-policy, and cardinality exceptions |

Data flows in one direction. Renderers never parse input, and the parser never formats output. A snapshot is created only after the stream completes successfully, preventing a partial report from looking final.

## Data Model and Metric Semantics

`AccessRecord` contains only fields required by the MVP: source IP (`str`), timestamp (`datetime` with parsed offset), request target (`str`), status (`int`), and User-Agent (`str`). It is ephemeral and is not retained after aggregation.

Aggregation state:

- `total_valid_requests: int`
- `invalid_line_count: int`
- `ip_counts: Counter[str]`
- `error_url_counts: Counter[str]`, updated only when `400 <= status <= 599`
- `hourly_counts: list[int]` of length 24, keyed by the hour present in each log timestamp
- `unique_user_agents: set[str]`, capped by configuration

The exact hourly percentage formula is `100 × hourly_request_count / total_valid_requests`. With zero valid requests, every hourly percentage is `0.0` and the report states that the denominator is zero. The unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`; it is `0.0` when there are no valid requests. Empty User-Agent values count as one literal observed value if the line is otherwise valid.

Top lists are ordered by count descending and then key ascending, making ties deterministic. URLs are the parsed request target exactly as logged; query strings remain part of the MVP key. At most 10 entries are emitted.

### Database Decision

There are no database tables, migrations, indexes, caches, or persistent application records. All dataclasses and counters live for one process invocation only. This is an intentional architectural decision, not an omitted design section.

## Parsing and Failure Policy

The MVP supports the conventional nginx combined log format with a quoted request and User-Agent. Parsing is line-oriented and compiled once per process. Bytes are decoded as UTF-8 with strict error handling so data corruption is visible.

Malformed syntactic lines are counted and skipped. If the stream contains no valid lines but at least one malformed line, the run fails with exit code 3 and emits no normal report. If some lines are valid, the report succeeds and includes `invalid_line_count`; terminal mode also prints a warning to stderr. File/read/decode failures map to exit code 2. Unexpected internal failures map to exit code 1 without a traceback unless debug behavior is added later.

Each exact-cardinality structure has a configurable safe cap, defaulting to a documented value established by benchmark. Crossing any cap terminates before a snapshot is rendered and returns exit code 4. The diagnostic names the exhausted dimension but does not dump log content.

## CLI Interface

### Command

```text
nginx-stream-analyzer [OPTIONS] [INPUT]
```

`INPUT` is an optional path. Omission or `-` reads stdin. The command accepts exactly one source and never follows files indefinitely in the MVP; “streams” means incremental one-pass processing, not tailing.

### Options

| Option | Meaning | Default |
|---|---|---|
| `--json` | Emit one JSON document | Off |
| `--csv` | Emit long-form CSV rows | Off |
| `--no-color` | Disable ANSI styling in terminal mode | Automatic when not a TTY |
| `--max-unique N` | Maximum distinct keys allowed per exact-cardinality dimension | Benchmark-backed package default |
| `--encoding NAME` | Input text encoding | `utf-8` |
| `--version` | Print version and exit | — |
| `--help` | Print Click help and exit | — |

`--json` and `--csv` are mutually exclusive. `--no-color` affects only terminal mode. Invalid option combinations and invalid values are usage errors.

### Inputs

- Regular text file containing one nginx combined-format event per line.
- Standard input from a pipe or redirection.
- Input is processed incrementally; the entire file is never loaded into memory.

### Outputs

- Terminal: four labeled Rich tables plus valid/invalid totals; ANSI color only when enabled and attached to a TTY.
- JSON: UTF-8 object with schema version, totals, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`; no ANSI sequences.
- CSV: UTF-8 header followed by long-form rows with columns `schema_version,metric,rank,key,count,percentage`; no ANSI sequences. Metrics are `top_ip`, `top_error_url`, `hour`, and `unique_user_agents`.
- Normal reports go to stdout. Diagnostics and warnings go to stderr.

### Exit Codes

| Code | Contract |
|---:|---|
| `0` | Successful analysis and complete requested output |
| `1` | Unexpected internal error |
| `2` | Input open/read/decode error |
| `3` | Usage error or input with no valid parseable records |
| `4` | Unique-cardinality exhaustion; no normal report is emitted |

The complete public contract is `0/1/2/3/4`; future features must not silently remap these meanings.

## Output Schemas

JSON uses a top-level `schema_version: 1`. Counts are integers and percentages are JSON numbers rounded only for display, not during aggregation. Each top entry is `{key, count, rank}` using `ip` or `url` rather than an overloaded key in the final schema. Each hourly entry contains `hour` (`00` through `23`), `count`, and `percentage`. `user_agents` contains `unique_count`, `share_percentage`, and `total_valid_requests`.

CSV is intentionally normalized so all four report families can share one stream. Non-applicable cells are empty, never filled with sentinel strings. RFC 4180-compatible quoting is delegated to Python's `csv` module during implementation.

## Security and Privacy

- No authentication mechanism exists because there is no service, account, privilege boundary, or remote endpoint.
- No network calls, telemetry, or uploads are permitted.
- Log fields are untrusted data and are never interpreted as terminal markup; Rich rendering escapes or disables markup for field values.
- Machine output is serialized by standard JSON/CSV libraries, not string concatenation.
- Diagnostics avoid echoing full log lines, which can contain tokens or personal data.
- Input paths are read-only; the program creates no working files.

## Packaging and Deployment

The deployment target is a local Python 3.11 environment. `pyproject.toml` defines an installable package and the `nginx-stream-analyzer` console entry point. Supported delivery is `python -m pip install .` from source and, after release, installation from a public package index.

There is no Docker image, Compose file, daemon, cloud resource, or Kubernetes manifest. Containers would add startup and file-mount friction without improving this local CLI’s contract. Release artifacts, if published later, are a source distribution and universal wheel built with standard Python packaging tools.

Environment variables are not part of the MVP configuration contract. Locale and terminal capability may influence Rich presentation but never metric values or JSON/CSV schemas.

## Performance and Resource Strategy

- Buffered sequential reads; no `read()` of the entire input.
- A compiled parser and minimal ephemeral `AccessRecord` allocation.
- One update per metric per valid record.
- `heapq.nsmallest`/equivalent bounded selection at finalization rather than sorting the raw stream.
- Exact counters guarded by `--max-unique`; failure is explicit rather than approximate.
- Benchmark corpus includes common, malformed, high-cardinality, and long-field cases.

The 30-second target is an acceptance gate measured end-to-end with output redirected to a file or `/dev/null` as appropriate. Profiling precedes optimization. Multiprocessing is excluded unless the single-process design fails the measured target.

## Architecture Decision Records

### ADR-001: Select a single-process streaming pipeline

- **Status:** Accepted by the product brief.
- **Decision:** Use Variant A and preserve module boundaries inside one process.
- **Consequences:** Minimal operations and deterministic streaming; exact cardinality requires explicit limits.

### ADR-002: Keep the product local and stateless

- **Status:** Accepted by the product brief.
- **Decision:** No database, API, authentication, server, cloud, or Kubernetes.
- **Consequences:** No cross-run history or remote querying; users can redirect JSON/CSV into their existing tools.

### ADR-003: Fail closed on exact-cardinality exhaustion

- **Status:** Accepted.
- **Decision:** Abort with exit code 4 and no complete report when a configured distinct-key cap is exceeded.
- **Consequences:** Results remain exact and honest; hostile inputs may require a future approximate or spill-to-disk mode.

The separate adversarial review is intentionally outside this session per the benchmark protocol; this document records no reviewer verdict.

