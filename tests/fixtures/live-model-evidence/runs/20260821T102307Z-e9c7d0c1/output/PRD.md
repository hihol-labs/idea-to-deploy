# Product Requirements Document: Nginx Stream Analytics CLI

## 1. Product Summary

Nginx Stream Analytics CLI gives DevOps/SRE users four immediate summaries from a local nginx combined-format access log: top-10 client IPs, top-10 request targets with 4xx/5xx responses, request distribution across local log hours, and exact unique User-Agent share. It reads a file or stdin in one pass and emits terminal, JSON, or CSV output.

## 2. Goals and Success Measures

- Produce correct, deterministic reports for supported records without storing logs.
- Fit shell and automation workflows through stable stdout, stderr, and exit behavior.
- Process a representative 1 GB log in under 30 seconds on a documented reference laptop.
- Install with pip on Python 3.11 and require no service or paid infrastructure.

## 3. Non-Goals

- Authentication or user management.
- Database, historical retention, search, or dashboards.
- HTTP API, background server, cloud, containers, or Kubernetes.
- Arbitrary nginx `log_format` parsing in the MVP.
- Approximate metrics presented as exact values.

## User Stories

### US-1 — Error hot spots

As an on-call SRE, I want the top 10 request targets producing 4xx/5xx responses so that I can identify the endpoints driving an incident.

Priority: **P0**

Acceptance criteria:

- [ ] Only valid records with status `400..599` contribute.
- [ ] Each item includes rank, request target, count, and percentage of total valid requests.
- [ ] Results sort by count descending, then target lexicographically, and contain at most 10 items.

### US-2 — Traffic concentration

As a platform engineer, I want the top 10 client IPs so that I can spot dominant clients or suspicious traffic concentration.

Priority: **P0**

Acceptance criteria:

- [ ] Every valid record contributes its client IP once.
- [ ] IPv4 and IPv6 tokens remain distinct and unchanged.
- [ ] Results sort by count descending, then IP lexicographically, and contain at most 10 items.

### US-3 — Hourly load shape

As a systems administrator, I want an hourly request distribution so that I can see when traffic peaks in the log’s local time.

Priority: **P0**

Acceptance criteria:

- [ ] Output contains hours `00` through `23`, including zero-count hours.
- [ ] Each percentage uses `100 × hourly_request_count / total_valid_requests`.
- [ ] The hour is taken directly from nginx `time_local`; no time-zone conversion is performed.

### US-4 — User-Agent diversity

As an SRE, I want the exact share of unique User-Agents so that I can quickly gauge client diversity or automation patterns.

Priority: **P0**

Acceptance criteria:

- [ ] The metric is `100 × unique_user_agents / total_valid_requests` and includes both numerator and denominator.
- [ ] Equality is based on the exact decoded User-Agent string; `-` is a valid distinct value.
- [ ] If distinct values cross the configured ceiling, no partial report is emitted and the command exits `4`.

### US-5 — Pipeline output

As a platform engineer, I want JSON and CSV output so that I can feed results into scripts and CI jobs.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` emits one parseable object matching the documented schema.
- [ ] `--csv` emits RFC 4180-compatible normalized rows with one header.
- [ ] JSON/CSV stdout contains no ANSI codes, warnings, or progress text.
- [ ] `--json` and `--csv` together are rejected with exit `2`.

### US-6 — Safe imperfect-input handling

As an operator, I want malformed records accounted for without losing valid data so that a partially damaged log still yields an honest report.

Priority: **P0**

Acceptance criteria:

- [ ] Mixed input skips malformed lines, reports their count, produces valid aggregates, and exits `0`.
- [ ] Empty or all-malformed input emits no report and exits `3`.
- [ ] The CLI implements the complete exit contract `0/1/2/3/4` defined in `PROJECT_ARCHITECTURE.md`.

### US-7 — Compressed archives

As an administrator, I want direct gzip input so that I can avoid a separate decompression command.

Priority: **P1**

Acceptance criteria:

- [ ] Deferred until all P0 acceptance and performance criteria pass.
- [ ] When implemented, gzip and externally decompressed stdin yield identical results.

### US-8 — Flexible ranking size

As an analyst, I want a configurable top-N value so that I can inspect more or fewer ranked entries.

Priority: **P2**

Acceptance criteria:

- [ ] Deferred; MVP always returns at most 10 ranked IP and URL items.

## 5. Functional Requirements

### P0 — Must ship

1. Accept one combined-format log from `INPUT`, stdin when omitted, or `-`.
2. Incrementally parse records and never load the entire input into memory.
3. Calculate all four metrics in the same pass.
4. Track total, valid, and malformed line counts.
5. Render Rich terminal text by default and stable JSON/CSV on request.
6. Enforce exact cardinality using `--max-unique-user-agents` and exit `4` on exhaustion.
7. Implement exit codes: `0` success; `1` internal error; `2` usage/input-open error; `3` no valid input records; `4` unique-cardinality exhaustion.
8. Provide deterministic ordering and stable machine schemas.

### P1 — Should ship after MVP

1. Direct `.gz` input with equivalent parse and error behavior.

### P2 — Could ship

1. Configurable top-N.
2. User-provided nginx format definitions after a separate format-contract design.

## 6. Output Requirements

The exact fields and CLI options are specified under `PROJECT_ARCHITECTURE.md` → `CLI Interface`.

- Terminal output has four labeled summaries plus scan counts and uses color only when appropriate.
- JSON uses `schema_version: 1` and numeric counts/percentages.
- CSV uses `schema_version,metric,rank,key,count,share_pct` and emits all 24 hours.
- Machine-readable results go to stdout. Diagnostics and warnings go to stderr.
- Percentages are numeric percentages in the `0..100` range, not unscaled fractions.

## 7. Quality Attributes

| Attribute | Requirement |
|---|---|
| Performance | Median of three timed 1 GB runs is < 30 seconds after one warm-up on documented reference laptop |
| Memory | Streaming design; exact UA ceiling defaults to 1,000,000 and exhaustion is explicit |
| Portability | CPython 3.11 on supported desktop/server operating systems; no shell dependency |
| Determinism | Identical valid input/options produce byte-stable JSON and CSV output |
| Privacy | No telemetry, persistence, or network communication |
| Testability | Hand-calculated golden fixture covers every metric and exit route |

## 8. Release Acceptance

- [ ] All P0 user-story acceptance criteria pass.
- [ ] Pip installation creates the documented console command.
- [ ] Parser/aggregation/renderer tests meet the 90% coverage target.
- [ ] The end-to-end fixture matches independently hand-calculated expected values.
- [ ] All exit codes `0/1/2/3/4` are exercised by CLI integration tests.
- [ ] The documented 1 GB benchmark meets the target without output suppression tricks or excluded parsing work.
- [ ] Required project and user documentation is current.

## 9. Kill Criteria

- Any supported valid record is silently dropped or assigned to the wrong metric.
- The optimized one-pass implementation cannot meet the performance target on the reference laptop; stop and revisit the architecture rather than relaxing the target silently.
- Exact User-Agent counting cannot be bounded with an honest exhaustion signal.
- A proposed MVP feature introduces persistence, networking, authentication, paid infrastructure, or a background service.

