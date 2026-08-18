# Project Architecture: nginx-insights

## 1. Context and Goals

`nginx-insights` is a Python 3.11 executable installed with pip and run locally by DevOps/SRE users. It streams nginx common or combined access logs, accumulates only the state needed for the report, and emits one of three representations. The performance goal is 1 GB in under 30 seconds on a documented laptop reference environment.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the command performs an ephemeral analysis, requires no cross-run querying, and must not create lifecycle, privacy, or cleanup obligations. An HTTP API is incorrect because there are no remote clients, shared state, authentication needs, or long-running jobs; stdin, file paths, stdout, stderr, and exit codes are the complete integration boundary.

## 2. Architecture Decision

The pre-approved architecture is one local process and one streaming pass:

```text
files / stdin
      |
      v
line iterator -> nginx parser -> valid AccessRecord -> StreamingAnalyzer
                       |                              |-- IP counts
                       |                              |-- error-URL counts
                       |                              |-- 24 hourly counts
                       |                              `-- exact User-Agent set
                       `-> skipped-line count                    |
                                                               v
                                                        AnalysisReport
                                                  / terminal / JSON / CSV
```

One process is the obvious choice for a one-weekend, local CLI. Multiprocessing would add ordering, merging, portability, and memory costs before profiling proves it useful. A database-backed index, Elastic pipeline, or service would contradict the explicit product boundary. Shell-only parsing remains a useful fallback but cannot provide the same tested input and output contract.

### Alternatives Considered and Rejected

| Alternative | Benefit | Why rejected for the MVP |
|---|---|---|
| Multiple worker processes | Potential CPU parallelism | Parsing is mixed with I/O; merge overhead and duplicate memory threaten simplicity and the laptop target |
| SQLite temporary aggregation | Bounded Python heap and SQL grouping | Adds disk I/O, persistence semantics, and cleanup to a one-shot report |
| Approximate sketches for all metrics | Strictly bounded memory | Surprising approximate top-10 results; exact aggregation is preferred for the target input, with an explicit User-Agent limit |
| Logstash/Elastic service | Rich retention and querying | Requires infrastructure, storage, and operations explicitly outside scope |

## 3. Technology Stack

| Layer | Technology | Responsibility |
|---|---|---|
| Runtime | CPython 3.11 | Single local process |
| Command layer | Click | Options, path validation, help, controlled exits |
| Presentation | Rich | Colored terminal tables and TTY-safe styling |
| Models | `dataclasses` | `AccessRecord`, metric rows, metadata, and `AnalysisReport` |
| Core library | `re`, `collections`, `datetime`, `json`, `csv` | Parsing, exact aggregation, calculation, serialization |
| Packaging | PEP 621 `pyproject.toml` | Dependencies and `nginx-insights` console entry point |

Runtime dependencies are limited to Click and Rich. There is no ORM, web framework, database driver, auth library, container runtime, or cloud SDK.

## 4. Components and File Layout

```text
pyproject.toml
src/nginx_insights/
  __init__.py
  cli.py                 # Click boundary and exit mapping
  models.py              # frozen input/output dataclasses
  parser.py              # common/combined parser protocol and implementation
  analyzer.py            # single-pass aggregation and report finalization
  errors.py              # typed expected failures and exit-code identities
  renderers/
    __init__.py
    terminal.py          # Rich-only human output
    json.py              # stable JSON document
    csv.py               # normalized CSV rows
tests/
  fixtures/
  test_parser.py
  test_analyzer.py
  test_cli.py
  test_renderers.py
  test_performance.py
```

Dependencies point inward: `cli` may call parser, analyzer, and renderers; renderers consume `AnalysisReport`; parser and analyzer do not import Click or Rich. This makes calculations independent of presentation and keeps all output modes consistent.

## 5. Data Contracts and Algorithms

### Input Record

`AccessRecord` is an immutable dataclass with `ip: str`, `timestamp: datetime`, `request_target: str`, `status: int`, and `user_agent: str | None`. The combined parser extracts all fields; the common parser sets `user_agent` to `None`. Request targets retain the nginx request-target token and exclude method/protocol. Timestamps use the offset in the log entry; the hour bucket is the logged local hour `00` through `23`.

The parser supports standard nginx `combined` and `common` formats in the MVP. It does not interpret arbitrary `log_format` directives. Each physical line is independently parsed. A malformed line increments `skipped_lines`, writes no per-line diagnostic during normal operation, and contributes to no metric. If the entire input has no valid records, the command exits `3`.

### Streaming State

`StreamingAnalyzer` holds:

- `Counter[str]` for valid client IP occurrences;
- `Counter[str]` for request targets whose status is 400–599;
- a fixed list of 24 integer hourly counts;
- `set[str]` for non-null User-Agent values, capped by `--max-unique-user-agents`;
- integer totals for physical, valid, skipped, error, and records-with-User-Agent lines.

No parsed records are retained. Exact IP and error-URL maps grow with their respective cardinalities; this is an accepted MVP trade-off and is covered by the performance fixture. The User-Agent set has a hard configurable bound because strings dominate the likely high-cardinality memory risk. Attempting to insert a new value after that bound is reached terminates with exit `4`; the tool never silently approximates the required share.

Top lists sort by descending count, then ascending key for deterministic ties, and take 10 entries. Hourly request distribution is a percentage calculated for each hour using the literal formula `100 × hourly_request_count / total_valid_requests`; the 24 displayed percentages therefore sum to approximately 100%, subject only to output rounding. The unique User-Agent share is `100 × unique_non_null_user_agent_count / total_valid_requests`; common-format records therefore contribute to the denominator but not the unique numerator. Reports expose both counts so the interpretation is auditable.

### Report Schema

`AnalysisReport` contains schema version, source labels, total/valid/skipped/error counts, ordered `top_ips`, ordered `top_error_urls`, 24 hourly buckets, `unique_user_agent_count`, `records_with_user_agent`, `unique_user_agent_share_percent`, and elapsed seconds. Percentages are calculated before rendering and serialized as numbers rounded to four decimal places in JSON/CSV; terminal output may show two decimals.

## CLI Interface

### Command

```text
nginx-insights [OPTIONS] [PATHS]...
```

With no path, the command reads UTF-8 text from stdin. One or more paths are read in argument order as one logical stream. `-` may appear once to identify stdin explicitly. Input decoding uses UTF-8 with replacement for invalid byte sequences; syntactically invalid lines are skipped under the parser rule.

### Options

| Option | Default | Contract |
|---|---|---|
| `--format [combined|common]` | `combined` | Select the supported nginx log grammar |
| `--json` | off | Emit one JSON object to stdout; mutually exclusive with `--csv` |
| `--csv` | off | Emit normalized CSV rows to stdout; mutually exclusive with `--json` |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive hard cap for exact unique User-Agent values |
| `--no-color` | off | Disable Rich color in terminal mode; irrelevant to JSON/CSV |
| `--version` | n/a | Print version and exit `0` |
| `--help` | n/a | Print Click help and exit `0` |

### Inputs

- Standard nginx combined or common access-log lines from regular files and/or stdin.
- Empty files and malformed lines are permitted, but at least one valid record is required for a successful analysis.
- Compressed files are not opened implicitly in the MVP; users may pipe `gzip -cd access.log.gz`.

### Outputs

- Default: Rich headings and tables on stdout. Color is enabled only for a capable terminal and never added when redirected or with `--no-color`.
- JSON: one UTF-8 JSON object with `schema_version: 1` and the complete report schema. No prose or ANSI escapes appears on stdout.
- CSV: UTF-8 with header `section,rank,key,count,percentage`; metadata and the four metric families are normalized into rows. Empty fields are present where rank/count/percentage is not applicable.
- Diagnostics: concise messages and skipped-line summary go to stderr, never into JSON/CSV stdout.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Successful report, help, or version output |
| `1` | Unexpected internal/runtime failure |
| `2` | Click usage error: invalid option/value, incompatible output flags, or missing path argument value |
| `3` | Input/parse failure: unreadable input, stream read failure, or zero valid records |
| `4` | Unique-cardinality exhaustion: a new User-Agent would exceed the configured exact-cardinality limit |

Expected failures are mapped once in `cli.py`. A code `4` condition is never remapped to `1` or `3`. If an unreadable path is detected before streaming, code `3` wins; during streaming, the first terminal failure determines the code.

## 7. Persistence, API, Authentication, and Deployment

There are no database tables because no data persists across invocations. There are no migrations, caches, queues, API endpoints, request/response bodies, ports, sessions, tokens, users, or authentication flow. This is a deliberate architecture result, not missing design work.

Deployment means building a universal wheel and source distribution and publishing them to PyPI. Users install into a local Python 3.11 environment with pip. Docker, docker-compose, Kubernetes, serverless functions, VPS hosts, and cloud resources are not required or supplied.

No environment variables are required. Locale, terminal capability, and standard process streams behave according to Python/Rich defaults; all product behavior is controlled through the documented command options.

## 8. Performance and Resource Design

The hot path reads line by line, uses one precompiled pattern per selected format, updates primitive counters, and does no per-line rendering. Final sorting occurs once after EOF. The benchmark uses a deterministic 1 GB combined-log fixture on a laptop whose CPU, RAM, OS, filesystem, storage, and Python patch version are recorded. The acceptance command performs three warm-cache runs and requires each timed analysis run to stay below 30 seconds; fixture generation and output writing are excluded from the timed parse/aggregate window.

Peak memory is measured alongside time. The analyzer retains aggregate keys but not records. A performance regression above 10% triggers investigation even if it remains below 30 seconds.

## 9. Reliability and Security Boundaries

Logs are untrusted text. Parsing must not evaluate input, expand paths found inside logs, emit control characters unescaped, or use unbounded regular-expression backtracking. Renderers rely on Rich escaping and standard JSON/CSV encoders. File access is read-only and limited to explicit paths. No logs, metrics, or telemetry leave the machine.

Broken pipes are handled quietly according to CLI convention. Partial JSON or CSV output is avoided by completing analysis before serialization. The terminal report may be constructed only after a complete `AnalysisReport` exists.

## 10. Test Strategy

- Parser fixtures cover IPv4/IPv6, quoted fields, timezone offsets, 2xx/4xx/5xx, common versus combined, malformed lines, and hostile control characters.
- Analyzer golden tests cover deterministic tie ordering, exactly 10 rows, valid-only denominators, all 24 hours, and the formula `100 × hourly_request_count / total_valid_requests`.
- CLI tests cover stdin, multiple files, TTY/no-TTY behavior, mutual exclusion, diagnostics separation, and the complete `0/1/2/3/4` exit contract.
- Renderer tests parse JSON and CSV rather than comparing only strings.
- A marked performance test runs against the deterministic 1 GB fixture outside the fast unit suite.

## 11. Architecture Decision Record

### ADR-001: Local Single-Process Streaming CLI

- **Status:** Accepted by the product constraints supplied for this blueprint.
- **Decision:** Use one Python 3.11 process, no durable state, and stdout/stderr as the output boundary.
- **Consequences:** Installation and operation stay simple and free; aggregate maps may grow with key cardinality, so performance and cardinality behavior require explicit tests.
- **Rejected:** Database-backed aggregation, HTTP service, cloud pipeline, Kubernetes, and premature multiprocessing.

### ADR-002: Exact Metrics with Explicit User-Agent Exhaustion

- **Status:** Accepted.
- **Decision:** Produce exact top counts and exact User-Agent cardinality up to a documented cap; exit `4` instead of silently approximating beyond it.
- **Consequences:** Results remain explainable and pipelines can distinguish capacity exhaustion from malformed input.

The separate Devil's Advocate review is intentionally outside this blueprint session. No adversarial or independent review result is asserted here.

