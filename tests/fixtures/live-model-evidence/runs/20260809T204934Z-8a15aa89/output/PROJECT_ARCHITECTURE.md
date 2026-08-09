# Project Architecture: Nginx Log Lens

## 1. Context and Constraints

Nginx Log Lens is a local, pip-installable Python 3.11 CLI. It consumes nginx
access-log lines from a file or stdin and emits a final report. It does not
authenticate users, listen on a network socket, persist data, or coordinate
multiple processes. The delivery budget is $0 and one weekend; the performance
target is 1 GB in under 30 seconds on a declared reference laptop.

The governing decision is: **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema and
lifecycle management to a one-pass question whose output can be computed from
in-memory counters; persistence would expand privacy and cleanup obligations
without improving the approved workflow. An HTTP API would require a server,
authentication and an operational boundary even though the user and the log
already share one machine. Standard input/output provides the needed pipeline
interface with lower latency, cost, and failure surface.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended)

- **Approach:** one Python process iterates line by line, parses each valid
  record, updates in-memory aggregators, freezes a summary, then renders it.
- **Pros:** simplest lifecycle; no IPC; deterministic totals; easiest packaging;
  matches stdin semantics and one-weekend delivery.
- **Cons:** CPU work is single-core; exact counters and User-Agent cardinality
  still consume memory proportional to distinct values.
- **Best for:** local analysis up to the approved 1 GB target.
- **Estimated complexity:** Low.

### Variant B: Chunked multiprocessing

- **Approach:** split seekable files into byte ranges, parse in workers, merge
  counters in a parent process; fall back to one process for stdin.
- **Pros:** can use multiple cores on large regular files.
- **Cons:** two execution paths, chunk-boundary complexity, IPC/merge overhead,
  higher peak memory, and no benefit for a live pipe.
- **Best for:** multi-gigabyte batch files after profiling proves parsing is CPU-bound.
- **Estimated complexity:** High.

### Variant C: Shell composition around specialized commands

- **Approach:** invoke `awk`, `sort`, and `uniq` for each metric.
- **Pros:** little Python aggregation code and leverages optimized system tools.
- **Cons:** multiple passes, platform-dependent quoting/behavior, fragile nginx
  parsing, temporary sorting, and inconsistent Windows support.
- **Best for:** a private Unix-only script with no stable package contract.
- **Estimated complexity:** Medium operational complexity despite low code volume.

### Recommendation

Variant A is selected because the architecture is obvious under the approved
scope: one input stream, four aggregations, one final report, one weekend, and
no service boundary. Variant B is retained only as a post-MVP option if a
profiled benchmark—not intuition—shows single-core parsing prevents the target.

## 3. System Structure

```text
file path or stdin
       |
       v
 InputSource (text lines)
       |
       v
 NginxParser ----invalid----> ParseDiagnostics
       |
       v valid AccessRecord
 StreamingAggregator
   |-- Counter(client_ip)
   |-- Counter(error_url), only status 400..599
   |-- 24-element hourly counts
   `-- set(user_agent), guarded by cardinality limit
       |
       v immutable AnalysisSummary
 RichRenderer | JsonRenderer | CsvRenderer
       |
       v
 stdout (report) + stderr (diagnostics)
```

All metrics are updated during the same iteration. The implementation must not
call `read()`, `readlines()`, or materialize all `AccessRecord` instances.

## 4. Components and Data Model

| Module | Responsibility | Key types/functions |
|---|---|---|
| `src/nginx_log_lens/cli.py` | Click command, option validation, stream ownership, exit translation | `main()`, `analyze()` |
| `src/nginx_log_lens/parser.py` | Parse supported nginx common/combined lines and timestamps | `NginxParser`, `ParseError` |
| `src/nginx_log_lens/models.py` | Immutable data exchanged between layers | `AccessRecord`, `RankedCount`, `HourlyBucket`, `AnalysisSummary` dataclasses |
| `src/nginx_log_lens/aggregate.py` | One-pass counters, percentages, deterministic top-10 ordering | `StreamingAggregator`, `UniqueCardinalityExhausted` |
| `src/nginx_log_lens/renderers/rich.py` | Colored human report | `render_rich()` |
| `src/nginx_log_lens/renderers/json.py` | Stable JSON document | `render_json()` |
| `src/nginx_log_lens/renderers/csv.py` | Stable long-form CSV records | `render_csv()` |
| `src/nginx_log_lens/errors.py` | Domain errors and exit-code mapping | `ExitCode` `IntEnum` |

### Dataclasses

| Type | Fields | Invariants |
|---|---|---|
| `AccessRecord` | `client_ip: str`, `timestamp: datetime`, `request_target: str`, `status: int`, `user_agent: str | None` | timezone-aware timestamp; status 100–599; target is the raw request target or `-` |
| `RankedCount` | `rank: int`, `key: str`, `count: int` | rank starts at 1; count > 0 |
| `HourlyBucket` | `hour: int`, `request_count: int`, `percentage: float` | hour 0–23; percentage computed from valid records only |
| `AnalysisSummary` | `total_lines`, `total_valid_requests`, `invalid_lines`, `top_ips`, `top_error_urls`, `hourly_distribution`, `distinct_user_agents`, `unique_user_agent_share` | immutable; list ordering is deterministic |

There are no database tables, fields, indexes, migrations, or stored records.
This is intentional, not an omitted design section. In-memory counters are
ephemeral process state and are discarded at exit.

## 5. Input Parsing Contract

The MVP supports nginx common and combined access-log records with the standard
shape:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

The parser extracts the client address, `%d/%b/%Y:%H:%M:%S %z` timestamp,
request target, numeric status, and optional User-Agent. Common format lacks
referer and User-Agent; its User-Agent is `None` and does not add to the
distinct set. Escaped quotes and backslashes inside quoted fields must be
handled according to the supported grammar. Unsupported custom `log_format`
records are invalid input, not guessed into fields.

Default mode skips malformed lines, increments `invalid_lines`, and prints a
bounded diagnostic summary to stderr. `--strict` stops at the first malformed
line and exits `3`. A completed stream with zero valid requests also exits `3`.

## 6. Aggregation Semantics

- **Top IPs:** count every valid request by the parsed client IP. Return at most
  10 entries, ordered by descending count then lexicographically ascending IP.
- **Top error URLs:** count request targets only when status is 400–599. Return
  at most 10 entries, ordered by descending count then lexicographically
  ascending URL. If none exist, return an empty list.
- **Hourly distribution:** use the hour in each record's own parsed timezone;
  do not convert zones. Emit all 24 hours. Each percentage uses the literal
  formula `100 × hourly_request_count / total_valid_requests`. The 24 unrounded
  values sum to 100 for non-empty input; renderers display a documented rounded
  representation without changing raw counts.
- **Unique User-Agent share:** `100 × distinct_non_missing_user_agent_count /
  total_valid_requests`. Repeated values count once; missing `-` values do not
  enter the set. This is a diversity ratio and may exceed neither 100 nor the
  count of valid requests under the one-UA-per-record grammar.
- **Cardinality guard:** before adding a new non-missing User-Agent beyond
  `--max-unique-user-agents`, raise `UniqueCardinalityExhausted`. Do not emit a
  partial report or silently approximate; exit `4`.

Counter memory is `O(U_ip + U_error_url + U_user_agent + 24)`, where `U` means
distinct values encountered. Processing time is `O(N + U log 10)` and each
input line is visited once. The performance benchmark must include stated
cardinalities so the memory result is meaningful.

## CLI Interface

### Commands

```text
nginx-log-lens analyze [OPTIONS] [INPUT]
nginx-log-lens --help
nginx-log-lens --version
```

`INPUT` is a path to a UTF-8 nginx access log. Omit it or pass `-` to consume
stdin. The process reads a regular file once from its current beginning; live
following/tailing is outside MVP scope. Decompression may be composed through
stdin, for example `gzip -dc access.log.gz | nginx-log-lens analyze -`.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Write one UTF-8 JSON object to stdout |
| `--csv` | false | Write UTF-8 RFC 4180-compatible long-form CSV to stdout |
| `--strict` | false | Stop on the first malformed line with exit `3` |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive ceiling for exact distinct User-Agent values; exhaustion exits `4` |
| `--no-color` | false | Disable ANSI color in terminal mode; has no effect on JSON/CSV |
| `--version` | n/a | Print package version and exit `0` |
| `--help` | n/a | Print usage and exit `0` |

`--json` and `--csv` are mutually exclusive. Click validates invalid values,
unknown options, conflicting output flags, and extra arguments as usage errors.

### Outputs

- **Terminal:** four Rich sections plus processed/invalid totals. Color is used
  only when enabled and stdout is a suitable terminal; data is never encoded
  only by color.
- **JSON:** keys are `schema_version`, `total_lines`,
  `total_valid_requests`, `invalid_lines`, `top_ips`, `top_error_urls`,
  `hourly_distribution`, `distinct_user_agents`, and
  `unique_user_agent_share`. Ranked entries contain `rank`, `value`, and
  `count`; hourly entries contain `hour`, `request_count`, and `percentage`.
- **CSV:** header `record_type,rank,key,count,percentage`; rows use record types
  `summary`, `top_ip`, `top_error_url`, `hour`, and `user_agent_share`. Fields
  irrelevant to a record type are empty. Exactly one header is emitted.
- **stderr:** input warnings and errors only. JSON and CSV stdout never contain
  colors, progress messages, warnings, or tracebacks.

For deterministic pipeline results, JSON keys and ranked rows use the ordering
above, tie-breaking is explicit, hours are `00` through `23`, newline is `\n`,
and displayed percentages use six decimal places. Unicode is emitted as UTF-8.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Successful analysis, help, or version output |
| `1` | Operational failure: input cannot be opened/read, output cannot be written, or unexpected internal failure |
| `2` | Click command-line usage error |
| `3` | Log-data error: strict parsing failure or no valid request records |
| `4` | Unique-cardinality exhaustion: exact User-Agent set would exceed the configured limit |

The `0/1/2/3/4` mapping is public API. Renderers must not remap domain errors;
`cli.py` is the only translation boundary.

## 8. Error Handling and Resource Safety

Expected errors become concise stderr messages without a traceback. File
handles opened by the CLI are closed in `finally`/context-manager paths; stdin
is never closed by the application. A line-length safety limit should be
enforced before parsing to prevent a single pathological record from consuming
unbounded memory; exceeding it is a log-data error (`3` in strict mode, skipped
and counted otherwise). Signals and broken pipes follow normal CLI conventions,
with broken output represented as operational failure unless the platform
raises the standard pipeline-close condition before any report is required.

No log lines, IPs, URLs, or User-Agents are sent over a network. Diagnostics
must not echo complete malformed records because they may contain sensitive
URLs or identifiers.

## 9. Packaging, Configuration, and Deployment

The project is a `src/`-layout Python package with a `pyproject.toml` console
entry point named `nginx-log-lens`. The deployment target is a local Python
3.11 virtual environment installed through pip. There is no Docker image,
`docker-compose.yml`, server deployment, cloud resource, Kubernetes manifest,
or runtime daemon; adding those would contradict the chosen architecture.

There are no required environment variables. Locale, terminal width, and
color capability may influence Rich layout but never metric values. CLI flags,
not hidden environment configuration, control product behavior.

## 10. Authentication and Network Boundary

Authentication is not applicable: the process runs with the invoking OS
user's filesystem permissions and exposes no network interface. There is no
login, session, token, role, endpoint, or authorization flow. The complete flow
is therefore:

```text
OS user invokes local process -> OS checks file permissions -> process reads input
```

There are no HTTP API endpoints, request/response bodies, ports, or network
protocols. stdin/stdout and the CLI contract above are the integration surface.

## 11. Test and Performance Architecture

Unit fixtures cover common/combined lines, IPv4/IPv6, quoting, timezone hours,
status boundaries, missing User-Agent, malformed lines, ties, empty errors, and
cardinality exhaustion. Integration tests invoke the installed console script
and assert stdout, stderr, and the complete exit-code contract. JSON is parsed
against its schema; CSV is read back through `csv.DictReader`; terminal tests
strip ANSI before semantic comparison.

The performance harness generates a reproducible 1 GB fixture outside the
repository, warms neither parser nor OS cache intentionally unless documented,
and records wall time and peak RSS. The release gate is under 30 seconds on the
named laptop. Benchmark data must contain enough distinct IPs, URLs, and agents
to exercise realistic allocation while remaining below the configured exact
User-Agent ceiling.

## 12. Architecture Decision Record (ADR)

### ADR-001: Single-process, stateless CLI

- **Status:** Accepted.
- **Decision:** Select Variant A and the literal database/API decision in
  Section 1.
- **Consequences:** minimal deployment and deterministic streaming behavior;
  counters remain bounded only by input cardinality, and the CPU path is
  single-core.

### Debate Summary — Labeled Self-Critique

Per the benchmark constraint, this review is a **self-critique by the authoring
agent**, not an independent, adversarial, or different-model review.

**Verdict:** APPROVE WITH CONDITIONS.

**Strengths acknowledged:** the design has one clear responsibility per layer,
one pass over input, no unnecessary service/storage boundary, stable output
contracts, and an explicit exactness failure mode.

**Challenges raised and resolutions:**

1. Exact distinct tracking can exhaust memory before the 1 GB file ends.  
   **Resolution:** require a positive cardinality ceiling, atomic failure, and
   exit `4`; benchmark with declared cardinalities.
2. Regex-only nginx parsing is vulnerable to quoting edge cases.  
   **Resolution:** define and test a finite common/combined grammar, including
   escapes, and never guess unsupported custom formats.
3. A nominally streaming design can still allocate the whole file accidentally.  
   **Resolution:** prohibit materializing input/records and enforce peak-RSS in
   the performance acceptance test.
4. Three renderers can disagree through independent calculations.  
   **Resolution:** make aggregation produce one immutable summary; renderers
   format but never recalculate metrics.
5. The under-30-second statement is meaningless without hardware and fixture context.  
   **Resolution:** make environment, generator, cardinalities, wall-time, and
   RSS evidence mandatory before the target is claimed.
6. Multiprocessing could be faster.  
   **Resolution:** reject it for MVP because stdin cannot be split reliably and
   complexity exceeds the weekend scope; reconsider only after profiling.

**Alternatives considered and rejected:**

- Chunked multiprocessing — rejected for dual execution paths, IPC, and higher memory.
- Database-backed ingestion — rejected because no cross-run query is required.
- HTTP service — rejected because local stdio already supplies the automation boundary.
- Shell commands — rejected because portability and parsing correctness are product requirements.

The conditions are incorporated into Sections 5–11. Before implementation,
`PRD.md` supplies acceptance criteria; `IMPLEMENTATION_PLAN.md` defines the
dependency order and verification commands.
