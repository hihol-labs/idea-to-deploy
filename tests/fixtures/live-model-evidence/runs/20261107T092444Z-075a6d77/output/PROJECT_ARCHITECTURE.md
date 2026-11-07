# Project Architecture: Nginx Lens

## Context and Decision

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

The input is a local finite file or stdin stream, the result is one report, and each invocation starts fresh. Persistence would add schema, cleanup, and privacy costs without supporting a requirement. An HTTP interface would add lifecycle, ports, and access-control work to a tool whose users already operate shell pipelines. In-memory counters last only until process exit; stateless does not mean constant-memory aggregation.

Python 3.11, Click, Rich, and dataclasses are approved. A single synchronous process is the obvious architecture for a solo weekend CLI; no architecture-choice pause is required.

## Architecture Variants and ADR

Chosen: one process with buffered line iteration, pure parser, exact counters, and separate renderers. Pros: simple install and deterministic behavior. Trade-offs: CPU-bound parsing and memory proportional to distinct keys.

Rejected alternatives: worker processes introduce serialization, counter merging, and extra memory before measurements justify them; persistent indexing introduces a database contrary to the brief; approximate heavy-hitter sketches reduce memory but violate exact output semantics. These are decision records, not an adversarial review. Devil's Advocate review is reserved for the external fresh session; no verdict exists here.

## Components and Data Flow

`Click arguments → bounded binary line reader → combined parser → Record → accumulator → Report → text/JSON/CSV → stdout`

Diagnostics go only to stderr. The process consumes input to EOF before writing a successful report. It never stores the entire log or a list of parsed records.

| Planned file | Responsibility |
|---|---|
| `src/nginx_lens/cli.py` | Click command, error mapping, stream ownership |
| `src/nginx_lens/reader.py` | Bounded binary line reads, UTF-8 decoding |
| `src/nginx_lens/parser.py` | Anchored combined-format parsing and validation |
| `src/nginx_lens/models.py` | Record, Report, RankedCount dataclasses |
| `src/nginx_lens/aggregate.py` | Exact counters, cardinality guard, ranking |
| `src/nginx_lens/renderers.py` | Rich, JSON, CSV serializers |
| `src/nginx_lens/__main__.py` | Module invocation |
| `tests/`, `bench/` | Synthetic fixtures, unit/integration tests, benchmark tooling |

## Input and Parsing Contract

MVP accepts nginx combined format: remote address, ident, user, bracketed timestamp with numeric timezone, quoted request, status, bytes, quoted referrer, quoted User-Agent. Handle escaped quotes and backslashes in quoted fields. Validate IPv4/IPv6 addresses, timezone-aware timestamps, three-digit status 100–599, and nonnegative bytes or `-`. Request is `METHOD target HTTP/version` or `-`; a missing request is valid but has no URL to rank. User-Agent `-` is valid but excluded from the distinct-UA numerator. Empty UA is treated as missing too.

UTF-8 input is decoded strictly per physical line. Invalid UTF-8, invalid fields, truncated records, and blank lines count as malformed. Lines over 64 KiB including newline are discarded once, draining to the next newline in bounded chunks; no unbounded `readline()` allocation. A valid last line without newline is accepted. Remote address is the logged IP, without forwarded-header inference. File input is read to EOF; stdin waits for EOF. `tail -f` can feed stdin, but there is no live report or built-in follow mode. gzip/custom formats are outside MVP.

## In-Memory Data Model

There are no database tables, indexes, or migrations. These typed records replace database/API template sections appropriately:

| Record | Fields and constraints |
|---|---|
| `Record` | `ip: str` canonical IP; `url: str | None`; `status: int` 100–599; `hour: int` 0–23; `user_agent: str | None` |
| `Accumulator` | `total_valid_requests: int`; `malformed_lines: int`; `ip_counts: dict[str,int]`; `error_url_counts: dict[str,int]`; `hour_counts: list[int]` length 24; `unique_user_agents: set[str]`; `unique_keys: int` |
| `RankedCount` | `value: str`; `count: int` positive |
| `Report` | schema version, totals, missing-UA count, unique-UA count/share, ranked lists, 24 hourly entries |

URL keys retain raw request targets including query strings; no URL decoding, path collapsing, or query stripping. UA keys are case-sensitive parsed field values after nginx quote/backslash unescaping. Unknown escape sequences remain literal. IP keys use canonical address spelling.

## Metric Semantics and Capacity

- Top IPs: count every valid record; sort by count descending then canonical IP string ascending; emit at most 10.
- Error URLs: count statuses 400–599 together, excluding missing URL; sort count descending then raw target ascending; emit at most 10.
- Hourly distribution: group by hour in each record's logged offset, across dates and offsets; this is local logged hour-of-day, not UTC or chronological buckets. Emit hours 0–23 including zeros. Percentage formula: `100 × hourly_request_count / total_valid_requests`.
- Unique-UA share: `100 × distinct_nonmissing_user_agents / total_valid_requests`. Repeated UAs count once in the numerator; valid requests with missing UA remain in the denominator. This is distinctness per request, not the percentage of requests with singleton UAs.
- Empty input produces all-zero metrics, empty leaders, and code 0. Nonempty input with zero valid records produces code 3 and no report. Mixed malformed/valid input produces a report plus a stderr warning unless strict mode is on. Percentages use two decimal places with round-half-even for serialization/presentation; hourly rounded values need not sum exactly to 100.
- Exactness is bounded: `unique_keys = len(ip_counts) + len(error_url_counts) + len(unique_user_agents)`. The same text in different collections counts separately. Default limit 100,000; configurable positive integer. Check all new keys for a record before mutating counters. Exceeding the limit yields code 4 and no successful report; never silently truncate or sample.
- Complexity: O(input bytes + U + V) using bounded top-10 selection, with O(U + V + A) memory for distinct IPs, error URLs, and UAs. No constant-memory claim. Worst-case key length also matters; the line-size cap and cardinality guard bound growth but do not guarantee 512 MiB on every admissible input.

Capacity goal: 1,000,000,000 bytes in <30 seconds end-to-end on a recorded laptop with Python 3.11, local SSD, 100,000 or fewer shared keys, normal combined records averaging 200–500 bytes, no malformed lines, and JSON output to a local sink. Measure at least three warm-cache runs and record every duration, median, hardware, OS, peak RSS, and fixture parameters. Target RSS <512 MiB on this fixture. Also report a cold-cache run separately when practical. This is an unmeasured goal, not a guarantee. Cardinality exhaustion is an expected controlled failure, independent of byte size.

## CLI Interface

Command: `nginx-lens [OPTIONS] [INPUT]`. Also available as `python -m nginx_lens`. `INPUT` is one local uncompressed file; omitted or `-` means stdin. No network inputs or implicit directory traversal.

| Option | Contract |
|---|---|
| `--json` | Emit one UTF-8 JSON document, newline terminated |
| `--csv` | Emit one UTF-8 CSV table, header included |
| `--strict` | Abort on first malformed line with code 3 |
| `--max-unique INTEGER` | Positive shared-key limit, default 100000; overflow code 4 |
| `--color [auto|always|never]` | Text mode only; default auto detects TTY and honors NO_COLOR |
| `--help`, `--version` | Print metadata and exit 0 without consuming input |

`--json` and `--csv` conflict and yield code 2. Explicit `--color` with either export also yields code 2. No environment configuration except `NO_COLOR`; example `NO_COLOR=1`. No `.env` or secrets are required.

Text output includes totals, malformed count, both leader tables, hourly counts/percentages, distinct-UA count and share. Rich interprets no input as markup, escapes control bytes, and never emits ANSI in JSON/CSV. Auto text mode emits no color when redirected.

JSON schema version 1 fields: `schema_version: int`, `total_valid_requests: int`, `malformed_lines: int`, `missing_user_agents: int`, `unique_user_agents: int`, `unique_user_agent_share_pct: number`, `top_ips: [{ip: string, count: int}]`, `top_error_urls: [{url: string, count: int}]`, `hourly_requests: [{hour: int, count: int, percentage: number}]`. Lists have deterministic order; numbers are finite. Example empty report uses zero totals, empty leaders, and 24 zero hourly rows.

CSV uses one long-form table with columns `schema_version,metric,key,count,percentage`. Rows: summary metrics `total_valid_requests`, `malformed_lines`, `missing_user_agents`, `unique_user_agents` (the last carries UA share in percentage); then `top_ips`, `top_error_urls`, `hourly_requests` in that order. Summary keys are empty, leader keys are IP/URL, hourly keys are `00`–`23`; percentages are blank except unique-UA share and hourly rows. Standard CSV quoting preserves commas/newlines/quotes; it is pipeline data, not spreadsheet formula sanitization. Empty reports still include the four summary rows and 24 hourly rows.

| Exit | Meaning | stdout |
|---|---|---|
| 0 | Successful report, including empty input or tolerated malformed lines; help/version success | Report or help/version text |
| 1 | Input/output failure, broken pipe, interruption, or unexpected internal failure | No report before rendering; OS write failure can leave partial bytes |
| 2 | Usage/option error, including nonpositive limit | Empty |
| 3 | Strict parse failure or nonempty stream with no valid records | Empty |
| 4 | unique-cardinality exhaustion | Empty |

Validate options before opening input; process failures occur in encounter order. Reader I/O failures map to 1, not 3. Errors go to stderr with no raw log line or traceback by default. Ctrl-C maps to 1 explicitly rather than Click's default behavior. Successful output starts only after EOF; a failed stdout write cannot be undone, so downstream consumers must check exit status.

Examples: `nginx-lens access.log`; `cat access.log | nginx-lens --json`; `nginx-lens --csv --strict access.log > report.csv`; `nginx-lens --max-unique 200000 access.log`.

## Security, Installation, and Operations

No auth flow exists: the invoking OS user must have file-read permission. No server, cloud, Kubernetes, container, Docker Compose, HTTP endpoints, listening ports, database, or deployment target applies. Distribution is a local wheel installed with pip into a virtual environment. Root permissions are unnecessary. Publishing a package is a separate external action requiring approval.

Logs are untrusted data and may contain personal information. No network calls, telemetry, subprocess evaluation, persistent cache, or copying input to diagnostics. Synthetic test/benchmark data only. Output files are created by the user's shell; permissions and retention belong to the user. Render terminal text safely without changing raw machine-export keys.

Dependencies: runtime Click and Rich; Python dataclasses/collections/json/csv/datetime/ipaddress from standard library. Development tools pytest, pytest-cov, and build. Exact compatible dependency versions will be resolved and recorded during implementation; this planning session installs nothing.

## Verification and Traceability

Use fixture-based parser tests, oracle aggregation tests, Click runner/subprocess exit tests, JSON/CSV round trips, clean-wheel smoke tests, and measured benchmark runs. Boundary cases include ties, IPv6, escaped quotes, malformed UTF-8, oversized lines, empty/all-invalid input, missing UA/request, timezone boundaries, errors 399/400/499/500/599, cardinality exactly at/over limit, and broken pipes.

[PRD.md](PRD.md) owns acceptance criteria; [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) owns priorities; [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) maps files/checks; [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) supplies execution prompts; [CLAUDE.md](CLAUDE.md) tracks status. No runtime or independent-review evidence has been produced by this planning session.
