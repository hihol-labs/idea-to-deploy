# Project Architecture: Nginx Stream Analyzer

## Architecture Context

The product is a local Python 3.11 process that consumes nginx access-log lines from one file or standard input, parses each line once, updates in-memory aggregates, and renders a final report. Its trust boundary is the local process: log content is untrusted data, while the operator controls CLI arguments and output destination.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect here because the required outputs can be computed in a single pass, persistence would increase latency and operational burden, and retention is outside scope. An HTTP API is incorrect because the users work locally or in shell pipelines, no multi-user service is needed, and a server would add lifecycle, security, and deployment concerns with no MVP value.

## Architecture Decision

The approved architecture is a single-process, layered CLI. Click owns argument validation and exit mapping; an input adapter yields text lines; a parser returns typed dataclasses; an aggregator updates counters and cardinality state; output renderers consume one immutable report model. No event list is retained.

### Obvious Alternatives Considered

| Alternative | Benefit | Why rejected for this scope |
|---|---|---|
| Multi-process parsing | Potential CPU parallelism | Ordering, IPC, merging, and startup overhead threaten weekend scope; benchmark before adding complexity |
| Embedded SQLite | Familiar aggregation with SQL | Adds writes, temporary storage, schema lifecycle, and disk dependence to a one-pass problem |
| Local HTTP service | Reusable endpoint | Adds server/auth/concurrency contracts when shell invocation already provides composition |

These are not open product decisions. The single-process variant is selected because the user pre-approved the obvious architecture.

## Component Model

```text
CLI arguments
     |
     v
Input source -> line parser -> streaming aggregator -> Report dataclass
                    |                  |                     |
                    v                  v                     v
             malformed counter   cardinality guard   text/json/csv renderer
                                                           |
                                                           v
                                                     stdout / stderr
```

| Component | Responsibility | Must not do |
|---|---|---|
| `cli.py` | Define Click command/options, select renderer, map domain failures to exits | Parse log grammar or own aggregation logic |
| `input.py` | Open UTF-8-compatible text input or use stdin; surface I/O failures | Buffer the entire file |
| `parser.py` | Parse supported nginx combined/common-compatible fields into `AccessRecord` | Emit output or mutate counters |
| `models.py` | Define `AccessRecord`, ranked row, hourly row, and `AnalysisReport` dataclasses | Depend on Click or Rich |
| `aggregate.py` | Maintain total counts, top-key counters, hours, unique User-Agents, and limits | Store raw records |
| `renderers/text.py` | Render accessible Rich terminal tables | Change metric values |
| `renderers/json.py` | Serialize the stable JSON object | Add ANSI formatting |
| `renderers/csv.py` | Serialize normalized CSV rows | Create multiple ambiguous CSV schemas |
| `errors.py` | Define failure categories and public exit codes | Print directly |

## Data and State Model

There are no database tables. Runtime state is process-local and discarded at exit.

### Parsed record

`AccessRecord` contains only fields needed by the four metrics:

| Field | Type | Constraint |
|---|---|---|
| `client_ip` | `str` | Non-empty token from the declared log grammar |
| `timestamp` | timezone-aware `datetime` | Parsed from nginx timestamp |
| `request_target` | `str` | URL/request-target token; method/protocol excluded from the ranking key |
| `status` | `int` | Three-digit HTTP status |
| `user_agent` | `str` | Quoted field; `-` is a valid literal value |

### Aggregation state

| State | Type | Growth / invariant |
|---|---|---|
| `total_lines` | `int` | Increment once per input line |
| `total_valid_requests` | `int` | Increment once per parsed record |
| `malformed_lines` | `int` | `total_lines = total_valid_requests + malformed_lines` |
| `ip_counts` | `Counter[str]` | One key per distinct IP, guarded by configured hard cardinality limit |
| `error_url_counts` | `Counter[str]` | Updated only for status 400–599, guarded by hard limit |
| `hour_counts` | fixed 24-element integer array | Index 0–23 in the timestamp's logged offset; bounded |
| `unique_user_agents` | `set[str]` | Exact uniqueness, guarded by hard limit |

The unique User-Agent share is `(unique_user_agent_count / total_valid_requests) × 100`. Hourly request distribution is a percentage computed for each hour using the literal formula `100 × hourly_request_count / total_valid_requests`. When there are no valid requests, neither percentage is fabricated; the command fails with exit code 3.

### Cardinality safety

Exact top counts require retaining a counter entry per distinct IP and error URL, and exact unique User-Agent share requires a set. The implementation defines conservative hard limits for all three structures. If inserting a new key would cross any limit, processing stops with exit code 4 (unique-cardinality exhaustion). The diagnostic identifies the exhausted dimension but never prints the untrusted log value. Approximation or spill-to-disk is outside MVP scope.

## Streaming Algorithm

For each line:

1. Increment `total_lines`.
2. Parse the line into an `AccessRecord`; on a malformed line, increment `malformed_lines` and continue.
3. Before adding new distinct keys, enforce cardinality limits.
4. Increment valid-request, IP, and hour counters.
5. For status 400–599, increment the request-target error counter.
6. Add the User-Agent to the exact set.

At EOF, reject an input with zero valid requests. Otherwise select deterministic top-10 rows by descending count and then ascending key, compute percentages, create `AnalysisReport`, and render once. Time complexity is `O(n + k log 10)` for `n` lines and `k` distinct ranking keys; memory is `O(i + u + a)` for distinct IPs, error URLs, and User-Agents, bounded by configured limits.

## CLI Interface

### Commands

Installable console command:

```text
nginx-stream-analyzer [OPTIONS] [INPUT]
```

`INPUT` is a path to one nginx access-log file. If omitted or `-`, lines are read from stdin. Exactly one input stream is processed per invocation.

### Options

| Option | Meaning | Default / rule |
|---|---|---|
| `--json` | Write the JSON report to stdout | Mutually exclusive with `--csv` |
| `--csv` | Write normalized CSV rows to stdout | Mutually exclusive with `--json` |
| `--no-color` | Disable Rich color in terminal text | Text mode only |
| `--version` | Print package version and exit | Exit 0 |
| `--help` | Print usage and exit | Exit 0 |

Unknown options, conflicting formats, or more than one positional input are CLI usage errors.

### Inputs

- Supported grammar: nginx combined log format and common-log-compatible lines when the User-Agent field is present as `-`.
- Text decoding: UTF-8 with replacement for invalid byte sequences so one bad byte does not abort a large file.
- Timestamps retain the logged numeric timezone offset; hourly buckets use the logged local hour.
- Request ranking key is the parsed request target, including its query string. Future normalization is a versioned behavior change.
- Malformed lines are skipped and counted. A stream with no valid lines is invalid data.

### Outputs

Default text output contains four named sections plus processed/valid/malformed totals. Color is emitted only in text mode when stdout is an interactive terminal and color is not disabled. Diagnostics go to stderr; data goes to stdout.

JSON is one object:

```json
{
  "schema_version": 1,
  "summary": {"total_lines": 0, "total_valid_requests": 0, "malformed_lines": 0},
  "top_ips": [],
  "top_error_urls": [],
  "hourly_request_distribution": [],
  "unique_user_agents": {"count": 0, "share_percent": 0.0}
}
```

Ranked rows contain `rank`, `value`, and `count`. Hour rows contain `hour`, `request_count`, and `percentage`, including all 24 hours in `00` through `23` order. Numeric percentages are rounded to two decimal places only at serialization.

CSV has one header and a normalized schema:

```text
section,rank,key,count,percentage
```

Sections are emitted in this fixed order: `top_ip`, `top_error_url`, `hour`, `unique_user_agent_summary`, `input_summary`. Non-applicable cells are empty. CSV is RFC 4180-compatible and written through Python's `csv` module.

### Exit-code contract

| Code | Name | Contract |
|---:|---|---|
| 0 | Success | Report was fully computed and written |
| 1 | Input/output failure | Input cannot be opened/read or output cannot be written |
| 2 | Usage failure | Click argument or option validation failed |
| 3 | Invalid log data | Input completed but contained zero valid supported records |
| 4 | Unique-cardinality exhaustion | A configured distinct-IP, error-URL, or User-Agent limit would be exceeded |

The complete public contract is `0/1/2/3/4`; code 4 is never remapped to a generic I/O or data error.

## Output Determinism and Numerical Rules

- Top lists contain at most 10 items and break equal counts by Unicode code-point ascending key.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`; serialized values are rounded to two decimal places.
- The sum of displayed hourly percentages may differ slightly from 100.00 because each bucket is rounded independently.
- User-Agent uniqueness is case-sensitive and exact within the cardinality limit.
- JSON object/array semantics are stable; consumers must not depend on insignificant whitespace.
- Text layout and color are presentation, not a machine-readable contract.

## Error Handling and Security

Log lines are untrusted. The tool does not execute, interpolate, fetch, or open paths found in log content. Rich rendering treats values as plain text with markup disabled or escaped. CSV cells use the standard writer; values beginning with formula-control characters are prefixed with a single quote to reduce spreadsheet formula injection risk. JSON uses the standard encoder. Diagnostics omit full log lines and cap malformed examples to avoid secret leakage and terminal flooding.

SIGINT follows conventional Click interruption behavior and does not emit a partial success report. Broken-pipe output is treated as an output failure unless Click/platform behavior safely terminates before a misleading report is claimed.

## Packaging and Runtime

The project is a pip-installable package using a `src/` layout and a console-script entry point. Runtime dependencies are pinned to compatible Click and Rich ranges. No Docker image, compose file, environment variables, service manager, network port, authentication flow, or deployment target exists. Deployment means installing the package into a Python 3.11 environment with pip or `pipx` and invoking it locally.

Proposed source topology for implementation:

```text
pyproject.toml
src/nginx_stream_analyzer/
  __init__.py
  cli.py
  input.py
  parser.py
  aggregate.py
  models.py
  errors.py
  renderers/
    text.py
    json.py
    csv.py
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_performance.py
```

## Performance Plan

The acceptance fixture is a generated, representative 1 GB supported-format log stored outside Git. The benchmark records Python version, CPU, storage type, wall-clock seconds, and peak RSS. It runs from a local file with output redirected away from terminal rendering. The release threshold is under 30 seconds on the documented reference laptop. Optimization proceeds only from profiling evidence, prioritizing parser hot paths and allocation reduction while preserving the public contract.

## Architecture Decision Record (ADR)

### ADR-001: Single-process stateless CLI

- **Status:** Accepted by pre-approved product constraints.
- **Decision:** Use one Python 3.11 process with layered parser, aggregator, and renderers.
- **Consequences:** Simple installation and deterministic behavior; CPU parallelism is deferred unless measured need outweighs complexity.

### ADR-002: Exact metrics with fail-closed cardinality limits

- **Status:** Accepted.
- **Decision:** Preserve exact counts up to explicit limits and terminate with exit code 4 before unsafe growth.
- **Consequences:** Results are never silently approximate; adversarial high-cardinality logs can intentionally stop analysis.

### ADR-003: No inline adversarial review in this blueprint session

- **Status:** Required by the benchmark session contract.
- **Decision:** Do not create `DEVILS_ADVOCATE_REVIEW.md` and do not claim independent review.
- **Consequence:** The external harness will run the actual reviewer in a fresh session; this document contains no substitute self-critique or reviewer verdict.
