# Project Architecture: nginx-log-top

## Architecture Summary

The product is a single Python 3.11 process with a linear flow:

```text
file path or stdin
       |
       v
line iterator -> parser -> streaming aggregator -> immutable result -> one renderer
                                              text | JSON | CSV
```

The architecture decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. Both constraints are correct because each run analyzes one explicit input stream, produces a complete result, and exits. Persistence would add schema, migration, corruption, cleanup, and privacy concerns without helping the required one-shot reports. An HTTP API would add authentication, networking, lifecycle management, resource isolation, and deployment obligations while weakening the local-file and Unix-pipeline workflow.

## Goals and Quality Attributes

- Correctly parse the documented nginx combined log format.
- Process a 1 GB input in under 30 seconds on a documented reference laptop.
- Use memory proportional to aggregate cardinality, never input byte size.
- Produce semantically equivalent text, JSON, and CSV reports.
- Remain deterministic: count descending, then key ascending for rank ties.
- Fail explicitly on I/O, parse policy, output, or unique-cardinality errors.

## Architecture Decision and Alternatives

### Chosen: single-process streaming pipeline

- **Approach:** one Click entry point connects input, a compiled parser, one mutable aggregation state, a frozen result model, and one selected renderer.
- **Advantages:** one pass, minimal serialization, straightforward profiling, pip-native distribution, and no operations burden.
- **Trade-off:** exact sets and counters still grow with unique IP, URL, or User-Agent cardinality; the User-Agent set therefore has a hard limit.
- **Best for:** local and piped nginx logs up to and beyond the 1 GB target.
- **Complexity:** Low.

### Rejected: shell pipeline

`awk | sort | uniq` is available everywhere but typically requires multiple parsing/counting pipelines, can create large sort intermediates, and lacks one stable JSON/CSV/error contract.

### Rejected: local SQLite staging

SQLite could bound application memory and support arbitrary queries, but would turn a one-shot stream into write-heavy persistence, add cleanup and disk-capacity failure modes, and likely jeopardize the 30-second target.

### Rejected: service or observability stack

GoAccess remains a good broader interactive alternative; Elastic/Logstash and an HTTP service solve retention, distributed search, and dashboards that this product explicitly does not need. Kubernetes and cloud deployment are outside scope.

The user pre-approved the chosen architecture; no further variant selection is required.

## Component Boundaries

| Path | Responsibility | Must not do |
|---|---|---|
| `src/nginx_log_top/cli.py` | Click command, option validation, resource lifecycle, exit mapping | Parse log syntax or format report rows |
| `src/nginx_log_top/parser.py` | Compile grammar and turn one line into `AccessRecord` | Store records or print diagnostics |
| `src/nginx_log_top/models.py` | Dataclasses for records, ranked items, hours, summary | Perform I/O |
| `src/nginx_log_top/aggregate.py` | Update counters/set and finalize deterministic top-10 results | Know terminal/JSON/CSV presentation |
| `src/nginx_log_top/renderers/text.py` | Rich terminal tables and summary | Change metric values |
| `src/nginx_log_top/renderers/json.py` | Stable JSON schema v1 | Emit color or diagnostics |
| `src/nginx_log_top/renderers/csv.py` | Stable long-form CSV rows | Emit color or diagnostics |
| `src/nginx_log_top/errors.py` | Typed domain failures and exit-code constants | Catch unexpected programming errors silently |

## Data Model

There is no database and therefore no database tables, migrations, indexes, or stored records. These in-memory dataclasses are the complete data model:

| Dataclass | Fields and types | Constraints |
|---|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `method: str`, `url: str`, `status: int`, `user_agent: str` | status 100–599; timestamp timezone-aware; URL retains nginx request target |
| `RankedCount` | `key: str`, `count: int` | count > 0; final ordering count desc/key asc |
| `HourlyBucket` | `hour: int`, `count: int`, `percentage: float` | hour 0–23; percentage calculated from valid requests |
| `AnalysisResult` | `total_lines: int`, `total_valid_requests: int`, `malformed_lines: int`, `top_ips: tuple[RankedCount, ...]`, `top_error_urls: tuple[RankedCount, ...]`, `hourly: tuple[HourlyBucket, ...]`, `unique_user_agents: int`, `unique_user_agent_share: float` | totals nonnegative; ranked tuples length <= 10 |

Runtime aggregation uses `Counter[str]` for IPs and error URLs, `list[int]` of length 24 for hours, and `set[str]` for exact User-Agents. No access record is retained after its counters are updated.

## Metric Semantics

- **Top IPs:** count every valid request by normalized client IP; return at most 10.
- **Top error URLs:** count request targets only where `400 <= status <= 599`; return at most 10. Query strings remain part of the target in MVP.
- **Hourly distribution:** emit all 24 local hours from each parsed timestamp offset. Each percentage is `100 × hourly_request_count / total_valid_requests`; for zero valid requests all hourly percentages are `0.0`.
- **Unique User-Agent share:** `100 × unique_user_agent_count / total_valid_requests`; repeated empty/`-` User-Agent values form one value. The metric is a share of distinct agents relative to valid requests, not a claim about distinct people.
- Percentages are serialized as numbers rounded to two decimal places for presentation. Counts remain authoritative if rounded percentages do not sum to exactly 100.

## Parsing Contract

MVP input is nginx's conventional combined format:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

The parser accepts IPv4/IPv6 textual client addresses, nginx timestamps with numeric offsets, quoted request/referer/User-Agent fields including supported escapes, and `-` placeholders. It extracts the method and request target from the quoted request. Lines are decoded as UTF-8 with replacement for invalid byte sequences so byte corruption cannot crash the process.

Lenient mode skips malformed lines and reports their count. `--strict` stops at the first malformed line with its 1-based line number. A file containing no valid requests is a successful empty analysis in lenient mode.

## Streaming and Resource Bounds

- Open regular files in buffered binary mode; wrap stdin without reading it eagerly.
- Iterate line by line and update a single `AggregateState`.
- Use `heapq.nsmallest`/equivalent bounded selection or sort unique counter entries only at finalization; never sort raw requests.
- Default `--max-unique-user-agents` is 1,000,000. Attempting to add a distinct value beyond the limit stops with exit code 4. No approximate answer is emitted.
- The IP and error-URL counters are also cardinality-dependent. Their observed peak memory is part of the 1 GB benchmark; a future bounded/approximate mode requires a new PRD decision.
- Check downstream write errors and handle a closed pipe quietly according to the output-error contract.

## CLI Interface

### Command

```text
nginx-log-top [OPTIONS] [INPUT]
```

`INPUT` is a path to one nginx access-log file. If omitted or `-`, bytes are read from standard input. Exactly one input stream is processed per invocation.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit JSON schema v1 to stdout; mutually exclusive with `--csv` |
| `--csv` | false | Emit RFC 4180 long-form CSV to stdout; mutually exclusive with `--json` |
| `--strict/--no-strict` | `--no-strict` | Stop on first malformed record or skip/count malformed records |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive ceiling for exact User-Agent cardinality |
| `--color/--no-color` | auto | Applies only to text; auto enables color for a TTY |
| `--version` | — | Print version and exit 0 |
| `--help` | — | Print usage and exit 0 |

The report size is fixed at top 10 for MVP. A configurable top-N is P1 and must not alter schema keys.

### Outputs

- **Text:** four Rich sections in order: Top client IPs, Top error URLs, Hourly request distribution, User-Agent diversity; then totals and malformed-line warning.
- **JSON:** one UTF-8 object with `schema_version`, input totals, `top_ips`, `top_error_urls`, 24 `hourly_distribution` objects, and `user_agent_summary`.
- **CSV:** header `report,key,count,percentage`; rows use report values `top_ip`, `top_error_url`, `hourly`, and `user_agent_summary`. Non-applicable cells are empty.
- stdout contains only the selected report. Diagnostics go to stderr. JSON/CSV never contain ANSI escapes.

### Exit Codes

| Code | Meaning |
|---:|---|
| 0 | Successful analysis, including an empty valid dataset in lenient mode |
| 1 | Input I/O failure: missing/unreadable file or read error |
| 2 | CLI usage error: invalid/mutually exclusive options or invalid numeric limit |
| 3 | Data/output failure: strict parse failure, report serialization/write failure, or unsupported record content |
| 4 | Unique-cardinality exhaustion: exact User-Agent set would exceed the configured ceiling |

## Output Schemas

JSON schema v1 uses this shape at the field level (example values are descriptive, not placeholders to implement literally):

| Field | Type |
|---|---|
| `schema_version` | string, `"1"` |
| `total_lines`, `total_valid_requests`, `malformed_lines` | nonnegative integer |
| `top_ips[]`, `top_error_urls[]` | object `{key: string, count: integer}` |
| `hourly_distribution[]` | object `{hour: integer, count: integer, percentage: number}` |
| `user_agent_summary` | object `{unique_count: integer, percentage: number}` |

CSV is normalized because the four reports have different dimensions. Consumers select rows using `report`, interpret `key` as an IP, URL, hour (`00`–`23`), or `unique`, and read only relevant numeric columns.

## Authentication and Trust Boundary

There is no authentication because there are no users, accounts, network listeners, remote calls, or protected shared resources. OS file permissions are the access-control boundary. The tool treats every log byte, path, request target, and User-Agent as untrusted data: it never executes input, interpolates it into a shell command, follows URLs, or renders raw Rich markup. Terminal output escapes or sanitizes control characters.

## Configuration and Environment

There are no required environment variables or `.env` file. Locale and terminal capabilities may affect Rich's color detection but never JSON/CSV values. `NO_COLOR`, when present, disables automatic color in conventional fashion; explicit `--color`/`--no-color` takes precedence.

## Deployment and Packaging

The deployment target is a local Python 3.11 environment on Linux or macOS, installed from a wheel through pip (Windows is supported where stdin and UTF-8 behavior pass CI). `pyproject.toml` declares the `nginx-log-top` console script. No Docker image, Compose file, server process, cloud resource, Kubernetes manifest, or daemon lifecycle exists.

Release verification builds both sdist and wheel, installs the wheel in a clean virtual environment, invokes `--help`, analyzes a fixture through a file and stdin, and checks all three formats.

## Performance Verification

`scripts/generate_benchmark_log.py` will deterministically generate a representative 1 GB file with controlled error and User-Agent cardinalities. `tests/performance/test_one_gb.py` or a documented benchmark command records Python version, CPU, storage, wall time, and peak RSS. The acceptance gate is under 30 seconds, with correctness compared to known generated totals. Performance tests are opt-in locally but must run before release.

## Architecture Decision Record

### ADR-001: stateless CLI pipeline

- **Status:** Accepted; product decision pre-approved.
- **Decision:** Use a single process, no database, no HTTP API, and exact one-pass aggregation.
- **Consequences:** Simple local installation and deterministic runs; memory varies with distinct aggregate keys; no historical queries.

### ADR-002: exact cardinality with a fail-closed ceiling

- **Status:** Accepted.
- **Decision:** Track exact User-Agent strings until the configured ceiling; exit 4 before publishing an inexact result.
- **Consequences:** The metric is auditable. Highly diverse/adversarial input fails explicitly instead of silently becoming approximate.

### ADR-003: one canonical result, three renderers

- **Status:** Accepted.
- **Decision:** Renderers consume the same finalized dataclasses.
- **Consequences:** Output modes cannot diverge in computation, and golden schema tests can focus on presentation.

No adversarial review is recorded here; it is intentionally delegated to the external benchmark harness in a separate session.
