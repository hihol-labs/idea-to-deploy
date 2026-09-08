# Product Requirements Document: nginx-insights

## 1. Summary

`nginx-insights` gives DevOps and SRE engineers a fast, local snapshot of nginx access logs. It streams files or stdin and reports top-10 IPs, top-10 URL paths producing 4xx/5xx responses, hourly request percentages, and unique User-Agent share. Default output is colored terminal text; JSON and CSV are stable pipeline modes.

## 2. Problem and Outcome

During incidents and ad hoc investigations, engineers often need a small set of answers before—or instead of—loading logs into a full observability platform. Shell one-liners are easy to get subtly wrong, while persistent analytics systems require infrastructure and retained data. The outcome is one trustworthy command that produces the required snapshot locally from gigabyte-scale input.

## 3. Users

- On-call SREs investigating traffic concentration and error spikes.
- DevOps engineers feeding log summaries into scripts or CI jobs.
- Platform engineers working in offline, restricted, or temporary environments.

## User Stories

- As a SRE, I want to see the ten most frequent client IPs so that I can spot concentrated or suspicious traffic.
  - Priority: P0
  - Acceptance: output contains at most ten IP entries sorted by count descending and key ascending for ties.
  - Acceptance: counts match the valid-record fixture exactly.
- As an on-call engineer, I want to see the ten URL paths with the most 4xx/5xx responses so that I can localize failing routes.
  - Priority: P0
  - Acceptance: only statuses 400 through 599 contribute.
  - Acceptance: query strings and fragments do not split the same path.
- As a DevOps engineer, I want hourly request distribution percentages so that I can recognize the traffic shape across the day.
  - Priority: P0
  - Acceptance: all 24 hour buckets are present.
  - Acceptance: each value uses `100 × hourly_request_count / total_valid_requests` and the non-empty percentages sum to 100 within floating-point tolerance.
- As a platform engineer, I want the share of unique User-Agents so that I can estimate client diversity without retaining raw logs.
  - Priority: P0
  - Acceptance: the share is the unique non-empty UA count divided by requests carrying a non-empty UA, multiplied by 100.
  - Acceptance: exceeding the configured unique-UA cap emits no partial report and exits 4.
- As a terminal user, I want colored readable output by default so that I can scan the result quickly.
  - Priority: P0
  - Acceptance: a TTY gets four labeled Rich sections; redirected output is uncolored unless explicitly forced.
- As an automation author, I want JSON output so that I can consume a single structured report without scraping terminal text.
  - Priority: P0
  - Acceptance: `--json` emits one valid document on stdout and diagnostics only on stderr.
- As an automation author, I want CSV output so that I can pipe the report into tabular tools.
  - Priority: P0
  - Acceptance: `--csv` emits the fixed `metric,rank,key,count,percentage` header and parseable rows.
- As an operator, I want invalid lines counted rather than silently accepted so that I can judge report completeness.
  - Priority: P1
- As an operator with compressed archives, I want direct gzip input so that I can avoid a decompression pipeline.
  - Priority: P2

## 5. Functional Requirements

### P0 — Must

| ID | Requirement |
|---|---|
| FR-001 | Accept zero or more file arguments; read stdin when none are supplied; allow `-` once among file inputs. |
| FR-002 | Parse declared nginx common and combined access-log records into typed values. |
| FR-003 | Skip malformed records, count them, and succeed if at least one valid record exists. |
| FR-004 | Count all valid requests per client IP and return at most ten, ordered by count descending then IP ascending. |
| FR-005 | Count normalized URL paths only for status codes 400–599 and return at most ten with deterministic ordering. |
| FR-006 | Remove query and fragment portions from request targets before URL error aggregation. |
| FR-007 | Emit 24 hourly buckets based on each record's encoded timezone offset. |
| FR-008 | Calculate hourly percentage as `100 × hourly_request_count / total_valid_requests`. |
| FR-009 | Count distinct non-empty User-Agent values exactly up to a configurable positive cap; fail before exceeding it. |
| FR-010 | Default to a four-section Rich terminal report with processed/valid/invalid totals. |
| FR-011 | Support mutually exclusive `--json` output with the schema in `PROJECT_ARCHITECTURE.md`. |
| FR-012 | Support mutually exclusive `--csv` output with the schema in `PROJECT_ARCHITECTURE.md`. |
| FR-013 | Auto-detect color for terminal output and support `--color/--no-color`; reject color options with machine modes. |
| FR-014 | Implement the full exit contract: 0 success, 1 I/O/operational failure, 2 usage/configuration error, 3 zero valid requests, 4 unique-cardinality exhaustion. |
| FR-015 | Keep stdout report-only and send warnings/errors to stderr. |

### P1 — Should

| ID | Requirement |
|---|---|
| FR-101 | Surface total, valid, and invalid line counts in every output mode. |
| FR-102 | Include concise source context without exposing raw log lines in diagnostics. |

### P2 — Could

| ID | Requirement |
|---|---|
| FR-201 | Read gzip files directly. |
| FR-202 | Accept a user-specified nginx log-format description. |

## 6. Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-001 | Process a deterministic 1 GB representative log in under 30 seconds on the documented laptop. | Median of three benchmark trials |
| NFR-002 | Stream input in one pass and never retain raw lines. | Design inspection plus peak-memory benchmark |
| NFR-003 | Memory is independent of line count except exact distinct-key counters, with the UA set hard-capped. | Unit cap test and benchmark RSS |
| NFR-004 | Produce deterministic output for identical bytes and options. | Repeated golden comparison |
| NFR-005 | Make no network call and retain no input data. | Integration test with network denied and architecture review |
| NFR-006 | Install and run on Python 3.11 through pip. | Clean-environment wheel smoke test |
| NFR-007 | Maintain at least 90% line coverage in parser, aggregation, and serialization modules. | Coverage gate |
| NFR-008 | Treat log fields as untrusted literal data in all renderers. | Injection-oriented fixtures |

## 7. Output Acceptance Contract

For the canonical fixture, terminal, JSON, and CSV modes must agree on counts and percentage inputs. JSON retains numeric percentage precision; terminal and CSV display two decimal places. Top lists contain zero to ten entries. Hourly output always contains 24 entries. A successful mixed-quality input reports its invalid count and exits 0.

Machine modes emit no banner, progress bar, warning, or color sequence on stdout. If processing fails, they emit no partial report. Broken or unreadable input maps to 1; option misuse to 2; no valid records to 3; unique-cardinality exhaustion to 4.

## 8. Scope Exclusions

- Authentication and user/account management.
- Any database, cache, retained history, or raw-log storage.
- HTTP API, daemon, web UI, or server.
- Cloud services, hosted telemetry, Docker requirement, or Kubernetes.
- Live file-follow/tail mode in the MVP.
- GeoIP, bot classification, percentile latency, bandwidth, or referrer analytics.
- Approximate top-k or approximate unique counting.

## 9. Dependencies and Assumptions

The runtime stack is Python 3.11, Click, Rich, and standard-library dataclasses. Inputs use nginx common or combined format and are readable by the invoking user. The 30-second target applies to a representative local SSD laptop profile recorded with benchmark evidence; it is not a universal guarantee for every disk, CPU, or pathological cardinality distribution.

## 10. Release and Kill Criteria

Release requires all P0 acceptance checks, successful wheel installation, complete `0/1/2/3/4` tests, no unresolved high-severity issue, and a passing reference benchmark. Re-scope if exact distinct IP/path state causes unacceptable peak memory on the reference corpus. Stop the weekend MVP if the performance target remains unmet after two evidence-driven optimization passes; do not introduce a database or server to mask failure.

## 11. Traceability

Technical realization is specified in `PROJECT_ARCHITECTURE.md`. Work order and verification commands are in `IMPLEMENTATION_PLAN.md`. Implementation prompts must preserve this PRD as the behavioral source of truth.
