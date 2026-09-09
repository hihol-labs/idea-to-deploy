# Project Architecture: nginx-insight

## 1. Context and Quality Attributes

The system is a Python 3.11 process that consumes nginx combined access-log records sequentially and emits one report. The load-bearing qualities are deterministic results, bounded and observable failure under adversarial cardinality, low setup cost, pipeline-safe output, and a measured target of processing a representative 1 GB log in under 30 seconds on a documented laptop baseline.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the product performs one-shot aggregation and promises no retained history; adding storage would increase I/O, setup, privacy exposure, and operational cost without serving a requirement. An HTTP API is incorrect because the users and inputs are local, shell composition is a required interface, and a resident server would add lifecycle, security, and deployment concerns. Authentication, cloud deployment, and Kubernetes are consequently not applicable.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** one process performs decode → parse → aggregate → render while retaining only counters, top-candidate maps, 24 hourly buckets, and an exact User-Agent set.
- **Pros:** simplest packaging and debugging, no IPC, natural stdin support, predictable order, fits one-weekend/$0 constraints.
- **Cons:** CPU work uses one core; exact unique-key state grows until the configured cap.
- **Best for:** the approved local CLI and representative logs that fit the cardinality policy.
- **Estimated complexity:** Low.

### Variant B: Unix pipeline of separate commands

- **Approach:** independent parser and metric commands exchange normalized records through pipes.
- **Pros:** individually composable stages and isolated experimentation.
- **Cons:** repeated serialization, fragile multi-process error propagation, harder single-command UX, and more packaging/test surface.
- **Best for:** a toolkit whose normalized event stream is itself a product.
- **Estimated complexity:** Medium.

### Variant C: Multiprocess chunk aggregation

- **Approach:** split seekable files into chunks, parse in workers, and merge partial aggregates.
- **Pros:** potential multicore throughput on large regular files.
- **Cons:** stdin/follow streams cannot be divided cleanly; chunk boundaries, IPC, merge memory, and deterministic failures complicate the MVP.
- **Best for:** a later release only if profiling proves parser CPU is the bottleneck.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the user pre-approved the obvious single-process architecture and it directly satisfies local streaming, $0 budget, pip installation, and one-weekend delivery. Variants B and C are documented as rejected alternatives, not pending decisions.

## 3. Component Model and Data Flow

```text
file path(s) / stdin
        |
        v
 InputReader (binary buffered iteration, source + line number)
        |
        v
 CombinedLogParser ---- invalid record ---> Diagnostics + invalid_count
        |
        v
 ParsedRecord dataclass
        |
        v
 AggregateState
   |-- IP request counts
   |-- error URL counts (status 400..599)
   |-- hourly buckets [0..23]
   `-- exact User-Agent set guarded by cardinality cap
        |
        v
 Report dataclasses ---> RichRenderer | JsonRenderer | CsvRenderer
```

The hot path processes a line once. It does not retain raw lines or parsed records. Aggregation maps are exact and therefore memory is `O(unique_ips + unique_error_urls + unique_user_agents)`, not strictly constant; the configurable shared cardinality guard makes exhaustion explicit. Twenty-four hourly counters are constant-space. Top 10 rows are selected at finalization with deterministic ordering: descending count, then ascending UTF-8 text.

## 4. Modules and Planned Files

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Python requirement, dependencies, console script, tool configuration |
| `src/nginx_insight/cli.py` | Click command, option validation, exception-to-exit mapping |
| `src/nginx_insight/models.py` | `ParsedRecord`, `Report`, and report-row dataclasses |
| `src/nginx_insight/parser.py` | Compiled combined-log grammar, timestamp/status extraction, parse errors |
| `src/nginx_insight/input.py` | Binary file/stdin iteration and decoding policy |
| `src/nginx_insight/aggregate.py` | Mutable `AggregateState`, cap enforcement, deterministic finalization |
| `src/nginx_insight/renderers/rich.py` | Human-readable Rich report |
| `src/nginx_insight/renderers/json.py` | Versioned JSON serialization |
| `src/nginx_insight/renderers/csv.py` | Normalized long-form CSV serialization |
| `src/nginx_insight/errors.py` | Typed operational, parse-quality, and cardinality errors |

This is a plan only; these files do not yet exist.

## CLI Interface

### Command

```text
nginx-insight [OPTIONS] [INPUTS]...
```

`INPUTS` accepts zero or more access-log paths. A missing input list or a single `-` reads stdin. `-` may not be combined with paths because ordering and repeated-stdin semantics would be ambiguous. Multiple paths are processed in argument order as one report. The MVP accepts uncompressed UTF-8/ASCII-compatible nginx combined-format logs; gzip is a Should feature.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | flag | Emit one CSV document; mutually exclusive with `--json` |
| `--no-color` | flag | Disable ANSI styling in terminal mode; no effect on JSON/CSV |
| `--max-unique INTEGER` | default `1000000` | Positive cap applied independently to IPs, error URLs, and User-Agents |
| `--encoding TEXT` | default `utf-8` | Input decoding; invalid byte sequences make that line malformed |
| `--version` | flag | Print version and exit 0 |
| `--help` | flag | Print help and exit 0 |

### Input grammar

The MVP parses nginx’s conventional combined log shape:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

The parser extracts client IP text, local timestamp including numeric offset, request target, integer status, and User-Agent. A request target is the raw request-target token between method and protocol; it is not URL-decoded. A missing/empty User-Agent represented by `"-"` is normalized to `null` and excluded from both the unique-UA numerator and the valid-UA denominator.

### Metric semantics

- **Top IPs:** up to 10 `(ip, request_count)` rows over valid records.
- **Top error URLs:** up to 10 `(url, error_count)` rows where status is 400–599 inclusive. Query strings remain part of the raw target.
- **Hourly request distribution:** 24 local-log-hour buckets. Each percentage is `100 × hourly_request_count / total_valid_requests`; if there are no valid records, every percentage is `0.0`.
- **Unique User-Agent share:** `100 × unique_non_missing_user_agents / valid_requests_with_non_missing_user_agent`, or `0.0` when the denominator is zero. The report includes numerator and denominator so the percentage is auditable.

Percentages are serialized as numbers rounded to six decimal places with the largest-remainder adjustment applied only to hourly display values so the 24 displayed percentages total exactly 100 when valid records exist. Raw hourly counts remain authoritative.

### Outputs

- Terminal mode writes four labeled Rich tables and a summary to stdout. Color is enabled only when stdout is a TTY and `--no-color` is absent.
- JSON writes UTF-8 with schema version `1`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `unique_user_agents`. Keys and types are fixed by [PRD.md](PRD.md).
- CSV writes one header and normalized rows with columns `schema_version,metric,rank,key,count,total,percentage`. Blank fields represent dimensions not applicable to that metric.
- Diagnostics always go to stderr and never corrupt JSON or CSV stdout.
- A cardinality failure emits no partial report to stdout, because exactness can no longer be guaranteed.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Complete successful report; no malformed records |
| `1` | Input/output operational failure, including unreadable input or broken output not caused by normal pipe closure |
| `2` | Click usage/configuration error, including conflicting format flags or non-positive cap |
| `3` | Partial-data report: at least one malformed record was skipped and at least one report was emitted |
| `4` | Unique-cardinality exhaustion: any protected exact set/map would exceed `--max-unique`; processing aborts without a report |

Normal downstream pipe closure is handled quietly according to Unix convention and does not print a traceback.

## 6. Domain Types and State

| Type | Fields |
|---|---|
| `ParsedRecord` | `ip: str`, `timestamp: datetime`, `request_target: str`, `status: int`, `user_agent: str | None` |
| `RankedCount` | `key: str`, `count: int`, `rank: int` |
| `HourlyBucket` | `hour: int`, `count: int`, `percentage: Decimal` |
| `UniqueUserAgentMetric` | `unique_count: int`, `observed_count: int`, `percentage: Decimal` |
| `Report` | `schema_version: int`, totals, ranked tuples, 24 hourly buckets, UA metric |
| `AggregateState` | mutable count maps, 24-element list, UA set, valid/invalid/UA-observed counters, cap |

Dataclasses form internal contracts. Renderers consume the immutable finalized `Report`, not the mutable aggregate.

## 7. Database, API, Authentication, and Deployment

### Database

No database and therefore no tables, migrations, indexes, credentials, or persistence lifecycle exist. The in-memory dataclasses and collections in Section 6 are runtime state, not a database. This deliberate exception to generic blueprint templates is required by the product constraint and justified in Section 1.

### HTTP API

No HTTP API and therefore no endpoints, request bodies, response bodies, listening ports, CORS, or API versioning exist. The complete public interface is the CLI contract above.

### Authentication

There is no authentication flow because the tool is a local process that reads only caller-authorized paths/stdin and performs no network operation. OS file permissions are the trust boundary.

### Deployment

The deployment artifact is a pure Python wheel and source distribution installable with pip into Python 3.11 environments. There is no Docker Compose configuration, container, resident service, staging environment, cloud resource, or Kubernetes manifest. Release verification installs the wheel into a clean virtual environment and invokes the console script.

### Environment variables

No product-specific environment variables are required. Locale and terminal capability may affect Rich presentation but not JSON/CSV data. All product configuration is explicit in CLI options for replayability.

## 8. Reliability, Security, and Privacy

- Files are opened read-only; the tool never mutates inputs.
- Log values are untrusted data and are escaped by Rich and serialized by standard JSON/CSV writers; they are never evaluated as format strings or shell commands.
- Paths and line numbers appear in diagnostics, but raw full log lines and User-Agent values do not, limiting accidental sensitive-data disclosure.
- Parser failures are recoverable per-line; I/O and cardinality failures are terminal.
- Ctrl-C returns the shell’s conventional interruption behavior without a Python traceback.
- No telemetry, network call, cache, or log persistence is permitted.
- Tests include ANSI/control characters, CSV/JSON injection-shaped values, huge lines, invalid bytes, boundary statuses, timestamps, and cap exhaustion.

## 9. Performance Plan

The reader uses buffered binary iteration; decoding and parsing happen once per line. The grammar is compiled once. Dataclasses are not constructed for invalid records and parsed records are consumed immediately. The implementation avoids global sorting: top rows use a bounded selection over aggregate maps, then deterministic sort of at most 10 results.

Benchmark gates:

1. Generate or retain a representative 1 GB combined-format fixture with documented cardinalities and hash.
2. Run the installed console entry point with stdout redirected, after one warm-up.
3. Record median of three wall-clock runs and peak RSS on named hardware/OS/Python.
4. Pass only when the median is under 30 seconds and results match a precomputed oracle.
5. Add a high-cardinality benchmark that must exit 4 at the configured cap rather than exhaust system memory.

## 10. Architecture Decision Records

### ADR-001: Single-process streaming core

- **Status:** Accepted (pre-approved).
- **Decision:** Variant A.
- **Consequences:** minimal operations and stdin support; no multicore scaling in MVP.

### ADR-002: Exact aggregation with an explicit cap

- **Status:** Accepted.
- **Decision:** preserve exact counts and unique User-Agents until a per-dimension cap, then fail with code 4.
- **Consequences:** results are auditable; worst-case high-cardinality input terminates rather than silently approximating.

### ADR-003: One finalized report, three renderers

- **Status:** Accepted.
- **Decision:** render Rich, JSON, and CSV from the same immutable report.
- **Consequences:** formats cannot drift in metric calculation; serialization contracts remain separately testable.

### ADR-004: No inline adversarial review in this session

- **Status:** Process constraint.
- **Decision:** the external harness will run the real Devil’s Advocate agent in a fresh session; this blueprint neither performs nor substitutes that review.

## 11. Traceability

Product behavior and acceptance criteria live in [PRD.md](PRD.md); delivery sequencing and file-level checks live in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md); implementation-session constraints live in [CLAUDE.md](CLAUDE.md).
