# Project Architecture: nginx-stream-report

## 1. Context and Decision

The product is a local Python 3.11 command-line application that consumes an nginx access-log byte stream once, aggregates four reports in memory, and renders only after the input completes successfully. The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add schema, writes, lifecycle, cleanup, and I/O without benefiting a one-shot report whose source of truth is the supplied log. An HTTP API would add a server, authentication and network attack surface while weakening stdin/file pipeline ergonomics. The CLI process is the deployment unit: it opens one input, owns all state, writes one output, and exits.

## 2. Architecture Variants

### Variant A: Single-process streaming CLI (selected)

- **Approach:** parse each line and update bounded in-memory counters in one Python process; render after EOF.
- **Pros:** simplest installation, no temporary data, deterministic lifecycle, pipe-friendly, appropriate for a weekend.
- **Cons:** exact distinct-key tracking consumes memory proportional to cardinality; CPU work is single-process.
- **Best for:** local logs up to the stated 1 GB target with enforced cardinality limits.
- **Estimated complexity:** Low.

### Variant B: Multi-process partition and merge

- **Approach:** split seekable files, aggregate partitions in worker processes, then merge.
- **Pros:** can use multiple CPU cores on large files.
- **Cons:** cannot naturally split stdin, complicates ordering/error semantics, increases peak memory and startup cost.
- **Best for:** larger repeatable batch jobs after profiling proves CPU-bound parsing.
- **Estimated complexity:** Medium.

### Variant C: Embedded analytical database

- **Approach:** load parsed records into a local embedded engine and query reports.
- **Pros:** flexible follow-up analysis.
- **Cons:** violates stateless scope, adds disk writes and a dependency, and is unnecessary for four fixed metrics.
- **Best for:** exploratory analytics outside this product.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is approved because it directly matches local one-shot use, the $0 budget, the fixed four-report scope, and the one-weekend schedule. Variants B and C remain rejected unless measured evidence changes the product constraints. The separate external Devil's Advocate review is intentionally outside this session.

## 3. System Context

```text
nginx log file ---------+
                        +--> Click CLI --> byte-line parser --> bounded aggregator
stdin / decompressor ---+                                      |
                                                               v
                                                  report dataclasses
                                                               |
                                      +------------------------+------------------+
                                      v                        v                  v
                                Rich text renderer       JSON renderer       CSV renderer
                                      |                        |                  |
                                   stderr                   stdout             stdout
                              (diagnostics only)       (when selected)      (when selected)
```

Normal report output is written to stdout in every mode. Warnings and concise failure messages go to stderr. No renderer is invoked until aggregation finishes, preventing partial reports on parse, I/O, or cardinality failure.

## CLI Interface

### Command

```text
nginx-stream-report [OPTIONS] [INPUT]
```

`INPUT` is an optional path. Omitted or `-` means stdin. Exactly one input stream is processed per invocation. The command accepts bytes from regular files, named pipes, and stdin; compressed files must be decompressed by an upstream command in the MVP.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one UTF-8 JSON object to stdout; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit UTF-8 RFC 4180 long-form CSV to stdout; mutually exclusive with `--json` |
| `--no-color` | flag, false | Disable color in text mode; structured modes never contain ANSI escapes |
| `--max-unique-values` | integer, `1000000` | Maximum number of distinct values in each exact IP, URL, or User-Agent set/map; must be >=10 |
| `--version` | flag | Print version and exit 0 without reading input |
| `--help` | flag | Print Click help and exit 0 without reading input |

Default mode is Rich terminal text. Color is enabled only when stdout is a TTY and `--no-color` is absent. Top lists contain at most 10 rows, ordered by descending count and then ascending UTF-8 key for deterministic ties.

### Input grammar and validity

The MVP supports the standard nginx common and combined access-log shapes:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

- The parser extracts client IP text, timestamp with numeric offset, request target, status, and optional User-Agent.
- A valid line has a parseable supported shape, an HTTP status from 100 through 599, a timestamp, and a request field containing a method, target, and protocol separated by spaces.
- The URL dimension is the request target exactly as logged, including its query string; no decoding, normalization, or host inference is performed.
- `"-"` User-Agent means missing and is excluded from both the distinct User-Agent numerator and the User-Agent-observed denominator.
- Malformed lines are skipped and counted. If at least one line is valid, they produce a warning on stderr but do not change exit code 0.
- An empty input or an input containing no valid records exits 3 and emits no report.

### Metric semantics

1. **Top client IPs:** request count per exact client IP across all valid records.
2. **Top error URLs:** request count per exact request target where status is 400–599, combining 4xx and 5xx.
3. **Hourly request distribution:** 24 local-log-time buckets (`00` through `23`). Every bucket percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`. Percentages are numeric, rounded to two decimal places for presentation; raw counts and the denominator are also emitted.
4. **Share of unique User-Agents:** `100 × distinct_non_missing_user_agent_count / valid_requests_with_non_missing_user_agent`. The report also includes numerator, denominator, and a two-decimal percentage. If no valid record has a User-Agent, the numerator and denominator are 0 and percentage is `null` in JSON, blank in CSV, and `N/A` in text.

### Outputs

Text mode displays a summary (valid and malformed line counts), two top-10 tables, a 24-row hourly table, and the User-Agent share. CSV has the fixed header:

```text
section,rank,key,count,total,percentage
```

Rows use `summary`, `top_ip`, `top_error_url`, `hour`, and `user_agent_share` as section values. Non-applicable cells are empty.

JSON uses this versioned shape:

```json
{
  "schema_version": 1,
  "summary": {"valid_requests": 0, "malformed_lines": 0},
  "top_ips": [{"ip": "string", "count": 0}],
  "top_error_urls": [{"url": "string", "count": 0}],
  "hourly_distribution": [{"hour": "00", "count": 0, "percentage": 0.0}],
  "unique_user_agents": {"distinct_count": 0, "observed_requests": 0, "percentage": null}
}
```

All JSON keys are always present after a successful run. JSON contains 24 hour objects, including zero-count hours. JSON and CSV use `\n` line endings and terminate with one newline.

### Exit-code contract

| Code | Meaning | Output behavior |
|---:|---|---|
| `0` | Success; at least one valid request was analyzed | Complete report on stdout; optional malformed-line warning on stderr |
| `1` | Input/output runtime failure, including unreadable input or broken/non-writable output | No knowingly partial report; concise error on stderr |
| `2` | CLI usage error, including conflicting options or invalid limits | Click usage/error text on stderr |
| `3` | No valid nginx records | No report on stdout; diagnostic on stderr |
| `4` | Unique-cardinality exhaustion for IP, URL, or User-Agent tracking | No report on stdout; named dimension and configured limit on stderr |

## 5. Components and Package Layout

```text
pyproject.toml
src/nginx_stream_report/
  __init__.py          # package version
  cli.py               # Click boundary and exit-code translation
  models.py            # ParsedRequest, Report, RankedItem, HourBucket, UAStats
  parser.py            # bytes-oriented common/combined parser
  aggregate.py         # one-pass bounded exact aggregation
  errors.py            # typed domain failures and exit-code mapping
  render/
    __init__.py
    text.py            # Rich presentation
    json.py            # schema_version 1 serialization
    csv.py             # long-form schema serialization
tests/
  fixtures/
  unit/
  integration/
  performance/
```

Dependency direction is `cli -> parser + aggregate -> models` and `cli -> render -> models`. Renderers never parse input; the parser never formats output; the aggregator never calls Click or Rich.

## 6. Data Model and Streaming State

There are no database tables, migrations, retained files, caches, or background processes. Runtime dataclasses are:

| Dataclass | Fields | Invariants |
|---|---|---|
| `ParsedRequest` | `ip: str`, `hour: int`, `target: str`, `status: int`, `user_agent: str \| None` | hour 0–23; status 100–599; non-empty IP/target |
| `RankedItem` | `key: str`, `count: int` | count >0 |
| `HourBucket` | `hour: int`, `count: int`, `percentage: float` | 24 buckets; percentage derived from valid total |
| `UserAgentStats` | `distinct_count: int`, `observed_requests: int`, `percentage: float | None` | `null` percentage iff denominator is 0 |
| `Report` | totals, ranked tuples, 24 hour buckets, `UserAgentStats` | immutable render-ready snapshot |

Mutable aggregation state consists of `Counter[str]` for IPs, `Counter[str]` for error URLs, a 24-element integer list, `set[str]` for User-Agents, and scalar totals. Before inserting a new key, the aggregator checks that dimension's `--max-unique-values` ceiling. Existing-key updates remain valid at the limit. Exceeding a ceiling raises a typed failure mapped to exit code 4.

Complexity is O(n) expected time for n valid lines, plus O(k log 10) final top selection, and O(u_ip + u_error_url + u_ua) memory. The log's byte size does not otherwise determine memory usage.

## 7. Parsing and Failure Boundaries

- Input is opened in binary mode and iterated line by line; the full file is never read into memory.
- Parsing operates on bytes for boundary discovery, decoding only extracted fields as UTF-8 with replacement so one invalid byte cannot crash the process.
- Timestamp hour is read from the log's local timestamp; no timezone conversion occurs.
- The aggregation update for one parsed line is atomic from the user's perspective: all prospective new keys are checked before any counter changes.
- `BrokenPipeError` maps to code 1 and is handled without a traceback.
- Expected usage/domain/I/O failures show concise messages; unexpected defects may show a traceback only when a future explicit debug option is introduced.

## 8. Security and Privacy

Logs can contain IP addresses, URLs, query strings, referrers, and User-Agents. The tool processes them locally, performs no network access or telemetry, and retains nothing after exit. It does not execute, interpolate, or treat log contents as Rich markup. Renderers escape terminal markup, JSON/CSV libraries handle quoting, and error messages do not echo entire malformed lines. Documentation warns that saved reports may contain personal or secret-bearing URL data.

## 9. Packaging and Deployment

The deployment target is a local Python 3.11 environment on Linux or macOS. A PEP 517 `pyproject.toml` builds a wheel and sdist, with the `nginx-stream-report` console entry point. Runtime dependencies are Click and Rich; dataclasses, JSON, CSV, collections, and heap utilities come from Python 3.11. There is no Docker image, daemon, environment variable, configuration file, server, cloud deployment, or Kubernetes manifest in the MVP. Reproducible use comes from an isolated virtual environment or `pipx`.

## 10. Quality and Performance Strategy

- Unit fixtures cover common/combined records, IPv4/IPv6 text, timezone offsets, escaped quotes, missing UA, malformed lines, and status boundaries.
- Property-style tests assert totals and percentage invariants without requiring a third-party property framework.
- Golden tests validate ANSI-free JSON/CSV and deterministic tie ordering.
- Integration tests invoke the installed-style Click command and cover every exit code.
- A generated, non-committed 1 GB fixture with documented cardinalities measures wall time and peak resident memory. Performance fixtures are test data, never represented as production evidence.

## 11. Architecture Decision Records

### ADR-001: One process, one pass

- **Status:** Accepted by the supplied product brief.
- **Decision:** Use Variant A with bounded exact counters.
- **Consequences:** Low operational complexity and exact results; explicit code 4 failure is required when cardinality cannot be represented safely.

### ADR-002: Render only after EOF

- **Status:** Accepted.
- **Decision:** Build an immutable report, then render it.
- **Consequences:** Output is not live-progress streaming, but pipeline consumers never mistake a partial report for success.

### ADR-003: Exact User-Agent diversity

- **Status:** Accepted.
- **Decision:** Track exact distinct non-missing User-Agent strings and guard the set with the configured ceiling.
- **Consequences:** Semantics are auditable; inputs above the safety bound terminate with code 4 rather than silently approximating.

No inline adversarial review was performed. The benchmark harness will run the repository's real Devil's Advocate agent separately.
