# Project Architecture: nginx-log-report

## 1. Context and constraints

The product is a Python 3.11 process invoked as `nginx-log-report [OPTIONS] [INPUT]`. It reads an nginx access log from `INPUT` or `-`/stdin, parses each line once, updates exact in-memory aggregates, and renders one report to stdout. Diagnostics go to stderr. It never stores log content after the current record and never opens a network listener.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema lifecycle, disk consumption, cleanup, and privacy exposure without improving a one-shot report; exact counters and sets can be maintained in memory during a single pass. An HTTP API would turn a local pipeline utility into a long-running service with authentication, request limits, deployment, and operations requirements. File/stdin input and stdout/stderr output already provide the right Unix integration contract.

## 2. Architecture decision and considered variants

### Chosen: single-process streaming pipeline

- **Approach:** Click constructs an immutable configuration, a parser yields one `AccessRecord` at a time, an aggregator updates report state, and one selected renderer emits the finalized report.
- **Advantages:** minimal operational surface, natural backpressure from blocking reads, deterministic lifecycle, $0 infrastructure, and the best fit for one-weekend delivery.
- **Trade-offs:** exact high-cardinality maps can grow; CPU parsing is single-core; there is no cross-run history.
- **Complexity:** Low.

### Rejected: shell pipeline of specialized subprocesses

- **Approach:** invoke separate parsing, sorting, and formatting processes.
- **Advantages:** reuse standard tools and per-stage composability.
- **Trade-offs:** repeated parsing, intermediate sorting, platform-dependent quoting, fragmented error handling, and no single stable JSON/CSV contract.
- **Why rejected:** it recreates the `grep`/`awk` alternative instead of supplying a reliable installable product.

### Rejected: local ingestion service with persistent analytics

- **Approach:** upload logs to a daemon backed by SQLite or a search store and query results over HTTP.
- **Advantages:** history and repeated queries.
- **Trade-offs:** violates the approved no-database/no-HTTP constraints and adds lifecycle, security, and cleanup work unrelated to the four reports.
- **Why rejected:** wrong optimization for one-shot local analysis.

No selection pause is needed: the user explicitly approved the obvious single-process architecture and excluded the other styles.

## 3. Runtime data flow

```text
file path or stdin
       |
       v
buffered text iterator
       |
       v
NginxLineParser ---- malformed count/diagnostic sample ----> stderr
       |
       v AccessRecord (one line only)
StreamingAggregator
  |-- Counter[ip]
  |-- Counter[error_url] for status 400..599
  |-- fixed list[24] for local timestamp hour
  `-- set[user_agent] + valid_user_agent_request_count
       |
       v
Report dataclass
       |
       +--> Rich text renderer --> stdout
       +--> JSON renderer ------> stdout
       `--> CSV renderer -------> stdout
```

The parser and aggregator form a synchronous pull pipeline. No queue is needed in a single process; the input iterator is the backpressure mechanism.

## 4. Planned package structure

```text
pyproject.toml
src/nginx_log_report/
  __init__.py
  cli.py
  models.py
  parser.py
  aggregate.py
  errors.py
  renderers/
    __init__.py
    text.py
    json.py
    csv.py
tests/
  fixtures/
  test_cli.py
  test_parser.py
  test_aggregate.py
  test_render_json.py
  test_render_csv.py
  test_render_text.py
  test_performance.py
scripts/
  generate_benchmark_log.py
```

These paths are plans, not product code created by this blueprint.

## 5. Component responsibilities

| Component | Responsibility | Must not do |
|---|---|---|
| `cli.py` | Validate Click options, select streams/renderer, map failures to exit codes | Parse lines or contain aggregation logic |
| `parser.py` | Parse supported common/combined records and normalize timestamp, status, URL, IP, User-Agent | Retain records or print output |
| `aggregate.py` | Update exact counters/sets and finalize sorted top-10 rows | Read files or know output formatting |
| `models.py` | Define `AccessRecord`, ranked rows, report metadata, and `Report` dataclasses | Perform I/O |
| `renderers/*` | Convert one canonical `Report` into text, JSON, or CSV | Recompute metrics or write diagnostics |
| `errors.py` | Define user-facing exception categories and exit-code mapping | Swallow unexpected defects |

## 6. In-memory data model; no database schema

There are no database tables, migrations, indexes, or persistence layer. The generic blueprint template requests database tables, but creating them would directly contradict the product contract. The complete runtime record model is:

| Dataclass/value | Fields and types | Invariants |
|---|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `url: str | None`, `status: int`, `user_agent: str | None` | One valid source line; 100–599 status; timezone-aware timestamp; `url=None` only for a `"-"` request field |
| `RankedCount` | `rank: int`, `key: str`, `count: int` | Rank starts at 1; descending count; lexical key tie-break |
| `ReportMeta` | `schema_version: str`, `total_lines: int`, `valid_lines: int`, `malformed_lines: int`, `input_name: str` | Counts are non-negative and total = valid + malformed |
| `Report` | `meta: ReportMeta`, `top_ips: tuple[RankedCount, ...]`, `top_error_urls: tuple[RankedCount, ...]`, `hourly_requests: tuple[int, ...]`, `unique_user_agents: int`, `user_agent_requests: int`, `unique_user_agent_share: float` | At most 10 ranked rows per list; exactly 24 hourly buckets; share is 0 when denominator is 0 |

Runtime collections are `collections.Counter[str]` for IPs and error URLs, a 24-element integer list for hours, and `set[str]` for User-Agent values. Space complexity is `O(U_ip + U_error_url + U_ua)` and does not depend on line count except through distinct cardinality. Final top-10 selection uses `heapq.nsmallest`/equivalent bounded selection with deterministic keys rather than sorting the full input.

Exactness has an enforceable support envelope. The default maximum is 500,000 distinct values summed across IP, error-URL, and User-Agent collections; a new insertion that would exceed `--max-distinct-values` aborts before mutation with exit 5 and no report. Individual IP, request, referrer, and User-Agent captures are limited to 64, 8,192, 8,192, and 4,096 decoded characters respectively, and an input record is limited to 1 MiB. Oversized records are malformed rather than partially aggregated. The guard is a deterministic pre-exhaustion failure path, not a claim that catching allocator-level `MemoryError` is safe. Tests set a small distinct limit to prove the exact behavior; the 1 GB acceptance fixture must also remain below 512 MiB peak RSS. Within these stated limits, metrics are exact over normalized decoded strings and are never silently approximated or truncated.

## 7. Input contract and parsing

- Input is read as bytes. The accepted grammar is exactly `$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent` (common) with optional ` "$http_referer" "$http_user_agent"` (combined), followed only by horizontal whitespace. Custom extra fields are rejected in v0.1.
- Bracket/quote boundaries are parsed by a byte-oriented state machine. Inside quoted fields, nginx default `\"`, `\\`, and `\xHH` escapes are recognized; malformed/incomplete escapes reject the line. Other backslash escapes remain literal backslash plus byte.
- Captured bytes are decoded as UTF-8 with replacement. Therefore “exact” IP/URL/User-Agent aggregation means exact equality after escape decoding and UTF-8 replacement, not identity of original invalid byte sequences; collision fixtures lock this policy.
- The request field is either `-` or exactly `METHOD SP request-target SP HTTP/version`, with one or more ASCII spaces separating tokens and no extra token. `-` yields no URL contribution but remains a valid record for IP/hour/status. The request target is reported without query normalization.
- An error URL is counted once for each valid record whose status is 400 through 599 inclusive.
- Hour buckets use the hour encoded in each record's timestamp; no machine-local timezone conversion occurs.
- Unique User-Agent share is `distinct non-empty User-Agent values / valid requests containing a non-empty User-Agent × 100`.
- Malformed lines are skipped and counted. Bounded stderr diagnostics contain only line number and a stable reason code; they never echo raw source text, avoiding terminal injection and accidental secret disclosure.
- Empty input or input with zero valid records exits nonzero; mixed valid/malformed input produces a report and a stderr warning.

Buffered binary iteration enforces the record-size limit before parsing. Tests cover common/combined boundaries, trailing extra fields, quoted requests, `-` requests, IPv4/IPv6, timezone offsets, all supported escapes, invalid UTF-8 collisions, incomplete escapes, and oversized records.

## 8. CLI contract; no HTTP API

There are no HTTP endpoints, request bodies, response codes, authentication flow, ports, or server process. The generic blueprint endpoint checklist is intentionally inapplicable. The full external interface is:

```text
nginx-log-report [OPTIONS] [INPUT]

INPUT                    Log path; omit or use '-' for stdin
--json                   Emit the versioned JSON document
--csv                    Emit normalized CSV rows
--no-color               Disable styling in terminal text
--max-diagnostic-lines N Number of malformed-line examples sent to stderr (default 5)
--max-distinct-values N Maximum summed distinct aggregation keys (default 500000)
--version                Print package version and exit
--help                   Print usage and exit
```

`--json` and `--csv` are mutually exclusive. Text is the default. JSON and CSV are always UTF-8 and never contain ANSI control sequences. Output is written only after successful report finalization so structured stdout is not mixed with progress messages.

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Report emitted successfully, including when some lines were skipped |
| 2 | Click usage or option error |
| 3 | Input cannot be opened/read |
| 4 | No valid records were found |
| 5 | Resource failure such as `MemoryError` |
| 1 | Unexpected internal error |

## 9. Output schemas

### Terminal text

Rich renders a title/metadata block, two ranked tables, a 24-row hourly table or compact histogram, and a User-Agent summary. Color is enabled only for an interactive terminal unless `--no-color` is supplied. Redirected default text remains readable plain text.

### JSON schema version 1

Top-level keys are `schema_version`, `meta`, `top_ips`, `top_error_urls`, `hourly_requests`, and `user_agents`. Ranked items use `rank`, `value`, and `count`. Hourly items use zero-padded `hour` (`00` through `23`) and `count`. `user_agents` contains `unique`, `requests_with_user_agent`, and `unique_share_percent`. Percent values are rounded to two decimals only at serialization.

### CSV schema version 1

CSV is one normalized stream with header:

```text
schema_version,section,rank,key,value,count,share_percent
```

Rows are emitted in this exact order; non-applicable cells are empty:

| Order | Section | Rank | Key | Value | Count | Share percent |
|---:|---|---|---|---|---:|---:|
| 1–5 | `meta` | empty | one of `input_name`, `total_lines`, `valid_lines`, `malformed_lines`, `schema_version` | string value | empty | empty |
| next ≤10 | `top_ip` | 1–10 | IP | empty | request count | empty |
| next ≤10 | `top_error_url` | 1–10 | URL | empty | error count | empty |
| next 24 | `hour` | empty | `00`–`23` | empty | request count | empty |
| final 3 | `user_agent` | empty | one of `unique`, `requests_with_user_agent`, `unique_share_percent` | empty | integer for the first two rows | two-decimal value for the share row |

This shape retains every report field. Golden tests lock header, complete row order, quoting, line endings, and section/key names.

## 10. Configuration and environment

There are no required environment variables or configuration files. All behavior is explicit through CLI arguments, supporting reproducible pipelines. Standard process environment (`NO_COLOR` as understood by Rich and locale/terminal capability) may influence only terminal styling, never metrics or JSON/CSV bytes.

## 11. Authentication and trust boundary

Authentication is absent because there is no network service or shared account boundary. The OS user's permission to read the input file is the only access control. The tool treats every log field as untrusted data. JSON/CSV use their standard escaping and retain normalized exact values. Terminal text passes every derived value through a shared display sanitizer that visibly escapes C0/C1 controls, ESC/ANSI/OSC sequences, carriage returns, newlines, bidi controls, and other non-printing format characters, disables Rich markup, and truncates a displayed cell to 200 characters without changing the underlying metric. Malformed diagnostics contain no source excerpts. The tool makes no outbound requests and does not execute content from logs.

## 12. Packaging and deployment

Deployment means installing a wheel into a local Python 3.11 environment with pip. `pyproject.toml` declares the `nginx-log-report` console script and only Click/Rich runtime dependencies. CI may build wheel and sdist artifacts, but runtime requires no Docker image, Compose file, VPS, serverless target, cloud account, or Kubernetes resources. Docker is omitted because it would complicate stdin/file mounting for a local pip tool without improving reproducibility beyond a locked Python package.

## 13. Performance and resource strategy

- Benchmark an exactly 1,073,741,824-byte fixture produced from a fixed generator version and seed. Record line-length, status, timestamp, IP, URL, and User-Agent cardinality distributions plus valid/malformed ratio and file hash.
- The acceptance run is end-to-end `--json` output to a regular file, so parsing, aggregation, serialization, and writing are included. Run five warm-cache repetitions after one unmeasured warm-up and require the median wall time under 30.0 seconds and every run under 33.0 seconds; record each duration and maximum RSS. Also record one cold-cache observation when the OS permits it without elevating privileges, but do not use it as the portable gate.
- Record CPU model, cores, RAM, storage medium, OS/kernel, Python patch version, package version, command, and `/usr/bin/time -v` measurement method. The absolute threshold is evidence for the named reference laptop, not a guarantee for all laptops.
- Add parser-only and high-cardinality small benchmarks to separate decoding costs from hash-table growth.
- Profile parsing before optimization. Prefer fixed-position scanning/splitting that correctly handles quoted fields; avoid compiling regexes per line.
- Keep diagnostics bounded and do not retain `AccessRecord` instances after aggregation.
- Avoid full-key sorts when selecting the top 10; deterministic tie-breaking remains mandatory.
- Exactness is preserved in the MVP. If adversarial cardinality exhausts memory, exit clearly rather than silently switching to approximate counts.

## 14. Failure handling and observability

Human diagnostics use concise Rich messages on stderr; pipeline payloads remain on stdout. Metadata includes total, valid, and malformed counts. No progress bar is emitted by default because it adds overhead and corrupts captured terminal text.

Any late input read/decode failure discards accumulated state and emits no report. Because finalized output is bounded by 20 ranked strings plus 24 hours and metadata, each renderer serializes its complete payload in memory before the first stdout write. A non-broken-pipe write or flush failure exits 1 with a sanitized stderr diagnostic; partial bytes may already exist at an external destination and cannot be retracted. `BrokenPipeError` closes stdout and exits quietly with 0, following filter-style pipeline behavior. Unexpected exceptions return 1 with a short message; developer tracebacks are not a stable user interface. Integration tests use failing input and output doubles to prove each branch.

## 15. Architecture Decision Record (ADR)

### ADR-001: Local synchronous streaming process

- **Status:** Accepted with all adversarial-review conditions incorporated.
- **Decision:** Use one Python process with parser, exact aggregator, canonical report dataclasses, and selectable renderers.
- **Drivers:** $0 budget, one-weekend delivery, local/offline use, fixed reports, 1 GB/<30 s target, pip installability.
- **Consequences:** minimal operations and deterministic output; memory depends on distinct cardinality and CPU work is single-core.
- **Rejected alternatives:** shell multiprocess pipeline and persistent local service, for the reasons in Section 2.

### Debate summary

The architecture was reviewed by the blueprint skill's Devil's Advocate agent.

**Verdict:** APPROVE WITH CONDITIONS

**Challenges and resolutions:**

1. Unbounded exact aggregation could exhaust the interpreter before a clean failure. **Resolution:** enforce a 500,000 summed-distinct-key limit, field/record bounds, exit 5 before mutation, and retain the 512 MiB measured gate.
2. “Common/combined” did not define an exact grammar or byte semantics. **Resolution:** define the byte grammar, state-machine escapes, request subgrammar, UTF-8 replacement semantics, and collision tests.
3. CSV could not represent all metadata unambiguously. **Resolution:** add a `value` column and enumerate every row and its order.
4. Rich markup disabling alone did not neutralize terminal control sequences. **Resolution:** add shared terminal sanitization and remove raw source excerpts from malformed-line diagnostics.
5. Late input and stdout failures lacked transactional semantics. **Resolution:** discard on late reads, pre-serialize bounded reports, specify write/flush and quiet broken-pipe behavior, and test failing streams.
6. The performance gate was not reproducible across workload/hardware details. **Resolution:** pin generator/seed/distributions, include end-to-end rendering, require five measured runs, and record a complete machine/protocol manifest.

**Alternatives considered and rejected:** A fundamentally different architecture was not warranted. The reviewer confirmed the fixed parser → aggregator → canonical report → renderer design and recommended contract hardening within it.

### Verification approach

Parser fixtures prove record extraction, aggregation tests prove exact counts and tie order, golden tests prove JSON/CSV schemas, Click integration tests prove stdout/stderr and exit codes, packaging smoke tests prove installation, and a real 1 GB run proves the performance requirement. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) and [PRD.md](PRD.md).
