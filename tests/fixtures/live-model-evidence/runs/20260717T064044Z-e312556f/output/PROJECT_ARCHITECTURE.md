# Project Architecture: Nginx Stream Report

## 1. Architecture goals and constraints

Nginx Stream Report is an installable Python 3.11 CLI that reads nginx access-log records from a file or standard input, computes exact cardinality-proportional aggregate statistics in one pass, and writes a terminal, JSON, or CSV report. The primary performance target is processing a 1 GiB log in under 30 seconds on a representative laptop while keeping raw-input memory constant; aggregate memory is explicitly `O(unique IPs + unique error URLs + unique User-Agents)` and is not claimed to be bounded.

The governing decision is **"no database — stateless streaming processing; no HTTP API — CLI-only tool"**. A database is incorrect here because the product has no persistence, query, concurrency, or cross-run history requirement; adding one would increase installation cost, I/O, failure modes, and budget without helping the one-pass report. An HTTP API is incorrect because the users and automation already operate on local files and Unix pipelines; a server would add authentication, lifecycle, networking, and deployment concerns while violating the approved local-only scope.

Additional constraints:

- Python 3.11, Click, Rich, and dataclasses are fixed stack decisions.
- No authentication, database, HTTP API, server, cloud service, container, or Kubernetes resources.
- `$0` operating budget, open-source dependencies, pip installation, and one-weekend delivery.
- Input is treated as untrusted text. Malformed lines must be counted and skipped without executing or interpreting their contents.

## 2. Architecture variants

### Variant A: Single-process streaming pipeline (recommended)

- **Approach:** one CLI process reads lines incrementally, parses each line into a dataclass, updates in-memory aggregators, and renders once at EOF or interruption.
- **Pros:** minimal moving parts; works with files and stdin; deterministic ordering; easy pip installation; no intermediate storage.
- **Cons:** one CPU core; exact unique User-Agent tracking can grow with cardinality; a final report is unavailable until the stream ends.
- **Best for:** the approved local CLI, one-weekend scope, and typical nginx logs up to and beyond 1 GB.
- **Estimated complexity:** Low.

### Variant B: Local multi-process chunk pipeline

- **Approach:** split seekable files into byte ranges, parse in worker processes, and merge partial counters.
- **Pros:** can use multiple CPU cores for very large regular files.
- **Cons:** cannot naturally handle stdin; chunk-boundary logic and merging increase complexity; process startup and serialization can erase gains; harder error accounting.
- **Best for:** a later version whose measured parsing performance misses the target on multi-gigabyte seekable files.
- **Estimated complexity:** Medium.

### Variant C: External analytics stack

- **Approach:** ingest logs into GoAccess or Logstash/Elastic and query stored aggregates.
- **Pros:** richer dashboards, historical queries, and broader ecosystem integrations.
- **Cons:** violates the no-database/no-server constraints; materially higher setup, resource, and operational cost; poor fit for ad hoc pipelines.
- **Best for:** teams needing persistent, multi-user observability rather than a local report.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the user pre-approved the obvious single-process architecture and it is the only variant aligned with every scope, budget, delivery, and pipeline constraint. Variant B remains a measurement-triggered fallback, not MVP scope. Variant C is an alternative product category.

## 3. Component model and data flow

```text
file path / stdin
       |
       v
Click command + option validation
       |
       v
incremental text reader -----> malformed-line counter
       |
       v
nginx combined-log parser -> AccessRecord dataclass
       |
       v
StreamingStats aggregator
  |          |             |              |
  v          v             v              v
IP counts  error URLs  hourly counts  User-Agent set
       \        |           |          /
        +-------+-----------+---------+
                        |
                        v
              Report dataclasses
               /       |       \
              v        v        v
          Rich text   JSON      CSV
```

Processing phases are deliberately separate: parse, aggregate, snapshot, serialize. Renderers receive the same immutable report model, preventing output modes from changing metric semantics.

## 4. Planned package structure

```text
pyproject.toml
src/nginx_stream_report/
  __init__.py
  cli.py                 # Click command, options, exit codes
  models.py              # AccessRecord and report dataclasses
  parser.py              # compiled-regex combined-log parser
  stats.py               # streaming aggregation and top-k finalization
  formatters/
    __init__.py
    terminal.py          # Rich tables and colors
    json_output.py       # stable machine-readable object
    csv_output.py        # normalized multi-section CSV
tests/
  fixtures/
    sample_access.log
    malformed_access.log
  test_parser.py
  test_stats.py
  test_cli.py
  test_performance.py
```

## 5. Runtime data model

No database schema exists. All records and aggregates are process-local and discarded at exit.

### `AccessRecord`

| Field | Python type | Validation/meaning |
|---|---|---|
| `remote_ip` | `str` | non-empty parsed address token; IPv4/IPv6 text retained |
| `timestamp` | `datetime` | timezone-aware nginx timestamp |
| `method` | `str` | request method, or empty when request token is incomplete |
| `url` | `str` | raw request-target path/query token |
| `protocol` | `str` | HTTP protocol token, possibly empty |
| `status` | `int` | 100–599 |
| `user_agent` | `str` | exact decoded field, including `-` if supplied |

### `StreamingStats` mutable state

| Field | Python type | Purpose |
|---|---|---|
| `ip_counts` | `Counter[str]` | request count per source IP |
| `error_url_counts` | `Counter[str]` | count per URL only for status 400–599 |
| `hour_counts` | `list[int]` of length 24 | request distribution by log-local hour |
| `user_agents` | `set[str]` | exact unique User-Agents |
| `total_requests` | `int` | successfully parsed records |
| `malformed_lines` | `int` | rejected records |
| `decode_replacements` | `int` | lines whose input decoder replaced at least one invalid byte |

### Report dataclasses

- `RankedItem(key: str, count: int)` for deterministic top-10 entries.
- `HourlyBucket(hour: int, count: int, share: float)` for every hour `00`–`23`.
- `Report(total_requests: int, malformed_lines: int, top_ips: tuple[RankedItem, ...], top_error_urls: tuple[RankedItem, ...], hourly: tuple[HourlyBucket, ...], unique_user_agents: int, unique_user_agent_share: float)`.

The unique User-Agent share is `unique_user_agents / total_requests * 100`, or `0.0` when no valid requests exist. Exact tracking is a P0 acceptance requirement. The benchmark includes representative- and high-cardinality profiles and records peak RSS. If allocation fails, the CLI writes a concise resource-exhaustion diagnostic to stderr, emits no apparently complete report, and exits `4`. A future approximate-cardinality mode is a P2 option only if evidence shows need and its error semantics are separately specified.

## 6. CLI contract

There are no HTTP endpoints. The complete public interface is one console command:

```text
nginx-stream-report [OPTIONS] [INPUT]
```

| Argument/option | Type/default | Behavior |
|---|---|---|
| `INPUT` | path, default `-` | nginx access log path; `-` reads stdin |
| `--json` | flag | emit one JSON document to stdout |
| `--csv` | flag | emit normalized CSV rows to stdout |
| `--encoding` | text, default `utf-8` | input decoding; invalid bytes are replaced and counted only if parsing fails |
| `--version` | flag | print package version and exit |
| `--help` | flag | print usage and exit |

`--json` and `--csv` are mutually exclusive. Terminal output is the default only when neither is supplied. Successful reports go to stdout; warnings and fatal diagnostics go to stderr. Broken pipes exit quietly with success-compatible behavior for Unix pipelines.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | report emitted successfully, even if some malformed lines were skipped |
| `2` | invalid CLI usage or mutually exclusive options |
| `3` | input cannot be opened or read |
| `4` | unexpected processing/output failure |
| `130` | interrupted by `SIGINT`; no report is emitted |

Normal EOF is the only completion condition that emits a report and exits `0`. `SIGINT` emits no partial report and exits `130`. A broken pipe emits no diagnostic and exits `0`, matching a downstream consumer that intentionally closed after receiving sufficient output. Read, memory, or non-broken-pipe output failures emit no report that can be mistaken for complete data.

## 7. Output contracts

### Terminal

Rich renders a summary followed by top IPs, top error URLs, 24 hourly buckets, and unique User-Agent count/share. Color is automatically disabled for non-TTY output and honors the standard `NO_COLOR` convention. Empty sections render an explicit `No data` state.

### JSON

JSON is UTF-8 followed by one `\n`, with `ensure_ascii=false`, `allow_nan=false`, and schema version integer `1`. Arrays are deterministic and empty arrays represent empty ranked sections. Percentages are JSON numbers rounded to two decimal places with round-half-even behavior; counts remain exact integers.

```json
{
  "schema_version": 1,
  "summary": {
    "total_requests": 0,
    "malformed_lines": 0,
    "decode_replacements": 0,
    "unique_user_agents": 0,
    "unique_user_agent_share_percent": 0.0
  },
  "top_ips": [],
  "top_error_urls": [],
  "hourly_distribution": [
    {"hour": "00", "count": 0, "share_percent": 0.0}
  ]
}
```

The example abbreviates the hourly array; actual output always contains 24 objects from `00` through `23`. Ranked objects are `{"rank": integer, "key": string, "count": integer}` and use descending count then ascending key. Key insertion order shown above is canonical for golden tests, though consumers must parse by key.

### CSV

CSV is UTF-8 with `\r\n` line endings and columns `schema_version,section,rank,key,count,share_percent`. Every row has schema version `1`. Summary rows use keys `total_requests`, `malformed_lines`, `decode_replacements`, `unique_user_agents`, and `unique_user_agent_share`; their `rank` is empty and the value occupies `count` except the share, which occupies `share_percent`. Ranked sections are `top_ips` and `top_error_urls`. Hourly rows use section `hourly_distribution`, ranks 1–24, keys `00`–`23`, exact counts, and two-decimal shares. One header is emitted; RFC 4180 quoting is delegated to Python's `csv` module. Empty input still emits summary and 24 hourly rows but no ranked rows.

Machine-readable modes never contain ANSI escape sequences, progress text, or Rich decoration.

## 8. Parsing and aggregation decisions

- Support this anchored standard combined grammar for MVP: `remote_addr SP ident SP user SP [time_local] SP "request" SP status SP body_bytes_sent SP "http_referer" SP "http_user_agent"`, with no trailing fields. `SP` is one ASCII space. `remote_addr`, `ident`, and `user` are non-space tokens; IPv4 and IPv6 text are accepted without semantic IP validation. `status` is exactly three ASCII digits in 100–599 and bytes is digits or `-`. Quoted fields accept nginx-style `\\"` and `\\\\` escapes. The request field is either `-` or exactly `METHOD SP request-target SP protocol`; `-` maps to empty method/URL/protocol, while any other incomplete request is malformed. A compiled, anchored regex or deterministic scanner may implement the grammar; profiling decides, not preference.
- Read through an iterator; never call `read()`, `readlines()`, or retain raw input lines.
- Preserve request targets exactly as parsed so URL rankings are auditable; no URL normalization in P0.
- Count only 4xx and 5xx statuses in error URL rankings.
- Use `Counter.most_common` or `heapq.nlargest` only at finalization. Stable alphabetical tie-breaking is applied explicitly.
- Interpret the hour from each record's own timestamp and timezone; aggregate into 24 wall-clock hour buckets.
- Decode using the requested encoding with replacement so streaming remains possible, and count every line containing replacement character `U+FFFD` in `decode_replacements` whether or not it otherwise parses. Continue past malformed records and report their count. Do not log each bad line by default, which would damage performance and pipelines.
- For an endless stdin stream, report only on EOF. `SIGINT` produces no partial report and exits `130`; periodic dashboards are out of scope.

## 9. Performance and resource strategy

The 1 GiB/30-second target uses a deterministic seeded generator rather than a checked-in giant file. Seed `20260717` produces two exact-size profiles: `representative` (1,000 IPs, 5,000 URLs, 500 User-Agents, 5% errors) and `high-cardinality` (unique IP, error URL where applicable, and User-Agent per record). The benchmark command records generator version/hash, seed, CPU model, RAM, OS, Python version, filesystem, cache treatment, elapsed seconds, MiB/s, valid lines, and peak RSS. Run three warm-cache repetitions from a local SSD and use the median elapsed time; the `<30.0 s` release gate applies to the representative profile, while high-cardinality results are a documented memory-safety observation rather than a fixed time gate. The hot path avoids per-line Rich calls, exceptions for valid input, repeated regex compilation, and datetime formatting.

Acceptance thresholds:

- the median of three 1 GiB representative runs completes in `<30.0 s` on the declared reference laptop;
- Peak memory does not grow with line count when cardinalities are held constant.
- File and stdin results are byte-equivalent for JSON and CSV.
- Terminal formatting occurs only after aggregation.

If the benchmark fails, profile before changing architecture. Optimize parsing and timestamp extraction first; consider Variant B only when a measured CPU-bound parser remains above target and stdin parity can be preserved.

## 10. Security and trust boundaries

The trust boundary is the local log stream and CLI arguments. The tool performs no network calls and executes no log-derived data. File access uses only the explicit path provided by the invoking user. Before terminal rendering, every log-derived string passes through a terminal-only sanitizer that converts C0/C1 controls, ESC, DEL, carriage return, tab, bidi formatting controls, and other non-printing code points to visible `\\xNN` or `\\uNNNN` escapes, followed by Rich markup escaping. JSON and CSV retain Unicode data through their standards-compliant escaping/quoting. Fixtures cover Rich markup, ANSI CSI, OSC hyperlinks, CR, tab, DEL, and bidi controls, and tests assert that no raw control changes terminal state. Error messages avoid echoing full log lines, which may contain tokens or personal data. The README must warn that IP addresses, URLs, and User-Agents can be sensitive and that redirected reports inherit that sensitivity.

## 11. Configuration and environment

No `.env` file or required environment variables exist. Standard environment behavior is limited to:

| Variable | Required | Example | Meaning |
|---|---|---|---|
| `NO_COLOR` | no | `1` | disable ANSI color in terminal mode |
| `PYTHONUTF8` | no | `1` | standard Python UTF-8 mode; not read directly by the app |

There is no Docker or `docker-compose.yml` architecture. Pip installation is the deployment mechanism; containers would add no runtime capability to a local stdin/file CLI.

## 12. Authentication, persistence, API, and deployment

- **Authentication:** not applicable. The CLI runs with the invoking operating-system user's permissions and has no remote trust boundary.
- **Persistence/database:** not applicable. Reports are written only to stdout at the user's direction; no tables, migrations, indexes, or state files exist.
- **HTTP API:** not applicable. There are no endpoints, request bodies, ports, or server lifecycle.
- **Deployment:** publish a source distribution and universal Python wheel to a pip-compatible package index; local execution requires Python 3.11+. Release work can be performed with standard PyPA tooling, but automated publishing is not part of the MVP implementation.

## 13. Architecture Decision Record (ADR)

### ADR-001: Single-process, exact, streaming CLI

- **Status:** Accepted (pre-approved).
- **Decision:** use Variant A with exact counters/sets and three renderer adapters.
- **Rationale:** it minimizes operational surface and directly supports local files and pipelines within a one-weekend budget.
- **Consequences:** performance is limited to one process and memory follows aggregate cardinality; both are transparent and benchmarkable.

### Debate summary

The architecture was reviewed by the repository-local Devil's Advocate agent.

**Verdict:** APPROVE WITH CONDITIONS. All six specification conditions were accepted and resolved without changing Variant A.

**Challenges raised and resolutions:**

1. Exact aggregation was incorrectly described as bounded. **Resolution:** state cardinality-proportional complexity, require representative/high-cardinality RSS evidence, define allocation failure, and retain approximation as P2.
2. Rich escaping alone does not neutralize terminal control sequences. **Resolution:** add a terminal-only control/bidi sanitizer and hostile golden fixtures.
3. Combined-log validity was underspecified. **Resolution:** define an anchored field grammar, escape handling, request `-`, invalid request behavior, and separate decode-replacement accounting.
4. The performance gate was not reproducible. **Resolution:** standardize on 1 GiB, a deterministic seed and two profiles, three warm-cache runs, median timing, environment metadata, and MiB/s/RSS evidence.
5. JSON/CSV contracts were incomplete. **Resolution:** set schema version `1`, define fields, ordering, empty representations, rounding, encoding, newlines, and CSV summary mapping.
6. `SIGINT` and broken-pipe semantics were ambiguous. **Resolution:** emit reports only at EOF, exit `130` without output for `SIGINT`, and exit quietly `0` for broken pipes.

**Alternatives considered and rejected:**

- Approximate counters as the default — rejected because P0 promises exact, auditable metrics; may return as an explicitly approximate P2 mode.
- Multi-process parsing — rejected absent measured failure of the optimized single-process benchmark and because it weakens stdin parity.
- Database/server analytics stack — rejected because it violates the approved product, cost, and deployment constraints.

Runtime performance and library behavior remain unverified until product implementation and the plan's tests/benchmark exist; this blueprint makes them verifiable rather than claiming them as facts.

## 14. Cross-document traceability

Product behavior and acceptance criteria are authoritative in `PRD.md`. Delivery sequencing and verification commands are in `IMPLEMENTATION_PLAN.md`. Market rationale, priorities, budget, risks, and Definition of Done are in `STRATEGIC_PLAN.md`. Contributor execution prompts are in `CLAUDE_CODE_GUIDE.md`.
