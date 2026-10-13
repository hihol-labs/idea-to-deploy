# Project Architecture: Nginx Lens

Status: proposed implementation contract using the user's pre-approved single-process architecture. No product code or runtime benchmark exists yet. Related: [strategy](STRATEGIC_PLAN.md), [PRD](PRD.md), [plan](IMPLEMENTATION_PLAN.md), [guide](CLAUDE_CODE_GUIDE.md), [README](README.md), [memory](CLAUDE.md).

## Decision and Scope

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Each invocation consumes a finite stream and discards its in-memory counters after producing a report. There is no cross-run query or history requirement, so a database would add persistence and maintenance without serving the brief. Users invoke the CLI locally or through a pipe; an HTTP API would add networking, server lifecycle, and access-control work to a tool with no remote consumers. Stateless means no durable application state; exact metrics still require bounded per-invocation state.

Python 3.11, Click, Rich, and dataclasses are fixed decisions. No authentication, database tables, migrations, HTTP endpoints, server, cloud infrastructure, or Kubernetes are applicable. Filesystem permissions govern access. No credentials, login flow, or network calls exist. Docker and docker-compose are unnecessary: install the wheel with pip into a virtual environment on a local workstation. No paid services are needed.

## Architecture Choice and ADR

The skill's explicit-stack and obvious-architecture exceptions apply: one process with small modules is selected without an interactive architecture choice.

| Alternative | Trade-off | Decision |
|---|---|---|
| Single-process iterator with exact counters | Simple deployment, no IPC; CPU and distinct-key limits matter | Selected for weekend scope |
| Worker processes and merged counters | Potential parsing parallelism; duplicated state, merge overhead, more error paths | Deferred unless measured profiling warrants a separately approved change |
| Persisted index or hosted analytics | Cross-run queries; infrastructure and data retention | Rejected by product constraints |
| Approximate sketches | Smaller memory; cannot promise exact ranking or unique count | Rejected for MVP; fail explicitly at the cap instead |

Decision provenance: stack, budget, timeline, reports, and no-service constraints come from the user. UTC bucketing, combined-only parsing, exactness limits, and the export schema are concrete planning choices made under pre-approval. The throughput goal is unmeasured. No Devil's Advocate or independent reviewer has run in this session; the external harness owns that review and its artifact. This ADR contains design rationale, not a review verdict.

## Components and Data Flow

```text
Click arguments -> binary file/stdin -> bounded line reader -> combined parser
                                                        -> invalid counters
                    valid LogRecord -> guarded Aggregator -> Report dataclass
                                            -> terminal / JSON / CSV -> stdout
diagnostics and errors ------------------------------------------------> stderr
```

| Planned path | Responsibility |
|---|---|
| pyproject.toml | Python >=3.11, package metadata, Click/Rich dependencies, nginx-lens entry point |
| src/nginx_lens/cli.py | Click arguments, resource lifecycle, exception-to-exit mapping |
| src/nginx_lens/reader.py | Bounded binary reads, overlong-line draining, source line numbers |
| src/nginx_lens/parser.py | Combined-format validation and LogRecord creation |
| src/nginx_lens/models.py | Slot-based dataclasses for records, limits, report rows |
| src/nginx_lens/aggregate.py | Counters, UTC buckets, unique UA set, capacity preflight |
| src/nginx_lens/render.py | Pure terminal/JSON/CSV serializers |
| tests/ | Hand-audited fixtures, parser, metrics, CLI and schema tests |
| benchmarks/ | Deterministic fixture generator and end-to-end timing runner |

Process one line at a time and never retain all records. Parse once, aggregate once, rank once at EOF. Do not render per-line progress. Top-10 selection uses a heap or equivalent O(K log 10) selection followed by deterministic sorting of the selected entries; full counts remain in memory. Total work is O(input bytes + distinct keys log 10); storage is O(distinct retained keys + retained key bytes + maximum line length).

## CLI Interface

Command: `nginx-lens [OPTIONS] [INPUT]`. The optional input is one file path; omitted input or `-` reads stdin until EOF. There are no subcommands. `nginx-lens --help` and `nginx-lens --version` exit 0. The planned distribution and executable name is `nginx-lens`; publication/name availability is not assumed.

| Option | Default | Contract |
|---|---|---|
| --json | Off | One complete JSON object followed by newline |
| --csv | Off | One UTF-8 CSV table with header |
| --strict | Off | First malformed record aborts with code 3 and no report |
| --no-color | Off | Disable terminal color; no effect on exports |
| --max-unique-keys INTEGER | 250000 | Positive combined count of IP keys, error URL keys, and distinct known UA keys |
| --max-key-bytes INTEGER | 67108864 | Positive total UTF-8 bytes of retained keys, counted separately per collection |
| --help / --version | Built in | Help or package version; do not open input |

`--json` and `--csv` together are usage error 2. No output-file flag: users redirect stdout. No configuration file, implicit log discovery, glob expansion, decompression, follow mode, or recursive directory reading. Explicitly named inputs must be regular files; stdin may be a pipe. Compressed/custom-format input is unsupported. A blocking stdin waits for upstream EOF, as normal for a stream processor.

All reports go to stdout; concise diagnostics and skipped-line totals go to stderr without raw log content. Terminal color is enabled only on a TTY, unless `--no-color` or `NO_COLOR` is present. `NO_COLOR` is the only application-interpreted environment variable (example: `NO_COLOR=1 nginx-lens access.log`); there are no required environment variables, `.env` files, tokens, or service endpoints.

| Exit code | Meaning | Report behavior |
|---|---|---|
| 0 | Successful valid or empty input; also help/version | Complete report (except help/version) |
| 1 | Input/output failure or unexpected internal runtime error | No intentionally published report before EOF; write failures can leave a partial output |
| 2 | CLI usage/option error, including conflicting export flags or nonpositive limits | No report |
| 3 | Malformed input detected | Default skips bad lines and emits complete report over valid lines, then returns 3; strict mode aborts with no report |
| 4 | unique-cardinality exhaustion: retained key-count or key-byte budget would be exceeded | Abort with no report; never silently approximate or truncate |

Validate options before opening the source. Once options are valid, the first fatal processing error determines the exit code. Nonfatal skipped records do not mask a later fatal I/O or capacity failure. Output write failure overrides a pending successful or malformed-input result with code 1. Catch broken pipes as code 1 without a traceback. A keyboard interrupt maps to code 1 with a short interruption diagnostic; externally forced process termination is outside this application exit contract. Emit no final report until processing and serialization succeed; stdout cannot be rolled back after an operating-system write failure.

## Input and Parsing Contract

MVP accepts the standard nginx combined layout: remote address, ident, remote user, bracketed timestamp, quoted request, three-digit status, body-byte count, quoted referrer, quoted User-Agent. Example (synthetic):

```text
192.0.2.1 - - [10/Oct/2026:13:05:00 +0200] "GET /health HTTP/1.1" 200 2 "-" "probe/1"
```

Input is UTF-8 with LF or CRLF; a final unterminated line is accepted. Invalid UTF-8, invalid IP, invalid calendar timestamp/offset, unknown format, empty lines, invalid escaping, invalid status outside 100–599, or a malformed request makes the entire line invalid. Bytes must be a nonnegative integer or `-`; ident, user, and referrer are parsed but not retained. IPv4 and IPv6 remote addresses are accepted and canonicalized using the standard library. Forwarded-header chains and hostnames are outside this format.

Require a nonempty method, nonempty request target, and HTTP version in a quoted request; a request of `-` is invalid because it cannot support the URL metric. Preserve the request target, including query and percent escapes, after log-level escape decoding; do not decode percent-encoded paths or strip query parameters. Nginx `\xHH` log escapes are decoded, then UTF-8 is validated; unsupported/dangling escapes are invalid. Delimiters must be found before decoding so escaped quotes cannot terminate fields. Only the known English nginx month abbreviations are accepted, independent of machine locale.

Maximum physical line length is 65,536 bytes excluding its LF/CRLF terminator. Read in bounded chunks; an overlong record is invalid and drained through its newline without buffering the remainder. Each physical line increments `total_lines` once, including a malformed final line. Every accepted record increments `total_valid_requests`; otherwise increment `invalid_lines`. In non-strict completed runs, `total_lines = total_valid_requests + invalid_lines`.

## Metrics and In-Memory Model

| Dataclass/state | Fields and types | Invariants |
|---|---|---|
| LogRecord | ip: str; utc_hour: int; target: str; status: int; user_agent: str or None | Hour 0–23; status 100–599; `-` or empty UA becomes None |
| Limits | max_unique_keys: int; max_key_bytes: int | Strictly positive; immutable |
| Aggregator | total_lines: int; valid: int; invalid: int; ip_counts: dict[str,int]; error_counts: dict[str,ErrorCounts]; hours: list[int]; agents: set[str]; key_bytes: int | 24 hourly slots; no persisted data |
| ErrorCounts | count_4xx: int; count_5xx: int | Total equals both counts summed |
| Report | schema_version: int; counters; top_ips; top_error_urls; hourly; unique_user_agents: int; unique_user_agent_share_percent: float; complete: bool | schema_version=1; complete=true only after EOF |

Top IPs rank all valid requests by descending request count, breaking ties by ascending canonical IP text. Top error URLs rank exact targets by descending combined 4xx and 5xx count, breaking ties by ascending target text (Unicode code-point order). Return at most 10 rows, with separate 4xx/5xx counts. Successful and 3xx requests do not enter the error-URL map.

Convert each timestamp's explicit offset to UTC, then aggregate by hour-of-day 00–23 across all dates. This is not a per-date timeline. Emit every hour, including zeros. Hourly percentage is exactly defined as `100 × hourly_request_count / total_valid_requests`. Unique UA share is `100 × unique_user_agent_count / total_valid_requests`, where the numerator is the number of distinct case-sensitive decoded, nonempty UA strings other than `-`. This is a diversity ratio, not the request share of the most popular agent. Unknown UAs remain in the denominator. Both percentages are 0 when there are no valid requests. Round exported/display percentages to six decimal places; rounded hourly percentages may not sum to exactly 100.

Example: four valid requests with UA strings `A`, `A`, `B`, `-` produce 2 distinct known agents and 50% unique share. If three requests fall in UTC hour 11 and one in hour 12, the hourly values are 75% and 25%. Malformed lines affect neither denominator nor metrics.

## Exactness and Resource Limits

Before committing a valid record, preflight all newly introduced IP, error-target, and known-UA keys together. Count each new key per collection and sum its UTF-8 byte length per collection. If either resulting total exceeds its configured cap, raise the capacity error before updating counters. At the cap, existing keys remain legal; a repeated known UA never consumes additional key budget. Unknown UA markers consume no UA entry. Error URLs have a separate namespace even if their text happens to equal another key.

The default caps bound retained data, not the number of requests. Key bytes do not include Python object overhead; key-count caps limit that overhead separately. Cap values and the 512 MiB reference RSS target must be tested; they are not a universal byte-exact RSS guarantee. Raising caps deliberately increases memory exposure. Actual allocation failure maps to code 1, whereas a configured cardinality/byte-budget rejection maps to code 4. No temporary spool, database, external sort, or probabilistic counter is used. Arbitrarily high-cardinality logs cannot simultaneously guarantee exact counts and fixed memory; explicit failure is the MVP contract.

## Output Schemas

Terminal sections: input summary, Top IPs, Top Error URLs (combined, 4xx, 5xx), Hourly Requests (UTC hour, count, percent), and Unique User-Agent Share (distinct count, valid-request denominator, percent). Render untrusted strings as literal text with control bytes escaped; disable Rich markup interpretation. Non-TTY output contains no ANSI escapes.

JSON has precisely these version-1 top-level keys: `schema_version`, `complete`, `total_lines`, `total_valid_requests`, `invalid_lines`, `unique_user_agents`, `unique_user_agent_share_percent`, `top_ips`, `top_error_urls`, `hourly`. Counts are integers; percentages are numbers, never NaN. `top_ips` rows are `{ip, request_count}`; `top_error_urls` rows are `{url, error_count, count_4xx, count_5xx}`; `hourly` rows are `{hour_utc, request_count, percent}`, ordered 0 through 23 with integer hours. `complete=true` denotes reaching EOF, even when invalid lines were skipped and exit code is 3. Empty input produces empty top lists, 24 zero-hour rows, and zero totals. JSON escapes control characters while preserving the original decoded text value.

CSV is one table, not concatenated tables. Exact header: `schema_version,section,key,count,percent,count_4xx,count_5xx`. Always use version 1. Summary rows, in order, have section `summary` and keys `complete` (count 1), `total_lines`, `total_valid_requests`, `invalid_lines`, `unique_user_agents`, `unique_user_agent_share` (count = distinct known agents, percent = share). Follow with `top_ips`, `top_error_urls`, and 24 `hourly` rows in report order. Top-IP keys are IPs; error keys are request targets; hour keys are zero-padded `00` through `23`. Error count and its breakdown occupy their corresponding columns; hourly percent uses the specified formula. Nonapplicable numeric cells are empty. Use RFC-style quoting, doubled quotes, a comma delimiter, and CRLF row endings.

For terminal and CSV display keys, replace control characters U+0000–U+001F and U+007F–U+009F with visible `\uXXXX` escapes. CSV text keys whose first non-whitespace character is `=`, `+`, `-`, or `@` receive a leading apostrophe to deter spreadsheet formulas. CSV keys are consequently display-safe values; use JSON for exact raw-key interchange. This transformation never changes metric grouping. No BOM or ANSI codes in either machine format. Schema changes require an explicit version increment and spec update.

## Verification, Performance, and Delivery

Use hand-audited tiny fixtures for metrics, invalid records, offsets/day crossings, ties, IPv6, escaping, unknown agents, empty input, hostile display strings, and capacity boundaries. Unit tests cover reader/parser/aggregator; Click integration tests cover file/stdin equivalence and the complete exit contract. Broken-pipe and read/write failures require injected failure tests in addition to normal subprocess runs.

Reference benchmark: deterministic generated combined logs totaling exactly 1,000,000,000 bytes including newlines; 10,000 IP keys, 20,000 error-target keys, 5,000 known UA keys; 10% 4xx, 5% 5xx, all records valid, distributed over 24 UTC hours. Generate legal variable-length padding in ignored referrers to reach the exact byte size; validate the generated expected counts outside the timed interval. Record seed, generator revision, dataset byte size and metric oracle in the benchmark manifest. This workload is intentionally within the default budgets; run a separate adversarial high-cardinality fixture that must stop with code 4.

Measure `nginx-lens --json reference.log` end to end from process start to exit, including reading, parsing, ranking, serialization, and output to a local file. Run three measured warm-cache repetitions after one untimed warmup on the same recorded laptop; every measured run must finish in under 30 seconds and peak RSS must be at most 512 MiB. Record CPU model, core count, RAM, OS, Python/dependency versions, storage type, cache policy, output destination, elapsed time, RSS, and exit status. Record a separate cold-cache observation when practical; do not advertise the warm-cache result as universal laptop performance. Arbitrary high-cardinality input is subject to the documented caps.

Deployment means wheel installation on the user's laptop, not a running service. Build with `python -m build`; smoke-test the wheel in a fresh venv and run help plus a tiny fixture through all formats. Dependency versions will be selected and recorded during implementation; no packages are installed in this planning session. Run Linux CI and a local OS smoke test before claiming support for that OS. Preserve $0 scope and MIT-compatible dependencies.
