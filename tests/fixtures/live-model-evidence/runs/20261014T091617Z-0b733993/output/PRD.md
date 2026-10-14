# Product Requirements Document: Nginx Stream Analyzer

## 1. Product Summary

Nginx Stream Analyzer is a local, stateless Python 3.11 CLI that turns a supported nginx combined access-log stream into four operational summaries. It serves DevOps/SRE users who need fast answers without deploying an observability stack or uploading logs. The MVP is pip-installable, open source, $0 to operate, and deliverable in one weekend.

## 2. Goals and Non-Goals

### Goals

- Process a 1 GB supported-format access log in under 30 seconds on the designated laptop.
- Report top 10 client IPs, top 10 URLs by 4xx/5xx errors, hourly request distribution, and unique User-Agent share.
- Offer colored terminal output and pipeline-safe JSON/CSV.
- Read a file or stdin in one pass without retaining raw records.
- Give automation a stable, complete 0/1/2/3/4 exit-code contract.

### Non-Goals

- Authentication, a database, saved history, an HTTP API, or a long-running server.
- Cloud execution, Docker as a runtime requirement, or Kubernetes.
- General-purpose log querying, dashboards, alerts, or multi-file correlation.
- Arbitrary nginx format inference in the MVP.
- Approximate cardinality presented as exact.

## 3. Personas and Jobs

| Persona | Job to be done | Success signal |
|---|---|---|
| On-call SRE | Identify who is generating traffic and which routes are failing | Useful ranked summary from a production log in one command |
| DevOps engineer | Feed repeatable metrics to shell tooling | Stable JSON/CSV and exit status, no stdout contamination |
| Platform engineer | Triage locally without new infrastructure | Pip install and local run with no service/configuration setup |

## User Stories

- As a on-call SRE, I want the top 10 client IPs by valid request count so that I can spot dominant or suspicious sources. **Priority: P0.**
- As a on-call SRE, I want the top 10 URLs ranked by combined 4xx/5xx count so that I can focus incident investigation on failing routes. **Priority: P0.**
- As a DevOps engineer, I want hourly request distribution as a percentage so that traffic shape is comparable across logs of different sizes. **Priority: P0.**
- As a platform engineer, I want the share of unique nonempty User-Agents so that I can estimate client diversity while receiving an explicit failure if exact tracking exceeds its bound. **Priority: P0.**
- As a DevOps engineer, I want JSON and CSV output with stable schemas so that I can consume reports in pipelines. **Priority: P0.**
- As a terminal user, I want a readable colored default report that becomes plain when redirected so that interactive and scripted use are both safe. **Priority: P0.**
- As a shell user, I want file and stdin input so that I can analyze live, rotated, or decompressed streams. **Priority: P0.**
- As an operator of rotated logs, I want direct gzip support so that I can skip an external decompression command. **Priority: P1.**
- As a user with custom nginx formats, I want configurable parsing so that I can analyze non-combined logs. **Priority: P2.**

## 5. P0 Functional Requirements and Acceptance Criteria

### FR-1: Streaming input and parsing

The command accepts one path or stdin (`-`/omitted), parses the documented nginx combined format in one pass, and does not retain raw lines.

- [ ] A supported fixture produces identical results from file and stdin.
- [ ] Some malformed lines are counted/skipped without corrupting valid aggregates and the command exits 0.
- [ ] An input containing zero valid requests exits 3 and writes a concise diagnostic only to stderr.
- [ ] Missing/unreadable files exit 1; invalid option combinations exit 2.

### FR-2: Top client IPs

Count client IPs over valid requests and return at most 10.

- [ ] Results sort by count descending, then IP ascending on ties.
- [ ] Fewer than 10 distinct IPs return only those present.
- [ ] Counts reconcile with the supported fixture.

### FR-3: Top error URLs

Count request targets only for statuses 400 through 599 inclusive and return at most 10.

- [ ] Status 399 is excluded; 400, 499, 500, and 599 are included; 600 is excluded.
- [ ] Results sort by error count descending, then URL ascending on ties.
- [ ] A log without errors returns an empty ranked list, not a failure.

### FR-4: Hourly distribution

Create 24 hour buckets using the hour encoded by the nginx timestamp and its offset. The percentage formula is exactly `100 × hourly_request_count / total_valid_requests`.

- [ ] All 24 buckets are emitted in hour order, including zeros.
- [ ] Unrounded percentages sum to 100 within floating-point tolerance when valid requests exist.
- [ ] Display/serialization rounds to two decimals only at the output boundary.

### FR-5: Unique User-Agent share

Count exact distinct nonempty User-Agent strings and report `100 × unique_nonempty_user_agent_count / total_valid_requests`.

- [ ] Repeated identical User-Agents count once; empty/missing values count zero distinct entries.
- [ ] All valid requests, including those with empty User-Agent, remain in the denominator.
- [ ] Exceeding `--ua-limit` emits no successful report, diagnoses unique-cardinality exhaustion on stderr, and exits 4.

### FR-6: Output modes

Default output is a Rich terminal report; `--json` and `--csv` are mutually exclusive alternatives.

- [ ] Terminal output contains counts and all four result sections; color is disabled for non-TTY output or `--no-color`.
- [ ] JSON is a single parseable schema-versioned object with numeric counts/percentages.
- [ ] CSV uses exactly `metric,rank,key,count,percentage,unit` and is parseable by Python's `csv` module.
- [ ] Diagnostics never appear on stdout in JSON or CSV mode.

### FR-7: Complete process contract

All executions follow this mapping: `0` successful report; `1` operational I/O failure; `2` CLI usage/configuration error; `3` input/data failure or zero valid requests; `4` unique-cardinality exhaustion.

- [ ] Integration tests exercise each of codes 0/1/2/3/4 through the installed console entry point.
- [ ] `--help` and `--version` exit 0 without opening input.
- [ ] Conflicting `--json --csv` returns 2 with no report on stdout.

## 6. P1 and P2 Requirements

| ID | Priority | Requirement | Acceptance boundary |
|---|---|---|---|
| FR-8 | P1 | Direct `.gz` input | Same aggregate/output semantics; benchmark separately from raw input |
| FR-9 | P2 | Explicit custom log-format grammar | User supplies a validated format; unsupported fields fail with code 2 |
| FR-10 | P2 | Additional `--top N` control | Positive bounded value; defaults to 10; schema remains stable |

P1/P2 work begins only after every P0 criterion and the performance gate passes.

## 7. Output Data Contract

JSON schema version `1` includes `counts`, `top_ips`, `top_error_urls`, `hourly_distribution`, and `user_agents`. CSV normalizes all values under `metric,rank,key,count,percentage,unit`. Ordering is deterministic. Percentages are numeric and expressed on a 0–100 scale, never as an unscaled fraction.

## 8. Non-Functional Requirements

| Area | Requirement | Evidence |
|---|---|---|
| Performance | 1 GB supported fixture in <30 s on designated laptop | Recorded hyperfine/time run and environment metadata |
| Memory | One-pass processing; no raw-line retention; exact UA ceiling | Peak RSS measurement and exhaustion test |
| Portability | Python 3.11; clean pip install | Fresh virtual-environment smoke test |
| Reliability | Deterministic ordering and 0/1/2/3/4 exits | Golden and subprocess tests |
| Privacy | No network, telemetry, persistence, or raw malformed-line echo | Static review plus behavior tests |
| Security | Escape terminal control sequences; never execute log content | Malicious fixture test |

## 9. Assumptions and Dependencies

- P0 supports the documented nginx combined access-log grammar in UTF-8.
- The 1 GB target is a file-size target, not a request-count promise.
- The benchmark laptop and cache conditions will be recorded before acceptance.
- Click and Rich are runtime dependencies; dataclasses come from Python 3.11.
- An exact UA ceiling is preferable to an undisclosed approximation.

## 10. Release and Kill Criteria

Release only when every P0 criterion passes from the installed package and the benchmark is below 30 seconds. Stop or revise scope if profiling cannot reach the target in Python, if the exact-cardinality safety bound makes representative inputs unusable, or if delivery would require a database, API, cloud, or post-weekend schedule. See `PROJECT_ARCHITECTURE.md` for decisions and `IMPLEMENTATION_PLAN.md` for executable sequencing.
