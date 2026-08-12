# Project Architecture: nginx-log-report

## Architectural Goals and Constraints

- Python 3.11, Click, Rich, and dataclasses; installable with pip.
- Local, single-process, one-pass analysis of a finite file or stdin stream.
- Target: a representative 1 GB nginx log in under 30 seconds on a documented laptop.
- Deterministic summaries and output schemas suitable for automation.
- Exact decision: **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

The database constraint is correct because reports are derived completely from the current input, persistence would add cost and privacy/operations burden, and no cross-run query is required. The HTTP API constraint is correct because the target user is already at a shell, file/stdin composition is the required integration boundary, and a listening service would introduce lifecycle, security, authentication, and deployment concerns without adding MVP value.

## Architecture Variants

The product decisions pre-approve Variant A; these alternatives document the decision rather than reopening it.

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** one Python process parses each line, updates aggregate state, and renders once at end-of-input.
- **Pros:** simplest delivery, minimal I/O, deterministic state, easy pip install, no IPC.
- **Cons:** CPU work is limited to one core; exact unique-UA storage is cardinality-dependent.
- **Best for:** local finite nginx logs and a one-weekend MVP.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunk analysis

- **Approach:** split seekable files, parse chunks in workers, and merge partial aggregates.
- **Pros:** can use multiple cores.
- **Cons:** cannot naturally support stdin, complicates line boundaries and exact set merging, raises memory, and exceeds the approved architecture.
- **Best for:** later optimization only if measurement proves the single process insufficient.
- **Estimated complexity:** Medium.

### Variant C: External analytics pipeline

- **Approach:** ingest into Logstash/Elastic or another persistent service.
- **Pros:** historical queries and dashboards.
- **Cons:** violates local/stateless/$0 constraints and adds servers, storage, auth, and operations.
- **Best for:** organizational observability platforms, not this product.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the workload is sequential text ingestion, the output requires only compact counters plus one guarded exact set, and the user explicitly approved a local stateless process. Variant B is allowed only as a future evidence-driven architectural change; Variant C is out of scope.

## System Context

```text
nginx log file or stdin
          |
          v
  [Click CLI boundary]
          |
          v
 [stream opener] -> [line parser] -> [aggregator] -> [result snapshot]
                                                    /       |       \
                                             Rich text    JSON      CSV
                                                 stdout  stdout    stdout

Diagnostics ------------------------------------------------------> stderr
Process result ---------------------------------------------------> exit code
```

There are no network listeners, external integrations, background workers, persistent stores, or telemetry calls.

## CLI Interface

### Command

```text
nginx-log-report [OPTIONS] [INPUT]
```

`INPUT` is one UTF-8 nginx access-log path or `-` for stdin. When omitted, it defaults to `-`. The command consumes input once and exits at EOF; it does not follow a growing file in MVP.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit the versioned JSON object; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit long-form RFC 4180 CSV; mutually exclusive with `--json` |
| `--format` | `combined\|common`, `combined` | Select the supported nginx grammar |
| `--strict/--no-strict` | flag, `--no-strict` | Strict mode exits `3` on the first malformed line; otherwise malformed lines are counted and skipped |
| `--max-unique-user-agents` | integer, `1000000` | Maximum distinct normalized User-Agent strings retained; must be ≥ 1 |
| `--no-color` | flag, false | Disable color in Rich output; structured formats never use ANSI |
| `--version` | flag | Print version and exit `0` |
| `--help` | flag | Print Click help and exit `0` |

### Inputs

- Combined format: `$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"`.
- Common format: `$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent`; it records User-Agent as unavailable and therefore cannot produce a meaningful unique-UA share. For Common input, the JSON value is `null`, the CSV percentage field is empty, and terminal output says `N/A`.
- Blank lines and syntactically malformed lines are invalid. In lenient mode they increment `invalid_line_count` and do not contribute to any denominator.
- Timestamps are parsed from nginx's numeric-offset form. Hour buckets are the `00`–`23` hour as written in each record's local timestamp; records with different offsets are not normalized.
- Request targets are taken from the request line, without URL decoding. If the request field is `-` or cannot yield a method and target, the line is malformed.
- Status is an integer from 100 through 599. Only 400–599 contributes to error-URL ranking.
- Input is decoded as UTF-8 with invalid byte sequences treated as malformed input, not silently replaced.

### Outputs

All rankings contain at most 10 entries and sort by count descending, then key ascending for deterministic ties.

- **Terminal (default):** Rich headings/tables for top IPs, error URLs, 24 hourly percentages, and unique-UA share, followed by valid/invalid counts. Color is enabled only when appropriate and not disabled.
- **JSON:** a single object with `schema_version`, `input`, `total_lines`, `total_valid_requests`, `invalid_line_count`, `top_ips`, `top_error_urls`, `hourly_request_distribution`, and `unique_user_agent_share_percent`. Ranked entries contain `value` and `count`; all 24 zero-padded hour keys are present.
- **CSV:** header `section,rank,key,count,percentage`; ranking rows use `section=top_ip|top_error_url`, hourly rows use `section=hourly_request_distribution`, and the summary row uses `section=unique_user_agent_share`. Non-applicable cells are empty.
- Machine-readable data goes only to stdout. Warnings and errors go only to stderr. JSON/CSV output contains no ANSI escape codes or explanatory prose.

Hourly request distribution is a percentage for each hour, calculated exactly as `100 × hourly_request_count / total_valid_requests`. If there are no valid requests, the command exits `3` and emits no report. Percentages are calculated with full precision and rendered to two decimal places in terminal/CSV; JSON numbers are rounded to six decimal places.

For Combined input, unique User-Agent share means `100 × unique_normalized_user_agent_count / total_valid_requests`. Leading/trailing whitespace is removed; case and internal bytes otherwise remain distinct; `-` is normalized to the single value `<missing>`. This metric is exact, not probabilistic.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Report or help/version completed successfully; lenient mode may have skipped malformed lines |
| `1` | I/O or unexpected runtime failure, including unreadable input or broken output not caused by normal pipe closure |
| `2` | Click usage error: invalid option/value, conflicting formats, or invalid arguments |
| `3` | Input-data failure: strict-mode malformed line, unsupported content, invalid UTF-8, or zero valid requests |
| `4` | Unique-cardinality exhaustion: adding another distinct normalized User-Agent would exceed `--max-unique-user-agents` |

On exit `4`, the command emits a concise stderr diagnostic and no partial report. Normal downstream pipe closure is treated as successful termination (`0`) when distinguishable from other output failures.

## Component Design

| Module | Responsibility | Must not do |
|---|---|---|
| `src/nginx_log_report/cli.py` | Click command, option validation, stream ownership, exception-to-exit mapping | Parse lines or format metric internals |
| `src/nginx_log_report/parser.py` | Compile supported grammar and convert one line into a typed record | Retain records or emit output |
| `src/nginx_log_report/models.py` | Dataclasses and typed result structures | Perform I/O |
| `src/nginx_log_report/aggregate.py` | Update counters/set and freeze final result | Read files or know output format |
| `src/nginx_log_report/renderers/text.py` | Rich terminal presentation | Write diagnostics |
| `src/nginx_log_report/renderers/json.py` | Versioned deterministic JSON | Emit ANSI or stderr text |
| `src/nginx_log_report/renderers/csv.py` | Stable long-form CSV | Use locale-dependent number formatting |
| `src/nginx_log_report/errors.py` | Domain exception classes and exit-code mapping | Catch broad exceptions silently |

### Dataclasses

| Type | Fields |
|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `target: str`, `status: int`, `user_agent: str | None` |
| `RankedCount` | `value: str`, `count: int` |
| `Report` | `total_lines: int`, `total_valid_requests: int`, `invalid_line_count: int`, `top_ips: tuple[RankedCount, ...]`, `top_error_urls: tuple[RankedCount, ...]`, `hourly_counts: tuple[int, ...]`, `unique_user_agent_count: int | None` |
| `RunConfig` | `input_label: str`, `log_format: LogFormat`, `strict: bool`, `max_unique_user_agents: int`, `output_format: OutputFormat`, `color: bool` |

Enums represent log/output formats. Public results are immutable snapshots so renderers cannot alter aggregation state.

## Streaming and Complexity

For each valid record, the aggregator increments `Counter[str]` values for IP and (only for 4xx/5xx) URL, one of 24 integer hour buckets, and the valid-request count. Combined-format UA strings are added to a set after checking the cap. At EOF, `heapq.nsmallest`/equivalent bounded selection produces deterministic top-10 lists without sorting every item where practical.

- Time: O(n + k log 10), where `n` is lines and `k` is distinct ranked keys.
- Memory: O(distinct IPs + distinct error URLs + distinct UAs), independent of raw file size but not of cardinality.
- Safety: distinct UAs are hard-capped. The IP and error-URL maps are not capped because exact top-10 cannot generally be guaranteed with bounded memory; the 1 GB benchmark must include adversarial-cardinality coverage and record peak memory. If that is unsafe, the exactness/product constraint must be revisited rather than hidden behind approximation.

The hot loop performs no Rich calls, JSON construction, per-line logging, database access, or record retention.

## Database, API, Authentication, and Deployment

### Database schema

Not applicable: there are zero database tables, migrations, indexes, or stored records. Adding a database would contradict the stateless decision and is an architectural change requiring a revised PRD.

### HTTP API

Not applicable: there are zero endpoints, request bodies, response bodies, ports, or server processes. The complete public integration contract is under `## CLI Interface`.

### Authentication

Not applicable: the tool reads only resources the invoking OS user can access and inherits filesystem permissions. It stores no identities or credentials and makes no network calls.

### Deployment and packaging

The deployment target is a local Python 3.11 environment. A PEP 517 wheel exposes the `nginx-log-report` console script through `pyproject.toml`; users install it with pip or `pipx`. Docker, Compose, cloud resources, and Kubernetes are deliberately absent. Release verification installs the exact wheel into a clean virtual environment before smoke testing.

### Environment variables

No environment variable is required. Standard `NO_COLOR` disables color, and the explicit `--no-color` option takes precedence. Locale must not change JSON/CSV formatting.

## Reliability, Security, and Observability

- Never include complete raw log lines in default errors; report the 1-based line number and reason to reduce accidental disclosure.
- Treat log contents as untrusted data: no shell execution, URL fetching, or Rich markup interpretation from values.
- Escape or render values as plain text in terminal tables; use standard JSON/CSV encoders.
- Close only streams opened by the program; do not close stdin.
- Catch expected parse, cardinality, and I/O errors at the CLI boundary and preserve their distinct exit codes.
- `--no-strict` prints a bounded summary warning, not one warning per malformed line.
- No telemetry is emitted. Operational evidence consists of exit status, stderr diagnostics, and optional external timing/RSS commands in the benchmark plan.

## Testing Strategy

- Parser fixtures for Combined/Common, IPv4/IPv6, quoted fields, timezone offsets, malformed syntax, invalid UTF-8, and status boundaries.
- Aggregator tests for ranking, tie order, only-4xx/5xx URL inclusion, all 24 hours, percentage formula, UA normalization, and exact cap boundary.
- Golden output tests for terminal-without-color, JSON schema, CSV quoting/newlines, stdout/stderr separation, and locale independence.
- CLI integration tests for file/stdin equivalence and every exit code `0/1/2/3/4`.
- Performance test using a deterministic representative 1 GB fixture, wall clock, and peak RSS on the recorded reference laptop.

## Architecture Decision Record (ADR)

### ADR-001: Stateless single-process CLI

- **Status:** Accepted and pre-approved.
- **Decision:** Use Variant A and the literal constraint **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- **Consequences:** low operational burden and easy composition; no historical queries; cardinality-sensitive exact aggregates require explicit safety policy.

### Debate Summary — Labeled Self-Critique

No independent or adversarial reviewer transport was available. The following is the architect's own adversarial self-critique and must not be represented as independent review.

**Verdict:** APPROVE WITH CONDITIONS

**Strengths acknowledged:** the architecture matches the approved scope, minimizes moving parts, isolates parsing/aggregation/rendering, and exposes deterministic pipeline contracts.

**Challenges raised and resolutions:**

1. Exact UA cardinality can exhaust memory. **Resolution:** add a user-visible hard cap and dedicated exit `4`; prohibit partial reports.
2. “Streaming” can falsely imply bounded memory. **Resolution:** document cardinality-dependent counters explicitly and benchmark high-cardinality data.
3. Common format has no User-Agent. **Resolution:** expose the metric as `N/A`/`null`, never as a misleading zero.
4. Mixed timezone offsets make hourly grouping ambiguous. **Resolution:** bucket by the hour as logged and state that no normalization occurs.
5. A generic CSV table can obscure metric meaning. **Resolution:** define a single long-form schema and test every row type.
6. A strict 30-second target is hardware-sensitive. **Resolution:** bind benchmark claims to a documented fixture, machine, command, and cache state.

**Alternatives considered and rejected:** multiprocessing is deferred until profiling demonstrates need; probabilistic cardinality is rejected because the required metric is exact; persistent analytics stacks are rejected because they violate local/stateless/$0 scope.

The conditions above are incorporated into this document and the acceptance criteria in `PRD.md`.

