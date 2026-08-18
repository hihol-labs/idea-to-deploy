# Product Requirements Document: nginx-insights

## 1. Product Summary

`nginx-insights` is a local Python 3.11 CLI that turns nginx common/combined access-log streams into four operational summaries: top client IPs, top error-producing URLs, hourly request percentages, and unique User-Agent share. The default is colored terminal output; JSON and CSV are first-class pipeline formats.

## 2. Problem and Outcome

During incidents and routine investigations, engineers often need a small set of traffic signals before a central observability system is available or worth operating. Shell pipelines are fast to start but fragile to quote, repeat, and integrate. The desired outcome is a reproducible single local command that analyzes a 1 GB log in under 30 seconds on a documented laptop without uploading or persisting the log.

## 3. Users and Use Context

Primary users are on-call SREs, DevOps engineers, and platform engineers on Linux or macOS with Python 3.11. They invoke the tool interactively against a file, pipe decompressed/remote output into stdin, or consume JSON/CSV in another process.

## User Stories

### US-01: Immediate Local Summary

As an on-call SRE, I want to stream an nginx access log into one local command so that I can see the main traffic signals without deploying infrastructure.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] With no paths, valid combined-format lines on stdin produce a report and exit `0`.
- [ ] With one or more readable paths, all files are processed in argument order as one logical input.
- [ ] No database, network request, server, or persistent analysis file is created.

### US-02: Identify Heavy Clients

As an SRE, I want the ten most frequent client IPs so that I can identify dominant or suspicious callers.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] The report lists at most 10 IPs ordered by descending valid-request count.
- [ ] Equal counts are ordered lexicographically by IP for deterministic output.
- [ ] Malformed lines do not contribute to counts.

### US-03: Identify Failing URLs

As a DevOps engineer, I want the ten URLs with the most 4xx/5xx responses so that I can focus failure investigation.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Only statuses 400 through 599 contribute to the ranking.
- [ ] The request-target is reported without method or HTTP protocol.
- [ ] Results contain at most 10 rows with deterministic count/key ordering.

### US-04: Understand Hourly Traffic Shape

As a platform engineer, I want every hour's request percentage so that I can recognize load concentration and gaps.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] The report always contains hour buckets `00` through `23` in order.
- [ ] Each bucket uses `100 × hourly_request_count / total_valid_requests`, not an unscaled fraction.
- [ ] Percentages total approximately 100%, within renderer rounding tolerance.

### US-05: Measure User-Agent Diversity Safely

As an SRE, I want the share of unique User-Agents with an explicit capacity failure so that I can use the metric without silent approximation or uncontrolled growth.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] The share is `100 × unique_non_null_user_agent_count / total_valid_requests`.
- [ ] The report includes unique count, records containing a User-Agent, total valid requests, and percentage.
- [ ] Common-format records have no User-Agent and contribute only to the valid-request denominator.
- [ ] Inserting a new User-Agent beyond `--max-unique-user-agents` stops analysis with exit `4` and a diagnostic on stderr.

### US-06: Integrate with Pipelines

As a DevOps engineer, I want stable JSON and CSV output so that downstream commands do not scrape terminal presentation.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `--json` emits one parseable schema-versioned object and exits `0` on valid input.
- [ ] `--csv` emits a parseable `section,rank,key,count,percentage` table and exits `0` on valid input.
- [ ] JSON and CSV contain no ANSI escapes or stderr diagnostics on stdout.
- [ ] Passing both flags is a usage error with exit `2`.

### US-07: Read Compressed Logs Conveniently

As an operator, I want direct gzip input so that I can avoid a separate decompression process.

**Priority:** P1 (Should)

**Acceptance criteria:**

- [ ] A post-MVP design preserves streaming and detects gzip explicitly.
- [ ] Until delivered, `gzip -cd access.log.gz | nginx-insights --json` remains documented and supported.

### US-08: Analyze Custom Formats

As an nginx administrator, I want to describe a custom `log_format` so that non-standard logs can use the same reports.

**Priority:** P2 (Could)

**Acceptance criteria:**

- [ ] Any future syntax is specified and tested before implementation.
- [ ] Existing `common` and `combined` behavior remains backward compatible.

## 5. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-01 | P0 | Read UTF-8 nginx text incrementally from stdin or ordered paths without loading the file into memory |
| FR-02 | P0 | Parse standard common/combined records; count and skip malformed individual lines; exit `3` if no record is valid |
| FR-03 | P0 | Count valid requests by client IP and return deterministic top 10 |
| FR-04 | P0 | Count request targets for status 400–599 and return deterministic top 10 |
| FR-05 | P0 | Return all 24 hourly percentages using `100 × hourly_request_count / total_valid_requests` |
| FR-06 | P0 | Calculate exact non-null unique User-Agent count and share over total valid requests |
| FR-07 | P0 | Enforce a positive configurable unique User-Agent cap and exit `4` on exhaustion |
| FR-08 | P0 | Default to Rich terminal output, with color only for capable terminals and an explicit `--no-color` override |
| FR-09 | P0 | Emit a stable schema-versioned JSON document with numeric values via `--json` |
| FR-10 | P0 | Emit normalized CSV with the documented header via `--csv` |
| FR-11 | P0 | Keep diagnostics on stderr and data/report output on stdout |
| FR-12 | P1 | Support gzip directly without changing report semantics |
| FR-13 | P2 | Allow a configurable top-N while retaining top 10 as the default |
| FR-14 | P2 | Support explicitly described custom nginx formats |

## 6. Non-Functional Requirements

| ID | Requirement | Acceptance measure |
|---|---|---|
| NFR-01 Performance | Analyze 1 GB in under 30 seconds | Three timed runs of deterministic fixture on documented laptop each pass |
| NFR-02 Streaming | Do not retain parsed records | Design/test inspection confirms aggregates only |
| NFR-03 Privacy | No network, telemetry, database, or persistent analysis output | Dependency and behavior inspection |
| NFR-04 Portability | Install and run under Python 3.11 on Linux and macOS | Clean virtualenv smoke tests |
| NFR-05 Determinism | Stable sorting, schemas, and rounding | Golden tests repeated across runs |
| NFR-06 Quality | At least 90% product-module coverage and green lint/types | Recorded pytest, Ruff, and mypy commands |
| NFR-07 Safety | Treat logs as untrusted data and escape output | Hostile fixture tests; no input evaluation |

## 7. CLI and Exit Contract

The authoritative command/options/input/output specification is under `## CLI Interface` in `PROJECT_ARCHITECTURE.md`. All modes use the complete contract: `0` success/help/version; `1` unexpected internal/runtime failure; `2` usage error; `3` input/parse failure; `4` unique-cardinality exhaustion. Code `4` specifically means the exact unique User-Agent limit was exhausted and may not be omitted or remapped.

## 8. Output Semantics

Counts and denominators use valid parsed requests only. `skipped_lines` remains visible as quality metadata. Percentages are numeric, rounded only at the reporting boundary, and JSON/CSV retain four decimal places of precision. Terminal mode may display two decimals. Empty top lists are allowed when valid traffic contains no 4xx/5xx responses.

## 9. Out of Scope

- Authentication, accounts, authorization, secrets, or multi-tenancy.
- Database, persistent index, saved dashboards, or historical cross-run comparison.
- HTTP API, daemon, server, UI, cloud deployment, Docker requirement, or Kubernetes.
- Log tail-follow mode, remote SSH/S3 retrieval, automatic rotation discovery, or telemetry.
- Exact support for arbitrary custom nginx `log_format` expressions in the MVP.
- Direct gzip handling in P0; stdin decompression is the supported workaround.

## 10. Release Acceptance

Release requires all P0 story criteria, installable wheel and sdist, structural JSON/CSV tests, the complete `0/1/2/3/4` exit matrix, and the recorded 1 GB benchmark below 30 seconds. Documentation must state format limitations and metric denominators.

## 11. Kill Criteria

Do not release if the reference benchmark remains at or above 30 seconds after profiling and reasonable single-process optimization; if any output mode calculates different metrics; if malformed-only input can succeed; if cardinality exhaustion can continue with an approximate or partial result instead of exit `4`; or if delivery requires a database, HTTP API, paid component, server, cloud, or Kubernetes. Revise the spec before changing any of these contracts.

## 12. Dependencies and Traceability

Architecture and schemas are defined in `PROJECT_ARCHITECTURE.md`. Delivery order and proof commands are defined in `IMPLEMENTATION_PLAN.md`. Product priorities and market rationale are defined in `STRATEGIC_PLAN.md`. Implementation prompts in `CLAUDE_CODE_GUIDE.md` must cite the relevant requirement and preserve this PRD as the durable source of truth.

