# Project Architecture: nginx-stream-report

## Architecture Summary

The approved design is a single Python 3.11 process with a linear pipeline:

```text
file path or stdin
        |
        v
line iterator -> parser -> aggregate state -> immutable report -> one renderer -> stdout
                    |             |
                    |             +-> cardinality ceiling -> exit 4
                    +-> malformed counter / diagnostic policy
diagnostics ----------------------------------------------------------> stderr
```

The central decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the command computes one ephemeral report from one input stream, persistence would add I/O and operations without improving the promised output, and retained logs would create avoidable privacy and lifecycle obligations. An HTTP API is incorrect because the target workflow is local files, stdin, shell pipelines, and incident terminals; a server would introduce authentication, ports, deployment, and concurrency concerns expressly outside the product.

The stack and single-process architecture are pre-approved. Architecture variants are therefore not presented as an open choice. Multiprocessing is rejected for the MVP because chunk boundaries complicate line parsing and exact merges while process and serialization overhead threaten the simple weekend scope. External sorting is rejected because it adds disk I/O and temporary-data handling. A service-backed analytics stack is rejected because it violates the local stateless contract.

## Goals and Quality Attributes

- Stream a 1 GB log in under 30 seconds on the documented reference laptop.
- Keep memory independent of input byte size except for distinct IP, error-URL, and User-Agent cardinality.
- Produce exact, deterministic metrics from valid supported records.
- Keep stdout machine-clean in JSON and CSV modes; send diagnostics only to stderr.
- Install with pip and run on Python 3.11 without Docker or an external service.

## Non-Goals

- Authentication, authorization, accounts, multi-tenancy, or telemetry.
- Database schemas, migrations, retention, dashboards, HTTP endpoints, or background workers.
- Cloud, server, container, or Kubernetes deployment.
- Tail-follow mode, historical comparisons, custom nginx `log_format`, or approximate cardinality in the MVP.

## CLI Interface

### Command

```text
nginx-stream-report [OPTIONS] [INPUT]
```

`INPUT` is an optional nginx access-log path. Omit it or pass `-` to read bytes/text from stdin. Exactly one input stream is processed per invocation.

### Options

| Option | Meaning | Default / constraints |
|---|---|---|
| `--json` | Emit one JSON report object | Mutually exclusive with `--csv`; never colored |
| `--csv` | Emit normalized CSV rows | Mutually exclusive with `--json`; never colored |
| `--no-color` | Disable Rich styling in terminal mode | Color is also disabled when stdout is not a TTY |
| `--max-unique-user-agents INTEGER` | Maximum exact distinct User-Agents retained | `1000000`; positive integer; crossing it exits 4 |
| `--strict` | Treat the first malformed non-empty line as a parse failure | Default is to skip malformed lines, report their count on stderr, and continue |
| `--version` | Print package version and exit | No input is opened |
| `--help` | Print usage and exit | No input is opened |

### Inputs

- A regular readable file or stdin.
- UTF-8 text with replacement disabled; undecodable input is a parse failure.
- nginx combined-log lines with remote address, timestamp and numeric zone, request, status, bytes, referrer, and User-Agent.
- Empty lines are ignored. Unsupported or malformed non-empty lines follow `--strict` behavior.

### Outputs

- Default terminal output: four titled Rich sections plus totals/warnings. Rankings are descending by count, then ascending lexicographically for deterministic ties.
- JSON output: one UTF-8 object with `schema_version`, `source`, `total_lines`, `total_valid_requests`, `malformed_lines`, `top_ips`, `top_error_urls`, `hourly_request_distribution`, and `unique_user_agent_share_percent`.
- CSV output: header `section,key,count,percentage,rank`; heterogeneous metrics are represented as normalized rows in deterministic section/rank order.
- stdout contains only the selected report. Diagnostics and malformed-line summaries go to stderr.

### Exit Codes

| Code | Contract |
|---:|---|
| `0` | Report completed successfully, including a report with skipped malformed lines in non-strict mode |
| `1` | Input I/O failure, including missing file, permission denial, or read error |
| `2` | CLI usage error, including conflicting formats or invalid option values |
| `3` | Parse/data failure: strict-mode malformed input, decoding failure, or no valid requests |
| `4` | Exact unique User-Agent cardinality exceeded `--max-unique-user-agents`; no partial report is emitted |

Click owns usage errors and maps them to 2. The application maps typed domain failures at the outer CLI boundary. Broken-pipe behavior is quiet and does not print a traceback.

## Metric Semantics

Only valid parsed requests contribute to metrics.

- **Top 10 IPs:** count every valid request by the exact parsed remote-address string; select ten by descending count then lexicographic address.
- **Top 10 error URLs:** include status codes 400–599, group by the request target exactly as logged, count all matching requests, and select ten by descending count then lexicographic target.
- **Hourly request distribution:** derive local log hour `00` through `23` from the timestamp and report all 24 buckets. Each percentage is `100 × hourly_request_count / total_valid_requests`; percentages are rounded only by the renderer, not in aggregate state.
- **Unique User-Agent share:** `100 × distinct_nonempty_user_agent_count / total_valid_requests`. The empty or `-` User-Agent is excluded from the numerator but its valid request remains in the denominator. Exact strings are case-sensitive.

## Components and Source Layout

```text
pyproject.toml
src/nginx_stream_report/
  __init__.py       package version
  __main__.py       `python -m` entry point
  cli.py            Click surface, stream ownership, error mapping
  models.py         ParsedRequest, AggregateState, Report dataclasses
  parser.py         combined-log line parser
  aggregate.py      counters, cardinality ceiling, report finalization
  errors.py         typed I/O, parse, and cardinality failures
  renderers/
    __init__.py
    terminal.py     Rich output
    json.py         schema-versioned JSON output
    csv.py          normalized CSV output
tests/
  fixtures/         small committed input and golden outputs
  perf/             deterministic large-log generator and benchmark harness
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_renderers.py
```

`ParsedRequest` holds only fields required for aggregation: `remote_addr: str`, `hour: int`, `target: str`, `status: int`, and `user_agent: str | None`. `AggregateState` owns `Counter[str]` values for IPs and error URLs, a fixed 24-integer hour array, an exact `set[str]` for User-Agents, and total/invalid counters. `Report` contains finalized sorted rows and unrounded numeric shares. Renderers may format but never recalculate metrics.

## Streaming and Resource Model

The CLI opens a path with a large buffered sequential reader or uses stdin without closing caller-owned stdin. It iterates one line at a time; the parser does not retain the source line after aggregation. No full-file read, list of requests, or global sort of raw records is allowed.

Memory is `O(U_ip + U_error_url + U_user_agent + 24)`. Exact User-Agent cardinality is explicitly capped. IP and error-URL counters remain exact and are monitored by the performance suite; introducing caps or approximation for them requires a PRD change. Top 10 selection uses bounded selection or sorting over aggregate keys only, never over all requests.

## Parsing Contract

The parser uses a compiled, anchored grammar or an equivalent single-pass tokenizer for the supported combined format. It validates the status range as three numeric digits, parses the timestamp hour and numeric offset, extracts the request target from the quoted request field, and preserves escaped quoted content correctly. A request field of `-` or one without a target is malformed. Parser failures contain line number and a concise reason but never echo an entire potentially sensitive log line.

## Output Schemas and Compatibility

JSON uses integer counts and numeric percentages, UTF-8, one trailing newline, and `schema_version: 1`. CSV uses RFC 4180 quoting through the standard library, one header, and one row per metric/ranking item. Machine modes are locale-independent and stable within schema version 1. Breaking field changes require a schema-version increment and corresponding PRD update.

## Data, API, Authentication, and Deployment Decisions

- **Database:** none. There are no tables, indexes, migrations, cache, or retained application data.
- **HTTP API:** none. There are no endpoints, request bodies, response bodies, ports, or network listeners.
- **Authentication:** none because there is no account or remote trust boundary. Access is governed by local operating-system file permissions.
- **Environment variables:** none are required. CLI arguments are the complete runtime configuration contract.
- **Docker:** none. Containers add no value to a pip-installed local CLI and are outside scope.
- **Deployment:** build a wheel and source distribution and install through pip into a user environment or virtual environment. Release automation may publish to a public package index after local verification; the runtime remains local.

## Error Handling and Security

Input is untrusted data. The parser never evaluates content, invokes a shell, follows embedded paths, or emits log contents in tracebacks. Rich markup is disabled or escaped for user-derived strings. JSON and CSV use standard-library encoders. Path errors are concise; verbose tracebacks are reserved for development tests. The process creates no temporary files and makes no network calls.

## Verification Architecture

- Unit fixtures cover IPv4/IPv6, timezone-bearing timestamps, escaped quotes, missing fields, status boundaries, empty User-Agents, ties, and malformed lines.
- Golden tests assert terminal no-color, JSON, and CSV meanings from the same fixture.
- CLI tests assert stdout/stderr separation and all exit codes `0/1/2/3/4`.
- A deterministic generated 1 GB fixture is excluded from version control; its generator seed and shape are recorded. The benchmark records elapsed wall time and peak resident memory on the named reference laptop.
- Packaging verification installs the built wheel into a clean Python 3.11 virtual environment and runs `--help`, `--version`, and a fixture report.

## Architecture Decision Record

### ADR-001: Single-Process Stateless CLI

- **Status:** Accepted from the product brief.
- **Decision:** Use one Python process and a parse/aggregate/render pipeline; do not add persistence or a service boundary.
- **Consequences:** Minimal operational surface and direct piping; exact distinct values can consume memory, so User-Agent cardinality has an explicit ceiling and exit code 4.
- **Rejected alternatives:** multiprocess chunking, external sorting, and service-backed ingestion for the scope and complexity reasons stated above.

### Review Status

The required independent Devil's Advocate review is intentionally deferred to the external harness. No adversarial verdict is asserted in this document, and no reviewer artifact is generated by this blueprint session.

`PRD.md` owns behavior and acceptance criteria; `IMPLEMENTATION_PLAN.md` turns this design into dependency-ordered work.
