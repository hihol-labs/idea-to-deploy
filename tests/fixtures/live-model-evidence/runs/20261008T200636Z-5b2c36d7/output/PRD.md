# Product Requirements Document: nginx-log-insights

## Product Summary

`nginx-log-insights` is a local Python 3.11 CLI that reads nginx combined access logs as a stream and produces four operational summaries: top client IPs, top error-producing URLs, hourly request distribution, and unique User-Agent share. It serves DevOps and SRE engineers who need fast, private, repeatable log triage without a server or persistent stack.

## Problem Statement

Operators can derive these answers with ad hoc shell pipelines or deploy a full analytics product, but the first option is fragile and hard to standardize while the second is excessive for a local incident snapshot. The product must make the common path one command, preserve pipeline compatibility, and expose data-quality and resource failures explicitly.

## Goals

- Produce the four defined metrics from a file or stdin in one pass.
- Process a representative 1 GB input in under 30 seconds on a documented laptop.
- Provide readable colored terminal output and stable JSON/CSV output.
- Install through pip on Python 3.11 with no external service.
- Maintain an explicit `0/1/2/3/4` exit-code contract.

## Non-Goals

- Authentication, users, permissions management, database, retention, or historical queries.
- HTTP API, server process, web dashboard, cloud resources, Docker, or Kubernetes.
- Log shipping, alerting, tail-state checkpointing, or multi-host aggregation.
- GeoIP enrichment, bot classification, request-latency analytics, or arbitrary nginx formats in P0.
- Approximate metrics presented as exact metrics.

## User Stories

- As a on-call SRE, I want to see the ten most frequent client IPs so that I can identify dominant or suspicious traffic sources during an incident. **Priority: P0**
- As a DevOps engineer, I want to see the ten request targets producing the most 4xx/5xx responses so that I can focus troubleshooting on the highest-volume failures. **Priority: P0**
- As a platform engineer, I want hourly request distribution expressed as percentages so that I can compare traffic shape independent of total log size. **Priority: P0**
- As a security-minded operator, I want the unique User-Agent share so that I can quickly gauge client diversity or automation-heavy traffic. **Priority: P0**
- As a pipeline author, I want JSON and CSV output with stable fields and clean stdout so that downstream automation can consume the report safely. **Priority: P0**
- As a runbook owner, I want documented exit codes for usage, runtime, parse, and cardinality failures so that automation can respond correctly. **Priority: P0**
- As an operator with rotated logs, I want direct gzip input so that I do not need an external decompression pipe. **Priority: P1**
- As an operator with a custom nginx `log_format`, I want a configurable format mapping so that I can use the tool without rewriting logs. **Priority: P1**
- As an on-call SRE, I want the tool to follow a growing file so that I can refresh the snapshot continuously. **Priority: P2**

## P0 Acceptance Criteria

### US-1: top client IPs

- [ ] A deterministic fixture returns at most ten IP/token entries ordered by descending request count, then ascending key for ties.
- [ ] IPv4 and IPv6 remote-address tokens are counted.
- [ ] Counts from a file and identical stdin input match exactly.

### US-2: top error URLs

- [ ] Only status codes 400 through 599 contribute.
- [ ] The request target, including query string, is used as the grouping key without decoding.
- [ ] Results contain at most ten entries with deterministic count/key ordering.

### US-3: hourly request distribution

- [ ] A successful report contains 24 ordered buckets for hours `00` through `23`.
- [ ] Every valid record contributes to the hour encoded by its nginx timestamp.
- [ ] Each percentage is calculated using `100 × hourly_request_count / total_valid_requests`, and successful report percentages total 100% within documented rounding tolerance.

### US-4: unique User-Agent share

- [ ] The unique count includes each distinct non-empty User-Agent once and excludes the nginx `-` placeholder.
- [ ] Share is `100 × unique_nonempty_user_agent_count / total_valid_requests` and is serialized to two decimal places.
- [ ] Adding duplicate User-Agent requests changes the denominator but not the unique count.

### US-5: three output modes

- [ ] Default output contains the four named metric sections and valid/malformed totals using Rich.
- [ ] `--json` emits one valid JSON document and no ANSI sequences.
- [ ] `--csv` emits the exact header `metric,rank,key,count,percentage` and no ANSI sequences.
- [ ] `--json` and `--csv` together are rejected as a usage error with exit code 2.
- [ ] Equivalent terminal, JSON, and CSV executions derive from the same renderer-neutral report values.

### US-6: failure and resource contract

- [ ] Success exits 0; I/O/runtime failure exits 1; usage failure exits 2; parse-quality failure exits 3; unique-cardinality exhaustion exits 4.
- [ ] `--strict` stops at the first malformed record with exit code 3.
- [ ] Non-strict mode counts malformed records and succeeds when at least one record is valid.
- [ ] Zero valid records exits 3.
- [ ] Exceeding `--max-unique-values` before retaining another distinct key exits 4 and does not emit a partial success report.

### US-7: installability and performance

- [ ] A clean Python 3.11 environment can install the built wheel and run `nginx-log-insights --help`.
- [ ] On the documented reference laptop, the representative 1 GB fixture completes in less than 30 seconds across a median of three runs.
- [ ] Peak RSS stays at or below 512 MiB for the representative benchmark, or the run exits 4 at the declared ceiling rather than being killed unpredictably.

## Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept exactly one `INPUT`: a UTF-8 text file path or `-` for stdin |
| FR-02 | Parse the documented nginx combined-log grammar line-by-line |
| FR-03 | Track total, valid, and malformed line counts |
| FR-04 | Compute exact top-10 client IP/token counts |
| FR-05 | Compute exact top-10 request-target counts for status 400–599 |
| FR-06 | Compute 24 hourly counts and percentages from valid requests |
| FR-07 | Compute unique non-empty User-Agent count and share |
| FR-08 | Render default Rich terminal, version-1 JSON, and normalized CSV |
| FR-09 | Keep stdout machine-clean and send diagnostics to stderr |
| FR-10 | Implement `--strict`, `--max-unique-values`, `--no-color`, `--help`, and `--version` |
| FR-11 | Enforce exit codes `0/1/2/3/4` exactly as documented |
| FR-12 | Install as a pip package with the `nginx-log-insights` console entry point |

### P1 — Should ship after P0

| ID | Requirement |
|---|---|
| FR-20 | Read gzip-compressed files directly while keeping stdin behavior unchanged |
| FR-21 | Support an explicit configurable format mapping with validation and versioned docs |

### P2 — Could ship

| ID | Requirement |
|---|---|
| FR-30 | Follow a growing regular file with documented snapshot/update semantics |

## Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | Python 3.11, Click, Rich, and standard-library dataclasses |
| NFR-02 | Representative 1 GB benchmark completes in under 30 seconds on documented hardware |
| NFR-03 | Raw log records are not retained after aggregation |
| NFR-04 | Unique aggregate state is capped by a default ceiling of 2,000,000 first-seen keys |
| NFR-05 | No network access, telemetry, persistent product state, or secrets |
| NFR-06 | Log-derived terminal strings are escaped as data, not interpreted as Rich markup/control sequences |
| NFR-07 | Metric behavior has deterministic tests and at least 90% branch coverage in core modules |
| NFR-08 | Machine-readable schemas are documented and protected by golden tests |

## CLI and Output Contract

The authoritative commands, options, inputs, outputs, formulas, and exit codes are in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. This PRD treats that section as part of the P0 acceptance contract. Behavior changes require updating both documents before implementation.

## Data Quality Rules

- A line is either valid or malformed; `total_lines = valid_lines + malformed_lines`.
- Malformed lines never contribute partially to any metric.
- A successful report requires at least one valid record.
- Valid/malformed counts are visible in every output mode.
- Percentages are based on valid requests, not total physical lines.

## Release and Kill Criteria

Release only when all P0 criteria pass, the wheel smoke test succeeds, JSON/CSV contracts are frozen, and the recorded performance run meets both time and memory targets. Do not hide a missed performance target by changing the benchmark fixture after implementation.

Pause release and revisit the architecture if the representative 1 GB median remains at or above 30 seconds after profiling, if representative unique state cannot fit under 512 MiB, or if combined-format support fails the initial users’ actual logs. Any move to approximate counts must be explicit in this PRD and visible in output.

## Dependencies and Traceability

- Strategy, priorities, budget, and risks: `STRATEGIC_PLAN.md`.
- Architecture, schemas, algorithms, and CLI contract: `PROJECT_ARCHITECTURE.md`.
- Ordered delivery and evidence: `IMPLEMENTATION_PLAN.md`.
- Session-sized execution prompts: `CLAUDE_CODE_GUIDE.md`.

## Open Product Decisions

There are no blocking product decisions for P0. P1 configurable-format syntax and P2 follow-mode refresh semantics are intentionally deferred and must not be invented during MVP implementation.
