# Project Architecture: Nginx Log Lens

## Architecture Drivers

- Local Python 3.11 CLI, installed with pip and operated by DevOps/SRE users.
- One streaming pass over file input or stdin; no full-log materialization.
- Four exact reports from supported, valid nginx Common/Combined lines.
- 1 GB processed in under 30 seconds on a documented laptop benchmark.
- Rich terminal output by default plus stable JSON and CSV pipeline formats.
- Zero-dollar, open-source, one-weekend delivery envelope.

The central decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. A database is wrong here because each invocation answers
questions about the supplied stream, persistence adds write amplification and
operations without serving an approved use case, and keeping raw logs local
reduces exposure. An HTTP API is wrong because the intended boundary is a
shell/pipeline command: a server would add lifecycle, networking,
authentication, deployment, and attack-surface concerns with no product value.

## Architecture Variants

### Variant A: Single-process layered CLI (Recommended)

- **Approach:** Click owns the boundary; a line parser yields immutable records;
  one aggregator updates counters; renderers consume one result snapshot.
- **Pros:** One pass, low coordination overhead, deterministic behavior, simple
  packaging and profiling.
- **Cons:** Exact counters grow with observed cardinality; CPU use is primarily
  single-core.
- **Best for:** The approved local one-weekend MVP and its 1 GB target.
- **Estimated complexity:** Low.

### Variant B: Multiprocess chunk workers

- **Approach:** Split seekable files into byte ranges, aggregate in workers,
  then merge partial counters.
- **Pros:** Can use multiple CPU cores on large regular files.
- **Cons:** Complex newline boundaries and timestamp parsing; merge memory;
  cannot naturally accelerate stdin; startup cost and nondeterministic errors.
- **Best for:** A later version backed by evidence that parsing is CPU-bound.
- **Estimated complexity:** High.

### Variant C: Unix pipeline of specialist commands

- **Approach:** Separate parser and metric processes communicate using a
  normalized stream.
- **Pros:** Components are independently composable.
- **Cons:** Multiple processes, serialization overhead, awkward coordinated
  errors, and repeated state; harder installation and cross-platform behavior.
- **Best for:** An ecosystem of reusable log-transform commands, not this MVP.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected. The user pre-approved the obvious single-process
architecture; it has the smallest delivery and operational surface and is the
only variant aligned with stdin, one weekend, and a $0 budget. Variants B and C
remain explicit rejected alternatives, not planned MVP work.

## CLI Interface

### Command

```text
nginx-log-lens [OPTIONS] [INPUT]
```

`INPUT` is one nginx access-log file path. If omitted or `-`, UTF-8 text is
read from stdin. The command never mutates the input.

### Options

| Option | Meaning | Default |
|---|---|---|
| `--json` | Emit one JSON document | Off |
| `--csv` | Emit long-form CSV | Off |
| `--input-format [auto|combined|common]` | Select or detect supported grammar | `auto` |
| `--max-unique-user-agents INTEGER` | Exact-UA cardinality ceiling; positive integer | `1000000` |
| `--color / --no-color` | Force or suppress terminal color | Auto from TTY/`NO_COLOR` |
| `--version` | Print version and exit | — |
| `--help` | Print usage and exit | — |

`--json` and `--csv` are mutually exclusive. Machine formats never include
ANSI escapes, progress displays, or non-data text on stdout. Diagnostics go to
stderr. Click performs usage validation before input is opened.

### Input Contract

Supported lines are nginx Common Log Format and Combined Log Format with a
bracketed timestamp containing a numeric UTC offset, quoted request, integer
status, and (for Combined) quoted User-Agent. Request parsing extracts the URL
token between method and protocol; `-` is accepted as a missing request or
User-Agent value. Lines are processed incrementally and line endings are
discarded. Auto detection is per non-empty line so compatible mixed
Common/Combined files remain processable.

Blank lines are ignored. A non-empty malformed line is a data error: the
command reports its line number and reason without echoing the raw line, emits
no report, and exits `3`. File decoding is strict UTF-8. An unreadable file or
decode/runtime I/O failure exits `1`.

Only successfully parsed non-empty lines are valid requests. Top client IPs
count all valid requests. Error URLs count statuses 400–599; missing request
URLs are excluded from that ranking but the request remains valid. Hours are
derived from each timestamp's written offset and labeled `00` through `23`.
For each hour, the percentage is exactly
`100 × hourly_request_count / total_valid_requests`. An empty/blank-only input
produces empty rankings, 24 zero-count/zero-percent hours, a zero UA summary,
and exit `0`.

For Common lines or Combined lines whose User-Agent is `-`, no UA observation
is added. `unique_user_agent_share_percent` is
`100 × unique_user_agent_count / total_user_agent_observations`, or `0` when
there are no observations. When adding a previously unseen User-Agent would
exceed `--max-unique-user-agents`, processing stops, no report is emitted, and
the command exits `4`.

### Output Contract

The default output is four Rich sections in this fixed order: top client IPs,
top error URLs, hourly distribution, and User-Agent diversity. Rankings contain
at most 10 entries and sort by descending count, then key in ascending Unicode
code-point order for deterministic ties. Percentages are rounded to two decimal
places using round-half-up for presentation; counts retain integer precision.

JSON is one UTF-8 object followed by a newline:

```json
{
  "schema_version": 1,
  "total_valid_requests": 0,
  "top_ips": [{"ip": "192.0.2.1", "count": 1}],
  "top_error_urls": [{"url": "/missing", "count": 1}],
  "hourly_distribution": [{"hour": "00", "count": 0, "percentage": 0.0}],
  "user_agents": {"observations": 0, "unique_count": 0, "unique_share_percentage": 0.0}
}
```

`hourly_distribution` always has 24 ordered entries. JSON percentages are
numbers rounded to two decimals; arrays may otherwise be empty.

CSV uses the header `section,rank,key,count,percentage`. It emits ranked rows
for `top_ips` and `top_error_urls`, 24 rows for `hourly_distribution`, and one
`user_agents` row whose `key` is `unique`; unused cells are empty. RFC 4180
quoting is handled by Python's `csv` module, and lines use `\r\n`.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Successful report, including empty input |
| `1` | Runtime or input/output failure, including unreadable input or UTF-8 decode failure |
| `2` | Click usage error, including invalid or conflicting options |
| `3` | Malformed non-empty log data; no report emitted |
| `4` | Unique-cardinality exhaustion; configured exact User-Agent ceiling exceeded |

No failure path emits a partial JSON/CSV/terminal report.

## Component Model

```text
Click boundary (`cli.py`)
  -> input stream (`input.py`)
  -> line parser (`parser.py`) -> AccessRecord (`models.py`)
  -> one-pass aggregator (`aggregate.py`) -> Report (`models.py`)
  -> selected renderer (`renderers/terminal.py|json.py|csv.py`)
```

| Module | Responsibility | Must not do |
|---|---|---|
| `src/nginx_log_lens/cli.py` | Options, dependency wiring, exception-to-exit mapping | Parse log grammar or compute metrics |
| `input.py` | Open stdin/path as a strict text stream | Buffer the entire file |
| `parser.py` | Convert one line to `AccessRecord` or typed parse error | Aggregate or render |
| `models.py` | Frozen dataclasses for records, ranking entries, hour buckets, report | Perform I/O |
| `aggregate.py` | Update counters and enforce UA cardinality limit | Know output format |
| `renderers/*` | Serialize the immutable report | Recompute metrics |
| `errors.py` | Typed domain failures and stable exit-code mapping | Print diagnostics |

`collections.Counter` stores IP and error-URL counts; a 24-element integer
array stores hours; a `set[str]` stores exact observed User-Agents up to the
configured ceiling. `heapq.nsmallest` (with a count-descending/key-ascending
key) or equivalent deterministic selection avoids sorting full counters where
practical. The log itself is never retained.

## Data Model

There are deliberately no database tables or migrations. In-memory dataclasses
are the complete transient model:

| Dataclass | Fields |
|---|---|
| `AccessRecord` | `ip: str`, `timestamp: datetime`, `url: str | None`, `status: int`, `user_agent: str | None` |
| `RankedCount` | `key: str`, `count: int` |
| `HourBucket` | `hour: int`, `count: int`, `percentage: Decimal` |
| `UserAgentSummary` | `observations: int`, `unique_count: int`, `unique_share_percentage: Decimal` |
| `Report` | `total_valid_requests: int`, `top_ips: tuple[RankedCount, ...]`, `top_error_urls: tuple[RankedCount, ...]`, `hourly_distribution: tuple[HourBucket, ...]`, `user_agents: UserAgentSummary` |

All report collections are immutable snapshots. The aggregator alone owns
mutable counters.

## Parsing and Processing Sequence

1. Click validates options and chooses stdout mode.
2. The input layer opens `INPUT` or wraps stdin without closing caller-owned stdin.
3. Each non-empty line is parsed once into an `AccessRecord`.
4. The aggregator increments request, IP, error-URL, hour, and UA state.
5. The UA set checks a new value against the ceiling before insertion.
6. End-of-stream finalization calculates percentages and deterministic top-10s.
7. Exactly one renderer writes the complete report to stdout.
8. A typed error maps to stderr and one code from `0/1/2/3/4`.

To prevent partial machine output, rendering builds a bounded result payload
only after aggregation succeeds. It does not buffer the input.

## Performance and Resource Budgets

- Complexity: `O(n)` parsing/aggregation for `n` valid lines; final ranking is
  `O(k log 10)` for `k` distinct keys.
- Input memory: `O(1)` beyond the current line.
- Aggregate memory: `O(I + E + U)`, for distinct IPs, error URLs, and bounded UAs.
- The UA ceiling is a correctness-preserving fail-fast limit, not approximate counting.
- Compile parsing expressions once and avoid per-line `datetime` objects if
  profiling shows hour extraction can be validated without them.
- Benchmark the installed console command against a fixed generated 1 GB
  fixture; record wall time, peak RSS, Python version, CPU, storage, and cache state.

The <30-second claim is an acceptance target, not an unmeasured guarantee.

## Error Handling and Observability

Domain exceptions include `InputError`, `LogParseError`, and
`UniqueCardinalityError`. The CLI converts them to codes `1`, `3`, and `4`.
Click owns code `2`. Diagnostics are concise, identify the input and line number
when safe, and never print a full log line. There is no telemetry or network
egress. Optional timing or debug output is out of MVP scope.

## Security and Privacy

- Treat every log field as untrusted data; renderers must escape/quote values.
- Rich output must not interpret log-derived markup.
- Never use `eval`, shell execution, or dynamic imports from log content.
- Do not follow a need for authentication: there is no server or shared state.
- Do not persist, upload, or silently sample IPs, URLs, or User-Agents.
- Bound line length (recommended 1 MiB) as an implementation guard; exceeding it
  is malformed data (`3`).

## Packaging and Deployment

Deployment means building a pure-Python wheel and source distribution from
`pyproject.toml`, then installing locally with pip. The console script is
`nginx-log-lens = nginx_log_lens.cli:main`. Runtime dependencies are Click and
Rich; Python requires `>=3.11,<4`. There is no Docker image, compose file,
daemon, database, cloud environment, or Kubernetes manifest because each would
contradict the approved local CLI boundary.

No application environment variables are required. Standard conventions are
honored: `NO_COLOR` suppresses color unless an explicit option takes priority,
and locale does not change JSON/CSV numbers or ordering.

## Testing Strategy

- Parser unit tests: valid Common/Combined, quoting, offsets, missing values,
  malformed status/timestamp/request, oversized line, and strict decoding.
- Aggregator unit tests: all four calculations, 4xx/5xx boundary statuses,
  deterministic ties, empty input, UA denominator, and exhaustion before insert.
- Renderer golden tests: terminal semantics without ANSI, JSON schema, RFC 4180 CSV.
- CLI integration tests: stdin/file parity, mutually exclusive flags, stderr,
  no partial output, and every exit code `0/1/2/3/4`.
- Property tests where useful: count conservation and hourly percentages summing
  to approximately 100 after presentation rounding for non-empty inputs.
- Performance test: generated 1 GB fixture on the declared reference laptop.

## Architecture Decision Record (ADR)

### ADR-001: Local single-process streaming pipeline

- **Status:** Accepted by pre-approved product decision.
- **Decision:** Use Variant A and the literal constraint stated at the top of this document.
- **Consequences:** Minimal operations and direct stdin support; exact aggregate
  state still scales with distinct IP/error URL values, while UA state is hard-bounded.
- **Rejected:** Multiprocessing until profiling justifies it; pipeline processes
  because their complexity does not serve the narrow MVP.

### ADR-002: Exact UA cardinality with explicit exhaustion

- **Status:** Accepted.
- **Decision:** Track exact unique non-missing User-Agents up to a configurable
  limit; fail with `4` before accepting the value that crosses it.
- **Consequences:** The reported share is exact when successful and never silently approximate.
- **Rejected:** HyperLogLog because approximation would weaken the simple output contract.

### Adversarial Review Status

No Devil's Advocate or independent architecture review was performed in this
session. Per the session boundary, the external harness will run the actual
review separately; this document does not anticipate or substitute its verdict.
