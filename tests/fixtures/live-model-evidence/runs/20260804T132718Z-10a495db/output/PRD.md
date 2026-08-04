# Product Requirements Document: nginx-stream-report

## Product Summary

A local Python 3.11 CLI turns a finite nginx combined access-log stream into four deterministic operational summaries. Its primary success measure is correct, pipeline-safe output while processing a 1 GB log in under 30 seconds on a documented laptop.

## Goals

- Make common nginx incident-triage questions answerable with one local command.
- Keep log contents local and avoid infrastructure or persistent state.
- Support both readable terminal output and stable JSON/CSV automation.
- Fail predictably on invalid input, I/O errors, and unsafe cardinality.

## Non-Goals

No authentication, database, HTTP API, server, cloud, Kubernetes, dashboard, query language, log shipping, retention, correlation, geolocation, bot detection, or arbitrary nginx `log_format` support is included in the MVP.

## User Stories

### US-1 — Analyze a local stream (P0)

As an on-call engineer, I want to pass a log file or stdin to one command so that I can triage traffic without deploying a service.

Acceptance criteria:

- [ ] A path, `-`, and omitted path/stdin produce equivalent results for identical bytes.
- [ ] Processing is incremental and never buffers the full input.
- [ ] Invalid UTF-8 or a line over 64 KiB is skipped/counts as malformed by default and exits 3 under `--strict`.
- [ ] A documented 1 GiB benchmark completes in under 30.0 seconds on the reference laptop.
- [ ] Missing/unreadable input exits 1; invalid invocation exits 2.

### US-2 — Find dominant clients (P0)

As an SRE, I want the top 10 client IPs by request count so that I can spot noisy clients.

Acceptance criteria:

- [ ] At most 10 entries are emitted, ordered by count descending and IP ascending for ties.
- [ ] Counts use only valid parsed requests.
- [ ] Text, JSON, and CSV represent the same entries and counts.

### US-3 — Find failing routes (P0)

As an application operator, I want the top 10 request targets with 4xx/5xx statuses so that I can prioritize broken or abused routes.

Acceptance criteria:

- [ ] Only status codes 400 through 599 contribute.
- [ ] At most 10 targets are emitted, ordered by count descending and target ascending for ties.
- [ ] The target is not URL-decoded or otherwise rewritten.

### US-4 — See hourly load shape (P0)

As a capacity engineer, I want every hour's percentage of valid requests so that I can see when traffic concentrates.

Acceptance criteria:

- [ ] Exactly 24 hour buckets from `00` through `23` are emitted.
- [ ] Each value uses `100 × hourly_request_count / total_valid_requests` and is displayed to two decimals.
- [ ] Empty valid input yields 0.00% for all hours.

### US-5 — Measure User-Agent diversity (P0)

As a security-minded operator, I want the share of distinct User-Agent values so that I can quickly assess client diversity.

Acceptance criteria:

- [ ] The percentage is `100 × unique_user_agent_count / total_valid_requests`.
- [ ] Empty valid input yields 0.00%.
- [ ] Exceeding the configured distinct-key ceiling emits no partial report and exits 4 for unique-cardinality exhaustion.

### US-6 — Feed pipelines (P0)

As a platform engineer, I want stable JSON or CSV output so that downstream scripts do not scrape terminal decoration.

Acceptance criteria:

- [ ] `--json` emits one valid UTF-8 JSON object and `--csv` emits the documented normalized schema.
- [ ] `--json` and `--csv` together exit 2.
- [ ] Neither format contains ANSI control sequences; diagnostics are confined to stderr.
- [ ] Control and bidi characters in untrusted keys are represented as visible `\\uXXXX` escapes and cannot add terminal or CSV lines.

### US-7 — Read a polished terminal report (P1)

As a human operator, I want colored, aligned output on a terminal so that high-volume results are easy to scan.

Acceptance criteria:

- [ ] Rich color is the default only on a TTY.
- [ ] `--no-color`, `NO_COLOR`, and redirected output suppress ANSI codes.

### US-8 — Analyze compressed archives (P1)

As a systems administrator, I want transparent gzip input so that I can avoid a separate decompression step.

Acceptance criteria:

- [ ] A `.gz` file produces the same report as its uncompressed content.
- [ ] Corrupt gzip input exits 1 with a concise diagnostic.

### US-9 — Follow a growing file (P2)

As an on-call engineer, I want an optional live-follow mode so that I can watch evolving traffic. This is deferred until finite-stream behavior and output snapshots are stable.

## Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Parse UTF-8 nginx combined-log records and count malformed records |
| FR-2 | P0 | Compute the four report groups exactly as specified in the user stories |
| FR-3 | P0 | Read one path or stdin in a single pass |
| FR-4 | P0 | Produce mutually exclusive text, JSON, or CSV output |
| FR-5 | P0 | Implement exit codes 0, 1, 2, 3, and 4 exactly as defined in `PROJECT_ARCHITECTURE.md` |
| FR-6 | P0 | Enforce a positive configurable distinct-key ceiling |
| FR-7 | P1 | Support gzip paths |
| FR-8 | P2 | Support a live follow mode after MVP |

## Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | Python 3.11; installable through pip with a console entry point |
| NFR-2 | 1 GiB processed in under 30.0 seconds on the documented reference laptop |
| NFR-3 | Memory is independent of total line count and bounded by per-dimension distinct-key, shared retained-byte, and physical-line limits |
| NFR-4 | Deterministic ordering and stable JSON/CSV schemas |
| NFR-5 | No network access, persistent state, telemetry, or sensitive-data retention |
| NFR-6 | Parser/aggregation/rendering branch coverage of at least 90% |

## Output Semantics

Malformed records are skipped by default, counted, and reported on stderr; `--strict` turns the first malformed record into exit 3. A valid empty stream succeeds. Percentages use valid records as denominator. Rounding is presentation-only; JSON preserves numeric percentages consistently and tests compare within the documented representation precision.

## Release Acceptance

Release requires all P0 criteria, a clean installation test on Python 3.11, golden JSON/CSV fixtures, no ANSI sequences in redirected output, and recorded elapsed time plus peak RSS for the 1 GiB fixture. P1 and P2 omissions do not block MVP.

## Kill Criteria

Pause delivery and revise the product premise if the target benchmark remains above 30 seconds after two evidence-led optimization passes, the declared nginx format cannot be parsed reliably, or exact cardinality cannot be bounded with exit code 4 without emitting misleading partial output.

The CLI syntax and exit behavior are authoritative in `PROJECT_ARCHITECTURE.md`; delivery steps are in `IMPLEMENTATION_PLAN.md`.
