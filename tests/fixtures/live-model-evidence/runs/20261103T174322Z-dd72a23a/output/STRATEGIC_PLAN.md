# Strategic Plan: Nginx Log Lens

## 1. Idea
A local, pip-installable Python 3.11 CLI, `nginx-log-lens`, streams nginx access logs and produces top-10 IPs, top-10 URLs by combined 4xx/5xx errors, hourly request percentages, and the share of unique User-Agents. DevOps/SRE engineers receive a colored terminal report or JSON/CSV for pipelines. Processing is stateless between invocations.

This is a planning deliverable. No product implementation or runtime performance result exists yet. Behavior is specified in [PRD.md](PRD.md), interfaces in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), execution in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), contributor prompts in [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md), and agent rules in [CLAUDE.md](CLAUDE.md).

## 2. Target audience
| Persona | Role | Pain | Response |
|---|---|---|---|
| On-call responder | SRE | Needs immediate local traffic/error attribution during incidents | One command, ranked IPs and failing paths |
| Platform operator | DevOps engineer | Wants repeatable reporting without maintaining infrastructure | stdin plus stable JSON/CSV |
| Service maintainer | Small-team engineer | Needs request timing and client diversity summaries | Hour percentages and exact UA ratio |

## 3. Competitive analysis
These are qualitative positioning comparisons, not fresh benchmarks or claims of missing competitor features.
| Alternative | Approach | Trade-off for this brief | Our distinction |
|---|---|---|---|
| GoAccess | Dedicated access-log analytics | Broader analytics/UI can exceed this narrow reporting need | Small Python CLI with an explicit machine-output contract |
| Logstash/Elastic/Kibana | Ingestion, indexed search, dashboards | Persistent services and operational overhead conflict with $0 local scope | No infrastructure or indexed storage |
| AWStats | Generated traffic statistics | Report configuration and recurring workflows are broader than a one-shot incident command | stdin-driven ad hoc invocation |
| grep/awk | Composable text processing | Teams must maintain parsing, ranking and export semantics themselves | Tested combined-log parser and consistent metrics |

## 4. Value proposition
Turn a local nginx combined access log into four precise incident summaries with one command and no running services.

## 5. Business model
Open source under MIT; free usage and no paid tiers, ads, telemetry, or monetization in MVP. Revenue, LTV and CAC are not applicable; distribution is through pip after a separately approved release. Contributor time is donated. Adoption goals below are hypotheses, not measured demand.

## 6. Technology stack
| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved local stack |
| Interface | Click | Argument validation and help |
| Terminal | Rich | Colored tables with terminal-aware output |
| Data model | dataclasses and standard-library counters | Explicit records, exact streaming aggregates |
| Packaging/testing | pyproject.toml, pip, pytest | Installable CLI and repeatable verification |

## 7. Timeline
| Period | Stage | Deliverable |
|---|---|---|
| Saturday, 8 hours | Interface, parser, counters | Core fixture-tested stream processing |
| Sunday, 8 hours | Reports, failure handling, performance, package | Locally verified release candidate |
| After weekend | Optional improvements | Only Should/Could work that does not delay Must scope |
The eight implementation steps total 16 estimated engineer-hours, with no paid infrastructure.

## 8. KPIs
| Metric | Month 1 target | Month 3 target | Month 6 target |
|---|---|---|---|
| Core correctness | All specified acceptance fixtures pass | Maintain | Maintain |
| Stream throughput | 1 GB in <30 seconds on recorded laptop/fixture | No regression | No regression |
| Peak memory | <=512 MiB on documented baseline workload | Maintain | Maintain |
| Adoption hypothesis | 5 opt-in user reports | 15 | 30 |
No telemetry is collected; adoption is measured only from voluntary feedback. Performance is a target, subject to the workload envelope in the architecture.

## 9. Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python parser misses throughput target | Medium | High | Benchmark early; profile parser; reduce scope rather than silently promise speed |
| Unique dimensions exhaust memory | High | High | Per-dimension cardinality caps; abort with code 4; never silently approximate |
| Custom nginx formats differ | High | Medium | Support combined format only; count malformed lines and document boundary |
| Sensitive URLs or UAs leak | Medium | High | Local processing; omit query strings; no raw-line diagnostics or telemetry |
| Weekend overrun | Medium | Medium | Freeze Must scope; defer Should and Could |

## 10. Budget
| Item | Monthly cash | Comment |
|---|---|---|
| Runtime/storage/services | $0 | Existing laptop and local files |
| Dependencies/tools | $0 | Open source tooling |
| Engineer time | $0 cash | 16 donated hours; not zero effort |
| Distribution | $0 planned | No publication performed in blueprint session |

## 11. Feature Roadmap
### MoSCoW
| Feature | Priority | Rationale |
|---|---|---|
| File/stdin combined-log streaming | Must | Supplies every metric |
| Top-10 IPs | Must | Traffic attribution |
| Top-10 URLs by 4xx/5xx | Must | Error triage |
| Hourly percentages | Must | Request timing |
| Unique UA share | Must | Client diversity |
| Colored text, JSON and CSV | Must | Human and pipeline outputs are required |
| Bounded exact counting and exit codes | Must | Predictable failures without false reports |
| pip installation and help | Must | Usable local distribution |
| gzip input | Should | Convenient archived-log analysis; post-MVP |
| Custom log formats | Could | Adds reach but complicates parser |
| Auth, database, HTTP API, server, cloud, Kubernetes | Won't | Explicitly excluded |
| Live follow mode, remote ingestion, approximate counting | Won't | Weekend scope and exact snapshot semantics |

### RICE scoring
Scores are planning estimates; confidence is a fraction in the calculation, not a whole percentage. Effort is person-days at eight hours/day. Overlapping feature estimates are prioritization inputs, not additive delivery estimates.
| Feature | Reach | Impact | Confidence | Effort | RICE score |
|---|---|---|---|---|---|
| File/stdin parser | 10 | 5 | 80% | 0.30 | 133.33 |
| Top-10 IPs | 10 | 4 | 90% | 0.30 | 120.00 |
| Top error URLs | 10 | 5 | 80% | 0.40 | 100.00 |
| Hourly percentages | 8 | 3 | 90% | 0.25 | 86.40 |
| Unique UA share | 8 | 3 | 80% | 0.25 | 76.80 |
| Bounded exact counting/exit codes | 10 | 4 | 90% | 0.50 | 72.00 |
| Text/JSON/CSV | 10 | 4 | 80% | 0.50 | 64.00 |
| pip install/help | 10 | 3 | 90% | 0.50 | 54.00 |
| gzip input | 5 | 2 | 60% | 0.50 | 12.00 |
Implementation follows descending value subject to dependencies: package scaffolding precedes parser tests; caps accompany every counter; optional gzip follows MVP.

## Definition of Done
- [ ] All Must requirements and P0 acceptance tests pass on Python 3.11.
- [ ] Unit and integration suites pass; parser/aggregation branch coverage >=90%.
- [ ] Full 0/1/2/3/4 exit behavior and deterministic exports verified.
- [ ] Recorded laptop benchmark meets throughput and memory targets within the declared workload envelope.
- [ ] Local wheel installation and file/stdin smoke tests pass.
- [ ] Docs match behavior; no known Critical/High security issues remain after review.
- [ ] Code review completed during implementation; external architecture review handled separately by the benchmark harness.
Staging deployment is inapplicable to a local CLI; substitute an isolated local installation smoke test. These are future product gates, not claims of completed implementation.
