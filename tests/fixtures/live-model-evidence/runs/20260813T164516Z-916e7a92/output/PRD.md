# Product Requirements Document: nginx-top

## Product Objective

Give DevOps and SRE engineers a fast, reproducible way to extract four incident-relevant summaries from nginx combined access logs on a local machine. The CLI must work as both a human-readable terminal tool and a stable pipeline component, without services or persistent state.

## Scope

### P0 — Must ship

- Stream one nginx combined-format file or stdin without loading raw input into memory.
- Report top 10 client IPs by valid request count.
- Report top 10 request-target URLs by combined 4xx/5xx response count.
- Report counts and percentages for all 24 hours.
- Report exact distinct nonempty User-Agent count and its share of valid requests.
- Render colored Rich terminal output by default when stdout is a TTY.
- Emit stable, ANSI-free JSON with `--json` and CSV with `--csv`.
- Enforce parse and unique-cardinality limits with the `0/1/2/3/4` exit contract.
- Process a representative 1 GB input in under 30 seconds on the documented reference laptop.
- Install through pip on Python 3.11.

### P1 — Should ship after MVP

- Transparently read gzip-compressed log files.
- Honor `NO_COLOR` when no explicit color option is provided.
- Publish a signed/tagged PyPI release after repository and credentials exist.

### P2 — Could ship later

- Allow configurable top-N between 1 and 100.
- Add documented parser profiles for common custom nginx `log_format` layouts.
- Merge multiple input files into one report.

### Out of scope / Won't

- Authentication, accounts, authorization, or secrets.
- A database, retained history, caches, or background jobs.
- An HTTP API, web UI, server, daemon, cloud service, or Kubernetes.
- Log shipping, alerting, tail-follow mode, or live dashboards.
- User-Agent classification, bot detection, IP geolocation, URL decoding, or PII redaction.
- Approximate unique-count algorithms in the MVP.

## User Stories

### US-1 — Identify dominant clients

As an on-call SRE, I want the top 10 client IPs so that I can quickly spot a noisy source during an incident.

Priority: P0

Acceptance criteria:

- [ ] Every valid request increments exactly one client IP count.
- [ ] Output contains no more than 10 IP rows, ordered by count descending and then IP string ascending.
- [ ] The same IPs and counts appear in terminal, JSON, and CSV outputs.

### US-2 — Find error-producing URLs

As a service operator, I want the top 10 URLs returning 4xx or 5xx statuses so that I can focus remediation on failing routes.

Priority: P0

Acceptance criteria:

- [ ] Statuses from 400 through 599 contribute to URL error counts.
- [ ] Statuses below 400 do not contribute to this metric.
- [ ] Output contains no more than 10 URL rows, ordered by count descending and then URL ascending.
- [ ] The parsed request-target is reported without URL decoding or normalization.

### US-3 — Understand hourly traffic shape

As a capacity-focused DevOps engineer, I want an hourly request distribution so that I can see when traffic occurred in the observed log.

Priority: P0

Acceptance criteria:

- [ ] Every valid request contributes to the hour encoded in its nginx timestamp.
- [ ] All 24 hour buckets, `00` through `23`, are emitted even when their count is zero.
- [ ] Each percentage is computed with the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] Percentages are rounded only for presentation, never before aggregation.

### US-4 — Measure User-Agent diversity

As an incident responder, I want the share of unique User-Agent values so that I can estimate client diversity at a glance.

Priority: P0

Acceptance criteria:

- [ ] Distinct nonempty User-Agent values other than `-` are counted exactly.
- [ ] Share is `100 × distinct_nonempty_user_agents / total_valid_requests`.
- [ ] Valid requests with a missing/`-` User-Agent remain in the denominator and add no unique value.
- [ ] If the configured uniqueness ceiling would be exceeded, no partial report is emitted and the process exits `4`.

### US-5 — Use reports in pipelines

As a platform engineer, I want JSON and CSV output so that scripts can consume metrics without scraping terminal formatting.

Priority: P0

Acceptance criteria:

- [ ] `--json` emits exactly one valid JSON document followed by a newline.
- [ ] `--csv` emits one documented long-form header and valid RFC 4180-compatible rows.
- [ ] Machine-readable output contains no Rich markup or ANSI control sequences.
- [ ] `--json --csv` is rejected before input is opened and exits `2`.
- [ ] Diagnostics are sent only to stderr.

### US-6 — Analyze local files and streams

As an SRE, I want to read either a file or stdin so that the same tool works on downloaded logs and shell pipelines.

Priority: P0

Acceptance criteria:

- [ ] A regular readable file is consumed once in binary mode.
- [ ] `INPUT` value `-` consumes non-seekable stdin once.
- [ ] Input is processed line by line and raw lines are not retained.
- [ ] File open/read failures emit a concise stderr diagnostic and exit `1`.

### US-7 — Trust failures in automation

As an automation author, I want stable exit codes so that a pipeline can distinguish misuse, bad input, I/O failures, and cardinality limits.

Priority: P0

Acceptance criteria:

- [ ] Success, help, and version exit `0`.
- [ ] Operational I/O failure exits `1`.
- [ ] Usage or option validation failure exits `2`.
- [ ] Parse-threshold exhaustion or zero valid requests exits `3`.
- [ ] Unique-cardinality exhaustion exits `4`.
- [ ] Error exits never emit a partial report.

### US-8 — Read compressed rotations directly

As a service operator, I want gzip input so that I do not need a separate decompression pipeline.

Priority: P1

Acceptance criteria:

- [ ] Gzip support, when implemented, preserves all P0 metric and exit semantics.
- [ ] Until then, documentation shows `gzip -dc access.log.gz | nginx-top -`.

## Functional Requirements

| ID | Priority | Requirement | Verification |
|---|---|---|---|
| FR-1 | P0 | Accept exactly one `INPUT` path or `-` | Click CLI tests |
| FR-2 | P0 | Parse standard nginx combined-format records | Parser fixtures including escaped and malformed fields |
| FR-3 | P0 | Aggregate the four defined metrics in one pass | Golden report fixture |
| FR-4 | P0 | Return deterministic top-10 ordering | Tie-order unit tests |
| FR-5 | P0 | Render Rich terminal output with TTY-aware color | Forced-color and redirected-output tests |
| FR-6 | P0 | Render the documented JSON schema | JSON schema/golden test |
| FR-7 | P0 | Render the documented long-form CSV schema | CSV round-trip test |
| FR-8 | P0 | Enforce configurable malformed-line threshold | Below/at/above threshold tests |
| FR-9 | P0 | Enforce combined unique-key ceiling before insertion | Boundary and exhaustion tests |
| FR-10 | P0 | Preserve stderr/stdout separation | CLI capture tests |
| FR-11 | P1 | Read gzip input | Compressed fixture test |
| FR-12 | P2 | Configure top-N | Range and schema compatibility tests |

## Non-Functional Requirements

| ID | Requirement | Acceptance target |
|---|---|---|
| NFR-1 Performance | Process representative 1 GB input | Under 30 seconds on a named reference laptop |
| NFR-2 Memory | Retain no raw input; enforce cardinality cap | Peak RSS recorded; cap exits `4` before overshoot |
| NFR-3 Compatibility | Run and install on CPython | Python 3.11 clean virtual environment |
| NFR-4 Determinism | Same input/options produce same ordered semantic report | Repeated golden runs match |
| NFR-5 Privacy | Make no network calls or implicit writes | Static review plus offline smoke test |
| NFR-6 Testability | Isolate parsing, aggregation, and rendering | Unit tests for each layer; CLI integration tests |
| NFR-7 Coverage | Exercise first-party modules | At least 90% line coverage |

## CLI and Exit-Code Acceptance Contract

The authoritative command, option, input, output, and schema contract is under `## CLI Interface` in `PROJECT_ARCHITECTURE.md`. The complete exit mapping is mandatory everywhere:

| Code | Meaning |
|---:|---|
| `0` | Successful report/help/version |
| `1` | Operational input/output failure |
| `2` | Usage or configuration error |
| `3` | Malformed-log threshold exceeded or no valid requests |
| `4` | Unique-cardinality exhaustion |

## Edge Cases

- Empty input and all-malformed input exit `3` with no report.
- A file with tolerated malformed lines reports their count and exits `0`.
- An input with no 4xx/5xx records produces an empty top-error-URL list.
- Hour buckets absent from input still appear with zero count and `0.0` percent.
- URLs containing commas or quotes round-trip through CSV quoting.
- Captured terminal markup and control characters are escaped rather than interpreted.
- IPv4 and IPv6 address strings are counted as written; no DNS lookup occurs.
- A request-target with a query string is distinct from the same path without it.
- A limit breach on what would be the next distinct key exits `4` without inserting it.
- A downstream expected broken pipe produces no traceback.

## Release Acceptance

The MVP is accepted only when all P0 story criteria pass, a wheel installs in a clean Python 3.11 environment, the same golden fixture agrees across all three renderers, and recorded benchmark evidence meets the 1 GB/30 second target. Documentation must describe actual behavior and the complete exit mapping.

## Kill and Reassessment Criteria

- If a profiled, optimized Python 3.11 implementation cannot process the representative 1 GB workload within 30 seconds on the named reference laptop, pause release and evaluate a compiled parser or a different runtime.
- If exact unique User-Agent tracking cannot stay within an agreed laptop memory envelope at the documented default cap, revise the cap or product metric explicitly; do not silently approximate it.
- If supporting real target logs requires multiple incompatible `log_format` variants at launch, re-scope parser profiles before broadening implementation.
- If requirements introduce storage, an API, authentication, a server, cloud, or Kubernetes, start a new architecture decision rather than extending this MVP implicitly.

## Dependencies and Traceability

Strategy and prioritization are defined in `STRATEGIC_PLAN.md`; architectural details and output schemas are defined in `PROJECT_ARCHITECTURE.md`; implementation sequencing is defined in `IMPLEMENTATION_PLAN.md`.
