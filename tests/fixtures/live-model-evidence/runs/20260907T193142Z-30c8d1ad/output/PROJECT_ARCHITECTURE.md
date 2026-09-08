# Project Architecture: Nginx Stream Analytics CLI

## 1. Context and Constraints

The product is a local Python 3.11 executable installed through pip and operated by DevOps/SRE engineers. It reads nginx Combined Log Format from one file or standard input, aggregates in a single process, writes one selected representation to standard output, and writes diagnostics to standard error.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the promised outputs can be computed during one pass, persistence adds cost and security/cleanup obligations, and retained request records violate the narrow local-triage scope. An HTTP API is incorrect because the consumer is a human shell or Unix pipeline, while a server would add lifecycle, port, authentication, deployment, and availability concerns without improving the required analysis.

Hard constraints: no authentication, server, cloud, Docker runtime requirement, or Kubernetes; $0 budget; one-weekend build; Python 3.11, Click, Rich, and dataclasses; exact results up to an explicit cardinality limit; 1 GB in under 30 seconds on a documented reference laptop.

## 2. Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** one Python process performs read → parse → aggregate → finalize → render, retaining counters and exact distinct-key sets only.
- **Pros:** one input pass, simple packaging, lowest operational overhead, natural stdin support, testable pure components.
- **Cons:** exact distinct cardinality consumes memory; CPU parsing remains single-process.
- **Best for:** local analysis of individual logs and Unix pipelines.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunk parsing

- **Approach:** split seekable files into byte ranges, parse in workers, and merge partial aggregates.
- **Pros:** can use multiple CPU cores on large regular files.
- **Cons:** complicates line boundaries, stdin support, deterministic errors, memory ceilings, and one-weekend delivery.
- **Best for:** later optimization only if profiling proves parsing CPU-bound.
- **Estimated complexity:** Medium.

### Variant C: Embedded analytical database

- **Approach:** load or query log records through an embedded database engine.
- **Pros:** flexible ad hoc queries and mature grouping operations.
- **Cons:** violates approved stateless design, adds dependency/startup/storage costs, and duplicates a one-pass workload.
- **Best for:** repeated exploratory analysis, which is outside scope.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the architecture is pre-approved and directly satisfies local execution, stdin streaming, $0 operations, and one-weekend delivery. Variant B is a profiling-triggered future decision; Variant C is rejected.

## 3. System Context and Data Flow

```text
nginx log file ─┐
                ├─> byte/text stream -> parser -> validated LogRecord
standard input ─┘                              |
                                                v
                                   StreamingAggregator
                       ┌────────────┬───────────┼──────────────┐
                       v            v           v              v
                   IP counts   error URLs   hour counts   unique UA set
                       └────────────┴───────────┴──────────────┘
                                                |
                                           Report model
                                                |
                                  terminal | JSON | CSV -> stdout
                                  diagnostics/errors      -> stderr
```

There are no background workers, network calls, persistent stores, or cross-run state. Rendering starts only after successful parsing so a failure cannot be mistaken for a complete report.

## 4. Package and Component Design

```text
pyproject.toml
src/nginx_stream_analytics/
├── __init__.py
├── cli.py                 # Click command, option validation, orchestration
├── models.py              # frozen LogRecord, RankedMetric, AnalysisReport dataclasses
├── parser.py              # compiled Combined Log Format parser and timestamp conversion
├── aggregate.py           # StreamingAggregator and cardinality guard
├── errors.py              # typed domain exceptions and exit-code mapping
└── renderers/
    ├── __init__.py
    ├── terminal.py        # Rich tables and percentages
    ├── json.py            # versioned object schema
    └── csv.py             # long-form row schema
tests/
├── fixtures/
├── test_parser.py
├── test_aggregate.py
├── test_renderers.py
├── test_cli.py
└── test_performance.py
```

| Component | Input | Output | Invariant |
|---|---|---|---|
| `cli` | Click parameters and input stream | selected renderer output or mapped error | stdout contains only the selected data format |
| `parser` | one physical line plus line number | `LogRecord` | rejects malformed/unsupported records with location |
| `StreamingAggregator` | one `LogRecord` at a time | immutable `AnalysisReport` | counters reflect every and only valid record |
| terminal renderer | `AnalysisReport` | Rich tables | color follows policy and never affects JSON/CSV |
| JSON renderer | `AnalysisReport` | one JSON object | deterministic keys and schema version |
| CSV renderer | `AnalysisReport` | header plus long-form rows | RFC 4180-compatible quoting via `csv` module |

### Domain models

- `LogRecord(remote_addr: str, timestamp: datetime, request_target: str, status: int, user_agent: str)` is immutable. The parser extracts the URL path plus query exactly as logged; request method and protocol may be parsed for validation but are not retained.
- `RankedMetric(key: str, count: int, percentage: float | None)` represents a stable ranked row.
- `AnalysisReport(schema_version: str, total_valid_requests: int, top_ips: tuple[RankedMetric, ...], top_error_urls: tuple[RankedMetric, ...], hourly_distribution: tuple[RankedMetric, ...], unique_user_agents: int, unique_user_agent_share_percent: float)` is renderer-independent.

Ties in top lists sort by count descending, then key ascending. All 24 hours appear from `00` through `23`, including zeros. Unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`, and is `0.0` for empty valid input. Hourly request distribution is a percentage calculated exactly as `100 × hourly_request_count / total_valid_requests`; for empty valid input each hour is `0.0%`.

## 5. Parsing Contract

The MVP accepts nginx Combined Log Format records equivalent to:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

- Read incrementally with a buffered text wrapper using UTF-8 and explicit replacement disabled; invalid UTF-8 is an input error.
- Compile the parsing expression once. Parse timestamps with the numeric source offset and derive the hour in that source timestamp; no implicit local-machine conversion.
- Count every valid request for IP, hour, total, and User-Agent distinctness.
- Count a URL in the error ranking only when status is 400–599 inclusive.
- Treat `"-"` as the literal absent User-Agent bucket; it remains one distinct value.
- Fail on the first malformed line by default, report its one-based line number on stderr, emit no report, and return exit code 3.
- An empty file is valid and produces empty rankings, zero counts, and 24 zero hourly percentages.

The parser does not follow files, auto-detect arbitrary custom formats, decompress input, or accept multiple input files in the MVP.

## 6. State, Memory, and Performance

Streaming state consists of `Counter[str]` for IPs, `Counter[str]` for error URLs, a fixed 24-element integer array, a `set[str]` of User-Agents, and the total-valid counter. The tool retains no raw lines or `LogRecord` objects after aggregation.

Exact top-10 requires counts for all distinct IPs/error URLs; exact unique User-Agent share requires an exact distinct set. Therefore `--max-unique` bounds each variable-cardinality collection. Reaching the limit is allowed; attempting to insert a new distinct key beyond it aborts with exit code 4 and no report. The CLI must never substitute sketches or partial rankings silently.

Performance design:

- one sequential pass with buffered reads;
- one compiled parser and direct field extraction;
- no per-line Rich objects, JSON objects, or retained records;
- a size-10 heap keyed by count descending/key ascending at finalization, avoiding a full sort while preserving deterministic ties;
- benchmark outside coverage/profiling overhead on a generated, content-described 1 GB fixture;
- record wall time and peak RSS across at least three warm-cache runs and one cold-cache run on the named reference laptop.

If the target fails, profile first. Multiprocessing requires a new architecture decision and must preserve stdin and deterministic error behavior.

## CLI Interface

### Command

```text
nginx-stream-analytics [OPTIONS] [INPUT]
```

`INPUT` is an optional path to one nginx access log. When omitted or exactly `-`, bytes are read from stdin. The command never mutates the input.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit exactly one JSON document; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit the long-form CSV schema; mutually exclusive with `--json` |
| `--color [auto|always|never]` | `auto` | Applies only to terminal output; `auto` colors only a TTY |
| `--max-unique INTEGER` | `1_000_000` | Positive ceiling applied independently to IP, error-URL, and User-Agent distinct keys |
| `--version` | flag | Print version and exit 0 without reading input |
| `--help` | flag | Print Click help and exit 0 without reading input |

Top-N is fixed at 10 in the MVP. `--json` and `--csv` imply no color. Invalid combinations or nonpositive `--max-unique` are usage errors.

### Outputs

Default terminal output contains four titled sections: Top 10 IPs (`IP`, `Requests`), Top 10 Error URLs (`URL`, `4xx/5xx Requests`), Hourly Request Distribution (`Hour`, `Requests`, `Percentage`), and User-Agent Uniqueness (`Unique`, `Total Requests`, `Share`).

JSON schema:

```json
{
  "schema_version": "1.0",
  "total_valid_requests": 0,
  "top_ips": [{"ip": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"url": "/missing", "count": 1}],
  "hourly_distribution": [{"hour": "00", "count": 0, "percentage": 0.0}],
  "user_agents": {"unique_count": 0, "share_percentage": 0.0}
}
```

The real `hourly_distribution` array always has 24 ordered elements. JSON percentages are numeric percentage points, not fractions.

CSV uses one header for all report sections:

```text
report,rank,key,count,percentage
top_ip,1,192.0.2.1,1,
error_url,1,/missing,1,
hour,,00,0,0.0
user_agent_share,,,0,0.0
```

Diagnostic messages go only to stderr and contain no traceback unless a future explicit debug option is added.

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Successful report, help, or version output |
| 1 | Unexpected internal/runtime failure |
| 2 | Click usage error, invalid option combination, or input file cannot be opened/read |
| 3 | Log decoding or parse error; no report emitted |
| 4 | Unique-cardinality exhaustion for IP, error URL, or User-Agent state; no report emitted |

## 8. Error and Observability Contract

Domain exceptions map once at the CLI boundary. Expected errors use `Error: <message>` on stderr and never print a traceback. Broken pipes exit 0 after closing stdout cleanly because a downstream consumer intentionally stopped reading. Unexpected exceptions return 1 with a concise diagnostic.

No telemetry or logging leaves the machine. Optional future verbose diagnostics must go to stderr and must not include entire access-log lines, because URLs and User-Agents may contain sensitive values.

## 9. Security and Privacy

Input is untrusted text, never evaluated or passed to a shell. Click supplies path handling; Python output libraries supply escaping/quoting. Rich markup is disabled or escaped for log-derived fields. The process performs no network access. Raw logs and aggregates are not persisted. Documentation warns that stdout may contain IP addresses, URLs, and User-Agents and should be redirected only to appropriately protected destinations.

Dependency scope is limited to Click and Rich at runtime. Release builds pin supported ranges, use a lock/constraints strategy for development, and run vulnerability and license checks without adding runtime services.

## 10. Data, API, Authentication, and Deployment Decisions

### Database

No database exists and there are no tables, schemas, migrations, indexes, or retained records. In-memory structures in Section 6 are ephemeral implementation state, not a database. This deliberate exception to the generic blueprint template is required by the product constraint.

### HTTP API

No HTTP API exists and there are no endpoints, request bodies, response bodies, sockets, or ports. The complete public interface is the CLI in `## CLI Interface`.

### Authentication

No authentication or authorization exists because there is no remote service or multi-user boundary. Authorization is the invoking operating-system user's ability to read the input and write the destination.

```text
OS user -> shell -> CLI process -> OS file/stdin permissions
                          X
                 no network/auth flow
```

### Configuration and environment

There are no required environment variables or `.env` file. Locale and terminal capability must not change JSON/CSV semantics. Standard `NO_COLOR` may be honored for default terminal color, while `--color` provides explicit behavior.

### Packaging and deployment

Deployment means building a wheel/sdist and installing it into a Python 3.11 environment with pip. `pyproject.toml` exposes the `nginx-stream-analytics` console script. There is no Docker Compose topology, container requirement, server deployment, cloud resource, or Kubernetes manifest.

Release verification installs the built wheel into a fresh virtual environment, runs `--help` and `--version`, analyzes a fixture from a file and stdin in all three formats, and compares schemas and exit codes.

## 11. Architecture Decision Record

### ADR-001: Stateless single-process CLI

- **Status:** Accepted by the product brief.
- **Decision:** Use Variant A and the literal constraint **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- **Consequences:** minimal operations and one-pass pipeline support; exact cardinality must be explicitly bounded; repeated ad hoc queries require rereading input.

### ADR-002: Exact aggregation with fail-closed cardinality guard

- **Status:** Accepted.
- **Decision:** Exact counters/sets up to `--max-unique`; exit 4 before accepting a distinct key beyond the ceiling.
- **Consequences:** results are exact when emitted; adversarial cardinality can stop analysis rather than degrade silently.

### ADR-003: One report model, three renderers

- **Status:** Accepted.
- **Decision:** Parsing and aggregation never depend on presentation; terminal, JSON, and CSV consume the same immutable report.
- **Consequences:** cross-format values can be tested for equality and pipeline output remains stable.

The planned external Devil's Advocate review is intentionally not recorded here: it runs in a separate fresh benchmark session and may append its own artifact or require later ADR amendments. No adversarial or independent reviewer ran during this blueprint session.

## 12. Quality Attributes and Acceptance

| Attribute | Requirement | Evidence planned |
|---|---|---|
| Correctness | Exact deterministic values and tie order | unit fixtures plus cross-renderer golden tests |
| Performance | 1 GB under 30 seconds on documented laptop | reproducible benchmark record |
| Memory safety | Explicit cardinality ceiling; no raw-line retention | exhaustion integration tests and peak-RSS measurement |
| Portability | Python 3.11 pip install on Linux/macOS; best-effort Windows | clean-environment wheel smoke tests |
| Pipeline safety | data on stdout, diagnostics on stderr, stable schemas | CLI integration tests |

Product behavior is specified in `PRD.md`; construction order and verification commands are in `IMPLEMENTATION_PLAN.md`.
