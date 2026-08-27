# Product Requirements Document: Nginx Stream Analyzer

## Product Summary

A pip-installable Python 3.11 CLI that incrementally analyzes one nginx access-log stream and reports operationally useful rankings and distributions. It is local, stateless, open source, and designed for DevOps/SRE incident workflows.

## Problem

Operators frequently need a fast answer from a large nginx log but do not have, want, or need a persistent observability stack. Ad hoc shell pipelines are easy to get wrong and hard to reuse. The product provides one specified parser, one pass, three output formats, and reliable process semantics.

## Goals

- Analyze a 1 GB supported nginx access log in under 30 seconds on a documented reference laptop.
- Report the required four analyses exactly and deterministically.
- Work with regular files and stdin without retaining raw requests.
- Support readable terminal output and stable JSON/CSV pipeline output.
- Fail explicitly on usage, I/O, unusable data, and unique-cardinality exhaustion.

## Non-Goals

- Authentication or authorization.
- Database, retained history, dashboard, HTTP API, or long-running server.
- Cloud service, container platform, or Kubernetes deployment.
- Live tailing, log rotation management, multiple simultaneous inputs, arbitrary custom nginx format expressions, geolocation, bot detection, or approximate analytics.

## User Stories

- As a SRE, I want to stream a large nginx log from a file or stdin so that I can investigate an incident without loading the file into memory. **Priority: P0.** Acceptance: the process reads incrementally, produces identical results for file and stdin input, and a test prevents whole-file reads.
- As an on-call engineer, I want the top 10 client IPs so that I can identify dominant traffic sources. **Priority: P0.** Acceptance: at most 10 IPs are ordered by count descending and lexicographic IP ascending on ties; counts match fixtures exactly.
- As a service owner, I want the top 10 request URLs producing 4xx/5xx responses so that I can locate failing routes. **Priority: P0.** Acceptance: only status 400–599 contributes; total, 4xx, and 5xx counts are exact; ties use target text ascending.
- As a capacity engineer, I want hourly request distribution percentages so that I can see when traffic concentrates. **Priority: P0.** Acceptance: all 24 local-log timestamp hours appear and each percentage uses `100 × hourly_request_count / total_valid_requests`; fixture percentages sum to 100 within rounding tolerance.
- As a security-minded operator, I want the share of unique User-Agents so that I can assess client diversity. **Priority: P0.** Acceptance: the exact distinct non-missing count and `100 × unique_user_agent_count / total_valid_requests` are output; exceeding the configured ceiling exits `4` without a partial report.
- As a terminal user, I want a colored readable report so that I can scan results quickly. **Priority: P0.** Acceptance: sections and labels are stable, color defaults to TTY detection, `--no-color` removes ANSI escapes, and log values cannot inject Rich markup.
- As an automation engineer, I want JSON and CSV modes so that I can consume results in pipelines. **Priority: P0.** Acceptance: both formats match the schemas in `PROJECT_ARCHITECTURE.md`, contain no ANSI codes, and diagnostics never contaminate stdout.
- As a script author, I want a complete exit-code contract so that automation can distinguish failures. **Priority: P0.** Acceptance: integration tests cover `0/1/2/3/4`, where `4` is unique-cardinality exhaustion.
- As a power user, I want configurable ranking length and a cardinality ceiling so that I can trade report depth against resources. **Priority: P1.** Acceptance: documented numeric ranges are validated as CLI usage and invalid values exit `2`.
- As an operator with archived logs, I want gzip input so that I can avoid a separate decompression command. **Priority: P2.** Acceptance: deferred until all P0 acceptance and performance targets pass.

## Functional Requirements

### P0 — Must

| ID | Requirement | Acceptance evidence |
|---|---|---|
| FR-01 | Accept one path, `-`, or omitted stdin input | Click integration tests for each form |
| FR-02 | Parse supported nginx common and combined lines | Valid/invalid fixture matrix including timezone and escaped fields |
| FR-03 | Count total, valid, and malformed lines | Exact fixture assertions |
| FR-04 | Produce deterministic top client IP ranking | Golden JSON and tie test |
| FR-05 | Produce deterministic 4xx/5xx URL ranking | Mixed-status golden test |
| FR-06 | Produce 24 hourly counts and percentages | Formula and zero-hour tests |
| FR-07 | Produce exact unique User-Agent count/share | Missing-agent and duplicate-agent tests |
| FR-08 | Render default Rich terminal report | TTY/non-TTY snapshots |
| FR-09 | Render schema-versioned JSON | JSON Schema or structural assertions |
| FR-10 | Render normalized CSV | Header, row-order, quoting, and round-trip tests |
| FR-11 | Apply exit codes `0/1/2/3/4` | Subprocess integration matrix |
| FR-12 | Stop at the unique-agent ceiling | Boundary and boundary+1 tests; no stdout on failure |
| FR-13 | Install with pip and expose console/module commands | Clean virtual-environment smoke test |

### P1 — Should

| ID | Requirement | Acceptance evidence |
|---|---|---|
| FR-14 | `--top` supports 1–1000, default 10 | Boundary and default tests |
| FR-15 | `--max-unique-user-agents` supports positive integers | CLI validation tests |
| FR-16 | `--color/--no-color` overrides terminal detection | ANSI snapshot tests |

### P2 — Could

| ID | Requirement | Acceptance evidence |
|---|---|---|
| FR-17 | Read gzip input without changing output semantics | Compressed/uncompressed equivalence test |

## Metric Semantics

- `total_valid_requests` is the denominator for both percentage metrics and includes valid common-format records without User-Agent data.
- Top IPs count every valid request by parsed client IP token.
- Top error URLs count only statuses 400–599. Statuses 400–499 increment client-error count; 500–599 increment server-error count.
- The target is the request-target token as logged; no host resolution, percent-decoding, query stripping, or path normalization occurs.
- Hour is the `00`–`23` hour present in the timestamp's logged numeric offset. The calculation is exactly `100 × hourly_request_count / total_valid_requests`.
- Unique User-Agent share is the number of distinct present User-Agent strings divided by total valid requests and scaled by 100. Missing combined/common values are separately counted.
- Rankings are count descending, then key ascending. Serialized percentages round to six decimal places; counts remain integers.

## Input and Error Requirements

Malformed lines are skipped and counted. If one or more valid records exist, a report succeeds and discloses malformed count. If no valid record exists, no report is written and the command exits `3`. Missing or unreadable input exits `1`; invalid CLI usage exits `2`; exceeding exact User-Agent cardinality exits `4`. All failure diagnostics use stderr and all nonzero exits suppress partial stdout.

## Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-01 | Performance | 1 GB under 30 seconds on recorded reference laptop |
| NFR-02 | Streaming | One pass; no raw-line/request collection proportional to line count |
| NFR-03 | Compatibility | CPython 3.11; pip wheel and source distribution |
| NFR-04 | Privacy | No network calls, telemetry, persistence, or content upload |
| NFR-05 | Determinism | Same input/options/version produce byte-stable JSON and CSV |
| NFR-06 | Safety | Log-derived data is never executed and cannot inject terminal markup |
| NFR-07 | Quality | At least 90% coverage on parser/aggregation/renderers and all P0 acceptance tests pass |

## Output Contract

The authoritative commands, options, input/output fields, and exit definitions are under `PROJECT_ARCHITECTURE.md` -> `CLI Interface`. Text wording may receive non-semantic polish; JSON schema version 1 and the CSV header/order are compatibility contracts.

## Release Acceptance

- All P0 stories and requirements pass on the exact release candidate.
- Build artifacts install in a clean Python 3.11 virtual environment.
- File and stdin golden results match for terminal-without-color, JSON, and CSV.
- The reference 1 GB benchmark is correct and under 30 seconds, with peak RSS recorded.
- Boundary tests demonstrate exit `4` for unique-cardinality exhaustion.
- Documentation contains no unsupported service, database, auth, cloud, or Kubernetes behavior.

## Kill Criteria

Pause release and re-scope if any condition holds after one profiling/fix iteration:

- Correct 1 GB analysis remains at or above 30 seconds on the reference laptop.
- Exact required metrics require memory proportional to total request count rather than controlled unique keys.
- Common/combined parsing cannot reach 99.9% validity on the approved valid fixture corpus.
- JSON/CSV cannot remain stable without weakening metric semantics.
- The one-weekend or $0 constraint would require dropping a P0 requirement.

## Dependencies

The architecture and schemas are defined in `PROJECT_ARCHITECTURE.md`; implementation sequence and verification commands are in `IMPLEMENTATION_PLAN.md`; agent execution prompts are in `CLAUDE_CODE_GUIDE.md`.
