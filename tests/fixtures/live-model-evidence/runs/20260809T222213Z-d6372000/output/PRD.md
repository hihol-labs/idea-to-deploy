# Product Requirements Document: nginx-stream-report

## Product Summary

A local Python 3.11 CLI that streams standard nginx combined access logs and produces four operational summaries without authentication, persistence, network services, or cloud infrastructure. Default output is colored terminal text; JSON and CSV are stable pipeline formats.

## Goals

- Give an on-call engineer a correct traffic/error summary with one local command.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Preserve line-by-line input processing and explicit memory/failure behavior.
- Offer deterministic, documented text, JSON, and CSV contracts.
- Ship as an open-source, pip-installable package in one weekend for $0.

## Non-Goals

- Authentication, database storage, HTTP API, server process, cloud service, or Kubernetes deployment.
- Historical retention, dashboards, alerting, log shipping, tail/follow mode, arbitrary nginx formats, or distributed processing.
- Replacing GoAccess or the Elastic stack for exploratory and longitudinal analysis.
- Approximate unique counts in the MVP; exhaustion must be explicit rather than silently estimated.

## User Stories

### US-1 — Stream local or piped logs (P0)

As an on-call SRE, I want to read a log path or stdin line by line so that I can analyze large and piped logs without loading the entire file.

Acceptance criteria:

- [ ] Omitting `INPUT` and using `INPUT=-` both read stdin; a path reads that regular file.
- [ ] A valid empty input exits 0 with zero metrics.
- [ ] Malformed lines are skipped, counted, excluded from all denominators, and summarized on stderr.
- [ ] A missing, unreadable, undecodable, or mid-stream failed input exits 3 without a partial JSON/CSV document.
- [ ] A representative 1 GB input completes in under 30 seconds on the recorded laptop benchmark.

### US-2 — Identify top client IPs (P0)

As an SRE investigating traffic, I want the top 10 client IPs by request count so that I can spot dominant or suspicious sources.

Acceptance criteria:

- [ ] All valid requests contribute exactly once to their exact remote-address key.
- [ ] At most 10 entries are emitted, ordered by count descending and then key ascending.
- [ ] Counts agree across text, JSON, and CSV.

### US-3 — Identify error-producing URLs (P0)

As a service operator, I want the top 10 request targets returning 4xx or 5xx so that I can prioritize broken or abused routes.

Acceptance criteria:

- [ ] Statuses 400 through 599 inclusive contribute; other statuses do not.
- [ ] The exact request target, including query string, is the grouping key.
- [ ] At most 10 entries use deterministic count-descending/key-ascending ordering.

### US-4 — Understand hourly traffic (P0)

As a capacity investigator, I want every log-hour's request share so that I can see the daily traffic shape.

Acceptance criteria:

- [ ] Output always contains buckets `00` through `23` in ascending order.
- [ ] Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] The log timestamp's recorded numeric offset is respected when extracting the hour.
- [ ] With zero valid requests, every count and percentage is zero; otherwise unrounded percentages sum to 100% within numeric tolerance.
- [ ] Serialized percentages have two decimal places and use round-half-even.

### US-5 — Measure unique User-Agent share safely (P0)

As an SRE screening client diversity, I want an exact unique User-Agent count and share so that I can compare agent diversity without an undisclosed approximation.

Acceptance criteria:

- [ ] The unique count uses exact User-Agent strings from valid records; literal `-` is one value.
- [ ] Share is `100 × unique_user_agent_count / total_valid_requests`, or zero for no valid requests.
- [ ] The default maximum is 1,000,000 distinct User-Agents and can be set to another positive integer.
- [ ] Inserting a distinct value beyond the configured maximum emits no report and exits 4; duplicates at the cap remain valid.

### US-6 — Read a clear terminal report (P0)

As an engineer at a terminal, I want readable colored tables by default so that I can scan results quickly.

Acceptance criteria:

- [ ] Text is the default and presents the four required sections in the architecture-defined order.
- [ ] ANSI color is enabled automatically only for a TTY, can be forced/disabled by the documented option, and never appears in JSON/CSV.
- [ ] Untrusted log values cannot be interpreted as Rich markup.

### US-7 — Consume structured output (P0)

As a platform engineer, I want JSON or CSV so that I can use the report in pipelines.

Acceptance criteria:

- [ ] `--json` emits exactly one JSON schema-version-1 object to stdout.
- [ ] `--csv` emits the documented header and deterministic record order with RFC 4180 escaping.
- [ ] The flags are mutually exclusive and conflict exits 2.
- [ ] Diagnostics never contaminate stdout and formula-leading CSV key cells are neutralized.

### US-8 — Analyze gzip files directly (P1)

As an operator handling rotated logs, I want direct gzip input so that I do not need a decompression pipeline.

Acceptance criteria:

- [ ] Deferred beyond MVP; for MVP, `gzip -dc access.log.gz | nginx-stream-report --json` is documented.

### US-9 — Select ranking length (P2)

As an analyst, I want configurable top-N rankings so that I can inspect more than ten keys.

Acceptance criteria:

- [ ] Deferred; MVP output is fixed at 10 as required.

## Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept one path, stdin by omission, or `-`, and process decoded lines incrementally |
| FR-02 | Parse documented standard combined-log records and count malformed records |
| FR-03 | Produce the exact four metrics and deterministic ranking/tie behavior |
| FR-04 | Render terminal text by default and JSON/CSV on mutually exclusive flags |
| FR-05 | Keep result data on stdout and diagnostics on stderr |
| FR-06 | Enforce exact User-Agent cardinality before insertion |
| FR-07 | Implement the complete `0/1/2/3/4` exit-code contract from `PROJECT_ARCHITECTURE.md` |
| FR-08 | Install with pip on Python 3.11 and expose `nginx-stream-report` |

### P1 — Should ship after MVP

- Direct streaming decompression for `.gz` input with the same error and output semantics.

### P2 — Could ship later

- Configurable top-N while preserving deterministic ordering and schema compatibility.
- Additional explicitly named nginx formats backed by fixtures.

## Output and Exit Contract

The canonical command, options, JSON/CSV schemas, percentage rounding, and output order are in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. Exit statuses are invariant: `0` success, `1` internal/output failure, `2` CLI usage failure, `3` input/open/read/decode failure, and `4` unique-cardinality exhaustion. A change to this mapping requires a PRD and major interface review before code changes.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | Representative 1 GB log under 30 seconds | Recorded benchmark with machine, Python, storage, CPU, wall time, and peak RSS |
| NFR-02 | No raw-line or record-history retention | Code review plus peak-memory comparison across repeated-line fixtures |
| NFR-03 | Deterministic output | Golden tests repeated under different hash seeds |
| NFR-04 | Offline/private operation | Test or review confirms no network client and no file writes except shell-directed stdout |
| NFR-05 | Python 3.11 support | Clean-environment install and test job |
| NFR-06 | Safe untrusted-text rendering | Rich, JSON, and CSV injection fixtures |
| NFR-07 | Maintainability | Parser, aggregation, renderer, and CLI concerns remain independently tested |

## Release Acceptance

Release requires every P0 checkbox, automated coverage of all exit statuses, successful packaging/install, and benchmark evidence. Warnings about malformed lines may accompany exit 0, but an incomplete JSON/CSV payload is never acceptable. The spec documents are updated before any behavioral divergence.

## Kill Criteria

Pause and re-scope if profiling cannot achieve the 30-second gate on the agreed representative fixture, if common combined-log fixtures cannot be parsed reliably, or if exact cardinality cannot be bounded with exit 4. Do not expand into a server, database, cloud deployment, or Kubernetes solution.
