# Product Requirements Document: nginx-stream-report

## Product Summary

`nginx-stream-report` is a local, pip-installable Python 3.11 CLI that streams one nginx combined access log and reports top client IPs, error-heavy URLs, hourly traffic percentages, and the share of unique User-Agents. It serves DevOps/SRE incident investigation and shell automation without a database, server, network dependency, or retained state.

## Problem Statement

Engineers often need a fast answer from a large nginx log before a full observability platform is available or justified. Existing platforms require services and storage; ad hoc shell pipelines are brittle and repeat parsing. The product must return the four approved metrics in one pass, remain useful on a 1 GB file, and expose stable JSON/CSV output for pipelines.

## Goals

- Analyze supported logs locally in a single streaming pass.
- Complete a 1 GB reference workload in under 30 seconds on a documented laptop.
- Produce exact, deterministic metrics and honest malformed-input diagnostics.
- Offer colored terminal text by default and stable JSON/CSV alternatives.
- Fail predictably through the complete `0/1/2/3/4` exit-code contract.

## Non-Goals

Authentication, database storage, HTTP APIs, servers, cloud services, Kubernetes, live dashboards, log retention, tail-following, arbitrary nginx formats, cross-file history, and approximate metrics are outside the MVP.

## User Stories

- As a DevOps engineer, I want to see the top 10 client IPs so that I can identify concentrated traffic or suspicious callers quickly.
  - Priority: P0
  - Acceptance criteria:
    - [ ] Every valid request increments its exact remote-address count once.
    - [ ] At most ten entries are ordered by descending count and then ascending address for ties.
- As an on-call SRE, I want to see the top 10 URLs producing 4xx/5xx responses so that I can focus incident response on failing routes.
  - Priority: P0
  - Acceptance criteria:
    - [ ] Only statuses 400–599 contribute to this ranking.
    - [ ] The exact request target is counted, with deterministic ordering and at most ten entries.
- As a capacity engineer, I want hourly request distribution as percentages so that I can recognize traffic concentration across the day.
  - Priority: P0
  - Acceptance criteria:
    - [ ] All 24 hour buckets are emitted, including zero-count hours.
    - [ ] Each percentage uses `100 × hourly_request_count / total_valid_requests` and is not stored as an unscaled fraction.
- As a privacy-conscious platform engineer, I want the exact share of unique User-Agents with a bounded cardinality policy so that the tool never silently substitutes an estimate.
  - Priority: P0
  - Acceptance criteria:
    - [ ] The percentage is `100 × distinct_nonempty_user_agent_count / total_valid_requests`.
    - [ ] Exceeding the configured exact-cardinality ceiling emits no partial report and exits 4.
- As a terminal user, I want readable colored output by default so that I can scan results during an incident.
  - Priority: P0
  - Acceptance criteria:
    - [ ] Four labeled sections and processing totals are readable in a TTY.
    - [ ] Color is absent with `--no-color` and when stdout is not a TTY.
- As an automation author, I want JSON and CSV formats so that downstream tools can consume the same report without scraping terminal text.
  - Priority: P0
  - Acceptance criteria:
    - [ ] `--json` emits one schema-versioned object and `--csv` emits normalized RFC 4180 rows.
    - [ ] Machine modes contain no ANSI escapes and send diagnostics only to stderr.
- As an operator with compressed archives, I want direct gzip input so that I can avoid a separate decompression command.
  - Priority: P1
- As a power user, I want configurable ranking sizes so that I can inspect more or fewer than ten entries.
  - Priority: P2

## Functional Requirements

### P0 — Must Ship

| ID | Requirement |
|---|---|
| FR-001 | Accept one file path, `-`, or omitted input for stdin and process it line by line. |
| FR-002 | Parse supported nginx combined-log records into remote address, timestamp hour, request target, status, and User-Agent. |
| FR-003 | Skip malformed non-empty lines by default, count them, and summarize diagnostics on stderr. |
| FR-004 | With `--strict`, stop on the first malformed non-empty line and exit 3. |
| FR-005 | Emit top 10 IPs from all valid requests with deterministic tie handling. |
| FR-006 | Emit top 10 request targets from valid requests whose status is 400–599. |
| FR-007 | Emit all 24 hourly buckets with percentage `100 × hourly_request_count / total_valid_requests`. |
| FR-008 | Emit unique User-Agent share as a percentage using exact, case-sensitive nonempty values. |
| FR-009 | Enforce `--max-unique-user-agents`, default 1,000,000; exit 4 before rendering when exceeded. |
| FR-010 | Render Rich colored terminal output by default, respecting `--no-color` and non-TTY output. |
| FR-011 | Support mutually exclusive `--json` and `--csv` formats with stable schemas and no color. |
| FR-012 | Support `--help`, `--version`, and the exit-code contract in `PROJECT_ARCHITECTURE.md`. |

### P1 — Should Ship Later

| ID | Requirement |
|---|---|
| FR-101 | Accept gzip-compressed file paths while preserving the same parsing and reporting semantics. |

### P2 — Could Ship Later

| ID | Requirement |
|---|---|
| FR-201 | Allow an explicit top-N value while retaining 10 as the default. |
| FR-202 | Allow a documented custom nginx format grammar without heuristically guessing formats. |

## Input Contract

The MVP supports UTF-8 nginx combined access-log lines. Each valid line provides remote address, timezone-bearing timestamp, quoted request, three-digit status, byte count, quoted referrer, and quoted User-Agent. The target is taken from the request field. Empty physical lines are ignored. An empty file, a file containing no valid requests, undecodable text, or a malformed line in strict mode is a parse/data failure.

## Report Contract

One invocation yields one report. Rankings use descending count and lexicographic key ties. JSON uses schema version 1. CSV uses `section,key,count,percentage,rank`. Percentages retain full internal precision and render consistently; JSON numeric values are not localized. stdout contains only output data and stderr contains diagnostics.

## Exit-Code Contract

| Code | Meaning |
|---:|---|
| `0` | Successful complete report |
| `1` | Input open/read/I/O failure |
| `2` | Invalid CLI invocation or option combination |
| `3` | Parse/data failure, including no valid requests |
| `4` | Exact unique User-Agent cardinality ceiling exhausted; no report emitted |

## Non-Functional Requirements

| ID | Requirement | Evidence |
|---|---|---|
| NFR-001 | Process a deterministic 1 GB supported log in under 30 seconds on the named reference laptop. | Recorded benchmark command, hardware/Python metadata, wall time |
| NFR-002 | Never read the entire input or retain parsed requests. | Code review plus peak-memory benchmark |
| NFR-003 | Keep peak memory below 256 MiB for the representative benchmark within configured cardinality. | Peak RSS record |
| NFR-004 | Produce identical metric semantics through all three renderers. | Shared golden fixture tests |
| NFR-005 | Support Python 3.11 and installation from a built wheel. | Clean-environment packaging test |
| NFR-006 | Make no network calls and create no persistent application data. | Static inspection and isolated integration test |
| NFR-007 | Do not expose full sensitive input lines in normal errors. | Error-message tests |

## Release Acceptance

- [ ] All P0 user-story criteria and requirements pass automated tests.
- [ ] Golden fixtures cover valid, malformed, tied, empty-UA, IPv4, and IPv6 cases.
- [ ] CLI integration tests exercise exit codes `0/1/2/3/4` and stdout/stderr separation.
- [ ] JSON and CSV outputs parse with standard-library readers and contain no ANSI escapes.
- [ ] The clean-wheel installation test passes on Python 3.11.
- [ ] The documented 1 GB benchmark meets time and memory targets.
- [ ] No authentication, database, API, server, cloud, or Kubernetes component exists.

## Kill Criteria

Pause release and reassess if any of these remain true after the weekend timebox:

- The reference 1 GB workload cannot complete under 30 seconds on Python 3.11.
- Golden-fixture output is not exact across terminal, JSON, and CSV modes.
- User-Agent cardinality exhaustion can cause uncontrolled memory growth or a partial/misleading report.
- The MVP requires a database, service, cloud resource, or non-$0 infrastructure to work.

## Dependencies

The architecture and CLI contract are authoritative in `PROJECT_ARCHITECTURE.md`. Delivery order and verification commands are in `IMPLEMENTATION_PLAN.md`; implementation-session prompts are in `CLAUDE_CODE_GUIDE.md`.
