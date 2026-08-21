# Project Architecture: logpulse

> Source of truth for the technical design. Cross-references:
> [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md), [PRD.md](PRD.md),
> [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md).

## Core architectural decision

**"no database — stateless streaming processing; no HTTP API — CLI-only tool"**

Both halves of this decision are correct for this product:

- **No database — stateless streaming processing.** The tool answers questions about
  *one log stream in one run* and then exits. There is no cross-run state, no history,
  and no query workload that a database would serve. A database would force a schema,
  an ingestion step, storage, and a consistency/lifecycle burden — all pure cost against
  the $0 budget and the one-weekend timeline. Streaming keeps memory flat (O(unique keys),
  not O(lines)), which is exactly what lets 1 GB finish in under 30 seconds on a laptop:
  the process reads line by line and never materializes the whole file. Persisting to a
  DB would *slow it down* and add the only stateful component that could corrupt or fill
  up. The metrics required (top-N counters, hourly buckets, a bounded unique-UA set) are
  all computable in a single pass with in-memory aggregates.

- **No HTTP API — CLI-only tool.** The user is a DevOps/SRE engineer at a terminal or in
  a pipeline. A CLI composes with the tools they already use (`ssh`, `zcat`, `tail`, `jq`,
  shell pipes) and needs no server to run, secure, authenticate, or keep alive. An HTTP
  API would introduce a network surface, a listener lifecycle, auth, and an operational
  component — none of which serves a one-shot local triage. Unix exit codes and stdout/stderr
  are a better contract for automation than a REST endpoint here. The explicit constraints
  (no auth, no server, no cloud) follow directly: there is nothing to authenticate and
  nothing to host.

## Architecture Variants

### Variant A: Single-process streaming CLI (Recommended)

- **Approach:** One Python process. A generator reads the input stream line by line, a
  compiled-regex parser yields typed `LogRecord` dataclasses, and a set of in-memory
  aggregators (counters + fixed 24-slot hourly array + bounded unique-UA set) fold each
  record. After EOF, renderers emit Rich / JSON / CSV. No shared state between runs.
- **Pros:** Flat memory, minimal deps, trivial to install and reason about, meets the
  1 GB/30 s target, matches every stated constraint.
- **Cons:** Single core (no parallelism); bounded by single-thread parse speed.
- **Best for:** One-shot local triage on a laptop — exactly this product.
- **Estimated complexity:** Low.

### Variant B: Multiprocessing chunked map-reduce

- **Approach:** Split the file into byte ranges, parse chunks in worker processes, merge
  partial aggregates in the parent.
- **Pros:** Uses multiple cores; higher throughput on very large files.
- **Cons:** Chunk-boundary line splitting, merge complexity, process overhead, harder to
  keep unique-UA cardinality bounded across workers; overkill for 1 GB/30 s which Variant A
  already meets.
- **Best for:** Multi-GB batch jobs — not the MVP.
- **Estimated complexity:** High.

### Variant C: External-tool wrapper (invoke GoAccess/awk under the hood)

- **Approach:** Shell out to an existing analyzer and reformat its output.
- **Pros:** Least code.
- **Cons:** Adds a heavy runtime dependency, breaks the $0/no-infra promise, loses control
  of the exact metric definitions and exit-code contract, portability pain.
- **Best for:** Nothing here — contradicts the strategy.
- **Estimated complexity:** Medium.

### Recommendation

**Variant A** is recommended because it is the only variant that satisfies every project
constraint simultaneously: stateless streaming (flat memory), $0/no-infra, one-weekend
build, and the 1 GB/30 s performance target — without the boundary/merge complexity of B
or the dependency debt of C. The other variants are documented so the choice is auditable,
per Step 2.1.

## Component design

```
                +-------------------+
  file / stdin  |   input.reader    |  yields raw lines (buffered, encoding-safe)
  ------------->|  (generator)      |
                +---------+---------+
                          |
                          v
                +-------------------+
                |  parser.parse     |  compiled regex -> LogRecord | None (skip)
                +---------+---------+
                          |
                          v
                +-------------------+
                |  aggregate.fold   |  updates all metrics in ONE pass:
                |                   |   - Counter[ip]
                |                   |   - Counter[url]  (only when status in 4xx/5xx)
                |                   |   - hourly[24]    (int array)
                |                   |   - unique_ua set (bounded by --max-unique)
                +---------+---------+
                          |
                          v  (after EOF)
                +-------------------+
                |  report.build     |  -> Report dataclass (typed results)
                +---------+---------+
                          |
             +------------+------------+
             v            v            v
        render_rich  render_json   render_csv
```

### Data model (dataclasses — the "schema" for this stateless tool)

There are **no database tables** (see the core decision). The equivalent typed structures are:

```python
@dataclass(slots=True)
class LogRecord:
    ip: str
    timestamp: datetime      # parsed from [10/Oct/2000:13:55:36 -0700]
    method: str
    url: str                 # request path (query string stripped for grouping)
    status: int              # HTTP status code
    bytes_sent: int
    user_agent: str

@dataclass(slots=True)
class Report:
    total_lines: int
    valid_requests: int
    skipped_lines: int
    top_ips: list[tuple[str, int]]              # up to --top (default 10)
    top_error_urls: list[tuple[str, int]]       # up to --top, ranked by 4xx/5xx count
    hourly_distribution: list[HourlyBucket]     # 24 buckets
    unique_user_agents: int
    unique_ua_share: float                      # unique_user_agents / valid_requests
    unique_ua_truncated: bool                   # True if cap hit (drives exit code 4)

@dataclass(slots=True)
class HourlyBucket:
    hour: int                # 0..23
    count: int
    percent: float           # 100 × hourly_request_count / total_valid_requests
```

### Aggregators

| Aggregate | Structure | Memory | Notes |
|-----------|-----------|--------|-------|
| Top-10 IPs | `collections.Counter[str]` | O(unique IPs) | `.most_common(top)` at the end |
| Top-10 error URLs | `collections.Counter[str]` | O(unique error URLs) | incremented only when `400 <= status <= 599` |
| Hourly distribution | `list[int]` length 24 | O(1) | bucket = `timestamp.hour`; percent computed at render |
| Unique User-Agents | `set[str]` bounded by `--max-unique` | O(min(unique UAs, cap)) | on cap breach: stop inserting, set `unique_ua_truncated=True` → exit code `4` |

## Environment variables

This is a local CLI; configuration is via flags, not env. Two optional overrides:

| Variable | Description | Example |
|----------|-------------|---------|
| `LOGPULSE_MAX_UNIQUE` | Default cap for unique-UA tracking if `--max-unique` not passed | `2000000` |
| `NO_COLOR` | Standard env; when set, disables ANSI color (same as `--no-color`) | `1` |

## CLI Interface

### Command

```
logpulse analyze [OPTIONS] [LOGFILE]
```

Auxiliary: `logpulse --version`, `logpulse --help`, `logpulse analyze --help`.

### Positional input

| Argument | Meaning |
|----------|---------|
| `LOGFILE` | Path to an nginx access log. Omit it, or pass `-`, to read from **stdin** (enables `zcat access.log.gz \| logpulse analyze -`). |

### Options

| Option | Type / default | Effect |
|--------|----------------|--------|
| `--json` | flag | Emit the report as a single JSON object to stdout (mutually exclusive with `--csv`) |
| `--csv` | flag | Emit the report as CSV sections to stdout (mutually exclusive with `--json`) |
| `--top N` | int, default `10` | Number of rows for the IP and error-URL tables |
| `--format NAME` | choice: `combined` (default), `common` | nginx log format to parse |
| `--max-unique N` | int, default `2000000` (or `LOGPULSE_MAX_UNIQUE`) | Cap on the unique-User-Agent set; breach → exit code `4` |
| `--no-color` | flag | Disable ANSI color (also honored via `NO_COLOR`) |
| `--version` | flag | Print version and exit `0` |
| `--help` | flag | Print help and exit `0` |

### Inputs

- A stream of nginx access-log lines (combined or common format) from a file or stdin.
- The stream may contain malformed lines; the parser skips them and counts them in
  `skipped_lines` (reported), never aborting the run for a single bad line.

### Outputs

- **Default:** colored Rich tables/bars to **stdout** — Top-10 IPs, Top-10 error URLs,
  a 24-row hourly distribution with percentages, and the unique-UA count + share.
- **`--json`:** one JSON object mirroring the `Report` dataclass to stdout.
- **`--csv`:** CSV blocks (one per metric, section-delimited) to stdout.
- **Diagnostics** (parse-skip summary, warnings, errors) go to **stderr**, so stdout stays
  a clean data channel for pipelines.

### Exit-code contract (`0/1/2/3/4`)

| Code | Meaning |
|------|---------|
| `0` | Success — report produced |
| `1` | Unexpected internal error (unhandled exception) |
| `2` | Usage error — invalid arguments/options (e.g. `--json` and `--csv` together); Click convention |
| `3` | Input error — LOGFILE missing/unreadable, or stream had zero valid requests |
| `4` | **unique-cardinality exhaustion** — the unique-User-Agent set hit `--max-unique`; results are emitted but flagged truncated |

This exact `0/1/2/3/4` contract, with code `4` meaning unique-cardinality exhaustion, is
carried verbatim into [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) and
[CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md); it must not be omitted or remapped.

## Metric definitions

- **Top-10 IPs:** the `--top` most frequent client IPs across all valid requests.
- **Top-10 URLs by errors:** the `--top` URLs with the highest count of responses whose
  status is 4xx or 5xx (`400 <= status <= 599`).
- **Hourly request distribution:** for each hour `h` in `0..23`, the percentage
  `100 × hourly_request_count / total_valid_requests`. This is a scaled percentage, **not**
  an unscaled fraction. The 24 percentages sum to ~100 (rounding aside).
- **Unique User-Agent share:** `unique_user_agents / valid_requests`, reported as a ratio
  and a percentage; `unique_user_agents` is bounded by `--max-unique` (see exit code `4`).

## Packaging & deployment

- **Deployment target:** the engineer's local machine. Distribution via **PyPI**
  (`pip install logpulse`) and GitHub source. No servers, containers, cloud, or Kubernetes
  — consistent with the core decision.
- `pyproject.toml` defines a console entry point `logpulse = "logpulse.cli:main"`.
- Runtime deps: `click`, `rich`. Dev deps: `pytest`.

## Auth

None. There is no server, no network listener, and no multi-user surface, so there is
nothing to authenticate — a direct consequence of the "no HTTP API — CLI-only tool"
decision above.

## Architecture Decision Record (ADR)

### ADR-001: Stateless single-pass streaming over any persistence

- **Decision:** Hold only bounded aggregates in memory; never persist between runs.
- **Rationale:** Meets 1 GB/30 s with flat memory; matches "no database" constraint; removes
  the only component that could fill disk or corrupt.
- **Rejected alternative:** Embedded SQLite for "history" — rejected: adds state, schema,
  and IO cost for a value (cross-run history) the product explicitly does not offer.

### ADR-002: Bounded unique-UA cardinality with an explicit failure code

- **Decision:** Track unique User-Agents in a set capped by `--max-unique`; on breach, stop
  inserting, flag the result truncated, and exit `4`.
- **Rationale:** An unbounded set on adversarial/high-cardinality logs risks OOM. A bounded
  set plus a distinct exit code turns an ambiguous OOM into a clear, actionable signal for
  automation.
- **Rejected alternative:** HyperLogLog approximate counting — deferred (adds a dependency
  and approximation error); acceptable for a future `Could` iteration, unnecessary for MVP.

> **Note on adversarial review:** the Devil's Advocate / independent adversarial review for
> this architecture is run by the external harness in a separate fresh session and is *not*
> performed inline here.
