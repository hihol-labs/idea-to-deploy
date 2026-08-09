# Project Architecture: Nginx Insights CLI

## Architecture Goals and Boundaries

The architecture optimizes for a one-weekend, $0, local Python 3.11 tool that processes a 1 GB nginx access log in under 30 seconds on a documented reference laptop. The binding decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database would add persistence, migrations, cleanup, and I/O without helping a one-shot report. An HTTP API would add a server lifecycle, network and security surface, and serialization boundary when users already work in a shell. Both constraints correctly preserve the smallest system that meets the product need.

There is no authentication because there is no remote service or multi-user resource. There is no Docker requirement because a pip-installed local command is the distribution unit. There is no cloud or Kubernetes deployment.

## Architecture Variants

### Variant A: Single-process streaming CLI (Selected)

- **Approach:** Read one text stream, parse each line, update in-memory aggregators, then render once.
- **Pros:** One pass; smallest code and operational surface; natural stdin support; no intermediate files.
- **Cons:** Exact IP, URL, and User-Agent cardinality consumes memory proportional to distinct values; CPU parallelism is limited.
- **Best for:** Local files and shell pipelines up to the stated 1 GB target.
- **Estimated complexity:** Low.

### Variant B: Multi-process partition and merge

- **Approach:** Split seekable files into byte ranges, aggregate in workers, and merge partial maps.
- **Pros:** Can use multiple CPU cores on large regular files.
- **Cons:** Complicates line boundaries, stdin behavior, determinism, errors, and memory; process startup may erase gains.
- **Best for:** Larger files after profiling proves parsing is CPU-bound.
- **Estimated complexity:** Medium.

### Variant C: Delegate to an external analytics engine

- **Approach:** Wrap GoAccess or a Logstash pipeline and normalize its output.
- **Pros:** Reuses mature high-performance parsing and aggregation.
- **Cons:** Violates the simple pip-only experience, weakens output control, and can introduce services or platform-specific binaries.
- **Best for:** Organizations already standardized on that engine.
- **Estimated complexity:** Medium to high operationally.

### Recommendation

Variant A is selected because the product decisions explicitly approve the obvious single-process architecture. It is the only variant aligned with pip installation, stdin, $0 infrastructure, one-weekend delivery, and no server/database. Variants B and C remain future reconsiderations only if measured evidence invalidates the performance target.

## CLI Interface

### Command

```text
nginx-insights [OPTIONS] [INPUT]
```

`INPUT` is a path to an nginx combined access log. Omitted input or `-` reads UTF-8 text from stdin. The command processes a finite stream and exits; it does not follow files like `tail -f`.

### Options

| Option | Meaning | Default |
|---|---|---|
| `--json` | Emit the versioned JSON report | Off |
| `--csv` | Emit long-form CSV | Off |
| `--no-color` | Disable Rich color in terminal mode | Color only when stdout is a TTY |
| `--max-unique-user-agents INTEGER` | Maximum exact distinct User-Agent values retained before controlled failure | `1000000` |
| `--version` | Print package version and exit | — |
| `--help` | Print usage and exit | — |

`--json` and `--csv` are mutually exclusive. Output data goes to stdout; diagnostics go to stderr.

### Input contract

- Python 3.11 text decoding uses UTF-8 with replacement for invalid byte sequences, preventing a single bad byte from terminating a run.
- P0 parsing accepts nginx combined-log fields: client IP, timestamp with numeric offset, quoted request, numeric status, response bytes or `-`, referrer, and User-Agent.
- The request target is extracted from the quoted request line. Missing or syntactically malformed records are rejected and counted.
- Blank and malformed lines do not contribute to metrics. A warning summary reports their count on stderr.
- Timestamps are grouped by the hour (`00` through `23`) represented in each log record; no timezone conversion is performed.

### Output contract

Terminal output contains a run summary, ranked IP table, ranked error-URL table, 24-hour request-percentage table, and unique User-Agent share. Rankings are descending by count and then ascending by key for deterministic ties. The URL ranking combines statuses 400–599.

Hourly distribution is calculated for every hour using the literal formula `100 × hourly_request_count / total_valid_requests`. Empty hours are `0.0%`; displayed percentages use two decimal places while JSON retains numeric values computed from integer counts.

Unique User-Agent share is `100 × distinct_nonempty_user_agent_count / total_valid_requests`. It is an exact percentage for successful runs, not an estimator. Empty User-Agent strings are excluded from the numerator but their otherwise valid records remain in the denominator.

JSON schema:

```text
schema_version: integer (1)
summary: {total_lines, total_valid_requests, malformed_lines}
top_ips: [{rank, ip, request_count}]
top_error_urls: [{rank, url, error_count}]
hourly_request_distribution: [{hour, request_count, percentage}]
user_agents: {distinct_count, share_percentage}
```

CSV has the fixed header `metric,rank,key,count,percentage`. Ranking rows use `top_ip` or `top_error_url`; hour rows use `hourly_requests`; the one User-Agent row uses `unique_user_agent_share`. Inapplicable fields are empty. CSV is RFC 4180-compatible and emitted with the standard library `csv` module.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Success, including a stream with some malformed lines when at least one valid record exists |
| `1` | Unexpected runtime, processing, or output failure |
| `2` | Invalid command usage, option, or mutually exclusive format selection |
| `3` | Input failure: unreadable input or no valid records in a non-empty/empty stream |
| `4` | Unique-cardinality exhaustion: the configured exact User-Agent limit would be exceeded; no partial report is emitted |

A downstream closed pipe is handled quietly according to normal Unix CLI behavior and is not printed as a traceback.

## Component Design

```text
Click command
  -> input stream adapter
  -> combined-log parser
  -> AggregationState.update(record)
       -> IP Counter
       -> error-URL Counter
       -> 24-element hourly counts
       -> exact User-Agent set with limit
  -> Report dataclasses
  -> one renderer: Rich | JSON | CSV
```

| Module | Responsibility | Must not do |
|---|---|---|
| `src/nginx_insights/cli.py` | Click command, option validation, exit mapping | Parse log syntax or calculate metrics |
| `src/nginx_insights/parser.py` | Compile the combined-log parser once and return `AccessRecord` or a structured rejection | Read files or print |
| `src/nginx_insights/models.py` | Frozen `AccessRecord` and report dataclasses | Hold open streams |
| `src/nginx_insights/aggregator.py` | One-pass state updates, cardinality guard, deterministic top-10 finalization | Render output |
| `src/nginx_insights/renderers/rich.py` | TTY-aware tables and color | Change metric values |
| `src/nginx_insights/renderers/json.py` | Stable JSON schema | Emit diagnostics to stdout |
| `src/nginx_insights/renderers/csv.py` | Stable long-form CSV schema | Invent metric-specific columns |
| `src/nginx_insights/errors.py` | Domain exceptions and exit-code association | Catch unexpected exceptions silently |

## Data Model and Algorithms

No database schema exists. Runtime-only dataclasses are the complete logical data model:

| Dataclass | Fields |
|---|---|
| `AccessRecord` | `ip: str`, `hour: int`, `request_target: str`, `status: int`, `user_agent: str` |
| `RankedCount` | `rank: int`, `key: str`, `count: int` |
| `HourlyBucket` | `hour: int`, `request_count: int`, `percentage: float` |
| `UserAgentSummary` | `distinct_count: int`, `share_percentage: float` |
| `Report` | schema version, line counts, tuples of rankings/buckets, User-Agent summary |

The parser operates line by line and never retains raw lines. `AggregationState` stores integer totals, a 24-integer array, counters for distinct IPs and error URLs, and a set of distinct nonempty User-Agents. Finalization uses `heapq.nsmallest` or an equivalently benchmarked bounded selection with key `(-count, key)`; it must produce exact and deterministic top 10 results. Complexity is O(n) parsing plus final selection over distinct keys. Memory is O(distinct IPs + distinct error URLs + distinct User-Agents), with an explicit User-Agent cap.

## Error Handling and Observability

- Expected domain failures become the documented exit code and a concise stderr message.
- Unexpected failures return 1; development/debug logging may include a traceback only under a future explicit debug option.
- Malformed lines are counted, not logged individually, to avoid I/O amplification and sensitive-log leakage.
- JSON and CSV stdout remain machine-clean even when diagnostics exist.
- No log contents, IPs, URLs, or User-Agents leave the local machine.

## Packaging and Runtime Layout

```text
pyproject.toml
src/nginx_insights/
  __init__.py
  cli.py
  parser.py
  models.py
  aggregator.py
  errors.py
  renderers/{__init__.py,rich.py,json.py,csv.py}
tests/{unit,integration,fixtures,performance}/
```

`pyproject.toml` declares Python `>=3.11,<4`, Click and Rich runtime dependencies, a `nginx-insights` console entry point, and development-only test/lint/type tools. No environment variables are required. Local pip installation is the deployment mechanism; PyPI is the optional distribution channel.

## Performance and Verification

The reference benchmark must name laptop CPU, RAM, OS, storage, Python patch version, input-generation seed, input byte size, valid/malformed mix, and cold/warm-cache policy. It invokes the installed CLI with stdout redirected for terminal mode and separately verifies JSON/CSV on smaller golden fixtures. The 1 GB run must complete in under 30 seconds with exit 0. Peak RSS is recorded as a diagnostic, with a high-cardinality fixture separately proving exit 4 and absence of partial stdout.

Correctness suites cover parser quoting and escapes, IPv4/IPv6, timezone-bearing timestamps, 4xx/5xx boundaries, tie ordering, 24 buckets and the exact percentage formula, empty User-Agents, malformed lines, mutually exclusive options, all exit codes, TTY color behavior, and machine-readable schemas.

## Security and Privacy

Input is untrusted data. It is never executed, interpolated into a shell, fetched as a URL, or used as a filesystem path beyond the user-supplied input filename. Rich rendering must escape markup from log fields. JSON and CSV use their standard encoders. Error messages avoid echoing full log records. Dependency versions and licenses are reviewed before release. Because there is no listener, credential store, persistence, or network client, authentication and remote authorization are intentionally absent.

## Architecture Decision Record (ADR)

### ADR-001: Local single-process exact aggregation

- **Status:** Accepted.
- **Decision:** Use Variant A and the binding no-database/no-API boundary.
- **Consequences:** Minimal installation and one-pass processing; exact cardinality has explicit memory limits and performance must be proven rather than assumed.

### Debate Summary — Labeled Self-Critique

Per the benchmark constraint, this was a self-critique by the drafting agent; no independent or adversarial reviewer ran.

**Verdict:** APPROVE WITH CONDITIONS.

**Strengths acknowledged:** The design matches the approved single-process boundary, keeps pipeline output clean, and makes exact metric and failure semantics testable.

**Challenges raised and resolutions:**

1. Exact sets and counters can violate practical memory expectations on adversarial cardinality. **Resolution:** retain the explicit User-Agent ceiling and exit 4; record peak RSS; document counter cardinality as a residual risk rather than claiming bounded memory.
2. A regex parser may mishandle nginx escaping. **Resolution:** compile once, maintain adversarial fixtures, and scope P0 to the documented combined format.
3. “Hourly” can be ambiguous across time zones. **Resolution:** bucket the literal local hour in each log timestamp and avoid implicit conversion.
4. Heterogeneous CSV sections can become unstable. **Resolution:** adopt one fixed long-form schema with contract tests.
5. Performance can be dominated by Rich rendering or output volume. **Resolution:** report only bounded tables plus 24 buckets, redirect benchmark output, and benchmark parsing/aggregation separately when profiling.

**Alternatives considered and rejected:**

- Multi-process partitioning — rejected for MVP because stdin parity and boundary correctness cost more than unmeasured speed benefit.
- SQLite or another database — rejected because persistence and I/O add no value to a one-shot report.
- HTTP service — rejected because it adds deployment and security surfaces without a user requirement.
- Approximate sketches — rejected for MVP because the approved report implies exact values; may be reconsidered as an opt-in future mode.

The approval conditions are incorporated in this architecture and in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
