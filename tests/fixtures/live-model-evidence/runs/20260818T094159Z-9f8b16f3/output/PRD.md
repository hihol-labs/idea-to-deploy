# Product Requirements Document: Nginx Stream Insights

## Product Summary

Nginx Stream Insights is a local, open-source Python 3.11 CLI that turns nginx combined access logs into four focused operational summaries without a server or persistent store. The target user is an SRE/DevOps engineer performing incident triage or composing a shell/CI pipeline.

## Goals

- Produce accurate top-10 IP, top-10 4xx/5xx URL, hourly, and User-Agent summaries in one streaming pass.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Offer human-friendly colored text and stable JSON/CSV output.
- Fail predictably through the complete `0/1/2/3/4` exit-code contract.
- Remain local, stateless, pip-installable, and deliverable in one weekend for $0.

## Non-Goals

Authentication, database storage, HTTP APIs, long-running servers, cloud services, Kubernetes, dashboards, historical comparisons, real-time file following, arbitrary nginx `log_format`, geo-IP enrichment, bot detection, and approximate cardinality are outside the MVP.

## User Stories

### US-1 — Find high-volume clients

As an on-call SRE, I want the ten client IPs with the most valid requests so that I can identify dominant or suspicious traffic sources.

Priority: P0

Acceptance criteria:

- [ ] Each valid line increments exactly one IP count.
- [ ] At most ten entries are returned, ordered by count descending and IP lexicographically on ties.
- [ ] The result is identical in meaning across text, JSON, and CSV.

### US-2 — Find failing URLs

As a service owner, I want the ten URLs with the most 4xx/5xx responses so that I can prioritize broken or abused endpoints.

Priority: P0

Acceptance criteria:

- [ ] Status codes 400–599 inclusive contribute; other statuses do not.
- [ ] At most ten entries are returned with deterministic count/key ordering.
- [ ] Query strings are preserved and malformed lines do not contribute.

### US-3 — See traffic by hour

As an SRE, I want request distribution across all 24 nginx-local hours so that I can see when traffic concentrates.

Priority: P0

Acceptance criteria:

- [ ] All hours `00`–`23` are present, including zero-count hours.
- [ ] Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] Percentages are `0.0` when `total_valid_requests` is zero and otherwise total approximately 100% within documented floating-point rounding.

### US-4 — Measure User-Agent diversity

As a platform engineer, I want the count and share of distinct nonempty User-Agent values so that I can quickly assess client diversity.

Priority: P0

Acceptance criteria:

- [ ] Quoted nonempty User-Agent strings are counted exactly once per distinct value.
- [ ] `-` and empty values are excluded from the distinct numerator.
- [ ] Share is `100 × distinct_nonempty_user_agent_count / total_valid_requests`, or `0.0` for no valid requests.
- [ ] Exceeding the exact cardinality limit exits with code 4 and emits no partial machine-readable report.

### US-5 — Readable terminal triage

As an on-call engineer, I want a colored terminal report by default so that I can scan results quickly.

Priority: P0

Acceptance criteria:

- [ ] Default output has labeled sections, counts, ranks, and percentages.
- [ ] Color is suppressed for non-terminal output or with `--no-color`.
- [ ] Diagnostics go to stderr and data goes to stdout.

### US-6 — Pipeline-safe serialization

As an automation engineer, I want JSON and CSV formats so that I can consume reports without scraping terminal text.

Priority: P0

Acceptance criteria:

- [ ] `--json` emits one valid UTF-8 JSON document matching the documented schema.
- [ ] `--csv` emits valid long-form CSV with one header and a `metric` discriminator.
- [ ] `--json` and `--csv` are mutually exclusive and invalid combinations exit 2.
- [ ] Machine-readable output contains no ANSI escape sequences or diagnostics.

### US-7 — Stream files and stdin

As a shell user, I want file paths or stdin as input so that the tool works interactively and in pipelines.

Priority: P0

Acceptance criteria:

- [ ] No path reads stdin; paths are streamed in argument order; `-` denotes stdin once.
- [ ] Input is never fully loaded into memory.
- [ ] Missing/unreadable input or nonempty input with no parseable records exits 3.

### US-8 — Read gzip logs

As an operator, I want transparent `.gz` input so that archived logs need not be expanded first.

Priority: P1

Acceptance criteria:

- [ ] Gzip input uses the same parser and report contract.
- [ ] Corrupt gzip input maps to exit 3.

### US-9 — Configure custom nginx formats

As an nginx administrator, I want to describe a custom `log_format` so that non-combined logs can be analyzed.

Priority: P2

Acceptance criteria:

- [ ] Deferred until after the MVP grammar and compatibility design are validated.

## Functional Requirements

### P0 — Must

| ID | Requirement |
|---|---|
| FR-1 | Accept zero or more input paths and stream stdin when none are given. |
| FR-2 | Parse the documented nginx combined log grammar and count malformed physical lines. |
| FR-3 | Report top-10 IPs from all valid requests with deterministic ties. |
| FR-4 | Report top-10 request targets for statuses 400–599. |
| FR-5 | Report 24 hourly counts and percentages using `100 × hourly_request_count / total_valid_requests`. |
| FR-6 | Report exact distinct nonempty User-Agent count and its percentage of valid requests. |
| FR-7 | Render Rich text by default and stable JSON/CSV on exclusive flags. |
| FR-8 | Enforce the `0/1/2/3/4` exit-code and stdout/stderr contract in `PROJECT_ARCHITECTURE.md`. |
| FR-9 | Enforce a positive configurable distinct-cardinality limit; code 4 means unique-cardinality exhaustion. |

### P1 — Should

| ID | Requirement |
|---|---|
| FR-10 | Transparently stream `.gz` files without changing metric semantics. |

### P2 — Could

| ID | Requirement |
|---|---|
| FR-11 | Support explicitly configured nginx log formats after the MVP. |

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 | Representative 1 GB input completes in < 30 seconds | Timed benchmark on recorded laptop and fixture |
| NFR-2 | Input memory is O(1) by line count; aggregate memory is bounded by configured cardinality | Peak RSS benchmark and exhaustion fixture |
| NFR-3 | Python 3.11 and pip installation are supported | Clean virtual-environment install/integration test |
| NFR-4 | Identical input and options produce deterministic JSON/CSV bytes except explicitly documented floating formatting | Golden-file tests |
| NFR-5 | No network or persistent storage access | Architecture/static review and isolated integration test |
| NFR-6 | Parser and aggregation modules reach at least 90% statement coverage | Coverage report |

## Output Schemas

JSON follows the fields specified in `PROJECT_ARCHITECTURE.md`; rankings use arrays of `{rank, key, count}`, hourly rows use `{hour, count, percentage}`, and User-Agent data uses `{count, share_percentage}`. `schema_version` starts at `1.0`; breaking changes require a major schema version.

CSV uses `metric,key,count,percentage,rank`. This long form supports multiple metric families without multiple files. Rows are deterministic: ranked IPs, ranked error URLs, hours 00–23, then the User-Agent summary.

## Exit and Error Requirements

The complete public exit contract is `0/1/2/3/4`: success, internal/runtime failure, usage error, input failure, and unique-cardinality exhaustion respectively. Code 4 is never remapped to a generic failure. On any nonzero result, stderr includes a concise actionable message; JSON/CSV stdout is empty unless a complete valid report can be produced.

## Release Criteria

- Every P0 acceptance criterion passes on Python 3.11.
- The documented 1 GB benchmark is under 30 seconds.
- All five exit codes have integration coverage.
- JSON and CSV schemas have golden fixtures.
- Pip installation and console entry point work in a clean environment.
- Required exact-candidate verification/review evidence is current.

## Kill Criteria

Stop or re-scope the MVP if profiling cannot achieve the 1 GB/30 s gate in the approved Python stack, or if exact cardinality cannot be bounded with explicit code-4 failure while retaining the promised metric semantics. Do not introduce a service, cloud store, or database as a workaround.

## Traceability

Architecture and interface details are normative in `PROJECT_ARCHITECTURE.md`. Delivery sequencing is in `IMPLEMENTATION_PLAN.md`; execution prompts are in `CLAUDE_CODE_GUIDE.md`; strategy and prioritization are in `STRATEGIC_PLAN.md`.
