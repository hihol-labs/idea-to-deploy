# Project Architecture: nginx-insight

## Context and Constraints

The product is a local, pip-installable Python 3.11 CLI that scans one nginx
combined access-log stream per invocation. It must remain stateless, use a
single operating-system process, spend $0 on infrastructure, and target a 1 GB
input in under 30 seconds on a documented laptop. Click defines the CLI, Rich
renders terminal output, and dataclasses carry parsed records and reports.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect here because no query,
retention, multi-user coordination, or cross-run state is required; it would
add I/O, schema, migration, and cleanup costs to a one-shot analysis. An HTTP
API is incorrect because the user already has the data locally and needs a
composable shell command, not a long-running network service, authentication,
ports, request limits, or deployment operations.

## Architecture Decision

The approved architecture is a single-process pipeline:

```text
file path or stdin
       |
       v
line iterator -> combined-log parser -> streaming aggregator -> immutable report
                      |                       |                    |
                      +-> malformed count     +-> bounded sets     +-> Rich / JSON / CSV
```

One reader, parser, and aggregator operate synchronously in the main process.
The tool never retains raw lines or parsed request records after updating
aggregates. Output rendering begins only after EOF so every format represents
the same complete report.

Alternatives were considered but not selected:

- Multiple worker processes could parse chunks faster, but stdin is not
  seekable, chunk boundaries complicate correctness, and merge overhead is not
  justified until a benchmark proves the single process inadequate.
- SQLite-backed aggregation would cap some in-memory maps, but violates the
  approved stateless design and adds disk-dependent performance.
- Approximate sketches could bound cardinality, but the MVP promises exact
  counts and instead fails explicitly when the User-Agent ceiling is reached.

## Component Boundaries

| Module | Responsibility | May depend on |
|---|---|---|
| `src/nginx_insight/cli.py` | Click command, option validation, input lifecycle, exit mapping | parser, aggregator, renderers |
| `src/nginx_insight/models.py` | Frozen dataclasses for `AccessRecord`, ranked values, and `AnalysisReport` | Python standard library only |
| `src/nginx_insight/parser.py` | Compile and apply nginx combined-format grammar; parse status and timestamp | models |
| `src/nginx_insight/aggregate.py` | Increment counters and finalize deterministic top-10/percentage results | models |
| `src/nginx_insight/render/terminal.py` | Rich tables and summary diagnostics | models |
| `src/nginx_insight/render/json_output.py` | Stable JSON object serialization | models |
| `src/nginx_insight/render/csv_output.py` | Stable long-form CSV serialization | models |
| `src/nginx_insight/errors.py` | Domain exceptions mapped to exit codes | standard library only |

Renderers must not parse input or recompute metrics. The CLI must not contain
ranking logic. This keeps terminal presentation independent from pipeline
contracts and permits identical fixture assertions across formats.

## Data Model and Algorithms

`AccessRecord` carries only `ip: str`, `timestamp: datetime`, `url: str`,
`status: int`, and `user_agent: str`. Parsing accepts nginx combined-format
lines, including IPv4/IPv6 addresses and escaped quoted fields. The request
target is the URL token in the quoted request line; the query string remains
part of the URL. A missing User-Agent represented by `"-"` is a valid value,
not a malformed record.

The aggregator maintains:

- `total_lines` and `total_valid_requests` integer counters;
- `malformed_lines` integer counter;
- `Counter[str]` for all client IPs;
- `Counter[str]` for URLs only when `400 <= status <= 599`;
- a fixed 24-element integer array indexed by the hour encoded in each log
  timestamp (00 through 23 in that timestamp's recorded offset);
- `set[str]` of exact User-Agent values, capped by
  `--max-unique-user-agents`.

Top lists sort by count descending, then key lexicographically ascending, and
return at most 10 entries. The hourly percentage for each bin is exactly
`100 × hourly_request_count / total_valid_requests`. The unique User-Agent
share is `100 × unique_user_agent_count / total_valid_requests`. Percentages
are stored as numeric values and serialized at six decimal places in CSV;
terminal formatting may show two decimals. JSON numbers are not strings.

No database tables exist. No database engine, migration, index, data file, or
cross-run cache is allowed. Exact IP and URL counts are input-cardinality
dependent; the performance suite must record peak RSS as well as elapsed time.
The explicit User-Agent ceiling prevents silent approximation or unbounded
growth for that metric.

## CLI Interface

### Command

```text
nginx-insight [OPTIONS] [PATH]
```

`PATH` is an nginx combined access-log file. If omitted or equal to `-`, input
is read from stdin. One invocation analyzes one logical stream and emits one
report.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit the JSON schema below to stdout; mutually exclusive with `--csv` |
| `--csv` | false | Emit the CSV schema below to stdout; mutually exclusive with `--json` |
| `--no-color` | false | Disable ANSI styling in terminal mode; color is otherwise used only on a capable TTY |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive ceiling for exact distinct User-Agent values; exceeding it terminates with exit 4 |
| `--version` | n/a | Print version and exit 0 without reading input |
| `--help` | n/a | Print usage and exit 0 without reading input |

Unknown options, conflicting formats, invalid/non-positive limits, and excess
positional arguments are usage errors handled by Click.

### Inputs

- UTF-8 text from a regular file or stdin, processed line by line.
- Nginx combined log format:
  `remote_addr - remote_user [time_local] "request" status bytes "referer" "user_agent"`.
- Blank or non-matching lines are malformed, counted, and skipped.
- A stream with zero valid records is an input/parse failure; no report is
  written to stdout.
- File-open, permission, read, and decoding failures are input failures.

### Outputs

All primary output goes to stdout. Diagnostics go to stderr and never corrupt
JSON or CSV. A successful report includes total lines, valid requests,
malformed lines, top client IPs, top error URLs, all 24 hourly bins, exact
unique User-Agent count, and unique User-Agent percentage.

Default terminal output uses Rich headings and tables in this order: summary,
top IPs, top 4xx/5xx URLs, hourly distribution, User-Agent share. ANSI color is
suppressed for non-TTY stdout or `--no-color`.

JSON schema (field names are stable for the 1.x line):

```json
{
  "schema_version": "1.0",
  "summary": {
    "total_lines": 0,
    "total_valid_requests": 0,
    "malformed_lines": 0
  },
  "top_ips": [{"rank": 1, "ip": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"rank": 1, "url": "/missing", "count": 1}],
  "hourly_distribution": [{"hour": 0, "count": 1, "percentage": 100.0}],
  "user_agents": {"unique_count": 1, "percentage": 100.0}
}
```

The real `hourly_distribution` always has 24 entries ordered from hour 0 to
23. CSV is UTF-8, RFC 4180 compatible, includes one header, and uses the stable
long-form columns `section,rank,key,count,percentage`. Summary rows use keys
`total_lines`, `total_valid_requests`, and `malformed_lines`; ranking rows use
the IP or URL as `key`; hourly rows use zero-padded hours; the User-Agent row
uses key `unique_user_agents`. Non-applicable cells are empty.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Success, including `--help` and `--version` |
| `1` | Unexpected internal/runtime failure |
| `2` | CLI usage or option-validation error |
| `3` | Input open/read/decode failure, or no valid nginx records |
| `4` | Unique-cardinality exhaustion: a new User-Agent would exceed `--max-unique-user-agents` |

On codes 1–4, diagnostics are concise and go to stderr. Code 4 must not emit a
partial success report.

## Error Handling and Observability

Malformed individual lines do not fail an otherwise valid run. Their count is
included in all successful formats, and terminal mode also prints a concise
stderr warning when the count is nonzero. Expected domain failures use typed
exceptions and the exit mapping above. Unexpected exceptions are caught only
at the CLI boundary, reported without a traceback by default, and mapped to 1.
No telemetry, log upload, or local persistence occurs.

## Performance and Resource Contract

The normal path is O(n) in input lines. The 24-hour array is O(1); exact IP,
URL, and User-Agent collections are O(distinct values). Input is consumed via a
buffered text iterator; no `read()`, `readlines()`, list of lines, or list of
records is permitted. Regexes and serializers are initialized once per run.

The acceptance benchmark uses a deterministic representative 1 GB combined
log, invokes the installed CLI in JSON mode with stdout redirected, and records
Python version, CPU, RAM, OS, storage, elapsed wall time, and peak RSS. Passing
requires elapsed time below 30 seconds on the documented laptop and identical
metric output to a smaller independently calculated oracle fixture. The target
is not claimed for arbitrary cardinality or storage hardware.

## Security and Trust Boundaries

The log is untrusted text. The tool never executes fields, expands shell
syntax, follows URLs, or interprets terminal control sequences as markup.
Rich output escapes untrusted values; CSV uses a standards-compliant writer;
JSON uses the standard encoder. Path handling reads only the explicit input.
There are no credentials, environment secrets, network listeners, plugins, or
privileged operations.

## Packaging and Runtime

`pyproject.toml` defines Python `>=3.11,<4`, runtime dependencies on Click and
Rich, and the `nginx-insight` console entry point. Wheels and source
distributions are built with a standard PEP 517 backend. There is no Docker
image, `docker-compose.yml`, server deployment target, environment-variable
contract, or authentication flow because the deployment target is the user's
local Python environment and the tool has no protected resource.

## Architecture Decision Record

### ADR-001: Single-process stateless CLI

- **Status:** Accepted by the project brief.
- **Decision:** Use the synchronous pipeline described above with no database
  and no HTTP API.
- **Why:** It minimizes delivery and operational cost, preserves stdin
  composability, and is sufficient unless measured profiling disproves the
  performance target.
- **Consequences:** Exact high-cardinality counters consume memory; output is
  available after EOF; historical comparison is delegated to shell pipelines.
- **Revisit when:** A reproducible benchmark shows the approved design cannot
  meet 1 GB under 30 seconds, or users require cross-run queries.

No Devil's Advocate or independent architecture review is recorded here; that
review is intentionally delegated to the external post-session harness.

## Traceability

Product priorities and risks come from `STRATEGIC_PLAN.md`. User-visible
behavior and acceptance criteria come from `PRD.md`. File-level delivery and
verification are sequenced in `IMPLEMENTATION_PLAN.md`.
