# Project Architecture: Nginx Stream Analytics CLI

## 1. Context and Constraints

This is a single-user, local Python 3.11 command-line program for nginx combined access logs. It must process a 1 GB log in under 30 seconds on a documented laptop, install through pip, remain open source at $0 infrastructure cost, and ship in one weekend. It has no authentication, database, HTTP API, server, cloud component, or Kubernetes deployment.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the requested summaries can be accumulated during a single sequential read; persistence would add I/O, schema lifecycle, cleanup, and privacy exposure without improving the one-shot task. An HTTP API is incorrect because the user and data are local, stdin/file composition is the integration boundary, and a listening service would introduce authentication, deployment, and operational work outside the product goal.

## 2. Architecture Variants

### Variant A: Single-process exact streaming pipeline (selected)

- **Approach:** one process reads bytes/text sequentially, parses each record, updates exact in-memory aggregates, then renders once.
- **Pros:** simplest install and operation; exact results; no intermediate files; natural stdin support.
- **Cons:** memory is O(unique IPs + unique error URLs + unique User-Agents); CPU remains single-core.
- **Best for:** incident-scale local logs and the one-weekend MVP.
- **Estimated complexity:** Low.

### Variant B: Chunked multiprocessing

- **Approach:** split seekable files into newline-aligned chunks, aggregate in workers, and merge maps.
- **Pros:** can use multiple CPU cores on very large regular files.
- **Cons:** complicates stdin, quoted-record boundaries, deterministic errors, memory, and packaging; process startup/merge overhead may erase gains.
- **Best for:** a measured CPU bottleneck after the MVP.
- **Estimated complexity:** Medium.

### Variant C: External-sort/SQLite-backed aggregation

- **Approach:** spill keys or counts to disk and reduce after ingestion.
- **Pros:** bounds RAM for extreme cardinality.
- **Cons:** violates the approved no-database/stateless design in the SQLite form, adds disk amplification and cleanup, and threatens the time target.
- **Best for:** a future separate mode with proven high-cardinality demand.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the architecture is pre-approved, has the fewest moving parts, supports stdin identically to files, and directly matches the delivery and operating constraints. Variant B is reserved for evidence-driven optimization; Variant C is rejected for the MVP.

## 3. System Context

```text
nginx access log file ─┐
                       ├─> Click CLI -> streaming parser -> aggregator -> renderer -> stdout
stdin / pipe ──────────┘                                  │
                                                         └──────────────> stderr diagnostics
```

Input is untrusted local text. Stdout is exclusively the selected report format. Diagnostics go to stderr so JSON and CSV stdout remain machine-readable. Exit status is the automation control surface.

## 4. Component and File Design

```text
src/nginx_stream_analytics/
├── __init__.py          package version
├── cli.py               Click command, options, streams, exit codes
├── models.py            dataclasses for parsed records, counters, report
├── parser.py            combined-log parser and timestamp normalization
├── aggregate.py         one-pass exact aggregate updates and top-k ordering
└── renderers/
    ├── __init__.py      renderer selection contract
    ├── terminal.py      Rich tables and TTY-aware color
    ├── json.py          versioned JSON document
    └── csv.py           normalized CSV rows
tests/
├── fixtures/            small valid/malformed log samples and golden outputs
├── test_parser.py
├── test_aggregate.py
├── test_cli.py
└── test_renderers.py
benchmarks/
├── generate_log.py      deterministic synthetic combined-log generator
└── benchmark.md         reference hardware, commands, time, peak RSS
```

Dependencies flow inward: `cli` composes parser, aggregator, and renderers; renderers consume immutable report dataclasses; parsing and aggregation never import Click or Rich.

## 5. Runtime Data Model

There are intentionally no database tables or migrations. The complete ephemeral model is:

| Dataclass/state | Fields and types | Invariant |
|---|---|---|
| `AccessRecord` | `ip: str`, `hour: int`, `method: str \| None`, `target: str \| None`, `status: int`, `user_agent: str` | Reference/test representation; the production hot path passes fields directly to aggregation and does not allocate this dataclass per line |
| `AggregateState` | `total_requests: int`, `skipped_lines: int`, `unique_keys: int`, `ip_counts: dict[str,int]`, `error_url_counts: dict[str,int]`, `hour_counts: list[int]` (24 entries), `user_agents: set[str]` | Updated once per parsed record; error map only includes status 400–599 with a target; empty UA excluded; unique insertions cannot exceed the configured guard |
| `RankedItem` | `value: str`, `count: int` | Top lists sort by count descending, then value ascending |
| `Report` | `schema_version: str`, `source: str`, `total_lines: int`, `parsed_requests: int`, `skipped_lines: int`, `top_ips: tuple[RankedItem,...]`, `top_error_urls: tuple[RankedItem,...]`, `hourly_requests: tuple[int,...]`, `unique_user_agents: int`, `unique_user_agent_share: float` | Immutable rendering boundary |

`unique_user_agent_share = unique non-empty User-Agent strings / parsed_requests × 100`; it is `0.0` for zero parsed requests. “Exact” means exact decoded Unicode values from valid UTF-8 after the specified nginx escape decoding. URL ranking uses the decoded request target, including query string, without path normalization; a future option may group by path.

## 6. Input Contract and Parsing

MVP input is the standard nginx combined format:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

- Accept one optional `LOGFILE` argument; `-` or omission means stdin.
- Read binary lines and decode each line as strict UTF-8. Invalid UTF-8 makes only that line malformed in default mode and triggers the normal first-error behavior in strict mode; different invalid byte sequences therefore cannot collapse into one “exact” key.
- Parse quoted/bracketed fields with an allocation-conscious scanner or a precompiled anchored expression proven by the benchmark. Accept nginx combined-format `\\\\`, `\\\"`, and `\\xHH` escapes and decode them once; reject incomplete or unknown escapes.
- Extract method and target from the request field. The conventional request value `"-"` remains a parsed request for IP/hour/User-Agent totals but has no method/target and never enters error-URL ranking. Other malformed request/status/timestamp fields make the line malformed.
- Bucket by the hour (`00`–`23`) present in the log timestamp; preserve the numeric offset but do not convert time zones.
- Default behavior skips malformed lines and reports their count. `--strict` stops at the first malformed line with exit 2.
- Read line-by-line with bounded buffering; never call `read()` for the full file or retain `AccessRecord` instances.
- Validate timestamp grammar but extract its two hour digits directly. Do not construct `datetime` or `AccessRecord` objects in the production loop.

## 7. Aggregation and Complexity

Each parsed record performs constant-time average updates. After the stream, top tens use `heapq.nsmallest`/`nlargest` or a bounded heap with a deterministic secondary key; do not sort the whole map merely for ten results unless benchmarks show no material cost.

- Time: O(n + u log 10), where `n` is lines and `u` is unique ranked keys.
- Memory: O(i + e + a), where `i` is unique IPs, `e` unique error targets, and `a` unique non-empty User-Agent strings.
- Hour buckets are fixed at 24 integers.

The word “streaming” applies to records, not approximate cardinality. Exact distinct User-Agents necessarily retain unique strings. The default `--max-unique 250000` guard counts first insertions across all three unbounded structures and exits 1 before inserting key 250,001; users may lower or explicitly raise it according to available RAM. The supported MVP envelope is a 1 GB file with at most 250,000 combined unique aggregate keys and peak RSS below 250 MB on the reference corpus. The benchmark includes a fixture at the guard boundary. A future approximate mode may broaden that envelope, but exact mode never degrades silently.

## 8. CLI Contract

```text
nginx-stats [OPTIONS] [LOGFILE]

Options:
  --json          emit one JSON document
  --csv           emit normalized CSV rows
  --strict        fail on the first malformed record
  --max-unique N  maximum combined unique aggregate keys [default: 250000]
  --no-color      disable terminal color
  --version       show version and exit
  --help          show help and exit
```

`--json` and `--csv` are mutually exclusive. `--no-color` affects only terminal mode. Color is automatically disabled if stdout is not a TTY or `NO_COLOR` is set.

Exit codes:

| Code | Meaning |
|---:|---|
| 0 | Report produced, including when some lines were skipped in non-strict mode |
| 1 | File/open/read, unique-key guard, serialization, or non-EPIPE stdout write error |
| 2 | CLI usage error or malformed line in strict mode |

## 9. Output Schemas

### Terminal

Rich renders four labeled tables/sections plus a summary with parsed and skipped counts. Counts are right-aligned; 4xx/5xx rows are visually distinct; output remains readable with color disabled.

### JSON

One UTF-8 object followed by a newline:

```json
{
  "schema_version": "1.0",
  "source": "access.log",
  "summary": {"total_lines": 100, "parsed_requests": 98, "skipped_lines": 2},
  "top_ips": [{"ip": "192.0.2.1", "count": 12}],
  "top_error_urls": [{"url": "/missing", "count": 4}],
  "hourly_requests": [{"hour": "00", "count": 3}],
  "user_agents": {"unique_count": 7, "share_percent": 7.142857}
}
```

All 24 hours are present in ascending order. Top lists have at most ten items. Numeric values remain numeric; ordering is deterministic.

### CSV

CSV uses columns `schema_version,metric,rank,key,count,value`. It emits summary rows, ranked `top_ip`/`top_error_url` rows, 24 `hourly_requests` rows, and `unique_user_agents` plus `unique_user_agent_share` rows. Non-applicable cells are empty; RFC 4180 quoting is delegated to Python’s `csv` module.

## 10. API, Authentication, Database, and Deployment Decisions

- **HTTP API endpoints:** none. The complete programmatic interfaces are stdin, stdout, stderr, and exit codes described above.
- **Authentication flow:** none. The program opens only a user-supplied local file or inherited stdin and acquires no additional privilege.
- **Database:** none. All state has process lifetime and is discarded after rendering.
- **Environment variables:** only standard `NO_COLOR` is recognized; there are no secrets or required `.env` values.
- **Docker/Compose:** intentionally absent. Pip installation into a Python 3.11 environment is the deployment model; containers would add no value to local file/stdin access.
- **Cloud/Kubernetes/server:** not applicable and prohibited by scope.

Distribution uses a PEP 517 `pyproject.toml`, a locked lower/upper dependency policy, a console script named `nginx-stats`, and source/wheel artifacts published to PyPI when release credentials are available. Local editable installation is the development path.

## 11. Performance Architecture

The performance gate is wall-clock under 30 seconds for a deterministic 1 GB fixture on a named reference laptop. The benchmark records Python version, CPU, storage, OS, fixture seed/profile, wall time, and peak RSS. It runs from a warmed filesystem cache and a cold-cache run is reported separately, because disk performance otherwise makes results irreproducible.

Design rules:

- Compile parsing machinery once.
- Bind hot-path functions/state locally where profiling validates benefit.
- Do no Rich work before aggregation completes.
- Do not materialize input, intermediate lists, or per-record dataclasses beyond the current iteration.
- Measure with `/usr/bin/time -v`; use `cProfile` only if the gate fails.
- Preserve correctness tests before accepting parser micro-optimizations.

## 12. Security and Reliability

- Treat log fields as data: Rich markup is disabled/escaped, CSV uses the standard writer, and JSON uses the standard encoder.
- Before terminal rendering only, replace ESC, C0/C1 controls, carriage returns, newlines, and tabs with visible escaped forms; JSON and CSV preserve valid Unicode values under their standard encoders/writers.
- Prefix CSV cells beginning with `=`, `+`, `-`, or `@` when a spreadsheet-safe mode is introduced; for MVP, document CSV as machine data and test exact preservation.
- Do not follow secondary paths or URLs found in logs.
- Avoid catastrophic regex patterns; include long-field adversarial tests.
- `BrokenPipeError`/EPIPE from an intentionally closed downstream consumer terminates quietly with exit 0 and no traceback. Any other serialization or stdout write failure exits 1. JSON is fully serialized before its sole write; CSV may already have emitted complete rows before a later write failure, so exit status remains authoritative.
- File errors name the path but never echo log contents.
- Deterministic output enables golden tests and reproducible pipelines.

## 13. Architecture Decision Record (ADR)

### ADR-001: Exact, single-process, stateless pipeline

- **Status:** Accepted.
- **Decision:** Use Variant A with exact in-memory aggregate maps and a single sequential reader.
- **Drivers:** one-weekend delivery, local stdin/file workflows, exact required outputs, zero operational budget.
- **Consequences:** minimal operation and exact results; memory grows with cardinality and parallel CPU is unused.
- **Revisit when:** a reproducible corpus fails either the 30-second or peak-memory gate after profiling.

### ADR-002: CLI formats are the integration API

- **Status:** Accepted.
- **Decision:** version JSON and CSV schemas, isolate diagnostics on stderr, and expose stable exit codes.
- **Consequences:** pipelines need no service; schema changes require compatibility discipline.

### Debate Summary

The architecture was reviewed by the repository-local Devil’s Advocate agent.

**Verdict:** APPROVE WITH CONDITIONS; all five conditions were resolved in this revision.

**Challenges raised:**

1. Per-line dataclass/datetime allocation threatened the 1 GB/30 s gate. **Resolution:** the production loop extracts the hour and directly updates aggregates; it creates neither object, and benchmark evidence remains a release gate.
2. Exact maps had no explicit resource envelope or predictable failure. **Resolution:** the MVP defines a 250,000 combined-unique-key default guard, a <250 MB reference envelope, exit 1 on guard breach, and a boundary benchmark.
3. UTF-8 replacement could collapse different invalid byte strings and request escaping was vague. **Resolution:** invalid UTF-8 is malformed, supported nginx escape forms are explicit, and exactness is defined over valid decoded Unicode after escape decoding.
4. Rich markup escaping did not address terminal control sequences. **Resolution:** terminal-only visible control escaping is required and adversarial golden tests cover it.
5. Broken-pipe and other output failures were conflated. **Resolution:** EPIPE is quiet exit 0; serialization and other writes fail with exit 1; JSON is serialized before writing.

**Alternatives considered and rejected:** multiprocessing adds stdin and merge complexity before a measured need; disk/SQLite spilling violates the approved stateless/no-database constraint; replacement-decoded invalid UTF-8 cannot support the promised exact identity semantics.

## 14. Traceability

Product behavior and acceptance criteria live in [PRD.md](PRD.md). Delivery order and verification commands live in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Scope, budget, and success gates live in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md).
