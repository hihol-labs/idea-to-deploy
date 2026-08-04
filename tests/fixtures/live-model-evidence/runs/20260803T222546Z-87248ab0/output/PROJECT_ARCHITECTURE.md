# Project Architecture: Nginx Log Stats

## Architecture Summary

Nginx Log Stats is an installable Python 3.11 command-line program for DevOps and SRE users. A single process reads one nginx access-log line at a time, parses the standard combined log format, updates guarded exact in-memory aggregates, and renders one report after end-of-input. There is no daemon, network listener, persistence layer, authentication boundary, or remote deployment target.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database would add writes, schema management, disk amplification, and operational state to a one-shot aggregation job whose result fits in bounded counters. An HTTP API would create a long-running service, authentication and deployment obligations without improving the local and pipeline-oriented use case. Both exclusions reduce cost and are necessary to retain a $0, one-weekend, laptop-friendly tool.

## Constraints and Quality Attributes

| Attribute | Contract |
|---|---|
| Runtime | CPython 3.11 |
| Performance | Process a 1 GB representative combined-format log in under 30 seconds on the reference laptop |
| Memory | Streaming line processing; default guard permits at most 250,000 total distinct keys across IP, error-URL, and User-Agent counters; representative benchmark peak RSS must be <=512 MiB |
| Cost | $0 runtime and service budget; open-source dependencies only |
| Portability | Installable with `pip`; Linux and macOS primary, Windows supported where text streams are available |
| Determinism | Same valid records and options produce the same machine-readable output ordering |
| Pipeline safety | Data on stdout, diagnostics on stderr; color disabled outside terminal output |
| Security | Treat log fields as untrusted text; never evaluate them or emit terminal control characters unsanitized |

## Architecture Variants

The architecture is pre-approved because the constraints make the choice obvious. These alternatives are recorded for traceability, not as an open decision.

### Variant A: Single-process streaming CLI (Selected)

- **Approach:** parser and aggregators run synchronously in one Python process; render after EOF.
- **Pros:** minimal dependencies and operational surface; natural stdin support; predictable failure model; achievable in one weekend.
- **Cons:** exact distinct-value counters can grow with cardinality; no cross-run history.
- **Best for:** local analysis and shell pipelines over individual log streams.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunked CLI

- **Approach:** split seekable files, parse chunks in workers, and merge partial counters.
- **Pros:** can use multiple CPU cores on very large regular files.
- **Cons:** cannot naturally split stdin; byte-boundary handling and deterministic merging add complexity; startup and serialization overhead may erase gains at 1 GB.
- **Best for:** repeated multi-gigabyte batch jobs after profiling proves parsing is CPU-bound.
- **Estimated complexity:** Medium.

### Variant C: Persistent analytics service

- **Approach:** ingest into a database and query through an HTTP service.
- **Pros:** historical queries and multi-user access.
- **Cons:** directly violates the approved no-database/no-API scope, $0 operations, and one-weekend delivery.
- **Best for:** a different product requiring retained history and shared dashboards.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected. The performance target is modest enough for optimized line-by-line parsing, while the stateless CLI model directly matches local files, stdin, and pipelines. Variant B remains a measured-performance contingency; Variant C is out of scope.

## Component Design

```text
path or stdin
     |
     v
InputSource -> CombinedLogParser -> RecordFilter -> StreamingAggregates
                    | invalid              |          | IP Counter
                    +------> Diagnostics   |          | Error-URL Counter
                                           |          | 24 hourly buckets
                                           |          | User-Agent Counter
                                           v          v
                                      RunStats ---> ReportModel
                                                       |
                                  +--------------------+------------------+
                                  v                    v                  v
                            Rich terminal          JSON writer        CSV writer
```

| Component | Planned path | Responsibility |
|---|---|---|
| Click entry point | `src/nginx_log_stats/cli.py` | Validate options, select streams and renderer, map exceptions to exit codes |
| Input source | `src/nginx_log_stats/input.py` | Read binary physical lines from a path or `sys.stdin.buffer`, enforce line/cardinality guards, and decode each line independently |
| Parser | `src/nginx_log_stats/parser.py` | Convert a combined-log line to an immutable `AccessRecord` dataclass |
| Models | `src/nginx_log_stats/models.py` | `AccessRecord`, `Report`, and summary dataclasses |
| Aggregation | `src/nginx_log_stats/aggregate.py` | Maintain counters and compute deterministic top-10 results and ratios |
| Terminal output | `src/nginx_log_stats/renderers/terminal.py` | Rich tables, headings, and summary diagnostics |
| JSON output | `src/nginx_log_stats/renderers/json.py` | Stable JSON object for pipelines |
| CSV output | `src/nginx_log_stats/renderers/csv.py` | Stable normalized CSV rows |
| Sanitization | `src/nginx_log_stats/sanitize.py` | Strip/control terminal-unsafe characters from untrusted fields |

Dependencies point inward: renderers and CLI may depend on models; the parser and aggregator do not depend on Click or Rich. Standard-library `re`, `collections`, `datetime`, `json`, `csv`, and `pathlib` cover core processing. Click handles the command contract, Rich handles only human output, and dataclasses define typed internal records.

## Processing and Data Model

The default accepted grammar is nginx's combined access-log format using nginx's default log escaping:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

`AccessRecord` contains `ip: str`, `timestamp: datetime`, `method: str | None`, `url: str`, `protocol: str | None`, `status: int`, `bytes_sent: int | None`, `referer: str | None`, and `user_agent: str`. The parser accepts IPv4/IPv6 address text, nginx default `\"` and `\\` escapes in quoted fields, and the special request value `"-"`; for that special case, `method`/`protocol` are `None` and `url` is the literal `-`. Other requests must have exactly three whitespace-delimited parts, so request targets containing raw spaces and `escape=json`/`escape=none` variants are outside MVP. The URL is not URL-decoded. A `-` byte count becomes `None`. Timestamps must include an offset. Fixtures and fuzz tests make these boundaries executable.

For each valid record, the aggregator performs constant-time updates:

- increment total valid requests and `ip_counts[ip]`;
- increment `error_url_counts[url]` when `400 <= status <= 599`;
- increment one of 24 `hour_counts[timestamp.hour]` buckets using the hour as written in the log's local offset;
- increment `user_agent_counts[user_agent]`.

At EOF, top lists sort by descending count and then ascending value for deterministic ties. `unique_user_agent_share` is `distinct_user_agents / valid_requests * 100`, or `0.0` when no valid requests exist. It measures the share of requests represented by unique User-Agent values, not human users. Exact counters are chosen because all four requested metrics are exact; a later approximate-cardinality mode is a possible P2 extension if high-cardinality memory is measured as a problem.

Before inserting a new key, the aggregator checks the combined distinct-key count across the three unbounded maps. At the default 250,000-key ceiling it exits cleanly with code `4`; `--max-cardinality` lets a user deliberately choose `1..5,000,000`. Input also rejects a physical line over 1 MiB as malformed, preventing one field from bypassing the cardinality guard. Exactness is preserved within the selected envelope; approximation is not silently introduced. There are no database tables, migrations, indexes, caches, or retained records. Process memory is released at exit.

## CLI Interface

### Command

```text
nginx-log-stats [OPTIONS] [INPUT]
```

`INPUT` is one nginx access-log file. If omitted or `-`, the command reads stdin. Paths and `sys.stdin.buffer` are consumed as binary physical lines, then each line is independently decoded so a decode failure can be skipped deterministically in default mode or attributed to a one-based line in strict mode. Text-only stdin wrappers are supported through their `.buffer` equivalent when present; otherwise already-decoded text is accepted for test/embedded use. The MVP consumes a **finite** stream and emits the report at EOF. Infinite `tail -F` streams and partial reports on `SIGINT` are not supported; users must first capture a finite window (for example, with `head`, `timeout` plus a file, or log rotation). Compressed files, multiple positional files, and directory traversal are not supported in MVP.

### Options

| Option | Meaning | Default / constraints |
|---|---|---|
| `--json` | Emit one JSON document | Mutually exclusive with `--csv` |
| `--csv` | Emit normalized CSV | Mutually exclusive with `--json` |
| `--top INTEGER` | Number of ranked IPs and error URLs | `10`; integer `1..100` |
| `--strict` | Stop at the first malformed line | Off; default skips malformed lines and reports their count |
| `--encoding TEXT` | Input text encoding | `utf-8`; decoding errors are malformed input |
| `--max-cardinality INTEGER` | Maximum combined distinct IP/error-URL/User-Agent keys | `250000`; integer `1..5000000`; exceeding it exits `4` |
| `--no-color` | Disable Rich colors in terminal mode | Color otherwise follows terminal capability and `NO_COLOR` |
| `--version` | Print package version and exit | — |
| `--help` | Print usage and exit | — |

### Outputs

Terminal mode writes four Rich sections to stdout: top IPs, top URLs with 4xx/5xx responses, all 24 hourly buckets, and unique User-Agent share plus valid/malformed totals. Untrusted IP, URL, and User-Agent strings are escaped or stripped of control sequences before display.

JSON mode writes a single object with schema version `1`:

```json
{
  "schema_version": 1,
  "summary": {"valid_requests": 0, "malformed_lines": 0, "unique_user_agents": 0, "unique_user_agent_share": 0.0},
  "top_ips": [{"ip": "192.0.2.1", "requests": 1}],
  "top_error_urls": [{"url": "/missing", "errors": 1}],
  "hourly_requests": [{"hour": 0, "requests": 0}]
}
```

`hourly_requests` always contains hours `0` through `23`. JSON output uses UTF-8, no ANSI escapes, and a trailing newline.

CSV mode writes this stable header:

```csv
section,key,value,rank
```

Rows use `section` values `summary`, `top_ip`, `top_error_url`, and `hourly_request`; `key` holds the metric name/IP/URL/hour, `value` holds the numeric value, and `rank` is populated only for top lists. Fields are quoted according to RFC 4180 rules. CSV contains no ANSI escapes. Diagnostics and skipped-line summaries go to stderr in JSON/CSV modes so stdout remains parseable.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Report completed, including an empty stream or a non-strict run with skipped malformed lines |
| `1` | Runtime failure while reading or writing the stream, including a broken/unwritable output |
| `2` | Click usage error: invalid option, incompatible output flags, invalid `--top`, or missing input path |
| `3` | Input-data error in `--strict` mode, including malformed syntax, invalid timestamp/status, or decoding failure |
| `4` | Configured cardinality/resource guard exceeded before an exact report could be produced |

## Error Handling and Observability

Default mode counts malformed lines, skips them, and prints one bounded summary rather than echoing log contents. Binary-per-line ingestion makes decoding failures recoverable at the next physical line. `--strict` reports the one-based line number and a categorical reason to stderr, without reproducing potentially sensitive request data. Missing/unreadable inputs fail before output. A broken stdout pipe exits without a traceback and follows code `1` unless the platform convention makes the write unobservable. `SIGINT` produces no partial report and follows the conventional interrupted-process behavior; it is not a successful analysis.

No telemetry or network calls are made. Performance benchmarking records elapsed time, peak resident memory, Python version, OS, CPU, input bytes, valid line count, and malformed line count locally.

## Security and Privacy Boundaries

- Logs may contain IP addresses, URLs, referrers, and User-Agents; the tool neither transmits nor persists them.
- Paths are opened read-only. The tool does not expand globs, follow URLs, execute shell commands, or interpret log content.
- Rich markup is disabled or escaped for data cells, C0/C1 controls are sanitized, and JSON/CSV use their standard encoders.
- Error messages avoid printing complete log lines. No secrets are required as environment variables.
- The cardinality and 1 MiB line-length guards bound supported exact inputs; raising the cardinality limit raises memory risk and is an explicit operator choice.
- CSV is a lossless machine-data format. Standard quoting does not neutralize spreadsheet formulas; users must import it as text rather than execute formula-leading cells. A future spreadsheet-safe mode may transform such values but is not the default because it would break exact round-tripping.

## Packaging and Deployment

The distribution uses a `pyproject.toml` build with a `src/` layout and console script `nginx-log-stats = nginx_log_stats.cli:main`. Runtime dependencies are constrained to compatible Click and Rich releases; Python 3.11 is the minimum. The deployment target is the user's local Python environment or isolated `pipx` environment. Publication to PyPI may be automated later, but MVP verification installs the wheel into a clean local virtual environment.

There is no Docker image, `docker-compose.yml`, server process, cloud resource, Kubernetes manifest, authentication flow, secret, or application environment variable. `NO_COLOR` is a conventional optional process setting, not a product secret. This absence is intentional and follows the selected CLI architecture.

## Performance Strategy

The first implementation gate is a performance spike, before renderer work. It compares the correctness-first `AccessRecord` path with a specialized streaming hot path that extracts only aggregation fields and timestamp hour without requiring per-line `datetime`/dataclass allocation. The deterministic 1 GB fixture manifest records byte size, record count, line-length distribution, malformed rate, and distinct IP/error-URL/User-Agent cardinalities. The chosen parser must match the reference parser's report exactly, finish in under 30 seconds, and keep peak RSS at or below 512 MiB on the declared laptop. Until that evidence exists, throughput is explicitly unverified. Optimizations are accepted only after profiling; multiprocessing is deferred unless a correct single process misses the target after measured optimization.

The benchmark acceptance command will take the form:

```bash
/usr/bin/time -v nginx-log-stats --json /path/to/representative-1gb.log > /tmp/nginx-log-stats.json
```

Pass criteria are wall time under 30 seconds, exit code `0`, parseable schema-version-1 JSON, and correct totals against the fixture manifest.

## Architecture Decision Record (ADR)

### ADR-001: Single-process stateless streaming

- **Status:** Selected with review conditions resolved in the specification; runtime evidence remains required.
- **Decision:** Use Variant A with exact guarded in-memory counters, binary-per-line ingestion, finite-stream post-EOF rendering, and an early performance spike.
- **Drivers:** 1 GB/30-second target, stdin pipelines, $0 budget, one-weekend scope, exact top lists and unique count.
- **Rejected:** persistent service because it violates product constraints; multiprocessing until evidence shows it is required.

### ADR-002: Three explicit presentation adapters

- **Status:** Selected.
- **Decision:** Build one renderer-neutral `Report` and separate terminal, JSON, and CSV adapters.
- **Reason:** prevents color and prose from leaking into pipeline formats and makes output contracts independently testable.

### Debate Summary

The architecture was reviewed by the repository-local Devil's Advocate agent.

**Verdict:** APPROVE WITH CONDITIONS.

**Challenges raised and resolutions:**

1. Exact counters were incorrectly described as bounded. **Resolution:** added a default 250,000 combined-key guard, 1 MiB line guard, code `4`, explicit operator override, and <=512 MiB representative-fixture gate.
2. The 1 GB/<30 s target had no architectural proof. **Resolution:** made a deterministic fixture manifest and reference-vs-hot-path performance spike the first implementation gate; the richer allocation path is retained only if measured.
3. Text iteration could not reliably recover after a decoding error. **Resolution:** specified binary physical-line reads with independent decoding and line accounting.
4. `tail -F` conflicted with render-at-EOF semantics. **Resolution:** removed live/infinite-stream support from MVP and made `SIGINT` non-successful with no partial report.
5. RFC 4180 quoting does not stop spreadsheet formula interpretation. **Resolution:** classified CSV as lossless machine data, documented safe text import, and deferred value-transforming spreadsheet-safe output.
6. Combined-format edge cases were underspecified. **Resolution:** defined default nginx escape handling, IPv6 text, `"-"` requests, three-token requests, and rejected escaping variants.

**Alternatives considered and rejected:**

- Approximate Space-Saving/HyperLogLog aggregates — rejected for MVP because exact metrics are required; a fail-closed cardinality guard is explicit instead.
- Multiprocess parsing — rejected until the performance spike proves a correct single process insufficient.
- Persistent analytics service — rejected because it violates the approved local, stateless CLI contract.

Implementation-level performance, signal, and parser compatibility behavior remains unverified until the tests and benchmark in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) run.

## Verification Strategy

Unit tests cover parser grammar and malformed categories, aggregation/tie ordering, 4xx/5xx boundaries, timezone-hour behavior, empty input, sanitization, and renderer schemas. Click integration tests cover stdin/files, mutually exclusive formats, broken inputs, strict/default behavior, stdout/stderr separation, and exit codes. Property/fuzz cases exercise arbitrary untrusted field text. A wheel smoke test validates installation and entry-point behavior. The performance test uses a generated 1 GB fixture with a separately stored expected manifest.

This document is the architecture source of truth for [PRD.md](PRD.md) and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
