# Project Architecture: nginx-scan

## Context and decision

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

A one-shot report needs only counters for the current invocation, so persistence adds lifecycle, schema and cleanup costs without product value. stdin, file paths, stdout and process exit codes already provide the integration boundary; an HTTP API would require an unwanted server and operations work. State exists only in memory during processing and is discarded on exit. The selected single-process architecture and Python 3.11/Click/Rich/dataclasses stack are pre-approved.

## Architecture selection

The skill's obvious-choice exception applies: a solo weekend CLI with an explicit stack does not need an architecture selection round. A service/database design violates the brief. Multiprocessing adds merging and serialization work; reserve it for a future measured need rather than the MVP. Approximate sketches reduce memory but cannot satisfy the exact metrics chosen here.

## Components and data flow

`Click invocation → binary file/stdin reader → combined parser → accumulator → immutable report → one renderer → stdout`

One process, one pass, no per-record retention. Rich handles terminal reports only. Diagnostics go to stderr. No background worker, network call or telemetry.

| Planned file | Responsibility |
|---|---|
| pyproject.toml | Python >=3.11, dependencies Click/Rich, console entry nginx-scan |
| src/nginx_scan/cli.py | Options, pipeline orchestration, exit mapping |
| src/nginx_scan/reader.py | Buffered binary lines with size checks |
| src/nginx_scan/parser.py | Anchored nginx combined grammar and timestamp validation |
| src/nginx_scan/models.py | dataclasses: LogRecord, Report, RankedCount |
| src/nginx_scan/aggregate.py | Exact counters, caps and report construction |
| src/nginx_scan/render.py | Terminal, JSON and CSV adapters |
| tests/ | Unit, fixture, CLI and package tests |
| benchmarks/ | Synthetic fixture generator and timed runner |

## Input grammar and data model

Support standard nginx combined logs: remote address, ident, user, bracketed timestamp with numeric offset, quoted request, three-digit status, bytes or `-`, quoted referrer, quoted User-Agent. Parse quoted fields with nginx backslash escaping; reject truncated/extra fields, invalid escapes, invalid timestamps/offsets, status outside 100–599, invalid IPs, and requests lacking method/target/protocol. Accept IPv4 and IPv6; canonicalize IP spelling with the standard library. Common-only and custom log formats are unsupported. A request field of `-` is malformed because it has no URL.

Read UTF-8 strictly; invalid byte sequences make that line malformed. A missing final newline is valid. Unescape quoted data before metric extraction. An absent User-Agent represented by `-` is unknown and excluded from the distinct set. No DNS lookup. Preserve request-target exactly after unescaping, including query strings; no URL decoding, query removal or path normalization. Do not store method, referrer, user or bytes beyond parsing validation.

| Dataclass | Fields and types | Constraints |
|---|---|---|
| LogRecord | ip: str, target: str, status: int, hour_utc: int, user_agent: str or None | Validated; hour 0–23; transient per line |
| RankedCount | key: str, count: int | Positive integer; key is IP or request-target |
| Report | schema_version: int; total_lines, total_valid_requests, malformed_lines, unique_user_agents: int; unique_user_agent_share_pct: float; top_ips, top_error_urls: list[RankedCount]; hourly: list[HourlyBucket] | Version 1; report only after successful EOF |
| HourlyBucket | hour_utc: int, request_count: int, percentage: float | Exactly 24 buckets in ascending order |

No database tables, fields, indexes or migrations exist: these are in-memory models, not persistent entities.

## Metric semantics

- Top IPs: count every valid request, order descending count then ascending canonical IP string, retain at most 10.
- Top error URLs: count requests with status 400–599 together per exact target; order descending count then ascending target, retain at most 10. Successful requests never contribute to this counter.
- Hourly request distribution: normalize each timestamp to UTC and collapse dates into 24 hour-of-day buckets. Percentage is `100 × hourly_request_count / total_valid_requests`.
- Unique User-Agent share: `100 × distinct_known_user_agents / total_valid_requests`. Compare unescaped known User-Agent strings case-sensitively; this is a diversity ratio, not a bot or unique-user estimate. Unknown User-Agents still contribute to total valid requests.
- Zero denominator: percentages are 0.0; empty input is a successful empty report with 24 zero buckets. All-malformed nonempty input is also a successful empty report with a warning and malformed count.
- Keep integer counts exact; round percentages to six decimal places in JSON/CSV and two in terminal output. Rounded hourly totals can differ slightly from 100.

## Resource bounds and performance

O(N) parsing/aggregation plus O(K log 10) top-k selection, with O(Uip + Uerror_target + Uua) dictionary/set memory. Streaming does not imply constant memory for exact unique counts. The total distinct-entry budget across IP keys, error-target keys and known User-Agent values defaults to 250,000; `--max-unique` overrides it. Charge one slot per new key per structure, even when strings match across structures. Check all newly required slots before mutating a record's aggregates; exceeding the limit aborts with exit 4 and no report. Never evict silently or report approximate success. Catch MemoryError as code 4 as well.

Read at most 65,537 bytes to detect lines exceeding the fixed 65,536-byte limit, excluding the newline. Drain an oversized line in bounded chunks, count it malformed once, then resume. Bound error messages; never echo raw lines. Input length bounds key size, while the cardinality budget bounds key count; this is not a promise of a specific RSS ceiling.

Performance target: process 1,000,000,000 bytes of an uncompressed combined log, below the default cardinality cap, in <30 seconds end-to-end on a declared laptop. Timing starts at command invocation and ends after report output; include parsing, ranking and rendering. Record CPU, RAM, OS, Python version, byte/line counts, cardinalities, wall time and peak RSS. Run three trials, disclose cache conditions and require every trial <30 seconds. Separate adversarial cap tests from throughput tests. No benchmark has run yet; profile before claiming feasibility.

## CLI Interface

### Commands and inputs

`nginx-scan [OPTIONS] [INPUT]` is the only command; no subcommands. INPUT is one local uncompressed file or `-` for stdin, default `-`. Read to EOF once; do not follow/rotate logs. No automatic directory traversal or gzip support in MVP. Example: `cat access.log | nginx-scan --json`.

| Option | Contract |
|---|---|
| --json | JSON report on stdout; mutually exclusive with --csv |
| --csv | One CSV document on stdout |
| --no-color | Disable terminal ANSI; structured outputs never have ANSI |
| --max-unique INTEGER | Positive total distinct-entry cap, default 250000 |
| --help | Usage, stdout, exit 0 without opening input |
| --version | Installed version, stdout, exit 0 |

Default terminal output uses Rich tables, color only on a TTY; redirected terminal output is plain text. Honor NO_COLOR. No product-specific environment variables or .env file; NO_COLOR presence disables color. Pipeline examples use shell redirection to save reports; no output-path option exists.

### Output schema

JSON is one UTF-8 object ending in a newline, with exactly the Report fields above. RankedCount serializes as `{"key":"/missing","count":2}`; hourly elements contain `hour_utc`, `request_count`, `percentage`. Sort JSON keys for deterministic output. Include schema_version=1. All formats expose total_lines, total_valid_requests, malformed_lines, unique_user_agents and unique_user_agent_share_pct plus the four metrics. A malformed-line warning is a bounded stderr summary, never mixed into stdout.

CSV uses the standard-library csv writer, UTF-8, comma delimiter, RFC-style quoting, header `section,key,count,percentage`. Emit summary rows with keys total_lines, total_valid_requests, malformed_lines, unique_user_agents and unique_user_agent_share_pct; put the share in percentage and other summary values in count. Then top_ips and top_error_urls rows with rank order; then 24 hourly rows, keys `00` through `23`. Unused cells are empty. Counts are decimal integers; percentages use six decimals and a dot. Treat fields as literal data; spreadsheets may interpret untrusted URL cells as formulas, so documentation must recommend importing cells as text rather than altering identifiers.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Successful complete report, including empty/all-malformed input; help/version |
| 1 | Unexpected internal failure or interruption; concise stderr diagnostic |
| 2 | Invalid arguments, conflicting output flags or nonpositive cap |
| 3 | Input/output failure: unreadable path, read failure, stdout failure/broken pipe |
| 4 | unique-cardinality exhaustion: distinct-entry budget exceeded or allocation failure |

Malformed lines are skipped and counted, not fatal. Argument validation precedes input opening. On a fatal parse-stage read/resource error emit no report. Render only after EOF and successful aggregation. A write failure can leave partial stdout; exit 3 means callers must discard it. Catch KeyboardInterrupt and map it to 1. Do not leak tracebacks or raw log contents on expected failures.

## Auth, security and privacy

Authentication is absent: the operating-system user reads files they already have permission to read. There are no tokens, sessions, roles or remote identities. Flow: `OS permissions → local reader → in-memory counts → caller-controlled stdout`. IPs, URLs and User-Agents can contain sensitive data; no network egress or persistent cache. Render untrusted strings as literal Rich Text, disable markup interpretation, and escape terminal control characters. JSON escaping and CSV quoting preserve data; terminal display escaping never changes aggregation keys.

## Packaging and deployment

Install locally through pip from a source checkout or wheel. No server, Docker image, docker-compose.yml, cloud, Kubernetes or staging environment is required. setuptools builds the package with console entry `nginx-scan = nginx_scan.cli:main`; supported development target is Python 3.11 on a local laptop, with portability checked on Linux/macOS when available. Click and Rich are runtime dependencies; pytest, pytest-cov, build and ruff are development tools. Select compatible versions and record them during implementation rather than inventing a tested lockfile now. Public registry upload is a separately approved external action.

## Architecture Decision Record (ADR)

Chosen by the approved brief: single-process exact counters, combined-only parser, UTC buckets, explicit cardinality failure, no persistence or service. Alternatives considered: approximate counting (rejected for exactness), disk spill/database (violates stateless/no-database scope), process pool (unnecessary unmeasured complexity). The throughput target is an unverified acceptance target, not evidence.

Adversarial review is reserved for a fresh external-harness session. No adversarial or independent reviewer ran in this session; no verdict is asserted here.

Requirements: [PRD.md](PRD.md). Delivery sequence: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Rationale: [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md). Execution: [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md).
