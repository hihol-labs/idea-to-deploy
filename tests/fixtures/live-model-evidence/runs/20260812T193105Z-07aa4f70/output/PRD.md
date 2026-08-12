# Product Requirements Document: nginx-report

## 1. Product Summary

`nginx-report` gives DevOps/SRE engineers a fast local summary of nginx combined access logs. It streams finite files or stdin without retaining requests and emits four exact analyses: top 10 client IPs, top 10 URLs with 4xx/5xx responses, hourly request distribution, and unique User-Agent share. Colored terminal text is the default; JSON and CSV are stable pipeline formats.

## 2. Problem and Outcome

During incidents and routine reviews, operators often need a trustworthy overview before deciding whether a full observability stack is justified. Existing platforms can be operationally excessive; hand-built shell pipelines are easy to misparse and difficult to standardize. The desired outcome is one pip-installable, private, reproducible command that processes a representative 1 GB log in under 30 seconds on a documented laptop.

## 3. Users

- On-call SREs triaging abnormal traffic and server errors.
- DevOps engineers incorporating log summaries into shell and CI pipelines.
- Operators in local-only, air-gapped, or privacy-sensitive environments.

## User Stories

### US-1: Stream local logs

As an SRE, I want to analyze a log file or stdin without loading the whole log into memory, so that I can inspect gigabyte-scale data on a laptop.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] With no path, the command reads stdin; with paths, it reads finite files in argument order.
- [ ] Raw requests are not retained after their aggregates are updated.
- [ ] A representative 1 GB combined log completes in under 30 seconds on documented reference hardware.
- [ ] Unreadable input exits 1 and invalid CLI configuration exits 2.

### US-2: Identify dominant clients

As an on-call engineer, I want the top 10 client IPs, so that I can spot traffic concentration or abusive sources.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] At most 10 IP rows are returned with counts and percentages of total valid requests.
- [ ] Results sort by count descending and IP bytewise ascending for ties.
- [ ] IPv4 and IPv6 values from valid combined records are supported.

### US-3: Identify failing URLs

As a service owner, I want the top 10 URLs producing 4xx/5xx responses, so that I can prioritize broken or abused routes.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Only statuses 400 through 599 contribute to the error URL ranking.
- [ ] At most 10 URL rows are returned with counts and percentages of total valid requests.
- [ ] Results sort by count descending and URL bytewise ascending for ties.

### US-4: See hourly traffic shape

As an SRE, I want a 24-hour request distribution, so that I can spot spikes and quiet periods.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Exactly 24 rows from hour `00` through `23` are returned.
- [ ] Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] Hours use the offset recorded in each log timestamp without timezone conversion.
- [ ] Empty valid input produces 0.0% for every hour.

### US-5: Measure User-Agent diversity exactly

As an operator, I want the share of unique User-Agents, so that I can estimate client diversity without exporting raw logs.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Exact distinct raw User-Agent values are counted, including `-` as a value.
- [ ] The percentage is `100 × unique_user_agent_count / total_valid_requests`, or 0.0% for zero valid requests.
- [ ] The configurable exact-cardinality ceiling is enforced before admitting an excess distinct value.
- [ ] Ceiling exhaustion emits no misleading complete report and exits with code 4.

### US-6: Read a safe terminal report

As an on-call engineer, I want a colored, readable default report, so that I can interpret results quickly in a terminal.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] A TTY receives Rich-formatted sections for all four metrics and summary counts.
- [ ] Redirected text contains no ANSI sequences unless color is explicitly forced.
- [ ] Crafted log values cannot inject Rich markup or terminal control sequences.

### US-7: Integrate structured output

As a DevOps engineer, I want JSON and CSV output, so that downstream automation does not scrape human-readable tables.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] `--json` emits schema version 1 and all canonical report fields as one valid UTF-8 JSON object.
- [ ] `--csv` emits the documented five-column RFC 4180 long-form table in canonical row order.
- [ ] JSON and CSV never contain ANSI sequences; diagnostics remain on stderr.
- [ ] `--json --csv` is rejected with exit code 2.

### US-8: Detect bad source data

As a pipeline owner, I want malformed records signaled separately from usage and I/O failures, so that automation can choose whether a partial valid-record report is acceptable.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Default mode skips malformed records atomically, produces the valid-record report, and exits 3.
- [ ] `--strict` stops on the first malformed record and exits 3.
- [ ] Diagnostics provide the source and one-based line number without echoing the full sensitive record.

### US-9: Follow a growing log

As an on-call engineer, I want to follow a growing log, so that I can refresh operational summaries during an incident.

Priority: **P1 (Should)**

Acceptance criteria:

- [ ] This behavior is deferred from MVP and requires a defined refresh/snapshot and termination contract before implementation.

### US-10: Parse configured nginx formats

As a platform engineer, I want to describe a non-default nginx access format, so that the tool supports our estate without reformatting logs.

Priority: **P1 (Should)**

Acceptance criteria:

- [ ] This behavior is deferred until the combined-format P0 grammar and fixture suite are stable.

## 5. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept zero or more finite input paths, with stdin as the no-path default and `-` allowed once |
| FR-02 | Parse nginx combined-log records and reject incomplete/invalid records atomically |
| FR-03 | Produce deterministic top-10 IP and error-URL rankings |
| FR-04 | Produce exactly 24 hourly count/percentage rows using the documented percentage formula |
| FR-05 | Produce exact unique User-Agent count/share within an explicit cardinality ceiling |
| FR-06 | Render safe colored text by default and support `--color/--no-color` |
| FR-07 | Support mutually exclusive `--json` and `--csv` contracts |
| FR-08 | Support `--strict` and the complete `0/1/2/3/4` exit-code contract |
| FR-09 | Provide `--help` and `--version` through Click |

### P1 — Should follow MVP

| ID | Requirement |
|---|---|
| FR-10 | Follow one growing regular file with an explicit snapshot/interrupt contract |
| FR-11 | Parse declared custom nginx formats through a validated configuration syntax |

### P2 — Could add

| ID | Requirement |
|---|---|
| FR-12 | Read gzip-compressed files directly |
| FR-13 | Allow top-N to be configured while keeping 10 as default |

## 6. Output and Calculation Contract

The canonical report and serialization details are normative in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. All percentages use total valid requests as their denominator and round to two decimal places using round-half-up. Empty denominators yield `0.0`, never NaN or infinity.

The hourly distribution is explicitly a percentage: `100 × hourly_request_count / total_valid_requests`. It is not an unscaled fraction. Top IP and top error URL percentages are likewise scaled percentages. The unique User-Agent share is the exact distinct count divided by total valid requests and multiplied by 100.

## 7. Exit-Code Contract

| Code | Product meaning |
|---:|---|
| `0` | Successful analysis with no malformed records |
| `1` | Input/output failure |
| `2` | CLI usage or configuration error |
| `3` | Malformed log data encountered |
| `4` | Exact unique-cardinality exhaustion |

This mapping is public compatibility surface. Code 4 is distinct and may not be omitted or remapped.

## 8. Non-Functional Requirements

| ID | Requirement | Evidence |
|---|---|---|
| NFR-01 | Process a representative 1 GB log in <30 seconds on a documented laptop | Exact-candidate benchmark with corpus identity, hardware, OS, Python, cache state, time, and RSS |
| NFR-02 | Remain streaming and avoid retaining raw request records | Design review plus memory-growth test |
| NFR-03 | Run on Python 3.11 and install through pip/pipx | Clean-environment wheel installation test |
| NFR-04 | Produce deterministic results independent of locale | Golden and locale-variation tests |
| NFR-05 | Make no network calls and persist no log-derived data | Static inspection and isolated integration test |
| NFR-06 | Keep parser/aggregate/serialization/exit modules at >=90% line coverage | Coverage gate plus boundary cases |
| NFR-07 | Never expose full malformed records in diagnostics | Golden diagnostic tests |

## 9. Scope Exclusions

Version 1 has no authentication, database, HTTP API, server, cloud service, Kubernetes, telemetry, dashboard, retained history, cross-run state, approximate cardinality, custom log format, live follow mode, direct compressed input, or configurable top-N. P1/P2 items are roadmap candidates, not hidden MVP commitments.

## 10. Dependencies and Assumptions

- Users provide nginx combined logs they are authorized to read.
- Input timestamps include nginx numeric offsets.
- Python 3.11, Click, Rich, and standard-library dataclasses are available through the package.
- The performance claim applies only to the documented reference environment and corpus; other systems may differ.
- Architecture choices are governed by `PROJECT_ARCHITECTURE.md`; delivery evidence by `IMPLEMENTATION_PLAN.md`.

## 11. Release Acceptance

Release requires every P0 acceptance criterion, all golden contracts, the complete exit-code integration suite, clean pip installation, no known Critical/High security issue, and a passing 1 GB benchmark on the documented reference laptop. The exact staged candidate must also pass the repository's current machine oracle and risk-tier adjudication.

## 12. Kill Criteria

Pause and revise the PRD rather than shipping if:

1. The complete profiled Python implementation still exceeds 30 seconds for the representative 1 GB corpus after two bounded optimization attempts.
2. Exact User-Agent tracking exhausts the agreed laptop memory ceiling on representative data at a rate that makes code 4 the common path.
3. Combined-format parsing cannot meet the golden fixtures without ambiguous or unsafe heuristics.
4. Pipeline schemas or exit behavior cannot remain deterministic across Python 3.11 environments.

Any relaxation—approximate cardinality, native extension, different language, or narrower input—requires an explicit specification and architecture decision before code changes.
