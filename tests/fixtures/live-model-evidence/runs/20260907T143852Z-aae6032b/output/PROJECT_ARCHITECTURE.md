# Project Architecture: nginx-stream-report

## 1. Context and Drivers

The product is a local Python 3.11 CLI that processes nginx common or combined access logs in a single pass. It must be installable with pip, default to colored terminal output, support JSON and CSV pipelines, remain stateless, and target processing 1 GB in under 30 seconds on a declared laptop benchmark. The product contract is [PRD.md](PRD.md).

Primary drivers are correctness, streaming performance, predictable memory use, stable machine-readable output, and one-weekend delivery with a $0 infrastructure budget.

## 2. Architecture Decision

**Decision:** **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add import time, storage, schema lifecycle, cleanup, and operational state without improving the required one-shot aggregates. An HTTP API would introduce a server lifecycle, port/security concerns, serialization overhead, authentication questions, and deployment work while the intended users already work in terminals and pipelines. Keeping input and output as process streams minimizes setup, preserves local data handling, and fits the latency, budget, and weekend constraints.

The chosen design is a single OS process with a layered internal pipeline. It is not a distributed system and has no background worker.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** buffered line iteration feeds a compiled parser, a mutable in-memory aggregate, and exactly one selected renderer.
- **Pros:** one pass, low setup, straightforward profiling, local-only data, minimal dependencies.
- **Cons:** exact unique cardinality consumes memory proportional to distinct User-Agents until the configured guard; one CPU process limits parallelism.
- **Best for:** the approved 1 GB local incident-triage workload.
- **Estimated complexity:** Low.

### Variant B: Multi-process partition and merge

- **Approach:** split seekable files, aggregate in workers, then merge partial counters and sets.
- **Pros:** potential multi-core parsing speedup.
- **Cons:** does not naturally support stdin, duplicates memory, complicates line boundaries and deterministic error reporting, and exceeds the weekend risk budget.
- **Best for:** much larger seekable files after evidence shows parsing is CPU-bound.
- **Estimated complexity:** Medium.

### Variant C: Embedded analytical store

- **Approach:** import records into SQLite/DuckDB, then query aggregates.
- **Pros:** flexible follow-up queries and reusable imported state.
- **Cons:** violates statelessness, adds write amplification and disk requirements, and delays the first answer.
- **Best for:** exploratory historical analysis, which is out of scope.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the architecture is pre-approved, the metrics are fixed reductions, stdin must work, and no persistence or interactive querying is required. Variants B and C are documented only as rejected alternatives, not as MVP branches.

## 4. Component Model

```text
paths / stdin
     │ buffered bytes
     ▼
InputSource ── lines ──▶ NginxParser ── LogRecord ──▶ StreamAggregator
                             │ malformed                    │
                             ▼                              ▼
                         ParseStats                    ReportSnapshot
                                                            │
                                      ┌─────────────────────┼────────────────────┐
                                      ▼                     ▼                    ▼
                               RichRenderer          JsonRenderer          CsvRenderer
                                      └─────────────────────┴────────────────────┘
                                                            │
                                                        stdout
diagnostics ───────────────────────────────────────────────────────────────▶ stderr
```

| Component | Proposed path | Responsibility |
|---|---|---|
| Click entry point | `src/nginx_stream_report/cli.py` | Validate options, select sources/renderer, map exceptions to exit codes |
| Input source | `src/nginx_stream_report/input.py` | Open files or stdin as buffered binary streams without loading whole files |
| Parser | `src/nginx_stream_report/parser.py` | Parse common/combined lines into typed records using precompiled patterns |
| Domain models | `src/nginx_stream_report/models.py` | `LogRecord`, `ParseStats`, `ReportSnapshot`, configuration dataclasses |
| Aggregator | `src/nginx_stream_report/aggregate.py` | Update four metric families and enforce unique-cardinality limit |
| Renderers | `src/nginx_stream_report/renderers/{terminal,json_output,csv_output}.py` | Emit one stable presentation format without recalculation |
| Errors | `src/nginx_stream_report/errors.py` | Typed failures carrying the defined process exit classification |

Allowed dependency direction is `cli → input/parser/aggregate/renderers → models/errors`; renderers never parse, parser never renders, and domain modules never import Click or Rich.

## 5. Data Model and Invariants

### `LogRecord`

| Field | Python type | Rule |
|---|---|---|
| `client_ip` | `str` | Non-empty parsed remote address token; IPv4/IPv6 accepted as text |
| `timestamp` | `str` or compact parsed fields | Original nginx timestamp retained only if required for diagnostics |
| `hour` | `int` | 0–23 from the wall-clock hour written in the log entry; no timezone normalization |
| `method` | `str` | Request method token, possibly empty for an nginx `-` request |
| `url` | `str` | Request-target token; query string is retained so ranking matches the log literally |
| `protocol` | `str` | HTTP protocol token or empty when request is `-` |
| `status` | `int` | Three-digit HTTP status |
| `user_agent` | `str` | Combined-log UA; common format uses the sentinel `<missing>` |

### `ParseStats`

| Field | Type | Invariant |
|---|---|---|
| `input_lines` | `int` | All physical lines read |
| `valid_requests` | `int` | Successfully parsed records |
| `malformed_lines` | `int` | Parse failures; `input_lines = valid_requests + malformed_lines` |

### `ReportSnapshot`

| Field | Type | Invariant |
|---|---|---|
| `top_ips` | ordered `list[(str, int)]` | At most N, count descending then key ascending |
| `top_error_urls` | ordered `list[(str, int)]` | Only statuses 400–599; same tie-break |
| `hourly_counts` | `tuple[int, ...]` | Exactly 24 values |
| `hourly_percentages` | `tuple[float, ...]` | Exactly 24 values computed from valid requests |
| `unique_user_agent_count` | `int` | Exact distinct count unless processing terminates with code 4 |
| `unique_user_agent_share` | `float` | `100 × unique_user_agent_count / total_valid_requests`, or `0.0` for zero valid requests |
| `parse_stats` | `ParseStats` | Same counters used for diagnostics and output metadata |

Hourly request distribution is a percentage for each hour, calculated with the literal formula `100 × hourly_request_count / total_valid_requests`. For zero valid requests, all 24 percentages are `0.0`; in strict mode the lack of any valid request is a parse/validation failure.

Ties in both top lists are deterministic: count descending, key ascending. Percentages are calculated at finalization using full integer counts and rendered to two decimal places in terminal/CSV; JSON numbers retain a stable documented precision of six decimal places.

## 6. Streaming and Memory Behavior

- Each source is read line by line from a buffered binary stream. No `read()` of an entire file and no retained raw records are allowed.
- IP and error-URL `Counter` objects grow with their distinct keys. The 24 hourly counters are constant-size.
- The exact User-Agent set grows with distinct values and is checked before insertion against `--max-unique-user-agents` (default 1,000,000). Reaching a new value beyond the limit stops processing with exit code 4; the tool must not emit a misleading partial report to stdout.
- Lines are decoded as UTF-8 with replacement only in quoted request/referrer/UA fields; the structural ASCII portions are parsed from bytes or an equivalently benchmarked representation.
- Multiple input files are processed as one logical stream in argument order. `-` denotes stdin and may appear at most once.
- No temp files, caches, telemetry, checkpoints, or persistent state are created.

## CLI Interface

### Command

```text
nginx-stream-report [OPTIONS] [INPUTS]...
```

`INPUTS` is zero or more nginx log paths. With no paths, or with a single `-`, input is stdin. Multiple paths contribute to one aggregate report.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | off | Emit one JSON object to stdout; mutually exclusive with `--csv` |
| `--csv` | off | Emit long-form RFC 4180 CSV to stdout; mutually exclusive with `--json` |
| `--format [combined|common]` | `combined` | Select supported nginx grammar |
| `--top INTEGER` | `10` | Number of ranked IP and error-URL rows; range 1–1000 |
| `--strict/--no-strict` | `--no-strict` | Strict stops at first malformed line with code 3; default skips and counts |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive hard limit for exact UA cardinality |
| `--color/--no-color` | auto | Force or disable Rich color; auto enables only for an appropriate terminal |
| `--version` | n/a | Print version and exit 0 |
| `--help` | n/a | Print Click help and exit 0 |

### Inputs

- Supported records are nginx `combined` and `common` formats with standard quoted request fields.
- Regular files and stdin are supported. FIFOs work through stdin semantics; direct URLs and compressed files are not MVP inputs.
- Malformed lines are skipped and counted by default. Under `--strict`, the first malformed line is reported with source and one-based line number, with no raw User-Agent or full line echoed by default.

### Outputs

Default terminal output is a Rich-rendered summary with four sections: top IPs, top 4xx/5xx URLs, 24 hourly percentage rows/bars, and a unique User-Agent summary. Diagnostics and the malformed-line summary go to stderr, never into JSON/CSV stdout.

JSON has this stable top-level shape:

```json
{
  "schema_version": 1,
  "summary": {"input_lines": 0, "valid_requests": 0, "malformed_lines": 0},
  "top_ips": [{"ip": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"url": "/missing", "count": 1}],
  "hourly_distribution": [{"hour": 0, "count": 0, "percentage": 0.0}],
  "user_agents": {"unique_count": 0, "share_percentage": 0.0}
}
```

CSV begins with `metric,rank,key,count,percentage`. It contains `top_ip`, `top_error_url`, `hourly_request`, and `unique_user_agent_share` rows. Non-applicable cells are empty, all 24 hourly rows are present, and fields are escaped through Python’s `csv` module.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Successful report, help, or version output |
| `1` | Runtime I/O/output failure, including unreadable input or broken non-pipeline destination |
| `2` | Click usage error: invalid option, mutually exclusive modes, invalid range, or invalid input combination |
| `3` | Parse/validation failure in strict mode, or zero valid requests under strict mode |
| `4` | Unique-cardinality exhaustion: a new distinct User-Agent would exceed the configured limit |

On codes 1, 2, 3, or 4, stdout contains no report. A concise diagnostic is written to stderr. A normal downstream pipe close is handled without a traceback and uses conventional successful pipe behavior where safely detectable.

## 8. Parsing Contract

- Precompile one anchored pattern for each supported format. Parse the nginx timestamp shape `[day/month/year:hour:minute:second zone]` and extract only the logged wall-clock hour for this report.
- A request of `"-"` is valid and yields empty method/protocol plus URL `-`; its status still participates in the error ranking.
- Status 400 through 599 inclusive contributes to `top_error_urls`; redirects and 1xx/2xx/3xx do not.
- Query strings remain part of the URL key. Percent-decoding, host normalization, path canonicalization, and bot classification are out of scope.
- In common format, every valid record uses `<missing>` as its UA value. This makes the unique share deterministic and communicates that the field was unavailable.
- Blank lines are malformed lines.

## 9. Persistence, API, Authentication, and Deployment

### Database

There are no database tables, migrations, indexes, caches, or persistence adapters. The template requirement to enumerate tables is not applicable because adding even an embedded database would violate the approved product contract.

### HTTP API

There are no endpoints, request bodies, response bodies, ports, or network listeners. JSON and CSV are process-output formats, not APIs.

### Authentication

There is no authentication or authorization flow because the process accesses only resources already available to the invoking OS user. File permissions and shell execution identity form the trust boundary.

### Deployment

Deployment means publishing a source distribution and wheel to a Python package index and installing locally with pip. There is no Docker image, Compose file, server, cloud service, or Kubernetes manifest. Supported runtime is CPython 3.11 on a user workstation.

### Environment variables

No application environment variables are required. Behavior is explicit through CLI options. Standard platform variables used internally by Python/pip are outside the application contract.

## 10. Security and Privacy Boundaries

- Logs are untrusted input. Parsing must be non-executing, bounded per line, and resistant to catastrophic regular-expression backtracking.
- Terminal strings are rendered as text; control characters are escaped or neutralized so log values cannot inject terminal control sequences.
- JSON and CSV use standard serializers; values are never manually concatenated.
- Diagnostics avoid echoing full log lines because logs can contain tokens, identifiers, referrers, and User-Agent fingerprints.
- No data leaves the machine and no telemetry is collected.
- CSV consumers must be warned that spreadsheet applications can interpret leading `=`, `+`, `-`, or `@`; the renderer prefixes dangerous text cells with a single quote or documents an equivalent deterministic neutralization rule.

## 11. Performance Plan

The acceptance benchmark uses a deterministic synthetic 1 GiB combined-format file on a declared laptop, CPython 3.11, one warm filesystem-cache run after one untimed warm-up, and `/usr/bin/time` (or platform equivalent) to capture wall time and peak RSS. The command is the installed console script with terminal output redirected to a file. Pass criterion: wall time below 30.0 seconds, correct golden summary, and no cardinality exhaustion at the fixture’s declared distinct-UA count.

Optimization order is: measure, profile, eliminate repeated parsing/allocation, reduce sorting to `nsmallest`/bounded ranking if profiling supports it, then reconsider the parser. Multiprocessing, approximate cardinality, and native extensions require a new architecture decision and PRD change.

## 12. Test Strategy

| Layer | Evidence |
|---|---|
| Parser | Valid common/combined fixtures, IPv6, quoting, malformed/blank lines, request `-`, timestamp boundaries |
| Aggregator | Exact counts, status boundaries 399/400/599/600, deterministic ties, 24 buckets, zero-valid behavior |
| Cardinality | At-limit success, first-over-limit code 4, no partial stdout |
| Renderers | Rich snapshot tests and golden JSON/CSV schemas with escaping cases |
| CLI | stdin/files/multiple files, option conflicts, every exit code `0/1/2/3/4`, stdout/stderr separation |
| Performance | Deterministic 1 GiB fixture generator and recorded benchmark metadata |
| Packaging | Clean Python 3.11 virtual environment, wheel build, console-script smoke test |

## Architecture Decision Record (ADR)

### ADR-001: Single-process layered stream

- **Status:** Accepted by the product brief.
- **Decision:** Use Variant A and retain only aggregate state.
- **Consequences:** Simple local operation and stdin support; exact distinct-key memory remains data-dependent and guarded.

### ADR-002: Exact cardinality with fail-closed limit

- **Status:** Accepted for MVP.
- **Decision:** Use a Python set for exact unique User-Agent count and stop with code 4 before exceeding the configured distinct-value limit.
- **Consequences:** Results are exact when emitted; some high-cardinality inputs fail explicitly instead of producing an approximation or risking uncontrolled memory.

### ADR-003: Stable process-output schemas

- **Status:** Accepted for MVP.
- **Decision:** JSON carries `schema_version: 1`; CSV uses a documented long-form row schema.
- **Consequences:** Pipeline compatibility is testable; breaking changes require a schema-version decision.

No adversarial review artifact or verdict is produced in this blueprint session; that separate workflow is reserved for the external harness as required.
