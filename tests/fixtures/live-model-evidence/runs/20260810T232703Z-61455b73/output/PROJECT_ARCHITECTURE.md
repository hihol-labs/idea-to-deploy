# Project Architecture: nginx-insights

## Context and Constraints

The product is a local Python 3.11 command-line utility for DevOps/SRE engineers. It reads nginx Common or Combined access logs from one file or stdin, processes records once without retaining source lines, and emits four reports. It must process a 1 GB reference log in under 30 seconds on a documented laptop. It has a $0 budget and a one-weekend delivery window.

The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is incorrect because the requested outputs require only in-process counters, 24 hourly buckets, and an exact bounded User-Agent set; persistence would add writes, schema, cleanup, and privacy exposure without user value. An HTTP API is incorrect because the user is at a shell with local logs and needs streaming and Unix-pipeline composition; a server would add lifecycle, ports, security, and deployment work explicitly outside scope.

Authentication, a server, cloud services, Docker, and Kubernetes are absent for the same reason: there is no remote trust boundary or long-running component to protect or deploy.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Selected)

- **Approach:** Click opens a file/stdin stream; a parser yields compact dataclass records; one aggregator updates counters; one selected renderer writes the report.
- **Pros:** One pass, lowest setup and operational cost, deterministic, testable, fits pip and weekend constraints.
- **Cons:** Exact unique User-Agent tracking can grow until the configured safety ceiling; one CPU core does parsing.
- **Best for:** Local analysis of a single log up to the stated laptop workload.
- **Estimated complexity:** Low.

### Variant B: Multi-process chunked parser (Rejected)

- **Approach:** Split seekable files into byte ranges, parse in workers, merge partial aggregates.
- **Pros:** Potential multi-core throughput on large regular files.
- **Cons:** Cannot naturally split stdin, must repair line boundaries, duplicates exact-cardinality memory across workers, adds merge and ordering complexity.
- **Best for:** Larger repeatable batch workloads after profiling proves CPU saturation.
- **Estimated complexity:** Medium.

### Variant C: Persistent analytics stack (Rejected)

- **Approach:** Ingest logs into a database/search service and query through an API/dashboard.
- **Pros:** Historical queries, retention, multi-user dashboards.
- **Cons:** Violates explicit no-database/no-server constraints, exceeds $0 operations and weekend delivery.
- **Best for:** A different product requiring history and fleet-wide analysis.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because the architecture is an obvious single-process fit for the approved local, stateless, one-weekend scope. Variant B remains a measured-performance contingency, not MVP architecture; Variant C is out of scope.

## System Structure

```text
file path or stdin
        |
        v
  Click CLI boundary ---- option/usage errors -> exit 2
        |
        v
 streaming text reader -- I/O failure --------> exit 1
        |
        v
 Common/Combined parser -- invalid lines -----> skipped counter
        |
        v
 one-pass Aggregator ---- UA limit -----------> exit 4
        |
        v
 immutable Report dataclasses
        |
        +---- Rich terminal renderer
        +---- JSON renderer
        +---- CSV renderer
        |
        v
 stdout; diagnostics on stderr
```

Only the renderer is output-specific. Parsing and aggregation never import Rich, Click, JSON, or CSV presentation concerns.

## Component and File Boundaries

| Path | Responsibility | Key contract |
|---|---|---|
| `pyproject.toml` | Python 3.11 metadata, dependencies, `nginx-insights` entry point | Installable with pip |
| `src/nginx_insights/cli.py` | Click command, input ownership, renderer selection, exception-to-exit mapping | No business calculations |
| `src/nginx_insights/parser.py` | Compile and parse Common/Combined lines | Yields `AccessRecord` or invalid result; never loads whole file |
| `src/nginx_insights/models.py` | Frozen `AccessRecord`, ranked item, hourly bucket, report dataclasses | Typed internal contract |
| `src/nginx_insights/aggregate.py` | One-pass counters, top-10 selection, percentages, UA guard | Deterministic report from valid records |
| `src/nginx_insights/render/text.py` | Rich terminal output | Color only when enabled and stdout is a TTY |
| `src/nginx_insights/render/json.py` | JSON document | Stable schema, UTF-8, no ANSI |
| `src/nginx_insights/render/csv.py` | Long-form CSV rows | Stable header, no ANSI |
| `src/nginx_insights/errors.py` | Domain exceptions and exit-code constants | Complete `0/1/2/3/4` mapping |
| `tests/` | Parser, aggregation, renderer, CLI, and performance evidence | Golden and boundary fixtures |

## Data Model and Algorithms

### AccessRecord

| Field | Type | Meaning |
|---|---|---|
| `client_ip` | `str` | Parsed first nginx remote-address token; IPv4/IPv6 stored as text |
| `timestamp` | `datetime` | Offset-aware timestamp parsed from `[day/Mon/year:hour:min:sec ±zzzz]` |
| `method` | `str` | Request method, or empty for malformed request field retained by an otherwise valid log line |
| `path` | `str` | Request target path with query string and fragment removed; `-` if no usable target |
| `protocol` | `str` | HTTP protocol token or empty |
| `status` | `int` | Three-digit HTTP status |
| `user_agent` | `str | None` | Combined-log User-Agent; `None` for Common logs or `-` |

The parser accepts standard nginx Common and Combined formats. It processes text line-by-line with a precompiled regular expression and `datetime.strptime`. A line missing required address, timestamp, request, or status fields is invalid. Decode failures use replacement characters only outside required structural tokens; a structurally unparseable line is skipped. Invalid lines increment `skipped_lines` and do not contribute to any denominator.

### Aggregation state

There are deliberately no database tables. The complete transient state is:

| Structure | Type | Growth |
|---|---|---|
| `total_valid_requests` | integer | Constant memory |
| `skipped_lines` | integer | Constant memory |
| IP counts | `Counter[str]` | O(distinct IPs) |
| Error-path counts | `Counter[str]` | O(distinct paths with status 400–599) |
| Hour counts | fixed list of 24 integers | Constant memory |
| Unique User-Agents | `set[str]` | O(distinct non-empty User-Agents), capped by option |

Each valid record updates the IP count and the bucket selected by the log timestamp's local hour (`00` through `23`, preserving the represented local wall-clock hour). Status codes 400–599 update the normalized path counter. A non-empty User-Agent is added to the exact set. Before adding a new value beyond `--max-unique-user-agents`, processing stops with exit code 4; the CLI emits no partial report.

Rankings sort by count descending, then key ascending, and take the first 10. This makes ties reproducible across runs. Hourly request distribution is a percentage calculated exactly as `100 × hourly_request_count / total_valid_requests`; all 24 buckets are present and percentages sum to approximately 100 subject to display rounding. The unique User-Agent share is `100 × distinct_nonempty_user_agent_count / total_valid_requests`. For Common logs without User-Agents, the share is 0%. Calculations retain full precision; presentation rounds percentages to two decimal places.

### Complexity and performance budget

- Time: O(n + d log 10) expected, where n is valid lines and d covers distinct ranking keys; `Counter.most_common` or an equivalent bounded selection is allowed if tie ordering remains exact.
- Memory: O(distinct IPs + distinct error paths + bounded distinct User-Agents), never O(number of lines).
- Source lines and `AccessRecord` objects are not retained after aggregation.
- The benchmark uses a documented 1 GB local regular file, warm-up run, three measured runs, wall-clock median, default cardinality ceiling, terminal rendering redirected to `/dev/null`, and the same laptop profile recorded in test output. The median must be below 30 seconds.

## CLI Interface

### Command

```text
nginx-insights [OPTIONS] [INPUT]
```

`INPUT` is an optional nginx access-log path. Omitted input or literal `-` reads UTF-8 text from stdin. Exactly one input stream is analyzed per invocation. Output goes to stdout; warnings and errors go to stderr.

### Options

| Option | Default | Contract |
|---|---|---|
| `--json` | false | Emit one JSON object; mutually exclusive with `--csv` |
| `--csv` | false | Emit long-form CSV; mutually exclusive with `--json` |
| `--no-color` | false | Disable color in text mode; accepted but redundant for JSON/CSV |
| `--max-unique-user-agents INTEGER` | `1000000` | Positive maximum exact distinct non-empty UA values; exceeding it exits 4 |
| `--version` | — | Print version and exit 0 |
| `--help` | — | Print usage and exit 0 |

Click rejects unknown options, extra inputs, invalid/non-positive cardinality values, and `--json --csv` together with exit code 2.

### Inputs

- Standard nginx Common and Combined access-log lines, newline delimited.
- Regular files, named pipes through stdin, and shell pipelines are supported.
- Compressed files, directory recursion, multiple input operands, custom `log_format`, and follow/tail mode are outside the MVP.
- Blank or malformed lines are skipped. A successful report requires at least one valid record.

### Outputs

Text mode contains a summary (`valid requests`, `skipped lines`, `unique User-Agents`, `unique User-Agent share`) and four titled tables/sections: top client IPs, top error URL paths, all 24 hourly percentages, and User-Agent share. Rich color is enabled only for an interactive TTY unless `--no-color` is set. Text redirected to a pipe is plain.

JSON uses this stable top-level shape:

```json
{
  "schema_version": 1,
  "summary": {
    "total_valid_requests": 0,
    "skipped_lines": 0,
    "distinct_user_agents": 0,
    "unique_user_agent_share_percent": 0.0
  },
  "top_ips": [{"rank": 1, "ip": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"rank": 1, "url": "/missing", "count": 1}],
  "hourly_request_distribution": [{"hour": "00", "count": 0, "percentage": 0.0}]
}
```

The hourly JSON array always contains 24 objects ordered `00`–`23`; top arrays contain at most 10 objects. JSON percentages are numeric values rounded to two decimal places.

CSV is UTF-8 RFC 4180-compatible long form with a single header:

```text
report,rank,key,count,percentage
```

Rows are ordered: `summary` (`total_valid_requests`, `skipped_lines`, `distinct_user_agents`, `unique_user_agent_share_percent`), `top_ip`, `top_error_url`, then 24 `hourly` rows. Unused cells are empty. The standard `csv` module performs quoting. JSON and CSV never contain Rich markup or ANSI escape sequences.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Success, including `--help` and `--version`; an analysis report has at least one valid record |
| `1` | Runtime or input I/O failure, including missing/unreadable file, broken input, or unexpected internal error |
| `2` | Click usage/configuration error, including conflicting formats or invalid option values |
| `3` | Input-data failure: the stream ended with zero valid records after blanks/malformed lines were skipped |
| `4` | Unique-cardinality exhaustion: adding a new User-Agent would exceed `--max-unique-user-agents`; no partial report is emitted |

The mapping `0/1/2/3/4` is public and must remain consistent in `PRD.md`, `IMPLEMENTATION_PLAN.md`, `CLAUDE_CODE_GUIDE.md`, `CLAUDE.md`, and tests.

## Configuration, Security, and Privacy

There are no required environment variables or configuration files. The CLI honors conventional `NO_COLOR` in text mode; command-line `--no-color` has the same disabling effect. Locale does not change machine schemas or sorting.

No auth mechanism exists because there is no server, account, remote request, or stored resource. The process has only the invoking user's file permissions. It must not follow directory trees, execute log contents, resolve IPs, call networks, or interpret terminal markup from untrusted fields. Rich output escapes untrusted values. Logs are read-only and never copied or persisted by the tool.

## Packaging and Deployment

Deployment means installing the wheel/sdist with pip into Python 3.11 and invoking its console script. Docker and `docker-compose` are intentionally absent: containerization adds no value to a local file/stdin utility and complicates file access and TTY behavior. Release verification builds wheel and sdist, installs the wheel into a clean virtual environment, and runs CLI smoke tests. No cloud or Kubernetes target exists.

## Observability

The utility emits concise actionable errors to stderr and keeps stdout schema-clean. In text mode it reports skipped lines; JSON/CSV include the same diagnostic count. It performs no telemetry, network access, log shipping, or persistent logging. Optional benchmark diagnostics belong to the test suite, not normal output.

## Architecture Decision Record (ADR)

### ADR-001: Single-process stateless CLI

- **Status:** Accepted (pre-approved).
- **Decision:** Use Variant A and the literal constraint **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- **Consequences:** Minimal operations and one-pass behavior; exact cardinalities require explicit in-memory limits; history and dashboards remain out of scope.

### Debate Summary — Labeled Self-Critique

No independent or adversarial reviewer was available for this benchmark. The following is the architect's own self-critique and must not be represented as independent review.

**Verdict:** APPROVE WITH CONDITIONS

**Strengths acknowledged:** The design matches the local shell workflow, minimizes moving parts, isolates output formats, and makes failure behavior explicit.

**Challenges raised and resolutions:**

1. Exact User-Agent uniqueness is not naturally bounded in a stream. **Resolution:** expose a positive cardinality ceiling, stop before exceeding it, reserve exit code 4, and suppress partial reports.
2. Counting every distinct IP and error path can also consume memory. **Resolution:** retain exact counters for MVP correctness, document complexity, benchmark adversarial fixtures, and make approximate heavy-hitter algorithms a future alternative only if measured memory is unacceptable.
3. Regex parsing can silently accept format drift. **Resolution:** support only named Common/Combined contracts, require structural fields, count skips, and exit 3 when no valid record exists.
4. Multi-process parsing might be faster. **Resolution:** do not add it until the reference benchmark fails and profiling identifies parsing CPU as the bottleneck; stdin semantics and weekend simplicity dominate now.
5. CSV representing heterogeneous reports can be ambiguous. **Resolution:** define one long-form header, fixed report ordering, report discriminator values, empty unused cells, and golden tests.
6. Rich rendering could leak ANSI/control behavior into pipelines. **Resolution:** machine renderers cannot import Rich; text color is TTY-aware; untrusted fields are escaped; golden tests assert no ANSI in JSON/CSV.

**Alternatives considered and rejected:**

- Multi-process chunking — rejected for MVP because it complicates stdin, line boundaries, and exact-set merging before performance evidence exists.
- SQLite or an analytics database — rejected because persistence adds latency and state without serving any required workflow.
- HTTP service/dashboard — rejected because the only approved interface is a local CLI and no remote consumer exists.
- Probabilistic User-Agent cardinality — rejected because the requested share is exact; deterministic exhaustion is clearer than silently approximate output.

**Conditions incorporated:** cardinality exhaustion, invalid-input behavior, schema definitions, deterministic ties, security escaping, and an executable benchmark are now explicit contracts.
