# Project Architecture: Nginx Stream Analytics CLI

## 1. Context and Decision

The product is a local Python 3.11 CLI that reads nginx access logs, aggregates four reports in one process, and writes either Rich terminal text, JSON, or CSV. Its target is a representative 1 GB log in under 30 seconds on a documented laptop baseline.

The approved architecture decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema lifecycle, cleanup, security exposure, and installation friction while the requested outputs can be derived during a single sequential scan. Persisting raw or aggregated access-log data would also expand the privacy boundary without improving the one-shot workflow. An HTTP API would require a long-running server, request/authentication semantics, deployment, and network hardening for a tool whose natural contract is files, stdin, stdout, stderr, and exit codes. Local pipeline formats already provide automation without a service.

## 2. Architecture Choice and Alternatives

The choice is obvious under the approved constraints, so no unresolved variant is presented for selection.

### Chosen: Single-process streaming pipeline

- **Approach:** Click opens a file or stdin; a parser yields one typed record at a time; one aggregator updates all metrics; one selected renderer writes the final report.
- **Pros:** minimal installation and operational surface, one input pass, straightforward profiling, no retained logs, natural shell composition.
- **Cons:** exact high-cardinality sets/counters can grow with input diversity; one invocation uses one CPU core; no historical queries.
- **Best for:** local one-off and pipeline analysis up to the measured laptop envelope.
- **Estimated complexity:** Low.

### Rejected: Delegate reporting to GoAccess

- **Gain:** mature parser and performance.
- **Loss:** external binary dependency, less control over exact JSON/CSV contracts, and mismatch with the required Python stack.

### Rejected: Ingestion plus persistent analytics stack

- **Gain:** historical querying, dashboards, distributed ingestion.
- **Loss:** violates the $0/local/no-database/no-server constraints and cannot fit a one-weekend operational footprint.

## 3. System Context

```text
nginx log file ─┐
                ├─> Click command -> line iterator -> parser -> aggregator -> renderer -> stdout
stdin pipeline ─┘                                      │                         │
                                                      └─ malformed counters     └─ text | JSON | CSV
stderr <──────────────────── warnings, diagnostics, and fatal parse/I/O errors ────────────────┘
```

There is one process and no background worker, daemon, telemetry collector, cache, database, socket, or network listener.

## 4. Package and Module Boundaries

```text
src/nginx_stream_analytics/
├── __init__.py        # package version only
├── cli.py             # Click options, streams, exit codes, renderer selection
├── parser.py          # nginx combined-log parsing and parse errors
├── models.py          # frozen LogRecord and report dataclasses
├── aggregate.py       # one-pass mutable aggregation and immutable final report
├── render_text.py     # Rich terminal tables
├── render_json.py     # stable JSON document
└── render_csv.py      # normalized CSV rows
tests/
├── fixtures/          # small hand-auditable nginx logs and golden outputs
├── test_parser.py
├── test_aggregate.py
├── test_cli.py
├── test_renderers.py
└── test_performance.py
```

Dependencies point inward: `cli` coordinates parser, aggregation, and renderers; renderers depend only on report models; aggregation knows nothing about Click, Rich, files, or output formats.

## 5. Runtime Data Model

These are in-memory dataclasses, not database tables.

| Dataclass | Field | Type | Constraint / meaning |
|---|---|---|---|
| `LogRecord` | `ip` | `str` | Non-empty IPv4, IPv6, or recorded nginx client token |
|  | `timestamp` | `datetime` | Parsed timezone-aware nginx timestamp |
|  | `method` | `str` | HTTP method token, retained for future diagnostics |
|  | `url` | `str` | Request target exactly as normalized by the parser contract |
|  | `protocol` | `str` | Request protocol token |
|  | `status` | `int` | 100–599 |
|  | `user_agent` | `str` | Unescaped User-Agent, including `-` when absent |
| `AnalysisReport` | `total_requests` | `int` | Count of valid records |
|  | `malformed_lines` | `int` | Count skipped in lenient mode |
|  | `top_ips` | `tuple[RankedCount, ...]` | At most ten, deterministic ordering |
|  | `top_error_urls` | `tuple[RankedCount, ...]` | At most ten 4xx/5xx URL counts |
|  | `hourly_requests` | `tuple[HourlyCount, ...]` | 24 entries, hours 00–23 in log timestamp timezone |
|  | `unique_user_agents` | `int` | Exact distinct UA count among valid records |
|  | `unique_user_agent_share` | `float` | Distinct UA count / valid request count; `0.0` for no valid records |

Mutable aggregation state contains `Counter[str]` for IPs and error URLs, a 24-element integer list, a `set[str]` for exact User-Agents, and scalar counters. The input line and parsed record become collectible after each update; the complete log is never retained.

### Database schema

Not applicable by design: there are zero tables, migrations, indexes, database credentials, and retained records. Adding any database requires a new architecture decision and PRD scope change.

## 6. Input and Parsing Contract

- Input is read as binary lines from one positional file path or `-`/omitted stdin, then each line is decoded as UTF-8 inside the parser boundary.
- MVP supports nginx's conventional combined access-log shape: remote address, identity/user tokens, bracketed timestamp with numeric offset, quoted request, status, bytes, quoted referrer, and quoted User-Agent.
- Escaped quotes and backslashes inside quoted fields are handled deliberately and covered by fixtures.
- Request targets preserve the path and query string as logged; aggregation keys the full target. This is explicit to avoid silently conflating distinct URLs.
- Hours are taken from each record's timestamp and numeric offset; no host-timezone conversion occurs.
- 4xx/5xx means status 400–599 inclusive.
- Invalid UTF-8 is a malformed line, not a stream-level crash. Lenient mode skips it, increments `malformed_lines`, and continues; `--strict` exits 2 with the line number. No surrogate values enter JSON or CSV.
- Lenient mode also skips syntactically malformed lines, increments `malformed_lines`, and emits a bounded diagnostic summary. `--strict` exits on the first malformed line.
- Blank input produces valid empty reports and exit code 0; I/O failures or strict parse failures produce exit code 2.

## 7. CLI Contract

```text
nginx-stream-analytics [OPTIONS] [INPUT]

INPUT                    File path; `-` or omission reads stdin
--json                   Emit one JSON document
--csv                    Emit normalized CSV rows
--strict                 Fail on the first malformed line
--no-color               Disable terminal color
--version                Print version and exit
--help                   Print usage and exit
```

`--json` and `--csv` are mutually exclusive. Default text uses color only when stdout is a TTY, `--no-color` is absent, and `NO_COLOR` is unset. Machine formats never contain ANSI escapes. Report data goes to stdout; diagnostics go to stderr.

### HTTP API

Not applicable by design: there are zero endpoints, methods, request bodies, response bodies, ports, or API credentials. The public automation interface is the CLI plus the versioned JSON/CSV schemas below.

### JSON schema (version 1)

```json
{
  "schema_version": 1,
  "summary": {"total_requests": 0, "malformed_lines": 0},
  "top_ips": [{"rank": 1, "ip": "192.0.2.1", "count": 4}],
  "top_error_urls": [{"rank": 1, "url": "/missing", "count": 2}],
  "hourly_requests": [{"hour": "00", "count": 0}],
  "user_agents": {"unique_count": 0, "unique_share": 0.0}
}
```

All 24 hourly entries are always emitted. Rankings sort by descending count, then ascending key for deterministic ties. Top-k selection must compare the complete key `(-count, key)` during selection—not select by count and sort afterward—so more than ten equal-count keys produce the ten lexicographically smallest keys regardless of input order. `unique_share` is a ratio in `[0,1]`, not a percentage.

### CSV schema (version 1)

One header is emitted: `schema_version,report,rank,key,count,value`. Each row uses one of `summary`, `top_ip`, `top_error_url`, `hourly_request`, or `user_agent`. Unused cells are empty. This normalized form keeps one valid CSV stream while preserving all report sections.

## 8. Performance and Resource Model

- Complexity is `O(n + u log 10)` time in the number of lines `n` and distinct ranking keys `u`; final top-k selection uses `heapq.nsmallest(10, items, key=lambda item: (-item[1], item[0]))` or a provably equivalent complete comparator.
- Memory is `O(i + e + a)`, where `i`, `e`, and `a` are distinct IP, error-URL, and User-Agent counts. It is independent of total line count but not of cardinality; this limitation must be benchmarked and documented.
- Parser selection is evidence-driven. First microbenchmark the compiled-regex/time parser on at least 100 MiB; parsing must consume no more than 18 seconds of the 30-second 1 GiB budget when linearly projected. If it exceeds that threshold, replace it with a bounded scanner that extracts only IP, hour/offset, request target, status, and User-Agent and avoids per-line `datetime` construction. Both paths must satisfy the same parser fixtures.
- Avoid per-line Click/Rich work; update all metrics in the same loop; render only after EOF. Fields not needed by aggregation must not survive the update.
- Performance acceptance uses a deterministic typical-cardinality 1 GiB fixture, Python 3.11, a stated filesystem-cache policy, wall-clock timing, peak RSS, CPU model, OS, command, file hash, and cardinalities. The target is under 30.0 seconds and peak RSS under 512 MiB.
- A second 1 GiB resource-envelope fixture uses 250,000 distinct IPs, 250,000 distinct error URLs, and 1,000,000 distinct User-Agents, with average URL and User-Agent lengths recorded. It must complete without uncontrolled OOM and with peak RSS under 2 GiB; its time is reported separately from the primary 30-second target. Exceeding this envelope triggers the PRD kill/rescope decision rather than silent approximation.
- A result without hardware, fixture metadata, cardinalities, and peak RSS is not acceptance evidence.

## 9. Security and Privacy

- Logs remain local and are not persisted, transmitted, or used for telemetry.
- Log fields are untrusted data. Before Rich markup escaping, the text renderer converts ESC, CR, C0/C1 controls (except layout created by the renderer), and bidi override/isolate controls into visible escaped notation. Tests assert that untrusted values cannot emit an active ANSI/control sequence. JSON uses JSON escaping and remains the canonical representation of exact values.
- CSV cells rely on standards-compliant quoting. Because spreadsheet applications may evaluate formula prefixes, values beginning with `=`, `+`, `-`, or `@` are prefixed safely and this transformation is documented.
- File paths are opened read-only. The command never follows URLs or executes content from a log.
- Tracebacks are hidden for expected user errors; diagnostics avoid echoing full sensitive log lines by default.
- No authentication mechanism exists because there is no shared service or protected remote boundary. Access control is the local operating system's file and process permissions.

## 10. Configuration and Environment

There is no `.env` file. Supported environment variables are deliberately minimal:

| Variable | Example | Meaning |
|---|---|---|
| `NO_COLOR` | `1` | Disable ANSI color according to the community convention |
| `PYTHONUTF8` | `1` | Optional Python runtime UTF-8 mode; not required on a correctly configured environment |

No secrets are accepted or stored.

## 11. Packaging and Deployment

The deployment target is a user's local Python 3.11 virtual environment or isolated CLI installer such as `pipx`. A wheel and source distribution expose the `nginx-stream-analytics` console script. Release validation installs the wheel into a clean environment and runs `--help`, `--version`, fixtures, and the benchmark.

Docker, Compose, cloud, system services, and Kubernetes are not part of the architecture: they add no value to a stdin/file CLI and conflict with the approved scope.

## 12. Observability and Failure Handling

The command reports elapsed time only with a future diagnostic flag, not in stable machine output. Exit codes are: `0` success (including lenient skips), `2` usage, I/O, or strict parse failure, and `1` unexpected internal failure. Warnings are bounded so a malformed file cannot flood stderr. Broken pipes terminate quietly with the conventional shell behavior.

## 13. Architecture Decision Record (ADR)

### ADR-001: Stateless single-process CLI

- **Status:** Accepted (pre-approved).
- **Decision:** Use one Python process and one input pass, with exact in-memory aggregation and pluggable final renderers.
- **Drivers:** $0 budget, one-weekend delivery, local data, pip installation, and 1 GB/30 s target.
- **Consequences:** No historical queries or horizontal scale; memory follows distinct-key cardinality; local shell composition stays simple.

### ADR-002: Exact User-Agent share

- **Status:** Accepted for MVP.
- **Decision:** Define share as `distinct User-Agent values / valid requests` and compute it exactly.
- **Consequences:** Semantics are clear and testable, but adversarial cardinality can increase memory. Approximation remains P2 and may not replace exact mode without a PRD revision.

### Debate Summary

The architecture was reviewed by the repository's Devil's Advocate role.

**Verdict:** APPROVE WITH CONDITIONS

**Challenges raised and resolutions:**

1. Count-only top-k could choose the wrong members at a ten-item tie boundary. **Resolution:** selection now compares `(-count, key)` and requires a 12-way equal-count test.
2. Regex plus per-line timezone-aware `datetime` creation may miss the 1 GiB/30 s target. **Resolution:** a 100 MiB parser microbenchmark has an 18-second projected parser budget; exceeding it activates a bounded scanner fast path with the same fixtures.
3. Text-stream decoding could raise before lenient parsing sees a line. **Resolution:** input is binary and UTF-8 decoding occurs per line inside strict/lenient accounting.
4. A low-cardinality benchmark would not prove a usable memory envelope. **Resolution:** acceptance now includes explicit typical and high-cardinality 1 GiB profiles, peak-RSS limits, and cardinality metadata.
5. Rich markup escaping alone would not stop terminal control injection. **Resolution:** terminal controls and bidi controls are visibly escaped before markup handling and tested adversarially.

**Alternatives considered and rejected:**

- Database-backed/external aggregation — rejected because it violates the approved stateless local boundary and is unnecessary for the target envelope.
- Approximate User-Agent counting — rejected for MVP because it weakens the exact PRD semantics.
- Full manual scanner from the outset — deferred until the parser microbenchmark demonstrates a need; it adds parsing complexity and fixture burden.

## 14. Traceability

- Product scope and acceptance: [PRD.md](PRD.md)
- Delivery sequence and verification: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- Strategic priorities and risks: [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md)
