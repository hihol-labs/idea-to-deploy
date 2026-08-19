# Product Requirements Document: nginx-logtop

## Product Summary

`nginx-logtop` gives DevOps/SRE engineers a reproducible summary of nginx Combined Log Format data without sending logs off-machine or operating a service. It streams files or stdin once and reports top client IPs, top 4xx/5xx URL paths, hourly request distribution, and exact unique User-Agent share. The default is colored terminal text; JSON and CSV are stable pipeline interfaces.

## Problem and Goals

During incidents, engineers need answers faster than they can deploy a logging stack and with more reliability than a one-off shell pipeline. The MVP must:

- produce the four requested metrics correctly from local streams;
- be installable with `pip`/`pipx` on Python 3.11;
- separate human presentation from deterministic JSON/CSV contracts;
- process the approved 1 GB fixture in under 30 seconds on a documented laptop;
- fail explicitly when input is unusable or exact User-Agent cardinality cannot be retained.

Success does not include dashboards, historical queries, a server, or general nginx configuration support.

## Personas

1. **On-call SRE:** wants a concise, colored summary during an incident.
2. **Platform engineer:** wants a dependable replacement for recurring ad hoc shell pipelines.
3. **Incident analyst:** wants deterministic machine output for follow-on analysis and reports.

## User Stories

### US-1 — Stream local logs

As an on-call SRE, I want to pipe or name nginx access logs so that I can analyze data without copying it to a service.

Priority: **P0**

Acceptance criteria:

- [ ] With no paths, valid UTF-8 Combined Log Format received on stdin is processed line by line.
- [ ] One or more named files are processed in argument order without loading a whole file into memory.
- [ ] Missing/unreadable input returns `1`; empty or entirely invalid input returns `3`.
- [ ] Diagnostics go to stderr and never echo complete raw log lines.

### US-2 — Identify busiest client IPs

As an on-call SRE, I want the top ten client IP values so that I can quickly spot concentrated traffic sources.

Priority: **P0**

Acceptance criteria:

- [ ] Each valid record increments its exact source-IP text once.
- [ ] At most ten rows are returned, sorted by descending count then ascending IP text for ties.
- [ ] Counts and percentages use `total_valid_requests` as the denominator and match golden fixtures.

### US-3 — Identify error-producing URLs

As a platform engineer, I want the top ten URL paths producing 4xx/5xx responses so that I can triage client and server errors.

Priority: **P0**

Acceptance criteria:

- [ ] Only statuses `400..599` enter this ranking, with 4xx and 5xx combined.
- [ ] The grouping key is request path with query and fragment excluded; missing/unparseable request uses `-`.
- [ ] At most ten rows are sorted by descending count then ascending path for ties.
- [ ] A fixture containing 2xx, 3xx, 4xx, and 5xx records yields exactly the specified golden result.

### US-4 — See hourly request distribution

As an incident analyst, I want request volume split across clock hours so that I can see when traffic was concentrated.

Priority: **P0**

Acceptance criteria:

- [ ] Output includes all 24 logged-offset hour-of-day buckets, including zeros.
- [ ] Each percentage is calculated with the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] The denominator excludes malformed lines and the percentages sum to 100% before display rounding when at least one record is valid.

### US-5 — Measure User-Agent diversity exactly

As a platform engineer, I want the share of unique User-Agent values so that I can judge client diversity or suspicious automation.

Priority: **P0**

Acceptance criteria:

- [ ] The unique count is exact over valid records, including the literal nginx `-` category.
- [ ] Share percentage is `100 × distinct_user_agent_count / total_valid_requests`.
- [ ] `--max-unique-user-agents` is positive and defaults to `1_000_000`.
- [ ] If a new distinct value would exceed the ceiling, no partial report is emitted and the command returns `4` for unique-cardinality exhaustion.

### US-6 — Read a useful terminal report

As an on-call SRE, I want colored, clearly labeled terminal sections so that I can scan results under time pressure.

Priority: **P0**

Acceptance criteria:

- [ ] Default output contains a summary and the four required metric sections.
- [ ] Color is automatic for a TTY, can be forced/suppressed, and is absent from redirected output unless forced.
- [ ] Log-derived text cannot inject Rich markup.

### US-7 — Feed automation safely

As an incident analyst, I want JSON or CSV output so that I can pass results into scripts and spreadsheets.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` emits one valid, versioned JSON object and `--csv` emits the documented tidy schema.
- [ ] `--json` and `--csv` are mutually exclusive and their combination returns usage code `2`.
- [ ] Machine formats contain no ANSI, use stable ordering, and send diagnostics only to stderr.

### US-8 — Read gzip logs directly

As an SRE, I want to pass a `.gz` access log so that I can avoid a decompression pipe.

Priority: **P1**

Acceptance criteria:

- [ ] Deferred until every P0 criterion and performance gate is satisfied.
- [ ] When delivered, decompression remains streaming and corrupted gzip input follows the data-format policy.

### US-9 — Supply another nginx log grammar

As a platform engineer, I want to describe a custom nginx `log_format` so that the tool can cover nonstandard fleets.

Priority: **P2**

Acceptance criteria:

- [ ] Not part of the one-weekend MVP.
- [ ] Any future grammar must name required fields for all four metrics and preserve the same report schemas.

## Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-1 | Parse complete UTF-8 nginx Combined Log Format lines with quoted-field safety and timezone-aware timestamps |
| FR-2 | Stream stdin or ordered regular-file paths in a single process |
| FR-3 | Compute top ten IPs and top ten combined 4xx/5xx URL paths with deterministic ties |
| FR-4 | Emit all 24 hourly buckets using `100 × hourly_request_count / total_valid_requests` |
| FR-5 | Emit exact distinct User-Agent count and share with an explicit cardinality ceiling |
| FR-6 | Render Rich terminal text by default and stable JSON/CSV on request |
| FR-7 | Preserve stdout for reports, stderr for diagnostics, and exit codes `0/1/2/3/4` |
| FR-8 | Count malformed lines, continue when valid records remain, and return `3` when none do |
| FR-9 | Provide Click help/version and install as the `nginx-logtop` console script |

### P1 — Should ship later

| ID | Requirement |
|---|---|
| FR-10 | Stream gzip-compressed named input while preserving all failure semantics |

### P2 — Could ship later

| ID | Requirement |
|---|---|
| FR-11 | Support explicitly configured nginx log grammars after a separate design update |

## CLI and Output Contract

The normative command, option, input, schema, and exit-code details live under `## CLI Interface` in `PROJECT_ARCHITECTURE.md`. Product acceptance requires the complete mapping:

- `0`: success/help/version;
- `1`: operational I/O/output/internal failure;
- `2`: invalid CLI usage;
- `3`: input/data-format failure, empty input, or no valid records;
- `4`: unique-cardinality exhaustion.

No output mode changes metric definitions. Text, JSON, and CSV are presentations of the same immutable report.

## Non-Functional Requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| NFR-1 | Process a deterministic 1 GB fixture in under 30 seconds on the documented laptop | Command, hardware/Python profile, wall time, peak RSS, known-result check |
| NFR-2 | Never retain log data after process exit or transmit it over a network | Architecture inspection and tests without network/service dependencies |
| NFR-3 | Avoid whole-file reads | Instrumented incremental-read test and bounded-cardinality memory measurement |
| NFR-4 | Achieve at least 90% line coverage in parser, aggregation, and renderer modules | pytest coverage report |
| NFR-5 | Make machine output deterministic and locale independent | Golden JSON/CSV tests in multiple terminal settings |
| NFR-6 | Install and run on a clean Python 3.11 environment | Built-wheel smoke test |
| NFR-7 | Do not leak full invalid lines or allow terminal markup injection | error and renderer security tests |

## Out of Scope

- Authentication or user/account concepts.
- Any database, retained index, history, cache, or migration.
- HTTP API, daemon, server, webhook, or background worker.
- Cloud service, container platform, Docker requirement, or Kubernetes.
- Dashboard, browser UI, interactive TUI, alerting, or log tail/follow mode.
- Remote file fetching, SSH, S3, vendor integration, or telemetry.
- Approximate cardinality in the MVP.

## Dependencies and Assumptions

- Users provide nginx Combined Log Format in strict UTF-8.
- Python 3.11 is available locally.
- Click and Rich can be installed from the configured Python package source.
- “Hourly” means the 24 clock-hour buckets in each record's logged numeric offset, not UTC conversion and not a chronological per-date series.
- Benchmark acceptance is meaningful only with documented hardware and deterministic input.

## Release Acceptance

The MVP is releasable only when every P0 user-story criterion passes, wheel installation succeeds in a clean Python 3.11 environment, all three renderers agree on golden counts, every exit code is exercised, and the documented 1 GB performance gate passes. Completion must use the repository's current Idea to Deploy verification/adjudication process; narration alone is not evidence.

## Kill Criteria

Stop or explicitly revise the product specification if:

1. Correct Combined Log Format parsing plus exact metrics cannot meet the 1 GB / 30 s target after profiling on the reference machine.
2. Realistic exact User-Agent cardinality routinely exceeds the documented ceiling and users reject explicit exit `4`.
3. Users require persistent history, remote ingestion, or multi-user access; those needs belong to a different architecture and competitive category.
4. Stable JSON/CSV semantics cannot be maintained across the three presentations without mode-specific metric behavior.
