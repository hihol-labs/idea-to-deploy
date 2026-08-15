# Project Architecture: nginx-stream-report

## Context and Drivers

The product is a local Python 3.11 command for DevOps/SRE users. It must consume nginx combined-format records from a file or standard input, process the stream once, and emit four exact report sections in terminal text, JSON, or CSV. The performance target is 1 GB in under 30 seconds on a documented laptop. Delivery is one weekend at $0.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the required output is derived during one invocation, persistence adds writes and lifecycle cost, and stored raw logs expand the privacy and disk footprint. An HTTP API is incorrect because the user already has a local file or pipe, a server would add deployment, authentication, ports, failure modes, and latency without improving the core workflow.

## Architecture Decision

A single Python process owns input, parsing, aggregation, and rendering. The process reads one physical line at a time; a parser turns valid lines into a small immutable dataclass; an aggregator immediately updates counters and sets; renderers receive a finalized report dataclass. Raw lines and parsed request objects are not retained.

This is the pre-approved architecture. Alternatives were assessed, not offered as open decisions:

| Variant | Trade-off | Decision |
|---|---|---|
| A. Single-process exact streaming (selected) | Minimal operational surface and exact results; distinct-key memory is bounded by policy rather than input bytes | Best match for a local weekend CLI |
| B. Multi-process chunk processing | Could use more CPU, but introduces byte-boundary parsing, merge logic, nondeterminism, and more memory | Rejected until profiling proves CPU parallelism necessary |
| C. SQLite-backed aggregation | Caps in-memory keys but adds persistent I/O, cleanup, schema, and violates the no-database constraint | Rejected |

## Component Model

```text
Click command
    │ validates options and selects input
    ▼
line iterator (file or stdin)
    │ one text line at a time
    ▼
combined-log parser ── malformed record ──► error policy / diagnostics
    │ ParsedRequest dataclass
    ▼
streaming aggregator ── cardinality ceiling ──► exit 4
    │ Report dataclass
    ├──────────────┬──────────────┐
    ▼              ▼              ▼
Rich text      JSON renderer   CSV renderer
```

Recommended package boundaries:

| Path | Responsibility |
|---|---|
| `src/nginx_stream_report/cli.py` | Click command, option validation, input lifecycle, exit mapping |
| `src/nginx_stream_report/models.py` | `ParsedRequest`, `Report`, and report-row dataclasses |
| `src/nginx_stream_report/parser.py` | Precompiled combined-format parser and timestamp normalization |
| `src/nginx_stream_report/aggregate.py` | One-pass counters, top-10 selection, unique-cardinality policy |
| `src/nginx_stream_report/renderers/text.py` | Rich tables and percentage formatting |
| `src/nginx_stream_report/renderers/json.py` | Stable JSON object serialization |
| `src/nginx_stream_report/renderers/csv.py` | Long-form CSV serialization |
| `src/nginx_stream_report/errors.py` | Typed domain failures and exit-code mapping |

## Data Contracts

### Input grammar

MVP input is nginx's conventional combined access-log format:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

The parser extracts client IP text, timestamp including offset, request target, integer status, and User-Agent. It accepts IPv4 and IPv6 as opaque validated address strings, uses the request-target token as the URL value, maps `-` User-Agent to a single literal unknown value, and treats an unparsable physical line as malformed. Blank lines are malformed. Bytes are decoded as UTF-8 with a clear input error on invalid sequences.

### Domain records

| Dataclass | Fields and types | Invariants |
|---|---|---|
| `ParsedRequest` | `ip: str`, `hour: int`, `url: str`, `status: int`, `user_agent: str` | `0 <= hour <= 23`; `100 <= status <= 599` |
| `RankedCount` | `value: str`, `count: int` | count positive |
| `HourlyShare` | `hour: int`, `request_count: int`, `percentage: float` | 24 rows; percentage derived from valid requests |
| `Report` | `total_valid_requests: int`, `malformed_lines: int`, `top_ips: tuple[RankedCount, ...]`, `top_error_urls: tuple[RankedCount, ...]`, `hourly_distribution: tuple[HourlyShare, ...]`, `unique_user_agents: int`, `unique_user_agent_share: float` | deterministic ordering and stable serialization |

Top lists sort by count descending and then value ascending, and contain at most 10 rows. `top_error_urls` counts only requests whose status is 400–599. Hourly request distribution is a percentage calculated exactly as `100 × hourly_request_count / total_valid_requests`; for zero valid requests every hourly percentage is `0.0`. Unique User-Agent share is `100 × unique_user_agents / total_valid_requests`, or `0.0` when there are no valid requests.

### State and memory bounds

The aggregator retains only counters keyed by IP and error URL, a 24-slot hourly counter, and a set of unique User-Agents. A single configurable `--max-unique` ceiling applies independently to distinct IPs, distinct error URLs, and distinct User-Agents. The default is 1,000,000 per category. Encountering a new value after its category reaches the ceiling aborts with exit code 4; the command never silently approximates exact results.

This makes memory proportional to bounded distinct cardinality, not to the 1 GB input size. The process does not spool, cache, or persist source logs.

## CLI Interface

### Commands

Installed console command:

```text
nginx-stream-report [OPTIONS] [INPUT]
```

With no `INPUT`, or with `INPUT` equal to `-`, the command reads stdin. With a path, it opens that local file read-only. Version 1 exposes one command and no subcommands.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `INPUT` | optional path; default `-` | nginx combined-format file or stdin |
| `--json` | flag | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | flag | Emit UTF-8 RFC 4180-style long-form CSV; mutually exclusive with `--json` |
| `--no-color` | flag | Disable ANSI styling in default text mode; no effect on JSON/CSV |
| `--max-unique INTEGER` | default `1000000`, minimum `1` | Per-category exact-cardinality ceiling |
| `--fail-on-malformed` | flag, default false | Stop on the first malformed line instead of counting and skipping it |
| `--help` | flag | Show usage and exit 0 |
| `--version` | flag | Show version and exit 0 |

Invalid combinations and invalid option values are usage errors. Diagnostics go to stderr; report data goes to stdout. Machine-readable modes never emit color or prose to stdout.

### Inputs

- A seekable or non-seekable text stream containing one nginx combined-format record per line.
- Regular uncompressed files in MVP. Gzip is a Should feature and may be piped through `gzip -dc` until implemented.
- No network URL, database, HTTP request, cloud object, or directory input.

### Outputs

Text mode uses Rich headings/tables for the four metrics and a summary of valid/malformed lines. It enables color only when stdout is a compatible terminal unless explicitly disabled.

JSON mode emits one object with schema version and deterministic fields:

```json
{
  "schema_version": 1,
  "total_valid_requests": 0,
  "malformed_lines": 0,
  "top_ips": [],
  "top_error_urls": [],
  "hourly_distribution": [],
  "unique_user_agents": 0,
  "unique_user_agent_share_percentage": 0.0
}
```

Each hourly item contains `hour`, `request_count`, and `percentage`. Each ranked item contains `value` and `count`.

CSV mode emits a header `section,key,count,percentage` followed by rows for `top_ip`, `top_error_url`, `hour`, and `unique_user_agents`. Non-applicable cells are empty; hour keys are `00` through `23`. CSV represents the same report, not one report per input record.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Report produced successfully, including an empty input |
| `1` | Input or I/O failure: missing/unreadable file, decoding failure, or interrupted read |
| `2` | CLI usage error: invalid option/value or mutually exclusive formats |
| `3` | Log-data error: first malformed record when `--fail-on-malformed` is active |
| `4` | Unique-cardinality exhaustion: IP, error-URL, or User-Agent ceiling exceeded |

On any nonzero exit, stdout contains no partial JSON or CSV document. Text mode may have no report; diagnostics identify the error category without leaking an entire sensitive log line.

## Persistence, API, Authentication, and Deployment

### Database

None. There are no tables, migrations, indexes, database files, or retained records. The template's database-table inventory is intentionally inapplicable because persistence would violate the approved stateless architecture.

### HTTP API

None. There are no endpoints, request bodies, ports, server process, or API versioning concerns. The CLI contract above is the complete external interface; inventing five endpoints to satisfy a generic template would violate product scope.

### Authentication

None. The tool runs with the invoking user's local file permissions, makes no network requests, and has no identity store or multi-user service boundary. Operating-system access control is the trust boundary.

### Deployment

Distribution is a pip-installable wheel and source distribution with a console-script entry point. It runs locally in a Python 3.11 environment. There is no Docker requirement, compose file, hosted target, cloud resource, or Kubernetes manifest. A clean virtual environment is the release smoke-test target.

### Environment variables

None are required. CLI arguments are explicit and replayable; environment-driven behavioral configuration is intentionally avoided in MVP.

## Error Handling and Observability

- Expected failures are typed and mapped once in `cli.py` to the `0/1/2/3/4` contract.
- Skipped malformed-line counts appear in successful reports; stderr warnings are summarized rather than emitted per line to avoid flooding.
- Diagnostics include the one-based line number and reason, not the full raw line or User-Agent.
- Broken pipes terminate quietly without a traceback when downstream closes normally.
- Debug tracebacks are developer behavior, not the stable end-user interface.

## Performance Strategy

- Read with buffered sequential I/O and never call `read()` without a bounded size.
- Compile the parsing expression once; avoid datetime objects when extracting the two-digit local hour suffices.
- Update aggregates in one pass and use `heapq.nsmallest`/equivalent bounded selection only at finalization.
- Render only after successful finalization so structured output is atomic at the document level.
- Benchmark a fixed 1 GB representative fixture after a warm-up run, record Python version, CPU, storage, wall time, throughput, and peak RSS, and require wall time below 30 seconds.

## Security and Privacy

Log contents are untrusted data, never shell commands or format strings. Paths are opened directly without shell interpolation. Terminal rendering must escape/control-filter untrusted values so URLs and User-Agents cannot inject ANSI control sequences. JSON and CSV use standard-library serializers. No telemetry, network egress, temporary log copy, or persistent state is allowed.

## Architecture Decision Record (ADR)

### ADR-001: Single-process exact streaming

- **Status:** Accepted (pre-approved product decision)
- **Decision:** Use one local Python process with bounded exact aggregators.
- **Consequences:** Installation and operation remain simple; throughput must be earned through efficient parsing; cardinality is explicitly capped.

### ADR-002: No persistence and no server interface

- **Status:** Accepted (pre-approved constraint)
- **Decision:** Apply **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- **Consequences:** No historical query or remote multi-user access; zero service operations and no retained sensitive data.

### ADR-003: Explicit cardinality failure

- **Status:** Accepted
- **Decision:** Preserve exactness up to a declared ceiling and fail with code 4 when it is exceeded.
- **Consequences:** Pipelines can distinguish capacity exhaustion from I/O, usage, and malformed-data failures; no silent approximation.

No adversarial or independent architecture review is represented in this document; that review is explicitly outside this session.

