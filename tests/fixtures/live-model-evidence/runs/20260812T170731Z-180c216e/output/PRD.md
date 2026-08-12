# Product Requirements Document: Nginx Stream Insights

## Product Summary

Nginx Stream Insights gives DevOps/SRE engineers a fast, local summary of nginx combined access logs. It processes a file or stdin once, retains only aggregate state, and emits colored terminal text, JSON, or CSV. `PROJECT_ARCHITECTURE.md` is authoritative for calculation, schema, error, and exit-code semantics.

## Goals and Success Metrics

- Report top 10 IPs, top 10 URLs with 4xx/5xx responses, 24-hour request distribution, and unique User-Agent share.
- Process a representative 1 GB log in under 30 seconds on the documented reference laptop.
- Use bounded streaming state rather than retaining log lines or parsed records.
- Produce deterministic, testable terminal, JSON, and CSV outputs.
- Install through pip and run on Python 3.11 with $0 infrastructure cost.

## Non-Goals

No authentication, database, persistence, HTTP API, server, dashboard, cloud, Docker requirement, or Kubernetes. No live tail-follow mode, historical comparison, distributed ingestion, arbitrary query language, geolocation, bot detection, or custom nginx format DSL in the MVP.

## User Stories

### US-1 — Analyze a local log (P0)

As an on-call SRE, I want to analyze an nginx access-log file with one command so that I can identify traffic and failure hotspots quickly.

Acceptance criteria:

- [ ] A readable combined-format file produces all four reports and exits 0.
- [ ] Input is consumed sequentially and raw request records are not accumulated.
- [ ] Default stdout is a readable Rich terminal report.
- [ ] A representative 1 GB fixture completes in under 30 seconds on the recorded reference laptop.

### US-2 — Find dominant clients (P0)

As an incident responder, I want the top 10 client IPs so that I can spot concentrated traffic.

Acceptance criteria:

- [ ] Results contain no more than 10 IPs, ordered by count descending and IP string ascending on ties.
- [ ] Counts include every valid request regardless of status.
- [ ] Fewer than 10 distinct IPs produces only the available rows.

### US-3 — Find failing routes (P0)

As a service owner, I want the top 10 URLs producing 4xx/5xx responses so that I can prioritize broken or abused routes.

Acceptance criteria:

- [ ] Only status codes 400 through 599 contribute.
- [ ] Results contain no more than 10 URLs, ordered by count descending and URL ascending on ties.
- [ ] A log with no 4xx/5xx requests produces an empty ranking, not an error.

### US-4 — Understand traffic by hour (P0)

As a capacity engineer, I want hourly request distribution so that I can see when traffic is concentrated.

Acceptance criteria:

- [ ] Output contains hours 00 through 23 in ascending order.
- [ ] Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] Counts and percentages are based only on valid requests and percentages sum to approximately 100% subject to display rounding.

### US-5 — Measure User-Agent diversity (P0)

As an SRE, I want the share of unique User-Agents so that I can quickly gauge client diversity.

Acceptance criteria:

- [ ] The result includes total distinct User-Agent strings and percentage `100 × unique_user_agent_count / total_valid_requests`.
- [ ] Exact values are used until the cardinality guard is reached.
- [ ] Reaching the guard emits no misleading report, explains the condition on stderr, and exits 4.

### US-6 — Use summaries in pipelines (P0)

As a platform engineer, I want JSON and CSV output so that downstream scripts can consume results reliably.

Acceptance criteria:

- [ ] `--json` emits one valid document matching the documented schema and no terminal markup.
- [ ] `--csv` emits the documented header and deterministically ordered normalized rows.
- [ ] Structured report data uses stdout while warnings/errors use stderr.
- [ ] `--json --csv` is rejected as usage error with exit code 2.

### US-7 — Control malformed input handling (P1)

As a CI owner, I want explicit strict and permissive modes so that I can choose resilience or data-quality enforcement.

Acceptance criteria:

- [ ] Default mode skips malformed lines, reports the count on stderr, and exits 0 if at least one line is valid.
- [ ] `--strict` stops on malformed data and exits 3 with a line number.
- [ ] Empty input, unreadable input, decode failure, or zero valid requests exits 3.
- [ ] Unexpected internal errors exit 1; all public implementations preserve `0/1/2/3/4` exactly.

### US-8 — Read gzip files directly (P2)

As an operator, I want transparent `.gz` input so that I can avoid a separate decompression command.

Acceptance criteria:

- [ ] Deferred until all P0/P1 requirements and performance evidence pass.

## Functional Requirements

### P0 — Must

- FR-1: Accept one optional file path; omission or `-` reads stdin.
- FR-2: Parse documented nginx combined log lines into IP, timestamp/hour, URL, status, and User-Agent.
- FR-3: Compute all four reports in a single pass.
- FR-4: Limit rankings to 10 with deterministic tie-breaking.
- FR-5: Compute hourly percentages as `100 × hourly_request_count / total_valid_requests`.
- FR-6: Compute unique User-Agent share as a percentage of valid requests.
- FR-7: Emit Rich terminal, versioned JSON, or normalized CSV.
- FR-8: Preserve stdout/stderr separation and the `0/1/2/3/4` exit-code contract.
- FR-9: Abort exact User-Agent aggregation at the safe cardinality limit with exit code 4.

### P1 — Should

- FR-10: Track skipped malformed lines and support `--strict`.
- FR-11: Provide `--no-color` and TTY-aware color behavior.
- FR-12: Maintain a reproducible 1 GB performance and peak-memory benchmark.

### P2 — Could

- FR-13: Transparently decompress gzip input while preserving streaming and error semantics.

## Output Contract

The exact command/options, JSON sections, CSV columns, ordering, and exit meanings are defined under `PROJECT_ARCHITECTURE.md` → `CLI Interface`. All implementations and guides must use:

- `0`: successful report.
- `1`: unexpected runtime/internal error.
- `2`: CLI usage error.
- `3`: input/data error.
- `4`: unique-cardinality exhaustion.

Schema changes require an updated PRD and architecture before code changes. JSON breaking changes increment `schema_version`; CSV breaking changes require an explicit release note and compatibility decision.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 | Python 3.11; installable wheel/sdist and console entry point | Clean-venv build/install smoke test |
| NFR-2 | Representative 1 GB in <30 seconds on reference laptop | Recorded benchmark command and environment |
| NFR-3 | No raw-line/record accumulation | Code review plus peak RSS across increasing input sizes |
| NFR-4 | Deterministic results | Repeat-run golden tests and tie fixtures |
| NFR-5 | No persistence or network access | Architecture/code review and isolated integration test |
| NFR-6 | Parser/aggregation coverage ≥90% | Coverage report |

## Assumptions and Dependencies

Input uses the documented nginx combined format and timestamps include an hour parseable by Python. Click and Rich remain Python 3.11 compatible. The reference benchmark laptop is available for final acceptance. Logs can contain sensitive data, so tests use synthetic fixtures.

## Release Acceptance

All P0 stories pass; P1 malformed-input behavior and performance verification pass; packaging works in a clean Python 3.11 environment; public output fixtures and exit codes are frozen; documentation agrees with `PROJECT_ARCHITECTURE.md`; there are no known critical/high security findings.

## Kill Criteria

Pause release and redesign if the reference 1 GB workload cannot meet 30 seconds after measured optimization, if peak memory grows because raw records are retained, if cardinality exhaustion can silently yield approximate output, or if combined-format parsing cannot be made deterministic. Persistence and an HTTP service are not acceptable rescue strategies.
