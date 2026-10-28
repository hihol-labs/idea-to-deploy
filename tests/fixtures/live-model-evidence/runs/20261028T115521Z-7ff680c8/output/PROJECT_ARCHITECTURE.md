# Project Architecture: nginx-stream-report

## Context and Goals

The system is a local Python 3.11 command-line program for operators who need a fast, reproducible summary of nginx access logs. It must process a 1 GB log in under 30 seconds on a documented laptop, avoid retaining complete input records, emit human-readable or pipeline-safe output, and never require a network service.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database would add writes, schema lifecycle, cleanup, and privacy risk while none of the required metrics needs persistence across runs. An HTTP API would add a daemon, ports, authentication, deployment, and remote-data concerns while the intended workflow is a local shell pipeline. Both constraints keep startup immediate, the $0 budget credible, and access logs on the operator's machine.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended)

- **Approach:** one Python process performs parse → validate → aggregate → render, reading one line at a time.
- **Pros:** simplest packaging and operations; no IPC; deterministic exit behavior; direct stdin support.
- **Cons:** CPU-bound parsing uses one core; exact cardinality storage grows with unique values until its safety ceiling.
- **Best for:** the approved one-weekend CLI and laptop benchmark.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunk parsing

- **Approach:** split regular files into byte ranges, parse in workers, and merge partial aggregates.
- **Pros:** can use several CPU cores for large seekable files.
- **Cons:** cannot naturally accelerate stdin; boundaries and merge logic increase correctness risk and memory; startup overhead hurts small files.
- **Best for:** a later release only if profiling proves parsing CPU-bound.
- **Estimated complexity:** High.

### Variant C: Shell toolkit composition

- **Approach:** coordinate system utilities such as `awk`, `sort`, and `uniq` from a Python wrapper.
- **Pros:** mature native utilities may be fast.
- **Cons:** platform-dependent behavior, multiple passes/processes, quoting hazards, and difficult JSON/CSV contracts.
- **Best for:** ad hoc operator scripts, not a portable pip package.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the user pre-approved the obvious single-process architecture and it minimizes delivery and correctness risk. Variant B remains a profile-driven escape hatch; Variant C is represented by an existing alternative rather than the product architecture.

## Component Model

```text
file path / stdin
       |
       v
  byte/text reader -- I/O error --> exit 3
       |
       v
 combined-log parser -- malformed --> skipped counter
       |
       v
 validated AccessRecord
       |
       +--> IP counter
       +--> error-URL counter (status 400..599)
       +--> 24 hourly counters + valid total
       +--> exact User-Agent set -- ceiling exceeded --> exit 4
       |
       v
 immutable Report
       |
       +--> Rich text renderer
       +--> JSON serializer
       +--> CSV serializer
```

Processing is single-pass and stateless across invocations. The program stores counters, at most 24 hourly buckets, and exact distinct User-Agent strings up to a configurable safety ceiling; it never stores complete input lines or records after aggregation.

## Package Structure

```text
pyproject.toml
src/nginx_stream_report/
  __init__.py
  cli.py                 # Click entry point, option validation, exit mapping
  models.py              # AccessRecord, Report, ranked metric dataclasses
  parser.py              # supported nginx combined-log parser
  aggregate.py           # streaming counters and cardinality guard
  render_text.py         # Rich terminal report
  render_json.py         # stable JSON document
  render_csv.py          # normalized CSV rows
  errors.py              # typed domain failures and exit-code mapping
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_cli.py
  test_performance.py
```

## Data Model and Metric Semantics

`AccessRecord` contains `client_ip: str`, `timestamp: datetime`, `request_target: str`, `status: int`, and `user_agent: str`. Only successfully parsed records increment `total_valid_requests`.

- **Top IPs:** rank all valid records by descending request count, then ascending IP string for deterministic ties; return at most 10.
- **Top error URLs:** include status codes 400–599, group by the URL/request target without query normalization in MVP, rank by descending count then ascending URL, and return at most 10.
- **Hourly request distribution:** create buckets `00` through `23` using the timestamp offset present in each log line. Each percentage is `100 × hourly_request_count / total_valid_requests`; if there are no valid requests, all percentages are `0.0` and no division occurs.
- **Unique User-Agent share:** `100 × unique_user_agent_count / total_valid_requests`, where distinct strings are compared exactly after parsing. Empty `"-"` values remain a single literal category. If the configured unique-cardinality ceiling would be exceeded, processing stops with exit code 4 and no partial report is emitted.
- **Malformed lines:** skip and count them. A run with at least one valid line succeeds and reports the skipped count; a non-empty input with zero valid lines is a processing failure (exit 3). Empty input is valid and returns an empty report.

Counts use Python integers. Percentages are serialized as numeric values rounded to two decimal places; renderers use the same computed report values.

## CLI Interface

### Command

```text
nginx-stream-report [OPTIONS] [INPUT]
```

### Inputs

- `INPUT`: optional path to a UTF-8-compatible nginx combined access log; `-` or omission reads standard input.
- Input is consumed sequentially. The tool does not modify the source and performs no network access.

### Options

| Option | Meaning | Default / constraint |
|---|---|---|
| `--json` | Emit one JSON document | Mutually exclusive with `--csv` |
| `--csv` | Emit normalized CSV rows | Mutually exclusive with `--json` |
| `--top INTEGER` | Number of ranked IPs and URLs | `10`; positive integer; Should-priority extension |
| `--max-unique-user-agents INTEGER` | Exact-cardinality safety ceiling | documented finite default; positive integer |
| `--no-color` | Disable ANSI color in text mode | color otherwise only when stdout is a TTY |
| `--version` | Print version and exit | Click standard behavior |
| `--help` | Print usage and exit | Click standard behavior |

### Outputs

- **Text (default):** Rich headings/tables for top IPs, error URLs, hourly percentages, unique User-Agent share, valid count, and malformed count. ANSI color is used only for a TTY and never on stderr diagnostics.
- **JSON:** object with `schema_version`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `unique_user_agents`. Ordering is deterministic.
- **CSV:** header `section,key,count,percentage`; rows for summary values, ranked metrics, all 24 hours, and User-Agent uniqueness. Fields follow RFC 4180 quoting through Python's CSV module.
- The report goes to stdout. Concise diagnostics go to stderr. No partial structured output is emitted after a fatal failure.

### Exit Codes

| Code | Contract |
|---:|---|
| `0` | Success, including empty input with a valid empty report |
| `1` | Unexpected internal failure |
| `2` | Click usage or option error, including conflicting output flags |
| `3` | Input/read/parse processing failure, including a non-empty input with no valid records |
| `4` | Unique-cardinality exhaustion: the User-Agent safety ceiling would be exceeded |

## Output Schemas

The JSON `schema_version` starts at `1`. Ranked entries use `{value, count, percentage}`; hourly entries use `{hour, count, percentage}`; `summary` contains `total_valid_requests` and `malformed_lines`; `unique_user_agents` contains `count` and `percentage`. Additive fields are allowed only in a future schema version policy; breaking changes increment `schema_version`.

CSV uses one stable table rather than concatenating unrelated tables. Consumers select rows by `section` (`summary`, `top_ip`, `error_url`, `hour`, `user_agent`). A missing count or percentage is encoded as an empty field, never an invented zero.

## Failure, Safety, and Observability

Expected failures become typed exceptions in `errors.py`; `cli.py` alone maps them to stderr messages and the `0/1/2/3/4` exit contract. Tracebacks are suppressed for expected errors. Tests may enable tracebacks for unexpected failures.

No secrets, PII, or log contents are persisted or transmitted. Reports can still contain IP addresses and URLs, so stdout is treated as user-controlled sensitive output. The CLI opens only the requested input path and does not follow a configuration file or execute shell commands.

The end-of-run summary provides valid and malformed counts. Performance tests record elapsed wall time and peak RSS outside normal output so JSON/CSV contracts remain clean.

## Performance Design

- Compile parsing machinery once and avoid per-line regex construction.
- Parse only fields needed by the four metrics.
- Update aggregates immediately and release the record each iteration.
- Use `Counter` for IPs and error URLs, fixed-length storage for hours, and a guarded set for User-Agents.
- Select top values with `most_common(top_n)` and apply deterministic tie handling.
- Benchmark a deterministic 1 GB fixture from a local SSD on a documented Python 3.11 laptop; the acceptance threshold is under 30 seconds.

The IP and URL counters are exact and can grow with distinct keys. This is acceptable for the stated laptop workload but must be measured with a high-cardinality fixture. A later bounded heavy-hitter algorithm would require an explicit PRD change because it changes exactness.

## Packaging and Deployment

There is no server deployment, container requirement, cloud resource, or Kubernetes manifest. Build a standard wheel and source distribution from `pyproject.toml`; expose `nginx-stream-report = nginx_stream_report.cli:main`; install locally with pip or `pipx`. CI, if added, runs tests and builds artifacts but does not publish without explicit human approval.

Runtime dependencies are Click and Rich. Development dependencies are isolated in an optional group. The package supports Python `>=3.11,<4` unless testing narrows that range.

## Database, API, Authentication, and Environment

- **Database:** none. There are no tables, migrations, files, caches, or persistent application state.
- **HTTP API:** none. There are no endpoints, request bodies, ports, or daemon lifecycle.
- **Authentication/authorization:** none because the process acts with the invoking user's local file permissions and exposes no remote boundary.
- **Environment variables:** none are required. Behavior is explicit through CLI options to keep runs reproducible.
- **Docker:** not part of the product or delivery path; pip installation is the deployment contract.

## Architecture Decision Record (ADR)

### ADR-001: Choose the single-process pipeline

- **Status:** Accepted (pre-approved product decision).
- **Decision:** Use Variant A and keep parsing, aggregation, and rendering in one process.
- **Consequences:** minimal installation and predictable streaming behavior; optimization must begin with profiling rather than distributed complexity.

### ADR-002: Keep the product local and stateless

- **Status:** Accepted.
- **Decision:** Do not add database, API, authentication, server, cloud, or Kubernetes components.
- **Consequences:** no history across runs and no remote dashboard; users can redirect JSON/CSV into tools of their choice.

### ADR-003: Exact uniqueness with a hard ceiling

- **Status:** Accepted.
- **Decision:** Track exact User-Agent strings until a configurable finite ceiling; fail atomically with code 4 before exceeding it.
- **Consequences:** the share is exact for successful runs and memory failure is explicit rather than silent approximation.

The external Devil's Advocate review is intentionally not recorded here: it is outside this session and will be run by the benchmark harness.

