# Project Architecture: Nginx Lens

## Decisions and Boundaries

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Each invocation reads its input once, accumulates ephemeral counters, prints a final report, and discards state. A database would add persistence, migrations, cleanup, and sensitive-data retention without a cross-run query requirement. An HTTP API would require a listening service and lifecycle/security management while the required consumers already use shell pipelines. Both omissions reduce operational cost and keep delivery within a weekend.

Python 3.11, Click, Rich, and dataclasses are approved. A single process with synchronous buffered I/O is the selected architecture. No architecture choice is awaiting approval.

## Components and Data Flow

`Click arguments → binary line reader → combined-log parser → exact accumulator → Report dataclass → Rich/JSON/CSV renderer → stdout`

Diagnostics and rejected-line totals go only to stderr. There is no per-line report and no live follow mode; stdin is consumed until EOF. No raw records are retained after aggregation.

| Planned file | Responsibility |
|---|---|
| pyproject.toml | Build metadata, Python >=3.11, Click/Rich dependencies, nginx-lens entry point |
| src/nginx_lens/cli.py | Arguments, stream ownership, precedence of failures |
| src/nginx_lens/reader.py | Bounded binary line reads, strict UTF-8 decoding |
| src/nginx_lens/parser.py | Combined grammar, timestamp and request validation |
| src/nginx_lens/models.py | Record, counter rows, Report dataclasses |
| src/nginx_lens/aggregate.py | Exact counters, deterministic ranking, cardinality budget |
| src/nginx_lens/render.py | Rich tables and standard-library JSON/CSV serialization |
| tests/ | Unit fixtures, integration cases, serialization checks |
| benchmarks/ | Reproducible fixture generator and timing harness |

## Input Grammar and Validation

Support nginx standard combined format: `remote_addr - remote_user [time_local] "request" status body_bytes_sent "http_referer" "http_user_agent"`. Accept IPv4/IPv6 addresses (no DNS lookup), nginx backslash/hex escapes in quoted fields, a timezone-bearing timestamp, status integers 100–599, and byte counts that are nonnegative integers or `-`. Validate calendar dates and timezone offsets. Decode quoted nginx escapes once; invalid escapes are malformed. Validate request as method, origin-form target beginning `/`, and HTTP/version tokens separated by spaces. Unsupported absolute-form targets and `request="-"` are malformed. Ignore validated identity, byte count, and referrer fields after parsing. Extra trailing fields are unsupported.

Read at most 65,536 bytes per logical line including its newline. Oversize lines are drained in bounded chunks and counted as one malformed line. Final lines without a newline are allowed within the same limit. Blank lines, invalid UTF-8, invalid IPs, invalid timestamps, and unsupported formats count as malformed. No raw rejected line is echoed. Strict parsing is a deliberate MVP boundary, surfaced through diagnostics.

## In-Memory Data Model

No database tables, indexes, migrations, persisted caches, or disk spill exist. The complete logical structures are:

| Structure | Fields and types | Constraints/lifetime |
|---|---|---|
| Record | ip: str; hour_utc: int; path: str; status: int; user_agent: str or None | One valid line; hour 0–23; normalized IP; query removed from path |
| Accumulator | total_valid_requests: int; malformed_lines: int; ip_counts: dict[str,int]; error_counts: dict[str,ErrorCount]; hours: list[int]; ua_seen: set[str] | Nonnegative counters, exactly 24 hour slots, invocation lifetime |
| ErrorCount | errors_4xx: int; errors_5xx: int | Only error URLs stored; sum is ranking score |
| Report | schema_version: int; totals; top_ips; top_error_urls; hourly_distribution; unique_user_agents: int; unique_user_agent_share_percent: float | schema_version=1; lists finalized after EOF |

IP addresses use canonical textual representation. URL means request path with everything from the first literal `?` removed; preserve case, escapes, and trailing slash; do not percent-decode. Group 400–499 and 500–599 together for ranking, retain separate counts, and exclude other statuses from the error map. Rank IPs by descending request count then ascending canonical IP string; rank paths by descending total errors then ascending path string. Return at most ten of each; fewer are valid.

Convert timestamp offsets to UTC before taking hour-of-day. Combine matching UTC hours across dates. Emit all 24 buckets, including zeros. Hourly distribution percentage is `100 × hourly_request_count / total_valid_requests`.

Unique User-Agent share percentage is `100 × distinct_nonmissing_user_agents / total_valid_requests`. A User-Agent decoded as `-` or the empty string is missing; exclude it from the unique set but keep the request in the denominator. Otherwise compare exact decoded, case-sensitive strings. This metric measures distinct strings per request, not singleton agents or unique visitors. For zero valid requests, both percentage metrics are 0. JSON/CSV use six decimal places of precision (numeric values for JSON); terminal uses two decimals. Rounding can make displayed hourly percentages sum slightly differently from 100.

## Resource and Failure Model

Streaming does not imply constant memory for exact distinct counts. Memory is O(distinct IPs + distinct error paths + distinct nonmissing UAs), plus bounded line/parser buffers. `--max-unique` defaults to 100000 and caps the sum of entries in the IP map, error-path map, and UA set; the same text in different namespaces costs separate entries. Before updating a valid record, calculate all new entries; if the combined total would exceed the limit, exit 4 with no report. Do not evict keys or silently approximate. Users may explicitly raise the limit with awareness of memory cost. A line-size cap bounds individual keys but the default cardinality cap is not a promise of a fixed byte-level RSS ceiling. Unexpected allocation failure exits 1, distinct from configured cardinality exhaustion.

Reports are produced only after input completes. A fatal read or cardinality error prevents report generation even if earlier lines were malformed. Stream serialization can still leave partially written stdout if an output error occurs; consumers must check status. Normal mixed-quality input produces a report over valid records plus exit 3. Empty input is successful with zeros; nonempty all-invalid input produces a zero report and exit 3.

## CLI Interface

### Command and Inputs

`nginx-lens [OPTIONS] [INPUT]`

INPUT is one UTF-8 combined access-log path or `-` for stdin; omitted means stdin. A filename beginning with `-` uses the option separator, for example `nginx-lens -- -access.log`. File input is uncompressed and sequential. For gzip use `gzip -dc access.log.gz | nginx-lens --json`; callers should enable their shell's pipe failure handling to detect decompressor errors.

| Option | Contract |
|---|---|
| --json | Emit one JSON object; mutually exclusive with --csv |
| --csv | Emit one normalized CSV table; mutually exclusive with --json |
| --max-unique INTEGER | Positive total entry budget; default 100000 |
| --no-color | Suppress terminal ANSI sequences; machine formats never contain ANSI |
| --help | Show usage and return 0 without reading input |
| --version | Show installed version and return 0 without reading input |

Examples: `nginx-lens access.log`, `nginx-lens --json access.log`, `nginx-lens --csv < access.log`.

### Outputs

Default Rich text contains a summary, IP table, error URL table, 24-hour table, and UA count/share. Color is enabled on a TTY unless suppressed; redirected text is plain. Untrusted text is rendered literally, never as Rich markup; terminal control characters are escaped.

JSON schema version 1 has exactly these top-level fields: `schema_version`, `total_valid_requests`, `malformed_lines`, `unique_user_agents`, `unique_user_agent_share_percent`, `top_ips`, `top_error_urls`, `hourly_distribution`. `top_ips` entries have `ip` and `request_count`. `top_error_urls` entries have `url`, `error_count`, `errors_4xx`, `errors_5xx`. `hourly_distribution` entries have `hour_utc` (integer 0–23), `request_count`, and `percentage`. Counts are integers; percentages are numbers. Serialize UTF-8, no NaN, with a final newline and no log prefixes.

CSV header is `schema_version,section,key,count,percentage,errors_4xx,errors_5xx`. Each row has schema_version `1`. Summary rows use section `summary`, keys `total_valid_requests`, `malformed_lines`, `unique_user_agents`; the latter also carries the UA share in percentage. Other summary percentage cells are empty. IP rows use section `top_ips`, canonical IP as key, and request count. URL rows use `top_error_urls`, path as key, total errors in count, and both error counts. Hour rows use `hourly_distribution`, zero-padded UTC hour `00`–`23` as key, count and percentage. Unused cells are empty, never ambiguous zero defaults. Row order is summary in the order above, ranked IPs, ranked URLs, ascending hours. Standard CSV quoting preserves commas, quotes, and newlines. Exports are pipeline data, not executable spreadsheet content; operators should import untrusted string columns as text.

### Exit Codes

The complete contract is **0/1/2/3/4**:

| Code | Meaning | Report behavior |
|---|---|---|
| 0 | Success, including empty input/help/version | Complete report for analysis |
| 1 | Operational/internal failure: file access, read/write failure, broken pipe, allocation error, or handled interrupt | No report if input processing failed; output failure may leave partial bytes |
| 2 | Invalid CLI arguments or incompatible options | No report |
| 3 | Completed analysis with one or more malformed lines skipped | Complete report over valid requests, stderr summary |
| 4 | unique-cardinality exhaustion | No report; stderr limit diagnostic |

Validate options before opening input. During processing, fatal 1 or 4 terminates immediately; if report writing fails, return 1; otherwise malformed_lines > 0 yields 3, else 0. A handled Ctrl-C maps to 1; uncatchable OS termination lies outside application return codes.

## Environment, Authentication, and Deployment

No required environment variables, `.env` file, credentials, or authentication flow. Optional `NO_COLOR` with a nonempty value disables terminal color; for example `NO_COLOR=1 nginx-lens access.log`. CLI `--no-color` also disables it. No hidden format or cardinality configuration.

Local OS permissions control file access: `operator → local OS file permission check → input stream → local stdout`. No network calls, HTTP endpoints, listeners, accounts, or privilege elevation. Sensitive report content remains under the operator's control.

Install a wheel or local source through pip; `nginx-lens = nginx_lens.cli:main` is the planned console entry point. Target local Linux/macOS laptops on Python 3.11; Windows compatibility is best effort until tested. No Dockerfile or docker-compose services are needed: adding containers would complicate a pip CLI without improving this delivery contract. No cloud or Kubernetes deployment exists.

## Performance and Verification

Target: 1 GB (1,000,000,000 bytes) under 30 seconds wall clock on a documented laptop, from process launch to completed JSON output. Record OS, CPU, RAM, Python/dependency versions, storage, fixture size, key cardinalities, valid/malformed ratios, and peak RSS. Benchmark three warm-cache runs and report each duration plus median; cold-cache behavior is separately documented if tested. Use a declared synthetic standard-combined fixture within the default key cap. High-cardinality fixtures separately validate exit 4 and are not passed off as successful throughput runs.

The target is unmeasured. Python IP/timestamp parsing may dominate; profile before optimizing, preserve the grammar and metrics, and do not change stack or approximate results without updating scope. Semantic tests cover offsets, ties, mixed errors, missing UAs, zero denominators, malformed/oversize lines, exact budget boundary, stdout failures, and serialization. See [PRD.md](PRD.md) for acceptance gates and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for implementation order.

## Architecture Decision Record (ADR)

Selected: one synchronous process with exact dictionaries and a shared report model. Multiprocessing is deferred because splitting input and merging exact sets increases memory and complexity; only measured need could justify it. Persistent analytics systems and HTTP services conflict with the approved constraints. Approximate heavy hitters or probabilistic UA counting would change the exact report contract and are excluded.

Adversarial review is pending in a separate external harness session. No Devil's Advocate or independent reviewer ran in this session and no review verdict is asserted. Full-mode architecture variants are unnecessary under the skill's obvious-choice exception for the explicitly specified stack and single-developer MVP.

Related: [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md), [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md), [CLAUDE.md](CLAUDE.md).
