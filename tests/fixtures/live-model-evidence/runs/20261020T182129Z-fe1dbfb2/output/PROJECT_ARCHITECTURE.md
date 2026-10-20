# Project Architecture: nginx-log-report

## Architecture Summary

The selected design is a single Python 3.11 process with a line-oriented pipeline:

```text
file(s) or stdin
       |
       v
 buffered text reader -> combined-log parser -> valid LogRecord
                                              |
                                              v
                                      StreamingAggregator
                                      /   |    |     \
                                  IPs  errors hours  UAs
                                              |
                                              v
                                  terminal | JSON | CSV
```

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect here because the product promises one-shot local analysis, retains no data, has a $0 budget, and does not need cross-run queries; persistence would add I/O, schema lifecycle, cleanup, and operational failure modes. An HTTP API is incorrect because the only consumers are a local operator and shell pipelines; a server would add authentication, networking, lifecycle, and deployment concerns without improving the required reports.

Only counters, 24 hourly buckets, rejected-line statistics, and distinct-key sets/maps remain in memory. No raw log line is retained after processing. Exact results are preferred; when configured unique-key capacity would be exceeded, processing stops with exit code 4 instead of approximating silently.

## Architecture Variants

### Variant A: Single-process streaming CLI (Selected)

- **Approach:** Read each input once, parse it, update in-memory aggregations, then render once.
- **Pros:** Lowest complexity, no intermediate storage, natural stdin support, easy pip installation, $0 runtime.
- **Cons:** Exact unique cardinality consumes memory; a failed run must restart.
- **Best for:** Local ad hoc analysis of bounded nginx logs.
- **Estimated complexity:** Low.

### Variant B: Unix pipeline of specialized commands

- **Approach:** Compose parsing, filtering, counting, and sorting with shell tools.
- **Pros:** Few Python dependencies and familiar primitives.
- **Cons:** Multiple passes/sorts, fragile quoting and User-Agent parsing, inconsistent cross-platform behavior, and no unified exit/schema contract.
- **Best for:** One-off exploration, not a distributable product.
- **Estimated complexity:** Low initially, medium to maintain.

### Variant C: Local indexed store

- **Approach:** Parse into SQLite or a search service and query reports afterward.
- **Pros:** Repeat queries and bounded application memory.
- **Cons:** Violates the approved no-database constraint, adds disk amplification and cleanup, and risks the 30-second target.
- **Best for:** Repeated historical analytics, explicitly outside this product.
- **Estimated complexity:** Medium to high.

### Recommendation

Variant A is selected because the scope is one local command, four fixed aggregations, no retained history, a one-weekend delivery, and no operating budget. The user has pre-approved this obvious single-process architecture.

## Components and Responsibilities

| Module | Responsibility | Key contract |
|---|---|---|
| `src/nginx_log_report/cli.py` | Click command, options, input selection, exception-to-exit mapping | Does not contain parsing or aggregation logic |
| `src/nginx_log_report/model.py` | Frozen `LogRecord` and `Report` dataclasses | Domain values are renderer-independent |
| `src/nginx_log_report/parser.py` | Parse supported combined-log lines and timestamps | Returns one record or a structured rejection |
| `src/nginx_log_report/stream.py` | Open files/stdin and yield lines with source locations | Never buffers an entire file |
| `src/nginx_log_report/aggregate.py` | Update exact counts, hourly buckets, and UA set | Enforces cardinality ceiling before inserting a new key |
| `src/nginx_log_report/render/terminal.py` | Rich tables and summary warnings | Color only for terminal presentation |
| `src/nginx_log_report/render/json.py` | Stable JSON document | UTF-8, deterministic keys, no ANSI escapes |
| `src/nginx_log_report/render/csv.py` | Stable long-form CSV | Header always present on success |
| `src/nginx_log_report/errors.py` | Typed operational failures and exit-code mapping | One authoritative mapping |

## Data Model and Calculations

`LogRecord` contains `client_ip: str`, `timestamp: datetime`, `request_target: str`, `status: int`, and `user_agent: str`. Request method/protocol and byte count may be parsed for validation but are not retained in the MVP report.

`Report` contains:

- `total_lines`, `total_valid_requests`, and `rejected_lines` as non-negative integers.
- `top_ips`: up to 10 `{ip, count, share_percent}` entries ordered by count descending, then IP ascending.
- `top_error_urls`: up to 10 `{url, error_count, share_of_error_requests_percent}` entries ordered by error count descending, then URL ascending.
- `hourly_distribution`: exactly 24 entries (`00` through `23`) with count and percent. Each percentage uses `100 × hourly_request_count / total_valid_requests`; when there are no valid requests, the command fails with exit code 3 rather than divide by zero.
- `unique_user_agents` and `unique_user_agent_share_percent`, where the share is `100 × unique_nonempty_user_agent_count / total_valid_requests`. Repeated requests with the same exact User-Agent string count once in the numerator. Missing/`-` values do not enter the distinct set.

Percentages are rounded to two decimal places only at serialization time. Internal calculations retain integer numerator/denominator pairs. Timestamp hours use the offset present in each log record; no timezone normalization is performed.

### Cardinality Bound

`--max-unique N` defaults to 1,000,000 distinct keys per tracked dimension (client IP, error URL, and nonempty User-Agent). Before adding a new key, the aggregator checks its dimension's size. Exceeding the limit raises `CardinalityExhausted`, emits a diagnostic to stderr, produces no partial report on stdout, and exits 4. Existing-key increments do not consume capacity. This makes the failure deterministic and avoids silently approximate reports.

## CLI Interface

### Command

```text
nginx-log-report [OPTIONS] [INPUT ...]
```

With no `INPUT`, the command reads stdin. One or more `INPUT` paths are processed sequentially as one logical stream. `-` may appear once to denote stdin. Inputs are UTF-8 text nginx access logs in the documented combined format; undecodable input is an input failure. Gzip support is a P1 feature and is not part of the first stable contract.

### Options

| Option | Meaning | Default |
|---|---|---|
| `--json` | Emit the JSON schema; mutually exclusive with `--csv` | off |
| `--csv` | Emit long-form CSV; mutually exclusive with `--json` | off |
| `--strict` | Fail on the first malformed line | off |
| `--max-unique INTEGER` | Positive per-dimension distinct-key ceiling | `1000000` |
| `--color / --no-color` | Force or suppress color in terminal mode | auto-detect |
| `--version` | Print version and exit | n/a |
| `--help` | Print Click help and exit | n/a |

In non-strict mode, malformed lines are skipped, counted, and summarized on stderr. In strict mode, the first malformed line exits 3. If all lines are malformed or there are zero valid requests, the command exits 3.

### Outputs

- **Terminal (default):** four Rich sections plus valid/rejected totals. Color is used when enabled; data remains readable without color.
- **JSON:** one object with `schema_version`, totals, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`. JSON goes only to stdout.
- **CSV:** UTF-8 RFC 4180-compatible rows with header `section,rank,key,count,percent`. Hour rows use ranks 0–23 and keys `00`–`23`; the UA summary uses key `unique_user_agents`.
- **Diagnostics:** source path, 1-based line number when known, and concise error text go to stderr. No successful data rows go to stderr.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Successful complete report (rejected lines are allowed only without `--strict` and with at least one valid request) |
| `1` | Unexpected internal/runtime failure |
| `2` | Click usage or configuration error, including conflicting modes, missing path, or invalid option value |
| `3` | Input/read/decoding/parsing failure, strict malformed line, or no valid requests |
| `4` | Unique-cardinality exhaustion; no partial report is emitted |

The `0/1/2/3/4` mapping is public and must remain stable across all renderers.

## Parsing Contract

The MVP supports the standard nginx combined-log shape:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

The parser accepts IPv4, IPv6, quoted request targets and User-Agents with spaces, `-` placeholders, numeric three-digit statuses, and timestamps with numeric UTC offsets. It rejects truncated lines, invalid status/timestamp fields, or requests from which no target can be derived. A compiled regular expression identifies fields; `datetime.strptime` validates timestamps. Tests, not permissive guessing, define extensions.

## Storage, API, Authentication, and Deployment

- **Database schema:** none. There are zero tables, migrations, indexes, or retained records by design.
- **HTTP API:** none. There are zero endpoints, request bodies, or network listeners by design.
- **Authentication/authorization:** none. The process has only the invoking user's local file permissions.
- **Environment variables:** none required. Locale, secrets, tokens, and service URLs are not part of the contract.
- **Docker/Kubernetes:** not used. A container would add startup and filesystem-mount friction to a pip-installable local tool; Kubernetes is expressly out of scope.
- **Deployment:** build a Python wheel and source distribution, install locally with pip, and expose the `nginx-log-report` console entry point. Publishing to a package index is a separate human-approved release action.

## Performance and Resource Strategy

- Read through Python's buffered iterator and process one line at a time.
- Compile parsing expressions and timestamp format helpers once.
- Store aggregate scalars and distinct keys, never raw records or lines.
- Use `heapq.nsmallest`/equivalent bounded selection over counters at finalization rather than sorting full item lists unnecessarily.
- Benchmark a deterministic, representative 1 GB fixture outside the repository and record laptop CPU, memory, Python version, wall time, and peak RSS.
- The acceptance target is under 30 seconds. Performance claims apply to uncompressed local input within the default cardinality ceiling.

## Security and Privacy

The tool never sends data over a network and writes no cache. It treats log text as untrusted data: renderers escape/control terminal behavior, CSV cells rely on the CSV library, and JSON uses the standard encoder. Diagnostics must not echo a full log line or expose more than path, line number, and parse category. Symlink and file access semantics follow the invoking user and operating system.

## Test Architecture

| Layer | Coverage |
|---|---|
| Parser unit tests | Valid combined logs, IPv6, quoting, offsets, malformed/truncated lines |
| Aggregator unit tests | Ties, errors only, 24 buckets, UA denominator, limit boundary and exhaustion |
| Renderer golden tests | Stable terminal semantics, JSON schema, CSV header/rows, no ANSI in machine modes |
| Click integration tests | stdin/files, multiple files, mutually exclusive flags, stderr separation, all exit codes |
| Performance test | Representative 1 GB generated fixture, wall time and peak RSS recorded |

## Architecture Decision Records

### ADR-001: Stateless single-process execution

- **Status:** Accepted by the product brief.
- **Decision:** Use Variant A and retain no cross-run state.
- **Consequences:** Simple local installation and privacy; exact distinct counts require a cardinality ceiling.

### ADR-002: Exact results or explicit failure

- **Status:** Accepted.
- **Decision:** Do not silently switch to probabilistic top-K or cardinality estimates.
- **Consequences:** Reports are trustworthy within limits; exit code 4 makes oversized cardinality a visible operational condition.

### ADR-003: Stable multi-renderer contract

- **Status:** Accepted.
- **Decision:** One renderer-neutral `Report` feeds terminal, JSON, and CSV output.
- **Consequences:** Calculations cannot drift by format and pipeline schemas can be golden-tested.

No adversarial review is recorded here; that review is outside this session by explicit instruction.

See `IMPLEMENTATION_PLAN.md` for delivery order and `PRD.md` for acceptance criteria.
