# Project Architecture: Nginx Lens

## Context and Decision

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Each invocation reads a local stream, holds temporary aggregates, emits a report and discards its state. A database adds persistence and lifecycle work without serving any query between runs. An HTTP API adds network exposure, auth and server operations without serving the local command-line audience. Both exclusions preserve the $0 budget and one-weekend scope.

The approved architecture is a single Python 3.11 process using Click, Rich and dataclasses. There are no runtime subprocesses, workers, authentication, database tables, migrations, HTTP endpoints, server, cloud or Kubernetes resources. Docker and docker-compose are unnecessary: a virtual environment and a pip wheel provide installation. No application environment variables or .env file are required; standard terminal environment conventions may influence Rich's automatic color detection, while --no-color overrides color.

## Architecture Selection and ADR

The explicit stack and obvious solo CLI design invoke the blueprint exception to architecture variants; no decision pause is needed. ADR-001 selects one streaming process. Rejected alternatives: retaining all records (memory scales with file size), a service/index stack (violates scope), parallel parsing (ordering and merge complexity before measurement), and approximate unique counts (would change the metric contract). These are design rationales, not results of an independent review. Adversarial review is deferred to the external harness and has not run in this session.

## Data Flow and Modules

`file/stdin -> bounded line reader -> combined parser -> AggregateState -> Report -> text/JSON/CSV -> stdout`

`diagnostics -> stderr`; all input handles opened by the application close on success or failure; stdin remains caller-owned.

| Planned path | Responsibility |
|---|---|
| pyproject.toml | Python requirement >=3.11, Click/Rich dependencies, nginx-lens entry point |
| src/nginx_lens/cli.py | Click options, input ownership, exit translation |
| src/nginx_lens/reader.py | Bounded binary line reading and UTF-8 decoding |
| src/nginx_lens/parser.py | Anchored combined-log parsing and field validation |
| src/nginx_lens/models.py | RequestRecord, AggregateState, Report dataclasses |
| src/nginx_lens/aggregate.py | Counters, quotas, percentages, deterministic top-10 |
| src/nginx_lens/render.py | Rich, JSON and CSV serializers |
| tests/ | Unit, golden-output, CLI, packaging and guard tests |
| benchmarks/ | Deterministic fixture generator and timed end-to-end runner |

## Input Grammar and Validity

Accept nginx standard combined format: remote address, ident, remote user, bracketed timestamp, quoted request, status, bytes sent, quoted referrer and quoted User-Agent. Validate IPv4/IPv6 using ipaddress and canonicalize IP spelling. Validate timestamp as `%d/%b/%Y:%H:%M:%S %z` with an explicit English month map independent of system locale. Validate request as METHOD, request-target, HTTP/version; status is an integer 100–599; byte count is a nonnegative integer or `-`. Ignore ident, remote user, referrer and bytes after syntax validation. Quoted fields support nginx `\xHH` escapes; decode those to bytes before strict UTF-8 validation. Do not apply URL percent decoding. Reject unsupported quoting and malformed escapes.

Support LF, CRLF and the final unterminated line. Input is UTF-8 after escape decoding; invalid encoding, blank lines, missing fields and oversized lines count as malformed. The reader caps each physical line at 64 KiB including newline, drains the remainder of an oversized line and increments skipped_lines once. No raw log lines appear in diagnostics. Custom log_format, combined logs without User-Agent, common-only format, gzip autodetection, follow mode and multiple input arguments are outside MVP. For live producers, stdin processes incrementally but the final report is emitted only at EOF.

## Metric Contract

- total_valid_requests counts every successfully parsed record. skipped_lines counts invalid physical lines and is excluded from every metric denominator.
- top_ips counts all valid requests per canonical IP. Sort by count descending, then canonical IP string ascending; take up to ten.
- top_error_urls counts valid requests whose status is 400–599, keyed by the request-target exactly as logged (including query string). 4xx and 5xx contribute to one combined error ranking. No host/path normalization or query stripping occurs. Sort by count descending then target string ascending; take up to ten. A URL with no errors never appears.
- Convert each timestamp to UTC; bucket by hour-of-day 00–23 across all dates. Emit all 24 buckets. Hourly request distribution is a percentage: `100 × hourly_request_count / total_valid_requests`.
- Unique User-Agent share is `100 × distinct_nonmissing_user_agents / total_valid_requests`. Count decoded, case-sensitive full User-Agent strings exactly. Empty and `-` agents represent missing values and do not enter the distinct set; their requests still enter the denominator. This is diversity per request, not browser market share or unique visitors.
- With zero valid requests, all percentages are 0.0, rankings empty, and all hourly counts zero. Empty input exits 0; all-malformed nonempty input emits the zero report and exits 1.
- Counts and distinct cardinality are integers. JSON and CSV percentages round to six decimal places; text shows two. Rounding may make the displayed hourly sum differ slightly from 100. Internal calculation uses unrounded counts.

## Exactness and Resource Limits

Streaming does not imply constant memory for exact key counts. State is O(Uip + Uerror-url + Uua + 24); input bytes are never retained wholesale. Default max_unique is 250000 entries shared across the IP map, error-URL map and UA set. The same string in separate namespaces consumes separate entries. Default max_key_bytes is 67108864, the sum of UTF-8 bytes of unique stored keys across these namespaces. Before adding any new keys for a record, calculate all quota deltas and reject the record atomically if either limit would be exceeded. Duplicate keys do not consume quota again; hitting a limit exactly is allowed. Quotas are positive CLI integers and can be lowered or raised explicitly. This is an exact counter with explicit exhaustion, never silent truncation, eviction or approximation.

Exhaustion exits 4, writes a concise diagnostic to stderr, and emits no report. Finalization and serialization happen only after successful EOF; fatal errors produce no successful report. Small per-record bounded temporary storage is allowed. Default quotas are safeguards, not a proven RSS bound; Python object overhead must be measured. Runtime MemoryError is a resource/I/O failure, exit 3. No disk spill or persisted cache is used.

## CLI Interface

### Commands and Options

`nginx-lens [OPTIONS] [INPUT]` analyzes a single source. INPUT is a regular readable file or `-`; omission means stdin. No recursive directories or implicit globs. `nginx-lens --help` and `nginx-lens --version` exit 0 without reading input.

| Option | Default | Contract |
|---|---|---|
| --json | off | Emit one JSON object |
| --csv | off | Emit normalized CSV with one header |
| --no-color | off | Disable text colors explicitly |
| --max-unique INTEGER | 250000 | Positive total distinct-entry ceiling |
| --max-key-bytes INTEGER | 67108864 | Positive total stored-key UTF-8 byte ceiling |

--json and --csv are mutually exclusive; conflicting options or invalid numbers exit 2 before input is read. There is no output-file option: use redirection. --no-color is harmless with machine formats. Text colors appear automatically only on a TTY; redirected text and machine output contain no ANSI sequences. Escape Rich markup and controls in all untrusted strings; output must not execute terminal escape sequences.

### Outputs

stdout contains exactly one final report. stderr contains bounded aggregate diagnostics (counts/reasons, no raw records); never mix progress text into stdout. On malformed records, continue processing, emit report with skipped count, warn on stderr and exit 1. Consumers requiring complete data must check the exit code.

JSON schema version 1 uses this complete shape: schema_version (integer 1), total_valid_requests (integer), skipped_lines (integer), top_ips (array of {ip: string, request_count: integer}), top_error_urls (array of {url: string, error_count: integer}), hourly_requests (24 objects {hour_utc: integer 0–23, request_count: integer, percentage: number}), user_agents ({unique_count: integer, unique_share_percentage: number}). No dynamic timestamps or input paths are needed in the report. JSON strings escape control characters.

CSV is UTF-8, RFC-style quoting via the standard csv module, LF record terminators. Header: `schema_version,section,key,count,percentage`. All rows have schema_version=1. Emit summary rows with keys total_valid_requests and skipped_lines, then top_ips and top_error_urls rows in ranking order, then hourly_requests rows with two-digit UTC hour keys, then user_agents row with key unique. count contains the relevant integer; percentage is empty except hourly_requests and user_agents. Missing metric values use empty fields, never localized numbers. IP/URL keys are raw data quoted by CSV rules; spreadsheet users must import as text to avoid formula interpretation. Do not mutate raw keys just for spreadsheet display.

### Exit Codes

The complete contract is 0/1/2/3/4:

| Code | Meaning | stdout |
|---|---|---|
| 0 | Complete valid analysis, including empty input; help/version | Report, or requested help/version |
| 1 | Completed with malformed lines skipped | Partial-data report with skipped_lines |
| 2 | CLI usage error | No report |
| 3 | Input/output/resource failure, including unreadable file, interrupted processing, broken pipe or MemoryError | No valid report; a broken output pipe may have received a prefix |
| 4 | unique-cardinality exhaustion (entry or key-byte quota) | No report |

Usage errors are resolved before analysis; fatal runtime failures 3/4 override pending skipped-line exit 1. The first fatal error aborts processing. KeyboardInterrupt maps to 3 with a concise message. Never advertise truncated stdout from an output failure as usable JSON/CSV.

## Performance and Verification

Target: 1 GB = 1,000,000,000 input bytes in <30 seconds end-to-end and <=512 MiB peak RSS on a recorded laptop profile (Python 3.11, CPU model, cores, RAM, OS, storage, dependency versions). This is an unverified target, not a current capability. Use an uncompressed regular file, <=100000 aggregate unique entries, <=32 MiB distinct-key bytes, mixed statuses and agents, one process and JSON output to a local sink. Time from process start through final write, excluding fixture generation. Record cold and warm cache conditions and three runs; all measured runs must meet the target. Separately test stdin equivalence and high-cardinality failure; arbitrary cardinality is not promised to fit.

Golden fixtures cover time-zone day rollover, all status boundaries, duplicate keys, ties, missing UAs, malformed encoding, long lines and zero denominators. Resource tests exercise exact and one-over quotas. Machine format tests independently parse output. See [PRD.md](PRD.md) for acceptance criteria, [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for execution and [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) for prompts.
