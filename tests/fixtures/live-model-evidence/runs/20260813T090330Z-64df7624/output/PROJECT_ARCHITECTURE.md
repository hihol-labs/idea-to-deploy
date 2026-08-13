# Project Architecture: Nginx Insights CLI

## 1. Context and Goals

The system is a local Python 3.11 process that consumes nginx combined access logs sequentially and produces one report. The design target is a representative 1 GB input in under 30 seconds on a documented laptop, with no persistent or network service. `PRD.md` owns product behavior; this document owns component boundaries and interface contracts.

## 2. Architecture Decision

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Both constraints are correct here. A database would add writes, schema lifecycle, storage cost, cleanup, and privacy exposure even though every required metric can be computed during one sequential scan. An HTTP API would require a long-running server, authentication and authorization decisions, port and deployment management, and a new attack surface while offering no advantage to a user who already has the log locally or on stdin. The CLI composes directly with SSH, pipes, schedulers, and shell redirection.

The approved architecture is one OS process with internal modules. The log content is not retained after exit. Aggregate maps and the User-Agent set exist only in memory and are bounded by a cardinality guard.

## 3. Architecture Alternatives

The architecture is pre-approved because the single-process choice is obvious for the stated scope; these alternatives are recorded for traceability, not presented as open decisions.

| Variant | Approach | Advantages | Disadvantages | Decision |
|---|---|---|---|---|
| A: Modular single-process CLI | Parser, aggregator, and renderers run in one Python process | Minimal operations, direct streaming, easy pip install | Bound by one process and Python throughput | **Selected** |
| B: Shell pipeline | Compose `awk`, `sort`, and related tools | No package install on many hosts | Format-sensitive, usually multiple passes, weak cross-platform output contract | Rejected |
| C: Local service with persistence | Ingest into a database and expose UI/API | Historical queries and multi-user access | Violates stateless, CLI-only, $0-operations scope | Rejected |

## 4. System Context and Data Flow

```text
file path or stdin
       |
       v
 [byte/text line reader] --I/O error--> exit 1
       |
       v
 [combined-log parser] --malformed--> diagnostic counter
       |
       v
 [streaming aggregator] --unique limit--> exit 4
       |
       v
 [immutable report]
       |
       +--> Rich terminal renderer
       +--> JSON renderer
       `--> CSV renderer
```

There is one pass over input. No renderer starts until aggregation succeeds, preventing misleading partial output on failure.

## 5. Package and Component Design

```text
pyproject.toml
src/nginx_insights/
  __init__.py
  cli.py              # Click command, input lifecycle, exit mapping
  models.py           # dataclasses: LogRecord, Report, RankedCount
  parser.py           # compiled combined-log parser and timestamp handling
  aggregate.py        # one-pass counters, percentages, cardinality guard
  errors.py           # typed domain failures and exit-code mapping
  renderers/
    __init__.py
    terminal.py       # Rich tables and diagnostics
    json.py           # stable JSON document
    csv.py            # normalized CSV rows
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_renderers.py
  test_performance.py
```

### Dataclasses

| Type | Fields | Invariants |
|---|---|---|
| `LogRecord` | `ip: str`, `timestamp: datetime`, `method: str`, `target: str`, `protocol: str`, `status: int`, `user_agent: str` | Status is 100–599; timestamp has source offset; target is nonempty |
| `RankedCount` | `key: str`, `count: int`, `rank: int` | Count > 0; rank starts at 1 |
| `HourlyBucket` | `hour: int`, `count: int`, `percentage: float` | Hour 0–23; percentage 0–100 |
| `UserAgentSummary` | `unique_count: int`, `eligible_count: int`, `total_valid_requests: int`, `percentage: float` | Nonnegative counts; percentage uses total valid requests |
| `Report` | top IPs, error URLs, 24 hourly buckets, UA summary, `valid_lines`, `malformed_lines` | Exactly 24 ordered hours; at most 10 ranked entries per list |

## 6. Parsing Contract

MVP accepts the standard nginx combined access-log shape:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

- Input is decoded as UTF-8 with invalid bytes treated as a malformed line, not silently replaced.
- The parser compiles its matching expression once. It parses the timestamp offset and preserves the hour expressed in the log record; it does not convert to the machine timezone.
- Request is split into method, request target, and protocol. The target is counted as emitted by nginx, including its query string; no URL decoding or normalization occurs in MVP.
- Status must be a three-digit integer from 100 through 599.
- Malformed lines increment `malformed_lines` and are skipped by default. If no valid record remains, processing fails with exit 3.
- The `--strict` option stops on the first malformed line with exit 3 and a line-number diagnostic.

## 7. Aggregation and Resource Bounds

For every valid record, the aggregator increments total requests, the exact IP count, and one of 24 source-local hourly buckets. It increments the target count only for statuses 400–599. A nonempty, non-`-` User-Agent is inserted into the User-Agent set.

Hourly request distribution is a percentage calculated exactly as `100 × hourly_request_count / total_valid_requests`. The report contains all 24 hours. Unique User-Agent share is `100 × distinct_nonempty_user_agents / total_valid_requests`.

Top lists are selected after EOF with descending count and ascending key as the tie-breaker. At most 10 entries are emitted. Processing time is O(n + u log 10), where n is valid records and u is distinct ranked keys. Memory is O(unique IPs + unique error URLs + unique User-Agents), bounded by `--max-unique` across each individual cardinality-bearing collection. If adding a new key would exceed the configured limit, processing stops with exit 4 and emits no report.

The default unique limit is 1,000,000 per collection. This makes memory behavior explicit; the performance fixture must exercise both ordinary and adversarial cardinality distributions.

## CLI Interface

### Command

```text
nginx-insights [OPTIONS] [INPUT]
```

`INPUT` is a path to a plain-text log. Omit it or pass `-` to read stdin. Exactly one report is written to stdout; diagnostics go to stderr.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit one UTF-8 JSON object; mutually exclusive with `--csv` |
| `--csv` | false | Emit normalized RFC 4180-compatible CSV; mutually exclusive with `--json` |
| `--strict` | false | Fail on the first malformed input line |
| `--max-unique INTEGER` | `1000000` | Positive per-collection distinct-key cap |
| `--no-color` | false | Disable terminal color; machine formats never contain ANSI |
| `--version` | — | Print version and exit 0 |
| `--help` | — | Print usage and exit 0 |

### Inputs

- Seekability is not required; stdin may be an unbounded pipe terminated by EOF.
- Plain UTF-8 text only in MVP; gzip can be provided through `gzip -dc file.gz | nginx-insights`.
- Combined format is supported as specified in Section 6. Empty input and input with no valid records return exit 3.

### Outputs

Terminal output uses four Rich sections plus a parsing summary. Color is enabled only when stdout is a compatible TTY and `--no-color` is absent.

JSON schema:

```json
{
  "schema_version": 1,
  "total_valid_requests": 0,
  "malformed_lines": 0,
  "top_ips": [{"rank": 1, "ip": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"rank": 1, "url": "/missing", "count": 1}],
  "hourly_distribution": [{"hour": "00", "count": 0, "percentage": 0.0}],
  "user_agents": {"unique_count": 0, "eligible_count": 0, "percentage": 0.0}
}
```

`hourly_distribution` always has 24 entries. Percentages are JSON numbers rounded to two decimal places for display; tests allow for the expected rounding sum around 100.

CSV uses columns `metric,rank,key,count,percentage`. Top-list rows use `metric=top_ip|top_error_url`; hourly rows use `metric=hour` and `key=00..23`; one `unique_user_agent_share` row carries distinct count in `count` and its percentage. Values are quoted by the standard CSV writer as needed.

### Exit Codes

| Code | Meaning |
|---:|---|
| 0 | Success, including `--help` and `--version` |
| 1 | Input I/O or decoding failure |
| 2 | CLI usage error, invalid option/value, or conflicting formats |
| 3 | Log-data failure: strict-mode malformed line, empty input, or zero valid records |
| 4 | Unique-cardinality exhaustion: an IP, error-URL, or User-Agent collection would exceed `--max-unique` |

The complete public exit-code contract is `0/1/2/3/4`; values must not be remapped by renderers.

## 9. Database, API, Authentication, and Deployment

### Database

No database exists, so there are no tables, fields, migrations, indexes, credentials, or retention jobs. The in-memory dataclasses and collections in Sections 5 and 7 are transient runtime state, not a database.

### HTTP API

No HTTP API exists, so there are no endpoints, request bodies, response bodies, ports, CORS rules, or API versioning. The complete public interface is under `## CLI Interface`.

### Authentication

There is no authentication flow because there is no shared service or remote resource. File-read authorization is delegated to the operating system account running the process. The tool does not elevate privileges and must not log raw lines in diagnostics.

### Deployment

Deployment means building a wheel/sdist and installing it with pip into Python 3.11. There is no Docker image, Compose file, server, cloud target, or Kubernetes manifest. A clean virtual environment is the release-validation target.

## 10. Configuration and Environment

There are no required environment variables or `.env` file. Locale and terminal capabilities may influence Rich presentation only; JSON and CSV remain deterministic. All behavior-bearing settings are explicit CLI options.

## 11. Error Handling, Security, and Observability

- Paths and line numbers may appear in stderr; raw log lines, referrers, and User-Agent values must not appear in error diagnostics.
- Broken-pipe behavior should exit cleanly without a traceback when a downstream consumer closes stdout.
- Parsing is data-only: request targets and User-Agents are never evaluated, interpolated into shell commands, or interpreted as terminal markup.
- Rich markup is disabled/escaped for log-derived values.
- The final summary reports valid and malformed line counts. Machine outputs contain the same counts.
- No telemetry or outbound network access is permitted.

## 12. Performance Verification

The benchmark fixture generator creates a deterministic 1 GB combined log outside the repository and records its generation parameters. The timed command reads from a warm local filesystem into JSON redirected to a file; setup and fixture generation are excluded. The reference laptop model, CPU, RAM, OS, Python patch version, input size, record count, wall time, and peak RSS are recorded. Acceptance requires wall time <30 seconds, valid JSON, expected totals, and no cardinality exhaustion at defaults.

## 13. Architecture Decision Records

### ADR-001: Single-process streaming CLI

- **Status:** Accepted (pre-approved)
- **Decision:** Use the modular single-process variant with no persistence or network service.
- **Consequences:** Minimal operations and one-pass behavior; exact high-cardinality aggregates require guarded in-memory collections.

### ADR-002: Exact metrics with explicit cardinality failure

- **Status:** Accepted
- **Decision:** Prefer exact counts and an explicit cap over approximate sketches.
- **Consequences:** Results are reproducible; adversarial input can terminate with documented exit code 4 instead of degrading silently.

The adversarial architecture review is intentionally deferred to the external harness and is not represented as completed in this document.

