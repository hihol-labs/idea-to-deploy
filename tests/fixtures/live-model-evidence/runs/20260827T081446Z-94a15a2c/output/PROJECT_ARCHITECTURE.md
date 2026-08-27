# Project Architecture: nginx Stream Analytics CLI

## Architecture Goals and Constraints

The product is a local Python 3.11 command-line application. It must process a
representative 1 GB nginx access log in under 30 seconds on a documented
laptop, avoid loading the input in memory, produce identical metrics through
three renderers, and remain installable through pip.

The governing decision is **"no database — stateless streaming processing; no HTTP API — CLI-only tool"**.

Both constraints are correct here. A database would add writes, schema
management, retained sensitive data, and operating cost without helping a
one-shot report. An HTTP API would turn a local diagnostic into a service that
needs lifecycle management, security, and concurrency handling. Files and
stdin already provide the right ingress boundary; stdout/stderr and exit codes
provide the right automation boundary.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** one Python process reads buffered text lines, parses valid
  records, updates in-memory aggregates, freezes one report model, and renders
  it once.
- **Pros:** minimum operational surface; one-pass I/O; deterministic; easiest
  to package, profile, and test within a weekend.
- **Cons:** exact distinct-value maps grow with input cardinality; CPU work is
  limited to one process.
- **Best for:** local incident triage and pipeline use on laptop-sized logs.
- **Estimated complexity:** Low.

### Variant B: Multi-process partition and reduce (Rejected for MVP)

- **Approach:** split seekable files into byte ranges, aggregate in workers,
  then merge counters and distinct sets.
- **Pros:** can use multiple cores for large regular files.
- **Cons:** quoted-line and boundary handling is more complex; stdin cannot be
  partitioned; merging cardinality sets spikes memory; more failure modes.
- **Best for:** a later version after profiling proves parsing is CPU-bound.
- **Estimated complexity:** Medium.

### Variant C: External analytics stack (Rejected)

- **Approach:** ingest into GoAccess or Logstash/Elastic and query retained
  data.
- **Pros:** richer exploration and historical analysis.
- **Cons:** violates local stateless scope, the $0 operational target, and the
  no-database/no-server constraints.
- **Best for:** teams that already operate those systems and need retention.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the architecture is an obvious single-process
fit for a one-weekend, zero-budget CLI. Variants B and C are documented to
make the trade-off replayable, not to reopen the approved decision.

## System Context and Data Flow

```text
nginx file or stdin
        |
        v
 buffered UTF-8 reader
        |
        v
 common/combined parser ---- malformed line counter / strict failure
        |
        v
 Aggregator
  | top-IP counts
  | error-URL counts (status 400..599)
  | 24 hourly counts
  | exact normalized User-Agent set with cardinality guard
        |
        v
 immutable Report dataclass
    /          |          \
 Rich text   JSON         CSV
 stdout      stdout       stdout
```

Parsing and aggregation happen per line. Rendering begins only after EOF so
rankings, totals, and percentages are final. Diagnostics go to stderr and
machine-readable reports remain clean on stdout.

## Component Boundaries and Planned Files

| Planned path | Responsibility | May depend on |
|---|---|---|
| `src/nginx_stream_analytics/cli.py` | Click command, option validation, error-to-exit mapping | input, pipeline, renderers |
| `src/nginx_stream_analytics/models.py` | Frozen `AccessRecord`, ranked item, and `Report` dataclasses | standard library only |
| `src/nginx_stream_analytics/parser.py` | Parse supported nginx common/combined lines | models, parsing errors |
| `src/nginx_stream_analytics/input.py` | Open file or stdin with buffered UTF-8 decoding | standard library only |
| `src/nginx_stream_analytics/aggregate.py` | Mutable one-pass counters and report finalization | models, domain errors |
| `src/nginx_stream_analytics/render/text.py` | Rich terminal report | models, Rich |
| `src/nginx_stream_analytics/render/json.py` | Stable JSON document | models, standard library |
| `src/nginx_stream_analytics/render/csv.py` | Stable long-form CSV rows | models, standard library |
| `src/nginx_stream_analytics/errors.py` | Typed domain failures and exit-code mapping | standard library only |

The parser knows syntax, the aggregator knows metric semantics, and renderers
know presentation. Renderers never recompute metrics.

## Data Model and Metric Semantics

`AccessRecord` contains `ip: str`, `timestamp: datetime`, `request_target: str`,
`status: int`, and `user_agent: str | None`. The parser accepts nginx common
and combined access-log lines. The request target is the raw target token from
the quoted request field; it includes the path and query string and excludes
the HTTP method and protocol. A missing combined-format User-Agent is
normalized to no value, while `"-"` is also treated as missing.

`Report` contains:

- `total_lines`, `total_valid_requests`, and `invalid_lines`;
- at most ten `(ip, request_count)` entries ordered by count descending, then
  IP string ascending;
- at most ten `(url, error_count)` entries for statuses 400 through 599,
  ordered by count descending, then URL ascending;
- all 24 hours, `00` through `23`, with request count and percentage;
- `unique_user_agent_count`, `requests_with_user_agent`, and
  `unique_user_agent_share_percent`.

Hourly request distribution is a percentage, calculated for each hour with
the literal formula `100 × hourly_request_count / total_valid_requests`. For
zero valid requests, every hourly percentage is `0.0`; otherwise percentages
are calculated from integer counts and serialized with stable decimal
rounding.

The unique User-Agent share is
`100 × unique_normalized_user_agent_count / total_valid_requests`. The
denominator deliberately includes valid requests with a missing User-Agent so
the metric remains comparable across common and combined logs. The value is
`0.0` when there are no valid requests.

## State, Storage, Database, API, Authentication, and Deployment

There are no database tables, migrations, retained files, caches, or remote
stores. Runtime state consists only of counters, 24 hourly buckets, distinct
keys needed for exact rankings, and the guarded User-Agent set. It disappears
when the process exits. This is stateless with respect to executions even
though bounded-lifetime in-memory aggregation occurs during one execution.

There are no HTTP endpoints, request/response bodies, ports, API credentials,
sessions, users, or authentication flow. Local operating-system file access is
the trust boundary. The process never sends log content over a network.

Deployment means building a wheel/sdist and installing it into a Python 3.11
environment with pip. Docker, Docker Compose, cloud resources, servers, and
Kubernetes are intentionally absent. No environment variables are required;
locale and terminal capability are read only through standard runtime APIs.

## CLI Interface

### Commands

The package exposes one console command:

```text
nginx-log-report [OPTIONS] INPUT
```

`INPUT` is a path to a regular readable access-log file or `-` for stdin.
Exactly one report is emitted per invocation. `--help` and `--version` are
standard Click eager options.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit one UTF-8 JSON object; mutually exclusive with `--csv` |
| `--csv` | false | Emit UTF-8 CSV with a header; mutually exclusive with `--json` |
| `--strict` | false | Stop on the first malformed non-empty line; otherwise count and skip it |
| `--encoding TEXT` | `utf-8` | Input decoding; invalid codec names are usage errors |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive safety cap for the exact User-Agent set |
| `--color / --no-color` | auto | Force or disable color for terminal text; ignored by machine formats |
| `--version` | n/a | Print version and exit 0 |
| `--help` | n/a | Print usage and exit 0 |

### Inputs

Files are opened read-only and iterated with buffering. Stdin is never closed
by the application. Lines are decoded using the chosen encoding. Empty lines
are malformed input lines. The MVP supports conventional nginx common and
combined formats; custom `log_format` layouts and compressed files are not
accepted directly.

### Outputs

Default terminal text uses Rich tables and color only when enabled. It shows
the input summary, both top-10 lists, all 24 hourly buckets, and User-Agent
counts/share. When stdout is not a TTY, automatic color is disabled.

JSON uses this stable top-level shape:

```json
{
  "summary": {"total_lines": 0, "total_valid_requests": 0, "invalid_lines": 0},
  "top_ips": [],
  "top_error_urls": [],
  "hourly_distribution": [],
  "user_agents": {"unique_count": 0, "requests_with_user_agent": 0, "share_percent": 0.0}
}
```

CSV uses long-form columns `metric,rank,key,count,percentage`. Summary rows,
ranked IP and URL rows, 24 hourly rows, and User-Agent rows share that schema.
Values requiring CSV quoting are quoted by the standard library. JSON and CSV
never contain ANSI escape sequences. A final newline is emitted in all modes.

Warnings and failures go to stderr. Non-strict malformed-line summaries go to
stderr so stdout remains a composable report stream.

### Exit Codes

| Code | Meaning |
|---:|---|
| 0 | Success, including a valid empty report after zero valid requests |
| 1 | Runtime or unexpected internal processing failure |
| 2 | CLI usage error, including invalid or conflicting options |
| 3 | Input failure: missing/unreadable file, decoding failure, or strict malformed line |
| 4 | Unique-cardinality exhaustion: adding another normalized User-Agent would exceed the configured cap |

No partial report is written after a failure. Diagnostics identify the input
and line number when available without echoing the entire access-log line.

## Performance and Resource Design

Input bytes are read once, and output is proportional to the fixed report
shape. Aggregate updates are amortized O(1) per valid line. Final top-10
selection uses `heapq.nsmallest`/`nlargest`-style bounded selection or an
equivalent deterministic ordering without sorting full lists when profiling
shows a benefit.

Memory is independent of input byte size but proportional to exact distinct IP
and error-URL keys plus the guarded User-Agent cardinality. The 1 GB target is
accepted only against a representative generated fixture whose distribution,
Python version, CPU, storage, elapsed time, and peak RSS are recorded. The
pipeline must not retain raw lines or parsed records after aggregation.

Rich is not used in the hot loop. Timestamp parsing extracts the hour without
constructing more objects than correctness requires. Optimizations are adopted
only after `cProfile` or equivalent measurements identify a bottleneck.

## Failure, Safety, and Privacy

- Files are opened read-only; no source log is modified.
- Log fields are untrusted data and are never evaluated or interpolated into a
  shell command.
- Terminal rendering escapes or safely prints control characters so a crafted
  URL or User-Agent cannot inject terminal control sequences.
- JSON and CSV use standard encoders.
- No telemetry, network call, or persistent copy of log data exists.
- Keyboard interruption produces an error diagnostic and nonzero runtime exit,
  without a partial report.

## Testing and Observability

Unit fixtures cover common/combined formats, IPv4/IPv6, query strings, escaped
quotes, boundary statuses 399/400/499/500/599/600, all hours, ties, missing
User-Agents, malformed lines, and zero valid requests. Integration tests invoke
the installed Click command for file and stdin input in all renderers and
assert stdout, stderr, and exit codes.

Observability is local and opt-in: `--verbose` is deliberately deferred, so
the MVP reports only actionable warnings and errors. The performance harness
records elapsed time and peak RSS outside the product process.

## Architecture Decision Records

### ADR-001: Single process, one pass

- **Status:** Accepted and pre-approved.
- **Decision:** Use Variant A.
- **Reason:** It meets the local CLI boundary and minimizes delivery and
  operational risk.
- **Consequence:** Parallel parsing is deferred unless evidence shows it is
  necessary.

### ADR-002: Exact metrics with explicit cardinality failure

- **Status:** Accepted.
- **Decision:** Keep exact User-Agent distinctness up to a configurable cap;
  fail with code 4 instead of silently approximating.
- **Reason:** Pipeline consumers must know whether the reported share is exact.
- **Consequence:** Highly adversarial cardinality may stop the run rather than
  produce a misleading report.

### ADR-003: One report model, three renderers

- **Status:** Accepted.
- **Decision:** Freeze metric semantics in dataclasses before rendering.
- **Reason:** Terminal, JSON, and CSV must not disagree.
- **Consequence:** Renderer tests can share one canonical report fixture.

The adversarial architecture review is intentionally not recorded here. It is
owned by the external fresh-session harness and may produce its own artifact
after this blueprint session.

