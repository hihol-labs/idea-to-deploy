# Project Architecture: nginx-stream-report

## 1. Context and constraints

This is a local Python 3.11 CLI that performs one-pass analysis of nginx common/combined access logs. The controlling decision is: **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema lifecycle, disk amplification, cleanup, and state semantics while the approved outputs can be accumulated during one pass. An HTTP API would introduce a long-running process, networking, authentication concerns, deployment, and an operational failure surface without helping the primary shell/file/pipe workflow. Avoiding both keeps the product local, $0, installable with pip, and feasible in one weekend.

Additional constraints:

- no authentication, server, cloud, Docker requirement, or Kubernetes;
- no full-file materialization; process iterators line by line;
- target: representative 1 GB input in <30 seconds on a documented laptop;
- default colored terminal output; `--json` and `--csv` are mutually exclusive;
- common and combined nginx access-log formats are the MVP grammar.

## 2. Architecture variants

### Variant A: single-process streaming pipeline (recommended and approved)

- **Approach:** Click command opens a file/stdin iterator; parser emits dataclass records; one aggregator updates metrics; a selected renderer writes the report.
- **Pros:** minimal dependencies, bounded operational surface, straightforward profiling, no IPC or serialization.
- **Cons:** CPU work is single-process; exact cardinality structures require explicit memory limits.
- **Best for:** local one-shot or piped analysis on laptop-sized files.
- **Estimated complexity:** Low.

### Variant B: multiprocessing chunk analysis

- **Approach:** split seekable files into byte ranges, aggregate in workers, merge partial results.
- **Pros:** can use multiple CPU cores for large regular files.
- **Cons:** complex boundary repair, unavailable for stdin/follow mode, higher peak memory, overhead may erase gains.
- **Best for:** repeat analysis of multi-gigabyte seekable files after profiling proves CPU saturation.
- **Estimated complexity:** Medium.

### Variant C: external Unix pipeline stages

- **Approach:** separate parser and reducers connected by pipes/processes.
- **Pros:** replaceable stages and native shell composition.
- **Cons:** process startup and serialization overhead, harder cross-platform packaging, fragile shared error semantics.
- **Best for:** ecosystems that explicitly standardize intermediate event streams.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the user approved the obvious single-process architecture, the input is naturally sequential, delivery is one weekend, and the performance goal should first be tested against the simplest zero-copy-ish iterator design. Variants B/C are rejected unless measurement shows Variant A cannot meet the target.

## 3. Component model and data flow

```text
file path / stdin / followed file
              |
              v
      InputSource iterator
              |
              v
   NginxLineParser -> ParseIssue counter/sample
              |
       AccessRecord dataclass
              |
              v
      StreamingAggregator
       |      |      |      |
       v      v      v      v
      IPs  error URLs hours  UAs
              |
              v
        Report dataclass
              |
       +------+------+ 
       |      |      |
     Rich    JSON   CSV
```

The CLI layer owns option validation and exit codes. Parsing owns grammar only. Aggregation owns metric definitions and memory policy. Renderers consume the same immutable report so all formats remain semantically equivalent.

## 4. Planned package structure

```text
pyproject.toml
src/nginx_stream_report/
  __init__.py
  cli.py                 # Click command, options, exit codes
  models.py              # AccessRecord, ParseIssue, Report dataclasses
  parser.py              # common/combined parser
  sources.py             # file/stdin/follow iterators
  aggregate.py           # streaming counters and bounded cardinality policy
  renderers/
    __init__.py
    terminal.py           # Rich tables and TTY color behavior
    json.py               # versioned JSON document
    csv.py                # rectangular CSV rows
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_renderers.py
  test_performance.py
```

These are planned paths, not code produced by this blueprint.

## 5. Domain model and parsing contract

`AccessRecord` fields:

| Field | Python type | Meaning |
|---|---|---|
| `remote_addr` | `str` | Client IP/token from nginx record |
| `hour` | `int` | Validated hour `0`–`23` extracted directly from the nginx timestamp |
| `target` | `str` | Raw request target; query string retained |
| `status` | `int` | HTTP response status |
| `user_agent` | `str | None` | Combined format only; `-` maps to `None` |

The hot-path `AccessRecord` is a frozen, slotted dataclass limited to fields consumed by approved metrics; it does not allocate a `datetime`, referrer, byte count, method, or protocol for every line. Parsing validates the complete timestamp/status/request grammar but extracts only its hour, target, IP, status, and UA. Richer diagnostic representations are test/debug-only.

Sources read binary input with bounded `readline(65_537)` calls; when the limit is hit without newline, the source discards bounded chunks through the next newline and records exactly one oversized malformed line. Structural tokens are ASCII-compatible. Retained fields decode as UTF-8 with `errors="replace"`, so invalid sequences become U+FFFD consistently for files and stdin. MVP support means nginx’s traditional default common/combined escaping only; custom formats plus `escape=json` and `escape=none` are explicitly unsupported. Unsupported grammar, oversized lines/keys, and impossible status/timestamp/numeric tokens are malformed records.

The parser compiles parsing machinery once. Malformed lines increment `invalid_lines`; the default continues and terminal output warns. `--max-invalid N` exits with code 2 after more than N malformed lines. Diagnostics go to stderr and never corrupt JSON/CSV stdout.

## 6. Metric semantics and memory

| Metric | Definition | Ordering/ties |
|---|---|---|
| Top IPs | Count of valid records grouped by exact `remote_addr` | count descending, key ascending; first 10 |
| Top error URLs | Count of valid records with status 400–599 grouped by raw request target | count descending, target ascending; first 10 |
| Hourly distribution | Valid requests grouped by the hour `00`–`23` written in each record; the offset is validated but no host-time conversion occurs | always emits all 24 buckets |
| Unique UA share | `distinct_non_empty_user_agents / valid_requests`; count and percentage both emitted | zero valid requests yields 0 and 0.0% |

IP, URL, UA cardinality, and key length can be attacker-controlled. Exactness uses separate fail-closed defaults: 100,000 IP keys, 50,000 URL keys, 50,000 UA keys, 256 UTF-8 bytes per IP token, 8 KiB per URL, and 4 KiB per UA. Retained encoded-key bytes are also capped independently at 16 MiB for IPs, 64 MiB for URLs, and 32 MiB for UAs. `--max-ip-keys`, `--max-url-keys`, and `--max-ua-keys` may lower key caps; raising a compiled safe default requires an explicit future architecture/schema change. Key-length, retained-byte, and 64-KiB line limits are fixed in schema version 1. Crossing a key/byte cap fails with exit code 3; oversized individual records follow the malformed-line policy. The error names the exceeded resource and never returns an incomplete “exact” report.

Step 2 measures Python map/set/string overhead at the specified key/byte ceilings and lowers—not raises—the compiled key defaults if projected peak RSS exceeds 192 MiB, leaving at least 64 MiB headroom under the 256 MiB KPI. Step 4 runs a representative 100–250 MB parser-plus-aggregator throughput/RSS gate before any renderer work. If projected/observed RSS is above 256 MiB or throughput is below 34 MiB/s (1 GiB/30 s plus margin), implementation stops for profiling and either further simplifies the direct-to-aggregator hot path or revises the spec. A future approximate heavy-hitter/cardinality mode is P2 and must advertise approximation in every output format.

## 7. CLI contract

Planned console command: `nginx-stream-report [OPTIONS] [PATH]`; omitted `PATH` or `-` reads stdin.

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit one versioned JSON object to stdout |
| `--csv` | false | Emit RFC 4180-style rectangular CSV to stdout |
| `--follow` / `-f` | false | Live-refresh a growing regular file in terminal mode; incompatible with stdin/JSON/CSV |
| `--refresh-interval FLOAT` | 2.0 | Seconds between Rich live snapshots in follow mode; must be >0 |
| `--max-invalid INTEGER` | unlimited | Stop when invalid-line count exceeds threshold |
| `--max-ip-keys INTEGER` | 100,000 | Exact IP-key ceiling; may only be lowered |
| `--max-url-keys INTEGER` | 50,000 | Exact error-URL-key ceiling; may only be lowered |
| `--max-ua-keys INTEGER` | 50,000 | Exact UA-key ceiling; may only be lowered |
| `--no-color` | false | Disable terminal styling; styling is also disabled when stdout is not a TTY |
| `--version` | — | Print version and exit |

`--json` and `--csv` conflict and produce Click usage error code 2. Follow mode uses Rich Live to redraw a terminal snapshot at the refresh interval; it rejects stdin, JSON, CSV, and non-TTY stdout because version 1 defines no multi-snapshot machine schema. Missing/unreadable input is exit 1; usage/parser-threshold errors are exit 2; cardinality safety stop is exit 3; success is exit 0. Ctrl-C leaves one final terminal snapshot and exits 130 if output completes safely; otherwise it emits a diagnostic to stderr.

## 8. Output schemas

### Terminal

Rich renders a title, source/valid/invalid totals, top-IP table, top-error-URL table, a 24-row hourly table, and unique-UA counts/share. 4xx and 5xx error sections use distinct accessible colors. No escape sequences are produced for non-TTY output or `--no-color`.

### JSON

Top-level keys are `schema_version`, `source`, `processed_lines`, `valid_requests`, `invalid_lines`, `top_ips`, `top_error_urls`, `hourly_requests`, and `user_agents`. Ranked arrays contain `{value, count}` objects. `hourly_requests` maps two-digit hour strings to integers. `user_agents` contains `unique`, `valid_requests_denominator`, and `share` (0–1 float). Schema version starts at `1`.

### CSV

Header: `schema_version,metric,rank,key,count,value`. Rows use `metric` values `summary`, `top_ip`, `top_error_url`, `hourly_request`, and `user_agent_share`. Unused cells are empty; `value` carries fractional share for `user_agent_share`. All fields use Python `csv` quoting and newline handling and preserve exact decoded key values. Spreadsheet formula mitigation is not silently applied because that would break JSON/CSV equivalence; documentation warns spreadsheet users, and an explicitly versioned `--spreadsheet-safe` representation is deferred to P2.

## 9. Database, API, authentication, and deployment

### Database schema

Not applicable by design: there are zero tables, migrations, indexes, or retained records. In-process dataclass instances and counters live only for the command duration. Introducing the template’s generic “three tables” would violate the approved stateless architecture.

### HTTP API

Not applicable by design: there are zero endpoints, request bodies, ports, or network listeners. The complete public interface is the CLI and its stdout/stderr/exit-code contract. Introducing the template’s generic “five endpoints” would violate the approved CLI-only scope.

### Authentication and authorization

None. The program reads only paths the invoking OS user can read and inherits filesystem authorization. It does not elevate privileges, accept credentials, or contact remote systems.

```text
OS user -> shell -> local process -> OS-authorized file/stdin
                    X no network/auth flow
```

### Environment variables

No product-specific environment variables. Locale and standard terminal variables may affect glyph/color capability but not metric semantics. All behavior-affecting settings are explicit CLI flags.

### Docker

No Dockerfile or `docker-compose.yml` is planned. Containers would slow the under-30-second local start path and are unnecessary for pip distribution.

### Deployment/distribution

Build a universal wheel/sdist with `pyproject.toml`, publish to PyPI, and install with `pipx install nginx-stream-report` or pip into an isolated environment. Release evidence includes Python 3.11 wheel installation on Linux/macOS and a documented WSL/Linux reference benchmark. No server deployment exists.

## 10. Performance and observability

- Read bounded lines from buffered binary I/O and iterate; never call `read()`/`readlines()` for the entire input.
- Parse each line once directly into the minimal slotted record/aggregator input; do not allocate unused fields or `datetime` objects.
- Keep stdout writes until final rendering for finite input; progress/debug output is off by default.
- Calibrate worst-case key-memory overhead in Step 2, then benchmark 100–250 MB immediately after core parser/aggregator integration and 1 GB at release. Record wall time, throughput, peak RSS, valid/invalid counts, CPU, OS, storage, Python, and fixture checksum/generator.
- Profile before changing architecture. Multiprocessing is allowed only through a new architecture decision.
- User-visible operational signals are processed/valid/invalid totals, deterministic exit codes, and stderr diagnostics.

## 11. Security and privacy

Logs may contain IP addresses, query strings, referrers, and User-Agents. Processing remains local; there is no telemetry or egress. Renderers escape terminal markup, CSV uses correct lossless quoting and documents formula-injection risk on spreadsheet import, JSON uses standard encoding, and diagnostics do not dump full malformed lines by default. Symlinks and file permissions follow normal OS semantics; the tool never writes beside the input.

## 12. Architecture Decision Record (ADR)

### ADR-001: Local single-process, stateless pipeline

- **Status:** Accepted (pre-approved).
- **Decision:** Select Variant A with no database and no HTTP API.
- **Drivers:** one-weekend schedule, $0 budget, pip install, shell workflow, 1 GB/30 s target.
- **Consequences:** simple operations and reproducible outputs; scale-up relies on parser efficiency and bounded maps rather than distributed execution.

### Debate summary

The architecture was read-only reviewed by the repository-local Devil’s Advocate agent against this document and `PRD.md`.

**Verdict:** APPROVE WITH CONDITIONS — all six conditions resolved in this revision.

**Challenges and resolutions:**

1. Three million potentially long keys did not prove the memory KPI. **Resolution:** separate per-map ceilings, fixed line/key limits, a 192 MiB projected envelope, and early measured RSS gate were added.
2. Per-line `datetime`/unused dataclass allocation threatened the release-blocking throughput goal. **Resolution:** the hot path now parses only five required values into a slotted record and runs a 100–250 MB gate before renderer work.
3. Follow mode had no observable result until interruption. **Resolution:** terminal-only Rich live refresh is specified; machine modes are rejected until a framed snapshot schema exists.
4. Encoding and nginx escaping were underspecified. **Resolution:** bounded binary reads, UTF-8 replacement semantics, and traditional default common/combined escaping are explicit.
5. Spreadsheet prefixing would make CSV lossy relative to JSON. **Resolution:** version 1 CSV is lossless; optional safe presentation is deferred and must be explicit/versioned.
6. `eligible_requests` contradicted the all-valid-request denominator. **Resolution:** the schema field is renamed `valid_requests_denominator`.

**Alternatives considered and rejected:** multiprocessing and external pipeline stages remain rejected because no benchmark yet proves the simpler architecture insufficient. Silent approximation, silent CSV mutation, and a multi-snapshot JSON/CSV stream are rejected because they weaken exact/stable output contracts.

See `STRATEGIC_PLAN.md` for priorities, `PRD.md` for acceptance behavior, and `IMPLEMENTATION_PLAN.md` for planned delivery.
