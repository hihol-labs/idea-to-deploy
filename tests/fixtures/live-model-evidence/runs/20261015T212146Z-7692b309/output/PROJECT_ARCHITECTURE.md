# Project Architecture: nginx-stream-report

## 1. Context and Decision

The product is a local, installable Python 3.11 CLI that consumes nginx combined access-log records and emits a finite report when input reaches EOF. The approved architecture is one process with explicit parser, aggregation, and presentation boundaries.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema lifecycle, disk amplification, cleanup, and operational state while none of the required reports needs persistence or cross-run queries. An HTTP API would add a listening service, authentication questions, network exposure, deployment work, and a second interface without improving local incident triage or shell composition. A CLI can consume local files/stdin, preserve privacy, and return machine-readable output directly to pipelines.

## 2. Architecture Overview

```text
file path(s) / stdin
         |
         v
  line iterator (text, bounded buffer)
         |
         v
  combined-log parser ---- malformed counter / strict failure
         |
         v
  ParsedRequest dataclass
         |
         v
  StreamingAggregator
    |       |          |              |
   IPs   error URLs  24 hours   unique UA set + cap
         |
         v
  ReportSnapshot dataclasses
         |
   +-----+---------+
   |     |         |
  Rich  JSON      CSV
 stdout only; diagnostics -> stderr; exit status -> shell
```

The process never retains raw log lines or parsed requests after their counters are updated. It stores bounded hourly counters, distinct-key counters required for exact top tens, and a User-Agent set guarded by a configurable cardinality ceiling. The benchmark must establish the practical memory envelope for IP and URL maps; the explicit UA cap prevents the most likely unbounded field from causing uncontrolled exhaustion.

## 3. Components and File Layout

```text
pyproject.toml
src/nginx_stream_report/
  __init__.py
  cli.py                 # Click command, option validation, exception-to-exit mapping
  models.py              # ParsedRequest, RankedItem, HourBucket, ReportSnapshot
  parser.py              # nginx combined-format line parser
  aggregate.py           # one-pass counters, top-ten selection, UA cardinality limit
  renderers/
    __init__.py
    terminal.py          # Rich tables and summary
    json.py              # stable JSON document
    csv.py               # stable long-form rows
  errors.py              # typed input/parse/resource errors
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_renderers.py
  test_performance.py
```

| Component | Responsibility | Must not do |
|---|---|---|
| `cli.py` | Select input/output, validate options, connect pipeline, map errors | Parse fields or calculate metrics |
| `parser.py` | Turn one combined-format line into a typed record | Retain records or print diagnostics |
| `aggregate.py` | Update counters and create a deterministic snapshot | Know terminal/JSON/CSV formatting |
| `renderers/*` | Serialize one snapshot | Recalculate domain metrics |
| `errors.py` | Stable typed failure categories | Swallow underlying context |

## 4. Data Model and Metric Semantics

This project has no database tables. The complete in-memory model is:

| Dataclass/state | Fields | Constraints |
|---|---|---|
| `ParsedRequest` | `remote_addr: str`, `timestamp: datetime`, `request_target: str`, `status: int`, `user_agent: str` | Timestamp is timezone-aware; target preserves path and query as logged; missing UA is normalized to `"-"` |
| `RankedItem` | `value: str`, `count: int` | `count >= 1`; ordered by count descending, then value ascending |
| `HourBucket` | `hour: int`, `count: int`, `percentage: float` | All hours `0..23` are present; percentage serialized consistently |
| `ReportSnapshot` | `total_lines`, `total_valid_requests`, `malformed_lines`, `top_ips`, `top_error_urls`, `hourly_distribution`, `unique_user_agent_count`, `unique_user_agent_share_percent` | Derived once after EOF; immutable to renderers |
| `StreamingAggregator` state | `Counter[str] ips`, `Counter[str] error_urls`, `list[int] hourly_counts`, `set[str] unique_user_agents`, totals | UA insert is refused after configured ceiling; no raw line retention |

Metric definitions:

- Top IPs: ten `remote_addr` values with the highest count across valid records.
- Error URLs: ten request targets with the highest count among status codes `400..599` inclusive.
- Hourly request distribution: local hour as encoded by each nginx timestamp offset; each bucket percentage is exactly `100 × hourly_request_count / total_valid_requests`. When there are zero valid requests, every hourly percentage is `0.0`.
- Unique User-Agent share: `100 × unique_user_agent_count / total_valid_requests`. It measures distinct normalized UA values relative to valid requests, not the proportion of requests with a UA header. It is `0.0` for zero valid requests.
- Ties: count descending, then UTF-8/Unicode value ascending, making all renderers deterministic.
- Percentages: numeric values rounded to two decimal places only at serialization; internal computation retains normal Python floating-point precision.

## 5. Parsing and Streaming Rules

- MVP accepts nginx **combined log format** in UTF-8-compatible text. Parsing is anchored to the whole line and must handle quoted request/referrer/User-Agent fields without catastrophic backtracking.
- Input is opened incrementally; stdin is represented by `-`. Multiple files are read in argument order into one report.
- `--strict` makes the first malformed non-empty line a parse failure. Without it, malformed lines are skipped and counted; a warning summary goes to stderr.
- Blank lines are malformed lines under the same policy.
- Unreadable input, decoding failures, and broken read streams are input failures.
- Log-provided strings are untrusted data. Rich rendering must neutralize markup/control interpretation; JSON/CSV use their standard escaping.
- Exact top tens require counters for distinct IPs and error URLs. This is still single-pass but not constant-cardinality memory. Performance and memory tests must document the safe operating envelope.

## CLI Interface

### Command

```text
nginx-stream-report [OPTIONS] [INPUTS]...
```

### Inputs

- `INPUTS`: zero or more nginx access-log paths. No input or a single `-` reads stdin. Combining `-` with file paths is rejected as usage error to avoid blocking/ordering ambiguity.
- Each valid line uses nginx combined format. Input terminates at EOF; following a never-ending file is not an MVP capability.

### Options

| Option | Meaning | Default / constraint |
|---|---|---|
| `--json` | Emit one JSON document | Mutually exclusive with `--csv` |
| `--csv` | Emit CSV header and long-form rows | Mutually exclusive with `--json` |
| `--strict` | Fail on the first malformed record | Otherwise skip and count malformed records |
| `--max-unique-user-agents INTEGER` | Maximum distinct normalized User-Agents retained | `1000000`; positive integer |
| `--color / --no-color` | Force or suppress terminal color | Auto by TTY; rejected with `--json`/`--csv` if explicitly forced on |
| `--version` | Print version and exit | No input consumed |
| `--help` | Print usage and exit | No input consumed |

### Outputs

- Default: four Rich sections plus total/valid/malformed summary. Color is enabled only for a suitable terminal unless forced.
- JSON: one object with `schema_version`, totals, arrays `top_ips`, `top_error_urls`, `hourly_distribution`, and `unique_user_agents` summary. No ANSI escapes.
- CSV: header `section,key,count,percentage`, then deterministic rows for `top_ip`, `top_error_url`, `hour`, and `unique_user_agents`. Empty ranked sections produce no data row; all 24 hours and one UA summary row are always present.
- Report data goes only to stdout. Warnings and errors go only to stderr.

### Exit-code contract

| Code | Meaning |
|---:|---|
| `0` | Report produced successfully, including a report with zero valid records in non-strict mode |
| `1` | Input/I/O/decoding failure or unexpected internal runtime failure |
| `2` | Click usage error: invalid option, incompatible output flags, or invalid input combination |
| `3` | Parse failure in `--strict` mode |
| `4` | unique-cardinality exhaustion: the next distinct User-Agent would exceed the configured cap |

The contract is complete and stable as `0/1/2/3/4`. Partial reports are never emitted for codes `1`, `3`, or `4`.

### Examples

```bash
nginx-stream-report /var/log/nginx/access.log
cat access.log | nginx-stream-report --json -
nginx-stream-report --csv access.log.1 access.log > report.csv
nginx-stream-report --strict --max-unique-user-agents 250000 access.log
```

## 7. Output Schemas

JSON uses a top-level `schema_version: 1`. Ranked entries use `{ "value": string, "count": integer }`; hourly entries use `{ "hour": integer, "count": integer, "percentage": number }`; the UA object uses `{ "count": integer, "share_percentage": number }`. Additive fields require a documented schema change; removing/renaming/changing types requires a new major schema version.

CSV is a normalized projection of the same snapshot. The `key` for an hour is zero-padded (`00` through `23`); non-applicable percentages are empty, never fabricated as zero.

## 8. Error Handling and Resource Safety

Typed errors map in exactly one place in `cli.py`. Each failure prints a concise, sanitized diagnostic without a traceback by default. The process closes files it opened but never closes caller-owned stdin/stdout. Broken output pipes follow normal CLI behavior and must not produce a Python traceback.

The UA set is checked before insertion. If a new value would exceed the cap, processing stops with exit `4` and no report. The default cap and measured approximate memory footprint are documented after benchmarking. The performance fixture is generated locally and contains no secrets.

## 9. Security and Privacy

- No network calls or telemetry exist.
- Log content is never persisted by the tool.
- Paths and parse snippets in diagnostics are length-bounded and control characters are escaped.
- Rich markup is disabled or escaped for all log-derived values.
- Dependencies are runtime-pinned with compatible lower/upper bounds and audited before release.
- The CLI inherits the invoking user’s filesystem permissions; it must not elevate privileges.

## 10. Packaging and Runtime

`pyproject.toml` defines Python `>=3.11,<4`, Click, Rich, the `src` package layout, and the `nginx-stream-report` console script. The installation target is any local Python 3.11 environment supported by pip. There is no Docker image, Compose file, daemon, cloud target, Kubernetes manifest, environment variable, authentication flow, database migration, or HTTP endpoint.

## 11. Architecture Alternatives

The single-process architecture is pre-approved because this is a solo, one-weekend CLI MVP.

| Alternative | Benefit | Why rejected |
|---|---|---|
| SQLite-backed aggregation | Bounds some memory and enables later queries | Violates stateless operation; adds disk I/O, schema, cleanup, and slower setup |
| Multiprocess chunk aggregation | Potential CPU parallelism | Complicates stdin, deterministic parsing/errors, merge logic, and memory; profile the simple path first |
| Go implementation | Likely higher throughput and easier static distribution | Violates the approved Python 3.11/Click/Rich stack and slows one-weekend delivery |
| Hosted collector/dashboard | Retention and team-wide views | Violates privacy, $0, no-server, no-cloud, and CLI-only constraints |

## 12. Architecture Decision Record

### ADR-001: Local single-process streaming CLI

- **Status:** Accepted by product brief.
- **Decision:** Use one Python process and keep parser, aggregator, and renderers as separate modules.
- **Consequences:** Minimal operations and simple shell use; exact distinct-key summaries consume memory proportional to cardinality, so cardinality and performance behavior must be measured and surfaced honestly.
- **Review note:** The separate Devil's Advocate review is intentionally outside this session. No independent or adversarial review is claimed here.

## 13. Traceability

- Product scope and success criteria: `STRATEGIC_PLAN.md`.
- Behavioral priorities and acceptance criteria: `PRD.md`.
- Ordered delivery work: `IMPLEMENTATION_PLAN.md`.
- Per-step execution prompts: `CLAUDE_CODE_GUIDE.md`.

