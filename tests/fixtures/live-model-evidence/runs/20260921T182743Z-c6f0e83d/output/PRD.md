# Product Requirements Document: nginx-stream-report

## Product Summary

`nginx-stream-report` is a local Python 3.11 CLI that streams nginx common/combined access logs and reports the top 10 client IPs, top 10 URLs by 4xx/5xx response count, hourly request distribution, and the share represented by unique User-Agent values. It serves DevOps and SRE incident triage without a database, server, HTTP API, authentication, cloud account, or Kubernetes.

## Problem Statement

Operators frequently need a fast answer from a large local access log but must choose between brittle one-off shell pipelines and analytics systems whose setup exceeds the incident task. The product must provide a small, predictable command that analyzes a 1 GB representative log in under 30 seconds on a documented laptop and works equally well for a terminal user or a shell pipeline.

## Goals

- Produce all four approved metrics in one streaming pass.
- Default to clear colored terminal text and support stable `--json` and `--csv` output.
- Remain installable through pip on Python 3.11.
- Keep cash cost at $0 and implementation feasible in one weekend.
- Fail predictably for usage, I/O, invalid data, and unsafe unique cardinality.

## Non-Goals

- Authentication, authorization, users, or secrets management.
- Database, persistent history, cross-run comparison, indexing, or search.
- HTTP API, web interface, daemon, hosted service, or network access.
- Cloud, container, Docker Compose, or Kubernetes deployment.
- Arbitrary nginx `log_format`, compressed inputs, multiple concurrent inputs, geo-IP, bots, sessions, or request latency analytics.
- Replacement for GoAccess, Elastic/Kibana, AWStats, or a general log-processing platform.

## User Stories

- As a on-call SRE, I want to stream a large nginx access log and see the top 10 client IPs so that I can identify concentrated or suspicious traffic quickly. **Priority: P0.** Acceptance: a supported fixture returns at most 10 rows ordered by count descending and IP ascending for ties; file and stdin results are identical.
- As a service owner, I want to see the top 10 request URLs that produced 4xx or 5xx statuses so that I can focus incident investigation on failing routes. **Priority: P0.** Acceptance: only statuses 400–599 contribute; results are ordered deterministically; query preservation follows the selected option.
- As a DevOps engineer, I want each hour's request percentage calculated as `100 × hourly_request_count / total_valid_requests` so that I can see when traffic was concentrated without doing more arithmetic. **Priority: P0.** Acceptance: all 24 hours appear, counts sum to total valid requests, and percentages sum to 100% within documented rounding tolerance when the total is nonzero.
- As a capacity-conscious SRE, I want the exact unique User-Agent share to stop at a configured cardinality ceiling so that hostile data cannot consume unbounded memory. **Priority: P0.** Acceptance: missing User-Agents do not enter the unique numerator; exceeding the ceiling emits no successful report and exits with code 4.
- As a pipeline author, I want JSON and CSV output with no terminal styling so that downstream tools can parse reports reliably. **Priority: P0.** Acceptance: JSON parses as one object, CSV parses with the documented header, and neither contains ANSI escape sequences.
- As a live operator, I want to follow a growing regular log file so that I can observe appended traffic without restarting the command. **Priority: P1.** Acceptance: `--follow` rejects stdin as a usage error and processes complete appended lines without duplicating earlier lines.
- As a power user, I want configurable top-N output so that I can widen or narrow a report. **Priority: P2.** Acceptance: deferred until after MVP; top 10 remains the fixed contract in the first release.

## Functional Requirements

### P0 — Must Have

#### FR-1: Stream ingestion and parsing

- Accept one optional `INPUT` path; omitted input or `-` means stdin.
- Parse nginx common and combined format lines incrementally as UTF-8.
- Ignore empty lines. In default mode, skip and count malformed non-empty lines. With `--strict`, stop at the first malformed line.
- Never retain the complete file or a list of parsed requests.

#### FR-2: Top client IPs

- Count every valid request by parsed client IP.
- Return no more than 10 IPs, ordered by count descending and IP text ascending for equal counts.

#### FR-3: Top error URLs

- Count request targets only where HTTP status is from 400 through 599 inclusive.
- Return no more than 10 targets, ordered by count descending and URL ascending for equal counts.
- Keep query strings by default; `--strip-query` removes them before aggregation.

#### FR-4: Hourly request distribution

- Use the hour and numeric offset encoded in each valid log timestamp; do not silently convert to the machine timezone.
- Emit buckets 00 through 23, including zeros.
- Define every bucket as the percentage `100 × hourly_request_count / total_valid_requests`.
- Render percentages with consistent decimal precision while retaining integer counts in structured output.

#### FR-5: Unique User-Agent share

- Count exact distinct, non-null User-Agent strings in combined-format records.
- Define share percentage as `100 × unique_non_null_user_agent_count / total_valid_requests`.
- Treat `-` or absent User-Agent as missing: it remains in the denominator but not the unique numerator.
- Default `--max-unique-user-agents` to 1,000,000 and stop with code 4 before inserting a value beyond the limit.

#### FR-6: Default terminal output

- Print a summary and four Rich tables.
- Auto-enable color only when stdout is a terminal; honor explicit `--color` and `--no-color` for text.
- Escape untrusted content as text rather than Rich markup.

#### FR-7: Pipeline output

- `--json` emits exactly one UTF-8 object with `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`.
- `--csv` emits `section,rank,key,count,percentage` followed by normalized rows.
- `--json` and `--csv` are mutually exclusive and never emit ANSI escapes.
- Report data uses stdout; diagnostics use stderr.

#### FR-8: Complete process status

- Exit `0` when a report is emitted successfully, including non-strict runs that skipped malformed lines.
- Exit `1` for input/output failures.
- Exit `2` for Click usage errors and invalid option combinations/values.
- Exit `3` for a strict malformed line or an input with zero valid requests.
- Exit `4` for unique-cardinality exhaustion.
- Do not remap or omit any code in the `0/1/2/3/4` contract.

### P1 — Should Have

#### FR-9: Follow mode

- `--follow` accepts only a regular path, waits for appended data, and buffers an incomplete final line.
- A normal interrupt after at least one completed reporting interval does not print a traceback.
- Follow-mode report cadence and final interrupt semantics must be locked by tests before release.

### P2 — Could Have

- Configurable top-N with bounded validation.
- An explicitly labeled approximate User-Agent cardinality mode.
- Additional supported nginx formats selected by named parser profiles.

## Output Contract

The normative command, options, JSON shape, CSV header, input rules, and exit codes live under `PROJECT_ARCHITECTURE.md` → `## CLI Interface`. User-facing help and tests must match it. Any incompatible JSON or CSV change requires a PRD and architecture update before code changes.

## Quality Attributes

| Attribute | Requirement | Evidence |
|---|---|---|
| Performance | Representative 1 GB input completes in <30 s | Timed run with dataset and laptop specifications |
| Memory | Streaming records; cardinality cap; target peak RSS <512 MiB | `/usr/bin/time -v` benchmark |
| Correctness | Supported valid fixtures parse 100%; deterministic rankings | Unit and golden-output tests |
| Testability | Core package coverage >=90% | Coverage report |
| Portability | Python 3.11; no platform-specific service dependency | Clean virtual-environment install/smoke test |
| Privacy | No network, telemetry, persistence, or secret ingestion | Static inspection and network-free tests |
| Pipeline safety | Structured stdout contains data only and no ANSI | JSON/CSV parser tests |

## Acceptance Scenarios

1. Given the combined fixture via a path and stdin, the JSON objects are identical and contain all four metric groups.
2. Given statuses 399, 400, 499, 500, 599, and 600, only the four values from 400 through 599 contribute to error URLs.
3. Given valid requests in two hours, the output contains 24 buckets and uses `100 × hourly_request_count / total_valid_requests` for every percentage.
4. Given repeated, missing, and distinct User-Agents below the ceiling, the exact unique count and share match hand calculation.
5. Given one more distinct User-Agent than the configured ceiling, stdout has no successful report, stderr names the limit, and status is 4.
6. Given malformed lines in default mode, valid lines still yield status 0 and the malformed count is reported; with `--strict`, the first malformed line yields status 3.
7. Given unreadable input, invalid flags, and valid input, statuses are 1, 2, and 0 respectively.
8. Given JSON and CSV modes, standard parsers accept the output and find no ANSI escapes.

## Dependencies and Assumptions

- CPython 3.11, Click, Rich, standard-library dataclasses/csv/json/collections/heapq.
- The 30-second target assumes local storage and a representative supported-format file; machine and cache state are reported with results.
- Exact User-Agent cardinality intentionally trades bounded memory for a visible code-4 failure at the configured ceiling.
- The invoking OS account supplies all required file permissions.

## Product Risks and Mitigations

- Format ambiguity is constrained by declaring common/combined support and exposing malformed counts.
- Performance uncertainty is resolved with a generated 1 GB benchmark before release.
- Unbounded high-cardinality keys are addressed explicitly for User-Agents; IP and URL maps are measured and documented, with future bounded heavy-hitter algorithms considered only if evidence requires them.
- Spreadsheet formula interpretation is documented for CSV consumers; output remains faithful data and does not silently mutate URLs/User-Agents.

## Kill Criteria

- The representative 1 GB dataset cannot be processed in under 30 seconds on the reference laptop after profiling and reasonable pure-Python optimization.
- Exact cardinality cannot be bounded with clear code-4 behavior at acceptable memory.
- Real supported-format fixtures show nondeterministic or materially incorrect parsing.
- Meeting the target would require a database, server, cloud service, or paid dependency, contradicting the core product premise.

If a kill criterion is reached, return to architecture and scope review. Do not silently weaken acceptance criteria.

