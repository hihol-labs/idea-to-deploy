# Project Architecture: Nginx Log Lens

## 1. Context and Goals

The product is an installable Python 3.11 CLI that reads nginx access logs
from one file or stdin, performs a single streaming pass, and renders four
reports. The primary quality attributes are correct parsing, stable
machine-readable output, bounded input buffering, and a measured target of
processing 1 GB in under 30 seconds on a named reference laptop.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
Both constraints are correct because every requested metric can be produced
from one input stream in one local process, users need immediate local and
pipeline output, persisted/queryable history is outside the use case, and a
server would add security, deployment, cost, and operational burdens without
improving the approved workflows.

## 2. System Context

```text
nginx log file ─┐
                ├─> Click CLI -> line reader -> parser -> aggregators
stdin / pipe ───┘                                  |
                                                   v
                                     immutable report snapshot
                                        /       |       \
                                   Rich text    JSON     CSV
                                    stdout     stdout   stdout

diagnostics, malformed-line summary, errors ----------------> stderr
```

The process has no network calls, daemon, database, cache, background worker,
authentication boundary, or telemetry.

## 3. Architecture Decision

### Selected: single-process layered CLI

- **Approach:** one Python process with separate input, parsing, aggregation,
  report-model, rendering, and CLI adapter modules.
- **Pros:** lowest operational complexity, deterministic data flow, easy local
  installation, no serialization between components, $0 runtime cost.
- **Cons:** exact counters grow with distinct IP/URL/User-Agent cardinality;
  CPU work is limited to one process.
- **Best for:** one-shot and piped analysis on a laptop.
- **Estimated complexity:** Low.

The product decisions and obvious architecture were pre-approved, so no
interactive variant selection is needed. Alternatives were still evaluated:

- A multi-process parser could improve CPU throughput but would add chunk
  boundary logic, result merging, nondeterminism, and startup overhead before
  profiling proves a need.
- An embedded SQLite store would permit later queries but violates stateless
  processing and adds write amplification, cleanup, and schema concerns.
- A Go implementation could offer more throughput but violates the approved
  Python 3.11 stack and reduces one-weekend feasibility.

## 4. Components and Responsibilities

| Module | Responsibility | Must not do |
|---|---|---|
| `src/nginx_log_lens/cli.py` | Click command, option validation, exit mapping | Parse records or format report internals |
| `src/nginx_log_lens/input.py` | Open UTF-8-compatible text stream from path or stdin | Read the entire input |
| `src/nginx_log_lens/parser.py` | Convert a combined-log line to `AccessRecord` or a typed parse failure | Print or mutate aggregators |
| `src/nginx_log_lens/models.py` | Dataclasses for parsed records, counters, and final report | Depend on Click or Rich |
| `src/nginx_log_lens/aggregate.py` | Update counters and finalize sorted top-10/report metrics | Perform terminal I/O |
| `src/nginx_log_lens/renderers/text.py` | Rich tables and summary | Change metric semantics |
| `src/nginx_log_lens/renderers/json.py` | Stable JSON document | Emit diagnostics to stdout |
| `src/nginx_log_lens/renderers/csv.py` | Stable long-form CSV rows | Emit terminal styling |
| `src/nginx_log_lens/errors.py` | Domain exception hierarchy and exit-code mapping | Swallow unexpected failures |

Dependency direction is CLI/renderers → report model; input/parser/aggregate →
report model. Domain modules do not import Click or Rich.

## 5. Data Model

All structures are in-memory dataclasses and standard-library counters; there
are no database tables.

### `AccessRecord`

| Field | Type | Constraint |
|---|---|---|
| `ip` | `str` | Non-empty token from remote address field |
| `timestamp` | timezone-aware `datetime` | Parsed from nginx timestamp including offset |
| `request_target` | `str` | URL/request-target token; raw target retained |
| `status` | `int` | 100–599 |
| `user_agent` | `str \| None` | `None` for missing/`-`; otherwise raw value |

### `AnalysisState`

| Field | Type | Meaning |
|---|---|---|
| `valid_requests` | `int` | Successfully parsed records |
| `malformed_lines` | `int` | Lines rejected by the parser |
| `ip_counts` | `Counter[str]` | Exact requests per IP |
| `error_url_counts` | `Counter[str]` | Exact 4xx/5xx requests per target |
| `hour_counts` | fixed 24-element integer list | Requests by local hour encoded in each record |
| `user_agents` | `set[str]` | Distinct non-empty User-Agent values |

### `AnalysisReport`

An immutable snapshot with total/valid/malformed counts, ordered top-IP and
top-error-URL entries, 24 hourly buckets, `unique_user_agents`, and
`unique_user_agent_share`. The share is:

```text
distinct non-empty User-Agent strings / valid_requests
```

It is `0.0` when there are no valid requests. This is a diversity ratio, not
the percentage of requests that contain a unique UA.

### Bounded Physical-Line Reader

`input.py` reads binary input in 64 KiB chunks and assembles records only up
to 1 MiB (1,048,576 bytes), excluding `\n` and an optional preceding `\r`.
When a physical line exceeds the limit, the reader discards bytes through the
next newline (or EOF) and yields exactly one typed overlong-line failure. This
contract is identical for files and stdin and prevents a newline-free input
from becoming an implicit whole-file allocation. A final line without `\n`
is valid if it is within the limit.

### Memory Characteristics

Input buffering is O(1) in file size and capped to one 1 MiB line plus a
64 KiB chunk. Exact results require O(I + U + A)
memory, where I is distinct IPs, U distinct error URLs, and A distinct
User-Agents. “Streaming” therefore means one pass without loading the file,
not constant memory under unbounded cardinality. This limitation is explicit
and must be benchmarked.

## 6. Parsing Contract

The MVP accepts the standard nginx combined format:

```text
address SP ident SP user SP "[" timestamp "]" SP quoted-request SP status SP bytes SP quoted-referer SP quoted-user-agent
```

- `SP` is one or more ASCII spaces between fields. The parser consumes the
  entire line; trailing non-space tokens are malformed.
- `address`, `ident`, and `user` are non-space tokens. IPv4, IPv6, and other
  non-empty address tokens are retained verbatim; semantic IP validation is
  outside P0.
- A deterministic single-pass state machine parses bracketed and quoted
  fields in O(line length). Inside quoted fields, `\"` becomes `"` and `\\`
  becomes `\`; a backslash before another character preserves that character
  literally. An unmatched quote or trailing backslash is malformed.
- Empty referer/User-Agent and `"-"` are allowed and become missing values.
- The quoted request must contain exactly three non-empty, space-separated
  tokens: method, request target, and protocol. Request `"-"`, embedded raw
  spaces in the target, or extra request tokens are malformed.
- Timestamps use the record’s numeric timezone; hourly grouping uses the hour
  written in that timestamp and does not convert zones.
- Blank or malformed lines are counted and skipped.
- A run with at least one valid record succeeds while reporting skipped lines.
- A non-empty input with zero valid records is a data error.
- Text is decoded with UTF-8 and replacement for invalid byte sequences so a
  single bad byte cannot abort a long run.
- A physical line over 1 MiB is one malformed line, even when it spans many
  input chunks.

## CLI Interface

### Command

```text
nginx-log-lens [OPTIONS] [INPUT]
```

`INPUT` is a path to a regular readable log file. If omitted or `-`, the
command reads stdin. Exactly one input stream is processed per invocation.

### Options

| Option | Meaning | Default |
|---|---|---|
| `--json` | Emit one JSON document | off |
| `--csv` | Emit normalized CSV rows | off |
| `--color / --no-color` | Force or suppress color for text mode | auto by TTY |
| `--version` | Print version and exit | — |
| `--help` | Print usage and exit | — |

`--json` and `--csv` are mutually exclusive. `--color` is rejected with a
machine-readable mode because JSON/CSV stdout must contain data only.

### Inputs

- Seekable and non-seekable text streams are supported.
- Files are opened locally; no URL, glob expansion, directory recursion, gzip,
  follow/tail, or multi-file mode exists in P0.
- A downstream broken pipe terminates quietly with exit code 0 and no
  traceback. A read failure before EOF exits 3 and emits no partial report.
- A truly zero-byte stream exits 0 with an empty report. Any physical input
  line (including blank/overlong lines) with zero valid records exits 4.

### Outputs

Default text output contains four Rich sections plus valid/malformed totals:
top IPs, top error URLs, hourly distribution (00–23), and User-Agent diversity.
Ties in top lists sort by key ascending after count descending.

JSON schema:

```json
{
  "schema_version": 1,
  "requests": {"valid": 0, "malformed": 0},
  "top_ips": [{"ip": "string", "count": 0}],
  "top_error_urls": [{"url": "string", "count": 0}],
  "hourly_requests": [{"hour": 0, "count": 0}],
  "user_agents": {"unique": 0, "share": 0.0}
}
```

CSV is RFC 4180-compatible UTF-8 with this header:

```text
section,key,count,value
```

The exact rows and order are:

| Order | section | key | count | value |
|---:|---|---|---|---|
| 1 | `meta` | `schema_version` | empty | `1` |
| 2 | `summary` | `valid_requests` | integer | empty |
| 3 | `summary` | `malformed_lines` | integer | empty |
| 4.. | `top_ip` | raw IP | integer | empty |
| next | `top_error_url` | raw request target | integer | empty |
| next 24 | `hour` | `00` through `23` | integer | empty |
| next | `user_agent` | `unique` | integer | empty |
| last | `user_agent` | `share` | empty | decimal with six fractional digits |

Ranked sections use report order and may contain zero to ten rows. Empty cells
are zero-length fields. The header plus `meta,schema_version,,1` defines CSV
schema version 1. Both machine formats end with one newline.

### Exit Codes

| Code | Meaning |
|---:|---|
| 0 | Analysis completed, including an empty input stream |
| 1 | Unexpected internal error |
| 2 | CLI usage or mutually exclusive option error (Click convention) |
| 3 | Input cannot be opened/read |
| 4 | Non-empty input contains no valid records |

Diagnostics go to stderr. stdout is never mixed with diagnostics.

## 8. Error Handling and Observability

Expected failures become concise messages without tracebacks. Debug
tracebacks are not part of the public P0 interface. The command reports input
read failures, valid/malformed totals, and elapsed time in text mode; JSON/CSV
contain data fields only, with optional performance diagnostics on stderr
never enabled by default.

No log line contents are echoed in errors, reducing accidental disclosure.
The process does not write temporary files.

## 9. Security and Privacy

- Logs are untrusted input; fields are data and are escaped by renderers.
- No shell execution or dynamic evaluation is used.
- Rich markup is disabled/escaped for log-derived values.
- CSV preserves raw values and is pipeline-safe, not spreadsheet-safe:
  RFC 4180 quoting does not neutralize formula-like cells. Opening untrusted
  output in Excel/LibreOffice is outside P0; a future opt-in spreadsheet-safe
  mode may trade byte fidelity for prefix escaping.
- No data leaves the machine and no telemetry is collected.
- Authentication and authorization are not applicable because there is no
  server, shared state, or privileged action.

## 10. Database, API, and Deployment

### Database

None. There are deliberately zero tables, migrations, indexes, connection
variables, or persistent caches. In-memory dataclasses and counters are
destroyed when the process exits.

### API

None. There are deliberately zero HTTP endpoints, request bodies, ports, or
API credentials. The public integration surface is the CLI contract above.

### Authentication

None. Local filesystem permissions and shell execution identity are the only
access boundary. Adding auth would imply a server or persistent identity
system that the product explicitly excludes.

### Deployment

Distribution is a wheel/sdist installed with pip. Runtime is the user’s local
Python 3.11 environment. There is no Docker runtime requirement, compose
file, cloud target, Kubernetes manifest, or staging service.

### Environment Variables

There are no product-specific environment variables in P0. Standard terminal
conventions such as `NO_COLOR` may be honored by Rich but are not required
configuration.

## 11. Performance Strategy

- Iterate directly over a buffered stream; never call `read()` for the whole
  file.
- Parse once and update all aggregations in that same pass.
- Keep Rich and serialization out of the hot loop.
- Use fixed-size hourly buckets and standard-library `Counter`.
- After parser and aggregators exist—and before renderers—run an early
  fail-closed benchmark gate. The representative deterministic 1 GB fixture
  uses at most 100,000 distinct IPs, 100,000 distinct error URLs, and 100,000
  distinct User-Agents and must have median wall time under 30 seconds and
  peak RSS under 256 MB on the named reference laptop.
- Also run a 1 GB adversarial fixture with near-unique values. It has no
  universal memory promise: record wall time and peak RSS, and fail the
  architecture gate if the OS kills the process, an unhandled error occurs,
  or the results reveal the tool is unsuitable for the documented laptop.
- Use local SSD, warm-up, and three measured runs; record Python version, CPU,
  OS, storage, fixture generator version/seed, SHA-256, median, and peak RSS.
- Profile before changing algorithms. Approximate heavy-hitter algorithms are
  not permitted for P0 because the output claims exact top 10.

## 12. Test Strategy

| Layer | Evidence |
|---|---|
| Parser unit tests | Valid combined lines, spaces/quotes, timezone, missing fields, invalid status/timestamp, bad bytes |
| Aggregation unit tests | 4xx/5xx boundaries, ties, top-10 truncation, 24 hours, UA denominator |
| Renderer golden tests | Text without ANSI, JSON schema/ordering, CSV header/quoting/newline |
| CLI tests | File/stdin, conflicts, unreadable file, empty/all-malformed input, broken pipe |
| Property/fuzz tests | Parser never hangs or crashes on bounded arbitrary lines |
| Performance test | 1 GB median under 30 seconds and measured peak RSS on reference laptop |

## 13. Architecture Decision Record (ADR)

### ADR-001: Local single-process streaming CLI

- **Status:** Accepted (pre-approved).
- **Decision:** Use one Python process and layered modules; no persistence or
  network interface.
- **Consequences:** Simple distribution and privacy; exact cardinality remains
  the primary memory risk.

### ADR-002: Exact aggregation

- **Status:** Accepted.
- **Decision:** Exact counters and UA set, not sketches.
- **Consequences:** Results are deterministic and explainable; memory scales
  with distinct values and is part of benchmark acceptance.

### ADR-003: One report model, three renderers

- **Status:** Accepted.
- **Decision:** Aggregation produces a format-neutral immutable report.
- **Consequences:** Metric semantics stay identical across text, JSON, and
  CSV; renderers can be golden-tested independently.

### Debate Summary

The architecture was reviewed using the repository-local Devil’s Advocate
agent contract.

**Verdict:** APPROVE WITH CONDITIONS

**Challenges and resolutions:**

1. A newline-free record could defeat bounded buffering. **Resolved:** specify
   64 KiB chunks, a 1 MiB physical-line limit, and discard-to-delimiter
   behavior yielding one malformed record.
2. Performance was a late gate and high-cardinality behavior was vague.
   **Resolved:** gate immediately after parser/aggregation, define the
   representative cardinalities and <30 s/<256 MB thresholds, and add a
   separate adversarial 1 GB run.
3. The combined grammar allowed divergent parsers. **Resolved:** define full
   consumption, token/escape/request rules, and a linear state machine.
4. CSV lacked explicit versioning and row semantics. **Resolved:** enumerate
   every row class/order and add a schema-version row.
5. Broken-pipe/read/blank-only outcomes were ambiguous. **Resolved:** define
   exact output and exit behavior.
6. RFC 4180 quoting was not spreadsheet-formula protection. **Resolved:**
   describe CSV as pipeline-safe, preserve raw values, and exclude spreadsheet
   safety from P0.

**Alternatives considered and rejected:**

- Unbounded native text iteration — rejected because one newline-free record
  can allocate proportional to the entire input.
- Approximate sketches — rejected because P0 promises exact rankings/share.
- Multiprocessing, database storage, server deployment, or a language change
  — rejected because evidence does not justify violating the pre-approved
  local one-process Python scope.

## 14. Related Documents

Product priorities are in `STRATEGIC_PLAN.md` and `PRD.md`; planned modules and
verification commands are in `IMPLEMENTATION_PLAN.md`.
