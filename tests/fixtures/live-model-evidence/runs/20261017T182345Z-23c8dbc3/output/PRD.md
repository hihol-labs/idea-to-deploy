# Product Requirements Document: nginx-stream-report

## Product Summary

`nginx-stream-report` gives DevOps and SRE engineers a fast, local summary of nginx combined access logs. It processes a file or stdin once, retains no history, and outputs colored terminal text, JSON, or CSV. MVP delivery is one weekend with a $0 budget.

## Goals

- Produce the four required views correctly in one streaming pass.
- Process a 1 GB supported log in under 30 seconds on a documented laptop.
- Be dependable in shell pipelines through structured output and explicit exit codes.
- Install through pip on Python 3.11 without infrastructure or external services.

## Non-Goals

- Authentication, authorization, multi-user behavior, or tenancy.
- Database persistence, historical queries, dashboards, HTTP APIs, or servers.
- Cloud services, Kubernetes, Docker-based deployment, or remote telemetry.
- Arbitrary nginx log-format parsing in the MVP.
- Visitor identity inference from IP or User-Agent.

## User Stories

- As a DevOps engineer, I want to stream a large nginx access log from a file or stdin so that I can inspect production traffic without loading the file into memory.
- As an on-call SRE, I want the top 10 client IPs so that I can spot concentrated traffic during an incident.
- As an on-call SRE, I want the top 10 URLs returning 4xx/5xx statuses so that I can prioritize failing routes.
- As a capacity engineer, I want hourly request distribution as a percentage so that I can see traffic shape across the day.
- As a security-minded operator, I want the share of unique User-Agents so that I can quickly assess client diversity without claiming it represents unique users.
- As a pipeline author, I want valid JSON or CSV and stable exit codes so that automation can consume results safely.

## Functional Requirements

### P0 — Must

#### P0.1 Streaming input and parsing

The command accepts a readable file path or stdin and supports newline-delimited nginx combined logs.

Acceptance criteria:

- [ ] File and stdin inputs produce identical report data for identical bytes.
- [ ] The analysis path does not call an unbounded whole-file read.
- [ ] Malformed lines are counted and skipped without echoing their full contents.
- [ ] Zero valid requests produces no report and exits 3.

#### P0.2 Top 10 client IPs

Acceptance criteria:

- [ ] Counts include every valid request.
- [ ] At most 10 entries are returned, ordered by count descending then IP ascending.
- [ ] Text, JSON, and CSV represent the same values.

#### P0.3 Top 10 error URLs

Acceptance criteria:

- [ ] Only status codes 400 through 599 contribute.
- [ ] The logged request target, including query string when present, is the grouping key.
- [ ] At most 10 entries are returned, ordered by count descending then URL ascending.

#### P0.4 Hourly request distribution

Hourly request distribution is the percentage `100 × hourly_request_count / total_valid_requests` for each hour `00`–`23`, based on the timestamp and numeric offset in each valid log record.

Acceptance criteria:

- [ ] All 24 hours appear in deterministic order.
- [ ] Percentages sum to 100 within documented floating-point/rounding tolerance when valid requests exist.
- [ ] An input with no valid requests follows exit code 3 rather than dividing by zero.

#### P0.5 Unique User-Agent share

The metric is `100 × unique_user_agent_count / total_valid_requests`. It is explicitly a ratio of unique strings to requests, not a visitor metric.

Acceptance criteria:

- [ ] Repeated identical User-Agent strings count once in the numerator.
- [ ] Exact cardinality is maintained up to the configured ceiling.
- [ ] Exceeding the ceiling emits no partial report and exits 4 for unique-cardinality exhaustion.

#### P0.6 Output formats

Acceptance criteria:

- [ ] Default output has four labeled Rich sections and uses color automatically only on a TTY.
- [ ] `--json` emits one parseable schema-versioned JSON object without ANSI escapes.
- [ ] `--csv` emits parseable normalized CSV with header `report,key,count,percentage,rank` and no ANSI escapes.
- [ ] `--json` and `--csv` are mutually exclusive usage options.

#### P0.7 Process contract

Acceptance criteria:

- [ ] Exit codes implement the complete `0/1/2/3/4` contract documented in `PROJECT_ARCHITECTURE.md`.
- [ ] Diagnostics use stderr; report data uses stdout.
- [ ] Expected failures do not show a traceback by default.

#### P0.8 Packaging and performance

Acceptance criteria:

- [ ] A clean Python 3.11 environment can install the built wheel through pip.
- [ ] The installed `nginx-stream-report` command exposes help and version.
- [ ] The deterministic 1 GB benchmark completes in under 30 seconds on the documented reference laptop.

### P1 — Should

- Transparently read gzip-compressed input while preserving streaming behavior.
- Include a concise malformed-line warning with counts and limited line-number examples.
- Publish wheel and source distribution metadata suitable for an open-source package index.

### P2 — Could

- Allow a configurable top-N value while keeping 10 as default.
- Support explicitly configured nginx formats.
- Offer optional approximate cardinality as a separately named metric/mode, never silently.

## CLI and Output Contract

The authoritative commands, options, inputs, output schemas, and exit codes are in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. Requirements in this PRD must not diverge from that contract.

## Performance and Quality Requirements

| Requirement | Target | Evidence |
|---|---|---|
| Throughput | 1 GB in <30 s | Recorded benchmark on named hardware |
| Package code coverage | >=90% | pytest coverage report |
| Determinism | Stable tie order and schemas | Repeated renderer tests |
| Memory behavior | No input retention; explicit UA ceiling | Streaming guard tests and exhaustion test |
| Compatibility | Python 3.11 | Clean-environment wheel smoke test |

## Privacy and Security Requirements

- No network calls, telemetry, database, or implicit report files.
- Log fields are treated as untrusted data and are never executed, fetched, or interpreted as formatting markup.
- Full malformed log lines are not printed in diagnostics.
- Documentation states that IPs, URLs, and User-Agents in output may be sensitive.

## Success Metrics

The MVP succeeds when all P0 acceptance criteria pass, the reference benchmark meets its target, the package installs cleanly, and at least one DevOps/SRE user can complete both a terminal and a pipeline workflow without undocumented steps.

## Kill Criteria

- Stop or change implementation language if profiling shows Python cannot meet 1 GB in 30 seconds within the weekend.
- Re-scope unique User-Agent reporting if exactness cannot be protected by a clear, tested ceiling.
- Defer all P1/P2 work if it threatens P0 correctness or release evidence.

## Dependencies

- `PROJECT_ARCHITECTURE.md` is the technical source of truth.
- `IMPLEMENTATION_PLAN.md` orders work and verification.
- `STRATEGIC_PLAN.md` owns positioning, prioritization, budget, and overall Definition of Done.

