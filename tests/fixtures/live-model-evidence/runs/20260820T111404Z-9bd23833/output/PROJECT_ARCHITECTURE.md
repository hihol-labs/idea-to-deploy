# Project Architecture: Nginx Stream Analytics CLI

## 1. Context and Goals

The product is a local Python 3.11 CLI that performs a single sequential pass over nginx common or combined access logs. It must produce four exact aggregates, support terminal/JSON/CSV rendering, install through pip, and process a 1 GB representative file in under 30 seconds on a documented laptop.

The governing architecture decision is **"no database — stateless streaming processing; no HTTP API — CLI-only tool"**.

- No database is correct because the product answers one bounded question about the current input, does not offer historical queries, and must have no setup or cleanup. Persistence would add I/O, schema lifecycle, failure modes, and operational cost without improving the required report.
- No HTTP API is correct because both primary inputs (a file and stdin) and all required outputs (terminal text, JSON, CSV) already compose through the shell. A server would create authentication, lifecycle, port, deployment, and security concerns explicitly outside the product goal.

## 2. Architecture Selection

The pre-approved architecture is one installable package and one process:

```text
file path or stdin
        |
        v
 buffered text reader -> line parser -> streaming aggregator -> immutable report
                              |                   |                    |
                         invalid count       guarded state      text | JSON | CSV
                                                                       |
                                                              stdout / stderr
```

This is the obvious choice for a solo, one-weekend, local MVP with a specified stack. Multiprocessing is not the default because record-boundary coordination, merge costs, and platform differences add complexity before profiling demonstrates a need. Multiple passes are rejected because stdin is not seekable and repeated I/O works against the performance target.

## 3. Technology Stack

| Layer | Choice | Contract |
|---|---|---|
| Runtime | CPython 3.11 | Supported interpreter baseline |
| CLI adapter | Click | Argument validation, help, file/stdin abstraction, usage errors |
| Terminal renderer | Rich | Colored tables only for default text output |
| Domain models | `dataclasses` | `AccessRecord`, mutable aggregation state, immutable `Report` |
| Standard library | `re`, `collections`, `csv`, `json`, `datetime`, `pathlib` | Parsing, counting, serialization, paths |
| Packaging | PEP 621 `pyproject.toml` | pip-installable wheel/sdist and console script |
| Verification | pytest | Unit, integration, golden, property-oriented, and benchmark tests |

No ORM, web framework, async runtime, container runtime, or external storage client is used.

## 4. Component Boundaries

| Component | Planned path | Responsibility | Must not do |
|---|---|---|---|
| CLI | `src/nginx_stream_analytics/cli.py` | Validate options, select input/output, map typed failures to exit codes | Parse log syntax or compute metrics |
| Parser | `src/nginx_stream_analytics/parser.py` | Convert one common/combined line to `AccessRecord`; return a typed malformed result | Read files, print, or retain history |
| Models | `src/nginx_stream_analytics/models.py` | Dataclasses and typed error categories | Perform I/O |
| Aggregator | `src/nginx_stream_analytics/aggregate.py` | Update counts once per valid record, enforce cardinality guard, finalize percentages/top lists | Format output |
| Text reporter | `src/nginx_stream_analytics/reporters/text.py` | Rich terminal tables and summary | Change metric values |
| JSON reporter | `src/nginx_stream_analytics/reporters/json.py` | Emit schema-versioned JSON | Emit ANSI sequences |
| CSV reporter | `src/nginx_stream_analytics/reporters/csv.py` | Emit normalized RFC 4180-style rows | Emit prose |
| Entrypoint | `src/nginx_stream_analytics/__main__.py` | Support `python -m nginx_stream_analytics` | Duplicate Click command logic |

Dependency direction is `cli -> parser + aggregate + reporters`, with parser and reporters depending only on models. Reporters consume the same finalized `Report`, ensuring all formats share identical values.

## 5. Data Model and Metric Semantics

### AccessRecord

| Field | Type | Source / rule |
|---|---|---|
| `client_ip` | `str` | nginx remote address token, retained as text |
| `timestamp` | timezone-aware `datetime` | `[day/month/year:hour:minute:second ±offset]` |
| `request_target` | `str` | Target from quoted request line; query string is retained |
| `status` | `int` | Three-digit HTTP status |
| `user_agent` | `str | None` | Combined-log User-Agent; `None` for common format or `"-"` |

The method and protocol may be parsed transiently for validation but are not retained because no required metric uses them. A request target that cannot be extracted from the quoted request field is malformed.

### Aggregation state

| State | Type | Update rule |
|---|---|---|
| `total_valid_requests` | `int` | Increment once per parsed record |
| `malformed_lines` | `int` | Increment for every non-empty line that fails parsing |
| `ip_counts` | `dict[str, int]` | Increment for every valid record |
| `error_url_counts` | `dict[str, int]` | Increment only when `400 <= status <= 599` |
| `hour_counts` | fixed `list[int]` of length 24 | Increment timestamp hour `0..23` as encoded in that record's offset |
| `unique_user_agents` | `set[str]` | Add non-missing combined-log User-Agent strings |

All distinct-key containers share a configurable guard (`--max-unique`, default 1,000,000 distinct values per container). Before inserting a new key, the aggregator checks the limit. Exceeding it terminates in a controlled fashion with exit code 4; the tool never silently switches to an approximate algorithm.

### Final report

- Top IPs: first 10 entries ordered by request count descending, then IP string ascending.
- Top error URLs: first 10 entries ordered by combined 4xx/5xx count descending, then request target ascending.
- Error URLs combine all statuses from 400 through 599; successful URLs are absent.
- Hourly request distribution contains all 24 hours, including zeroes. Each percentage is calculated with the literal formula `100 × hourly_request_count / total_valid_requests` and serialized with six decimal places in JSON/CSV; text may display two decimal places.
- Unique User-Agent share is `100 × unique_non_missing_user_agent_count / total_valid_requests`, serialized with six decimal places in JSON/CSV. Missing `-` values and common-format records do not add a unique User-Agent but remain in the denominator.
- Percentages use unrounded integer counts and are rounded only by a reporter.

## 6. Streaming and Performance Design

The reader iterates over buffered text input; it never calls `read()` for the whole file and never stores raw lines or `AccessRecord` objects after aggregation. A compiled anchored parser is created once. Hot-loop code uses local references and integer/list updates; Rich objects are built only after aggregation.

Time complexity is `O(n + u log 10)` for `n` lines and `u` distinct IP/error-URL entries during final top selection; fixed-size heap selection may avoid sorting all keys. Space is `O(i + e + a + 24)`, where `i`, `e`, and `a` are distinct IPs, error URLs, and User-Agents, bounded by the cardinality guard. The guard is a correctness and safety contract, not a claim of constant memory.

Performance acceptance uses a deterministic generated 1 GB combined-log fixture and records hardware, OS, Python 3.11 patch version, storage type, cache condition, command, elapsed wall time, and peak resident memory. Text rendering time is included. JSON/CSV benchmarks may be recorded separately but cannot substitute for the default-mode target.

## 7. Input and Parsing Contract

Supported input is UTF-8 text in nginx common or combined log format, one record per line. The reader uses `errors="replace"`; a replacement character inside a syntactically valid quoted field is data, while damaged structure is malformed. Empty lines are ignored and do not increment malformed count.

Default behavior skips malformed non-empty lines, records their count, prints a concise warning to stderr, and succeeds if at least one valid record exists. `--strict` stops at the first malformed record and exits 3. An empty input or input with zero valid records exits 3. Diagnostics contain line numbers and reason categories but never echo full log lines, reducing accidental leakage of URLs or User-Agents.

Regular files, named pipes, and stdin are supported. Direct `.gz` decoding is a Should feature; until implemented, `gzip -dc access.log.gz | nginx-log-report` is the documented path.

## CLI Interface

### Commands

```text
nginx-log-report [OPTIONS] [INPUT]
python -m nginx_stream_analytics [OPTIONS] [INPUT]
```

Both forms invoke the same Click command. `INPUT` is a path or `-`; when omitted it defaults to `-` (stdin).

### Options

| Option | Meaning | Validation |
|---|---|---|
| `--json` | Emit one JSON document to stdout | Mutually exclusive with `--csv` |
| `--csv` | Emit one normalized CSV document to stdout | Mutually exclusive with `--json` |
| `--strict` | Fail on the first malformed non-empty line | Default is skip-and-count |
| `--max-unique INTEGER` | Maximum distinct keys in each guarded container | Positive integer; default `1000000` |
| `--no-color` | Disable Rich color in text mode | Has no effect on structured formats |
| `--version` | Print package version and exit 0 | Takes no input |
| `--help` | Print usage and exit 0 | Takes no input |

The `NO_COLOR` environment convention also disables color. `--no-color` is explicit and wins. JSON and CSV never contain ANSI control sequences. Progress bars are not emitted because they would complicate pipelines and distort the benchmark.

### Inputs

- Positional `INPUT`: readable UTF-8 nginx common/combined access log, or `-` for stdin.
- No configuration file, database, network socket, environment secret, or remote URL is read.
- Input is consumed exactly once and is not modified.

### Outputs

- stdout contains exactly one selected report: colored Rich text by default, a JSON object for `--json`, or a CSV header plus rows for `--csv`.
- stderr contains usage-independent diagnostics and the malformed-line summary. It contains no report data.
- Broken-pipe handling exits cleanly without a Python traceback when a downstream consumer closes normally.

### Exit codes

| Code | Meaning | Examples |
|---:|---|---|
| `0` | Report produced successfully | Valid input; malformed lines skipped in non-strict mode |
| `1` | Operational or internal failure | File unreadable, decode/read failure, stdout write failure other than handled broken pipe, unexpected internal error |
| `2` | CLI usage error | Conflicting formats, invalid `--max-unique`, extra arguments |
| `3` | Input data / parse failure | Strict-mode malformed line, empty input, or zero valid records |
| `4` | Unique-cardinality exhaustion | A new distinct IP, error URL, or User-Agent would exceed `--max-unique` |

This `0/1/2/3/4` mapping is public and must remain identical in Click integration tests and all implementation guides.

## 9. Output Schemas

### Text

The text report contains a summary line (`valid`, `malformed`, `unique_user_agents`, share), a Top 10 IPs table, a Top 10 4xx/5xx URLs table, and a 24-row hourly distribution table. Color distinguishes headings and error metrics; meaning never depends on color alone.

### JSON (`schema_version: 1`)

```json
{
  "schema_version": 1,
  "summary": {
    "total_valid_requests": 123,
    "malformed_lines": 2,
    "unique_user_agent_count": 17,
    "unique_user_agent_share_percent": 13.821138
  },
  "top_ips": [{"ip": "192.0.2.1", "request_count": 20}],
  "top_error_urls": [{"url": "/missing", "error_count": 9}],
  "hourly_distribution": [
    {"hour": 0, "request_count": 5, "request_share_percent": 4.065041}
  ]
}
```

`hourly_distribution` always has 24 ordered entries. JSON is UTF-8, uses a trailing newline, and writes no NaN/Infinity values.

### CSV

CSV uses columns `schema_version,section,rank,key,count,percent`. Sections are ordered `summary`, `top_ip`, `top_error_url`, `hour`. Summary keys are `total_valid_requests`, `malformed_lines`, `unique_user_agent_count`, and `unique_user_agent_share_percent`; irrelevant cells are empty. Top sections use ranks 1–10 where present. Hour rows use keys `00` through `23`, counts, and six-decimal percentages. The standard library `csv` writer controls quoting and platform-safe newlines.

## 10. Error and Failure Handling

Domain exceptions are typed (`InputDataError`, `CardinalityLimitError`, `OperationalError`) and translated to codes only at the CLI boundary. Unexpected exceptions produce a concise error without a traceback unless a future debug option is explicitly introduced. Report generation is finalize-then-render: no partial JSON or CSV is written for parse/cardinality failure. For normal file sizes, the finalized structured report is small enough to serialize as a unit.

## 11. Security and Privacy

Logs are untrusted data. The tool performs no shell interpolation, URL fetching, dynamic imports, template execution, or terminal rendering of raw values with markup enabled. Rich output escapes control/markup characters; JSON and CSV use standard serializers. Diagnostic messages do not reproduce full log lines. No telemetry or network access exists, and no data is persisted by the application.

CSV output is intended for machine processing. Keys beginning with spreadsheet formula characters remain standards-compliant CSV data; documentation warns users that importing untrusted CSV into spreadsheet software may execute formulas unless that software's safe-import mode is used. Altering raw values to avoid this would make CSV inconsistent with JSON.

## 12. Database, API, Authentication, and Deployment

### Database schema

There are no database tables, migrations, indexes, or persistence layer. The in-memory structures in Section 5 are ephemeral and disappear on process exit.

### HTTP API

There are no endpoints, request bodies, response bodies, ports, or network listeners. The entire public integration surface is specified under `## CLI Interface`.

### Authentication

There is no authentication flow because the process only accesses resources already readable by the invoking operating-system user. OS file permissions are the trust boundary.

### Environment variables

No application-specific environment variables are required. The conventional `NO_COLOR` variable is observed; its value is not secret configuration.

### Deployment and installation

The deployment artifact is a pure-Python wheel and source distribution installed with pip into Python 3.11. No Dockerfile, `docker-compose.yml`, server process, cloud resource, or Kubernetes manifest is part of the product. Release verification installs the built wheel into a clean virtual environment and runs `nginx-log-report --version`, stdin smoke tests, and all three output modes.

## 13. Architecture Decision Records

### ADR-001: Single-process stateless pipeline

- **Status:** Accepted (pre-approved)
- **Decision:** One buffered reader, parser, aggregator, and selected reporter in one Python process.
- **Reasons:** stdin compatibility, minimal coordination overhead, weekend scope, zero infrastructure.
- **Rejected:** multiprocessing before profiling; multiple passes; service-based ingestion.

### ADR-002: Exact metrics with an explicit cardinality guard

- **Status:** Accepted
- **Decision:** Maintain exact key counts and exact User-Agent uniqueness up to `--max-unique`; exit 4 on exhaustion.
- **Reasons:** The PRD promises exact top lists and share; silent approximation would violate pipeline trust.
- **Rejected:** HyperLogLog or sketches in MVP; uncontrolled sets/dictionaries.

### ADR-003: One canonical report, three reporters

- **Status:** Accepted
- **Decision:** Finalize metrics once into `Report`, then render text, JSON, or CSV.
- **Reasons:** Prevents semantic drift and enables cross-format tests.
- **Rejected:** Reporter-specific aggregation logic.

## 14. Traceability

- Product scope, alternatives, budget, and KPIs: `STRATEGIC_PLAN.md`.
- User outcomes and acceptance criteria: `PRD.md`.
- Ordered delivery units and verification: `IMPLEMENTATION_PLAN.md`.
- Implementation-session prompts and guardrails: `CLAUDE_CODE_GUIDE.md` and `CLAUDE.md`.
