# Project Architecture: nginx-stream-stats

## 1. Context and Drivers

This is a local Python 3.11 command-line program for DevOps/SRE users. It must process nginx combined access logs in one pass, support human and pipeline output, install through pip, cost $0, and be deliverable in one weekend. The performance target is a 1 GB input in under 30 seconds on a documented laptop.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database would add writes, schema lifecycle, cleanup, and I/O without helping a one-shot aggregate. An HTTP API would add a server, networking, authentication, deployment, and operational state to a tool whose users already have files and Unix pipes. Both constraints are correct: bounded in-process counters are the minimum mechanism for the outputs, and a local CLI is the direct user interface.

## 2. Chosen Architecture

The pre-approved architecture is one operating-system process with layered modules:

```text
file path or stdin
       |
       v
Click command -> line iterator -> combined-log parser -> streaming aggregator
                                                        |
                                                        v
                                                  immutable report
                                                        |
                         +------------------------------+------------------+
                         v                              v                  v
                    Rich terminal                  JSON encoder       CSV writer
```

There are no workers, threads, services, sockets, queues, database connections, or intermediate files. The parser emits one `AccessRecord` at a time; the aggregator updates counters and discards it. Only distinct keys needed for exact results remain in memory.

| Layer | Responsibility | Must not do |
|---|---|---|
| `cli.py` | Click options, stream ownership, exit mapping | Parse records or calculate metrics |
| `parser.py` | Convert one combined-log line to a record or parse error | Perform I/O or mutate aggregates |
| `aggregator.py` | Update counters, enforce cardinality guard, finalize | Render or exit the process |
| `models.py` | Dataclasses for records and reports | Depend on Click or Rich |
| `renderers/` | Serialize one report to terminal, JSON, or CSV | Recalculate metrics |
| `errors.py` | Typed domain exceptions | Print directly |

Time is `O(n + u log 10 + p log 10)` for `n` valid lines, `u` IPs, and `p` error URLs. Memory is `O(u + p + a + 24)`, where `a` is distinct User-Agents up to a hard limit. Rankings sort by count descending, then key ascending.

## CLI Interface

### Command, options, and input

```text
nginx-stream-stats [OPTIONS] [INPUT]
```

`INPUT` is a local text-file path or `-`; omission means stdin. MVP input is one nginx combined-format record per line, decoded as strict UTF-8.

| Option | Default | Contract |
|---|---|---|
| `--json` | false | One JSON document; mutually exclusive with `--csv` |
| `--csv` | false | RFC 4180-compatible UTF-8 CSV; mutually exclusive with `--json` |
| `--no-color` | false | Disable Rich color in terminal mode |
| `--strict` | false | Abort on first malformed non-empty line with exit 3; otherwise skip/count it |
| `--top INTEGER` | `10` | Positive ranked-result count; default fulfills top-10 requirements |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive exact-cardinality cap; exceeding it aborts with exit 4 |
| `--version` | — | Print version and exit 0 |
| `--help` | — | Print usage and exit 0 |

Click validates combinations before opening input. Stdout contains only the report; warnings/errors use stderr. Color appears only in default terminal mode attached to a TTY. JSON and CSV never contain ANSI codes.

Combined fields are remote address, identity, authenticated user, timestamp with offset, request line, status, response size, referrer, and User-Agent. Quoted strings and escaped quotes/backslashes are preserved. Each valid record contributes to total, IP, hour, and User-Agent metrics. Status 400–599 also contributes the request target to error URLs. Lenient mode excludes blank/malformed lines and reports their count. Zero valid records is exit 3.

### Outputs

Every renderer exposes total valid and invalid counts; ranked IPs; ranked 4xx/5xx URLs; all 24 hourly buckets; and exact distinct User-Agent count/share.

Hourly request distribution is a percentage using `100 × hourly_request_count / total_valid_requests`. Unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`. Zero denominator cannot occur in a successful report.

JSON has this stable shape (percentages are numbers rounded to six decimals):

```json
{
  "total_valid_requests": 120,
  "invalid_line_count": 2,
  "top_ips": [{"rank": 1, "ip": "192.0.2.1", "request_count": 40}],
  "top_error_urls": [{"rank": 1, "url": "/missing", "error_count": 7}],
  "hourly_distribution": [{"hour": "00", "request_count": 5, "percentage": 4.166667}],
  "unique_user_agents": {"count": 18, "percentage": 15.0}
}
```

CSV is a tidy table with header `metric,rank,key,count,percentage`, rows for `top_ip`, `top_error_url`, 24 `hourly_distribution` buckets, `unique_user_agents`, `summary`, and `invalid_lines`. Standard-library quoting and a trailing newline are required. Terminal mode uses four labeled Rich sections and two-decimal percentages.

### Exit-code contract

| Code | Meaning | Examples |
|---:|---|---|
| `0` | Success | Report emitted, help, version |
| `1` | Operational or unexpected failure | Input/read/output error, internal failure |
| `2` | Invalid CLI invocation | Unknown option, bad value, incompatible modes |
| `3` | Log data or format failure | No valid records, invalid UTF-8, strict malformed line |
| `4` | Unique-cardinality exhaustion | New User-Agent would exceed the configured cap |

Typed exceptions map only in the CLI. Cardinality failure is never remapped to 1 and never emits an approximate report.

## 4. Data Model

There are no database tables, migrations, or persistent records. The complete in-memory dataclass contract is:

| Dataclass | Fields and types | Constraints |
|---|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `method: str`, `target: str`, `protocol: str`, `status: int`, `user_agent: str` | Frozen; status 100–599; timezone-aware timestamp |
| `RankedCount` | `rank: int`, `key: str`, `count: int` | Frozen; positive rank/count |
| `HourlyBucket` | `hour: int`, `request_count: int`, `percentage: float` | Frozen; hour 0–23; percentage 0–100 |
| `UniqueAgentSummary` | `count: int`, `percentage: float` | Frozen; non-negative, percentage 0–100 |
| `AnalysisReport` | totals, tuples of ranked results, 24 hourly buckets, unique-agent summary | Frozen; positive valid total; exactly 24 hours |

Private mutable state is two `Counter[str]` instances (IPs/error URLs), a 24-integer list, `set[str]` for User-Agents, and valid/invalid totals. No storage adapter is needed because there is no storage implementation.

## 5. Parsing and Aggregation Decisions

1. Compile one anchored combined-log regular expression at import.
2. Iterate buffered text line by line; never call `read()` or `readlines()`.
3. Parse timezone-aware timestamps and bucket by the hour as logged.
4. Split request line with bounded splits; use the request target verbatim, including query string, as URL key.
5. Treat only 400–599 as error statuses.
6. Add exact User-Agents only while under the cap; a new value past it raises `CardinalityLimitError`.
7. Finalize once at EOF and share one immutable report among renderers.

## 6. Package Layout

```text
pyproject.toml
src/nginx_stream_stats/
  __init__.py
  cli.py
  parser.py
  aggregator.py
  models.py
  errors.py
  renderers/{__init__.py,terminal.py,json_output.py,csv_output.py}
tests/
  fixtures/{combined.log,malformed.log}
  unit/{test_parser.py,test_aggregator.py}
  integration/{test_cli.py,test_output_contracts.py}
  performance/{generate_log.py,test_benchmark.py}
```

The console script points to `nginx_stream_stats.cli:main`.

## 7. Dependencies and Security

Runtime dependencies are Click and Rich in compatible release ranges; dataclasses, counters, datetime, JSON, and CSV use Python 3.11. Log content is untrusted data: never terminal markup, format strings, shell commands, filenames, or code. Rich text is escaped; CSV/JSON use standard encoders. The tool opens only explicit input, has no network access, and writes only its report to stdout.

## 8. Configuration, Packaging, and Deployment

No environment variable or config file is required. `NO_COLOR` may disable terminal color; explicit CLI options win. Correctness-affecting limits remain flags for replayability.

Deployment is a Python wheel installed locally or from a package index. There is no Docker/Compose stack, daemon, staging server, cloud target, or Kubernetes manifest. Release checks build sdist/wheel, verify metadata, install into a clean Python 3.11 environment, run CLI smoke tests, and then publish.

## 9. Architecture Decisions and Rejected Alternatives

The single-process architecture and stack were pre-approved, so no interactive variant choice is needed.

| Alternative | Decision and reason |
|---|---|
| `awk`/`sort` pipeline | Rejected: combined-format quoting and stable multi-output contracts are fragile |
| Go binary | Rejected for MVP: conflicts with the approved Python stack |
| SQLite or another database | Rejected: persistence and extra I/O do not help one-shot aggregates |
| REST service/microservices | Rejected: adds auth, deployment, networking, and state without value |
| Parallel chunks | Deferred until profiling; boundaries and overhead add weekend risk |
| Approximate cardinality | Rejected: exact share plus explicit exit 4 is safer than silent approximation |

No adversarial or independent architecture review is recorded here; it is outside this planning session.

## 10. Quality Verification

| Attribute | Acceptance mechanism |
|---|---|
| Correctness | Parser fixtures, hand-calculated aggregates, golden renderer tests |
| Performance | Generated 1 GB fixture, wall-clock and peak RSS on named laptop |
| Memory | Streaming test and cardinality tests at limit and limit + 1 |
| Portability | Clean Python 3.11 wheel install and CLI tests |
| Pipeline stability | JSON schema assertions, CSV round-trip, stderr/stdout separation |
| Maintainability | Typed boundaries, one report model, at least 90% statement coverage |

Requirements are in [PRD.md](PRD.md); implementation checks are in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
