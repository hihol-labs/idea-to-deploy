# Product Requirements Document: Nginx Stream Analyzer

## 1. Product Summary

Nginx Stream Analyzer is a local Python 3.11 CLI that converts an nginx combined-format access-log stream into four operational summaries. It is optimized for fast, private, ad-hoc analysis by DevOps/SRE engineers and for deterministic use in Unix pipelines.

The architecture in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) is authoritative when interpreting implementation boundaries. The delivery sequence is in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## 2. Goals

- Report the top 10 IP addresses by request count.
- Report the top 10 request URLs by combined 4xx/5xx response count.
- Report request counts for each of the 24 hours represented in log-local time.
- Report distinct User-Agent count and its share of valid requests.
- Provide default colored terminal output and stable JSON/CSV pipeline formats.
- Process a representative 1 GB log in less than 30 seconds on a documented laptop.
- Keep logs local and create no persistent state.

## 3. Non-Goals

- Authentication or multi-user access.
- A database, history, incremental persistence, or dashboards.
- HTTP API, daemon, server, cloud service, or Kubernetes deployment.
- General-purpose log search, correlation, alerting, tail-follow mode, or arbitrary nginx formats in MVP.
- Replacing GoAccess or a centralized observability platform.

## 4. Users and Use Cases

Primary users are on-call SREs, DevOps engineers, and platform engineers working with local or piped nginx logs. Typical use cases are incident triage, error-hotspot identification, traffic-shape checks, and feeding summary data into scripts.

## 5. User Stories

### US-01 — Human incident summary

As an on-call SRE, I want one colored terminal report from a local nginx log so that I can identify dominant clients, failing URLs, traffic hours, and User-Agent diversity during triage.

Priority: **P0**

Acceptance criteria:

- [ ] With a valid fixture, default output contains sections for top IPs, error URLs, 24 hourly counts, and User-Agent uniqueness.
- [ ] Each top list contains no more than 10 rows and uses deterministic tie ordering.
- [ ] Color appears only for an interactive terminal and can be disabled.
- [ ] No database, network connection, or persistent cache is used.

### US-02 — JSON pipeline

As a DevOps engineer, I want a JSON report on stdout so that I can consume metrics with `jq` or another automation step.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` produces one valid JSON document matching the schema in PROJECT_ARCHITECTURE.md.
- [ ] JSON contains no ANSI escape sequences and diagnostics remain on stderr.
- [ ] All 24 hour buckets are present, including zero counts.
- [ ] Empty valid input produces finite zero values and exits successfully.

### US-03 — CSV pipeline

As a platform engineer, I want normalized CSV output so that I can load summaries into standard tabular tools without custom parsing.

Priority: **P0**

Acceptance criteria:

- [ ] `--csv` produces the header `report,rank,key,value` and parseable rows for all report types.
- [ ] Embedded commas, quotes, Unicode, and newlines are encoded by standard CSV rules.
- [ ] Potential spreadsheet formula prefixes in log-derived values are neutralized and documented.
- [ ] CSV contains no terminal decoration.

### US-04 — Stream from stdin

As an SRE, I want to omit the input path or pass `-` so that decompression and filtering tools can pipe logs directly into the analyzer.

Priority: **P0**

Acceptance criteria:

- [ ] Both omitted `INPUT` and explicit `-` consume stdin line by line.
- [ ] The command does not require a seekable input and does not read the complete stream into memory.
- [ ] A downstream broken pipe exits without a traceback.

### US-05 — Trustworthy imperfect-log handling

As an operator, I want malformed records counted without exposing their contents so that partial corruption does not hide valid insights or leak sensitive log data.

Priority: **P1**

Acceptance criteria:

- [ ] Malformed lines are skipped and their total is available in every output format.
- [ ] A concise warning is written to stderr without copying the original line.
- [ ] Unreadable input fails non-zero with an actionable path-level message and no traceback by default.

### US-06 — Configurable ranking size

As a power user, I want to choose a top-N value so that I can inspect more or fewer ranking rows.

Priority: **P2**

Acceptance criteria:

- [ ] A future `--top N` accepts a bounded positive integer.
- [ ] Default behavior remains top 10 and schemas remain backward compatible.

## 6. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-01 | P0 | Accept a combined-format log path, omitted input, or `-`, and iterate it line by line |
| FR-02 | P0 | Count successfully parsed requests per client IP and return at most 10 leaders |
| FR-03 | P0 | Count URLs only when status is 400–599 and return at most 10 leaders |
| FR-04 | P0 | Count requests in 24 buckets using the hour and offset written in each record |
| FR-05 | P0 | Count exact distinct User-Agent strings |
| FR-06 | P0 | Compute unique User-Agent share as distinct User-Agents divided by valid requests; use 0.0 for no valid requests |
| FR-07 | P0 | Parse IPv4/IPv6, nginx timestamps, request triple, status, and quoted User-Agent from combined format |
| FR-08 | P0 | Default to Rich terminal output, automatically suppressing color for non-TTY output or `NO_COLOR`/`--no-color` |
| FR-09 | P0 | `--json` emits the stable JSON schema and is mutually exclusive with `--csv` |
| FR-10 | P0 | `--csv` emits the normalized four-column schema with safe quoting and formula neutralization |
| FR-11 | P1 | Skip/count malformed lines, preserve valid results, and separate diagnostics onto stderr |
| FR-12 | P1 | Define exit 0 for produced reports, 1 for runtime/input errors, and 2 for usage errors |
| FR-13 | P2 | Allow a future bounded `--top N` while retaining 10 as default |
| FR-14 | P2 | Add explicitly selected nginx format templates without weakening combined-format validation |

## 7. Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 Performance | Median runtime for a documented representative 1 GB fixture is <30 seconds after warm-up | Three timed installed-CLI runs; record median and environment |
| NFR-02 Streaming | Input is never fully materialized; one parsing/aggregation pass | Code review plus stdin integration and memory benchmark |
| NFR-03 Compatibility | Package runs on supported CPython 3.11 environments | Clean virtual-environment install and test |
| NFR-04 Privacy | No network calls, persistent cache, or raw malformed-line diagnostics | Static review and integration tests |
| NFR-05 Determinism | Equal counts are ordered lexicographically by key; machine schemas are stable | Unit/golden tests |
| NFR-06 Quality | Package test coverage is at least 90% with lint clean | Coverage and ruff commands in implementation plan |
| NFR-07 Memory | Peak RSS is recorded on representative and high-cardinality corpora | `/usr/bin/time -v` benchmark evidence |
| NFR-08 Input bound | Reject/drain logical lines over 64 KiB and reject invalid UTF-8 without unbounded allocation | Oversized/invalid-byte parser and memory tests |
| NFR-09 Terminal safety | Visibly escape terminal and bidi controls in terminal presentation only | Renderer golden tests with control payloads |

## 8. Output Semantics

- “Top IPs” ranks valid requests by exact client-address string.
- “Error URLs” combines 4xx and 5xx counts and ranks the request target exactly as logged, including query strings.
- “Hourly distribution” is by the hour present in the per-record timestamp; no cross-time-zone normalization is performed.
- “Unique User-Agent share” is `distinct valid User-Agent values / valid request count`, not the share of requests that contain a User-Agent.
- Malformed records do not contribute to the denominator or any metric.

## 9. Prioritization Traceability

P0 corresponds to Must, P1 to Should, and P2 to Could in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md). The implementation uses RICE order inside dependency layers; package/parser foundations precede consumer-facing features because those features cannot be verified without them.

## 10. Release Acceptance

The MVP may release only when every P0 user-story criterion passes, all P0 functional requirements have automated coverage, the installed package passes its lint/test/build checks, the representative 1 GB benchmark completes in under 30 seconds, and both representative and high-cardinality profiles remain at or below 512 MiB peak RSS. P1 malformed-line and exit behavior should ship in the weekend release but cannot delay a correct P0 demonstration unless it causes unsafe output or crashes.

## 11. Kill Criteria

- The measured 1 GB median remains at or above 30 seconds after profiling and one bounded optimization iteration.
- Exact high-cardinality aggregation exceeds an agreed practical laptop memory envelope and stakeholders reject approximate semantics.
- User discovery shows the primary need is persistent, collaborative, or remotely served analysis; that requirement belongs to another product architecture.
- The supported combined-format parser cannot reach ≥99.9% accuracy on the approved fixture corpus without broad format inference.
