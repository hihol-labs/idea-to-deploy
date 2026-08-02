# Project Architecture: nginx-log-report

## 1. Context and Goals

The product is a local Python 3.11 CLI that consumes nginx access-log lines incrementally and emits four aggregate reports in terminal text, JSON, or CSV. It must remain installable through pip, cost $0 to operate, fit a one-weekend delivery, and process an exactly 1,000,000,000-byte (decimal 1 GB) reference log in under 30 seconds on the reference laptop.

The governing decision is: **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema lifecycle, storage cleanup, and operational state without improving a one-shot local report; in-memory counters and a User-Agent set are sufficient for exact MVP results. An HTTP API would require a long-running server, request security, deployment, and lifecycle management even though the target users already work in terminals and pipelines. Files/stdin plus stdout/stderr form the smallest complete boundary.

## 2. Architecture Decision and Alternatives

The user-approved architecture is a single OS process with one streaming read pass. Architectural alternatives are recorded, not reopened for selection:

| Variant | Approach | Advantages | Costs/risks | Decision |
|---|---|---|---|---|
| A: single-process streaming | Parse and aggregate each line synchronously; render once at EOF | Smallest implementation, deterministic, pipeline friendly, no IPC | Exact cardinality maps can grow with unique values | **Selected** |
| B: local multiprocessing | Split seekable files into byte ranges and merge worker aggregates | Potential CPU throughput | stdin complexity, boundary repair, duplicated sets, IPC, weekend risk | Rejected until profiling proves necessary |
| C: external analytics stack | Ship logs to GoAccess or Elastic-family services | Richer analysis and persistence | Violates zero-infrastructure, stateless, and narrow-scope constraints | Rejected |

## 3. Component Model

```text
file path or stdin
       |
       v
 InputSource -> LineParser -> Aggregator -> ReportSnapshot
                    |             |               |
                    v             |               v
             Parse diagnostics    |      Text / JSON / CSV renderer
                                  |               |
                                  +---------------+--> stdout
                           warnings/summary ----------> stderr
```

| Component | Proposed path | Responsibility |
|---|---|---|
| Click entry point | `src/nginx_log_report/cli.py` | Options, stream ownership, error-to-exit mapping |
| Record model | `src/nginx_log_report/models.py` | Frozen `AccessRecord` and immutable `ReportSnapshot` dataclasses |
| Parser | `src/nginx_log_report/parser.py` | Parse supported combined-format lines into typed records |
| Aggregator | `src/nginx_log_report/aggregate.py` | Update IP/error-URL counters, 24 hour buckets, request count, UA set |
| Renderers | `src/nginx_log_report/renderers/{text,json,csv}.py` | Pure snapshot-to-output transformations |
| Errors | `src/nginx_log_report/errors.py` | Domain exceptions and exit-code mapping |

The CLI reads bytes lazily with a fixed-size IO buffer. Parsing and aggregation happen once per line. Rendering happens only after successful EOF. The input is never loaded wholesale. Time complexity is `O(n + k log N)`, where `n` is lines, `k` is distinct counter keys, and `N` is `--top`; state is `O(unique IPs + unique error URLs + unique User-Agents + 24)` because the MVP requires exact results.

## 4. Data Model

No database tables, migrations, files, or persistent caches exist. The document-template table requirement is intentionally inapplicable because persistence is explicitly prohibited.

### `AccessRecord` dataclass

| Field | Python type | Constraint/meaning |
|---|---|---|
| `ip` | `bytes` | Non-empty client token; raw bytes preserve identity |
| `timestamp` | `datetime` | Offset-aware datetime parsed from nginx timestamp |
| `method` | `bytes` | Raw request method token; may be empty for request `-` |
| `url` | `bytes` | Raw request target; query string retained |
| `protocol` | `bytes` | Raw HTTP protocol token when present |
| `status` | `int` | Three-digit status, 100–599 |
| `user_agent` | `bytes` | Exact logged UA bytes; `-` normalizes to empty/unknown |

### `ReportSnapshot` dataclass

| Field | Python type | Constraint/meaning |
|---|---|---|
| `total_lines` | `int` | All input lines observed |
| `valid_requests` | `int` | Successfully parsed records |
| `malformed_lines` | `int` | Lines skipped by parser policy |
| `top_ips` | `tuple[RankedItem, ...]` | At most requested N, ordered by count desc then key asc |
| `top_error_urls` | `tuple[RankedItem, ...]` | Only statuses 400–599; same deterministic ordering |
| `hourly_requests` | `tuple[int, ...]` | Exactly 24 local-log-hour buckets, indices 0–23 |
| `unique_user_agents` | `int` | Count of distinct non-empty UA strings |
| `unique_user_agent_share` | `float` | `unique_user_agents / valid_requests * 100`; 0.0 when none valid |

### In-memory aggregates

| Structure | Key/value | Update rule |
|---|---|---|
| IP counter | `dict[bytes, int]` | Increment for every valid request |
| Error URL counter | `dict[bytes, int]` | Increment only for status 400–599 |
| Hour buckets | `list[int]` of length 24 | Increment `timestamp.hour` |
| User-Agent set | `set[bytes]` | Add each non-empty exact UA byte sequence |

## 5. Parsing Contract

The MVP supports nginx combined log format:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

- Delimiter parsing operates on raw bytes. Exact ranking/cardinality identity and tie ordering are defined over those bytes; decoding occurs only for presentation, so distinct invalid UTF-8 sequences never collapse.
- Quoted fields accept only `\\"` and `\\\\` escapes. Unescaped closing quotes delimit fields; extra trailing non-whitespace tokens, embedded NUL, invalid status/timestamp grammar, and lines over 1 MiB are malformed. CRLF and an incomplete final line are accepted after removing only the record terminator.
- A request of `"-"` has empty method/URL/protocol but remains a valid nginx record; it contributes to IP, hour, and UA but not error-URL ranking.
- Malformed lines are skipped and counted. Up to five examples, with line numbers and truncated content, are reported to stderr in human-readable mode; structured stdout remains valid.
- Timestamps retain their logged offset. Hourly distribution uses the hour written in each log record, not the machine timezone.
- Ties in top lists sort lexicographically by raw-byte key after descending count. Finalization uses a composite key such as `heapq.nsmallest(N, items, key=lambda item: (-item.count, item.key))`; it must not preselect tied items using insertion order.

## CLI Interface

### Command

```text
nginx-log-report [OPTIONS] [PATH]
```

`PATH` is an nginx access-log file. Omit it or pass `-` to read stdin. Exactly one input stream is processed per invocation.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one JSON document; mutually exclusive with `--csv` |
| `--csv` | flag, false | Emit RFC 4180 long-form CSV; mutually exclusive with `--json` |
| `--top N` | integer, `10` | Number of ranked IPs/error URLs; `1 <= N <= 1000` |
| `--format NAME` | choice, `combined` | MVP accepts only `combined`; reserves an explicit extension point |
| `--color / --no-color` | tri-state auto | Default auto enables color only for a terminal; `--color` forces it for text only |
| `--version` | flag | Print package version and exit |
| `--help` | flag | Print usage and exit |

JSON/CSV modes never include ANSI escape sequences. Diagnostics go to stderr. A regular file is opened read-only; stdin is never closed by application code.

### Default text output

Rich renders a title, input summary, two ranked tables, a 24-row hourly table/bar view, and a User-Agent summary. Counts and percentages are plain numeric values, colors convey emphasis only, and redirected stdout automatically becomes uncolored text.

### JSON output

```json
{
  "schema_version": 1,
  "meta": {"total_lines": 0, "valid_requests": 0, "malformed_lines": 0},
  "top_ips": [{"rank": 1, "ip": "192.0.2.1", "requests": 12}],
  "top_error_urls": [{"rank": 1, "url": "/missing", "errors": 4}],
  "hourly_requests": [{"hour": 0, "requests": 2}],
  "user_agents": {"unique": 3, "share_percent": 25.0}
}
```

All 24 hourly objects are emitted. JSON uses UTF-8, one trailing newline, and finite numeric values. Valid UTF-8 log bytes display normally. Invalid octets display deterministically as `<0xNN>` tokens; this is a stable display representation rather than a round-trip byte encoding. Ranking identity still uses raw bytes.

### CSV output

CSV always writes this header:

```csv
section,rank,key,value,percentage
```

Rows use `section` values `meta`, `top_ip`, `top_error_url`, `hour`, and `user_agent`. `key` contains the metric name, IP, URL, zero-padded hour (`00`–`23`), or `unique`; unused `rank`/`percentage` cells are empty. Fields are escaped by Python's `csv` module and records use RFC 4180 line endings.

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Report completed; malformed lines may have been skipped and are disclosed |
| 2 | Click usage/option error |
| 3 | Input cannot be opened/read |
| 4 | Input contains no valid log records; stdout is empty in every mode and stderr contains the summary |
| 130 | Interrupted by SIGINT before a complete report |

A downstream closed pipe is handled without a traceback and exits 0, matching normal Unix pipeline behavior. Unexpected internal failures exit 1 with a concise stderr message; `--json`/`--csv` stdout is not polluted by error text. Input read errors discovered after valid lines also produce no stdout because all rendering is deferred until successful EOF.

## 7. Output and Domain Semantics

- “Top IPs” ranks all valid requests by exact logged client address bytes.
- “Error URLs” includes response status 400 through 599 inclusive and ranks raw request-target bytes including query strings.
- “Hourly” means 24 buckets based on each record's nginx `time_local` hour.
- “Unique User-Agent share” is `(distinct non-empty UA byte sequences / valid requests) × 100`, rounded to two decimals only at rendering. This is a diversity ratio, not the share of requests having a UA; the label and help text must say so.
- Empty-but-valid input semantics are avoided: zero valid records produces exit 4 rather than a misleading zero report.

## 8. Error Handling and Security

Log content is untrusted data. It is never evaluated, passed to a shell, interpreted as Rich markup, or used as a path. One pure `sanitize_terminal(bytes) -> str` function is used for every log-derived Rich cell and stderr excerpt: decode valid UTF-8; render invalid octets as `<0xNN>`; render C0, DEL, C1, ESC, CR, LF, backspace, OSC/hyperlink introducers, and Unicode bidi controls as visible `\\u{XXXX}` tokens; and pass the result to Rich with markup disabled. JSON/CSV use their standard encoders plus the invalid-octet display mapping, never terminal presentation escaping. Excerpts are limited to 200 displayed code points. The process makes no network calls and collects no telemetry.

File errors and parse outcomes use the exit contract above. Empty or malformed-only input emits no stdout and exits 4. Memory exhaustion is caught at the command boundary and exits 1 with a concise resource message; unexpected exceptions also exit 1, with no partial report. Symlinks follow normal OS read behavior. The CLI does not elevate privileges and documentation warns against running it with unnecessary root access.

## 9. Performance Architecture

- One buffered sequential read and one parser pass; no `read()` of the full file.
- No Rich objects or rendered strings in the hot loop.
- `collections.Counter`/dict increments and a fixed 24-element list dominate aggregation.
- Top N is selected at finalization with the full composite order `(-count, raw_key)` so ties at the cutoff cannot depend on insertion order.
- Benchmark fixture generation is deterministic and outside the timed region.
- Acceptance uses a deterministic seed `20260802` corpus of exactly 1,000,000,000 bytes: 95% valid combined records and 5% malformed records; valid records cycle through every hour and status classes, with up to 100,000 distinct IPs, 250,000 distinct URLs, and 500,000 distinct User-Agents. Its generator version, SHA-256, line count, cardinalities, and expected snapshot SHA-256 are frozen in `tests/performance/corpus-manifest.json` before renderer work.
- Measurement uses Python 3.11, a warm local filesystem, three runs, median wall time under 30 seconds, and records peak RSS plus laptop CPU, RAM, OS, Python patch version, and storage details. The support envelope additionally requires peak RSS at or below 2.0 GiB on this reference corpus.
- A separate exactly 1,000,000,000-byte high-cardinality corpus freezes 1,000,000 distinct IPs, error URLs, and User-Agents and must finish without `MemoryError` at or below 3.0 GiB RSS; elapsed time is recorded but is not the 30-second gate. Inputs beyond these tested cardinalities remain best-effort and are documented as such.

If the time or memory envelope is missed, profile first. Permitted optimizations retain the single-process contract: raw-byte keys, faster field scanning, fewer allocations, larger buffer, and local variable binding. Multiprocessing or temporary spill is a post-MVP architectural reconsideration, not a silent optimization.

## 10. Packaging and Deployment

Deployment is a pip-installed local console application, not a hosted environment:

```text
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install .
nginx-log-report --help
```

`pyproject.toml` declares Python `>=3.11,<4`, Click, Rich, the `src/` package layout, and the `nginx-log-report` console script. No Docker, docker-compose, environment variables, daemon, system service, cloud resource, or Kubernetes manifest is required. Reproducible development uses a locked dev dependency set if chosen during implementation; the distributable remains ordinary wheel/sdist artifacts.

## 11. Testing Strategy

| Layer | Evidence |
|---|---|
| Parser unit tests | Valid combined lines, exact escape grammar, IPv4/IPv6, `-` request, raw-byte identity, length/NUL/trailing-token malformed cases |
| Aggregator unit tests | Status boundaries, ties, exact hours, empty UA, percentage calculation |
| Renderer golden tests | ANSI behavior, JSON schema/value types, RFC 4180 CSV quoting and row contract |
| Click integration tests | file/stdin, option conflicts, all exit codes, broken pipe, stderr separation |
| Property/fuzz tests (bounded) | Arbitrary log strings do not crash or execute markup/control behavior |
| Performance test | Frozen decimal 1 GB manifest, median under 30 seconds, <=2.0 GiB RSS; separate high-cardinality <=3.0 GiB RSS |
| Packaging smoke test | Build wheel, install cleanly, run console entry point |

## 12. Architecture Decision Record (ADR)

### ADR-001: Local stateless single process

- **Status:** Accepted and pre-approved.
- **Decision:** Use one Python process, streaming input, in-memory exact aggregates, and post-EOF rendering.
- **Consequences:** Minimal setup and deterministic behavior; aggregate memory grows with cardinality, and reports are not retained between runs.

### ADR-002: No database and no HTTP API

- **Status:** Accepted and pre-approved.
- **Decision:** **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- **Consequences:** Zero service operations and attack surface; persistence, dashboards, remote queries, and multi-user access are intentionally unavailable.

### ADR-003: Exact User-Agent diversity

- **Status:** Accepted for MVP.
- **Decision:** Track exact distinct non-empty User-Agent byte sequences and divide by valid request count.
- **Consequences:** Reproducible results but cardinality-dependent memory; approximate sketches are deferred until evidence requires them.

### Debate Summary

The architecture was reviewed under `.itd-plugin/agents/devils-advocate.md` against this document.

**Verdict:** APPROVE WITH CONDITIONS

**Challenges raised:**

1. Exact aggregation lacked a memory envelope. **Resolution:** Defined representative and high-cardinality corpora, 2.0/3.0 GiB RSS limits, tested cardinalities, and controlled `MemoryError` behavior.
2. Replacement decoding could merge distinct byte values. **Resolution:** Parsing and aggregation now use raw-byte identity; invalid bytes are mapped only at presentation.
3. The performance oracle was ambiguous. **Resolution:** Defined decimal 1 GB, seed/distribution/cardinalities, manifest/hash/expected snapshot, environment record, and timing method.
4. Count-only top-N could select ties nondeterministically. **Resolution:** Required composite `(-count, raw_key)` selection and corrected complexity to `O(k log N)`.
5. Terminal safety was asserted but underspecified. **Resolution:** Defined one sanitizer, exact control classes, invalid-byte mapping, excerpt limit, and Rich markup policy.
6. Zero-valid structured behavior was ambiguous. **Resolution:** Empty/malformed-only and late read failures now emit no stdout and have explicit exit behavior.

**Alternatives considered and rejected:**

- Temporary external sort/spill — preserves exactness at lower RAM but adds file lifecycle and disk failure modes inconsistent with weekend scope; reconsider only if the high-cardinality oracle fails.
- Approximate cardinality sketches — reduce memory but violate exact P0 User-Agent semantics.
- Multiprocessing — adds input partitioning and merge complexity without profiling evidence.

## 13. Traceability

Product scope and acceptance criteria are in [PRD.md](PRD.md). Delivery order and verification commands are in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). The implementation-session prompts in [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) treat this architecture as the technical source of truth.
