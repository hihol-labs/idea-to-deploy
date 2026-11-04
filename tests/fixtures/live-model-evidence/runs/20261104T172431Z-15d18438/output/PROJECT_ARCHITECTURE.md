# Project Architecture: Nginx Lens

## Decision and boundaries
**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Each invocation owns temporary in-memory counters and discards them on exit. A database adds persistence and administration with no requirement for cross-run state. An HTTP API adds networking, lifecycle, and access-control obligations without helping local stdin/file pipelines. No authentication is needed: operating-system file permissions govern input access. No server, cloud, Kubernetes, containers, or migrations are required. Distribution is a local pip-installed wheel, not a deployment.

## Architecture selection
The approved single-process modular CLI is the obvious choice under the specified stack; no choice is pending. Reading entire files would violate streaming and increase memory. Worker processes add merge overhead and complexity before profiling establishes a need. Persistent search systems violate the scope. These are decision trade-offs, not an adversarial review.

## Components and data flow
`Click → bounded binary line reader → combined parser → exact accumulator → Report → Rich / JSON / CSV → stdout`

Diagnostics go exclusively to stderr. Reading and aggregation are incremental; final output starts only after EOF and successful aggregation. No full input or per-request list is retained. A downstream write failure may leave partial output and returns 1.

| Planned path | Responsibility |
|---|---|
| src/nginx_lens/cli.py | Click entry point, error mapping |
| src/nginx_lens/reader.py | File/stdin ownership, bounded line reads |
| src/nginx_lens/parser.py | Combined format validation |
| src/nginx_lens/models.py | Record, Report dataclasses |
| src/nginx_lens/aggregate.py | Counters, exact sets, caps |
| src/nginx_lens/render.py | Rich, JSON, CSV rendering |
| tests/ | Golden and failure fixtures, CLI tests |
| benchmarks/ | Reproducible corpus generator and runner |

## Input and parsing semantics
Only standard nginx combined format is supported: remote address, ident, user, bracketed timestamp with numeric offset, quoted request, status, bytes, quoted referrer, quoted User-Agent. A tokenizer must respect escaped quotes/backslashes. Decode UTF-8 strictly per line; invalid bytes, invalid timestamp/IP/status, missing fields, or invalid request are malformed. Accept IPv4/IPv6, status 100–599, bytes as integer or `-`; validate the whole line. Maximum physical line is 64 KiB including newline; drain oversized lines incrementally and count each as one malformed line. No raw log excerpts in diagnostics.

Request must have method, request target, and HTTP version; accept origin-form targets beginning `/`. URL identity is the raw path before `?`, without percent decoding or slash normalization. Query strings and referrers are not retained. The client IP is remote_addr, never inferred from proxy headers. User-Agent identity is the parsed unescaped field, case-sensitive, without trimming; `-` and empty strings are excluded from the unique set but their requests remain in the denominator.

## In-memory data model
No database tables, indexes, or persisted models exist; generic database-table rubric is inapplicable.

| Dataclass | Fields and types | Constraints |
|---|---|---|
| Record | ip: str, hour_utc: int, path: str, status: int, user_agent: str | Validated before update |
| Accumulator | total_valid_requests: int, invalid_lines: int, ip_counts: dict[str,int], error_urls: dict[str,ErrorCounts], hours: list[int], user_agents: set[str] | 24 hours; bounded unique collections |
| ErrorCounts | errors_4xx: int, errors_5xx: int | Nonnegative; sum determines ranking |
| Report | schema_version: int, total_valid_requests: int, invalid_lines: int, top_ips: list, top_error_urls: list, hours: list, unique_user_agents: int, unique_user_agent_share_pct: float | schema_version = 1 |

Top IPs count every valid request. Top error URLs count only status 400–599, ranked by total errors with separate 4xx/5xx columns. Both rankings sort count descending then key lexicographically ascending; return up to ten rows. Convert timestamps to UTC, combine dates into hour-of-day buckets 00–23 and always emit all 24 buckets.

Hourly request distribution: `100 × hourly_request_count / total_valid_requests`.
Unique User-Agent share: `100 × unique_user_agents / total_valid_requests`; this is distinct known UA strings per valid request, not a traffic share by browser family. Empty valid input yields zero counts and 0.0 percentages. Machine numbers are not rounded; terminal percentages display two decimal places.

## Exactness and resource policy
Exact top-k needs counts for all observed keys; retaining only ten candidates is incorrect. Memory is O(distinct IPs + error paths + User-Agents + 24), not constant in cardinality. Default `--max-unique` is 100000 for each of the three collections independently. Before inserting a new distinct key, enforce its cap; exceeding any cap aborts with exit 4 and no report. No evictions, silent truncation, disk spill, approximation, or fallback database. Check all needed inserts before mutating a record's counters. A 64 KiB line bound and collection caps bound retained input volume; Python allocation overhead still requires measurement. Actual allocation/IO failures use exit 1, not a false cardinality diagnosis.

## CLI Interface
Command: `nginx-lens [OPTIONS] [INPUT]`; omitted INPUT or `-` reads stdin. One UTF-8 plain file per invocation; directories, gzip, and multiple file arguments are unsupported in MVP. It reads to EOF, including pipes; a never-ending pipe never produces a final report.

| Option | Contract |
|---|---|
| --json | JSON object to stdout |
| --csv | CSV long-form report to stdout |
| --strict | Abort on first malformed record, exit 3 |
| --max-unique INTEGER | Positive per-collection cap; default 100000 |
| --no-color | Disable Rich colors; automatic plain output when stdout is not a TTY or NO_COLOR exists |
| --help / --version | Informational output, exit 0 |

`--json` and `--csv` are mutually exclusive (exit 2). Default skips malformed lines, counts them, and prints a summary diagnostic to stderr. Nonempty input with zero valid records returns 3 without a report; truly empty input succeeds. Successful mixed input is exit 0 unless strict is enabled. No environment variables are required; `NO_COLOR` is presence-based (example `NO_COLOR=1`). No credentials or `.env` file.

| Code | Meaning |
|---|---|
| 0 | Successful report, including empty input; help/version |
| 1 | IO/output/runtime failure, including broken pipe or allocation failure |
| 2 | Invalid CLI usage or options |
| 3 | Invalid log data: strict rejection or nonempty input with no valid records |
| 4 | unique-cardinality exhaustion |

Error precedence: option validation precedes IO; during streaming the first fatal error wins. Cardinality abort is immediate even if earlier malformed lines were skipped. On 2/3/4 stdout is empty; Click errors are caught to preserve the contract. File readability errors are 1, not Click usage errors. Help/version do not open input.

### Output schema
JSON contains Report fields above. `top_ips` entries have `ip,count`; `top_error_urls` have `url,count,errors_4xx,errors_5xx`; `hours` entries have `hour_utc,count,percentage`. `unique_user_agents` is the exact cardinality; denominator and invalid count are always explicit. Lists use ranking order or increasing UTC hour.

CSV is UTF-8 RFC-style quoting with header `section,key,count,percentage,errors_4xx,errors_5xx`. Sections, in order: `summary` (keys total_valid_requests, invalid_lines, unique_user_agents, unique_user_agent_share_pct), `top_ips`, `top_error_urls`, `hours`. Summary share uses percentage with count blank; other summary metrics use count. Hour keys are 00–23. Unused cells are blank; no ANSI or banners. JSON is one object plus newline. Terminal shows totals, rejection count, four labeled sections and UTC labeling; escape controls and render log-derived text literally without Rich markup.

## Security, packaging, and operations
Treat log strings as data, never commands or Rich markup. Never send logs or telemetry externally. Reports contain IPs and paths: operators control redirection and retention. CSV preserves raw machine values; spreadsheet consumers should import keys as text to avoid formula interpretation. Close files opened by the program, leave stdin ownership to the caller. Interruptions return 1 with a concise diagnostic. pyproject.toml declares Python >=3.11, Click/Rich dependencies and nginx-lens console entry. Test installation into a fresh local virtualenv. No HTTP endpoints, auth flow, Docker compose, or hosted deployment configuration is applicable.

## Performance validation
Target: 1,000,000,000 bytes in <30 seconds wall-clock from open to completed output on a documented laptop/SSD, Python 3.11, no network. Generate reproducible combined logs with fixed seed, mixed status classes, bounded distinct keys below caps, and recorded line length/cardinalities. Run three times per format, record each duration and peak RSS; all runs must meet target. Report cache conditions, CPU/RAM/OS and dependency versions. Also test cap exhaustion separately; the target does not promise exact processing of unlimited cardinality. Performance remains unmeasured at blueprint time.

## Architecture Decision Record (ADR)
Chosen: approved Python single-process CLI with bounded exact state. Rejected: persistence, services, whole-file loading and premature multiprocessing for the reasons above. Trade-off: inputs beyond caps fail explicitly rather than produce approximate results. Independent Devil's Advocate review is reserved for the external harness; no reviewer verdict exists in this session.

Related: [PRD](PRD.md), [strategy](STRATEGIC_PLAN.md), [implementation](IMPLEMENTATION_PLAN.md), [guide](CLAUDE_CODE_GUIDE.md), [instructions](CLAUDE.md).
