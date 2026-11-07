# Project Architecture: Nginx Lens

## Context and Decisions
Python 3.11, Click, Rich and dataclasses; one synchronous process. **no database — stateless streaming processing; no HTTP API — CLI-only tool**

No database is correct because each invocation computes a disposable summary from a finite stream; persistence, queries across runs and migrations offer no MVP value. No HTTP API is correct because local engineers and shell pipelines already provide input/output orchestration; a server would add lifecycle, access control and deployment work without a requirement.

## Components and Data Flow
`file/stdin -> bounded line reader -> combined parser -> LogRecord -> Aggregates -> Report -> terminal/JSON/CSV`

Planned files: `src/nginx_lens/cli.py`, `reader.py`, `parser.py`, `models.py`, `aggregate.py`, `render.py`, `errors.py`; packaging in `pyproject.toml`. Input is consumed once, with no retained raw records or external calls. Rendering starts only after complete successful aggregation.

## Data Model and Metric Semantics
All structures are transient; no database tables, indexes, migrations or on-disk caches.
| Model | Fields and types | Constraints |
|---|---|---|
| LogRecord | ip: str; timestamp: datetime; url: str; status: int; user_agent: str | Validated IP, aware time, status 100–599 |
| Aggregates | total_valid_requests: int; malformed_lines: int; ips: dict[str,int]; error_urls: dict[str,int]; hours: list[int]; user_agents: set[str] | Nonnegative counters; hours length 24; bounded distinct entries |
| Report | schema_version: int; total_valid_requests: int; malformed_lines: int; top_ips: list; top_error_urls: list; hourly_distribution: list; unique_user_agents: int; unique_user_agent_share_pct: float | Schema version 1; exact counts |

Supported input is standard nginx combined format: remote address, ident, remote user, bracketed timestamp with numeric offset, quoted request, numeric status, body bytes, quoted referer and quoted UA. Scanner handles escaped quotes/backslashes and rejects unclosed fields/trailing garbage. UTF-8 decoding is strict per line; invalid bytes count as malformed. Missing request (`-`), invalid IP/date/status, or missing UA are malformed; the combined UA sentinel `-` is a valid literal category. Accept IPv4/IPv6; canonicalize IPs using stdlib `ipaddress`. Parse request as method, request-target, protocol; URL is the exact request-target including query string, with no URL decoding or redaction. Referer, ident, user and body bytes are parsed but not aggregated.

Top IPs count every valid request. Error URLs count only status 400–599 together. Sort counts descending, then keys ascending by Unicode code-point order; return at most ten entries without tie expansion.

Convert timestamps to UTC, then accumulate hour-of-day 00–23 across all dates. Always emit all 24 buckets; each percentage is `100 × hourly_request_count / total_valid_requests`. This is a percentage, not a fraction. Unique UA share is `100 × distinct_user_agent_count / total_valid_requests`; exact UA string equality after combined-field unescaping. Zero denominator yields 0.0 for all percentages. Emit numeric percentages rounded to six decimal places in JSON/CSV and two in terminal; rounding can make totals differ slightly from 100.

## Resource Limits
Streaming avoids storage proportional to total lines, but exact distinct metrics need memory proportional to key cardinality. Default `--max-unique 100000` caps the sum of distinct IP keys, error URL keys and UA values, counting each namespace separately. Before accepting a valid record, compute all newly needed entries; if their sum exceeds the cap, abort atomically with exit 4 and no report. Never silently approximate or evict. Operators can explicitly raise the cap at their own memory cost.

Default `--max-line-bytes 1048576` bounds one physical line including its newline. Read bounded chunks, drain overlong lines without accumulating them, and count each as one malformed line. Memory is O(max-line-bytes + max-unique key storage); byte size of keys is bounded by the line limit, so the cap is not a fixed RSS promise. Benchmark a representative distribution and a hostile high-cardinality fixture separately.

## CLI Interface
Installed executable: `nginx-lens`. One root command; no subcommands.

```text
nginx-lens [OPTIONS] [INPUT]
nginx-lens access.log
cat access.log | nginx-lens --json -
nginx-lens --csv access.log > report.csv
```

| Option/input | Contract |
|---|---|
| INPUT | One regular readable UTF-8 file; omitted or `-` reads stdin until EOF |
| --json | Schema-v1 JSON document, newline terminated |
| --csv | UTF-8 CSV, header and normalized metric rows |
| --no-color | Disable terminal ANSI colors |
| --max-unique INTEGER | Positive integer, default 100000 |
| --max-line-bytes INTEGER | Positive integer, default 1048576 |
| --help / --version | Print help/version and exit 0 without reading input |

`--json` and `--csv` conflict (exit 2). Reject unknown options and invalid option values with exit 2. No hidden environment configuration. Rich colors only when stdout is a TTY and neither `--no-color` nor the standard `NO_COLOR` environment variable is present; redirected text has no ANSI sequences. JSON/CSV never contain ANSI. No required environment variables, secrets or `.env` file.

Successful stdout contains only the selected report. Diagnostics and malformed-line summary go to stderr without echoing raw input. Skip malformed lines; mixed input succeeds, with count included in every format. Empty input succeeds with empty rankings and zero percentages. Nonempty input containing no valid records fails with exit 3 and no report.

| Exit code | Meaning |
|---|---|
| 0 | Success, including empty input/help/version |
| 1 | Input/output failure or unexpected runtime failure |
| 2 | CLI usage/configuration error |
| 3 | Nonempty input with zero valid records |
| 4 | unique-cardinality exhaustion |

Input read failure emits no report. Serialize before writing; if stdout later fails, report exit 1 where possible, and pipelines must discard partial stdout on any nonzero exit. Broken pipe is exit 1, without traceback. User interruption maps to 1. Runtime failure diagnostics omit raw log content.

JSON keys are the Report fields above. Rankings contain objects `{key, count}`. Hourly entries contain `{hour_utc, request_count, percentage}` in ascending hour order. CSV header is `metric,key,count,percentage`; rows are total_valid_requests, malformed_lines, top_ip, top_error_url, hourly_requests, unique_user_agents, unique_user_agent_share in that order. Scalar counts use empty key/percentage; hourly keys are `00`–`23`; share uses empty key/count. Ranking rows have blank percentage. CSV uses stdlib quoting for commas, quotes and newlines; consumers must treat keys as untrusted data, including spreadsheet formulas.

## Architecture Alternatives and ADR
Selected single-process streaming architecture is pre-approved; no architecture choice is pending. Loading the whole file is rejected because memory scales with input size. A multi-process parser is deferred because serialization and merge complexity threaten weekend delivery; revisit only with profiling evidence. Go or external sorting could help future performance/cardinality requirements but would change approved scope or dependencies.

Adversarial review is reserved for the external harness after this session; no independent review verdict is asserted here.

## Authentication and Trust Boundary
Authentication is inapplicable: the OS controls file permissions and process execution. Treat log fields as untrusted strings, disable Rich markup interpretation for them, escape control characters in terminal output, and never execute their contents. No network traffic, telemetry or persistence. Reports may contain sensitive IPs and query strings; users control local destination permissions.

## Installation and Deployment
Local pip installation from a wheel/source tree; planned MIT license. No Docker or docker-compose structure is required: there are no services to orchestrate. No server, cloud, Kubernetes, auth or deployment pipeline is included. Publishing requires separate authorization; this session creates documentation only.

## Performance and Verification
Target, not measured result: <30 seconds for a 1,000,000,000-byte local combined log on a documented laptop, including parsing, aggregation and output, excluding fixture generation/install. Capture CPU/RAM/OS/Python/storage, cold/warm cache conditions, input mix/cardinalities, wall time and peak RSS across three runs; require each measured run below target. Exact correctness and cap handling must remain intact during optimization.
See [PRD](PRD.md), [plan](IMPLEMENTATION_PLAN.md), [strategy](STRATEGIC_PLAN.md), and [implementation guide](CLAUDE_CODE_GUIDE.md).
