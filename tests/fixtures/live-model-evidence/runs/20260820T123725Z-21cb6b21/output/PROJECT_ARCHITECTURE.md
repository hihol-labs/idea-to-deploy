# Project Architecture: nginx-analyzer

## Context and Constraints

`nginx-analyzer` is a local Python 3.11 CLI that analyzes one nginx combined access-log stream. It must be pip-installable, use Click, Rich, and dataclasses, cost $0, and be deliverable in one weekend. The primary performance objective is processing the canonical 1 GB fixture in under 30 seconds on a documented laptop.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect here because the four summaries can be computed during one sequential pass, persistence would add latency and operational state, and the user asked for ad-hoc local analysis. An HTTP API is incorrect because there is no remote client, multi-user service, authentication boundary, or server lifecycle; stdin/files plus stdout/stderr are the complete integration surface.

## Architecture Decision

The pre-approved architecture is a single OS process with a streaming pipeline:

```text
file path or stdin
       |
       v
buffered byte-line reader -> combined-log parser -> aggregate state
                                                 |-- Counter: client IP
                                                 |-- Counter: 4xx/5xx URL
                                                 |-- 24 integer hour buckets
                                                 `-- bounded set: User-Agent values
                                                        |
                                                        v
                                                immutable report model
                                                        |
                                      Rich text | JSON | CSV renderer
                                                        |
                                                   stdout/stderr
```

Only the User-Agent set grows with distinct cardinality. The default maximum is 1,000,000 distinct values, configurable through the CLI. Exceeding it aborts without a partial report and returns exit code 4.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** Parse each line once and update in-memory aggregate structures.
- **Pros:** Minimal operations, no intermediate data, straightforward deterministic tests, one-pass performance, natural stdin support.
- **Cons:** One CPU core; exact User-Agent distinctness requires bounded memory proportional to cardinality.
- **Best for:** A local one-off report over files up to and around 1 GB.
- **Estimated complexity:** Low.

### Variant B: Unix-tool composition

- **Approach:** Coordinate `awk`, `sort`, and related subprocesses for each metric.
- **Pros:** Familiar primitives and potentially optimized native sorting.
- **Cons:** Repeated passes or temporary files, fragile quoted-field parsing, platform differences, and no single error/output contract.
- **Best for:** Disposable operator scripts with one metric and trusted simple input.
- **Estimated complexity:** Medium once portability and correctness are included.

### Variant C: Multiprocess chunk analysis

- **Approach:** Split seekable files and merge worker aggregates.
- **Pros:** Can use multiple cores for very large regular files.
- **Cons:** Complex record-boundary handling, unavailable for stdin, higher memory during merge, more failure modes, and poor one-weekend value.
- **Best for:** Proven CPU-bound workloads substantially larger than the MVP target.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the stack and architecture are pre-approved, the input is naturally sequential, the report state is small except for one explicitly bounded set, and the 1 GB target does not justify multiprocessing before measurement. Variants B and C remain rejected unless performance evidence changes the constraints.

## Components and Responsibilities

| Module | Planned path | Responsibility |
|---|---|---|
| CLI | `src/nginx_analyzer/cli.py` | Click command, option validation, stream selection, exception-to-exit mapping |
| Input | `src/nginx_analyzer/input.py` | Buffered binary reads from a file or stdin; decoding policy and I/O errors |
| Parser | `src/nginx_analyzer/parser.py` | Parse supported nginx combined lines into `AccessRecord`; classify malformed lines |
| Models | `src/nginx_analyzer/models.py` | Frozen dataclasses for parsed records, counters metadata, and final report |
| Aggregator | `src/nginx_analyzer/aggregate.py` | One-pass counters, 24 hour buckets, valid/malformed totals, bounded unique User-Agent set |
| Rich renderer | `src/nginx_analyzer/renderers/rich_text.py` | Human-readable colored tables; TTY-aware color |
| JSON renderer | `src/nginx_analyzer/renderers/json_output.py` | Stable single JSON document |
| CSV renderer | `src/nginx_analyzer/renderers/csv_output.py` | Stable normalized CSV rows representing all report sections |
| Errors | `src/nginx_analyzer/errors.py` | Typed domain exceptions with exit-code ownership |

The CLI composes these modules; parser, aggregator, and renderers never call Click directly. Renderers consume the same final report dataclass so their numbers cannot diverge by independent calculation.

## Data Model

### Parsed record

`AccessRecord` is a frozen dataclass with:

| Field | Python type | Meaning |
|---|---|---|
| `client_ip` | `str` | First nginx remote-address field, retained as logged |
| `timestamp` | `datetime` | Offset-aware timestamp parsed from `[dd/Mon/yyyy:HH:mm:ss ±zzzz]` |
| `request_target` | `str` | Request target token from the quoted request line; query string retained |
| `status` | `int` | HTTP status code |
| `user_agent` | `str` | Quoted User-Agent value; `-` is a valid literal value |

The supported grammar is nginx's standard combined format. Escaped quotes and backslashes in quoted fields are handled. The request line is split into method, target, and protocol; only the target is aggregated. URLs are compared exactly as logged, including query strings. IPv4 and IPv6 text are accepted without DNS lookup.

### Aggregate state

| Field | Type | Bound |
|---|---|---|
| `valid_requests` | `int` | One integer |
| `malformed_lines` | `int` | One integer |
| `ip_counts` | `Counter[str]` | One entry per distinct client IP |
| `error_url_counts` | `Counter[str]` | One entry per distinct target with status 400–599 |
| `hour_counts` | `list[int]` | Exactly 24 entries |
| `unique_user_agents` | `set[str]` | At most `--max-unique-user-agents`; default 1,000,000 |

Top-10 ordering is deterministic: descending count, then ascending UTF-8 lexical value for ties. Error URLs combine 4xx and 5xx counts. Hour is the `00`–`23` value in each record's logged local timestamp; timestamps are not converted between offsets.

Hourly request distribution is a percentage computed for every hour using `100 × hourly_request_count / total_valid_requests`. If there are no valid requests, the command produces no report and exits 3, so division by zero is not represented.

Unique User-Agent share is also a percentage: `100 × distinct_user_agent_count / total_valid_requests`. It measures distinct logged User-Agent values relative to valid requests, not the percentage of requests belonging to agents that appear once. Output retains enough numerator/denominator fields to avoid ambiguity.

### Persistence and database schema

There is no database, schema, migration, cache, temporary results table, or persisted application state. All aggregate objects live only for the command duration and are released on exit. This intentional exception to generic architecture templates is required by the product boundary.

## CLI Interface

### Command

```text
nginx-analyzer [OPTIONS] [INPUT]
```

`INPUT` is one nginx combined-log file path. If omitted or exactly `-`, bytes are read from standard input. Multiple files, directories, URLs, compressed files, and follow/tail mode are outside MVP scope.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit one UTF-8 JSON document; mutually exclusive with `--csv`; never emit ANSI color |
| `--csv` | false | Emit UTF-8 CSV with header; mutually exclusive with `--json`; never emit ANSI color |
| `--no-color` | false | Disable color in terminal-text mode; redundant but accepted when stdout is not a TTY |
| `--strict` | false | Abort on the first malformed non-empty line with exit code 3; default mode skips and counts malformed lines |
| `--encoding TEXT` | `utf-8` | Decode quoted text using the named codec with replacement for invalid byte sequences; invalid codec name is usage error 2 |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive ceiling for exact distinct User-Agent values; exceeding it returns 4 |
| `--version` | — | Print version and exit 0 |
| `--help` | — | Print usage and exit 0 |

Empty physical lines are ignored and are not counted as malformed. Options are validated before input is consumed.

### Outputs

- Normal report data is written only to stdout.
- Diagnostics are written only to stderr and never mixed into JSON or CSV.
- Rich terminal text contains a summary and four sections: top client IPs, top error URLs, 24 hourly percentages, and User-Agent distinct share. Color is enabled only when stdout is a TTY and `--no-color` is absent.
- JSON is one object with `schema_version`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`. Counts are integers and shares are numeric percentages rounded to six decimal places.
- CSV uses columns `section,key,count,percentage,rank`. It emits ranked rows for `top_ip` and `top_error_url`, 24 `hour` rows, one `user_agents` row, and summary rows. Non-applicable cells are empty.
- A successful tolerant run reports `malformed_lines` in all formats. It may succeed when some lines are malformed, but never when zero valid requests remain.

### Exit-code contract

| Code | Meaning | Output behavior |
|---:|---|---|
| `0` | Success, including `--help` and `--version` | Complete requested output on stdout |
| `1` | Unexpected internal/runtime failure | Concise diagnostic on stderr; no claim that stdout is complete |
| `2` | CLI usage or option validation error | Click usage diagnostic on stderr |
| `3` | Input/data failure: unreadable input, strict malformed line, or zero valid records | Diagnostic on stderr; no report |
| `4` | Unique-cardinality exhaustion: distinct User-Agent count exceeds the configured ceiling | Diagnostic on stderr; no partial report |

Shell broken-pipe handling follows conventional CLI behavior: stop writing promptly without a traceback. It is not remapped into a false successful report when the renderer did not complete.

## Output Schemas

The JSON structure is versioned from `schema_version: 1`. Field names and meanings are part of the P0 contract. Additive fields require a minor release; removal, renaming, type changes, or semantic changes require a new schema version.

CSV row ordering is stable: summary, top IPs, top error URLs, hours `00` through `23`, then User-Agent share. RFC 4180 quoting is delegated to Python's standard `csv` writer. Rich layout is human-facing and may change without changing machine schema.

## Error Handling and Observability

- Domain errors carry a category and safe message, never a traceback by default.
- With tolerant parsing, malformed line count is accumulated; a bounded sample of line numbers may be included in terminal diagnostics without retaining raw lines.
- No log contents, IPs, URLs, or User-Agent values leave the machine.
- No telemetry or network access exists.
- Tests may expose tracebacks through the test runner; the production CLI maps known failures to codes 2, 3, or 4 and unknown failures to 1.

## Performance and Resource Model

- Read in buffered binary mode and process one physical line at a time.
- Compile parser patterns once; avoid per-line dataclass creation when an extracted tuple can update aggregates directly, while retaining dataclasses at module boundaries.
- Compute top 10 values after streaming with `heapq.nsmallest`/equivalent deterministic selection or a measured faster alternative.
- Do not retain raw records.
- Cardinality memory is explicit and bounded for User-Agents; the IP and error-URL counters are monitored in the canonical and adversarial fixtures.
- Benchmark wall time and peak RSS after a warm-up run on a documented Python 3.11 interpreter, laptop CPU, OS, and storage medium. The acceptance threshold is under 30 seconds for the canonical 1 GB fixture.

If profiling shows the target is missed, optimize parsing and allocations first. Multiprocessing or native extensions require an architecture update and are not implicit escape hatches.

## Security and Privacy

Inputs are untrusted local bytes. The tool does not evaluate strings, invoke a shell, make network calls, resolve DNS, follow URLs, or interpret terminal markup from log fields. Rich values are rendered as text with markup disabled/escaped. File access is read-only. Raw logs may contain personal data, but the application neither persists nor transmits them.

Resource protections include streamed reads, the User-Agent cardinality ceiling, bounded diagnostic samples, and no raw-record collection. Extremely high IP or URL cardinality remains a documented memory risk to be covered by stress tests; no silent approximation is permitted in MVP.

## Packaging and Deployment

Deployment means a local pip installation, not a server rollout:

```text
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install .
nginx-analyzer --help
```

The package uses a `src/` layout, a standards-based `pyproject.toml`, and a `nginx-analyzer` console-script entry point. Runtime dependencies are Click and Rich; dataclasses and all parsing/aggregation utilities come from Python 3.11. No Docker, Compose, environment variables, daemon, cloud resource, or Kubernetes manifest is required.

## Testing Strategy

| Layer | Evidence |
|---|---|
| Parser unit tests | Common valid lines, IPv6, escaped quoted fields, malformed requests, invalid dates/statuses, invalid bytes |
| Aggregation unit tests | Four metrics, exact formulas, ties, empty hours, 4xx/5xx inclusion and 3xx exclusion, cardinality boundary |
| Renderer contract tests | Golden Rich plaintext, parsed JSON schema, parsed CSV rows, no ANSI in machine output |
| CLI integration tests | File/stdin parity, option exclusivity, tolerant/strict behavior, exit codes `0/1/2/3/4` |
| Packaging test | Build wheel, install into clean Python 3.11 environment, run `--version` and a sample report |
| Performance test | Generate deterministic 1 GB fixture, record wall time and peak RSS on reference laptop |

## Architecture Decision Record (ADR)

### ADR-001: Local stateless CLI

- **Status:** Accepted by the user before blueprint generation.
- **Decision:** Use one Python process and in-memory streaming aggregates; expose only a CLI.
- **Rationale:** Meets the four-report requirement with the smallest operational surface and $0 budget.
- **Consequences:** No historical queries, shared dashboards, remote service, or persistence. Exact User-Agent cardinality needs a bounded set and a dedicated exhaustion result.
- **Rejected:** ELK/Logstash service stack, embedded database, HTTP service, cloud function, Kubernetes job, and multiprocess default.

No adversarial or independent review is recorded here; that review is intentionally delegated to the external harness in a separate fresh session.

Requirements are defined in `PRD.md`; sequencing and verification commands are in `IMPLEMENTATION_PLAN.md`; execution prompts are in `CLAUDE_CODE_GUIDE.md`.
