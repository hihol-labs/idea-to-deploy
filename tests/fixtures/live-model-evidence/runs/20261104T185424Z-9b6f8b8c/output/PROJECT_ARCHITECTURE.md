# Project Architecture: Nginx Lens

## Context and Decision

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Each invocation reads a finite stream and discards its in-memory state on exit. Persistence adds migrations and lifecycle work without supporting a requirement. File/stdin input and stdout exports satisfy local interaction and automation; an HTTP service would add a process, ports, access control, and operations outside the brief. There is no authentication because no network or shared service exists; local OS file permissions govern access. No credentials or secret configuration are needed.

Single-process modular CLI is the pre-approved architecture. Python 3.11, Click, Rich, and dataclasses are fixed choices. The skill's obvious-choice exception applies: no architecture-selection pause or variants are required. See [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) and [PRD.md](PRD.md).

## Components and Data Flow

`Click → bounded binary input → combined parser → exact aggregator → Report → terminal / JSON / CSV → stdout`

Only one line and aggregate state are retained. Render once at EOF. Stdin is not followed indefinitely by the program; a pipe stays open until its producer closes. No raw log is persisted or sent elsewhere.

| Planned path | Responsibility |
|---|---|
| `src/nginx_lens/cli.py` | Click options, lifecycle, exit mapping, stderr |
| `src/nginx_lens/input.py` | File/stdin ownership and bounded line iteration |
| `src/nginx_lens/parser.py` | Strict combined grammar, escapes, timestamp and status validation |
| `src/nginx_lens/models.py` | Dataclass contracts |
| `src/nginx_lens/aggregate.py` | Counters, unique budget, deterministic rankings |
| `src/nginx_lens/render.py` | Rich, JSON and CSV serializers |
| `tests/` | Unit fixtures, subprocess and golden-format tests |
| `benchmarks/` | Deterministic generator and measurement runner |

## CLI Interface

### Commands, Options, and Inputs

`nginx-lens [OPTIONS] [INPUT]` analyzes one file. Omitted INPUT or literal `-` reads binary stdin. Example: `nginx-lens access.log --json`; pipeline: `cat access.log | nginx-lens --csv`.

| Option | Contract |
|---|---|
| `--json` | One UTF-8 JSON object on stdout |
| `--csv` | One UTF-8 long-form CSV table on stdout |
| `--no-color` | Disable ANSI color in terminal mode |
| `--max-unique INTEGER` | Positive combined entry limit, default 1000000 |
| `--help` | Print help, exit 0 without consuming input |
| `--version` | Print installed package version, exit 0 |

`--json` and `--csv` together are usage error 2. No subcommands, database URL, API endpoint, `.env`, custom formats, multiple-file merge, gzip, recursion, or output-file overwrite option in MVP. Shell redirection can save stdout. `NO_COLOR` when present disables terminal color; non-TTY stdout disables color automatically; `--no-color` always wins. Structured formats never contain ANSI codes. No other application environment variables.

### Outputs

Terminal output contains processed/valid/malformed totals, top IP counts, top URL error counts with 4xx and 5xx breakdowns, 24 UTC hour rows with count and percentage, and unique-UA count and share. Rich must treat field text as literal data, disable markup/highlighting for it, and escape control characters. Rank lists contain at most ten rows each.

JSON schema version 1 has these keys and types:

| Key | Value |
|---|---|
| `schema_version` | integer 1 |
| `total_lines`, `total_valid_requests`, `malformed_lines` | nonnegative integers |
| `top_ips` | array of `{ip: string, count: integer}` |
| `top_error_urls` | array of `{url: string, errors_4xx: integer, errors_5xx: integer, total_errors: integer}` |
| `hourly_requests` | array of `{hour_utc: integer, count: integer, percentage: number}`, hours 0–23 |
| `unique_user_agents` | `{count: integer, percentage: number}` |

CSV header is exactly `section,key,count,errors_4xx,errors_5xx,percentage`. Row order: summary keys `total_lines`, `total_valid_requests`, `malformed_lines`; `top_ips`; `top_error_urls`; `hourly_requests` keys `00`–`23`; `unique_user_agents` key `distinct`. Each row has six columns. Summary and IP rows use count only; URL rows use count=total_errors and both error columns; hourly and UA rows use count and percentage. Irrelevant cells are empty, not zero. CSV uses standard quoting, newline terminators, and literal field contents; consumers should import it as data, not evaluate cells as spreadsheet formulas.

Numbers are rounded half-even to two decimals only when rendering percentages, with unrounded integer counts retained. JSON percentages are numbers; CSV/terminal percentages display two decimal places. Zero denominators produce zero. Sorting is count descending then key ascending by Python Unicode code-point order; URL ranking uses total_errors. No sorting depends on input order. Stderr contains a summary of malformed input without raw log lines. Stdout contains only the selected report.

### Exit Codes

| Code | Meaning |
|---|---|
| 0 | Completed report with no malformed lines; includes empty input and help/version |
| 1 | Operational failure: read/write/encoding failure, broken pipe, or unexpected internal failure |
| 2 | Invalid CLI usage or option value |
| 3 | Report completed with malformed lines skipped, including all-malformed input |
| 4 | unique-cardinality exhaustion: a new distinct key would exceed `--max-unique`; no report emitted |

Precedence: validate options before opening input (2); fatal runtime outcomes (1 or 4, first encountered) suppress report generation and supersede malformed status (3). On output-write failure, partial stdout may already exist; it is invalid and exit 1 is authoritative. User interruption maps to 1. Never let Click's default broken-pipe handling turn this failure into success. In-process input/limit failures occur before rendering, so stdout stays empty. No partial or approximate success on code 4.

## Input Format and Parsing

Support nginx standard combined log fields: remote address, ident, remote user, bracketed timestamp, quoted request, status, byte count, quoted referer, quoted User-Agent, and no trailing fields. Remote address must be an IPv4 or IPv6 literal, canonicalized with `ipaddress.ip_address`; ident/user are consumed but not retained. Validate numeric status 100–599 and bytes as nonnegative decimal or `-`. Timestamp format is `dd/Mon/yyyy:HH:mm:ss ±HHMM`, with English month tokens and a valid calendar date/offset. Convert to UTC before selecting hour. Referer is parsed but not stored. Request is either `-` (URL key `-`) or method, request-target, and HTTP/version separated by spaces. Request-target must be an origin-form path starting `/` or literal `*`; unsupported absolute-form/CONNECT targets make the line malformed. Store method/version only during parsing.

Quoted fields support nginx `\xHH`, escaped quote and escaped backslash; reject truncated/unsupported escapes and unterminated quotes. Decode the physical line as strict UTF-8; invalid bytes count as malformed. Remove LF and optional preceding CR. Last line without LF is processed. Empty lines are malformed. The reader consumes at most 64 KiB per physical line including terminator; drain oversized lines in bounded chunks and count each once as malformed. Avoid splitting on arbitrary whitespace or loading all input.

Normalize request-target by removing the first `?` and the remainder. Preserve case, percent escapes, and trailing slash; do not percent-decode or normalize dot segments. Thus `/health?a=1` and `/health?a=2` share `/health`, while `/Health` differs. Empty or `-` User-Agent is missing; all other decoded values are compared exactly without case folding. Raw query parameters and referers are discarded.

## In-Memory Data Contracts

No database tables, indexes, migrations, API endpoints, auth flows, or Docker Compose are applicable. The following typed records replace persistence and HTTP models:

| Dataclass | Fields and constraints |
|---|---|
| `ParsedRequest` | `ip: str`, `url: str`, `status: int`, `hour_utc: int` (0–23), `user_agent: str | None`; validated before aggregation |
| `UrlErrors` | `errors_4xx: int`, `errors_5xx: int`; total is their sum |
| `AggregateState` | `total_lines: int`, `valid: int`, `malformed: int`, `ip_counts: dict[str,int]`, `url_errors: dict[str,UrlErrors]`, `hour_counts: list[int]` length 24, `user_agents: set[str]`, `unique_entries: int` |
| `Report` | Immutable snapshot of totals, ranked rows, hourly rows, unique-UA result; one shared input for every renderer |

Top IPs count all valid requests. Top URLs count only statuses 400–599, ranking the union of 4xx and 5xx rather than independent lists. Successful and redirect requests do not create URL keys. Hourly request distribution is the percentage `100 × hourly_request_count / total_valid_requests`, aggregated across all dates by UTC hour-of-day. Missing hours appear with zero. Unique-UA share is `100 × distinct_nonmissing_user_agents / total_valid_requests`; it is not a bot score or the share of requests made by rare agents. Missing agents contribute to valid requests but not the set. Empty/all-malformed input yields empty rankings and zero-valued hour and UA summaries.

## Cardinality and Performance

Streaming does not imply constant memory for exact distinct counts. Space is O(I + E + U + 24), where I=distinct IPs, E=distinct error URL paths, U=distinct nonmissing agents. The budget counts the sum of entries in those three namespaces: identical strings in two namespaces consume two entries. Default combined limit is 1000000. Before mutating a valid record's state, calculate its new keys; if `unique_entries + new_keys > max_unique`, raise cardinality exhaustion and exit 4 with only stderr. Exactly reaching the limit succeeds; repeated keys at the limit continue. `--max-unique` permits deliberate adjustment, not automatic eviction. No approximate counters, spill files, database, or truncation.

The budget bounds entry count, not exact bytes: long keys increase RAM. Lines have a size bound; benchmark RSS is still a release requirement. Users can reduce the cap for constrained hosts. Top-ten extraction uses `heapq.nsmallest` with key `(-count, key)` rather than sorting every key; time is O(bytes + (I+E) log 10), excluding timestamp and hashing constants. Release target: 1 GB decimal in under 30 seconds on a recorded laptop, with at most 512 MiB peak RSS on a representative bounded-cardinality fixture. This is a target, not a measured capability.

Benchmark fixture: exactly 1,000,000,000 bytes of complete valid combined-format records, 10000 IPs, 10000 error paths, 1000 agents, varied statuses and offsets; deterministic seed. Adjust valid field padding to reach the byte size without a malformed tail. Measure file → JSON → OS null sink, including parsing, aggregation and serialization, excluding generation/install. Record CPU, RAM, OS, Python/dependency versions, fixture size/cardinalities, storage, cache conditions, wall time and peak RSS for three runs; each must meet the target. A separate unbounded-uniqueness case must exit 4 and produce no stdout. Do not claim arbitrary 1-GB inputs will fit the default key budget.

## Packaging, Local Installation, and Operations

Use `pyproject.toml` with setuptools, Python >=3.11, runtime Click and Rich, and console entry point `nginx-lens = nginx_lens.cli:main`. Test on Python 3.11 as the baseline. Dev dependencies include pytest, coverage tooling and build. Record resolved versions in benchmark evidence. Local wheel installation is the delivery target; no hosted deployment, container, daemon, Kubernetes, database provisioning, or release upload. Publishing later requires explicit human approval.

## Architecture Decision Record (ADR)

ADR-001: keep one synchronous process and exact capped in-memory structures. This minimizes packaging and operational work for one weekend. Multiprocessing is deferred because splitting stdin, merging exact distinct sets, and transferring large counters complicate correctness; revisit only if profiling proves a need. Persistent indexing is rejected because reports have no cross-run history requirement. Approximate sketches are rejected because exported counts must be exact. Query stripping reduces accidental cardinality and avoids retaining query values; path/UA/IP fields may still be sensitive and remain local.

Adversarial review is reserved for a separate fresh external harness session. No Devil's Advocate or independent reviewer ran here, and no verdict or review artifact is supplied by this document.

Verification and implementation sequencing: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Operator examples: [README.md](README.md). Agent prompts and project rules: [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md), [CLAUDE.md](CLAUDE.md).
