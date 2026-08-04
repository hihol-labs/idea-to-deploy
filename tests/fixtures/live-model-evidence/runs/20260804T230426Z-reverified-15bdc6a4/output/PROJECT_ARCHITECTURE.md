# Project Architecture: Nginx Stream Insights

## 1. Context and Constraints

The product is a local Python 3.11 CLI that consumes nginx access-log lines from one file or standard input and emits one report. The governing decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

Both constraints are correct here. A database would add installation, persistence, cleanup, schema, and privacy obligations while the required metrics can be accumulated during a single pass. An HTTP API would turn a local analysis command into a long-running service with authentication, networking, deployment, and attack-surface costs, none of which helps the one-shot SRE workflow. The process owns all state, emits a report, and exits.

Other hard constraints: $0 budget, open-source dependencies, pip installation, one-weekend delivery, no authentication/server/cloud/Kubernetes, and a 1 GB input target under 30 seconds on a documented laptop.

## 2. Architectural Drivers

1. Correct metrics with an explicit valid-record denominator.
2. Sequential I/O and bounded state for gigabyte inputs.
3. One canonical report model shared by terminal, JSON, and CSV.
4. Deterministic ranking and stable pipeline schemas.
5. Explicit failure behavior, especially exact-cardinality exhaustion.
6. Small, testable modules that remain feasible in one weekend.

## 3. Architecture Variants

### Variant A: One-pass modular CLI (Selected)

- **Approach:** Click invokes an iterator-based parser; a single aggregator updates counters/sets; one immutable report is rendered once.
- **Pros:** One read, works with stdin, low latency, bounded except for guarded exact User-Agent cardinality, simplest packaging.
- **Cons:** Exact unique User-Agent counting needs a hard memory guard; no retrospective queries.
- **Best for:** This local, one-shot incident-analysis tool.
- **Estimated complexity:** Low.

### Variant B: Two-pass exact analytics

- **Approach:** First pass discovers dimensions; second pass computes/report metrics.
- **Pros:** Some intermediate state can be reduced; simpler validation for selected calculations.
- **Cons:** Cannot operate naturally on stdin, doubles I/O, threatens the 30-second target.
- **Best for:** Seekable files where exact recomputation matters more than streaming.
- **Estimated complexity:** Medium.

### Variant C: External pipeline/database

- **Approach:** Ingest into an analytics engine or delegate to GoAccess/Elastic tooling.
- **Pros:** Queries, persistence, dashboards, broader formats.
- **Cons:** Violates the $0, local, stateless, no-database scope and weekend delivery target.
- **Best for:** Long-term fleet observability, which is out of scope.
- **Estimated complexity:** High.

### Recommendation

Variant A is selected because every required metric is incrementally computable, stdin is a first-class input, and the constraints explicitly favor a single local process. Variants B and C add cost without improving the approved MVP outcome.

## 4. System Context and Data Flow

```text
nginx log file OR stdin
          |
          v
 buffered text-line iterator
          |
          v
 NginxLineParser ---- malformed count / diagnostic sample
          |
       LogRecord
          |
          v
 ReportAccumulator
   | IP Counter
   | error-URL Counter
   | 24 hourly buckets
   | guarded User-Agent set
          |
      Report dataclass
       /      |      \
 terminal   JSON     CSV
```

Only parsed `LogRecord` values enter the accumulator. After each update, the record becomes unreachable. Renderers receive a finalized report, never the input stream or mutable accumulator.

## 5. Components and Responsibilities

| Module | Responsibility | Key public objects |
|---|---|---|
| `src/nginx_stream_insights/cli.py` | Click command, option validation, I/O lifecycle, exit mapping | `main()` |
| `src/nginx_stream_insights/models.py` | Typed immutable domain/report values | `LogRecord`, `RankedItem`, `Report` dataclasses |
| `src/nginx_stream_insights/parser.py` | Parse supported nginx combined/common lines and timestamps | `NginxLineParser`, `ParseError` |
| `src/nginx_stream_insights/aggregate.py` | Incremental metrics, deterministic top-N, cardinality guard | `ReportAccumulator`, `CardinalityLimitError` |
| `src/nginx_stream_insights/renderers/terminal.py` | Rich terminal report and color policy | `render_terminal()` |
| `src/nginx_stream_insights/renderers/json.py` | Stable JSON object | `render_json()` |
| `src/nginx_stream_insights/renderers/csv.py` | Stable normalized CSV rows | `render_csv()` |
| `src/nginx_stream_insights/io.py` | Open file/stdin with consistent decoding and close ownership | `open_input()` |

Dependencies point inward: CLI and renderers depend on models; parser and aggregator depend on models; the domain core does not import Click or Rich.

## 6. Data Model

There are no database tables or migrations. These are in-memory dataclasses:

| Dataclass | Field | Type | Invariant |
|---|---|---|---|
| `LogRecord` | `client_ip` | `str` | Non-empty parsed token; IPv4/IPv6 text retained |
|  | `timestamp` | `datetime` | Offset-aware nginx timestamp |
|  | `url` | `str` | Request target; query string retained in MVP ranking |
|  | `status` | `int` | 100–599 |
|  | `user_agent` | `str` | Quoted field; `-` is a valid literal value |
| `RankedItem` | `key` | `str` | Dimension value |
|  | `count` | `int` | Positive count |
| `Report` | `total_lines` | `int` | Valid plus malformed lines |
|  | `total_valid_requests` | `int` | Denominator for request percentages |
|  | `malformed_lines` | `int` | Lines rejected by parser |
|  | `top_ips` | `tuple[RankedItem, ...]` | At most 10 by `count DESC, key ASC` |
|  | `top_error_urls` | `tuple[RankedItem, ...]` | Only status 400–599; at most 10 |
|  | `hourly_percentages` | `tuple[float, ...]` | Exactly 24 values, hours 00–23 |
|  | `unique_user_agents` | `int` | Exact count if report succeeds |
|  | `unique_user_agent_share_percent` | `float` | `100 × unique_user_agents / total_valid_requests` |

The accumulator holds two `Counter[str]` maps, a fixed 24-integer list, and a guarded `set[str]` for User-Agents. IP and URL cardinality can still grow with distinct input; this is accepted for exact top-10 in the MVP and measured by the benchmark. The User-Agent set has an explicit default maximum because the required exit code names that exhaustion mode.

## 7. Metric Semantics

- **Top IPs:** count every valid request by exact `client_ip`; order by count descending and IP text ascending; return at most 10.
- **Top error URLs:** count the exact request target only when `400 <= status <= 599`; order by count descending and URL ascending; return at most 10.
- **Hourly request distribution:** use the local hour encoded in each log timestamp. For every hour, the percentage is exactly `100 × hourly_request_count / total_valid_requests`. If there are zero valid requests, all 24 percentages are `0.0` and the command exits `3` rather than presenting a successful report.
- **Unique User-Agent share:** `100 × unique_user_agents / total_valid_requests`, counting exact case-sensitive User-Agent strings among valid requests. If a new distinct value would exceed the configured cap, stop and exit `4`; never label a partial count as exact.
- **Malformed input:** rejected lines increment `malformed_lines` but do not contribute to any metric or denominator.

## CLI Interface

### Command

```text
nginx-stream-insights [OPTIONS] [INPUT]
```

`INPUT` is an optional path. Omit it or pass `-` to read UTF-8 text from stdin. The command reads one source per invocation and never writes to it.

### Options

| Option | Meaning | Default / validation |
|---|---|---|
| `--json` | Emit one JSON document | Mutually exclusive with `--csv` |
| `--csv` | Emit normalized CSV rows | Mutually exclusive with `--json` |
| `--top N` | Number of ranked IPs/error URLs | `10`; integer 1–100 |
| `--max-unique-user-agents N` | Exact-cardinality safety limit | `1_000_000`; positive integer |
| `--encoding NAME` | Input text encoding | `utf-8`; unknown codec is usage error |
| `--color / --no-color` | Force/disable ANSI color in terminal mode | Auto: enabled only for a TTY |
| `--version` | Print version and exit | — |
| `--help` | Print help and exit | — |

### Inputs

MVP accepts nginx combined and common access-log lines. Combined format supplies User-Agent; common-format lines treat the absent User-Agent as `-`. Quoting and escaped quotes are parsed explicitly; lines that do not match the grammar, contain an invalid timestamp/status, or cannot be decoded are input-data failures. Regular files are opened lazily with buffered text I/O; stdin ownership remains with the caller.

### Outputs

- **Terminal (default):** Rich headings/tables for metadata, top IPs, top error URLs, hourly percentages, and unique User-Agent share. Diagnostics go to stderr. ANSI is absent when redirected unless forced.
- **JSON:** stdout contains one object with schema version, input summary, `top_ips`, `top_error_urls`, 24 `hourly_distribution` entries, and `unique_user_agents` fields. No ANSI or commentary appears on stdout.
- **CSV:** stdout contains header `section,key,count,percentage` and normalized rows for ranked values, all 24 hours, and User-Agent summary. No ANSI or commentary appears on stdout.
- Percentages are rounded to two decimal places only at rendering; internal calculations retain full precision.

### Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Report completed successfully; malformed lines may be present but at least one valid request exists |
| `1` | Operational I/O failure, such as missing/unreadable input or broken output not caused by normal pipe closure |
| `2` | Click usage/option error, including incompatible formats or invalid numeric options |
| `3` | Input-data failure: no valid requests, unsupported/malformed content prevents a report, or decoding fails |
| `4` | Unique-cardinality exhaustion: exact distinct User-Agent count would exceed the configured cap |

Normal downstream pipe closure is handled quietly according to Unix convention; it must not produce a traceback.

## 9. Output Schemas

JSON uses `schema_version: 1` and these top-level keys: `input`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, `user_agents`. Ranked arrays contain `{value, count}`; hourly entries contain `{hour, count, percentage}`; User-Agent data contains `{unique_count, share_percentage, cardinality_limit}`.

CSV uses a single stable table so pipelines need no multi-document parsing. `section` is one of `summary`, `top_ip`, `error_url`, `hour`, or `user_agent`; absent numeric cells are empty, not overloaded with zero.

## 10. Error and Resource Handling

The CLI translates typed domain exceptions at one boundary and sends concise diagnostics to stderr. Parser errors include a line number and reason; at most the first five malformed examples are retained to keep memory bounded. Raw log lines are not echoed by default because URLs and User-Agents can contain secrets or personal data. Counters use Python integers. The cardinality check happens before inserting a new User-Agent, so exit `4` is deterministic.

## 11. Performance Design

- Iterate buffered lines; never call `read()` for the full file.
- Compile parsing machinery once and avoid per-record logging/object retention.
- Update primitive counters directly; create sorted lists only at finalization.
- Use `Counter.most_common()` followed by deterministic tie normalization for top-N.
- Benchmark wall time and peak RSS against a generated-but-fixed 1 GB corpus outside the package; document CPU, storage, OS, and Python patch version.
- Performance acceptance: three warm-cache runs, median under 30 seconds, with output redirected so terminal rendering is not the bottleneck.

## 12. Packaging, Configuration, and Deployment

The package uses `pyproject.toml`, a `src/` layout, and a console-script entry point named `nginx-stream-insights`. Runtime dependencies are Click and Rich with compatible bounded versions. There is no Docker Compose, container, daemon, environment-variable configuration, network port, database, or deployment target. Deployment means publishing a wheel/sdist and installing it into a local Python 3.11 environment with pip. All behavior is controlled by CLI options to keep invocation replayable.

## 13. Security and Privacy

The tool performs no network access and persists no log data. It treats file/stdin content as untrusted data, never as commands. Output quoting is delegated to JSON/CSV libraries and Rich text is rendered as literal data rather than markup. Diagnostics avoid raw records. Tests cover control characters, oversized tokens, hostile Rich markup, invalid encodings, and output-path failures. Users remain responsible for access permissions and downstream handling of IP addresses, URLs, and User-Agents.

## 14. Test Architecture

| Layer | Scope | Examples |
|---|---|---|
| Unit | Parser, accumulator, calculations, tie ordering | IPv6, escaped quotes, 399/400/599 boundaries, zero denominator |
| Property/invariant | Generated valid records | Hour counts sum to valid requests; percentages sum near 100% |
| Renderer contract | One frozen `Report` | JSON/CSV/terminal represent identical counts and percentages |
| CLI integration | Click runner and subprocess pipes | stdin/file, mutual exclusion, stderr separation, exit `0/1/2/3/4` |
| Performance | Fixed 1 GB corpus | Median wall time, peak RSS, stable result digest |
| Packaging | Clean virtual environment | wheel install, entry point, Python 3.11 |

## 15. Architecture Decision Record (ADR)

### ADR-001: One-pass process-local aggregation

- **Status:** Accepted.
- **Decision:** Select Variant A and keep all aggregation state process-local.
- **Consequences:** Minimal operations and stdin support; exact User-Agent cardinality needs a hard cap; there is no historical query capability.

### ADR-002: Exact metrics with guarded cardinality

- **Status:** Accepted.
- **Decision:** Provide exact counts only. Stop with exit `4` if the User-Agent set cap is exceeded rather than silently switching to an approximation.
- **Consequences:** Pipeline consumers can trust semantics; extreme-cardinality logs require a higher explicit cap or a future approximate mode.

### Self-Critique Debate Summary

This was a self-critique because the benchmark explicitly has no independent reviewer or subagent transport. It is not represented as an independent or adversarial review.

**Verdict:** APPROVE WITH CONDITIONS.

1. **All exact IP/URL counters can also grow with cardinality.** Resolution: accept this scoped risk, measure peak RSS on the 1 GB corpus, and record approximate heavy hitters as a future option only if the memory KPI fails.
2. **Regex-centric parsing can be slow or mishandle escapes.** Resolution: isolate the parser behind fixtures, compile once, benchmark early, and permit a hand-written scanner without changing domain contracts.
3. **Common format has no User-Agent.** Resolution: define the absent value as `-` so valid-request and User-Agent denominators remain explicit and reproducible.
4. **Malformed lines could make a nominally successful report misleading.** Resolution: always expose valid/malformed totals and exit `3` when no valid request remains.
5. **CSV has heterogeneous report sections.** Resolution: use a normalized schema with an explicit `section` discriminator and contract tests.
6. **A 30-second claim is hardware-sensitive.** Resolution: define the benchmark protocol and require reference-machine details with results.

**Alternatives considered and rejected:** two-pass processing is incompatible with stdin and doubles I/O; SQLite adds persistence and schema cost without improving the one-shot report; GoAccess/Elastic delegation breaks the focused pip-installable product contract; approximate cardinality would weaken the required exact share unless introduced later as an explicit separate mode.

## 16. Traceability

Product priorities and risks originate in `STRATEGIC_PLAN.md`. User-observable acceptance criteria are in `PRD.md`. Module/file sequencing and verification commands are in `IMPLEMENTATION_PLAN.md`; prompts for implementing those steps are in `CLAUDE_CODE_GUIDE.md`.
