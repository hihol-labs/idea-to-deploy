# Product Requirements Document: Nginx Stream Analytics CLI

## Product Summary

Nginx Stream Analytics CLI gives DevOps/SRE engineers a fast, private summary of one nginx access-log stream. It is a local, pip-installable Python 3.11 command that never requires authentication, a database, an API, a server, cloud resources, or Kubernetes.

## Goals and Success Measures

- Produce the four required reports correctly from a file or stdin in one pass.
- Complete a 1 GB reference log in under 30 seconds on a documented laptop.
- Provide readable colored terminal output and stable JSON/CSV pipeline contracts.
- Bound high-cardinality memory risk and report all failure classes through exit codes 0/1/2/3/4.
- Install cleanly through pip/pipx and cost $0 to run.

## Non-Goals

- Historical storage, dashboards, live tail-follow mode, multi-file joins, or remote collection.
- Arbitrary nginx `log_format` discovery in MVP; the supported combined-format grammar is explicit.
- Authentication, authorization, database, HTTP API, daemon/server, cloud, Docker, or Kubernetes.
- Approximate metrics or silent sampling.
- Replacing GoAccess or Elastic for durable observability.

## User Stories

### US-1 — Stream local or piped logs (P0)

As an on-call SRE, I want to analyze a file or stdin so that I can use the same command interactively and in pipelines.

Acceptance criteria:

- [ ] An existing readable path is consumed once in buffered streaming mode.
- [ ] Omitted `INPUT` and `INPUT=-` both consume stdin.
- [ ] The tool does not seek, modify, persist, or transmit input.
- [ ] Missing/unreadable input exits 1 with a concise stderr message and no partial report.

### US-2 — Identify busiest client IPs (P0)

As an SRE investigating traffic, I want the ten most frequent client IPs so that I can identify dominant sources.

Acceptance criteria:

- [ ] Only valid records increment IP counts.
- [ ] At most ten entries appear, ordered by count descending then IP ascending.
- [ ] Each entry contains rank, IP, and request count in all output modes.

### US-3 — Identify failing URLs (P0)

As an application operator, I want the ten request targets with the most 4xx/5xx responses so that I can prioritize failing routes.

Acceptance criteria:

- [ ] Only status codes 400–599 contribute.
- [ ] Grouping uses the parsed request target, including its query string when logged.
- [ ] At most ten entries appear, ordered by count descending then target ascending.
- [ ] A valid log with no 4xx/5xx records yields an empty error-URL ranking, not an error.

### US-4 — Understand hourly traffic shape (P0)

As an operations lead, I want requests distributed across hours as percentages so that I can see when traffic occurs.

Acceptance criteria:

- [ ] Output includes hours `00` through `23`, even when their count is zero.
- [ ] Every percentage uses `100 × hourly_request_count / total_valid_requests`.
- [ ] Percentages are presentation-rounded consistently and unrounded values sum to 100% within floating-point tolerance.
- [ ] Timestamps use the hour present in each log record; no timezone conversion is performed.

### US-5 — Measure User-Agent diversity (P0)

As an SRE checking client diversity, I want the share of unique User-Agents so that I can spot unusually concentrated or diverse traffic.

Acceptance criteria:

- [ ] The distinct count includes each non-empty User-Agent string once.
- [ ] Share equals `100 × distinct_non_empty_user_agents / total_valid_requests`.
- [ ] Empty/missing User-Agent values remain in the valid-request denominator but not the distinct numerator.
- [ ] Exceeding the distinct-key guardrail exits 4 without a partial report.

### US-6 — Use human-readable terminal output (P0)

As an engineer at a terminal, I want colored labeled tables so that I can scan the result quickly.

Acceptance criteria:

- [ ] Default output presents all four reports and valid/malformed totals.
- [ ] Color is enabled only for a capable TTY and can be disabled with `--no-color`.
- [ ] Untrusted log fields are rendered as text, never Rich markup or control instructions.

### US-7 — Automate with JSON or CSV (P0)

As a platform engineer, I want deterministic machine output so that CI and shell tooling can consume reports safely.

Acceptance criteria:

- [ ] `--json` emits the documented single-object schema; `--csv` emits the documented long-form schema.
- [ ] The flags are mutually exclusive and conflict exits 2.
- [ ] JSON/CSV contain no ANSI escapes; data is stdout and diagnostics are stderr.
- [ ] Repeated execution on identical input produces byte-identical machine output except a deliberately documented source label.

### US-8 — Read compressed logs directly (P1)

As an operator reviewing rotated logs, I want direct gzip input so that I do not need a decompression pipeline.

Acceptance criteria:

- [ ] Deferred until every P0 requirement and performance gate passes.
- [ ] If delivered, decompression remains local and streaming.

### US-9 — Choose ranking size (P2)

As an analyst, I want configurable top-N output so that I can inspect beyond ten entries.

Acceptance criteria:

- [ ] Deferred; MVP remains fixed at ten.

## Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-1 | Accept one optional file path; otherwise read stdin |
| FR-2 | Parse the declared nginx combined-format subset and count malformed lines |
| FR-3 | Report top-10 IPs and top-10 400–599 request targets with deterministic ties |
| FR-4 | Report 24 hourly counts and percentages using `100 × hourly_request_count / total_valid_requests` |
| FR-5 | Report distinct non-empty User-Agent count and its percentage of valid requests |
| FR-6 | Provide terminal, JSON, and CSV output contracts |
| FR-7 | Enforce line-length and unique-cardinality resource guardrails |
| FR-8 | Implement the exact exit-code contract 0/1/2/3/4 |

### P1 — Should ship after MVP

- Direct streaming `.gz` input with the same reports and errors.

### P2 — Could ship later

- Configurable top-N, explicit URL normalization modes, and additional documented nginx formats.

## Output Contract

Terminal output has four labeled sections and totals. JSON keys and CSV columns are defined in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md#cli-interface). Percentages are numbers, not formatted fractions. Machine formats are versioned, deterministic, UTF-8, and free of ANSI codes.

The complete process result contract is:

- `0`: successful complete report;
- `1`: input/I/O or unexpected runtime failure;
- `2`: invalid CLI usage;
- `3`: no valid records;
- `4`: unique-cardinality exhaustion.

No partial machine report is emitted on nonzero exit.

## Non-Functional Requirements

| Area | Requirement |
|---|---|
| Performance | 1 GB in <30 seconds on the documented reference laptop |
| Memory | No raw-record retention; distinct-key tracking stops at the configured ceiling |
| Compatibility | Python 3.11; pip/pipx installable on supported desktop/server OSes |
| Privacy | No network egress, telemetry, persistent state, or input modification |
| Reliability | Deterministic ties/schemas; malformed lines disclosed; failures fail closed |
| Security | Terminal markup/control escaping, bounded line size and cardinality, read-only input |
| Accessibility | `--no-color`, meaningful labels, machine-readable alternatives |

## Release Acceptance

- Every P0 story's acceptance criteria pass under Python 3.11.
- Golden outputs match documented terminal, JSON, and CSV schemas.
- CLI tests demonstrate each exit code 0/1/2/3/4.
- Generated representative 1 GB input passes the timed benchmark and records peak RSS.
- Clean wheel and pipx smoke installs expose `nginx-log-report`.
- A current exact-candidate Idea to Deploy adjudication receipt accepts the implementation.

## Kill Criteria

Pause and rescope if the single-process implementation cannot reach the 1 GB/30 s target after measurement and focused profiling; if exact distinct tracking cannot be safely bounded with a comprehensible exit-4 contract; or if supported-format ambiguity prevents deterministic parsing within the weekend. Do not solve these by adding a database, server, cloud stack, or silent approximation.

## Dependencies and Traceability

The architecture and schemas live in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md). Delivery steps and verification commands live in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Priorities originate in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md).
