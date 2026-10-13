# Strategic Plan: Nginx Lens

## 1. Idea

Nginx Lens is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx combined access logs line by line and produces top-10 client IPs, top-10 request targets with 4xx/5xx responses, hourly request percentages, and the share of unique User-Agents. Rich terminal output is the default; JSON and CSV support automation. No log contents leave the machine.

Hourly distribution uses `100 × hourly_request_count / total_valid_requests` in UTC hour-of-day buckets; an empty denominator gives 0%. The architecture defines the precise parsing and metric semantics.

This is a planning deliverable, not a working release. Product choices and priorities are pre-approved. The independent adversarial review belongs to the external harness and has not run in this session. See [architecture](PROJECT_ARCHITECTURE.md), [requirements](PRD.md), [delivery plan](IMPLEMENTATION_PLAN.md), [quick start](README.md), [implementation prompts](CLAUDE_CODE_GUIDE.md), and [project memory](CLAUDE.md).

## 2. Target Audience

| Persona | Role | Pain | Response |
|---|---|---|---|
| Incident responder | On-call SRE | Needs a quick summary from a copied access log | One local command with deterministic rankings |
| Service owner | DevOps engineer | Needs to locate failing URLs without provisioning infrastructure | Combined 4xx/5xx ranking with separate counts |
| Automation maintainer | Operations engineer | Ad hoc shell scripts disagree on percentages and failure handling | Stable JSON/CSV schema and explicit exit codes |

## 3. Competitive Analysis

These are qualitative planning comparisons, not a current feature audit or measured product benchmark. The alternatives were supplied in the brief; validate comparative claims before publishing marketing copy.

| Alternative | Approach | Fit limitation for this brief | Our distinction |
|---|---|---|---|
| GoAccess | Access-log reporting and interactive analysis | Broader reporting interface than the four fixed summaries required here | Small Python package with a deliberately narrow export contract |
| Logstash/Elastic/Kibana | Collection, indexing, and dashboards | Operational stack conflicts with the no-service, $0 weekend scope | No ingestion service or persistent index |
| AWStats | Generated traffic statistics | Periodic report workflow is a less direct fit for one-off pipeline use | Stateless invocation over a file or stdin |
| grep/awk | Composable text processing | Each team must maintain parsing, denominator, escaping, and error conventions | Tested combined-log semantics and consistent machine output |

## 4. Unique Value Proposition

Turn a local nginx log into four precise incident-triage summaries with a single command and no deployed infrastructure.

## 5. Business Model

Open-source utility under the MIT license; no paid tiers, subscriptions, telemetry, or monetization in MVP. LTV, paid CAC, and subscription unit economics are not applicable. Distribution is via source and a pip-installable wheel; public package-name availability and publication remain future release work. Contributor time is donated, not a cash expense.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved stack and accessible operations tooling |
| CLI | Click | Arguments, help, and consistent usage errors |
| Terminal | Rich | Readable colored tables on a TTY |
| Data model | Standard-library dataclasses | Explicit parsed record and report contracts |
| Aggregation | Dictionaries, sets, fixed hour array | One pass, exact results within explicit cardinality limits |
| Packaging | pyproject.toml, setuptools, wheel, pip | Ordinary local installation without services |
| Verification | pytest, coverage, synthetic benchmark harness | Replayable correctness and measured release criteria |

## 7. Timeline

| Period | Stage | Result |
|---|---|---|
| Saturday, 7 hours | Steps 1–4 | Package scaffold, parser, exact metrics, resource guardrails |
| Sunday, 7 hours | Steps 5–8 | Outputs, integration, measured tuning, installation and docs |
| Remaining weekend buffer, 2 hours | Recover or cut deferred scope | P0 work only; performance failure stays visible |

## 8. KPIs

Targets are hypotheses, not adoption measurements or performance results.

| Metric | Month 1 | Month 3 | Month 6 |
|---|---|---|---|
| Correctness | All P0 acceptance fixtures pass | No unresolved P0 regressions | Same release gate |
| Throughput | 1,000,000,000-byte reference file in under 30 seconds | Preserve on recorded hardware | Preserve on recorded hardware |
| Resource use | Peak RSS at most 512 MiB on reference benchmark | No unbounded state growth | Same guardrails |
| Adoption | 3 engineers try it | 10 repeat users report usefulness | 20 repeat users report usefulness |
| Installation | Clean Python 3.11 virtual environment succeeds | Preserve reproducible install | Preserve reproducible install |

Adoption uses voluntary feedback, never bundled telemetry. The benchmark profile, timing boundary, and hardware metadata are specified in the architecture.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python parsing misses the throughput target | Medium | High | Benchmark on day two; profile timestamp/escape parsing and avoid per-line Rich work; block release if still slow |
| Exact unique counts consume excessive memory | High | High | Aggregate key-count and byte budgets; fail with code 4 before inserting beyond limits |
| Custom nginx formats look like supported input | High | Medium | Support combined format only, validate strictly, count invalid records, and return code 3 |
| Query strings/IPs disclose sensitive information | Medium | High | Local processing, no raw lines in diagnostics, document that reports inherit source sensitivity |
| Weekend scope expands | Medium | High | Keep P1/P2 deferred; no database, server, cloud, auth, or dashboard |
| Malicious log fields manipulate terminal/CSV viewers | Medium | Medium | Escape controls, disable Rich markup for log data, protect CSV text cells from formula interpretation |

## 10. Budget

| Item | Monthly cash cost | Comment |
|---|---|---|
| Runtime and development tools | $0 | Open-source dependencies |
| Compute and storage | $0 incremental | Existing laptop; user retains their log files |
| Hosting/database/cloud | $0 | None used |
| Labor | $0 cash | 14 estimated engineering hours plus 2-hour contingency |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| File/stdin combined-log parser and invalid-line accounting | Must / P0 | Foundation for credible results |
| Top-10 IP counts | Must / P0 | Identify dominant clients |
| Top-10 error URLs with 4xx/5xx breakdown | Must / P0 | Locate failing resources |
| UTC hourly request percentages | Must / P0 | Explain traffic distribution |
| Exact unique User-Agent share | Must / P0 | Describe client diversity |
| Colored terminal, JSON, CSV | Must / P0 | Satisfy humans and pipelines |
| Cardinality guards, exit contract, pip package, benchmark | Must / P0 | Make the required workflow operable |
| gzip input | Should / P1 | Useful for rotated logs; deferred beyond weekend |
| Date/status filtering | Could / P2 | Convenience once denominators can be extended carefully |
| Authentication, DB, HTTP API, server, cloud, Kubernetes | Won't | Conflict with explicit constraints |
| Live tailing, custom formats, approximate counts, GeoIP | Won't in MVP | Additional lifecycle, semantics, or data dependencies |

### RICE Scoring

Confidence is a fraction in the calculation: 80% = 0.8. Reach uses the requested 1–10 relative scale; impact uses 1–5. Estimates are planning judgments. One person-day = 8 hours. Grouped metric work avoids pretending four counters are four independent delivery projects.

| Feature group | Reach | Impact | Confidence | Effort (days) | RICE score |
|---|---|---|---|---|---|
| Four exact metrics | 10 | 5 | 80% | 0.25 | 160 |
| Colored terminal, JSON, CSV | 10 | 4 | 90% | 0.25 | 144 |
| File/stdin parser and malformed policy | 10 | 5 | 80% | 0.375 | 106.67 |
| Guards, exit contract, pip delivery, benchmark | 10 | 5 | 70% | 0.875 | 40 |
| gzip input (deferred) | 6 | 2 | 70% | 0.375 | 22.4 |

Implement high-value metrics and exports as soon as their parser and package prerequisites exist. Guardrails accompany aggregation rather than waiting for release. The dependency-adjusted sequence appears in IMPLEMENTATION_PLAN.md; the four Must groups total 1.75 person-days.

## Definition of Done

The blueprint being written does not mark any product feature done. A release requires:

- [ ] Python package builds and installs into a clean Python 3.11 environment.
- [ ] P0 unit and integration acceptance checks pass; parser and aggregator branch coverage is at least 90%.
- [ ] Exit codes 0/1/2/3/4, output schema, resource boundaries, and hostile input cases are exercised.
- [ ] The defined reference workload meets time and RSS targets with recorded hardware and repeatable evidence.
- [ ] Code review and security review have no unresolved Critical/High findings.
- [ ] Documentation examples match installed behavior and the MIT license is included.
- [ ] Wheel is manually smoke-tested on the development laptop; there is no staging service to deploy.
- [ ] The external architecture review is recorded by its actual reviewer before implementation handoff is accepted.
