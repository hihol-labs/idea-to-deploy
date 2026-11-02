# Project Architecture: Nginx Pulse

## Context and Decision
**no database — stateless streaming processing; no HTTP API — CLI-only tool**

One Python 3.11 process reads a finite source, aggregates in RAM, emits a final report, and discards all state on exit. Persistence adds schema/retention work without helping a one-shot report. HTTP adds server lifecycle, routing and access controls without helping local shell users. No authentication, server, cloud, Kubernetes, migrations, Docker or compose file is required. Delivery target: an installed wheel on the user's laptop. The stack and single-process choice are pre-approved; architecture variants need no selection round.

## Components and Data Flow
`Click → bounded binary line reader → combined parser → aggregate state → immutable report → Rich / JSON / CSV → stdout`

| Planned file | Responsibility |
|---|---|
| `src/nginx_pulse/cli.py` | Click command, validation, exit mapping, stderr diagnostics |
| `src/nginx_pulse/reader.py` | Bounded file/stdin iteration, drain oversized lines |
| `src/nginx_pulse/parser.py` | Combined-log grammar, timestamp and status validation |
| `src/nginx_pulse/models.py` | Record, aggregate/report dataclasses |
| `src/nginx_pulse/aggregate.py` | Exact counters, resource guards, report finalization |
| `src/nginx_pulse/render.py` | Terminal, JSON and CSV serializers |
| `src/nginx_pulse/__init__.py` | Package version |

Time complexity: O(input bytes + Uip log 10 + Uerror-path log 10) using bounded top-k selection at EOF; no global full ranking is necessary. Memory depends on distinct keys and is capped explicitly, rather than being falsely described as constant memory.

## Input and Parsing Contract
Support UTF-8 nginx standard combined access logs: remote address, ident, remote user, bracketed timestamp, quoted request, status, byte count, quoted referrer and quoted User-Agent. Accept IPv4/IPv6 address literals without DNS resolution, `-` byte count and escaped quotes/backslashes inside quoted fields. Validate timestamps including calendar date and numeric UTC offset; status is 100–599. A request has method, origin-form target starting `/` (or `*`), and HTTP version. Unsupported custom formats are malformed, not guessed. Preserve request path case and percent escapes; strip everything from the first `?` for URL aggregation. Do not URL-decode or resolve paths. Distinct absolute targets are unsupported in v1.

Read binary lines with a 64 KiB content limit (excluding LF and an optional preceding CR). Oversized lines are drained in bounded chunks and counted once as malformed. Decode valid-size lines as strict UTF-8. Blank, malformed, invalid-encoding or invalid-timestamp lines increment `malformed_lines` and are skipped. Each accepted line increments `total_valid_requests`; referrer and remote-user fields are validated structurally but not retained. nginx quoted `-` for User-Agent denotes missing UA, counted as a valid request but not a unique UA. Empty UA also denotes missing. Unescape recognized nginx escapes for UA consistently; reject invalid escape sequences. UA comparison is case-sensitive with no other normalization. Escape terminal controls when displaying log-derived strings.

## Metrics and In-Memory Data Model
No database tables, indexes, migrations, or API endpoints exist. These ephemeral structures replace the template's database/API inventory.
| Dataclass / field | Type | Constraint |
|---|---|---|
| `Record.ip` | str | Valid IP literal, canonicalized via ipaddress |
| `Record.path` | str | Query-free origin path or `*` |
| `Record.status` | int | 100–599 |
| `Record.hour` | int | 0–23, timestamp's own numeric-offset local hour |
| `Record.user_agent` | str or None | Unescaped UA; missing maps to None |
| `Aggregate.total_valid_requests` | int | Nonnegative |
| `Aggregate.malformed_lines` | int | Nonnegative |
| `Aggregate.ip_counts` | dict[str,int] | Every accepted request |
| `Aggregate.error_url_counts` | dict[str,int] | Combined 400–599 requests only |
| `Aggregate.hour_counts` | list[int] | Exactly 24 entries |
| `Aggregate.unique_user_agents` | set[str] | Exact distinct nonmissing UA strings |
| `Aggregate.key_bytes` | int | Sum UTF-8 sizes of retained keys across containers |
| `Report` | frozen dataclass | Snapshot carrying schema version, totals, rankings and metrics |

Top IPs: at most ten `(ip,count)` pairs across all valid requests. Error URLs: at most ten `(path,count)` pairs by combined 4xx/5xx frequency. Sort by count descending then canonical IP/path string ascending using Unicode code-point order; ties at position ten use that order. No approximate heavy-hitter algorithm.

Hourly distribution is `100 × hourly_request_count / total_valid_requests`. Emit all 24 hour buckets, ordered 0–23, combining dates and retaining each record's local hour (no timezone conversion). Unique User-Agent share is `100 × unique_nonmissing_user_agent_count / total_valid_requests`, not requests with a UA divided by all requests. Missing UAs stay in the denominator. Compute using full precision, round only exported/displayed percentages to six decimal places. Rounded hourly percentages can sum slightly above/below 100; counts are authoritative.

## Resource Contract
Default `--max-unique 250000` limits the sum `len(ip_counts) + len(error_url_counts) + len(unique_user_agents)`; repeated keys use no new slot. An IP, path and UA with identical text still consume separate slots. Also cap total retained key UTF-8 bytes at 64 MiB (fixed v1 constant). Before committing any record's updates, calculate all new keys/bytes. If either budget would be exceeded, terminate with exit 4 and no final report; do not truncate, evict, approximate or partially account for that record. Counters and 24 buckets add bounded overhead; actual RSS must be benchmarked. Even a raised max-unique cannot bypass the key-byte cap. No disk spilling or hidden persistence.

## CLI Interface
Command name: `nginx-pulse [OPTIONS] [INPUT]`. `INPUT` defaults to `-` (stdin); otherwise one regular local file path, opened read-only. Symlinks to regular files are acceptable; directories and device files are rejected. No multiple-file expansion, gzip decoding, network URLs, follow mode or implicit config files. stdin ends at EOF; long-running pipe sources produce a report only when closed.

| Option | Meaning |
|---|---|
| `--json` | One UTF-8 JSON object followed by newline |
| `--csv` | One UTF-8 RFC 4180 CSV table with header |
| `--no-color` | Disable default terminal colors |
| `--max-unique INTEGER` | Positive integer, default 250000; exact aggregate slot cap |
| `--help` | Usage and metric definitions; exit 0 |
| `--version` | Installed package version; exit 0 |

`--json` and `--csv` together are usage error 2. Color is enabled for terminal text on a TTY unless `--no-color` or `NO_COLOR` is present. Redirected text and machine exports contain no ANSI escapes; no environment variable affects parsing or metrics. There are no application env vars, `.env` file or credentials. `NO_COLOR=1` is an optional conventional display example.

stdout contains only the final report (help/version excepted); stderr contains warnings/errors. Skip malformed lines and issue one summary warning with count, never raw log lines. Any fatal failure before rendering produces no report. A write failure may leave partial output; consumers must require exit 0. Broken pipe or file read failure returns 1. A mixed valid/malformed source succeeds with warning; zero valid requests returns 3 and no report. Interrupt returns 3 and no final report if rendering has not begun.

| Exit code | Meaning |
|---|---|
| 0 | Successful complete report, or help/version |
| 1 | Input/output failure, including unreadable input or broken pipe |
| 2 | Invalid command/options, conflicting formats or nonpositive limit |
| 3 | No valid records, interrupted processing or unexpected processing failure |
| 4 | unique-cardinality exhaustion: distinct-key slot or retained-key-byte budget exceeded |

Validate usage before opening input. During processing, first encountered fatal error determines the exit; EOF with no valid records gives 3. Expected exceptions map at the CLI boundary; unexpected errors produce a concise stderr message without dumping logs. Export errors use 1 for I/O, otherwise 3.

### Output Schema v1
JSON keys: `schema_version` (1), `total_valid_requests` (int), `malformed_lines` (int), `top_ips` (array of `{ip,count}`), `top_error_urls` (array of `{url,count}`), `hourly_distribution` (24 `{hour,count,percentage}` objects), `unique_user_agents` (`{count,percentage}`). Percentages are JSON numbers; use strict serialization with no NaN. Empty error rankings are `[]`.

CSV has columns `schema_version,section,key,count,percentage`. Each row repeats version 1. Emit `summary,total_valid_requests`, `summary,malformed_lines`, top rows as `top_ips,<ip>` and `top_error_urls,<path>`, 24 `hourly_distribution,00` through `23`, and `unique_user_agents,distinct`. `count` is always an integer; percentage is populated only for hour and UA rows (fixed six decimal places), otherwise empty. Row order follows this description and ranking order; quote commas, quotes and line breaks correctly. CSV preserves actual keys for machine consumers; opening untrusted keys as spreadsheet formulas is outside the pipeline contract.

Terminal text shows totals, ranked IP/error tables, all hourly counts/percentages and unique UA count/percentage. If no errors, display an explicit empty state. Never include raw User-Agent strings in any output.

## Packaging, Security and Operations
`pyproject.toml` defines Python >=3.11, Click/Rich dependencies and console script `nginx-pulse = nginx_pulse.cli:main`. Release development includes pytest and build tooling. No runtime networking, child processes or writes to input. Trust boundary: log fields are data, never shell commands, Rich markup or executable templates. No auth flow exists because execution uses the invoking user's filesystem permissions. Reports still contain IPs and paths; operators control their destination. Benchmark data must be synthetic.

## Performance and Validation
Target: one decimal GB (1,000,000,000 bytes) in <30 seconds end-to-end to JSON redirected to a local sink, with peak RSS ≤512 MiB, on a documented laptop. Use a seeded combined-log corpus below both uniqueness budgets, record CPU/RAM/OS/Python/dependency versions, storage, input checksum in benchmark artifacts, cache conditions, command, three run durations and RSS; require every run to meet target and metrics to match an independent fixture oracle. Also test a high-cardinality source that exits 4. This session makes no throughput claim. See [plan](IMPLEMENTATION_PLAN.md) for commands and [PRD](PRD.md) for acceptance.

## Architecture Decision Record (ADR)
ADR-001: Approved single-process exact aggregation. A DB and HTTP server are excluded for the reasons above. Multi-process parsing adds merge/order/memory complexity before profiling proves a need. Approximate sketches lose the exact top-ten and UA contract. Full-file loading violates streaming. These are design trade-offs, not independent review findings.

Adversarial review status: deferred to the external harness's fresh session. No Devil's Advocate or independent reviewer ran in this session; no verdict is claimed. See [strategy](STRATEGIC_PLAN.md) and [guide](CLAUDE_CODE_GUIDE.md).
