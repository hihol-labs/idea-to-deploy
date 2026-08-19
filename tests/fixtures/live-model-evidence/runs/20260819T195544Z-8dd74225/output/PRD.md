# Product Requirements Document: Nginx Log Lens

## Product Summary

Nginx Log Lens is a local, pip-installable Python 3.11 CLI that streams nginx
combined access logs and reports four operational metrics. It is optimized for
DevOps/SRE incident triage, deterministic pipelines, a $0 budget, and delivery
within one weekend.

## Goals

- Produce top-10 client IPs and top-10 4xx/5xx URLs from a file or stdin.
- Show 24 hourly request buckets as counts and percentages, calculated exactly
  as `100 × hourly_request_count / total_valid_requests`.
- Report unique User-Agent count and its percentage share of valid requests.
- Offer Rich colored terminal output by default and stable JSON/CSV output.
- Process the fixed 1 GB acceptance log in under 30 seconds on the declared
  reference laptop while stopping safely on unique-cardinality exhaustion.

## Non-Goals

Authentication, databases, retained history, an HTTP API, a server, cloud
services, Kubernetes, distributed processing, live dashboards, arbitrary query
languages, and automatic log discovery are outside the MVP. The tool does not
tail a growing file indefinitely; “streaming” means single-pass, bounded-input
processing without loading the complete file.

## User Stories

### US-1 — Find high-volume clients

As an on-call SRE, I want the ten most active client IPs so that I can spot a
traffic source dominating an incident.

**Priority:** P0

**Acceptance criteria:**

- [ ] With more than ten distinct IPs, output contains exactly ten ranked rows by default.
- [ ] Rows sort by count descending and then IP ascending for ties.
- [ ] `--top N` changes both ranked sections and rejects values outside 1–100 with exit 2.

### US-2 — Locate failing URLs

As a DevOps engineer, I want the ten URLs with the most 4xx/5xx responses so
that I can focus troubleshooting on failing routes.

**Priority:** P0

**Acceptance criteria:**

- [ ] Only status codes 400–599 contribute to the ranking.
- [ ] The request target, including query string as logged, is the ranking key.
- [ ] Rows sort by error count descending and then URL ascending for ties.

### US-3 — Understand traffic by hour

As an SRE, I want all 24 hourly request buckets as percentages so that I can
see when traffic is concentrated.

**Priority:** P0

**Acceptance criteria:**

- [ ] Output contains buckets `00` through `23`, including zero-count hours.
- [ ] Each percentage uses `100 × hourly_request_count / total_valid_requests` and is displayed to two decimal places.
- [ ] For valid input, the unrounded percentages sum to 100%, subject only to display rounding.

### US-4 — Assess client diversity

As a platform engineer, I want the unique User-Agent count and share so that I
can estimate client diversity and notice automation-heavy traffic.

**Priority:** P0

**Acceptance criteria:**

- [ ] The report includes exact distinct User-Agent count within the configured limit.
- [ ] Share is `100 × unique_user_agent_count / total_valid_requests` and is displayed to two decimal places.
- [ ] Exceeding `--max-unique` stops without a partial report and exits 4.

### US-5 — Use a readable terminal report

As an engineer working interactively, I want a colored, compact report so that
I can scan the result without post-processing.

**Priority:** P0

**Acceptance criteria:**

- [ ] Default output uses Rich tables and labels all four metric groups.
- [ ] ANSI styling does not appear when output is redirected to a non-terminal.
- [ ] Malformed-line and valid-record totals remain visible.

### US-6 — Feed automation safely

As a pipeline author, I want stable JSON and CSV so that downstream tools can
consume the same values as the terminal report.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits one parseable JSON document and no ANSI codes.
- [ ] `--csv` emits valid normalized CSV with header `section,rank,key,count,percentage`.
- [ ] `--json --csv` is rejected with exit 2.
- [ ] JSON, CSV, and text are derived from the same report model.

### US-7 — Handle imperfect logs predictably

As an operator, I want malformed lines counted and deterministic failures so
that pipeline behavior is auditable.

**Priority:** P0

**Acceptance criteria:**

- [ ] A mixture of valid and malformed lines produces a report and exits 0.
- [ ] Nonempty input with no valid combined-format lines emits no report and exits 3.
- [ ] Missing or unreadable input exits 1; invalid CLI usage exits 2.
- [ ] The complete exit-code contract is `0/1/2/3/4`, with code 4 reserved for unique-cardinality exhaustion.

### US-8 — Read compressed logs directly

As an operator with rotated logs, I want direct gzip input so that I can avoid
an explicit decompression pipeline.

**Priority:** P1

**Acceptance criteria:**

- [ ] A `.gz` file can be processed with the same report semantics.
- [ ] Decompression errors map to input failure exit 1.

### US-9 — Support a custom format template

As a platform engineer with a nonstandard nginx format, I want to declare a
field template so that I can reuse the analyzer.

**Priority:** P2

**Acceptance criteria:**

- [ ] A future format option can map the required IP, timestamp, request, status, and User-Agent fields.
- [ ] Combined format remains the zero-configuration default.

## Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept one file path, `-`, or stdin and process it line by line |
| FR-02 | Parse nginx combined-format IP, timestamp, request, status, bytes, referrer, and User-Agent fields |
| FR-03 | Count malformed lines without per-line stderr output |
| FR-04 | Produce deterministic top-10 IP and 4xx/5xx URL rankings |
| FR-05 | Produce all 24 hourly counts and percentage values |
| FR-06 | Produce exact unique User-Agent count/share within a configurable cardinality limit |
| FR-07 | Render Rich text by default and JSON/CSV on mutually exclusive flags |
| FR-08 | Enforce exit codes `0/1/2/3/4` exactly as specified in `PROJECT_ARCHITECTURE.md` |
| FR-09 | Install through pip and expose `nginx-log-lens` |

### P1 — Should ship after MVP

- FR-10: Transparently read gzip-compressed file input.

### P2 — Could ship later

- FR-11: Accept an explicit custom nginx log-format mapping.
- FR-12: Allow ranking normalization that strips query strings, as an opt-in
  mode with separate documented semantics.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | Fixed 1 GB fixture completes in under 30 seconds | Timed benchmark on declared Python 3.11 laptop profile |
| NFR-02 | Peak RSS is at most 256 MiB on the same fixture within default cardinality limits | `/usr/bin/time -v` or platform-equivalent measurement |
| NFR-03 | No source input is modified and no output is sent over a network | Integration test plus dependency/architecture inspection |
| NFR-04 | Output ordering and field names are deterministic | Golden tests across repeated runs |
| NFR-05 | Product modules maintain at least 90% line coverage | pytest coverage report |
| NFR-06 | Python 3.11 wheel installs and runs in a clean environment | build/install smoke test |

## Output and Exit Contract

The canonical CLI details are in `PROJECT_ARCHITECTURE.md` under `CLI
Interface`. The required exit mapping is: 0 success, 1 input/I/O failure, 2
usage error, 3 nonempty input with no valid records, and 4 unique-cardinality
exhaustion. No failure exit emits a partial data report.

## Release Acceptance

- All P0 user-story criteria pass on fixtures containing valid, mixed, empty,
  malformed-only, high-cardinality, and tie-ranked cases.
- Rich, JSON, and CSV values reconcile to the same report model.
- The 1 GB performance and memory gates pass on the documented machine.
- The wheel installs under Python 3.11 and the console script runs.
- Documentation states supported format limitations and the complete exit
  contract.

## Kill Criteria

Pause or re-scope release if the fixed benchmark remains at or above 30 seconds
after profiling and one focused optimization pass; if exact metrics cannot stay
within the memory gate under the declared cardinality ceiling; or if combined
format parsing is not reliable on the acceptance corpus. Database, server, and
distributed workarounds are not acceptable scope expansions.

## Traceability

Strategy and prioritization are in `STRATEGIC_PLAN.md`; component and interface
contracts are in `PROJECT_ARCHITECTURE.md`; build sequence and proof commands
are in `IMPLEMENTATION_PLAN.md`.

