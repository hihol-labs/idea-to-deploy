# Project Architecture: Nginx Log Lens

## Context and approved architecture
Python 3.11, Click, Rich and dataclasses implement a single-process local CLI. The approved decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

A database would introduce persistence, setup, migrations and retention concerns without helping a one-shot summary. In-memory counters last only for one invocation. An HTTP API would introduce a server lifecycle, network surface and authentication concerns while stdin/stdout already provide pipeline integration. Neither constraint prevents the required local reporting.

Related contracts: [PRD.md](PRD.md), [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md), [CLAUDE.md](CLAUDE.md), and [README.md](README.md).

## Components and data flow
`Click args -> binary file/stdin reader -> combined-log parser -> bounded exact aggregates -> report dataclasses -> text / JSON / CSV -> stdout`

One record at a time; no full-log collection, threads, subprocess workers or durable state. stdin is consumed until EOF; this is streaming snapshot analysis, not follow mode. stderr carries diagnostics, never report rows. Formatters run only after successful EOF and finalization.

## Planned source structure
| Path | Responsibility |
|---|---|
| pyproject.toml | Metadata, Python >=3.11, Click/Rich dependencies, console entry point |
| src/nginx_log_lens/cli.py | Click command, input ownership, exit mapping |
| src/nginx_log_lens/reader.py | Bounded binary line reader, UTF-8 decoding |
| src/nginx_log_lens/parser.py | Combined-format validation and extraction |
| src/nginx_log_lens/models.py | Record/report dataclasses |
| src/nginx_log_lens/aggregate.py | Counters, cardinality guard, ranking |
| src/nginx_log_lens/render.py | Terminal, JSON and CSV serialization |
| tests/ | Parser, aggregate, CLI, output and package tests |
| benchmarks/ | Deterministic fixture generator and benchmark runner |

## Input and parsing contract
Support nginx standard combined format: `remote_addr - remote_user [time_local] "request" status body_bytes_sent "http_referer" "http_user_agent"`. Accept valid IPv4/IPv6 literals, numeric status 100–599, decimal byte count or `-`, timezone-bearing nginx timestamps, and request method/target/protocol tokens. Validate dates and UTC offsets. Quoted fields support nginx `\xHH` escapes, decoded once; reject malformed escapes. Custom formats and gzip are outside MVP.

Read binary input with a 65,537-byte maximum read chunk per line; lines over 65,536 bytes including newline are discarded in bounded chunks as one malformed line. The final line need not end in newline. Decode UTF-8 strictly after framing; invalid bytes, blank lines and malformed records increment `malformed_lines` and are skipped. Diagnostics contain counts, never raw records. If any records are valid, skipped lines alone do not make the invocation fail.

An origin-form request target starts with `/`; strip the query at the first `?`. Keep percent encoding, case and repeated slashes; no route inference, URL decoding or fragment normalization. Reject unsupported absolute-form and `*` targets as malformed for MVP. Parse referer/remote_user to validate structure but do not retain them. Missing UA `-` is valid and excluded from unique UA cardinality; empty quoted UA is also treated as missing. Other UA values compare exactly after escape decoding.

## Metrics and deterministic semantics
- `total_valid_requests`: all accepted records, regardless of status.
- IP ranking: count every valid record by canonical IP string; IPv6 textual aliases canonicalize using the standard library.
- Error URLs: count only status 400–599 by query-stripped path, with separate `count_4xx`, `count_5xx` and their sum `count`. Return at most ten nonzero entries ranked by sum descending, then URL string ascending. IP ties use canonical string ascending.
- Hour buckets: retain each timestamp's source UTC offset; key `YYYY-MM-DDTHH:00:00±HH:MM`. Different offsets remain separate, including DST repeated hours. Sort by bucket UTC instant, then key. Emit observed buckets only. Every bucket's percentage is `100 × hourly_request_count / total_valid_requests`. Round to six decimal places at serialization; rounded percentages may not sum to exactly 100.
- UA share: `100 × unique_user_agent_count / total_valid_requests`, percentage of requests represented by distinct non-missing UA strings, not a bot share or a fraction of unique visitors. A repeated UA increases the denominator only. All-missing UAs produce zero percent.
- No valid records: exit 3 without a report, preventing division by zero.

## In-memory data model (no database tables)
These are dataclasses and containers, not persistent tables; there are no schemas, migrations, constraints or database indexes to deploy.
| Model | Fields and types | Invariants |
|---|---|---|
| ParsedRequest | ip: str; path: str; status: int; hour: str; ua: str or None | Validated record; not retained after update |
| AggregateState | total_valid_requests: int; malformed_lines: int; ip_counts: dict[str,int]; error_urls: dict[str,ErrorCounts]; hours: dict[str,int]; user_agents: set[str] | Nonnegative integers; capped keys |
| ErrorCounts | count_4xx: int; count_5xx: int | Sum is combined count |
| Report | schema_version: int; total_valid_requests: int; malformed_lines: int; unique_user_agent_count: int; unique_user_agent_share_pct: float; top_ips: list[IpRow]; top_error_urls: list[UrlRow]; hourly_requests: list[HourRow] | schema_version=1; ranked lists max ten |
| IpRow / UrlRow / HourRow | ip,count / url,count,count_4xx,count_5xx / hour,count,percentage | Keys as strings, counts as integers, percentages as numbers |

## Memory bounds and performance
Exact top-k requires counters for every distinct key, not only the current ten leaders. `--max-unique` defaults to 100000 and caps each of IPs, error URLs, UAs and hour buckets separately; minimum 1, maximum 1000000. Existing keys remain usable at the cap. Before inserting a new key beyond any cap, abort with exit 4, emit a dimension-specific count-only diagnostic, and produce no report. No eviction, sampling, spilling, approximation or silent truncation. Working state is O(distinct keys plus bounded line length); this is stateless across runs, not constant memory across arbitrary cardinality.

The target is a decimal 1 GB (1,000,000,000 bytes) under 30 seconds, measured with the complete command including reading and output to a local sink. Baseline: Python 3.11, local SSD, 4+ physical CPU cores, 16 GiB RAM, <=100000 distinct keys per dimension, <=10000 hour buckets, mean line <=512 bytes, uncompressed valid combined log. Record actual laptop CPU/OS, storage, Python/dependency versions, fixture composition, wall time and peak RSS; aim <=512 MiB RSS. Run three times and require every timed run <30 seconds. Also test adversarial high cardinality and maximum-length lines for bounded failure. Arbitrary 1 GB logs are not guaranteed to meet time or memory targets. No measurement has been made in this planning session.

## CLI Interface
### Commands and options
| Interface | Contract |
|---|---|
| `nginx-log-lens [INPUT]` | One optional file path; omitted or `-` means stdin |
| `--json` | One JSON object, schema version 1 |
| `--csv` | One CSV stream using the schema below |
| `--json --csv` | Mutually exclusive; usage failure |
| `--no-color` | Disable terminal color; accepted in all modes |
| `--max-unique INTEGER` | Per-dimension cap, default 100000, range 1–1000000 |
| `--help`, `--version` | Print help/version, exit 0 without reading input |
No subcommands, output-file flag, remote URLs, configuration files or runtime environment variables. Unknown arguments and multiple input paths fail with code 2. stdin must not be closed by the CLI; owned file handles must be closed.

### Inputs and outputs
Examples: `nginx-log-lens access.log`, `cat access.log | nginx-log-lens --json`, `nginx-log-lens access.log --csv > report.csv`.

Default text uses Rich with four metric sections and totals/skipped-line summary. Colors appear only on a TTY, unless `--no-color` or `NO_COLOR` is set. Non-TTY text and both machine formats contain no ANSI escapes, progress bars or decorative messages. No app-defined env variables; `NO_COLOR` is the sole recognized display convention.

JSON keys are exactly the Report fields above. Rows contain the fields named in the model table. Arrays are empty when no error URLs exist; total requests remains positive for any report. Serialize UTF-8 JSON with a final newline, finite numeric percentages and integer counts; never locale-dependent numbers.

CSV uses UTF-8, RFC-style quoting, a single header and fixed columns:
`section,key,count,count_4xx,count_5xx,percentage`
Rows are: summary (`total_valid_requests`, `malformed_lines`, `unique_user_agent_count`, `unique_user_agent_share_pct`); `top_ips`; `top_error_urls`; `hourly_requests`, in that order. Summary count metrics use `count`; UA share uses `percentage`. IP/hour/URL values occupy `key`; irrelevant cells are empty, not zero. Hour rows carry count and percentage; URL rows carry all three counts. Zero-error results have no URL rows. Consumers must treat cells as data, not spreadsheet formulas; preserve exact path strings in pipeline exports.

### Exit codes
| Code | Meaning | stdout |
|---|---|---|
| 0 | Successful complete report, or help/version | Report or requested help/version |
| 1 | Input/output or unexpected runtime failure | No report before rendering; output-write failure may leave partial bytes |
| 2 | Invalid CLI usage/options | No report |
| 3 | No valid requests, including empty/all-malformed input | No report |
| 4 | unique-cardinality exhaustion | No report |
Diagnostics go to stderr. Broken pipe is an output failure, code 1; suppress traceback. Runtime failures after output starts cannot retract emitted bytes; pipelines must check exit status. Keyboard interrupt maps to 1. Controlled errors never expose input lines or local tracebacks by default.

## Auth, infrastructure and installation
Authentication and authorization: none; the process inherits the caller's local OS file permissions. No credentials or secrets are required. Logs are untrusted data; never execute, interpolate into shell commands, or allow Rich markup from fields. Render escaped literals and neutralize terminal control characters in text; machine output uses normal JSON/CSV escaping while preserving data.

Deployment target is a user's existing laptop through `python -m pip install .` or a built wheel. No HTTP endpoints exist. Docker and docker-compose are unnecessary; no containers, ports, HTTP health checks, cloud, Kubernetes or server are designed. No `.env` or infrastructure credentials are needed. Distribution to a public package index requires a later explicit release approval.

## Architecture Decision Record (ADR)
ADR-001: Choose the approved single-process streaming design with exact capped counters. A database-backed index conflicts with ephemeral analysis and $0 operations; a multiprocessing parser adds merge/IPC complexity before profiling shows a need. The specified Python stack and weekend scope make architecture selection unambiguous, so no variant selection is pending.

ADR-002: Prefer explicit exit 4 to approximate UA cardinality or top-k eviction. This preserves correctness within the documented envelope and makes resource exhaustion observable to pipelines.

Adversarial review is delegated by the user to the external benchmark harness after this session. No Devil's Advocate or independent review ran here, no verdict is asserted, and no review artifact is authored here.
