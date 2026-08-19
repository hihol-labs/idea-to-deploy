# Project Architecture: Nginx Stream Report

## 1. Context and Constraints

The system is a pip-installable Python 3.11 command-line application for local DevOps/SRE analysis of nginx combined access logs. It accepts a file path or stdin, processes valid records in one pass, and emits one of three equivalent representations. The architecture decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add installation, persistence, schema, cleanup, security, and I/O costs without helping a one-shot report whose source of truth is already the input log. An HTTP API would add a long-running server, network exposure, authentication questions, deployment work, and serialization overhead while the users and pipeline callers already have a native process boundary. In-memory bounded aggregation gives the shortest operational path and meets the $0, one-weekend, local-only brief.

Hard constraints:

- Python 3.11, Click, Rich, and dataclasses.
- No authentication, database, HTTP API, server, cloud, or Kubernetes.
- Exact results for accepted records; no sampling or probabilistic cardinality in MVP.
- Target: a representative 1 GB log in under 30 seconds on a documented laptop profile.
- Default top size is 10.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** one CLI process performs buffered read, parse, aggregate, finalize, and render stages.
- **Pros:** simplest install and operation; one pass over input; no serialization between components; easiest deterministic testing; $0 infrastructure.
- **Cons:** exact unique sets consume memory proportional to distinct values until the configured safety ceiling; CPU work is single-process.
- **Best for:** local ad-hoc analysis and shell pipelines on laptop-scale logs.
- **Estimated complexity:** Low.

### Variant B: Unix pipeline of specialized commands

- **Approach:** separate parser and metric commands exchange line-oriented records over pipes.
- **Pros:** individual stages can be replaced and independently parallelized.
- **Cons:** multiple entry points, extra serialization, harder atomic error behavior, and a worse sub-30-second path.
- **Best for:** toolkits whose intermediate event format is itself a public product.
- **Estimated complexity:** Medium.

### Variant C: Local worker pool

- **Approach:** split seekable files into chunks, aggregate in worker processes, then merge partial counters.
- **Pros:** can use multiple CPU cores for parsing.
- **Cons:** stdin is not naturally splittable; chunk boundaries and merge semantics add substantial complexity; worker startup and data transfer can erase benefits.
- **Best for:** a later version only if profiling proves parsing is CPU-bound and the single-process target is unattainable.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the architecture is pre-approved, the feature set is small, stdin is a first-class input, and the one-weekend constraint favors a deterministic process over coordination machinery. Variant C is a performance contingency, not MVP scope.

## 3. System Context

```text
nginx access log file ----\
                           > [nginx-report process] ---> Rich terminal text
stdin --------------------/              |------------> JSON document
                                          \-----------> normalized CSV rows
```

There are no network calls, persistent stores, credentials, user accounts, daemons, or external runtime services.

## 4. Component Design

```text
Click CLI
  -> Input adapter (buffered binary file or stdin)
  -> Combined-log parser
  -> Aggregator
       - request counter
       - IP Counter
       - error-URL Counter
       - 24 hourly buckets
       - User-Agent set
       - per-dimension cardinality guards
  -> Result finalizer (stable ordering and percentages)
  -> Renderer (Rich | JSON | CSV)
```

| Module | Responsibility | Must not do |
|---|---|---|
| `src/nginx_stream_report/cli.py` | Click command, option validation, input/output ownership, exception-to-exit mapping | Parse individual records or format metric internals |
| `src/nginx_stream_report/parser.py` | Convert one supported combined-log line into an immutable `AccessRecord` dataclass | Retain lines or perform aggregation |
| `src/nginx_stream_report/models.py` | `AccessRecord`, ranked item, hourly bucket, and report dataclasses | File I/O or presentation |
| `src/nginx_stream_report/aggregate.py` | Update exact counters/sets, enforce cardinality ceilings, and finalize `Report` | Read the entire file or emit output |
| `src/nginx_stream_report/renderers/text.py` | Rich tables and warnings for terminal mode | Change metric values |
| `src/nginx_stream_report/renderers/json.py` | Stable JSON schema | Add terminal styling |
| `src/nginx_stream_report/renderers/csv.py` | Stable normalized CSV schema | Emit multiple incompatible tables |
| `src/nginx_stream_report/errors.py` | Typed expected failures and exit-code mapping | Catch programmer defects indiscriminately |

Only aggregate state survives between lines. Raw lines and `AccessRecord` objects become collectible immediately after each update.

## 5. Input and Parsing Contract

MVP accepts nginx combined-log records shaped as:

```text
remote_addr - remote_user [dd/Mon/yyyy:HH:mm:ss ±HHMM] "METHOD request HTTP/version" status bytes "referer" "user_agent"
```

Contract details:

- Input encoding is UTF-8 with invalid byte sequences replaced for parsing; the replacement-containing line will normally be malformed and skipped.
- A positional `INPUT` is a regular file path or `-`; omitted input also means stdin.
- Reading is buffered and line-oriented. The program never calls an unbounded whole-file read.
- The request target is the literal target between method and protocol; query strings remain part of the URL key.
- Status is a three-digit integer. Error URLs count records with status 400 through 599 inclusive.
- The hour is the `HH` value as recorded in each timestamp. The report has 24 clock-hour buckets `00` through `23`; mixed offsets are not normalized.
- Malformed lines are counted and skipped. A report can succeed with warnings when at least one valid line exists.
- Empty input or input with zero valid records is a parse/input failure (exit 3), not a zero-filled successful report.
- MVP does not accept arbitrary custom `log_format` definitions, multiline records, or retrospective timezone conversion.

## 6. Metric Semantics

Let `total_valid_requests` be the number of records accepted by the parser.

- **Top client IPs:** exact count per `remote_addr`, sorted by count descending and key ascending for ties, truncated to the configured top size (10 by default).
- **Top error URLs:** exact count per literal request target for statuses 400–599, same deterministic ordering, truncated to 10 by default.
- **Hourly request distribution:** for every hour `00`–`23`, `100 × hourly_request_count / total_valid_requests`. Values are JSON numbers and CSV decimal fields; text uses two decimal places. Unrounded internal values drive structured output.
- **Unique User-Agent share:** `100 × unique_user_agent_count / total_valid_requests`, where the numerator is the exact number of distinct literal User-Agent strings among valid records. The result may exceed neither 100% nor the valid-request count because every valid record contributes one User-Agent value.
- **Malformed lines:** exposed as metadata/warning count but excluded from every denominator and ranking.

Exact aggregation needs memory proportional to unique IPs, error URLs, and User-Agents. `--max-unique` sets the maximum distinct keys allowed independently in each dimension (default 1,000,000). Exceeding any dimension fails immediately with exit 4 and no partial report; this is unique-cardinality exhaustion.

## CLI Interface

### Command

```text
nginx-report [OPTIONS] [INPUT]
```

### Inputs

- `INPUT`: optional nginx access-log file path. `-` or omission reads stdin.
- The program reads exactly one input stream per invocation.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one JSON document to stdout |
| `--csv` | flag, false | Emit normalized CSV to stdout |
| `--top INTEGER` | 10 | Ranking size; integer in `1..1000` |
| `--max-unique INTEGER` | 1,000,000 | Per-dimension distinct-key ceiling; positive integer |
| `--no-color` | flag, false | Disable Rich color in text mode |
| `--version` | flag | Print version and exit 0 |
| `--help` | flag | Print Click help and exit 0 |

`--json` and `--csv` are mutually exclusive. Text is the default. Structured modes never contain ANSI styling. Diagnostics and malformed-line warnings go to stderr; the selected report goes to stdout. Rich disables color when stdout is not a terminal unless color is explicitly supported, and `--no-color` always disables it.

### Outputs

Text output contains a summary followed by Top IPs, Top Error URLs, Hourly Distribution, and User-Agent Diversity sections. Empty error rankings are shown explicitly rather than omitted.

JSON schema, represented structurally:

```json
{
  "schema_version": 1,
  "total_valid_requests": 0,
  "malformed_lines": 0,
  "top_ips": [{"rank": 1, "ip": "string", "count": 0}],
  "top_error_urls": [{"rank": 1, "url": "string", "count": 0}],
  "hourly_distribution": [{"hour": "00", "count": 0, "percentage": 0.0}],
  "unique_user_agents": {"count": 0, "share_percentage": 0.0}
}
```

CSV always has the header `section,rank,key,count,percentage`. Ranking rows use `top_ip` or `top_error_url`; hourly rows use `hourly_distribution`; the single User-Agent row uses `unique_user_agents`. Inapplicable fields are empty. CSV quoting follows Python's `csv` module.

### Exit Codes

| Code | Meaning |
|---:|---|
| 0 | Successful report, including success with one or more malformed lines skipped |
| 1 | Unexpected internal failure or output I/O failure |
| 2 | CLI usage error, including invalid option values or mutually exclusive modes |
| 3 | Input/read/parse failure, including missing/unreadable input, empty input, or zero valid records |
| 4 | Unique-cardinality exhaustion: a configured distinct-key ceiling was exceeded |

No report is written after a fatal code 1, 2, 3, or 4 is determined. Expected diagnostics are concise, stable in meaning, and written to stderr.

## 8. Data and Persistence

There are **no database tables, migrations, files written as state, caches, checkpoints, or retained reports**. The complete data model is the dataclasses and transient collections described above. This intentionally replaces the template's database-schema section: adding even one table would violate the approved architecture.

Approximate memory is bounded operationally by `--max-unique` for each exact unique-key collection plus small fixed state. The input size itself does not determine retained memory. The default is a safety limit, not a promise that every machine can hold the maximum; documentation will recommend lowering it under tighter memory limits.

## 9. API, Authentication, and Security

There are **no HTTP endpoints and no authentication flow**. The complete public interface is the process/CLI contract under `## CLI Interface`. This intentionally replaces the template's endpoint and auth sections: a server or auth mechanism would create an incorrect threat surface for a local file-processing tool.

Security boundaries:

- Treat log content as untrusted data, never as terminal markup, format strings, paths, or instructions.
- Escape/sanitize control characters in Rich output; JSON and CSV use standard encoders.
- Never evaluate input, invoke a shell, follow URLs, or make network calls.
- Open only the user-selected input path and write only to stdout/stderr.
- Avoid echoing full malformed lines in diagnostics; report line number and reason to limit sensitive-data leakage.
- Handle broken pipes as output failures consistently and without tracebacks by default.

## 10. Configuration and Environment

All behavior is controlled by command options. **No environment variables are required or read by the MVP.** There is no `.env` file. Locale and terminal capability may affect Rich's presentation mechanics, but never metric values or structured schemas.

## 11. Packaging and Deployment

Deployment means installing a wheel into a local Python 3.11 environment:

```text
source checkout -> python -m build -> wheel -> python -m pip install <wheel> -> nginx-report
```

`pyproject.toml` declares Python `>=3.11,<4`, runtime dependencies on compatible Click and Rich releases, package discovery under `src/`, and the `nginx-report` console script. Releases should pin tested lower/upper dependency bounds and include an sdist and wheel.

There is no Docker image, `docker-compose.yml`, hosted target, staging server, cloud resource, or Kubernetes manifest. Containers add no value to a local pip-installed CLI and would conflict with the 30-second quick-start goal.

## 12. Performance Architecture

- Iterate buffered bytes and decode only each current line.
- Compile parsing machinery once, outside the loop.
- Update primitive counters/sets directly; do not retain records.
- Maintain 24 integer hour buckets.
- Rank only after EOF with `heapq.nsmallest`/equivalent deterministic selection if profiling shows full sorting material; correctness precedes micro-optimization.
- Do not update Rich progress output per line; benchmark mode has no presentation work until finalization.
- Benchmark from a regular local file with warmed and cold-cache conditions identified, using wall-clock time and peak RSS.

The acceptance benchmark uses a checked fixture generator or content-addressed fixture description, a recorded laptop CPU/RAM/OS/Python profile, and the command equivalent to `python -m nginx_stream_report --json benchmark-1gb.log > /dev/null`. Passing means elapsed wall time is under 30 seconds and results match the fixture oracle.

## 13. Error Handling and Observability

Expected exceptions are narrow domain types mapped once in `cli.py`. Default failures have no traceback; a developer test can exercise original exceptions. Operational observability is local: stderr diagnostics include category, relevant line number when safe, malformed count on partial success, and remediation for cardinality exhaustion. There is no telemetry.

## 14. Testing Strategy

| Layer | Evidence |
|---|---|
| Parser unit tests | Valid combined lines, IPv4/IPv6, escaping, malformed timestamps/status/request fields, invalid bytes |
| Aggregator unit tests | All metric formulas, 24 buckets, tie ordering, top size, malformed exclusion, each cardinality boundary |
| Renderer golden tests | Text structure without ANSI, exact JSON schema/types, exact CSV header/quoting/sections |
| CLI integration tests | File/stdin equivalence, mode exclusivity, stderr separation, help/version, complete exit codes 0/1/2/3/4 |
| Packaging smoke test | Build wheel, install into clean environment, invoke console script |
| Performance test | Representative 1 GB under 30 seconds with peak RSS recorded and metric oracle checked |

## 15. Architecture Decision Records

### ADR-001: Choose the single-process streaming variant

- **Status:** Accepted by the pre-approved product decision.
- **Decision:** Use Variant A with one process and one input pass.
- **Reason:** It is the smallest design satisfying local operation, stdin, deterministic output, $0 budget, and weekend delivery.
- **Consequences:** Exact cardinality consumes bounded-but-input-dependent memory; exit 4 makes exhaustion explicit. Multiprocessing remains deferred until measurement justifies it.

### ADR-002: Use no persistence and no network API

- **Status:** Accepted.
- **Decision:** **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- **Reason:** The input log already provides durability, and process I/O already provides the integration boundary.
- **Consequences:** Each invocation recomputes results; callers persist JSON/CSV themselves if needed. There are no database, server, or authentication operational burdens.

### ADR-003: Preserve exactness with fail-closed cardinality limits

- **Status:** Accepted.
- **Decision:** Track exact keys until a configurable per-dimension ceiling, then terminate with code 4 and no partial report.
- **Reason:** Silent approximation would change the required top rankings and User-Agent share.
- **Consequences:** Extremely high-cardinality inputs may not produce a report; the diagnostic tells the operator to raise the ceiling only when memory permits.

No adversarial review is recorded here; that review is outside this blueprint session.
