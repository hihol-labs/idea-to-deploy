# Strategic Plan: Nginx Lens

## 1. Idea
A pip-installable local Python 3.11 CLI that reads nginx combined access logs incrementally and prints top-10 IPs, top-10 URLs by 4xx/5xx errors, hourly request percentages, and unique User-Agent share. See [PRD](PRD.md) for acceptance criteria and [architecture](PROJECT_ARCHITECTURE.md) for exact semantics.

## 2. Target Audience
| Persona | Role | Pain | Solution |
|---|---|---|---|
| On-call engineer | SRE | Needs a quick traffic/error summary during incidents | One command against a local export |
| Platform operator | DevOps | Needs repeatable pipeline reports | Stable JSON and CSV |
| Service maintainer | Developer | Cannot justify deploying analytics infrastructure | Offline, zero-service installation |

## 3. Competitive Analysis
These are qualitative planning comparisons, not newly verified product claims.
| Alternative | Approach | Trade-off for this brief | Differentiation |
|---|---|---|---|
| GoAccess | Dedicated access-log reporting | Broader reporting interface than this narrow task | Small, explicitly specified pipeline contract |
| Logstash/Elastic/Kibana | Collection, indexing, dashboards | Operational scope exceeds a local weekend utility | No infrastructure or persistent index |
| AWStats | Established log statistics reports | Report-oriented workflow differs from a disposable pipe | Direct terminal, JSON and CSV output |
| grep/awk | Composable shell analysis | Each team must maintain parsing and aggregation logic | Shared tested semantics for quoting, time and limits |

## 4. Unique Value Proposition
An offline command with four useful incident metrics and deterministic machine output, without operating an analytics service.

## 5. Business Model
Open source under MIT; no paid tiers, telemetry, subscription, or revenue target. LTV/CAC and per-customer hosting cost are inapplicable; maintenance is volunteer time. Publishing to a package index is a later explicitly authorized external action.

## 6. Technology Stack
| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved stack and accessible maintenance |
| CLI | Click | Options, help and usage errors |
| Presentation | Rich | Colored terminal tables |
| Models | dataclasses | Explicit internal records |
| Packaging/tests | pip, pyproject.toml, pytest | Local install and reproducible checks |

## 7. Timeline
| Window | Work | Outcome |
|---|---|---|
| Saturday | Plan steps 1–4, about 8 hours | Parser and exact metrics |
| Sunday | Steps 5–8, about 8 hours | Formats, failure handling, benchmark and handoff |
One developer, one weekend; reduce optional polish before changing core semantics.

## 8. KPIs
Targets, not measurements or adoption forecasts:
| Metric | Month 1 | Month 3 | Month 6 |
|---|---|---|---|
| 1 GB decimal combined-log run | <30 seconds | Retain | Retain |
| Golden-fixture correctness | All agreed fixtures | Retain | Retain |
| Core branch coverage | >=85% | >=85% | >=85% |
| External services required | 0 | 0 | 0 |

## 9. Risks
| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| High distinct-key counts | High | Memory exhaustion | Exact aggregate cap and exit 4 |
| Custom nginx formats | High | Invalid or misleading analysis | Combined format only, reject/count malformed records |
| Python throughput | Medium | Missed latency target | Benchmark early; optimize parser using profiles |
| Sensitive IPs/query strings | High | Accidental disclosure | Local only; sanitized fixtures; no telemetry |
| Weekend scope pressure | Medium | Incomplete release | Defer Should/Could work |

## 10. Budget
| Item | Monthly cash | Comment |
|---|---|---|
| Infrastructure | $0 | Existing laptop, offline execution |
| Dependencies/tools | $0 | Open-source tooling |
| Development | $0 cash | Approximately 16 volunteer hours |
No paid infrastructure or external service dependency is approved.

## 11. Feature Roadmap
Product decisions and priorities were pre-approved in the user brief.
### MoSCoW
| Feature | Priority | Rationale |
|---|---|---|
| Combined-log file/stdin streaming | Must | Input foundation |
| Exact IP/error-URL rankings | Must | Primary incident value |
| Hourly percentages and UA share | Must | Required traffic summary |
| Terminal/JSON/CSV | Must | Interactive and pipeline usage |
| Malformed-input and cardinality safety | Must | Trustworthy results |
| pip installation/help | Must | Usable distribution |
| Extended troubleshooting examples | Should | Faster operator onboarding |
| Shell completion | Could | Optional polish |
| Auth/database/HTTP API/cloud/Kubernetes | Won't | Outside local stateless scope |
| Live tailing/custom formats/gzip | Won't | Avoid weekend scope growth |

### RICE Scoring
Confidence is a decimal multiplier in calculation; estimates are assumptions. Effort partitions the 16-hour core weekend plus optional later work. Scores rank value; dependencies take precedence.
| Feature | Reach | Impact | Confidence | Effort (days) | RICE |
|---|---|---|---|---|---|
| IP/error-URL rankings | 10 | 5 | 80% | 0.25 | 160 |
| Hourly/UA metrics | 10 | 4 | 80% | 0.25 | 128 |
| pip/help | 10 | 3 | 90% | 0.25 | 108 |
| Combined-log streaming | 10 | 5 | 80% | 0.5 | 80 |
| Terminal/JSON/CSV | 10 | 4 | 90% | 0.5 | 72 |
| Input/cardinality safety | 10 | 5 | 70% | 0.25 | 140 |
| Troubleshooting examples | 6 | 2 | 70% | 0.25 | 33.6 |
Safety is built into the first metric increments despite its separate score; parser and packaging are dependencies of those increments. See [implementation plan](IMPLEMENTATION_PLAN.md).

## Definition of Done
- [ ] Unit and CLI integration tests pass; core branch coverage >=85%.
- [ ] Exact metric, malformed-record and all exit-status fixtures pass.
- [ ] Local wheel installs and runs in a clean Python 3.11 environment.
- [ ] Recorded representative-laptop benchmark meets <30 seconds for 1,000,000,000 bytes, with peak RSS reported.
- [ ] Review and security findings have no unresolved Critical/High issues.
- [ ] Documentation and local smoke checks agree; no staging service applies.
This planning session does not assert product readiness. [CLAUDE.md](CLAUDE.md) records implementation status.
