# Project Architecture: Nginx Lens

## Scope and Decision
**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Each invocation reads a finite input and emits one report; no history or shared state needs persistence, so a database adds lifecycle and storage work without serving a requirement. Local files and pipes already provide the integration boundary, so an HTTP API adds a server, ports, and access controls without benefiting this use case. No authentication, cloud, Kubernetes, or daemon is involved.

## Architecture Choice and ADR
The explicitly approved stack and single-process design make a variant selection round unnecessary under the blueprint's obvious-choice exception.

- Chosen: a synchronous iterator pipeline with exact in-memory aggregation. Low complexity suits a $0 weekend CLI.
- Rejected: materialize all records before aggregation; memory would scale with total requests.
- Rejected: multiprocessing parser; serialization/merging and multiplied cardinality state increase complexity before measurement justifies them.
- Rejected: persistent indexing/service architecture; conflicts with the approved scope.

Adversarial review is reserved for the external harness after this session. No independent review or review verdict is recorded here.

## Components and Data Flow
`Click CLI → bounded binary line reader → combined-format parser → aggregator → Summary dataclass → terminal/JSON/CSV renderer → stdout`

`stderr ← input diagnostics / invalid-count warning / failure description`

| Planned file | Responsibility |
|---|---|
| src/nginx_lens/cli.py | Click command, precedence, error mapping |
| src/nginx_lens/reader.py | File/stdin lifetime and bounded reads |
| src/nginx_lens/parser.py | Parse combined format into LogRecord |
| src/nginx_lens/models.py | LogRecord and Summary dataclasses |
| src/nginx_lens/aggregate.py | Exact counters, hourly bins, unique cap |
| src/nginx_lens/render.py | Stable machine outputs and Rich text |
| src/nginx_lens/__init__.py | Package version |
| pyproject.toml | Python 3.11, Click, Rich, entry point nginx-lens |

No product files are implemented by this blueprint.

## Input and Parsing Semantics
Support nginx standard combined format: remote address, ident, user, bracketed timestamp with numeric offset, quoted request, status, bytes, quoted referrer, quoted User-Agent. Parse escaped quotes/backslashes in quoted fields. Reject unsupported custom field layouts. IPv4/IPv6 remote addresses are literal grouping keys; do not resolve DNS or trust forwarded headers. Status is 100–599; bytes is a nonnegative integer or `-`. Timestamp must be calendar-valid with offset. Request is `METHOD target HTTP/version`; accept origin-form targets beginning `/` only. Missing request (`-`), invalid status/date/encoding, malformed escapes, and incomplete lines are invalid.

Read UTF-8 strictly, one bounded binary line at a time. A final line without newline is accepted if structurally valid. Maximum line payload is 65,536 bytes excluding CR/LF; oversized lines are drained in bounded chunks and counted once as invalid. Empty lines count as invalid. Treat log data as untrusted text; never execute it or interpret Rich markup/ANSI controls. Query strings and fragments are removed before counting URL paths; preserve percent escapes and case. Full raw lines are never printed in diagnostics.

## Metric and Resource Contract
Only valid parsed requests enter metric denominators. Invalid lines are skipped and counted; a run with at least one valid request can succeed with a warning.

| Metric | Definition |
|---|---|
| Top IPs | All valid requests per literal IP; descending count, lexical key tie-break; at most 10 |
| Top error URLs | Valid requests with status 400–599 grouped by normalized path; combined count, same sorting; at most 10 |
| Hourly distribution | 24 bins 00–23, using the hour in each log timestamp's own offset; dates collapse together; `100 × hourly_request_count / total_valid_requests` |
| Unique UA share | `100 × distinct_nonmissing_user_agents / total_valid_requests`; exact strings after unescaping; `-` and empty UA excluded from numerator, included in request denominator |

Percentages are percentages on 0–100, rendered to two decimal places. Hourly values may sum to 99.99 or 100.01 after rounding. JSON percentages are numeric rounded values. Report distinct UA count and denominator so the ratio can be recomputed; this is diversity per request, not a bot classification.

The global entry budget is `len(ip_counts) + len(error_url_counts) + len(user_agent_set)`, default 1,000,000. `--max-unique` sets a positive total budget. Before accepting a valid record, determine how many new entries all three structures would need. If the addition exceeds the budget, terminate with code 4 and emit no report; never evict or silently approximate. Check budget before updating any metric. Storage is O(Uip + Uerror_paths + Uua + 24), bounded by the entry budget plus bounded keys; it is not constant-memory exact cardinality. The line limit bounds key length. A high budget with long keys can still exceed laptop memory; MemoryError maps to 4. Default limit is an explicit capacity guard, not a promise of fixed RSS.

## CLI Interface
Command: `nginx-lens [OPTIONS] [INPUT]`. INPUT defaults to `-` (stdin). Exactly one regular file path or stdin is accepted; no globs, multiple files, gzip decompression, watch, or network input. An upstream decompressor can pipe bytes to stdin.

| Option | Contract |
|---|---|
| --json | Emit one JSON object; mutually exclusive with --csv |
| --csv | Emit one normalized CSV table; mutually exclusive with --json |
| --max-unique INTEGER | Positive global entry budget, default 1000000 |
| --no-color | Disable terminal color |
| --help | Usage text, exit 0 |
| --version | Installed version, exit 0 |

Default text uses Rich tables, color only when stdout is a TTY and NO_COLOR is absent. `--no-color` takes precedence. Machine modes never emit ANSI escapes. There is no config file or product-specific environment variable. Standard `NO_COLOR` presence disables text color; example `NO_COLOR=1 nginx-lens access.log`. UTF-8 output is deterministic across locales.

Inputs are consumed through EOF before rendering. Stdout contains only a complete successful report (apart from a downstream write failure); progress/warnings/errors go to stderr. Do not open/truncate an output path: users redirect stdout. Reader failures discard accumulated results. Broken pipe maps to 1 without traceback. Invalid options and conflicting formats are checked before input is opened.

| Code | Meaning |
|---|---|
| 0 | Complete report with at least one valid request, or help/version |
| 1 | Input/output failure or unexpected runtime failure |
| 2 | Invalid CLI usage/options |
| 3 | No valid requests (empty input or all lines invalid); no report |
| 4 | unique-cardinality exhaustion, including MemoryError; no report |

Precedence: usage errors first; encountered I/O or resource errors abort immediately; only clean EOF can yield 3 or successful 0. Interrupt maps to 1 with a brief diagnostic. No partial aggregate is presented as complete.

## Output Schemas
JSON schema version 1 has exactly these top-level fields: `schema_version` (integer 1), `total_valid_requests` (integer), `invalid_lines` (integer), `top_ips` (array of `{ip: string, count: integer}`), `top_error_urls` (array of `{path: string, count: integer}`), `hourly_distribution` (24 objects `{hour: integer, count: integer, percentage: number}` ordered 0–23), `unique_user_agents` (integer), `unique_user_agent_percentage` (number). All counts are nonnegative; successful reports have a positive denominator. JSON uses standard escaping and no NaN/Infinity.

CSV is UTF-8 with header `schema_version,metric,key,count,percentage`, LF record terminators, RFC-style double-quote escaping of quotes/comma/newlines. Every row has schema_version `1`. Emit ordered rows: `total_valid_requests` and `invalid_lines` with empty key/percentage; `top_ip` rows with IP key/count; `top_error_url` rows with path key/count; 24 `hour` rows with two-digit key/count/percentage; one `unique_user_agents` row with empty key, distinct count, and share percentage. Non-percentage rows have empty percentage cells. It is a machine pipeline format; spreadsheet consumers must treat keys as text. Renderers escape terminal controls for display without altering machine metric keys.

## Data Model and Persistence
Transient `LogRecord`: `ip: str`, `hour: int` (0–23), `path: str`, `status: int`, `user_agent: str | None`. Aggregation dictionaries map `str → int`; hourly counts are a fixed list of 24 integers. `Summary` carries exactly the output fields above with typed list entries. Counters use Python integers. No rows, indexes, database tables, migrations, disk spill, or durable state exist.

## Runtime, Security, and Distribution
Python 3.11, Click and Rich runtime dependencies; dataclasses and parsing/serialization from stdlib. Planned dev tools: pytest, pytest-cov, build. No auth flow: OS read permission → local process → caller-owned stdout. No credentials, telemetry, outbound calls, or downloaded runtime data. Source logs can contain personal data; avoid logging them and strip queries as specified.

Deployment target is a local laptop/CI shell via `pip install` of a wheel. No Docker or docker-compose structure is needed: there are no services to coordinate. No HTTP endpoints, ports, environment secrets, or cloud deployment. Packaging/publication is separate from this planning session.

## Performance and Verification
Target: 1,000,000,000 uncompressed input bytes in less than 30 seconds wall time on a documented laptop, measured from process start through completed report. Benchmark a regular local file with terminal output redirected, default entry budget, no invalid lines, representative combined records, and total distinct entries below budget. Record CPU, RAM, OS, Python/dependency versions, cache state, input composition, elapsed time, and peak RSS; report median of three warm-cache runs and a cold-cache observation where feasible. Performance is currently unmeasured. Separately test high-cardinality exhaustion and long-line bounds; never conflate an early exit with throughput success.

Parser, metric, schema, CliRunner, subprocess installation, and benchmark checks are detailed in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Requirements live in [PRD.md](PRD.md); scope and trade-offs in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md); execution prompts in [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md); session rules in [CLAUDE.md](CLAUDE.md).
