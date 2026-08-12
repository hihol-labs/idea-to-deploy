# Project Architecture: Nginx Stream Insights

## 1. Context and Constraints

The product is a local Python 3.11 command-line application for DevOps and SRE users. It consumes nginx combined access logs, performs one-pass exact aggregation, and writes one report. The architectural decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add installation, storage lifecycle, schema, privacy, and cleanup burdens to a tool whose complete value is produced during one invocation; retaining input or aggregates is not a requirement. An HTTP API would turn a local command into an operated service with networking, authentication, availability, and deployment concerns while adding no value to file/stdin pipelines. Local stdin/files and stdout/stderr already form the correct integration boundaries.

Hard constraints:

- Python 3.11, Click, Rich, and dataclasses; pip-installable.
- One process and one pass over decoded input.
- No authentication, database, HTTP API, server, cloud, Docker requirement, or Kubernetes.
- $0 cash and infrastructure budget; one-weekend delivery.
- Target: process a representative 1 GB access log in under 30 seconds on a documented laptop.

## 2. Architecture Variants

### Variant A: Single-process streaming CLI (selected)

- **Approach:** one Click process reads lines, parses records, updates bounded in-memory aggregates, then renders once.
- **Pros:** simplest installation and debugging; works with stdin; no coordination or serialization overhead; deterministic errors.
- **Cons:** one CPU core; exact distinct-key maps remain memory-sensitive and require a cardinality ceiling.
- **Best for:** the approved local, one-weekend MVP.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunk analysis

- **Approach:** seekable files are partitioned and worker aggregates are merged.
- **Pros:** may use multiple cores for very large regular files.
- **Cons:** stdin cannot be partitioned naturally; line-boundary handling, merge memory, process startup, and deterministic diagnostics complicate the product.
- **Best for:** a later version whose measured CPU profile proves parallel parsing is necessary.
- **Estimated complexity:** Medium.

### Variant C: External analytics pipeline

- **Approach:** ingest into GoAccess or Logstash/Elastic and query stored results.
- **Pros:** broader querying, dashboards, and history.
- **Cons:** violates the no-database/no-server constraints, costs operational time, and is oversized for four fixed metrics.
- **Best for:** teams that require retained history and interactive analytics rather than this product.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the product decisions and single-process architecture are pre-approved, it serves both files and stdin, and it is the only variant consistent with the weekend scope and zero infrastructure budget. Variants B and C are recorded to make the trade-off replayable, not to reopen the decision.

## 3. System Shape and Data Flow

```text
file(s) or stdin
       |
       v
InputSource (binary buffering + strict line decoding)
       |
       v
CombinedLogParser ---- malformed-line count/diagnostic sample
       |
       v
AccessRecord dataclass
       |
       v
StreamingAggregator
  |        |            |                 |
IP counts  error URLs   hour[24] counts   User-Agent distinct set
  \________|____________|_________________/
                       |
                       v
                  Report dataclass
                       |
           +-----------+-----------+
           v           v           v
       Rich text      JSON     normalized CSV
           \___________|___________/
                       |
                  stdout; diagnostics -> stderr
```

Only the compact parsed fields needed by the aggregators survive each iteration. Raw lines and `AccessRecord` instances become collectible immediately. Rendering begins after input is exhausted so top-10 ordering and percentages are final.

## 4. Component and File Boundaries

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Python 3.11 constraint, dependencies, package metadata, `nginx-insight` entry point |
| `src/nginx_insight/cli.py` | Click command, option validation, exception-to-exit-code mapping |
| `src/nginx_insight/models.py` | Frozen/slotted `AccessRecord`, report row, and report dataclasses |
| `src/nginx_insight/input.py` | Ordered file/stdin opening, buffering, decoding, source diagnostics |
| `src/nginx_insight/parser.py` | Parse supported nginx combined log grammar into required fields |
| `src/nginx_insight/aggregate.py` | Exact counters, top-10 ranking, percentages, cardinality enforcement |
| `src/nginx_insight/render_text.py` | Rich terminal tables and summaries |
| `src/nginx_insight/render_json.py` | Stable JSON object serialization |
| `src/nginx_insight/render_csv.py` | Stable normalized CSV row serialization |
| `src/nginx_insight/errors.py` | Typed domain failures associated with exit codes 1, 3, and 4 |
| `tests/` | Unit, golden, CLI integration, and performance-contract tests |

Dependencies point inward: `cli` composes input, parser, aggregation, and one renderer; renderers depend only on report models; the parser and aggregator do not import Click or Rich.

## 5. Input and Parsing Contract

The MVP supports nginx's combined log shape:

```text
remote_addr remote_user time_local "request" status body_bytes_sent "http_referer" "http_user_agent"
```

Required parsed fields are client IP text, timestamp including numeric offset, request target, integer status, and User-Agent text. The request target is extracted from `METHOD TARGET PROTOCOL`; an unparsable request field makes that line invalid. URL ranking uses the target exactly as logged, including its query string, with no decoding or normalization.

- Inputs are processed in argument order; `-` denotes stdin, and stdin is the default when no input is named.
- Lines are decoded as UTF-8 by default. A fatal decode or read error is an input/data failure.
- Blank and malformed lines are skipped and counted. A bounded sample of diagnostics is written to stderr, never stdout.
- If at least one record is valid, malformed lines do not change a successful exit code. If zero records are valid, the command exits 3.
- Timestamp hour is the `00`–`23` wall-clock hour encoded in each record's `time_local`; offsets are not normalized, matching how operators read a server's log. This behavior is explicit for mixed-offset inputs.
- Statuses `400`–`599` contribute to the error-URL ranking; other statuses do not.

## 6. Aggregation and Resource Contract

The streaming state is:

- `ip_counts: dict[str, int]`
- `error_url_counts: dict[str, int]`
- `hour_counts: list[int]` of length 24
- `user_agents: set[str]`
- scalar `total_valid_requests` and `invalid_line_count`

Top lists are ordered by descending count and then ascending UTF-8/Unicode string value for deterministic ties. Each list contains at most 10 entries.

Hourly percentage for hour `h` is exactly `100 × hourly_request_count / total_valid_requests`. All 24 hours appear in machine formats, including zero-count hours. Percentages are computed from integer counts at report time and serialized without changing the underlying counts.

Unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`. An empty or `-` User-Agent is still a literal observed value in a syntactically valid combined-log line. The report includes both the numerator and denominator so consumers need not reverse a rounded percentage.

### Cardinality guard

`--max-unique N` defaults to `1_000_000` and applies independently to `ip_counts`, `error_url_counts`, and `user_agents`. Updating an existing key is always allowed. Before inserting a new key, the owning collection's size is checked; exceeding the limit aborts without emitting a partial report, identifies the exhausted dimension on stderr, and exits 4. `N` must be positive; invalid values are usage errors (exit 2).

This is an exact, bounded strategy. The MVP does not silently sample, truncate, evict, or substitute approximate cardinality algorithms.

## CLI Interface

### Command

```text
nginx-insight [OPTIONS] [INPUT]...
```

### Options

| Option | Contract |
|---|---|
| `--json` | Emit one UTF-8 JSON object; mutually exclusive with `--csv` |
| `--csv` | Emit normalized RFC 4180-compatible CSV; mutually exclusive with `--json` |
| `--max-unique INTEGER` | Positive per-dimension distinct-key ceiling; default `1000000` |
| `--encoding TEXT` | Input encoding; default `utf-8` |
| `--color` / `--no-color` | Override automatic color detection for text only |
| `--version` | Print version and exit 0 |
| `--help` | Print help and exit 0 |

The top-list size is fixed at 10 in the MVP. Output mode defaults to text. Text color is enabled only for an interactive terminal unless `--color` is explicit; `NO_COLOR` and `--no-color` disable it. JSON and CSV never contain ANSI escapes. All report data goes to stdout and all diagnostics go to stderr.

### Inputs

- Zero `INPUT` arguments: read stdin.
- One or more paths: read each regular file sequentially in the given order.
- `-`: read stdin at that position; it may appear at most once.
- Directories and unavailable/unreadable inputs are rejected as input failures.
- Gzip input is post-MVP (`Should`), not inferred by the MVP.

### Outputs

Text output has four labeled sections plus totals: top client IPs, top error URLs, hourly distribution, and User-Agent uniqueness. Rich tables use color only as described above.

JSON uses this stable top-level shape:

```json
{
  "schema_version": 1,
  "total_valid_requests": 0,
  "invalid_line_count": 0,
  "top_ips": [{"ip": "string", "count": 0}],
  "top_error_urls": [{"url": "string", "count": 0}],
  "hourly_distribution": [{"hour": 0, "count": 0, "percentage": 0.0}],
  "user_agents": {"unique_count": 0, "share_percentage": 0.0}
}
```

CSV begins with `metric,key,count,percentage`. Rows use `top_ip`, `top_error_url`, `hour`, and `unique_user_agents` as the metric discriminator. `key` is the IP, URL, zero-padded hour, or `unique`; percentage is blank where not applicable. CSV quoting is delegated to Python's CSV library.

### Exit codes

| Code | Meaning | Examples |
|---:|---|---|
| `0` | Success or informational command | Report emitted, `--help`, `--version` |
| `1` | Unexpected runtime or output failure | Broken internal invariant, renderer failure other than normal closed-pipe handling |
| `2` | CLI usage/configuration error | Unknown option, `--json` with `--csv`, non-positive `--max-unique`, repeated `-` |
| `3` | Input or data failure | Unreadable file, fatal decoding/read error, or zero valid records |
| `4` | Unique-cardinality exhaustion | A new IP, error URL, or User-Agent would exceed `--max-unique` |

A normal downstream closed pipe is handled quietly according to conventional CLI behavior and must not produce a traceback.

## 8. Error Handling and Observability

- Domain exceptions carry safe context such as source name and line number, never the full log line by default.
- At most the first five malformed-line diagnostics are printed; the final invalid count remains in successful reports.
- Expected failures produce a concise stderr message with no traceback. Unexpected failures exit 1; development diagnostics may enable tracebacks through test-only configuration, not a public MVP option.
- No telemetry, network calls, input retention, or hidden files are produced.

## 9. Security and Privacy

Log content is untrusted data. The parser never evaluates fields, invokes a shell, follows URLs, or interprets ANSI control sequences. Rich rendering must escape or sanitize control markup from IP, URL, and User-Agent values. JSON and CSV use standard-library encoders. Input paths are those explicitly supplied by the caller; the tool does not recursively discover files or follow application-level includes.

Processing remains local. No log line or aggregate leaves the process through a network interface. No authentication is needed because there is no server or shared state; operating-system file permissions define access.

## 10. Packaging and Runtime

`pyproject.toml` declares Python `>=3.11,<4`, runtime dependencies on compatible Click and Rich versions, and a console script entry point. A wheel and source distribution are the deployable artifacts. The supported execution environment is a local POSIX-like terminal with Python 3.11; portability tests should also run on major desktop CI runners if publication is pursued.

There are no environment variables required for operation, no `.env` file, no Docker Compose topology, no service port, and no deployment target beyond the user's Python environment. `NO_COLOR` is honored as a standard presentation signal, not application configuration.

## 11. Performance Design

- Read through buffered binary streams and decode line by line; never call `read()` for the whole file.
- Compile any parsing pattern once and keep the grammar linear; benchmark a manual parser if profiling identifies regex cost.
- Store only aggregation keys and integer counts, not records or raw lines.
- Render only after aggregation; keep Rich out of the hot path.
- Measure the 1 GB target with a deterministic generator or declared fixture, Python 3.11 version, hardware profile, wall-clock command, and peak RSS.
- Treat `--max-unique` as the safety boundary, not as proof of a fixed byte limit. The benchmark must include representative and high-cardinality shapes.

## 12. Architecture Decision Record (ADR)

### ADR-001: Local stateless CLI

**Status:** Accepted (pre-approved).

**Decision:** Use Variant A and the literal constraint **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

**Consequences:** setup and privacy risk are minimal, stdin pipelines are first-class, and historical querying is out of scope. Exact high-cardinality analysis must be guarded in memory.

### Self-Critique of the Architecture

This benchmark has no independent reviewer or subagent transport. The following is a deliberately adversarial **self-critique**, not an independent or Devil's Advocate agent review.

**Verdict:** APPROVE WITH CONDITIONS.

1. **Exact dictionaries can consume substantial memory before one million distinct values.** Resolution: make the limit user-visible, apply it independently per dimension, benchmark peak RSS at representative cardinality, and never promise constant memory.
2. **A 30-second Python target may be hardware- and log-shape-sensitive.** Resolution: bind acceptance evidence to a documented laptop, fixture, interpreter, elapsed time, and RSS; profile the parser before adding parallelism.
3. **Combined-log parsing has escaping and malformed-request edge cases.** Resolution: define the grammar, use golden fixtures for escaped quotes and invalid records, and fail with code 3 when no valid records remain.
4. **Mixed timestamp offsets make an hourly histogram semantically ambiguous.** Resolution: aggregate the wall-clock hour as logged and state that decision in every user-facing contract; timezone normalization is out of scope.
5. **A normalized multi-metric CSV is less intuitive than separate files.** Resolution: use a stable discriminator schema and preserve JSON as the richer pipeline format.
6. **Terminal control characters in log fields could spoof output.** Resolution: escape Rich markup and control sequences and test hostile values.

**Alternatives considered and rejected:** multiprocessing is deferred until profiling proves it necessary because it complicates stdin and merging; approximate sketches are rejected for MVP because required results are exact; persistence and an API are rejected because they contradict the local stateless product.

## 13. Traceability

- Product priorities and success measures: `STRATEGIC_PLAN.md`.
- User behavior and acceptance criteria: `PRD.md`.
- Ordered build work and verification: `IMPLEMENTATION_PLAN.md`.
- Step prompts for an implementation agent: `CLAUDE_CODE_GUIDE.md`.
- Persistent project instructions: `CLAUDE.md`.
