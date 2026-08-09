# Project Architecture: StreamSift

## 1. Context and Goals

StreamSift is a pip-installable Python 3.11 CLI that consumes nginx access-log lines from a file or stdin and computes four summaries in one process. The primary quality attributes are correctness, deterministic pipeline output, low operational burden, and processing a representative 1 GB log in under 30 seconds on a documented laptop.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect here because the product emits a one-shot summary, must avoid persistence and operational setup, and can maintain only aggregation state during a run. An HTTP API is incorrect because the users and integrations are local shells, cron jobs, and pipelines; a server would add lifecycle, port, security, and deployment concerns without improving the requested workflow.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (selected)

- **Approach:** Click owns input validation; a line iterator feeds a parser and one in-memory aggregator; immutable result dataclasses feed one selected renderer.
- **Pros:** One pass, direct failure semantics, minimal packaging, no IPC, easy profiling.
- **Cons:** CPU work remains single-core; distinct-key maps can grow until the explicit cap.
- **Best for:** A local one-shot CLI and one-weekend delivery.
- **Estimated complexity:** Low.

### Variant B: Unix composition of independent metric commands

- **Approach:** Four subcommands each parse the same stream and compute one metric, composed by the caller.
- **Pros:** Very small components; individual metric invocation is simple.
- **Cons:** Four passes or external teeing, inconsistent atomic failure, more pipeline complexity, worse 1 GB performance.
- **Best for:** Environments where each metric is always used alone.
- **Estimated complexity:** Medium.

### Variant C: Multiprocess parsing and reduction

- **Approach:** Partition input among workers and merge partial counters.
- **Pros:** Potential CPU parallelism.
- **Cons:** Complex ordered input, IPC and merge overhead, higher peak memory, harder stdin/error semantics, poor weekend fit.
- **Best for:** A later version proven CPU-bound by measurement.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the architecture choice is obvious under the approved local, stateless, one-weekend scope. Variants B and C are documented to expose trade-offs, not to reopen the decision.

## 3. Component Model and Data Flow

```text
file path or stdin
       |
       v
Click command / input adapter
       |
       v  Iterator[str]
nginx line parser ---- malformed line ----> diagnostic counter
       |
       v  AccessRecord
StreamingAggregator
  |-- IP Counter
  |-- error-URL Counter (status 400..599 only)
  |-- 24 hourly counters
  `-- User-Agent set + cardinality guard
       |
       v  AnalysisResult
Rich renderer | JSON renderer | CSV renderer
       |
       +---- results to stdout
       `---- diagnostics/errors to stderr
```

One `AccessRecord` exists only for the duration of an iteration. The aggregator retains counts keyed by distinct IP and error URL, 24 integer hourly buckets, and distinct User-Agent values. It never retains raw lines or a list of records. Before inserting any new distinct key, the shared unique-cardinality guard checks the configured cap; exhaustion terminates safely with exit code `4`.

## 4. Module and File Boundaries

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Python requirement, dependencies, console entry point, tool configuration |
| `src/streamsift/cli.py` | Click command, option validation, input/output selection, exception-to-exit mapping |
| `src/streamsift/model.py` | `AccessRecord`, metric row, summary, and diagnostic dataclasses |
| `src/streamsift/parser.py` | Compile grammar once; convert a supported nginx line into `AccessRecord` |
| `src/streamsift/aggregate.py` | Single-pass counters, ranking, percentages, cardinality cap |
| `src/streamsift/render.py` | Rich, JSON, and normalized CSV serialization |
| `src/streamsift/errors.py` | Typed domain failures and canonical exit-code constants |
| `tests/fixtures/` | Small supported, malformed, empty, tie, and high-cardinality logs |
| `tests/test_parser.py` | Parsing and malformed-line behavior |
| `tests/test_aggregate.py` | Metrics, filtering, formula, tie-breaking, guard behavior |
| `tests/test_cli.py` | Options, streams, schemas, stderr separation, exit codes |
| `tests/test_performance.py` | Opt-in generated-input benchmark and memory-scaling checks |

Dependency direction is `cli -> parser/aggregate/render -> model/errors`; renderers never parse input, and aggregation never writes output.

## CLI Interface

### Command

```text
streamsift [OPTIONS] [INPUT]
```

`INPUT` is an optional nginx access-log path. Omitting it or passing `-` reads stdin. Exactly one input stream is processed per invocation. The only supported MVP record grammar is the documented nginx combined log format; the parser also accepts the common-log prefix when the referrer and User-Agent fields are present as `-` placeholders. Bytes are decoded as UTF-8 with replacement for invalid byte sequences so one bad byte cannot crash a long run.

### Options

| Option | Meaning | Default/constraint |
|---|---|---|
| `--json` | Emit one JSON document | Mutually exclusive with `--csv` |
| `--csv` | Emit normalized CSV rows | Mutually exclusive with `--json` |
| `--color / --no-color` | Force or suppress ANSI styling in terminal mode | Auto: color only on a TTY |
| `--max-cardinality INTEGER` | Maximum total distinct tracked IP, error-URL, and User-Agent keys before safe abort | Positive integer; documented default `1_000_000` |
| `--strict` | Treat the first malformed nonblank record as a parse failure | Default: skip malformed lines and report count |
| `--version` | Print version and exit | No input consumed |
| `--help` | Print usage and exit | No input consumed |

### Outputs

Default terminal output contains four labeled Rich tables/summary panels plus `valid`, `malformed`, and `total` record counts. Rankings contain at most 10 rows and use count descending, then key lexicographically ascending for deterministic ties.

JSON stdout is one UTF-8 object:

```json
{
  "schema_version": 1,
  "total_lines": 0,
  "valid_requests": 0,
  "malformed_lines": 0,
  "top_ips": [{"ip": "192.0.2.1", "request_count": 3}],
  "top_error_urls": [{"url": "/missing", "error_count": 2}],
  "hourly_request_distribution": [{"hour": "00", "request_count": 1, "percentage": 25.0}],
  "unique_user_agents": 1,
  "unique_user_agent_share_percentage": 25.0
}
```

CSV stdout begins `metric,dimension,count,percentage`. Ranking rows use metric `top_ip` or `top_error_url`; hourly rows use `hourly_request_distribution`; the User-Agent summary uses `unique_user_agent_share`. Inapplicable cells are empty. CSV values are escaped by Python's `csv` module.

Diagnostics and fatal error messages go only to stderr and contain no traceback unless a future explicit debug option is added.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Analysis completed; valid requests were processed and output was written |
| `1` | Input/output runtime failure, such as unreadable file, broken read, or write failure |
| `2` | CLI usage error, including invalid options, nonexistent option value, or conflicting formats |
| `3` | Log-data failure: strict-mode malformed record or input containing no valid requests |
| `4` | Unique-cardinality exhaustion: the configured distinct-key limit would be exceeded |

### Metric Semantics

- Top IPs count every valid request by parsed client IP.
- Top error URLs count request-target occurrences whose integer status is 400–599 inclusive. Query strings remain part of the request target in MVP.
- Hour is derived from the numeric offset in each nginx timestamp and labeled `00` through `23`. Each percentage is `100 × hourly_request_count / total_valid_requests`; values are rounded to two decimal places only during serialization, and all 24 buckets are emitted.
- Unique User-Agent share is `100 × distinct_nonempty_user_agent_count / total_valid_requests`, rounded to two decimal places during serialization. Repeated requests by the same User-Agent do not increase the numerator; `-` is treated as missing and excluded.
- A top-10 list has fewer than 10 rows when fewer keys exist. A request with a valid grammar but unexpected status outside 100–599 is malformed.

## 6. Data Model and State

There are no database tables, migrations, files written for persistence, caches, or network calls.

| Dataclass/state | Fields | Lifetime/invariant |
|---|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `method: str`, `target: str`, `protocol: str`, `status: int`, `user_agent: str | None` | One parsed iteration; status 100–599 |
| `AnalysisState` | `total_lines: int`, `valid_requests: int`, `malformed_lines: int`, `ip_counts: Counter[str]`, `error_url_counts: Counter[str]`, `hour_counts: list[int]`, `user_agents: set[str]` | One invocation; `hour_counts` length is 24 |
| `RankedCount` | `key: str`, `count: int` | Final immutable output row |
| `HourlyShare` | `hour: int`, `request_count: int`, `percentage: float` | Final immutable output row; 24 rows |
| `AnalysisResult` | record totals, ranked tuples, hourly tuple, User-Agent cardinality/share | Renderer input; internally consistent totals |

Worst-case memory is `O(U_ip + U_error_url + U_user_agent)`, bounded by `--max-cardinality`; time is expected `O(N + U log 10)` using `Counter` updates and bounded top selection, where `N` is valid lines and `U` is distinct ranked keys.

## 7. Parsing and Failure Policy

The parser compiles its expression once at import or parser construction, parses the nginx time with its explicit UTC offset, and extracts the request triplet without splitting quoted fields naively. Blank and malformed lines increment diagnostics in default mode. In `--strict`, the first malformed line becomes exit `3`. If zero valid records remain, no percentages are divided by zero: the invocation exits `3` without a results payload.

The CLI catches only expected domain, Click, I/O, and broken-pipe conditions at its boundary. Broken pipe follows runtime-output failure code `1`; it emits no noisy traceback. Unexpected defects are not silently converted into successful output.

## 8. Output Compatibility

Human formatting may evolve without schema guarantees. JSON includes `schema_version: 1`; field removal or semantic change requires a schema-version increment. CSV column names and metric discriminators are a public contract. Numeric values use locale-independent decimal points. Sorting and UTF-8 encoding are deterministic. stdout contains exactly the selected result format; warnings go to stderr.

## 9. Packaging, Security, and Deployment

Distribution is a standard wheel/sdist installed with pip into a virtual environment or tool runner. Deployment means local installation; there is no Docker image, daemon, cloud environment, Kubernetes manifest, authentication flow, secret, port, or environment variable required. Dependency versions use compatible lower bounds and are tested on Python 3.11.

Logs are untrusted data. The implementation does not evaluate fields, interpolate them into shell commands, open URLs found in logs, or write them to filenames. Rich rendering escapes markup/control sequences. JSON and CSV use standard serializers. Input files are opened read-only. No telemetry or log content leaves the machine.

## 10. Performance Strategy

- Read through a buffered text iterator and process each line exactly once.
- Compile parsing machinery once; avoid intermediate dictionaries and retained raw records.
- Update all four aggregations in the same loop.
- Use bounded top selection and defer percentage/serialization work until EOF.
- Generate the 1 GB performance fixture outside the repository, record its format/cardinality and machine details, and time the installed command with stdout redirected.
- Profile if the target fails; multiprocess parsing is permitted only through a later architecture decision backed by evidence.

## 11. Verification Strategy

Unit tests cover parser edge cases and pure metric computations. Click's test runner covers file/stdin equivalence, mutually exclusive modes, stdout/stderr separation, all exit codes, TTY color policy, broken input, and golden JSON/CSV. Property checks assert sum of hourly counts equals valid requests and percentages are derived from unrounded counts. The opt-in performance test records wall time and peak memory on a documented reference machine.

## 12. Architecture Decision Record and Self-Critique

No independent or adversarial reviewer was available for this benchmark. The following is a labeled self-critique, not an independent review.

**Self-critique verdict: APPROVE WITH CONDITIONS.**

| Challenge | Resolution/condition |
|---|---|
| Exact regex parsing can reject legitimate custom nginx formats | MVP explicitly declares its grammar; fixtures cover escapes and placeholders; custom format support is deferred |
| Cardinality across three containers can grow before a per-container limit is noticed | Use one aggregate distinct-insertion budget and check before every insertion; exit `4` deterministically |
| A set gives exact User-Agent share but can dominate memory | Exactness is an approved requirement; bounded cardinality fails safely rather than silently approximating |
| Python may miss 1 GB/30 s | Make the benchmark a release gate, profile early, and avoid architecture escalation without evidence |
| Per-record timezone offsets make “hourly” ambiguous | Define hour as the hour written in each record's offset, document it, and test mixed offsets |
| CSV combines heterogeneous metrics | A normalized four-column schema plus discriminator is explicit and pipeline-friendly |
| Skipped malformed lines can hide poor input quality | Always report counts on stderr/default report; `--strict` and no-valid-data exit `3` provide fail-fast modes |

Rejected alternatives are persistent analytics stacks (violate local/stateless/$0 constraints), database-backed ingestion (unnecessary persistence), an HTTP service (wrong interface and added security lifecycle), repeated shell pipelines (weaker parsing and performance contract), and multiprocessing (unjustified complexity until profiling demonstrates need).

