# Project Architecture: nginx-stream-report

## Context and Constraints

The product is a Python 3.11 command-line program installed with pip and run on a local finite stream. The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the required report can be accumulated in one pass, persistence would retain potentially sensitive log data, and storage setup would violate the $0/weekend/local constraints. An HTTP API is incorrect because there are no remote consumers, authentication needs, or server lifecycle; stdin/stdout and stable exit codes already provide the required automation boundary.

The process is single-threaded and single-process for the MVP. It holds exact counters for IPs, error URLs, hours, and User-Agent cardinality, with a configurable hard ceiling on distinct keys. It never buffers the full input.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended)

- **Approach:** one Click process opens a path or stdin, parses each line, updates in-memory dataclass aggregators, and renders once at EOF.
- **Pros:** minimal moving parts, predictable ordering, easy profiling, no serialization overhead.
- **Cons:** one CPU core; exact distinct-key state grows with input cardinality until its guard trips.
- **Best for:** finite local nginx logs up to and beyond the 1 GB target.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunk aggregation

- **Approach:** split seekable files into newline-aligned byte ranges, aggregate in workers, merge maps.
- **Pros:** may use multiple CPU cores on very large regular files.
- **Cons:** cannot naturally handle stdin, complicates quoting-boundary correctness and deterministic failures, raises peak memory, and exceeds weekend scope.
- **Best for:** a later measured CPU bottleneck on multi-gigabyte seekable files.
- **Estimated complexity:** Medium.

### Variant C: Embedded analytical database

- **Approach:** ingest records into an embedded engine and query metrics.
- **Pros:** flexible follow-up queries.
- **Cons:** ingestion/storage overhead, disk writes, larger dependency and data-retention surface.
- **Best for:** exploratory analytics beyond the fixed report, which is out of scope.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the product decisions explicitly approve an obvious single-process architecture and the four fixed aggregations need no persistence. Variant B remains a profiling-triggered future option; Variant C contradicts the stateless contract.

## Component Design

```text
path or stdin
     |
     v
Input opener -> line iterator -> combined-log parser -> AggregateState
                                                        |  |  |  |
                                                        v  v  v  v
                                                   IP/error/hour/UA
                                                        |
                                                        v
                                              text | JSON | CSV renderer
                                                        |
                                                        v
                                                   stdout/stderr
```

Planned modules:

| Path | Responsibility |
|---|---|
| `src/nginx_stream_report/cli.py` | Click command, option validation, exception-to-exit mapping |
| `src/nginx_stream_report/input.py` | File/stdin opening and UTF-8 decoding policy |
| `src/nginx_stream_report/parser.py` | Compiled combined-log parser and timestamp normalization |
| `src/nginx_stream_report/models.py` | Frozen parsed-record and mutable aggregate dataclasses |
| `src/nginx_stream_report/aggregate.py` | Single-pass updates, top-k derivation, percentages, limits |
| `src/nginx_stream_report/render.py` | Rich text, JSON, and CSV serialization |
| `src/nginx_stream_report/errors.py` | Typed domain errors and canonical exit codes |

Processing is O(n + k log 10) time, where n is lines and k is distinct tracked keys, and O(k) memory subject to both entry and retained-byte budgets. Final ranking uses a size-10 heap/partial selection and sorts only the selected rows; the comparison key preserves count descending then key ascending determinism.

## Data Model and Streaming State

There are no database tables, migrations, indexes, or persistent records. The template's database inventory is intentionally not applicable because persistence violates the chosen architecture.

| Dataclass/state | Fields | Invariant |
|---|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `request_target: str`, `status: int`, `user_agent: str` | Created only from a valid combined-log line |
| `AggregateState` | `total_valid_requests: int`, `invalid_lines: int`, `ip_counts: Counter[str]`, `error_url_counts: Counter[str]`, `hour_counts: list[int]`, `user_agents: set[str]`, `estimated_key_bytes: int` | Hour list has exactly 24 positions; totals update atomically per record |
| `Report` | ranked IP/error rows, hourly rows, `unique_user_agent_count`, `unique_user_agent_share`, totals | Immutable rendering boundary; ordering is deterministic |

The User-Agent metric is exact: `100 × unique_user_agent_count / total_valid_requests`, where `unique_user_agent_count` is the number of distinct User-Agent strings among valid requests. Empty input produces 0.0%, not division by zero.

`AggregateState.add(record)` is a two-phase operation. It first derives every applicable key and preflights all prospective insertions against per-dimension entry ceilings and the shared retained-key budget. Only if every check succeeds does it update the total, hour, IP, error-URL, and User-Agent structures. A rejected record leaves the entire state unchanged. Tests must exercise a record that fits two dimensions but exhausts the third.

Before any new distinct IP, error URL, or User-Agent would exceed `--max-unique` or the shared `--max-key-bytes` estimate, processing stops with exit code 4 and emits no partial report. The conservative estimate adds each key's UTF-8 byte length plus 192 bytes per new mapping/set entry. Defaults allow at most 100,000 distinct keys per dimension and 32 MiB of estimated retained key state across dimensions. A 64 KiB physical-line ceiling prevents a single record from creating an unbounded buffer. These defaults are provisional release limits: the adversarial benchmark must demonstrate peak RSS below 256 MiB; if it does not, defaults are reduced rather than weakening the bound.

Hourly request distribution is a percentage for each local hour parsed from the nginx timestamp: `100 × hourly_request_count / total_valid_requests`. All 24 hours are emitted, zero-filled, and percentages are rendered with two decimal places; empty input yields 0.00% for every hour.

## CLI Interface

### Commands

```text
nginx-stream-report [OPTIONS] [PATH]
nginx-stream-report --help
nginx-stream-report --version
```

With no `PATH` or with `PATH` equal to `-`, input is read from stdin. One regular file is accepted; directories and multiple paths are rejected. Version 1 supports nginx combined-log format in UTF-8 with replacement disabled.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit one UTF-8 JSON object; mutually exclusive with `--csv` |
| `--csv` | false | Emit UTF-8 CSV rows with header `section,rank,key,count,percentage`; mutually exclusive with `--json` |
| `--no-color` | false | Disable color in text mode; JSON/CSV never contain ANSI codes |
| `--strict` | false | Stop on the first malformed line with exit 3; otherwise count and skip malformed lines |
| `--max-unique INTEGER` | `100000` | Positive ceiling applied independently to distinct IP, error URL, and User-Agent keys |
| `--max-key-bytes INTEGER` | `33554432` | Positive shared estimate ceiling for retained distinct-key state |
| `--max-line-bytes INTEGER` | `65536` | Positive physical-line byte ceiling; oversized lines follow malformed-line policy |
| `--version` | n/a | Print version and exit 0 |
| `--help` | n/a | Print help and exit 0 |

### Inputs

Input is consumed by a bounded binary line iterator, then each line is decoded as strict UTF-8 and matched to nginx combined format. Invalid UTF-8 and oversized lines are malformed records: permissive mode skips and counts them, while `--strict` exits 3. Filesystem/read failures remain exit 1. The request target is derived from the request field without URL decoding; absent request/User-Agent markers (`-`) are retained as literal values. Statuses 400–599 contribute to the error-URL ranking. A final line without newline is accepted.

### Outputs

Text mode writes four Rich sections to stdout and a malformed-line warning to stderr. Color is enabled only when stdout is a TTY and `NO_COLOR` is absent. JSON keys are `schema_version`, `total_valid_requests`, `invalid_lines`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`; ranked values contain explicit counts and percentages. CSV emits one normalized table; `section` is one of `top_ip`, `error_url`, `hour`, `user_agent_summary`. Top lists contain at most 10 rows.

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Successful report, including an empty valid stream or permissively skipped malformed lines |
| 1 | Runtime or I/O failure such as missing/unreadable input or broken read |
| 2 | Click usage error, invalid option/value, or mutually exclusive output flags |
| 3 | Input-format failure in strict mode |
| 4 | Unique-cardinality exhaustion: a distinct-key ceiling would be exceeded |

stdout contains a complete report only for exit 0. Diagnostics go to stderr. Broken downstream pipes terminate quietly according to the platform convention and do not print a traceback.

## Error and Security Boundaries

Log fields are untrusted data. Before display or serialization, a shared output-safety function converts C0/C1 controls, DEL, ESC, carriage return, newline, and bidi override/isolate controls to visible `\\uXXXX` escapes. Rich markup is then escaped; JSON uses the standard encoder and CSV uses `csv.writer`. Thus no raw field can inject an ANSI sequence, overwrite a terminal line, or create an extra CSV row. The escaped representation is intentionally safe rather than byte-identical; counts still group by the original decoded value. No field is executed, interpolated into a shell, or interpreted as terminal style. The CLI does not follow network URLs. Path access uses ordinary caller permissions. It stores no logs, telemetry, configuration, credentials, or cache.

## Performance Contract

The authoritative baseline is an Intel Core i7-1165G7 laptop (4 cores/8 threads), 16 GiB RAM, Ubuntu 24.04 x86-64, and CPython 3.11.9. `bench/generate_log.py --bytes 1073741824 --seed 20260804 --unique-ips 50000 --unique-urls 50000 --unique-user-agents 50000 bench/access-1g.log` creates the deterministic combined-log fixture with key lengths capped by the production line limit. After one unmeasured cache-warming read, run `/usr/bin/time -f 'elapsed=%e maxrss=%M' nginx-stream-report --json bench/access-1g.log >/dev/null` three times. The release gate is median elapsed wall time below 30.0 seconds and worst observed peak RSS below 262144 KiB. Record OS/kernel, exact Python patch, package commit, commands, and all three observations in `bench/README.md`. The benchmark is a future acceptance oracle, not a current performance claim. Profiling must confirm line parsing and counter updates dominate; multiprocessing is considered only after evidence shows the single-process design cannot meet the target.

## Packaging and Deployment

The deployment target is a local Python 3.11 virtual environment installed through pip from an sdist or wheel. `pyproject.toml` exposes the `nginx-stream-report` console script. There is no Docker Compose, image, server, cloud resource, or Kubernetes manifest; adding them would create unsupported deployment modes. Runtime environment variables are limited to standard `NO_COLOR`; all product settings are CLI options.

P1 gzip support extends the `InputSource` abstraction with streaming `gzip.open` only for paths ending in `.gz`; gzip autodetection and compressed stdin are not supported. Operators may use `gzip -dc file.gz | nginx-stream-report -`. Decompressed lines remain subject to `--max-line-bytes`, all aggregation budgets remain unchanged, and corrupt/truncated gzip streams exit 1 without a report.

## Authentication and API

Authentication is not applicable: the process acts with the invoking user's local filesystem permissions and has no identity boundary. There are no API endpoints, methods, request bodies, response bodies, ports, or schemas. The stable automation API is the `## CLI Interface` contract above.

## Architecture Decision Record (ADR)

### ADR-001: Local single-process streaming

- **Status:** Accepted (pre-approved).
- **Decision:** Use Variant A and the literal constraint **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- **Consequences:** minimal deployment and no retained data; exact cardinality needs a hard limit and CPU scaling is limited to one process.

### Debate Summary

The architecture was reviewed by the plugin's Devil's Advocate agent.

**Verdict:** APPROVE WITH CONDITIONS; all conditions are resolved in this revision.

**Challenges raised:**

1. Entry counts did not defend the 256 MiB target. **Resolution:** added line, per-dimension entry, and shared conservative retained-byte budgets; release benchmarking may only lower unsafe defaults.
2. Cardinality failure could partially mutate state. **Resolution:** made two-phase preflight-before-mutation and a three-dimension boundary test normative.
3. Rich markup escaping alone did not stop terminal controls. **Resolution:** specified shared visible escaping for terminal/CSV control and bidi characters before rendering.
4. The benchmark was not reproducible and full sorting was avoidable. **Resolution:** fixed the baseline, fixture seed/distribution, commands, run policy, timing/RSS gates, and size-10 selection.
5. Invalid encoding and gzip evolution were ambiguous. **Resolution:** defined bounded binary input, strict UTF-8 as malformed-record policy, and a suffix-selected streaming P1 gzip source.

**Alternatives considered and rejected:**

- Multiprocess chunking remains deferred because stdin compatibility and deterministic failure are more valuable before profiling proves a CPU need.
- An embedded database remains rejected because fixed reports need no retention or query engine.
- A fundamentally different architecture was not warranted by the reviewer.

See `IMPLEMENTATION_PLAN.md` for sequencing and `PRD.md` for behavioral acceptance criteria.
