# Project Architecture: nginx-stream-stats

## 1. Context and Goals

The system is an installable Python 3.11 CLI that analyzes nginx combined access logs locally in one pass. Its architectural boundary is explicit: **no database — stateless streaming processing; no HTTP API — CLI-only tool**. Both constraints are correct because a database would add ingestion, schema, retention, cleanup, and privacy work to a result that is fully derived during one invocation, while an HTTP API would turn a zero-operations local utility into a server with networking, authentication, lifecycle, and attack-surface obligations. Neither improves the required four metrics or pipeline use.

Primary quality goals:

1. Process a 1 GB supported log in under 30 seconds on the documented reference laptop.
2. Read input incrementally and never retain raw log lines.
3. Produce deterministic terminal, JSON, and CSV representations of the same report.
4. Fail explicitly on bad invocation, unreadable input, unusable data, or unique-cardinality exhaustion.

## 2. Scope and System Boundary

In scope: local files, `-`/stdin, nginx combined-format parsing, aggregation, formatting, CLI errors, packaging, and tests. Out of scope: authentication, persistence, HTTP, daemon mode, remote ingestion, cloud services, containers, and orchestration.

```text
file path or stdin
        |
        v
 buffered text iterator -> combined-log parser -> AnalysisAccumulator
                              | invalid             | valid record
                              v                     v
                       diagnostics count      counters/sets/hour bins
                                                    |
                                                    v
                                              immutable Report
                                         /          |          \
                                  Rich text        JSON         CSV
```

One process owns the full pipeline. Backpressure is provided naturally by synchronous iteration: the next line is not read until the current line has been parsed and accumulated.

## 3. Architecture Decision and Rejected Alternatives

The obvious approved architecture is a single-process layered CLI. No user choice remains to resolve.

| Variant | Trade-off | Decision |
|---|---|---|
| Single-process streaming CLI | Lowest complexity and operations; unique-key maps still consume memory | **Selected**; directly matches local/weekend constraints |
| Multi-process chunked CLI | May use multiple cores, but complicates stdin, ordering, merging, and deterministic error accounting | Rejected for MVP; benchmark before considering |
| Persistent ingestion service | Enables historical queries but requires database, API, auth, deployment, retention, and budget | Rejected; directly violates scope |

## 4. Technology and Package Layout

| Concern | Choice | Contract |
|---|---|---|
| Runtime | CPython 3.11 | Supported interpreter floor is `>=3.11,<4` |
| CLI | Click | One `nginx-stream-stats analyze` command; Click owns usage errors |
| Terminal | Rich | Styling only for interactive text output |
| Models | stdlib dataclasses | `LogRecord`, `AnalysisConfig`, and `Report` are explicit typed values |
| Aggregation | stdlib `Counter`, `set`, 24-element list | Exact values until configured cardinality ceiling |
| Packaging | PEP 517 via `pyproject.toml` | Console script named `nginx-stream-stats` |

Planned repository topology:

```text
pyproject.toml
src/nginx_stream_stats/
  __init__.py
  cli.py
  models.py
  parser.py
  analyzer.py
  errors.py
  renderers/
    __init__.py
    text.py
    json.py
    csv.py
tests/
  fixtures/
  test_parser.py
  test_analyzer.py
  test_renderers.py
  test_cli.py
  test_performance.py
```

## 5. Data Contracts and Metric Semantics

### Parsed record

`LogRecord` contains only fields needed after parsing:

| Field | Type | Rule |
|---|---|---|
| `ip` | `str` | Non-empty remote address token; IPv4/IPv6 is not normalized |
| `timestamp` | timezone-aware `datetime` | Parsed from nginx `%d/%b/%Y:%H:%M:%S %z` |
| `url` | `str` | Request-target token; query string remains part of the URL in MVP |
| `status` | `int` | Three-digit HTTP status from 100 through 599 |
| `user_agent` | `str` | Quoted field; `-` is treated as missing, not a unique agent |

The request method, protocol, referrer, response bytes, and raw line are discarded after validation.

### Report

| Field | Type | Semantics |
|---|---|---|
| `total_lines` | `int` | Every physical input line |
| `total_valid_requests` | `int` | Successfully parsed records |
| `malformed_lines` | `int` | Lines rejected by format or field validation |
| `top_ips` | ordered list of `(ip, count)` | Top 10 across valid requests; count descending, key ascending on ties |
| `top_error_urls` | ordered list of `(url, count)` | Top 10 where status is 400–599; count descending, key ascending on ties |
| `hourly_distribution` | 24 percentages | For hour `00` through `23`, `100 × hourly_request_count / total_valid_requests`; input timestamps retain their logged UTC offset and are bucketed by their displayed local hour |
| `unique_user_agents` | `int` | Count of distinct non-missing User-Agent strings among valid requests |
| `unique_user_agent_share` | percentage | `100 × unique_user_agents / total_valid_requests`; zero when there are no valid requests, though that condition exits `3` and emits no success report |

Percentages are numbers rounded to two decimal places only at serialization. Internal calculation uses full precision. The sum of displayed hourly percentages may differ slightly from 100.00 due to independent rounding.

### Persistence schema

There are no database tables, migrations, indexes, caches, or retained output. Runtime structures are not persistence tables:

| Runtime structure | Key/value | Lifetime | Bound |
|---|---|---|---|
| IP counter | `str -> int` | One invocation | Shared unique-cardinality ceiling |
| Error URL counter | `str -> int` | One invocation | Shared unique-cardinality ceiling |
| User-Agent set | `str` | One invocation | Shared unique-cardinality ceiling |
| Hour bins | 24 integers | One invocation | Constant |

The process increments a shared count whenever a new key is inserted into any of the three variable-cardinality structures. If insertion would exceed `--max-unique`, analysis stops before that insertion and exits `4`. This is an intentional exactness-over-approximation policy.

## CLI Interface

### Command

```text
nginx-stream-stats analyze [OPTIONS] INPUT
```

`INPUT` is a readable local file path or `-` for stdin. Exactly one input is required. Input is decoded as UTF-8 with strict error handling. Direct gzip handling is deferred; users may pipe `gzip -dc access.log.gz` to stdin.

### Options

| Option | Type/default | Behavior |
|---|---|---|
| `--json` | flag, false | Emit one JSON report object to stdout |
| `--csv` | flag, false | Emit long-form CSV to stdout |
| `--color / --no-color` | auto | Force/disable color in text mode; auto uses color only on a TTY |
| `--max-unique INTEGER` | `1_000_000` | Positive ceiling across distinct IP, error-URL, and User-Agent keys |
| `--show-malformed INTEGER` | `0` | Include up to N malformed line numbers and reasons on stderr; never raw line contents |
| `--version` | flag | Print version and exit `0` |
| `--help` | flag | Print help and exit `0` |

`--json` and `--csv` are mutually exclusive. Progress bars are not emitted, so stdout remains clean for every mode. Warnings and failure messages go to stderr.

### Outputs

Default text output uses four Rich sections plus a concise validity summary. JSON uses this stable top-level shape: `schema_version`, `input`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`. CSV is UTF-8 with a header and long-form columns `schema_version,metric,rank_or_bucket,key,count,percentage`; cells not applicable to a row are empty. Successful output represents only valid requests while reporting malformed counts separately.

### Exit codes

| Code | Meaning | Examples |
|---:|---|---|
| `0` | Success | Report emitted; malformed lines may have been skipped if at least one valid request exists |
| `1` | Input/runtime failure | Missing/unreadable file, UTF-8 decode error, broken internal I/O |
| `2` | CLI usage error | Conflicting formats, invalid positive integer, missing input |
| `3` | Data-format failure | Input read successfully but contains zero valid supported records |
| `4` | Unique-cardinality exhaustion | A new distinct IP/error URL/User-Agent would exceed `--max-unique` |

## 7. Parser and Streaming Algorithm

1. Open the file with a large read buffer or use stdin without closing it.
2. Iterate line by line, incrementing `total_lines`.
3. Match a precompiled combined-format regular expression and validate timestamp/status/request target.
4. On a malformed line, increment the diagnostic count and optionally retain only line number plus bounded reason text.
5. On a valid record, increment the IP count, hour bin, and total valid count; for 4xx/5xx, increment the URL error count; insert a non-missing User-Agent.
6. Before inserting a new variable-cardinality key, enforce `--max-unique`; abort with exit `4` if exhausted.
7. After EOF, reject zero valid records with exit `3`; otherwise use `heapq.nsmallest`/bounded sorting semantics to select deterministic top 10 values and construct a `Report`.
8. Pass the report to exactly one renderer.

Expected time is O(n + u log 10), where n is lines and u is unique counter keys. Memory is O(i + e + a), where i, e, and a are distinct IPs, error URLs, and User-Agents, capped by `--max-unique`; raw file size does not determine memory.

## 8. Error, Privacy, and Security Boundaries

- Raw log lines may contain tokens or personal data and are never echoed or retained. Optional diagnostics identify only line number and a controlled reason.
- The tool performs no network calls and emits no telemetry.
- ANSI control characters from parsed values are escaped/sanitized in terminal output; JSON and CSV use their standard encoders.
- `INPUT` is opened as a path directly—never passed to a shell.
- Broken pipe on stdout is treated as normal pipeline termination and returns `0` if analysis succeeded; other output failures return `1`.
- There is no authentication mechanism because there is no server, account, privilege boundary, or shared state. Local filesystem permissions remain the operating-system trust boundary.

## 9. Configuration and Deployment

There are no environment variables in MVP; command options are explicit and reproducible. There is no Docker or `docker-compose.yml`, because a container would slow a local pip-first workflow without supplying a runtime dependency. There is no server deployment target. Distribution is a Python wheel and source distribution installed into a local Python 3.11 environment with pip.

Release artifacts are built with `python -m build`, checked with `twine check dist/*`, installed into a clean virtual environment, and smoke-tested. Publishing to a public package index is a separate maintainer action, not part of analysis runtime.

## 10. Testing and Performance Evidence

| Layer | Evidence |
|---|---|
| Parser | Valid IPv4/IPv6, escaping, timezone, 4xx/5xx boundaries, malformed and invalid UTF-8 cases |
| Analyzer | Golden counts, deterministic ties, empty/invalid input, percentage math, missing User-Agent, exhaustion before insertion |
| Renderers | ANSI rules, JSON types/schema version, CSV header/rows, stdout/stderr separation |
| CLI | File/stdin parity, mutually exclusive flags, exact `0/1/2/3/4` codes, help/version, broken pipe |
| Performance | Generated 1 GB combined-format fixture; wall-clock under 30 s on documented hardware; peak RSS recorded |

The benchmark fixture generator may generate data for performance testing, but no synthetic data is presented as real user analysis.

## 11. Architecture Decision Record (ADR)

### ADR-001: Stateless single-process analysis

**Status:** Accepted.  
**Decision:** Use the selected single-process streaming CLI and exact, capped aggregations.  
**Consequences:** Minimal operations and deterministic results; performance is limited to one process, and exact unique values require cardinality-dependent memory.

### Labeled Self-Critique (not independent review)

No independent/adversarial reviewer or subagent ran in this benchmark. The following is the authoring agent’s self-critique using the skill’s Devil’s Advocate questions.

**Verdict:** APPROVE WITH CONDITIONS

1. **Challenge:** Exact sets/counters are not truly constant-memory. **Resolution:** Document the O(unique keys) model, enforce a shared configurable ceiling, and reserve exit `4` for exhaustion.
2. **Challenge:** Python may not meet 1 GB under 30 seconds. **Resolution:** Make the benchmark an early acceptance gate; optimize allocations/parser only with profiles, and apply the PRD kill criterion if it remains over target.
3. **Challenge:** “nginx access log” could imply arbitrary custom formats. **Resolution:** Define combined format as the MVP contract and make custom grammar P2 rather than silently misparse.
4. **Challenge:** A single unique-agent ratio can be misunderstood as the share of requests with a unique agent. **Resolution:** Give the exact numerator, denominator, missing-value behavior, and formula in architecture, PRD, and output docs.
5. **Challenge:** CSV must represent heterogeneous sections. **Resolution:** Specify one long-form schema and test every row kind rather than emitting several incompatible tables.
6. **Challenge:** Logs can contain secrets/control bytes. **Resolution:** Never echo raw invalid lines, sanitize terminal fields, and perform no network or persistence operations.

**Conditions incorporated:** early performance gate, explicit combined-format scope, exact cardinality failure, long-form CSV schema, and safe diagnostic/output rules.

### Alternatives considered and rejected

- Approximate sketches—rejected because top-10 and unique count correctness are more valuable than silently approximate output; explicit exhaustion is safer.
- Multi-process parsing—rejected until profiling proves single-process parsing cannot meet the target.
- Database/API service—rejected because it violates the approved local, stateless, zero-budget product boundary.

## 12. Traceability

- Product priorities and success measures: [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md)
- User-visible requirements and acceptance criteria: [PRD.md](PRD.md)
- File-by-file delivery sequence: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- Implementation prompts: [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md)
