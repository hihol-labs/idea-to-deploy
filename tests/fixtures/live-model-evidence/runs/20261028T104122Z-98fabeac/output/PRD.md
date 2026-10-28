# Product Requirements Document: nginx-stream-insights

## Product Summary

A local Python 3.11 CLI helps DevOps/SRE engineers turn nginx access-log streams into four actionable summaries without installing or operating a server. The default is a colored terminal report; JSON and CSV are stable pipeline interfaces.

## Goals and Success Measures

- Correctly compute top-10 IPs, top-10 URLs with 4xx/5xx responses, hourly request percentages, and unique User-Agent share.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Remain stateless, local, pip-installable, and predictable under malformed or high-cardinality input.
- Preserve the CLI and exit-code contracts in `PROJECT_ARCHITECTURE.md` with automated tests.

## User Stories

- As a SRE, I want to stream a local nginx log and see the top client IPs so that I can identify abusive or anomalous traffic quickly. **Priority: P0.**
- As an on-call engineer, I want the top URLs producing 4xx/5xx responses so that I can focus incident investigation on failing routes. **Priority: P0.**
- As a platform engineer, I want hourly request distribution as percentages so that I can recognize traffic spikes without manual calculations. **Priority: P0.**
- As a service owner, I want the share of unique User-Agents so that I can assess client diversity and possible bot activity. **Priority: P0.**
- As an automation engineer, I want JSON and CSV output so that I can feed results into pipelines without scraping terminal text. **Priority: P0.**
- As an operator, I want malformed-line counts and strict mode so that I know whether input quality affected the report. **Priority: P1.**

### P0 Acceptance Criteria

1. Given a committed fixture with more than ten distinct IPs, output contains exactly ten ranked IP entries, ordered by count descending and IP ascending on ties.
2. Only status codes 400–599 contribute to error-URL ranking; URLs are ranked by count descending and URL ascending on ties.
3. Each hour uses the literal formula `100 × hourly_request_count / total_valid_requests`; the 24 percentages sum to approximately 100% when valid requests exist and are all 0.0 otherwise.
4. Unique User-Agent share equals `100 × unique_user_agents / total_valid_requests`; missing/empty User-Agents do not add a distinct value.
5. Default terminal output contains all four summaries and uses color only when enabled; `--json` parses as one JSON document and `--csv` parses with the documented header.
6. File input and stdin produce identical reports for identical bytes.
7. A documented representative 1 GB benchmark completes in under 30 seconds on the reference laptop.
8. Each exit path maps to the complete `0/1/2/3/4` contract, including code 4 for unique-cardinality exhaustion.

## Functional Requirements

### P0 — Must

- FR-1: Accept one file path, `-`, or omitted input for stdin.
- FR-2: Parse documented nginx `combined` and `common` formats incrementally.
- FR-3: Count valid and invalid lines and all required metrics in one pass.
- FR-4: Emit top 10 IPs and top 10 error URLs with deterministic tie-breaking.
- FR-5: Emit 24 hourly counts and percentage shares.
- FR-6: Emit the exact unique User-Agent count and percentage share within the configured safety bound.
- FR-7: Provide colored terminal, JSON, and CSV renderers with no ANSI escapes in machine output.
- FR-8: Enforce mutual exclusion of `--json` and `--csv` and the exit-code contract.
- FR-9: Stop with code 4 before reporting inexact results when a cardinality ceiling is reached.

### P1 — Should

- FR-10: Support `--errors strict|skip` and show invalid-line accounting.
- FR-11: Support explicit input encoding and color overrides.
- FR-12: Provide an opt-in reproducible 1 GB benchmark command and record environment metadata.

### P2 — Could

- FR-13: Read gzip-compressed logs by explicit option or suffix.
- FR-14: Compile user-supplied nginx `log_format` patterns.

## Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | Python 3.11, Click, Rich, and dataclasses; installable through pip |
| NFR-2 | Single-process streaming; no database, server, HTTP API, auth, cloud, or Kubernetes |
| NFR-3 | Representative 1 GB input in <30 s on the documented reference laptop |
| NFR-4 | Memory scales with unique cardinality and stops safely at a configurable ceiling |
| NFR-5 | Stable JSON/CSV schema version and deterministic ordering |
| NFR-6 | No log contents or telemetry leave the machine |

## Input and Edge Cases

- Empty input succeeds with empty rankings and zero percentages.
- Invalid lines are counted and skipped by default; strict mode stops on the first one with code 3.
- Query strings remain part of the URL key in MVP; this behavior is documented and tested.
- The hour is taken from the timestamp as represented in the log entry; no host-timezone conversion occurs.
- IPv4 and IPv6 addresses are treated as opaque parsed client strings.
- A line longer than available memory is an operating-system/resource failure outside the normal contract; typical input remains line-delimited.

## Out of Scope

Authentication, databases, history, dashboards, HTTP APIs, servers, agents, tail-follow mode, cloud services, Kubernetes, geo-IP enrichment, bot classification, approximate cardinality, arbitrary log-format DSLs in P0, and automatic input mutation are excluded.

## Dependencies and Assumptions

- Input matches a documented supported nginx common/combined format.
- The reference performance environment has local SSD storage and CPython 3.11.
- Exact counts are required within the cardinality ceiling; approximation is not silently substituted.
- `PROJECT_ARCHITECTURE.md` is authoritative for CLI schemas and exit semantics.

## Kill Criteria

- The approved stack cannot reach the 1 GB/30 s target after profiling and one focused optimization pass.
- Exact aggregation exceeds safe laptop memory for representative logs at a useful ceiling.
- Parser compatibility cannot be stated and tested without expanding the weekend scope.
- Machine-readable outputs cannot remain backward-compatible under a versioned schema.

