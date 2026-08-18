# Project Architecture: Nginx Stream Insights

## Context and Goals

The system is a local Python 3.11 command-line program for DevOps/SRE users. It makes one streaming pass over nginx combined access logs, aggregates four summaries, and renders either colored terminal text or stable machine-readable output. The primary non-functional target is a representative 1 GB log in under 30 seconds on a documented laptop.

## Architecture Decision

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Both constraints are correct here. A database would add writes, schema lifecycle, disk amplification, and cleanup for a report that is fully derivable in one pass; it would also violate the $0, local, one-weekend operating model. An HTTP API would turn a bounded process into a long-running service requiring authentication, hardening, deployment, and concurrency semantics while adding no value to file/stdin analysis. The process boundary and stdout/stderr streams are the appropriate integration interface.

The approved architecture is a single process with a small internal module boundary: Click owns invocation, the parser yields dataclass records, the aggregator owns state, and renderers serialize one immutable report. This is the obvious architecture for a solo weekend CLI, so no artificial microservice or persistence variants are proposed.

## System Components

```text
file path(s) / stdin
        |
        v
 input iterator --> combined-log parser --> valid AccessRecord
                         |                       |
                         +--> malformed count    v
                                            Aggregator
                         (counters, exact sets, cardinality guard)
                                                  |
                                                  v
                                             Report dataclass
                                      / text / JSON / CSV /
                                     stdout; diagnostics -> stderr
```

| Module | Responsibility | Planned path |
|---|---|---|
| CLI | Validate options, select source/format, map exceptions to exit codes | `src/nginx_stream_insights/cli.py` |
| Input | Lazily open files or use stdin; never load a whole log | `src/nginx_stream_insights/input.py` |
| Parser | Parse documented combined format into an `AccessRecord` or malformed result | `src/nginx_stream_insights/parser.py` |
| Models | Dataclasses for records, ranked entries, distributions, report | `src/nginx_stream_insights/models.py` |
| Aggregator | Update counters/sets once per valid record; enforce cardinality limit | `src/nginx_stream_insights/aggregate.py` |
| Renderers | Text, JSON, and CSV implementations over the same report | `src/nginx_stream_insights/renderers/` |
| Errors | Typed domain failures and exit-code mapping | `src/nginx_stream_insights/errors.py` |

## CLI Interface

### Command

```text
nginx-stream-insights [OPTIONS] [INPUT...]
```

With no `INPUT`, the command reads stdin. One or more `INPUT` paths are processed in argument order as one logical stream. `-` denotes stdin and may appear at most once. The MVP accepts UTF-8-compatible nginx combined log lines; undecodable/malformed lines are counted as malformed rather than silently reinterpreted.

### Options

| Option | Contract |
|---|---|
| `--json` | Emit exactly one JSON report to stdout; mutually exclusive with `--csv` |
| `--csv` | Emit RFC 4180 long-form CSV to stdout; mutually exclusive with `--json` |
| `--no-color` | Disable color in default text mode; rejected as meaningless with JSON/CSV only if Click validation policy chooses strictness |
| `--cardinality-limit INTEGER` | Maximum distinct tracked values per exact-set/counter dimension; positive; default `1_000_000` |
| `--version` | Print package version and exit 0 |
| `--help` | Print usage and exit 0 |

### Inputs

Supported input records use nginx combined form:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

The parser needs the client IP string, timestamp including timezone, request target, integer status, and quoted User-Agent. It extracts the URL/request-target from the request field. `-` remains a legitimate missing-value marker. The process does not mutate input files.

### Outputs

- Text: Rich headings/tables on stdout; color only for a capable terminal and never in redirected output unless a future explicit force option is added.
- JSON: UTF-8 object with `schema_version`, `total_lines`, `total_valid_requests`, `malformed_lines`, `top_ips`, `top_error_urls`, `hourly_request_distribution`, and `unique_user_agents`.
- CSV: header `metric,key,count,percentage,rank`; rows identify `top_ip`, `top_error_url`, `hourly_request_distribution`, or `unique_user_agents`. Empty fields are blank, never overloaded.
- Diagnostics: concise failures go to stderr. Machine-readable stdout is never mixed with progress, color, or warnings.

Rankings are ordered by descending count and then lexicographic key; only ten rows are emitted. Hours use `00` through `23` and all 24 rows are emitted. Hourly request distribution is a percentage calculated as `100 × hourly_request_count / total_valid_requests`; if there are no valid requests, all hourly percentages are `0.0`.

`unique_user_agents` contains `count` and `share_percentage`. The share is `100 × distinct_nonempty_user_agent_count / total_valid_requests`, with `0.0` for no valid requests. This is the share of unique User-Agent values relative to valid requests, not the share of requests whose User-Agent is globally unique.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Report produced successfully; some malformed lines may have been counted |
| `1` | Runtime/internal processing failure not covered below |
| `2` | CLI usage or option validation error (Click convention) |
| `3` | Input failure: missing/unreadable file, stream read error, or no parseable records from non-empty input |
| `4` | Unique-cardinality exhaustion: a configured distinct-value limit was exceeded |

The complete public contract is `0/1/2/3/4`. Broken-pipe handling should exit quietly according to normal CLI pipeline behavior and must not emit a traceback.

## Domain and Data Model

No database tables exist. These in-memory dataclasses are the complete data model:

| Dataclass | Fields and types | Invariants |
|---|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `url: str`, `status: int`, `user_agent: str` | timezone-aware timestamp; status 100–599; nonempty IP/URL |
| `RankedCount` | `key: str`, `count: int`, `rank: int` | count > 0; rank 1–10 |
| `HourlyBucket` | `hour: int`, `count: int`, `percentage: float` | hour 0–23; percentage 0–100 |
| `UniqueUserAgents` | `count: int`, `share_percentage: float` | count >= 0; percentage 0–100 |
| `Report` | `schema_version: str`, totals, tuples of ranked counts/buckets, `unique_user_agents` | valid + malformed = total lines; deterministic ordering |

Mutable aggregation state consists of counters for IPs, error URLs, and 24 hours plus an exact set of nonempty User-Agent strings. Exact top-10 results require counts for each distinct IP/error URL; each distinct dimension is checked against `cardinality_limit` before insertion. Exceeding the limit raises a typed exhaustion error and maps to exit code 4.

## Parsing and Metric Semantics

- Every physical line increments `total_lines` once.
- A syntactically valid combined-format line with a valid timestamp/status increments `total_valid_requests` and all applicable metrics.
- Malformed lines increment `malformed_lines` and contribute to no denominator or ranking.
- Top IPs count all valid requests.
- Top error URLs count valid requests whose status is 400–599 inclusive.
- Request target parsing preserves query strings because the metric is specified as URL; normalization is out of scope.
- Hour is taken from nginx's parsed local timestamp, not converted to the machine timezone.
- User-Agent `-` or an empty quoted value is missing and excluded from the distinct count; the denominator remains all valid requests.

## API, Authentication, Database, and Deployment

- API endpoints: none. The exact integration surface is `## CLI Interface`.
- Authentication: none. The process inherits local filesystem permissions from the invoking user and opens no network listener.
- Database schema/migrations: none. State lives only for process lifetime.
- Containers/Kubernetes: none required or planned. A container would not improve the pip-installable local workflow.
- Deployment target: Python 3.11 environments on operator laptops and POSIX-like CI runners, installed into a virtual environment with pip.
- Environment variables: none required. Locale and terminal capability may influence Rich presentation only; JSON/CSV content remains deterministic.

## Performance and Resource Strategy

The input iterator and parser retain only the current line/record. Aggregation memory is proportional to distinct IPs, distinct error URLs, and distinct User-Agents, not total lines. The explicit cardinality limit converts adversarial growth into exit 4. The first implementation should use standard-library parsing/counters and profile before adding complexity.

The benchmark fixture and laptop specification must be recorded with file size, line count, storage type, CPU, OS, Python version, elapsed wall time, and peak RSS. Acceptance is wall time under 30 seconds for 1 GB, excluding fixture generation and pip installation. Performance tests must consume the same streaming path as production.

## Security and Privacy

Logs may contain personal data and secrets in URLs. The tool stays local, makes no network calls, writes only explicitly selected stdout/stderr, and does not persist raw records. Error messages expose paths only as necessary and never echo whole log lines by default. Formula/spreadsheet injection is mitigated in CSV keys beginning with `=`, `+`, `-`, or `@` by prefixing a single quote or by a documented equivalent safe serialization policy.

## Packaging and Planned Structure

```text
pyproject.toml
src/nginx_stream_insights/
  __init__.py
  cli.py
  input.py
  parser.py
  models.py
  aggregate.py
  errors.py
  renderers/{__init__,text,json,csv}.py
tests/{fixtures,unit,integration,performance}/
```

`pyproject.toml` exposes the `nginx-stream-insights` console script and declares Python `>=3.11,<4`, Click, and Rich. Runtime version metadata is read from the installed package.

## Architecture Decision Record (ADR)

### ADR-001: Single-process streaming CLI

- Status: accepted by the pre-approved project brief.
- Decision: one Python process with internal modules and no persistence or network boundary.
- Consequences: minimal operations and fast delivery; aggregation memory depends on distinct cardinality; horizontal scaling and historical querying are intentionally unavailable.
- Alternatives rejected: Go implementation (conflicts with approved stack), database-backed batch job (unneeded persistence), HTTP service/microservices (unneeded operations/auth), external observability stack (cost and scope).

### Review Boundary

No Devil's Advocate or independent review ran in this blueprint session. The external benchmark harness is responsible for running the repository's real `devils-advocate` agent in a fresh session and for producing any review artifact. This document therefore contains no simulated debate verdict.
