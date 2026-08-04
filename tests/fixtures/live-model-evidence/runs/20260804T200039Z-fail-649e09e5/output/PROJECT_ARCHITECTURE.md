# Project Architecture: Nginx Stream Analytics CLI

## 1. Context and Decision

The product is a pip-installable Python 3.11 command that reads nginx access-log lines from one or more local files or stdin, aggregates four exact reports in one process, and writes one selected representation to stdout. Diagnostics go to stderr. The literal governing decision is: **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add setup, write amplification, retention/security duties, and a second data model when the requested result can be derived in one pass and discarded. An HTTP API would introduce a server lifecycle, port/security surface, authentication questions, and deployment work while the target users already operate in shells and pipelines. Neither creates value for a local one-off 1 GB analysis.

## 2. Architecture Variants

### Variant A: Single-process streaming CLI (selected and recommended)

- **Approach:** Click owns command validation; a line iterator feeds a compiled parser; one aggregation state updates per valid record; a renderer emits text, JSON, or CSV.
- **Pros:** smallest operational surface, deterministic behavior, direct stdin support, no IPC/serialization overhead, one-weekend fit.
- **Cons:** exact unique maps can consume memory; a single Python process may become CPU-bound.
- **Best for:** local one-off logs up to the stated 1 GB target.
- **Estimated complexity:** Low.

### Variant B: Unix pipeline of specialized commands

- **Approach:** separate parser and metric commands exchange normalized records over pipes.
- **Pros:** composable and independently replaceable stages.
- **Cons:** repeated serialization, harder atomic failure semantics, more commands to learn, and either multiple passes or fan-out buffering.
- **Best for:** users building custom metric chains.
- **Estimated complexity:** Medium.

### Variant C: Multiprocessing map/reduce CLI

- **Approach:** split seekable files into byte ranges, aggregate in workers, merge states in a parent.
- **Pros:** can use multiple cores on large regular files.
- **Cons:** complex newline/range handling, poor stdin fit, high merge memory, platform variance, and likely overhead for 1 GB.
- **Best for:** proven CPU bottlenecks on much larger files.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the product decisions pre-approve the obvious single-process architecture, the deadline is one weekend, and the primary benefit is zero-setup local use. Variant C is a future profiling-driven option, not speculative MVP complexity.

## 3. System Boundaries and Flow

```text
local file(s) / stdin
        |
        v
 byte-safe text iterator --> combined-log parser --> AggregationState
                              | malformed              | counts/maps/set
                              v                        v
                         skipped counter       immutable Report
                                                     |
                                  +------------------+------------------+
                                  v                  v                  v
                              Rich text             JSON               CSV
                                  +------------------+------------------+
                                                     |
                                                   stdout

diagnostics, malformed summary, fatal reason ------------------------> stderr
```

There is no network boundary, daemon, background worker, cache, database, authentication layer, or retained application state. State lifetime is one invocation.

## CLI Interface

### Command

```text
nginx-stream-report [OPTIONS] [PATHS]...
```

With no `PATHS`, input is stdin. A path of `-` also denotes stdin and may appear at most once. Multiple files are processed in argument order as one logical stream. MVP input is UTF-8 nginx combined access-log text; invalid bytes are replaced for parsing and counted as malformed if the record cannot be parsed. Gzip input is a P1 extension.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit exactly one JSON document; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit UTF-8 RFC 4180-compatible normalized rows; mutually exclusive with `--json` |
| `--top` | integer, `10` | Number of ranked IP and error-URL rows; must be 1–100; default fulfills top-10 requirement |
| `--max-cardinality` | integer, `1000000` | Maximum combined newly admitted distinct IP, URL, and User-Agent keys; positive integer |
| `--color` | `auto|always|never`, `auto` | Applies only to terminal text; JSON and CSV never contain ANSI escapes |
| `--version` | flag | Print version and exit 0 |
| `--help` | flag | Print Click help and exit 0 |

### Metric definitions

- Top IPs count every valid request by parsed client IP. Sort by count descending, then IP string ascending; return at most `--top` rows.
- Top error URLs include only status codes 400–599. The URL key is the request target exactly as logged, without decoding or query stripping. Sort by count descending, then URL ascending.
- Hourly request distribution has 24 UTC-offset-preserving log-time buckets `00` through `23`, including zero buckets. Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`. Percentages are numeric and derived from unrounded counts; text rounds to two decimals.
- Unique User-Agent share is `100 × distinct_nonempty_user_agent_count / total_valid_requests`. The parser preserves the logged User-Agent string; `"-"` is treated as empty. When there are no valid requests, processing fails with exit 3 and no report is emitted.
- Malformed lines do not enter any numerator or denominator. Their count is included in successful output metadata and summarized on stderr only when nonzero.

### Outputs

Default text is a Rich report with four labeled sections and a summary. On non-TTY stdout Rich uses no color under `--color auto`.

JSON uses this stable top-level shape:

```json
{
  "schema_version": 1,
  "summary": {"total_lines": 0, "valid_requests": 0, "malformed_lines": 0},
  "top_ips": [{"ip": "192.0.2.1", "requests": 10}],
  "top_error_urls": [{"url": "/missing", "errors": 3}],
  "hourly_distribution": [{"hour": 0, "requests": 0, "percentage": 0.0}],
  "user_agents": {"distinct_nonempty": 0, "share_percentage": 0.0}
}
```

CSV writes one header followed by normalized rows:

```text
section,key,count,percentage
summary,total_lines,100,
top_ip,192.0.2.1,10,
top_error_url,/missing,3,
hour,00,8,8.0
user_agent_share,distinct_nonempty,25,25.0
```

Machine-readable report data goes only to stdout. Usage errors and processing diagnostics go only to stderr. A downstream broken pipe is handled quietly and must not print a traceback.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Success, including `--help` and `--version` |
| `1` | Unexpected internal processing/rendering failure |
| `2` | Invalid command usage or option combination (Click contract) |
| `3` | Input/data failure: missing/unreadable input, unsupported encoding/format, read error, or zero valid requests |
| `4` | Unique-cardinality exhaustion: admitting another distinct tracked IP, URL, or User-Agent would exceed `--max-cardinality`; no partial report is emitted |

## 5. Components and Repository Layout

```text
pyproject.toml
src/nginx_stream_report/
  __init__.py          # package version only
  cli.py               # Click boundary and exit mapping
  errors.py            # typed domain failures and exit constants
  input.py             # stdin/file line iterators
  parser.py            # combined-log parser -> AccessRecord
  models.py            # AccessRecord, Report, row dataclasses
  aggregate.py         # AggregationState and cardinality guard
  render/
    __init__.py
    text.py             # Rich rendering
    json.py             # schema v1 serialization
    csv.py              # normalized CSV serialization
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

Dependencies point inward: `cli` composes input, parser, aggregation, and renderers; renderers depend only on immutable models; domain modules never import Click or Rich.

## 6. Data Model and Algorithms

### Dataclasses

| Type | Fields | Invariants |
|---|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `target: str`, `status: int`, `user_agent: str | None` | Status 100–599; timestamp timezone-aware; target nonempty |
| `RankedIP` | `ip: str`, `requests: int` | Requests positive |
| `RankedErrorURL` | `url: str`, `errors: int` | Errors positive |
| `HourlyBucket` | `hour: int`, `requests: int`, `percentage: float` | Exactly 24 report rows; hour 0–23 |
| `ReportSummary` | `total_lines: int`, `valid_requests: int`, `malformed_lines: int` | `total_lines = valid_requests + malformed_lines` |
| `Report` | summary, ranked tuples, hourly tuple, UA distinct count/share | Immutable renderer input |

The parser compiles one regex once and validates request/status/timestamp fields. `AggregationState` contains `Counter[str]` for IPs, a `Counter[str]` for error URLs, a 24-element integer list, and a `set[str]` for nonempty User-Agents. Ranking uses `heapq.nsmallest` or an equivalent bounded selection with the documented composite key, avoiding a full sort when cardinality is high.

Time is O(lines + distinct_keys log top); memory is O(distinct IPs + distinct error URLs + distinct User-Agents), explicitly bounded by `--max-cardinality`. Processing is one-pass and never stores raw lines or records after aggregation.

## 7. Database, API, Authentication, and Deployment

### Database

Not applicable by decision: there are zero tables, fields, migrations, indexes, connections, or retained records. Invocation-scoped Python containers are not a database and are destroyed on exit.

### HTTP API

Not applicable by decision: there are zero endpoints, methods, request bodies, ports, or network listeners. The complete public interface is the `## CLI Interface` contract.

### Authentication and authorization

Not applicable: the process reads only paths the invoking OS user can access and writes to that user's stdout/stderr. Operating-system file permissions are the trust boundary. The tool must not elevate privileges, read implicit credential files, or send telemetry.

### Deployment and configuration

Deployment is a Python wheel/source distribution installed with pip into a virtual environment or `pipx`; the console script is `nginx-stream-report`. There is no Docker image, Compose file, Kubernetes manifest, cloud resource, or service unit. This is intentional: Python 3.11 plus pip is the runtime contract.

There are no required environment variables. Standard `NO_COLOR` may disable automatic terminal color; CLI `--color` is authoritative when explicitly supplied. Locale must not alter JSON numbers, CSV delimiter, ranking, or timestamps.

## 8. Reliability, Security, and Performance

- Open inputs lazily and close each deterministically; do not follow directory traversal beyond paths explicitly passed.
- Treat log content as untrusted data. Never evaluate it, interpolate it into a shell, or allow Rich markup from values.
- CSV uses the standard library writer; JSON uses the standard encoder; terminal values have markup escaped.
- Counters use Python integers. Validate status and timestamp before state mutation.
- Cardinality is checked before adding any new distinct key, and exit 4 prevents a partial output from being mistaken for a complete report.
- Benchmark the installed CLI, not an internal function, against a deterministic 1 GB representative fixture. Record wall time and peak RSS. The acceptance threshold is under 30 seconds on the named reference laptop.
- A malformed subset is nonfatal when at least one valid request exists; the successful report exposes the skipped count. A totally unsupported/no-valid input is exit 3.

## 9. Testing Strategy

Unit tests cover parser quoting, timezone offsets, IPv4/IPv6 strings, empty fields, status boundaries, tie-breaking, all-zero hours, percentage formulas, cardinality boundary, and renderer escaping. Click integration tests cover files, stdin, multiple files, mutually exclusive formats, unreadable paths, zero valid input, broken pipes, stdout/stderr separation, and exit codes `0/1/2/3/4`. Golden fixtures pin JSON schema v1 and CSV columns. A marked performance test generates its input outside normal unit runs and asserts the documented budget.

## 10. Architecture Decision Record (ADR)

### ADR-001: Invocation-scoped single process

- **Status:** Accepted.
- **Decision:** Use Variant A with exact aggregation and an explicit cardinality ceiling.
- **Consequences:** Minimal installation and operational complexity; memory grows with distinct keys until a safe, visible exit 4.

### Debate Summary — labeled self-critique

No independent or adversarial reviewer was available for this benchmark. The following review is an explicitly labeled **self-critique**, applying the repository-local Devil's Advocate structure.

**Strengths acknowledged:** the architecture matches the local CLI problem, makes pipeline output deterministic, and refuses silent approximation.

**Verdict:** **APPROVE WITH CONDITIONS**.

**Challenges raised:**

1. **Exact maps may violate the memory target (High).** Alternative: approximate sketches or external sorting. Trade-off: bounded memory versus exact requested values. **Resolution:** retain exactness, enforce a configurable aggregate cardinality limit, exit 4 before partial output, and benchmark peak RSS.
2. **A Python regex parser may miss the 30-second target (High).** Alternative: native parser or multiprocessing. Trade-off: speed versus packaging and one-weekend complexity. **Resolution:** profile the installed single-process path early; compile once and minimize allocations. Trigger kill/re-scope criteria rather than silently redesigning.
3. **One fixed nginx format limits real-world usefulness (Medium).** Alternative: configurable log-format grammar. Trade-off: compatibility versus parser ambiguity and scope. **Resolution:** name combined format as the MVP contract, count malformed lines, fail on zero valid records, and keep custom formats P2.
4. **CSV combines heterogeneous sections (Medium).** Alternative: one output file per metric. Trade-off: clearer schemas versus inability to stream one report to stdout. **Resolution:** pin a normalized discriminator-based schema and golden-test it.
5. **Multiple file arguments could accidentally double-count stdin (Low).** Alternative: prohibit `-` when paths are present. Trade-off: simpler input semantics versus composition. **Resolution:** permit stdin at most once and process all sources in declared order.

**Alternatives considered and rejected:** persistent SQLite was rejected because it adds writes and lifecycle without supporting a requested feature; Go/Rust was rejected because Python 3.11 is pre-approved; an HTTP service was rejected because it adds a security and deployment boundary; multiprocessing is deferred until profiling proves it necessary.

### Conditions incorporated

The architecture now treats the cardinality ceiling, benchmark evidence, supported-format boundary, normalized CSV schema, and single-stdin rule as acceptance contracts rather than implementation suggestions.

## 11. Traceability

Product priorities and constraints originate in `STRATEGIC_PLAN.md`; user-visible acceptance is in `PRD.md`; implementation sequencing and checks are in `IMPLEMENTATION_PLAN.md`.
