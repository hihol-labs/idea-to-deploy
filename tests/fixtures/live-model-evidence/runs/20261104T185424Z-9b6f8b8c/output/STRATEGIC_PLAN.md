# Strategic Plan: Nginx Lens

## 1. Idea

Nginx Lens is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx combined access logs once, aggregates in memory, and emits a final report at EOF: top ten IPs, top ten URL paths by combined 4xx/5xx errors, hourly request percentages, and unique User-Agent share. Rich terminal output is the default; JSON and CSV serve pipelines. No telemetry or network access is needed.

The specification is the deliverable for this session. Product code, performance measurements, publication, and independent review are future work. See [PRD.md](PRD.md) for acceptance criteria and [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for the executable interface contract.

## 2. Target Audience

| Persona | Role | Pain | Response |
|---|---|---|---|
| On-call SRE | Incident triage | Needs a quick local view of a copied log | One command and deterministic top ten tables |
| Platform engineer | Automation | Handwritten awk scripts drift and lack schemas | Stable JSON/CSV and documented exit codes |
| Service owner | Capacity review | Full log platforms cost setup time | Hourly percentages from a file or stdin |

## 3. Competitive Analysis

These are qualitative positioning comparisons, not current feature or pricing audits; no external research was performed.

| Alternative | Approach | Trade-off for this brief | Our difference |
|---|---|---|---|
| GoAccess | Dedicated access-log reporting | A broader reporting surface than these four metrics | Small Python package with a tightly specified pipeline contract |
| Logstash/Elastic/Kibana | Ingest, index, and visualize logs | Persistent infrastructure exceeds this local, zero-budget scope | No service or index lifecycle |
| AWStats | Periodic web traffic statistics | Scheduled report workflow differs from incident-time stdin analysis | Single invocation with structured stdout |
| grep/awk | Shell filtering and counting | Per-team scripts require repeated correctness work | Tested parsing, percentages, ties, and error handling |

## 4. Unique Value Proposition

Get four incident-ready nginx summaries locally with exact counts and predictable pipeline output, without operating a log platform.

## 5. Business Model

Free open-source utility under the MIT license. No paid tiers, ads, accounts, or monetization. LTV and CAC are not meaningful financial targets; adoption comes from an existing team workflow. Maintainer time is voluntary. Package and repository names must be checked before any eventual publication; `nginx-lens` is the planned distribution and command name, not a claim of registry availability.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved local runtime |
| Command parsing | Click | Typed flags, help, validation |
| Terminal | Rich | Legible tables and TTY-aware colors |
| Internal contracts | dataclasses | Explicit records and reports |
| Aggregation/export | Standard library | Counters, sets, datetime, json, csv |
| Packaging/testing | setuptools, pip; pytest as dev dependency | Installable wheel and focused tests |

## 7. Timeline

| Window | Stage | Outcome |
|---|---|---|
| Saturday morning | Steps 1–3 | CLI contract, parser, aggregation |
| Saturday afternoon | Steps 4–6 | Three renderers |
| Sunday | Steps 7–8 | Failure tests, benchmark, local wheel rehearsal |

Budget approximately 16 focused engineering hours, excluding optional enhancements. [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) specifies dependencies and checks.

## 8. KPIs

These are targets, not observed results. Adoption is assessed voluntarily without embedded telemetry.

| Metric | 1 month | 3 months | 6 months |
|---|---|---|---|
| Correctness | All P0 fixtures pass | No unresolved count regressions | Same contract retained |
| Throughput | 1,000,000,000-byte fixture under 30 seconds on recorded laptop | Maintain target | Maintain target |
| Peak RSS | Target at most 512 MiB on defined benchmark | Maintain target | Maintain target |
| Useful local adoption | 1 team trial | 3 voluntary reports | 5 voluntary reports |

Hourly request distribution is `100 × hourly_request_count / total_valid_requests`. Unique User-Agent share is `100 × distinct_nonmissing_user_agents / total_valid_requests`. Both use valid requests as the denominator and equal zero for empty valid input. Architecture defines rounding and missing agents.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python parsing misses throughput target | Medium | High | Benchmark bounded fixtures early; profile before optimizing |
| High unique cardinality consumes RAM | High | High | Exact combined key budget and exit 4; never silently approximate |
| Custom log format misparsed | High | High | Support combined format only; malformed-line diagnostics |
| Long/untrusted log fields break output | Medium | Medium | Bounded line reads; escaped terminal cells; literal CSV fields |
| Weekend scope expansion | Medium | High | Ship Must features first; defer Should/Could |

## 10. Budget

| Item | Monthly cash | Comment |
|---|---|---|
| Runtime and libraries | $0 | Open-source dependencies |
| Hosting/database | $0 | None required |
| Development hardware | $0 incremental | Existing laptop |
| Labor | $0 cash | Approximately 16 volunteer hours; opportunity cost exists |
| Total | $0 | No paid infrastructure or services |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Combined-format file/stdin parser | Must / P0 | Every summary depends on valid records |
| Exact four-metric aggregation with key cap | Must / P0 | Core value and bounded failure behavior |
| Colored terminal report | Must / P0 | Default interaction |
| JSON export | Must / P0 | Required pipeline format |
| CSV export | Must / P0 | Required pipeline format |
| Deterministic diagnostics and exits | Must / P0 | Automation cannot consume misleading success |
| gzip input | Should / P1 | Convenient for rotated logs; deferred beyond weekend |
| Configurable top-N | Could / P2 | Fixed top ten satisfies the brief |
| Auth, DB, HTTP API, server, cloud, Kubernetes | Won't | Violates approved boundaries |
| Watch/follow mode and arbitrary log formats | Won't | EOF reports and one parser keep MVP small |

### RICE Scoring

Estimates use confidence as a fraction: score = Reach × Impact × Confidence / Effort. Reach is a relative 1–10 scale, not measured users. One person-day means eight hours. Shared integration work is covered in the weekend plan, so feature estimates are not a separate schedule commitment.

| Feature | Reach | Impact | Confidence | Effort (days) | Score |
|---|---|---|---|---|---|
| Parser | 10 | 5 | 80% | 0.30 | 133.33 |
| Aggregation and cap | 10 | 5 | 80% | 0.35 | 114.29 |
| Terminal | 10 | 4 | 80% | 0.30 | 106.67 |
| JSON | 8 | 4 | 80% | 0.25 | 102.40 |
| CSV | 7 | 3 | 80% | 0.25 | 67.20 |
| Diagnostics and exits | 10 | 4 | 80% | 0.50 | 64.00 |
| gzip input | 5 | 2 | 60% | 0.25 | 24.00 |

Descending RICE orders stories and feature work; dependency work comes first. Failure behavior is designed in step 1 and implemented alongside each feature, with its consolidated matrix checked in step 7.

## Definition of Done

- All P0 stories in [PRD.md](PRD.md) pass unit and CLI integration tests.
- Parser and aggregation branch coverage reaches 90%; failure branches have explicit tests.
- All formats match the same report and the full exit contract is tested.
- Recorded representative laptop benchmark meets throughput and RSS targets; otherwise performance remains a failed release criterion.
- Wheel installs and runs locally in a clean environment; documentation examples match it.
- A code review and dependency/security check find no unresolved critical or high issues before release.
- No staging deployment applies: validate a local installed wheel instead.
- Independent architecture review is pending the external harness; no reviewer verdict is asserted here.

Execution prompts and continuity rules live in [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) and [CLAUDE.md](CLAUDE.md).
