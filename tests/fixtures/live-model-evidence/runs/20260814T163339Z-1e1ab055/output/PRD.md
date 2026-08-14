# Product Requirements Document: Nginx Stream Analytics CLI

## Document Contract

This PRD is the durable behavioral source of truth for the MVP. `PROJECT_ARCHITECTURE.md` defines the implementation boundaries, and `IMPLEMENTATION_PLAN.md` sequences delivery. Requirement changes must update this file before product code.

## Product Summary

A local Python 3.11 CLI lets DevOps/SRE users stream an nginx combined access log from a file or stdin and receive four deterministic metrics: top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and unique User-Agent share. Default output is colored terminal text, with JSON and CSV alternatives for pipelines.

## Goals

- Produce the four required metrics in one streaming pass.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Provide stable human and machine output contracts.
- Make malformed input and exact-cardinality exhaustion visible and automatable.
- Install through pip and run entirely locally with a $0 infrastructure budget.

## Non-Goals

- Authentication or multi-user access.
- Database, persistence, history, dashboards, or cross-run queries.
- HTTP API, server/daemon mode, cloud service, Docker deployment, or Kubernetes.
- General-purpose log search, alerting, tail-follow mode, or arbitrary nginx formats in the MVP.
- Approximate unique counting presented as exact.

## User Stories

### US-1: Analyze a local incident log (P0)

As an on-call SRE, I want to analyze a combined access-log file in one command so that I can identify high-volume clients and failing routes during an incident.

**Acceptance criteria:**

- [ ] Given a valid fixture, the command emits the exact top 10 IPs by valid request count.
- [ ] It emits the exact top 10 request targets whose status is 400–599.
- [ ] Ties sort by count descending and then key ascending.
- [ ] The process reads incrementally and does not load the complete file.

### US-2: Understand traffic by hour (P0)

As an SRE, I want a 24-hour request distribution so that I can spot traffic concentration and gaps.

**Acceptance criteria:**

- [ ] All hours `00` through `23` appear in ascending order, including zero-count hours.
- [ ] Each percentage uses `100 × hourly_request_count / total_valid_requests`.
- [ ] Percentages use the timestamp's recorded numeric UTC offset and sum to approximately 100% within display-rounding tolerance when valid requests exist.
- [ ] With zero valid requests, every hourly count and percentage is zero.

### US-3: Measure User-Agent diversity (P0)

As a platform engineer, I want the exact unique User-Agent count and its share of valid requests so that I can quickly judge client diversity.

**Acceptance criteria:**

- [ ] The report contains exact unique count and `100 × unique_user_agent_count / total_valid_requests`.
- [ ] Duplicate User-Agent strings count once in the numerator.
- [ ] Empty valid-request input yields count `0` and share `0.0`.
- [ ] Exceeding the configured exact-cardinality limit emits no partial report and exits 4.

### US-4: Consume results in automation (P0)

As a DevOps engineer, I want JSON and CSV output so that I can feed the same analysis into shell pipelines and CI jobs.

**Acceptance criteria:**

- [ ] `--json` emits one valid JSON document conforming to schema version `1` and no non-JSON diagnostics on stdout.
- [ ] `--csv` emits the documented normalized header and RFC 4180-compatible rows.
- [ ] Text, JSON, and CSV values reconcile to the same immutable summary.
- [ ] `--json --csv` is rejected as a usage error with exit 2.

### US-5: Read from stdin safely (P0)

As a systems engineer, I want to pipe logs into the command so that I can compose it with local decompression and filtering tools.

**Acceptance criteria:**

- [ ] Omitting `INPUT` or passing `-` reads stdin.
- [ ] Piped output has no ANSI escapes unless a future explicit force-color option is specified.
- [ ] Broken downstream pipes terminate quietly without a traceback.
- [ ] Input and runtime I/O failures emit no report and exit 1.

### US-6: Diagnose data quality (P1)

As an operator, I want malformed-line counts and strict mode so that I know whether a report is complete enough to trust.

**Acceptance criteria:**

- [ ] Default mode skips malformed lines, reports their count, and exits 0 after a complete report.
- [ ] `--strict` with one or more malformed lines emits no report and exits 3.
- [ ] `total_lines = valid_requests + malformed_lines` for every completed parse.

### US-7: Use readable terminal output (P0)

As an on-call engineer, I want a colored, compact terminal report so that the important signals are scannable under time pressure.

**Acceptance criteria:**

- [ ] A TTY receives four labeled metric sections and an input-quality footer.
- [ ] `--no-color`, `NO_COLOR`, and non-TTY stdout produce no ANSI escapes.
- [ ] Log-derived markup-like strings display literally and cannot alter terminal formatting.

### US-8: Analyze compressed logs directly (P2)

As an operator, I want gzip input so that I can avoid a separate decompression command. This is deferred until after the MVP and must not delay release.

### US-9: Configure alternate nginx formats (P2)

As a platform owner, I want a custom format mapping so that non-standard installations can use the tool. This is deferred until parsing and schema versioning are stable.

## Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| P0-FR-1 | P0 | Parse conventional nginx combined-format records from a file or stdin and count malformed lines. |
| P0-FR-2 | P0 | Return up to 10 IP/count pairs using deterministic ordering. |
| P0-FR-3 | P0 | Return up to 10 request-target/count pairs limited to status 400–599 using deterministic ordering. |
| P0-FR-4 | P0 | Return 24 hourly count/percentage buckets and exact unique User-Agent count/share. |
| P0-FR-5 | P0 | Render safe Rich terminal output by default with automatic and explicit no-color behavior. |
| P0-FR-6 | P0 | Render schema-versioned JSON with stable primitive types and keys. |
| P0-FR-7 | P0 | Render normalized RFC 4180 CSV with stable section semantics. |
| P0-FR-8 | P0 | Enforce the complete `0/1/2/3/4` exit-code and no-partial-report contract. |
| P0-FR-9 | P0 | Enforce a positive exact User-Agent cardinality cap and return 4 upon exhaustion. |
| P1-FR-1 | P1 | Support `--strict` to fail the entire report when any malformed line is present. |
| P1-FR-2 | P1 | Expose `total_lines`, `valid_requests`, and `malformed_lines` in every output format. |
| P2-FR-1 | P2 | Add gzip file input without changing stdin or output contracts. |
| P2-FR-2 | P2 | Add explicit custom log-format configuration with a versioned grammar. |

## Metric Definitions

| Metric | Population | Calculation | Edge behavior |
|---|---|---|---|
| Top IPs | All valid requests | Count by parsed remote address; first 10 after deterministic sort | Empty list when no valid requests |
| Top error URLs | Valid requests with status 400–599 | Count by full parsed request target; first 10 after deterministic sort | Empty list when no qualifying responses |
| Hourly distribution | All valid requests | `100 × hourly_request_count / total_valid_requests` for each timestamp hour | 24 zero buckets when denominator is zero |
| Unique User-Agent share | All valid requests | `100 × unique_user_agent_count / total_valid_requests` | `0.0` when denominator is zero; exhaustion returns 4 |

Percentages are calculated at full precision and rendered to two decimal places. Query strings remain part of URL identity in the MVP. Hour extraction uses the numeric offset contained in each log record; no host-timezone conversion occurs.

## CLI and Exit-Code Contract

The command and option details are authoritative under `PROJECT_ARCHITECTURE.md` → `## CLI Interface`. Every implementation and guide must preserve:

| Code | Contract |
|---:|---|
| `0` | Complete successful report |
| `1` | Input/runtime I/O failure |
| `2` | CLI usage error |
| `3` | Strict parse failure |
| `4` | Unique-cardinality exhaustion |

For codes 1–4, no partial report is written to stdout.

## Output Requirements

- All renderers consume the same `Summary`; no renderer recalculates a metric.
- JSON includes `schema_version`, input quality, ranked arrays, 24 hourly buckets, and User-Agent statistics.
- CSV uses `section,rank,key,count,percentage` and standard-library quoting.
- Default text has four labeled sections and a quality footer; log-derived text is never interpreted as Rich markup.
- Diagnostics use stderr and must not corrupt stdout pipelines.

## Non-Functional Requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| NFR-1 Performance | Process exactly 1 GiB (1,073,741,824 bytes) in under 30 seconds on a documented laptop profile | Current opt-in benchmark record with corpus parameters and exact result assertions |
| NFR-2 Streaming | Never materialize the entire input; hot path is single-pass | Code review plus peak-RSS benchmark |
| NFR-3 Compatibility | Install and run on CPython 3.11 | Clean-environment wheel smoke test |
| NFR-4 Correctness | Golden fixtures reconcile all formats and edge cases | Unit/integration suite, at least 90% line coverage |
| NFR-5 Determinism | Same bytes and options produce the same ordering and machine output | Repeated-run snapshot test |
| NFR-6 Privacy | No network access or persistence; no input-derived telemetry | Dependency/config review and offline integration run |
| NFR-7 Safety | Expected failures have concise diagnostics and no traceback/partial report | Exit-code matrix integration test |

## Dependencies and Constraints

- Runtime: Python 3.11, Click, Rich, standard library, dataclasses.
- Packaging: pip-installable sdist and wheel.
- Cash budget: $0; license and dependencies must permit open-source distribution.
- Delivery: one weekend.
- Architecture: one local process, no authentication/database/API/server/cloud/Kubernetes.

## Release Acceptance

The MVP is accepted only when all P0 story criteria pass, the exact candidate satisfies the repository verification/adjudication contract, the performance target is measured on documented hardware, and a clean Python 3.11 environment installs the wheel and runs file/stdin smoke tests for all three formats.

## Kill Criteria

- The representative 1 GiB workload remains at or above 30 seconds after measurement-led optimization on the target profile.
- Exact cardinality cannot be bounded with an explicit, tested exit-4 failure.
- Machine formats cannot remain reconciled with terminal results from one summary model.
- MVP delivery requires violating the local, stateless, $0, one-weekend constraints.

Meeting a kill criterion triggers re-scoping; it does not authorize adding a database, server, or distributed deployment.
