# Product Requirements Document: nginx-insights

## 1. Product Summary

`nginx-insights` gives DevOps/SRE users four trustworthy nginx access-log views from a local command: top client IPs, top error-producing URL paths, hourly request percentages, and unique User-Agent share. It processes a file or stdin in one pass, defaults to colored terminal output, and supports JSON and CSV pipelines.

The MVP is free, open source, installable with pip, and deliverable in one weekend. `PROJECT_ARCHITECTURE.md` is authoritative for data, CLI, output, and failure contracts.

## 2. Problem and Outcome

During incident triage, users often have logs but no configured dashboard. Ad-hoc shell pipelines are easy to get wrong, while full analytics stacks require too much setup. A successful outcome is one command that completes a 1 GB representative log in under 30 seconds on the documented laptop baseline and returns deterministic, scriptable results.

## User Stories

- As a SRE, I want to stream an nginx log from a file or stdin, so that I can inspect traffic without loading the file into memory or deploying a service. **Priority: P0.** Acceptance criteria: file and stdin produce identical reports; processing is single-pass; a 1 GB benchmark completes in under 30 seconds on the documented baseline.
- As an on-call engineer, I want the ten most active client IPs, so that I can identify dominant or suspicious sources quickly. **Priority: P0.** Acceptance criteria: every valid request contributes once; results are count-descending then IP-ascending; no more than ten rows appear.
- As a service owner, I want the ten URL paths with the most 4xx/5xx responses, so that I can focus on broken or failing routes. **Priority: P0.** Acceptance criteria: only statuses 400–599 count; query strings/fragments are excluded; ties are path-ascending; records without a usable path are excluded from this metric.
- As a capacity engineer, I want each hour's share of valid requests, so that I can see daily traffic shape. **Priority: P0.** Acceptance criteria: all 24 hours appear; each percentage uses `100 × hourly_request_count / total_valid_requests`; the record's encoded timezone offset is retained; rounding occurs only for output.
- As a platform engineer, I want the share of unique User-Agent values, so that I can estimate client diversity. **Priority: P0.** Acceptance criteria: the numerator is distinct non-null User-Agent strings; the denominator is valid requests with a non-null User-Agent; share is zero when that denominator is zero; exhausting the configured exact-cardinality cap returns code 4 without a normal report.
- As an automation author, I want stable JSON and CSV output, so that I can consume reports in pipelines without scraping terminal tables. **Priority: P0.** Acceptance criteria: `--json` and `--csv` are mutually exclusive; stdout contains only the chosen data format; diagnostics use stderr; machine formats never include ANSI escapes.
- As an operator, I want malformed input to be visible and optionally fatal, so that I can decide whether a report is trustworthy. **Priority: P0.** Acceptance criteria: invalid lines are counted; non-strict mode can report when at least one record is valid; `--fail-on-malformed` returns 3 and suppresses the normal report when any line is invalid; no valid records returns 3.
- As an operator with archived logs, I want direct gzip input, so that I can avoid a decompression pipeline. **Priority: P1.** Acceptance criteria: `.gz` input is detected explicitly, decompressed as a stream, and produces the same report as equivalent text.
- As a frequent user, I want a configurable top-N result size, so that I can expand investigations after the fixed overview. **Priority: P2.** Acceptance criteria: a positive validated option controls both ranked lists without altering default top 10 behavior.

## 4. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept one text file path, `-`, or omitted input for stdin and process line by line |
| FR-02 | Parse supported nginx common and combined access-log lines and count malformed physical lines |
| FR-03 | Produce exact top-10 client-IP counts with deterministic tie-breaking |
| FR-04 | Produce exact top-10 normalized paths for 400–599 responses |
| FR-05 | Produce 24 hourly counts and percentages using `100 × hourly_request_count / total_valid_requests` |
| FR-06 | Produce distinct User-Agent count, observation count, and percentage share |
| FR-07 | Render terminal output by default and stable JSON/CSV when selected |
| FR-08 | Enforce a configurable positive cardinality cap independently for IPs, paths, and User-Agents |
| FR-09 | Implement the complete exit-code contract `0/1/2/3/4` from `PROJECT_ARCHITECTURE.md` |
| FR-10 | Print data only to stdout and diagnostics only to stderr |

### P1 — Should ship after MVP

- Stream gzip-compressed file input while keeping stdin behavior unchanged.

### P2 — Could ship

- Allow a validated positive `--top` option; default remains 10.

## 5. Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | 1 GB in under 30 seconds on the documented baseline | Automated benchmark with generated fixture and output redirected |
| NFR-02 | Input is never fully materialized | Code review plus peak-RSS benchmark |
| NFR-03 | Results are deterministic | Repeat golden tests and explicit tie fixtures |
| NFR-04 | Compatible with Python 3.11 | CI/test environment and package metadata |
| NFR-05 | Installable through pip | Build wheel, install into clean venv, run smoke test |
| NFR-06 | No network, persistence, authentication, database, server, cloud, or Kubernetes | Dependency/config review and network-disabled integration run |
| NFR-07 | Untrusted log text cannot inject terminal control sequences | Renderer security fixtures |
| NFR-08 | First-party line coverage is at least 90% | Coverage command in `IMPLEMENTATION_PLAN.md` |

## 6. Input and Parsing Scope

Supported input is uncompressed nginx common or combined access-log text encoded as UTF-8. The parser recognizes standard field order, quoted requests, referrer and User-Agent fields, IPv4/IPv6 address text, timezone-bearing timestamps, and `-` sentinel values. Custom `log_format`, JSON logs, multiline events, and corrupted encodings are not interpreted heuristically; their lines are malformed under the exit policy.

For rankings, URL means the path extracted from the request target. Query and fragment components do not participate. Error means HTTP status 400 through 599 inclusive.

## 7. Output Requirements

Terminal mode uses Rich tables and color only for an interactive terminal unless `--no-color` is supplied. JSON uses the top-level objects defined in `PROJECT_ARCHITECTURE.md`. CSV uses the stable `section,rank,label,count,percentage` long-form schema. All three are projections of one report model.

Every successful report exposes `total_lines`, `valid_requests`, and `invalid_lines`. Hour rows always include 00–23 even when counts are zero. Numeric machine output is locale-independent.

## 8. Failure Contract

| Code | Product interpretation |
|---:|---|
| 0 | Complete report emitted |
| 1 | Unexpected internal failure |
| 2 | Invalid invocation or input I/O failure |
| 3 | Input parsing did not meet the selected quality policy |
| 4 | Unique-cardinality exhaustion prevented an exact complete report |

Codes 2, 3, and 4 suppress normal report output. Error messages identify the category without echoing entire untrusted log lines.

## 9. Out of Scope

- Authentication, users, tenancy, permissions, or secrets
- Database, retained history, cache, or incremental state
- HTTP API, web UI, daemon/server, or background service
- Cloud deployment, containers, Docker, or Kubernetes
- Live nginx control, log mutation, packet capture, or remote collection
- Arbitrary/custom nginx `log_format` parsing in MVP
- Approximate cardinality or sampled rankings

## 10. Dependencies and Assumptions

- Users provide readable local input or stdin and understand its nginx log format.
- Python 3.11 and pip are available.
- Click and Rich are the only required runtime libraries.
- The performance baseline uses local SSD input; network filesystems are not covered by the target.
- Product decisions and priorities in this PRD are pre-approved for the benchmark.

## 11. Release Acceptance

The release candidate is accepted only when all P0 acceptance criteria pass, the complete exit-code matrix is exercised, wheel installation succeeds in a clean Python 3.11 environment, and the 1 GB performance oracle meets the target. Required documentation must match observed CLI behavior.

## 12. Kill Criteria

Stop or formally revise the MVP if profiling proves Python 3.11 cannot meet 1 GB in 30 seconds on the baseline with exact results, or if exact cardinality cannot be bounded safely for representative input. Approximation, sampling, persistence, or a service architecture requires a new product decision rather than silent substitution.
