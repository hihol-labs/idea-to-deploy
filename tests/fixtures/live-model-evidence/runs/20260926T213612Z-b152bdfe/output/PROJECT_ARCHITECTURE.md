# Project Architecture: Nginx Stream Analyzer

## 1. Architecture Summary

The product is a single-process Python 3.11 CLI with a pipeline of input iterator → line parser → streaming aggregator → selected renderer. The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because reports are derived from one invocation's input, persistence creates installation and privacy burdens, and the one-weekend/$0 brief requires no retained state. An HTTP API is incorrect because the users already operate in terminals and pipelines; a server would introduce authentication, lifecycle, ports, deployment, and attack surface without improving the required workflow.

Authentication is therefore not applicable: the process has only the invoking operating-system user's file and pipe permissions. Deployment means installing a Python package with pip. Docker, cloud infrastructure, Kubernetes, background workers, and network listeners are explicitly absent.

## 2. Constraints and Quality Attributes

| Attribute | Contract |
|---|---|
| Runtime | CPython 3.11 |
| Scale | Stream a 1 GB input in under 30 seconds on the documented reference laptop |
| State | Invocation-local only; no files written except an explicitly redirected output stream |
| Memory | Do not retain raw lines or per-request records; guard exact User-Agent cardinality |
| Privacy | No network access, telemetry, or persistence |
| Portability | Linux and macOS primary; Windows supported where Python/Click/Rich support it |
| Determinism | Stable tie-breaking and output schema for identical input and options |

## 3. Component Design

Planned package layout:

```text
pyproject.toml
src/nginx_stream_analyzer/
  __init__.py
  cli.py                 # Click command, option validation, exception-to-exit mapping
  models.py              # dataclasses for ParsedRequest and Report
  parser.py              # combined-log parser and ParseError classification
  aggregate.py           # counters, top-k selection, hourly percentages, UA guard
  inputs.py              # stdin/file text stream ownership and decoding policy
  outputs/
    __init__.py
    terminal.py          # Rich tables and color
    json_output.py       # stable JSON object
    csv_output.py        # normalized multi-section CSV rows
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_outputs.py
  test_performance.py
```

| Component | Input | Output | Responsibility |
|---|---|---|---|
| `inputs` | path or stdin | text-line iterator | Open with UTF-8 replacement policy, track ownership, surface I/O errors |
| `parser` | one text line | `ParsedRequest` or classified parse error | Parse supported combined format once without retaining source text |
| `aggregate` | valid records | final `Report` | Count total/invalid, IPs, error URLs, 24 hourly buckets, exact UA set up to limit |
| `terminal` | `Report` | stderr-free terminal text on stdout | Rich headings/tables with color capability detection |
| `json_output` | `Report` | one JSON document | Stable types and keys, no ANSI output |
| `csv_output` | `Report` | normalized CSV | Stable header and section-discriminated rows, no ANSI output |
| `cli` | argv and streams | output + exit status | Compose pipeline and enforce public contract |

## 4. Data Model

No database tables exist. The complete invocation-local data model is:

```text
ParsedRequest (frozen dataclass)
  client_ip: str
  timestamp: datetime        # timezone-aware, parsed from nginx timestamp
  request_target: str        # raw request-target token; query string retained
  status: int
  user_agent: str            # "-" is a value unless product tests decide otherwise

RankedCount (frozen dataclass)
  value: str
  count: int

HourlyShare (frozen dataclass)
  hour: int                  # 0..23 in the offset encoded by each log timestamp
  request_count: int
  percentage: float

Report (frozen dataclass)
  total_lines: int
  total_valid_requests: int
  malformed_lines: int
  top_ips: tuple[RankedCount, ...]
  top_error_urls: tuple[RankedCount, ...]
  hourly_distribution: tuple[HourlyShare, ...]  # always 24 ordered buckets
  unique_user_agents: int
  unique_user_agent_share_percentage: float
```

Operational aggregation state contains an IP counter, error-URL counter, 24 integer hour buckets, and an exact User-Agent set. Counters contain distinct keys, not requests; this is streaming but cardinality-sensitive. `--max-unique-user-agents` defaults to 1,000,000. Crossing the limit aborts with exit code 4 rather than silently switching to an estimate. Empty valid input yields zero counts and percentages, not division by zero.

Top lists sort by descending count and then ascending UTF-8/Unicode string value for deterministic ties. Error URLs include response statuses 400–599. Hourly request distribution is a percentage calculated exactly as `100 × hourly_request_count / total_valid_requests`; output rounds only at rendering time. The unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests` and may exceed neither 100% nor the number of valid requests.

## 5. Parsing Contract

- MVP accepts nginx's conventional combined access-log shape: remote address, identity/user fields, bracketed timestamp with numeric offset, quoted request, status, byte count, quoted referrer, and quoted User-Agent.
- The request field is split into method, request target, and protocol; only the request target is aggregated.
- IPv4 and IPv6 textual addresses are accepted as emitted in the first field.
- Escaped quotes/backslashes in quoted nginx fields must be handled by the parser's explicit state machine or a compiled, tested pattern; `split()` over the entire line is forbidden.
- Timestamp parse failures, invalid status values, missing fields, and malformed quoting classify the line as malformed.
- Input decoding uses UTF-8 with replacement so an isolated byte does not crash the run; the replacement character remains visible in affected values.
- By default, malformed lines are skipped, summarized, and cause exit code 3 after valid output is emitted. `--fail-fast` stops on the first malformed line and returns 3 without a partial report.

## 6. Processing Flow

```text
argv
  │
  ▼
Click validation ──invalid usage──────────────► exit 2
  │
  ▼
open file/stdin ──I/O/runtime failure─────────► exit 1
  │
  ▼
line iterator → parser ──malformed────────────► count/skip or fail-fast → exit 3
  │ valid
  ▼
streaming aggregators ──UA limit exceeded─────► exit 4
  │ EOF
  ▼
finalize deterministic top-10 and percentages
  │
  ▼
terminal | JSON | CSV renderer ──success──────► exit 0 (or 3 if malformed skipped)
```

## CLI Interface

### Command

```text
nginx-stream-analyzer [OPTIONS] [INPUT]
```

`INPUT` is an optional path. Omitted or `-` reads standard input. The command never follows/tails a growing file; “streaming” means one-pass incremental processing to EOF.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag | Emit JSON; mutually exclusive with `--csv` |
| `--csv` | flag | Emit normalized CSV; mutually exclusive with `--json` |
| `--no-color` | flag | Disable color in terminal mode; ignored by machine formats |
| `--fail-fast` | flag | Stop at the first malformed line with exit 3 |
| `--max-unique-user-agents INTEGER` | default `1000000`, minimum `1` | Exact-cardinality safety limit |
| `--version` | flag | Print version and exit 0 |
| `--help` | flag | Print usage and exit 0 |

### Inputs

- One seekable or non-seekable text stream in supported nginx combined format.
- File and stdin have identical parsing behavior.
- Directories, missing/unreadable paths, and stream read failures are operational errors.
- The analyzer emits no progress text, ensuring redirected stdout remains a valid chosen format.

### Outputs

Terminal mode writes four Rich report sections plus input totals. Color is enabled for capable terminals by default and disabled by `--no-color` or Rich's non-terminal detection.

JSON is one UTF-8 object with this stable shape:

```json
{
  "summary": {"total_lines": 0, "valid_requests": 0, "malformed_lines": 0},
  "top_ips": [{"ip": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"url": "/missing", "count": 1}],
  "hourly_distribution": [{"hour": 0, "request_count": 0, "percentage": 0.0}],
  "user_agents": {"unique_count": 0, "share_percentage": 0.0}
}
```

The actual hourly array contains all 24 hours in ascending order. JSON numbers remain numeric.

CSV uses the exact header `section,key,count,percentage`. Rows use `summary` keys (`total_lines`, `valid_requests`, `malformed_lines`), `top_ip` keys (IP strings), `top_error_url` keys (URL strings), `hour` keys (`00`–`23`), and `user_agent` key `unique`. Fields not applicable to a row are empty. Python's CSV writer performs all quoting.

Diagnostics go to stderr. Reports go to stdout. Machine formats contain no ANSI escape sequences.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Successful analysis with no malformed input; also help/version |
| `1` | Operational failure such as unreadable input, stream error, or unexpected internal failure |
| `2` | CLI usage or option validation error |
| `3` | Malformed log input encountered, whether skipped or fail-fast |
| `4` | Unique-cardinality exhaustion: the configured exact User-Agent limit was exceeded |

The precedence when multiple conditions are observed is `1`, then `4`, then `3`; Click validation returns `2` before processing begins.

## 8. Output and Error Boundaries

- Renderers receive a completed immutable `Report`; they do not parse or aggregate.
- Expected domain failures have typed exceptions. `cli.py` is the only layer mapping them to process statuses.
- Broken pipe while writing to a downstream command terminates quietly under the platform convention and is treated as an operational boundary rather than printing a traceback.
- No traceback is shown for expected user/input failures. Unexpected errors return 1 with a concise diagnostic; debug traceback support is outside MVP.

## 9. Packaging, Configuration, and Deployment

`pyproject.toml` declares Python `>=3.11,<4`, Click and Rich runtime dependencies, pytest tooling, and the `nginx-stream-analyzer` console entry point. Runtime environment variables are intentionally absent; all behavior is explicit in CLI options. There is no `.env`, container image, Compose file, daemon, network port, deployment environment, or migration.

Installation target:

```bash
python3.11 -m pip install nginx-stream-analyzer
nginx-stream-analyzer --help
```

During development, use an isolated virtual environment and `python -m pip install -e '.[dev]'`. Publishing to an open-source package index is optional release work and must not require paid infrastructure.

## 10. Architecture Decision Record

### ADR-001: Single-process streaming CLI

- **Status:** Accepted by the product brief.
- **Decision:** One Python process owns input, parsing, aggregation, and rendering through separated modules.
- **Why:** It is the lowest-complexity design that meets privacy, $0, pip installation, and one-weekend delivery constraints.
- **Consequences:** No cross-process coordination or durable state; cardinality, rather than input byte size, governs memory.

### Alternatives considered and rejected

- **Go implementation:** could improve throughput and distribute one binary, but violates the approved stack and adds delivery risk.
- **SQLite-backed aggregation:** bounds Python heap for high cardinality but adds disk I/O, cleanup, persistence/privacy questions, and contradicts stateless processing.
- **Multiprocessing pipeline:** may improve CPU utilization but complicates ordering, errors, portability, and memory; profile the simple path first.
- **GoAccess:** excellent broader interactive analytics, but does not supply this intentionally narrow Python library/CLI contract.
- **Elastic/Logstash/Kibana:** appropriate for retained fleet-wide analytics, disproportionate for local one-shot triage.
- **AWStats:** oriented toward historical reports rather than composable incident pipelines.
- **Shell pipelines:** useful for one-offs but do not provide a portable parser or stable JSON/CSV/exit contract.

No adversarial or independent architecture review is recorded in this document; that review is explicitly delegated to the external harness.

## 11. Performance and Verification Strategy

- Keep the hot loop free of Rich calls, JSON allocations, and retained request objects.
- Compile parsing machinery once; update primitive counters immediately.
- Use `collections.Counter.most_common` only at finalization, then apply deterministic tie sorting for the boundary candidates.
- Generate a reproducible 1 GB fixture outside the repository and record laptop CPU, storage, OS, Python patch version, wall time, and peak RSS.
- Verify correctness against a smaller known-answer fixture before accepting benchmark results.
- Treat <30 seconds as a release gate, not an architectural assumption; profile parser and counter hotspots if missed.

## 12. Security and Privacy

The trust boundary is the local log stream and argv. The parser treats log contents solely as data, never as terminal markup or format strings. Rich text must escape or disable markup for log-derived strings. CSV uses the standard writer; values beginning with spreadsheet formula characters remain a documented consumer risk because the CLI does not mutate log data. The process makes no network calls, stores no history, executes no content, and relies on OS file permissions.

