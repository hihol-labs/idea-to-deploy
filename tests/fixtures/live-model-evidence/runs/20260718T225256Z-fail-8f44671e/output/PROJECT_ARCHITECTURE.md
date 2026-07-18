# Project Architecture: nginx-stream-report

## 1. Context and constraints

The system is a local Python 3.11 process invoked from a shell. It consumes one nginx combined access-log stream, retains only aggregate state, and writes one report to stdout. It has no network listener and no persistent product state. The explicit architectural decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema lifecycle, disk amplification, cleanup, and operational state without helping a one-shot four-metric report. An HTTP API would introduce a daemon, bind address, lifecycle management, authentication questions, and a larger attack surface while the target users already work in terminals and pipelines. File/stdin input plus stdout/stderr and process exit codes are the complete interface required by the product.

## 2. Architecture decision and considered alternatives

### Chosen: single-process streaming pipeline

- **Approach:** `binary stream -> decode/parse -> update aggregates -> immutable report model -> one renderer` in one Python process.
- **Pros:** minimal deployment, deterministic flow, low startup cost, easy piping, no IPC or persisted sensitive logs.
- **Cons:** one CPU core and exact high-cardinality sets may constrain throughput or memory.
- **Best for:** the approved one-laptop, one-file, one-weekend product.
- **Estimated complexity:** Low.

### Rejected: chunked multiprocessing

- **Approach:** split seekable files on newline boundaries, parse in workers, merge partial aggregates.
- **Pros:** can use multiple cores.
- **Cons:** does not naturally support stdin, complicates timestamps and errors, duplicates high-cardinality state, adds IPC and benchmark variance.
- **Best for:** a later version only if profiling proves parsing is CPU-bound.
- **Estimated complexity:** Medium.

### Rejected: ingest into an analytics store

- **Approach:** normalize every log line into a local or remote database and query it.
- **Pros:** reusable ad-hoc queries and historical retention.
- **Cons:** directly violates statelessness, increases runtime and storage, and duplicates GoAccess/Elastic-class tools.
- **Best for:** ongoing historical analytics, which is out of scope.
- **Estimated complexity:** High.

### Recommendation

The chosen single-process pipeline is pre-approved and best matches local stdin support, zero budget, weekend delivery, and the 1 GB target. Multiprocessing remains a measured fallback, not speculative complexity.

## 3. Component model

```text
file path ─┐
           ├─> Click CLI ─> binary line reader ─> combined-log parser
stdin ─────┘                                      │
                                                  v
                                           streaming analyzer
                                      ┌───────────┼───────────┐
                                      v           v           v
                                 counters     hour bins   UA exact set
                                      └───────────┼───────────┘
                                                  v
                                            Report dataclass
                                         ┌────────┼────────┐
                                         v        v        v
                                      Rich text  JSON     CSV
```

Planned source boundaries:

| Path | Responsibility |
|---|---|
| `src/nginx_stream_report/cli.py` | Click command, option validation, stream ownership, exit codes |
| `src/nginx_stream_report/parser.py` | Parse one combined-format byte line into `AccessRecord` |
| `src/nginx_stream_report/models.py` | `AccessRecord`, ranked item, hourly bucket, and `Report` dataclasses |
| `src/nginx_stream_report/analyzer.py` | One-pass state updates and deterministic finalization |
| `src/nginx_stream_report/renderers/text.py` | Rich terminal report and color policy |
| `src/nginx_stream_report/renderers/json.py` | Stable JSON document serialization |
| `src/nginx_stream_report/renderers/csv.py` | Normalized multi-section CSV serialization |

The parser and analyzer contain no Click or Rich dependencies. Renderers consume only the finalized report model, preventing format-specific business logic.

## 4. Processing and data contracts

### Supported input

- One positional `PATH`, or `-`/omitted input for stdin.
- nginx combined log format: remote address, remote user, local timestamp with numeric offset, request line, status, response bytes, referrer, and User-Agent.
- Input is opened in binary mode and iterated line by line. Fields are decoded as UTF-8 with replacement for invalid bytes; raw lines are never retained.
- Blank and malformed lines are skipped by default and counted. If no valid records exist, the command exits with a data-error code and explains the failure on stderr.
- The timestamp offset is parsed, but hourly distribution uses the hour printed in each log entry. This answers “server-log clock distribution” without silently converting mixed offsets.

### In-memory models

| Dataclass/state | Fields | Invariant |
|---|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `method: str`, `url: str`, `protocol: str`, `status: int`, `user_agent: str` | Created only for syntactically valid lines |
| `AnalyzerState` | `total: int`, `malformed: int`, `ip_counts: Counter[str]`, `error_url_counts: Counter[str]`, `hour_counts: list[int]`, `user_agents: set[str]` | One state instance per invocation; no input records retained |
| `RankedCount` | `value: str`, `count: int` | Final ranking sorted by count descending, then value ascending |
| `Report` | `total_requests`, `malformed_lines`, `top_ips`, `top_error_urls`, `hourly_requests`, `unique_user_agents`, `unique_user_agent_share` | Share is `unique_user_agents / total_requests * 100`, or `0.0` when total is zero |

“Share of unique User-Agents” is defined as `distinct non-empty User-Agent strings / valid requests × 100`, expressed as a percentage. The exact set provides deterministic results; the benchmark must report its peak memory. A later approximate-cardinality mode requires an explicit PRD change because it changes semantics.

### Aggregation rules

- Every valid record increments total requests, its IP counter, and its `00`–`23` hour bucket.
- Statuses 400–599 increment the counter keyed by the request-target URL exactly as logged.
- A non-empty User-Agent is inserted into the exact distinct set; `"-"` is treated as missing.
- Top lists contain at most 10 entries and use deterministic tie-breaking: `(-count, value)`.
- Arithmetic uses counts with no sampling. Render rounding occurs only at the final boundary.

### Complexity

For `n` valid lines and cardinalities `i`, `u`, and `a` for IPs, error URLs, and User-Agents: time is `O(n + i log 10 + u log 10)` using bounded top selection or equivalent deterministic ranking, and memory is `O(i + u + a + 24)`. The application never stores all log records. Exact aggregate cardinality—not file size—is the primary memory risk.

## 5. CLI interface (the public API)

```text
nginx-stream-report [OPTIONS] [PATH]

PATH                         nginx access log; omit or use - for stdin
--json                       emit one JSON document
--csv                        emit normalized CSV rows
--strict                     fail on the first malformed line (P1)
--no-color                   disable terminal colors (P1)
--version                    print version and exit
--help                       print usage and exit
```

`--json` and `--csv` are mutually exclusive. Default text uses color only when stdout is an interactive terminal and respects `NO_COLOR`; pipeline modes never emit ANSI escapes. Report data goes to stdout; diagnostics go to stderr.

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Report generated from at least one valid record |
| 2 | Click usage/option error |
| 3 | Input cannot be opened or read |
| 4 | No valid records, or malformed data under `--strict` |
| 70 | Unexpected internal error; concise message without traceback by default |

### JSON schema

The top-level object has `schema_version` (`1`), `summary`, `top_ips`, `top_error_urls`, and `hourly_requests`. `summary` contains numeric `total_requests`, `malformed_lines`, `unique_user_agents`, and `unique_user_agent_share_percent`. Ranked arrays contain `{value, count}` objects. Hourly requests contains all 24 keys `00` through `23`, including zeros. Key names and types are release contracts.

### CSV schema

CSV emits the fixed header `section,rank,key,count,share_percent`. Rows use sections `summary`, `top_ip`, `top_error_url`, and `hour`. Irrelevant fields are empty, not omitted. The summary row carries total count and User-Agent percentage; top rows carry 1-based rank, key, and count; 24 hour rows use `00`–`23` as key. RFC 4180 quoting is delegated to Python's `csv` module.

## 6. Database, HTTP API, authentication, and server contracts

| Concern | Decision | Justification |
|---|---|---|
| Database tables/indexes/migrations | None | No persistence is needed; aggregates die with the process |
| HTTP endpoints/request bodies | None | The CLI contract above is the only public interface |
| Authentication/authorization | None | No server, accounts, privilege boundary, or remote access exists |
| Docker/Compose | None | pip and a Python 3.11 environment are the deployment unit |
| Cloud/Kubernetes | None | Explicitly excluded and provides no value for a local process |

Local filesystem permissions are the trust boundary. The tool opens only the path the user supplies, performs no shell expansion, makes no outbound requests, and does not write the input or report unless the caller redirects stdout.

## 7. Configuration and environment

There is no required configuration file or secret.

| Environment variable | Behavior | Example |
|---|---|---|
| `NO_COLOR` | Any non-empty value disables Rich color | `NO_COLOR=1` |
| `PYTHONUTF8` | Standard Python UTF-8 mode; optional operational override | `PYTHONUTF8=1` |

CLI flags take precedence over terminal auto-detection. No product-specific environment variables are introduced in MVP.

## 8. Packaging and local deployment

The package uses a `src/` layout, declares Python `>=3.11,<4`, and exposes the console script `nginx-stream-report = nginx_stream_report.cli:main`. Runtime dependencies are pinned by compatible ranges for Click and Rich; development extras hold pytest, Ruff, and mypy. Release verification builds a wheel and source distribution, installs the wheel into a clean virtual environment, and runs `nginx-stream-report --help` and a golden fixture.

## 9. Performance architecture

- Read buffered binary lines; do not call `read()` without a size or materialize `list(file)`.
- Compile parsing machinery once at module import or use a single-pass scanner; profile the chosen parser.
- Update primitive counters directly and construct dataclasses only at the parser/report boundaries.
- Render only after EOF so terminal work is independent of input length.
- Benchmark a reproducibly generated 1 GB combined-format fixture outside the repository, record CPU, Python version, storage type, wall time, and peak RSS.
- The release gate is `<30 s` wall time on the declared reference laptop. Benchmark results from warm and cold cache are labeled; the target applies to the documented reference run.

## 10. Reliability and security

- Cap any retained diagnostic sample; counts are unbounded integers but raw malformed lines are not accumulated.
- Treat log content as untrusted data. Rich markup is disabled/escaped, CSV uses the standard encoder, and JSON uses the standard serializer.
- Do not interpret request targets, referrers, or User-Agents as terminal markup, format strings, file paths, URLs to fetch, or commands.
- Broken pipes terminate quietly with a pipeline-compatible non-error outcome after closing stdout.
- File I/O and parse errors include line number where useful but never echo an entire potentially sensitive line by default.
- Tests cover ANSI/control characters, CSV formula-leading values as data, oversized fields, invalid bytes, truncated lines, and signal/broken-pipe behavior.

## 11. Observability

Because the tool is one-shot and local, observability means deterministic stderr diagnostics and measurable process behavior—not telemetry. Default successful execution is quiet except for the report. Malformed count appears in every output format. Benchmark scripts record wall time and peak RSS. There are no logs, metrics endpoints, tracing exporters, or outbound analytics.

## 12. Architecture Decision Record (ADR)

### ADR-001: Local single-process stream

- **Status:** Accepted and pre-approved.
- **Decision:** Use the one-process pipeline described above; retain only exact aggregate state.
- **Consequences:** Minimal installation and stdin compatibility; throughput is bounded to one process and exact cardinalities may dominate memory.
- **Revisit trigger:** A representative profiled parser misses the 30-second gate after evidence-backed optimization, or the exact-set memory gate fails.

### Debate summary

This section will record the required Devil's Advocate review verdict, its challenges, and their resolutions before the blueprint is finalized.

## 13. Cross-document traceability

Product priority and kill criteria are in `STRATEGIC_PLAN.md`; user-visible acceptance criteria and schemas are in `PRD.md`; delivery sequencing and verification commands are in `IMPLEMENTATION_PLAN.md`. If behavior changes, update those specifications before product code.
