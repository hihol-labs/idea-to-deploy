# Product Requirements Document: nginx-stream-insights

## 1. Summary

`nginx-stream-insights` gives DevOps and SRE engineers a fast, local, reproducible summary of nginx access logs. It is a Python 3.11 CLI, installed with pip, that streams a file or stdin and emits colored text by default or stable JSON/CSV for pipelines.

## 2. Goals and Success Measures

- Correctly compute the promised four views from common and combined nginx logs.
- Analyze the reference 1 GB fixture in under 30 seconds on the designated laptop.
- Keep raw events stateless and avoid any database, HTTP API, server, cloud, or Kubernetes dependency.
- Provide deterministic machine output and the complete `0/1/2/3/4` exit contract.
- Ship within one weekend at $0 infrastructure/tooling cost.

## 3. Non-goals

- General-purpose log query language, dashboards, historical storage, alerts, or cross-file joins.
- Authentication, accounts, authorization, HTTP endpoints, daemon/service operation, or remote collection.
- Arbitrary nginx `log_format` parsing in MVP.
- GeoIP, bot identification, sessionization, latency percentiles, or approximate cardinality in MVP.
- Docker, cloud, or Kubernetes deployment.

## User Stories

- As a DevOps engineer, I want to pipe nginx access logs into one command so that I can identify the ten busiest client IPs without temporary files. **Priority: P0 (Must).**
- As an on-call SRE, I want the ten most frequent URLs among 4xx/5xx responses so that I can focus incident diagnosis on failing routes. **Priority: P0 (Must).**
- As a platform engineer, I want hourly request percentages and unique User-Agent share so that I can understand traffic shape and client diversity. **Priority: P0 (Must).**
- As an automation author, I want stable JSON or CSV and documented exit codes so that a pipeline can consume results safely. **Priority: P0 (Must).**
- As a terminal user, I want readable colored tables that automatically avoid ANSI codes when redirected so that the same command works interactively and in scripts. **Priority: P0 (Must).**
- As an operator, I want to select top-N and cap exact User-Agent cardinality so that output and memory risk are explicit. **Priority: P1 (Should).**
- As an operator watching an active log, I want follow mode for regular files so that the summary can include newly appended lines until I stop it. **Priority: P1 (Should).**
- As an operator handling extreme cardinality, I want an approximate distinct count so that memory remains bounded with an explicitly different accuracy contract. **Priority: P2 (Could; deferred).**

### P0 acceptance criteria

1. **Streaming input and top IPs**
   - [ ] File input and `-`/omitted stdin produce the same report for identical bytes.
   - [ ] Raw lines are processed one at a time and are not retained.
   - [ ] Top IPs are ordered by descending count and then IP text ascending, limited to 10 by default.
2. **Error URLs**
   - [ ] Only status codes 400–599 contribute to the error URL list.
   - [ ] The request target, including query string, is the URL key in MVP.
   - [ ] Ties use ascending URL text and output is limited to 10 by default.
3. **Hourly and User-Agent metrics**
   - [ ] Every report contains buckets `00` through `23` in order.
   - [ ] Each bucket percentage is exactly defined as `100 × hourly_request_count / total_valid_requests`, with `0.0` when the denominator is zero; it is never presented as an unscaled fraction.
   - [ ] Unique User-Agent share is `100 × distinct_nonempty_user_agents / total_valid_requests`, with `0.0` for empty input.
4. **Pipeline output**
   - [ ] `--json` emits exactly one valid document matching the schema in `PROJECT_ARCHITECTURE.md`.
   - [ ] `--csv` emits RFC 4180 rows headed `metric,rank,key,count,percentage`.
   - [ ] JSON and CSV represent the same report values as text mode and never contain ANSI escapes.
5. **Terminal behavior**
   - [ ] Default TTY output uses Rich styling; `--no-color` and redirected stdout do not.
   - [ ] Diagnostics go only to stderr; successful data goes only to stdout.
6. **Performance and packaging**
   - [ ] The fixed reference 1 GB combined-format fixture completes in under 30 seconds on the documented laptop.
   - [ ] A wheel installs in a clean Python 3.11 virtual environment and exposes `nginx-stream-insights`.

## 5. Functional Requirements

### P0 — Must

| ID | Requirement |
|---|---|
| FR-01 | Accept a path, `-`, or omitted input and stream UTF-8 lines without retaining raw events. |
| FR-02 | Parse nginx common and combined formats into client IP, timestamp/hour, request target, status, and optional User-Agent. |
| FR-03 | Produce exact top-10 IP and top-10 4xx/5xx URL rankings with deterministic tie-breaking. |
| FR-04 | Produce all 24 hourly counts and percentages using `100 × hourly_request_count / total_valid_requests`. |
| FR-05 | Produce exact non-empty distinct User-Agent count and its percentage of valid requests. |
| FR-06 | Render default Rich text, one JSON document, or normalized CSV; reject `--json --csv`. |
| FR-07 | Count malformed lines; return 3 only when non-empty input has no valid line. |
| FR-08 | Enforce and document exit codes 0 success, 1 input/internal I/O failure, 2 usage error, 3 parse-policy failure, and 4 unique-cardinality exhaustion. |

### P1 — Should

| ID | Requirement |
|---|---|
| FR-09 | Accept `--top` from 1 through 1000 and apply it to both rankings. |
| FR-10 | Accept a positive `--max-unique-user-agents`, default 1,000,000, and stop with code 4 before exceeding it. |
| FR-11 | Support `--follow` only with a regular-file input, continuing until interrupted. |

### P2 — Could

| ID | Requirement |
|---|---|
| FR-12 | Offer a separately named approximate cardinality mode with documented error bounds; it must never masquerade as exact output. |

## 6. Input and Parsing Rules

- Input encoding is UTF-8; undecodable or structurally invalid lines are malformed.
- MVP grammars are named `combined` and `common`; no automatic guessing is promised.
- The logged timestamp’s hour is used directly, preserving the source offset.
- Missing/empty User-Agent does not enter the distinct set but the line remains a valid request when all required common fields parse.
- An empty stream is a successful empty report. A non-empty stream with zero valid lines exits 3 without a data report.
- Mixed valid/malformed input produces a report and exit 0, with `malformed_lines` visible.

## 7. Output Contract

The canonical semantic report and serializer schemas are defined under `PROJECT_ARCHITECTURE.md` → `CLI Interface`. Percent values are 0–100 numbers. Serializers may round for presentation but must derive from integer counts, not from previously rounded values. Text labels may evolve without changing JSON/CSV field names inside a major version.

## 8. Exit-code Contract

| Code | Required meaning |
|---:|---|
| 0 | Success, including empty input |
| 1 | Input or unexpected runtime I/O failure |
| 2 | Invalid CLI usage or incompatible options |
| 3 | Non-empty input with no valid records |
| 4 | Unique-cardinality exhaustion |

## 9. Quality Attributes

- **Performance:** 1 GB under 30 seconds on the reference laptop.
- **Privacy:** no network calls, telemetry, database, or raw-line logging by default.
- **Determinism:** stable tie-breaking, 24 ordered hours, pinned machine schemas.
- **Portability:** Python 3.11 package installable through pip; behavior tested on Linux first.
- **Maintainability:** parser, aggregation, and rendering have separate modules and tests.
- **Accessibility:** color is supplemental; labels and values remain meaningful without it.

## 10. Release and Kill Criteria

Release only when all P0 acceptance criteria pass, the wheel smoke test is green, and the benchmark meets the target. Stop or re-scope if Python cannot meet the target after profiling, exact aggregation cannot stay within a documented laptop memory budget, or supported nginx grammar cannot be parsed deterministically. Do not replace failed criteria with undocumented approximations.

## 11. Traceability

Architecture and CLI semantics live in `PROJECT_ARCHITECTURE.md`; build order and verification commands live in `IMPLEMENTATION_PLAN.md`; execution prompts live in `CLAUDE_CODE_GUIDE.md`; strategy and prioritization live in `STRATEGIC_PLAN.md`.

