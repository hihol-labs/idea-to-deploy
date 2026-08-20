# Project Architecture: nginx-report

## 1. Context and Drivers

`nginx-report` is a Python 3.11 command-line program that reads nginx combined
access-log records incrementally and reports four exact summaries. The design
is optimized for a one-weekend, $0 open-source delivery and a measured target
of processing a representative 1 GB log in under 30 seconds on a laptop.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect here because the required
outputs are derivable in one pass, persistence would increase setup, I/O, and
privacy exposure, and no query/history requirement exists. An HTTP API is
incorrect because the target user already operates in a shell, files and stdin
are the natural trust boundary, and a server would introduce authentication,
ports, lifecycle, and deployment concerns without product value.

## 2. Architecture Decision

### Chosen variant: single-process layered CLI

One Python process owns input, parsing, aggregation, finalization, and one
selected presenter. Modules have one-way dependencies and communicate through
dataclasses. Input is never loaded wholesale. This is the pre-approved and
recommended architecture because it is the smallest design that meets the
local CLI, performance, packaging, and output-contract requirements.

### Alternatives considered and rejected

| Variant | Benefits | Costs/reason rejected |
|---|---|---|
| Unix-pipeline wrappers around `awk`, `sort`, and `uniq` | Minimal custom code; familiar tools | Brittle combined-log quoting, platform differences, multiple full-file sorts, and weak JSON/CSV/error contracts |
| Go single binary | Excellent throughput and bounded runtime footprint | Violates the approved Python 3.11/Click/Rich stack and adds no needed deployment capability |
| Local SQLite staging | Flexible repeat queries | Violates stateless/no-database scope, duplicates the source log, adds disk I/O and cleanup |
| Multiprocess Python pipeline | Potential CPU parallelism | Ordering, merging, startup, and platform complexity are unjustified until a single process is benchmarked |

## 3. System Context and Data Flow

```text
file path(s) / stdin
        |
        v
  InputSource iterator  -- I/O failure ----------------------> exit 1
        |
        v
  CombinedLogParser     -- malformed line --> diagnostic count
        |
        v
  Aggregator
   |        |          |                    |
   v        v          v                    v
 IP counts  error URL  24 hourly buckets   unique UA set + cap
   \___________  immutable Report dataclass  ___________/
                         |
           +-------------+-------------+
           |             |             |
        Rich text       JSON           CSV
```

The parser and aggregator run once per line. Presentation starts only after a
finite input stream reaches EOF. Multiple input files are concatenated in
argument order. Exact count maps make memory proportional to distinct IPs and
error URLs; the exact User-Agent set has an explicit configurable safety cap.

## 4. Components and Repository Layout

```text
pyproject.toml
README.md
src/nginx_report/
  __init__.py
  cli.py                 # Click options, orchestration, exit mapping
  models.py              # LogRecord, Report, ErrorUrlMetric dataclasses
  parser.py              # Supported combined-log grammar and timestamps
  sources.py             # File/stdin/gzip iterators
  aggregate.py           # Counters, hourly buckets, UA cardinality cap
  errors.py              # Typed operational and cardinality exceptions
  presenters/
    __init__.py
    terminal.py          # Rich tables and TTY color policy
    json_output.py       # Stable JSON document
    csv_output.py        # Stable normalized row stream
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_presenters.py
  test_performance.py
```

| Component | Input | Output | Responsibility |
|---|---|---|---|
| `sources` | path list or stdin | iterator of `(source, line_number, text)` | Open lazily, decode UTF-8, optionally decompress gzip |
| `parser` | one line | `LogRecord` or parse failure | Parse combined format and normalize timestamp hour/status/URL/IP/UA |
| `aggregate` | valid records | immutable `Report` | Maintain counters, top-ten ordering, percentages, cap |
| `presenters` | `Report` | text bytes on stdout | Render exactly one output format |
| `cli` | argv, stdin | stdout/stderr and exit code | Validate options, wire components, map failures |

## 5. Input and Parsing Contract

Supported input is the standard nginx combined form:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

- UTF-8 is decoded strictly; a decoding/open/read error is operational failure.
- IPv4, IPv6, and non-empty nginx `$remote_addr` tokens are counted verbatim.
- The request field must contain method, request-target, and protocol. The URL
  key is the request-target exactly as logged, including its query string.
- Status must be a three-digit integer. Errors are statuses 400–599.
- Timestamp offsets are parsed, but hourly distribution uses the log entry's
  displayed local hour (`00` through `23`), not conversion to machine time.
- User-Agent is the quoted field unescaped to its logged string; `"-"` is a
  legitimate single value, not missing data.
- Malformed lines are skipped and counted. If zero valid records remain, the
  command emits no report and exits 3.

Blank lines are malformed lines. Files are opened sequentially; `-` selects
stdin and may appear at most once. Input order does not change aggregate
results or tie ordering.

## 6. Metric Semantics

| Metric | Definition | Deterministic ordering |
|---|---|---|
| Top client IPs | Up to ten IP keys by count across all valid requests | Count descending, then IP string ascending |
| Top error URLs | Up to ten request-target keys by combined 4xx + 5xx count; each row also carries separate 4xx and 5xx counts | Total errors descending, then URL ascending |
| Hourly distribution | All 24 hours, including zero buckets; each percentage is `100 × hourly_request_count / total_valid_requests` | Hour ascending from `00` to `23` |
| Unique User-Agent share | `100 × unique_user_agent_count / total_valid_requests`; numerator is exact distinct logged UA values | One scalar plus unique and total counts |

Percentages are computed at finalization, represented as JSON numbers, and
rendered to two decimal places in terminal and CSV. The 24 unrounded hourly
values mathematically sum to 100%; displayed rounded values may differ by a
few hundredths. No approximate cardinality algorithm is used.

The default `--max-unique-user-agents` is 1,000,000. Encountering a new value
after the limit has been reached stops processing, writes a diagnostic to
stderr, emits no partial report, and exits 4. This makes unique-cardinality
exhaustion explicit rather than returning a misleading percentage.

## CLI Interface

### Command

```text
nginx-report [OPTIONS] [INPUT]...
```

With no `INPUT`, the command reads stdin. One or more paths are processed in
order. A literal `-` means stdin and cannot be repeated. There are no
subcommands and no tail/follow mode in the MVP.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | false | Emit normalized CSV rows; mutually exclusive with `--json` |
| `--no-color` | false | Disable terminal color; accepted but redundant in JSON/CSV |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive cardinality cap; invalid values are usage errors |
| `--gzip / --no-gzip` | auto by `.gz` suffix | Explicitly enable/disable gzip decoding for all named files; stdin requires explicit `--gzip` |
| `--version` | — | Print version and exit 0 |
| `--help` | — | Print Click help and exit 0 |

### Inputs

- Named regular files, gzip files under the policy above, or stdin.
- UTF-8 standard nginx combined access-log lines.
- Pipelines must pass `-` or omit all paths; stdin is never implicitly mixed
  with named files.

### Outputs

Normal data is written only to stdout. Warnings and errors are written only to
stderr. Terminal mode uses Rich tables and color only when stdout is a TTY and
`--no-color` is absent. JSON and CSV never include ANSI escapes.

JSON top-level schema:

```json
{
  "schema_version": 1,
  "input": {"valid_lines": 0, "invalid_lines": 0},
  "top_ips": [{"ip": "string", "request_count": 0}],
  "top_error_urls": [{"url": "string", "error_count": 0, "client_error_count": 0, "server_error_count": 0}],
  "hourly_distribution": [{"hour": 0, "request_count": 0, "percentage": 0.0}],
  "user_agents": {"unique_count": 0, "share_percentage": 0.0}
}
```

CSV always writes this header:

```text
section,rank,key,request_count,percentage,client_error_count,server_error_count,valid_line_count,invalid_line_count
```

It then writes one `input_summary` row followed by `top_ip`, `top_error_url`,
`hour`, and `user_agent_summary` rows in that order. The summary row carries
the valid and invalid line counts. Non-applicable cells are empty; `key`
contains the IP, URL, zero-padded hour, or `unique` respectively. CSV quoting
follows Python's `csv` module and output uses `\n` line endings.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Report completed, or `--help`/`--version` completed |
| `1` | Operational failure: input open/read/decode, gzip, unexpected processing, or stdout write failure |
| `2` | Click usage error: invalid/mutually exclusive options, invalid cap, repeated stdin |
| `3` | Parse exhaustion: processing reached EOF with zero valid records |
| `4` | Unique-cardinality exhaustion: distinct User-Agents would exceed the configured cap |

On codes 1, 2, 3, or 4, no partial JSON/CSV/terminal report is written.

## 8. Data and Persistence

There is no database, schema, migration, cache, or durable application state.
In-memory state consists only of counters, a 24-element integer array, the
exact User-Agent set, source diagnostics, and scalar totals. State is released
when the process exits. The input logs remain the user's source of truth.

Database-table requirements from generic service templates are intentionally
not applicable: inventing three tables would violate the approved design and
create data-retention and privacy obligations with no product requirement.

## 9. API, Authentication, and Trust Boundaries

There are no HTTP endpoints, sockets, credentials, users, sessions, tokens, or
authorization roles. The complete public API is the CLI interface above.
Generic endpoint and authentication-flow template sections are intentionally
not applicable.

The OS account invoking the program governs file access. Log content is
untrusted data: it is never evaluated as code, passed to a shell, interpreted
as Rich markup, or interpolated into diagnostics without escaping. Output may
contain sensitive IPs, URLs, and User-Agents and is written only to the
caller-selected stdout destination. The tool has no telemetry or egress.

## 10. Configuration and Environment

There are no required environment variables or configuration files. CLI
arguments are the only runtime configuration. Standard environment variables
that Python/Click may honor are not part of the product contract; behavior and
tests must not depend on them.

## 11. Packaging and Deployment

The deployment target is a local Python 3.11 environment. `pyproject.toml`
declares runtime dependencies, the `src` package, version metadata, and the
`nginx-report = nginx_report.cli:main` console script. Users install from a
local checkout or, after release, from PyPI with pip.

Docker, Compose, a server process, cloud resources, and Kubernetes are not
used. A container would obscure stdin/file mounts and add no portability value
beyond the approved pip installation. Release artifacts are source and wheel
distributions built reproducibly by the packaging toolchain.

## 12. Performance and Resource Strategy

- Complexity is O(n + u log u + e log e) time at finalization, where `n` is
  valid lines and `u`/`e` are distinct IP/error-URL keys; streaming work is O(n).
- Input memory is O(1); aggregate memory is O(u + e + a), where `a` is distinct
  User-Agents capped by the CLI option.
- Parsing regexes are compiled once. The hot loop uses standard-library data
  structures and performs no rendering, logging, sorting, or JSON work.
- `Counter.most_common` is not the tie-order contract by itself; selection
  uses a bounded deterministic key so identical counts are ordered lexically.
- The 1 GB/30 s target is a release gate measured after correctness. The
  benchmark records hardware, OS, Python, cold/warm cache status, fixture
  cardinalities, wall time, peak RSS, and command.

The target is not a claim about every possible log. Adversarially high distinct
IP/URL cardinality can consume memory; this is documented and exercised in
stress tests. Unique User-Agent growth receives the dedicated exit-4 guard.

## 13. Error Handling and Observability

Diagnostics are concise, prefixed with `nginx-report:`, and never include ANSI
in non-TTY stderr. At successful completion, `valid_lines` and `invalid_lines`
appear in every report. Individual malformed lines are not printed by default,
preventing stderr floods and accidental disclosure; a final warning reports
their count. Broken-pipe/stdout failures map to exit 1 without a traceback.
Unexpected failures map to exit 1 with a concise message; developer tracebacks
belong in tests, not the stable interface.

## 14. Testing Strategy

| Layer | Evidence |
|---|---|
| Parser unit tests | IPv4/IPv6, escapes, query strings, offsets, 4xx/5xx, malformed/UTF-8 cases |
| Aggregator unit tests | all metric formulas, ties, 24 buckets, cap boundary and exhaustion |
| Presenter golden tests | ANSI policy, stable JSON fields/types, normalized CSV quoting/order |
| Click integration tests | files/stdin/gzip, mutual exclusion, stderr separation, exit `0/1/2/3/4` |
| Property tests where useful | count conservation and hourly percentages over generated valid records |
| Performance test | representative 1 GB fixture under 30 seconds with recorded peak RSS |
| Packaging smoke test | clean Python 3.11 venv, wheel install, help, one fixture report |

## 15. Architecture Decision Records

### ADR-001: Single process and no persistence

- **Status:** Accepted (pre-approved product constraint)
- **Decision:** Use the layered single-process streaming architecture; do not
  add a database or HTTP API.
- **Consequences:** Minimal setup and privacy surface; repeat analysis rereads
  the log; distinct-key counters remain memory-resident.

### ADR-002: Exact metrics with a User-Agent safety cap

- **Status:** Accepted
- **Decision:** Keep exact counters and an exact UA set; fail with code 4 when
  the configured unique-UA cap would be exceeded.
- **Consequences:** Reproducible results and an explicit failure boundary;
  highly diverse inputs may require a larger cap and more RAM.

### ADR-003: Stable normalized CSV

- **Status:** Accepted
- **Decision:** Represent heterogeneous report sections in one row schema with
  a `section` discriminator.
- **Consequences:** One stdout stream works in pipelines; consumers must filter
  by section and tolerate empty non-applicable cells.

No adversarial or independent architecture review is recorded here; that
review is intentionally assigned to the external harness in a separate session.
