# Product Requirements Document: Nginx Stream Analytics CLI

## 1. Summary

Nginx Stream Analytics CLI gives DevOps/SRE engineers a fast, local first-pass summary of nginx access logs. It streams a file or stdin once, emits four exact reports, and supports human-readable terminal output plus stable JSON and CSV for pipelines. It is not an observability service or historical analytics store.

## 2. Problem and Outcome

During incidents, engineers often need to answer who is generating traffic, which URLs are failing, when requests concentrate, and how diverse client User-Agents are. Shell one-liners are fragile, while hosted or database-backed stacks take too long to deploy for an isolated log. The desired outcome is a trustworthy report from up to 1 GB in under 30 seconds on a documented laptop, with no infrastructure and explicit failure semantics.

## 3. Goals

- Analyze a standard nginx Combined Log Format stream in a single local process.
- Return exact top-10 IPs, exact top-10 URLs with 4xx/5xx statuses, 24 hourly buckets, and unique User-Agent share.
- Provide default Rich terminal output and pipeline-safe JSON/CSV.
- Make malformed data, unreadable input, internal failures, and cardinality exhaustion distinguishable by exit code.
- Ship as a Python 3.11 pip-installable package within one weekend and $0 cash budget.

## 4. Non-goals

- Authentication or user accounts.
- Database, retained history, search index, or cache between runs.
- HTTP API, server, daemon, file-follow mode, cloud service, Docker deployment, or Kubernetes.
- Dashboards, alerts, correlations across files, arbitrary nginx format discovery, or approximate metrics.
- Replacement for GoAccess, Elastic/Kibana, AWStats, or general-purpose shell tools outside this focused workflow.

## 5. Personas

- **On-call SRE:** needs a rapid, legible report during incident triage.
- **Platform engineer:** needs stable structured output for a larger shell/CI pipeline.
- **DevOps generalist:** needs useful analytics without installing or operating a stack.

## User Stories

- As a SRE on call, I want to stream a large nginx log from a path so that I can identify the ten most active client IPs without loading the file into memory. **Priority: P0.**
- As a SRE on call, I want the ten URLs with the most 4xx/5xx responses so that I can focus incident investigation on failing routes. **Priority: P0.**
- As a platform engineer, I want 24 hourly request percentages calculated as `100 × hourly_request_count / total_valid_requests` so that I can compare time-of-day concentration without another transform. **Priority: P0.**
- As a DevOps engineer, I want the unique User-Agent count and percentage share so that I can quickly estimate client diversity. **Priority: P0.**
- As a platform engineer, I want JSON or CSV on stdout with diagnostics isolated on stderr so that I can safely compose the command in pipelines. **Priority: P0.**
- As a cautious operator, I want the run to fail explicitly when exact distinct-key state exceeds its configured ceiling so that I never mistake partial or approximate data for exact results. **Priority: P0.**
- As a terminal user, I want readable colored tables that automatically disable color when redirected so that interactive output is easy to scan and redirected output remains clean. **Priority: P0.**
- As a repeat user, I want configurable top-N and timestamp timezone normalization so that I can adapt the summary after the MVP. **Priority: P1.**
- As an engineer with archived logs, I want gzip input and configurable nginx log formats so that I can analyze more sources directly. **Priority: P2.**

### P0 acceptance criteria

#### Streaming and top client IPs

- [ ] A file path and `-`/omitted stdin input produce equal report values for identical bytes.
- [ ] Every valid record increments exactly one client-IP bucket and total request count.
- [ ] At most ten rows are emitted, ordered by count descending and IP ascending for ties.
- [ ] A 1 GB reference fixture finishes under 30 seconds on the documented laptop.

#### Error URL ranking

- [ ] Only status codes 400–599 contribute to error-URL counts.
- [ ] 1xx, 2xx, 3xx, and invalid status fields do not silently enter the ranking; invalid records fail parsing.
- [ ] At most ten URLs are emitted, with deterministic count-descending/key-ascending ordering.

#### Hourly distribution

- [ ] Output contains 24 ordered buckets `00` through `23`, including zero-count hours.
- [ ] Each percentage is `100 × hourly_request_count / total_valid_requests`, not an unscaled fraction.
- [ ] Percentages sum to 100% within documented floating-point tolerance when total valid requests is positive.
- [ ] Empty valid input reports zero for every hour without division by zero.

#### User-Agent uniqueness

- [ ] Each distinct parsed User-Agent contributes once to the unique count.
- [ ] Share percentage equals `100 × unique_user_agent_count / total_valid_requests`.
- [ ] Empty valid input produces unique count 0 and share 0.0%.

#### Output formats

- [ ] With no format flag, four labeled Rich terminal sections are written to stdout.
- [ ] `--json` writes one parseable object matching schema version `1.0` and no ANSI escapes.
- [ ] `--csv` writes a parseable long-form table with columns `report,rank,key,count,percentage` and no ANSI escapes.
- [ ] `--json --csv` is rejected as usage error 2.
- [ ] Equivalent terminal, JSON, and CSV reports contain the same counts and percentages.

#### Failure safety and cardinality

- [ ] The first malformed or invalid-UTF-8 line produces an actionable line-number diagnostic, no report, and exit 3.
- [ ] An unreadable/missing input produces stderr diagnostics and exit 2.
- [ ] Inserting a new IP, error URL, or User-Agent beyond `--max-unique` produces no report and exit 4.
- [ ] Unexpected runtime failure produces exit 1; successful reports, help, and version use exit 0.

## 7. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept zero or one input path; zero or `-` means stdin. |
| FR-02 | Parse nginx Combined Log Format deterministically and fail fast on malformed input. |
| FR-03 | Compute all metrics in one pass without persisting raw records. |
| FR-04 | Emit top-10 client IP counts with deterministic ties. |
| FR-05 | Emit top-10 request targets whose statuses are 400–599. |
| FR-06 | Emit 24 request-count and percentage buckets using `100 × hourly_request_count / total_valid_requests`. |
| FR-07 | Emit exact unique User-Agent count and percentage share. |
| FR-08 | Provide mutually exclusive terminal, JSON, and CSV renderers. |
| FR-09 | Enforce positive `--max-unique` independently for exact IP, error-URL, and User-Agent state. |
| FR-10 | Implement the complete exit contract `0/1/2/3/4` defined in `PROJECT_ARCHITECTURE.md`. |

### P1 — Should ship after MVP

| ID | Requirement |
|---|---|
| FR-11 | Allow a configurable top-N while retaining deterministic ordering. |
| FR-12 | Allow an explicit output timezone for hourly buckets. |

### P2 — Could ship

| ID | Requirement |
|---|---|
| FR-13 | Read gzip-compressed files with the same metrics and failure behavior. |
| FR-14 | Accept a constrained configurable nginx log-format mapping. |

## 8. Non-functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | Process the reproducible 1 GB fixture in under 30 seconds on the named laptop. |
| NFR-02 | Retain no raw input records and make cardinality growth explicitly bounded. |
| NFR-03 | Support Python 3.11 and installation from a built wheel with pip. |
| NFR-04 | Keep stdout format-pure; write diagnostics only to stderr. |
| NFR-05 | Never use network access, persist logs, or interpret input as code/markup. |
| NFR-06 | Cover parser, aggregator, renderers, and CLI branches at least 90%. |

## 9. Output and Compatibility Contract

The CLI surface, JSON object, CSV columns, tie rules, parser policy, and `0/1/2/3/4` exits are normative in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. Schema-breaking JSON/CSV changes require a major schema version and an explicit PRD update. Human wording may evolve without changing metric meanings.

## 10. Analytics Definitions

- `total_valid_requests`: number of successfully parsed input records.
- `top_ips`: up to ten distinct client IPs ranked by request count.
- `top_error_urls`: up to ten request targets ranked by count among records whose status is 400–599.
- `hourly_request_count`: valid records whose parsed source-local timestamp hour matches the bucket.
- Hourly request distribution percentage: `100 × hourly_request_count / total_valid_requests`.
- `unique_user_agent_count`: exact cardinality of parsed User-Agent strings, including one literal absent-value bucket when logged as `-`.
- Unique User-Agent share: `100 × unique_user_agent_count / total_valid_requests`.

All percentages are 0.0 when the denominator is zero and are rendered as percentage points, not fractions.

## 11. Success Metrics and Release Gates

- All P0 acceptance criteria pass against fixtures and CLI integration tests.
- The built wheel installs and the console script works in a clean Python 3.11 environment.
- The benchmark evidence meets 1 GB in under 30 seconds on the documented laptop.
- No critical/high security findings or known silent-correctness defects remain.
- JSON/CSV schemas and complete exit behavior are documented and regression-tested.

## 12. Kill Criteria

Pause release if exact output cannot meet the reference performance target after evidence-led optimization, if supported format parsing is ambiguous, if cardinality protection can only be achieved through silent approximation, or if output formats disagree. Re-scope before adding services or persistence.

## 13. Dependencies

`PROJECT_ARCHITECTURE.md` is the normative technical design. `IMPLEMENTATION_PLAN.md` maps these requirements to files and verification. `STRATEGIC_PLAN.md` records priority and success rationale.
