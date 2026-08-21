# Project Architecture: nginx-stream-stats

## 1. Context and Drivers

The product is a local Python 3.11 process that consumes nginx access-log text and emits one final report. It must be pip-installable, complete a representative 1 GB input in under 30 seconds on a documented laptop, work from a file or stdin, and expose identical metrics as colored terminal text, JSON, or CSV. It retains no data after process exit.

The approved architecture decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is wrong here because the requested result is computed during one bounded scan and no query, history, sharing, or cross-run state is required. An HTTP API is wrong because the user and integration boundary is already a local shell pipeline; a server would add lifecycle, port, security, deployment, and failure concerns without adding product value.

## 2. Architecture Decision

A single-process, layered CLI is the obvious and approved choice:

```text
argv / environment
       |
       v
Click CLI + validation -----> stderr diagnostics / exit code
       |
       v
text stream (file or stdin)
       |
       v
nginx line parser -> ParseRecord or ParseError -> skipped-line counter
       |
       v
one-pass Aggregator
  | client-IP Counter
  | error-URL Counter
  | 24 hourly buckets
  | exact User-Agent set with hard ceiling
       |
       v
immutable Report dataclass
       |
       +---- Rich terminal renderer
       +---- JSON renderer
       `---- CSV renderer
```

Only the current input line and aggregate structures are retained. No parsed-line list, temporary output file, subprocess, network call, or background worker is used.

### Alternatives considered

| Alternative | Decision | Reason |
|---|---|---|
| Single-process layered CLI | Selected | Lowest operational complexity; direct fit for one-pass local analysis |
| Multiprocessing parser | Rejected for MVP | IPC, chunk boundaries, merge logic, and platform variance threaten the weekend scope; benchmark evidence must justify it later |
| SQLite-backed aggregation | Rejected | Adds writes and schema lifecycle while making the common in-memory path slower |
| Go implementation | Rejected | Conflicts with the approved Python 3.11 stack; revisit only if measured optimization cannot meet the performance gate |
| Log shipping to an observability service | Rejected | Violates local, stateless, $0, no-server constraints |

No adversarial-review result is recorded in this document; that review is outside this blueprint session.

## 3. Component Boundaries

| Component | Proposed path | Responsibility | Must not do |
|---|---|---|---|
| CLI adapter | `src/nginx_stream_stats/cli.py` | Click command, option validation, stream ownership, renderer selection, exit mapping | Parse log lines or calculate metrics |
| Domain models | `src/nginx_stream_stats/models.py` | Frozen/slotted dataclasses for parsed records, ranked values, metadata, and final report | Perform I/O |
| Parser | `src/nginx_stream_stats/parser.py` | Compile the selected format once; convert one line into a minimal record or typed parse failure | Retain input lines |
| Aggregator | `src/nginx_stream_stats/aggregator.py` | Update counters, hourly buckets, and exact User-Agent set; enforce ceiling | Render output |
| Metrics | `src/nginx_stream_stats/metrics.py` | Deterministic top-10 ranking and percentage calculations; construct report | Read input |
| Terminal renderer | `src/nginx_stream_stats/renderers/terminal.py` | Rich tables, labels, percentages, warnings | Change or recalculate metrics |
| JSON renderer | `src/nginx_stream_stats/renderers/json.py` | Emit the versioned JSON document | Write diagnostics to stdout |
| CSV renderer | `src/nginx_stream_stats/renderers/csv.py` | Emit the versioned rectangular CSV table | Add terminal decoration |
| Error model | `src/nginx_stream_stats/errors.py` | Typed failures and the `0/1/2/3/4` mapping | Swallow failures |

Dependencies point inward: adapters and renderers depend on the domain/report contracts; the domain does not import Click or Rich.

## 4. Data Contracts and Calculations

### Parsed record

`ParsedRecord` contains only fields needed after parsing:

| Field | Type | Rule |
|---|---|---|
| `client_ip` | `str` | Non-empty nginx remote address token; no DNS lookup |
| `timestamp` | timezone-aware `datetime` | Parsed from nginx bracketed timestamp including numeric offset |
| `request_target` | `str` | Target from the quoted request line; method and protocol discarded after validation |
| `status` | `int` | Three-digit HTTP status from 100 through 599 |
| `user_agent` | `str | None` | Combined-format User-Agent; `-`, absent common-format value, or empty value becomes `None` |

The parser supports nginx `combined` and `common` formats as documented formats. A malformed physical line increments `skipped_lines` and processing continues. Decoding uses UTF-8 with replacement so an isolated invalid byte cannot crash an otherwise readable stream; replacement characters remain visible in affected values.

### Aggregates

- `total_lines`: every physical line read.
- `total_valid_requests`: successfully parsed request records.
- `skipped_lines`: `total_lines - total_valid_requests`.
- Client IP counter: incremented for every valid request.
- Error URL counter: incremented only when `400 <= status <= 599`.
- Hourly buckets: 24 integers keyed `00` through `23`, using the hour expressed in each log entry's timestamp and offset; buckets combine dates.
- User-Agent set: one exact normalized value per valid request with a present User-Agent. No case folding or whitespace rewriting occurs beyond parser extraction.
- `requests_with_user_agent`: count of valid requests whose User-Agent is present.

Top lists contain at most 10 entries and sort by descending count, then ascending key as a deterministic tie-break. Top error URLs combine 4xx and 5xx responses in one ranking.

Hourly request distribution is a percentage for each bucket, calculated with the literal formula `100 × hourly_request_count / total_valid_requests`. If there are no valid requests, no report is emitted and the command exits 1; division by zero is therefore not represented.

Unique User-Agent share is `100 × unique_user_agent_count / requests_with_user_agent`. If no valid request has a User-Agent, the unique count is 0 and the percentage is 0.0. This denominator is published so common-format input is not misleadingly treated as one repeated agent.

Percentages are represented as numbers, rounded only at serialization to two decimal places. The 24 hourly values may differ from exactly 100.00 after independent display rounding; raw counts remain authoritative.

### Cardinality boundary

The exact User-Agent set has a configurable hard ceiling, default 1,000,000 distinct values. Before inserting a value that would exceed the ceiling, aggregation raises `UniqueCardinalityExhausted`, emits no partial report, writes a diagnostic to stderr, and exits 4. Approximate cardinality is explicitly not used because it would silently change the requested metric.

IP and URL counters are also cardinality-dependent. A Python `MemoryError` or other internal resource failure maps to exit 3, never to a partial success.

## CLI Interface

### Command

```text
nginx-stream-stats [OPTIONS] [INPUT]
```

`INPUT` is one filesystem path or `-`; it defaults to `-` for stdin. The command reads one uncompressed text stream to EOF. Shell decompression may be piped into stdin, but native gzip support is not part of the MVP.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit one JSON object to stdout; mutually exclusive with `--csv` |
| `--csv` | false | Emit one CSV header and rows to stdout; mutually exclusive with `--json` |
| `--log-format [combined|common]` | `combined` | Select the documented nginx input grammar |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive exact-cardinality ceiling; exceeding it exits 4 |
| `--color / --no-color` | auto | For terminal mode only; auto enables color on a capable TTY and disables it when redirected |
| `--version` | n/a | Print package version and exit 0 |
| `--help` | n/a | Print Click help and exit 0 |

Supplying incompatible options, a non-positive ceiling, an extra positional argument, or an invalid log-format value is usage error 2. `--color`/`--no-color` has no effect on JSON/CSV bytes.

### Inputs

- Regular file paths are opened read-only and closed by the CLI.
- `-` or omitted input reads stdin and does not close the caller-owned stream.
- Input is line-oriented nginx access-log text in the selected common or combined format.
- FIFOs work through normal stream reads; seeking and input-size discovery are not required.

### Outputs

Stdout contains only the selected report format. Diagnostics contain no report fragments and go only to stderr.

Terminal output contains a summary (`total_lines`, `valid_requests`, `skipped_lines`), top IP table, top error-URL table, 24-row hourly distribution with counts and percentages, and unique User-Agent count/share. Color is presentation only.

JSON output has this stable top-level contract:

```text
schema_version: 1
summary: {total_lines, total_valid_requests, skipped_lines, requests_with_user_agent}
top_ips: [{rank, ip, request_count}]
top_error_urls: [{rank, url, error_count}]
hourly_distribution: [{hour, request_count, percentage} x 24]
user_agents: {unique_count, requests_with_user_agent, percentage}
```

CSV is one rectangular document with columns:

```text
schema_version,section,rank,key,count,percentage
```

It contains `summary` rows for line counts, ranked `top_ip` and `top_error_url` rows, 24 `hourly_distribution` rows, and a `unique_user_agent_share` row. Inapplicable fields are empty, CSV quoting follows RFC 4180 through the standard library, and a final newline is present.

### Exit-code contract

| Code | Meaning | Output behavior |
|---:|---|---|
| `0` | Successful report, help, or version | Complete requested stdout output |
| `1` | Input reached EOF but contained zero valid requests | No report on stdout; concise diagnostic on stderr |
| `2` | Invalid command usage or option/configuration value | Click usage diagnostic on stderr |
| `3` | Input open/read failure, unexpected internal/runtime failure, or memory exhaustion outside the unique-UA ceiling | No partial report; diagnostic on stderr |
| `4` | Unique-cardinality exhaustion: the next distinct User-Agent would exceed the configured ceiling | No partial report; cardinality diagnostic on stderr |

Malformed individual lines alone do not make a run fail when at least one valid request exists; their count is part of every successful report.

## 6. Output Atomicity and Error Handling

Aggregation completes before rendering begins, so a parser, I/O, runtime, or cardinality failure cannot leave a syntactically partial JSON/CSV document. The final report model is frozen before it reaches a renderer. Broken-pipe handling follows Unix expectations: terminate quietly when the downstream reader closes, without a traceback; its precise process status is covered by integration tests and must not remap defined application errors.

User diagnostics are concise and omit stack traces by default. Tests may exercise exception causes directly. File paths may be named, but log contents and complete User-Agent values are not echoed in errors.

## 7. Performance and Resource Design

- Compile parsing expressions once, outside the line loop.
- Read with buffered iteration; never call `read()` for the whole input.
- Extract only five record fields and update aggregate structures immediately.
- Use fixed 24-element hourly storage and slotted dataclasses where measured useful.
- Rank with `heapq.nlargest` or an equivalent `O(k log 10)` selection, followed by deterministic tie ordering; do not fully sort unless measurement shows it is acceptable.
- Render only after EOF, and render only top lists plus fixed-size summaries.
- Do not add progress output because it would pollute pipelines and distort the benchmark.

Time complexity is `O(n + c log 10)` for `n` valid/invalid lines and `c` distinct IP/URL keys. Memory is `O(i + u + a)`, where `i`, `u`, and `a` are distinct IPs, URLs, and User-Agents; `a` is explicitly capped. “Streaming” means input records are not retained, not constant-memory exact aggregation for unbounded distinct keys.

The release benchmark uses a representative 1 GB fixture outside the repository, a warmed local filesystem or clearly declared cold-cache procedure, Python 3.11, and a named reference laptop. It records wall time, peak RSS, valid/skipped counts, and output checksum comparison to an expected report. The acceptance target is under 30 seconds; no claim is made until measured.

## 8. Database, API, Authentication, and Deployment

### Database

Not applicable by design. There are zero tables, migrations, indexes, files used as stores, caches, or retained records. Aggregate memory dies with the process. Adding storage requires a new architecture decision and is outside the MVP.

### HTTP API

Not applicable by design. There are zero endpoints, methods, request bodies, response bodies, ports, or network listeners. The complete public interface is the `## CLI Interface` contract above.

### Authentication and authorization

Not applicable because there is no remote boundary, account, tenant, privileged action, or retained user data. Access to the input file is governed by the invoking operating-system user. Introducing application authentication would neither protect a local file from that same user nor reduce a network risk, because there is no network service.

### Deployment and packaging

The deployment target is a local laptop or workstation with CPython 3.11 and pip. Build a wheel and source distribution from `pyproject.toml`; install them into an isolated environment and expose the `nginx-stream-stats` console script. There is no Docker image, `docker-compose.yml`, server process, cloud resource, or Kubernetes manifest. This avoids needless container startup and volume/permission complexity for a local stdin/file tool.

### Environment variables

There are no application-specific environment variables. All behavior is explicit in command options, which makes runs reproducible. Standard process environment such as locale and terminal capability may be observed only by Python/Rich; JSON and CSV output must remain UTF-8 and deterministic across locales.

## 9. Security and Privacy

- Treat every log value as untrusted data, never as terminal markup or a format string; Rich text must escape or disable markup for values.
- Never execute, resolve, fetch, or open request targets or User-Agent contents.
- JSON and CSV encoders provide structural escaping; tests include commas, quotes, control characters, and terminal markup sequences.
- Read input only; do not mutate logs or create temporary copies.
- Do not send telemetry or network traffic.
- Avoid including raw log lines in error output because access logs can contain sensitive URLs and identifiers.
- Dependency versions and licenses are reviewed before release; only Click and Rich are required runtime dependencies.

## 10. Test Architecture

| Layer | Tests | Evidence |
|---|---|---|
| Parser unit | common/combined, timezone offsets, IPv4/IPv6 token, escaped quotes policy, malformed status/request, missing UA | Deterministic records/failures |
| Aggregator unit | all four metrics, status boundaries, 24 buckets, tie ordering, cardinality boundary | Exact in-memory report |
| Renderer unit | special characters, no ANSI in JSON/CSV, 24 hours, rounding, schema fields | Golden outputs parse back successfully |
| CLI integration | file/stdin, flags, mutual exclusion, missing file, empty/all-invalid input, exit `0/1/2/3/4` | `CliRunner` and subprocess assertions |
| Cross-renderer contract | same fixture through all renderers | Counts and percentages equivalent after decoding |
| Performance | generated representative 1 GB file on reference laptop | Under 30 seconds with recorded setup and peak RSS |
| Packaging | build, wheel install, console entry point, `--help`, `--version` | Clean Python 3.11 environment |

## 11. Repository Layout

```text
pyproject.toml
src/nginx_stream_stats/
  __init__.py
  cli.py
  errors.py
  models.py
  parser.py
  aggregator.py
  metrics.py
  renderers/
    __init__.py
    terminal.py
    json.py
    csv.py
tests/
  fixtures/
  test_parser.py
  test_aggregator.py
  test_metrics.py
  test_renderers.py
  test_cli.py
  test_performance.py
  test_packaging.py
```

This is a planned layout, not an instruction to create product code during blueprinting.

## 12. Architecture Acceptance

- The CLI can process file/stdin without retaining parsed lines.
- All renderers consume the same immutable report.
- Metric formulas, ranking ties, missing User-Agent behavior, malformed-line accounting, and exit codes are unambiguous.
- No database, HTTP API, server, authentication layer, cloud resource, Docker artifact, or Kubernetes artifact is introduced.
- A measured release candidate meets the 1 GB under 30 seconds target on the declared reference laptop.

See `PRD.md` for product acceptance, `IMPLEMENTATION_PLAN.md` for sequencing, and `CLAUDE_CODE_GUIDE.md` for step prompts.
