# Project Architecture: Nginx Stream Insights

## 1. Context and constraints

The product is a local Python 3.11 command-line program. One OS process reads a file or stdin sequentially, parses each nginx access-log record, updates in-memory aggregates, and renders one final report. The target is 1 GB in under 30 seconds on a documented laptop. There is no authentication, persistent data, network listener, cloud dependency, Docker requirement, or Kubernetes deployment.

The binding decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

- A database is incorrect here because the four outputs are aggregates of one input stream, persistence creates avoidable I/O and lifecycle costs, and users explicitly need local handling. Exact cardinality sets may consume memory proportional to unique values, but a database would not make the workflow stateless or faster by default.
- An HTTP API is incorrect because there are no remote clients, accounts, long-running jobs, or shared state. stdin/stdout, exit codes, JSON, and CSV already provide the integration contract expected by DevOps pipelines.

## 2. Architecture decision

### Chosen approach: single-process streaming pipeline

`Click command -> input iterator -> parser -> aggregator -> immutable report -> renderer -> stdout`

This obvious architecture is pre-approved. It minimizes copies and operational surface while keeping parsing, aggregation, and presentation independently testable.

### Alternatives considered and rejected

| Alternative | Benefit | Cost / reason rejected |
|---|---|---|
| Multi-process chunking | Potential CPU parallelism | Chunk boundaries complicate line safety and merging; startup and IPC costs are unjustified before profiling |
| Embedded SQLite staging | SQL aggregation and bounded Python objects | Adds disk I/O and persistence semantics to a one-pass local report |
| Go rewrite | Higher throughput ceiling | Violates the approved Python 3.11 stack and one-weekend constraint |
| Client/server service | Shared remote analysis | Adds authentication, API, deployment, and data-transfer risks with no approved user need |

## 3. Components and responsibilities

| Module | Responsibility | Key contract |
|---|---|---|
| `src/nginx_stream_insights/cli.py` | Click options, input selection, renderer selection, exit codes | Exactly one path argument or `-` for stdin; `--json` and `--csv` are mutually exclusive |
| `input.py` | Open binary streams and yield bounded lines without materializing the file | Strict UTF-8 per record, 1 MiB maximum record, and never closes caller-owned stdin |
| `parser.py` | Parse supported common/combined records | Returns `AccessRecord` or a structured malformed result; no unhandled per-line exception |
| `models.py` | Dataclasses for records, diagnostics, and final report | Presentation-independent, serializable values |
| `aggregate.py` | Update counters and finalize rankings/distributions | O(1) average update per valid record; deterministic tie-breaking |
| `renderers/terminal.py` | Rich default output | Color only when appropriate; human-readable sections |
| `renderers/json.py` | JSON document output | Stable keys and JSON only on stdout |
| `renderers/csv.py` | Normalized CSV output | Stable header and section-labelled rows |

## 4. Domain data model

These are in-memory dataclasses, not database tables.

### `AccessRecord`

| Field | Python type | Rule |
|---|---|---|
| `client_ip` | `str` | Non-empty parsed token; IPv4/IPv6 kept as text |
| `timestamp` | `datetime` | Timezone-aware nginx timestamp |
| `method` | `str | None` | Request method, or `None` for an unparsable request field |
| `url` | `str` | Request target as logged; query-string policy must remain consistent |
| `status` | `int` | 100–599 accepted; 4xx and 5xx feed error ranking |
| `user_agent` | `str | None` | Combined-format value; absent in common format |

### `AnalysisReport`

| Field | Python type | Meaning |
|---|---|---|
| `total_requests` | `int` | Valid parsed records |
| `malformed_lines` | `int` | Rejected records |
| `top_ips` | `tuple[RankedCount, ...]` | At most 10, count descending then key ascending |
| `top_error_urls` | `tuple[RankedCount, ...]` | At most 10 URLs among 4xx/5xx records |
| `hourly_requests` | `tuple[HourlyCount, ...]` | Hours 00–23, including zero-count hours |
| `unique_user_agents` | `int` | Count of distinct present User-Agent strings |
| `user_agent_observations` | `int` | Valid records that contain User-Agent |
| `unique_user_agent_share` | `float` | `unique_user_agents / user_agent_observations`, or `0.0` when denominator is zero |

## 5. Streaming and complexity model

The parser consumes one line at a time. Aggregation uses `Counter` objects for IPs and error URLs, a fixed 24-element hourly counter, and a `set` for exact User-Agent uniqueness. Finalization uses `heapq.nsmallest`/`nlargest` or sorting after profiling; rankings must be deterministic.

- Time: O(n) parsing and updates, plus O(k log 10) ranking for k distinct ranked keys.
- Memory: O(i + u + a), where i is distinct IPs, u is distinct error URLs, and a is distinct User-Agents; it is independent of input byte size but not cardinality.
- Backpressure: synchronous iteration naturally limits reading to processing speed.
- Parallelism: none in MVP. Profile first; preserve the simple merge-free path unless measured evidence demands change.

## 6. CLI contract (the only public interface)

```text
nginx-stream-insights [OPTIONS] LOG_PATH

LOG_PATH                 File path, or - for stdin
--json                   Emit one JSON document
--csv                    Emit normalized CSV rows
--no-color               Disable terminal color
--version                Print version and exit
--help                   Print help and exit
```

`--json` and `--csv` are mutually exclusive. Data is written to stdout; diagnostics and malformed-line summaries that are not part of a machine schema go to stderr. Success is exit 0, Click usage errors exit 2, and input/processing/output failures exit 1. A downstream broken pipe exits 0 quietly without a traceback. No endpoint catalogue exists because there is no HTTP API.

Before the first JSON/CSV stdout write, serialize the bounded final report completely so an internal serialization failure cannot leave a partial machine document. Expected errors never show a traceback.

| Failure | Exit | stdout | stderr |
|---|---:|---|---|
| Invalid options or missing path | 2 | Empty | Click usage message |
| Cannot open/read input, including mid-stream read failure | 1 | Empty | Concise path/context message |
| All or some records malformed | 0 | Complete selected report | Summary only where not already represented by schema |
| Internal aggregation/render failure | 1 | Empty for JSON/CSV | Concise error; traceback only in developer diagnostics |
| Non-broken-pipe stdout write/encoding failure | 1 | May be partial only for terminal mode | Concise error where stderr remains writable |
| Downstream closes pipe (`BrokenPipeError`) | 0 | Prefix consumed downstream | Empty; no traceback |

## 7. Output schemas

### JSON

One UTF-8 object terminated by `\n`, with this canonical shape and insertion order. `schema_version` is the string `"1.0"`; counts are integers; `unique_share` is a JSON number rounded to six decimal places in the closed interval 0–1. Consumers must ignore unknown additive fields within the same major version. Removing or renaming fields, or changing their types, requires a new major version.

```json
{
  "schema_version": "1.0",
  "total_requests": 1,
  "malformed_lines": 0,
  "top_ips": [{"rank": 1, "value": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"rank": 1, "value": "/missing", "count": 1}],
  "hourly_requests": [{"hour": 0, "count": 0}, {"hour": 1, "count": 1}],
  "user_agents": {"unique": 1, "observations": 1, "unique_share": 1.0}
}
```

The example abbreviates hours 02–23 only for readability; actual output always contains 24 ascending hourly entries. Ranking arrays use rank ascending.

### CSV

UTF-8, RFC-4180-style CSV with `\n` record terminators and one header: `schema_version,section,rank,key,count,share`. Every row uses schema version `1.0`. Rows are ordered: ranked IPs, ranked error URLs, hours 00–23, then the User-Agent summary. Unused cells are empty; `share` uses six decimal places; CSV is generated with the standard library to ensure correct quoting.

```csv
schema_version,section,rank,key,count,share
1.0,top_ip,1,192.0.2.1,1,
1.0,top_error_url,1,/missing,1,
1.0,hour,,00,0,
1.0,hour,,01,1,
1.0,user_agent_summary,,unique,1,
1.0,user_agent_summary,,observations,1,
1.0,user_agent_summary,,unique_share,,1.000000
```

The example abbreviates hours 02–23 only for readability. Empty input has no ranking rows, 24 zero-valued hour rows, and the three zero-valued User-Agent rows.

### Terminal

Rich tables present four named sections and a parsed/malformed summary. Color never changes semantic content and is disabled for non-TTY output or `--no-color`.

## 8. Parsing and error policy

- Support documented nginx common and combined access-log forms for MVP. Accept LF or CRLF and IPv4/IPv6 client tokens; require the expected token count and reject trailing tokens.
- Read bytes with a 1 MiB per-record limit, then decode each record as strict UTF-8. Invalid UTF-8 and oversized records are each one malformed line, preserving aggregate key identity without lossy replacement.
- Inside quoted fields, support nginx-style `\\`, `\"`, and `\xHH` escapes. Reject invalid escapes, timestamps, and status codes; accept a `"-"` request field as a valid record with `method=None` and `url="-"`, excluded from error-URL ranking.
- Parse from stable delimiters and bounded operations; avoid catastrophic regular expressions.
- Treat malformed records as data-quality events: increment the count and continue.
- Fail when the input cannot be opened/read or an internal invariant is violated.
- Empty input is valid and produces zero-valued sections.
- Timestamps retain their logged timezone; hourly distribution groups by logged local hour.
- The full request target, including query string, is the URL ranking key for MVP; document this privacy/cardinality trade-off.

## 9. Security and privacy

Logs may contain IP addresses, URLs, tokens in query strings, referrers, and User-Agents. The program performs no network access and writes only the selected report. It must not echo raw malformed lines by default. Documentation warns users that JSON/CSV reports can still contain sensitive aggregate keys. File paths are treated as data, subprocesses are not invoked, and Rich markup is escaped for log-derived values.

Authentication is not applicable: the operating-system user and filesystem permissions define the trust boundary. There is no login flow, token, secret, or role model.

## 10. Configuration and environment

There are no required environment variables and no `.env` file. Locale-independent UTF-8 machine output is part of the contract. Optional conventional variables such as `NO_COLOR` may be honored only if documented and tested; CLI flags take precedence.

## 11. Packaging and deployment

Deployment means installation into a local Python 3.11 environment with pip. `pyproject.toml` exposes the `nginx-stream-insights` console script. Wheels and source distributions are the only release artifacts. Docker, docker-compose, a server process, cloud resources, and Kubernetes manifests are intentionally absent.

## 12. Performance verification

The repository will include a versioned deterministic fixture generator outside product runtime. Benchmark profile `baseline-v1` uses seed `20260716`, exactly 1,000,000,000 bytes, 90% combined and 10% common records, 1% malformed records, 150–2048-byte line lengths, 100,000 distinct IPs, 50,000 distinct error URLs, and 25,000 distinct User-Agents. Expected aggregates are generated independently and checked before timing.

The reference envelope is Linux/WSL on a laptop with at least four physical x86-64 cores, 16 GB RAM, NVMe storage, and CPython 3.11. Acceptance requires three explicitly warm-cache runs with median wall time below 30 seconds and peak RSS below 250 MB; one cold-cache-qualified run is also reported but is diagnostic, not a pass gate. Metadata records generator version/seed, CPU, RAM, storage, OS, Python, cache state, input bytes/lines/cardinalities, valid/malformed counts, wall time, and peak RSS.

Exact-mode memory support is additionally tested with `cardinality-v1`: up to 1,000,000 distinct IPs, 250,000 distinct error URLs, and 250,000 distinct User-Agents within 750 MB peak RSS. Above this tested envelope, results remain exact if resources permit. A caught `MemoryError` produces no JSON/CSV report, a concise stderr explanation, and exit 1. Approximate counting is not an implicit fallback and would require a future opt-in PRD/ADR change.

## 13. Architecture Decision Record (ADR)

### ADR-001: Local single-process streaming CLI

- **Status:** Accepted (pre-approved)
- **Decision:** Use the pipeline in section 2 with exact in-memory aggregation.
- **Drivers:** one-weekend delivery, $0 budget, local privacy, pip distribution, 1 GB/30 s target.
- **Consequences:** minimal operations and deterministic behavior; memory grows with distinct keys and scale-up requires profiling rather than horizontal deployment.

### Debate summary

The architecture was reviewed by the repository-local Devil's Advocate agent.

**Verdict:** APPROVE WITH CONDITIONS

**Challenges raised and resolutions:**

1. Performance evidence was not reproducible. **Resolution:** section 12 now fixes generator seed/version, exact bytes, format mix, cardinalities, reference hardware, cache qualification, wall-time gate, and peak-RSS gate.
2. Exact aggregation lacked a supported memory envelope. **Resolution:** section 12 adds a high-cardinality profile, 750 MB tested ceiling, controlled `MemoryError` behavior, and forbids silent approximation.
3. Decoding and parsing could collapse invalid identities or admit unbounded lines. **Resolution:** sections 3 and 8 now require binary bounded reads, strict UTF-8, a 1 MiB limit, explicit escapes, and acceptance/rejection rules.
4. JSON/CSV schemas were underspecified. **Resolution:** section 7 now provides literal types, ordering, precision, empty-input behavior, compatibility policy, and canonical examples.
5. Stream-boundary failures were ambiguous. **Resolution:** section 6 now defines an exception/exit/output matrix, pre-serialization for machine modes, and broken-pipe behavior.

**Alternatives considered and rejected:** multi-process chunking, embedded SQLite, a Go rewrite, and a client/server service remain rejected because the review found no fundamental architecture change warranted; tighter contracts address every condition.

See `PRD.md` for acceptance behavior and `IMPLEMENTATION_PLAN.md` for file-by-file delivery.
