# Project Architecture: Nginx Log Lens

## Architecture Summary

The approved design is a single Python 3.11 process with a linear pipeline:

```text
file path or stdin
        |
        v
line iterator -> combined-log parser -> streaming aggregator -> immutable report
                                                          |          |
                                                          v          v
                                                  cardinality guard  Rich / JSON / CSV
```

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the product answers a
one-shot question over a supplied stream: persistence would add I/O, schema,
cleanup, and operational state without improving the four required metrics. An
HTTP API is incorrect because the target user is already at a terminal or in a
shell pipeline; a server would introduce lifecycle, port, security, and auth
concerns with no approved remote-use case.

No authentication is needed because there is no network boundary or account.
No Docker, cloud, or Kubernetes deployment is needed because pip installation
and a console entry point are the entire delivery model.

## CLI Interface

### Command

```text
nginx-log-lens [OPTIONS] [INPUT]
```

`INPUT` is an optional path to an uncompressed nginx access-log file. Omitted
`INPUT` or `-` reads bytes/text from standard input. MVP parsing supports the
nginx combined log format. Processing is single-pass; input is never loaded in
full.

### Options

| Option | Type/default | Contract |
|---|---|---|
| `--json` | flag, false | Emit one UTF-8 JSON document to stdout |
| `--csv` | flag, false | Emit one normalized UTF-8 CSV table to stdout |
| `--top N` | integer, `10` | Number of ranked IP and error-URL rows; must be 1–100, with the required default of 10 |
| `--max-unique N` | integer, `1000000` | Maximum distinct keys retained per guarded dimension before exit 4 |
| `--version` | flag | Print version and exit 0 |
| `--help` | flag | Print Click help and exit 0 |

`--json` and `--csv` are mutually exclusive. Diagnostics and warnings go to
stderr; report data goes to stdout. Machine formats never contain ANSI escape
sequences. Default text uses Rich color only when appropriate for the output
terminal.

### Inputs

- A regular readable file path, `-`, or stdin.
- UTF-8/ASCII-compatible nginx combined-format lines; undecodable or malformed
  lines are counted as malformed rather than treated as valid records.
- `request` is split into method, target, and protocol; ranking uses the target
  as logged, including its query string.
- Timestamp hour is interpreted from the offset present in each log line and
  bucketed by local log hour `00` through `23`.

### Outputs

Every renderer expresses the same `Report` values:

- total lines, valid requests, and malformed lines;
- top client IPs ordered by request count descending, then IP ascending;
- top URLs among 4xx/5xx records ordered by error count descending, then URL
  ascending;
- all 24 hourly buckets, each as count and percentage calculated exactly as
  `100 × hourly_request_count / total_valid_requests` (zero when there are no
  valid requests);
- unique User-Agent count and unique User-Agent share, where share is
  `100 × unique_user_agent_count / total_valid_requests` (zero when there are
  no valid requests).

JSON uses stable snake_case keys and numeric percentages rounded to two decimal
places. CSV uses columns `section,rank,key,count,percentage`; scalar summary
values use `section=summary`. Rich text labels percentages with `%` and reports
malformed-line counts.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Report produced successfully; some malformed lines may have been skipped |
| `1` | Input I/O failure, including missing, unreadable, or interrupted input |
| `2` | CLI usage error, including invalid or conflicting options |
| `3` | Parsing failure because input contained lines but no valid supported records |
| `4` | Unique-cardinality exhaustion: a guarded distinct-key limit was exceeded |

Partial reports are never emitted for exit codes 1, 2, 3, or 4. Errors are
short, actionable, and written to stderr.

## Components and Responsibilities

| Module | Responsibility | Depends on |
|---|---|---|
| `src/nginx_log_lens/cli.py` | Click command, option validation, stream ownership, exception-to-exit mapping | parser, aggregator, renderers |
| `src/nginx_log_lens/models.py` | Frozen dataclasses for `LogRecord`, `RankedItem`, `HourlyBucket`, and `Report` | standard library |
| `src/nginx_log_lens/parser.py` | Precompiled combined-format parsing and typed field conversion | models |
| `src/nginx_log_lens/aggregate.py` | One-pass counters, error filtering, hourly buckets, unique-UA set, cardinality checks | models, errors |
| `src/nginx_log_lens/errors.py` | Domain exceptions for input, parse-empty, and cardinality outcomes | standard library |
| `src/nginx_log_lens/renderers/text.py` | Rich terminal tables and summaries | models, Rich |
| `src/nginx_log_lens/renderers/json.py` | Stable JSON document | models, standard library |
| `src/nginx_log_lens/renderers/csv.py` | Normalized CSV records | models, standard library |

Renderers do not parse or recalculate metrics. The aggregator returns a frozen
report, making semantic parity testable across formats.

## Data Model

There are no database tables. Runtime-only dataclasses are the complete data
model:

| Dataclass | Fields |
|---|---|
| `LogRecord` | `ip: str`, `timestamp: datetime`, `method: str`, `target: str`, `protocol: str`, `status: int`, `bytes_sent: int | None`, `user_agent: str` |
| `RankedItem` | `key: str`, `count: int` |
| `HourlyBucket` | `hour: int`, `count: int`, `percentage: float` |
| `Report` | `total_lines: int`, `total_valid_requests: int`, `malformed_lines: int`, `top_ips: tuple[RankedItem, ...]`, `top_error_urls: tuple[RankedItem, ...]`, `hourly: tuple[HourlyBucket, ...]`, `unique_user_agents: int`, `unique_user_agent_share: float` |

Mutable counters and sets exist only during aggregation and are released at
process exit. Counts are Python integers. Percentages are computed at report
finalization and rounded only at rendering boundaries.

## Streaming and Complexity

For `n` input lines and `u` distinct guarded keys, parsing is `O(n)`. Final
ranking is `O(u log 10)` conceptually and may use `heapq.nsmallest`/`nlargest`
or deterministic sorting after aggregation. The input file is never retained.

Exact top IPs, exact top error URLs, and exact unique User-Agent count require
tracking distinct keys. They are therefore bounded operationally, not constant
memory: each distinct-key collection checks `--max-unique` before insertion.
Exceeding the limit aborts with exit code 4. The 1 GB acceptance fixture must
stay within the default limit and complete below 30 seconds on the documented
reference laptop.

## Error Handling

The parser returns either a `LogRecord` or a malformed result without logging
per-line warnings, which would destroy throughput. The aggregator counts
malformed lines. Empty input produces a valid empty report with exit 0; nonempty
input with zero valid records exits 3. I/O exceptions map to 1, Click usage
errors to 2, and cardinality-limit exceptions to 4. Unexpected internal errors
are not silently remapped; they produce exit 1 with a concise diagnostic in
normal CLI operation and remain visible during tests.

## Packaging and Runtime

The package uses a `src/` layout, a PEP 621 `pyproject.toml`, and the console
script `nginx-log-lens = nginx_log_lens.cli:main`. Runtime dependencies are
Click and Rich. Python 3.11 is the minimum supported interpreter. The artifact
is a wheel/sdist installable through pip; no environment variables are required.

There is no container definition, compose file, service manager, deployment
manifest, or listening port. A release consists of building the package,
validating metadata, installing the wheel into a clean Python 3.11 virtual
environment, and executing smoke tests.

## Security and Privacy

- Log content is untrusted data and is never evaluated or interpolated into a
  shell command.
- Rich/text output escapes or safely renders control-like content; JSON and CSV
  use their standard-library encoders.
- No logs or aggregates leave the machine and no state persists automatically.
- CSV cells beginning with spreadsheet formula markers (`=`, `+`, `-`, `@`)
  are prefixed safely when the field is textual.
- Input paths are opened read-only. The tool never modifies the source log.

## Architecture Variants and Decision

The architecture is an obvious approved single-process choice, so no user
selection is pending. Two relevant alternatives remain documented:

### Variant A: Single-process streaming CLI (selected)

- **Approach:** Parse and aggregate in one Python process, then render once.
- **Pros:** Small surface, local privacy, straightforward packaging, zero
  infrastructure, easy pipeline use.
- **Cons:** Exact high-cardinality metrics require bounded in-memory state; no
  retained cross-run history.
- **Best for:** One-shot local analysis within the stated 1 GB target.
- **Estimated complexity:** Low.

### Variant B: Unix pipeline of specialized commands

- **Approach:** Provide documented `awk`, `sort`, and `uniq` compositions.
- **Pros:** No package and familiar primitives.
- **Cons:** Repeated scans/sorts, platform variation, fragile parsing, and no
  unified JSON/CSV or exit-code contract.
- **Best for:** One-off expert investigation with disposable commands.
- **Estimated complexity:** Low initially, high to maintain.

### Variant C: Persistent analytics service

- **Approach:** Ingest into a database or Elastic stack and expose dashboards or
  an API.
- **Pros:** Historical queries, collaboration, and rich exploration.
- **Cons:** Violates budget, delivery time, privacy, deployment, and CLI-only
  constraints.
- **Best for:** A different product requiring retention and multi-user access.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because it alone satisfies the approved local, stateless,
$0, one-weekend product while keeping the 1 GB performance target directly
measurable. Variant C is rejected, not deferred.

## Architecture Decision Records

### ADR-001: One process and one pass

- **Status:** Accepted by pre-approved product decision.
- **Decision:** A modular single process reads the input once and constructs one
  report model.
- **Consequences:** Low coordination overhead and consistent renderers; bounded
  exact-cardinality state must be guarded explicitly.

### ADR-002: Supported input contract

- **Status:** Accepted.
- **Decision:** MVP supports nginx combined format, a path or stdin, and
  uncompressed input. Gzip is P1.
- **Consequences:** The parser remains fast and testable; custom formats are P2.

### ADR-003: No inline adversarial review in this blueprint session

- **Status:** Required by benchmark protocol.
- **Decision:** This document records design decisions but no Devil's Advocate
  verdict or self-critique artifact.
- **Consequences:** The external harness may perform the independent review in a
  fresh session without false provenance from this planning run.

## Traceability

Product scope and priorities originate in `STRATEGIC_PLAN.md` and `PRD.md`.
Concrete construction order and verification are in `IMPLEMENTATION_PLAN.md`.
Implementation prompts must preserve this architecture through
`CLAUDE_CODE_GUIDE.md` and `CLAUDE.md`.

