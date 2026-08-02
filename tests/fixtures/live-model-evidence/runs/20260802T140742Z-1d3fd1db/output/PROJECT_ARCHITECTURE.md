# Project Architecture: nginx-log-report

## Architecture Drivers

- Local Python 3.11 CLI, installable through pip.
- One-pass streaming processing of nginx access logs.
- Four exact metrics: top-10 IPs, top-10 4xx/5xx URLs, hourly requests, unique User-Agent share.
- Human-first Rich output plus machine-stable JSON and CSV.
- Target: 1 GB in under 30 seconds on a documented laptop.
- $0 budget and one-weekend delivery.
- No long-running operational surface.

## Architecture Variants

### Variant A: Single-process streaming pipeline (Recommended and approved)

- **Approach:** Click validates the command, a generator reads and parses one line at a time, an in-memory aggregator updates counters, and exactly one renderer emits the final report.
- **Pros:** one input pass, simple installation, no IPC or persisted state, direct profiling, predictable failure behavior.
- **Cons:** exact high-cardinality counters consume memory proportional to distinct IPs/URLs/User-Agents; CPU work remains single-process.
- **Best for:** local one-shot analysis of files up to the stated 1 GB target.
- **Estimated complexity:** Low.

### Variant B: Unix pipeline of separate parser and metric processes

- **Approach:** parse records into an intermediate stream consumed by independent metric commands.
- **Pros:** composable stages and potential parallel consumers.
- **Cons:** serialization/IPC overhead, more commands and failure modes, harder cross-platform packaging, and repeated or buffered streams.
- **Best for:** teams already standardizing on shell-composed log processors.
- **Estimated complexity:** Medium.

### Variant C: SQLite staging and SQL reports

- **Approach:** parse each record into a temporary SQLite database, then query metrics.
- **Pros:** exact high-cardinality aggregation can spill to disk; ad hoc queries become possible.
- **Cons:** violates stateless/no-database scope, adds writes and cleanup, increases latency and complexity.
- **Best for:** repeated exploratory queries over a retained dataset, which is outside this product.
- **Estimated complexity:** Medium.

### Recommendation

Variant A is selected because the architecture is pre-approved, the input is local, the reports are fixed, the budget is $0, and delivery is one weekend. Variant B adds coordination without improving the fixed report. Variant C solves persistence and repeated-query problems the product explicitly does not have.

## Architecture Decision

**no database — stateless streaming processing; no HTTP API — CLI-only tool**

Both constraints are correct here. A database would duplicate the source log, introduce schema/migration/cleanup work, and turn an ephemeral report into a state-management problem. Exact counters and 24 hourly buckets can be updated during a single scan and discarded after rendering. An HTTP API would require a server lifecycle, authentication and request limits, deployment, and network threat handling while providing no benefit to a user who already has a local file or stdin stream. Click options and stdout/stderr are the complete interaction boundary.

Consequently:

- **Database schema/tables/indexes:** none; data lives only in process memory for the command lifetime.
- **HTTP endpoints/request/response bodies:** none; JSON and CSV are stdout serialization contracts, not APIs.
- **Authentication/authorization flow:** none; operating-system file permissions and shell execution identity are the trust boundary.
- **Docker/Compose/Kubernetes:** none; pip installation is the deployment mechanism.
- **Environment variables:** none required for MVP; explicit CLI options take precedence over ambient configuration.

## System Context and Flow

```text
local file(s) or stdin
        |
        v
 buffered binary/text reader -> line decoder -> combined-log parser
                                                | valid record
                           malformed counter <--+--> streaming aggregator
                                                        |
                                                        v
                                               immutable report model
                                                        |
                                  +---------------------+--------------------+
                                  v                     v                    v
                            Rich text stdout       JSON stdout          CSV stdout
                                  ^                     ^                    ^
                                  +---------- diagnostics to stderr --------+
```

The hot path never calls Rich and never constructs output rows. Rendering begins only after end-of-input. The program holds no full log lines after parsing.

## Component Boundaries

| Module | Responsibility | Key types/functions | Must not do |
|---|---|---|---|
| `src/nginx_log_report/cli.py` | Click command, option validation, stream ownership, exit mapping | `main`, `OutputMode`, `RunConfig` | Parse log syntax or calculate metrics |
| `src/nginx_log_report/parser.py` | Decode and parse supported nginx lines | `AccessRecord`, `ParseError`, `parse_line` | Print, retain input, aggregate |
| `src/nginx_log_report/aggregate.py` | Update exact counters and finalize sorted results | `StreamingStats`, `Report`, `consume` | Read files or choose output format |
| `src/nginx_log_report/render/text.py` | Rich tables and summary | `render_text` | Affect machine-output modes |
| `src/nginx_log_report/render/json.py` | Stable JSON document | `render_json` | Emit color or diagnostics |
| `src/nginx_log_report/render/csv.py` | Stable normalized CSV rows | `render_csv` | Invent undocumented columns |
| `src/nginx_log_report/io.py` | Open files/stdin, decoding policy, source labels | `iter_lines`, `InputError` | Parse records or aggregate |
| `src/nginx_log_report/errors.py` | Typed failures and exit-code mapping | error hierarchy | Catch unexpected defects silently |

## Data Model and Algorithms

`AccessRecord` is a frozen dataclass containing `remote_addr: str`, `timestamp: datetime`, `request_target: str`, `status: int`, and `user_agent: str | None`. Only fields required for the report survive parsing.

`StreamingStats` contains:

- `total_valid: int` and `malformed: int`.
- `ip_counts: Counter[str]` for every valid request.
- `error_url_counts: Counter[str]` only when `400 <= status <= 599`.
- `hour_counts: list[int]` of length 24, indexed by the hour encoded in each log timestamp.
- `user_agents: set[str]` for non-missing User-Agent values and `user_agent_observations: int`.

The supported exact-processing envelope is: physical line length at most 64 KiB (including delimiter), at most 100,000 distinct IPs, at most 250,000 distinct error URLs, and at most 100,000 distinct non-missing User-Agent values per invocation. Limits are checked before inserting a new key. Exceeding one returns exit code 5 with the limit name and observed threshold on stderr; no partial JSON/CSV document is emitted. These limits make memory behavior enforceable while remaining above the representative fixture profile. They are product limits, not silent approximation.

At finalization, `Counter.most_common(10)` produces each ranked list. Ties follow first-seen order as provided by Python's insertion-ordered dictionaries; this deterministic rule is part of the output contract. The unique User-Agent share is:

```text
100 * count(distinct non-missing User-Agent values) / count(valid requests)
```

It is `0.0` for empty input. Missing User-Agent values do not enter the distinct set but remain in the denominator. This metric is explicitly a **User-Agent diversity percentage**, not the percentage of requests that supplied a User-Agent. The report exposes `unique_user_agents`, `user_agent_observations`, and `valid_requests` so consumers can audit missing values and recompute the ratio. The canonical percentage is rounded to six decimal places using decimal half-up rounding; JSON emits that value as a number, CSV emits exactly six fractional digits, and terminal text displays two fractional digits.

Time complexity is O(n + u log 10 + i log 10), effectively O(n) for `n` lines. Memory is O(I + U + A), where `I`, `U`, and `A` are distinct IP, error-URL, and User-Agent cardinalities. This is bounded by input cardinality, not file byte size; adversarial cardinality must be included in benchmarks.

## Supported Input Format

MVP supports nginx Combined Log Format with the conventional fields:

```text
$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
```

- Input is binary-split with the bounded reader, then each bounded line is decoded as strict UTF-8. Invalid UTF-8 makes the line malformed. MVP deliberately has no arbitrary encoding option; this keeps newline detection, error counts, and performance deterministic.
- Request target is the second token of the quoted request field. A missing/malformed request target makes the line malformed.
- The URL key preserves the logged request target, including query string, because rewriting it would change evidence. Normalization is a possible later option, not MVP behavior.
- Status must be a three-digit integer from 100 through 599.
- Timestamp hour is taken from nginx's logged local timestamp; offsets are parsed for validity but hourly buckets represent each record's logged local hour.
- Blank lines are malformed lines.
- Multiple input files are consumed in argument order; stdin may be selected with `-` and cannot be mixed with another `-`.
- A physical line may contain at most 65,536 bytes including its newline. The reader consumes fixed-size chunks; when a record crosses the limit it stops buffering that record, drains through the next newline, then skips/counts it in default mode or fails in strict mode.
- Quoted fields accept nginx default escaping: escaped quote, escaped backslash, and hexadecimal byte escapes. A trailing backslash, invalid hex escape, unescaped control byte, or unbalanced quote makes the line malformed. Parsed escapes are treated as data and never as Rich markup or shell syntax.

## CLI Interface

### Command

```text
nginx-log-report [OPTIONS] [INPUTS]...
```

`INPUTS` is zero or more readable file paths. With no paths, or with one path equal to `-`, the command reads stdin. The command processes uncompressed regular files and non-seekable stdin streams; compressed files and follow/tail mode are outside MVP.

### Options

| Option | Meaning | Default / validation |
|---|---|---|
| `--json` | Emit one JSON document | Mutually exclusive with `--csv`; disables color |
| `--csv` | Emit normalized CSV rows | Mutually exclusive with `--json`; disables color |
| `--strict` | Stop on the first malformed line | Off; otherwise malformed lines are skipped and counted |
| `--no-color` | Disable terminal color | Automatically effective when stdout is not a TTY |
| `--version` | Print version and exit | No input consumed |
| `--help` | Print usage and exit | No input consumed |

### Inputs and stream ownership

- Each file is opened read-only and closed by the command.
- Stdin is consumed but never closed by application code.
- Results go only to stdout. Warnings, skipped-line counts, and errors go only to stderr.
- Ctrl-C stops promptly and produces exit code 130 without a partial machine-format document.

### Text output

The default report contains a processing summary, a ranked top-IP table, a ranked top-error-URL table, a 24-row hourly distribution, and a unique User-Agent summary. Color is used only on a TTY unless explicitly disabled. Empty ranked sections display `No matching requests`; all 24 hourly buckets remain visible with zero counts.

### JSON output

The UTF-8 JSON document uses this stable top-level shape:

| Field | Type | Contract |
|---|---|---|
| `schema_version` | integer | `1` for this contract |
| `summary` | object | `valid_requests`, `malformed_lines`, `unique_user_agents`, `user_agent_observations`, `unique_user_agent_share` |
| `top_ips` | array | Up to 10 objects with `rank`, `ip`, `requests` |
| `top_error_urls` | array | Up to 10 objects with `rank`, `url`, `errors` |
| `hourly_requests` | array | Exactly 24 objects with zero-padded `hour` and `requests` |

Numbers remain JSON numbers, keys are emitted consistently, and no ANSI escapes or human diagnostics appear on stdout.

### CSV output

CSV begins with exactly:

```text
metric,rank,key,value,unit
```

Rows use metric values `top_ip`, `top_error_url`, `hourly_requests`, `unique_user_agents`, `user_agent_observations`, and `unique_user_agent_share`. `rank` is populated only for ranked metrics; `key` is the IP, URL, hour (`00`–`23`), or empty for scalar metrics. `unit` is `requests`, `errors`, `agents`, `observations`, or `percent`. RFC 4180-compatible quoting protects commas, quotes, and newlines in values.

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Report generated successfully, including empty input or skipped malformed lines in default mode |
| 2 | Click usage/option error, including `--json --csv` |
| 3 | Input open/read/decode configuration failure |
| 4 | Strict parsing failure |
| 5 | Documented resource envelope exceeded (line size or distinct-key limit) |
| 70 | Unexpected internal error; concise message on stderr |
| 130 | Interrupted by user |

## Error Handling and Observability

Errors carry source name and one-based line number where available, never echo an entire potentially sensitive log line, and truncate any token excerpt. Default mode completes with exit code 0 while reporting the malformed count to stderr. Strict mode fails immediately with exit code 4 and emits no JSON/CSV result. A resource-envelope violation fails with exit code 5 in either mode. `MemoryError` is caught at the orchestration boundary, reported as resource exhaustion without a traceback or partial machine document, and also maps to 5. Internal exceptions are not converted into successful empty reports.

No telemetry, log upload, network call, or usage tracking is permitted. Benchmark output records elapsed wall time, peak RSS, Python version, OS, CPU, and fixture characteristics locally.

## Performance Strategy

- Buffered sequential reads and a precompiled parser.
- No `read()`, `readlines()`, whole-file split, pandas, or per-line Rich work.
- Parse only fields needed by the report.
- Update integer counters in place; construct dataclass report objects once.
- Benchmark a deterministic 1 GB realistic fixture (50,000 IPs, 100,000 error URLs, 20,000 User-Agents, 0.1% malformed lines, mixed request lengths) and a boundary fixture approaching every documented cardinality and line-size limit.
- Run an early hot-path spike before renderer work and record decode, parse, aggregation, total wall time, and peak RSS separately. If total projected runtime exceeds 30 seconds, profile and decide on a lower-allocation scanner before feature work continues.
- Profile before changing parsing strategy. If the target is missed, first reduce allocations; native extensions or multiprocessing require a new architecture decision.

Acceptance for the performance requirement is the median of at least three measured runs under 30 seconds on the declared reference laptop, with no run over 33 seconds and peak RSS below 256 MB for the realistic fixture. The boundary fixture must complete within the limits with peak RSS reported; it is a robustness measurement rather than the <30-second KPI. Exact success for inputs outside the documented envelope is not promised.

## Security and Privacy

The tool treats every log field as untrusted data. Renderers escape/quote values for their format, Rich markup is disabled or escaped for log-derived strings, file paths are never executed, and diagnostics avoid full log disclosure. There is no privilege escalation, secret storage, network access, plugin loading, or shell invocation. Symlink behavior follows normal OS file-open semantics and is documented rather than hidden.

## Packaging and Deployment

The package uses a `src/` layout and a PEP 517 `pyproject.toml`. The console entry point is `nginx-log-report = nginx_log_report.cli:main`. Supported runtime is CPython 3.11. Installation paths are `pip install nginx-log-report` after publication or `pip install .` from source. Release verification uses a clean virtual environment, builds wheel and sdist, installs the wheel, runs `--version`, and exercises stdin in all three output modes.

There is no server deployment, container image, compose file, cloud account, or Kubernetes manifest.

## Architecture Decision Record (ADR)

### ADR-001: Single-process, exact, stateless aggregation

- **Status:** Accepted (pre-approved).
- **Decision:** Use Variant A with exact in-memory counters and one input pass.
- **Consequences:** Minimal runtime and operational complexity; memory scales with distinct values. The 1 GB performance target must include a cardinality profile.
- **Rejected:** multi-process Unix pipeline (coordination overhead), SQLite staging (persistence and writes), ELK-style service (scope/cost mismatch).

### ADR-002: Fixed Combined Log Format for MVP

- **Status:** Accepted.
- **Decision:** Parse the conventional combined format and fail/skip explicitly when lines do not match.
- **Consequences:** Weekend delivery remains credible; custom `log_format` users need later parser extensions.

### ADR-003: Enforced resource and UTF-8 envelope

- **Status:** Accepted after adversarial review.
- **Decision:** Use a 64 KiB bounded binary line reader, strict UTF-8 per line, explicit distinct-key ceilings, and exit code 5 for resource-limit failures.
- **Consequences:** Streaming memory claims become testable and unsafe inputs fail predictably. Some syntactically plausible, extreme-cardinality or legacy-encoded inputs are explicitly unsupported rather than approximated.

### Debate Summary

The architecture was reviewed by the repository-local Devil's Advocate agent.

**Verdict:** APPROVE WITH CONDITIONS — all five conditions are resolved in this revision.

**Challenges raised:**

1. Exact aggregation lacked an enforceable memory envelope. **Resolution:** cardinality, 64 KiB line, 256 MB representative-fixture, and exit-code-5 contracts are now explicit.
2. The 1 GB performance driver had no early evidence gate. **Resolution:** the plan includes a hot-path projection and records realistic and boundary fixture measurements. Final performance remains unverified until implementation, as expected for a planning-only blueprint.
3. Untrusted lines could allocate without a bound and escaping was ambiguous. **Resolution:** a chunked bounded reader and accepted/rejected nginx escape grammar are specified.
4. Arbitrary encoding conflicted with replacement counting and exit semantics. **Resolution:** `--encoding` was removed; MVP is strict UTF-8 and decoding failures follow the malformed-line policy.
5. User-Agent share and numeric precision were underspecified. **Resolution:** the metric is defined as diversity percentage, observations are exposed, and rounding/serialization rules are fixed.

**Alternatives considered and rejected:**

- SQLite/disk-backed exact aggregation — rejected because exact success outside the supported envelope is not an MVP requirement and disk staging violates the approved stateless boundary.
- Approximate heavy-hitter algorithms — rejected because they would silently weaken the requested exact top-10 report.
- Arbitrary codec support — rejected for MVP because it expands the I/O state machine and undermines a deterministic weekend performance target.

## Testing Strategy

- Parser unit tests cover valid, missing, escaped, malformed, status-boundary, Unicode, and oversized-field cases.
- Aggregator unit tests cover ties, empty input, error filtering, all 24 hours, and User-Agent denominator rules.
- Renderer golden tests parse JSON/CSV structurally and normalize Rich output without relying only on snapshots.
- CLI integration tests cover stdin, multiple files, unreadable files, strict/default malformed behavior, mutual exclusions, stderr isolation, and exit codes.
- Packaging smoke tests install the built wheel into a clean environment.
- A reproducible benchmark validates time and memory against the 1 GB target.

`PRD.md` defines behavioral acceptance. `IMPLEMENTATION_PLAN.md` maps these boundaries to files and executable checks.
