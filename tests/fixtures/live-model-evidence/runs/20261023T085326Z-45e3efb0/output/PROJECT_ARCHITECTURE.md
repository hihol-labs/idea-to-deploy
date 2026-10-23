# Project Architecture: nginx-top

## 1. Context and Goals

`nginx-top` is a local Python 3.11 batch-style CLI that consumes nginx combined access-log records incrementally and emits one final report. It must process a representative 1 GB input in under 30 seconds on a documented laptop, remain installable with pip, and expose equivalent Rich text, JSON, and CSV views.

The selected architecture is an obvious single-process modular CLI: input adapter → parser → streaming aggregator → immutable result → renderer. The process keeps counters and an explicitly guarded set for exact User-Agent cardinality, but no records after exit.

## 2. Architectural Decision

**Decision:** no database — stateless streaming processing; no HTTP API — CLI-only tool

Both constraints are correct here. A database would add writes, schema lifecycle, storage cost, and privacy exposure while none of the required outputs needs cross-run history. A streaming pass computes the requested snapshot directly and allows stdin pipelines. An HTTP API would require a server, authentication decisions, port/process management, and a network trust boundary without serving the target workflow; DevOps/SRE users already invoke local diagnostic commands and need stdout artifacts.

The architecture uses one OS process and one input-reading thread of execution. It does not include authentication because there is no network service or persistent user boundary. Access control remains the host filesystem and shell user's permissions. Deployment means installing a Python package locally; there is no container or remote deployment target.

## 3. System Components

| Component | Planned path | Responsibility |
|---|---|---|
| CLI composition | `src/nginx_top/cli.py` | Click command, option validation, source lifecycle, renderer selection, exception-to-exit mapping |
| Input adapter | `src/nginx_top/input.py` | Open regular files or bind stdin as UTF-8 text streams without loading whole inputs |
| Parser | `src/nginx_top/parser.py` | Convert one nginx combined-format line into the minimal `LogRecord` dataclass |
| Domain models | `src/nginx_top/models.py` | `LogRecord`, ranked item, hourly bucket, diagnostics, and `AnalysisResult` dataclasses |
| Aggregator | `src/nginx_top/aggregate.py` | Update counters in one pass and enforce the User-Agent cardinality ceiling |
| Text renderer | `src/nginx_top/renderers/text.py` | Rich tables, headings, percentages, TTY-aware color |
| JSON renderer | `src/nginx_top/renderers/json.py` | Stable object schema with numeric counts and percentages |
| CSV renderer | `src/nginx_top/renderers/csv.py` | Stable long-form rows suitable for downstream tools |
| Errors | `src/nginx_top/errors.py` | Typed operational failures carrying the public exit code |

### Processing Flow

```text
file path(s) or stdin
        │
        ▼
line iterator ── I/O failure ───────────────► stderr + exit 1
        │
        ▼
combined-log parser ── malformed line ──────► count/skip or exit 3 (--strict)
        │
        ▼
single-pass aggregator ── UA limit exceeded ► stderr + exit 4
        │
        ▼
AnalysisResult dataclass
        │
        ├── Rich text ─► stdout
        ├── JSON ──────► stdout
        └── CSV ───────► stdout
```

## 4. Data Model and Streaming State

There are no database tables. The complete in-memory model is:

| Dataclass/state | Fields and types | Invariants |
|---|---|---|
| `LogRecord` | `client_ip: str`, `timestamp: datetime`, `request_target: str`, `status: int`, `user_agent: str` | Created only from a valid supported-format line; timestamp is timezone-aware |
| `RankedCount` | `key: str`, `count: int`, `rank: int` | Rank starts at 1; deterministic tie break by key ascending |
| `HourlyBucket` | `hour: int`, `request_count: int`, `percentage: float` | Hours 0–23; percentage is `100 × hourly_request_count / total_valid_requests` |
| `Diagnostics` | `total_lines: int`, `valid_lines: int`, `malformed_lines: int`, `input_sources: int` | `total_lines = valid_lines + malformed_lines` after normal completion |
| `AnalysisResult` | `top_ips: tuple[RankedCount, ...]`, `top_error_urls: tuple[RankedCount, ...]`, `hourly_distribution: tuple[HourlyBucket, ...]`, `unique_user_agent_count: int`, `unique_user_agent_share_percent: float`, `diagnostics: Diagnostics` | Ranked lists contain at most 10 items; all renderers consume this object |
| Aggregation state | `Counter[str]` for IPs, `Counter[str]` for error URLs, fixed `list[int]` of 24 hours, `set[str]` for unique UAs, integer diagnostics | Updated once per valid record; set size may not exceed the configured ceiling |

The unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`. An empty valid input reports `0.0` for all percentages and empty ranked lists. Exact uniqueness requires memory proportional to the number of distinct User-Agent strings; `--max-unique-user-agents` makes that trade-off explicit and exits 4 before producing an incomplete report.

The top-10 lists are selected at finalization with deterministic ordering: count descending, then key ascending. The error URL counter includes statuses 400–599 inclusive and groups by the parsed request target exactly as logged, including query string.

## 5. Supported Input Contract

- Input is one or more paths supplied as arguments, or `-`/no paths for stdin.
- Paths are processed sequentially as one logical dataset; a path cannot be combined with an implicit stdin.
- Text decoding is UTF-8 with replacement for undecodable byte sequences, preventing platform-dependent crashes while preserving line boundaries.
- The supported record shape is nginx's conventional combined format: remote address, ident/user fields, bracketed timestamp with numeric offset, quoted request, status, body-byte count, quoted referrer, and quoted User-Agent.
- The request target is the second token of a standard three-token request field (`METHOD target HTTP/version`). A request field of `-` is valid but has no target and therefore cannot contribute to the error-URL ranking.
- Blank or non-matching lines are malformed. Default behavior counts and skips them; `--strict` stops at the first malformed line with exit 3.
- Timestamps are bucketed by the hour encoded in each record's own numeric timezone offset; logs are not normalized to the machine timezone.
- Regular files are read line by line. No seek, second pass, decompression, tail-follow mode, or directory recursion is part of the MVP.

## CLI Interface

### Command

```text
nginx-top [OPTIONS] [INPUTS]...
```

### Arguments and Options

| Surface | Type/default | Contract |
|---|---|---|
| `INPUTS` | zero or more paths | Sequential log files; zero inputs or a single `-` reads stdin |
| `--json` | flag, off | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | flag, off | Emit long-form CSV with a header; mutually exclusive with `--json` |
| `--strict` | flag, off | Fail on the first malformed record instead of counting and skipping it |
| `--max-unique-user-agents INTEGER` | default `1000000` | Positive exact-cardinality ceiling; exceeding it exits 4 |
| `--color / --no-color` | auto | Applies only to text; auto enables color only on a capable TTY |
| `--version` | flag | Print version and exit 0 |
| `--help` | flag | Print usage and exit 0 |

Invalid combinations, a non-positive cardinality ceiling, or `-` mixed with file paths are Click usage errors and exit 2.

### Inputs

The command reads nginx combined access logs from named local files or stdin. All sources form one aggregate. It never writes to input files and never sends data over a network.

### Outputs

- Data output is written only to stdout.
- Warnings and errors are written only to stderr.
- Default text contains four sections: top client IPs, top error URLs, hourly distribution, and User-Agent summary, followed by parse diagnostics.
- JSON uses top-level keys `top_ips`, `top_error_urls`, `hourly_distribution`, `user_agents`, and `diagnostics`. Percentages are JSON numbers rounded to six decimal places at serialization.
- CSV uses columns `metric,rank,key,count,percentage`. Ranked metrics populate `rank`, `key`, and `count`; hourly rows use `key` values `00` through `23` and populate count/percentage; the User-Agent row uses `metric=unique_user_agent_share`, its unique count, and percentage. Empty cells remain empty, not zero.
- Ordering is deterministic across all formats.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Analysis completed and output was fully written, including an empty valid dataset |
| `1` | Input/output operational failure, such as unreadable input, broken non-pipe output, or write failure |
| `2` | CLI usage or option validation error |
| `3` | Malformed input encountered in `--strict` mode |
| `4` | Unique-cardinality exhaustion: distinct User-Agents exceeded `--max-unique-user-agents` |

A normal downstream pipe close may be treated as a clean exit 0; other output failures are exit 1. No nonzero path emits a partial JSON/CSV report.

## 7. Output Schema Examples

Illustrative JSON shape (values are examples, not fixtures):

```json
{
  "top_ips": [{"rank": 1, "key": "192.0.2.10", "count": 42}],
  "top_error_urls": [{"rank": 1, "key": "/missing", "count": 7}],
  "hourly_distribution": [{"hour": 0, "request_count": 10, "percentage": 25.0}],
  "user_agents": {"unique_count": 4, "share_percent": 10.0},
  "diagnostics": {"total_lines": 40, "valid_lines": 40, "malformed_lines": 0, "input_sources": 1}
}
```

All 24 hourly buckets appear in JSON, CSV, and text even when their count is zero. This prevents consumers from mistaking a missing bucket for missing analysis.

## 8. Performance and Resource Design

- One parse and aggregation pass gives O(n) input time.
- Fixed hourly state is O(1); IP and error-URL counters are O(distinct keys); exact User-Agent state is O(distinct User-Agents) up to the configured ceiling.
- The implementation reads through buffered text streams and does not retain raw lines or `LogRecord` instances after aggregation.
- The parser uses one precompiled expression or an equivalent allocation-conscious scanner, and parses only fields needed by the metrics.
- Benchmark acceptance uses a generated, representative 1 GB file on a named laptop with Python version, CPU, memory, warm/cold-cache condition, wall time, and peak RSS recorded.
- Performance is not claimed from unit tests. `tests/perf/benchmark_1gb.py` is an opt-in benchmark and is excluded from routine test runs.

## 9. Error Handling and Observability

The CLI catches only known boundary errors and maps them to the `0/1/2/3/4` contract. Messages identify the source and line number when available but never echo a complete access-log record, reducing accidental disclosure of tokens or personal data in diagnostics. Tracebacks are suppressed for expected user errors.

No telemetry, log upload, or analytics is present. In default non-strict mode, the successful report includes total, valid, and malformed line counts. This is the audit signal that the summary may exclude bad lines.

## 10. Security and Privacy

- Logs remain local; no network client is part of runtime dependencies.
- Input is treated as untrusted data and is never evaluated or interpolated into shell commands.
- Rich rendering escapes or safely prints log-derived strings so terminal markup/control content cannot become formatting instructions.
- CSV cells are serialized with the standard library. Values beginning with spreadsheet formula triggers (`=`, `+`, `-`, `@`) are prefixed with a single quote in CSV output to reduce formula-injection risk.
- JSON serialization uses the standard library and never builds JSON by concatenation.
- The README warns that output may still contain IP addresses, URLs, and User-Agents and should be handled as log-derived potentially sensitive data.

## 11. Packaging and Deployment

The package uses a `src/` layout, `pyproject.toml`, and a console-script entry point named `nginx-top`. The supported deployment target is a Python 3.11 virtual environment on Linux or macOS installed by pip. A wheel and source distribution are the release artifacts.

Docker, Docker Compose, cloud, Kubernetes, systemd, and server deployment are intentionally absent. A container would add no isolation benefit required by this local read-only workflow and would complicate access to local logs and stdin.

There are no application environment variables. Behavior is explicit through CLI options; standard process settings such as locale and `NO_COLOR` may influence presentation but are not application configuration secrets.

## 12. Authentication and Authorization

Authentication is not applicable because there is no server, account, remote request, or persistent multi-user state. Authorization is inherited from the operating system:

```text
shell user ── filesystem permission ──► readable nginx log
           └─ execute permission ─────► installed nginx-top command
```

The program does not elevate privileges. Operators should grant narrowly scoped read permission or analyze a copied log rather than running the tool as root.

## 13. Architecture Decision Record

### ADR-001: Single-process streaming CLI

- **Status:** Accepted; pre-approved in the product brief.
- **Decision:** Use one modular Python process with line-by-line parsing and aggregation.
- **Why:** It is the smallest architecture satisfying local privacy, pip installation, pipeline operation, $0 cost, and weekend delivery.
- **Consequences:** Simple install and deterministic flow; exact distinct-value metrics still require guarded memory, and CPU parallelism is not assumed.

### Alternatives considered and rejected

- GoAccess integration — capable but makes the Python package a wrapper around an external binary and weakens the stable JSON/CSV contract.
- Logstash/Elastic/Kibana — violates the no database/server/cloud boundary and weekend budget.
- AWStats — persistent report workflow does not fit stdin pipelines.
- Shell-only `grep`/`awk` — insufficiently stable for quoted fields, repeatable exit semantics, and cross-platform pip distribution.
- Multi-process parser — added ordering, IPC, and error-coordination complexity is unjustified until a benchmark proves one process cannot meet the target.

No adversarial or independent architecture review is recorded here; that review is intentionally performed by the external harness in a separate session.

## 14. Repository Layout

```text
pyproject.toml
src/nginx_top/
  __init__.py
  cli.py
  input.py
  parser.py
  aggregate.py
  models.py
  errors.py
  renderers/
    __init__.py
    text.py
    json.py
    csv.py
tests/
  fixtures/
  unit/
  integration/
  perf/
```

The planned implementation paths are specifications only; this blueprint does not create product code.

