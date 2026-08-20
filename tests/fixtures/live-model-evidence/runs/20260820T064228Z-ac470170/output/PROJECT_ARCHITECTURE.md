# Project Architecture: Nginx Stream Insights

## 1. Context and Architectural Drivers

The product is a Python 3.11 command-line utility for local analysis of nginx
combined access logs. The dominant drivers are one-pass streaming, exact and
stable reporting, safe pipeline behavior, pip installation, a $0 budget, and a
1 GB / 30 second performance target on a documented laptop.

The governing decision is **"no database — stateless streaming processing; no HTTP API — CLI-only tool"**. A database is incorrect because the four requested
summaries can be accumulated in one pass and do not require history, joins, or
cross-run queries; adding storage would increase I/O, lifecycle, privacy, and
operational cost. An HTTP API is incorrect because the users and inputs are
local shell workflows, and a server would introduce ports, authentication,
deployment, concurrency, and data-exposure concerns without improving the
approved use case.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** One Python process reads one line at a time, parses supported
  combined-log records, updates in-memory aggregates, freezes a report model,
  and invokes exactly one renderer.
- **Pros:** Minimal moving parts, no inter-process serialization, deterministic
  semantics, simple installation, straightforward profiling.
- **Cons:** One CPU core for parsing; exact User-Agent cardinality requires a
  guarded set.
- **Best for:** The approved one-weekend local CLI and 1 GB target.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunked parser

- **Approach:** Workers parse byte ranges and merge partial aggregates.
- **Pros:** Can use multiple CPU cores.
- **Cons:** Complex record-boundary handling, expensive set/counter merges,
  higher peak memory, harder deterministic errors and stdin behavior.
- **Best for:** Measured CPU-bound workloads substantially beyond the MVP.
- **Estimated complexity:** Medium.

### Variant C: External analytics pipeline

- **Approach:** Ship logs to GoAccess or an Elastic-style ingestion and storage
  stack.
- **Pros:** Existing dashboards and long-term exploration.
- **Cons:** Services, persistence, configuration, cost, and data movement; does
  not satisfy the local stateless product.
- **Best for:** Ongoing fleet analytics rather than incident-time summaries.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the architecture is obvious for the fixed scope,
the user has pre-approved it, and it minimizes both runtime overhead and
delivery risk. Variants B and C are recorded only as rejected alternatives;
they are not open decisions.

## 3. Component Model

| Planned module | Responsibility | Key inputs/outputs |
|---|---|---|
| `src/nginx_stream_insights/cli.py` | Click command, option validation, exception-to-exit mapping | CLI arguments → application call / exit status |
| `src/nginx_stream_insights/io.py` | Open file/stdin as a text stream; gzip extension point | Path or `-` → iterator of lines |
| `src/nginx_stream_insights/parser.py` | Parse the supported combined-log grammar and normalize timestamp/status/URL/UA | Text line → `AccessRecord` or parse failure |
| `src/nginx_stream_insights/models.py` | Frozen dataclasses for records, counters, report rows, diagnostics | Typed domain values |
| `src/nginx_stream_insights/aggregator.py` | Single-pass counters, 24 hourly buckets, exact UA set and limit | Records → mutable aggregate state |
| `src/nginx_stream_insights/report.py` | Deterministic sorting, percentage calculation, immutable report | Aggregate state → `AnalysisReport` |
| `src/nginx_stream_insights/renderers/rich_text.py` | Colored terminal tables and diagnostics | Report → terminal text |
| `src/nginx_stream_insights/renderers/json_output.py` | Versioned JSON document | Report → UTF-8 JSON |
| `src/nginx_stream_insights/renderers/csv_output.py` | Normalized multi-metric CSV rows | Report → RFC 4180-compatible CSV |
| `src/nginx_stream_insights/errors.py` | Typed operational/data/cardinality failures | Exception → public failure category |

Dependencies point inward: CLI and renderers depend on report/domain models;
the parser and aggregator never import Click or Rich. No plugin system,
background worker, database driver, network client, or framework container is
needed.

## 4. Data Flow and Streaming Invariants

```text
file or stdin
    │ lines (one at a time)
    ▼
combined-log parser ── malformed ──► diagnostic counters/sample
    │ AccessRecord
    ▼
single aggregate state
    ├── Counter[ip]
    ├── Counter[url] only where 400 <= status <= 599
    ├── hourly_count[24]
    └── exact set[user_agent] with configured ceiling
    │ end of input
    ▼
immutable AnalysisReport ──► Rich text | JSON | CSV
```

The input is never loaded wholesale. At end-of-stream, all rankings use
`count DESC, key ASC` for deterministic ties. Top-10 truncation happens only
when freezing the report so counts remain exact. Memory is proportional to
distinct IPs + distinct error URLs + distinct User-Agents, not file size. The
User-Agent set has a hard ceiling; crossing it aborts with exit code 4 rather
than emitting a partial or approximate share.

Hourly request distribution is a percentage for each hour `00` through `23`,
using the timestamp and offset recorded in each log entry and the literal
formula `100 × hourly_request_count / total_valid_requests`. Empty hours are
reported as `0.0`; percentages are serialized with consistent decimal
rounding. The unique User-Agent share is likewise a percentage:
`100 × unique_user_agent_count / total_valid_requests`.

## 5. Supported Log Contract

The MVP supports the standard nginx combined format:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

The parser extracts client IP text, timestamp plus numeric UTC offset, request
target, integer status, and User-Agent. The URL metric uses the request target
without query or fragment so cache-busting parameters do not split one route;
an unparsable request field invalidates that line. IPv4 and IPv6 strings are
accepted. Statuses 400–599 contribute to the error-URL ranking. Malformed
lines are skipped, counted, and summarized on stderr for text mode; structured
formats include diagnostics in their contract without mixing stderr into
stdout. If no line is valid, the command emits no report and exits 3.

## CLI Interface

### Commands and synopsis

```text
nginx-stream-insights [OPTIONS] INPUT...
nginx-stream-insights [OPTIONS] -
python -m nginx_stream_insights [OPTIONS] INPUT...
```

One or more input files are processed as one logical stream in argument order.
`-` means UTF-8 stdin and may appear only once. With no input argument, stdin
is selected when it is not an interactive terminal; otherwise Click reports a
usage error.

### Options

| Option | Contract |
|---|---|
| `--json` | Emit one JSON document to stdout; mutually exclusive with `--csv`; disables color |
| `--csv` | Emit normalized CSV with a header to stdout; mutually exclusive with `--json`; disables color |
| `--color [auto|always|never]` | Text mode only; default `auto`, which colors only an eligible TTY |
| `--max-unique-user-agents INTEGER` | Positive exact-cardinality ceiling; default 1,000,000 |
| `--encoding TEXT` | Input encoding, default `utf-8`; decoding errors are operational input failures |
| `--version` | Print version and exit 0 |
| `--help` | Print usage and exit 0 |

### Inputs

- Regular local files and `-` for stdin; all are read incrementally.
- Standard nginx combined-log lines encoded as configured.
- A later Should-priority extension may infer gzip from `.gz`; it is not part
  of the first release contract.

### Outputs

Text output contains four labeled sections in this order: top client IPs, top
error URLs, hourly distribution, and User-Agent diversity, followed by valid
and malformed record totals. Data goes to stdout; warnings and actionable
errors go to stderr. Broken pipe is treated as normal downstream termination.

JSON uses a top-level `schema_version`, `summary`, `top_ips`,
`top_error_urls`, `hourly_distribution`, and `user_agents`. Ranked entries
contain `rank`, a key, and `count`; hourly entries contain `hour`, `count`, and
`percentage`; `user_agents` contains `unique_count` and `percentage`.

CSV columns are `schema_version,metric,rank,key,count,percentage`. Each metric
is a row group; absent values are empty fields, and `key` holds IP, URL, hour,
or the literal `unique_user_agents`. This normalized contract avoids multiple
incompatible tables in one stream.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Successful report, `--help`, or `--version`; malformed lines may have been skipped if at least one record was valid |
| `1` | Input/output or unexpected runtime failure, including missing/unreadable files and decode/write errors |
| `2` | Click usage error: invalid option, conflicting format flags, invalid limit, or invalid stdin selection |
| `3` | Data failure: input ended with zero valid access-log records |
| `4` | Unique-cardinality exhaustion: distinct User-Agents exceeded the configured exact ceiling; no report is emitted |

The `0/1/2/3/4` mapping is public and must remain identical in every renderer,
the console entry point, `python -m` execution, documentation, and tests.

## 7. Data Model

Planned dataclasses:

| Type | Fields | Invariants |
|---|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `path: str`, `status: int`, `user_agent: str` | timezone-aware timestamp; status 100–599; normalized path |
| `RankedCount` | `rank: int`, `key: str`, `count: int` | rank 1–10; positive count |
| `HourlyBucket` | `hour: int`, `count: int`, `percentage: float` | hour 0–23; nonnegative values |
| `UserAgentStats` | `unique_count: int`, `percentage: float` | nonnegative; exact only |
| `Diagnostics` | `total_lines: int`, `valid_lines: int`, `malformed_lines: int`, `malformed_samples: tuple[str, ...]` | totals reconcile; samples bounded and sanitized |
| `AnalysisReport` | schema version plus all report sections and diagnostics | immutable, deterministic order, at least one valid record |

There are no database tables, schemas, migrations, indexes, retention jobs, or
persistent caches. That absence is an architectural requirement, not an
omission.

## 8. Error, Resource, and Security Boundaries

- Open paths read-only and never follow an application-managed write path.
- Do not interpret log contents as terminal markup; Rich receives escaped text.
- CSV uses the standard library writer, and cells beginning with spreadsheet
  formula sigils are prefixed safely when formula-injection protection is
  enabled by the renderer contract.
- JSON is produced by the standard library encoder with no manual escaping.
- Malformed samples are length-bounded and control characters are escaped.
- Counters use Python integers; lines have a maximum accepted length to avoid
  pathological allocation, with overlong lines counted as malformed.
- Exact User-Agent cardinality is bounded by the CLI option and failure code 4.
- No secrets, environment credentials, network calls, telemetry, subprocesses,
  dynamic imports, or executable configuration are part of the product.

## 9. Packaging and Deployment

The deployment artifact is a pure-Python wheel built from `pyproject.toml`
with a `src/` layout. The console script is `nginx-stream-insights`. Supported
runtime is CPython 3.11; installation is through pip into a virtual environment
or `pipx`. There is no Docker image, Compose file, server, health endpoint,
cloud resource, or Kubernetes manifest. Release verification builds the wheel,
installs it into a clean Python 3.11 environment, and runs golden CLI fixtures.

No runtime environment variables are required. Standard process conventions
such as `NO_COLOR` may inform Rich's automatic color behavior, but explicit
CLI options win and no `.env` file is read.

## 10. Performance Strategy

The reference benchmark must identify CPU, storage, OS, Python patch version,
input size, valid/malformed mix, distinct cardinalities, wall time, and peak
resident memory. The implementation will use buffered sequential reads, a
compiled parser pattern, direct integer/status checks, fixed 24-hour storage,
and a single final sort per ranking. Benchmark acceptance is median wall time
below 30 seconds across three warm-cache runs for a 1 GB fixture, while also
recording a cold-cache run separately. Optimization decisions require profiler
evidence; multiprocessing is not introduced speculatively.

## 11. Architecture Decision Record

### ADR-001: Local single-process streaming CLI

- **Status:** Accepted by the supplied product constraints.
- **Decision:** Use Variant A with the fixed Python 3.11, Click, Rich, and
  dataclasses stack.
- **Consequences:** Simple installation and deterministic single-pass behavior;
  performance must be demonstrated, and exact cardinality needs a guard.
- **Rejected:** Multiprocessing before profiling; any persistent or networked
  analytics service.

### ADR-002: Exact User-Agent diversity with fail-closed ceiling

- **Status:** Accepted.
- **Decision:** Track exact values until the configured limit. On the next new
  value, stop and exit 4 without emitting a report.
- **Consequences:** Results are never mislabeled estimates; extreme-cardinality
  inputs must raise the ceiling with sufficient memory or use a future explicit
  approximate mode.

No adversarial or independent review was run in this blueprint session; the
external harness owns that separate review and its artifact.
