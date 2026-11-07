# Project Architecture: Nginx Lens

The [strategic plan](STRATEGIC_PLAN.md) sets scope; [PRD](PRD.md) defines acceptance; [implementation plan](IMPLEMENTATION_PLAN.md) maps this design to files. Status: planned, unimplemented.

## Architecture Decision
**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Each invocation reads local input once, keeps only bounded aggregate state, emits one report at EOF and discards memory. A database would add persistence, schema management and sensitive-log retention without serving a requirement. An HTTP API would add a server lifecycle and access control without improving shell workflows. There is no authentication: OS file permissions govern local access. There are no tables, indexes, migrations, endpoints, network listeners or credentials.

## Architecture Choice and ADR
The approved obvious design is a single synchronous process. No variants require a user choice. Multiprocessing is deferred because coordination and merging exact high-cardinality state complicate a weekend build. External analytics systems exceed the $0 local-only scope. Re-reading the whole file or sorting every record would violate streaming intent.

Devil's Advocate review is deferred to the external harness. No verdict or debate is asserted in this document.

## Components and Data Flow
`file/stdin → bounded line reader → combined parser → exact aggregator → immutable report → text/json/csv writer`

| Planned file | Responsibility |
|---|---|
| src/nginx_lens/cli.py | Click entry point; options, resources and exit mapping |
| src/nginx_lens/reader.py | Bounded binary line reads and UTF-8 decoding |
| src/nginx_lens/parser.py | Parse nginx standard combined format |
| src/nginx_lens/models.py | Dataclasses for LogRecord and Report |
| src/nginx_lens/aggregate.py | Counters, exact distinct UA set and caps |
| src/nginx_lens/render.py | Rich, JSON and CSV serializers |
| src/nginx_lens/errors.py | Typed operational/cardinality errors |

## Input and Parsing Contract
Support standard nginx combined records: remote_addr, ident, remote_user, bracketed timestamp with numeric offset, quoted request, three-digit status, byte count or `-`, quoted referrer and quoted User-Agent. Accept escaped quotes/backslashes inside quoted fields; unescape once. Unsupported formats are malformed. Validate IP as IPv4/IPv6, date/offset, status 100–599 and request as METHOD SP target SP HTTP/version. A `-` request is malformed. Blank records count as malformed; final line without newline is supported.

Read binary lines with a 64 KiB maximum record length including terminator. Drain oversized records in bounded chunks, counting each as one malformed record. Invalid UTF-8 is malformed rather than silently replaced. Retain only normalized fields needed for aggregation. No raw lines are printed in diagnostics.

## In-Memory Data Model
| Dataclass/state | Fields and types | Constraints |
|---|---|---|
| LogRecord | ip: str, target: str, hour_utc: int, status: int, user_agent: str | Parsed and validated; hour 0–23 |
| Aggregator | valid: int, malformed: int, ips: dict[str,int], error_urls: dict[str,int], hours: list[int], uas: set[str] | 24 hour bins, exact counters; capped combined key count |
| Report | schema_version: int, total_valid_requests: int, malformed_lines: int, top_ips: list, top_error_urls: list, hours: list, unique_user_agents: int, unique_user_agent_share_percent: float | Schema version 1; produced only after successful consumption |

Top IPs count all valid requests; canonicalize IP strings using standard-library ipaddress. Error URLs count requests with status 400–599, combining both classes. URL key is the exact decoded request target including query string; no query stripping or percent decoding. Sort both rankings by count descending then key ascending, returning up to 10. Missing UA token `-` maps to no UA and is excluded from the distinct set but its request remains in the denominator. Empty UA is treated as missing too. Otherwise UA equality is exact and case-sensitive.

Convert timestamps to UTC before accumulating hour-of-day across all dates. Emit all 24 bins in ascending order. Hourly percentage is `100 × hourly_request_count / total_valid_requests`. Unique UA share is `100 × unique_user_agents / total_valid_requests`. This is a distinct-string-to-request ratio, not a percentage of people or bots. For zero valid requests all percentages are 0 and rankings empty. Round only serialized/displayed percentages to two decimal places; counts remain integers. Rounded hourly percentages need not sum to exactly 100.

## Streaming, Limits and Performance
Exact ranking requires all distinct IP/error URL counts, and exact UA share requires a distinct set. Memory is O(distinct keys + maximum line length), not constant in input size. `--max-unique-keys` defaults to 100000 combined entries across IPs, error URLs and UAs. Before accepting a valid record, calculate all new keys; if their sum would exceed the cap, fail atomically with exit 4, no partial report and no approximate fallback. The same string in different collections counts separately. The line bound controls key length; the key cap is not a guarantee of a fixed RSS for adversarial long strings.

Benchmark target: 1,000,000,000 bytes in <30 s end to end on an identified laptop, Python 3.11, regular local input, no more than 100000 combined keys, representative ~200-byte lines; peak RSS <=512 MiB. Measure three runs, report every run and median, input bytes, counts, cardinalities, hardware/OS and cache conditions. Require all runs <30 s. High-cardinality data beyond the cap intentionally fails; pathological long keys may use more memory within the cap. Performance remains unverified. No whole-file materialization; finalize top-10 with bounded heap selection rather than sorting all keys.

## CLI Interface
Command: `nginx-lens [OPTIONS] [INPUT]`. INPUT is one local plain-text path or `-`; omitted INPUT means stdin. Consume until EOF; no follow mode, network inputs, gzip or multiple-file expansion in MVP. Example: `cat access.log | nginx-lens --json`.

| Option | Contract |
|---|---|
| --json | Emit one JSON object; mutually exclusive with --csv |
| --csv | Emit one CSV table; mutually exclusive with --json |
| --max-unique-keys INTEGER | Positive combined-key cap, default 100000 |
| --no-color | Disable terminal color |
| --help | Usage and metric definitions; exit 0 |
| --version | Package version; exit 0 |

Default output is Rich terminal text, colored for a TTY and plain when redirected. `NO_COLOR` disables color; `--no-color` wins. No application configuration env vars or .env file. JSON/CSV never contain ANSI escapes. stdout contains only the report; stderr carries concise diagnostics and malformed-line totals. Rich markup and terminal controls from log fields must be escaped/sanitized for text display. JSON encodes controls safely; CSV quotes fields per standard CSV rules. CSV consumers should treat keys as untrusted text, including spreadsheet formula prefixes; exact keys are preserved.

JSON fields: `schema_version`, `total_valid_requests`, `malformed_lines`, `top_ips` (objects with `ip`, `count`), `top_error_urls` (objects with `url`, `count`), `hours` (objects with `hour_utc`, `count`, `percent`), `unique_user_agents`, `unique_user_agent_share_percent`.

CSV header: `schema_version,section,key,count,percent`. Summary rows use section `summary`, keys `total_valid_requests`, `malformed_lines`, `unique_user_agents` (integer count, blank percent), and `unique_user_agent_share_percent` (blank count, percentage). Ranking rows use sections `top_ips`/`top_error_urls`, the actual key and count, blank percent. Hour rows use section `hours`, keys `00`–`23`, counts and percentages. Summary, IP, URL, then hours is the fixed section order. Every row has schema_version 1. UTF-8, CSV writer with newline control, header always present.

| Exit | Meaning | Output behavior |
|---|---|---|
| 0 | Successful read/report, including empty input or skipped malformed lines | Complete report |
| 1 | Input/output failure or unexpected internal failure | Diagnostic; no success claim |
| 2 | Invalid invocation/options | Click usage error; no report |
| 3 | Nonempty input with zero valid requests | Diagnostic; no report |
| 4 | unique-cardinality exhaustion | Diagnostic; no partial report |

Read/aggregate errors produce no stdout because rendering waits until EOF. A write failure may leave partial bytes; exit 1 tells pipelines to discard them. Empty byte stream succeeds; a stream of blank lines is nonempty and exits 3. An I/O or cap failure stops immediately and takes precedence over later validation. Broken pipe maps to 1. Interrupt maps to 1 with a short diagnostic. All guides must preserve this 0/1/2/3/4 contract.

## Packaging and Execution Environment
Python 3.11, Click, Rich, standard-library dataclasses, json and csv. pyproject.toml declares console script `nginx-lens = nginx_lens.cli:main`. Record tested dependency versions when implemented. No Docker/compose, hosting, server, cloud or Kubernetes: users install a wheel in a local virtual environment. There are no secrets or application env variables. Inputs remain local; logs may contain private IPs and URLs, so diagnostics avoid raw content and no telemetry is added.

## Verification
Use golden combined-log fixtures covering UTC offset crossings, ties, escaping, invalid UTF-8, missing UA, all-error/empty/all-invalid inputs, line bounds and atomic cap exhaustion. Assert identical metrics across text/JSON/CSV and subprocess exit codes. See [PRD acceptance](PRD.md) and [guide](CLAUDE_CODE_GUIDE.md). Product tests and benchmarks are future work, not evidence from this planning session.
