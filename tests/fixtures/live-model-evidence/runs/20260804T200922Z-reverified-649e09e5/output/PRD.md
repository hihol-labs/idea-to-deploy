# Product Requirements Document: Nginx Stream Analytics CLI

## 1. Purpose

Provide DevOps and SRE engineers a fast, private, local way to turn nginx combined access logs into four actionable reports. The MVP is a Python 3.11 CLI installed by pip, processes data as a stream, costs $0 to operate, and is deliverable in one weekend.

## 2. Goals and Non-Goals

### Goals

- Process a representative 1 GB nginx access log in under 30 seconds on a documented laptop.
- Report exact top client IPs, error URLs, hourly percentages, and unique User-Agent share.
- Work naturally for humans in terminals and for programs through JSON or CSV.
- Avoid data upload, persistent state, and service operations.
- Fail predictably with stable exit codes and no misleading partial report.

### Non-goals

- Authentication, authorization, database storage, HTTP API, server mode, cloud deployment, or Kubernetes.
- Log retention, search, dashboards, alerting, correlation across runs, or continuous tail-follow mode in v0.1.
- Arbitrary nginx `log_format` parsing, compressed input, approximate metrics, or distributed processing in P0.
- Replacement for GoAccess, Elastic/Kibana, AWStats, or a general shell-processing toolkit.

## 3. Personas and Primary Scenarios

- **On-call SRE:** downloads or accesses an incident log, runs one command, identifies noisy IPs and failing routes.
- **Platform engineer:** pipes a log through stdin and consumes versioned JSON in automation.
- **Application operator:** exports CSV for a spreadsheet while retaining exact counts and metric definitions.

## User Stories

### US-01 — Analyze a file locally

As an on-call SRE, I want to analyze an nginx access-log file with one command so that I can triage traffic without deploying infrastructure.

**Priority:** P0

**Acceptance criteria:**

- [ ] `nginx-stream-report access.log` reads the file incrementally and exits 0 when at least one valid request exists.
- [ ] The default stdout contains labeled top-IP, error-URL, hourly-distribution, and User-Agent sections.
- [ ] Raw lines are not retained after their aggregation update and no network connection is opened.
- [ ] A missing or unreadable file emits a useful stderr diagnostic, emits no report, and exits 3.

### US-02 — Find top clients and broken routes

As an SRE investigating an incident, I want deterministic top-10 client IP and 4xx/5xx URL counts so that ties and reruns produce the same answer.

**Priority:** P0

**Acceptance criteria:**

- [ ] Every valid request contributes once to its client IP count.
- [ ] Only statuses 400–599 contribute to error-URL counts.
- [ ] Both lists default to at most 10 entries, sorted by count descending and key ascending on ties.
- [ ] `--top N` accepts 1–100 and changes both rankings; invalid values exit 2.

### US-03 — Understand traffic by hour

As a platform engineer, I want each hour's request percentage so that I can see traffic concentration across the log.

**Priority:** P0

**Acceptance criteria:**

- [ ] Output contains all 24 hour buckets, `00` through `23`, in order.
- [ ] Each percentage is computed with the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] Malformed lines are excluded from hourly counts and `total_valid_requests`.
- [ ] JSON/CSV percentages are numbers; text presents two decimal places.

### US-04 — Measure User-Agent diversity

As an application operator, I want the share of unique User-Agents so that I can estimate client diversity in the request population.

**Priority:** P0

**Acceptance criteria:**

- [ ] The share is `100 × distinct_nonempty_user_agent_count / total_valid_requests`.
- [ ] Identical logged User-Agent strings count once; `"-"` and absent values are not distinct agents.
- [ ] The exact distinct count and percentage are both present in JSON and the corresponding CSV row.
- [ ] If the aggregate distinct-key ceiling would be exceeded, no partial report is emitted and the command exits 4.

### US-05 — Use reports in automation

As a platform engineer, I want stable JSON and CSV output so that pipelines do not scrape colored terminal text.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits one valid JSON document with `schema_version: 1` and the architecture-defined fields.
- [ ] `--csv` emits the normalized `section,key,count,percentage` header and RFC 4180-compatible rows.
- [ ] JSON and CSV contain no ANSI control sequences and no diagnostic text.
- [ ] `--json --csv` is rejected with exit 2.

### US-06 — Pipe input safely

As a shell user, I want stdin and multiple ordered files so that I can compose the analyzer with existing tools.

**Priority:** P0

**Acceptance criteria:**

- [ ] With no path, the command reads stdin; `-` explicitly denotes stdin.
- [ ] Multiple sources form one report in argument order and stdin may appear at most once.
- [ ] Normal output goes to stdout and diagnostics go to stderr.
- [ ] A downstream closed pipe ends without a traceback.

### US-07 — See trustworthy data quality

As an operator, I want malformed input accounted for so that a superficially successful report does not hide parser failure.

**Priority:** P0

**Acceptance criteria:**

- [ ] Every physical input line increments exactly one of valid or malformed counts.
- [ ] A mixed valid/malformed stream succeeds, includes all three summary counts, and reports skipped lines.
- [ ] An input with zero valid requests emits no report and exits 3.
- [ ] The invariant `total_lines = valid_requests + malformed_lines` holds.

### US-08 — Read compressed logs directly

As an on-call engineer, I want gzip input so that I can avoid a decompression step.

**Priority:** P1

**Acceptance criteria:**

- [ ] A `.gz` file produces the same report as its decompressed bytes.
- [ ] Corrupt gzip content exits 3 without a partial report.

### US-09 — Support custom log formats

As a platform engineer, I want to describe a custom nginx log format so that the tool works beyond the combined format.

**Priority:** P2

**Acceptance criteria:**

- [ ] A future format grammar names required IP, timestamp, request target, status, and User-Agent fields.
- [ ] Invalid or incomplete grammars fail before reading input.

## 5. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept one or more paths or stdin and process physical lines in one pass. |
| FR-02 | Parse the documented nginx combined format into timezone-aware records. |
| FR-03 | Produce deterministic top-N IP counts and 4xx/5xx URL counts. |
| FR-04 | Produce 24 hourly request counts and percentage values. |
| FR-05 | Produce exact distinct nonempty User-Agent count and share. |
| FR-06 | Render Rich text by default and stable JSON/CSV on explicit flags. |
| FR-07 | Track total, valid, and malformed lines and never include malformed data in metrics. |
| FR-08 | Enforce a positive cardinality ceiling across distinct tracked keys. |
| FR-09 | Implement the complete `0/1/2/3/4` exit contract from `PROJECT_ARCHITECTURE.md`. |
| FR-10 | Provide `--help`, `--version`, `--top`, `--max-cardinality`, and color policy options. |

### P1 — Should ship after MVP

- FR-11: Transparently stream gzip-compressed file paths with equivalent metrics and failure behavior.

### P2 — Could ship later

- FR-12: Parse explicitly configured nginx log formats.
- FR-13: Offer approximate bounded-memory cardinality only through a visibly distinct mode/schema.

## 6. Non-Functional Requirements

| Area | Requirement |
|---|---|
| Performance | Installed CLI processes the deterministic 1 GB reference fixture in <30 seconds on the documented Python 3.11 laptop. |
| Memory | Never retain raw lines or parsed records; peak RSS is measured and targeted below 512 MiB on the representative fixture. |
| Correctness | Ranking ties, metric denominators, malformed handling, and output schemas are deterministic and tested. |
| Compatibility | CPython 3.11 on supported Linux/macOS; Windows behavior may be documented after MVP verification. |
| Privacy | No network traffic, telemetry, implicit file discovery, or persistent report data. |
| Security | Treat every log field as untrusted; escape Rich markup and use standard JSON/CSV encoders. |
| Packaging | Wheel and sdist build; wheel installs in a clean environment and exposes `nginx-stream-report`. |
| Observability | Human-readable failures include source context without dumping entire sensitive log lines. |

## 7. Input and Output Contract

`PROJECT_ARCHITECTURE.md` section `CLI Interface` is normative for commands, options, format schemas, metric definitions, stdout/stderr separation, and exits. Changes to observable behavior require updating that specification and these acceptance criteria before code.

The supported request field follows nginx combined-log quoting. The request target is preserved as logged, including query string. Timestamps use their recorded offset and are bucketed by the recorded hour; the tool does not normalize to machine local time.

## 8. Error Policy

| Code | Product interpretation |
|---:|---|
| `0` | Complete successful report or successful help/version action |
| `1` | Unexpected internal processing/rendering failure |
| `2` | Invalid CLI usage/options |
| `3` | Input/data failure, including no valid records |
| `4` | Unique-cardinality exhaustion; report withheld |

Malformed lines are recoverable only when at least one valid line remains. The CLI must never emit a report that looks complete after an exit-4 condition.

## 9. Release Acceptance

- All P0 story criteria pass on Python 3.11.
- Unit/integration suite and static checks pass; critical domain modules meet the coverage threshold in `STRATEGIC_PLAN.md`.
- JSON schema v1 and normalized CSV golden outputs are reviewed and pinned.
- Benchmark evidence contains machine, fixture, command, elapsed time, and peak RSS, and meets <30 seconds for 1 GB.
- Clean wheel installation, `--help`, stdin, and all exit codes are exercised.
- No P1/P2 behavior is implied by help or documentation unless implemented and verified.

## 10. Kill Criteria

Pause release and re-scope if the exact Python 3.11 implementation cannot meet the performance target after measured profiling; if supported-format accuracy remains below 99.9% on the representative corpus; or if cardinality safety can only be achieved by silently approximate output or persistent storage. Any change to exactness, runtime stack, or local-only boundary needs a new product decision.

## 11. Dependencies and Traceability

The business rationale and MoSCoW/RICE order live in `STRATEGIC_PLAN.md`. Architecture and public schemas live in `PROJECT_ARCHITECTURE.md`. Delivery evidence is defined in `IMPLEMENTATION_PLAN.md`.
