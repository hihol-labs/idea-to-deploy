# Product Requirements Document: Nginx Insight

## 1. Product Summary

Nginx Insight is a local Python 3.11 CLI for DevOps/SRE engineers who need a fast, trustworthy summary of nginx combined access logs without deploying an observability stack. It streams files or stdin and reports top client IPs, top error-producing URLs, hourly request percentages, and exact unique User-Agent share. Rich terminal text is the default; JSON and CSV are stable pipeline formats.

## 2. Problem and Goals

During incident response, an engineer often has a large access log but no suitable retained index. Existing options are either brittle one-off shell pipelines or systems that require services and persistence. The product must make the common first-pass analysis repeatable.

Goals:

- Produce all four required metrics in one sequential pass.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Work locally with no authentication, database, HTTP API, server, cloud, or Kubernetes.
- Be installable with pip on Python 3.11.
- Provide deterministic human, JSON, and CSV reporting with reliable automation exit codes.

Non-goals include historical storage, dashboards, log shipping, arbitrary search, real-time network listening, custom nginx format configuration, geolocation, bot classification, and security blocking/remediation.

## 3. Personas and Primary Scenarios

| Persona | Scenario | Success signal |
|---|---|---|
| On-call SRE | Pipe a live/copied access stream into a first-pass incident report | Sees traffic sources and failing endpoints without preprocessing |
| DevOps engineer | Analyze several rotated plain-text logs as one dataset | Receives deterministic aggregate metrics and clear malformed-line counts |
| Platform engineer | Feed results into another tool | Parses versioned JSON or fixed-column CSV and branches on exit status |

## User Stories

### US-01 — Stream and parse operational logs

As an on-call SRE, I want to read an nginx combined access log from a file or stdin so that I can analyze data where it already exists.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] With no input arguments, the command reads stdin; with file arguments, it processes them sequentially in argument order.
- [ ] Every valid combined-format line increments `total_valid_requests` exactly once and raw lines are not retained.
- [ ] Default mode skips malformed lines, reports their count, and exits 0 after emitting the report.
- [ ] `--strict` stops at the first malformed/undecodable line, emits source and line number without the full line, and exits 1.
- [ ] Missing/unreadable input exits 3, while invalid command syntax exits 2.

### US-02 — Find top client IPs

As an SRE investigating load or abuse, I want the ten most active client IPs so that I can identify dominant traffic sources.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Counts include every valid request and group by exact logged client-IP string.
- [ ] At most ten rows are returned, ordered by count descending and IP ascending for ties.
- [ ] An input with fewer than ten IPs returns only existing IPs; empty valid input returns no synthetic entry.

### US-03 — Find URLs producing errors

As an on-call engineer, I want the ten URLs with the most 4xx/5xx responses so that I can focus diagnosis on failing request targets.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Only status codes 400 through 599 contribute.
- [ ] Counts group by the exact request-target field and include at most ten URLs.
- [ ] Rows sort by count descending and URL ascending for ties.
- [ ] Successful and redirect responses do not contribute.

### US-04 — Understand hourly traffic shape

As a DevOps engineer, I want requests distributed over hours so that I can spot time-local traffic concentration.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Output contains all 24 buckets `00` through `23`, derived from the hour in each valid log timestamp as written.
- [ ] Each bucket percentage uses `100 × hourly_request_count / total_valid_requests`.
- [ ] With zero valid requests, every hourly count and percentage is zero.
- [ ] Display percentages use two decimal places and tolerate a rounded total of 99.99 or 100.01.

### US-05 — Measure User-Agent diversity

As a platform engineer, I want the exact share of unique User-Agents so that I can estimate client diversity in the analyzed requests.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] The numerator is the count of exact distinct non-empty User-Agent strings among valid requests.
- [ ] Share percentage uses `100 × unique_user_agent_count / total_valid_requests` and is zero for no valid requests.
- [ ] The report exposes both the distinct count and percentage.
- [ ] If a new tracked key would exceed `--max-unique`, no approximate result is emitted and the command exits 4.

### US-06 — Use readable terminal output

As an on-call SRE, I want a colored, structured terminal report so that I can scan results quickly.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Default output contains a summary and clearly labeled sections for all four metrics.
- [ ] Rich markup from log values is escaped and cannot alter terminal structure.
- [ ] `--no-color` removes ANSI styling; machine formats never contain ANSI styling.

### US-07 — Integrate with pipelines

As a DevOps engineer, I want JSON and CSV output so that scripts can consume reports without scraping terminal text.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `--json` emits one newline-terminated object with `schema_version: 1` and the schema in `PROJECT_ARCHITECTURE.md`.
- [ ] `--csv` emits exactly the documented header and deterministic long-form rows.
- [ ] `--json` and `--csv` together are rejected with exit 2.
- [ ] Diagnostics go only to stderr and a failure does not leave a partial JSON/CSV report on stdout.

### US-08 — Aggregate rotated logs

As a DevOps engineer, I want multiple files treated as one logical stream so that I can analyze a rotation window in one invocation.

**Priority:** P1 (Should)

**Acceptance criteria:**

- [ ] Totals and rankings aggregate across every supplied file rather than producing per-file reports.
- [ ] Only one file is open at a time.
- [ ] `-` may be supplied at most once; duplicate stdin use exits 2.

### US-09 — Analyze a custom nginx format

As a user with a custom `log_format`, I want to describe its fields so that the tool can analyze non-combined logs.

**Priority:** P2 (Could; deferred)

This is not accepted into the weekend MVP. It requires a separate grammar and security/compatibility design.

## 5. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Provide the `nginx-insight [OPTIONS] [INPUTS]...` console command after pip installation |
| FR-02 | Support conventional nginx combined access-log lines from stdin and plain-text files |
| FR-03 | Maintain `total_lines`, valid request count, and malformed-line count |
| FR-04 | Produce the top 10 IPs and top 10 4xx/5xx URLs with deterministic ties |
| FR-05 | Produce 24 hourly counts and percentages using the approved literal formula |
| FR-06 | Produce exact unique User-Agent count and share below a cardinality ceiling |
| FR-07 | Render Rich terminal text by default, JSON with `--json`, or CSV with `--csv` |
| FR-08 | Enforce exact-cardinality exhaustion with exit 4 and no approximate fallback |
| FR-09 | Honor the complete `0/1/2/3/4` exit contract in `PROJECT_ARCHITECTURE.md` |
| FR-10 | Never emit progress, warnings, or ANSI escapes into JSON/CSV stdout |

### P1 — Should ship

| ID | Requirement |
|---|---|
| FR-11 | Aggregate multiple file arguments in order and support one explicit stdin marker |
| FR-12 | Provide strict parsing that fails on the first invalid line |
| FR-13 | Allow a positive `--max-unique` override and forced terminal color behavior |

### P2 — Could follow

| ID | Requirement |
|---|---|
| FR-14 | Accept a safe declarative custom nginx log-format grammar |
| FR-15 | Allow configurable top-N while preserving a default of 10 |

## 6. Non-Functional Requirements

| Area | Requirement | Evidence |
|---|---|---|
| Performance | Representative 1 GB input completes in <30 s on a documented reference laptop | Median of three measured runs after warm-up, with command/dataset recorded |
| Memory | Raw lines/records are not accumulated; unique state is capped | Memory-focused test plus peak RSS benchmark |
| Compatibility | CPython 3.11; Linux and macOS are primary | CI/test matrix where available |
| Determinism | Same valid records produce byte-identical JSON/CSV | Golden tests across repeated invocations |
| Correctness | P0 parser and aggregation logic has >=90% line coverage and boundary fixtures | pytest coverage report and oracle fixtures |
| Privacy | No network, telemetry, full malformed-line echo, or persistence | Static review and subprocess tests |
| Safety | Untrusted terminal/CSV values cannot inject formatting/formulas | Adversarial output fixtures |

## 7. Interface and Exit Contract

The authoritative command/options/input/output specification is under `## CLI Interface` in `PROJECT_ARCHITECTURE.md`. The public exit mapping is complete and stable:

- `0`: success, including non-strict skipped malformed lines.
- `1`: processing/data error.
- `2`: CLI usage error.
- `3`: input/output error.
- `4`: unique-cardinality exhaustion.

All implementation and verification work must preserve this `0/1/2/3/4` mapping.

## 8. Dependencies and Assumptions

- Python 3.11, Click, Rich, and dataclasses are approved.
- Inputs are plain-text nginx combined logs; gzip discovery/decompression is not part of the MVP.
- “Hourly” means the hour component encoded in each record's timestamp, including its recorded offset; logs are not normalized into another timezone.
- “Unique User-Agent share” is exact distinct non-empty User-Agents divided by all valid requests, as a percentage.
- The 1 GB target is conditional on representative cardinality remaining under configured limits.

## 9. Out of Scope

- Authentication or user accounts.
- Database, cache, search index, or saved history.
- HTTP API, network listener, daemon, web UI, or server.
- Cloud, Docker, Kubernetes, or managed deployment.
- Live tail/reopen semantics, remote files, compressed inputs, and recursive directory discovery.
- Request-body processing, geolocation, threat blocking, alerting, or remediation.
- Silent approximate-cardinality algorithms.

## 10. Release Acceptance and Kill Criteria

Release requires all P0 acceptance criteria, exact golden outputs, package installation proof, and recorded performance evidence. It must not be labeled complete if any required document/test is missing or if the benchmark was not actually run.

Pause release and revise the design when:

- The reference benchmark remains at or above 30 seconds after profile-guided optimization.
- Peak memory is unbounded because raw records are retained or cardinality limits are bypassed.
- Machine output is nondeterministic, contains ANSI/progress text, or can be partially emitted on failure.
- Any error path remaps or omits code 4.
- Meeting the goal would require introducing a database, HTTP service, cloud deployment, or authentication; that requires a new product decision.

## 11. Traceability

`STRATEGIC_PLAN.md` owns market/scope priority, `PROJECT_ARCHITECTURE.md` owns technical and CLI contracts, and `IMPLEMENTATION_PLAN.md` maps these requirements to files and executable checks.
