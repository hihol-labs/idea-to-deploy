# Project Architecture: nginx-logstats

## Context and Decision
**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Each invocation reads a finite input stream, holds counters in process memory, emits one report, and discards state. A database would introduce persistence, migrations, and cleanup without serving a cross-run query requirement. An HTTP API would introduce a server lifecycle, network exposure, and deployment work without helping file/stdin pipelines. Neither belongs in this $0 weekend tool.

Python 3.11, Click, Rich, and dataclasses are approved. The obvious single-process modular CLI is selected; no architecture-choice pause is needed. There are no product authentication, secrets, database tables, migrations, API endpoints, Docker services, cloud resources, or Kubernetes manifests. Installation targets the user's local Python environment through pip. No product-specific environment variables or `.env` file are required; `--no-color` provides explicit color control.

## Architecture Decision Record (ADR)
The product brief pre-approves this design. This session has not run an adversarial or independent reviewer; the external harness performs that review separately.

Alternatives considered at planning level: whole-file loading fails streaming memory requirements; a multiprocess parser adds serialization/ordering complexity before evidence justifies it; persistent analytics infrastructure conflicts with scope and budget. Approximate sketches are rejected because the four metrics must be exact. A limit failure is preferable to silently inaccurate output.

## Components and Flow
`file/stdin → bounded binary line reader → combined parser → typed record → accumulator → report → terminal/JSON/CSV renderer`

| Planned path | Responsibility |
|---|---|
| `src/nginx_logstats/cli.py` | Click command, options, stderr diagnostics, exit-code mapping |
| `src/nginx_logstats/reader.py` | Sequential file/stdin reads, line-size limit, decoding |
| `src/nginx_logstats/parser.py` | Anchored combined-format parser and typed validation |
| `src/nginx_logstats/models.py` | Record, accumulator/report dataclasses and error types |
| `src/nginx_logstats/aggregate.py` | Exact counters, distinct sets, limits, deterministic top-k |
| `src/nginx_logstats/render.py` | Pure terminal, JSON, CSV serialization |
| `src/nginx_logstats/__main__.py` | Module entry point |
| `tests/` and `benchmarks/` | Golden oracles, CLI tests, generated performance fixture |

All paths above are planned; no implementation is delivered by this blueprint.

## Input and Parsing Contract
MVP accepts standard nginx combined records: remote address, ident, remote user, bracketed timestamp with numeric timezone offset, quoted request, status, bytes, quoted referrer, quoted User-Agent. Field separators and quoting are parsed structurally; never split the line on whitespace alone. Accept nginx escaped quotes/backslashes and `\xHH` sequences inside quoted fields. Preserve their literal escaped spelling as the aggregation key; decoded aliases are not merged. Actual invalid UTF-8, invalid timestamp/offset, invalid IPv4/IPv6 address, missing fields, trailing unexpected fields, and statuses outside 100–599 are malformed. Ignore final LF/CRLF framing; allow a final record without a newline.

Request must contain method, request target, and HTTP version; a request of `-` is malformed. Bytes may be decimal or `-`. A User-Agent of `-` is a valid literal key. Neither forwarded addresses nor referrers affect metrics. Empty physical lines count as malformed. Default maximum physical line size is 65,536 bytes excluding LF and optional CR. Drain an oversized line in bounded chunks and count it once as malformed; never retain its entire body. No decompression, directory traversal, glob expansion, multiple inputs, custom formats, or live following in MVP. Read until EOF; a never-ending stdin requires the producer to close it.

## In-memory Data Contracts and Metrics
| Dataclass/state | Fields and types | Invariants |
|---|---|---|
| `Record` | `ip: str`, `url: str`, `status: int`, `hour: int`, `user_agent: str` | Validated record only; hour 0–23 |
| `Accumulator` | `valid: int`, `malformed: int`, `ip_counts: dict[str,int]`, `error_urls: dict[str,int]`, `hours: list[int]`, `user_agents: set[str]` | 24 hour counters; counts change only for valid records |
| `Report` | `schema_version: int`, `total_valid_requests: int`, `malformed_lines: int`, `unique_user_agents: int`, `unique_user_agent_share_percent: float`, ranked lists and hourly rows | Schema version 1; immutable report snapshot |

Top IPs count all valid requests using the literal address string (equivalent IPv6 spellings remain separate). Top error URLs count requests with status 400–599, combining 4xx and 5xx. URL means the raw request target including query string; never normalize or decode it. Each list has at most 10 entries sorted by count descending, then key ascending using Python string ordering. Use a bounded heap for final top-10 selection; never sort all keys merely to emit ten.

Hourly request distribution uses `100 × hourly_request_count / total_valid_requests`. Bucket by the logged local hour, pooling different dates and offsets into 24 buckets. This is a time-of-day profile, not a chronological time series; no UTC conversion occurs. Emit all hours 00–23, including zeros.

Unique User-Agent share is `100 × unique_user_agents / total_valid_requests`, where distinctness is exact and case-sensitive across the complete escaped User-Agent field. This measures distinct strings per request, not distinct visitors or the percentage of singleton agents. Empty valid input yields empty top lists, 24 zero hourly rows, zero distinct agents, and zero share. Malformed records contribute to no metric denominator. JSON retains numeric precision; terminal/CSV percentages round to two decimal places. Rounded hourly percentages need not sum to exactly 100.

## Cardinality, Complexity, and Performance
Let K be `len(ip_counts) + len(error_urls) + len(user_agents)`. Default `--max-unique-keys` is 250000 across these three stores combined. Before applying a valid record, determine the new keys it would add and fail atomically if K would exceed the limit. No truncation, eviction, spill files, or approximation. Code 4 means unique-cardinality exhaustion; no normal report is emitted. User-supplied higher limits can consume more memory and are outside the default memory acceptance envelope.

Streaming means O(line_limit + K + 24) storage, not constant memory independent of distinct input. Per-record dictionary/set work is expected O(1), parsing O(record length); final top selection O(K log 10). Cap, bounded line size, and exact accounting make the trade-off explicit. The target is 1,000,000,000 input bytes in under 30 seconds on the declared reference laptop with peak RSS at most 512 MiB at the default cap. This is unmeasured until implementation. See the benchmark protocol in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## CLI Interface
### Commands and Options
`nginx-logstats [OPTIONS] [INPUT]` and `python -m nginx_logstats [OPTIONS] [INPUT]` share behavior. No subcommands. INPUT defaults to `-` (stdin); a path opens one uncompressed binary file. Read sequentially without seeking. Examples: `nginx-logstats access.log`, `cat access.log | nginx-logstats --json`, `nginx-logstats --csv access.log > report.csv`.

| Option | Contract |
|---|---|
| `--json` | Emit one JSON object, schema version 1 |
| `--csv` | Emit one UTF-8 CSV document with header |
| `--no-color` | Disable terminal colors; accepted harmlessly with machine formats |
| `--max-unique-keys INTEGER` | Positive combined distinct-key budget; default 250000 |
| `--max-line-bytes INTEGER` | Positive physical-line ceiling; default 65536 |
| `--help`, `--version` | Print help/version and exit 0 without reading input |

`--json` and `--csv` are mutually exclusive; invalid options, nonpositive limits, and excess inputs return code 2 before opening input. No log data is executed or sent over the network.

### Outputs
Default Rich output has four metric sections plus valid/malformed totals. Color is automatic on a TTY and disabled on redirected stdout. Escape markup and display control characters visibly. Logs are untrusted display data.

JSON keys: `schema_version`, `total_valid_requests`, `malformed_lines`, `top_ips` (objects with `ip`, `count`), `top_error_urls` (objects with `url`, `count`), `hourly_distribution` (24 objects with `hour`, `request_count`, `percentage`), `unique_user_agents`, `unique_user_agent_share_percent`. Hour is an integer 0–23. No banners, ANSI sequences, or diagnostics on machine stdout.

CSV columns, in order: `schema_version,metric,key,count,percentage`. Version is always 1. Emit summary rows first in this order: `total_valid_requests`, `malformed_lines`, `unique_user_agents`, `unique_user_agent_share`; keys are empty, counts are the respective counts (distinct count for the share row), and percentage is empty except on the share row. Follow with `top_ip` rows, `top_error_url` rows, and 24 `hourly_requests` rows. Ranked keys preserve raw IP/URL strings; hourly keys use `00`–`23`. Counts are integers. Empty percentage means not applicable. Use standard CSV quoting for commas, quotes, CR/LF and UTF-8; this machine format is intended for pipelines, not automatic spreadsheet formula execution.

### Exit Codes
| Code | Meaning | stdout behavior |
|---|---|---|
| 0 | Successful report; no malformed lines (including empty input), or help/version | Complete report or requested help/version |
| 1 | Input/output or unexpected runtime failure, including broken pipe | No success report promised; output may be partial on write failure |
| 2 | CLI usage/option validation failure | No report |
| 3 | EOF reached with one or more malformed lines | Complete report over valid records; stderr warning |
| 4 | unique-cardinality exhaustion | No report; stderr diagnostic naming the limit |

Parsing errors are counted and processing continues; code 3 is selected only after EOF. Terminal I/O failures (1) or cardinality exhaustion (4) stop immediately and take precedence over accumulated malformed counts; if output fails after EOF, return 1. Buffer only the small completed report before writing; input/cardinality failures occur before rendering. stderr diagnostics include counts/reason without echoing entire raw records. Keyboard interrupt returns 1 with a concise diagnostic. Pipelines must inspect the process exit code, including when code 3 carries usable output.

## Verification and Delivery
Golden fixtures must independently establish expected counters, ties, escaped fields, mixed offsets, and malformed behavior. Test the installed command, all formats, all exit codes, atomic cap boundaries, oversized lines, and streaming input. Local wheel installation is delivery; external publication is deferred. See [PRD.md](PRD.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md), and [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md). Persistent contributor instructions live in [CLAUDE.md](CLAUDE.md).
