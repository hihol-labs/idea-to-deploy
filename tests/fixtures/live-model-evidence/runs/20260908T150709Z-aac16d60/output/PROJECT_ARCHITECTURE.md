# Project Architecture: nginx-insights

## 1. Context and Goals

`nginx-insights` is a Python 3.11 CLI that reads nginx access logs sequentially and produces four summaries: top-10 IPs, top-10 URL paths among 4xx/5xx requests, hourly request distribution, and unique User-Agent share. Its non-functional target is a 1 GB input in under 30 seconds on a documented laptop. The architecture optimizes for a one-weekend, $0, local-only release.

The controlling decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is wrong here because inputs are already append-style files or streams, outputs are aggregate snapshots, persistence creates cost and lifecycle work, and retaining potentially sensitive access data expands the threat surface. An HTTP API is wrong because the intended users work locally and in shell pipelines; a server would add authentication, deployment, concurrency, and operational obligations without improving the required analysis.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended)

- **Approach:** one Python process parses each line once, updates in-memory counters, and renders only after EOF.
- **Pros:** simplest correctness model; works with stdin; no IPC or temporary storage; aligned with the approved stack and weekend budget.
- **Cons:** CPU-bound parsing uses one core; aggregation cardinality must be bounded explicitly.
- **Best for:** the stated local 1 GB workload and stable common/combined nginx formats.
- **Estimated complexity:** Low.

### Variant B: Chunked multiprocessing

- **Approach:** split seekable files into byte ranges, parse in workers, then merge counters.
- **Pros:** can use multiple cores for large regular files.
- **Cons:** cannot naturally split stdin; boundary handling and counter merging add correctness risk; higher peak memory; unnecessary before measurement.
- **Best for:** a future workload proven to exceed the single-process performance budget.
- **Estimated complexity:** Medium.

### Variant C: SQLite-backed aggregation

- **Approach:** write parsed keys and counters into a local temporary SQLite database.
- **Pros:** handles very high key cardinality with bounded RAM and supports later queries.
- **Cons:** violates the approved no-database boundary, adds disk I/O and cleanup, and is slower for an ephemeral four-metric report.
- **Best for:** a different product requiring persistent or exploratory history.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected. It is the obvious fit for a stateless CLI, preserves stdin streaming, minimizes moving parts, and should meet the performance target with a lean parser. Variants B and C are documented only as rejected alternatives; they are not part of MVP implementation.

## 3. System Context

```text
nginx log file(s) or stdin
            |
            v
  Click CLI + input manager
            |
            v
  line parser -> valid AccessRecord -----> streaming Aggregator
       |                    invalid lines          |
       +-------------------------> diagnostics     v
                                              ReportSnapshot
                                                    |
                          +-------------------------+------------------+
                          v                         v                  v
                    Rich terminal              JSON stdout        CSV stdout
```

There are no external services, network calls, persistent stores, background workers, accounts, secrets, or telemetry.

## 4. Component Design

| Module | Responsibility | Key contract |
|---|---|---|
| `src/nginx_insights/cli.py` | Click command, option validation, stream lifecycle, exit mapping | Does not contain parsing or rendering logic |
| `src/nginx_insights/models.py` | Frozen `AccessRecord`, `ReportSnapshot`, ranked-entry dataclasses | Domain values are renderer-independent |
| `src/nginx_insights/parser.py` | Parse declared common/combined lines into records | Returns a record or a typed invalid-line result; never prints |
| `src/nginx_insights/normalize.py` | Normalize request targets to URL paths | Removes query and fragment; preserves `/`; uses a documented fallback for malformed targets |
| `src/nginx_insights/aggregate.py` | Update totals, counters, hourly buckets, UA set/cap | One record at a time; no retained raw lines |
| `src/nginx_insights/report.py` | Deterministic sorting and percentage calculation | Count descending, then key ascending for ties |
| `src/nginx_insights/render_terminal.py` | Rich terminal tables and warnings | Color only when enabled; report content matches machine modes |
| `src/nginx_insights/render_json.py` | Versioned JSON serialization | One valid JSON document on stdout |
| `src/nginx_insights/render_csv.py` | Long-form CSV serialization | Fixed header and one row per metric item |
| `src/nginx_insights/errors.py` | Typed operational failures and exit codes | Central mapping for `0/1/2/3/4` |

## 5. Data Model and Aggregation Semantics

### AccessRecord

| Field | Python type | Meaning |
|---|---|---|
| `client_ip` | `str` | First nginx remote-address token, preserved verbatim after validation |
| `timestamp` | `datetime` | Offset-aware nginx timestamp |
| `method` | `str | None` | Request method; `None` for an nginx `-` request field |
| `target` | `str | None` | Raw request target before normalization |
| `url_path` | `str | None` | Normalized path used for error ranking |
| `protocol` | `str | None` | HTTP protocol token when available |
| `status` | `int` | Three-digit HTTP status |
| `user_agent` | `str | None` | Combined-log UA; `None` for absent or `-` |

### Streaming state

- `total_lines: int`
- `total_valid_requests: int`
- `invalid_lines: int`
- `ip_counts: Counter[str]`
- `error_url_counts: Counter[str]`, updated only when `400 <= status <= 599` and a normalized path exists
- `hour_counts: list[int]` of exactly 24 buckets, using the offset encoded in each log timestamp
- `unique_user_agents: set[str]`, excluding missing/`-` values and capped by `--max-unique-user-agents`
- `requests_with_user_agent: int`, the denominator for UA share

Top lists contain at most ten entries and sort by count descending, then label ascending. Hourly request distribution includes all 24 buckets and is a percentage calculated exactly as `100 × hourly_request_count / total_valid_requests`. Unique User-Agent share is `100 × unique_user_agent_count / requests_with_user_agent`; it is `0.0` when no valid request supplies a User-Agent. Percentages are full-precision values in JSON and rounded to two decimal places in terminal and CSV presentation.

The parser accepts nginx common and combined access-log records. Invalid lines are skipped and counted. A run with at least one valid record succeeds; a run with zero valid records exits 3 and emits no report. Raw log lines are never stored.

### Persistent data model

None. There are zero database tables, schemas, migrations, indexes, caches, or durable application data. This is deliberate, not an omitted design area.

## CLI Interface

### Command

```text
nginx-insights [OPTIONS] [INPUT]...
```

With no `INPUT`, the command reads stdin. `INPUT` may contain one or more regular text-file paths; `-` denotes stdin and may appear at most once. Inputs are processed in argument order as one logical stream. The command reads bytes incrementally and never requires seeking.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit one JSON report; mutually exclusive with `--csv` |
| `--csv` | false | Emit long-form CSV; mutually exclusive with `--json` |
| `--color / --no-color` | auto | Force or disable color in terminal mode; rejected with machine modes |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive hard cap on distinct non-empty User-Agents |
| `--version` | n/a | Print package version and exit 0 |
| `--help` | n/a | Print usage and exit 0 |

### Outputs

- **Terminal (default):** four Rich sections plus processed/valid/invalid counts. Human diagnostics go to stderr. Color is enabled only for a TTY unless forced.
- **JSON:** UTF-8 object with keys `schema_version`, `source_count`, `total_lines`, `total_valid_requests`, `invalid_lines`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`. Ranked entries contain `rank`, label, and `count`; hourly entries contain `hour`, `count`, and `percentage`; `user_agents` contains `unique_count`, `request_count`, and `share_percentage`.
- **CSV:** UTF-8 with header `metric,rank,key,count,percentage`. Top-list rows leave percentage empty; hourly rows use keys `00` through `23`; the UA summary uses metric `unique_user_agent_share`.

Stdout contains only the selected report format, enabling redirection. Warnings and actionable errors go to stderr. On failure, no partial JSON or CSV document is emitted.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Success, including successful processing with some skipped invalid lines |
| `1` | Input/output failure: unreadable input, read error, broken output other than normal pipe closure |
| `2` | Click usage or configuration error, including conflicting options or an invalid cap |
| `3` | Data/parse failure: input completed but contained zero valid requests |
| `4` | Unique-cardinality exhaustion: adding a new User-Agent would exceed the configured cap |

## 7. Error Handling and Resource Bounds

The input manager closes only streams it opens. A normal downstream pipe closure is treated as clean termination; other output failures map to code 1. Parser failures are data, not exceptions crossing the record boundary. Unexpected internal exceptions are reported concisely and map to code 1 without a traceback unless a future debug option is explicitly specified.

Memory use is `O(U_ip + U_error_path + min(U_ua, cap) + 24)`, not `O(lines)`. IP and error-path counters remain input-cardinality-dependent in the MVP; the 1 GB benchmark records peak RSS, and a future bounded heavy-hitter algorithm requires a spec change because it would make top-10 results approximate. User-Agent cardinality is fail-closed: the command exits 4 before inserting the key that exceeds the cap and emits no partial report.

## 8. Security and Privacy

- No input content leaves the machine.
- No raw line is persisted by the application.
- Log text is untrusted data; it is never evaluated, used as a path, or rendered with Rich markup enabled.
- JSON and CSV use standard serializers for escaping.
- Terminal values are emitted as literal text to avoid control/markup injection.
- Error messages include file paths and line counts but do not echo full log lines by default.
- Packaging pins only direct compatibility ranges; release checks inspect dependency vulnerabilities and licenses.

Authentication is not applicable because there is no server, remote interface, account, or privileged action. The tool runs with the invoking user's file permissions and does not elevate privileges.

## 9. Packaging and Deployment

The deployment target is a local Python 3.11 environment installed through pip from the source tree initially and a standard package artifact at release. `pyproject.toml` defines the `nginx-insights` console script. There is no Docker image, Compose file, daemon, HTTP listener, cloud resource, or Kubernetes manifest. A virtual environment is recommended but not required by the runtime contract.

Configuration uses CLI options only. There are no required environment variables or secret files.

## 10. Performance Strategy

- Read and parse incrementally with buffered file iteration.
- Compile parser patterns once or use a measured manual parser; select by benchmark evidence.
- Keep Rich entirely outside the hot loop.
- Normalize only fields used by aggregates.
- Use `Counter` and fixed 24-element storage.
- Benchmark a deterministic generated 1 GB corpus after functional correctness is green.
- Record Python version, OS, CPU, storage, elapsed wall time, throughput, and peak RSS; acceptance is median wall time below 30 seconds across three warm-cache runs on the reference laptop.

## 11. Testing Strategy

Unit tests cover parser edge cases, URL normalization, error status boundaries, deterministic ranking, percentage formulas, missing UAs, and cap exhaustion. CLI tests cover file/stdin equivalence, multiple files, each output mode, stderr separation, conflicting options, and every exit code. Golden tests validate JSON structure and CSV header/rows. The performance test is separately marked so ordinary tests stay fast.

Key fixtures include IPv4/IPv6, escaped quotes, `-` fields, timezone offsets, malformed status/timestamp/request fields, query strings, ties, 399/400/599/600 boundaries, empty input, all-invalid input, and a UA cap crossing.

## 12. Architecture Decision Records

### ADR-001: Single-process streaming

- **Status:** Accepted by the supplied product decision.
- **Decision:** Use Variant A and retain no raw records.
- **Consequences:** minimal operational complexity and stdin support; exact counters may grow with distinct IPs/paths and must be measured.

### ADR-002: No database and no HTTP API

- **Status:** Accepted.
- **Decision:** Keep the product local, ephemeral, and CLI-only.
- **Consequences:** $0 infrastructure and small attack surface; no historical query or remote collaboration features.

### ADR-003: Exact results with explicit UA cap

- **Status:** Accepted.
- **Decision:** Keep exact rankings and exact unique-UA counts; fail with code 4 if the UA cap would be exceeded.
- **Consequences:** deterministic reports; pathological cardinality is an explicit failure rather than silent approximation.

The external adversarial review is intentionally outside this blueprint session and is not represented as completed here.
