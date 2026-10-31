# Product Requirements Document: nginx-log-report

## Product Summary

`nginx-log-report` gives DevOps and SRE engineers a fast, local summary of nginx combined access logs. It processes input incrementally, defaults to colored terminal output, and provides stable JSON and CSV representations for pipelines. It does not authenticate users, persist data, listen on a network, or require infrastructure.

## Goals

- Produce the four required metrics correctly from finite files and stdin.
- Meet the reference performance target of 1 GB in under 30 seconds on a laptop.
- Keep processing stateless and local, with an explicit guard against exact User-Agent cardinality exhaustion.
- Make human output readable and machine output deterministic.

## Non-Goals

- Authentication, authorization, database storage, HTTP API, server mode, cloud resources, or Kubernetes.
- A web dashboard, historical comparisons, alerting, log shipping, or full-text search.
- Supporting arbitrary nginx `log_format` definitions in the MVP.
- Silently approximating distinct counts.

## User Stories

- As a DevOps engineer, I want the top 10 client IPs so that I can identify dominant or suspicious traffic sources. **Priority: P0.** Acceptance: counts use valid records only; results sort by count descending then IP ascending; no more than 10 rows are returned in every format.
- As an on-call SRE, I want the top 10 URLs producing 4xx/5xx statuses so that I can find failing resources quickly. **Priority: P0.** Acceptance: only status codes 400–599 contribute; URLs with no errors are absent; ties are deterministic.
- As a capacity engineer, I want hourly request distribution as percentages so that I can see traffic concentration during the day. **Priority: P0.** Acceptance: every hour `00`–`23` is emitted; each percentage uses `100 × hourly_request_count / total_valid_requests`; displayed percentages sum to approximately 100% within rounding tolerance.
- As a reliability engineer, I want the share of unique User-Agents so that I can estimate client diversity without exporting logs. **Priority: P0.** Acceptance: the exact unique count and percentage are emitted; the percentage denominator is all valid requests; exceeding the configured unique limit exits `4` without a partial report.
- As a pipeline automation author, I want JSON and CSV modes so that I can consume the report without parsing terminal text. **Priority: P0.** Acceptance: the modes are mutually exclusive; stdout contains only the selected payload; schemas match `PROJECT_ARCHITECTURE.md`; diagnostics use stderr.
- As a DevOps operator, I want malformed records skipped and counted so that a partially damaged file still provides a useful report. **Priority: P1.** Acceptance: mixed input succeeds if at least one record is valid; all-invalid input exits `3`; diagnostics never expose a full raw log line.
- As an on-call SRE, I want to follow an actively written log so that I can stop and receive a summary for the observed window. **Priority: P1.** Acceptance: `--follow` works only with a regular file and a clean interrupt finalizes the report.
- As a maintainer, I want a reproducible performance benchmark so that changes cannot silently violate the 1 GB/30 s target. **Priority: P1.** Acceptance: fixture generation is deterministic; elapsed time and peak memory are recorded; the reference environment is documented.

## Functional Requirements

### P0 — Must ship

1. Accept one file path, stdin when the path is omitted, or `-` for stdin.
2. Parse nginx combined-log records and validate IP text, timezone-aware timestamp, request target, status, and User-Agent.
3. Produce top-10 client IP counts from valid records.
4. Produce top-10 request targets whose responses are 4xx or 5xx.
5. Produce 24 hourly buckets. Each percentage is exactly defined by `100 × hourly_request_count / total_valid_requests` before display rounding.
6. Produce the exact count of unique User-Agents and their share of valid requests.
7. Protect unique tracking with `--max-unique-user-agents`; a would-be overflow terminates with exit code `4`.
8. Default to Rich terminal output and support mutually exclusive `--json` and `--csv` modes.
9. Implement the complete exit-code contract `0/1/2/3/4` from `PROJECT_ARCHITECTURE.md`.
10. Install through pip on Python 3.11 and expose `nginx-log-report` as a console command.

### P1 — Should ship

1. Count and display malformed lines without echoing their contents.
2. Support `--follow` for regular files and produce a final report after a clean keyboard interrupt.
3. Provide deterministic generated performance data and a documented benchmark procedure.

### P2 — Could follow

1. Read gzip-compressed input directly.
2. Accept a named set of additional nginx log formats.
3. Add an explicitly designed approximate-cardinality mode for unusually high-cardinality workloads.

## Output Acceptance Contract

Terminal output contains four clearly labeled sections and valid/malformed totals. JSON contains the versioned keys defined in `PROJECT_ARCHITECTURE.md`. CSV contains the exact normalized header `metric,rank,key,count,percentage`. Rankings and serialization are deterministic for identical input. Machine formats never contain ANSI escape sequences.

## Quality Requirements

| Attribute | Requirement |
|---|---|
| Performance | Process a deterministic 1 GB combined-log fixture in under 30 seconds on the documented reference laptop |
| Memory | Stream input; retain no raw lines or record list; fail explicitly at User-Agent cardinality limit |
| Correctness | Golden tests cover rankings, 4xx/5xx filtering, all 24 hours, percentages, and exact unique share |
| Compatibility | Python 3.11; Linux and macOS are primary, with no deliberate Windows-only incompatibility |
| Security | No network or persistence; untrusted values escaped by standard serializers; no tracebacks by default |
| Accessibility | `--no-color` works and non-TTY terminal output defaults to no ANSI color |

## Release Acceptance Scenarios

1. Given a mixed valid/malformed fixture, all three output modes agree on counts and percentages and exit `0`.
2. Given only 404 and 500 records plus successful records, error ranking contains only the error targets.
3. Given requests across timezone-aware timestamps, the 24 hourly percentages follow each entry's recorded local hour and the literal formula.
4. Given no valid records, the command exits `3`, reports the condition on stderr, and emits no JSON/CSV payload.
5. Given one more unique User-Agent than the configured maximum, the command exits `4` and emits no partial report.
6. Given a missing file or read failure, the command exits `1`; given incompatible options, it exits `2`.
7. Given the generated 1 GB fixture on the reference laptop, the timed command completes below 30 seconds.

## Dependencies and Assumptions

The parser supports the conventional nginx combined access-log shape for MVP. The performance target depends on the documented reference laptop, local uncompressed storage, and representative line lengths. `PROJECT_ARCHITECTURE.md` is authoritative for data and interface contracts; `IMPLEMENTATION_PLAN.md` sequences delivery.

## Kill Criteria

Pause release and re-scope if the 1 GB target remains unattainable after measured profiling, if exact cardinality cannot be bounded safely without defeating common usage, or if real-world combined logs cannot achieve reliable parser acceptance. Adding persistent or network infrastructure is not an automatic remedy because it violates the approved scope.
