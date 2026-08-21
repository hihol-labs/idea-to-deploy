# Project Architecture: Nginx Stream Insights

## Context and Quality Drivers

The product is a local Python 3.11 CLI that analyzes nginx combined access
logs in one pass. Its drivers are correctness on quoted log fields,
deterministic machine output, local data handling, installation through pip,
and processing 1 GB in under 30 seconds on a documented reference laptop.
There is no authentication boundary because there is no network service or
multi-user state.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended)

- **Approach:** one process performs read → parse → aggregate → report → render.
- **Pros:** minimal startup and serialization cost, easy pip installation,
  deterministic behavior, direct stdin support.
- **Cons:** one CPU-bound parsing path; exact distinct User-Agents consume
  memory proportional to their cardinality until the configured guard fires.
- **Best for:** local finite logs and shell pipelines within the stated target.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunk parsing

- **Approach:** partition seekable files, parse chunks in workers, merge
  partial counters in a coordinator.
- **Pros:** can use multiple CPU cores on large regular files.
- **Cons:** does not naturally support stdin/follow mode, makes record-boundary
  handling and deterministic failure semantics harder, and adds merge memory.
- **Best for:** multi-gigabyte seekable batch files after measurement proves a
  single process insufficient.
- **Estimated complexity:** Medium.

### Variant C: Persistent analytics service

- **Approach:** ingest logs into a database and query through an HTTP service.
- **Pros:** historical queries and multi-user dashboards.
- **Cons:** violates local/stateless/$0 constraints and adds authentication,
  deployment, retention, and operational burdens.
- **Best for:** a different centralized-observability product.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the architecture choice is pre-approved and
fits finite local analysis, pipeline use, a one-weekend budget, and the stated
performance goal. Variant B remains a measurement-triggered future option;
Variant C is out of scope.

## Architecture Decision Record

### ADR-001: Process and interface boundary

**Decision:** **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would retain sensitive access
logs, add schema/migration/storage operations, and provide no value for a
report computed once from a stream. An HTTP API would require a server,
network security, authentication, lifecycle management, and a serialization
hop even though the users and inputs are already in a shell. A single local
process minimizes moving parts and keeps log data on the user's machine.

**Consequences:** there are no database tables, migrations, indexes, API
endpoints, request/response bodies, authentication flow, Docker services, or
cloud deployment target. The deployment artifact is a Python wheel installed
with pip. Per-key counters and the exact User-Agent set exist only for the
duration of the process.

**Review status:** the separately requested adversarial review is outside this
session and is not represented in this document.

### ADR-002: Exactness and cardinality failure

Top-IP and error-URL counts are exact. The unique User-Agent share is also
exact, defined as `100 × distinct_nonempty_user_agents / total_valid_requests`.
The process stops before inserting a User-Agent beyond
`--max-unique-user-agents` and exits 4. It must not silently substitute an
approximation or emit a success report labeled exact.

### ADR-003: One report model, three renderers

Aggregation produces a renderer-neutral `Report` dataclass. Terminal, JSON,
and CSV renderers consume only that report. This prevents output modes from
recomputing metrics differently.

## Component Design

```text
file path / stdin / followed file
              |
              v
        streaming line reader
              |
              v
 combined-log parser --> malformed-line counter + diagnostics
              |
              v
          Aggregator
   IP Counter | error-URL Counter
   24 hourly counts | exact UA set
              |
              v
        Report dataclass
       /        |        \
 Rich terminal JSON      CSV
```

| Component | Planned path | Responsibility |
|---|---|---|
| Click entry point | `src/nginx_stream_insights/cli.py` | Validate options, choose input/output, map typed failures to exit codes |
| Reader | `src/nginx_stream_insights/input.py` | Yield text lines from stdin, a file, or follow mode without retaining the file |
| Parser | `src/nginx_stream_insights/parser.py` | Parse the supported nginx combined grammar into `AccessRecord` |
| Models | `src/nginx_stream_insights/models.py` | `AccessRecord`, ranked item, hourly bucket, and `Report` dataclasses |
| Aggregator | `src/nginx_stream_insights/aggregate.py` | Maintain counters, exact UA set, totals, and finalize deterministic top 10 lists |
| Renderers | `src/nginx_stream_insights/renderers/{terminal,json_output,csv_output}.py` | Serialize the shared report contract |
| Errors | `src/nginx_stream_insights/errors.py` | Typed input, parse/data, output, and cardinality exceptions |

## Data and Streaming Model

The supported record grammar is nginx's conventional combined format:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

`AccessRecord` contains `ip: str`, `timestamp: datetime` with its parsed numeric
offset, `method: str`, `url: str`, `protocol: str`, `status: int`, and
`user_agent: str`. A syntactically valid line increments
`total_valid_requests`; a malformed line increments `malformed_lines` and is
excluded from every metric. Request target parsing preserves the target token
as logged; no URL decoding or query-string removal occurs in the MVP.

The aggregator maintains:

- `Counter[str]` for all valid request IPs;
- `Counter[str]` for URL targets only when `400 <= status <= 599`;
- a fixed list of 24 integer hourly counts using the hour in each timestamp's
  logged numeric offset;
- `set[str]` for non-empty User-Agent values, guarded by the configured limit;
- scalar counts for valid and malformed lines.

Top lists sort by descending count, then ascending UTF-8 string value for a
stable tie-break. Hourly request distribution includes all 24 buckets and is
the percentage `100 × hourly_request_count / total_valid_requests`. When the
valid total is zero, no report is emitted and exit code 3 is returned. The
unique User-Agent share is
`100 × distinct_nonempty_user_agents / total_valid_requests`.

Streaming means input lines and parsed records are discarded after their
counts are applied. Memory is therefore independent of file size but remains
proportional to distinct IPs, distinct error URLs, and distinct User-Agents;
only the User-Agent dimension has an explicit MVP exhaustion guard.

## CLI Interface

### Command and inputs

```text
nginx-insights [OPTIONS] [INPUT]
```

`INPUT` is an optional nginx combined-format log path. Omitted input or `-`
reads UTF-8 text from stdin. `--follow` requires a regular file path, begins at
its current start by default, waits for appended complete lines, and runs until
interrupted; machine reports are written only on clean termination. Input is
decoded as UTF-8 with invalid byte sequences treated as malformed input lines.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit exactly one JSON document; mutually exclusive with `--csv` |
| `--csv` | false | Emit one RFC 4180 CSV stream; mutually exclusive with `--json` |
| `--follow` / `-f` | false | Continue reading appended lines; invalid with stdin |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive maximum distinct non-empty UAs before exit 4 |
| `--color` / `--no-color` | auto | Force/disable Rich color; auto enables only on a TTY and never for JSON/CSV |
| `--version` | n/a | Print version and exit 0 |
| `--help` | n/a | Print help and exit 0 |

### Outputs

Default terminal output contains four labeled Rich tables/summary blocks and
a malformed-line warning on stderr when needed. Normal data goes to stdout;
diagnostics go to stderr. JSON and CSV contain no ANSI escape sequences.

The JSON document has this versioned shape:

```json
{
  "schema_version": 1,
  "total_valid_requests": 0,
  "malformed_lines": 0,
  "top_ips": [{"rank": 1, "ip": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"rank": 1, "url": "/missing", "count": 1}],
  "hourly_distribution": [{"hour": "00", "count": 0, "percentage": 0.0}],
  "unique_user_agents": {"count": 0, "share_percentage": 0.0}
}
```

All 24 hourly objects are emitted. Percentages are JSON numbers rounded to six
decimal places for presentation; calculations use unrounded counts.

CSV uses the header
`metric,rank,key,count,percentage`. It emits ranked `top_ip` and
`top_error_url` rows, 24 `hourly_distribution` rows (`key` is `00`–`23`), and
one `unique_user_agents` row. Empty cells are blank, not invented zero values.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Successful report, or successful `--help`/`--version` |
| `1` | Input/output operating error, such as unreadable input or broken output destination |
| `2` | Click usage error or invalid option combination |
| `3` | Data error: the finite input contains no valid records |
| `4` | Unique-cardinality exhaustion: another distinct User-Agent would exceed the configured maximum |

On codes 1–4, diagnostics go to stderr and no complete machine report is
claimed. SIGINT during follow mode follows Click's interruption behavior and
does not remap the documented application codes.

## Packaging and Deployment

The repository uses a `src/` package layout and a PEP 517 `pyproject.toml`.
The wheel exposes `nginx-insights = nginx_stream_insights.cli:main`. Supported
deployment is `python3.11 -m pip install nginx-stream-insights` into a virtual
environment or isolated tool installer. There is no Docker, daemon, HTTP
listener, cloud resource, or Kubernetes manifest.

Runtime environment variables are intentionally absent. Locale must not
change JSON/CSV keys, decimal punctuation, ranking, or hour labels.

## Performance Strategy

- Read through a buffered text stream and process each line once.
- Compile parser patterns once; avoid `split()` strategies that break quoted
  fields.
- Do not retain raw lines or `AccessRecord` instances after aggregation.
- Use `Counter.most_common` only at finalization, with explicit deterministic
  tie handling.
- Benchmark a representative 1 GB fixture from a warm local filesystem with
  `/usr/bin/time`, recording CPU, wall time, peak RSS, Python version, CPU, and
  storage.
- Profile before considering Variant B. The acceptance target is under 30
  seconds, not architectural parallelism for its own sake.

## Security and Privacy

Access logs can contain personal data, tokens in query strings, and internal
paths. The CLI never transmits or persists input. Diagnostics must include line
numbers and reasons but not echo full raw log lines. Terminal escaping must be
handled by Rich; JSON and CSV use standard-library serializers. No shell is
invoked with user-controlled values. Package dependencies are pinned through
normal project lock/release practices and scanned before release.

## Test Architecture

- Parser unit fixtures cover spaces and escapes in quoted fields, IPv4/IPv6,
  time-zone offsets, malformed timestamps/statuses, and empty User-Agents.
- Aggregator tests cover 4xx/5xx boundaries, stable ties, fewer than 10 keys,
  24-hour totals, the literal percentage formula, and the UA limit boundary.
- CLI integration tests cover file/stdin, mutual exclusions, stderr/stdout,
  ANSI behavior, and every exit code `0/1/2/3/4`.
- Golden tests validate JSON schema and parsed CSV semantics rather than
  platform-specific terminal width.
- A generated high-cardinality fixture proves exit 4 without allocating past
  the configured limit.
- A local 1 GB benchmark supplies performance evidence; it is not a routine
  unit-test fixture.

## Architectural Boundaries and Deferred Work

Custom `log_format` parsing, gzip-aware input, approximate cardinality,
distributed processing, persistence, dashboards, authentication, HTTP APIs,
servers, cloud, and Kubernetes are outside the MVP. Any future approximation
must use a new explicit metric contract and cannot silently replace the exact
User-Agent result specified here.

