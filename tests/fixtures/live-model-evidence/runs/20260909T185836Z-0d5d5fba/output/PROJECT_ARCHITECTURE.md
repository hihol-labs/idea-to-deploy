# Project Architecture: Nginx Pulse

## 1. Architectural Context

Nginx Pulse is one Python 3.11 process that reads nginx access-log records sequentially, updates in-memory aggregates, freezes a result dataclass, and renders that result once. It has no background worker, network listener, persistent state, or external runtime dependency beyond Click and Rich.

**"no database — stateless streaming processing; no HTTP API — CLI-only tool"**

Both constraints are correct here. A database would add writes, schema lifecycle, cleanup, and operational cost while the required result is derived from one input stream and discarded after output. An HTTP API would introduce a server, authentication and network attack surface without helping the intended local shell workflow. The single process gives the shortest data path and makes stdin, files, exit codes, and backpressure native operating-system concerns.

The explicit stack and solo, one-weekend scope make a single-process architecture the pre-approved obvious choice. Architecture variants are therefore not offered: a service, database-backed design, or distributed pipeline would violate product constraints rather than represent a viable alternative.

## 2. System Context

```text
nginx log file ─┐
                ├─> Click CLI -> line reader -> parser -> aggregator -> result
stdin stream ───┘                                               |
                                                             renderer
                                                    ┌──────────┼──────────┐
                                                    v          v          v
                                              Rich text      JSON       CSV
                                              (stdout)     (stdout)    (stdout)

diagnostics ----------------------------------------------------> stderr
process outcome ------------------------------------------------> exit code
```

There is exactly one bounded read-ahead line. Counters live only for the process lifetime. Output is written after input completes so renderer choice cannot change metric calculation.

## 3. Package Structure

```text
pyproject.toml
src/nginx_pulse/
  __init__.py          # package version
  __main__.py          # python -m nginx_pulse entry
  cli.py               # Click command, validation, stream ownership, exit mapping
  models.py            # LogRecord, AnalysisResult, RankedItem dataclasses
  parser.py            # combined-log parsing and timestamp/status validation
  aggregate.py         # streaming accumulator and deterministic ranking
  render/
    __init__.py
    text.py            # Rich terminal renderer
    json.py            # stable JSON serializer
    csv.py             # stable long-form CSV serializer
tests/
  fixtures/
  unit/
  integration/
  performance/
```

Dependency direction is `cli -> parser + aggregate + render`, `aggregate -> models`, and `render -> models`. Parser and render modules do not import Click. The domain layer does not import Rich.

## 4. Components and Data Flow

1. `cli.py` validates mutually exclusive output modes and opens either a UTF-8 text file or stdin without closing caller-owned stdin.
2. `parser.py` consumes one physical line and returns either an immutable `LogRecord` or a typed parse failure.
3. `aggregate.py` records the line outcome, increments total valid requests, IP count, error-URL count for status 400–599, hourly count, and the exact User-Agent set.
4. The aggregator rejects a new distinct User-Agent once the configured ceiling would be exceeded; it does not emit an approximation.
5. At end-of-stream, the accumulator creates one `AnalysisResult`, calculating percentages only when total valid requests is nonzero.
6. The chosen renderer writes the result to stdout. Diagnostics and the malformed-line summary go to stderr when applicable.

The top-10 lists sort by count descending and then key ascending, making ties deterministic across platforms and renderers.

## 5. Domain Model

All structures are standard-library dataclasses.

| Dataclass | Field | Type | Invariant |
|---|---|---|---|
| `LogRecord` | `ip` | `str` | Non-empty parsed client token |
| `LogRecord` | `timestamp` | `datetime` | Offset-aware timestamp parsed from nginx combined format |
| `LogRecord` | `method` | `str` | Request method or empty when request field is `-` |
| `LogRecord` | `url` | `str` | Raw request-target token; query string is retained |
| `LogRecord` | `protocol` | `str` | Protocol token or empty |
| `LogRecord` | `status` | `int` | 100–599 |
| `LogRecord` | `user_agent` | `str` | Exact decoded field; `-` is a valid literal value |
| `RankedItem` | `key` | `str` | IP or URL |
| `RankedItem` | `count` | `int` | Positive count |
| `AnalysisResult` | `total_lines` | `int` | Valid plus malformed lines |
| `AnalysisResult` | `total_valid_requests` | `int` | Successfully parsed lines |
| `AnalysisResult` | `malformed_lines` | `int` | Failed lines |
| `AnalysisResult` | `top_ips` | `tuple[RankedItem, ...]` | At most ten |
| `AnalysisResult` | `top_error_urls` | `tuple[RankedItem, ...]` | At most ten, statuses 400–599 only |
| `AnalysisResult` | `hourly_distribution` | `tuple[float, ...]` | Exactly 24 values in hour order |
| `AnalysisResult` | `unique_user_agents` | `int` | Exact distinct count |
| `AnalysisResult` | `unique_user_agent_share` | `float` | Percentage of valid requests |

Hourly request distribution for hour `h` is the percentage `100 × hourly_request_count / total_valid_requests`. When there are no valid requests, every hourly percentage is `0.0`. The unique User-Agent share is `100 × unique_user_agents / total_valid_requests`, or `0.0` for no valid requests. Percentages are rounded only by renderers to two decimal places; internal calculation retains normal Python floating-point precision.

## 6. Parsing Contract

MVP input is nginx's standard combined log shape:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

The parser supports quoted-field backslash escaping, IPv4/IPv6 or hostname client tokens, offset-bearing `%d/%b/%Y:%H:%M:%S %z` timestamps, and `-` placeholders. The URL is the middle request token after the method and before the protocol; a request field of `-` yields an empty method/URL/protocol and remains valid if all other fields validate. Lines with a missing field, invalid timestamp, invalid integer status, status outside 100–599, or invalid UTF-8 are malformed. A final line without a newline is valid.

Timestamps are bucketed by their logged local hour (`00` through `23`); offsets are parsed for validity but not normalized, because the requested view is the server-log hour distribution.

## 7. Aggregation and Resource Model

The scan is `O(n)` in lines. Final ranking costs `O(i log i + u log u)` for distinct IPs `i` and error URLs `u`; only ten items are retained in the result. Working memory is `O(i + u + a)`, where `a` is distinct User-Agent cardinality. This is streaming because records and raw lines are not retained; exact group counts necessarily retain distinct keys for the duration of the process.

The default distinct User-Agent ceiling is 1,000,000 and is configurable downward or upward with `--max-unique-user-agents`. On exhaustion, processing stops before inserting the excess value, no normal report is emitted, a diagnostic is written to stderr, and the process exits 4. This explicit fail-closed behavior prevents a misleading "exact" share or uncontrolled memory growth.

The performance acceptance target is a generated 1 GB representative combined log processed in under 30 seconds on the documented reference laptop, with output redirected. The benchmark records Python version, CPU, storage, input hash, wall time, and peak resident memory.

## CLI Interface

### Command

```text
nginx-pulse [OPTIONS] [INPUT]
python -m nginx_pulse [OPTIONS] [INPUT]
```

There is one command. `INPUT` is an optional path; omission or `-` reads stdin. At most one input is processed per invocation.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit the JSON object schema below; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit the CSV row schema below; mutually exclusive with `--json` |
| `--color / --no-color` | auto | Override color for text only; auto enables color only on a capable TTY |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive ceiling for exact unique User-Agent values |
| `--version` | flag | Print package version and exit 0 |
| `--help` | flag | Print usage and exit 0 |

Unknown options, conflicting format flags, non-positive cardinality limits, and more than one input are usage errors. Output options do not affect aggregation.

### Inputs

- Regular file path, opened as UTF-8 text with strict decoding.
- `-` or omitted path, read from stdin.
- Supported content is the combined-log contract in section 6.
- Compressed files, directory traversal, multiple files, custom format strings, follow/tail mode, and network locations are not interpreted by MVP.

### Outputs

Default text is a Rich report containing a summary, ranked IP table, ranked 4xx/5xx URL table, 24 hourly percentages, and the unique User-Agent count/share. ANSI color is absent when stdout is redirected or `--no-color` is set.

JSON writes one UTF-8 object followed by a newline:

```json
{
  "schema_version": 1,
  "total_lines": 0,
  "total_valid_requests": 0,
  "malformed_lines": 0,
  "top_ips": [{"ip": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"url": "/missing", "count": 1}],
  "hourly_distribution_percent": [{"hour": 0, "percentage": 0.0}],
  "unique_user_agents": 0,
  "unique_user_agent_share_percent": 0.0
}
```

The illustrative arrays above show their member shapes; actual `hourly_distribution_percent` always has 24 members and rankings have zero to ten members.

CSV is UTF-8 RFC 4180 with one header and a long-form schema:

```text
section,rank,key,count,percentage
summary,,total_valid_requests,0,
summary,,malformed_lines,0,
top_ip,1,192.0.2.1,1,
top_error_url,1,/missing,1,
hour,,00,,0.00
unique_user_agent,,unique_user_agents,0,0.00
```

Actual CSV contains both summary rows, zero to ten ranking rows per ranking, 24 hour rows, and one unique-User-Agent row. Fields are quoted by the standard-library CSV writer when required. Machine-readable modes never emit Rich markup or ANSI escapes. Normal output goes only to stdout; diagnostics go only to stderr.

### Exit codes

| Code | Meaning | Output behavior |
|---:|---|---|
| 0 | Success; all lines valid, including an empty input | Complete report on stdout |
| 1 | Input/output runtime failure, including missing/unreadable file, decode failure, broken non-pipeline output, or unexpected internal failure | No guarantee of normal stdout; concise diagnostic on stderr |
| 2 | Click usage error | Usage diagnostic on stderr |
| 3 | Partial analysis because one or more syntactically malformed log lines were skipped | Complete report on stdout plus malformed count/diagnostic on stderr |
| 4 | Unique-cardinality exhaustion | No report; diagnostic on stderr |

The precedence is 2 before processing, then 4 if the cardinality guard trips, then 1 for runtime failure, then 3 for a completed partial analysis, otherwise 0. A downstream pipe closure may terminate quietly using the platform's conventional behavior when it is clearly a consumer close; other write failures map to 1.

## 9. Persistence, API, Authentication, and Environment

### Database

None. There are zero database tables, migrations, files used as state, caches shared across runs, or retention jobs. In-memory dictionaries and a set are ephemeral algorithm state, not persistence.

### HTTP API

None. There are zero endpoints, sockets, request/response bodies, or API-versioning concerns. The complete public interface is `## CLI Interface`.

### Authentication and authorization

None. The process inherits the invoking user's local filesystem permissions and never elevates privileges. It does not collect credentials or identity.

```text
local user -> operating-system file permission check -> nginx-pulse process
           -> no login/session/token flow          -> stdout/stderr
```

### Environment variables

None are read by the application. Locale, terminal capability, and standard streams may influence presentation only as mediated by Python/Rich; metric values and machine-readable schemas remain stable. All supported behavior is controlled by documented CLI options.

## 10. Packaging and Deployment

`pyproject.toml` declares Python `>=3.11,<4`, Click, Rich, and the `nginx-pulse = nginx_pulse.cli:main` console script. The release artifact is a pure-Python wheel and source distribution. Recommended user deployment is `pipx install nginx-pulse`; `python -m pip install nginx-pulse` is supported in an isolated environment.

There is no Dockerfile, Compose file, daemon, cloud deployment, or Kubernetes manifest. Containers add no value to a local CLI and would complicate stdin/file access. Releases are built and tested in CI, but publication requires an explicit maintainer action and token held by the package index workflow, not the application.

## 11. Security and Privacy

- Logs are untrusted input. Parsing is non-evaluating, has no dynamic regular-expression input, and never invokes a shell.
- No log content, telemetry, or identifiers leave the machine.
- Diagnostics avoid echoing complete log lines or User-Agent values; line numbers and reason categories are sufficient.
- JSON/CSV escaping is delegated to standard serializers; Rich receives plain text cells.
- The CLI does not follow URLs or interpret request targets as local paths.
- Cardinality bounds defend the largest unbounded exact set; performance fixtures exercise long fields and high distinctness.

## 12. Observability and Testability

Operators observe totals, malformed count, stderr diagnostics, elapsed time measured externally, and the exit code. There is no application log file. Unit tests cover parsing and aggregation invariants; integration tests run the installed command with file/stdin fixtures and compare stdout, stderr, and exit code; property tests are optional for parser robustness; the performance suite is opt-in and records reproducible metadata.

## 13. Architecture Decision Records

### ADR-001: Single-process streaming CLI

- **Status:** Accepted by the supplied project brief.
- **Decision:** Iterate once over a file or stdin and retain only aggregate keys.
- **Consequences:** Minimal operations and fast startup; exact distinct/group metrics still consume memory proportional to cardinality.

### ADR-002: Exact cardinality with fail-closed ceiling

- **Status:** Accepted.
- **Decision:** Use an exact set and stop with exit 4 at the configured ceiling.
- **Consequences:** Results remain semantically exact; extreme inputs require an explicit higher limit or a future approximate P2 mode.

### ADR-003: One result model, three renderers

- **Status:** Accepted.
- **Decision:** Freeze aggregation into one model before output formatting.
- **Consequences:** Metrics stay consistent across text, JSON, and CSV; results are emitted only after the scan.

### Rejected alternatives

- Go implementation: likely faster but violates the approved Python stack and weekend focus.
- SQLite or another database: provides persistence the product neither needs nor permits.
- REST service: adds lifecycle, security, and deployment work while weakening shell composability.
- Multiprocessing: makes stdin ordering, aggregation, and memory less predictable; profile evidence is required before reconsideration.
- Full Elastic/Logstash integration: duplicates an existing ecosystem and violates the local, $0 operational goal.

No adversarial review is recorded here; that review is intentionally reserved for the external harness. Requirements and priorities remain sourced from `STRATEGIC_PLAN.md` and `PRD.md`; delivery sequencing is in `IMPLEMENTATION_PLAN.md`.
