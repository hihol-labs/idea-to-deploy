# Product Requirements Document: Nginx Pulse

## 1. Product Summary

Nginx Pulse is a local Python 3.11 CLI that sequentially processes one nginx combined access-log stream and reports four operational views in colored terminal text, JSON, or CSV. It serves DevOps/SRE users who need fast, repeatable analysis without installing or operating a server-side analytics stack.

## 2. Problem and Goals

During incidents, raw nginx logs contain immediate traffic and failure signals, but ad hoc shell pipelines are hard to reproduce and full observability stacks may be unavailable or excessive. The MVP must turn a file or stdin into a deterministic report, preserve pipeline semantics, stay local, and process a representative 1 GB log in under 30 seconds on a documented laptop.

Goals:

- Correctly parse the documented nginx combined-log format while isolating malformed records.
- Report top IPs, error URLs, hour distribution, and exact unique User-Agent share from one pass.
- Provide human-readable defaults and stable machine-readable schemas.
- Remain stateless, installable through pip, and operable at $0.

Non-goals include authentication, persistence, HTTP APIs, servers, live tail/follow mode, cloud services, Kubernetes, dashboards, and arbitrary nginx format configuration.

## User Stories

- As a on-call SRE, I want the top 10 client IPs by request count so that I can identify concentrated traffic during an incident.
  - Priority: P0
  - Acceptance criteria:
    - [ ] Counts include every valid record and exclude malformed records.
    - [ ] Results contain at most ten items, ordered by count descending then IP ascending.
- As a service operator, I want the top 10 URLs producing 4xx/5xx responses so that I can find failing routes quickly.
  - Priority: P0
  - Acceptance criteria:
    - [ ] Only status codes 400 through 599 contribute to the ranking.
    - [ ] Query strings remain part of the URL key and ties sort by URL ascending.
- As a capacity engineer, I want hourly request distribution percentages so that I can see when traffic is concentrated.
  - Priority: P0
  - Acceptance criteria:
    - [ ] All 24 logged local-hour buckets appear, including zero-value hours.
    - [ ] Each bucket uses `100 × hourly_request_count / total_valid_requests`, or `0.0` when there are no valid requests.
- As a security-minded operator, I want the share of unique User-Agent strings so that I can spot unusual client diversity.
  - Priority: P0
  - Acceptance criteria:
    - [ ] The numerator is the exact count of distinct User-Agent strings among valid records.
    - [ ] Exceeding the configured exact-cardinality ceiling emits no report and exits 4.
- As a terminal user, I want a concise colored default report so that important values are easy to scan interactively.
  - Priority: P0
  - Acceptance criteria:
    - [ ] Interactive text contains all four metric views plus valid/malformed totals.
    - [ ] Redirected text and `--no-color` output contain no ANSI escapes.
- As an automation engineer, I want stable JSON output so that scripts can consume metrics without scraping terminal text.
  - Priority: P0
  - Acceptance criteria:
    - [ ] `--json` emits exactly one schema-versioned object followed by a newline.
    - [ ] Diagnostics and ANSI escapes never appear on stdout.
- As a reporting engineer, I want stable CSV output so that I can load results into shell and spreadsheet workflows.
  - Priority: P0
  - Acceptance criteria:
    - [ ] `--csv` emits the documented long-form header and deterministic row ordering.
    - [ ] Values containing commas, quotes, or newlines are escaped through RFC 4180 CSV rules.
- As an operator with rotated logs, I want direct gzip input so that I can avoid a separate decompression process.
  - Priority: P1
- As an nginx administrator, I want to describe a custom `log_format` so that nonstandard logs can be analyzed.
  - Priority: P2

## 4. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-001 | Accept one optional `INPUT`; a path reads that file, while omitted input or `-` reads stdin sequentially. |
| FR-002 | Parse the combined-log fields and validate timestamp and status as specified in `PROJECT_ARCHITECTURE.md`. |
| FR-003 | Count every physical line as either valid or malformed and never include malformed data in metrics. |
| FR-004 | Return the top 10 IPs by valid request count with deterministic tie ordering. |
| FR-005 | Return the top 10 raw URL targets whose statuses are in 400–599, with deterministic tie ordering. |
| FR-006 | Return 24 hour buckets where each percentage is `100 × hourly_request_count / total_valid_requests`; all values are zero for no valid requests. |
| FR-007 | Return exact unique User-Agent count and percentage share, bounded by the configured cardinality ceiling. |
| FR-008 | Default to Rich terminal text and support mutually exclusive `--json` and `--csv`. |
| FR-009 | Keep normal results on stdout, diagnostics on stderr, and use the complete `0/1/2/3/4` exit-code contract. |
| FR-010 | Provide `--help`, `--version`, color control, and positive `--max-unique-user-agents`. |
| FR-011 | Install as `nginx-pulse` via a Python 3.11-compatible wheel and run equivalently as `python -m nginx_pulse`. |

### P1 — Should follow MVP

| ID | Requirement |
|---|---|
| FR-101 | Detect and stream gzip-compressed local input without changing output schemas or metric semantics. |

### P2 — Could follow evidence

| ID | Requirement |
|---|---|
| FR-201 | Support explicitly described custom nginx log formats with a validation command. |
| FR-202 | Offer an opt-in approximate User-Agent cardinality mode clearly labeled as approximate. |

## 5. Output and Error Contract

Text, JSON, and CSV represent the same immutable analysis result. Exact field/row schemas and ordering are defined under `## CLI Interface` in `PROJECT_ARCHITECTURE.md`.

| Exit | Product meaning |
|---:|---|
| 0 | Successful complete analysis, including empty input |
| 1 | Input/output or internal runtime failure |
| 2 | Invalid CLI usage |
| 3 | Successful partial analysis with one or more malformed records skipped |
| 4 | Unique-cardinality exhaustion; no normal report emitted |

Malformed lines are recoverable and produce exit 3 after rendering valid-record metrics. Invalid UTF-8 is an input failure and produces exit 1 because line boundaries/content cannot be trusted under the declared input encoding.

## 6. Non-Functional Requirements

| ID | Requirement | Acceptance measure |
|---|---|---|
| NFR-001 | Performance | Representative 1 GB fixture completes in under 30 seconds on the documented reference laptop with output redirected |
| NFR-002 | Streaming | No raw record list or full-file buffer; one-pass scan and memory proportional only to distinct aggregate keys |
| NFR-003 | Determinism | Identical input/options/runtime version produce byte-identical JSON and CSV output |
| NFR-004 | Correctness | Maintained parser/metric fixture corpus passes completely on Python 3.11 |
| NFR-005 | Privacy | No telemetry, networking, persistence, or log-content echo in diagnostics |
| NFR-006 | Portability | Linux and macOS are release-blocking; Windows behavior is tested where CI is available |
| NFR-007 | Maintainability | Ruff, mypy, and pytest pass; changed production modules maintain at least 90% branch coverage |
| NFR-008 | Resource safety | New User-Agent values cannot exceed the configured ceiling; exhaustion is explicit, never approximate |

## 7. Edge Cases

- Empty input succeeds with empty rankings, 24 zero percentages, and zero unique share.
- A final non-newline-terminated record is processed.
- All-malformed input emits a zero-valued report and exits 3.
- URL query strings distinguish keys; percent encoding is not normalized.
- A User-Agent value of `-` participates as one literal distinct value.
- IPv6 tokens are counted exactly as logged.
- Equal counts use ascending Unicode code-point order of parsed strings.
- A missing/unreadable input, invalid UTF-8, or stdout write failure maps to exit 1.
- The first would-be User-Agent beyond the limit maps to exit 4 without a partial report.

## 8. Release Acceptance

The MVP is accepted when every P0 story criterion passes, an isolated Python 3.11 environment can install the built wheel, all three formats agree on a golden fixture, the complete exit-code matrix is verified, and the reproducible 1 GB benchmark meets the target. No service, database, HTTP listener, authentication mechanism, cloud asset, or Kubernetes artifact may be introduced.

## 9. Kill Criteria

Pause or reduce scope when any of these is true:

- Supported-format metric correctness is below 100% on the agreed fixture corpus.
- The 1 GB target remains at or above 30 seconds after two profile-led optimization iterations.
- Exact unique cardinality cannot be bounded without silently changing the defined metric.
- A required dependency or distribution route introduces a monetary cost.
- The one-weekend time box is exceeded before the P0 file/stdin, four-metric, text, JSON, and CSV path is end-to-end complete; P1/P2 work is dropped first.

Priorities originate in `STRATEGIC_PLAN.md`; technical details originate in `PROJECT_ARCHITECTURE.md`; work sequencing is defined in `IMPLEMENTATION_PLAN.md`.
