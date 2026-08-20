# Product Requirements Document: Nginx Stream Analytics CLI

## 1. Product Summary

Nginx Stream Analytics CLI is a local, open-source Python 3.11 command-line tool for fast incident triage and pipeline automation. It streams a common or combined nginx access log from a file or stdin and reports:

1. Top 10 client IPs by valid request count.
2. Top 10 request URLs by combined 4xx/5xx response count.
3. A 24-hour request distribution as percentages.
4. The share of unique, non-missing User-Agent values among all valid requests.

Default output is colored terminal text. `--json` and `--csv` provide deterministic pipeline formats. The MVP is stateless and local, with no authentication, database, HTTP API, server, cloud component, or Kubernetes deployment.

## 2. Problem and Outcome

DevOps and SRE engineers often receive a raw access log before a full observability platform is available or worth configuring. Shell pipelines are quick but brittle, while full log platforms are costly to operate for a one-off local question. The desired outcome is a trustworthy operational summary from one command, without services or persistent state, fast enough that a 1 GB file remains interactive work.

## 3. Goals and Success Metrics

| Goal | Acceptance measure |
|---|---|
| Fast local triage | Representative 1 GB log completes in under 30 seconds on a documented reference laptop |
| Correct metrics | P0 fixtures produce exact counts, deterministic top-10 ordering, and exact percentage denominators |
| Pipeline safety | JSON and CSV schemas are stable, contain no ANSI escapes, and use the complete `0/1/2/3/4` exit contract |
| Resource safety | Cardinality guard produces controlled exit 4 before insertion beyond the configured limit |
| Simple adoption | Clean Python 3.11 environment installs a wheel with pip and completes a stdin quick start in under 30 seconds |

## 4. Non-goals

- Historical storage, cross-file sessions, incremental checkpoints, or a database.
- Authentication, authorization, multi-tenancy, an HTTP API, a daemon, or a web dashboard.
- Cloud hosting, containers as a runtime requirement, or Kubernetes.
- Arbitrary nginx `log_format` parsing in the MVP.
- Approximate metrics or silent sampling.
- Replacing GoAccess or a centralized observability stack for long-term analysis.

## User Stories

### US-01 — Stream a local log

As an on-call SRE, I want to analyze a file or stdin in one pass so that I can triage an incident without deploying infrastructure.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `nginx-log-report access.log` and `cat access.log | nginx-log-report` yield identical metric values.
- [ ] The input is consumed once; raw lines and parsed records are not accumulated.
- [ ] Common and combined nginx fixtures are accepted.
- [ ] At least one valid record produces exit 0 in default non-strict mode.

### US-02 — Identify dominant clients and failing URLs

As an on-call SRE, I want ranked client IP and failing-URL lists so that I can quickly see traffic concentration and error hotspots.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Top IPs include at most 10 entries counted across every valid request.
- [ ] Top error URLs include at most 10 entries counted only for statuses 400 through 599 inclusive.
- [ ] Both lists sort by count descending and then key ascending for ties.
- [ ] Query strings remain part of the request target, so `/x?a=1` and `/x?a=2` are distinct.

### US-03 — Understand traffic by hour

As a DevOps engineer, I want a complete hourly percentage distribution so that I can spot traffic concentration without calculating it manually.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] The report contains ordered hours 00 through 23, including zero-count hours.
- [ ] Each hourly percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] The hour is taken from the timezone-aware timestamp as encoded in each log record.
- [ ] JSON and CSV serialize percentages to six decimal places; text may display two.

### US-04 — Measure User-Agent diversity

As a platform engineer, I want the share of unique User-Agents so that I can estimate client diversity at a glance.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Distinct non-missing combined-log User-Agent strings are counted exactly.
- [ ] The share is `100 × unique_non_missing_user_agent_count / total_valid_requests`.
- [ ] Common-format records and User-Agent `"-"` contribute to the valid-request denominator but not the unique count.
- [ ] Exceeding the configured distinct-key guard exits 4 without emitting a partial report.

### US-05 — Use output safely in automation

As a DevOps engineer, I want stable JSON, CSV, and exit codes so that a shell or CI pipeline can consume the report reliably.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `--json` emits one schema-versioned JSON object and a trailing newline.
- [ ] `--csv` emits the documented normalized header and deterministic sections.
- [ ] `--json` and `--csv` are mutually exclusive and their conflict exits 2.
- [ ] JSON/CSV contain no ANSI escape sequences and all report data is on stdout.
- [ ] Exit codes are exactly `0` success, `1` operational/internal failure, `2` usage error, `3` input/parse failure, and `4` unique-cardinality exhaustion.

### US-06 — See useful terminal output

As an on-call SRE, I want readable colored tables by default so that the important signals are easy to scan during an incident.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Default mode shows summary, Top 10 IPs, Top 10 4xx/5xx URLs, and all 24 hours.
- [ ] Meaning is preserved without color; `--no-color` and `NO_COLOR` disable ANSI color.
- [ ] Untrusted URL and User-Agent characters cannot inject Rich markup or terminal controls.

### US-07 — Analyze compressed logs directly

As a DevOps engineer, I want direct `.gz` input so that archived logs need no shell decompression step.

**Priority:** P1 (Should)

**Acceptance criteria:**

- [ ] If implemented after MVP, `.gz` files stream through the same parser and produce the same report as decompressed bytes.
- [ ] Until implemented, documentation provides the supported `gzip -dc ... | nginx-log-report` pipeline and does not imply direct support.

### US-08 — Adjust report breadth

As a platform engineer, I want a configurable top-N so that I can inspect more than ten entries when necessary.

**Priority:** P2 (Could)

**Acceptance criteria:**

- [ ] If implemented, the default remains 10 and structured schemas retain deterministic ranking.

## 6. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-001 | P0 | Accept one optional path positional input; omitted or `-` means stdin |
| FR-002 | P0 | Parse documented nginx common and combined lines as UTF-8 with replacement semantics |
| FR-003 | P0 | Count valid requests per exact client-IP string and emit deterministic top 10 |
| FR-004 | P0 | Count exact request targets only for HTTP status 400–599 and emit deterministic top 10 |
| FR-005 | P0 | Count valid records in each encoded local hour 0–23 |
| FR-006 | P0 | Calculate each hour as `100 × hourly_request_count / total_valid_requests` |
| FR-007 | P0 | Count exact, non-missing User-Agent strings and calculate their share over total valid requests |
| FR-008 | P0 | Enforce `--max-unique` before new-key insertion in IP, error-URL, and User-Agent containers |
| FR-009 | P0 | Default mode skips/counts malformed non-empty lines and succeeds if any valid record exists |
| FR-010 | P0 | `--strict` stops on first malformed non-empty line and exits 3; zero-valid input exits 3 |
| FR-011 | P0 | Diagnostics use stderr, include sanitized line number/reason, and never echo a full raw record |
| FR-012 | P0 | Default renderer emits colored Rich text while preserving meaning without color |
| FR-013 | P0 | `--json` emits schema version 1 exactly as specified in `PROJECT_ARCHITECTURE.md` |
| FR-014 | P0 | `--csv` emits the normalized schema and ordering specified in `PROJECT_ARCHITECTURE.md` |
| FR-015 | P0 | Map outcomes to the immutable exit-code contract `0/1/2/3/4` |
| FR-016 | P1 | Support direct gzip streaming without changing report semantics |
| FR-017 | P2 | Allow top-N configuration while retaining a default of 10 |

## 7. Non-functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-001 | Process a deterministic 1 GB combined log in under 30 seconds on the documented reference laptop | Timed default-text benchmark including final rendering |
| NFR-002 | Never load the full input or retain raw/parsed records after aggregation | Code review plus large-input memory measurement |
| NFR-003 | Keep peak RSS under 256 MB on the standard benchmark with normal cardinality | Recorded peak-memory benchmark |
| NFR-004 | Run on CPython 3.11 and install from wheel/sdist using pip | Clean virtual-environment smoke test |
| NFR-005 | Produce deterministic ranking and structured output independent of hash randomization | Golden tests across multiple `PYTHONHASHSEED` values |
| NFR-006 | Maintain at least 90% branch coverage for parser, aggregator, reporters, and CLI | pytest coverage gate |
| NFR-007 | Perform no network access, telemetry, application persistence, or external command execution | Dependency/code review and offline integration test |
| NFR-008 | Escape terminal output and serialize JSON/CSV with standard libraries | Adversarial control/markup fixture tests |

## 8. CLI and Output Acceptance Contract

The exact command, options, schemas, stream separation, and detailed cases are defined in `PROJECT_ARCHITECTURE.md` under `## CLI Interface` and Section 9. The externally observable outcome mapping is:

| Code | Contract |
|---:|---|
| `0` | A complete report was produced successfully |
| `1` | Operational or unexpected internal failure |
| `2` | Invalid CLI invocation or option combination |
| `3` | Strict parse failure, empty input, or zero valid records |
| `4` | Unique-cardinality exhaustion in a guarded distinct-key container |

Click's own usage-error behavior must be integration-tested to preserve code 2. Code 4 is distinct because pipelines may choose to retry with a reviewed higher limit or route the file to a different tool; silently approximating or remapping it would conceal lost exactness.

## 9. Malformed and Boundary Behavior

- Empty physical lines are ignored and are neither valid nor malformed.
- A malformed non-empty line increments `malformed_lines` only in default mode; strict mode exits immediately.
- If no record is valid, no report is emitted and the process exits 3.
- Status 399 is excluded; 400 and 599 are included; 600 is excluded.
- Top lists may contain fewer than 10 entries and may be empty.
- A User-Agent string is compared exactly after syntactic unescaping; no case folding or normalization occurs.
- Values with control characters are escaped for terminal safety but remain correctly encoded data in JSON/CSV.
- Broken downstream pipes do not display a traceback.

## 10. Dependencies and Assumptions

- The input uses nginx common or combined format, not an arbitrary custom `log_format`.
- The reference performance log has realistic line lengths and cardinality; adversarial cardinality is tested separately.
- File permission and confidentiality are controlled by the invoking OS user.
- Python 3.11, Click, and Rich are available through pip without monetary cost.
- Exact unique tracking is required up to the configured guard; approximation is not acceptable in MVP.

## 11. Release Criteria

Release requires every P0 acceptance criterion, all NFR verification, exact `0/1/2/3/4` subprocess tests, the reproducible 1 GB result, an adversarial exit-4 result, cross-format metric equivalence, a clean wheel/sdist install, and current help/README documentation. P1 and P2 items do not block the MVP.

## 12. Kill and Rescope Criteria

Pause release and revise the durable specs if any of these occurs:

- The Python 3.11 single-process implementation misses 1 GB / 30 s after profiling and one focused optimization pass.
- Exact guarded cardinality cannot stay below the normal-case 256 MB target.
- Representative target logs predominantly require custom nginx formats.
- JSON, CSV, and text cannot share one canonical report without semantic divergence.
- Achieving the goal would require a database, HTTP service, authentication, cloud deployment, or non-zero cash budget.

These are rescope triggers, not permission to weaken metrics or hide failures.

## 13. Traceability

- Product strategy, competitors, priorities, budget, KPIs: `STRATEGIC_PLAN.md`.
- Architecture, data contracts, commands, and schemas: `PROJECT_ARCHITECTURE.md`.
- Ordered implementation units and machine checks: `IMPLEMENTATION_PLAN.md`.
- Session-by-session execution prompts: `CLAUDE_CODE_GUIDE.md`.
