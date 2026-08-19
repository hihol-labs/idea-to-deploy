# Project Architecture: nginx-log-insights

## Context and Decision

This is a Python 3.11 process invoked locally by an operator or shell pipeline.
The approved architecture is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because results are
computed for one invocation, retention is not a requirement, and persistence
would add I/O, lifecycle, and schema work without user value. An HTTP API is
incorrect because the consumer is a local engineer or Unix pipeline; a server
would add authentication, ports, deployment, and attack surface while violating
the $0, one-weekend scope.

The process reads one line at a time. It never loads the log file itself into
memory. Exact top counts and unique User-Agent share require cardinality-sized
maps/sets, so a configurable unique-key ceiling provides a deterministic memory
safety boundary and exit code 4 instead of an out-of-memory crash.

## Architecture Variants

The obvious single-process architecture is pre-approved. These are recorded as
decision context, not as an unresolved choice.

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** input iterator → parser → in-process aggregator → one renderer.
- **Pros:** least coordination overhead, pip-installable, deterministic, easy to test.
- **Cons:** one CPU core; exact unique counts consume memory proportional to cardinality.
- **Best for:** local analysis of individual logs under the declared bound.
- **Estimated complexity:** Low.

### Variant B: Multiprocess map/reduce

- **Approach:** split seekable files into chunks, aggregate in workers, merge results.
- **Pros:** may improve throughput on large seekable files.
- **Cons:** does not fit stdin naturally, complicates line boundaries and merging,
  adds memory/process overhead, and threatens weekend scope.
- **Best for:** a later measured CPU bottleneck on multi-gigabyte files.
- **Estimated complexity:** Medium.

### Variant C: External analytics platform

- **Approach:** ingest into GoAccess or an Elastic-style retained system.
- **Pros:** richer historical exploration and dashboards.
- **Cons:** setup, persistence, services, and operational cost; violates constraints.
- **Best for:** continuous retained analytics, which is out of scope.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because it directly satisfies local execution, stdin
streaming, pip installation, zero infrastructure, and one-weekend delivery.
Variants B and C require evidence and a new scope decision before adoption.

## Component Model

```text
file path or stdin
       │ text lines
       ▼
Input adapter ──I/O error──► diagnostic + exit 1
       │
       ▼
CombinedLogParser ──malformed──► invalid counter/warning
       │ AccessRecord
       ▼
StreamingAggregator ──unique limit──► diagnostic + exit 4
       │ Report dataclass
       ├────────────┬─────────────┐
       ▼            ▼             ▼
 Rich terminal   JSON encoder   CSV encoder
```

All components run synchronously in one process. Parsing and aggregation are
fused in the CLI loop to minimize allocation while remaining separable in unit
tests. Rendering begins only after EOF because exact rankings and percentages
require final totals.

## Package Structure

```text
pyproject.toml
src/nginx_log_insights/
  __init__.py          # package version only
  cli.py               # Click command, orchestration, exit mapping
  models.py            # AccessRecord, RankedItem, Report dataclasses
  parser.py            # precompiled combined-log parser
  aggregate.py         # StreamingAggregator and cardinality guard
  renderers/
    __init__.py
    terminal.py        # Rich tables and color policy
    json_output.py     # stable JSON document
    csv_output.py      # stable normalized CSV rows
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_output_contracts.py
  test_performance.py
```

The distribution uses a `src/` layout to prevent tests from importing an
uninstalled working-tree package accidentally.

## Data Contracts

There are no database tables, migrations, indexes, ORM models, or persistent
records. The template's database section is intentionally not applicable under
the approved stateless architecture. The complete in-memory dataclass contract
is:

| Dataclass | Field | Python type | Constraint |
|---|---|---|---|
| `AccessRecord` | `client_ip` | `str` | Non-empty parsed token; no DNS lookup |
|  | `timestamp` | timezone-aware `datetime` | Parsed from nginx `%d/%b/%Y:%H:%M:%S %z` |
|  | `method` | `str` | Request method token, may be `-` for malformed request field |
|  | `url` | `str` | Request target exactly as logged; no URL decoding |
|  | `status` | `int` | 100–599 |
|  | `user_agent` | `str` | Quoted combined-log field, including `-` if logged |
| `RankedItem` | `key` | `str` | IP or URL |
|  | `count` | `int` | Positive |
| `HourlyBucket` | `hour` | `int` | 0–23 in each record's logged numeric offset |
|  | `count` | `int` | Non-negative |
|  | `percentage` | `float` | 0–100; computed before serialization |
| `Report` | `total_valid_requests` | `int` | Positive for successful report |
|  | `invalid_lines` | `int` | Non-negative |
|  | `top_ips` | `tuple[RankedItem, ...]` | At most 10 |
|  | `top_error_urls` | `tuple[RankedItem, ...]` | At most 10, status 400–599 only |
|  | `hourly_distribution` | `tuple[HourlyBucket, ...]` | Exactly 24 ordered buckets |
|  | `unique_user_agents` | `int` | Exact distinct count within configured limit |
|  | `unique_user_agent_share` | `float` | `100 × unique_user_agents / total_valid_requests` |

Hourly request distribution is a percentage calculated with the literal
formula `100 × hourly_request_count / total_valid_requests`. It is not an
unscaled fraction. Empty hours have count `0` and percentage `0.0`. Percentages
are rounded only during rendering (two decimals), never in aggregation.

Ranking is deterministic: descending count, then ascending UTF-8 string key.
The error-URL ranking combines 4xx and 5xx observations by exact logged request
target. Query strings remain part of the target.

## Streaming and Resource Bounds

The aggregator keeps `Counter[str]` instances for IPs and error URLs, a
24-element integer list, and a `set[str]` for User-Agents. Before adding a new
distinct IP, error URL, or User-Agent, it checks a shared `--max-unique-keys`
budget (default 1,000,000 distinct keys across those collections). Crossing the
limit aborts without a partial report and maps to exit code 4. This explicit
bound reconciles exact results with predictable laptop memory; it does not make
the process persistent.

The hot path performs one line read, one parse, and constant-number dictionary
updates. The performance acceptance command generates its fixture outside the
timed interval and records wall time and peak RSS. The target is a representative
1 GB combined log in under 30 seconds on the documented reference laptop.

## CLI Interface

### Command

```text
nginx-log-insights [OPTIONS] [INPUT]
```

`INPUT` is a path to a UTF-8 nginx combined access log. If omitted or `-`, input
is read from standard input. Input is processed incrementally; seekability is
not required. The MVP does not follow growing files and does not accept gzip
implicitly.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit one JSON document to stdout; mutually exclusive with `--csv` |
| `--csv` | false | Emit normalized RFC 4180-style CSV to stdout; mutually exclusive with `--json` |
| `--max-unique-keys INTEGER` | `1000000` | Positive cardinality ceiling; exhaustion exits 4 |
| `--strict` | false | Abort with exit 3 on the first malformed non-empty line; otherwise skip and count it |
| `--no-color` | false | Disable color in terminal mode; ignored by JSON/CSV |
| `--version` | — | Print version and exit 0 |
| `--help` | — | Print usage and exit 0 |

Click rejects unknown options, non-positive limits, extra arguments, and the
`--json`/`--csv` combination as usage errors with exit 2.

### Inputs

The accepted grammar is nginx's standard combined log format, including the
quoted request, referrer, and User-Agent fields. Lines are decoded as UTF-8 with
replacement for undecodable bytes and trailing newline removal. A blank or
non-matching line is malformed. Non-strict mode writes a concise malformed-line
summary to stderr after processing; it never writes diagnostics to stdout.

### Outputs

Default output is Rich terminal text with a summary followed by top IPs, top
error URLs, 24 hourly buckets, and unique User-Agent count/share. Color is used
only when stdout is a TTY and `--no-color` is absent.

JSON has this stable top-level shape:

```json
{
  "total_valid_requests": 42,
  "invalid_lines": 1,
  "top_ips": [{"ip": "192.0.2.1", "count": 5}],
  "top_error_urls": [{"url": "/missing", "count": 3}],
  "hourly_distribution": [{"hour": 0, "count": 2, "percentage": 4.76}],
  "unique_user_agents": {"count": 7, "share_percentage": 16.67}
}
```

CSV always starts with
`section,rank,key,count,percentage`. Rows use sections `top_ip`,
`top_error_url`, `hour`, and `unique_user_agents`; inapplicable fields are empty.
Hours use zero-padded keys `00` through `23`, rank is empty for hour/summary
rows, and the UA row carries distinct count and share percentage. Machine
formats use UTF-8, decimal points, `\n` record endings, and no ANSI escapes.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Successful report, `--help`, or `--version` |
| `1` | Input/output failure, including unreadable input or stdout write failure |
| `2` | CLI usage or option/configuration error |
| `3` | Parse/validation failure: strict malformed line or no valid requests |
| `4` | Unique-cardinality exhaustion at `--max-unique-keys`; no partial report |

## Error Handling and Observability

Expected failures raise typed domain exceptions and are mapped once in
`cli.py`. Diagnostics include the input label and line number where useful but
never echo a complete log line, which may contain tokens or personal data.
There is no telemetry, network call, log upload, or retained state.

## Security and Privacy

Log content is untrusted data. The parser never evaluates escapes, invokes a
shell, resolves hostnames, or fetches URLs. Rich rendering treats fields as
plain text with markup disabled. JSON and CSV use standard-library encoders.
The tool does not authenticate because it exposes no service and relies on the
calling user's filesystem permissions. IPs and User-Agents may be personal
data; they remain local and disappear when the process exits.

## Packaging and Deployment

Deployment means building a pure-Python wheel and source distribution from
`pyproject.toml`, verifying both, and installing via pip into Python 3.11. The
console script maps `nginx-log-insights` to `nginx_log_insights.cli:main`.
Runtime dependencies are Click and Rich; dataclasses and CSV/JSON support come
from Python 3.11. No environment variables, `.env` file, Docker image,
`docker-compose.yml`, daemon, cloud target, or Kubernetes manifest exists.

## Architecture Decision Record (ADR)

### ADR-001: Single-process stateless CLI

- **Status:** Accepted (pre-approved product decision).
- **Decision:** Use Variant A and the literal constraint stated in Context and Decision.
- **Consequences:** Simple install and zero operations; throughput is single-core and exact cardinality is explicitly bounded.

### ADR-002: Exact metrics with an explicit cardinality ceiling

- **Status:** Accepted.
- **Decision:** Keep exact maps/sets until a shared unique-key ceiling is reached; then exit 4 without output.
- **Consequences:** Results are never approximate, but adversarial cardinality can terminate the run intentionally.

### ADR-003: One report model, three renderers

- **Status:** Accepted.
- **Decision:** Compute a renderer-neutral `Report`, then select terminal, JSON, or CSV.
- **Consequences:** Output contracts can be tested independently and pipeline output remains free of presentation markup.

### Alternatives considered and rejected

- GoAccess: good interactive analysis, but not the focused schema/CLI contract requested.
- Logstash/Elastic/Kibana: retained distributed analytics is disproportionate and violates constraints.
- AWStats: historical report workflow is not immediate pipeline-oriented triage.
- `grep`/`awk`: insufficiently robust as the installable, tested product contract.
- Multiprocessing: defer until a benchmark proves single-process parsing cannot meet the target.

No Devil's Advocate or independent adversarial review was performed in this
blueprint session; that review is deliberately external to this artifact set.

