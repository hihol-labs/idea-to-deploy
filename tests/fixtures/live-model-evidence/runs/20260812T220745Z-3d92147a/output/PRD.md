# Product Requirements Document: nginx-log-report

## Product Summary

`nginx-log-report` gives DevOps/SRE engineers a trustworthy local summary of nginx combined access logs from a file or stdin. In a single streaming pass it reports top client IPs, error-producing URLs, hourly traffic percentages, and unique User-Agent share. Default output is colored terminal text; JSON and CSV are stable automation interfaces.

## Problem Statement

During incidents and routine traffic checks, engineers often need only a small set of signals but must choose between fragile shell commands and heavyweight analytics stacks. The product must return the required signals quickly, locally, and reproducibly without installing or operating a database or server.

## Goals

- Produce the four required exact metrics from nginx combined logs in one pass.
- Process a deterministic 1 GB reference log in under 30 seconds on a documented laptop.
- Support humans and pipelines through terminal, JSON, and CSV outputs.
- Make malformed input, usage problems, unexpected failures, and cardinality exhaustion distinguishable.
- Remain pip-installable, local, stateless, open source, and deliverable in one weekend at $0 cash cost.

## Non-Goals

- Authentication, users, database, HTTP API, server, cloud service, Docker deployment, or Kubernetes.
- Historical retention, cross-run comparisons, dashboards, alerting, or log shipping.
- Arbitrary nginx log-format configuration in the MVP.
- Built-in file following or periodic screen refresh; operators can pipe `tail -F` to stdin.
- Approximate metrics or silent sampling.

## User Stories

### US-1: Inspect dominant client IPs

As an on-call SRE, I want the top 10 client IPs by request count so that I can quickly spot concentrated or abusive traffic.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] A valid file and the same bytes on stdin produce identical IP/count rows.
- [ ] At most 10 rows are returned, ordered by count descending and IP ascending on ties.
- [ ] IPv4 and IPv6 values are supported and malformed addresses do not become keys.

### US-2: Find URLs causing client/server errors

As an SRE investigating an incident, I want the top 10 URLs by combined 4xx/5xx responses so that I can locate failing or misused routes.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Only statuses `400..599` contribute to URL error ranking.
- [ ] Each result includes combined, 4xx, and 5xx counts, with combined equal to their sum.
- [ ] Results are sorted by combined count descending and URL ascending on ties, then truncated to 10.

### US-3: See hourly request distribution

As a DevOps engineer, I want all 24 hourly request buckets as percentages so that I can recognize traffic concentration over the logged day cycle.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] The output contains ordered buckets `00` through `23`, including zero-count hours.
- [ ] Each percentage uses exactly `100 × hourly_request_count / total_valid_requests`.
- [ ] For non-empty valid input, unrounded percentages sum to 100 subject only to floating-point tolerance; for zero valid requests every percentage is `0.0`.
- [ ] The hour is taken from the nginx timestamp as recorded, with no timezone conversion.

### US-4: Measure User-Agent diversity

As a platform engineer, I want the unique User-Agent count and its share of valid requests so that I can estimate client diversity in the inspected stream.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] The unique count is exact and the share is `100 × unique_user_agent_count / total_valid_requests`.
- [ ] A zero-valid-request input reports count `0` and share `0.0`.
- [ ] Repeated User-Agents count once; `-` is treated as a legitimate logged value.
- [ ] A new distinct value beyond the configured limit produces exit `4` and no partial report.

### US-5: Use the report in automation

As a DevOps engineer, I want deterministic JSON and CSV output so that I can consume results in CI jobs and shell pipelines.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `--json` emits one valid schema-versioned JSON document and no ANSI escapes.
- [ ] `--csv` emits the documented fixed header, row order, quoting, and CRLF line endings with no ANSI escapes.
- [ ] `--json` and `--csv` together fail as usage error `2`.
- [ ] Diagnostics are written to stderr and never mixed into report stdout.

### US-6: Control malformed input handling

As an operator, I want default skip-and-count behavior and optional strict parsing so that I can choose between best-effort incident triage and fail-fast auditability.

**Priority:** P1 (Should)

**Acceptance criteria:**

- [ ] Default mode skips malformed nonblank lines and reports their count in terminal, JSON, and CSV.
- [ ] `--strict` stops on the first malformed nonblank line with exit `3` and no partial report.
- [ ] Error diagnostics identify source and line number without echoing sensitive log content.

### US-7: Install and run locally

As an engineer on a Python 3.11 workstation, I want to install through pip and run a single command so that no service deployment is required.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] A built wheel installs in a clean Python 3.11 virtual environment.
- [ ] `nginx-log-report` and `python -m nginx_log_report` expose equivalent behavior.
- [ ] No database, network service, credentials, container, or application environment variables are required.

### US-8: Configure additional log formats

As an nginx administrator with custom fields, I want a format mapping so that I can analyze non-combined logs.

**Priority:** P2 (Could; deferred)

Acceptance requires a separate parser-extension design and is not part of the MVP.

## Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Accept one UTF-8 nginx combined log from `INPUT` path or stdin (`-`, default) and iterate it without bulk loading. |
| FR-2 | P0 | Parse validated IP, timestamp hour, request-target, status, and quoted User-Agent from each valid line. |
| FR-3 | P0 | Produce exact top 10 IPs with deterministic tie ordering. |
| FR-4 | P0 | Produce exact top 10 URLs across 4xx/5xx statuses with combined and family counts. |
| FR-5 | P0 | Produce 24 hourly counts and percentages using `100 × hourly_request_count / total_valid_requests`. |
| FR-6 | P0 | Produce exact unique User-Agent count/share with a bounded distinct-value policy. |
| FR-7 | P0 | Render a complete Rich terminal report by default and honor `--no-color`. |
| FR-8 | P0 | Render stable JSON schema version 1 and the documented tidy CSV schema. |
| FR-9 | P0 | Implement exit codes `0` success, `1` unexpected internal failure, `2` CLI usage error, `3` input/data error, and `4` unique-cardinality exhaustion. |
| FR-10 | P0 | On exit `3` or `4`, write a concise diagnostic to stderr and no partial report to stdout. |
| FR-11 | P1 | Default to skip-and-count malformed nonblank lines; `--strict` fails on the first one. |
| FR-12 | P0 | Support pip installation and equivalent console-script/module entry points on Python 3.11. |
| FR-13 | P2 | Add configurable log-format mappings only after the MVP contract is stable. |

## Output Requirements

Terminal output includes summary counts, top IPs, top error URLs, all 24 hours, and User-Agent count/share. JSON keys, CSV columns, ordering, rounding, and zero-input behavior are normative in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), under `## CLI Interface`. All three renderers consume the same immutable report model.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 Performance | Process a deterministic 1 GB reference fixture in <30 seconds on a documented laptop | Release benchmark records wall time, hardware, OS, Python, fixture seed, and peak RSS |
| NFR-2 Memory | Never retain raw lines/records; explicitly bound exact distinct User-Agents | Iterator spy, aggregation inspection/test, limit-boundary test |
| NFR-3 Determinism | Identical input/options produce identical JSON/CSV bytes | Golden and repeated-run tests |
| NFR-4 Correctness | Exact counts and defined tie behavior; ≥90% line coverage in core modules | Independent expected totals plus unit/integration tests |
| NFR-5 Safety | Log content is untrusted data and cannot trigger shell/markup evaluation | Hostile-input tests and code review |
| NFR-6 Portability | Python 3.11 on Linux and macOS; no GNU-only runtime commands | Clean-environment smoke tests |
| NFR-7 Privacy | No network, telemetry, persistent store, or output of complete malformed lines | Architecture/code inspection |

## Data and Parsing Rules

The accepted combined format, line validity, IP/request-target semantics, recorded-hour handling, status families, zero denominator, encoding, and malformed-line policy are exactly those in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md). A contract change must update that file, this PRD, golden outputs, and user documentation together.

## Success Metrics

- Reference 1 GB benchmark meets `<30 s` before release.
- All P0 acceptance criteria and the exact `0/1/2/3/4` exit-code matrix pass in a clean Python 3.11 environment.
- JSON and CSV golden contracts are stable and ANSI-free.
- No known P0 defect, critical/high security issue, or unexplained metric mismatch remains.

## Dependencies and Constraints

- Python 3.11, Click, Rich, dataclasses, standard library, and pip packaging.
- $0 cash budget, open-source distribution, one-weekend delivery.
- Single local process; no authentication, database, HTTP API, server, cloud, or Kubernetes.
- Exact results for the MVP; approximation requires a new approved decision.

## Release Criteria

The MVP is releasable only when all P0 stories pass, the wheel installs cleanly, all output modes agree semantically, every exit code has an integration test, and the documented reference benchmark meets the target. P1 strict/no-color behavior is included in the weekend plan; P2 items do not block release.

## Kill Criteria

Stop or re-scope rather than ship if correct profiled Python cannot meet 1 GB in 30 seconds on the reference laptop, representative cardinality causes an unacceptable documented memory envelope, or combined-format correctness remains unreliable after the planned parser hardening. Do not hide failure through sampling, partial output, or changed metric definitions.

## Traceability

- Strategy, alternatives, budget, KPIs, and risks: [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md)
- Binding technical/CLI contracts: [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md)
- Sequenced delivery and checks: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- Step-by-step implementation prompts: [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md)
