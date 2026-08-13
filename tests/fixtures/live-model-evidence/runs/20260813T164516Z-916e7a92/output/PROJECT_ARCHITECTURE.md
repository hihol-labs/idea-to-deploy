# Project Architecture: nginx-top

## Architecture Decision

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Both constraints are correct because each invocation analyzes a bounded input stream and returns a report immediately. A database would add schema, migration, storage, cleanup, and privacy obligations without improving the required one-shot metrics. An HTTP API would require a resident server, authentication, request limits, deployment, and a remote trust boundary even though the target user already has local shell access to the log. The appropriate design is one local process whose only durable outputs are those explicitly redirected by the caller.

The approved architecture is a layered single-process Python package. No architecture-variant decision is open: a service, microservice, or persistence variant directly contradicts the approved scope. Relevant product alternatives are compared in `STRATEGIC_PLAN.md`.

## System Context

```text
nginx access-log file ─┐
                      ├─> Click CLI -> byte-line parser -> streaming aggregator
stdin pipeline ───────┘                                  -> report snapshot
                                                              |
                                      ┌───────────────────────┼──────────────────┐
                                      v                       v                  v
                                Rich terminal              JSON stdout        CSV stdout
```

The parser processes one line at a time. The aggregator retains counters and uniqueness keys, never raw lines. Output is rendered only after the stream completes successfully. Diagnostics go to stderr; report data goes to stdout.

## Components and Source Layout

```text
pyproject.toml
src/nginx_top/
├── __init__.py          # package version
├── cli.py               # Click command, option validation, stream lifecycle
├── models.py            # frozen dataclasses: ParsedRequest, Report
├── parser.py            # compiled combined-log parser and parse result/errors
├── aggregate.py         # counters, cardinality guard, report finalization
├── errors.py            # typed application failures and exit-code mapping
└── renderers/
    ├── __init__.py
    ├── terminal.py      # Rich tables and color policy
    ├── json.py          # stable JSON schema
    └── csv.py           # stable long-form CSV schema
tests/
├── fixtures/
├── test_parser.py
├── test_aggregate.py
├── test_cli.py
├── test_renderers.py
└── test_performance.py
benchmarks/
└── generate_log.py      # deterministic representative benchmark fixture generator
```

Dependencies flow inward: renderers and `cli.py` may depend on domain dataclasses; domain and aggregation modules do not depend on Click or Rich. This keeps metric correctness independently testable.

## Data Model and Streaming Algorithm

No database schema or tables exist. Runtime state uses these dataclasses and containers:

| Model/state | Fields | Type/invariant |
|---|---|---|
| `ParsedRequest` | `client_ip`, `path`, `status`, `hour`, `user_agent` | Frozen dataclass; status `100..599`; hour `0..23`; URL is the request-target path/query token |
| `Report` | `total_valid_requests`, `malformed_lines`, `top_ips`, `top_error_urls`, `hourly`, `unique_user_agents`, `unique_user_agent_share` | Frozen dataclass; renderer-neutral finalized values |
| IP counts | client IP → count | `dict[str, int]`; cardinality guarded |
| Error URL counts | URL → count | `dict[str, int]`; only status `400..599`; cardinality guarded |
| Hour counts | hour → count | Fixed list of 24 integers |
| User-Agent set | normalized nonempty UA values | `set[str]`; exact cardinality, guarded |

For each valid line, the aggregator increments `total_valid_requests`, IP count, and one hour bucket. For status 4xx or 5xx it increments the request-target count. A nonempty User-Agent other than `-` is added to the exact set. New keys are admitted only while the combined number of distinct IPs, error URLs, and User-Agents is at or below `--max-unique`; exceeding the limit aborts without emitting a partial report and exits `4`.

Top lists are selected after EOF with `heapq.nsmallest(10, ...)` over keyed counts and a deterministic ordering of count descending, then key ascending. This avoids sorting all keys while preserving stable ties. The hourly report always contains 24 buckets. Hourly percentage is exactly `100 × hourly_request_count / total_valid_requests`. Unique User-Agent share is `100 × distinct_nonempty_user_agents / total_valid_requests`; a valid request whose User-Agent is missing or `-` remains in the denominator and contributes no distinct value.

Time complexity is O(n + u log 10), where n is input lines and u is retained distinct keys. Memory is O(u), capped by `--max-unique`; it is independent of raw input byte size within that explicit cardinality bound.

## Supported Log Format

MVP supports the standard nginx combined access-log shape:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

Parsing rules:

- The regex is compiled once and applied to bytes for throughput.
- `$remote_addr`, the timestamp hour, request token, status, and User-Agent are required fields.
- The request token must contain method, request-target, and protocol; the target is reported without URL decoding or normalization.
- The hour is taken as written in `$time_local`; no timezone conversion occurs.
- Blank and nonmatching lines are malformed, skipped, and counted until `--max-parse-errors` is exceeded.
- If the threshold is exceeded, processing stops and exits `3`; no partial report is written.
- If EOF is reached with zero valid requests, processing exits `3`.

Supporting custom `log_format` values is explicitly outside the MVP. The isolated parser permits a later `--format` extension without changing aggregation or output schemas.

## CLI Interface

### Command

```text
nginx-top [OPTIONS] INPUT
```

`INPUT` is one filesystem path or `-` for stdin. Exactly one input stream is processed per invocation. Shell glob expansion may invoke the command multiple times; multi-file merging is not part of the MVP.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit exactly one JSON document to stdout |
| `--csv` | flag, false | Emit RFC 4180-compatible UTF-8 CSV to stdout |
| `--color / --no-color` | auto for terminal | Force or suppress Rich color; rejected with `--json` or `--csv` when explicitly forced on |
| `--max-parse-errors INTEGER` | `0` | Maximum malformed lines tolerated; nonnegative |
| `--max-unique INTEGER` | `1000000` | Combined distinct IP/error-URL/User-Agent ceiling; positive |
| `--version` | flag | Print version and exit `0` without reading input |
| `--help` | flag | Print help and exit `0` without reading input |

`--json` and `--csv` are mutually exclusive. Click validates option types before opening the input.

### Inputs

- Regular files are opened read-only in binary mode.
- `-` consumes `stdin.buffer`; input need not be seekable and is never reread.
- Directories, nonexistent paths, permissions failures, and read errors are I/O failures.
- Compressed files are not auto-detected in MVP; use `gzip -dc access.log.gz | nginx-top -`.

### Outputs

Default terminal output contains a summary followed by four sections: top client IPs, top 4xx/5xx URLs, all 24 hourly buckets with count and percentage, and unique User-Agent count/share. Color is enabled only on a TTY unless forced. Redirected terminal output remains plain text.

JSON uses this schema (field order is stable for readability but consumers must use keys):

```json
{
  "total_valid_requests": 0,
  "malformed_lines": 0,
  "top_ips": [{"ip": "string", "count": 0}],
  "top_error_urls": [{"url": "string", "count": 0}],
  "hourly_request_distribution": [{"hour": "00", "count": 0, "percentage": 0.0}],
  "unique_user_agents": {"count": 0, "share_percentage": 0.0}
}
```

Percentages are finite numbers rounded to six decimal places. JSON contains no ANSI escapes and ends with one newline.

CSV uses a single long-form table so one invocation has one header:

```text
record_type,rank,key,count,percentage
ip,1,203.0.113.1,42,
error_url,1,/missing,9,
hour,,00,12,24.0
unique_user_agents,,all,7,14.0
summary,,total_valid_requests,50,
summary,,malformed_lines,0,
```

Absent top-list rows are omitted; all 24 hour rows and both summary rows are present. CSV contains no ANSI escapes. Values are quoted according to the standard library `csv` module.

stderr is reserved for diagnostics, including the line number and reason for tolerated parse errors, threshold failure, I/O failure, and cardinality exhaustion. It never contains report records in JSON/CSV modes.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Report, help, or version completed successfully; tolerated parse errors did not exceed the configured threshold |
| `1` | Input open/read failure, output write failure other than an expected broken pipe, or other operational I/O failure |
| `2` | Click usage/configuration error, including invalid values or conflicting format flags |
| `3` | Log-data failure: malformed-line threshold exceeded or no valid requests were found |
| `4` | Unique-cardinality exhaustion: admitting another distinct retained key would exceed `--max-unique` |

No partial JSON, CSV, or terminal report is emitted on exits `1`, `2`, `3`, or `4`. An expected broken pipe caused by a downstream consumer that closes early exits cleanly without a traceback.

## Output Correctness and Determinism

- Top lists contain at most 10 entries and order by count descending, then key ascending.
- Statuses `400..599` contribute to error URL counts; 1xx/2xx/3xx do not.
- Every valid request contributes to exactly one hourly bucket.
- The 24 hourly percentages sum to approximately 100% subject only to output rounding; each unrounded value uses `100 × hourly_request_count / total_valid_requests`.
- JSON and CSV use the same finalized `Report` object as the terminal renderer.
- Locale does not change numeric serialization or sorting.

## Error and Resource Boundaries

Typed application errors map once, in `cli.py`, to the exit contract. Renderers write through an output abstraction so write failures cannot be confused with parse failures. The tool closes files it opens and never closes stdin/stdout supplied by the caller.

The uniqueness limit is checked before insertion, preventing an off-by-one overshoot. The error message reports the configured limit and recommends filtering input or raising the limit only when memory capacity is known. It does not silently approximate the unique User-Agent metric.

## Security and Privacy

Logs are untrusted input. The parser never evaluates fields, invokes a shell, follows URLs, or interprets terminal markup. Rich rendering escapes control/markup characters in captured values; JSON and CSV use standard-library encoders. Error messages do not echo full log lines. The process makes no network calls and writes no files other than shell-directed stdout/stderr.

Symlink handling follows normal local file semantics. Running against sensitive logs remains a local user authorization decision; the documentation warns that pipeline output may contain client IPs, URLs, and User-Agent strings.

## Packaging and Deployment

The deployment target is a local laptop or workstation with CPython 3.11. `pyproject.toml` defines a standards-based wheel and the `nginx-top = nginx_top.cli:main` console entry point. Runtime dependencies are pinned to compatible major ranges for Click and Rich; dataclasses are from the standard library.

Installation and smoke test:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install .
nginx-top --version
```

There is no Docker image, compose file, server deployment, cloud resource, or Kubernetes manifest. Containers would add startup and file-mount friction without improving the local CLI contract.

## Configuration and Environment

There are no required environment variables, configuration files, secrets, credentials, ports, or migrations. Behavior is controlled entirely by explicit CLI options. Conventional `NO_COLOR` support may be added as a P1 compatibility feature only if it does not override an explicit `--color` choice.

## Performance Validation

The benchmark fixture generator must be deterministic, produce syntactically representative combined-format lines, and create data outside version control. The acceptance run records Python version, OS, CPU, storage type, input byte count, valid line count, wall time, and peak RSS. The pass condition is a cold-process run over 1 GB in under 30 seconds on the named reference laptop, with output redirected so terminal rendering is not the bottleneck.

Profiling priorities are compiled parsing, decoding allocation, dictionary updates, and final top-list selection. No concurrency is planned: disk throughput and Python parsing are expected to dominate, while multiprocessing would complicate stdin, exact cardinality accounting, deterministic errors, and the one-weekend scope.

## Architecture Decision Record

### ADR-001: Single-process stateless pipeline

- **Status:** Accepted by the user-provided project constraints.
- **Decision:** Use one Python 3.11 process with layered parser, aggregator, and renderer modules.
- **Alternatives rejected:** GoAccess as an external dependency (does not provide this exact CLI contract); Elastic stack (service and database overhead); AWStats (batch/persistent workflow); shell pipelines (fragile parsing and repeated work); multiprocessing (complexity without evidence it is required).
- **Consequences:** Simple installation and privacy boundary; exact unique metrics require an explicit cardinality ceiling.

### ADR-002: Exact metrics with fail-closed cardinality guard

- **Status:** Accepted.
- **Decision:** Retain exact unique keys up to `--max-unique`, then exit `4` without partial output.
- **Alternatives rejected:** HyperLogLog and sketch-based top-K would bound memory but silently change exact semantics; unbounded sets risk process exhaustion.
- **Consequences:** Predictable failure and reproducible results; users with extremely high-cardinality logs must filter input or consciously raise the cap.

No adversarial review was performed or represented in this document; that activity is outside this blueprint session.

## Traceability

Product priorities and risks are in `STRATEGIC_PLAN.md`. Behavioral acceptance criteria are in `PRD.md`. File-by-file delivery steps and verification commands are in `IMPLEMENTATION_PLAN.md`.
