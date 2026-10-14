# Project Architecture: Nginx Stream Analyzer

## 1. Context and Constraints

The product is an installable Python 3.11 process that consumes one nginx access-log stream, aggregates four summaries, renders once, and exits. The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. Input is already an append-oriented file or stdin stream, the requested output is a one-shot aggregate, and retention/query capabilities would add state, migration, privacy, and operations without serving the incident-time workflow. Likewise, callers are humans and shell pipelines on the same machine; an HTTP API would require a server lifecycle, authentication and network threat model while adding no necessary capability. Authentication, cloud, containers, and Kubernetes are therefore absent, not deferred dependencies.

Non-functional constraints: local execution, $0 infrastructure, one-weekend delivery, pip installation, one sequential pass, and 1 GB in under 30 seconds on the recorded benchmark laptop.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** Click validates input/options; a streaming reader yields parsed dataclasses; one aggregator owns counters; a selected renderer emits terminal, JSON, or CSV output.
- **Pros:** minimal copying, deterministic lifecycle, easy profiling, no operational dependencies.
- **Cons:** one machine/process; exact unique cardinality requires bounded memory policy.
- **Best for:** local one-shot analysis up to and beyond the stated 1 GB target.
- **Estimated complexity:** Low.

### Variant B: Unix-stage subprocess pipeline

- **Approach:** separate parser, metric, and renderer processes communicate through pipes.
- **Pros:** stages can be recombined and independently scaled.
- **Cons:** serialization and process overhead, harder error propagation, packaging complexity.
- **Best for:** a future toolkit of interchangeable transforms.
- **Estimated complexity:** Medium.

### Variant C: Embedded analytical database

- **Approach:** load records into a temporary SQLite/DuckDB database and query aggregates.
- **Pros:** flexible ad hoc queries and mature SQL aggregation.
- **Cons:** violates stateless streaming intent, adds disk I/O/dependency, expands privacy and cleanup concerns.
- **Best for:** exploratory multi-query sessions, which are out of scope.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the architecture choice is pre-approved and it uniquely matches the one-process, one-pass, local CLI constraints. Variants B and C add mechanisms without improving the four fixed reports.

## 3. Component Model

```text
file path / stdin
       |
       v
 Click CLI + option validation
       |
       v
 streaming text reader -> nginx parser -> RequestRecord dataclass
                                           |
                                           v
                              StreamingAggregator
                              - total/valid/skipped
                              - IP Counter
                              - error-URL Counter
                              - 24 hourly buckets
                              - bounded UA set
                                           |
                                           v
                                  Report dataclasses
                                           |
                     +---------------------+--------------------+
                     v                     v                    v
               Rich renderer          JSON renderer       CSV renderer
```

Only normalized fields required for aggregation cross the parser boundary: client IP, timestamp/hour, request target, status, and User-Agent. Raw lines are not retained.

## 4. Modules and Data Contracts

| Path | Responsibility | Principal contract |
|---|---|---|
| `src/nginx_stream_analyzer/cli.py` | Click command, input ownership, renderer selection, exit mapping | `main()` / console script |
| `src/nginx_stream_analyzer/models.py` | Immutable parsed and result dataclasses | `RequestRecord`, `RankedValue`, `Report` |
| `src/nginx_stream_analyzer/parser.py` | Supported combined-log grammar and timestamp decoding | `parse_line(str) -> RequestRecord` or parse error |
| `src/nginx_stream_analyzer/aggregate.py` | Single-pass counters and cardinality ceiling | `StreamingAggregator.consume(record)` and `.report()` |
| `src/nginx_stream_analyzer/renderers/terminal.py` | Colored Rich report | write report to stdout |
| `src/nginx_stream_analyzer/renderers/json.py` | Versioned JSON object | write one JSON document |
| `src/nginx_stream_analyzer/renderers/csv.py` | Normalized CSV rows | write header plus metric rows |
| `src/nginx_stream_analyzer/errors.py` | Domain errors and exit-code mapping | typed failure classes |

Conceptual dataclasses:

| Dataclass | Fields |
|---|---|
| `RequestRecord` | `client_ip: str`, `timestamp: datetime`, `url: str`, `status: int`, `user_agent: str` |
| `RankedValue` | `rank: int`, `key: str`, `count: int` |
| `HourlyShare` | `hour: int`, `request_count: int`, `percentage: float` |
| `Report` | schema version; line totals; top IPs; error URLs; 24 hourly shares; unique UA count/share |

Database schema: none. There are zero tables, migrations, indexes, or persistent records. API schema: none. There are zero HTTP endpoints or request/response bodies. Auth flow: none because no identity boundary exists. Deployment target: a local Python 3.11 environment installed through pip. Docker and `docker-compose` are intentionally excluded; they would slow the under-30-second quick start and do not improve reproducibility beyond a locked Python package.

## 5. Streaming and Aggregation Semantics

Each physical input line is read once. A valid supported-format line increments `total_valid_requests`; an invalid nonempty line increments `skipped_lines`. An input with at least one valid line produces a report and may mention skips on stderr; an input with no valid requests is a data error.

- Top IPs rank descending by valid request count, then ascending by IP string for deterministic ties.
- Error URLs include status 400–599, rank descending by error count, then ascending by URL.
- Hour is derived from each record's nginx timestamp and numeric UTC offset; buckets are local log hours `00` through `23`.
- Hourly request distribution is a percentage: `100 × hourly_request_count / total_valid_requests`. If there are no valid requests, no distribution is emitted and exit code 3 applies.
- Unique User-Agent share means `100 × unique_nonempty_user_agent_count / total_valid_requests`. The exact set is bounded by a configurable cardinality ceiling; exceeding it fails closed with exit code 4 rather than returning an approximation mislabeled as exact.
- Missing/empty User-Agent values do not enter the unique set but their requests remain in the denominator.

Counters grow with distinct IP/URL values, not line count. The 24 hourly buckets are constant-size. The exact User-Agent set is bounded by the ceiling. The CLI releases all state when the process exits.

## CLI Interface

### Commands and Inputs

The installed command is `nginx-stream-analyzer [OPTIONS] [INPUT]`. `INPUT` is a local nginx access-log path; omit it or pass `-` to read UTF-8 text from stdin. Exactly one input stream is processed. Compressed input is not a P0 promise; users can pipe `gzip -dc` into stdin.

### Options

| Option | Meaning | Default/constraint |
|---|---|---|
| `--json` | Emit one JSON document | Mutually exclusive with `--csv` |
| `--csv` | Emit normalized CSV | Mutually exclusive with `--json` |
| `--no-color` | Disable terminal styling | Relevant only to terminal mode; auto-disabled when stdout is not a TTY |
| `--ua-limit INTEGER` | Maximum exact unique User-Agents | Positive integer; documented safe default `1_000_000` |
| `--encoding TEXT` | Input text encoding | `utf-8`; decoding failures are data errors |
| `--version` | Print version and exit | No input opened |
| `--help` | Print command help and exit | No input opened |

### Outputs

Default stdout is a colored Rich report with input counts and four sections. JSON stdout is a single object with `schema_version`, `counts`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`; numeric percentages remain numbers. CSV stdout has the fixed columns `metric,rank,key,count,percentage,unit`, allowing heterogeneous results without multiple files. Diagnostics go only to stderr. No mode logs progress to stdout.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Successful report (including input with some skipped malformed lines) |
| `1` | Operational I/O failure, including missing/unreadable input or write failure other than a normal closed pipe |
| `2` | CLI usage/configuration error, including conflicting format flags or invalid `--ua-limit` |
| `3` | Input/data failure: decoding failure or zero valid requests |
| `4` | Unique-cardinality exhaustion: exact User-Agent count exceeded `--ua-limit` |

Click-owned usage errors must be normalized to code 2. A downstream consumer closing a pipe after receiving enough output is treated as a quiet successful termination when safely identifiable; other output failures map to 1.

Examples:

```bash
nginx-stream-analyzer /var/log/nginx/access.log
gzip -dc access.log.gz | nginx-stream-analyzer --json -
nginx-stream-analyzer --csv access.log > report.csv
```

## 7. Output Schemas

JSON arrays are sorted exactly as displayed; hourly entries always contain all 24 hours. The schema version begins at `1`. Counts are integers and percentages are rounded for display only after calculation, to two decimal places. CSV emits one `summary` row for total/valid/skipped values, ranked `top_ip` and `error_url` rows, 24 `hour` rows, and one `user_agent_share` row. Tests use golden fixtures for all three modes.

## 8. Performance and Resource Design

- Use buffered sequential text I/O and compile the parser once.
- Avoid intermediate per-line dictionaries, retaining `RequestRecord` only for one consume call.
- Keep Rich entirely after aggregation.
- Use `collections.Counter.most_common(10)` only at finalization; profile distinct-key behavior.
- Benchmark from the installed console script against a deterministic 1 GB fixture, recording wall time, peak RSS, Python version, OS, CPU, storage, and warm/cold cache status.
- The acceptance budget is under 30 seconds on the designated laptop and a documented peak-memory ceiling; failure triggers profiling before feature expansion.

## 9. Security, Privacy, and Failure Boundaries

Logs are untrusted data, never commands. The implementation opens only the user-selected input, does not follow URLs, executes no subprocess, performs no network I/O, and emits no telemetry. It does not print raw malformed lines by default because URLs and User-Agents may contain secrets. Terminal content is escaped/sanitized to prevent control-sequence injection. File handles are closed by their owner, and partial output is not presented as a successful report after a renderer error.

Dependencies are minimal and pinned for release builds. Since there is no database, API, auth, server, cloud, or container, those attack surfaces and configuration variables do not exist. The MVP defines no environment variables; behavior is controlled by explicit CLI options.

## 10. Testing Strategy

Unit tests cover valid/invalid grammar, status boundaries, timezone/hour extraction, ties, percentage denominators, missing User-Agents, output escaping, cardinality exhaustion, and exit mapping. Integration tests invoke the installed command for file/stdin and each renderer. Golden output tests lock JSON/CSV schemas and color-disabled terminal structure. A generated benchmark fixture covers the performance target without committing a 1 GB file.

## 11. Architecture Decision Record (ADR)

### ADR-001: Local single-process stream

- **Status:** Accepted by the supplied product brief.
- **Decision:** Use Variant A with Python 3.11, Click, Rich, and dataclasses.
- **Consequences:** Simple local installation and lifecycle; no cross-run queries; exact high-cardinality state needs a hard ceiling.
- **Rejected:** subprocess stages, embedded database, service/API architectures.

### ADR-002: Exact bounded User-Agent cardinality

- **Status:** Accepted.
- **Decision:** Track exact unique nonempty User-Agent strings until `--ua-limit`; then terminate with code 4.
- **Consequences:** Honest semantics and bounded risk, at the cost of rejecting pathological cardinality rather than estimating it.

### Review provenance

No Devil's Advocate or independent adversarial review was run in this session, by explicit benchmark instruction. That external review is intentionally left to the harness; this document does not claim its verdict.

## 12. Traceability

Behavioral priorities and acceptance criteria live in `PRD.md`; build order and verification commands live in `IMPLEMENTATION_PLAN.md`; execution prompts live in `CLAUDE_CODE_GUIDE.md`; persistent contributor rules live in `CLAUDE.md`.
