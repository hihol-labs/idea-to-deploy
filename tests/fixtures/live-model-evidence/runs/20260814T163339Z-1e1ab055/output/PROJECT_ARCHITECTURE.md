# Project Architecture: Nginx Stream Analytics CLI

## Architecture Summary

The approved architecture is a pip-installable Python 3.11 package containing one Click process and a single-pass streaming pipeline:

```text
file path or stdin
        |
        v
line iterator -> combined-log parser -> validated LogRecord
        |                                 |
 malformed counter                        v
                                streaming aggregators
                                | IP Counter
                                | error-URL Counter
                                | 24 hourly buckets
                                | exact User-Agent set (capped)
                                v
                              Summary
                        /        |        \
                  Rich text     JSON      CSV
```

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the utility produces one summary from one stream, has no cross-run queries, and must add no persistence, migration, or cleanup burden. An HTTP API is incorrect because the users already operate in terminals and pipelines, logs may be sensitive, and a resident service would add authentication, network exposure, deployment, and lifecycle concerns without improving the four required metrics.

## Architecture Alternatives

The single-process variant is pre-approved because the workload is sequential parsing with small aggregate state and the one-weekend delivery constraint favors a low-overhead design.

| Variant | Benefits | Costs | Decision |
|---|---|---|---|
| A. Single-process streaming Python CLI | Simplest install, deterministic order, no IPC, direct stdin support | One CPU core; exact distinct values consume memory | **Selected** |
| B. Multi-process chunk parser | Potential CPU scaling for seekable files | Complicated line boundaries, merging, stdin behavior, and profiling; overhead may dominate | Rejected for MVP |
| C. Embedded analytical database | Flexible follow-up queries | Violates stateless constraint and adds persistence/I/O lifecycle | Rejected |

GoAccess, Logstash/Elastic/Kibana, AWStats, and shell pipelines remain product alternatives rather than internal architecture variants; their trade-offs are recorded in `STRATEGIC_PLAN.md`.

## CLI Interface

### Command

```text
nginx-stream-report [OPTIONS] [INPUT]
```

`INPUT` is an optional path to an nginx combined access-log file. If omitted or exactly `-`, bytes are read from standard input. Input is decoded as UTF-8 with invalid byte sequences treated as malformed lines; the process never seeks and never loads the full file.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one UTF-8 JSON object to stdout |
| `--csv` | flag, false | Emit normalized UTF-8 CSV rows to stdout |
| `--no-color` | flag, false | Disable ANSI color in terminal mode; color is also disabled when stdout is not a TTY |
| `--strict` | flag, false | Return 3 if any input line is malformed; still do not emit a misleading partial report |
| `--max-unique-user-agents INTEGER` | default `1000000` | Positive hard limit for exact unique User-Agent values; crossing it returns 4 |
| `--version` | flag | Print version and exit 0 |
| `--help` | flag | Print Click help and exit 0 |

`--json` and `--csv` are mutually exclusive. Invalid combinations and invalid option values are Click usage errors (exit 2).

### Metrics and Deterministic Ordering

- `top_ips`: up to 10 IP/count pairs over valid requests, sorted by count descending then IP text ascending.
- `top_error_urls`: up to 10 URL/count pairs for responses with status 400–599, sorted by count descending then URL ascending. Query strings remain part of the request target in the MVP.
- `hourly_distribution`: 24 local-offset hour buckets (`00` through `23`) taken from each log timestamp. Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`. When there are zero valid requests, every hourly percentage is `0.0`.
- `unique_user_agent_share_percent`: `100 × unique_user_agent_count / total_valid_requests`, or `0.0` when there are zero valid requests. Missing/empty User-Agent fields are invalid under the combined-format parser and count as malformed lines.
- Percentages are rounded only during rendering to two decimal places; internal calculations retain full precision.

### Outputs

Default terminal output writes a Rich summary to stdout with four sections and an input-quality footer (`total_lines`, `valid_requests`, `malformed_lines`). Diagnostics go to stderr.

JSON schema:

```json
{
  "schema_version": "1",
  "input": {"total_lines": 0, "valid_requests": 0, "malformed_lines": 0},
  "top_ips": [{"ip": "192.0.2.1", "count": 12}],
  "top_error_urls": [{"url": "/missing", "count": 4}],
  "hourly_distribution": [{"hour": "00", "request_count": 0, "percentage": 0.0}],
  "user_agents": {"unique_count": 0, "share_percent": 0.0}
}
```

CSV is a single normalized table with the header `section,rank,key,count,percentage`. Top lists use `rank`, `key`, and `count`; hourly rows use `key` as `00`–`23`, `count`, and `percentage`; the User-Agent summary uses `key=unique_user_agents`, `count`, and `percentage`. Empty non-applicable cells remain empty. RFC 4180 quoting is applied by Python's `csv` module.

### Exit Codes

| Code | Meaning | Output rule |
|---:|---|---|
| `0` | Success | Complete report emitted; malformed lines are allowed unless `--strict` |
| `1` | Input/runtime I/O failure | No report; concise diagnostic on stderr |
| `2` | CLI usage error | Click-generated usage diagnostic on stderr |
| `3` | Strict parse failure | No report; malformed-line diagnostic on stderr |
| `4` | Unique-cardinality exhaustion | No report; limit and remediation diagnostic on stderr |

No partial machine-readable report is emitted for codes 1, 2, 3, or 4.

## Package and Module Boundaries

```text
pyproject.toml
src/nginx_stream_report/
  __init__.py          # package version only
  cli.py               # Click command, option validation, exit mapping
  models.py            # frozen LogRecord, Summary, ranked-item dataclasses
  parser.py            # bytes/text line to LogRecord or ParseError
  aggregate.py         # mutable single-pass accumulator and finalization
  render_text.py       # Rich renderer
  render_json.py       # JSON renderer
  render_csv.py        # normalized CSV renderer
tests/
  fixtures/            # small synthetic log inputs with documented expected values
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_renderers.py
  test_performance.py
```

Dependencies flow inward: `cli` orchestrates parser, aggregator, and renderers; renderers consume only frozen summary dataclasses; parser and aggregator do not import Click or Rich.

## Domain and Data Model

There are no database tables. In-memory state is intentionally explicit:

| Dataclass/state | Fields and types | Invariant |
|---|---|---|
| `LogRecord` | `ip: str`, `timestamp: datetime`, `method: str`, `target: str`, `protocol: str`, `status: int`, `bytes_sent: int | None`, `referrer: str`, `user_agent: str` | Constructed only from a fully valid combined-format line |
| `RankedIP` | `ip: str`, `count: int` | Positive count |
| `RankedURL` | `url: str`, `count: int` | Positive count; source status was 400–599 |
| `HourlyBucket` | `hour: int`, `request_count: int`, `percentage: float` | Hour 0–23; 24 buckets always present |
| `UserAgentStats` | `unique_count: int`, `share_percent: float` | Exact count below or at configured cap |
| `InputStats` | `total_lines: int`, `valid_requests: int`, `malformed_lines: int` | `total_lines = valid_requests + malformed_lines` |
| `Summary` | `input: InputStats`, `top_ips: tuple[RankedIP, ...]`, `top_error_urls: tuple[RankedURL, ...]`, `hourly_distribution: tuple[HourlyBucket, ...]`, `user_agents: UserAgentStats` | Immutable renderer input |
| `Accumulator` | `ip_counts: Counter[str]`, `error_url_counts: Counter[str]`, `hour_counts: list[int]`, `user_agents: set[str]`, integer counters | Exists for one run only |

Memory is `O(distinct IPs + distinct error URLs + distinct User-Agents)`. The first two counters are necessary for exact top-10 results; the User-Agent set has a hard configurable cap. Exceeding the cap raises a typed domain error mapped to exit 4. No approximate answer is silently substituted.

## Parsing Contract

The parser accepts nginx's conventional combined format: remote address, remote user, bracketed timestamp with numeric UTC offset, quoted request line, status, byte count (`-` allowed), quoted referrer, and quoted User-Agent. It parses without catastrophic-backtracking regexes. A request line must contain exactly method, target, and protocol tokens; status must be 100–599; timestamp must match `%d/%b/%Y:%H:%M:%S %z`.

Blank, truncated, undecodable, or semantically invalid lines increment `malformed_lines`. In default mode processing continues. In `--strict` mode the implementation may continue counting for a useful diagnostic but must emit no report and must return 3 if any malformed line was observed.

## Processing Lifecycle

1. Click validates mutually exclusive formats, positive cardinality limit, and input argument.
2. The CLI opens the path in binary mode or binds stdin without taking ownership of its lifecycle.
3. Each line is decoded and parsed independently.
4. Valid records update the four aggregations; malformed lines update quality counters.
5. Cardinality overflow stops processing immediately and maps to exit 4.
6. End of input finalizes deterministic top lists and percentages into `Summary`.
7. Strict-mode parse failures map to exit 3; otherwise exactly one renderer writes stdout and returns 0.
8. Broken pipe is handled quietly using normal CLI conventions; other read/write failures map to exit 1.

## Error and Observability Contract

Diagnostics are single-line, actionable stderr messages without tracebacks for expected failures. Tests may enable exception propagation internally. The CLI never logs input lines, URLs, IPs, or User-Agents to a remote system. The footer exposes line-quality counts, while elapsed time and throughput may be included only on stderr behind a future opt-in diagnostics option.

## Performance Architecture

- Stream with buffered binary I/O; do not call `read()` without a bounded size or materialize all lines.
- Keep the hot loop free of Rich, JSON serialization, and per-record logging.
- Use `Counter`, a fixed 24-integer list, and one exact capped set.
- Parse only fields needed by the contract, while retaining the typed record boundary for testability.
- Benchmark in a separate test marker against a generated-on-disk 1 GB fixture that is excluded from version control.
- Record laptop CPU, storage, OS, Python patch version, bytes processed, wall time, throughput, and peak RSS. Acceptance requires wall time under 30 seconds.

## Security and Privacy

The trust boundary is the local input stream. Treat every field as untrusted data: apply no `eval`, shell invocation, template interpretation, path construction, or terminal markup parsing. Rich text rendering must escape or disable markup for log-derived strings; CSV and JSON use standard-library encoders. File access is read-only. Results remain local unless the caller redirects them. No authentication is needed because there is no network service or shared state.

## Configuration and Environment

There are no required environment variables, `.env` files, Docker services, or runtime configuration files. Locale must not alter timestamp parsing, sorting, JSON keys, decimal separators, or CSV delimiters. Standard conventions such as `NO_COLOR` may complement `--no-color`, but explicit CLI options win.

## Packaging and Deployment

Deployment means publishing an sdist and universal Python wheel to a Python package index and installing it with pip into Python 3.11. `pyproject.toml` declares Click and Rich runtime dependencies, a `nginx-stream-report` console script, build backend, Python constraint, license, and classifiers. The release workflow builds artifacts, validates metadata, installs the wheel in a clean virtual environment, and runs smoke tests. Docker, Compose, servers, cloud resources, and Kubernetes are intentionally absent.

## Architecture Decision Records

### ADR-001: Single-process streaming pipeline

- **Status:** Accepted (pre-approved product decision)
- **Decision:** Use one Python process, one pass over input, and in-memory exact aggregators.
- **Why:** Lowest implementation and operating complexity, natural stdin support, deterministic output, and adequate target scale pending benchmark evidence.
- **Consequence:** Exact distinct-key state can grow; User-Agent cardinality is capped and other aggregate growth is measured during performance testing.

### ADR-002: No persistent or network service layer

- **Status:** Accepted (pre-approved product constraint)
- **Decision:** Apply the literal constraint stated in the Architecture Summary.
- **Why:** The workload is run-scoped and local; persistence and remote access add risks with no required capability.
- **Consequence:** Cross-run history and dashboards remain out of scope.

### ADR-003: One summary model, three renderers

- **Status:** Accepted
- **Decision:** Render text, JSON, and CSV from the same immutable `Summary`.
- **Why:** Prevents metric drift and enables cross-format contract testing.
- **Consequence:** Output schema changes require coordinated versioning and PRD updates.

No adversarial or independent review was performed in this blueprint session; that review is deliberately reserved for the external harness and is not represented by an artifact here.

## Related Documents

Product requirements and acceptance criteria are in `PRD.md`. The ordered delivery plan is in `IMPLEMENTATION_PLAN.md`; implementation prompts must preserve these architecture decisions.
