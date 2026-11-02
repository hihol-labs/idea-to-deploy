# Project Architecture: nginx-stream-insights

## 1. Context and Decision

The product is a single-process Python 3.11 command-line application. Its defining architecture decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add installation, storage lifecycle, privacy, and operational cost even though the promised results can be computed in one pass and discarded. An HTTP API would add a server, authentication, network exposure, deployment, and versioned protocol without helping the intended local and pipeline workflows. Files and standard input already provide the appropriate boundary.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended)

- **Approach:** Read one line at a time, parse into a small dataclass, update in-memory aggregators, finalize one immutable report, render it.
- **Pros:** Minimal I/O and complexity; testable; pip-installable; natural stdin support; no raw-event retention.
- **Cons:** Exact distinct User-Agent tracking can grow with cardinality; one CPU core.
- **Best for:** The specified 1 GB laptop workload and one-weekend delivery.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunk parsing

- **Approach:** Split seekable files into chunks, parse in workers, and merge partial aggregates.
- **Pros:** Can use multiple cores on very large regular files.
- **Cons:** Does not naturally support stdin/follow mode, complicates line boundaries and deterministic errors, adds merge and memory overhead.
- **Best for:** A later, measured CPU-bound workload above the MVP target.
- **Estimated complexity:** Medium.

### Variant C: External Unix pipeline

- **Approach:** Compose shell tools for parsing, sorting, and counting.
- **Pros:** No Python package and familiar primitives.
- **Cons:** Multiple passes/sorts, platform variance, weak nginx quoting semantics, and no unified output contract.
- **Best for:** One-off exploratory work, not this product.
- **Estimated complexity:** Low initially, high to harden.

### Recommendation

Variant A is selected because the architecture is pre-approved, the workload is bounded, stdin is first-class, and the delivery window rewards one deterministic pipeline. Variant B remains a profiling-driven future option, not speculative MVP complexity.

## CLI Interface

### Command

```text
nginx-stream-insights [OPTIONS] [INPUT]
```

`INPUT` is an optional path to a UTF-8 nginx access log. When omitted or `-`, bytes are read from standard input. A regular file is opened read-only. Input is processed line-by-line; raw lines and parsed events are not retained.

### Options

| Option | Default | Contract |
|---|---|---|
| `--format [combined|common]` | `combined` | Select supported nginx log grammar |
| `--top INTEGER` | `10` | Number of IP and error-URL rows; must be 1–1000 |
| `--json` | false | Emit exactly one JSON document to stdout |
| `--csv` | false | Emit RFC 4180 CSV rows to stdout; mutually exclusive with `--json` |
| `--no-color` | false | Disable ANSI color in text mode; color is also disabled when stdout is not a TTY |
| `--follow` | false | Continue reading appended lines; valid only for a regular-file `INPUT` |
| `--max-unique-user-agents INTEGER` | `1000000` | Stop before exact cardinality exceeds this positive ceiling |
| `--version` | — | Print version and exit 0 |
| `--help` | — | Print help and exit 0 |

### Outputs

- **Text (default):** Rich headings/tables for totals, top IPs, top error URLs, 24 hourly buckets, unique User-Agent count/share, and malformed-line count. Diagnostic messages go to stderr.
- **JSON:** object with `schema_version`, `total_valid_requests`, `malformed_lines`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `unique_user_agents` (`count` and `share_percent`). Top-list items contain `value`, `count`, and `share_percent`; hourly keys are `00` through `23`.
- **CSV:** header `metric,rank,key,count,percentage`, followed by ranked `top_ip` and `top_error_url` rows, all 24 `hourly_distribution` rows, and one `unique_user_agents` row. Non-applicable `rank` or `percentage` cells are empty.
- All percentages are numeric values in the range 0–100, rounded only during serialization. Hourly percentage is `100 × hourly_request_count / total_valid_requests`; when there are no valid requests, every percentage is `0.0`. Unique User-Agent share is `100 × distinct_nonempty_user_agents / total_valid_requests`, also `0.0` when there are no valid requests.
- Deterministic ordering: descending count, then key ascending for ties; hours always `00`–`23`.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Successful analysis and output, including an empty valid input |
| `1` | Input I/O failure (missing, unreadable, or read error) |
| `2` | CLI usage/configuration error, including incompatible options |
| `3` | Parse-policy failure: input is non-empty but contains no valid lines |
| `4` | Unique-cardinality exhaustion: the configured exact User-Agent ceiling would be exceeded |

For mixed valid and malformed lines, processing succeeds with code 0 and reports the malformed count. This policy preserves useful results without treating corrupt records as valid.

## 4. Component Model

```text
file/stdin -> InputSource -> NginxParser -> StreamingAggregator -> Report
                                                        |          |
                                                        |          +-> RichRenderer -> stdout
                                                        |          +-> JsonRenderer -> stdout
                                                        |          +-> CsvRenderer  -> stdout
                                                        +-> counters/sets only
diagnostics --------------------------------------------------------> stderr
```

| Module | Responsibility | Must not do |
|---|---|---|
| `src/nginx_stream_insights/cli.py` | Click command, validation, source/render selection, exit mapping | Parse log syntax or calculate metrics |
| `input.py` | File/stdin iteration and optional follow behavior | Retain raw logs |
| `parser.py` | Parse common/combined lines to `AccessEvent` | Print or terminate the process |
| `models.py` | `AccessEvent`, ranked item, hourly bucket, final `Report` dataclasses | Perform I/O |
| `aggregator.py` | Counters, exact UA set with ceiling, report finalization | Know output format |
| `renderers/text.py` | Rich terminal representation | Recalculate metrics |
| `renderers/json.py` | Stable JSON schema | Emit diagnostics to stdout |
| `renderers/csv.py` | Stable tabular schema | Emit terminal styling |

## 5. Domain and Streaming State

`AccessEvent` contains `client_ip: str`, `timestamp: datetime`, `request_target: str`, `status: int`, and `user_agent: str | None`. The parser extracts only these fields.

The aggregator retains:

- `total_valid_requests: int`;
- `malformed_lines: int`;
- `ip_counts: Counter[str]`;
- `error_url_counts: Counter[str]` for statuses 400–599;
- `hour_counts: list[int]` of length 24, using the timestamp’s logged offset without timezone conversion;
- `unique_user_agents: set[str]`, excluding missing/empty values and enforcing the configured ceiling.

This is streaming with respect to raw events. Exact distinct values and exact frequency maps necessarily scale with observed cardinality; the ceiling makes the User-Agent bound explicit. The benchmark records peak memory so the architecture does not confuse “one pass” with constant space.

## 6. Parsing Contract

- Support nginx common and combined formats, including quoted request and User-Agent fields and `-` placeholders.
- Treat an invalid IP token, timestamp, request line, status, or quoting structure as a malformed line.
- Define URL as the request-target token from the quoted request line; preserve query strings in MVP.
- Statuses 400–599 contribute to the error-URL ranking; redirects and successful requests do not.
- Count valid requests independently of whether User-Agent is present.
- Never log the original raw line by default, preventing accidental disclosure in diagnostics.

## 7. Data, API, Authentication, and Deployment Decisions

### Database

There are no database tables, migrations, indexes, or durable records. Adding even three placeholder tables would violate the product constraint and create data-retention obligations. Input logs remain owned by the caller; output goes only to stdout/stderr.

### HTTP API

There are no HTTP endpoints, request bodies, ports, listeners, or network dependencies. The complete public protocol is the CLI contract above.

### Authentication and authorization

There is no application authentication because there is no server or shared resource. Access control is inherited from local OS permissions on the executable and input file. The process must not elevate privileges.

### Deployment

Distribution is a pip-installable wheel with a `nginx-stream-insights` console entry point. There is no Docker runtime, Compose file, cloud deployment, server, or Kubernetes manifest. CI may build and test wheels, but installing or publishing a release is a separate human-approved action.

### Environment variables

None are required. Locale, terminal capability, and standard Python environment variables may affect the host generally but are not product configuration; explicit CLI flags own product behavior.

## 8. Performance and Resource Budget

- Reference acceptance target: a fixed 1 GB representative combined-format fixture completes in under 30 seconds on the designated laptop, excluding fixture generation and disk-cache assumptions documented by the benchmark.
- One sequential read; no loading the file wholesale; no full sort of raw events.
- Use `Counter.most_common(top_n)` or an equivalent bounded selection at finalization.
- Profile before introducing multiprocessing or parser extensions.
- Performance tests record wall time, peak resident memory, valid/malformed counts, Python version, and machine details.

## 9. Error and Safety Model

Expected failures become the documented exit codes and concise stderr messages without tracebacks. Unexpected internal exceptions return code 1 only at the outer CLI boundary, with debug tracebacks enabled only in development tests. Broken pipes should terminate quietly using conventional CLI behavior. Output serialization is atomic at the report level: compute the report, then write one chosen representation.

## 10. Test Architecture

- Parser table tests cover quoting, IPv4/IPv6, timestamps, status boundaries, missing fields, and malformed lines.
- Aggregator tests cover ties, empty input, 24 buckets, error filtering, percentage formulas, and cardinality ceiling.
- CLI tests cover stdin/file/follow validation, stdout/stderr separation, mutual exclusion, and all exit codes `0/1/2/3/4`.
- Golden tests pin text semantics and exact JSON/CSV schemas.
- A generated non-sensitive 1 GB fixture is used only for the explicit performance suite; it is not committed as product data.

## 11. Architecture Decision Record (ADR)

### ADR-001: Single-process stateless CLI

- **Status:** Accepted from the approved product brief.
- **Decision:** Choose Variant A and omit database, HTTP API, auth subsystem, containers, cloud, and Kubernetes.
- **Consequences:** Lowest operational burden and direct pipeline compatibility; exact-cardinality memory must be bounded and measured.
- **Alternatives rejected:** Multiprocessing until profiling demonstrates need; Elastic-style persistence because it contradicts local stateless scope; shell-only parsing because it cannot provide the promised stable tested contract.

### Review status

No Devil’s Advocate or independent review was run in this session. Per the benchmark contract, adversarial review is delegated to the external harness and no review artifact is created here.

