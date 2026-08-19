# Project Architecture: Nginx Insight

## 1. Context and Constraints

Nginx Insight is an installable Python 3.11 CLI that turns one or more nginx combined access-log streams into a single aggregate report. It targets DevOps/SRE users, a one-weekend delivery, $0 infrastructure, and a measured goal of processing 1 GB in under 30 seconds on a documented laptop.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect here because the required metrics can be accumulated in one pass, persistence would add I/O and lifecycle burden, and the product promises an ad-hoc local report rather than retained analytics. An HTTP API is incorrect because the intended interfaces are a terminal and Unix pipelines; a server would introduce networking, authentication, deployment, and availability concerns without improving the required workflow.

Additional constraints:

- No authentication, background service, cloud resources, containers, or Kubernetes.
- No network calls or telemetry at runtime.
- No product code may depend on input size by storing raw lines.
- Unique dictionaries/sets are exact but bounded; exhaustion is explicit, never silently approximated.
- The initial parser supports nginx combined log format only.

## 2. Architecture Decision

The architecture is an obvious single-process, layered pipeline:

```text
file(s) / stdin
      |
      v
binary buffered iterator -> line decoder -> combined-log parser
                                              |
                                              v
                                      immutable LogRecord
                                              |
                                              v
                                  StreamingAggregator (one pass)
                                    |       |       |       |
                                  IPs   error URLs hours    UAs
                                              |
                                              v
                                        ReportSnapshot
                                     /        |         \
                                  Rich       JSON       CSV
```

One process owns all state. Input is consumed sequentially; raw records are discarded after aggregation. Renderer selection happens before processing, but rendering happens only after the immutable report snapshot is finalized, preventing partial machine-readable documents.

## 3. Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** Buffered sequential input, parse each line once, update in-memory counters/sets, render once at EOF.
- **Pros:** Small operational surface; no intermediate files; natural stdin support; lowest weekend complexity; fast enough to test directly.
- **Cons:** Exact high-cardinality metrics consume memory; no historical queries; one CPU-bound parse path.
- **Best for:** Ad-hoc local analysis of individual or concatenated logs.
- **Estimated complexity:** Low.

### Variant B: Multi-process chunk map/reduce

- **Approach:** Split seekable files, parse chunks in workers, merge partial counters.
- **Pros:** Can use multiple cores on large regular files.
- **Cons:** stdin and quoted-line boundary handling are harder; merge memory remains; startup/IPC cost; platform variability; much larger test surface.
- **Best for:** Repeated analysis of multi-gigabyte seekable files where profiling proves parsing is CPU-bound.
- **Estimated complexity:** Medium.

### Variant C: Persistent indexed analytics stack

- **Approach:** Ingest into a database/search service and query reports.
- **Pros:** Historical exploration and repeated arbitrary queries.
- **Cons:** Violates the approved stateless/$0/no-server scope; adds operations, storage, schemas, and deployment.
- **Best for:** Long-lived centralized observability, which is explicitly not this product.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because every required output is reducible in one pass, the primary interfaces are files/stdin, and the approved delivery and operational constraints reward simplicity. Variant B is deferred until benchmark/profile evidence justifies it. Variant C is rejected.

No adversarial or independent review is represented here; that review belongs to the separate external harness.

## 4. Module and File Layout

```text
pyproject.toml
src/nginx_insight/
  __init__.py          # package version only
  cli.py               # Click command, option validation, exception-to-exit mapping
  model.py             # LogRecord, ReportSnapshot, ranked-row dataclasses
  parser.py            # bytes/line decoding and combined-log parser
  aggregate.py         # one-pass StreamingAggregator and cardinality guard
  render/
    __init__.py
    terminal.py        # Rich tables and warnings
    json_output.py     # versioned JSON document
    csv_output.py      # stable long-form CSV rows
tests/
  fixtures/            # small valid/malformed combined-log files and golden outputs
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_outputs.py
  test_performance.py
benchmarks/
  generate_log.py      # deterministic representative-data generator
```

Dependency direction is `cli -> parser + aggregate + render`, `aggregate -> model`, and `render -> model`. Parser and renderers must not import Click. Domain modules must not write to stdout/stderr or terminate the process.

## 5. Domain Model and Streaming State

Dataclasses:

| Type | Fields | Contract |
|---|---|---|
| `LogRecord` | `ip: str`, `timestamp: datetime`, `method: str`, `url: str`, `protocol: str`, `status: int`, `bytes_sent: int | None`, `user_agent: str` | One valid combined-log line; request URL retains the logged request-target text |
| `RankedCount` | `key: str`, `count: int` | One deterministically ranked metric row |
| `HourlyBucket` | `hour: int`, `count: int`, `percentage: float` | Hour is 0–23 from the timestamp as written in the log |
| `ReportSnapshot` | `schema_version: int`, `total_lines: int`, `total_valid_requests: int`, `malformed_lines: int`, `top_ips: tuple[RankedCount, ...]`, `top_error_urls: tuple[RankedCount, ...]`, `hourly_distribution: tuple[HourlyBucket, ...]`, `unique_user_agents: int`, `unique_user_agent_share: float` | Immutable completed report shared by all renderers |

Mutable aggregation state consists only of integer counters, a fixed 24-element hour array, `dict[str, int]` counts for IPs and error URLs, and `set[str]` for User-Agents. No raw input lines or full `LogRecord` history is retained.

Cardinality is bounded by `--max-unique`, applied separately to the IP dictionary, error-URL dictionary, and User-Agent set. The default is 1,000,000 entries per collection. Attempting to insert the `(limit + 1)`th distinct key raises a typed `CardinalityExhausted` error; the CLI emits a concise diagnostic and exits 4. Existing-key increments remain allowed at the limit. Exactness is preserved below the limit; there is no approximate fallback.

## 6. Parsing Contract

The MVP accepts the conventional nginx combined format:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

Rules:

- Read input through a large buffered binary stream and decode each line as UTF-8 with strict error detection.
- Parse quoted fields without splitting on ordinary spaces inside requests, referrers, or User-Agents.
- Accept an absent byte count written as `-` and model it as `None`.
- Require status `100..599`, a timestamp matching nginx's standard `%d/%b/%Y:%H:%M:%S %z`, and a request with method, request target, and protocol.
- In default non-strict mode, malformed or undecodable lines increment `malformed_lines`, produce a final warning on stderr for machine formats, and do not contribute to metrics.
- With `--strict`, the first malformed/undecodable line terminates processing with exit 1 and identifies source and line number without echoing the potentially sensitive full line.
- An empty stream is valid and yields zero counts and percentages.

Multiple files are concatenated logically in argument order. `-` means stdin and may appear at most once. File handles are opened and closed sequentially so the number of inputs does not increase open-descriptor usage.

## 7. Metric Semantics

Only valid parsed requests contribute to metrics.

| Metric | Definition | Ordering |
|---|---|---|
| Top IPs | Count every valid request by exact client IP string; return at most 10 | Count descending, then IP string ascending |
| Top error URLs | Count request targets only when status is 400–599; return at most 10 | Count descending, then URL string ascending |
| Hourly distribution | All 24 hour buckets from the hour encoded in each log timestamp | Hour ascending from `00` through `23` |
| Unique User-Agent share | Exact distinct non-empty User-Agent count divided by all valid requests, expressed as percent | Single percentage; zero when there are no valid requests |

Hourly percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`. The unique User-Agent share uses `100 × unique_user_agent_count / total_valid_requests`. Percentages are computed with full Python float precision and rendered to two decimal places in terminal/CSV; JSON includes numeric values rounded to two decimal places. Hourly percentages may sum to 99.99 or 100.01 after display rounding.

## CLI Interface

### Command

```text
nginx-insight [OPTIONS] [INPUTS]...
```

With no `INPUTS`, the command reads stdin. Each input is a regular file path or `-` for stdin. Directories, missing/unreadable files, duplicate stdin markers, and unsupported encodings are handled under the exit contract below. The implementation must never overwrite an input path.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | off | Write exactly one JSON report document to stdout |
| `--csv` | off | Write one CSV header followed by long-form metric rows to stdout |
| `--strict` | off | Treat the first malformed line as a processing/data error |
| `--max-unique INTEGER` | `1000000` | Positive ceiling applied independently to each exact high-cardinality collection |
| `--color / --no-color` | auto | Force or suppress color for terminal text; invalid with `--json` or `--csv` |
| `--version` | n/a | Print package version and exit 0 |
| `--help` | n/a | Print Click help and exit 0 |

`--json` and `--csv` are mutually exclusive. Machine-readable stdout contains no progress text, warnings, or ANSI escapes. Diagnostics go to stderr.

### Terminal Output

The default Rich report includes a summary (`total_lines`, `valid_requests`, `malformed_lines`), ranked top-IP and error-URL tables, a 24-row hourly count/percentage table, and unique User-Agent count/share. Color is used only when enabled. If a top list is empty, the relevant table states “No data” rather than inventing a row.

### JSON Output

The top-level object has this stable shape:

```json
{
  "schema_version": 1,
  "summary": {"total_lines": 0, "total_valid_requests": 0, "malformed_lines": 0},
  "top_ips": [{"rank": 1, "ip": "192.0.2.1", "count": 3}],
  "top_error_urls": [{"rank": 1, "url": "/missing", "count": 2}],
  "hourly_distribution": [{"hour": "00", "count": 0, "percentage": 0.0}],
  "unique_user_agents": {"count": 0, "share_percentage": 0.0}
}
```

All 24 hourly rows are present. Arrays are deterministically ordered. JSON ends with one newline.

### CSV Output

CSV uses RFC 4180-compatible quoting and the fixed header:

```text
metric,rank,key,count,percentage
```

- `top_ip` and `top_error_url` rows populate rank, key, and count.
- `hourly_request` rows populate key (`00`–`23`), count, and percentage.
- One `unique_user_agents` row has blank rank, key `all`, distinct count, and share percentage.
- One `summary` row per summary key uses key and count, with blank rank/percentage.

### Exit Codes

| Code | Meaning | Examples |
|---:|---|---|
| `0` | Success | Report emitted; help/version shown; empty valid input; non-strict malformed lines were skipped |
| `1` | Processing/data error | Strict malformed or undecodable line; invariant failure while parsing/aggregating |
| `2` | CLI usage error (Click contract) | Unknown option, mutually exclusive output flags, invalid/non-positive option value, duplicate stdin marker |
| `3` | Input/output error | Missing/unreadable input, directory supplied, read failure, or output write failure |
| `4` | Unique-cardinality exhaustion | A new IP, error URL, or User-Agent would exceed `--max-unique` |

This `0/1/2/3/4` mapping is public and must be golden-tested. Unexpected defects may be normalized to 1 after a concise diagnostic in normal mode; developer tracebacks are test/debug behavior, not public output.

## 9. Output and Error Boundaries

`cli.py` is the only layer that maps exceptions to exit codes. `parser.py` raises structured parse errors with source/line metadata; `aggregate.py` raises cardinality/invariant errors; renderers raise ordinary I/O errors. The CLI catches only known categories, writes one diagnostic to stderr, and ensures machine stdout is either a complete report or empty.

Signals and interrupts follow conventional shell behavior: `KeyboardInterrupt` exits 130, outside the product's normal `0/1/2/3/4` completion contract. Broken output pipes are treated as a normal downstream close only if no other processing error occurred; otherwise the originating product error wins.

## 10. Performance and Resource Design

- Complexity is `O(n + u log 10)`, where `n` is valid lines and `u` is distinct tracked keys; top-10 extraction uses `heapq.nsmallest`/equivalent bounded selection rather than sorting all entries.
- Memory is `O(unique_ips + unique_error_urls + unique_user_agents)`, bounded explicitly by `--max-unique`; the 24 hourly buckets are constant space.
- Compile parser structures once, bind hot-loop functions locally where evidence helps, and avoid constructing dictionaries per line.
- Do not use Rich progress bars while streaming; terminal work occurs after aggregation.
- Benchmark with a deterministic 1 GB fixture on the documented reference laptop using `/usr/bin/time`, recording wall time and peak RSS. Run at least one warm-up and three measured samples; the median must be under 30 seconds.
- Performance changes require profile evidence and correctness regression tests. Multi-processing is not an assumed remedy.

## 11. Security and Privacy

- Treat every log field as untrusted data. Renderers escape Rich markup and rely on JSON/CSV encoders for quoting.
- Do not evaluate, shell-expand, fetch, or normalize logged URLs/User-Agents.
- Do not print full malformed lines in diagnostics; logs can contain tokens, paths, and personal data.
- Do not make network calls or emit telemetry.
- Open only explicitly supplied paths and stdin; no recursive discovery or symlink policy beyond normal read-only OS semantics.
- CSV consumers can interpret leading formula characters. Prefix keys beginning with `=`, `+`, `-`, or `@` with a single quote in CSV output and document this safety transform; JSON/terminal preserve the original value.

## 12. Packaging and Deployment

Deployment is a local pip installation, not a running environment:

```text
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install .
nginx-insight --help
```

`pyproject.toml` declares Python `>=3.11,<4`, runtime dependencies `click` and `rich`, and console script `nginx-insight = nginx_insight.cli:main`. A wheel and source distribution are the release artifacts. There are no environment variables, configuration files, Docker files, compose services, ports, health endpoints, database tables, migrations, API endpoints, authentication flows, or cloud deployment resources.

## 13. Architecture Decision Records

### ADR-001: One local process

- **Status:** Accepted by product constraints.
- **Decision:** Select Variant A, the streaming single-process pipeline.
- **Reason:** Best fit for stdin/files, weekend scope, and zero operational cost.
- **Consequence:** Exact cardinality state is memory-bound and explicitly guarded.

### ADR-002: Exact metrics with fail-closed cardinality

- **Status:** Accepted.
- **Decision:** Keep exact distinct collections up to a public ceiling; exit 4 on attempted overflow.
- **Reason:** Silent approximation would break incident/pipeline trust.
- **Consequence:** Users with genuinely higher cardinality must raise the limit with sufficient memory or pre-filter/split input.

### ADR-003: Combined format only for MVP

- **Status:** Accepted.
- **Decision:** Support the conventional combined grammar; reject/skip other lines according to strict mode.
- **Reason:** Arbitrary `log_format` configuration is incompatible with a reliable one-weekend implementation.
- **Consequence:** Custom formats are a P2 future decision.

### Review Boundary

The required Devil's Advocate review is intentionally not executed or synthesized in this session. Its fresh-session artifact and verdict are owned by the external benchmark harness; this document makes no claim that such a reviewer has run.

## 14. Traceability

- Product intent, budget, competition, and prioritization: `STRATEGIC_PLAN.md`.
- User-visible requirements and acceptance criteria: `PRD.md`.
- File-by-file delivery order and checks: `IMPLEMENTATION_PLAN.md`.
- Implementation prompts that preserve this contract: `CLAUDE_CODE_GUIDE.md`.
