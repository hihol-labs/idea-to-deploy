# Project Architecture: nginx-log-report

## Architecture Summary

The product is a single Python process with a linear pipeline:

```text
file path or stdin
        |
        v
line iterator -> combined-log parser -> in-memory aggregator -> report snapshot
                                                            -> terminal renderer
                                                            -> JSON renderer
                                                            -> CSV renderer
```

Each input line is parsed and folded into aggregates before the next line. Raw events are never retained. There is no daemon, network listener, persistent cache, or background worker.

The binding decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the required answer is a disposable summary of one supplied stream: persistence would add I/O, schema management, privacy exposure, cost, and operational setup without improving the four metrics. An HTTP API is incorrect because the users are local operators and pipeline authors: a server would add lifecycle, authentication, port, concurrency, and deployment concerns while stdin/stdout already provide the right composition boundary.

## Architecture Variants

### Variant A: Single-process streaming Python CLI (Recommended and approved)

- **Approach:** one Click process parses each line, updates exact in-memory aggregates, freezes a report dataclass, and invokes one renderer.
- **Pros:** simplest install and operation; no intermediate data; all four metrics share one scan; matches Python 3.11/Click/Rich constraint.
- **Cons:** exact cardinality-dependent maps consume memory; CPU work is single-core.
- **Best for:** local incident snapshots and Unix pipelines up to the stated 1 GB target.
- **Estimated complexity:** Low.

### Variant B: Multi-process Python map/reduce

- **Approach:** split seekable files into byte ranges, aggregate in workers, merge counters.
- **Pros:** can use multiple cores on large regular files.
- **Cons:** does not naturally support stdin; correct line-boundary splitting and merge logic add complexity; worker copies raise peak memory; unnecessary before profiling.
- **Best for:** multi-gigabyte batch files after the MVP proves CPU-bound.
- **Estimated complexity:** Medium.

### Variant C: Native Go binary

- **Approach:** implement the same streaming contract as a compiled executable.
- **Pros:** likely higher throughput and lower runtime overhead.
- **Cons:** violates the approved stack and pip-first delivery; increases implementation and packaging scope.
- **Best for:** a future rewrite only if measured Python performance cannot meet the release gate.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because it is the only option that simultaneously honors the approved stack, one-weekend budget, stdin workflow, and obvious single-process architecture. Variants B and C are documented as escalation paths, not open decisions.

## CLI Interface

### Command

```text
nginx-log-report [OPTIONS] [INPUT]
```

`INPUT` is one nginx combined-access-log file path or `-` for stdin. It defaults to `-`. The implementation must read text incrementally; it must not call `read()`, `readlines()`, or materialize the input iterator. Shell composition provides live streaming, for example `tail -F /var/log/nginx/access.log | nginx-log-report -`; built-in following is out of MVP scope.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit exactly one JSON document to stdout; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit UTF-8 RFC 4180-compatible tidy CSV to stdout; mutually exclusive with `--json` |
| `--no-color` | flag, false | Disable ANSI styling in terminal mode; accepted but has no effect on JSON/CSV bytes |
| `--strict` | flag, false | Stop on the first malformed nonblank line with exit `3`; default is skip-and-count |
| `--max-unique-user-agents INTEGER` | integer, `1000000` | Maximum distinct User-Agents retained; must be ≥1; exceeding it stops with exit `4` and no report |
| `--version` | flag | Print package version and exit `0` |
| `--help` | flag | Print Click help and exit `0` |

### Input contract

- Encoding is UTF-8. A leading UTF-8 BOM is tolerated only on the first line.
- The MVP accepts nginx **combined** format: `$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"`.
- `remote_addr` is counted as the IP key exactly as logged after syntactic validation (IPv4 or IPv6).
- The URL key is the request-target from the quoted request field (`METHOD request-target PROTOCOL`), preserved byte-for-character after UTF-8 decoding; method and protocol are not part of the key.
- A status in `400..599` increments that URL's error count and its 4xx or 5xx sub-count. Other valid statuses do not enter the error-URL counter.
- The hour is `00..23` from `$time_local` as recorded, including its offset; the MVP performs no timezone conversion.
- Blank lines are ignored and are not valid or malformed requests.
- In default mode, malformed nonblank lines increment `malformed_lines` and processing continues. In `--strict` mode the first such line is an input/data error.
- An empty input is successful and produces zero counts, zero percentages, empty top lists, and all 24 hourly buckets at zero.

### Metric semantics

- **Top IPs:** up to 10 entries sorted by request count descending, then IP ascending for deterministic ties.
- **Top error URLs:** up to 10 entries sorted by combined 4xx+5xx count descending, then URL ascending; every row includes `error_count`, `http_4xx_count`, and `http_5xx_count`.
- **Hourly request distribution:** all 24 buckets (`00` through `23`), with percentage defined literally as `100 × hourly_request_count / total_valid_requests`; when `total_valid_requests = 0`, every percentage is `0.0`.
- **Unique User-Agent share:** `100 × unique_user_agent_count / total_valid_requests`; it is `0.0` when there are no valid requests. The quoted User-Agent string, including `-`, is a value.
- Percentages remain numeric and are rounded to two decimal places only at the renderer boundary using round-half-even semantics. Raw counts are exact.

### Output contract

Diagnostics go to stderr; reports go to stdout. On exit `3` or `4`, no partial report is written.

**Terminal (default):** Rich renders a title, source/summary line, top-IP table, top-error-URL table, 24-row hourly table, and User-Agent summary. Color is enabled only when permitted by terminal detection and `--no-color` is absent. Counts and percentages are still present in plain text when styling is disabled.

**JSON:** one UTF-8 object followed by `\n`, with stable keys:

```json
{
  "schema_version": 1,
  "summary": {
    "total_valid_requests": 0,
    "malformed_lines": 0,
    "unique_user_agent_count": 0,
    "unique_user_agent_share_percent": 0.0
  },
  "top_ips": [],
  "top_error_urls": [],
  "hourly_distribution": [
    {"hour": "00", "request_count": 0, "percentage": 0.0}
  ]
}
```

`top_ips` rows contain `rank`, `ip`, and `request_count`. `top_error_urls` rows contain `rank`, `url`, `error_count`, `http_4xx_count`, and `http_5xx_count`. `hourly_distribution` always contains 24 ordered rows.

**CSV:** one tidy table with header `metric,rank,key,count,percentage,http_4xx_count,http_5xx_count`. Rows are ordered: top IPs, top error URLs, 24 hours, then one unique-User-Agent row. Unused cells are empty. CSV quoting is delegated to Python's `csv` module; newline is `\r\n` on all platforms. Summary counts not naturally represented by those rows are included as `summary_valid_requests` and `summary_malformed_lines` rows, so pipelines can audit the denominator.

### Exit-code contract

| Code | Meaning | Examples |
|---:|---|---|
| `0` | Success | Report emitted; empty input; `--help`; `--version` |
| `1` | Unexpected internal failure | Invariant violation or unforeseen runtime exception, with concise stderr diagnostic |
| `2` | CLI usage error (Click contract) | Unknown option, invalid integer, conflicting `--json --csv` |
| `3` | Input/data error | Missing/unreadable file, invalid UTF-8, or malformed line under `--strict` |
| `4` | Unique-cardinality exhaustion | A new User-Agent would exceed `--max-unique-user-agents`; no partial report |

## Components and Responsibilities

| Module | Responsibility | Must not do |
|---|---|---|
| `src/nginx_log_report/cli.py` | Click parameters, source opening, renderer selection, exception-to-exit mapping | Parse log syntax or format metrics |
| `src/nginx_log_report/parser.py` | Compiled combined-log parser and typed `LogRecord` result | Aggregate or print |
| `src/nginx_log_report/models.py` | Frozen/dataclass records, report rows, domain exceptions | Perform I/O |
| `src/nginx_log_report/aggregator.py` | Fold records into counters, enforce UA cardinality, freeze deterministic report | Retain raw records |
| `src/nginx_log_report/renderers/terminal.py` | Rich terminal report | Change domain ordering or values |
| `src/nginx_log_report/renderers/json.py` | Stable schema-versioned JSON | Emit diagnostics |
| `src/nginx_log_report/renderers/csv.py` | Stable tidy CSV | Hand-roll CSV escaping |
| `src/nginx_log_report/__main__.py` | `python -m nginx_log_report` adapter | Duplicate Click command logic |

Dependency direction is `cli/renderers -> models`, `cli -> parser + aggregator`, and `aggregator/parser -> models`. Parser, aggregator, and models do not import Click or Rich.

## Data and State Model

There are no database tables, migrations, files written by the application, or persistent caches. The generic blueprint database-table template is deliberately non-applicable under the binding stateless decision.

In-process state consists of:

| Structure | Type | Purpose | Growth |
|---|---|---|---|
| `ip_counts` | `Counter[str]` | Exact requests per validated IP | Distinct IPs |
| `error_url_counts` | `dict[str, ErrorCounts]` | Exact 4xx, 5xx, combined errors | Distinct error URLs |
| `hour_counts` | `list[int]` length 24 | Exact requests by recorded local hour | Constant |
| `user_agents` | `set[str]` | Exact distinct User-Agents | Bounded by option |
| `total_valid_requests` | `int` | Shared denominator | Constant |
| `malformed_lines` | `int` | Audit count for skipped input | Constant |

No raw line or `LogRecord` survives its aggregation call. The implementation must check whether a User-Agent is already present before enforcing the maximum, so repeated values at the limit remain valid.

## API, Authentication, and Network Boundaries

There are no HTTP endpoints, request/response bodies, authentication flows, sockets, or environment-variable secrets. The complete public interface is the CLI contract above. Adding an API or authentication would contradict the approved product boundary rather than improve it.

## Configuration and Environment

Behavior is configured only through explicit CLI arguments. No application-specific environment variables or config files are read, preventing hidden differences between interactive and pipeline execution. Standard `NO_COLOR` may be honored as an ecosystem convention, but `--no-color` is authoritative and JSON/CSV never contain ANSI bytes.

## Packaging and Deployment

Build a PEP 517 wheel and source distribution from `pyproject.toml`, requiring Python `>=3.11,<4` and exposing `nginx-log-report = nginx_log_report.cli:main`. Runtime dependencies are Click and Rich with bounded compatible versions. Deployment means `python -m pip install nginx-log-report` into a local environment. There is no Docker image, Compose file, cloud target, Kubernetes manifest, staging service, or server rollout; those generic blueprint sections are intentionally non-applicable to a pip-installed local CLI.

## Performance and Resource Model

- Time complexity is `O(n + u log 10)` in input lines and unique keys; `Counter.most_common` or a size-10 heap may be selected after profiling.
- Space is `O(i + e + a)`: distinct IPs, distinct error URLs, and distinct User-Agents. The 24 hourly buckets are constant.
- The acceptance benchmark is a deterministic 1 GB combined-log fixture, processed from a warm local filesystem in under 30 seconds on a documented laptop with Python 3.11. The benchmark records CPU, wall time, peak RSS, Python version, OS, hardware, fixture generator/seed, and command.
- Performance work follows profiling. The first optimizations are compiled regex reuse, local hot-loop bindings, minimal datetime construction, and avoiding per-record dictionaries.
- Exact IP/error URL counts remain the MVP contract. If representative logs demonstrate unsafe cardinality, approximation or additional bounds require a PRD/architecture decision rather than a silent behavior change.

## Reliability and Security

- Treat logs as untrusted data: never evaluate content, interpolate it into a shell, or allow Rich markup interpretation.
- Open only the explicit path; do not recurse, follow include directives, or write beside the input.
- Sanitize stderr messages so they contain line numbers and reason categories, not full potentially sensitive log lines.
- Catch only domain/Click/I/O boundaries. Map unexpected exceptions to `1` without a traceback by default.
- Broken pipe after downstream closure is handled quietly according to conventional CLI behavior and must not corrupt a pipeline with a traceback.
- JSON uses the standard encoder and CSV uses `csv.writer`; terminal fields render as text with markup disabled/escaped.

## Test Architecture

| Layer | Coverage |
|---|---|
| Parser unit tests | IPv4/IPv6, quoted fields, escapes, empty request, malformed timestamps/status/request lines, BOM, UTF-8 |
| Aggregator unit tests | four metrics, ties, 24 buckets, zero denominator, repeated UA at ceiling, exhaustion on new UA |
| Renderer golden tests | ANSI-free JSON/CSV, stable ordering/schema/newlines, terminal plain-text content |
| CLI integration tests | file/stdin parity, flags, conflicts, unreadable input, strict/default parsing, exit `0/1/2/3/4` |
| Packaging smoke test | clean wheel install, console script, module entry point |
| Performance test | generated 1 GB fixture, under-30-second release gate, peak-RSS record |

## Architecture Decision Record (ADR)

### ADR-001: Stateless CLI boundary

- **Status:** Accepted (pre-approved).
- **Decision:** Use Variant A and the literal binding decision stated in Architecture Summary.
- **Consequences:** minimal operation and privacy surface; no historical query; exact aggregate memory depends on distinct keys.

### ADR-002: Exact aggregation with explicit User-Agent ceiling

- **Status:** Accepted.
- **Decision:** Produce exact metrics; cap distinct User-Agents at a configurable default and fail with code `4` before emitting a partial report.
- **Consequences:** honest, deterministic behavior; adversarial distinct IP/error-URL growth remains a measured risk and future decision point.

### ADR-003: Stable renderer schemas

- **Status:** Accepted.
- **Decision:** Build one immutable report model and render it three ways; version JSON and freeze CSV columns/order.
- **Consequences:** outputs cannot disagree; schema changes require explicit versioning and PRD updates.

### Self-critique (substituting for unavailable adversarial review)

This is a self-critique by the same planning agent, **not** an independent or adversarial reviewer run.

**Verdict:** APPROVE WITH CONDITIONS.

1. **Exact IP and error-URL counters can still grow without a bound.** Resolution: retain exactness for the approved MVP, record peak RSS in the benchmark, and make representative high-cardinality fixtures a release gate; do not invent approximation without approval.
2. **A Python regex may miss the throughput target.** Resolution: benchmark after the parser/aggregator slice, profile before optimization, and treat failure of the 1 GB/30 s gate as a kill/re-scope condition.
3. **“Share of unique User-Agents” could be misread.** Resolution: define the denominator and zero-input behavior identically in architecture, PRD, and tests.
4. **CSV has heterogeneous metrics.** Resolution: freeze a tidy schema, define row ordering and empty cells, and include denominator/audit rows.
5. **Skipping malformed lines could conceal poor data quality.** Resolution: show `malformed_lines` in every output and provide fail-fast `--strict`.
6. **Terminal styling can leak control/markup interpretation.** Resolution: treat fields as untrusted text and golden-test hostile values with markup disabled.

**Alternatives considered and rejected:** GoAccess is broader than the stable pipeline contract; Elastic/Logstash introduces persistent distributed infrastructure; AWStats targets historical reporting; `grep`/`awk` remains useful for one-offs but does not provide this single validated schema; multiprocessing and Go are held as post-benchmark escalation paths.
