# Project Architecture: nginx-report

## 1. Context and Constraints

`nginx-report` is a pip-installable Python 3.11 CLI that reads nginx combined access logs as a stream and emits a deterministic summary. It targets local DevOps/SRE use, a $0 budget, and one-weekend delivery. The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema lifecycle, disk amplification, cleanup, and privacy exposure to a one-shot computation whose complete result can be derived from the current input. An HTTP API would add a server lifecycle, network attack surface, authentication questions, deployment, and concurrency concerns while making shell pipelines harder. The CLI already supplies the appropriate process boundary, stdin/file input, stdout data, stderr diagnostics, and exit status.

Explicit exclusions are authentication, database/storage, HTTP API, daemon/server, cloud services, containers as a runtime requirement, and Kubernetes. The process performs no network calls and persists nothing.

## 2. Architecture Decision

The pre-approved architecture is one local process with small internal modules:

```text
file or stdin
     |
     v
byte/text iterator -> combined-log parser -> valid LogRecord stream
                                             | invalid counter
                                             v
                                      StreamingAggregator
                                      /      |       \
                              Counters   24 buckets   UA set
                                      \      |       /
                                        Report model
                                      /      |       \
                                Rich text   JSON     CSV
                                      \      |       /
                                   stdout; diagnostics -> stderr
```

The process retains aggregate counts, not log records. Runtime is `O(n)` in input lines; memory is `O(u_ip + u_error_target + u_user_agent)`, plus 24 hourly buckets. Exact top values and exact unique share require exact counts/sets. A configurable cardinality guard bounds failure behavior rather than silently switching to approximate results.

### Considered and Rejected Alternatives

| Alternative | Benefit | Reason rejected for the MVP |
|---|---|---|
| Multi-process parsing | Potential use of multiple CPU cores | Chunk boundaries, ordering, merge overhead, and stdin behavior add complexity before profiling proves a need |
| SQLite-backed aggregation | Bounded Python heap and durable intermediate data | Violates statelessness and adds I/O/schema cost for ephemeral results |
| Go implementation | Strong raw throughput and single-binary distribution | Contradicts the approved Python 3.11 stack and one-weekend delivery plan |
| Hosted/API service | Shared access and central operation | Violates local-only, $0, no-auth, no-server constraints |

## 3. Technology Stack

| Layer | Technology | Responsibility |
|---|---|---|
| Runtime | CPython 3.11 | Execution platform |
| CLI | Click | Command/options, usage validation, console entry point |
| Terminal | Rich | Human-readable TTY tables and color |
| Models | Python `dataclasses` | Parsed record, aggregate report, and report rows |
| Core | Standard library | `collections.Counter`, `set`, datetime parsing, JSON/CSV primitives |
| Packaging | `pyproject.toml` with a PEP 517 backend | Wheel/sdist and `nginx-report` console script |
| Tests | pytest and coverage tooling | Unit, integration, CLI, schema, and benchmark checks |

## 4. Repository Structure

```text
pyproject.toml
src/nginx_report/
  __init__.py
  cli.py                 # Click command, stream ownership, exit mapping
  models.py              # LogRecord, Report, RankedRow dataclasses
  parser.py              # combined-log parsing and ParseResult
  aggregate.py           # one-pass counters, buckets, cardinality guard
  renderers/
    __init__.py
    text.py              # Rich terminal report
    json.py              # stable JSON document
    csv.py               # normalized CSV rows
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_render_json.py
  test_render_csv.py
  test_cli.py
  test_performance.py
```

No product code exists during blueprinting; these are planned paths.

## 5. Data Contracts

### Supported Input Grammar

The MVP supports nginx's standard combined log shape:

```text
remote_addr - remote_user [time_local] "request" status body_bytes_sent "http_referer" "http_user_agent"
```

Required parsed fields are:

| Field | Type | Rule |
|---|---|---|
| `remote_addr` | `str` | Non-empty token; IPv4, IPv6, or nginx-provided address text |
| `timestamp` | timezone-aware `datetime` | `%d/%b/%Y:%H:%M:%S %z`; hour normalized to UTC |
| `request_target` | `str` | Middle token from request line; retained verbatim, including query string |
| `status` | `int` | Three-digit `100..599` |
| `user_agent` | `str | None` | `-` becomes `None`; otherwise unescaped quoted value |

A line is valid only when all required fields except User-Agent parse successfully. The request line must contain method, target, and protocol tokens. Metrics use valid records only. Invalid lines increment `invalid_line_count` and produce no partial record.

### Metric Definitions

- **Top IPs:** the ten `remote_addr` values with the highest count among valid requests.
- **Top error URLs:** the ten verbatim request targets with the highest count among valid requests whose status is `400..599`.
- **Hourly request distribution:** 24 UTC-hour buckets (`00` through `23`). Each percentage is exactly `100 × hourly_request_count / total_valid_requests`; when there are no valid requests, every percentage is `0.0`.
- **Share of unique User-Agents:** `100 × distinct_nonempty_user_agent_count / total_valid_requests`; `-` is excluded from the numerator but its otherwise-valid request remains in the denominator. The value is `0.0` when there are no valid requests.
- **Tie-breaking:** count descending, then key ascending by Unicode code point. This applies identically to text, JSON, and CSV.
- **Precision:** internal percentages use full Python float precision; text displays two decimal places, JSON emits numbers, and CSV emits six decimal places.

### In-memory Dataclasses

| Dataclass | Fields |
|---|---|
| `LogRecord` | `remote_addr: str`, `timestamp: datetime`, `request_target: str`, `status: int`, `user_agent: str | None` |
| `RankedRow` | `rank: int`, `key: str`, `count: int` |
| `HourlyRow` | `hour_utc: int`, `count: int`, `percentage: float` |
| `Report` | `total_lines: int`, `valid_requests: int`, `invalid_lines: int`, `top_ips: tuple[RankedRow, ...]`, `top_error_urls: tuple[RankedRow, ...]`, `hourly_distribution: tuple[HourlyRow, ...]`, `distinct_user_agents: int`, `unique_user_agent_share: float` |

There are no database tables, migrations, indexes, ORM models, or persisted records. The data structures above are the complete state model.

## 6. Processing Pipeline

1. Click validates mutually exclusive output flags and numeric limits before opening input.
2. The input adapter iterates one text line at a time from a named file or stdin using UTF-8 with replacement for undecodable bytes.
3. The parser returns either a complete immutable `LogRecord` or an invalid marker.
4. The aggregator increments total/valid/invalid counts, the IP counter, an error-target counter for 4xx/5xx, one UTC-hour bucket, and the non-empty User-Agent set.
5. Before inserting a new distinct IP, error target, or User-Agent, the aggregator enforces `--max-unique`; exhaustion stops processing without a report.
6. At end of stream, the aggregator creates the immutable `Report`, sorting only the aggregate keys needed for deterministic top-ten output.
7. Exactly one renderer writes the report to stdout. Warnings and failures go only to stderr.

No raw log line is retained after parsing. No renderer reparses input.

## CLI Interface

### Command

```text
nginx-report [OPTIONS] [INPUT]
```

`INPUT` is one nginx combined access-log file path. If omitted or `-`, input is read from stdin. The command reads a non-seekable stream in one pass and never closes caller-owned stdin.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | off | Emit one UTF-8 JSON object; mutually exclusive with `--csv` |
| `--csv` | off | Emit normalized RFC 4180-compatible CSV; mutually exclusive with `--json` |
| `--top INTEGER` | `10` | Number of ranked IP and error-URL rows; must be `1..1000` |
| `--max-unique INTEGER` | `2000000` | Maximum distinct keys in each exact IP, error-target, or User-Agent structure; positive integer |
| `--no-color` | off | Disable Rich color; ignored semantically by JSON/CSV |
| `--version` | n/a | Print version and exit `0` |
| `--help` | n/a | Print usage and exit `0` |

Default output is colored Rich terminal text only when stdout is a TTY and `NO_COLOR` is absent; redirection automatically disables color. JSON and CSV never contain ANSI escapes. Locale does not affect ordering or decimal separators.

### Output Contracts

Text contains a summary followed by Top IPs, Top 4xx/5xx URLs, Hourly UTC Distribution, and User-Agent Diversity sections. A nonzero invalid-line count is visible in the summary and produces one concise stderr warning, but does not by itself make the run fail if at least one valid request exists.

JSON schema:

```json
{
  "schema_version": 1,
  "summary": {"total_lines": 0, "valid_requests": 0, "invalid_lines": 0},
  "top_ips": [{"rank": 1, "ip": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"rank": 1, "url": "/missing", "count": 1}],
  "hourly_distribution": [{"hour_utc": 0, "count": 0, "percentage": 0.0}],
  "user_agents": {"distinct_nonempty": 0, "unique_share_percentage": 0.0}
}
```

`hourly_distribution` always has 24 ordered entries. Ranked arrays may be empty and never exceed `--top`.

CSV has the fixed header `section,rank,key,count,percentage`. It emits `summary` rows for totals, ranked `top_ip` and `top_error_url` rows, 24 `hourly_utc` rows, and `user_agent` rows for distinct count and unique-share percentage. Non-applicable cells are empty; fields are escaped by Python's CSV writer.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Successful report, including an empty input stream |
| `1` | Input/output or unexpected runtime failure, including a missing/unreadable file or broken renderer |
| `2` | Click usage error: invalid option/value, incompatible output flags, or extra arguments |
| `3` | Parsing failure: input is non-empty but contains zero valid requests |
| `4` | Unique-cardinality exhaustion: a new distinct IP, error target, or User-Agent would exceed `--max-unique` |

On codes `1`, `2`, `3`, or `4`, stdout contains no report. Diagnostics are concise and written to stderr without a traceback unless a future explicit debug mode is added.

## 8. Module Responsibilities

| Module | Owns | Must not own |
|---|---|---|
| `cli.py` | Option validation, streams, renderer selection, exception-to-exit mapping | Parsing grammar or metric calculations |
| `parser.py` | One-line grammar and typed conversion | Counters, output, or process exit |
| `aggregate.py` | Metric state, cardinality guard, deterministic report construction | Click or Rich objects |
| `models.py` | Typed immutable cross-module contracts | I/O or behavior |
| `renderers/*` | Serialization/presentation only | Metric recomputation or stderr policy |

Dependencies point inward: CLI and renderers depend on models/core; parser and aggregator do not depend on Click or Rich. This keeps core tests fast and makes output contracts independently testable.

## 9. Failure, Security, and Privacy

- Input is untrusted data, never executed or interpolated into a shell command.
- Rich markup escaping is mandatory for log-derived values to prevent terminal markup injection.
- JSON and CSV use standard serializers, not manual string concatenation.
- The parser has a maximum accepted line length of 1 MiB; longer lines are invalid, preventing a single pathological record from dominating memory.
- The cardinality guard fails closed with code `4`; it never labels an approximate result as exact.
- No logs, summaries, telemetry, or crash data leave the process or persist automatically.
- Broken pipes are treated as output failure (`1`) without traceback noise.

## 10. Performance and Capacity

The acceptance baseline is a generated, versioned-shape 1 GB combined-format log on a documented laptop, run from a local SSD with a warm-up excluded. The measured command records wall time, CPU time, peak RSS, Python version, and input characteristics. Release acceptance requires wall time under 30 seconds and peak RSS under 512 MiB for the representative cardinality profile.

Performance design rules:

- compile parsing primitives once;
- avoid `split()` of the entire input or retaining raw lines;
- update primitive counters directly;
- defer ranking and percentage construction until EOF;
- benchmark text output to a file or `/dev/null` separately from parser-only profiling;
- test high-cardinality exhaustion independently from the representative benchmark.

## 11. Packaging and Local Operation

`pyproject.toml` declares Python `>=3.11,<4`, Click and Rich runtime dependencies, and the `nginx-report = nginx_report.cli:main` console script. The release artifact is a wheel installable with pip in a local virtual environment. There is no Docker image, compose file, service unit, deployment target, environment file, or secret. Optional behavior is controlled only by CLI options and the conventional `NO_COLOR` environment variable.

## 12. Testing Strategy

- Parser table tests cover IPv4/IPv6, escaped quotes, `-` User-Agent, query strings, all status classes, timezone offsets, malformed records, and overlong lines.
- Aggregator tests prove exact totals, error filtering, UTC-hour normalization, the literal percentage formula, deterministic ties, zero-valid behavior, and cardinality failure.
- Renderer golden tests prove schema, escaping, 24-hour presence, precision, and absence of ANSI in JSON/CSV.
- Click tests prove stdin/file parity, stream separation, `--json`/`--csv` exclusion, range validation, and the complete `0/1/2/3/4` exit contract.
- Package smoke tests build a wheel, install it into a fresh Python 3.11 environment, and invoke `--help` plus a fixture report.
- A performance test is opt-in for local release verification, not a flaky per-commit unit test.

## 13. Architecture Decisions Summary

| Decision | Status | Consequence |
|---|---|---|
| Single local Python process | Accepted and pre-approved | Minimal operational footprint; profile before parallelizing |
| Exact aggregates with guard | Accepted | Deterministic metrics; memory proportional to cardinality; code `4` on exhaustion |
| Combined format only in MVP | Accepted | Clear parser contract; custom formats deferred |
| UTC hourly buckets | Accepted | Comparable results across offsets; explicitly differs from source-local hour |
| Verbatim request target | Accepted | No hidden normalization; query strings can increase cardinality |
| No database and no HTTP API | Accepted | Stateless, offline, pipeline-native execution |

No adversarial or independent review is recorded in this document; that review is outside this session by instruction.
