# Product Requirements Document: nginx-stream-report

## Product Summary

`nginx-stream-report` turns a local nginx combined access log into a concise operational report. It serves DevOps/SRE engineers who need answers during incident triage without deploying or operating an analytics stack.

## Goals and Success Criteria

- Produce all four required metric groups in one sequential pass.
- Process the documented 1 GB fixture in under 30 seconds on a reference laptop.
- Support readable text and stable JSON/CSV pipeline contracts.
- Install through pip on Python 3.11 with no external service.
- Keep successful results deterministic for identical inputs and options.

## Non-Goals

Authentication, a database, an HTTP API, a server, cloud resources, Kubernetes, live dashboards, historical storage, geo-IP enrichment, bot detection, and arbitrary nginx format inference are outside the MVP.

## User Stories

- As a DevOps engineer, I want to see the top client IPs so that I can identify dominant or suspicious request sources. **Priority: P0.**
- As an on-call SRE, I want to see the URLs producing the most 4xx/5xx responses so that I can locate failing routes quickly. **Priority: P0.**
- As a capacity engineer, I want an hourly percentage distribution so that I can understand when traffic concentrates. **Priority: P0.**
- As a platform engineer, I want the share of unique User-Agents so that I can estimate client diversity. **Priority: P0.**
- As an automation author, I want JSON and CSV output so that I can consume reports safely in pipelines. **Priority: P0.**
- As an operator, I want malformed lines counted without losing valid results so that imperfect logs remain useful. **Priority: P0.**
- As a power user, I want to choose top-N and normalize timezones so that I can adapt reports to deeper analysis. **Priority: P1.**
- As an administrator with custom nginx formats, I want selectable format definitions so that I can reuse the tool. **Priority: P2.**

### P0 Acceptance Criteria

1. Given a fixture with deterministic counts, text, JSON, and CSV all report the same top-10 IP ordering by count descending and key ascending on ties.
2. Only response statuses 400–599 contribute to the error-URL top 10; 1xx–3xx do not.
3. Hourly request distribution contains all 24 buckets and calculates each percentage with `100 × hourly_request_count / total_valid_requests` using only valid records.
4. Unique User-Agent share equals 100 times the exact distinct User-Agent count divided by valid requests; exceeding the configured ceiling emits no partial report and exits 4.
5. Default text uses color only on a TTY. `--json` and `--csv` are mutually exclusive and emit no ANSI escapes.
6. File input and stdin produce byte-for-byte equivalent structured reports for the same content.
7. Malformed lines are skipped and counted when at least one valid record exists. Non-empty, wholly invalid input exits 3; empty input succeeds with an empty report.
8. The documented 1 GB fixture finishes in under 30 seconds on the documented reference laptop.

## Functional Requirements

### P0 — Must

| ID | Requirement |
|---|---|
| FR-01 | Read a named local file, `-`, or omitted stdin sequentially without modifying it. |
| FR-02 | Parse the supported nginx combined-log grammar into only the fields required for metrics. |
| FR-03 | Report top-10 IPs and top-10 request targets for statuses 400–599. |
| FR-04 | Report 24 hourly counts and percentages based on the offset in each record. |
| FR-05 | Report exact distinct User-Agent count and share with a configurable safety ceiling. |
| FR-06 | Render colored terminal text by default and stable `--json`/`--csv` formats. |
| FR-07 | Count malformed lines, keep valid results, and honor the complete `0/1/2/3/4` exit contract. |
| FR-08 | Produce deterministic ordering and two-decimal percentages. |

### P1 — Should

| ID | Requirement |
|---|---|
| FR-09 | Allow `--top` to replace the default 10 with a positive integer. |
| FR-10 | Allow explicit output timezone normalization without changing the default log-offset semantics. |

### P2 — Could

| ID | Requirement |
|---|---|
| FR-11 | Support named additional nginx log grammars through explicit, tested selection. |
| FR-12 | Offer approximate bounded-memory heavy hitters only behind an explicit mode and clearly label approximation. |

## Quality Requirements

| Attribute | Requirement |
|---|---|
| Performance | 1 GB under 30 seconds on the documented reference laptop |
| Memory | Streaming records; peak RSS target under 250 MB on bounded-cardinality fixture |
| Compatibility | CPython 3.11; Linux and macOS first, no OS-specific shell dependency |
| Reliability | Stable exit codes; no partial structured output on fatal failure |
| Privacy | No network activity or persistence; input contents remain local |
| Testability | Unit fixtures for grammar edges and CLI integration for every mode/code |

## Interface Contract

The canonical commands, options, output schemas, and exit codes live under `PROJECT_ARCHITECTURE.md` → `CLI Interface`. That section is normative; implementation and tests must not redefine it.

## Dependencies and Assumptions

- Input follows the documented nginx combined format and timestamps include numeric offsets.
- Python 3.11, Click, and Rich are available through pip installation.
- The performance target assumes local SSD input and a documented laptop; stdin producer speed is outside the tool's control.
- Exact IP and URL counters fit the target laptop for the reference corpus; high-cardinality stress is measured separately.

## Release and Kill Criteria

Release only when all P0 acceptance criteria pass in a clean Python 3.11 environment and the wheel installs locally. Stop or rescope if the reference benchmark cannot meet 30 seconds after profiling, if successful exact cardinality cannot be bounded safely, or if real fixtures show that the supported grammar yields unreliable metrics. Do not expand scope to a database or server to rescue the MVP.

