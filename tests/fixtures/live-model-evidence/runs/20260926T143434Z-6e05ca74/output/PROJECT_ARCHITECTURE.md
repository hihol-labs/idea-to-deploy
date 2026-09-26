# Project Architecture: nginx-stream-report

## 1. Context and Constraints

The system is a local Python 3.11 command-line program for DevOps/SRE engineers. It consumes nginx access-log text from one file or standard input and builds a report in one pass. It is installable with pip, costs $0 to operate, and must target processing a 1 GB representative log in under 30 seconds on a documented laptop.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the requested outputs can be accumulated during a single scan and the product must neither retain sensitive logs nor require lifecycle operations. An HTTP API is incorrect because the user is local or in a shell pipeline; a server would add authentication, deployment, ports, and failure modes without improving the required workflow.

Out of scope: authentication, databases, network listeners, background services, cloud resources, Docker as a runtime requirement, and Kubernetes.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Approved)

- **Approach:** Click invokes one synchronous pipeline: byte/text input → compiled parser → mutable aggregate state → immutable report dataclasses → selected renderer.
- **Pros:** One scan, simple packaging, deterministic behavior, low startup cost, easy stdin composition.
- **Cons:** Exact IP, URL, and User-Agent cardinalities consume memory proportional to distinct values; one CPU core performs parsing.
- **Best for:** A one-weekend local CLI analyzing individual logs up to the stated target.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunk parsing

- **Approach:** Split seekable files into chunks, parse in worker processes, then merge partial counters.
- **Pros:** Can use multiple cores on very large regular files.
- **Cons:** Cannot naturally split stdin, complicates line boundaries and deterministic errors, increases memory and weekend scope.
- **Best for:** A later version after profiling proves parsing is CPU-bound.
- **Estimated complexity:** Medium.

### Variant C: Embedded analytical database

- **Approach:** Load or query logs through an embedded engine and express reports as SQL.
- **Pros:** Flexible follow-up queries and mature aggregation engine.
- **Cons:** Violates the approved no-database decision, adds dependency/startup/storage overhead, and may materialize sensitive data.
- **Best for:** Exploratory analytics with retained data, which is not this product.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is approved because it directly satisfies local execution, stdin support, $0 operations, one-weekend delivery, and the no-database/no-server constraints. Variants B and C remain rejected unless measured evidence and a changed product contract justify them.

## 3. System Components

```text
file path ─┐
           ├─> Input stream ─> nginx parser ─> Aggregator ─> Report snapshot
stdin ─────┘                         │              │              │
                              diagnostics    counters/set      ┌──┴───────┐
                                                             terminal JSON CSV
```

| Component | Planned path | Responsibility |
|---|---|---|
| CLI adapter | `src/nginx_stream_report/cli.py` | Click command, option validation, renderer selection, exception-to-exit mapping |
| Stream coordinator | `src/nginx_stream_report/analyzer.py` | Iterate input once, track physical line number, apply malformed-line policy |
| Parser | `src/nginx_stream_report/parser.py` | Parse the supported combined-log grammar into minimal fields |
| Records | `src/nginx_stream_report/models.py` | `LogRecord`, `Report`, ranked-row and hourly-row dataclasses |
| Aggregation | `src/nginx_stream_report/aggregate.py` | Counts, valid/invalid totals, distinct User-Agent set and ceiling |
| Terminal renderer | `src/nginx_stream_report/renderers/terminal.py` | Rich tables and stderr diagnostics |
| JSON renderer | `src/nginx_stream_report/renderers/json.py` | Stable versioned JSON document |
| CSV renderer | `src/nginx_stream_report/renderers/csv.py` | Stable normalized CSV rows |
| Error taxonomy | `src/nginx_stream_report/errors.py` | Typed failures carrying the public exit code |

Imports point inward: renderers and the CLI may depend on models, but the parser and aggregate layer never depend on Click or Rich.

## 4. Streaming Data Model

There are no database tables, migrations, persisted caches, or temporary data files. The only state lives in process memory for the duration of one command.

| Dataclass/state | Fields and types | Invariants |
|---|---|---|
| `LogRecord` | `ip: str`, `timestamp: datetime`, `request_target: str`, `status: int`, `user_agent: str` | Created only for a valid combined-log line; target excludes method/protocol |
| `AggregateState` | `total_valid: int`, `total_invalid: int`, `ip_counts: Counter[str]`, `error_url_counts: Counter[str]`, `hour_counts: list[int]` length 24, `unique_user_agents: set[str]` | Updated once per valid record; 4xx/5xx means `400 <= status <= 599`; empty/`-` UA is not distinct |
| `RankedCount` | `rank: int`, `key: str`, `count: int` | Sort by count descending, then key ascending; maximum 10 per ranked section |
| `HourlyShare` | `hour: int`, `count: int`, `percentage: float` | Exactly 24 rows; percentage is `100 × hourly_request_count / total_valid_requests`, or `0.0` when no valid requests |
| `Report` | schema version, source label, totals, ranked tuples, hourly tuple, `unique_user_agent_count: int`, `unique_user_agent_share: float` | Renderers receive one immutable snapshot after successful analysis |

Unique User-Agent share is `100 × unique_nonempty_user_agent_count / total_valid_requests`, with `0.0` for an empty valid set. Exact distinct counting is retained until `--max-unique-user-agents`; attempting to exceed that ceiling aborts with exit code 4 rather than silently approximating.

Memory complexity is `O(U_ip + U_error_url + U_ua)`, plus constant parser/line buffers. The implementation must not call `read()`, `readlines()`, or retain `LogRecord` instances after aggregation.

## 5. Parsing Contract

P0 accepts nginx combined-log lines in this logical form:

```text
remote_addr ident authuser [timestamp zone] "METHOD request-target PROTOCOL" status bytes "referer" "user-agent"
```

- Input is UTF-8 text with replacement disabled; invalid UTF-8 is a data-format error.
- The request target is preserved as logged, including query string; URL counts therefore distinguish different query strings.
- The hour is the two-digit wall-clock hour in each log timestamp. Time-zone conversion is not performed.
- Status 400–599 contributes to the error URL ranking.
- A malformed line increments the invalid count and emits a concise stderr warning by default; `--strict` stops on the first malformed line with code 3.
- If no valid lines exist, the command still returns a zero-valued report and code 0 unless strict parsing already failed.
- Reading a regular file is line buffered. `-` or an omitted input path reads stdin.

## CLI Interface

### Commands

The package exposes one console script and one analysis command:

```text
nginx-report [OPTIONS] [INPUT]
```

`INPUT` is an nginx access-log path. Omit it or pass `-` to read standard input. Multiple files, directories, URLs, compressed-file auto-detection, and follow/tail mode are outside the MVP.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit only the JSON report to stdout |
| `--csv` | flag, false | Emit only normalized CSV to stdout |
| `--strict` | flag, false | Abort on the first malformed line with exit 3 |
| `--max-unique-user-agents INTEGER` | positive integer, `5000000` | Abort with exit 4 before adding a distinct UA beyond the ceiling |
| `--no-color` | flag, false | Disable Rich color in terminal mode; color is also disabled when stdout is not a TTY |
| `--version` | flag | Print version and exit 0 |
| `--help` | flag | Print Click help and exit 0 |

`--json` and `--csv` are mutually exclusive; Click rejects invalid combinations with exit 2. Machine formats never contain ANSI escapes. Diagnostics and warnings go to stderr; report data goes to stdout.

### Outputs

Default terminal output contains four labeled sections plus valid/invalid totals. Rankings contain at most ten rows. Ties are ordered lexicographically after count sorting so output is deterministic.

JSON uses this top-level shape and stable key names:

```json
{
  "schema_version": 1,
  "source": "stdin",
  "total_valid_requests": 0,
  "invalid_lines": 0,
  "top_ips": [],
  "top_error_urls": [],
  "hourly_request_distribution": [],
  "unique_user_agents": {"count": 0, "share_percentage": 0.0}
}
```

Ranked JSON rows contain `rank`, `value`, and `count`; hourly rows contain `hour` (`"00"`–`"23"`), `request_count`, and `percentage`. Percentages are numbers rounded to two decimal places for presentation; tests allow the documented rounding while internal calculation retains full precision.

CSV begins with:

```text
section,rank,key,count,percentage
```

- `top_ip` and `top_error_url` rows use rank/key/count and leave percentage empty.
- `hourly_request_distribution` rows use key as `00`–`23`, count, and percentage; rank is empty.
- One `unique_user_agents` row uses key `distinct`, count, and percentage; rank is empty.
- Python's `csv` module performs RFC 4180-compatible quoting and newline handling.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Analysis and selected rendering completed successfully, including an empty but readable input |
| `1` | I/O or unexpected runtime failure, including missing/unreadable input or broken output not caused by normal pipe closure |
| `2` | CLI usage error from Click, such as mutually exclusive formats or invalid option values |
| `3` | Input data/format failure, including invalid UTF-8 or a malformed line in strict mode |
| `4` | Unique-cardinality exhaustion: adding another distinct nonempty User-Agent would exceed the configured ceiling |

Normal downstream pipe closure is handled quietly according to standard CLI convention and must not print a traceback.

## 7. Error and Diagnostic Design

Domain exceptions map in exactly one place in `cli.py`. Expected failures print a one-line `error:` message to stderr with source and line number where relevant. No expected error prints a Python traceback. Unexpected exceptions map to code 1; debug tracebacks are a development/testing concern and are not enabled by a public MVP option.

Default malformed-line warnings are rate-limited: show the first five with line numbers, then one suppression summary. Invalid count remains exact. A successful report with skipped lines clearly displays `invalid_lines` in every output format.

## 8. Performance Design

- Compile the parsing expression once at module import.
- Iterate the input object directly and update primitive counters immediately.
- Extract only fields required by the report; do not retain referer, byte count, ident, or auth user.
- Use `Counter.most_common()` only after the stream ends, then apply deterministic tie ordering.
- Benchmark from a generated, non-sensitive combined-log fixture whose byte size and cardinalities are recorded.
- Measure wall-clock time and peak resident memory with a warmed local filesystem cache and at least three runs; report the median.
- The acceptance target is a median under 30 seconds for 1 GB on the recorded reference laptop, with output redirected to avoid terminal rendering cost.

No concurrency is added without profiling evidence. No approximate ranking or cardinality algorithm may silently replace exact results.

## 9. Security and Privacy

Logs are untrusted input. The parser does not evaluate shell syntax, follow URLs, deserialize objects, or interpolate fields into commands. Rich markup is disabled/escaped for log-derived values. CSV cells are quoted; because CSV may be opened in spreadsheet software, values beginning with `=`, `+`, `-`, or `@` are prefixed safely in CSV only and the transformation is documented in help.

The tool performs no telemetry and writes no persistent data. File access is read-only. Error messages avoid echoing entire lines, which may contain tokens or personal data. Dependency versions and licenses are reviewed before release.

## 10. Packaging and Deployment

The deployment target is a local Python 3.11 environment installed from an sdist or wheel with pip. `pyproject.toml` defines the `nginx-report` console entry point and runtime dependencies (`click`, `rich`). Docker, Compose, cloud, and Kubernetes are intentionally absent. Supported release verification runs on Linux; macOS compatibility is expected and tested if runner time allows. Windows is best-effort for the MVP because nginx log workflows are primarily Unix-like.

There are no environment variables, secrets, configuration files, ports, endpoints, health checks, or database schemas. All behavior is explicit in the command invocation.

## 11. Architecture Decision Records

### ADR-001: Use a synchronous single-process streaming pipeline

- **Status:** Accepted by the pre-approved product brief.
- **Decision:** Use Variant A and hold only aggregate state.
- **Consequences:** Simple stdin behavior and packaging; memory grows with exact distinct keys and must be measured.

### ADR-002: No persistence and no network API

- **Status:** Accepted.
- **Decision:** **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- **Consequences:** Zero service operations and no retained history; users compose files and pipes for repeatability.

### ADR-003: Exact User-Agent cardinality with a hard ceiling

- **Status:** Accepted.
- **Decision:** Track exact nonempty strings up to a configurable ceiling, then exit 4.
- **Consequences:** Results never become silently approximate; extreme inputs fail explicitly.

### Review status

The separate Devil's Advocate review is intentionally outside this session per the benchmark protocol. No independent or adversarial-review verdict is asserted here; an external reviewer may append or request ADR revisions later.

## 12. Test Boundaries

- Parser unit tests cover valid combined lines, escaping, IPv4/IPv6 strings, status boundaries, timestamps, malformed requests, and invalid UTF-8 handling at the input boundary.
- Aggregator unit tests cover all four metrics, tie ordering, empty input, exact percentage formulas, and the cardinality ceiling.
- Renderer golden tests cover terminal content without relying on ANSI sequences and exact JSON/CSV schemas.
- CLI integration tests invoke Click's runner for stdin/files and assert stdout, stderr, and every code in `0/1/2/3/4`.
- Performance tests are marked separately and record environment and fixture metadata.

