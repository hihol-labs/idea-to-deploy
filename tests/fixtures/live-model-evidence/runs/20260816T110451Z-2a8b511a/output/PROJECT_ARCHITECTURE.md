# Project Architecture: nginx-stream-stats

## Architecture Summary

The approved architecture is a single local Python 3.11 process with a linear pipeline:

```text
file(s) or stdin
      │ text lines
      ▼
input opener → combined-log parser → streaming aggregator → immutable report → one renderer
                    │                     │                       ├─ Rich terminal
                    └─ malformed count    └─ cardinality guard    ├─ JSON
                                                                    └─ CSV
```

There are no background workers, network listeners, persistent stores, or subprocess pipelines. Each input line is parsed once. Aggregates retain only counters, 24 hourly buckets, bounded unique values, and error metadata—not raw records.

## Architecture Decision

**"no database — stateless streaming processing; no HTTP API — CLI-only tool"**

Both constraints are correct here. A database would add writes, schema lifecycle, cleanup, disk amplification, and state semantics without improving a one-shot report. The source log already is the durable input, and the complete report can be derived in one pass. An HTTP API would require a long-running server, authentication and authorization decisions, deployment, resource isolation, and an operational lifecycle that conflict with the local, $0, one-weekend goal. Files/stdin plus stdout/stderr are the native and composable DevOps interface.

The pre-approved single-process architecture is the obvious choice for a solo weekend CLI; the workflow therefore does not invent microservices, serverless, or persistence variants. Alternatives rejected at the system boundary are documented under ADR-001 below.

## Technology Stack

| Layer | Technology | Responsibility |
|---|---|---|
| Runtime | Python 3.11 | File iteration, parsing, aggregation, serialization |
| CLI | Click | Arguments, mutually exclusive modes, help, usage errors, exit mapping |
| Terminal | Rich | Colored headings, tables, warning presentation |
| Models | `dataclasses` + type hints | Parsed record, counters, report, and configuration |
| Standard library | `re`, `datetime`, `collections`, `json`, `csv`, `pathlib`, `sys` | One-pass implementation without extra runtime systems |
| Packaging | PEP 621 `pyproject.toml` | pip installation and `nginx-stream-stats` console script |
| Quality | pytest, coverage tooling, benchmark harness | Correctness, output contracts, and 1 GB target evidence |

## Component Boundaries

Planned source layout:

```text
pyproject.toml
src/nginx_stream_stats/
├── __init__.py
├── cli.py          # Click command, mode selection, errors and exits
├── inputs.py       # UTF-8 text streams for paths, gzip (P1), and stdin
├── parser.py       # Default nginx combined-format line → AccessRecord
├── models.py       # dataclasses and enums; no I/O
├── aggregate.py    # Streaming counters and cardinality ceiling
└── renderers/
    ├── terminal.py # Rich output
    ├── json.py     # schema version 1
    └── csv.py      # normalized row stream
tests/
├── fixtures/
├── test_parser.py
├── test_aggregate.py
├── test_cli.py
├── test_output_contracts.py
└── test_performance.py
```

Dependencies flow inward: `cli` may call inputs, parser, aggregate, and renderers; renderers consume report dataclasses; parsing and aggregation do not import Click or Rich. All output is emitted after aggregation so a late cardinality failure cannot leave a partial machine-readable report.

## Domain and Data Model

No database tables exist. The in-memory dataclasses are the complete transient schema:

| Model | Field | Type | Invariant |
|---|---|---|---|
| `AccessRecord` | `client_ip` | `str` | Non-empty parsed token |
|  | `timestamp` | timezone-aware `datetime` | Parsed from nginx timestamp and offset |
|  | `request_target` | `str` | URL/request-target token exactly as logged; query string retained |
|  | `status` | `int` | 100–599 |
|  | `user_agent` | `str` | Quoted field decoded; `-` is a real normalized sentinel |
| `AggregationConfig` | `top_n` | `int` | MVP fixed to 10 through public CLI |
|  | `max_unique` | `int` | Positive cardinality ceiling applied independently to exact sets/counters |
| `MutableAggregate` | `ip_counts` | `Counter[str]` | One increment per valid record |
|  | `error_url_counts` | `Counter[str]` | Increment only for status 400–599 |
|  | `hour_counts` | `list[int]` | Exactly 24 buckets, using log timestamp hour as recorded in its offset |
|  | `unique_user_agents` | `set[str]` | Exact; bounded by `max_unique` |
|  | `valid_count` | `int` | Denominator for percentages |
|  | `malformed_count` | `int` | Lines rejected by parser |
| `Report` | `schema_version` | `int` | `1` for initial JSON/CSV contract |
|  | `top_ips` | `tuple[RankedCount, ...]` | At most 10, deterministic ordering |
|  | `top_error_urls` | `tuple[RankedCount, ...]` | At most 10, deterministic ordering |
|  | `hourly_distribution` | `tuple[HourlyShare, ...]` | Exactly 24 entries |
|  | `unique_user_agent_count` | `int` | Exact count |
|  | `unique_user_agent_share_percent` | `float` | `100 × unique_user_agent_count / total_valid_requests` |
|  | `valid_count`, `malformed_count` | `int` | Processing summary |

Top lists sort by descending count, then ascending UTF-8 string value to make ties deterministic. Hourly request distribution is a percentage for each hour using the literal formula `100 × hourly_request_count / total_valid_requests`. Percentages are computed from integer counts, serialized as numbers rounded to six decimal places, and terminal-rendered to two decimal places. The 24 unrounded values conceptually sum to 100%; rounded display values may differ slightly.

The exact User-Agent share is defined as `100 × unique_user_agent_count / total_valid_requests`. The report also emits both source counts, preventing ambiguity.

## Parsing Contract

MVP input is the conventional nginx combined log format:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

- Iterate text lines lazily; do not call `read()`, `readlines()`, or retain raw lines.
- Parse quoted fields and the bracketed timestamp without splitting on all spaces.
- Extract the request target from the request line (`METHOD target PROTOCOL`). A malformed request line rejects that record.
- Accept IPv4, IPv6, and other non-empty remote-address tokens without DNS lookup.
- Treat blank lines, bad timestamps, absent required fields, invalid status codes, and malformed requests as malformed records.
- Continue past malformed records and expose their count. If no valid records exist, produce no report and exit 3.
- Multiple files are logically concatenated in argument order. `-` denotes stdin and may occur at most once.
- Input decoding defaults to UTF-8 with strict errors; decode/open/read failures exit 1 with a concise stderr diagnostic.

The parser supports the documented format, not arbitrary custom `log_format` definitions. Custom grammars are P2.

## Database

There is no database, schema, table, index, migration, cache service, or persisted application state. The transient dataclasses listed above replace the generic blueprint template's database-table section because adding even a local database would violate the approved architecture and would not serve the one-shot report.

## HTTP API and Authentication

There are no HTTP endpoints, request/response bodies, listening ports, sessions, tokens, users, roles, or authentication flows. OS file permissions and the identity of the invoking local process define access. This intentionally replaces the generic blueprint template's API/auth sections; creating placeholder endpoints or auth would violate the product scope.

## Streaming and Resource Contract

Processing time is O(number of lines). The 24 hourly buckets are constant-space. IP counters, error-URL counters, and the exact User-Agent set are cardinality-dependent; calling the whole algorithm constant-space would therefore be false.

`--max-unique` sets a positive ceiling (default 1,000,000) for each exact high-cardinality collection. Before adding a new distinct IP, error URL, or User-Agent beyond its ceiling, aggregation raises a typed exhaustion error. The CLI emits no partial report, names the exhausted dimension on stderr, and exits 4. This fail-closed behavior preserves exactness; approximate sketches are outside MVP scope.

The acceptance benchmark uses a representative 1 GB fixture and a documented laptop. It must record elapsed wall time and peak RSS. Passing requires elapsed time under 30 seconds and no cardinality exhaustion at the declared fixture cardinalities.

## CLI Interface

### Command

```text
nginx-stream-stats [OPTIONS] [INPUT]...
```

With no `INPUT`, the command reads stdin. One or more paths are processed in order; `-` explicitly selects stdin. The command represents one analysis operation and needs no subcommands.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit JSON schema v1 to stdout; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit CSV schema v1 to stdout; mutually exclusive with `--json` |
| `--no-color` | flag, false | Disable Rich color in default terminal mode; ignored in machine modes because they never use color |
| `--encoding` | text, `utf-8` | Strict input decoding codec; unknown codecs are usage errors |
| `--max-unique` | positive integer, `1000000` | Per-dimension exact-cardinality ceiling |
| `--version` | flag | Print package version and exit 0 |
| `--help` | flag | Print Click help and exit 0 |

### Inputs

- Plain text nginx combined-format access logs from regular files, named pipes, or stdin.
- Multiple file paths are accepted; nonexistent/unreadable paths are input failures.
- P1 adds `.gz` auto-detection by suffix without changing the record semantics.
- Input is never modified and no sidecar/state file is written.

### Outputs

Default terminal output contains a processing summary, a top-10 IP table, a top-10 4xx/5xx URL table, a 24-row hourly percentage table, and exact unique User-Agent count/share. Color and layout are presentation only.

JSON stdout is one object:

```json
{
  "schema_version": 1,
  "summary": {"valid_requests": 0, "malformed_lines": 0},
  "top_ips": [{"rank": 1, "ip": "...", "request_count": 0}],
  "top_error_urls": [{"rank": 1, "url": "...", "error_count": 0}],
  "hourly_distribution": [{"hour": 0, "request_count": 0, "percentage": 0.0}],
  "user_agents": {"unique_count": 0, "share_percentage": 0.0}
}
```

CSV stdout begins with `schema_version,row_type,rank,key,count,percentage`. It emits summary rows, ranked `ip` and `error_url` rows, 24 `hour` rows (`key` is `00` through `23`), and a `user_agent_unique` row. Inapplicable cells are empty. Standard library CSV quoting and `\n` line endings are mandatory.

Data goes to stdout. Diagnostics and warnings go to stderr. Machine modes never include ANSI escape sequences, banners, or progress text.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Success, including a mix of valid and malformed lines; malformed count is reported |
| `1` | Runtime/input/output failure: open, read, decode, unexpected processing, or non-broken-pipe write failure |
| `2` | Click usage/configuration error: invalid option, incompatible modes, bad cardinality/encoding, or invalid stdin placement |
| `3` | Analysis completed but yielded zero valid requests |
| `4` | Unique-cardinality exhaustion: an exact IP, error-URL, or User-Agent collection would exceed `--max-unique` |

On a downstream closed pipe, follow normal Unix behavior: stop cleanly without a traceback. Tests pin the chosen platform-specific process status; it is not remapped to a misleading analytics result.

## Output Consistency

All three renderers consume the same finalized `Report`; they may not calculate metrics independently. Golden fixtures assert matching counts and percentages across Rich-normalized text, JSON, and CSV. Schema changes require a PRD/architecture update and a schema-version decision before code changes.

## Security and Privacy

Logs may contain personal data in IPs, URLs, referrers, and User-Agents. Processing remains local; there is no telemetry or network egress. Diagnostics must not echo entire malformed lines, and errors should name only the input path and line number where practical. The CLI follows paths supplied by the invoking user and does not elevate privileges. Documentation warns users that redirecting reports creates data that needs the same access controls as source logs.

## Deployment and Packaging

Deployment is a pip installation into Python 3.11 (preferably `pipx` for isolated CLI use). `pyproject.toml` declares the Click and Rich runtime dependencies, Python compatibility, package discovery, and the `nginx-stream-stats = nginx_stream_stats.cli:main` entry point. No Docker image, Compose file, daemon, cloud resource, or Kubernetes manifest is required. A source distribution and universal pure-Python wheel are the release artifacts.

There are no environment variables required for operation. Reproducibility comes from CLI arguments and input content; no hidden environment configuration controls report semantics.

There is no Docker or Compose runtime structure. A container would be optional downstream packaging, not architecture, and is excluded from the one-weekend MVP. The deployable artifacts are the wheel and source distribution only.

## Architecture Decision Records

### ADR-001: Single-process stateless pipeline

- **Status:** Accepted (pre-approved product decision).
- **Decision:** Use the linear local pipeline described above and the literal database/API decision statement in this document.
- **Why:** It minimizes operational surface and lets one pass produce every required metric.
- **Alternatives rejected:** GoAccess is a viable external product but does not define this narrow schema; Elastic/Logstash is stateful and operationally disproportionate; AWStats is report/history oriented; shell pipelines are too fragile for the promised parsing and schema contract; microservices, HTTP servers, and Kubernetes contradict explicit scope.
- **Consequence:** Horizontal/distributed processing and historical queries are not supported.

### ADR-002: Exact metrics with bounded failure

- **Status:** Accepted.
- **Decision:** Keep exact counters/sets until the configured ceiling, then exit 4 without output.
- **Why:** Approximation would silently change the meaning of top-10 and unique-share metrics.
- **Alternative rejected:** Probabilistic sketches reduce memory but need an accuracy/error contract not approved for MVP.

### ADR-003: One report model, three renderers

- **Status:** Accepted.
- **Decision:** Finalize one typed report and render it as terminal, JSON, or CSV.
- **Why:** Prevents semantic divergence and makes output-contract tests direct.

No Devil's Advocate review or inline substitute was performed in this blueprint session. The external harness owns that separate review and its artifact.

## Traceability

Product priorities and risks live in `STRATEGIC_PLAN.md`; executable user acceptance behavior lives in `PRD.md`; file-by-file delivery lives in `IMPLEMENTATION_PLAN.md`; implementation prompts must remain consistent with `CLAUDE_CODE_GUIDE.md`.
