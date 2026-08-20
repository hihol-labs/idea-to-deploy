# Project Architecture: Nginx Stream Analyzer

## 1. Context and Constraints

The product is a local Python 3.11 command-line application for DevOps/SRE log triage. The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add installation, schema, retention, cleanup, and data-governance work while the required result is a one-shot summary of one stream. An HTTP API would add a server lifecycle, network security, authentication pressure, serialization overhead, and operational ownership without improving local file/stdin analysis. The CLI already provides a composable process boundary through stdin, stdout, stderr, structured formats, and exit codes.

Other fixed constraints are Python 3.11, Click, Rich, dataclasses, pip installation, no authentication/cloud/Kubernetes, $0 budget, one-weekend delivery, and a target of processing 1 GB in under 30 seconds on a documented laptop.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended and approved)

- **Approach:** One process reads one line at a time, parses it into a dataclass, updates bounded aggregate state, then renders once at EOF.
- **Pros:** Minimal moving parts; no IPC; predictable failure handling; easy stdin support; best fit for one-weekend delivery.
- **Cons:** CPU parsing remains single-core; exact User-Agent cardinality still requires memory proportional to unique values up to a safety ceiling.
- **Best for:** Local one-shot analysis of files up to the stated performance envelope.
- **Estimated complexity:** Low.

### Variant B: Single process with parallel parser workers

- **Approach:** A coordinator chunks file input and sends chunks to worker processes, then merges aggregates.
- **Pros:** Can use multiple CPU cores for regular files.
- **Cons:** Complex record boundaries, stdin behavior, ordering, merge logic, IPC overhead, and error propagation; risks exceeding weekend scope.
- **Best for:** Much larger files after profiling proves CPU parsing is the bottleneck.
- **Estimated complexity:** High.

### Variant C: External Unix pipeline of specialized commands

- **Approach:** Compose parsing and aggregation from `awk`, `sort`, `uniq`, and related tools.
- **Pros:** No package runtime beyond standard utilities; individually inspectable stages.
- **Cons:** Multiple passes/sorts, platform variation, fragile quoting, duplicated parsing logic, and no cohesive schema or exit contract.
- **Best for:** Disposable operator-specific analysis, not a maintained tool.
- **Estimated complexity:** Medium operational complexity.

### Recommendation

Variant A is selected because the product decisions pre-approve an obvious single-process architecture and prioritize a reliable weekend MVP over speculative multicore scale. Variant B remains a post-benchmark option only if measured evidence requires it; Variant C is a competing workflow, not the product architecture.

## 3. System Boundary and Data Flow

```text
file path or stdin
       |
       v
 buffered text reader -> line parser -> validated AccessRecord
                              |                 |
                              | invalid         v
                              +-------> counters/diagnostics
                                                |
                                                v
                                     StreamingAggregator
                           (counts, top candidates, 24 hourly bins,
                            bounded exact User-Agent set)
                                                |
                                                v
                                      immutable Report dataclass
                                                |
                         +----------------------+------------------+
                         v                      v                  v
                    Rich terminal            JSON               CSV
                    stdout report         stdout object      stdout rows
```

The reader never loads the full input. Parsed records are short-lived. Aggregation state consists of counters keyed by IP and error URL, 24 fixed hourly counters, totals, and an exact User-Agent set guarded by a configured hard ceiling. Rendering starts only after successful EOF and report construction, preventing partial structured output.

## CLI Interface

### Commands

The installed console command is:

```text
nginx-stream-analyzer [OPTIONS] [INPUT]
```

`INPUT` is an optional nginx access-log path. If omitted or `-`, input is read from stdin. Exactly one input stream is processed per invocation.

### Options

| Option | Meaning | Default/constraint |
|---|---|---|
| `--json` | Emit one JSON report to stdout | Mutually exclusive with `--csv` |
| `--csv` | Emit normalized CSV sections/rows to stdout | Mutually exclusive with `--json` |
| `--format [combined|common]` | Select supported nginx log format | `combined`; common records have no User-Agent value |
| `--ua-cardinality-limit INTEGER` | Maximum exact distinct User-Agents before safe failure | Positive integer; documented package default |
| `--no-color` | Disable ANSI styling in terminal mode | Color otherwise only when appropriate for a terminal |
| `--version` | Print version and exit | — |
| `--help` | Print usage and exit | — |

### Inputs

- UTF-8 text from a regular file or stdin; undecodable bytes are input errors rather than silently replaced data.
- Nginx common or combined log lines with standard quoted request and User-Agent fields.
- Empty input is valid and yields zero totals and empty top lists.
- Malformed lines are excluded from all denominators and counted in `invalid_line_count`.

### Outputs

- Default: colored Rich terminal text containing source summary, valid/invalid counts, top 10 IPs, top 10 error URLs, 24 hourly percentage bins, and unique User-Agent share.
- JSON: a single UTF-8 JSON object with `schema_version`, counts, ordered top lists, all 24 hourly bins, and User-Agent fields. No ANSI escapes.
- CSV: UTF-8 CSV with a stable `section` discriminator so heterogeneous report rows remain machine-readable. No ANSI escapes.
- Normal report data is written to stdout. Diagnostics are written to stderr.
- Top lists sort by count descending, then key lexicographically ascending; no more than 10 entries are emitted.

Hourly request distribution is a percentage for each hour `00` through `23`, calculated using the literal formula `100 × hourly_request_count / total_valid_requests`. When `total_valid_requests` is zero, every hourly percentage is `0.0`.

Unique User-Agent share is `100 × unique_nonempty_user_agent_count / total_valid_requests`. Common-format records contribute to total valid requests but have no User-Agent and therefore do not increase the numerator. When the denominator is zero, the share is `0.0`.

### Exit-code Contract

| Code | Meaning |
|---:|---|
| `0` | Analysis completed and a complete report was emitted, including empty input or input containing some malformed lines |
| `1` | Input/runtime failure, such as missing file, permission error, read error, or UTF-8 decode failure |
| `2` | CLI usage error, including invalid options or mutually exclusive formats |
| `3` | No valid records were found in non-empty input; diagnostics are emitted and no success report is claimed |
| `4` | Unique-cardinality exhaustion: the exact User-Agent set would exceed `--ua-cardinality-limit`; processing stops safely |

The complete `0/1/2/3/4` contract is public and must be preserved across renderers. Codes 3 and 4 take precedence over report emission; structured modes must not emit a truncated object or partial CSV report.

## 5. Components and Repository Layout

```text
pyproject.toml
src/nginx_stream_analyzer/
  __init__.py          # package metadata only
  cli.py               # Click command, validation, exception-to-exit mapping
  models.py            # AccessRecord, aggregate rows, Report dataclasses
  parser.py            # compiled common/combined parsers and timestamp parsing
  aggregate.py         # one-pass mutable aggregation and resource ceiling
  service.py           # orchestration from text stream to immutable Report
  renderers/
    terminal.py        # Rich terminal output
    json.py            # stable JSON schema
    csv.py             # stable CSV row schema
tests/
  fixtures/            # small reviewed nginx samples and expected outputs
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_renderers.py
  test_performance.py
```

Dependency direction is `cli -> service -> parser + aggregate -> models`; renderers consume only `Report` models. Parser and aggregator do not import Click or Rich. This keeps domain correctness testable without a terminal.

## 6. Domain Model

| Dataclass | Fields | Invariants |
|---|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `method: str`, `url: str`, `protocol: str`, `status: int`, `user_agent: str | None` | Timestamp is timezone-aware; status is 100–599; parsed from one valid line |
| `CountEntry` | `value: str`, `count: int` | Count > 0; output ordering is deterministic |
| `HourEntry` | `hour: int`, `request_count: int`, `percentage: float` | Hour 0–23; all 24 entries present |
| `Report` | schema version, input/valid/invalid totals, top lists, hourly entries, UA unique count/share | Totals are non-negative; percentages use valid requests only |

The mutable `StreamingAggregator` is an internal accumulator, not a serialized model. It maintains `Counter[str]` for IPs and error URLs, a 24-element integer list, numeric totals, and `set[str]` for nonempty User-Agents.

## 7. Parsing Contract

- Compile format-specific regular expressions once per run.
- Parse timestamps with nginx offset (`%d/%b/%Y:%H:%M:%S %z`) and derive the hour from the timestamp as recorded, without host-timezone conversion.
- Preserve the request target as logged for URL aggregation; do not normalize query strings in MVP.
- Treat status codes 400–599 as errors for the error-URL top 10.
- A missing request (`"-"`) may be a valid nginx line but has no URL and is excluded from URL ranking.
- Each rejected line increments both total-line and invalid-line counts; processing continues unless an I/O/decode/cardinality failure occurs.
- Non-empty input with zero valid records ends with exit 3.

## 8. Aggregation and Complexity

One pass over `n` lines yields O(n) parsing/update time. State is O(I + U + 24 + A), where `I` is distinct IP count, `U` is distinct error URL count, and `A` is distinct User-Agent count up to the configured hard limit. Top 10 extraction is deferred until EOF using `heapq.nsmallest`/equivalent deterministic bounded selection, avoiding a full output sort when possible.

The User-Agent ceiling is checked before insertion of a new value. Crossing it raises a domain exception mapped to exit 4. Exactness is preferred over approximate cardinality because the requested metric is a share and the CLI provides a clear safe-failure contract.

The 1 GB/30-second target must be tested with a generated-on-disk benchmark corpus outside the repository. Benchmark documentation records CPU, memory, storage medium, Python version, file size, line count, elapsed wall time, and peak RSS.

## 9. Output Schemas

JSON uses a versioned top-level object:

| Field | Type |
|---|---|
| `schema_version` | string |
| `total_lines`, `total_valid_requests`, `invalid_line_count` | integer |
| `top_ips` | array of `{ip: string, count: integer}` |
| `top_error_urls` | array of `{url: string, count: integer}` |
| `hourly_distribution` | 24 objects `{hour: "HH", request_count: integer, percentage: number}` |
| `unique_user_agents` | integer |
| `unique_user_agent_share_percentage` | number |

CSV rows share a fixed header: `schema_version,section,key,count,percentage`. `section` is one of `summary`, `top_ip`, `top_error_url`, `hourly_distribution`, or `unique_user_agents`. Fields irrelevant to a row are empty, never repurposed.

## 10. Database, HTTP API, and Authentication

- **Database:** none. There are no tables, migrations, indexes, connection strings, or retained records.
- **HTTP API:** none. There are no endpoints, methods, request bodies, response bodies, ports, or server process.
- **Authentication:** none. Access is governed by local operating-system file permissions and process execution rights.

These absences are intentional architectural requirements, not deferred design gaps.

## 11. Configuration and Environment

The CLI has no required environment variables and no `.env` file. Behavior is controlled by explicit CLI options. Standard process environment affecting terminal capability/encoding may be observed only through Click/Rich conventions; it does not alter report semantics.

## 12. Packaging and Deployment

Deployment is a Python wheel/sdist installed locally with pip into a virtual environment or isolated tool environment. `pyproject.toml` declares Python `>=3.11,<4`, Click, Rich, build metadata, and the console entry point.

There is no Docker image, Docker Compose file, daemon, staging environment, cloud target, or Kubernetes manifest. Release validation builds both artifacts, checks metadata, installs the wheel into a clean Python 3.11 virtual environment, runs smoke/golden tests, and invokes `--version` and `--help`.

## 13. Reliability and Security

- Never execute, interpolate, or treat log content as terminal markup; escape Rich-rendered values.
- Keep JSON/CSV output free from diagnostics and color; use library encoders/writers for escaping.
- Mitigate CSV formula injection for cells beginning with spreadsheet formula prefixes, or document a safe escaping policy and test it.
- Do not follow special input sources beyond normal OS open semantics without documenting blocking behavior.
- Stop cleanly on broken pipes using conventional CLI behavior.
- Never emit partial structured output on fatal errors.
- Bound exact User-Agent cardinality and document that IP/error-key memory remains data-dependent for MVP.

## 14. Architecture Decision Record

### ADR-001: Local single-process streaming CLI

- **Status:** Accepted by the project constraints.
- **Decision:** Use Variant A, with no database and no HTTP service.
- **Rationale:** Lowest operational and implementation complexity; natural file/stdin composition; adequate expected performance subject to benchmark evidence.
- **Consequences:** Processing is one-shot and single-core. Cross-run history and interactive querying are out of scope. Distinct-key aggregation consumes memory proportional to cardinality, with a hard guard for User-Agents.
- **Alternatives rejected:** Parallel workers add complexity before profiling evidence; a Unix-only pipeline lacks a stable cross-platform contract; GoAccess/ELK/AWStats solve broader or different problems.

No adversarial or independent review is recorded in this document; that review is explicitly outside this blueprint session.

## 15. Traceability

Product priorities and success constraints originate in `STRATEGIC_PLAN.md`. Observable behavior and acceptance criteria are in `PRD.md`. File-level delivery and verification are in `IMPLEMENTATION_PLAN.md`.
