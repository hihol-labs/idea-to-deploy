# Project Architecture: nginx-stream-insights

## Architecture Drivers

- Local Python 3.11 CLI for DevOps/SRE users.
- One input pass, no raw-log retention, and a 1 GB file in under 30 seconds on a documented laptop.
- Four metrics: top client IPs, error URLs, hourly percentages, and unique User-Agent share.
- Human-readable Rich output plus stable JSON and CSV.
- Pip installation, $0 budget, one-weekend scope.
- No authentication, database, HTTP API, server, cloud, or Kubernetes.

## Architecture Decision

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Both constraints are correct here. A database would add installation, migrations, disk writes, retention/security decisions, and slower time-to-first-result while the product promises a disposable summary of one stream. An HTTP API would require a long-running process, network security, serialization lifecycle, and service operations without improving the local file/stdin workflow. In-memory counters are the minimum sufficient state; CLI arguments and process exit codes are the correct integration boundary.

The approved design is one OS process with a synchronous pipeline:

```text
file path or stdin
       |
       v
 buffered text reader -> nginx line parser -> AggregateState
                              |                    |
                         malformed count      counters/sets
                                                   |
                                                   v
                                     text | JSON | CSV renderer
                                                   |
                                              stdout/stderr
```

This is an obvious solo-MVP choice, so framework, database, API, auth, and deployment variants are not presented as open decisions. Alternatives are recorded below only to preserve rationale.

## CLI Interface

### Command

```text
nginx-stream-insights [OPTIONS] [INPUT]
```

`INPUT` is an optional nginx access-log path. Omitted input or `-` reads UTF-8 text from stdin. The command processes exactly one stream per invocation.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit exactly one JSON document; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit RFC 4180-compatible long-form CSV; mutually exclusive with `--json` |
| `--log-format` | `combined` | Select `combined` or `common` parser profile |
| `--top` | integer, `10` | Number of ranked IPs and error URLs; must be 1–1000 |
| `--max-unique-user-agents` | integer, `1000000` | Maximum exact User-Agent cardinality before exit 4 |
| `--color/--no-color` | auto | Force or suppress ANSI color in text mode; auto colors only a TTY |
| `--version` | flag | Print version and exit 0 |
| `--help` | flag | Print usage and exit 0 |

### Inputs

- Regular file, named pipe, or stdin as selected above.
- Supported records are nginx common/combined access-log lines with IP, timestamp including numeric UTC offset, request target, status, and optional User-Agent.
- The request target is normalized to the URL path plus query exactly as logged; the method/protocol are excluded from URL ranking.
- Lines that do not match the selected format are counted as malformed and skipped. An input with zero valid records exits 3.
- Timestamps are grouped by their logged local hour (`00`–`23`); no timezone conversion is performed.

### Outputs

Text output contains a summary followed by ranked IPs, ranked error URLs, a 24-row hourly distribution, and User-Agent uniqueness. Hourly percentage is defined literally as `100 × hourly_request_count / total_valid_requests`; all 24 percentages are computed from valid records and displayed to two decimal places.

JSON uses this versioned shape:

```json
{
  "schema_version": 1,
  "summary": {"total_lines": 0, "valid_requests": 0, "malformed_lines": 0},
  "top_ips": [{"ip": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"url": "/missing", "count": 1}],
  "hourly_distribution": [{"hour": 0, "request_count": 1, "percentage": 100.0}],
  "user_agents": {"unique_count": 1, "valid_request_count": 1, "unique_share_percentage": 100.0}
}
```

CSV uses columns `metric,rank,key,count,percentage`. Summary rows use metric names such as `valid_requests`; ranked rows use `top_ip` and `top_error_url`; all 24 `hourly_distribution` rows carry count and percentage; `unique_user_agent_share` carries unique count and percentage. Empty cells are blank. Structured output goes only to stdout; diagnostics go only to stderr. No structured mode emits ANSI sequences.

The unique User-Agent share is `100 × distinct_nonempty_user_agents / valid_requests_with_user_agent`. It is `0.0` when no valid record contains a User-Agent. Exact cardinality is retained only up to the configured ceiling.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Successful analysis and rendering |
| `1` | Input I/O failure, including unreadable path or interrupted read |
| `2` | CLI usage/configuration error, including conflicting format flags |
| `3` | Parse failure: input was read but contained zero valid requests |
| `4` | Unique-cardinality exhaustion: distinct User-Agents exceeded the configured exact limit |

## Component Design

| Component | Responsibility | Key interface |
|---|---|---|
| `cli.py` | Click command, validation, stream ownership, exit mapping | `main(input, output_mode, ...)` |
| `parser.py` | Compile format-specific regex and parse one line | `parse_line(line, profile) -> LogRecord | None` |
| `models.py` | Immutable `LogRecord`, result rows, and configuration dataclasses | Typed data only |
| `aggregator.py` | Update counters/set and finalize deterministic rankings | `consume(record)`, `snapshot()` |
| `renderers/text.py` | Rich terminal tables and warnings | `render(result, console)` |
| `renderers/json.py` | Schema-versioned JSON | `render(result, stream)` |
| `renderers/csv.py` | Long-form CSV | `render(result, stream)` |

`LogRecord` carries `client_ip: str`, `timestamp: datetime`, `url: str`, `status: int`, and `user_agent: str | None`. `AggregateState` carries total/valid/malformed counts, `Counter[str]` for IPs and error URLs, a fixed 24-element integer array, and `set[str]` for exact nonempty User-Agents. Rankings sort by descending count then ascending key for deterministic ties.

## Processing and Complexity

Each line is parsed once and updates O(1)-average counters. Runtime is O(n + k log k), where n is line count and k is distinct ranked keys at finalization. Memory is O(distinct IPs + distinct error URLs + distinct User-Agents); the User-Agent set has an explicit ceiling and exits 4 rather than silently approximating. The performance path uses buffered iteration, a precompiled regex, primitive counter updates, and no Rich rendering until EOF.

The 1 GB target is an acceptance benchmark, not a claim independent of hardware. The benchmark records CPU, memory, Python version, storage medium, valid/malformed mix, elapsed wall time, and peak RSS. If unbounded distinct IP/URL keys become material in adversarial inputs, a later version may add explicit ceilings or approximate modes; the MVP preserves exact top-10 results.

## Data Model and Persistence

There is no database and therefore no database tables, schema migrations, indexes, or stored records. The template’s database-table requirement is intentionally inapplicable because persistence contradicts an explicit product constraint. All state lives inside one process and is released at exit.

| In-memory structure | Type | Constraint |
|---|---|---|
| IP counts | `Counter[str]` | One key per distinct parsed client IP |
| Error URL counts | `Counter[str]` | Updated only for status 400–599 |
| Hour counts | `list[int]` length 24 | Indexed by logged hour |
| User-Agents | `set[str]` | Nonempty values; configured cardinality maximum |
| Accounting | integer fields | `total_lines = valid_requests + malformed_lines` |

No temporary file, cache, telemetry record, or result history is created.

## API and Authentication

There is no HTTP API, so there are no endpoints, methods, request bodies, or network error contracts. The complete public interface is `## CLI Interface`. There is no authentication because execution authority and file access are inherited from the invoking local OS user; adding application credentials would neither protect the source file from that user nor create a meaningful trust boundary.

## Packaging and Deployment

The package uses a `src/` layout, `pyproject.toml`, a locked lower/upper dependency policy, and a console script named `nginx-stream-insights`. Deployment is `python3.11 -m pip install nginx-stream-insights` into a virtual environment or isolated CLI installer. No Docker image, compose file, server unit, cloud resource, or Kubernetes manifest is part of the product. A wheel and source distribution are sufficient artifacts.

No required environment variables exist. Locale does not affect structured output; encoding errors are reported as input failures. `NO_COLOR` is honored for text output, while `--color` and `--no-color` take explicit precedence.

## Repository Layout

```text
pyproject.toml
src/nginx_stream_insights/
  __init__.py
  cli.py
  models.py
  parser.py
  aggregator.py
  renderers/
    __init__.py
    text.py
    json.py
    csv.py
tests/
  fixtures/
  test_parser.py
  test_aggregator.py
  test_cli.py
  test_renderers.py
  test_performance.py
```

## Reliability and Security

- Treat log content as untrusted data: never evaluate fields or interpolate them into shell commands.
- Rich escapes control sequences in displayed log values; JSON and `csv` standard-library encoders quote values.
- Broken pipes terminate quietly with the conventional successful pipeline behavior only after output production begins; input read failures remain exit 1.
- SIGINT returns exit 1 with a concise diagnostic and no traceback by default.
- Tests cover oversized lines, Unicode, control characters, missing fields, invalid timestamps/statuses, deterministic ties, and output separation.
- The tool performs no network calls or telemetry and never writes the input elsewhere.

## Observability

The result itself includes line accounting. Human mode warns about malformed rows. JSON exposes counts in `summary`; CSV emits equivalent summary rows. Timing or debug output is not included in stable stdout; future diagnostics, if added, must go to stderr behind an explicit flag.

## Architectural Alternatives Considered

| Alternative | Why rejected for MVP |
|---|---|
| Multiprocessing chunks | Complex record-boundary handling and merge overhead before profiling proves a need |
| SQLite-backed aggregation | Violates statelessness and adds write amplification/setup |
| Local HTTP service | Adds lifecycle, port, and security concerns with no CLI benefit |
| Go rewrite | Could improve throughput but violates the approved stack before Python is benchmarked |
| HyperLogLog for User-Agents | Bounded memory but approximate; requirement is clearer with exact results and explicit exhaustion |

## Architecture Decision Record

### ADR-001: Single synchronous streaming process

- **Status:** Accepted by the supplied product brief.
- **Decision:** Parse and aggregate in one Python process, then render once.
- **Consequences:** Simple installation and deterministic behavior; counters scale with key cardinality, and exact User-Agent cardinality has an explicit limit.

### ADR-002: No persistence or network interface

- **Status:** Accepted by the supplied product brief.
- **Decision:** Use only local input/output and ephemeral memory.
- **Consequences:** $0 operations and no data-retention risk; cross-run trend analysis stays out of scope.

No adversarial or independent review was performed in this blueprint session. Per the benchmark protocol, that review is reserved for the external harness and no review verdict is recorded here.

