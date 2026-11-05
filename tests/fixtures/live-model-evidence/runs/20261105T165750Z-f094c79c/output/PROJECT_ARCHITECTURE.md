# Project Architecture: Nginx Lens

## Context and Decision

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Each invocation reads local input, aggregates in memory, writes one report and discards state. A database adds persistence, migrations and cleanup without a cross-run query requirement. An HTTP API adds service lifecycle, exposure and protocol handling without a remote-client requirement. Both constraints preserve the $0 budget and weekend schedule. Stateless means no durable state between runs; exact aggregation still requires bounded in-process state.

The user pre-approved Python 3.11, Click, Rich, dataclasses and a single-process design. Architecture variants are unnecessary under the skill's explicit-stack/obvious-choice exception. No product code is created by this blueprint.

## Components and Data Flow

```text
Click options -> binary file/stdin -> bounded line reader -> combined parser
    -> exact aggregators -> Report dataclass -> text / JSON / CSV -> stdout
                         diagnostics and failures -> stderr
```

| Planned path | Responsibility |
|---|---|
| pyproject.toml | Package nginx-lens, entry point nginx-lens = nginx_lens.cli:main |
| src/nginx_lens/cli.py | Click interface, orchestration, exit-code mapping |
| src/nginx_lens/reader.py | Bounded binary line iteration, UTF-8 decoding, I/O errors |
| src/nginx_lens/parser.py | Explicit combined grammar and record validation |
| src/nginx_lens/models.py | Record, AggregateState, Report dataclasses |
| src/nginx_lens/aggregate.py | Exact counters, deterministic rankings, resource budget |
| src/nginx_lens/render.py | Rich text, JSON and CSV serialization |
| tests/ | Unit fixtures, CLI integration, golden exports and benchmark correctness |
| benchmarks/run.py | Reproducible generated-corpus timing, RSS and environment capture |

## Input Grammar and Models

Only nginx combined access logs are supported: remote address, ident, user, bracketed timestamp with numeric timezone, quoted request, status, byte count, quoted referrer, quoted User-Agent. Parser recognizes escaped quotes/backslashes within quoted fields. Custom formats, compressed files and live follow are outside MVP.

Use IPv4/IPv6 address validation and canonical address spelling. Timestamp must be a valid calendar time with offset. Request must contain method, request-target and HTTP version; accept origin-form targets beginning `/`, normalize URL grouping to the path before `?`, preserve case and percent escapes, and do not decode. Status must be 100–599. Missing UA `-` is valid but excluded from UA statistics; empty quoted UA is also missing. Malformed UTF-8 or records failing grammar/field checks increment invalid count and are skipped. Blank lines are invalid. A missing final newline is accepted. An oversized line is discarded incrementally through its newline and counted invalid once.

| Model | Fields and types |
|---|---|
| Record | ip: str; hour_utc: int (0–23); path: str; status: int; user_agent: str or None |
| AggregateState | valid_requests: int; invalid_lines: int; ua_present_requests: int; ip_counts: dict[str,int]; error_url_counts: dict[str,int]; hourly_counts: list[int] of length 24; unique_uas: set[str] |
| Report | schema_version: int = 1; valid_requests: int; invalid_lines: int; ua_present_requests: int; unique_user_agents: int; unique_user_agent_share_pct: float; top_ips: list[IPRow]; top_error_urls: list[ErrorURLRow]; hourly_distribution: list[HourRow] |

IPRow contains ip: str and request_count: int. ErrorURLRow contains url: str, error_count: int, client_error_count: int, server_error_count: int. HourRow contains hour_utc: int, request_count: int, percentage: float. Counters use Python integers. No raw records, referrers or user names are retained after parsing.

## Metric Semantics

- Top IPs count all valid requests; sort by count descending then canonical IP string ascending; return up to ten.
- Error URLs count statuses 400–599 grouped by normalized path; retain separate 4xx and 5xx counts. Sort by combined count descending then path ascending; return up to ten.
- Hourly distribution combines all dates into 24 UTC hour-of-day buckets after timestamp-offset conversion. Percentage is `100 × hourly_request_count / total_valid_requests`. It is not a date-by-date series. Every hour appears, including zero counts.
- Unique User-Agent share is `100 × distinct_nonmissing_user_agents / ua_present_requests`. Equality is the exact decoded UA string, with no trimming or case folding. All valid statuses count. Report the numerator and denominator alongside the percentage. This measures distinctness, not browser market share.
- Zero denominators produce 0.0, never NaN/null or division errors. Percentages round to six decimal places for machine formats and two for terminal display; sums may differ slightly from 100 due to rounding.

## CLI Interface

### Commands, Options and Inputs

Single command: `nginx-lens [OPTIONS] [INPUT]`. INPUT is one plain UTF-8 combined-log file; omitted or `-` means stdin. Read to EOF; no daemon or tailing. Multiple files are composed upstream using stdin. No application configuration or required environment variables exist. Standard terminal conventions such as `NO_COLOR` affect presentation only; no secrets are accepted.

| Option | Contract |
|---|---|
| --json | One schema-versioned JSON document on stdout |
| --csv | One rectangular CSV report on stdout; mutually exclusive with --json |
| --no-color | Disable Rich color; redirected output has no ANSI escapes by default |
| --max-unique INTEGER | Positive total entry limit across IP keys, error-path keys and UA set; default 1000000 |
| --max-line-bytes INTEGER | Positive byte limit excluding newline; default 65536 |
| --help | Usage on stdout, exit 0 |
| --version | Package version on stdout, exit 0 |

Examples: `nginx-lens access.log`, `cat access.log | nginx-lens --json`, `nginx-lens --csv -`, `nginx-lens --max-unique 100 access.log`.

### Outputs

Text output includes totals, malformed-line count, top IP table, error-path table, 24 hourly rows and unique-UA share with numerator/denominator. Escape untrusted Rich markup and control characters before terminal rendering. JSON strings preserve data through proper JSON escaping. CSV uses standard quoting and LF line endings; machine exports are data, so spreadsheet consumers must treat values as text.

JSON fields are the Report fields above. Top arrays are empty when no matching requests exist; hourly_distribution always has 24 rows. No timestamps or input filenames are added to machine output, keeping identical input deterministic. Diagnostics go only to stderr, never mixed into exports.

CSV header is exactly `section,key,count,percentage,client_errors,server_errors`. Rows: summary keys `valid_requests`, `invalid_lines`, `ua_present_requests`, `unique_user_agents` with count; `unique_user_agent_share_pct` with percentage; then `top_ips` keyed by IP with count; `top_error_urls` keyed by path with count and client/server fields; then `hourly_distribution` keyed by zero-padded UTC hour with count and percentage. Inapplicable cells are empty. Ordering matches JSON rankings and ascending hourly buckets.

Report only after successful full processing, including empty/all-invalid inputs; warnings on skipped invalid lines accompany a successful report. Processing failures emit no aggregate report. Output stream failures may leave a partial report and return 1; atomic stdout delivery cannot be guaranteed.

### Exit Codes

The complete contract is **0/1/2/3/4**:

| Code | Meaning |
|---|---|
| 0 | Successful report, including empty input, all-invalid input or skipped malformed records; help/version also succeed |
| 1 | File/read/write error, broken pipe or unexpected runtime failure; concise stderr diagnostic |
| 2 | Invalid CLI usage, conflicting output flags or invalid option bounds |
| 3 | Interrupted processing (SIGINT/SIGTERM); no final processing report |
| 4 | unique-cardinality exhaustion; no approximate/truncated report |

Click's default interrupt behavior must be explicitly mapped to 3. Test signal and broken-pipe behavior at the process boundary.

## Resource and Performance Design

Each new IP key, new error-path key and new UA consumes one entry from a shared budget; an identical string used in different collections consumes an entry in each. Check the number of new entries needed by a record before mutating any counters; exceed the budget -> code 4. Ranking sorts bounded counters only at EOF. Memory is O(distinct IPs + error paths + UAs + max-line-bytes), not O(file bytes). Exact distinct counting is not constant-memory. Catch resource failures as code 1 when not an intentional cardinality limit; never mislabel them code 4.

Default cardinality and line limits bound retained data, though Python object overhead varies; they do not promise a universal RSS ceiling. Do not retain an unbounded rejected line. Counters and parsing remain in one process; avoid read-all, per-record Rich calls and multiprocessing serialization.

Target: a decimal 1 GB (1,000,000,000-byte) valid combined-log file, under 30 seconds wall time on a declared laptop. Benchmark must record CPU, RAM, OS, Python/dependency versions, corpus byte/line/cardinality counts, filesystem/cache conditions, all run times and peak RSS. Generate a deterministic corpus with varied status, path, IP, offset and UA, within default limits; use a small reference oracle to check expected summaries. Run three timed subprocesses per output format including parsing, EOF ranking and rendering; require each below 30 seconds. Record cold/warm cache conditions rather than silently claiming cold performance. Separately test cardinality exhaustion with a deliberately small budget. The target is unverified until implementation measurements exist; if it fails, profile and revise the plan rather than inventing results.

## Database, API, Auth, Environment and Deployment

Database tables, indexes and migrations: none. HTTP endpoints, request/response handlers and API auth: none. Access uses existing OS file permissions; no accounts or authentication flow. No application env vars, credentials, Dockerfile, docker-compose, cloud resources or Kubernetes manifests are needed. Distribution is a locally built wheel installed with pip; this session neither publishes nor deploys. Logging is concise stderr diagnostics without dumping full source lines. Reports can contain IP/path/UA-derived information and remain under the operator's file permissions.

## Architecture Decision Record (ADR)

ADR-001: Adopt the pre-approved single-process streaming CLI. Persistence and HTTP services are rejected because neither supports a stated use case. Multiprocessing and approximate sketches are deferred until measured evidence warrants a separate scope decision. Exact counters plus explicit exhaustion preserve trustworthy results at a bounded cardinality.

Review status: adversarial review has not run in this session. The external harness will invoke the real reviewer in a fresh session; no verdict or review artifact is authored here.

See [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md), [PRD.md](PRD.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) and [CLAUDE.md](CLAUDE.md).
