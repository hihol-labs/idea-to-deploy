# Project Architecture: Nginx Stream Analytics CLI

## Context and Constraints

The product is an installable Python 3.11 CLI used locally by DevOps/SRE engineers. It has a one-weekend, $0 budget and a target of processing 1 GB of nginx access logs in under 30 seconds on a reference laptop. The architecture is deliberately one process and one pass.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because no cross-run state, query workload, or concurrent writer exists; it would add I/O and lifecycle cost while undermining streaming. An HTTP API is incorrect because the users already operate in terminals and pipelines, and a listening service would add authentication, deployment, and attack-surface concerns without improving the required workflow.

## Architecture Decision

Use a single-process layered pipeline:

```text
file path / stdin
       |
       v
input byte iterator -> nginx line parser -> validated LogRecord
                                              |
                                              v
                                      streaming Aggregator
                                      /   /   |    \
                                  IPs URLs hours unique UAs
                                              |
                                              v
                                          Report model
                                      /         |         \
                                 Rich text     JSON       CSV
```

This is the obvious architecture for the approved scope, so framework, database, API, authentication, and deployment variants are not offered as live choices. Alternatives considered were Go for more raw throughput and multiprocess chunking for parallelism; both are rejected for MVP because Python 3.11 is mandated, ordered line parsing is adequate for the target, and process coordination would increase complexity before measurement proves it necessary.

## Components and Source Layout

```text
pyproject.toml
src/nginx_stream_report/
  __init__.py
  cli.py              # Click command, option validation, exit mapping
  models.py           # LogRecord, report rows, aggregate result dataclasses
  parser.py           # supported nginx common/combined line grammar
  aggregate.py        # one-pass counters, top-N selection, UA limit
  render_text.py      # Rich terminal output
  render_json.py      # stable JSON document
  render_csv.py       # normalized multi-section CSV rows
  errors.py           # typed domain failures and exit-code mapping
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_cli.py
  test_performance.py
```

`LogRecord` contains only fields required by aggregation: client IP string, timezone-aware timestamp, request target, status integer, and User-Agent string. The parser owns syntax and validation. The aggregator owns all counters and limits. Renderers consume an immutable report dataclass and never parse input or recompute domain metrics.

## Streaming and Data Model

Input is opened in binary mode and iterated line by line. The parser decodes only required captures, validates the status and timestamp, and returns either a `LogRecord` or a malformed-line outcome. No complete input, record list, or sorted request list is retained.

The aggregator retains:

- `Counter[str]` for client IP counts.
- `Counter[str]` for request targets only when status is 400–599.
- A fixed 24-element integer array for hourly counts.
- A set of exact User-Agent strings, capped by `--max-unique-user-agents`.
- Scalar totals for lines, valid requests, malformed lines, and requests having a User-Agent.

Top-10 results are selected with bounded heap operations at finalization. Ties are deterministic: count descending, then key lexicographically ascending. Hourly request distribution is a percentage defined exactly as `100 × hourly_request_count / total_valid_requests`; all 24 hours are emitted, and each percentage is `0.0` when there are no valid requests (the command then exits 3 rather than reporting success).

Unique User-Agent share means `100 × unique_nonempty_user_agent_count / valid_requests_with_user_agent`. Missing or `-` User-Agent values do not enter either side of this ratio. If the exact unique set would exceed its configured cap, processing stops with exit code 4; the tool does not substitute an approximation.

## CLI Interface

### Command

```text
nginx-stream-report [OPTIONS] [INPUT]
```

`INPUT` is an nginx access-log path. When omitted or `-`, bytes are read from standard input. Exactly one input stream is processed per invocation.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | false | Emit normalized CSV; mutually exclusive with `--json` |
| `--top INTEGER` | 10 | Number of ranked IP and error-URL rows; positive integer |
| `--max-unique-user-agents INTEGER` | 1,000,000 | Positive hard cap for exact unique-cardinality tracking |
| `--color / --no-color` | auto | Affects terminal text only; auto enables color on a TTY |
| `--version` | — | Print version and exit 0 |
| `--help` | — | Print Click help and exit 0 |

### Inputs

The supported MVP grammar is nginx common or combined access-log format with a quoted request and numeric status. Combined-format User-Agent is used when present. Lines are separated by LF or CRLF. Malformed lines are counted and skipped; an input containing zero valid records is a distinct failure.

### Outputs

- Default: Rich headings/tables for processing summary, top IPs, top error URLs, 24 hourly percentages, and unique User-Agent share. Progress and diagnostics go to stderr; report data goes to stdout.
- JSON: one UTF-8 object with `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `unique_user_agents` keys. Ranked items contain `rank`, key, and `count`; hours contain `hour`, `count`, and `percentage`.
- CSV: UTF-8 header `section,rank,key,count,percentage` followed by normalized rows. Summary rows and unique-UA share use the same schema with empty non-applicable cells.
- Machine formats never contain ANSI escape sequences. Floating-point percentages are numbers in JSON and decimal text in CSV, rounded only for rendering.

### Exit Codes

| Code | Meaning |
|---:|---|
| 0 | Successful analysis and rendering |
| 1 | Input I/O failure, including missing file, permission denial, or read error |
| 2 | CLI usage or option validation error |
| 3 | No valid nginx records were found |
| 4 | Unique-cardinality exhaustion: the configured exact User-Agent limit was exceeded |

Partial reports are not emitted for exit codes 1, 2, 3, or 4. Diagnostics are concise, actionable, and written to stderr.

## Persistence, API, Authentication, and Deployment

| Concern | Decision |
|---|---|
| Database | None. There are no tables, schemas, migrations, indexes, or persisted records. |
| HTTP/API | None. There are no endpoints, request bodies, response bodies, ports, or network listeners. |
| Authentication | None. The process relies on the invoking OS user's permission to read the input. |
| Docker/Kubernetes | None. Container orchestration is outside scope and unnecessary for a local CLI. |
| Deployment | Build a Python wheel and source distribution; install with pip into Python 3.11. |
| Configuration | CLI options only; no required environment variables or configuration files. |

These absences are architectural constraints, not missing design work.

## Performance and Resource Budgets

- One pass over input; time complexity O(n + k log 10), where n is lines and k is distinct ranked keys.
- Memory is independent of line count but proportional to distinct IPs, distinct error URLs, and exact User-Agents. User-Agent cardinality is explicitly capped; benchmark evidence must also validate realistic IP/URL cardinality.
- Compile parsing machinery once, minimize intermediate strings, and avoid Rich work until aggregation is complete.
- The reference performance test records Python version, CPU, storage, input size and checksum, wall time, and peak RSS. Acceptance is 1 GB in less than 30 seconds on the named laptop.

## Security and Privacy

Logs may contain IP addresses, request targets, and User-Agent identifiers. The tool performs no network access, telemetry, or persistence. Reports can still contain sensitive values, so documentation warns users before sharing or redirecting output. Terminal control characters from log fields are sanitized before rendering. Input size and line length are treated as untrusted; an implementation-defined maximum line length must fail or skip safely and be tested.

## Architecture Decision Record

### ADR-001: Single-process stateless stream

- **Status:** Accepted by the supplied product brief.
- **Decision:** Parse and aggregate in one Python process without durable state or network service.
- **Consequences:** Minimal installation and operational burden; exact distinct maps can grow with input cardinality and therefore require an explicit guard.
- **Rejected:** ELK/Logstash, a local database, a web dashboard, a server process, multiprocessing before profiling, cloud services, and Kubernetes.

The separate Devil's Advocate review is intentionally not recorded here because the benchmark harness runs it in a fresh session after this blueprint.

