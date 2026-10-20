# Project Architecture: nginx-log-top

## Context and Goals

The product is an installable Python 3.11 CLI that performs one-pass analysis of nginx Combined Log Format access logs. It must accept a path or stdin, retain no raw log lines, render colored terminal text by default, and offer stable JSON and CSV output. The performance objective is 1 GB in under 30 seconds on a documented representative laptop.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect here because the requested metrics can be accumulated during a single pass, persistence would add I/O and operational cost, and the product explicitly avoids retained log data. An HTTP API is incorrect because the operator runs analysis locally against a file or pipe; a server would add lifecycle, authentication, network-exposure, and deployment concerns without improving that workflow.

## Architecture Decision

Use one synchronous process with a narrow pipeline:

```text
file path or stdin
       |
       v
line iterator -> CLF parser -> aggregate state -> immutable AnalysisResult
                                                       |
                                      +----------------+---------------+
                                      v                v               v
                                  Rich text          JSON             CSV
```

The process is CPU-bound during parsing. Synchronous iteration minimizes copying and makes input errors and exit codes deterministic. There are no workers, network calls, background tasks, persistence layers, or cross-process synchronization.

## Architecture Variants

The single-process design is pre-approved; these variants record the decision rather than request a new choice.

### Variant A: Single-process Python stream (Selected)

- **Approach:** Click invokes a parser/aggregator pipeline and one renderer.
- **Pros:** Small install, testable modules, deterministic output, no services, weekend-sized.
- **Cons:** Exact high-cardinality sets can consume memory; pure-Python parsing must be benchmarked.
- **Best for:** Local one-shot incident analysis and shell pipelines.
- **Estimated complexity:** Low.

### Variant B: Unix-tool composition

- **Approach:** Document `awk`, `sort`, `uniq`, and `jq` recipes.
- **Pros:** Few dependencies and familiar primitives.
- **Cons:** Parsing is fragile, recipes diverge, repeated passes and external sorts undermine the fixed contract.
- **Best for:** One-off exploratory work on small known formats.
- **Estimated complexity:** Low initially, high to support reliably.

### Variant C: Existing analytics suite

- **Approach:** Adopt GoAccess or ship logs to Logstash/Elastic/Kibana or AWStats.
- **Pros:** Richer mature feature sets.
- **Cons:** Broader scope, more configuration, and—in the stack case—services and persistence explicitly outside the boundary.
- **Best for:** Long-lived dashboards, retention, and interactive exploration.
- **Estimated complexity:** Medium to high operationally.

### Recommendation

Variant A is selected because it alone matches the fixed Python stack, $0 budget, one-weekend delivery, local-data boundary, machine-output contract, and stateless performance goal.

## CLI Interface

### Command

```text
nginx-log-top [OPTIONS] [INPUT]
```

`INPUT` is an nginx access-log path. `-` or an omitted argument reads UTF-8 text from stdin. The MVP supports nginx Combined Log Format; undecodable bytes and non-matching lines are malformed records.

### Options

| Option | Type / default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one JSON object to stdout; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit normalized CSV to stdout; mutually exclusive with `--json` |
| `--no-color` | flag, false | Disable ANSI styling in terminal mode; machine formats never contain ANSI |
| `--max-unique-user-agents INTEGER` | default `1_000_000` | Positive ceiling for exact unique User-Agent cardinality |
| `--strict` | flag, false | Stop at the first malformed line with exit code 3 instead of counting and continuing |
| `--version` | flag | Print version and exit 0 |
| `--help` | flag | Print usage and exit 0 |

Specifying both `--json` and `--csv`, a non-positive cardinality ceiling, or an invalid option is a usage error. Diagnostics go to stderr; reports go to stdout.

### Inputs

- A regular text file, named pipe, or stdin stream.
- One request per physical line in nginx Combined Log Format:
  `$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"`.
- Empty input is valid and yields zero counts, empty rankings, 24 zero percentages, and a `0.0` unique User-Agent share.
- Malformed lines are skipped and counted unless `--strict` is active.

### Outputs

- **Terminal (default):** Rich summary and four sections: top client IPs, top error URLs, hourly distribution, and User-Agent uniqueness. Color is enabled only for an interactive TTY unless forced off.
- **JSON:** A versioned object with `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`. Ranking entries carry `rank`, key, and `count`; hours are strings `00` through `23` with `request_count` and `percentage`.
- **CSV:** UTF-8 RFC 4180 rows with header `section,rank,key,count,percentage`. Summary and User-Agent scalar metrics use an empty rank; absent values are empty fields.

Hourly request distribution is a percentage for each parsed timestamp hour, calculated as `100 × hourly_request_count / total_valid_requests`; when there are no valid requests, every hourly percentage is `0.0`. Percentages are rounded to two decimal places only at rendering time.

User-Agent share is `100 × unique_nonempty_user_agent_count / total_valid_requests`; a missing or `-` User-Agent is not added to the unique set, while its request remains valid. Exact tracking stops before the configured ceiling would be exceeded.

Stable ranking order is count descending, then key lexicographically ascending. Only statuses 400–599 contribute to `top_error_urls`. The URL key is the raw request-target token, without query normalization in the MVP.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Analysis completed and output was emitted, including empty input |
| `1` | Input I/O failure, including missing file, permission error, or read failure |
| `2` | CLI usage or option-validation error |
| `3` | Parsing failure in strict mode or no usable parser state due to an internal format error |
| `4` | Unique-cardinality exhaustion: the configured exact User-Agent ceiling would be exceeded |

The complete public exit-code contract is `0/1/2/3/4`. Unexpected internal exceptions are caught at the CLI boundary, reported without a traceback by default, and mapped to `3`.

## Package and Module Structure

```text
pyproject.toml
src/nginx_log_top/
  __init__.py          # package version
  __main__.py          # python -m entry point
  cli.py               # Click command, error mapping, stream ownership
  models.py            # ParsedRequest, AnalysisResult dataclasses
  parser.py            # compiled CLF parser and timestamp conversion
  aggregate.py         # streaming counters and cardinality guard
  renderers/
    __init__.py
    text.py            # Rich terminal output
    json.py            # versioned JSON schema
    csv.py             # normalized CSV schema
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_renderers.py
  test_performance.py
```

## Component Contracts

### Parser

`parse_line(line: str, line_number: int) -> ParsedRequest` either returns a frozen dataclass or raises a typed `MalformedLine` carrying the line number and a safe reason. A compiled regular expression extracts the bounded CLF fields. Timestamp parsing accepts nginx's numeric UTC offset; the local hour token from the timestamp determines the report bucket, so logs spanning offsets retain their recorded local-hour meaning.

### Aggregator

`Analyzer.consume(ParsedRequest)` increments `total_valid_requests`, a 24-slot integer array, client-IP counts, error-URL counts for statuses 400–599, and an exact set of nonempty User-Agents. It does not retain `ParsedRequest` objects. `finalize(malformed_count)` returns an immutable `AnalysisResult` and selects top-10 rows with deterministic tie-breaking.

IP and error-URL counters can grow with distinct keys. This is an accepted exactness trade-off for the MVP benchmark, measured explicitly in stress tests. The User-Agent set has a hard configured ceiling because its exact cardinality has a public failure contract.

### Renderers

Renderers depend only on `AnalysisResult`, never on Click or open streams. JSON uses `json.dumps(..., ensure_ascii=False)` and a schema version of `1`. CSV uses Python's `csv.writer`. Rich writes only in terminal mode and is configured with `color_system=None` when output is redirected or `--no-color` is set.

## Data Model

There is no database schema. These in-memory dataclasses are the full domain model:

| Dataclass | Field | Type | Constraint |
|---|---|---|---|
| `ParsedRequest` | `ip` | `str` | Nonempty parsed token |
|  | `timestamp` | `datetime` | Offset-aware |
|  | `request_target` | `str` | Extracted from request line; `-` allowed |
|  | `status` | `int` | 100–599 |
|  | `user_agent` | `str | None` | `None` for missing/`-` |
| `RankedCount` | `key` | `str` | IP or URL |
|  | `count` | `int` | Positive |
| `HourlyBucket` | `hour` | `int` | 0–23 |
|  | `request_count` | `int` | Nonnegative |
|  | `percentage` | `float` | 0–100, derived at finalization |
| `AnalysisResult` | `total_lines` | `int` | Valid plus malformed |
|  | `total_valid_requests` | `int` | Nonnegative |
|  | `malformed_lines` | `int` | Nonnegative |
|  | `top_ips` | `tuple[RankedCount, ...]` | At most 10 |
|  | `top_error_urls` | `tuple[RankedCount, ...]` | At most 10 |
|  | `hourly_distribution` | `tuple[HourlyBucket, ...]` | Exactly 24, ordered |
|  | `unique_user_agent_count` | `int` | Nonnegative and at most configured ceiling |
|  | `unique_user_agent_share` | `float` | Percentage of valid requests |

## Performance and Resource Model

- Read through the text iterator with the platform's buffered I/O; never call `read()` without a bound.
- Compile parsing expressions once and avoid intermediate dictionaries in the hot path.
- Maintain `O(D_ip + D_error_url + D_ua + 24)` memory, where each `D` is distinct observed cardinality; raw input size is not retained.
- Compute top 10 using `heapq.nsmallest`/`nlargest` semantics with explicit stable keys rather than sorting raw records.
- Benchmark with a generated, deterministic 1 GB fixture outside the repository and record Python version, CPU, storage, elapsed time, throughput, and maximum RSS.
- Treat the 30-second target as a release gate on the representative laptop, not a universal hardware guarantee.

## Error Handling and Security

- Open user paths read-only; never follow input content as commands or format strings.
- Avoid logging complete malformed lines because URLs and User-Agents may contain secrets or personal data.
- Write concise diagnostics with line numbers to stderr and cap repeated malformed-line warnings.
- Handle `BrokenPipeError` as normal pipeline termination without a traceback.
- Set CSV quoting through the standard library, and JSON escaping through the standard encoder.
- The tool performs no network access, dynamic imports, subprocess execution, authentication, or secret storage.

## Packaging and Deployment

The deployment target is the user's local Python 3.11 environment. A PEP 517 package defined by `pyproject.toml` exposes the console script `nginx-log-top = nginx_log_top.cli:main`. Build universal wheels and source distributions; users install via `pipx install nginx-log-top` or `python -m pip install nginx-log-top`. No Docker image, service manager, cloud resource, or Kubernetes manifest is part of the product.

Runtime dependencies are pinned by compatible major/minor bounds for Click and Rich. Development dependencies are optional extras. The package version is available through both `importlib.metadata` and `--version`.

## Test Strategy

- Parser unit tests cover IPv4/IPv6, escaped quotes, query strings, all status classes, timezone offsets, malformed records, and non-ASCII User-Agents.
- Aggregation tests cover deterministic ties, exactly 10 rows, status boundaries 399/400/599, empty input, all 24 hours, and the percentage formula.
- Cardinality tests prove that the ceiling is accepted and the next distinct User-Agent exits 4 without partial output.
- CLI tests cover file/stdin parity, stdout/stderr separation, mutually exclusive modes, color behavior, and every exit code in `0/1/2/3/4`.
- Golden renderer tests parse JSON structurally and CSV with `csv.reader`; ANSI absence is asserted for machine modes.
- A performance test generates data outside version control and is opt-in locally; release evidence records the 1 GB wall-clock and RSS measurements.

## Decision Records

### ADR-001: Stateless synchronous pipeline

- **Status:** Accepted and pre-approved.
- **Decision:** One Python process streams records into in-memory aggregates.
- **Consequences:** Minimal operations and predictable flow; exact distinct-key state can grow and must be measured.

### ADR-002: Exact User-Agent cardinality with a hard ceiling

- **Status:** Accepted.
- **Decision:** Preserve exact metrics until the configured ceiling, then fail with exit code 4.
- **Consequences:** No silent approximation; callers can distinguish resource-policy failure and retry with a deliberate ceiling.

### ADR-003: No in-session adversarial review artifact

- **Status:** Deferred to the external benchmark harness by instruction.
- **Decision:** This blueprint records no claim that an adversarial or independent reviewer ran, and does not create a review artifact.
- **Consequences:** Architecture review evidence, if any, is produced separately after this workflow exits.

