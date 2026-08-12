# Project Architecture: nginx-insights

## 1. Context and Goals

`nginx-insights` is a Python 3.11 command-line application that consumes a finite nginx combined access-log stream from a path or standard input. A single process parses each line, updates four exact aggregate views, and renders one final report. The architecture prioritizes correctness, pipe safety, low operational overhead, and a measured target of processing 1 GB in under 30 seconds on a documented laptop.

The controlling decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect here because the product has no cross-run queries, mutation workflow, or retention requirement; persistence would add I/O, schema, lifecycle, and cleanup work without improving the four requested summaries. An HTTP API is incorrect because the users and input already live in shell workflows; a listener would introduce deployment, authentication, networking, and service-operation obligations expressly outside the product.

## 2. Architectural Constraints

- Python 3.11, Click, Rich, and dataclasses are fixed stack choices.
- The program is one local OS process and makes no network calls.
- Input is processed in one pass; raw lines and per-request objects are not retained.
- There is no authentication, database, HTTP API, server, cloud service, container requirement, or Kubernetes resource.
- Installation is through pip with a `nginx-insights` console entry point.
- Cash budget is $0 and the release window is one weekend.
- The supported grammar is nginx's standard combined log format, documented in [PRD.md](PRD.md).

## 3. Architecture Decision Path

The user pre-approved the obvious single-process architecture, so no interactive variant selection is needed.

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** Click command → buffered iterator → parser → in-memory aggregate state → selected renderer.
- **Pros:** one pass, simple install, no inter-process serialization, directly testable.
- **Cons:** exact high-cardinality keys consume memory; a failed run is restarted from the beginning.
- **Best for:** bounded local files and stdin pipelines up to the stated target.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunk-and-merge

- **Approach:** split seekable files into byte ranges, aggregate in workers, then merge.
- **Pros:** potential CPU parallelism on very large files.
- **Cons:** complex line-boundary logic, unavailable for general stdin, higher memory, and a larger weekend risk.
- **Best for:** repeatable multi-gigabyte batch jobs after profiling proves parsing is CPU-bound.
- **Estimated complexity:** Medium.

### Variant C: Persistent analytics service

- **Approach:** ingest logs into a database behind an API.
- **Pros:** historical queries and shared dashboards.
- **Cons:** violates explicit scope, budget, deployment, and statelessness constraints.
- **Best for:** a different centralized-observability product.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because it is the only variant aligned with finite local streams, zero infrastructure, pip installation, and a one-weekend delivery. Variant B remains a post-MVP optimization only if measurement justifies it; Variant C is rejected.

## 4. Component Model

```text
file path ─┐
           ├─> Click CLI ─> text stream ─> line parser ─> AggregateState ─> Report
stdin ─────┘                                      │                │          │
                                                  └─ invalid count  │          ├─ Rich terminal
                                                                    │          ├─ JSON
                                     cardinality guard <────────────┘          └─ CSV
```

| Component | Planned file | Responsibility |
|---|---|---|
| CLI adapter | `src/nginx_insights/cli.py` | Validate options, open/close input, select renderer, map exceptions to exits |
| Parser | `src/nginx_insights/parser.py` | Compile grammar once and convert a combined-log line into `AccessRecord` |
| Models | `src/nginx_insights/models.py` | Immutable parsed record, aggregate state, and report dataclasses |
| Aggregation | `src/nginx_insights/aggregate.py` | Update counts and finalize ordered top-10/percentage values |
| Orchestration | `src/nginx_insights/pipeline.py` | Iterate lazily, apply invalid-line policy, and produce `Report` |
| Rich renderer | `src/nginx_insights/renderers/rich_text.py` | Human-readable colored tables and warnings |
| JSON renderer | `src/nginx_insights/renderers/json_output.py` | Stable JSON object written to stdout |
| CSV renderer | `src/nginx_insights/renderers/csv_output.py` | Normalized multi-section CSV rows written to stdout |
| Error taxonomy | `src/nginx_insights/errors.py` | Typed failures and canonical exit-code mapping |

Dependencies point inward: renderers and CLI consume domain models; parser and aggregation do not import Click or Rich.

## 5. Data Model and Aggregation Semantics

There are no database tables or migrations. The complete transient model is:

| Dataclass / value | Fields and types | Constraints |
|---|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `request_target: str`, `status: int`, `user_agent: str` | Produced only by a valid combined-log line; timestamp is timezone-aware; request target preserves nginx text |
| `AggregateState` | `total_valid_requests: int`, `invalid_lines: int`, `ip_counts: Counter[str]`, `error_url_counts: Counter[str]`, `hour_counts: list[int]` of length 24, `unique_user_agents: set[str]` | Mutated only by aggregator; unique-key collections obey `max_unique` |
| `RankedItem` | `rank: int`, `value: str`, `count: int` | Rank begins at 1; deterministic order is count descending then value ascending |
| `HourlyShare` | `hour: int`, `count: int`, `percentage: float` | Hours 0–23 in log-local clock; percentage rounded only during rendering |
| `Report` | `total_valid_requests: int`, `invalid_lines: int`, `top_ips: tuple[RankedItem, ...]`, `top_error_urls: tuple[RankedItem, ...]`, `hourly_distribution: tuple[HourlyShare, ...]`, `unique_user_agent_count: int`, `unique_user_agent_share_percentage: float` | Immutable renderer input; zero-valid-input percentages are `0.0` |

Definitions:

- An error URL is the parsed request target of a valid record whose status is 400–599 inclusive.
- Hourly distribution uses the timestamp's explicit log offset and bins by its written local hour; no host-time conversion occurs.
- For every hour, the percentage is `100 × hourly_request_count / total_valid_requests`. If there are no valid requests, every hourly percentage is `0.0`.
- Unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`. It measures distinct observed User-Agent strings per valid request and may exceed neither 100% nor the valid-request count. A missing combined-format User-Agent value represented as `-` is one literal observed value.
- Top-10 ties sort by raw UTF-8/Unicode string value ascending after count descending so all formats agree.

Exact counters can grow with input cardinality. `--max-unique` limits the number of distinct keys in each exact tracker (`ip_counts`, `error_url_counts`, and `unique_user_agents`). Attempting to add the next distinct key aborts without a report and returns exit code 4; the tool never silently approximates.

## CLI Interface

### Command

```text
nginx-insights [OPTIONS] [PATH]
```

`PATH` is one nginx combined access-log file. Omitting it or passing `-` reads UTF-8 text from standard input. Exactly one final report is emitted after EOF; indefinite follow mode is not part of MVP.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit the JSON schema below; mutually exclusive with `--csv` |
| `--csv` | false | Emit normalized CSV below; mutually exclusive with `--json` |
| `--max-unique INTEGER` | `5000000` | Positive maximum distinct keys per exact tracker; invalid values are usage errors |
| `--fail-on-invalid` | false | Stop at the first malformed non-empty line with exit 3 instead of counting and skipping it |
| `--color / --no-color` | auto | Controls ANSI color only in terminal mode; auto enables it for a compatible TTY |
| `--version` | — | Print version and exit 0 |
| `--help` | — | Print usage and exit 0 |

No environment variables are required. Locale, host timezone, and terminal width must not change JSON/CSV values or ordering.

### Inputs

- Input encoding is UTF-8; an undecodable stream is an input/parse failure (exit 3).
- Each non-empty line must match nginx combined format: remote address, ident, user, bracketed timestamp with numeric offset, quoted request, three-digit status, bytes or `-`, quoted referrer, and quoted User-Agent.
- The request target is extracted from the quoted request's middle token. A request value of `-` yields target `-`.
- Empty lines are malformed and follow the same skip-or-fail policy; they are included in `invalid_lines` when skipped.
- Files are opened with buffered sequential I/O. stdin is never closed by application code.

### Outputs

Default terminal mode writes the report to stdout using Rich. It includes total valid and invalid line counts, ranked IP and error-URL tables, all 24 hour buckets with counts and percentages, and unique User-Agent count/share. Diagnostics go to stderr. ANSI escapes are never emitted in JSON or CSV modes.

JSON is one UTF-8 object followed by a newline:

```json
{
  "total_valid_requests": 0,
  "invalid_lines": 0,
  "top_ips": [{"rank": 1, "value": "192.0.2.1", "count": 2}],
  "top_error_urls": [{"rank": 1, "value": "/missing", "count": 1}],
  "hourly_distribution": [{"hour": 0, "count": 0, "percentage": 0.0}],
  "unique_user_agents": {"count": 0, "share_percentage": 0.0}
}
```

`hourly_distribution` always contains 24 ascending entries. Empty ranked arrays are valid. Numeric percentages are rounded to six decimal places at serialization.

CSV begins with `section,rank,key,count,percentage`. It emits `summary` rows for valid/invalid totals, ranked `top_ip` and `top_error_url` rows, 24 `hourly_distribution` rows (`key` is `00`–`23`), and one `unique_user_agents` row. Non-applicable fields are empty. RFC 4180 quoting and `\n` record separators make output deterministic across platforms.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Success, including a stream with zero valid requests when invalid lines were skipped |
| `1` | Operational/internal failure, including unexpected runtime errors or stdout write failure |
| `2` | Click usage error, such as incompatible output flags or invalid option values |
| `3` | Input or parse failure, including unreadable path, decoding error, or `--fail-on-invalid` rejection |
| `4` | Unique-cardinality exhaustion: a distinct-key tracker would exceed `--max-unique` |

No report is emitted after exits 1, 3, or 4. Help and version are successful exits. Broken-pipe behavior is normalized to exit 1 with no traceback.

## 7. Parsing and Error Strategy

The parser compiles one expression at module load, validates status range and timestamp, and returns either an `AccessRecord` or a structured parse rejection. Expected malformed data never raises a traceback to the user. The pipeline owns line numbers so fail-fast diagnostics can identify `PATH:line` or `stdin:line` without echoing the potentially sensitive log line.

The CLI catches only known domain exceptions plus a final defensive exception boundary. It writes concise diagnostics to stderr and delegates termination to Click without remapping the canonical codes. Partial renderer output is prevented by finalizing the report before serialization; JSON is assembled as one logical object, while unavoidable OS-level partial writes still return 1.

## 8. Performance and Resource Design

- Complexity is O(n + k log 10) time for n lines and k distinct counted keys; final top-10 selection uses `heapq.nsmallest`/equivalent deterministic bounded selection rather than sorting every key when profiling supports it.
- Raw requests are discarded immediately after aggregation.
- The 24-hour vector is fixed-size. Exact IP, error-URL, and User-Agent collections are bounded by `--max-unique`.
- Input is iterated by the buffered text stream; `read()` of the entire file is forbidden.
- Rich objects are created only after aggregation and are never used in JSON/CSV paths.
- Benchmark acceptance records Python version, CPU, storage, input size and distribution, wall-clock time, and peak RSS. A generated benchmark fixture is test data, never presented as production data.

## 9. Security and Privacy

The tool operates locally and does not transmit logs or telemetry. Paths and line numbers may appear in diagnostics, but raw log contents do not. Terminal rendering escapes or treats IPs, URLs, and User-Agent strings as plain text so Rich markup cannot be injected. CSV uses the standard library writer; values starting with formula-control characters remain valid CSV data, and documentation warns spreadsheet users about formula interpretation. JSON uses the standard encoder. Symlink handling follows normal OS file-open semantics.

There is no authentication flow because there is no identity boundary or shared service. File-read authorization is provided by the invoking OS user. There is no deployment topology; pip installs a local console script into the user's selected Python environment.

## 10. Packaging and Repository Layout

```text
pyproject.toml
src/nginx_insights/
  __init__.py
  cli.py
  errors.py
  models.py
  parser.py
  aggregate.py
  pipeline.py
  renderers/
    __init__.py
    rich_text.py
    json_output.py
    csv_output.py
tests/
  fixtures/
  unit/
  integration/
  performance/
```

`pyproject.toml` declares Python `>=3.11,<4`, runtime dependencies on Click and Rich, the console entry point, and optional development dependencies. Wheels and source distributions are the only deployment artifacts. Docker, docker-compose, cloud manifests, and Kubernetes resources are intentionally absent.

## 11. Architecture Decision Record (ADR)

### ADR-001: Single-process exact streaming analysis

- **Status:** Accepted.
- **Decision:** Use one Python process with exact in-memory aggregation and an explicit cardinality ceiling.
- **Reason:** It is the smallest design satisfying the CLI, correctness, installation, and performance constraints.
- **Consequences:** The run is restart-only and memory scales with distinct tracked values until the guard.

### ADR-002: Stable renderer-neutral report model

- **Status:** Accepted.
- **Decision:** All three renderers consume the same immutable `Report`.
- **Reason:** Prevents semantic drift among terminal, JSON, and CSV output.
- **Consequences:** The report must be finalized before any normal output is written.

### Self-Critique Debate Summary

This is a labeled self-critique performed because the benchmark has no independent reviewer or subagent transport. It is not an independent or adversarial-agent review.

**Verdict:** APPROVE WITH CONDITIONS.

**Strengths acknowledged:** the selected design matches the explicit stateless CLI scope, minimizes operational surface, and creates one semantic source for all output modes.

#### Challenge 1: Exact aggregation has cardinality-driven memory risk

- **Weakness:** Top counts and distinct User-Agents require exact key retention, so one-pass processing alone does not bound memory.
- **Risk level:** High.
- **Alternative:** Use sketches and bounded heavy-hitter algorithms.
- **Trade-off:** Approximation bounds memory but violates the approved exact-report contract and makes cross-format results harder to explain.
- **Question for architect:** What deterministic behavior prevents an OS-level out-of-memory failure without silently approximating?
- **Resolution:** Apply the same configurable distinct-key guard to every exact tracker and reserve exit 4 for the attempted insertion past that ceiling.

#### Challenge 2: “Streaming” may imply live follow behavior

- **Weakness:** Users may expect periodic output from a growing file, while this design emits only after EOF.
- **Risk level:** Medium.
- **Alternative:** Add an indefinite follow loop with interval snapshots and signal handling.
- **Trade-off:** Live mode improves incident monitoring but creates windowing, shutdown, CSV/JSON framing, and test complexity beyond the weekend MVP.
- **Question for architect:** Is the finite-stream behavior explicit enough that a user will not depend on unimplemented `tail -f` semantics?
- **Resolution:** Define streaming as one-pass bounded-memory processing from file/stdin, state that output occurs after EOF, and defer indefinite follow behavior as P2.

#### Challenge 3: Hour buckets can vary with timezone interpretation

- **Weakness:** Converting offsets through the host timezone makes the same log produce different hourly results on different laptops.
- **Risk level:** High.
- **Alternative:** Normalize all timestamps to UTC before bucketing.
- **Trade-off:** UTC is globally comparable but no longer represents the hour written by nginx, which is the most direct local traffic view.
- **Question for architect:** Which clock defines an “hour,” and can the result remain invariant across hosts?
- **Resolution:** Use the hour as written with the log's explicit numeric offset and never convert through host local time.

#### Challenge 4: Multiple views do not naturally fit one CSV table

- **Weakness:** Independent ranked, hourly, and summary shapes can lead to unstable ad hoc column layouts.
- **Risk level:** Medium.
- **Alternative:** Emit a ZIP or directory containing one CSV per view.
- **Trade-off:** Separate files are relationally cleaner but cannot be emitted as one simple stdout pipeline artifact.
- **Question for architect:** Can downstream tools distinguish rows without guessing from blank columns?
- **Resolution:** Specify one normalized `section,rank,key,count,percentage` schema, fixed section order, and golden tests.

#### Challenge 5: Invalid-line policy can hide loss or make logs unusable

- **Weakness:** Always skipping damaged lines under-reports problems; always failing makes a single bad line prevent useful analysis.
- **Risk level:** High.
- **Alternative:** Choose only a strict fail-fast parser.
- **Trade-off:** Strict-only behavior maximizes integrity but reduces practical value on imperfect operational logs.
- **Question for architect:** How does a pipeline distinguish a fully valid report from one based on partially rejected input?
- **Resolution:** Default to counted skips, expose `invalid_lines` in every format, add `--fail-on-invalid`, and map strict rejection to exit 3.

#### Challenge 6: The performance target is environment-dependent

- **Weakness:** “1 GB under 30 seconds on a laptop” is not reproducible without hardware and fixture characteristics.
- **Risk level:** Medium.
- **Alternative:** Replace the target with records per second independent of a named environment.
- **Trade-off:** Throughput is more comparable but still depends on record length and does not directly prove the user's stated file-size goal.
- **Question for architect:** What evidence makes a pass repeatable and prevents a favorable synthetic fixture from masking worst-case cardinality?
- **Resolution:** Bind acceptance evidence to the exact candidate, documented Python/CPU/storage environment, byte size, fixture distribution, wall time, and peak RSS; keep correctness/cardinality tests separate.

**Alternatives considered and rejected:** multiprocess chunking is premature without profiling and fails for general stdin; SQLite violates statelessness and adds write cost; a regex-per-metric grep pipeline repeats parsing and weakens the output contract; an HTTP service contradicts the product boundary.

The conditions above are incorporated into this architecture, [PRD.md](PRD.md), and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
