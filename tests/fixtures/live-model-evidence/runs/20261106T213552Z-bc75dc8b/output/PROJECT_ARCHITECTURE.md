# Project Architecture: Nginx Lens

## Context and decision
**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Each invocation consumes a finite stream, retains only aggregate counters, emits one report at EOF, and exits. No history, shared writes, queries across runs, or remote clients require a database. Adding an HTTP API would introduce a listener, lifecycle management, access control, and operational work with no benefit for file/stdin workflows. Stateless means no retained state between invocations; exact counters still consume memory during a run.

## Architecture Variants
The user approved the obvious single-process design and stack. No architecture choice requires a question.

| Variant | Benefits | Trade-offs | Decision |
|---|---|---|---|
| A: Single-process iterator and exact counters | Simple ordering, low IPC cost, weekend scope | Python parsing throughput must be measured | Selected; low complexity |
| B: Worker processes with merged counters | Potential parallel parsing | IPC, duplicate unique sets, merge memory, harder budget enforcement | Rejected for initial delivery; medium complexity |

## Components and data flow
`file/stdin → bounded line reader → combined-log parser → aggregate counters → immutable report → text/JSON/CSV renderer → stdout`

| Future file | Responsibility |
|---|---|
| src/nginx_lens/cli.py | Click entry point, option validation, exit mapping |
| src/nginx_lens/reader.py | Binary line streaming, line-size bound, UTF-8 decoding |
| src/nginx_lens/parser.py | Anchored combined-format grammar and typed conversion |
| src/nginx_lens/models.py | dataclasses: LogRecord, AggregateState, Report |
| src/nginx_lens/aggregate.py | Exact counts, unique-key budget, final sorting |
| src/nginx_lens/render.py | Rich tables, JSON schema, CSV schema |
| src/nginx_lens/errors.py | Typed processing exceptions |
| tests/ | Unit, acceptance, CLI and export tests |
| benchmarks/ | Synthetic corpus generator and timing driver |

No product files listed here are created by the blueprint.

## Input and parsing contract
Support nginx standard combined access logs only: remote address, ident, remote user, bracketed timestamp including numeric timezone, quoted request, status, bytes, quoted referer, quoted User-Agent. Recognize escaped quote/backslash sequences inside quoted fields. Validate the address as IPv4/IPv6, status 100–599, numeric bytes or `-`, a request with method/target/protocol, and a calendar-valid timestamp. `-` as the entire request is malformed in v1. Ignore ident/user/referer after validating field structure. Extended/custom formats are unsupported and count as malformed.

Read UTF-8 strictly per line; invalid UTF-8, blank lines, malformed grammar/values, and lines longer than 65,536 bytes excluding the newline count as malformed. Drain oversized lines in bounded chunks; never allocate an entire oversized line. Accept a final line without newline and CRLF. Count each physical line once. Read errors abort the invocation. Valid records are not retained after aggregation.

## Data model and calculations
| Object | Fields and types | Constraints |
|---|---|---|
| LogRecord | ip: str; target: str; status: int; hour: int; user_agent: str or None | hour 0–23, validated input |
| AggregateState | valid: int; malformed: int; ip_counts: dict[str,int]; error_url_counts: dict[str,int]; hourly: list[int]; agents: set[str]; observed_agents: int; key_count: int | hourly length 24; no persisted rows |
| Report | schema_version: int; total_valid_requests: int; malformed_lines: int; top_ips: list; top_error_urls: list; hourly: list; unique_user_agents: int; requests_with_user_agent: int; unique_user_agent_share_pct: float or None | schema_version 1, top lists length ≤10 |

- Top IPs count every valid record. IP keys use canonical textual form; never trust forwarding headers.
- Top error URLs count requests with status 400–599, combining 4xx and 5xx. The URL key is the logged request target including its query string; no decoding, normalization, or URL inference. Ties sort by key lexicographically after descending count, independently of locale.
- Hourly buckets merge the same hour-of-day across dates, using the timestamp's own logged offset without converting timezones. Emit all 24 buckets in hour order. Each percentage is `100 × hourly_request_count / total_valid_requests`. With no valid requests all hourly percentages are 0.0. Round displayed/exported percentages to two decimal places; their sum may differ from 100 by rounding.
- A User-Agent is the exact unescaped quoted field, case-sensitive. `-` and empty string mean missing; exclude them from both unique-agent count and observed-agent denominator. Unique User-Agent share = `100 × unique_user_agents / requests_with_user_agent`. Emit null in JSON, empty CSV cell, and N/A in text when the denominator is zero. This measures string diversity, not distinct people or bots.
- Malformed records contribute to none of the metric denominators.

## Resource and performance contract
Exact top lists require tracking all eligible keys, not keeping only the current ten. Cap the sum `len(ip_counts) + len(error_url_counts) + len(agents)` at `--max-unique` (default 250,000). The same string in different collections occupies separate slots. Preflight all new keys for a record; if the record would exceed the cap, abort with code 4 before mutating counters. Do not evict, approximate, or emit a partial report. Increasing the cap is an explicit memory trade-off.

Memory is O(unique keys plus their string lengths), bounded additionally by the line-size limit; it is not constant-memory for arbitrary cardinality. Target peak RSS ≤512 MiB on the recorded representative benchmark, not a guarantee for every legal key length. Input volume alone must not grow memory for repeated keys. Count updates are amortized O(1); final top-10 selection uses bounded heaps O(U log 10), plus final deterministic ordering. Timestamp validation must avoid unnecessary general-purpose date parsing overhead while remaining correct.

Performance target: process a 1,000,000,000-byte local uncompressed combined-log corpus in <30 seconds on a documented laptop, with ≤250,000 total unique keys. Measure end-to-end reading, aggregation, and rendering; record Python version, CPU, RAM, OS, corpus distributions and warm/cold cache conditions. Report three runs and their median, with peak RSS. This is an unverified target, not an achieved result. Cardinality overflow is a separate correctness test.

## CLI Interface
Planned installed command: `nginx-lens [OPTIONS] [INPUT]`. INPUT is one regular file path or `-`; omitted INPUT means stdin. Read until EOF; no live tail. `--help` and `--version` exit successfully without reading input.

| Option | Contract |
|---|---|
| --json | Emit one versioned JSON object |
| --csv | Emit one normalized CSV table |
| --max-unique INTEGER | Positive shared unique-key limit; default 250000 |
| --color [auto/always/never] | Text color; default auto, effective only for text |
| --help | Print usage |
| --version | Print package version |

`--json` and `--csv` together are usage error 2. Text is the default; Rich colors activate on a TTY, with `NO_COLOR` disabling auto color. Explicit always/never takes precedence. JSON/CSV contain no ANSI escapes or progress output. Logs are never interpreted as Rich markup; control characters are visibly escaped in terminal labels. Machine encoders preserve strings using their normal escaping rules.

Examples: `nginx-lens access.log`, `cat access.log | nginx-lens --json`, `nginx-lens --csv -`, `nginx-lens --max-unique 500000 access.log`.

JSON fields are the Report fields above. `top_ips` entries are `{ip: string, count: integer}`; `top_error_urls` entries are `{url: string, count: integer}`; `hourly` entries are `{hour: integer, count: integer, percentage: number}`. No elapsed runtime field is included, keeping reports reproducible.

CSV uses UTF-8, a header `section,key,count,percentage`, standard quoting, and these rows in order: summary/total_valid_requests, summary/malformed_lines, summary/unique_user_agents, summary/requests_with_user_agent, summary/unique_user_agent_share_pct; top_ip rows; top_error_url rows; hourly rows with zero-padded hour keys 00–23. Summary counts occupy count; the share occupies percentage with empty count; other unused cells are empty. Hourly rows contain both count and percentage. CSV is a machine interchange format; raw request targets should not be opened as trusted spreadsheet formulas.

Successful reports go only to stdout; warnings/errors go only to stderr. Build aggregation before writing output; input/parse/cardinality errors produce no report. Output write failures can leave bytes already written; there is no transactional guarantee for stdout. Broken pipe is code 1 without traceback.

| Exit code | Meaning | Output |
|---|---|---|
| 0 | Successful processing, including empty input; help/version | Complete report, or requested help/version |
| 1 | Input/output failure, interruption, or unexpected processing failure | stderr diagnostic; no completed report guaranteed |
| 2 | Invalid CLI usage/options | stderr usage and diagnostic |
| 3 | Nonempty input with zero valid records | stderr unsupported/malformed input diagnostic, no report |
| 4 | unique-cardinality exhaustion | stderr limit/observed-budget diagnostic, no partial report |

Mixed valid/malformed input succeeds with code 0 and a stderr warning naming malformed count. Empty input succeeds with empty top lists, zero totals and hourly percentages, and unavailable User-Agent share. Precedence: Click validates usage first; processing errors 1/4 abort immediately; only after EOF apply all-malformed code 3; output failure after aggregation is code 1. Interruptions use code 1 consistently.

## Database, API, auth, environment, and delivery
Database tables, fields, indexes, constraints, and migrations: none. In-memory dataclasses above replace a persistence schema. HTTP endpoints, methods, paths, request bodies, and response bodies: none; the complete public interface is the CLI contract. Auth mechanism: none, because local OS read permissions control file access and no listener exists. Input files remain unmodified.

Environment variables: `NO_COLOR` (any present value disables automatic terminal color); no product-specific variables or secrets. Python/package environment is managed with a virtual environment. Docker and docker-compose are not required and no container configuration is planned. Deployment target is a local Python 3.11 virtual environment installed through pip, with a wheel built using the standard Python build frontend. No server, cloud, Kubernetes, telemetry, or network access at runtime. Public package publishing would require separate explicit authorization.

## Architecture Decision Record (ADR)
Single-process exact aggregation was selected from approved product constraints. Multi-process parsing and persistent analytics were rejected for initial complexity and lack of a persistent query requirement. A cardinality cap preserves exactness while making resource exhaustion explicit; approximate sketches were rejected because they would change the reporting promise.

Adversarial review is deferred to the external harness's fresh session. No Devil's Advocate, independent review, debate verdict, or review artifact was produced in this session.

Traceability: [strategy](STRATEGIC_PLAN.md), [acceptance specification](PRD.md), [delivery steps](IMPLEMENTATION_PLAN.md), [implementation guide](CLAUDE_CODE_GUIDE.md), [README](README.md), [agent context](CLAUDE.md).
