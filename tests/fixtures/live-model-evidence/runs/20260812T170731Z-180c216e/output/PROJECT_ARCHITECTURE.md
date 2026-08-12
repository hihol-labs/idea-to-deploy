# Project Architecture: Nginx Stream Insights

## Context and Constraints

The product is an installable Python 3.11 CLI for one-pass analysis of nginx access logs. The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add writes, schema lifecycle, disk amplification, privacy exposure, and cleanup to a task whose output is a disposable aggregate. An HTTP API would add a daemon, ports, authentication questions, deployment, and concurrency without improving the local file/stdin workflow. The filesystem or stdin is the input boundary; stdout/stderr and process exit status are the integration boundary.

Other fixed constraints are $0 spend, open source, pip installation, no authentication, no server/cloud/Kubernetes, solo one-weekend delivery, and a target of processing 1 GB in under 30 seconds on a documented reference laptop.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended)

- **Approach:** Click command opens a text stream; a parser yields compact dataclass records; one aggregator updates counters; a selected renderer writes the final snapshot.
- **Pros:** One pass, deterministic, easy to test, no IPC, minimal operational surface.
- **Cons:** CPU work remains single-process; exact IP/URL/User-Agent sets grow with input cardinality.
- **Best for:** The approved local one-shot workflow.
- **Estimated complexity:** Low.

### Variant B: Unix-stage subprocess pipeline

- **Approach:** Separate parser, aggregator, and formatter processes connected by pipes.
- **Pros:** Stages can be replaced independently and parallelized later.
- **Cons:** Serialization and IPC overhead, harder cross-platform behavior, fragmented error/exit semantics.
- **Best for:** A toolkit whose intermediate record stream is itself public.
- **Estimated complexity:** Medium.

### Variant C: Embedded persistent index

- **Approach:** Parse into SQLite and query aggregates afterward.
- **Pros:** Repeatable ad hoc queries and retained history.
- **Cons:** Violates statelessness, adds write amplification and cleanup, threatens the time target, retains potentially sensitive log data.
- **Best for:** Repeated exploratory analysis outside this product scope.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected. The user has pre-approved the obvious single-process architecture, and neither persistence nor a public intermediate stream is a requirement.

## Component Model

```text
file path / stdin
       |
       v
 Click CLI + input opener
       |
       v
 line iterator -> nginx parser -> RequestRecord
                                  |
                                  v
                         StreamingAggregator
                                  |
                                  v
                           AnalysisSnapshot
                        /         |         \
                  Rich text      JSON       CSV
                        \         |         /
                         stdout; diagnostics -> stderr
```

| Component | Planned path | Responsibility |
|---|---|---|
| CLI | `src/nginx_stream_insights/cli.py` | Command/options, stream ownership, error mapping, renderer selection |
| Parser | `src/nginx_stream_insights/parser.py` | Supported combined-log parsing and validation |
| Models | `src/nginx_stream_insights/models.py` | Frozen/slot dataclasses for parsed records and snapshots |
| Aggregator | `src/nginx_stream_insights/aggregate.py` | One-pass counters, top-N selection, exact cardinality guard |
| Renderers | `src/nginx_stream_insights/renderers/{terminal,json,csv}.py` | Presentation only; no metric calculation |
| Errors | `src/nginx_stream_insights/errors.py` | Typed failures mapped to the public exit contract |

## Data Model and Streaming State

There are no database tables, migrations, indexes, or retained records. In-memory state is process-local and discarded on exit.

| Dataclass/state | Fields and types | Invariant |
|---|---|---|
| `RequestRecord` | `ip: str`, `timestamp: datetime`, `url: str`, `status: int`, `user_agent: str` | One syntactically valid supported log line |
| `AnalysisSnapshot` | `total_valid_requests: int`, `invalid_lines: int`, `top_ips: tuple[RankedCount, ...]`, `top_error_urls: tuple[RankedCount, ...]`, `hourly_distribution: tuple[HourlyShare, ...]`, `unique_user_agents: int`, `unique_user_agent_share: float` | Immutable renderer input |
| `RankedCount` | `key: str`, `count: int`, `rank: int` | Rank starts at 1; at most 10 per ranking |
| `HourlyShare` | `hour: int`, `request_count: int`, `percentage: float` | Hours 0–23; percentage uses valid requests only |
| Aggregator state | `Counter[str]` for IP and error URL, 24-element integer list, `set[str]` for User-Agents, valid/invalid counters | Updated once per valid parsed record |

Top lists sort by descending count, then ascending key for deterministic ties. An error URL is counted once for each valid request whose status is 400–599. Hourly request distribution for each hour is the percentage `100 × hourly_request_count / total_valid_requests`; when there are zero valid requests, every hourly percentage is `0.0` and the command follows the input-validity policy below.

The unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`. It measures how many distinct User-Agent strings exist relative to valid requests; it is not the percentage of requests belonging to unique-only agents. Exact strings are used after parser unescaping; missing `"-"` is a value unless product fixtures establish it as missing.

The cardinality guard has a configurable internal/default limit documented in release notes. Crossing it aborts exact processing rather than silently approximating and returns exit code 4.

## CLI Interface

### Commands

Installed command:

```text
nginx-stream-insights [OPTIONS] [INPUT]
```

`INPUT` is an optional nginx access-log path. Omission or `-` reads UTF-8 text from stdin. Version 1 supports nginx combined log format; unsupported custom `log_format` layouts are invalid input, not guessed.

### Options

| Option | Meaning | Rules |
|---|---|---|
| `--json` | Emit one JSON document | Mutually exclusive with `--csv` |
| `--csv` | Emit normalized CSV rows | Mutually exclusive with `--json` |
| `--no-color` | Disable Rich color | Relevant only to terminal output; accepted with structured output as a no-op |
| `--strict` | Fail if any malformed line is encountered | Without it, skip malformed lines, count them, warn on stderr |
| `--version` | Print version and exit | No input opened |
| `--help` | Print Click help and exit | No input opened |

### Inputs

- Regular file path, read sequentially without loading it in full.
- `-` or omitted input, read sequentially from stdin.
- UTF-8 decoding is strict; decoding failures are input errors.
- Empty input or input with zero valid requests is an invalid-data failure.

### Outputs

- Default terminal output: four labeled Rich sections/tables plus valid and skipped line totals. Color is enabled only when appropriate for the terminal and not when `--no-color` is set.
- JSON output: one object with `schema_version`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`. All 24 hours are emitted in ascending order.
- CSV output: header `report,rank,key,count,percentage`; normalized rows for top IPs, error URLs, 24 hours, and the User-Agent summary. Empty cells represent fields not applicable to a report type.
- Successful report data goes to stdout. Warnings and errors go to stderr. Structured stdout never contains Rich markup or diagnostics.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Report produced successfully; non-strict skipped-line warnings may exist |
| `1` | Runtime/internal failure not covered below |
| `2` | CLI usage error, including conflicting options |
| `3` | Input/data error: unreadable file, decode failure, strict parse failure, empty/no-valid input |
| `4` | Unique-cardinality exhaustion: exact User-Agent tracking exceeds the safe configured limit |

Click usage validation must preserve code 2. Domain exceptions are caught only at the command boundary and mapped once. Broken pipe during a downstream pipeline is handled quietly according to platform convention and must not corrupt a partial structured record.

## Error and Validation Policy

Parsing is fail-soft by default: malformed lines increment `invalid_lines` and produce a final stderr warning. `--strict` turns the first malformed line into exit code 3 and emits its line number without echoing the entire potentially sensitive line. Filesystem and decode errors are code 3. Unexpected exceptions are code 1 with a concise message; tracebacks are reserved for a development/debug mechanism, not default output.

## Performance and Resource Model

- Single sequential read and one parser invocation per line.
- No list of raw lines or parsed records.
- Counter memory is `O(unique_ips + unique_error_urls + unique_user_agents)`; hourly state is constant.
- Top 10 selection occurs after streaming using bounded selection or `Counter.most_common`, with deterministic tie handling verified separately.
- Benchmark fixture, Python version, dependency versions, laptop CPU, storage, OS, elapsed time, and peak RSS are recorded.
- Acceptance target: a representative 1 GB combined log in under 30 seconds on the reference laptop. The benchmark excludes cold package installation and includes parsing, aggregation, and output.

## Security and Privacy

The CLI does not authenticate because there is no remote boundary or multi-user service. It does not phone home or persist logs. Paths are passed to Python file APIs without shell evaluation. Diagnostics avoid printing complete log lines. Dependency versions and licenses are reviewed before release. Operators remain responsible for permissions on source logs and redirected output, which may contain IPs, URLs, and User-Agent strings.

## Packaging and Deployment

The deployment target is a developer/SRE laptop with Python 3.11. A PEP 517 `pyproject.toml` builds a wheel and source distribution; a console-script entry point exposes `nginx-stream-insights`. Installation is through `pipx install .` for isolated CLI use or `python -m pip install .` in a virtual environment. There is no Docker image, Compose stack, environment-variable contract, daemon, staging environment, or Kubernetes manifest because each would contradict the local CLI scope.

## Architecture Decision Record (ADR)

### ADR-001: Stateless single-process CLI

- **Status:** Accepted.
- **Decision:** Use Variant A and the literal constraint **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- **Consequences:** Minimal operations and a clean pipeline contract; repeated analysis rereads input; exact unique sets require a cardinality guard.

### Self-Critique Debate Summary

No independent or adversarial reviewer was available in this isolated benchmark. The following is a labeled self-critique, not an independent review.

**Verdict:** APPROVE WITH CONDITIONS.

1. Exact User-Agent tracking can exhaust memory on hostile/high-cardinality input. **Resolution:** enforce a guard and public exit code 4; never silently switch to approximation.
2. The 30-second target is hardware and fixture dependent. **Resolution:** define and record the reference environment and fixture characteristics.
3. Fixed combined-format parsing limits real deployments. **Resolution:** make support explicit; defer custom format templates rather than guess.
4. Full IP and URL counters remain cardinality-dependent. **Resolution:** document memory complexity and profile representative worst cases; retain exactness for MVP.
5. CSV could become ambiguous. **Resolution:** freeze a normalized long-form schema and test row ordering.
6. Default malformed-line skipping could conceal quality issues. **Resolution:** emit counts/warnings and provide `--strict` for CI.

Rejected alternatives are subprocess staging (complexity without a public intermediate-format requirement), persistence (scope and privacy cost), and a server/API (no remote-use requirement).

## Traceability

Product priorities and success criteria live in `STRATEGIC_PLAN.md` and `PRD.md`. Delivery sequencing and file-level checks live in `IMPLEMENTATION_PLAN.md`. Implementation sessions must follow `CLAUDE.md` and the prompts in `CLAUDE_CODE_GUIDE.md`.
