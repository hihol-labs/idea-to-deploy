# Project Architecture: nginx-insight

## 1. Architectural Decision

The selected architecture is a single Python process with a linear pipeline:

```text
file(s) or stdin -> byte/text line iterator -> parser -> streaming aggregator -> renderer -> stdout
                                               |                              |
                                               +-> diagnostics                +-> stderr diagnostics
```

The binding decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the report is computed once from caller-owned logs, retention is not a requirement, and persistence would add I/O, schema lifecycle, cleanup, and privacy exposure. An HTTP API is incorrect because the intended users are local shell and pipeline users; a server would introduce ports, lifecycle management, authentication questions, and deployment work with no product benefit.

The user has pre-approved this obvious single-process architecture. Microservices, a modular server, and distributed workers are not viable variants within a $0, one-weekend, local CLI scope.

## 2. Quality Attributes and Constraints

- Runtime: CPython 3.11.
- Performance: a representative 1 GB nginx access log completes in under 30 seconds on the documented reference laptop.
- Processing: one pass over each input; memory is proportional to distinct IPs, error URLs, and User-Agents, not total lines.
- Safety: a configurable aggregate unique-key ceiling stops execution before uncontrolled memory growth.
- Determinism: identical valid records and options produce identical JSON/CSV values and tie ordering.
- Portability: pip-installable on supported Python 3.11 environments.
- Privacy: no log content leaves the machine and no report is persisted by the tool.

## 3. Package and Component Boundaries

```text
src/nginx_insight/
  __init__.py       package version
  cli.py            Click command, option validation, exit mapping
  models.py         ParsedRecord, AggregateSnapshot, ParseStats dataclasses
  parser.py         supported nginx combined-log parsing
  aggregate.py      one-pass counters, hourly buckets, cardinality guard
  inputs.py         files/stdin iteration and decoding policy
  renderers/
    terminal.py     Rich tables and summary
    json.py         versioned JSON object
    csv.py          normalized CSV rows
  errors.py         typed domain failures mapped to exit codes
```

`cli.py` depends on the other modules; renderers depend only on immutable snapshot models. Parsing does not know about Click or Rich. The aggregator accepts parsed records and produces a final snapshot, allowing unit tests without file I/O.

## 4. Data Model and Metric Semantics

`ParsedRecord` contains `remote_addr: str`, `timestamp: datetime` with parsed offset, `request_target: str`, `status: int`, and `user_agent: str`. The parser supports the standard nginx combined log format. The request target is the request-target token from the quoted request line; the HTTP method and protocol are parsed for validation but are not aggregation keys.

`AggregateSnapshot` contains:

- `total_lines`, `total_valid_requests`, and `malformed_lines`.
- `top_ips`: up to ten `(ip, count)` entries across all valid requests.
- `top_error_urls`: up to ten `(url, error_count)` entries for status codes 400–599 only.
- `hourly_distribution`: exactly 24 buckets keyed `00` through `23`; each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- `unique_user_agent_count` and `unique_user_agent_share_percent`, where the share is `100 × unique_user_agent_count / total_valid_requests`.

Ties in top lists sort by count descending and then key ascending. A valid empty User-Agent value is still one distinct value. When there are no valid requests, percentages are not fabricated; execution fails with exit code 3.

The cardinality guard tracks the union of keys stored by the IP counter, error-URL counter, and User-Agent set. Before adding a new key that would exceed `--max-unique`, the aggregator raises the typed exhaustion error; it emits no partial report and maps to exit code 4. The default is 5,000,000 keys and must be performance-tested.

## CLI Interface

### Command

```text
nginx-insight [OPTIONS] [INPUTS]...
```

### Inputs

- Each `INPUT` is a readable nginx access-log path.
- `-` means standard input; if no input is supplied, standard input is used.
- Inputs are processed in argument order as one logical report.
- Text is decoded as UTF-8 with invalid byte sequences rejected and reported as input errors.
- MVP supports uncompressed standard combined-format logs. Gzip and live following are deferred.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit normalized CSV; mutually exclusive with `--json` |
| `--max-unique INTEGER` | `5000000` | Positive ceiling across stored unique aggregate keys |
| `--strict` | flag, false | Treat the first malformed log line as a parse failure instead of skipping it |
| `--no-color` | flag, false | Disable terminal styling; irrelevant to JSON/CSV |
| `--version` | flag | Print version and exit 0 |
| `--help` | flag | Print usage and exit 0 |

### Outputs

Default output is a Rich terminal report with four sections and a processed/skipped summary. Color is enabled only when stdout is a compatible TTY and `--no-color` is absent. Diagnostics go to stderr; report data goes to stdout.

JSON has a top-level `schema_version`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`. Counts are integers and percentages are JSON numbers rounded to six decimal places only at serialization.

CSV uses the header `schema_version,section,key,count,percentage`. It emits rows for top IPs, top error URLs, all 24 hourly buckets, and one `unique_user_agents` row. Non-applicable cells are empty. CSV is RFC 4180-compatible and contains no ANSI sequences.

### Exit Codes

| Code | Meaning |
|---:|---|
| 0 | Report produced successfully, or help/version requested |
| 1 | Input/I/O failure, including unreadable path or decoding error |
| 2 | CLI usage or option validation error |
| 3 | Log-data failure: strict malformed line, or no valid requests available |
| 4 | Unique-cardinality exhaustion at the configured ceiling |

No failure emits a partial JSON or CSV document. Warnings and diagnostics are sent to stderr.

## 6. Parsing and Streaming Strategy

`inputs.py` opens files sequentially with a large buffered reader and yields lines without reading an entire file. `parser.py` uses a single compiled pattern and explicit conversions. It preserves request targets and User-Agent values exactly after syntactic extraction. It rejects timestamps, status codes, and request lines that do not match the supported contract.

For each valid record, `aggregate.py` increments the IP counter, conditionally increments the error-URL counter, increments one of 24 local-hour buckets using the offset encoded in that record, and inserts the User-Agent into a set. The report is finalized only after all inputs finish. Counter selection uses `heapq.nsmallest` or equivalent bounded selection, followed by the specified deterministic sort.

Malformed lines are counted and skipped by default. A bounded sample of line numbers and reasons is retained for diagnostics; raw log lines are not retained. `--strict` changes malformed input into code 3 on the first occurrence.

## 7. Persistence, API, Authentication, and Deployment

There are no database tables, migrations, indexes, cache, HTTP endpoints, request/response bodies, authentication flow, environment variables, Docker Compose file, cloud resources, or Kubernetes manifests. These omissions are architectural decisions, not unfinished sections.

Deployment is a built wheel/sdist published or installed through pip. The wheel exposes the `nginx-insight` console script. A release check installs the wheel into a clean Python 3.11 virtual environment and runs help, fixture, output-schema, and benchmark smoke tests.

## 8. Error Handling and Observability

Domain exception types separate input failures, data failures, and cardinality exhaustion. `cli.py` is the sole exit-code mapper. Unexpected internal exceptions are rendered without a traceback by default and exit 1; development tests exercise the underlying exception.

Terminal diagnostics include source path, line number when known, a short reason, total lines, valid requests, and malformed-line count. Raw User-Agent strings and full rejected lines are not echoed by default, reducing accidental disclosure.

## 9. Security and Privacy

- Treat file content and filenames as untrusted data; never execute or interpolate them into shell commands.
- Rich output escapes or safely renders untrusted fields so markup cannot control the terminal.
- JSON and CSV use standard library encoders and writers rather than manual quoting.
- Avoid symlink policy surprises by documenting that normal OS file permissions and path resolution apply.
- Never transmit, persist, or silently sample log data outside process memory.
- Dependency versions are bounded in packaging and reviewed before release.

## 10. Performance Verification

The benchmark fixture must be representative of combined-format lines and generated outside the timed interval. Record CPU, RAM, storage type, Python version, input size, elapsed wall time, throughput, peak resident memory, and valid/malformed counts. Run the installed wheel with terminal rendering redirected to a file, JSON, and CSV separately; the release gate is under 30 seconds for the named 1 GB case. Synthetic benchmark data is valid only as benchmark evidence and must never be presented as production data.

## 11. Architecture Decision Record

### ADR-001: Single-process stateless CLI

- **Status:** Accepted by product brief.
- **Decision:** Use one Python process and a parse → aggregate → render pipeline, without a database or network service.
- **Consequences:** Installation and privacy are simple; exact aggregates can consume memory proportional to unique values, so code 4 and a tested ceiling are mandatory.
- **Rejected:** ELK-style persistence, embedded SQLite, HTTP service, microservices, cloud workers, and Kubernetes because they violate explicit scope and add no value to a one-shot local report.

No Devil's Advocate or independent review was performed in this session; that review is intentionally reserved for the external harness.
