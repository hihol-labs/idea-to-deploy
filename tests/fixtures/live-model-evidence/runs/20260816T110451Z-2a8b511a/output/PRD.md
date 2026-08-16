# Product Requirements Document: nginx-stream-stats

## Product Summary

`nginx-stream-stats` is a local Python 3.11 command-line tool for quickly extracting four operational views from nginx combined-format access logs. It streams files or stdin, defaults to colored terminal output, and supports stable JSON and CSV output for pipelines. It is stateless, open source, installable with pip, costs $0 to operate, and targets delivery in one weekend.

## Problem Statement

During incidents and routine checks, DevOps/SRE engineers often need a bounded answer from a large local log before a full observability platform is available or justified. Ad hoc shell pipelines are easy to misquote and often scan repeatedly. Existing analytics stacks solve broader problems but add services, persistence, configuration, or UI. The product must return a correct, explicit report from one local streaming pass.

## Goals

- Process conventional nginx combined-format logs from files or stdin without loading raw input into memory.
- Report top-10 IPs, top-10 URLs by combined 4xx/5xx count, 24 hourly request percentages, and exact unique User-Agent share.
- Produce semantically equivalent Rich terminal, JSON v1, and CSV v1 outputs.
- Process a representative 1 GB fixture in under 30 seconds on a documented laptop baseline.
- Fail visibly when input, usage, absence of valid data, or exact-cardinality limits prevent a valid report.

## Non-Goals

- Authentication, authorization, accounts, database, historical storage, HTTP API, or server mode.
- Cloud services, telemetry, Docker as a runtime requirement, or Kubernetes.
- Dashboards, interactive TUI, HTML reports, log tail-following, distributed processing, or cross-run comparison.
- Arbitrary nginx `log_format` support in P0.
- Approximate or silently sampled statistics.

## Personas

1. **On-call SRE:** needs an immediate, trustworthy incident snapshot from a host log.
2. **DevOps engineer:** needs useful analytics where a centralized stack is unavailable or excessive.
3. **Automation engineer:** needs stable stdout schemas and exit statuses for scheduled or piped workflows.

## User Stories

### US-1 — Stream local input

As an on-call SRE, I want to analyze one or more nginx logs or stdin in one command so that I can inspect traffic without copying data into another service.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] With no path, the command consumes stdin; with paths, it processes them in argument order.
- [ ] A 1 GB input is iterated incrementally and raw records are not retained.
- [ ] The supported combined format is documented and representative valid lines parse IPv4, IPv6, timezone, target, status, and User-Agent correctly.
- [ ] Malformed lines are counted and skipped; a mix of valid/malformed lines exits 0 and reports both counts.
- [ ] If zero valid records remain, stdout has no report and the command exits 3.

### US-2 — Find dominant clients

As an SRE investigating load, I want the ten IPs with the most valid requests so that I can spot dominant sources.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Each valid request increments exactly one client-IP count.
- [ ] At most ten results are ordered by count descending, then IP string ascending for ties.
- [ ] Fewer than ten distinct IPs returns all available IPs without padding.
- [ ] Terminal, JSON, and CSV modes expose identical ranks and counts.

### US-3 — Find error-prone URLs

As an on-call engineer, I want the ten request targets producing the most 4xx/5xx responses so that I can prioritize failing routes.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Only status codes 400 through 599 increment the error URL counter.
- [ ] 1xx, 2xx, and 3xx requests do not appear in this ranking.
- [ ] At most ten targets are ordered by error count descending, then target ascending for ties.
- [ ] Query strings remain part of the request-target key, matching the source log.

### US-4 — Understand hourly distribution

As a DevOps engineer, I want request distribution across all 24 logged hours so that I can see traffic concentration.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Output includes hours 00 through 23, including zero-count hours.
- [ ] Each hour uses the timestamp hour with its logged UTC offset; no host-timezone conversion occurs.
- [ ] Each percentage uses exactly `100 × hourly_request_count / total_valid_requests`; it is not an unscaled fraction.
- [ ] Machine output rounds numeric percentages to no more than six decimal places and includes the underlying counts.

### US-5 — Measure User-Agent uniqueness

As an SRE checking client diversity or bot activity, I want the exact unique User-Agent count and its share of valid requests so that I can judge whether clients are repetitive or diverse.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] The exact unique count treats each distinct parsed User-Agent string, including normalized `-`, as one value.
- [ ] Share percentage equals `100 × unique_user_agent_count / total_valid_requests` and both counts are output.
- [ ] Exceeding the configured exact-cardinality ceiling yields no partial report, identifies the dimension on stderr, and exits 4.

### US-6 — Use human-readable terminal output

As a human operator, I want colored, readable terminal tables by default so that I can scan the results quickly.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Default output contains a summary and all four required analyses.
- [ ] `--no-color` removes ANSI color without changing data.
- [ ] Diagnostics go to stderr, separate from report stdout.

### US-7 — Integrate with pipelines

As an automation engineer, I want JSON and CSV modes so that downstream scripts can consume the same report reliably.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `--json` emits only a valid JSON schema-version-1 object to stdout.
- [ ] `--csv` emits only the documented schema-version-1 rows to stdout using standard quoting.
- [ ] `--json` and `--csv` together are rejected as a usage error with exit 2.
- [ ] Neither machine mode emits Rich/ANSI decoration or progress messages.

### US-8 — Read compressed logs

As a DevOps engineer, I want `.gz` logs opened transparently so that I do not need a decompression pipeline.

**Priority:** P1 (Should)

**Acceptance criteria:**

- [ ] A `.gz` suffix selects streaming gzip decompression.
- [ ] Parsing, metrics, outputs, and exits match equivalent plain text input.

### US-9 — Choose a different top limit

As an operator, I want a configurable top-N so that I can inspect more or fewer ranked items.

**Priority:** P2 (Could)

**Acceptance criteria:**

- [ ] A future positive `--top` value applies identically to IP and error-URL rankings.
- [ ] The default remains 10 and schema compatibility is preserved.

### US-10 — Parse custom nginx formats

As an operator with a nonstandard nginx configuration, I want to map my `log_format` fields so that I can use the same metrics.

**Priority:** P2 (Could)

**Acceptance criteria:**

- [ ] Any future format mapping validates all fields needed for the four metrics before processing.
- [ ] Unsupported mappings fail as usage errors rather than guessing.

## Functional Requirements

### P0 — Must

| ID | Requirement |
|---|---|
| FR-001 | Expose the `nginx-stream-stats [OPTIONS] [INPUT]...` console command through pip packaging. |
| FR-002 | Parse the documented conventional nginx combined format from files/stdin in one pass. |
| FR-003 | Count valid and malformed lines and never include malformed lines in any denominator. |
| FR-004 | Return deterministic top-10 IPs from all valid requests. |
| FR-005 | Return deterministic top-10 request targets whose status is 400–599. |
| FR-006 | Return 24 hourly counts and percentages computed with `100 × hourly_request_count / total_valid_requests`. |
| FR-007 | Return exact unique User-Agent count and `100 × unique_user_agent_count / total_valid_requests`. |
| FR-008 | Enforce `--max-unique` separately for IP, error-URL, and User-Agent cardinalities, failing closed with exit 4. |
| FR-009 | Render one finalized report as colored Rich text by default, JSON v1 with `--json`, or CSV v1 with `--csv`. |
| FR-010 | Keep stdout machine-parseable and send warnings/errors to stderr. |
| FR-011 | Implement the complete exit contract: `0` success, `1` runtime/input/output failure, `2` usage error, `3` zero valid requests, `4` unique-cardinality exhaustion. |

### P1 — Should

| ID | Requirement |
|---|---|
| FR-101 | Stream gzip-compressed input selected by `.gz` suffix. |

### P2 — Could

| ID | Requirement |
|---|---|
| FR-201 | Support a positive configurable top-N while retaining 10 as default. |
| FR-202 | Support an explicitly validated mapping for custom nginx log formats. |

## Output Contracts

The JSON and CSV field contracts, deterministic sorting, rounding policy, and stdout/stderr split are normative in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. Renderer tests must demonstrate that all formats originate from the same report data.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-001 | Representative 1 GB input completes in <30 seconds on a documented laptop. | Timed benchmark recording hardware, fixture cardinalities, cache conditions, elapsed time, and peak RSS |
| NFR-002 | Raw log lines are not retained; work is one pass. | Static review plus a memory-profile test with increasing input size and bounded declared cardinality |
| NFR-003 | Product supports Python 3.11 and installs via pip into a clean environment. | Build wheel/sdist, install wheel, run `--version` and smoke fixture |
| NFR-004 | Product performs no network calls or telemetry. | Dependency/static review and isolated integration test |
| NFR-005 | Parser, aggregate, and output contracts have at least 90% line coverage. | Coverage command in `IMPLEMENTATION_PLAN.md` |
| NFR-006 | Logs and reports are treated as sensitive local data. | Confirm diagnostics do not print full malformed records and docs contain privacy warning |

## Exit-Code Acceptance Matrix

| Code | Required scenario |
|---:|---|
| `0` | Valid report, including input that also contains malformed lines |
| `1` | Unreadable input, decode failure, or report write/runtime failure |
| `2` | Invalid/incompatible CLI arguments or configuration |
| `3` | Empty input or all records malformed, leaving zero valid requests |
| `4` | Exact unique-cardinality ceiling exhausted for IPs, error URLs, or User-Agents |

## Release Acceptance

- [ ] All P0 acceptance criteria pass on Python 3.11.
- [ ] Cross-format golden fixtures agree on all counts, rankings, and percentages.
- [ ] All five exit codes are exercised by CLI integration tests.
- [ ] Wheel installation smoke test passes in a clean environment.
- [ ] Representative 1 GB benchmark meets the target with recorded evidence.
- [ ] README documents format assumptions, schemas, privacy, and resource failure behavior.
- [ ] The exact candidate satisfies the project's current Verification Loop acceptance protocol.

## Kill Criteria

Pause and re-scope rather than ship if any of these is true:

- After profiling, the representative 1 GB fixture cannot complete under 30 seconds on the documented baseline without abandoning Python 3.11 or exact required semantics.
- Exact required metrics cannot be bounded safely and the product would need silent sampling/approximation.
- Real target logs cannot be parsed reliably without expanding custom-format work beyond the one-weekend budget.
- JSON/CSV correctness would be sacrificed to preserve terminal presentation or speed.

## Dependencies and Traceability

Architecture and CLI schemas are specified in `PROJECT_ARCHITECTURE.md`. Business priority and RICE rationale are in `STRATEGIC_PLAN.md`. Implementation files, checks, and order are in `IMPLEMENTATION_PLAN.md`.
