# Product Requirements Document: nginx-insight

## Product Summary

`nginx-insight` is a local Python 3.11 CLI that gives DevOps/SRE engineers four exact summaries from nginx combined access logs in one streaming pass. It favors zero setup, predictable automation, and local data handling over persistent dashboards.

## Goals

- Produce top 10 client IPs, top 10 URLs with 4xx/5xx responses, hourly request percentages, and unique User-Agent share from supported logs.
- Accept stdin and one or more files without buffering raw logs.
- Provide a readable default terminal report and stable JSON/CSV pipeline formats.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Install with pip on Python 3.11 and require no service or configuration.

## Non-Goals

- Authentication, users, authorization, or multi-tenancy.
- Database, retained history, cache, search index, or HTTP API.
- Server, cloud, Kubernetes, Docker, or hosted dashboard.
- Arbitrary nginx `log_format`, compressed input, GeoIP, bot classification, alerting, or log mutation.
- Follow/tail mode and configurable top-N in the MVP.

## User Stories

### US-1: Analyze a local incident log

As an on-call SRE, I want to run one command on an nginx access log so that I can see the most active clients and failing URLs quickly.

**Priority:** P0

**Acceptance criteria:**

- [ ] Given more than 10 distinct IPs, output contains exactly the highest 10 ordered by count descending and value ascending for ties.
- [ ] Given responses across status families, the URL ranking includes only statuses 400–599.
- [ ] A readable terminal report is written to stdout and diagnostics, if any, to stderr.

### US-2: Pipe logs without temporary files

As a DevOps engineer, I want to pipe nginx logs through stdin so that I can compose the tool with local shell workflows.

**Priority:** P0

**Acceptance criteria:**

- [ ] With no file argument, the CLI consumes stdin line-by-line.
- [ ] Raw records are not retained after their aggregate update.
- [ ] Empty stdin produces a valid empty report and exit 0.

### US-3: Consume a stable JSON report

As a platform engineer, I want JSON output so that automation can parse metrics without terminal formatting.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits one valid JSON object and a trailing newline on stdout.
- [ ] The object contains the schema version, input-quality totals, both rankings, 24 hourly buckets, and User-Agent count/share.
- [ ] stdout contains no ANSI sequences, warnings, or progress output.

### US-4: Export normalized CSV

As an SRE, I want CSV output so that I can load a report into spreadsheet and command-line tools.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--csv` emits the documented header and normalized metric rows using a standard CSV serializer.
- [ ] Values containing commas, quotes, or newlines are escaped correctly.
- [ ] Counts and percentages reconcile with the JSON representation for the same input.

### US-5: Understand traffic by hour

As an incident responder, I want every hour's share of valid requests so that I can identify traffic concentration without calculating it manually.

**Priority:** P0

**Acceptance criteria:**

- [ ] Output always includes hours 00 through 23 in ascending order.
- [ ] Each percentage uses `100 × hourly_request_count / total_valid_requests`.
- [ ] With valid requests, unrounded percentages total 100%; with zero valid requests, all are 0.0.

### US-6: Measure User-Agent diversity safely

As a platform engineer, I want the exact share of unique User-Agents with a capacity guard so that I never consume an approximate value unknowingly.

**Priority:** P0

**Acceptance criteria:**

- [ ] The report includes distinct User-Agent count and `100 × unique_user_agent_count / total_valid_requests`.
- [ ] `--max-unique-user-agents` accepts a positive integer and defaults to 1,000,000.
- [ ] Adding a new value beyond the configured exact-cardinality limit emits no partial structured report and exits 4.

### US-7: Diagnose imperfect logs predictably

As an operator, I want malformed records and input failures treated consistently so that automation can distinguish data quality from filesystem errors.

**Priority:** P0

**Acceptance criteria:**

- [ ] Default mode skips malformed lines, reports their count, and calculates metrics only from valid records.
- [ ] `--strict` stops at the first malformed record with exit 1.
- [ ] Missing, unreadable, directory, interrupted, or invalid-UTF-8 input exits 3.
- [ ] Invalid option usage exits 2 and successful reports exit 0.

### US-8: Adjust ranking depth later

As an experienced operator, I want configurable top-N rankings so that I can inspect broader distributions when needed.

**Priority:** P1

This is a post-MVP requirement and does not alter the fixed top-10 acceptance criteria.

### US-9: Follow a live log later

As an on-call SRE, I want to follow a growing file so that I can observe incident metrics continuously.

**Priority:** P1

This is deferred until windowing, refresh, signal, and structured-output completion semantics are separately specified.

### US-10: Parse custom formats later

As a DevOps engineer, I want to supply an nginx format template so that non-standard access logs can be analyzed.

**Priority:** P2

This is optional and requires a separate grammar and safety design.

## Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Consume stdin or one or more explicit file paths sequentially as UTF-8 lines. |
| FR-2 | P0 | Parse the documented nginx combined format and classify malformed records without crashing. |
| FR-3 | P0 | Count exact client IP occurrences and emit a deterministic top 10. |
| FR-4 | P0 | Count exact request targets for status 400–599 and emit a deterministic top 10. |
| FR-5 | P0 | Emit 24 local-log-hour buckets whose percentages use `100 × hourly_request_count / total_valid_requests`. |
| FR-6 | P0 | Emit exact distinct User-Agent count and share, bounded by the configured cardinality limit. |
| FR-7 | P0 | Render four Rich terminal sections by default without interpreting log values as markup. |
| FR-8 | P0 | Emit one schema-versioned JSON object when `--json` is selected. |
| FR-9 | P0 | Emit normalized CSV rows when `--csv` is selected. |
| FR-10 | P0 | Enforce mutually exclusive formats, strict mode, color policy, stdout/stderr separation, and exits `0/1/2/3/4`. |
| FR-11 | P1 | Permit a configured top-N shared by the IP and error-URL rankings. |
| FR-12 | P1 | Follow a regular file with explicitly specified refresh and termination semantics. |
| FR-13 | P2 | Parse a safe, documented subset of custom nginx format definitions. |

## Output Semantics

- A valid request is a line that fully satisfies the supported combined-format parser and field invariants.
- IP ranking counts all valid requests by logged client address.
- Error-URL ranking counts the logged request target only for 4xx/5xx statuses; query strings remain part of the target.
- Hour is the 00–23 hour present in nginx's `$time_local`; records are not converted to another timezone.
- Hourly request distribution is a percentage, never an unscaled fraction: `100 × hourly_request_count / total_valid_requests`.
- Unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`; both numerator and denominator are emitted.
- Presentation rounds percentages to two decimal places, while comparisons and reconciliation derive from integer counts.

## CLI and Exit Requirements

The normative command, option, input, output, and exit-code contract is under `PROJECT_ARCHITECTURE.md` → `## CLI Interface`. The complete status mapping is: `0` success; `1` processing/data failure; `2` usage failure; `3` input I/O or decoding failure; `4` unique-cardinality exhaustion. Code 4 cannot be reassigned or collapsed into code 1.

## Non-Functional Requirements

| ID | Requirement | Acceptance method |
|---|---|---|
| NFR-1 | Python 3.11 and pip-installable wheel | Install and smoke-test in a clean Python 3.11 environment |
| NFR-2 | Representative 1 GB input completes in <30 s on a documented laptop | Reproducible benchmark records command, hardware, cache state, time, and peak RSS |
| NFR-3 | Raw input is streamed and not retained | Code review plus bounded-input iterator test |
| NFR-4 | No network, persistence, server, auth, cloud, or Kubernetes | Dependency/configuration inspection and network-isolated test run |
| NFR-5 | Pipeline stdout is deterministic and decoration-free | Golden structural tests and repeated-run comparison |
| NFR-6 | Parser, aggregation, and renderer line coverage is at least 90% | pytest coverage gate |
| NFR-7 | Untrusted values are not executed or interpreted as markup | Security fixtures for control sequences, Rich markup, JSON, and CSV |

## Release Acceptance

- [ ] All P0 user-story criteria pass against the installed wheel.
- [ ] Cross-format reports reconcile for the same fixture.
- [ ] The complete exit-code suite proves `0/1/2/3/4`, including cardinality exhaustion at 4.
- [ ] The documented performance benchmark passes on the reference laptop.
- [ ] Source distribution and wheel pass metadata checks and require no runtime service.
- [ ] `README.md`, `PROJECT_ARCHITECTURE.md`, and CLI help agree.

## Kill Criteria

Stop or revise the MVP if representative 1 GB performance remains at or above 30 seconds after profiling and one bounded optimization cycle; if exact required aggregates exceed a reasonable documented laptop memory envelope on representative input; or if combined-log compatibility cannot be delivered without expanding into a custom-format language during the weekend.

## Dependencies and Traceability

- Strategic priorities and constraints: `STRATEGIC_PLAN.md`.
- Technical boundaries and CLI schema: `PROJECT_ARCHITECTURE.md`.
- Delivery sequence and verification: `IMPLEMENTATION_PLAN.md`.
- Step-by-step implementation prompts: `CLAUDE_CODE_GUIDE.md`.

