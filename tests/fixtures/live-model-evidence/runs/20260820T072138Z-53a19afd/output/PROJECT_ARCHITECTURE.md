# Project Architecture: nginx Stream Analytics CLI

## 1. Context and Quality Drivers

This is a local, pip-installable Python 3.11 CLI for DevOps/SRE incident analysis. It performs one sequential pass over nginx combined-format access logs and emits four aggregations in terminal, JSON, or CSV form.

Quality drivers, in priority order:

1. Correct, deterministic metrics and machine-output schemas.
2. Streaming performance: a representative 1 GB log in under 30 seconds on a documented laptop.
3. Predictable automation behavior through the complete `0/1/2/3/4` exit-code contract.
4. Bounded operational behavior on malformed or adversarial input.
5. Small, maintainable dependency and deployment surface.

## 2. Architecture Decision

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Both constraints are correct because every report is derived completely from one input stream and has no value that requires durable storage. A database would add writes, schema lifecycle, disk amplification, and cleanup while violating the $0, local, one-weekend goal. An HTTP API would require a long-running server, network/security lifecycle, serialization transport, and deployment model even though the only consumers are a person at a terminal or a Unix pipeline. File/stdin input plus stdout/stderr output is the smallest complete interface.

The approved architecture is a single OS process with a sequential parsing loop. It is an obvious fit for a solo, time-boxed CLI and therefore does not require an architecture-choice pause.

### Considered approaches

| Approach | Decision | Trade-off |
|---|---|---|
| Single-process exact streaming aggregation | **Selected** | Minimal operation and deterministic exact metrics; memory grows with distinct IPs, error URLs, and User-Agents, so cardinality must be guarded |
| Multi-process chunk parsing | Rejected for MVP | May improve CPU throughput, but merging counters, splitting lines, ordering errors, and benchmark variability add weekend-scale risk |
| External sort / temporary SQLite | Rejected | Can bound RAM for extreme cardinality, but adds disk I/O and violates the approved stateless/no-database decision |
| Persistent observability service | Rejected | Supports history and dashboards but contradicts the local CLI product |

## 3. Component Model

```text
file path or stdin
        |
        v
 Input opener ----> line iterator
                        |
                        v
                  nginx parser ---- malformed counter
                        |
                 valid LogRecord
                        |
                        v
               streaming Aggregator
          +-------------+-------------+-------------+
          |             |             |             |
       IP counts   error URL counts  hour counts  User-Agent set
          +-------------+-------------+-------------+
                        |
                   Report dataclasses
                        |
             +----------+----------+
             |          |          |
          Rich text    JSON        CSV
             +----------+----------+
                        |
                  stdout / exit code
```

The Click command is the composition root. It opens the input, creates parser and aggregator objects, processes lines, finalizes immutable report dataclasses, selects one renderer, and maps typed failures to stderr messages and exit codes.

## 4. Module and File Layout

```text
pyproject.toml
src/nginx_stream_report/
  __init__.py              # package version only
  cli.py                   # Click command, option validation, failure mapping
  input.py                 # stdin/plain-file opener and optional gzip opener
  parser.py                # combined-format parser -> LogRecord | malformed result
  models.py                # LogRecord, RankedItem, HourBucket, Report dataclasses
  aggregate.py             # one-pass counters, cardinality checks, report finalization
  renderers/
    __init__.py            # renderer protocol/factory
    terminal.py            # Rich tables and summary
    json.py                # stable JSON object
    csv.py                 # normalized CSV rows
tests/
  fixtures/                # small deterministic logs and expected outputs
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_renderers.py
  test_performance.py
```

Dependencies point inward: `cli` may depend on all application modules; renderers and aggregation depend on `models`; parsing depends only on `models` and the standard library. Domain modules never import Click or Rich.

## 5. Domain Data Contracts

The implementation uses frozen, slotted dataclasses where practical:

| Dataclass | Fields | Contract |
|---|---|---|
| `LogRecord` | `client_ip: str`, `timestamp: datetime`, `request_target: str`, `status: int`, `user_agent: str | None` | One syntactically valid combined-format line; request target is the URL/path token from the quoted request line, including query string |
| `RankedItem` | `value: str`, `count: int`, `rank: int` | Rank is 1-based; ordering is count descending then value ascending |
| `HourBucket` | `hour: int`, `request_count: int`, `percentage: float` | Hour is `0..23`; all 24 buckets are emitted in ascending order |
| `Report` | `schema_version: int`, `total_lines: int`, `valid_requests: int`, `malformed_lines: int`, `top_ips: tuple[RankedItem, ...]`, `top_error_urls: tuple[RankedItem, ...]`, `hourly_distribution: tuple[HourBucket, ...]`, `unique_user_agents: int`, `unique_user_agent_share: float` | Complete renderer-independent result |

Metric rules:

- Top IPs count every valid record and return at most 10 entries.
- Top error URLs count records with status `400..599` and return at most 10 entries. Client errors and server errors are combined.
- Hourly distribution groups by the wall-clock hour encoded in each nginx timestamp, across all dates and offsets. Each bucket is a percentage using exactly `100 × hourly_request_count / total_valid_requests`; this is a percentage, not an unscaled fraction. When there are no valid requests, no report is emitted and exit code `3` is returned.
- Unique User-Agent share is `100 × distinct_non_placeholder_user_agent_count / total_valid_requests`. The nginx placeholder `-` and an empty value are not distinct agents, but their requests remain in the denominator. The displayed/serialized percentage is rounded to two decimal places; internal calculation uses integer counts and full floating-point precision until rendering.
- Top-list ties are deterministic: count descending, then UTF-8 string value ascending.

## 6. Streaming and Resource Model

The input is opened in binary mode and decoded line-by-line as UTF-8 with replacement for invalid byte sequences. The parser uses one precompiled regular expression matching nginx combined format, then parses only the fields required by the report. A malformed line increments `malformed_lines` and processing continues.

State retained for the full stream is limited to:

- `Counter[str]` for client IPs;
- `Counter[str]` for error request targets only;
- a fixed 24-element integer array for hourly counts;
- `set[str]` for distinct non-placeholder User-Agents;
- scalar line and validity counts.

Exact top-10 results require exact counts, so IP and error-URL counter cardinality are monitored and documented as performance assumptions. Exact User-Agent distinctness is protected by `--max-unique-user-agents` (default `1_000_000`). Exceeding it stops processing with exit code `4`; approximation or silent eviction is forbidden. The performance fixture must include realistic, bounded cardinality and record its distinct counts alongside elapsed time and peak RSS.

No input contents, aggregates, or temporary files persist after process exit.

## 7. Parsing Contract

Supported MVP input is nginx's conventional combined access-log format:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

The request field must contain a method, request target, and protocol separated by spaces; the request target is extracted without URL-decoding. IPv4 and IPv6 text are accepted as opaque non-space client identifiers. Status must be a three-digit integer. Timestamp parsing accepts nginx's `%d/%b/%Y:%H:%M:%S %z` form. Extra data outside the combined-format contract is malformed.

Input errors (missing file, directory path, unreadable file, decode/open failure) are distinct from malformed content. A mix of valid and malformed records succeeds and reports the malformed count. An input with lines but zero valid records returns `3` and emits no partial report.

## CLI Interface

### Command

```text
nginx-stream-report [OPTIONS] [INPUT]
```

`INPUT` is an optional path. Omitted input or `INPUT` equal to `-` reads stdin. Exactly one input stream is processed per invocation.

### Options

| Option | Meaning | Default / validation |
|---|---|---|
| `--json` | Emit one JSON document | Mutually exclusive with `--csv` |
| `--csv` | Emit normalized CSV records | Mutually exclusive with `--json` |
| `--max-unique-user-agents INTEGER` | Exact distinct-agent safety ceiling | `1_000_000`; integer >=1 |
| `--color / --no-color` | Force or disable ANSI color in terminal mode | Auto: color only for a capable TTY and when `NO_COLOR` is absent |
| `--version` | Print version and exit | Click eager option |
| `--help` | Print usage and exit | Click eager option |

### Inputs

- Plain-text combined-format log by path.
- Standard input, including pipelines and `-`.
- Gzip-by-suffix (`.gz`) is a P1/Should extension, not required for MVP acceptance.

### Outputs

- Default: four Rich report sections plus total/valid/malformed counts. Human formatting goes to stdout; diagnostics go to stderr.
- JSON: UTF-8 JSON object with the exact `Report` field names, nested ranked items/hour buckets, numeric counts, numeric percentages, and `schema_version: 1`. No ANSI escapes.
- CSV: UTF-8 with header `section,rank,key,count,percentage`. Ranked sections use rank/key/count; all 24 hourly rows use key `00` through `23`, count, and percentage; the unique-agent summary uses key `unique_user_agents`, count, and percentage. No ANSI escapes.
- Successful empty error ranking is represented by an empty JSON list, no ranked CSV rows for that section, and an explicit empty-state terminal message.
- Broken-pipe shutdown after a downstream consumer closes stdout is quiet and does not print a traceback.

### Exit-code contract

| Code | Meaning |
|---:|---|
| `0` | Report completed successfully, including inputs containing both valid and malformed lines |
| `1` | Unexpected internal error |
| `2` | CLI usage or input I/O error: invalid option combination/value, missing/unreadable input, or stream read failure |
| `3` | Data error: processing completed or reached EOF with zero valid nginx records |
| `4` | Unique-cardinality exhaustion: adding another distinct User-Agent would exceed `--max-unique-user-agents` |

Only the selected report format is written to stdout. Usage, input, data, cardinality, and internal-error messages go to stderr. Expected failures never include a Python traceback.

## 9. Output Stability and Versioning

Terminal layout may gain non-breaking decoration, but metric names and meanings are stable. JSON's `schema_version` begins at `1`; removing/renaming fields or changing semantics requires a version increment. CSV column order and section keys are a public contract. Numeric percentages use JSON numbers and decimal CSV fields, always rounded to two decimal places at serialization.

Locale does not change timestamps, sort order, decimal separators, headers, or keys. Output ends with one newline.

## 10. Errors, Logging, and Security

The tool does not log raw lines or User-Agent values to stderr on failure, limiting accidental leakage. It never interprets request targets or User-Agents as markup, shell syntax, paths, or Rich markup. Terminal cells are rendered as text with markup disabled/escaped, and control characters are normalized to visible safe replacements.

Input paths are user-selected local resources; the tool performs read-only sequential access. There are no credentials, authentication flows, environment secrets, outbound network calls, plugins, subprocesses, or dynamic code execution. `NO_COLOR` is the only behavior-affecting environment variable.

## 11. Persistence, API, Authentication, and Deployment

### Database

None. There are no tables, migrations, indexes, caches, or persisted report records. In-memory Python collections exist only for the invocation lifetime. This explicit absence is required by the decision in Section 2.

### HTTP API

None. There are no endpoints, ports, request/response bodies, server framework, or network protocol. The complete public integration surface is under `## CLI Interface`.

### Authentication

None. The process runs with the invoking user's local file permissions and does not create an identity or authorization boundary.

### Environment variables

| Variable | Meaning | Example |
|---|---|---|
| `NO_COLOR` | Any present value disables ANSI color unless an explicit product policy chooses to make `--color` authoritative; tests freeze the chosen precedence | `1` |

No `.env` file is loaded.

### Deployment

Publish a pure-Python wheel and source distribution installable with pip on Python 3.11. The console-script entry point is `nginx-stream-report`. Docker, Docker Compose, Kubernetes, a VPS, serverless infrastructure, and cloud resources are unnecessary because there is no service to deploy. Release validation uses a fresh local virtual environment.

## 12. Performance Verification

The benchmark generates or references a deterministic representative 1 GB combined-format fixture outside Git, then records fixture generation parameters, byte count, valid/malformed ratio, distinct cardinalities, Python version, OS, CPU, RAM, elapsed wall-clock time, and peak RSS. The timed command redirects output to a file or null sink so terminal rendering does not dominate parsing measurement.

Acceptance requires under 30 seconds on the documented reference laptop. Run at least one warm-up and three measured iterations; use the median for acceptance and retain all results. Correctness is checked against independently derived expected totals before the timing is accepted. A smaller committed smoke benchmark catches gross regressions in routine tests.

## 13. Architectural Runway and Evolution Boundaries

The runway is intentionally small: package layout, typed domain records, parser fixtures, renderer-independent report objects, and benchmark instrumentation. P1 gzip support belongs in `input.py` and must not affect aggregation. P2 format support should add a parser implementation behind the same `LogRecord` contract.

The following require a new product/architecture decision and are not incremental MVP work: approximate cardinality, persistence, cross-file history, tail-follow mode, multiprocessing, an HTTP service, authentication, cloud deployment, or Kubernetes.
