# Product Requirements Document: Nginx Stream Analyzer

## 1. Summary

Nginx Stream Analyzer is a local, stateless CLI that converts nginx combined access logs into four operational views: top 10 IPs, top 10 URLs with 4xx/5xx responses, hourly request percentages, and unique User-Agent percentage. It serves DevOps/SRE incident triage and automation without a service, database, or retained data.

## 2. Problem Statement

Operators regularly need a fast answer from a log file but face a poor choice between fragile one-off shell pipelines and heavyweight persistent observability systems. The product supplies a tested, one-command middle ground that works interactively and in pipelines.

## 3. Goals and Non-Goals

### Goals

- Analyze a path or stdin in one streaming pass.
- Produce exact, deterministic reports in text, JSON, and CSV.
- Process a 1 GB supported-format log in under 30 seconds on a declared laptop.
- Fail explicitly when exact unique-cardinality state exceeds the supported budget.
- Install with pip on Python 3.11 and cost $0 to operate.

### Non-Goals

- Authentication or multi-user access.
- Database, historical retention, indexing, or search.
- HTTP API, server, dashboard, cloud service, Docker, or Kubernetes.
- General-purpose nginx configuration parsing or arbitrary log formats in MVP.
- Approximate cardinality results silently substituted for exact results.

## 4. Personas

- **On-call SRE:** needs a fast, readable incident snapshot from a local log.
- **DevOps automation author:** needs stable schemas, stdout/stderr separation, and meaningful exits.
- **Platform engineer:** needs bounded behavior on large and adversarial files.

## User Stories

### US-1 — Analyze local files and stdin

As an on-call SRE, I want to analyze either a log path or stdin so that I can use the tool on downloaded files and live shell pipelines.

**Priority:** P0

**Acceptance criteria:**

- [ ] A regular file path and the same bytes on stdin produce equivalent report data.
- [ ] Omitting `INPUT` and passing `-` both select stdin.
- [ ] An unreadable or missing path writes a concise stderr diagnostic and exits `1`.

### US-2 — Find dominant client IPs

As an SRE, I want the top 10 source IPs so that I can identify concentrated traffic or abusive clients.

**Priority:** P0

**Acceptance criteria:**

- [ ] Only valid records contribute to counts.
- [ ] At most 10 rows are returned, ordered by count descending then IP ascending.
- [ ] IPv4 and IPv6 strings are preserved exactly.

### US-3 — Find URLs producing errors

As an incident responder, I want the top 10 request targets with 4xx/5xx statuses so that I can prioritize failing routes.

**Priority:** P0

**Acceptance criteria:**

- [ ] Status codes 400 through 599 are included; 399 and lower are excluded.
- [ ] Request targets, including query strings, are counted as logged.
- [ ] Results are limited to 10 with deterministic tie ordering.

### US-4 — Understand hourly traffic shape

As a platform engineer, I want requests grouped by source-log hour as percentages so that I can spot traffic concentration across the day.

**Priority:** P0

**Acceptance criteria:**

- [ ] Output contains all hours 00 through 23, including zero-count hours.
- [ ] Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] For a non-empty valid dataset, percentages total 100% within documented floating-point rounding tolerance.

### US-5 — Measure User-Agent diversity

As an SRE, I want the share of unique User-Agent values so that I can quickly judge client diversity.

**Priority:** P0

**Acceptance criteria:**

- [ ] Uniqueness is exact and case-sensitive over valid records.
- [ ] The report includes both unique count and `100 × unique_user_agent_count / total_valid_requests`.
- [ ] Exceeding the total distinct-key budget emits no partial success report and exits `4`.

### US-6 — Consume stable machine output

As a DevOps automation author, I want JSON or CSV so that downstream tools can consume reports without parsing terminal formatting.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits one valid schema-versioned JSON document and no ANSI escapes.
- [ ] `--csv` emits one header using `schema_version,section,key,count,percentage` and no ANSI escapes.
- [ ] `--json` and `--csv` together are rejected as a usage error with exit `2`.
- [ ] Diagnostics use stderr and report data uses stdout.

### US-7 — Analyze gzip logs directly

As an operator, I want transparent gzip input so that I can avoid a separate decompression command.

**Priority:** P1

Acceptance is deferred until the P0 release is stable.

### US-8 — Configure the nginx format

As a platform engineer, I want a documented format option so that I can analyze a common custom access-log layout.

**Priority:** P1

Acceptance is deferred; design must preserve one-pass parsing.

### US-9 — Select a top-N value

As an operator, I want to choose the ranking length so that I can expand a report during deeper investigation.

**Priority:** P2

Acceptance is deferred; MVP remains fixed at top 10.

## 6. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Accept one file path, omitted input, or `-` for stdin |
| FR-2 | P0 | Parse the documented nginx combined-log grammar line by line and count malformed lines |
| FR-3 | P0 | Count valid requests by exact IP and return deterministic top 10 |
| FR-4 | P0 | Count exact request targets for status 400–599 and return deterministic top 10 |
| FR-5 | P0 | Return 24 hourly counts and percentages using `100 × hourly_request_count / total_valid_requests` |
| FR-6 | P0 | Return exact unique User-Agent count and percentage over valid requests |
| FR-7 | P0 | Support Rich text, versioned JSON, and normalized CSV output |
| FR-8 | P0 | Enforce exits `0/1/2/3/4`, where `4` is unique-cardinality exhaustion |
| FR-9 | P1 | Support gzip input after MVP evidence |
| FR-10 | P1 | Support a constrained configurable format after MVP evidence |
| FR-11 | P2 | Support configurable top-N |

## 7. Output and Exit Contract

Text is the default. JSON and CSV schemas are specified in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md). All modes expose `total_valid_requests` and `invalid_lines`; percentages never use invalid records as the denominator.

| Exit | Product meaning |
|---:|---|
| `0` | Successful report, including a truly empty input |
| `1` | Input/output operational failure or unexpected internal failure |
| `2` | Invalid command usage |
| `3` | Non-empty input with no valid supported records |
| `4` | Unique-cardinality exhaustion before an exact report could be completed |

## 8. Non-Functional Requirements

| ID | Requirement | Acceptance method |
|---|---|---|
| NFR-1 Performance | 1 GB in under 30 seconds on declared laptop | Reproducible benchmark record after warm-up |
| NFR-2 Memory | No raw-line retention; unique state capped | Peak-RSS record and forced exhaustion test |
| NFR-3 Compatibility | Python 3.11 on Linux/macOS | Clean virtual-environment wheel install |
| NFR-4 Determinism | Same data produces same row order and machine schemas | Golden tests and repeated runs |
| NFR-5 Privacy | No network calls or persistence | Static dependency/code inspection and integration test |
| NFR-6 Testability | ≥90% branch coverage on core modules | Coverage command from implementation plan |

## 9. Edge Cases

- Empty input: valid empty report, exit `0`, all percentages `0.0`.
- Non-empty but entirely malformed input: diagnostic summary and exit `3`.
- Mixed valid/malformed input: report valid records, expose invalid count, exit `0`.
- Fewer than 10 distinct values: return all available values without padding.
- Ties: order lexicographically by exact key after count descending.
- Broken output pipe or unreadable path: concise diagnostic without a raw traceback, exit `1`.
- Cardinality limit reached: stop before retaining another distinct value, no partial machine report, exit `4`.

## 10. Success and Release Criteria

Release requires all P0 acceptance criteria, exact text/JSON/CSV parity, explicit tests for exits `0/1/2/3/4`, a clean wheel install on Python 3.11, and documented evidence that the 1 GB fixture finishes under 30 seconds on the declared reference laptop.

## 11. Kill Criteria

The MVP is stopped or re-scoped if its profiled Python implementation cannot meet the 1 GB / 30-second target, if exact cardinality cannot be bounded with an explicit error, or if user validation shows that persistent historical querying—not local one-shot triage—is the dominant need.

## 12. Dependencies

Click and Rich are the only runtime third-party dependencies. No external system, credential, port, persistent store, or paid service is required. The implementation sequence is [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
