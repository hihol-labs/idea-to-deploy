# Product Requirements Document: Nginx Stream Insights

## 1. Summary

Nginx Stream Insights is a Python 3.11 CLI that streams a local nginx combined access log and emits four operational views: top client IPs, top URLs producing 4xx/5xx responses, hourly request distribution, and unique User-Agent share. Default output is colored terminal text; JSON and CSV support reliable pipelines.

The product is open source, costs $0 to operate, and is deliverable in one weekend. [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) is the technical source of truth; this PRD is the behavioral source of truth.

## 2. Problem and Outcome

During incident response, engineers often need a compact summary before deciding whether a full observability stack is warranted. Existing stacks require setup or persistence, and ad hoc shell pipelines are fragile. The desired outcome is an accurate, reproducible report from a path or stdin in one command, with pipeline-safe schemas and bounded failure behavior.

## 3. Goals and Non-Goals

### Goals

- Process nginx combined access logs in a single streaming pass.
- Report the required four metrics accurately and deterministically.
- Process a representative 1 GB file in under 30 seconds on a named laptop.
- Support terminal users and JSON/CSV pipeline consumers.
- Remain installable with pip and safe under excessive unique cardinality.

### Non-goals

- Authentication, accounts, authorization, or multi-tenancy.
- Database, saved history, indexing, or cross-run comparisons.
- HTTP API, server, web UI, cloud service, Docker deployment, or Kubernetes.
- Arbitrary nginx formats in the P0 release.
- GeoIP, bot detection, live dashboard refresh, or log mutation.

## User Stories

### US-1 — Analyze a local incident log

As an on-call SRE, I want to analyze an nginx access-log file with one command so that I can see the dominant clients and traffic shape quickly.

Priority: **P0**

Acceptance criteria:

- [ ] A readable UTF-8 combined-log path produces all four metric sections and exits `0`.
- [ ] The default top-IP list contains at most 10 rows, ordered by count descending and IP ascending for ties.
- [ ] A 1 GB representative log completes in under 30 seconds on the documented reference laptop.

### US-2 — Identify error-heavy URLs

As a DevOps engineer, I want URLs ranked by 4xx/5xx response count so that I can focus investigation on failing request targets.

Priority: **P0**

Acceptance criteria:

- [ ] Only statuses 400 through 599 inclusive contribute to error URL counts.
- [ ] The default list contains at most 10 URLs, ordered by count descending and URL ascending for ties.
- [ ] The request target is not percent-decoded, so distinct log values remain auditable.

### US-3 — Understand hourly load shape

As an SRE, I want the request share for every hour so that I can locate periods of concentrated traffic.

Priority: **P0**

Acceptance criteria:

- [ ] Output contains all 24 log-local hours from `00` through `23`.
- [ ] Each percentage uses exactly `100 × hourly_request_count / total_valid_requests`.
- [ ] For one or more valid requests, percentages sum to 100% within documented floating-point/rounding tolerance.

### US-4 — Measure User-Agent diversity

As a platform engineer, I want the share of unique User-Agents so that I can quickly judge client diversity or automation patterns.

Priority: **P0**

Acceptance criteria:

- [ ] Distinct User-Agents are exact, case-sensitive parsed strings, including the `-` marker.
- [ ] Share is `100 × distinct_user_agent_count / total_valid_requests`.
- [ ] Output includes both distinct count and percentage.

### US-5 — Use analysis in a pipeline

As an automation author, I want stable JSON or CSV so that I can consume the report without scraping terminal text.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` emits one valid document matching the versioned schema and exits `0` on success.
- [ ] `--csv` emits the documented header and deterministic long-form rows and exits `0` on success.
- [ ] `--json` and `--csv` together are rejected with exit `2`.
- [ ] Diagnostics go only to stderr, and data failures do not emit partial JSON/CSV.

### US-6 — Stream from another process

As a DevOps engineer, I want stdin support so that decompression or filtering tools can feed analysis without a temporary file.

Priority: **P0**

Acceptance criteria:

- [ ] Omitting `INPUT` or passing `-` reads stdin.
- [ ] The same bytes through stdin and a file produce equivalent report data.
- [ ] The implementation never seeks stdin or retains all raw lines.

### US-7 — Fail safely on extreme cardinality

As an SRE, I want a clear bounded failure when unique values exceed the configured ceiling so that a hostile or unusual log cannot consume memory indefinitely.

Priority: **P0**

Acceptance criteria:

- [ ] At the ceiling, processing remains allowed; the next new tracked key stops processing.
- [ ] Unique-cardinality exhaustion exits with code `4` and a concise stderr diagnostic.
- [ ] JSON/CSV stdout is empty on this failure.

### US-8 — Read gzip files directly

As an operator, I want transparent gzip input so that archived logs need no explicit decompression pipeline.

Priority: **P1**

Acceptance criteria:

- [ ] A `.gz` path produces the same report as its decompressed content.
- [ ] Corrupt gzip input maps to input error `2`.

### US-9 — Choose ranking length

As an investigator, I want to change top-N so that I can widen or narrow a report.

Priority: **P1**

Acceptance criteria:

- [ ] `--top N` accepts integers at least 1 and applies to both rankings.
- [ ] Invalid values exit `2` without processing input.

### US-10 — Support custom formats later

As an nginx administrator, I want configurable log formats so that non-combined installations can use the tool.

Priority: **P2**

Acceptance criteria:

- [ ] A future design defines a safe format grammar before implementation.

## 5. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Read UTF-8 input incrementally from one file path, stdin, or `-` |
| FR-2 | P0 | Parse documented nginx combined-log fields and count malformed lines |
| FR-3 | P0 | Count valid requests per exact client IP and return deterministic top 10 by default |
| FR-4 | P0 | Count request targets only for status 400–599 and return deterministic top 10 by default |
| FR-5 | P0 | Emit 24 hourly buckets using `100 × hourly_request_count / total_valid_requests` |
| FR-6 | P0 | Emit exact distinct User-Agent count and its percentage of valid requests |
| FR-7 | P0 | Enforce `--max-unique` across tracked dictionaries and exit `4` on exhaustion |
| FR-8 | P0 | Render TTY-aware colored terminal text by default and honor `--no-color` |
| FR-9 | P0 | Render versioned, deterministic JSON with no terminal styling |
| FR-10 | P0 | Render deterministic RFC-compatible long-form CSV and mitigate spreadsheet formulas |
| FR-11 | P0 | Keep normal data on stdout and diagnostics on stderr |
| FR-12 | P0 | Implement exit codes `0/1/2/3/4` exactly as specified in the architecture |
| FR-13 | P1 | Support gzip-compressed path input |
| FR-14 | P1 | Support `--top N` for both rankings |
| FR-15 | P2 | Consider a safely specified custom-format grammar in a later release |

## 6. Output Data Contract

### JSON

The top-level keys are `schema_version`, `summary`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`. `summary` contains line and valid/malformed counts. Ranking elements contain `value` and `count`. Hour elements contain `hour`, `count`, and `percentage`. `user_agents` contains `distinct_count` and `percentage`.

### CSV

Every row follows `schema_version,metric,key,count,percentage`. `metric` identifies `summary`, `top_ip`, `error_url`, `hour`, or `user_agent_share`. Empty cells represent non-applicable values, never unknown data. Rows use deterministic metric and tie order.

Schema changes require a new `schema_version`, PRD update, and compatibility test.

## 7. Error and Exit Contract

| Code | Required behavior |
|---:|---|
| `0` | Successful report, including empty input and non-strict runs that retain at least one valid line |
| `1` | Unexpected internal error; concise diagnostic without traceback by default |
| `2` | Invalid CLI use or input I/O/UTF-8 failure |
| `3` | Strict malformed line or non-empty input with zero valid records |
| `4` | Unique-cardinality exhaustion |

In non-strict mode, malformed lines are skipped and disclosed. In strict mode the first malformed line stops analysis. Machine-readable output remains empty for exits `2`, `3`, and `4`.

## 8. Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 Performance | Representative 1 GB file in < 30 seconds on named laptop | Three warm-cache runs; median under target |
| NFR-2 Memory | No raw-line accumulation; tracked unique keys honor the configured ceiling | Code review, boundary test, peak-RSS benchmark |
| NFR-3 Portability | Python 3.11 and pip-installable wheel | Fresh virtual-environment smoke test |
| NFR-4 Determinism | Same records/options yield the same JSON/CSV bytes | Golden and repeated-run tests |
| NFR-5 Privacy | No network, telemetry, persistence, or raw-line diagnostics | Static review and network-isolated integration test |
| NFR-6 Testability | >= 90% branch coverage for parser, aggregate, and renderers | Coverage command from implementation plan |
| NFR-7 Accessibility | Meaning is not conveyed by color alone; redirected text is uncolored | Text golden tests with and without TTY |

## 9. Prioritization and Release Scope

P0 corresponds to Must, P1 to Should, and P2 to Could in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md). The first release includes all P0 items. Gzip and configurable top-N may follow after the release gate, although the architecture reserves their option semantics. Custom formats require a separate design decision. Authentication, persistence, services, cloud, and Kubernetes are Won’t for this product version.

## 10. Analytics and Telemetry

The CLI collects no telemetry. Product KPIs rely on opt-in package statistics, issue reports, and local benchmark evidence; report contents and file metadata are never sent elsewhere.

## 11. Kill Criteria

Pause the release and re-scope if any condition holds:

- Correct parsing cannot be achieved for the documented combined format without ambiguous silent results.
- Unique-cardinality input can bypass the ceiling or produce partial machine output.
- The measured 1 GB median is 30 seconds or more after profiling and reasonable single-process optimization.
- A P0 output or exit-code contract remains untested.
- Delivery requires a database, HTTP service, paid dependency, or ongoing infrastructure.

## 12. Acceptance and Traceability

Implementation proceeds in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). US-1 through US-7 and FR-1 through FR-12 are release gates. Each must map to an automated test, while the performance criterion maps to recorded benchmark evidence. Documentation completion alone does not claim product implementation or runtime validation.
