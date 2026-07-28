# Project Architecture: nginx-log-top

## 1. Context and Constraints

`nginx-log-top` is an installable Python 3.11 command-line tool for DevOps/SRE engineers. It reads nginx access logs as a stream and produces operational summaries without retaining log records. The delivery window is one weekend, the budget is $0, and the performance target is processing a 1 GB log in under 30 seconds on a representative laptop.

The governing architecture decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here:

- A database would add writes, schema lifecycle, disk growth, privacy exposure, and operational setup while the required metrics can be computed with bounded counters in one pass. Results are point-in-time reports, not durable queryable history.
- An HTTP API would turn a local analysis utility into a long-running service with networking, authentication, deployment, and support obligations. The users need shell composition and machine-readable stdout, which `--json` and `--csv` provide directly.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended)

- **Approach:** Click parses the command, a line iterator feeds a parser, dataclass events update in-memory aggregators, and a renderer writes terminal, JSON, or CSV output.
- **Pros:** one pass; low operational complexity; natural stdin support; minimal dependencies; straightforward profiling.
- **Cons:** unique User-Agent exactness requires memory proportional to distinct values; a single CPU core may limit parsing throughput.
- **Best for:** local files and Unix pipelines up to several gigabytes.
- **Estimated complexity:** Low.

### Variant B: Chunked multiprocessing

- **Approach:** seekable files are divided into byte ranges, worker processes aggregate partitions, and a parent process merges results.
- **Pros:** can use multiple CPU cores on very large regular files.
- **Cons:** cannot naturally process stdin; chunk boundary handling and merge logic increase defect risk; process startup and serialization can erase gains at 1 GB.
- **Best for:** a later release targeting multi-gigabyte seekable files and measured CPU saturation.
- **Estimated complexity:** Medium.

### Variant C: External sort/embedded analytics engine

- **Approach:** normalize records and delegate aggregation to DuckDB or shell utilities.
- **Pros:** mature grouping primitives and ad hoc extensibility.
- **Cons:** violates the intentionally small stack; may materialize data; raises install size and startup cost; weakens predictable streaming behavior.
- **Best for:** exploratory analytics with arbitrary queries rather than a fixed report.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the product decisions pre-approve the obvious single-process architecture, the fixed metrics are one-pass aggregations, and the one-weekend constraint rewards a small, profile-driven design. Variants B and C remain measured-response options, not MVP scope.

## 3. System Structure

```text
file path / stdin
       |
       v
line iterator -> nginx parser -> AccessLogEvent dataclass
                                   |
                                   v
                           StreamingReport
                    +----------+---------+----------+
                    |          |         |          |
                 IP count   error URL  hourly    UA set
                    +----------+---------+----------+
                                   |
                                   v
                       Rich / JSON / CSV renderer
                                   |
                              stdout/stderr
```

Recommended package layout:

```text
pyproject.toml
src/nginx_log_top/
  __init__.py
  cli.py
  models.py
  parser.py
  aggregate.py
  renderers.py
  errors.py
tests/
  fixtures/
  test_cli.py
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_performance.py
```

Responsibilities:

| Module | Responsibility |
|---|---|
| `cli.py` | Click command, option validation, stream ownership, exit mapping |
| `models.py` | frozen/slotted dataclasses for parsed events and report snapshots |
| `parser.py` | compiled nginx combined-log parser and timestamp normalization |
| `aggregate.py` | one-pass counters, top-10 selection, unique-UA share |
| `renderers.py` | Rich terminal tables plus stable JSON and CSV schemas |
| `errors.py` | typed user-facing input/configuration errors |

Dependencies flow inward: `cli` may depend on parser, aggregator, and renderers; parser and aggregator depend on models; models depend only on the standard library. Renderers receive immutable report data and never parse input.

## CLI Interface

### Commands

Installable console entry point:

```text
nginx-log-top [OPTIONS] [INPUT]
```

There are no subcommands in the MVP. `INPUT` is an optional path to an nginx access-log file. Omitting it or passing `-` reads UTF-8 text from stdin.

### Options

| Option | Meaning | Default / validation |
|---|---|---|
| `--json` | Emit one JSON document | mutually exclusive with `--csv` |
| `--csv` | Emit CSV sections suitable for pipelines | mutually exclusive with `--json` |
| `--top INTEGER` | Number of IP and error-URL rows | `10`; integer from 1 to 100 |
| `--strict` | Fail on the first malformed non-empty line | off; otherwise malformed lines are counted and skipped |
| `--no-color` | Disable ANSI styling in terminal mode | color enabled only when stdout is a TTY |
| `--version` | Print package version and exit | no input consumed |
| `--help` | Print usage and exit | no input consumed |

### Inputs

- nginx **combined** access-log lines: remote address, timestamp with numeric offset, request, status, bytes, referrer, and User-Agent.
- Regular UTF-8 file, `-`, or piped stdin.
- Lines are consumed lazily; input is never loaded in full.
- Empty lines are ignored. In lenient mode, malformed lines increment `malformed_lines`; in strict mode they are fatal.
- A physical line may contain at most 1 MiB including its terminator. Oversized lines are consumed and discarded with a bounded reader, then treated as malformed; strict mode exits `4`.
- Timestamps are grouped by the hour present in the log entry after parsing its explicit offset. The output key is `YYYY-MM-DDTHH:00:00±HH:MM`; no host-timezone conversion occurs.
- A missing/empty User-Agent field is normalized as `"(missing)"` and participates in the unique count.

### Outputs

All report modes contain:

- total parsed requests and malformed-line count;
- top N client IPs by request count;
- top N URLs whose response status is 400–599, ranked by error count;
- request count for every observed hour, chronologically sorted;
- distinct User-Agent count and `unique_user_agent_share = distinct_user_agents / parsed_requests`.

Ties in top lists are ordered lexicographically by IP or URL for deterministic output.

Terminal mode writes colored Rich tables to stdout. Diagnostics and malformed-line summaries go to stderr; color is automatically suppressed when stdout is not a TTY or `NO_COLOR`/`--no-color` applies.

JSON mode writes exactly one UTF-8 object:

```json
{
  "summary": {
    "parsed_requests": 120,
    "malformed_lines": 2,
    "distinct_user_agents": 18,
    "unique_user_agent_share": 0.15
  },
  "top_ips": [{"ip": "203.0.113.10", "requests": 20}],
  "top_error_urls": [{"url": "/missing", "errors": 7}],
  "hourly_requests": [{"hour": "2026-07-28T13:00:00+03:00", "requests": 44}]
}
```

CSV mode writes a single RFC 4180 stream with a stable union schema:

```text
section,key,count,value
summary,parsed_requests,120,
summary,unique_user_agent_share,,0.150000
top_ip,203.0.113.10,20,
top_error_url,/missing,7,
hourly_requests,2026-07-28T13:00:00+03:00,44,
```

CSV ordering is summary rows, top IPs, top error URLs, then chronological hours. Machine-readable modes never emit progress or ANSI codes to stdout.

### Exit-code contract

| Code | Meaning |
|---:|---|
| `0` | Report produced successfully, including an empty valid input |
| `2` | Click usage error or invalid/mutually exclusive options |
| `3` | Input cannot be opened or read |
| `4` | Strict parsing failure |
| `1` | Unexpected internal failure |

Broken pipes are handled quietly and do not produce a traceback, following normal Unix CLI behavior.

## 5. Data Model and Streaming State

No persistent schema exists. The complete transient model is:

| Type/state | Fields | Constraints |
|---|---|---|
| `AccessLogEvent` | `ip: str`, `timestamp: datetime`, `url: str`, `status: int`, `user_agent: str` | timestamp timezone-aware; status 100–599; URL is request target |
| `HourBucket` | `local_date: date`, `hour: int`, `offset_minutes: int` | immutable/hashable; preserves logged wall-clock hour and explicit offset |
| `ReportSnapshot` | totals, sorted top lists, hourly rows, UA cardinality/share | immutable renderer input |
| Aggregator state | `Counter[str] ip_counts`, `Counter[str] error_url_counts`, `Counter[HourBucket] hourly_counts`, `set[str] user_agents`, integer totals | updated once per valid event |

Space is `O(I + E + H + U)`, where `I` is distinct IPs, `E` distinct error URLs, `H` observed hours, and `U` distinct User-Agents. It is not strictly constant-memory because exact cardinality and exact top counts require distinct-key state. This is an explicit, testable trade-off; an approximate sketch is deferred unless profiling shows pathological cardinality.

### Database inventory

There are zero database tables, migrations, indexes, connections, or durable records. File content is read-only and report state dies with the process. This is a deliberate architecture decision, not an omitted design.

## 6. Parsing and Aggregation

The bounded line reader never allocates more than 1 MiB plus its fixed read buffer for one physical record. The parser compiles its expression once and avoids per-line exception-heavy fallbacks. It extracts only fields required by the PRD. Request parsing separates method, target, and protocol while preserving the target for URL ranking. Status filtering for error URLs is `400 <= status <= 599`.

For each valid event the aggregator:

1. increments total requests and the IP counter;
2. increments the error-URL counter only for 4xx/5xx status;
3. constructs `HourBucket(local_date, hour, offset_minutes)` from the logged wall-clock representation and increments that bucket;
4. inserts the normalized User-Agent into a set.

Distinct local-hour/offset combinations remain separate even if they represent the same UTC instant. Finalization sorts hour rows by `(UTC instant at bucket start, offset_minutes, canonical display string)` for deterministic chronology. It uses `heapq.nsmallest`/equivalent bounded selection with key `(-count, key)` or sorting after profiling. The share is `0.0` for no parsed requests, otherwise `len(user_agents) / parsed_requests`.

## 7. API, Authentication, and Security Boundaries

### HTTP API inventory

There are zero HTTP endpoints, request bodies, response bodies, listeners, ports, sessions, or API credentials. The stable integration interfaces are the CLI arguments, stdin, stdout, stderr, exit codes, JSON schema, and CSV schema documented under `## CLI Interface`.

### Authentication inventory

Authentication and authorization are not applicable because the process exposes no network service and has no user/account model. Access control remains the host operating system’s file permissions. The tool:

- opens only the input path explicitly supplied by the caller;
- never executes log content or resolves URLs;
- treats log fields as untrusted display data: terminal rendering disables Rich markup for field values and replaces ESC, C0/C1 controls, CR, LF, and NUL with visible escaped forms such as `\\x1b`, `\\r`, and `\\n`; JSON/CSV receive original parsed strings and rely on structural serializers;
- never writes input records to disk;
- avoids echoing full malformed lines in default diagnostics.

## 8. Configuration and Environment

No required environment variables or `.env` file exist.

| Variable | Required | Behavior |
|---|---:|---|
| `NO_COLOR` | No | Any non-empty value disables terminal color, consistent with common CLI practice |
| `PYTHONUTF8` | No | Standard Python runtime control; users may set it for non-UTF-8 locales |

CLI options take precedence where relevant. There are no secrets.

## 9. Packaging and Deployment

Deployment is a pure-Python wheel and source distribution published or installed through pip:

```text
python3.11 -m pip install .
nginx-log-top --help
```

`pyproject.toml` defines Python `>=3.11`, Click, Rich, a `src/` package, and the `nginx-log-top` console script. Runtime support targets Linux and macOS; Windows compatibility is best effort because nginx log pipelines are primarily Unix-oriented.

Docker, Docker Compose, a server, cloud resources, and Kubernetes are intentionally absent. Containerization would add image maintenance without improving a local pip-installed streaming CLI.

## 10. Performance and Reliability

### Normative benchmark oracle

The named baseline is **BR-1**: Intel Core i7-1165G7 laptop CPU (one process/core used), 16 GiB RAM, NVMe SSD, Ubuntu 24.04 x86_64 on ext4, and CPython 3.11.latest with dependencies locked by the release candidate. Faster machines may report secondary results but cannot replace BR-1 acceptance.

`tests/benchmark-manifest.json` freezes:

- fixture generator version and seed, SHA-256, exact byte/line counts;
- 70% successful responses, 25% 4xx, 5% 5xx, and 1% malformed lines;
- cardinality profile: 100,000 IPs, 250,000 request targets, 168 hours, and 200,000 User-Agents;
- regular-file input and `--json` output redirected to `/dev/null`;
- one untimed warm-up followed by five timed warm-cache runs;
- acceptance on median wall-clock time, with fixture generation and warm-up excluded;
- `/usr/bin/time -v` peak-RSS measurement and locked Python/dependency versions.

Acceptance requires a 1 GiB (`1,073,741,824` byte) fixture to complete in under 30.0 seconds median and use no more than 1.5 GiB peak RSS on BR-1. A second 1 GiB high-cardinality fixture (all IPs, URLs, and User-Agents distinct) is a stress characterization, not the latency oracle; it must complete without corrupt output and its peak RSS is published.

Exact aggregation has no universal fixed-memory guarantee. The supported MVP envelope is the normative cardinality profile above. If the normal-profile RSS ceiling is breached, release acceptance fails and profiling decides explicitly between optimization, approximate HyperLogLog/Space-Saving semantics in a future major mode, or exact spill-and-merge. The MVP must not silently approximate. For inputs beyond the envelope, host memory exhaustion can still terminate the process; this limitation is documented rather than disguised.

Performance design rules:

- one sequential pass and buffered text I/O;
- no record-level Rich objects or output during ingestion;
- compiled parsing and local variable bindings in the hot loop;
- no full event list;
- profile before adding multiprocessing or approximate algorithms.

Malformed lines do not corrupt aggregate state. `KeyboardInterrupt`, input errors, broken pipes, and strict parse failures are mapped at the CLI boundary without tracebacks in normal operation.

## 11. Test Strategy

| Layer | Evidence |
|---|---|
| Parser unit tests | valid combined lines, IPv4/IPv6, escaped fields, offsets, malformed and >1 MiB lines |
| Aggregator unit tests | 4xx/5xx filtering, distinct equal-instant offset buckets, ties, empty input, UA share |
| Renderer golden tests | ANSI-free JSON/CSV, schema/order stability, CSV quoting, terminal control/markup neutralization |
| CLI integration tests | file/stdin parity, option conflicts, stderr separation, exit codes |
| Property/fuzz tests | parser never crashes on arbitrary text; counters preserve invariants |
| Performance test | 1 GB benchmark report under 30 seconds on reference hardware |

Target coverage is at least 90% for `src/nginx_log_top`, with all P0 acceptance criteria represented by automated tests.

## 12. Architecture Decision Record (ADR)

### ADR-001: Stateless single-process CLI

- **Status:** Accepted.
- **Decision:** Use Variant A, an in-process iterator/parser/aggregator/renderer pipeline.
- **Consequences:** very small deployment and strong shell interoperability; exact distinct-key state can grow with cardinality; parallelism is deferred.

### ADR-002: Exact User-Agent share

- **Status:** Accepted with a profiling gate.
- **Decision:** retain an exact set of normalized User-Agent strings for MVP correctness.
- **Consequences:** precise share; memory is proportional to distinct agents. The BR-1 normal-profile gate is 1.5 GiB peak RSS; the tool never silently substitutes an estimate.

### ADR-003: Preserve logged hour and offset

- **Status:** Accepted after adversarial review.
- **Decision:** aggregate with `HourBucket(local_date, hour, offset_minutes)`, not aware `datetime` identity.
- **Consequences:** local hour/offset rows never collapse merely because they represent the same instant; chronological sorting needs an explicit UTC-based sort key.

### ADR-004: Bound physical records and terminal controls

- **Status:** Accepted after adversarial review.
- **Decision:** cap physical lines at 1 MiB and visibly escape terminal control characters with Rich markup disabled for field values.
- **Consequences:** pathological records are rejected predictably; terminal text is a safe display representation while JSON/CSV retain serializer-safe original values.

### Debate Summary

The architecture was reviewed under `.itd-plugin/agents/devils-advocate.md`.

**Verdict:** APPROVE WITH CONDITIONS — all four conditions below are incorporated.

**Challenges raised:**

1. Aware `datetime` keys can collapse distinct local hours/offsets. → **Resolution:** added `HourBucket` identity and explicit chronological sort semantics in ADR-003.
2. Exact aggregation lacked an enforceable resource boundary. → **Resolution:** defined the BR-1 1.5 GiB normal-profile gate, a high-cardinality characterization, no silent approximation, and an evidence-driven fallback decision.
3. The performance gate was not reproducible. → **Resolution:** froze BR-1 hardware, fixture distribution/hash manifest, warm-cache protocol, five-run median, and peak-RSS method.
4. Hostile fields and unbounded physical lines were underspecified. → **Resolution:** capped lines at 1 MiB, defined bounded discard behavior, terminal escaping, and security test cases.

**Alternatives considered and rejected:**

- Multiprocessing — rejected for MVP because it breaks natural stdin processing and adds merge/chunk complexity before profiling.
- Approximate sketches — rejected for MVP because exact results are part of the current contract; retained as a future explicit mode only if evidence demands it.
- Exact spill-and-merge — rejected because disk materialization and cleanup complexity are disproportionate for the supported envelope.
- DuckDB/external sort — rejected because it expands dependencies and weakens the small stateless streaming design.

## 13. Traceability

- Product outcomes, roadmap, and risks: `STRATEGIC_PLAN.md`
- User-facing requirements and acceptance criteria: `PRD.md`
- Ordered delivery work and verification: `IMPLEMENTATION_PLAN.md`
- Execution prompts: `CLAUDE_CODE_GUIDE.md`
- Persistent implementation instructions: `CLAUDE.md`
