# Project Architecture: nginx-log-insights

## Architecture Goals

- Process a representative 1 GB nginx access log in under 30 seconds on a documented laptop.
- Consume regular files and stdin incrementally; never load the complete log into memory.
- Produce deterministic, equivalent metrics in terminal, JSON, and CSV forms.
- Stay locally installable with pip and require no external runtime service.
- Fail explicitly on invalid invocation, I/O/runtime problems, unacceptable parse quality, and unsafe unique cardinality.

## Constraints and Core Decision

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add installation, schema, persistence, privacy, cleanup, and I/O overhead while the product only promises a point-in-time aggregate from one stream. An HTTP API would introduce a server lifecycle, authentication question, network attack surface, serialization hop, and deployment burden without improving the intended local shell workflow. Streaming local input directly to bounded in-process aggregates is the shortest path to the latency, privacy, $0-budget, and one-weekend goals.

Also excluded are authentication, cloud services, Kubernetes, background workers, and telemetry. The operating-system user and filesystem permissions are the trust boundary.

## Architecture Decision

### Selected: single-process layered CLI

One Python process owns input, parsing, aggregation, and rendering. Dependencies point inward: Click adapts command-line input, the parser emits domain records, the aggregator updates result state, and one selected renderer serializes the final snapshot.

```text
file path or stdin
       |
       v
 buffered text iterator -> combined-log parser -> streaming aggregator
                                |                      |
                                v                      v
                         parse counters        final Report dataclass
                                                       |
                                      +----------------+---------------+
                                      v                v               v
                                Rich terminal         JSON             CSV
```

This is the obvious architecture for a solo, one-weekend CLI and therefore does not need artificial database, API, microservice, or deployment variants.

### Alternatives considered and rejected

| Alternative | Why rejected |
|---|---|
| Multiprocessing parser | Coordination, serialization, chunk-boundary, and merge complexity are premature until a benchmark proves a single optimized process insufficient |
| SQLite temporary aggregation | Violates the no-database decision and adds disk I/O and cleanup |
| Approximate heavy-hitter sketch | Changes the meaning of “top 10”; exact counts are preferred until representative cardinality proves infeasible |
| Service-based ingestion | Violates CLI-only/local requirements and adds operations, auth, and cost |

## Component Boundaries

Planned paths are implementation targets, not files created by this blueprint.

| Component | Planned path | Responsibility | Must not do |
|---|---|---|---|
| CLI adapter | `src/nginx_log_insights/cli.py` | Click command, options, streams, renderer selection, exception-to-exit mapping | Parse log grammar or calculate metrics |
| Parser | `src/nginx_log_insights/parser.py` | Convert a supported line into a typed record or structured parse failure | Read files, print, or terminate the process |
| Domain models | `src/nginx_log_insights/models.py` | Frozen parsed-record and report dataclasses | Import Click or Rich |
| Aggregator | `src/nginx_log_insights/aggregate.py` | Update counters, enforce cardinality ceiling, finalize derived percentages and top lists | Format output |
| Terminal renderer | `src/nginx_log_insights/renderers/terminal.py` | Rich tables and warnings | Change metric values |
| JSON renderer | `src/nginx_log_insights/renderers/json.py` | Stable JSON document | Emit ANSI or diagnostics to stdout |
| CSV renderer | `src/nginx_log_insights/renderers/csv.py` | Stable normalized row stream | Emit ANSI or diagnostics to stdout |
| Error types | `src/nginx_log_insights/errors.py` | Named domain exceptions mapped to exit codes | Catch unrelated programmer errors silently |

## Data Model and Streaming State

There are no database tables, migrations, persisted cache files, or hidden state. The only in-memory domain types are:

| Dataclass/state | Fields | Meaning |
|---|---|---|
| `AccessRecord` | `remote_addr: str`, `timestamp: datetime`, `method: str`, `target: str`, `status: int`, `user_agent: str` | Valid subset of one nginx combined-log line needed by P0 metrics |
| `ParseStats` | `total_lines: int`, `valid_lines: int`, `malformed_lines: int` | Input-quality accounting |
| `AggregateState` | `ip_counts: Counter[str]`, `error_url_counts: Counter[str]`, `hour_counts: list[int]`, `user_agents: set[str]`, `stats: ParseStats`, `unique_value_count: int` | Mutable one-pass state; no raw records retained |
| `RankedCount` | `key: str`, `count: int`, `rank: int` | Deterministic top-list entry |
| `HourlyBucket` | `hour: int`, `count: int`, `percentage: float` | One of 24 hourly buckets |
| `Report` | `schema_version: str`, `source: str`, `stats: ParseStats`, `top_ips: tuple[RankedCount, ...]`, `top_error_urls: tuple[RankedCount, ...]`, `hourly: tuple[HourlyBucket, ...]`, `unique_user_agents: int`, `unique_user_agent_share: float` | Renderer-neutral result |

`unique_value_count` counts first-seen keys across the IP map, error-URL map, and User-Agent set. Before inserting a new key, the aggregator compares the count to `--max-unique-values`; reaching the ceiling raises a cardinality exception and yields exit code 4. This makes memory failure explicit. Empty User-Agent values represented as `"-"` are treated as missing and excluded from the unique set.

Top lists use exact counters, sort by descending count, then ascending key for deterministic ties, and take ten entries. Error URLs include only statuses 400–599. The target is the request-target token exactly as logged, including its query string; decoding or URL normalization is out of scope for MVP.

Hours are the `00`–`23` hour component in each valid line’s explicit nginx timestamp offset. No cross-timezone normalization is performed in MVP. Every valid request contributes to exactly one bucket. Each bucket percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`; if there are no valid requests, parsing fails with exit code 3 instead of dividing by zero.

Unique User-Agent share is `100 × unique_nonempty_user_agent_count / total_valid_requests`, expressed as a percentage with two decimal places in presentation formats. It measures diversity relative to requests, not the share of requests whose User-Agent is non-empty.

## Input and Parsing Contract

MVP accepts UTF-8 nginx combined-log text, one record per line, with replacement disabled: undecodable input is an I/O/runtime error. The parser extracts remote address, timestamp with numeric offset, request method and target, status, and quoted User-Agent. Referer and byte count are syntactically consumed but not retained. IPv4, IPv6, and non-IP tokens are accepted as the `remote_addr` token because nginx may log upstream-provided identifiers; semantic validation is not needed for counting.

Malformed lines are counted and skipped by default. `--strict` stops at the first malformed line and returns code 3. Without `--strict`, processing returns code 3 if no valid records exist; otherwise it completes, emits malformed counts in all output modes, and returns 0. Diagnostics go to stderr only.

Input is opened with a large buffered reader and iterated line-by-line. Standard input is never closed by the application. A regular file read failure or broken output pipe maps to code 1, with broken-pipe diagnostics suppressed where conventional shell behavior requires it.

## CLI Interface

### Command

```text
nginx-log-insights [OPTIONS] INPUT
```

`INPUT` is a path to one regular text file or `-` for stdin. Directories and multiple input paths are rejected. Live use is composed through `tail -F /var/log/nginx/access.log | nginx-log-insights -`.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | off | Emit one JSON document to stdout; mutually exclusive with `--csv` |
| `--csv` | off | Emit normalized CSV rows to stdout; mutually exclusive with `--json` |
| `--strict` | off | Stop at first malformed line and exit 3 |
| `--max-unique-values INTEGER` | `2000000` | Positive ceiling across first-seen IP, error-URL, and User-Agent keys; exhaustion exits 4 |
| `--no-color` | off | Disable color in terminal mode; has no effect on JSON/CSV |
| `--version` | — | Print version and exit 0 |
| `--help` | — | Print usage and exit 0 |

### Inputs

- UTF-8 nginx combined access-log lines from `INPUT` or stdin.
- No network URLs, glob expansion, compressed-file decoding, configuration file, environment-variable configuration, or database input in P0.

### Outputs

- Default: four Rich sections plus valid/malformed totals. Color is enabled only when appropriate for the output terminal and not when `--no-color` is set.
- JSON: UTF-8 object with `schema_version`, `source`, `stats`, `top_ips`, `top_error_urls`, `hourly`, and `user_agents` members. Ranked arrays contain at most ten entries; `hourly` always contains 24 ordered buckets.
- CSV: header `metric,rank,key,count,percentage`; rows use metric names `top_ip`, `top_error_url`, `hourly_request`, and `unique_user_agents`. Inapplicable cells are empty, and the final User-Agent row carries its unique count and share.
- stdout contains only the selected result format. Human diagnostics and parse warnings go to stderr.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Successful report, including a non-strict report with at least one valid record and declared malformed records |
| `1` | Runtime or I/O failure, including unreadable input or output failure |
| `2` | Click usage error, invalid option combination, invalid ceiling, or invalid input argument |
| `3` | Parse-quality failure: strict-mode malformed line or zero valid records |
| `4` | Unique-cardinality exhaustion before another distinct aggregate key can be retained |

The `0/1/2/3/4` contract is stable across terminal, JSON, and CSV modes.

## Output Schemas and Numerical Rules

JSON numbers remain numbers; percentages are rounded only when serialized to two decimal places using round-half-even consistently. Counts remain integers. JSON keys and CSV rows are emitted in the documented order for reproducibility, although consumers must identify JSON members by name.

The JSON `schema_version` starts at `1`. Backward-incompatible field changes require a version increment and PRD update. CSV keeps its five-column normalized schema for version 1. Empty top lists still emit no ranked rows; all 24 hourly rows are emitted when a successful report exists.

## Error and Resource Handling

Domain exceptions are translated once at the CLI boundary. The parser returns structured failures rather than printing. Tracebacks are hidden for expected user/input failures and remain available only during development tests. Each renderer accepts the immutable `Report`; it cannot observe mutable counters.

The input is streaming, but exact aggregation is proportional to unique values rather than file size. The configured ceiling converts that fact into a bounded contract. A benchmark must record elapsed wall time and peak RSS; “streaming” alone is not accepted as evidence of the performance target.

## Security and Privacy

- All processing is local and no telemetry or network call exists.
- Log contents are untrusted data, never evaluated as code or terminal markup.
- Rich text created from log values must escape markup and control characters.
- CSV cells use the standard library writer; spreadsheet-formula neutralization is not promised because URLs and User-Agents are data exports, so README warns consumers opening untrusted CSV in spreadsheet software.
- Error messages avoid echoing full log lines by default; line numbers and short reasons are sufficient.
- Files are opened read-only; symlink behavior follows the invoking user’s operating-system permissions.

## Packaging and Deployment

Deployment means installing a Python wheel into a local environment with pip. Planned package metadata lives in `pyproject.toml`, exposes the `nginx-log-insights` console script, declares Python `>=3.11`, and pins compatible major versions of Click and Rich. Source distributions and wheels are built locally; no container, Docker Compose, service manager, cloud target, or Kubernetes manifest is part of the product.

There are no runtime environment variables. This absence is intentional: every behavior-changing input is visible in the command invocation. Development tooling may use conventional tool-specific variables, but they are not product contracts.

## Testing and Performance Architecture

| Layer | Planned evidence |
|---|---|
| Parser unit tests | Valid IPv4/IPv6, escaping, timestamps, 4xx/5xx, malformed and undecodable input |
| Aggregator unit tests | Ties, fewer than ten values, 24-hour math, User-Agent exclusions, ceiling boundary |
| CLI integration tests | File/stdin parity, mutually exclusive formats, stderr separation, every exit code |
| Renderer golden tests | Stable terminal structure without ANSI, JSON schema, CSV schema and quoting |
| Property tests (optional) | Accounting invariant: `total_lines = valid_lines + malformed_lines` |
| Performance test | Generated representative 1 GB file, median of three runs, wall time under 30 seconds and peak RSS at most 512 MiB |

The benchmark fixture shape, hardware, operating system, Python patch version, and command must be recorded so the target is reproducible rather than anecdotal.

## Architecture Decision Record

### ADR-001: single-process exact streaming aggregation

- **Status:** Accepted from the pre-approved product brief.
- **Decision:** Use one Python process with a line parser, exact in-memory counters, an explicit unique-value ceiling, and renderer adapters.
- **Consequences:** Minimal setup and deterministic exact results; memory scales with distinct values and therefore must be guarded and benchmarked.

### ADR-002: no persistence or network interface

- **Status:** Accepted from the pre-approved product brief.
- **Decision:** Use local files/stdin and stdout/stderr only.
- **Consequences:** Zero operational cost and strong local privacy; no historical query, collaboration, remote ingestion, or dashboard.

### ADR-003: one supported grammar in P0

- **Status:** Accepted for the weekend scope.
- **Decision:** Parse nginx combined format exactly and expose parse accounting.
- **Consequences:** Fast, testable MVP; custom `log_format` support is P1 and must extend the input contract deliberately.

## Related Documents

Business priorities are in `STRATEGIC_PLAN.md`, behavior and acceptance criteria in `PRD.md`, and dependency-ordered delivery in `IMPLEMENTATION_PLAN.md`.
