# Project Architecture: nginx-log-report

## 1. Context and Constraints

The system is a local Python 3.11 CLI. It reads nginx access-log lines from one or more files, gzip files, or stdin; parses and aggregates them in one pass; then emits one report. It has no long-lived process and performs no network access.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the required outputs are produced during one bounded scan and no cross-run query, retention, coordination, or mutation exists. Avoiding one removes disk-write amplification, schema migration, cleanup, and privacy exposure. An HTTP API is incorrect because the user and automation boundary is already a shell process with files/stdin and stdout/stderr; a server would add lifecycle, port, security, and authentication obligations without enabling a required use case.

Hard constraints:

- Python 3.11, Click, Rich, and dataclasses; pip installable.
- Stateless streaming processing; a log is never loaded wholesale.
- Target: a 1 GB representative log in under 30 seconds on a documented laptop.
- $0 operating budget and one-weekend implementation.
- No authentication, database, HTTP API, server, cloud, Docker requirement, or Kubernetes.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** one Click process owns input iteration, parsing, aggregation, report finalization, and rendering.
- **Pros:** minimal overhead and operational surface; deterministic; easy stdin support; directly matches the approved constraints.
- **Cons:** bounded by one CPU core for parsing; exact distinct-value sets consume memory proportional to cardinality.
- **Best for:** local one-shot analysis of logs up to and beyond the 1 GB target.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunk parsing

- **Approach:** split seekable files into byte ranges, parse in workers, merge partial counters.
- **Pros:** may use multiple cores on very large regular files.
- **Cons:** cannot naturally split stdin/gzip; boundary repair and merge logic increase risk; IPC copies large cardinality maps.
- **Best for:** future measured workloads where parsing is proven CPU-bound.
- **Estimated complexity:** Medium.

### Variant C: External sort / embedded persistence

- **Approach:** spill keys or counts to local disk and merge them after ingestion.
- **Pros:** supports cardinality beyond RAM.
- **Cons:** violates the approved no-database/simple stateless direction in spirit, adds heavy I/O and cleanup, and threatens the 30-second target.
- **Best for:** a different product whose primary requirement is unbounded exact cardinality.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected. It is the only variant whose operational model is identical for a file, gzip stream, and stdin, and it creates the smallest credible implementation for a one-weekend, $0 tool. The explicit cardinality guard turns the main memory risk into a deterministic contract rather than hidden degradation.

## 3. Component Model

```text
Click CLI
  -> Input opener/line iterator
      -> Combined-log parser
          -> Streaming aggregator
              -> immutable Report dataclass
                  -> Rich renderer | JSON renderer | CSV renderer
```

| Module | Responsibility | Must not do |
|---|---|---|
| `src/nginx_log_report/cli.py` | Click arguments, stream selection, orchestration, exit mapping | Parse log syntax or format metric values |
| `src/nginx_log_report/input.py` | Open `-`, plain files, and `.gz`; yield text lines | Accumulate the full input |
| `src/nginx_log_report/parser.py` | Convert a supported combined-log line to `AccessRecord` or a parse failure | Print or mutate aggregate state |
| `src/nginx_log_report/models.py` | Dataclasses and public report schema | Depend on Click or Rich |
| `src/nginx_log_report/aggregate.py` | Counters, sets, limits, deterministic top-10 selection, formulas | Perform terminal output |
| `src/nginx_log_report/renderers.py` | Rich, JSON, and CSV serialization from one `Report` | Recompute metrics |
| `src/nginx_log_report/errors.py` | Typed failures and exit-code mapping | Swallow underlying input context |

The hot path performs no rendering and no per-line logging. Regex compilation and field conversion occur outside or minimally within the loop. Final sorting is over distinct keys, not all requests.

## 4. Domain and Streaming State

There are no persistent tables. The complete in-memory model is:

| Dataclass/state | Fields and types | Constraints |
|---|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `request_target: str`, `status: int`, `user_agent: str` | Timestamp must retain the parsed offset; status is 100–599; request target is the raw target token after the method |
| `CountEntry` | `value: str`, `count: int`, `rank: int` | `count >= 1`; rank 1–10; ties sort by value ascending |
| `HourEntry` | `hour: int`, `request_count: int`, `percentage: float` | All 24 hours emitted; hour 0–23 from the timestamp as logged; percentage rounded only when rendered |
| `Report` | `total_lines: int`, `total_valid_requests: int`, `invalid_lines: int`, `top_ips: tuple[CountEntry, ...]`, `top_error_urls: tuple[CountEntry, ...]`, `hourly: tuple[HourEntry, ...]`, `unique_user_agents: int`, `unique_user_agent_share: float` | Counts reconcile; sequences are deterministic and immutable at render time |
| `AggregationState` | `ip_counts: dict[str,int]`, `error_url_counts: dict[str,int]`, `hour_counts: list[int]` length 24, `user_agents: set[str]`, totals | Exists only during one invocation; each distinct-key collection obeys `--max-cardinality` |

The unique User-Agent share is `100 × unique_user_agents / total_valid_requests`. An absent User-Agent field in a syntactically valid supported line is normalized to the literal `(missing)` and therefore represents one distinct value. When there are zero valid requests, no report is emitted and exit code 3 is returned.

Hourly request distribution is a percentage for each log-local hour using the literal formula `100 × hourly_request_count / total_valid_requests`. Because combined logs include a numeric UTC offset, “hourly” means the `HH` component as recorded in each line; records are not converted to the machine timezone.

Top IPs count every valid request. Top error URLs count only requests whose status is 400–599. URL means the request-target token with query string preserved; no percent-decoding or normalization occurs in MVP. Ranking is descending count, then ascending UTF-8 string value, truncated to 10.

## 5. Parsing Contract

MVP supports nginx’s conventional combined log shape:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

IPv4 and IPv6 textual addresses are accepted as opaque non-whitespace client tokens. `$request` is split into method, target, and protocol; a request without exactly those usable parts is invalid. Quoted fields must honor the supported nginx escaping rules. Lines that cannot satisfy the grammar, timestamp, or status constraints increment `invalid_lines` and processing continues. Decoding uses UTF-8 with replacement so a bad byte cannot crash an otherwise readable log; this policy is exposed in output documentation.

## CLI Interface

### Command

```text
nginx-log-report [OPTIONS] [INPUT]...
```

With no `INPUT`, or with the single input `-`, the command reads stdin. Multiple explicit paths are processed in argument order. `-` may not be combined with file paths because replay/order semantics would be surprising. Files ending in `.gz` are decompressed as gzip; all others are read as plain bytes/text streams.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one JSON object to stdout |
| `--csv` | flag, false | Emit a normalized CSV table to stdout |
| `--color / --no-color` | auto from TTY | Applies only to terminal format; machine formats never contain ANSI |
| `--max-cardinality INTEGER` | positive, `1000000` | Maximum distinct keys in each IP, error-URL, and User-Agent collection; crossing it exits 4 |
| `--strict` | flag, false | Exit 3 if any malformed line is encountered; default tolerates malformed lines if at least one record is valid |
| `--version` | flag | Print version and exit 0 without reading input |
| `--help` | flag | Print help and exit 0 |

`--json` and `--csv` are mutually exclusive. stdout is reserved for the selected report; diagnostics go to stderr.

### Inputs

- Zero or more readable local plain/gzip paths, or stdin.
- Conventional nginx combined-log records as defined above.
- Input is consumed once and is never rewound or retained.

### Outputs

Terminal output contains a summary plus four sections: top IPs, top error URLs, 24 hourly percentage rows, and User-Agent uniqueness. Rich color is enabled only for a TTY unless explicitly overridden.

JSON uses stable snake_case keys matching the `Report` fields. Counts are integers and percentages are JSON numbers rounded to six decimal places; list order is ranking/hour order. CSV uses columns `section,rank,key,count,percentage`. It emits rows for `top_ip`, `top_error_url`, each of 24 `hour` buckets, and one `user_agent_summary` row. CSV is RFC 4180-compatible and writes a header even when a ranked section is empty.

### Exit Codes

| Code | Meaning |
|---:|---|
| 0 | Report completed; malformed lines may have been counted unless `--strict` is set |
| 1 | Unexpected internal error |
| 2 | CLI usage or input I/O error, including unreadable paths, invalid options, or invalid gzip data |
| 3 | Data error: no valid requests, or any malformed line under `--strict` |
| 4 | Unique-cardinality exhaustion: a configured distinct-key limit would be exceeded |

## 7. Error, Security, and Resource Boundaries

- Treat every log field as untrusted data. Rich rendering must not interpret embedded terminal control sequences; JSON/CSV libraries perform escaping.
- Never include full rejected log lines in default diagnostics because URLs and headers may contain secrets. Report path, line number, and reason class; an optional future debug mode would require an explicit redaction design.
- Symlinks follow normal local filesystem semantics. The process does not elevate privileges, recursively discover files, or write beside inputs.
- Broken pipe is handled quietly according to CLI convention and does not produce a traceback.
- Cardinality is checked before inserting a new distinct key. No approximate fallback is permitted because silently changing metric semantics is worse than exit 4.
- Memory complexity is `O(U_ip + U_error_url + U_user_agent + 24)` and time is `O(N + U log U)` during final ranking. Benchmark evidence must include adversarial cardinality cases.

## 8. Packaging and Runtime

`pyproject.toml` defines a `src/` package and console script `nginx-log-report = nginx_log_report.cli:main`. Runtime dependencies are constrained to compatible Click and Rich versions; development dependencies are separate. A wheel and source distribution must build and install into a clean Python 3.11 virtual environment.

There are no environment variables, config files, containers, daemon units, ports, migrations, external integrations, or deployment credentials. Deployment means installing the wheel with pip into a user-controlled environment. The tool makes no network requests and emits no telemetry.

## 9. Test and Performance Architecture

| Layer | Evidence |
|---|---|
| Parser unit tests | IPv4/IPv6, escaped quotes, missing fields, malformed timestamps/statuses, Unicode replacement |
| Aggregator unit tests | All formulas, error filtering, ties, empty ranked sections, 24 hours, cardinality boundary |
| CLI integration tests | stdin/plain/gzip/multiple files, mutual exclusion, stderr separation, complete `0/1/2/3/4` mapping |
| Golden tests | Semantically identical terminal, JSON, and CSV reports with deterministic ordering |
| Packaging test | Build wheel, clean install, `--version`, smoke analysis |
| Performance test | Generated 1 GB representative corpus, elapsed time and peak RSS on recorded hardware |

The large benchmark corpus is generated locally and excluded from source control. A small hand-auditable fixture remains in tests. Performance and cardinality scenarios are separate: the normal 1 GB corpus must complete; a deliberately over-limit corpus must exit 4 without partial stdout.

## 10. Architecture Decision Record (ADR)

### ADR-001: Single-process, exact, bounded-cardinality streaming

- **Status:** Accepted from the pre-approved product brief.
- **Decision:** Use Variant A with exact dictionaries/sets and a configurable hard ceiling.
- **Consequences:** Simple and deterministic operation; memory grows with distinct values; limit exhaustion is explicit rather than approximated.
- **Alternatives rejected:** Multiprocessing has no demonstrated need and complicates stdin/gzip. Disk-backed aggregation contradicts the local one-shot simplicity and performance target.

### ADR-002: One canonical report model, three renderers

- **Status:** Accepted.
- **Decision:** Finalize aggregation once into a dataclass consumed by terminal, JSON, and CSV renderers.
- **Consequences:** Pipeline formats cannot accidentally use different formulas; schema changes require coordinated tests and documentation.

### Review boundary

No Devil’s Advocate review was performed in this session. Per the execution brief, the external harness will run the real reviewer in a separate fresh session and own its artifact. This document contains no substitute self-review verdict.

