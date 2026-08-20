# Project Architecture: nginx-insight

## Architecture Summary

The approved design is one installable Python 3.11 process. It opens each input sequentially, parses one line at a time into a dataclass, updates in-memory aggregators, then renders a report after end-of-input. Raw log records are never retained. The explicit decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add persistence, schema management, I/O, cleanup, and privacy exposure while the product only needs a one-run summary. An HTTP API would add a server lifecycle, network and authentication concerns, deployment, and a second interface while the target user already works in a terminal and needs stdin/stdout composition. The process is local, has no authentication, and makes no network calls.

## Architecture Variants

### Variant A: Single-process streaming CLI (Selected)

- **Approach:** Click owns argument validation; an input iterator yields lines; a parser emits `AccessRecord` values; one `ReportAccumulator` updates four metric-specific structures; a renderer serializes the final `Report`.
- **Pros:** smallest operational surface, one-pass I/O, direct pip install, straightforward tests, no infrastructure cost.
- **Cons:** exact top lists can grow with distinct IP/URL cardinality; CPU work is single-process; results exist only for the run.
- **Best for:** local analysis of individual nginx access logs up to the stated laptop target.
- **Estimated complexity:** Low.

### Variant B: Unix pipeline of independent metric commands

- **Approach:** parse once per metric or fan parsed records out to separate commands.
- **Pros:** individually simple components and familiar shell composition.
- **Cons:** repeated parsing or IPC overhead, harder atomic output/error semantics, more complicated packaging and CSV/JSON consistency.
- **Best for:** teams already maintaining shell-native analytics stages.
- **Estimated complexity:** Medium.

### Variant C: Local multiprocessing map/reduce

- **Approach:** split seekable files into chunks, aggregate in workers, then merge partial reports.
- **Pros:** can use multiple CPU cores on very large files.
- **Cons:** stdin is not naturally splittable; nginx line boundaries and merge logic add complexity; startup and memory costs oppose the one-weekend scope.
- **Best for:** a future release only if profiling proves parsing CPU-bound.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the user pre-approved the obvious single-process architecture and it directly meets the stateless, local, $0, one-weekend constraints. Variants B and C remain documented alternatives, not pending decisions.

## Component Boundaries

| Component | Planned path | Responsibility | Must not do |
|---|---|---|---|
| CLI | `src/nginx_insight/cli.py` | Define command/options, validate combinations, map exceptions to exits | Parse log syntax or format metric details |
| Input | `src/nginx_insight/input.py` | Yield decoded lines from stdin and ordered files | Buffer whole files |
| Parser | `src/nginx_insight/parser.py` | Parse supported combined-log lines into `AccessRecord` or classified parse error | Perform aggregation |
| Models | `src/nginx_insight/models.py` | Dataclasses for records, counters, ranked items, and report | Depend on Click or Rich |
| Aggregation | `src/nginx_insight/aggregate.py` | Update counts and finalize percentages/rankings | Write output |
| Renderers | `src/nginx_insight/renderers/{terminal,json,csv}.py` | Serialize one canonical `Report` | Recompute metrics |
| Errors | `src/nginx_insight/errors.py` | Typed domain errors and stable exit-code mapping | Print diagnostics directly |

Data flow:

```text
files/stdin -> decoded line iterator -> combined-log parser -> AccessRecord
                                                        |
                                                        v
                                              ReportAccumulator
                                     (IP, error URL, hour, UA set)
                                                        |
                                                        v
                                                    Report
                                                        |
                                          terminal | JSON | CSV
```

## Data Model and State

There are no database tables, migrations, files written by default, caches, or retained history. These in-memory dataclasses form the complete domain model:

| Dataclass | Fields and types | Invariants |
|---|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `method: str`, `url: str`, `protocol: str`, `status: int`, `bytes_sent: int | None`, `user_agent: str` | Timestamp has parsed offset; status is 100–599; absent byte count is `None` |
| `RankedCount` | `value: str`, `count: int`, `rank: int` | Count > 0; stable rank starts at 1 |
| `HourlyBucket` | `hour: int`, `count: int`, `percentage: float` | Hour 0–23; all 24 buckets emitted; percentage derived from valid records |
| `UserAgentSummary` | `unique_count: int`, `total_valid_requests: int`, `percentage: float`, `limit: int` | Percentage is zero when denominator is zero; cardinality cannot exceed limit |
| `Report` | `total_lines: int`, `total_valid_requests: int`, `malformed_lines: int`, `top_ips: tuple[RankedCount, ...]`, `top_error_urls: tuple[RankedCount, ...]`, `hourly: tuple[HourlyBucket, ...]`, `user_agents: UserAgentSummary` | Rankings have at most 10 rows; counts reconcile with input accounting |

Transient aggregation structures:

- `dict[str, int]` for exact IP counts.
- `dict[str, int]` for exact URL counts, updated only for status 400–599.
- A fixed list of 24 integer request counters, keyed by the timestamp hour as written in the log's offset.
- `set[str]` of distinct User-Agent strings, capped by `--max-unique-user-agents` (default `1_000_000`). Crossing the cap fails with exit 4 rather than returning an approximate or misleading percentage.
- Scalar totals for all, valid, and malformed lines.

Raw records are eligible for collection immediately after each update. Final ranking sorts by descending count and then ascending value, ensuring deterministic ties. Hourly request distribution is a percentage calculated for every hour with the literal formula `100 × hourly_request_count / total_valid_requests`; when there are no valid requests, every bucket is `0.0`.

Unique User-Agent share means the percentage of valid requests represented by distinct User-Agent values: `100 × unique_user_agent_count / total_valid_requests`. It is a diversity indicator and may exceed intuitive “traffic share” interpretations, so the JSON and CSV field is named `unique_user_agent_percentage` and the count is also emitted.

## Parsing Contract

MVP input is the standard nginx combined-log shape:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

- UTF-8 is decoded strictly. An undecodable source is an input failure, exit 3.
- A syntactically malformed line increments `malformed_lines` and processing continues by default.
- `--strict` makes the first malformed line a processing failure, exit 1, with source and line number on stderr.
- The request field is split into method, URL target, and protocol. A literal `-` request is malformed for MVP metrics.
- The URL metric uses the request target exactly as logged, including its query string. No decoding, normalization, or secret scrubbing is implied.
- Only valid records contribute to all four metrics and their denominators.
- Empty input and input with zero valid records produce a valid empty report and exit 0 unless `--strict` encounters malformed content.

## CLI Interface

### Command

```text
nginx-insight [OPTIONS] [LOG_FILE]...
```

With no `LOG_FILE`, input is read from stdin. One or more file paths are processed in command-line order. The command never recursively discovers files and never follows them in the MVP.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit normalized RFC 4180-compatible CSV; mutually exclusive with `--json` |
| `--strict` | flag, false | Stop on the first malformed log line with exit 1 |
| `--no-color` | flag, false | Disable ANSI styling in terminal mode; ignored for JSON/CSV |
| `--max-unique-user-agents INTEGER` | default `1000000`, minimum 1 | Bound exact User-Agent cardinality; exhaustion exits 4 |
| `--version` | flag | Print version and exit 0 without reading input |
| `--help` | flag | Print Click help and exit 0 without reading input |

### Inputs

- Binary file handles or stdin are decoded as UTF-8 and consumed line-by-line.
- Regular files, FIFOs, and piped stdin are supported. Directories and missing/unreadable files are rejected before reporting.
- Multiple explicit files form one logical report; counters and percentages span all valid records across them.
- The CLI does not accept URLs, compressed files, nginx configuration files, or alternate format templates in MVP.

### Outputs

- **Terminal (default):** four Rich sections on stdout: top IPs, top error URLs, 24 hourly buckets, and unique User-Agent count/share. Color is enabled only when appropriate and not forced into redirected output. A final input-quality line shows valid and malformed counts.
- **JSON:** one UTF-8 object followed by a newline. Keys are `schema_version`, `total_lines`, `total_valid_requests`, `malformed_lines`, `top_ips`, `top_error_urls`, `hourly_request_distribution`, and `user_agents`. Rankings contain `rank`, `value`, and `count`; hours contain `hour`, `count`, and `percentage`.
- **CSV:** header plus normalized rows with columns `schema_version,metric,rank,bucket,value,count,percentage`. Metrics are `top_ip`, `top_error_url`, `hourly_request_distribution`, and `unique_user_agents`.
- Reports go to stdout. Diagnostics go to stderr. JSON/CSV stdout contains no Rich markup, warnings, or progress text.
- Percentages are numeric values rounded to two decimal places for presentation; calculations use unrounded counts and reconciliation allows only rounding drift.

### Exit Codes

| Code | Meaning | Examples |
|---:|---|---|
| `0` | Success | Report emitted, including empty report; help/version shown |
| `1` | Processing/data failure | Strict-mode malformed line; violated internal report invariant |
| `2` | CLI usage failure | Invalid option, mutually exclusive formats, invalid cardinality limit |
| `3` | Input I/O or decoding failure | Missing/unreadable file, directory input, UTF-8 decode error, interrupted read |
| `4` | Unique-cardinality exhaustion | Exact distinct User-Agent count would exceed configured limit |

For nonzero exits, no partial JSON/CSV document is emitted. A concise diagnostic is written to stderr. Click's parse-time errors are normalized to code 2; domain exceptions are mapped once at the CLI boundary.

## Error and Security Boundaries

- Log content is untrusted data. It is never executed, interpolated into shell commands, or interpreted as Rich markup.
- Renderers escape terminal control sequences or represent them safely; JSON and CSV use standard serializers.
- Diagnostics include source path and line number but do not echo an entire potentially sensitive line by default.
- No authentication mechanism exists because there is no server, identity boundary, or privileged operation. Access is governed by local filesystem permissions.
- The tool makes no outbound requests and stores no analytics. Logs may contain personal data, but processing remains local.
- `KeyboardInterrupt` yields exit 3 and no partial structured output.

## Performance and Capacity

The target is 1 GB in under 30 seconds on a documented laptop. The implementation remains single-process until profiling demonstrates otherwise.

- Time is O(n + u log u + e log e), where n is lines, u distinct IPs, and e distinct error URLs; final sorting creates the log factors.
- Raw-input memory is O(1); aggregate memory is O(u + e + a), where a is distinct User-Agents up to the configured cap.
- The parser compiles its pattern once, avoids per-line dictionaries, and does not instantiate renderer objects in the hot loop.
- Benchmark output is directed away from a terminal so rendering speed does not distort parsing/aggregation measurement.
- A representative 1 GB fixture, Python version, CPU, RAM, storage, OS, cache state, wall time, peak RSS, valid/malformed counts, and command are recorded.

Exact IP and error-URL counts are required, so silent approximate sketches are not permitted in MVP. If profiling shows adversarial cardinality threatens laptop memory, the product must gain an explicit general cardinality policy in a later spec revision rather than changing semantics silently.

## Packaging and Deployment

Deployment means installing a wheel into a local Python 3.11 environment:

```text
python3.11 -m pip install nginx-insight
nginx-insight --version
```

`pyproject.toml` declares Python `>=3.11,<4`, Click and Rich runtime dependencies, the `src/` package layout, and the `nginx-insight` console entry point. No Dockerfile, `docker-compose.yml`, daemon, HTTP listener, cloud resource, Kubernetes manifest, database, or environment variable is required. This is deliberate rather than missing deployment work.

## Observability

The CLI's observable surface is stdout, stderr, exit status, and optional external timing/RSS tools. It does not emit telemetry. Diagnostics are concise and stable enough for operators but are not part of structured stdout. Future verbose timing would require a new documented option and must remain on stderr.

## Architecture Decision Record (ADR)

### ADR-001: Local stateless single-process CLI

- **Status:** Accepted from pre-approved user constraints.
- **Decision:** Use Variant A and the literal constraint **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- **Consequences:** Minimal operations and local privacy; no history or remote access; memory grows with exact distinct-value metrics.

### ADR-002: Exact metrics with explicit User-Agent cardinality failure

- **Status:** Accepted.
- **Decision:** Preserve exact results. Bound the distinct User-Agent set and return exit 4 upon exhaustion rather than approximate silently.
- **Consequences:** Automation can distinguish capacity failure; a run may fail on extreme diversity and must be retried only with a consciously higher bound and sufficient memory.

### ADR-003: One canonical report, three renderers

- **Status:** Accepted.
- **Decision:** Calculate once and serialize the same `Report` to terminal, JSON, or CSV.
- **Consequences:** Cross-format values can be contract-tested and presentation code cannot redefine metrics.

The required adversarial review is intentionally deferred to the external harness. No inline Devil's Advocate or independent-review verdict is represented in this document.

