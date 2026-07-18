# Product Requirements Document: nginx-stream-report

## 1. Product summary

A local Python 3.11 command-line tool turns nginx common/combined access-log streams into four deterministic summaries for incident triage and automation. It is stateless, pip-installable, colored for humans, and schema-stable for pipelines.

## 2. Goals

- Produce top 10 IPs, top 10 error URLs, 24 hourly buckets, and unique User-Agent share in one pass.
- Accept a regular file, stdin, and (P1) a growing file.
- Keep machine-readable stdout clean and deterministic.
- Process a representative 1 GB log in under 30 seconds on the documented reference laptop.
- Remain local, $0, and operationally simple.

## 3. Non-goals

Authentication, database/storage, HTTP API, server mode, browser UI, cloud service, Kubernetes, remote log collection, full-text search, dashboards, arbitrary nginx `log_format`, and historical correlation across runs are out of scope.

## 4. Users and core journeys

1. An on-call SRE runs the command against a finite access log and reads the terminal report.
2. A DevOps engineer pipes rotated/decompressed log content through stdin and captures JSON.
3. A platform engineer consumes CSV rows in a spreadsheet or pipeline.
4. An operator sees malformed-record totals without losing valid results.

## 5. User stories

### US-1 — Analyze a finite log

As an on-call SRE, I want to analyze an nginx access-log file with one command so that I can identify traffic and error hotspots quickly.

Priority: **P0**

Acceptance criteria:

- [ ] Given a mixed valid common/combined fixture, the report’s top 10 IPs match an independent oracle.
- [ ] Only status 400–599 records contribute to the top 10 error URLs.
- [ ] Rankings use count descending and key ascending for deterministic ties.
- [ ] A successful finite-file run exits 0.

### US-2 — Understand time and client diversity

As an SRE, I want hourly request counts and User-Agent diversity so that I can recognize traffic shape and unusual client populations.

Priority: **P0**

Acceptance criteria:

- [ ] All hour keys `00` through `23` are present, including zeros.
- [ ] Each request uses the written hour from its own validated nginx timestamp; no host-time conversion occurs.
- [ ] Unique-UA share equals distinct non-empty User-Agent values divided by valid requests.
- [ ] Empty input reports zero unique UAs and `0.0` share without division error.

### US-3 — Use reports in pipelines

As a platform engineer, I want JSON and CSV output so that I can automate incident and reporting workflows.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` emits one parseable schema-versioned JSON document and no color codes.
- [ ] `--csv` emits the documented header and parseable rows with correct quoting and no color codes.
- [ ] stdin produces the same metrics as the same bytes read from a file.
- [ ] Diagnostics go only to stderr; stdout remains parseable.
- [ ] Passing `--json --csv` is rejected with exit code 2.

### US-4 — Trust imperfect input handling

As an operator, I want malformed records counted and optionally limited so that partial log corruption is visible and automations can fail safely.

Priority: **P1**

Acceptance criteria:

- [ ] Default behavior skips malformed lines, reports their count, and preserves valid metrics.
- [ ] `--max-invalid N` exits 2 once the count exceeds N.
- [ ] Diagnostics omit raw full lines by default to avoid leaking log data.

### US-5 — Watch a live file

As an incident responder, I want to follow a growing access log so that I can inspect the latest aggregate during an active event.

Priority: **P1**

Acceptance criteria:

- [ ] `--follow PATH` reads appended complete lines without rereading prior lines and refreshes a Rich terminal snapshot every 2 seconds by default.
- [ ] Follow mode rejects stdin, JSON, CSV, and non-TTY stdout with a usage error.
- [ ] `--refresh-interval` accepts only positive values; Ctrl-C leaves one final snapshot and uses the documented interrupt exit behavior.

### US-6 — Tune report depth

As a power user, I want configurable top-N output so that I can inspect more than ten keys when time permits.

Priority: **P2**

Acceptance criteria:

- [ ] A future `--top N` applies identically to IP and error-URL ranking.
- [ ] Default remains exactly 10.

## 6. Functional requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Read nginx common/combined records from a path, `-`, or omitted-path stdin using streaming iteration |
| FR-2 | P0 | Emit the four metrics with semantics defined in `PROJECT_ARCHITECTURE.md` |
| FR-3 | P0 | Render terminal, JSON, and CSV from one shared report model |
| FR-4 | P0 | Use TTY-aware color only for terminal mode |
| FR-5 | P0 | Enforce deterministic ranks, stable schemas, stderr diagnostics, and documented exit codes |
| FR-6 | P0 | Enforce separate exact IP/URL/UA cardinality ceilings plus fixed line/key limits; never silently approximate |
| FR-7 | P1 | Count malformed lines and enforce an optional invalid threshold |
| FR-8 | P1 | Follow appended lines in a regular file |
| FR-9 | P2 | Configure top-N |
| FR-10 | P2 | Consider explicitly labeled approximate cardinality/heavy-hitter modes |

## 7. Non-functional requirements

| Area | Requirement |
|---|---|
| Performance | Representative 1 GB fixture completes in <30 s on a named reference laptop; benchmark is reproducible |
| Memory | Never materialize input; enforce separate count/retained-byte ceilings, calibrate to a projected 192 MiB envelope, and verify peak RSS <256 MiB |
| Compatibility | Python 3.11; Linux/macOS/WSL primary; bounded binary lines, UTF-8 replacement decoding, traditional common/combined escaping |
| Reliability | Deterministic output and exit codes; malformed records cannot corrupt machine stdout |
| Privacy | No telemetry, network egress, persistence, or full-line diagnostic leakage by default |
| Quality | >=90% branch coverage for parser/aggregation; property/fixture tests for quoting and ranking |
| Packaging | Clean-environment wheel install exposes `nginx-stream-report` console command |

## 8. Output and UX requirements

Terminal mode gives readable labeled tables and a visible malformed-line warning. JSON and CSV follow the exact lossless schemas in `PROJECT_ARCHITECTURE.md`; schema-breaking changes require a version increment. CSV documentation warns that lossless values may be interpreted as formulas by spreadsheets. `--help` documents source selection, mutually exclusive formats, metric definitions, limits, exit codes, and examples. Empty valid input is a successful zero report unless invalid-threshold behavior says otherwise.

## 9. Release acceptance

- All P0 story checks pass on common, combined, malformed, empty, tie, Unicode, and high-cardinality fixtures.
- File and stdin results are byte-equivalent after excluding the declared source label.
- A clean Python 3.11 environment installs the built wheel and runs help/report commands.
- The benchmark artifact proves the target or records the release blocker.
- Static checks, tests, dependency/security review, and manual terminal inspection pass.

## 10. Kill criteria

Do not release the MVP if the representative 1 GB run remains >=30 seconds after evidence-led profiling, exact metrics cannot stay within the documented memory guardrail, supported-format correctness is <99.9%, or reliable operation would require a database/server. In that case, revise the scope/architecture rather than quietly weakening guarantees.

## 11. Dependencies and traceability

Architecture and output schemas are authoritative in `PROJECT_ARCHITECTURE.md`. Priority rationale is in `STRATEGIC_PLAN.md`. Delivery tasks and commands are in `IMPLEMENTATION_PLAN.md`.
