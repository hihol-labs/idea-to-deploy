# Project Architecture: nginx-stream-report

## Architecture Drivers

- Local Python 3.11 CLI for DevOps/SRE users.
- Stream a 1 GB nginx access log in under 30 seconds on a documented laptop baseline.
- Produce top-10 IPs, top-10 URLs with 4xx/5xx responses, hourly percentages, and unique User-Agent share.
- Default to colored terminal output and support deterministic JSON and CSV for pipelines.
- Remain installable with pip, open source, stateless, and operable at $0.
- Retain only aggregation state, never raw lines or full parsed-request history.

## Architecture Decision

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Both constraints are correct here. A database would add schema, lifecycle, I/O, cleanup, privacy, and deployment costs without helping a one-shot summary; the input log is already the record of truth and all required aggregates can be produced in one pass. An HTTP API would turn a local utility into a long-running service with authentication, request limits, upload handling, and attack surface. File/stdin input and stdout/stderr output compose directly with established Unix and incident-response workflows.

The selected design is a single-process, layered pipeline: Click validates the command, an iterator reads lines, a parser produces immutable dataclass records, an aggregator updates counters and a bounded exact User-Agent set, and one renderer emits the final report.

## Architecture Variants

### Variant A: Layered single-process stream (selected)

- **Approach:** One Python process with separate CLI, parser, aggregation, and rendering modules.
- **Pros:** Minimal runtime overhead; easy unit testing; one-pass I/O; clear contracts; pip-native.
- **Cons:** CPU work remains single-core; exact high-cardinality state still consumes memory up to its cap.
- **Best for:** Local one-off files and stdin pipelines up to the stated laptop target.
- **Estimated complexity:** Low.

### Variant B: Minimal single-module script

- **Approach:** Parsing, aggregation, and printing in one file.
- **Pros:** Fastest initial authoring and slightly less call overhead.
- **Cons:** Renderer/schema coupling, poor test seams, and higher regression risk within a weekend.
- **Best for:** Disposable personal analysis, not a packaged tool.
- **Estimated complexity:** Low initially, medium to maintain.

### Variant C: Multiprocess chunk processing

- **Approach:** Partition seekable files and merge worker aggregates.
- **Pros:** Can use multiple CPU cores on very large regular files.
- **Cons:** Cannot naturally partition stdin, complicates line boundaries and deterministic failures, multiplies unique-set memory, and is unnecessary before measurement.
- **Best for:** A future version only if profiling proves parsing CPU-bound.
- **Estimated complexity:** High relative to MVP.

Variant A is pre-approved because it preserves the obvious single-process architecture, meets stdin semantics, and keeps the weekend scope credible. Variant B is rejected for maintainability; Variant C is rejected until measured evidence shows it is necessary.

## CLI Interface

### Command

```text
nginx-stream-report [OPTIONS] [INPUT]
```

`INPUT` is one nginx access-log path. If omitted or exactly `-`, records are read from stdin. Input is decoded as UTF-8 with strict decoding and parsed as nginx's standard combined-log format. Regular files and non-seekable streams use the same line-by-line path. The MVP does not follow files and does not read directories, URLs, or compressed files directly.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one UTF-8 JSON object; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit RFC 4180-compatible rows; mutually exclusive with `--json` |
| `--color / --no-color` | auto | Default text uses color only when stdout is a TTY; ignored for JSON/CSV |
| `--max-unique-user-agents INTEGER` | positive integer, `1000000` | Maximum exact distinct User-Agent strings retained; crossing it exits 4 |
| `--version` | flag | Print package version and exit 0 |
| `--help` | flag | Print usage and exit 0 |

### Input record contract

The parser accepts a standard combined line containing remote address, remote identity, authenticated user, bracketed timestamp with numeric UTC offset, quoted request, status, bytes, quoted referer, and quoted User-Agent. The request target is taken from the request field; query strings are retained, and an unparsable request field makes the line invalid. Statuses `400..599` contribute to the error-URL ranking.

Malformed lines are skipped, counted in `invalid_lines`, and summarized on stderr after successful processing. Blank lines are malformed. A valid empty input produces a successful zero-valued report. Invalid lines never enter `total_valid_requests` or any percentage. A decoding error, read error, or nonexistent input is an input failure (exit 3), not a skipped line.

### Metric semantics

- **Top IPs:** the ten highest request counts by exact remote-address string.
- **Top error URLs:** the ten highest counts by exact request target among status codes 400 through 599.
- **Hourly request distribution:** 24 UTC-offset-local log-hour buckets (`00` through `23`), each calculated with the literal formula `100 × hourly_request_count / total_valid_requests`. When `total_valid_requests` is zero, all 24 percentages are `0.0`.
- **Share of unique User-Agents:** `100 × unique_user_agent_count / total_valid_requests`, or `0.0` when there are no valid requests. The count is exact within the configured cardinality limit; missing/empty `"-"` is treated as one literal User-Agent value.
- **Ranking:** count descending, then key ascending by Unicode code point; this makes ties deterministic. Exactly 10 rows are returned at most.
- **Percent serialization:** round to two decimal places using round-half-even at the renderer boundary; counters retain integers.

### Output contracts

Normal results go only to stdout. Diagnostics go only to stderr.

Text output contains four titled Rich tables in this order: `Top IPs`, `Top Error URLs`, `Hourly Request Distribution`, and `User-Agent Summary`, followed by valid/invalid line totals. JSON is one object with schema:

```text
{
  "schema_version": 1,
  "total_valid_requests": integer,
  "invalid_lines": integer,
  "top_ips": [{"ip": string, "count": integer}],
  "top_error_urls": [{"url": string, "count": integer}],
  "hourly_distribution": [{"hour": "00".."23", "count": integer, "percentage": number}],
  "user_agents": {"unique_count": integer, "share_percentage": number}
}
```

CSV begins with `record_type,rank,key,count,percentage`. It emits `top_ip`, `top_error_url`, and 24 `hour` rows, then one `user_agent_summary` row. Empty/non-applicable cells remain empty. CSV fields are escaped by the standard library `csv` writer and use `\r\n` record endings.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Successful report, help, or version output; skipped malformed lines alone do not change success |
| `1` | Unexpected internal error or output write failure |
| `2` | CLI usage error, invalid option/value, conflicting output flags, or extra arguments |
| `3` | Input failure: path/open/read/UTF-8 decoding failure |
| `4` | Unique-cardinality exhaustion: another distinct User-Agent would exceed `--max-unique-user-agents` |

No partial JSON or CSV document may be written for exit 3 or 4: computation finishes before serialization. Broken-pipe behavior is normalized to exit 1 with no traceback.

## Component Model

```text
Click command
    │ validates options, opens input
    ▼
line iterator ──> parser ──> Aggregator.consume(record)
                       invalid │          │ bounded counters/set
                               ▼          ▼
                         diagnostics   Report dataclass
                                           │
                               ┌───────────┼───────────┐
                               ▼           ▼           ▼
                            Rich text     JSON         CSV
```

| Module | Responsibility | Must not do |
|---|---|---|
| `src/nginx_stream_report/cli.py` | Click command, option validation, stream ownership, exception-to-exit mapping | Parse fields or calculate metrics |
| `src/nginx_stream_report/parser.py` | Compile grammar once; turn a line into `AccessRecord` or typed invalid result | Read files or print |
| `src/nginx_stream_report/models.py` | Frozen `AccessRecord`, aggregate/report dataclasses, domain exceptions | Depend on Click or Rich |
| `src/nginx_stream_report/aggregate.py` | Update counters, enforce cardinality cap, create deterministic report | Render output |
| `src/nginx_stream_report/renderers/text.py` | Rich terminal report and color policy | Mutate report |
| `src/nginx_stream_report/renderers/json.py` | JSON schema v1 serialization | Emit diagnostics |
| `src/nginx_stream_report/renderers/csv.py` | CSV record stream serialization | Infer metrics |
| `src/nginx_stream_report/errors.py` | Stable domain exceptions and exit-code mapping | Catch unknown exceptions silently |

## Data Model and State Bounds

There is no database and therefore no tables, migrations, indexes, or persistence model. Runtime data is represented by dataclasses:

| Dataclass | Fields | Invariants |
|---|---|---|
| `AccessRecord` | `remote_addr: str`, `timestamp: datetime`, `target: str`, `status: int`, `user_agent: str` | Frozen; timestamp is timezone-aware; status is 100..599 |
| `RankedCount` | `key: str`, `count: int` | Count is positive |
| `HourlyBucket` | `hour: int`, `count: int`, `percentage: Decimal` | Hour 0..23; percentage 0..100 |
| `UserAgentSummary` | `unique_count: int`, `share_percentage: Decimal` | Count non-negative; percentage 0..100 |
| `Report` | `schema_version: int`, totals, tuples of ranked counts/buckets, UA summary | Immutable renderer input; schema version is 1 |

The aggregator owns `Counter[str]` for IPs, `Counter[str]` for error URLs, a fixed 24-element integer list, and `set[str]` for exact User-Agents. It never stores raw lines or `AccessRecord` objects after `consume`. IP and URL distinct-key maps can still grow with input cardinality; the benchmark must measure this. A future bounded heavy-hitter algorithm is a spec-level change because it can alter exact top-10 results. The User-Agent set is explicitly bounded and fails closed with exit 4.

## Parsing and Processing Sequence

1. Click validates flags and the positive cardinality limit before opening input.
2. The CLI opens the path or uses stdin via a context that never closes process-owned stdin.
3. Each decoded line is parsed by one precompiled expression plus timestamp parsing.
4. Invalid syntax increments `invalid_lines`; no partial fields are aggregated.
5. A valid record updates total, IP count, optional error-URL count, hour bucket, and exact User-Agent set.
6. Before inserting a new User-Agent, the aggregator checks the configured bound and raises `UniqueCardinalityExhausted` without rendering.
7. End of input creates one immutable `Report`; rankings use bounded `heapq.nsmallest`/equivalent deterministic selection rather than sorting full maps where beneficial.
8. Exactly one selected renderer writes stdout; a concise invalid-line summary writes stderr.

Time is O(n + k log 10), with n lines and k distinct ranking keys. Memory is O(i + u + 24), where i is distinct IPs, u combines distinct error URLs and exact User-Agents, with the User-Agent component capped by configuration.

## Failure, Security, and Privacy Model

- Log content is untrusted data. It is never evaluated, interpolated into a shell, or emitted without renderer escaping.
- Rich markup interpretation is disabled/escaped for log-derived strings; CSV formula injection is documented because CSV consumers may execute leading `=`, `+`, `-`, or `@`. The CSV renderer prefixes such key cells with a single quote.
- The tool makes no network calls, stores no logs, writes no cache, and emits no telemetry.
- Tracebacks are suppressed during normal CLI use; `Exception` maps to exit 1 after a concise stderr message. Programmer interrupts are not swallowed.
- JSON uses standard escaping and disallows NaN/Infinity. Output is not emitted until the full report exists, preserving machine-readable atomicity for domain failures.
- File permissions are inherited from the invoking user; the tool neither escalates privileges nor follows an alternate service identity.

## Packaging and Deployment

Deployment is a local pip installation into a virtual environment or isolated installer such as pipx. `pyproject.toml` declares Python `>=3.11,<4`, Click and Rich runtime dependencies, and the `nginx-stream-report` console entry point. There is no Docker image, Compose file, daemon, cloud target, Kubernetes manifest, environment variable, or authentication flow. Reproducible releases use a source distribution and wheel built by standard PEP 517 tooling.

## Test and Performance Architecture

- Parser unit fixtures cover valid combined lines, IPv4/IPv6 strings, escaped quotes, malformed lines, statuses, timestamps, and strict UTF-8 failures at the I/O boundary.
- Aggregator tests cover all metric formulas, deterministic ties, zero valid records, 4xx/5xx boundaries, and the cap transition that raises exit 4.
- Renderer golden tests cover escaping, Unicode, color/no-color, JSON schema v1, CSV row order, and stdout/stderr isolation.
- Click integration tests cover stdin, files, every exit code `0/1/2/3/4`, conflicting flags, and broken output.
- A deterministic generator creates a representative 1 GB fixture outside the repository. The benchmark records CPU, peak RSS, Python version, storage medium, processor, and command. The release gate is under 30 seconds, not an undocumented anecdote.

## Architecture Decision Record (ADR)

### ADR-001: Stateless layered CLI

- **Status:** Accepted (pre-approved by project brief).
- **Decision:** Use Variant A with one process and no persistent or network component.
- **Consequences:** Simple installation and privacy boundary; CPU scaling and exact-cardinality memory require measurement.

### Debate Summary — labeled self-critique

No independent or adversarial reviewer was available for this benchmark. The following is the architect's own Devil's Advocate-style self-critique, not an independent review.

**Verdict:** APPROVE WITH CONDITIONS.

| Challenge raised in self-critique | Resolution/condition |
|---|---|
| Exact User-Agent cardinality can exhaust memory | Enforce the documented cap before insertion and map it exclusively to exit 4 |
| “Streaming” may falsely imply constant memory | State exact map/set bounds honestly and measure peak RSS; never retain lines |
| Regex parsing may reject legitimate custom formats | Scope MVP to standard combined format and expose skipped-line counts |
| Single-process Python may miss 1 GB/30 s | Benchmark after the parser/aggregator slice; profile before considering a spec change |
| CSV keys can trigger spreadsheet formulas | Neutralize formula-leading key cells while preserving raw values in JSON/text |
| Partial pipeline documents would be dangerous | Aggregate fully before JSON/CSV serialization and separate stdout/stderr |

Alternatives rejected: a database-backed service adds state without product value; an HTTP upload API adds security and operations; multiprocessing breaks the simple stdin model; a one-file script weakens testability. The architecture is approved only if cardinality exhaustion, output atomicity, and the performance gate receive executable tests/evidence.

## Cross-Document Contract

`PRD.md` owns observable requirements and acceptance criteria. `IMPLEMENTATION_PLAN.md` orders implementation. `CLAUDE_CODE_GUIDE.md` turns those steps into bounded prompts. Any behavior change must update those specs before product code.
