# Project Architecture: nginx-stream-report

## Architecture Summary

The product is a single-process Python 3.11 CLI installed with pip. Click owns argument validation and process exit behavior. A line iterator feeds a parser, parsed records feed a streaming aggregator, and an immutable result snapshot feeds exactly one renderer. Rich is used only by the human renderer; JSON and CSV use the standard library.

The governing decision is **"no database — stateless streaming processing; no HTTP API — CLI-only tool"**. A database would add storage, migrations, I/O, and lifecycle management while the product only needs a per-run summary. An HTTP API would add a server, authentication questions, deployment, and an attack surface without improving the local incident-response workflow. Both constraints keep the $0, one-weekend, local-only product coherent.

```text
file path / stdin
       |
       v
input iterator -> line parser -> validated LogRecord -> streaming Aggregator
                         |                         |
                    malformed count          bounded state
                                                   |
                                                   v
                                             ReportResult
                                                   |
                              +--------------------+--------------------+
                              v                    v                    v
                         Rich text               JSON                 CSV
```

## Architecture Decision

The approved variant is a single process with a layered package. The following possibilities were evaluated without reopening the pre-approved decision:

| Variant | Benefits | Costs | Decision |
|---|---|---|---|
| Layered single-process Python CLI | Minimal setup; one-pass data flow; independently testable parser, aggregation, and renderers | Exact unique cardinality needs an explicit memory ceiling | Selected |
| Shell pipeline built from grep/awk/sort | No package installation | Format fragility, several passes, platform differences, poor structured output | Rejected |
| Persistent analytics service | Query history and dashboards | Violates no database/server/cloud constraints and weekend budget | Rejected |

Python is acceptable only if the benchmark passes. The components avoid per-line object retention, repeated parsing, and sorting the full stream. Top-10 extraction occurs after aggregation; IP and error-URL maps necessarily scale with their distinct keys. User-Agent exactness is protected by a hard configurable ceiling that fails explicitly rather than silently becoming approximate.

## Components and Responsibilities

| Module | Responsibility | Must not do |
|---|---|---|
| `src/nginx_stream_report/cli.py` | Click command, options, stream selection, renderer dispatch, exit mapping | Parse log syntax or format tables directly |
| `src/nginx_stream_report/parser.py` | Compile supported log pattern and convert a line to `LogRecord` | Retain prior lines or print |
| `src/nginx_stream_report/models.py` | Dataclasses for records, counts, report metadata | Perform I/O |
| `src/nginx_stream_report/aggregate.py` | Update counters in one pass; enforce cardinality ceiling; finalize percentages/top 10 | Depend on Click or Rich |
| `src/nginx_stream_report/renderers/text.py` | Colored, readable Rich report | Emit machine schemas |
| `src/nginx_stream_report/renderers/json.py` | Stable JSON document to stdout | Add ANSI escape sequences |
| `src/nginx_stream_report/renderers/csv.py` | Stable normalized CSV rows to stdout | Emit prose |
| `src/nginx_stream_report/errors.py` | Typed operational exceptions and exit-code mapping | Catch unexpected programmer errors broadly |

## Data Model and Streaming State

There are no database tables. In-memory state lasts for one invocation only.

```text
LogRecord
- ip: str
- timestamp: datetime (timezone-aware)
- request_target: str
- status: int
- user_agent: str

AggregationState
- total_lines: int
- valid_requests: int
- malformed_lines: int
- ip_counts: Counter[str]
- error_url_counts: Counter[str]
- hourly_counts: list[int]  # exactly 24 slots, local offset from log timestamp
- unique_user_agents: set[str]
- unique_user_agent_limit: int

ReportResult
- top_ips: tuple[RankedCount, ...]       # at most 10
- top_error_urls: tuple[RankedCount, ...] # at most 10
- hourly_distribution: tuple[HourShare, ...] # 24 entries
- unique_user_agents: int
- unique_user_agent_share_percent: float
- totals: ReportTotals
```

Hourly request distribution is a percentage for each hour `00` through `23`, calculated as `100 × hourly_request_count / total_valid_requests`. With zero valid requests every hourly percentage and the unique User-Agent share are `0.0`; the empty result is not a division error.

The unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`. It measures unique values relative to valid requests, not unique visitors. If adding another distinct User-Agent would exceed the configured ceiling, aggregation stops with exit code 4; the tool must not emit a misleading partial report.

## Parsing Contract

MVP input is nginx combined log format with a quoted request and quoted User-Agent. The parser extracts client IP, timestamp/offset, request target, numeric status, and User-Agent. The request target preserves the logged path and query string. Statuses 400–599 contribute to error-URL counts. Malformed or unsupported lines are counted and skipped; if no valid lines remain, the command exits 3.

Input is decoded as UTF-8 with replacement for invalid byte sequences so a single bad byte cannot crash a long run. Line iteration is lazy. The parser is deterministic and does not perform DNS, filesystem, or network lookups.

## CLI Interface

### Commands

```text
nginx-stream-report [OPTIONS] [INPUT]
nginx-stream-report --help
nginx-stream-report --version
```

There is one analysis command. `INPUT` is a path to a regular readable log file; `-` means stdin and is the default.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit normalized CSV; mutually exclusive with `--json` |
| `--color / --no-color` | auto | Override color for text mode; ignored by machine modes |
| `--max-unique-user-agents INTEGER` | positive int, `1000000` | Hard ceiling for exact User-Agent cardinality |
| `--version` | flag | Print version and exit 0 |
| `--help` | flag | Print usage and exit 0 |

### Inputs

- A path supplied as `INPUT`, opened read-only.
- Standard input when `INPUT` is omitted or `-`.
- Supported content: newline-delimited nginx combined access logs.
- Regular uncompressed text is P0. Gzip is P1 and may be deferred.

### Outputs

- Human mode: four labeled Rich sections, totals, and malformed-line count on stdout. Color defaults on only for a TTY.
- JSON mode: one object with `schema_version`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `unique_user_agents` keys.
- CSV mode: header `report,key,count,percentage,rank`; rows distinguish reports through `report`.
- Diagnostics go to stderr. Machine output on stdout remains parseable even when warnings occur.
- Ties in top-10 lists sort by key ascending after count descending, producing deterministic output.

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Successful report, including reports that skipped some malformed lines |
| 1 | Unexpected internal error |
| 2 | CLI usage error, invalid option combination, missing/unreadable input |
| 3 | Input was readable but contained zero valid requests |
| 4 | Unique-cardinality exhaustion: the configured exact User-Agent ceiling was exceeded |

The complete public exit-code contract is `0/1/2/3/4`.

## Output Schemas

JSON uses numbers for counts and percentages and preserves the 24-hour order. Its initial `schema_version` is `1`. CSV emits one row per ranked or hourly item plus one `unique_user_agents` row; unused cells are empty, not invented zeroes. Both formats end with a newline and use UTF-8.

## Error Handling and Observability

- Expected usage and input failures are concise and mapped to documented codes.
- Malformed lines increment counters; up to five representative line numbers may be described on stderr without echoing full potentially sensitive log content.
- Unexpected exceptions return 1 and show a concise message. A future opt-in debug flag may expose tracebacks.
- No telemetry or network calls occur.
- The benchmark records elapsed wall time, peak resident memory, Python version, platform, input size/hash, and valid/malformed counts outside normal output schemas.

## Security and Privacy

Logs may contain IPs, URLs, query strings, and User-Agents. Processing stays local and stateless; the tool creates no cache or report file unless the caller redirects stdout. It never executes or interprets log fields, follows no URLs, resolves no IPs, and avoids reproducing full malformed lines in diagnostics. Documentation warns that generated reports can still contain sensitive data.

## Packaging and Deployment

- `pyproject.toml` defines Python `>=3.11,<4`, runtime dependencies (`click`, `rich`), the console script, and wheel/sdist metadata.
- Installation target is a local virtual environment via pip. There is no Docker image, daemon, service manager, staging environment, or deployment target.
- Build artifacts are wheels and source distributions. A clean environment install is the release smoke test.
- Runtime configuration is by CLI options only; there are no required environment variables or secrets.

## Performance Design

The target is a 1 GB file in under 30 seconds on a documented laptop. The benchmark uses a deterministic generated fixture and excludes fixture generation from timing. Optimization order is: stream bytes/lines, compile parsing once, avoid unnecessary datetime construction, update primitive counters, profile, then optimize verified hotspots. The release criterion includes the exact reference hardware and command so the number is reproducible.

Memory is bounded for hourly state and explicitly bounded for unique User-Agents. IP and URL exact counters can grow with adversarial cardinality; the MVP documents this limitation and includes high-cardinality testing. A later version may add explicit ceilings for all dimensions, but must never switch silently to approximate results.

## Testing Strategy

- Unit tests: parser edge cases, status filtering, timestamps, tie ordering, percentages, zero-valid input, and cardinality ceiling.
- Renderer contract tests: parse JSON/CSV, assert no ANSI in machine modes, snapshot stable text structure without brittle terminal widths.
- CLI integration tests: file/stdin parity, option conflicts, stdout/stderr separation, and all exit codes `0/1/2/3/4`.
- Property/fuzz tests if time permits: arbitrary malformed lines never execute data or crash the parser.
- Performance test: deterministic 1 GB fixture, repeated warm/cold runs, median under 30 seconds.

## Architecture Decision Record (ADR)

### ADR-001: Local stateless CLI

- **Status:** Accepted (pre-approved product constraint)
- **Decision:** Use a layered single Python process with no persistence or network server.
- **Consequences:** Simple install and operation; no historical query capability; every run scans its input.

### ADR-002: Exact unique cardinality with explicit exhaustion

- **Status:** Accepted
- **Decision:** Keep an exact set up to a user-visible hard ceiling, then fail with exit code 4.
- **Consequences:** Results are exact when produced; adversarial cardinality cannot cause unbounded growth past the ceiling; some valid inputs require a higher operator-approved limit.

No Devil's Advocate or independent review was run in this session, as required by the benchmark protocol. The external harness owns that separate review artifact.

