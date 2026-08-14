# Project Architecture: Nginx Stream Analytics CLI

## 1. Scope and Quality Attributes

The system is a local Python 3.11 process that consumes one nginx access-log stream, parses valid records, updates in-memory aggregates, and writes one report. It has no long-running component.

Priority quality attributes:

1. Process a representative 1 GB log in under 30 seconds on a documented laptop.
2. Keep processing single-pass and memory predictable.
3. Produce stable terminal, JSON, and CSV contracts.
4. Fail explicitly rather than return incomplete or approximate results without consent.

## 2. Architecture Decision

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Both constraints are correct here. A database would add persistence, schema management, I/O overhead, and cleanup without helping a one-shot summary whose source of truth is already the log stream. An HTTP API would add a server lifecycle, networking, authentication questions, and an attack surface while the intended users are operating locally or composing shell pipelines. The CLI is the product boundary; stdout is its data interface and stderr is its diagnostics interface.

The approved architecture is one process with explicit internal module boundaries. Architecture variants are not presented because the user pre-approved the obvious single-process design and the workflow says not to manufacture variants for an obvious choice.

## 3. Runtime Data Flow

```text
file path or stdin
      |
      v
buffered text iterator -> combined-log parser -> validated LogRecord
                                                    |
                                                    v
                                  single-pass MetricsAccumulator
                                  /        |        |        \
                               IP count error URL hourly   UA set + guard
                                  \        |        |        /
                                           v
                                     ReportSnapshot
                                           |
                           +---------------+---------------+
                           v               v               v
                       Rich text          JSON            CSV
                           \_______________|_______________/
                                           v
                                         stdout

diagnostics and malformed-line notices ------------------> stderr
```

Only a bounded top-10 result is rendered, but exact frequency counters may grow with distinct IPs and error URLs. Exact unique User-Agent tracking is explicitly guarded by a configurable ceiling; crossing it stops processing with exit code 4.

## 4. Package and Module Structure

```text
pyproject.toml
src/nginx_stream_analytics/
  __init__.py          # package version only
  cli.py               # Click command, orchestration, exit mapping
  models.py            # LogRecord and ReportSnapshot dataclasses
  parser.py            # nginx combined-log parsing and validation
  aggregate.py         # one-pass MetricsAccumulator
  errors.py            # typed domain failures and exit-code mapping
  renderers/
    __init__.py        # renderer protocol/dispatch
    terminal.py        # Rich terminal output
    json.py            # stable JSON document
    csv.py             # normalized CSV rows
tests/
  fixtures/            # valid, malformed, mixed, and cardinality logs
  test_cli.py
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_performance.py
```

`cli.py` owns process concerns; parsing, aggregation, and rendering remain independently testable. Renderers consume an immutable snapshot and never re-read input.

## 5. Domain Model

`LogRecord` fields:

| Field | Python type | Meaning |
|---|---|---|
| `client_ip` | `str` | Parsed remote address token; IPv4 or IPv6 text |
| `timestamp` | `datetime` | Timezone-aware nginx timestamp |
| `request_method` | `str` | Method token from quoted request |
| `request_target` | `str` | Original request target used for URL ranking |
| `protocol` | `str` | HTTP protocol token |
| `status` | `int` | Three-digit response status |
| `bytes_sent` | `int | None` | Response size; `-` maps to `None` |
| `referer` | `str | None` | Referer; `-` maps to `None` |
| `user_agent` | `str | None` | User-Agent; `-` maps to `None` |

`ReportSnapshot` contains `total_lines`, `total_valid_requests`, `malformed_lines`, ordered top-IP rows, ordered error-URL rows, 24 hourly rows, `unique_user_agents`, and `unique_user_agent_share_percent`.

Tie-breaking for top lists is count descending, then key lexicographically ascending. A URL is counted only when its status is 400–599. Hour means the hour `00`–`23` in the offset encoded by each log record; timestamps are not converted to machine-local time.

Hourly request distribution is a percentage calculated for every hour with the literal formula `100 × hourly_request_count / total_valid_requests`. When there are no valid requests, every hourly percentage is `0.0` and the unique User-Agent share is `0.0`.

Unique User-Agent share is `100 × distinct_non_null_user_agents / total_valid_requests`. Missing (`-`) User-Agents remain valid requests but do not increase the numerator.

## 6. Persistence, API, Authentication, and Deployment

| Concern | Decision | Justification |
|---|---|---|
| Database/schema | None | The process is stateless and derives all output from the current stream |
| HTTP endpoints | None | There is no server or network protocol |
| Authentication | None | The tool uses the invoking user's local filesystem/stdin permissions |
| Docker | Not part of the product | pip installation is the approved delivery path and avoids container overhead |
| Cloud/Kubernetes | None | Explicitly outside scope |
| Deployment | Install into a local Python 3.11 environment with pip | Matches workstation and automation use cases |

There are consequently no database tables, migrations, API request/response bodies, environment variables, secrets, auth flow, Docker Compose services, health endpoints, or ports. Inventing any would violate the product constraints rather than improve completeness.

## CLI Interface

### Command

```text
nginx-stream-report [OPTIONS] [INPUT]
```

`INPUT` is an optional path to an uncompressed text log. If omitted or exactly `-`, the command reads stdin. Exactly one input stream is processed per invocation.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | off | Emit one UTF-8 JSON object; mutually exclusive with `--csv` |
| `--csv` | off | Emit normalized UTF-8 CSV; mutually exclusive with `--json` |
| `--top INTEGER` | `10` | Number of IP and error-URL rows; integer >=1 |
| `--max-unique-user-agents INTEGER` | `1000000` | Exact unique-cardinality ceiling; integer >=1 |
| `--strict` | off | Treat the first malformed non-empty line as a parse failure instead of skipping and counting it |
| `--no-color` | off | Disable ANSI color in terminal mode; JSON/CSV are always color-free |
| `--version` | — | Print version and exit 0 |
| `--help` | — | Print Click help and exit 0 |

### Inputs

- UTF-8 text with replacement disabled; invalid UTF-8 is an input error.
- nginx combined-log records, one per line.
- Regular files, named pipes, and stdin are supported through sequential reads.
- Empty lines are ignored and are not counted as malformed.
- Compressed files are not opened directly; users may pipe decompressor output to stdin.

### Outputs

Default terminal output uses Rich headings and tables for summary, top IPs, error URLs, hourly distribution, and unique User-Agent share. Color is enabled only when stdout is a TTY and `--no-color` is absent.

JSON top-level keys are: `schema_version`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`. Counts are integers and percentage values are JSON numbers.

CSV has the stable columns `report,key,count,percentage`. It contains summary rows, top-IP rows, error-URL rows, 24 hourly rows, and a User-Agent row. Fields not applicable to a row are empty. Header is always emitted.

Normal report data goes only to stdout. Diagnostics go only to stderr. Partial JSON/CSV must never be emitted on failure; orchestration builds and validates the snapshot before starting machine-format output.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Successful processing and complete output, including an empty input |
| `1` | Input/runtime I/O failure, invalid UTF-8, or unexpected internal failure |
| `2` | Click usage error: invalid/mutually exclusive options or invalid option values |
| `3` | Log parse failure in strict mode, or no valid records when non-empty malformed input was supplied |
| `4` | Unique-cardinality exhaustion: the configured exact User-Agent ceiling would be exceeded |

## 8. Parsing and Error Policy

The parser accepts nginx's standard combined format, including escaped content inside quoted fields. It validates status, timestamp, and request structure. Default mode skips malformed non-empty lines, increments `malformed_lines`, and prints one bounded summary warning to stderr rather than one warning per line. If all non-empty lines are malformed, the command exits 3 and emits no report. Strict mode exits 3 on the first malformed non-empty line.

Broken pipes are handled without a traceback. They are treated as output I/O failure under code 1 unless platform conventions require silent termination; tests freeze the chosen Python behavior. Keyboard interruption maps to 1 with a concise diagnostic.

## 9. Performance and Resource Design

- Read sequentially with the standard buffered text layer; never call `read()` for the whole input.
- Parse each line once and update all aggregates in that same pass.
- Store integer counters for IPs, error URLs, and 24 hours; do not store records.
- Track exact non-null User-Agent strings in a set until the configured ceiling.
- Build sorting candidates only after EOF; select top N with a heap when profiling shows full sorting is material.
- Avoid Rich work in the hot loop.
- Benchmark wall time and peak RSS against a deterministic 1 GB generated fixture on a named laptop, with terminal rendering excluded from input-processing timing only if that distinction is reported.

The 30-second target is an acceptance target, not an unverified architectural guarantee.

## 10. Security and Privacy

Logs remain local and no telemetry is sent. The input is untrusted data: no request field is evaluated as code, terminal text is escaped by Rich, CSV uses the standard library writer, and JSON uses the standard encoder. Diagnostics avoid echoing full log lines or User-Agent strings. Files are opened read-only and the tool creates no persistent data.

## 11. Architecture Decision Record

### ADR-001: Single-process streaming CLI

- **Status:** Accepted by the project brief.
- **Context:** One-shot local analysis, $0 budget, one-weekend delivery, 1 GB/30 s target.
- **Decision:** Use one Python process with parser, accumulator, and renderer modules; no database, service, or concurrency in MVP.
- **Consequences:** Simple install and bounded operational complexity; exact high-cardinality counters remain the main memory risk and require a fail-closed ceiling.
- **Rejected alternatives:** Go rewrite (violates approved stack), multiprocessing (complexity and merge overhead before profiling), persistent indexing (violates stateless boundary), hosted API (violates local CLI boundary).

No Devil's Advocate or independent architecture review was performed in this blueprint session, by explicit session scope. An external harness may conduct that review separately.

## 12. Related Documents

Product priorities and acceptance criteria are in `PRD.md`; sequencing and verification commands are in `IMPLEMENTATION_PLAN.md`; prompts for implementation sessions are in `CLAUDE_CODE_GUIDE.md`.
