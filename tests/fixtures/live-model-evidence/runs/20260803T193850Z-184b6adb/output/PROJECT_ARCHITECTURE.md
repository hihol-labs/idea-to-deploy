# Project Architecture: nginx-log-top

## Architecture Drivers

- Local Python 3.11 CLI, pip-installable, delivered in one weekend at $0.
- One-pass processing of files or stdin; target 1 GB in under 30 seconds on a declared laptop.
- Four reports: top-10 IPs, top-10 4xx/5xx URLs, hourly distribution, and unique User-Agent share.
- Human-readable colored output by default; deterministic JSON and CSV for pipelines.
- Exact approved boundary: **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema lifecycle, disk amplification, cleanup, and state semantics to an analysis that can be completed in one pass and discarded. An HTTP API would require a long-running process, input-upload security, networking, authentication decisions, and operations without improving the local incident-response workflow. The CLI can already compose with files, pipes, cron, and shell tooling.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended and approved)

- **Approach:** Click invokes a line iterator; a parser emits immutable dataclass records; one aggregator updates counters; a selected renderer writes the final snapshot.
- **Pros:** One pass, low overhead, easy local installation, clear test seams, no operational dependencies.
- **Cons:** Exact high-cardinality sets consume memory; one CPU-bound process does not use all cores.
- **Best for:** The specified 1 GB local analysis and weekend scope.
- **Estimated complexity:** Low.

### Variant B: Multi-process chunk analysis

- **Approach:** Seekable files are partitioned, worker processes aggregate chunks, and a coordinator merges summaries.
- **Pros:** Can use multiple CPU cores.
- **Cons:** Complicated newline boundaries, stdin cannot be partitioned, merge logic and startup overhead threaten weekend delivery.
- **Best for:** Proven CPU bottlenecks on much larger seekable files.
- **Estimated complexity:** Medium.

### Variant C: Shell pipeline with focused commands

- **Approach:** Separate commands emit normalized rows composed with sort/uniq tools.
- **Pros:** Very small Python core and familiar Unix composition.
- **Cons:** Repeated passes, platform-dependent behavior, weaker unified error/output contract.
- **Best for:** Expert-only exploratory tooling rather than this packaged product.
- **Estimated complexity:** Low to medium.

### Recommendation

Variant A is selected because the user pre-approved the obvious single-process architecture. It minimizes delivery and operational risk while leaving parsing, aggregation, and rendering independently testable. Variant B is a post-MVP option only if profiling proves it necessary.

## System Context and Data Flow

```text
file path / stdin
       |
       v
buffered text line iterator
       |
       v
CombinedLogParser -> ParseResult(valid record | malformed reason)
       |                         |
       v                         +--> diagnostic counters
StreamingAggregator
  | Counter(IP)
  | Counter(error URL)
  | 24 hourly buckets
  | set(User-Agent) + total valid requests
       |
       v
ReportSnapshot dataclasses
       |
       +--> Rich terminal renderer
       +--> JSON renderer
       `--> normalized CSV renderer
```

The input is never loaded wholesale. Peak memory is `O(distinct IPs + distinct error URLs + distinct User-Agents)` because exact top-10 and exact unique-agent semantics require cardinality state. Hour buckets are constant-size. This limit must be exposed in documentation and measured with a high-cardinality fixture.

## Component Boundaries

| Planned path | Responsibility | Must not do |
|---|---|---|
| `src/nginx_log_top/cli.py` | Click command, option validation, stream ownership, exit mapping | Parse log grammar or format reports |
| `src/nginx_log_top/models.py` | Frozen dataclasses for records, diagnostics, report snapshot | Perform I/O |
| `src/nginx_log_top/parser.py` | Parse supported combined-log lines, timezone-aware timestamps, statuses, URLs, User-Agents | Aggregate or print |
| `src/nginx_log_top/aggregate.py` | Update bounded/declared state and finalize deterministic rankings | Know Click or output encoding |
| `src/nginx_log_top/render/terminal.py` | Rich tables and warnings | Change metric values |
| `src/nginx_log_top/render/json.py` | Stable JSON document | Emit ANSI styling |
| `src/nginx_log_top/render/csv.py` | Stable normalized CSV rows | Emit locale-dependent numbers |
| `src/nginx_log_top/errors.py` | Domain exceptions and exit-code mapping | Swallow unexpected failures |

## Domain and Parsing Contract

The MVP supports nginx's conventional combined access-log shape:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

`AccessRecord` fields are: `client_ip: str`, `timestamp: datetime` (timezone-aware), `method: str | None`, `target: str | None`, `protocol: str | None`, `status: int`, `bytes_sent: int | None`, `referer: str | None`, and `user_agent: str | None`. A `-` byte count maps to `None`; quoted `"-"` for request, referer, or User-Agent maps to absent fields. A missing request does not invalidate an otherwise valid record, but it cannot contribute to error-URL ranking.

The supported lexical grammar is normative:

- Fields are separated by one or more ASCII spaces only where the combined format places separators. The client address is an opaque nonempty token, so both IPv4 and IPv6 text are accepted without DNS or IP normalization.
- Timestamp must match `%d/%b/%Y:%H:%M:%S %z`; status is exactly three ASCII digits; bytes is an unsigned decimal integer or `-`.
- Each quoted field terminates only at an unescaped quote. It accepts `\\`, `\"`, and `\xHH` (exactly two hexadecimal digits), decodes them once, and rejects unknown or truncated escapes. Empty quoted referer/User-Agent values map to absent values.
- A non-missing request is split on ASCII spaces: first token is method, last token matching `HTTP/<digits>.<digits>` is protocol, and all intervening text is the target. Fewer than three components, an empty target, or an invalid protocol makes the line malformed.
- The decoded target, including query string, is retained without URL decoding, case folding, or query normalization. Each physical record is capped at 64 KiB; a longer line is consumed, counted malformed, and never retained.

A malformed line increments `malformed_lines` and processing continues. If zero valid records remain, the command fails with exit 4 and emits no success report. Parser conformance fixtures cover IPv4, IPv6, empty/missing fields, escaped quote/backslash/hex, query strings, unusual target spaces, missing request, invalid/truncated escapes, invalid timestamps/status/bytes, overlong records, and truncated lines.

Hourly distribution uses the hour `00` through `23` from each record's logged local timestamp/offset, not the machine timezone. All 24 buckets are emitted, including zero counts. Error URLs include status `400..599`. Rankings sort by count descending, then key ascending for deterministic ties. Top lists contain at most 10 entries.

“Share of unique User-Agents” is explicitly:

```text
unique_user_agent_share_percent = distinct_nonempty_user_agents / valid_requests * 100
```

It is `0.0` only for an empty internal snapshot; the public CLI rejects zero-valid-record input. Missing/empty User-Agents are excluded from the numerator but their valid records remain in the denominator. The output includes numerator and denominator to make the percentage auditable.

## CLI Interface

### Commands and invocation

```text
nginx-log-top [OPTIONS] [INPUT]
python -m nginx_log_top [OPTIONS] [INPUT]
```

`INPUT` is an optional nginx access-log path. Omitted input or `-` reads stdin. Exactly one input stream is processed per invocation. Compressed files, directories, URLs, glob expansion, tail/follow mode, and multiple input files are out of scope.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one UTF-8 JSON object; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit UTF-8 CSV with header; mutually exclusive with `--json` |
| `--no-color` | flag, false | Disable ANSI styling in terminal mode; ignored as a no-op for JSON/CSV |
| `--version` | flag | Print version and exit 0 without reading input |
| `--help` | flag | Print Click help and exit 0 |

Unknown options, extra arguments, and `--json --csv` are usage errors. Terminal color is enabled only when terminal mode is selected, stdout is a TTY, `--no-color` is absent, and the conventional `NO_COLOR` environment variable is absent.

### Outputs

- **Terminal:** four labeled Rich sections plus a diagnostics line when malformed records were skipped. Data output goes to stdout; errors and warnings go to stderr.
- **JSON:** one compact object with `schema_version`, `summary`, `top_ips`, `top_error_urls`, `hourly_requests`, and `diagnostics`. Arrays remain ordered by the ranking contract. Keys are emitted in the example order, Unicode is UTF-8 rather than ASCII-escaped, separators are `,` and `:`, and the document ends with one LF. No ANSI bytes are permitted.
- **CSV:** header `report,key,count,value` and the exact row types below. The Python `csv` module's `excel` dialect supplies RFC 4180 quoting and CRLF record endings. UTF-8 is emitted without BOM. No ANSI bytes are permitted.

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Analysis completed; malformed lines may have been skipped and reported |
| 2 | Click usage/option error |
| 3 | Input cannot be opened, decoded, or read |
| 4 | Input contains no valid supported log records |
| 1 | Unexpected internal failure |

Broken pipe is handled quietly, without a traceback, and treated as a normal pipeline termination (0). Partial JSON/CSV must never be emitted for known input-open failures or zero-valid-record input because rendering occurs only after aggregation finalizes.

## Output Schema Examples

The JSON field contract is normative: `schema_version`, counts, and hours' `count` are integers; IP/URL/hour are strings; the share is a JSON number rounded once to two decimal places using decimal half-up; none of these fields are nullable. `hourly_requests` always has 24 entries. Diagnostics counts are included even when zero.

```json
{
  "schema_version": 1,
  "summary": {"valid_requests": 100, "unique_user_agents": 25, "unique_user_agent_share_percent": 25.0},
  "top_ips": [{"ip": "192.0.2.1", "count": 9}],
  "top_error_urls": [{"url": "/missing", "count": 4}],
  "hourly_requests": [
    {"hour": "00", "count": 2}, {"hour": "01", "count": 0},
    {"hour": "02", "count": 0}, {"hour": "03", "count": 0},
    {"hour": "04", "count": 0}, {"hour": "05", "count": 0},
    {"hour": "06", "count": 0}, {"hour": "07", "count": 0},
    {"hour": "08", "count": 0}, {"hour": "09", "count": 0},
    {"hour": "10", "count": 0}, {"hour": "11", "count": 0},
    {"hour": "12", "count": 0}, {"hour": "13", "count": 0},
    {"hour": "14", "count": 0}, {"hour": "15", "count": 0},
    {"hour": "16", "count": 0}, {"hour": "17", "count": 0},
    {"hour": "18", "count": 0}, {"hour": "19", "count": 0},
    {"hour": "20", "count": 0}, {"hour": "21", "count": 0},
    {"hour": "22", "count": 0}, {"hour": "23", "count": 0}
  ],
  "diagnostics": {"total_lines": 103, "malformed_lines": 3}
}
```

CSV row contract and order:

| Order | `report` | `key` | `count` | `value` |
|---:|---|---|---|---|
| 1 | `summary` | `valid_requests` | base-10 integer | empty |
| 2 | `summary` | `unique_user_agents` | base-10 integer | empty |
| 3 | `unique_user_agent_share` | `percent` | empty | fixed two-decimal half-up number, no `%` |
| 4.. | `top_ip` | raw decoded IP string | base-10 integer | empty |
| next | `top_error_url` | raw decoded target string | base-10 integer | empty |
| next 24 | `hourly_request` | zero-padded `00`..`23` | base-10 integer | empty |
| final two | `diagnostic` | `total_lines`, then `malformed_lines` | base-10 integer | empty |

Top rows follow their deterministic ranking. Empty cells are empty strings, never `null`, `-`, or whitespace. Standard CSV quoting preserves commas, quotes, CR, and LF in machine values. Golden tests parse the CSV back and compare typed logical rows; byte-golden tests fix header, order, encoding, and record endings. Any incompatible JSON/CSV change increments `schema_version` (and introduces an explicit CSV version policy before release).

## Persistence, API, Authentication, and Deployment

- **Database schema:** intentionally none. There are zero tables, migrations, indexes, files of persisted state, or caches. This is an explicit architecture decision, not an omitted design.
- **HTTP/API endpoints:** intentionally none. There are zero methods, paths, request bodies, response bodies, ports, or listeners. JSON/CSV stdout is the machine interface.
- **Authentication/authorization:** not applicable because the process has no remote boundary or identity model. File permissions and invoking-user privileges are inherited from the OS; the CLI never elevates them.
- **Docker/compose:** intentionally absent. pip installation into a virtual environment is the deployment model. A container would add no required isolation or service packaging.
- **Deployment target:** a local Linux/macOS shell or compatible Python 3.11 environment on an engineer's laptop/workstation. Windows support may be validated later but is not a release blocker unless added to the PRD.
- **Environment variables:** `NO_COLOR` is honored by presence. No secrets or product-specific environment configuration exists.

## Performance and Resource Strategy

- Use buffered iteration over a text stream; never call `read()` for the whole file.
- Compile parsing expressions once and keep hot-path objects minimal.
- Update all metrics in the same pass.
- Use `collections.Counter` for exact frequencies, a fixed 24-element list for hours, and a set for exact User-Agents.
- Finalize and sort only after EOF; use `heapq.nsmallest`/equivalent ranked selection if profiling shows full sorts material.
- Benchmark a content-hashed 1 GB fixture using `/usr/bin/time` and record elapsed time and peak RSS. Include realistic and adversarial high-cardinality profiles.
- Do not promise that the target holds on every laptop; acceptance is tied to the declared reference environment.

The release benchmark is executable through a checked-in manifest recording CPU model/core count, RAM, storage type, OS/kernel, Python patch version, package version/candidate hash, fixture generator parameters, fixture SHA-256, byte/line counts, distinct IP/error-URL/User-Agent counts, maximum field length, and command. Acceptance uses a local laptop with at least 4 physical cores, 16 GB RAM, and SSD storage; runs the installed wheel end-to-end (startup, read, parse, aggregate, and JSON serialization) three times after one unmeasured warm-up; requires the median elapsed time below 30.0 seconds, every measured run below 33.0 seconds, and peak RSS below 512 MiB. Output is redirected to a real file on the same SSD and validated afterward. The result states that this is a warm-cache benchmark and is not generalized to other machines.

The guaranteed exact-metric envelope for the 1 GB release corpus is: at most 1,000,000 distinct IPs, 250,000 distinct error targets, 250,000 distinct nonempty User-Agents, and 64 KiB per record, within the 512 MiB peak-RSS gate. Inputs outside that cardinality envelope are best-effort and explicitly not covered by the performance guarantee. A caught `MemoryError`/allocation failure maps to exit 1 with a resource-exhaustion diagnostic, but the documentation warns that an OS OOM kill cannot be converted into a CLI exit contract. If real adoption needs a larger exact envelope, an opt-in external-sort/spill design requires a new ADR and cleanup/security contract; approximation is never introduced silently.

## Error Handling and Security

Log contents are untrusted data. The CLI does not evaluate escapes, invoke a shell, fetch URLs, or interpolate log values into terminal markup. Terminal display first replaces C0/C1 controls, DEL, ESC, bidi overrides/isolates, and other Unicode format controls with visible `\\u{HEX}` tokens, then applies Rich markup escaping. CR, LF, and TAB in a field therefore cannot move the cursor or forge rows. This transformation is terminal-only; JSON/CSV retain decoded logical values through their encoders/quoting. Tests cover ESC, CR, LF, TAB, DEL, C1, and bidi controls. Error messages include a line number and a bounded reason, not entire potentially sensitive log lines. Tracebacks are suppressed for expected errors and available only to developers through test/debug tooling, not a public MVP option.

## Architecture Decision Record (ADR)

### ADR-001: Local stateless single-process pipeline

- **Status:** Accepted (pre-approved).
- **Decision:** Use Variant A with no persistence and no network listener.
- **Consequences:** Minimal installation/operations and simple pipeline composition; exact cardinality state can grow and multi-core speedup is deferred.

### ADR-002: Exact metrics in MVP

- **Status:** Accepted.
- **Decision:** Exact counters and exact distinct User-Agent set.
- **Consequences:** Results are auditable; memory scales with distinct values and must be benchmarked.

### ADR-003: One normalized CSV stream

- **Status:** Accepted.
- **Decision:** Use a discriminator column rather than several incompatible tables.
- **Consequences:** Easy piping and one header; consumers filter by `report`.

### Debate Summary

The architecture was reviewed by the repository-local Devil's Advocate agent.

**Verdict:** APPROVE WITH CONDITIONS; all five conditions were incorporated before blueprint acceptance.

**Challenges raised:**

1. Ambiguous parsing grammar → **Resolution:** added normative separators, quoted escapes, request splitting, absent-field semantics, line cap, and conformance corpus.
2. Terminal control-sequence injection → **Resolution:** added terminal-only control/format sanitization before Rich escaping and named security cases.
3. Unbounded exact-cardinality resource risk → **Resolution:** established cardinality/RSS envelope, best-effort boundary, allocation-failure behavior, and post-MVP exact spill option.
4. Non-executable 1 GB/30 s claim → **Resolution:** defined benchmark manifest, reference class, measured runs, elapsed/RSS thresholds, and scope of the claim.
5. Partially ambiguous JSON/CSV → **Resolution:** specified types, rounding, ordering, empty values, encoding/newlines, complete 24 buckets, and the CSV row matrix.

**Alternatives considered and rejected:**

- Multiprocess chunking — rejected for stdin incompatibility and weekend complexity without profiling evidence.
- Approximate cardinality — rejected because it silently weakens auditable MVP semantics.
- External spill/sort in MVP — rejected because cleanup, disk, and error semantics exceed the validated 1 GB envelope; retained as an ADR-triggered future option.

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the dependency order and [PRD.md](PRD.md) for acceptance criteria.
