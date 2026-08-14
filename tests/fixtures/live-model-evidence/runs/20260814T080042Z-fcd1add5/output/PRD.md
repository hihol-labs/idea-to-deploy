# Product Requirements Document: Nginx Stream Analytics CLI

## 1. Product Summary

Nginx Stream Analytics CLI gives DevOps and SRE engineers a fast, local summary of nginx combined access logs. A single invocation reads a file or stdin and reports top client IPs, URLs with the most 4xx/5xx responses, hourly request distribution, and unique User-Agent share in terminal, JSON, or CSV form.

## 2. Problem Statement

During incident response, engineers frequently need a small set of reliable traffic indicators. Shell pipelines are quick but brittle, while full analytics platforms require ingestion, storage, and operations. The product fills the gap with deterministic one-pass analysis that does not move or retain logs.

## 3. Goals and Non-Goals

### Goals

- Analyze a representative 1 GB nginx log in under 30 seconds on a documented laptop.
- Compute all required metrics in a single sequential pass.
- Work interactively and in automation through stable text, JSON, and CSV contracts.
- Install through pip on Python 3.11.
- Make malformed input and exact-cardinality limits visible through stderr and exit status.

### Non-Goals

- Authentication or multi-user access.
- Database, history, indexing, or cross-run comparison.
- HTTP API, server, dashboard, cloud service, Docker, or Kubernetes deployment.
- Direct decompression, log tail-following, or remote log transport in MVP.
- Supporting arbitrary custom nginx `log_format` definitions in MVP.

## 4. Personas

- **On-call SRE:** needs trustworthy results in seconds while diagnosing an incident.
- **Platform engineer:** needs a stable machine-readable report inside shell or CI automation.
- **DevOps engineer:** needs a low-setup local view of error hotspots after deployment.

## User Stories

### US-1 — Analyze a local log

As an on-call SRE, I want to analyze an nginx access-log file with one command so that I can identify the busiest client sources quickly.

Priority: **P0**

Acceptance criteria:

- [ ] Given a valid combined-format fixture, the report lists at most 10 IPs ordered by count descending and IP ascending for ties.
- [ ] Input is processed sequentially without retaining parsed records.
- [ ] Successful output exits 0.

### US-2 — Find error-producing URLs

As a DevOps engineer, I want the URLs responsible for the most 4xx and 5xx responses so that I can focus investigation on failing routes.

Priority: **P0**

Acceptance criteria:

- [ ] Only records with status 400–599 contribute to this ranking.
- [ ] The report lists at most 10 request targets ordered by count descending and target ascending for ties.
- [ ] The result is present consistently in text, JSON, and CSV.

### US-3 — Understand hourly traffic shape

As an SRE, I want requests grouped by their logged hour so that I can see when traffic concentrated.

Priority: **P0**

Acceptance criteria:

- [ ] All 24 hours from `00` through `23` are emitted in order.
- [ ] Every value is a percentage computed using `100 × hourly_request_count / total_valid_requests`.
- [ ] Hours are taken from each timestamp's recorded offset without conversion to machine-local time.
- [ ] Empty valid input yields `0.0` for all 24 hours.

### US-4 — Measure User-Agent diversity

As a platform engineer, I want the share of unique User-Agents so that I can spot unusually diverse or concentrated clients.

Priority: **P0**

Acceptance criteria:

- [ ] The percentage is `100 × distinct_non_null_user_agents / total_valid_requests`.
- [ ] A missing `-` User-Agent does not add to the distinct count but remains in the denominator.
- [ ] If the next distinct User-Agent would exceed the configured exact ceiling, no report is emitted and the process exits 4.

### US-5 — Use pipeline-safe output

As a platform engineer, I want JSON or CSV output so that I can feed the same results into automation without scraping terminal tables.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` emits one valid JSON object with the documented top-level keys and no ANSI escapes.
- [ ] `--csv` emits the stable `report,key,count,percentage` header and normalized rows with no ANSI escapes.
- [ ] `--json` and `--csv` together cause Click usage exit code 2.
- [ ] Report data is written only to stdout and diagnostics only to stderr.

### US-6 — Pipe logs through stdin

As an SRE, I want to read stdin so that I can use decompression and filtering tools without creating temporary files.

Priority: **P0**

Acceptance criteria:

- [ ] Omitting `INPUT` or passing `-` reads stdin.
- [ ] A named file and stdin produce identical reports for identical bytes.
- [ ] Input open/read failures exit 1 with a concise stderr diagnostic.

### US-7 — Control malformed input handling

As a platform engineer, I want tolerant and strict parsing modes so that I can choose between incident triage and validation.

Priority: **P1**

Acceptance criteria:

- [ ] Default mode skips malformed non-empty lines, counts them, and emits one bounded warning summary.
- [ ] `--strict` exits 3 on the first malformed non-empty line and emits no partial report.
- [ ] Non-empty input with zero valid records exits 3.

### US-8 — Change ranking size

As an SRE, I want to change top-N so that I can expand an investigation without changing tools.

Priority: **P1**

Acceptance criteria:

- [ ] `--top N` applies to both IP and error-URL rankings.
- [ ] Values below 1 are rejected with exit code 2.

### US-9 — Support custom nginx formats

As an nginx administrator, I want to describe a custom `log_format` so that the tool works across nonstandard configurations.

Priority: **P2**

Acceptance criteria:

- [ ] Deferred until the combined-format MVP and performance target are complete.

## 6. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept one optional file path or stdin and stream UTF-8 nginx combined-log lines |
| FR-02 | Parse client IP, timezone-aware timestamp, request, status, bytes, referer, and User-Agent |
| FR-03 | Count all valid requests by client IP and output the deterministic top 10 by default |
| FR-04 | Count request targets for statuses 400–599 and output the deterministic top 10 by default |
| FR-05 | Output all 24 hourly percentages using `100 × hourly_request_count / total_valid_requests` |
| FR-06 | Output distinct non-null User-Agent count and its percentage of all valid requests |
| FR-07 | Stop with exit code 4 when the exact unique User-Agent ceiling would be exceeded |
| FR-08 | Default to colored Rich terminal output when stdout is a TTY |
| FR-09 | Provide mutually exclusive `--json` and `--csv` formats with stable schemas |
| FR-10 | Keep stdout for reports and stderr for diagnostics |
| FR-11 | Implement exit codes `0/1/2/3/4` exactly as documented in `PROJECT_ARCHITECTURE.md` |

### P1 — Should ship if the weekend allows

| ID | Requirement |
|---|---|
| FR-12 | Provide `--top` for both rankings |
| FR-13 | Provide `--strict` malformed-line behavior |
| FR-14 | Provide `--no-color`, `--version`, and complete `--help` text |

### P2 — Could follow later

| ID | Requirement |
|---|---|
| FR-15 | User-declared custom nginx formats |
| FR-16 | Explicit opt-in approximate unique counting with clearly distinct output semantics |

## 7. Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | Representative 1 GB input completes in <30 seconds on the named laptop | Repeatable local performance test, median of three runs |
| NFR-02 | Input is read in a single pass and records are not retained | Unit tests with a one-shot iterator plus code review |
| NFR-03 | Parser, aggregation, and renderer modules reach >=90% branch-relevant coverage | `pytest --cov` |
| NFR-04 | Machine formats are deterministic and contain no terminal escape sequences | Golden-output tests |
| NFR-05 | Package installs on clean Python 3.11 through pip | Build-and-install smoke test in a fresh virtual environment |
| NFR-06 | Input content is never executed and full sensitive lines are not echoed in diagnostics | Security-focused tests and review |

## 8. Output Contract Summary

- Terminal: summary plus Rich tables, color only on a TTY unless disabled.
- JSON: one object with `schema_version`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`.
- CSV: `report,key,count,percentage` followed by normalized report rows.
- Counts are exact unless a future explicitly opt-in approximation feature is introduced.
- Percentages are numeric and renderers use a shared snapshot to prevent cross-format disagreement.

## 9. Exit-Code Contract

| Code | Contract |
|---:|---|
| `0` | Complete successful report, including empty input |
| `1` | Input/runtime I/O, encoding, or unexpected internal failure |
| `2` | CLI usage or option validation error |
| `3` | Strict parse failure or non-empty input with no valid records |
| `4` | Unique-cardinality exhaustion |

## 10. Dependencies and Assumptions

- Python 3.11, Click, Rich, and standard-library `dataclasses` are approved.
- The supported MVP input is nginx combined format.
- The benchmark machine and generated fixture parameters will be recorded with results.
- No database, API, auth, hosted runtime, or telemetry is required.

## 11. Release Criteria

Release when every P0 acceptance criterion passes, all exit codes have CLI coverage, the clean-install smoke test passes, and the measured 1 GB target is below 30 seconds. P1 omissions are documented; P2 remains out of scope.

## 12. Kill Criteria

Pause or re-scope if profiling cannot bring representative 1 GB processing below 30 seconds, exact required aggregation cannot operate within a safe local memory bound, or scope pressure introduces a persistent or server component.

## 13. Traceability

Architecture and interface details live in `PROJECT_ARCHITECTURE.md`. Work packages and commands live in `IMPLEMENTATION_PLAN.md`. The MoSCoW and RICE rationale lives in `STRATEGIC_PLAN.md`.
