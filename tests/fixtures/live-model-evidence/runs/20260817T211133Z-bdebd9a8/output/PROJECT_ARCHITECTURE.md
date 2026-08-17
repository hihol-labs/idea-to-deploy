# Project Architecture: Nginx Stream Analyzer

## Architecture Goals and Constraints

- Local Python 3.11 command, installable with pip.
- Single-process, single-pass processing of files or stdin.
- Target: analyze a 1 GB supported log in under 30 seconds on a recorded laptop.
- No authentication, database, HTTP API, server, cloud, or Kubernetes.
- Cash budget $0 and one-weekend MVP delivery.
- Stable terminal, JSON, CSV, and exit-code contracts.

The governing decision is **"no database — stateless streaming processing; no HTTP API — CLI-only tool"**.

Both constraints are correct here. A database would add persistence, schema
management, writes, cleanup, and operational state when the requested report
is fully derivable during one scan. An HTTP API would add a long-running
process, network exposure, serialization surface, deployment, and likely
authentication without improving the local pipe/file workflow. In-process
aggregation is transient: all state is released at process exit and no input
or report is retained unless the caller redirects output.

## Chosen Architecture

The approved architecture is one OS process with a layered internal pipeline:

```text
file(s) / stdin
      |
      v
InputSource iterator -> nginx line parser -> LogRecord dataclass
      |                       |                    |
      |                 parse diagnostics         v
      |                                      StreamingAggregator
      |                                      /   |    |    \
      |                                  IP top URL top hours UA set
      |                                             |
      +---------------------------------------------v
                                               Report dataclass
                                           /          |         \
                                    Rich terminal    JSON       CSV
```

There are no worker processes or threads. This avoids ordering, merge, and
IPC overhead for a workload dominated by sequential reading and parsing.
Modules communicate through dataclasses and iterators rather than global
state. The renderer receives only the finalized `Report`, so every output
format uses identical values and ordering.

## CLI Interface

### Command

```text
nginx-stream-analyzer [OPTIONS] [FILE]...
```

With no `FILE`, input is read from stdin. A literal `-` also denotes stdin and
may appear at most once. Multiple files are read in command-line order and
produce one aggregate report. Directories are rejected. Input is UTF-8 text;
invalid bytes follow the selected error policy. The MVP accepts uncompressed
files only.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | off | Emit exactly one JSON document to stdout; mutually exclusive with `--csv` |
| `--csv` | off | Emit one RFC 4180 CSV document to stdout; mutually exclusive with `--json` |
| `--color [auto\|always\|never]` | `auto` | Controls ANSI styling for terminal mode; usage error with `--json` or `--csv` unless `auto` |
| `--strict/--no-strict` | `--no-strict` | Strict mode stops at the first malformed record with exit 3; otherwise skip, count, and report malformed lines |
| `--max-cardinality INTEGER` | `1000000` | Positive upper bound for each exact IP, URL, and User-Agent key set; exceeding it exits 4 |
| `--format [combined\|common]` | `combined` | Selects the supported nginx log grammar; `common` has no User-Agent field |
| `--version` | n/a | Print version and exit 0 |
| `--help` | n/a | Print help and exit 0 |

`--format common` reports `unique_user_agent_count: 0` and
`unique_user_agent_share_percent: null`, because the input grammar has no
User-Agent field. This is absence, not a measured zero percent.

### Inputs

Supported `combined` records contain remote address, remote user, local
timestamp with numeric offset, request line, status, body bytes, referrer, and
User-Agent. Supported `common` records end after body bytes. Escaped quotes and
backslashes inside quoted fields are handled. The parser preserves URL target
text from the request line; it does not decode percent escapes, remove query
strings, or normalize case. A request line of `-` has no URL and is a malformed
record for metric purposes.

Blank lines and unsupported/malformed records increment `invalid_lines`. In
non-strict mode they are skipped and a concise warning is written to stderr;
machine output remains parseable on stdout. If the entire input has zero valid
records, processing exits 3 and emits no report.

### Metric Definitions

- `top_ips`: at most ten `(ip, request_count)` rows over valid records, sorted
  by count descending and then IP string ascending.
- `top_error_urls`: at most ten `(url, error_count)` rows for statuses 400–599
  inclusive, sorted by count descending and then raw URL ascending.
- `hourly_request_distribution`: exactly 24 rows, hours `00` through `23`.
  Each percentage is `100 × hourly_request_count / total_valid_requests`,
  calculated from the hour written in each record's timestamp and rounded only
  for display to two decimal places. JSON retains a numeric two-decimal value.
- `unique_user_agent_share_percent`: for combined format,
  `100 × distinct_nonempty_user_agent_count / total_valid_requests`, rounded
  only for display to two decimal places. A literal `-` is treated as missing,
  not as a distinct agent.

Counts are integers. Percentage rounding uses decimal round-half-even to two
places; the unrounded numerator and denominator are also present in machine
output so consumers can recompute values.

### Outputs

Terminal mode writes a title, input summary, top-IP table, top-error-URL table,
24-hour distribution, User-Agent summary, and malformed-line warning. Color is
enabled only when stdout is a TTY under `auto`. Diagnostics go to stderr.

JSON uses this versioned shape and deterministic key order:

```json
{
  "schema_version": 1,
  "summary": {"valid_requests": 0, "invalid_lines": 0},
  "top_ips": [{"ip": "192.0.2.1", "request_count": 1}],
  "top_error_urls": [{"url": "/missing", "error_count": 1}],
  "hourly_request_distribution": [
    {"hour": "00", "request_count": 0, "percentage": 0.00}
  ],
  "user_agents": {
    "distinct_count": 0,
    "observed_request_count": 0,
    "share_percent": 0.00
  }
}
```

The actual hourly array always has 24 entries. In common format, the final
three User-Agent values are `0`, `0`, and `null` respectively.

CSV uses columns `schema_version,metric,rank,key,count,percentage`. It contains
rows in this order: `summary` (`valid_requests`, `invalid_lines`), `top_ip`,
`top_error_url`, 24 `hour` rows, then `user_agent` rows for distinct and
observed counts plus share. Non-applicable cells are empty. Fields use standard
CSV quoting and `\n` line endings for cross-platform golden tests.

### Exit Codes

| Code | Meaning |
|---:|---|
| 0 | Successful report, including non-strict runs that skipped at least one malformed line |
| 1 | Operational failure: unreadable input, broken pipe other than normal downstream close, or unexpected I/O failure |
| 2 | Click usage error: invalid/mutually exclusive options, invalid cardinality value, directory input, or repeated stdin |
| 3 | Log data failure: strict-mode parse failure, invalid UTF-8 under strict policy, or zero valid requests |
| 4 | Unique-cardinality exhaustion: an exact IP, URL, or User-Agent key set would exceed `--max-cardinality` |

No partial report is written for exits 1–4. Diagnostics are concise, include
the source name and line number when available, and never include an entire
potentially sensitive log record.

## Package and Module Layout

```text
pyproject.toml
src/nginx_stream_analyzer/
  __init__.py          # package version only
  cli.py               # Click command, option validation, exit mapping
  models.py            # LogRecord, ParseStats, Report dataclasses
  parser.py            # combined/common grammar and timestamp/request parsing
  sources.py           # ordered lazy iteration over files/stdin
  aggregate.py         # counters, cardinality limits, report finalization
  renderers/
    __init__.py
    terminal.py        # Rich output
    json.py            # versioned JSON shape
    csv.py             # long-form CSV rows
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_renderers.py
  test_performance.py
```

`cli.py` depends inward on sources, parser, aggregation, and renderer
interfaces. Parsing and aggregation never import Click or Rich. Renderers do
not parse inputs. This keeps hot-loop tests independent of terminal behavior.

## Data Model and Invariants

### `LogRecord`

| Field | Type | Invariant |
|---|---|---|
| `remote_addr` | `str` | Non-empty source token; IPv4, IPv6, or nginx-provided address text |
| `timestamp` | `datetime` | Offset-aware value parsed from nginx timestamp |
| `method` | `str` | Non-empty request method |
| `target` | `str` | Raw non-empty request target, unchanged |
| `protocol` | `str` | Request protocol token |
| `status` | `int` | 100–599 |
| `body_bytes` | `int | None` | Non-negative; `-` maps to `None` |
| `user_agent` | `str | None` | Combined-format value; `-`/common maps to `None` |

### `Report`

| Field | Type | Invariant |
|---|---|---|
| `schema_version` | `int` | Exactly 1 for the MVP |
| `valid_requests` | `int` | Positive for any emitted report |
| `invalid_lines` | `int` | Non-negative |
| `top_ips` | `tuple[RankedCount, ...]` | Length 0–10, deterministic ordering |
| `top_error_urls` | `tuple[RankedCount, ...]` | Length 0–10, deterministic ordering |
| `hour_counts` | `tuple[int, ...]` | Exactly 24 non-negative counts; sum equals valid requests |
| `distinct_user_agents` | `int` | Non-negative and within configured ceiling |
| `observed_user_agent_requests` | `int` | Count of valid records with non-missing UA |
| `user_agent_share_percent` | `Decimal | None` | `None` for common format; otherwise 0–100 |

No database tables exist. Transient dictionaries/sets are implementation
details, not persistence. The cardinality ceiling is checked before adding a
new key, so memory growth is bounded by three configured key budgets.

## Streaming Algorithm and Complexity

For each input line:

1. Parse directly into a `LogRecord`; never retain the raw line.
2. Increment total and one of 24 hour buckets.
3. Increment the IP counter.
4. For status 400–599, increment the raw-target counter.
5. If User-Agent is present, increment observed count and insert into its set.
6. Before introducing any new key, enforce the exact cardinality ceiling.

At EOF, select ten items from each counter with `heapq.nsmallest` using the
documented inverse count/lexical key and construct one immutable report.
Runtime is O(n + u log 10), where `n` is lines and `u` is distinct counted
keys. Memory is O(u_ip + u_error_url + u_ua), capped per set by
`--max-cardinality`; it is independent of total line count.

## Error, Privacy, and Security Boundaries

- Log content is untrusted data, never code or a format string.
- No shell is invoked and no path is constructed from log fields.
- Diagnostics expose source and line number plus a reason code, not full
  records, URLs, referrers, or User-Agents.
- Terminal output escapes/control-sanitizes values before Rich rendering.
- JSON and CSV use standard-library encoders.
- The tool makes no network calls and writes no files.
- Input may contain personal data such as IPs and User-Agents; processing stays
  local, and users are warned before sharing reports.
- Dependency versions are bounded in `pyproject.toml`; the lock/release process
  checks known vulnerabilities without introducing a runtime service.

## Packaging and Runtime

`pyproject.toml` declares Python `>=3.11,<4`, Click and Rich runtime
dependencies, a `src` layout, and console script
`nginx-stream-analyzer = nginx_stream_analyzer.cli:main`. A wheel and source
distribution are built with a standard PEP 517 backend and tested in a clean
virtual environment. There is no Docker image: pip installation on a laptop
is the deployment target. There are no environment variables, secrets,
ports, health endpoints, migrations, or background services.

## Performance Verification

The release benchmark generates or uses a disclosed 1 GB combined-log corpus
outside the timed region, then invokes the installed wheel with stdout
redirected to a file. It records wall time, peak RSS, CPU, Python version,
hardware, input size, valid-record count, and output-format mode. Run terminal
without color, JSON, and CSV separately; all must be semantically equivalent,
and the slowest supported mode must stay below 30 seconds. A high-cardinality
corpus verifies deterministic exit 4 without an out-of-memory failure.

## Architecture Decision Records

### ADR-001: Single-process streaming CLI

- **Status:** Accepted; product decision pre-approved.
- **Decision:** Use one Python process with lazy input iteration, pure parsing
  and aggregation layers, and renderer adapters.
- **Why:** It directly fits local files/pipes, $0 operations, one-weekend
  delivery, and the absence of cross-request state.
- **Consequences:** No horizontal scaling or stored history; users rerun the
  command for a new report. The 1 GB performance gate is release-blocking.

### ADR-002: Exact aggregation with explicit cardinality failure

- **Status:** Accepted.
- **Decision:** Keep exact counters/sets up to a caller-visible ceiling and
  exit 4 before exceeding it.
- **Why:** Approximate heavy-hitter or probabilistic cardinality algorithms
  would make the unqualified metric names misleading.
- **Consequences:** Pathological cardinality does not yield a partial or
  approximate report; the caller must raise the limit on a suitable machine
  or preprocess the input.

### ADR-003: One report model, three renderers

- **Status:** Accepted.
- **Decision:** Finalize all metrics into an immutable report before rendering.
- **Why:** This prevents semantic drift among terminal, JSON, and CSV output.
- **Consequences:** Final result metadata and top-ten arrays remain briefly in
  memory, which is negligible relative to aggregation state.

Product alternatives and their trade-offs are recorded in
`STRATEGIC_PLAN.md`; detailed behavior is the acceptance contract in `PRD.md`.
