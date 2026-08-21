# Project Architecture: Nginx Stream Analytics CLI

## 1. Context and Goals

The product is a local Python 3.11 process that transforms an nginx combined-format byte stream into four summaries. The architectural priorities are correctness, deterministic pipeline output, bounded operational behavior, installability, and a measured target of processing 1 GB in under 30 seconds on a reference laptop.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the requested outputs are aggregates over one invocation and retaining raw or derived logs would add I/O, schema, privacy, cleanup, and operational costs without product value. An HTTP API is incorrect because the users already work in terminals and pipelines; a server would add lifecycle, networking, authentication, concurrency, and deployment burdens to a local one-shot analysis task.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** Click invokes a reader/parser/aggregator pipeline and a selected renderer in one Python process.
- **Pros:** One pass, no IPC or serialization overhead, simple packaging, deterministic lifecycle, easiest profiling.
- **Cons:** CPU work uses one core; exact unique cardinality needs a guarded in-memory set.
- **Best for:** The approved one-weekend, local 1 GB workload.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunk parsing

- **Approach:** Split seekable files into byte ranges, parse in workers, and merge partial aggregates.
- **Pros:** Can use multiple CPU cores on large regular files.
- **Cons:** Does not fit stdin naturally; chunk-boundary correctness, IPC, set merging, and startup overhead threaten the weekend scope.
- **Best for:** A later version after profiling proves CPU-bound parsing misses the target.
- **Estimated complexity:** Medium.

### Variant C: External Unix-tool composition

- **Approach:** Orchestrate `awk`, `sort`, `uniq`, and related commands.
- **Pros:** Strong native throughput and low Python implementation effort.
- **Cons:** Platform-dependent behavior, multiple scans/sorts, fragile parsing, and no coherent cross-platform package contract.
- **Best for:** Ad hoc operator scripts, not this installable product.
- **Estimated complexity:** Low implementation, high portability risk.

### Recommendation

Variant A is selected because the user pre-approved the obvious single-process architecture, stdin is a first-class input, and the target should first be met by a profiled one-pass design. Variant B is a contingency only if measured evidence shows parsing is CPU-bound after hot-path optimization.

No adversarial or independent review is recorded in this document; that review is intentionally outside this session.

## 3. Component Model

```text
Click CLI
  ├── input opener (path or stdin)
  ├── combined-log parser -> ParsedRecord dataclass | MalformedRecord
  ├── streaming aggregator
  │     ├── IP Counter
  │     ├── error-URL Counter (status 400..599)
  │     ├── 24-bin hourly Counter
  │     └── exact User-Agent set + cardinality guard
  └── renderer: Rich terminal | JSON | normalized CSV
```

Planned package layout:

```text
pyproject.toml
src/nginx_stream_analytics/
  __init__.py
  cli.py
  models.py
  parser.py
  aggregate.py
  errors.py
  renderers/
    __init__.py
    terminal.py
    json_output.py
    csv_output.py
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_cli.py
  test_performance.py
```

Responsibilities do not overlap: parsing owns syntax and time-zone-aware timestamp extraction; aggregation owns metric inclusion and counting; renderers receive one immutable result object and never recompute metrics; `cli.py` owns I/O selection and error-to-exit mapping.

## 4. Data Contracts

### Supported input

- One nginx **combined log format** record per line:
  `remote_addr - remote_user [time_local] "request" status body_bytes_sent "http_referer" "http_user_agent"`.
- UTF-8 decoding uses `errors="replace"` for textual fields so a single invalid byte does not terminate a large scan.
- Input comes from one positional `INPUT` path or `-`/omitted input for stdin. Regular and named streams are read incrementally; no whole-file read is allowed.
- A valid record must contain a parseable timestamp/hour, integer status in `100..599`, request target, client IP token, and User-Agent field. A malformed line is counted and skipped.
- The request target is the second token of the quoted request line. If the request is `-` or lacks a target, the record is malformed.
- All valid requests contribute to IP, hour, and User-Agent metrics. Only statuses `400..599` contribute to error-URL counts.

### In-memory domain models

| Dataclass | Field | Type | Constraint |
|---|---|---|---|
| `ParsedRecord` | `client_ip` | `str` | Non-empty token; IPv4/IPv6 preserved as logged |
| `ParsedRecord` | `hour` | `int` | `0..23`, taken from nginx `time_local` without UTC conversion |
| `ParsedRecord` | `request_target` | `str` | Non-empty request target, including query string as logged |
| `ParsedRecord` | `status` | `int` | `100..599` |
| `ParsedRecord` | `user_agent` | `str` | Exact decoded field; `-` is a legitimate distinct value |
| `AnalysisResult` | `total_lines` | `int` | Non-negative |
| `AnalysisResult` | `valid_requests` | `int` | Non-negative and ≤ total lines |
| `AnalysisResult` | `malformed_lines` | `int` | `total_lines - valid_requests` |
| `AnalysisResult` | `top_ips` | `tuple[RankedItem, ...]` | At most 10, sorted by count desc then key asc |
| `AnalysisResult` | `top_error_urls` | `tuple[RankedItem, ...]` | At most 10, same deterministic tie-break |
| `AnalysisResult` | `hourly_distribution` | `tuple[HourlyItem, ...]` | Exactly 24 entries when valid requests exist |
| `AnalysisResult` | `unique_user_agents` | `int` | Exact set cardinality |
| `AnalysisResult` | `unique_user_agent_share_pct` | `float` | `100 × unique_user_agents / total_valid_requests` |

Hourly request distribution is a percentage for each local log hour using the literal formula `100 × hourly_request_count / total_valid_requests`. Counts and percentages are both exposed; percentages use full precision internally and render to two decimals only in human output.

“Share of unique User-Agents” means `100 × unique_user_agents / total_valid_requests`. This can exceed neither 100% nor the number of valid requests because each valid request supplies exactly one User-Agent value. It is not the share of traffic belonging to agents seen once.

### Persistence and database decision

There are no database tables, schemas, migrations, indexes, caches, or persistent application records. Counters and the User-Agent set live only for the invocation and are released at process exit. The template’s database-table inventory is therefore intentionally empty rather than underspecified.

### API decision

There are no HTTP, REST, GraphQL, gRPC, or internal network endpoints; consequently there are no request/response bodies, ports, CORS rules, or API versioning. The complete public interface is the CLI contract below.

## CLI Interface

### Commands

```text
nginx-stream-analytics [OPTIONS] [INPUT]
nginx-stream-analytics --help
nginx-stream-analytics --version
```

`INPUT` is a path to a readable log. If omitted or equal to `-`, bytes are read from stdin. Exactly one input stream is analyzed per invocation.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one JSON object; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit normalized CSV; mutually exclusive with `--json` |
| `--color / --no-color` | auto | Override terminal color; rejected as irrelevant with JSON/CSV if explicitly enabled |
| `--max-unique-user-agents INTEGER` | `1_000_000` | Positive exact-cardinality ceiling; crossing it exits `4` without a partial report |
| `--version` | flag | Print version and exit `0` |
| `--help` | flag | Print usage and exit `0` |

The top-N value is fixed at 10 in the MVP. Options may occur before or after `INPUT` according to Click parsing.

### Outputs

- **Terminal:** four labeled Rich tables plus a scan summary. Color is enabled only for a TTY unless forced. Diagnostics go to stderr.
- **JSON:** one UTF-8 object with `schema_version`, `source`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`. Ranked entries include `rank`, key, `count`, and `share_pct`. Hours are strings `00` through `23`.
- **CSV:** UTF-8 with header `schema_version,metric,rank,key,count,share_pct`. Rows use metrics `top_ip`, `error_url`, `hour`, and `unique_user_agents`; absent ranks are empty. All 24 hourly rows are emitted. RFC 4180 quoting is handled by Python’s `csv` module.
- Successful JSON/CSV stdout contains no progress text, Rich markup, or ANSI escape sequences.
- For equal counts, ranked output sorts lexicographically by raw decoded key after descending count, giving repeatable output.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Success, including help/version and a report with at least one valid record |
| `1` | Unexpected internal error; concise diagnostic on stderr |
| `2` | CLI usage error, invalid option combination, invalid limit, or unreadable/missing input |
| `3` | Input/data error: stream has no valid records (empty or all malformed); diagnostic includes counts |
| `4` | Unique-cardinality exhaustion: distinct User-Agents exceed `--max-unique-user-agents`; no partial report |

Mixed valid and malformed records produce a report and exit `0`, with malformed counts in output and a warning on terminal stderr. Broken-pipe handling exits cleanly without a traceback and follows the platform convention as documented during implementation; it must not be remapped to a successful complete analysis.

## 6. Streaming and Performance Design

- Open the input in binary mode with a large buffered reader and iterate line by line.
- Compile the parser expression once. Avoid constructing dictionaries and datetime objects per record; extract only the five required fields and hour.
- Maintain integer counters for IPs, error URLs, and 24 hours. Final `Counter.most_common` output is re-sorted for deterministic ties.
- Maintain an exact `set[str]` for User-Agents. Check cardinality immediately after insertion; if the configured ceiling is crossed, discard results and raise the domain error mapped to code `4`.
- Do not render progress or rows during parsing. Create `AnalysisResult` once at EOF.
- Memory is O(distinct IPs + distinct error URLs + distinct User-Agents), not O(lines). The cardinality guard bounds the most adversarial required exact set, while benchmark fixtures validate realistic IP/URL cardinality.
- Performance acceptance uses a generated 1 GB combined-log fixture, `/usr/bin/time` elapsed/RSS capture, three timed runs after one warm-up, and the median elapsed time. The reference laptop CPU, RAM, OS, Python patch release, input storage, and fixture generator seed are recorded.

## 7. Error Handling and Security Boundaries

- Input is untrusted data, never a format string, shell argument, or instruction.
- The process never invokes a shell and never resolves URLs from log content.
- Rich escapes untrusted terminal values; CSV and JSON use standard encoders. Spreadsheet formula injection is documented for CSV consumers; cells beginning with formula sigils are prefixed with a single quote in CSV only while JSON preserves raw values.
- File errors are converted to code `2`; malformed record syntax is accounted for; impossible invariant failures become code `1`.
- Tracebacks are suppressed by default and may be made available only through a future explicit debug option.
- No log contents, identifiers, or usage telemetry leave the machine.

## 8. Packaging, Configuration, and Deployment

- `pyproject.toml` declares Python `>=3.11,<4`, Click, Rich, package metadata, and the `nginx-stream-analytics` console script.
- Installation target is any local Python 3.11 virtual environment via pip. A wheel and source distribution are the deployment artifacts.
- Docker, docker-compose, Kubernetes, cloud services, and long-running process managers are intentionally absent.
- There are no required environment variables or `.env` file. Locale and terminal capability may influence Rich presentation but never JSON/CSV schemas or metric values.
- Runtime configuration is exclusively through the CLI options documented above.

## 9. Testing Strategy

| Layer | Evidence |
|---|---|
| Parser unit tests | IPv4, IPv6, escaping, query strings, all status classes, malformed/truncated lines, invalid bytes |
| Aggregation unit tests | Inclusion rules, top-10 cutoff, deterministic ties, all 24 hours, exact UA share, guard exhaustion |
| Renderer snapshot/schema tests | No ANSI in machine formats, valid JSON, parseable normalized CSV, stable keys |
| Click integration tests | File/stdin parity, mutual exclusion, unreadable files, and exit codes `0/1/2/3/4` |
| End-to-end golden fixture | Hand-calculated counts and percentages across all reports |
| Performance test | Generated 1 GB fixture under 30 seconds on documented reference laptop |

## 10. Architecture Decision Record (ADR)

### ADR-001: One process and one pass

- **Status:** Accepted by pre-approved product decision.
- **Decision:** Use Variant A, with no intermediate records written to disk.
- **Consequences:** Simple stdin behavior and packaging; single-core performance must be benchmarked.

### ADR-002: Exact User-Agent cardinality with explicit exhaustion

- **Status:** Accepted.
- **Decision:** Store exact distinct User-Agent strings up to a configurable ceiling and exit `4` if exceeded.
- **Consequences:** The reported share is exact whenever a report is emitted; adversarial cardinality cannot silently exhaust memory or degrade into an unlabeled estimate.

### ADR-003: Stable normalized CSV

- **Status:** Accepted.
- **Decision:** Use one long-form CSV schema rather than four incompatible tables.
- **Consequences:** Pipelines can stream one header/schema; consumers select rows by `metric`.

### Alternatives considered and rejected

- Persistent SQLite/PostgreSQL — rejected because no cross-run query or retention requirement exists.
- HTTP service — rejected because it expands security and operations without helping local analysis.
- Approximate HyperLogLog for User-Agents — rejected for MVP because the requirement is expressed as an exact share and approximation would change semantics.
- Multiprocessing — deferred until benchmark evidence demonstrates need.

