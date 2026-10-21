# Project Architecture: nginx-stream-report

## Architecture Summary

The chosen architecture is a single Python 3.11 process with a streaming pipeline:

```text
file path or stdin
       |
       v
line iterator -> parser -> validated LogRecord -> Aggregator -> Report
                    |                              |
                    +-> malformed counter          +-> text | JSON | CSV renderer
```

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the required metrics can be accumulated during one pass, persistence adds cost and lifecycle complexity, and the product explicitly analyzes local input without retaining it. An HTTP API is incorrect because the user is an engineer at a shell, file/stdin are the natural input transports, and a server would introduce authentication, networking, deployment, and operational concerns without improving the one-command workflow.

The architecture is bounded except for the exact set used to calculate unique User-Agent cardinality. That set has an explicit configurable maximum; crossing it aborts with exit code `4` rather than swapping, crashing unpredictably, or silently returning an approximation.

## Architecture Decision

The approved architecture is a layered single-process CLI, not a service and not a distributed system. Product constraints make the alternatives obvious, so no architecture-selection pause is needed.

### Chosen Variant: Layered Single-Process Streaming CLI

- **Approach:** Click owns the command boundary; an input adapter yields lines; a parser creates immutable dataclass records; one aggregator updates counters; one selected renderer writes the final report.
- **Pros:** one-pass I/O, straightforward tests, no persistent state, pip installation, clean separation of parsing/analysis/presentation.
- **Cons:** CPU work is single-process; exact unique cardinality consumes memory proportional to distinct User-Agents until its safety ceiling.
- **Best for:** local incident triage and shell pipelines on laptop-scale logs.
- **Estimated complexity:** Low.

### Rejected Variant: Shell Pipeline (`grep`/`awk`/`sort`)

- **Approach:** Compose separate Unix tools for each metric.
- **Pros:** no package install on many systems; quick for one-off questions.
- **Cons:** repeated reads/sorts, fragile quoting and parsing, inconsistent error handling, no shared output schema.
- **Rejected because:** it cannot provide the required stable multi-format contract and tested semantics economically.

### Rejected Variant: GoAccess or Elastic Stack Wrapper

- **Approach:** Delegate analysis to an existing analyzer or ingestion platform.
- **Pros:** mature feature sets and broader analysis capabilities.
- **Cons:** mismatched output contract; the Elastic path adds persistent services and cost; a wrapper inherits external configuration complexity.
- **Rejected because:** the narrow one-weekend product needs a predictable local pipeline, not an integration layer.

## CLI Interface

### Command

```text
nginx-stream-report [OPTIONS] [INPUT]
```

`INPUT` is a path to one nginx access-log file. If omitted or equal to `-`, bytes are read from standard input. Input is decoded as UTF-8 with invalid byte sequences treated as malformed lines. Version 1 supports the standard nginx combined access-log format. The program reads sequentially and never seeks, enabling pipes and large files.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one UTF-8 JSON document to stdout |
| `--csv` | flag, false | Emit UTF-8 RFC 4180-compatible long-form CSV to stdout |
| `--max-unique-user-agents INTEGER` | positive integer, `1000000` | Abort with code `4` before retaining more distinct User-Agents than the ceiling |
| `--no-color` | flag, false | Disable color in default text mode |
| `--version` | flag | Print package version and exit `0` |
| `--help` | flag | Print usage and exit `0` |

`--json` and `--csv` are mutually exclusive; selecting both is a usage error (`2`). Color is used only in default text output when stdout is a capable terminal and `NO_COLOR` is not set. JSON and CSV never contain ANSI escape sequences.

### Inputs

- One regular file path, `-`, or omitted input for stdin.
- Standard nginx combined-log lines, processed incrementally.
- Empty lines and lines that do not match the grammar are malformed and counted.
- Timestamps retain the offset from the log line; the hour bucket is the logged local hour `00` through `23` without timezone conversion.
- URL ranking uses the request-target token as logged, including query string. A request line without a parseable target is malformed.
- Status codes `400`–`599` contribute to error-URL ranking; all other valid status codes do not.
- A missing User-Agent represented by `"-"` is a valid literal category; unique share is therefore well-defined for every valid record.

### Outputs

All rankings use count descending, then key ascending for deterministic ties. Each top list contains at most 10 entries.

Hourly request distribution is the percentage `100 × hourly_request_count / total_valid_requests` for each of 24 buckets. With zero valid requests, no report is emitted and the program exits `3`, so division by zero never occurs. Percentages are represented to two decimal places in text/CSV and as JSON numbers rounded to two decimal places.

Unique User-Agent share is `100 × distinct_user_agent_count / total_valid_requests`, not the proportion of requests with non-empty User-Agents. It is represented to two decimal places.

Default text output contains a summary (valid and malformed counts), a top-IP table, a top error-URL table, a 24-row hourly percentage table, and the distinct User-Agent count/share. Diagnostics go to stderr.

JSON has this stable top-level shape:

```text
{
  "schema_version": 1,
  "summary": {"valid_requests": integer, "malformed_lines": integer},
  "top_ips": [{"ip": string, "count": integer}],
  "top_error_urls": [{"url": string, "count": integer}],
  "hourly_distribution": [{"hour": "00".."23", "request_count": integer, "percentage": number}],
  "unique_user_agents": {"count": integer, "share_percentage": number}
}
```

CSV is long-form with the fixed header `metric,rank,key,count,percentage`. Rows use metrics `summary_valid`, `summary_malformed`, `top_ip`, `top_error_url`, `hourly_requests`, and `unique_user_agents`. Non-applicable fields are empty; `key` contains an IP, URL, hour, or `distinct` as appropriate.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Analysis completed and a report was emitted |
| `1` | Input or runtime I/O failure, including unreadable file or broken output |
| `2` | CLI usage error, including conflicting formats or invalid option value |
| `3` | No valid log records were available after parsing input |
| `4` | Unique-cardinality exhaustion: the configured distinct User-Agent ceiling would be exceeded |

No partial report is written after a fatal error. For JSON/CSV, stdout remains machine-data-only and diagnostics are written to stderr.

## Component Design

| Module | Responsibility | Key public objects |
|---|---|---|
| `src/nginx_stream_report/cli.py` | Click command, option validation, stream lifecycle, exit mapping | `main` |
| `src/nginx_stream_report/models.py` | Immutable parsed record and report dataclasses | `LogRecord`, `Report`, ranking entry types |
| `src/nginx_stream_report/parser.py` | Precompiled combined-log parser and timestamp/request extraction | `parse_line` |
| `src/nginx_stream_report/aggregator.py` | One-pass counters, unique-UA ceiling, deterministic finalization | `Aggregator`, `UniqueCardinalityExhausted` |
| `src/nginx_stream_report/renderers/text.py` | Rich terminal report | `render_text` |
| `src/nginx_stream_report/renderers/json.py` | Schema-versioned JSON | `render_json` |
| `src/nginx_stream_report/renderers/csv.py` | Long-form CSV | `render_csv` |

`LogRecord` contains `ip: str`, `hour: int`, `request_target: str`, `status: int`, and `user_agent: str`. It intentionally excludes fields not required by the reports. `Report` contains valid/malformed counts, finalized top lists, all 24 hourly counts and percentages, and unique-UA count/share.

## Streaming and Complexity

For `n` valid lines, processing is `O(n)` expected time. Counters hold one entry per distinct IP and error URL; the unique-UA set holds at most the configured ceiling; the hourly array has exactly 24 counters. Final ranking uses `heapq.nsmallest`/equivalent bounded selection or sorting after measurement confirms it fits the 1 GB target. The parser is compiled once, renderer selection occurs before reading, and records are not retained.

Backpressure is inherited from synchronous file/stdin reads. There are no worker queues, background threads, temporary databases, or intermediate files. A benchmark fixture should represent realistic line length, cardinalities, successful/error status mix, and malformed records.

## Data Storage and Database

There is no database, schema, migration, cache service, or durable application state. In-memory structures exist only for the command lifetime:

| Structure | Key/value | Bound/lifetime |
|---|---|---|
| IP counter | `str -> int` | Distinct IPs in one run |
| Error URL counter | `str -> int` | Distinct 4xx/5xx request targets in one run |
| Hour counters | `list[int]` of length 24 | Constant, one run |
| User-Agent set | `set[str]` | Explicit `--max-unique-user-agents` ceiling, one run |

The generic blueprint template’s request for database tables is intentionally inapplicable: inventing three tables would violate the approved product boundary and worsen performance and operability.

## HTTP API and Authentication

There are no HTTP endpoints and no authentication flow. OS file permissions and the invoking user define access to input logs and destinations. The tool makes no network connections. The generic blueprint template’s endpoint/auth sections are intentionally satisfied by this explicit non-applicability decision rather than fictitious interfaces.

## Security and Privacy

- Treat every log field as untrusted data; renderers escape/encode it through Rich, `json`, or `csv`, never terminal markup interpretation.
- Never execute, fetch, resolve, or interpolate values found in logs.
- Do not log full input records in diagnostics by default; report line numbers and error categories.
- Avoid symlink policy inventions: use normal OS open semantics and document that users control the path.
- Do not send telemetry or network requests.
- Bound unique-UA cardinality and surface exhaustion explicitly as exit code `4`.

## Packaging and Deployment

The deployment target is a local Python 3.11 environment. `pyproject.toml` declares Click and Rich and exposes the `nginx-stream-report` console script. Users install with pip from a source checkout or package artifact. There is no Docker image, `docker-compose.yml`, server deployment, cloud resource, or Kubernetes manifest because those artifacts contradict the local CLI scope.

## Configuration and Environment

No environment variables are required. `NO_COLOR`, when present according to its common convention, disables terminal color. Locale does not alter JSON keys, CSV headers, sorting, decimal separators, or exit behavior.

## Testing Strategy

- Parser unit tests cover valid combined lines, escaping, IPv4/IPv6, malformed timestamps/status/request lines, UTF-8 errors, and very long fields.
- Aggregator unit tests cover every metric, status boundaries, tie ordering, all 24 hours, formula rounding, and the unique-UA ceiling.
- Renderer golden tests validate text sections, JSON shape/types, CSV header/rows, Unicode, quoting, and absence of ANSI in machine formats.
- CLI integration tests cover file/stdin parity, options, stderr separation, and the complete `0/1/2/3/4` contract.
- A repeatable benchmark checks a representative 1 GB input under 30 seconds and records the laptop CPU, RAM, OS, Python patch version, and peak RSS.

## Architecture Decision Record (ADR)

### ADR-001: Local Stateless CLI

- **Status:** Accepted by the product brief.
- **Decision:** Use one Python process and one streaming pass; provide no database, API, server, authentication, cloud, or Kubernetes components.
- **Reason:** This is the least complex architecture that meets the user workflow, budget, privacy posture, and performance target.
- **Consequences:** Installation is simple and input stays local. Cross-run queries and dashboards are deliberately unavailable.

### ADR-002: Exact Unique Cardinality With Fail-Closed Ceiling

- **Status:** Accepted.
- **Decision:** Calculate exact distinct User-Agent count until an explicit ceiling, then exit `4`.
- **Reason:** An approximate sketch would make the required share semantically surprising, while an unbounded set can exhaust memory.
- **Consequences:** Results are exact when emitted; exceptionally high-cardinality input requires a higher explicitly chosen ceiling or a future product decision.

No Devil's Advocate or independent architecture review is recorded here; that review is outside this session by instruction.
