# Project Architecture: nginx-logtop

## Architecture Summary

`nginx-logtop` is an installable Python 3.11 console application. A single process reads one or more plain-text sources sequentially, parses each line, updates in-memory aggregate counters, and renders one final report. The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. Both constraints are correct because the required metrics are computable in one pass, results do not need persistence or multi-user access, local processing protects log data, and operating a service would add cost and failure modes without improving the approved workflow.

The architecture stores aggregate dictionaries, 24 hourly counters, and an exact set of User-Agent strings; it never stores parsed requests. The User-Agent set is intentionally bounded by a configurable ceiling because exact cardinality cannot otherwise guarantee safe memory use.

## Architecture Decision

### Selected: single-process streaming CLI

- **Approach:** Click invokes a synchronous pipeline of input reader, parser, aggregator, and renderer in one Python process.
- **Benefits:** simplest pip installation, deterministic data flow, no inter-process serialization, no operational dependencies, and easy stdin integration.
- **Trade-offs:** one CPU core processes parsing; exact unique-cardinality memory grows with distinct User-Agents up to the configured limit.
- **Fit:** local, one-shot analysis of files up to and beyond the 1 GB performance fixture.

### Alternatives considered and rejected

| Alternative | Useful when | Why rejected for this MVP |
|---|---|---|
| Multi-process chunking | CPU saturation is measured as the bottleneck and files are seekable | Complicates stdin, line boundaries, merging, and deterministic failure behavior before profiling proves a need |
| SQLite-backed aggregation | Aggregates must survive runs or exceed memory | Adds I/O and persistence to a deliberately stateless tool; only 24 hour buckets and keyed counters are needed |
| Go/Rust rewrite | Profiling proves Python cannot meet the accepted target | Violates the approved Python 3.11 stack and one-weekend scope without current evidence |
| Elastic/Logstash service | Historical querying, dashboards, and multiple operators are required | Requires a server, database, operations, and budget explicitly outside scope |

The single-process choice is pre-approved. No architecture-choice pause is required. The separate Devil's Advocate review is intentionally outside this session and is not represented here as completed.

## Component Boundaries

| Module | Responsibility | Must not do |
|---|---|---|
| `src/nginx_logtop/cli.py` | Define Click command/options, validate combinations, map domain failures to exit codes | Parse log lines or format metric calculations |
| `src/nginx_logtop/models.py` | Define slotted dataclasses for a parsed record, aggregate result, and render metadata | Perform I/O |
| `src/nginx_logtop/parser.py` | Compile and apply the nginx combined-format parser; validate timestamp/status/request target | Keep cross-line state |
| `src/nginx_logtop/aggregate.py` | Update counters, enforce cardinality ceiling, finalize deterministic top-10 rows and percentages | Read files or write output |
| `src/nginx_logtop/inputs.py` | Yield decoded lines from stdin or files, report source and line number, reject invalid decoding | Interpret nginx fields |
| `src/nginx_logtop/render_terminal.py` | Render Rich summary and warnings | Change metric values |
| `src/nginx_logtop/render_json.py` | Serialize the stable JSON document | Emit ANSI styling |
| `src/nginx_logtop/render_csv.py` | Serialize the stable long-form CSV rows | Emit ANSI styling |
| `src/nginx_logtop/errors.py` | Typed domain exceptions and canonical exit-code mapping | Catch unexpected internal failures |

Dependency direction is `cli -> inputs/parser/aggregate -> models`, then `cli -> one renderer`. Renderers consume the same finalized result and do not recalculate metrics.

## Data Flow

1. Click validates options before opening inputs.
2. `inputs.py` opens each source in argument order, or uses stdin when the sole input is `-` or no input is supplied.
3. `parser.py` converts each valid combined-log line into a short-lived slotted dataclass.
4. `aggregate.py` increments total valid requests, per-IP counts, error URL counts split by 4xx/5xx, one of 24 hourly buckets, and the exact User-Agent set.
5. Invalid lines increment a counter in lenient mode; in strict mode the first invalid line raises a data error.
6. A new distinct User-Agent at the configured limit raises cardinality exhaustion; no normal partial report is emitted.
7. Finalization sorts top rows deterministically and computes percentages once.
8. Exactly one renderer writes stdout. Warnings and diagnostics go to stderr.

Peak state is `O(unique_ips + unique_error_urls + min(unique_user_agents, ceiling) + 24)`. Request count does not itself increase memory.

## Log Format Contract

The MVP accepts the conventional nginx combined format:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

- Input is UTF-8 text. A decoding failure is an input/data error.
- The request field must contain a method, request target, and protocol. The URL metric uses the request target exactly as logged, including its query string; no URL decoding or normalization occurs.
- Status must be an integer from 100 through 599.
- The hour is taken from the wall-clock hour in nginx's bracketed timestamp. The logged numeric offset is validated but requests are not converted to another timezone.
- A User-Agent of `-` is treated as absent: it contributes to total valid requests but not to the unique count.
- Files are processed in the order given. Duplicate paths intentionally count duplicate lines.
- Compressed files are not opened directly in MVP; users pipe decompressed bytes, for example `gzip -cd access.log.gz | nginx-logtop`.

## Metric Definitions

| Metric | Definition | Ordering |
|---|---|---|
| Top IPs | Up to 10 client IPs ranked by count across all valid requests | Count descending, then IP string ascending |
| Top error URLs | Up to 10 request targets ranked by statuses 400–599; each row includes total error, 4xx, and 5xx counts | Total error descending, then URL string ascending |
| Hourly request distribution | All 24 wall-clock hour buckets; each percentage is `100 × hourly_request_count / total_valid_requests` | Hour `00` through `23` |
| Unique User-Agent share | `100 × unique_nonempty_user_agent_count / total_valid_requests` | Single percentage plus numerator and denominator |

Percentages are numeric values in the range 0–100. Human and CSV output display two decimal places; JSON emits numbers rounded to two decimal places. Empty error sets and IP sets produce empty top lists. Zero valid requests is a data failure, not a zero-filled successful report.

## CLI Interface

### Commands

```text
nginx-logtop [OPTIONS] [INPUTS]...
nginx-logtop --help
nginx-logtop --version
```

`INPUTS` are plain-text paths. No input means stdin. `-` explicitly means stdin and must be the only input, preventing ambiguous repeated reads.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit one UTF-8 CSV stream with a header; mutually exclusive with `--json` |
| `--strict` | flag, false | Fail at the first malformed line instead of skipping and counting it |
| `--max-unique-user-agents INTEGER` | positive integer, `1000000` | Maximum exact distinct nonempty User-Agents; exhaustion exits `4` |
| `--color / --no-color` | auto by TTY | Control Rich color for terminal output; machine formats never contain ANSI sequences |
| `--version` | flag | Print package version and exit `0` without reading input |
| `--help` | flag | Print Click help and exit `0` without reading input |

### Inputs

- Files are opened read-only and streamed line by line.
- Standard input supports pipes and redirected files.
- Inputs are never modified, uploaded, cached, or persisted.
- Malformed lines are skipped by default and reported as a count on stderr and in machine output metadata.

### Outputs

- Default: four Rich terminal sections plus total-valid and invalid-line summary. Color is enabled only for a TTY unless explicitly overridden.
- JSON: a single UTF-8 object followed by newline, with schema version, source count, valid/invalid totals, `top_ips`, `top_error_urls`, 24 `hourly_distribution` rows, and `unique_user_agents`.
- CSV: a header followed by long-form rows using columns `schema_version,metric,rank,label,count,percentage,count_4xx,count_5xx,total_valid,invalid_lines`. Empty cells represent fields inapplicable to a metric. It contains `top_ip`, `top_error_url`, `hour`, and `unique_user_agent_share` rows.
- Normal data goes only to stdout. Diagnostics go only to stderr. On exit `3` or `4`, no normal report is written, so a consumer cannot mistake partial data for success.

### Exit Codes

| Code | Meaning | Examples |
|---:|---|---|
| `0` | Success | Report emitted; help/version shown |
| `1` | Unexpected internal error | Unhandled invariant failure; concise diagnostic without traceback by default |
| `2` | CLI usage error | Invalid option, conflicting formats, missing option value, invalid stdin combination |
| `3` | Input or data error | File unreadable, UTF-8 decode failure, strict parse failure, or zero valid requests |
| `4` | Unique-cardinality exhaustion | A new distinct nonempty User-Agent would exceed `--max-unique-user-agents` |

## Output Schemas

The JSON top-IP row contains `rank`, `ip`, and `request_count`. A top-error row contains `rank`, `url`, `error_count`, `count_4xx`, and `count_5xx`. Each hourly row contains `hour`, `request_count`, and `percentage`. The unique-UA object contains `unique_count`, `eligible_request_count`, `total_valid_requests`, and `percentage`; the percentage denominator remains total valid requests per the metric definition.

Machine schemas start at string `schema_version: "1"`. Backward-incompatible field changes require a new schema version and PRD update.

## Persistence, Database, and Data Retention

There are no database tables, migrations, cache files, or retained reports. All aggregate state dies with the process. This deliberate zero-table design avoids stale data, schema operations, disk writes, and privacy exposure. Users who want history redirect JSON/CSV to storage they control.

## HTTP API, Authentication, and Authorization

There are no endpoints, request/response bodies, listeners, accounts, sessions, tokens, roles, or authentication flow. OS file permissions and shell execution permissions are the only access boundary. Adding authentication to a local read-only CLI would not protect the source file and would create credential management without a server-side trust boundary.

## Configuration and Environment

There are no required environment variables or `.env` file. Behavior is controlled only by explicit CLI options so pipeline execution is reproducible. Locale and terminal detection may affect Rich styling but never parsed values, ordering, JSON, or CSV.

## Deployment and Packaging

The deployment target is a local laptop or workstation with CPython 3.11. A PEP 517 `pyproject.toml` builds a wheel and source distribution and registers the `nginx-logtop` console script. Installation is through pip, preferably inside `venv` or `pipx`. There is no Dockerfile, Compose file, cloud manifest, server process, or Kubernetes resource because container orchestration does not improve a local stdin/file CLI.

## Error Handling and Observability

- Expected usage and domain failures map once to the documented exit codes.
- Error messages include source and line number where safe, but never echo the full log line or User-Agent.
- Unexpected failures exit `1`; development tests may enable tracebacks, while normal CLI output remains concise.
- `valid_lines`, `invalid_lines`, and input count are included in successful metadata.
- No telemetry, network request, or background process is permitted.

## Performance Design

- Compile the combined-format regex once.
- Avoid `split()` chains and Rich objects in the hot loop.
- Use integer counters and slotted dataclasses; discard each parsed record after aggregation.
- Maintain only error URLs, not all URLs.
- Render only after all input is consumed.
- Benchmark a fixed, representative 1 GB combined-format fixture using wall time and peak RSS on a named laptop with Python and package versions recorded.
- The acceptance target is under 30 seconds. Optimization decisions require profiler evidence; multiprocessing is a contingency, not part of MVP.

## Security and Privacy

Inputs are untrusted. Paths are read-only; data is not evaluated as code. Machine output uses standard JSON/CSV serializers to prevent malformed quoting. Terminal rendering treats log-derived text as literal content so Rich markup cannot be injected. Diagnostics avoid copying raw lines. There is no network egress, telemetry, secret store, or persistence.

## Testing Strategy

- Parser unit fixtures cover valid combined lines, quoting, IPv4/IPv6, time offsets, requests, missing User-Agent, malformed lines, and decoding errors.
- Aggregation unit tests prove rankings, ties, 4xx/5xx splits, all 24 buckets, the literal percentage formula, and cardinality exhaustion.
- Renderer golden tests prove semantically identical results and absence of ANSI in JSON/CSV.
- Click end-to-end tests cover stdin, multiple files, conflicts, strict mode, zero-valid input, and all exit codes `0/1/2/3/4`.
- A packaging smoke test builds and installs the wheel in a clean Python 3.11 environment.
- A performance test records the 1 GB result separately from fast correctness tests.

## Architecture Decision Record

| Decision | Status | Rationale |
|---|---|---|
| Single synchronous process | Accepted and pre-approved | Lowest complexity; supports stdin and all required aggregates |
| No database or retained state | Accepted | One-shot metrics need no persistence |
| CLI only, no HTTP API | Accepted | The user workflow is local files and pipelines |
| Exact User-Agent set with hard ceiling | Accepted | Exact required metric with fail-closed memory protection |
| Combined nginx format only in MVP | Accepted | Makes parsing deterministic within one weekend |
| Query string retained in URL identity | Accepted | Avoids silent semantic transformation and preserves exact logged target |

No adversarial-review verdict is recorded in this document. That review belongs to the external harness in a separate session.
