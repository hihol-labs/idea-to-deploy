# Product Requirements Document: nginx-insight

## Product Summary

`nginx-insight` is a local Python 3.11 CLI that lets DevOps and SRE engineers obtain four deterministic summaries from nginx common or combined access logs without a server, database, cloud service, or retained state. It reads files or stdin, defaults to colored terminal text, and supports JSON and CSV for pipelines.

## Problem

During incident triage, operators frequently need a quick answer to who is generating traffic, which URLs are failing, when traffic occurs, and how diverse clients are. Existing observability stacks are expensive to deploy for an ad hoc local log, while shell one-liners are difficult to reproduce and expose as a stable automation contract.

## Goals and Success Criteria

- Produce exact top-10 IP and error-URL rankings for all valid input records.
- Produce a 24-hour percentage distribution using `100 × hourly_request_count / total_valid_requests`.
- Produce exact distinct User-Agent share within the documented cardinality ceiling.
- Offer human-readable terminal output plus machine-readable JSON and CSV from one report model.
- Process a representative 1 GB log in under 30 seconds on the documented reference laptop.
- Install through pip and require no service or paid resource.

## Non-Goals

- Authentication, user accounts, database storage, HTTP API, server mode, web UI, cloud deployment, Docker requirement, or Kubernetes.
- Historical dashboards, log retention, alerting, tail-follow mode, distributed processing, or telemetry.
- Arbitrary custom nginx `log_format` parsing in the MVP.
- Approximate metrics or silent degradation when exact User-Agent cardinality cannot be retained.

## User Stories

### US-1: Identify high-volume client IPs

As an on-call SRE, I want the ten client IPs with the most valid requests so that I can spot traffic concentration during an incident.

**Priority:** P0

**Acceptance criteria:**

- [ ] Every valid request increments exactly one parsed client IP.
- [ ] At most ten rows are returned, ordered by count descending then IP string ascending.
- [ ] The result is identical across terminal, JSON, and CSV for the same input.
- [ ] Malformed lines never contribute to a count.

### US-2: Locate failing URLs

As an SRE, I want the ten request targets with the most 4xx/5xx responses so that I can focus diagnosis on the endpoints producing errors.

**Priority:** P0

**Acceptance criteria:**

- [ ] Only statuses 400 through 599 contribute.
- [ ] 4xx and 5xx counts are combined per raw request target.
- [ ] At most ten rows are ordered by count descending then URL ascending.
- [ ] Query strings remain part of the raw request target for MVP grouping.

### US-3: Understand hourly traffic shape

As a platform engineer, I want each hour’s request count and percentage so that I can identify traffic concentration by time of day.

**Priority:** P0

**Acceptance criteria:**

- [ ] Exactly 24 buckets, hours 0 through 23, are emitted in ascending order.
- [ ] Each record is bucketed using the hour and offset recorded in its nginx timestamp; no time-zone conversion occurs.
- [ ] Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`, not an unscaled fraction.
- [ ] Displayed percentages are rounded to two decimal places and raw counts remain available in JSON and CSV.

### US-4: Measure User-Agent diversity

As an operator, I want the share of distinct nonempty User-Agents so that I can quickly assess client diversity or automation concentration.

**Priority:** P0

**Acceptance criteria:**

- [ ] The numerator is the exact number of distinct, nonempty User-Agent strings.
- [ ] The value is `100 × distinct_nonempty_user_agent_count / total_valid_requests` and is displayed to two decimal places.
- [ ] Repeated User-Agent strings contribute once to the numerator, while missing or `-` values do not.
- [ ] Exceeding the configured exact-cardinality ceiling emits no partial report and exits with code 4.

### US-5: Automate analysis in pipelines

As a DevOps engineer, I want stable JSON and CSV outputs so that I can feed metrics into shell and reporting workflows.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits one valid UTF-8 JSON object with `schema_version: 1` and all four metrics.
- [ ] `--csv` emits the documented `section,key,count,percentage` columns with library-correct quoting.
- [ ] JSON and CSV stdout never contains ANSI escapes or diagnostics.
- [ ] Supplying both flags is a usage error with exit code 2.

### US-6: Diagnose input quality safely

As an on-call engineer, I want malformed lines reported without corrupting useful output so that I can judge whether a report is trustworthy.

**Priority:** P0

**Acceptance criteria:**

- [ ] By default, malformed nonblank lines are skipped, counted, and summarized on stderr.
- [ ] With `--fail-on-invalid`, any malformed nonblank line prevents report output and exits with code 3.
- [ ] An input with no valid requests emits no report and exits with code 3.
- [ ] Operational and usage failures follow the complete `0/1/2/3/4` exit contract.

### US-7: Analyze rotated compressed logs directly

As a platform engineer, I want `.gz` file input so that I do not need a separate decompression command for routine rotations.

**Priority:** P1

**Acceptance criteria:**

- [ ] A gzip file produces the same report as its decompressed bytes.
- [ ] Corrupt gzip data is an operational failure with exit code 1.
- [ ] Streaming decompression does not materialize the entire file.

### US-8: Change the ranking size

As an advanced operator, I want to configure top-N so that I can inspect more or fewer ranked entries.

**Priority:** P2

**Acceptance criteria:**

- [ ] A later option accepts a positive bounded integer while retaining the same tie-break rules.
- [ ] Default behavior remains top 10 for compatibility.

## Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Consume one or more files sequentially, or stdin when no path is supplied, in a single pass |
| FR-2 | P0 | Parse supported common and combined nginx records into typed values and count invalid nonblank lines |
| FR-3 | P0 | Rank up to ten IPs by total valid-request count with deterministic ties |
| FR-4 | P0 | Rank up to ten raw request targets by combined 400–599 count with deterministic ties |
| FR-5 | P0 | Emit 24 hourly counts and percentages calculated as `100 × hourly_request_count / total_valid_requests` |
| FR-6 | P0 | Calculate exact distinct nonempty User-Agent share, protected by a configured cardinality ceiling |
| FR-7 | P0 | Render one shared report model as colored terminal text, JSON schema version 1, or normalized CSV |
| FR-8 | P0 | Keep report data on stdout and diagnostics on stderr |
| FR-9 | P0 | Enforce exit codes `0/1/2/3/4`, where 4 exclusively means unique-cardinality exhaustion |
| FR-10 | P0 | Emit no partial report for codes 1, 2, 3, or 4 |
| FR-11 | P1 | Stream `.gz` file input when time remains after P0 completion |
| FR-12 | P2 | Add configurable top-N without changing the default |

## CLI and Output Contract

The normative commands, options, inputs, output schemas, and exit codes are defined under `## CLI Interface` in `PROJECT_ARCHITECTURE.md`. The PRD adopts that contract without remapping it. In brief: code 0 is success, 1 operational failure, 2 usage failure, 3 input-data failure, and 4 unique-cardinality exhaustion.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 Performance | Representative 1 GB combined log completes in <30 seconds on the recorded reference laptop | Explicit performance test with report output redirected |
| NFR-2 Memory | Peak RSS is ≤512 MiB on the same fixture and machine | Process resource measurement |
| NFR-3 Portability | Runs on supported Python 3.11 environments and installs from a wheel using pip | Clean virtual-environment test |
| NFR-4 Correctness | Supported-format fixture suite and cross-renderer semantic checks pass | pytest unit, CLI, and golden tests |
| NFR-5 Coverage | Parsing, aggregation, and renderer modules each achieve ≥90% line coverage | Coverage gate |
| NFR-6 Determinism | Same ordered input/options/version produce the same semantic result | Repeated-run golden test |
| NFR-7 Privacy | No network calls, telemetry, database writes, or retained log copies | Static dependency review and isolated runtime test |
| NFR-8 Safety | Untrusted log fields are serialized/escaped and never interpreted as code or Rich markup | Adversarial-field fixture tests |

## Assumptions and Edge Cases

- Input may contain blank or malformed lines; blank lines are ignored while malformed nonblank lines are counted.
- The raw request-target token, including a query string, defines URL identity in MVP.
- Timestamp offsets are preserved; “hourly” means the hour written in each record, not conversion to one zone.
- Fewer than ten unique IPs or error URLs produces fewer ranked rows.
- No valid requests is an input-data failure, avoiding undefined percentage denominators.
- If a downstream consumer closes a pipe intentionally, the command exits 0 without a traceback.
- The default exact User-Agent ceiling is 1,000,000 distinct nonempty values and can be lowered with the CLI option.

## Prioritization Traceability

P0 maps to Must, P1 to Should, and P2 to Could in `STRATEGIC_PLAN.md`. Implementation follows data dependencies, then RICE order: establish the parser, deliver high-value aggregations, guard User-Agent cardinality, render outputs, integrate the exit contract, and consider gzip only after every P0 criterion passes.

## Release Acceptance

The MVP is accepted when every P0 story criterion, all non-functional gates, package installation, and the complete exit-code matrix pass against the exact release candidate. P1 and P2 omissions do not block the MVP.

## Kill Criteria

Stop or rescope if exact supported-format results cannot meet the 1 GB/30-second target on the reference laptop within one weekend, if peak memory cannot remain within 512 MiB under representative cardinality, or if stable pipeline schemas cannot be delivered without adding a service or persistent store. The response is an explicit scope or target decision, never silent approximation.

