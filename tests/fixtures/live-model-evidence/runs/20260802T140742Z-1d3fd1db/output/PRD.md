# Product Requirements Document: nginx-log-report

## Product Summary

`nginx-log-report` lets DevOps/SRE engineers turn local nginx Combined Log Format input into a focused operational report in one streaming pass. It defaults to colored terminal text and supports stable JSON and CSV for pipelines. The MVP is local, stateless, open source, and installable with pip.

## Problem and Outcome

During incidents and routine troubleshooting, engineers often need only a few signals from a large access log. General analytics stacks take time to deploy and shell one-liners are fragile across quoting, malformed records, and multiple metrics. The desired outcome is a trustworthy report in under 30 seconds for a representative 1 GB file, without uploading or retaining log data.

## Goals

- Compute the four specified metrics in one input pass.
- Keep stdout deterministic and automation-safe in JSON/CSV modes.
- Provide useful malformed-input evidence without leaking full log lines.
- Install and run on CPython 3.11 through pip.
- Meet the documented 1 GB performance target on a representative laptop.

## Non-Goals

- Authentication, accounts, authorization, or multi-tenancy.
- Database, retained history, dashboards, HTTP API, or long-running server.
- Cloud, Docker, Kubernetes, agents, or centralized log collection.
- Arbitrary nginx `log_format`, compressed input, follow/tail mode, approximate counters, or URL normalization in MVP.
- Replacing full observability/search platforms.

## User Stories

### US-1: Identify the noisiest client IPs

As an on-call SRE, I want the ten client IP addresses with the most valid requests so that I can spot abusive or unexpectedly active clients.

Priority: **P0**

Acceptance criteria:

- [ ] Every valid parsed request increments exactly one IP count.
- [ ] Output contains at most ten IPs ordered by descending count with deterministic first-seen tie order.
- [ ] Empty input produces an empty ranked result, not a fabricated row or failure.

### US-2: Find routes producing client and server errors

As a service owner, I want the ten request targets with the most 4xx/5xx responses so that I can prioritize failing routes.

Priority: **P0**

Acceptance criteria:

- [ ] Statuses 400 through 599 inclusive contribute; 100 through 399 do not.
- [ ] The exact logged request target, including query string, is the grouping key.
- [ ] Output contains at most ten targets ordered by descending error count with deterministic tie behavior.

### US-3: Understand hourly traffic distribution

As a capacity engineer, I want request counts for every hour of day so that I can see peaks and quiet periods.

Priority: **P0**

Acceptance criteria:

- [ ] The report always contains exactly 24 buckets from `00` through `23`.
- [ ] Each valid request increments the hour encoded in its parsed nginx local timestamp.
- [ ] Hours without requests have a numeric zero count.

### US-4: Measure User-Agent diversity

As an incident responder, I want the share of distinct User-Agent values relative to valid requests so that I can quickly assess client diversity.

Priority: **P0**

Acceptance criteria:

- [ ] The numerator is the count of distinct non-missing User-Agent strings.
- [ ] The denominator is all valid parsed requests, including requests with a missing User-Agent.
- [ ] Empty input produces a `0.0` percent share and zero counts.
- [ ] The report exposes the numerator and denominator alongside the percentage.

### US-5: Consume reports in automation

As a DevOps engineer, I want JSON and CSV output modes so that scripts and pipeline steps can parse results without scraping terminal text.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` emits one valid schema-versioned JSON document and no ANSI escapes.
- [ ] `--csv` emits the documented five-column header and parseable RFC 4180-compatible rows.
- [ ] JSON and CSV are mutually exclusive and invalid combination exits with code 2.
- [ ] Diagnostics are written only to stderr and do not corrupt stdout.

### US-6: Choose strictness for malformed records

As an SRE, I want to skip and count malformed lines by default or stop immediately with `--strict` so that exploratory use and audited automation are both safe.

Priority: **P1**

Acceptance criteria:

- [ ] Default mode skips malformed lines, reports their count, and returns 0 if the report is otherwise generated.
- [ ] Strict mode stops at the first malformed line, returns 4, and identifies source and line number without echoing the full line.

### US-7: Follow a growing log

As an on-call SRE, I want an optional follow mode so that I can refresh the same metrics while an incident continues.

Priority: **P2**

Acceptance criteria:

- [ ] The feature is not included in MVP and cannot delay any P0 release criterion.
- [ ] Before implementation, its snapshot interval, interruption, and machine-output semantics are added to this PRD and the CLI architecture.

## Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-1 | Accept zero or more uncompressed file paths; read stdin when paths are absent or equal to a single `-` |
| FR-2 | Parse the conventional nginx Combined Log Format defined in `PROJECT_ARCHITECTURE.md` |
| FR-3 | Process records sequentially without retaining the input or using persistent storage |
| FR-4 | Compute top-10 IPs, top-10 4xx/5xx URLs, 24 hourly buckets, and unique User-Agent share exactly as specified |
| FR-5 | Render a default Rich terminal report with safe handling of untrusted log-derived strings |
| FR-6 | Render schema-versioned JSON through `--json` |
| FR-7 | Render normalized CSV through `--csv` |
| FR-8 | Honor the exit-code and stdout/stderr contract under `## CLI Interface` in `PROJECT_ARCHITECTURE.md` |
| FR-9 | Install through pip and expose `nginx-log-report` on Python 3.11 |

### P1 — Should ship after core behavior

| ID | Requirement |
|---|---|
| FR-10 | Support `--strict` and default skip/count malformed-line policies |
| FR-11 | Report malformed UTF-8 records through the same default/strict policy as syntax failures |
| FR-12 | Publish reproducible performance and peak-memory evidence |

### P2 — Could follow MVP

| ID | Requirement |
|---|---|
| FR-13 | Follow a growing file with `--follow` and periodic snapshot output |
| FR-14 | Accept additional named nginx log formats |
| FR-15 | Read gzip-compressed input while preserving stream semantics |

## Output Requirements

- Default text contains a summary and every requested metric; log-derived strings cannot activate Rich markup.
- JSON has `schema_version: 1` and the exact top-level fields documented in the architecture.
- CSV has exactly `metric,rank,key,value,unit` and the documented metric/unit vocabulary.
- All modes represent empty input successfully and consistently.
- Machine modes contain no color, progress bar, warning, or prose on stdout.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 | Median processing time for a deterministic representative 1 GB file is <30 s, no measured run >33 s | At least three runs with environment and fixture hash recorded |
| NFR-2 | Sequential processing; no whole-file reads or second pass | Iterator contract test and code review |
| NFR-3 | Peak RSS is measured and target is <256 MB for the representative fixture | Benchmark report |
| NFR-4 | Python 3.11 wheel installs and command runs in a clean environment | Build/install smoke test |
| NFR-5 | Total test coverage >=85%, with parser and aggregation edge cases | pytest coverage report |
| NFR-6 | No network calls, telemetry, persistent state, shell execution, or full-line error disclosure | Static review and integration tests |
| NFR-7 | Ctrl-C stops promptly and returns 130 without a partial machine document | CLI integration test |
| NFR-8 | Input lines and distinct keys remain inside the architecture's explicit resource envelope; violations return 5 without partial machine output | Boundary fixtures and CLI integration tests |

## Input and Error Policy

Supported syntax and field rules are owned by `PROJECT_ARCHITECTURE.md`. Unreadable input returns 3. A malformed line is counted and skipped by default; strict mode returns 4. Usage errors return 2. Unexpected defects return 70 and are never disguised as an empty successful report.

## Release Acceptance

- [ ] All P0 user-story acceptance criteria pass on file and stdin input.
- [ ] JSON and CSV are structurally parsed in tests, not accepted only by snapshots.
- [ ] Clean-wheel installation smoke test passes on CPython 3.11.
- [ ] The 1 GB benchmark meets NFR-1 with environment and peak RSS evidence.
- [ ] No critical/high security or review finding is unresolved.
- [ ] README examples match the installed command and output contracts.

## Kill Criteria

Stop or re-scope the MVP if any condition remains true after profiling and one focused optimization pass:

- Representative 1 GB processing median is 45 seconds or more on the declared laptop.
- Exact aggregation requires more than 512 MB peak RSS on the representative fixture and common realistic cardinality.
- More than 1% of lines from three representative intended-user samples fail the documented format parser.
- Stable JSON/CSV contracts cannot be delivered within the weekend without dropping a required metric.
- The design begins requiring a database, server, cloud resource, authentication, or non-$0 infrastructure to deliver its core value.

Crossing a kill criterion triggers a specification and architecture review; it does not authorize silently relaxing the criterion in code.

## Dependencies and Traceability

`STRATEGIC_PLAN.md` owns scope and priority, `PROJECT_ARCHITECTURE.md` owns parsing/CLI/schema decisions, and `IMPLEMENTATION_PLAN.md` maps requirements to concrete files and checks. Behavior changes start in this PRD and the architecture before implementation.
