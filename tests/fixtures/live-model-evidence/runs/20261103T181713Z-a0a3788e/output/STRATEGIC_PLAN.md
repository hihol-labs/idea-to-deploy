# Strategic Plan: Nginx Pulse

## 1. Idea
A local, pip-installable Python 3.11 CLI for DevOps/SRE engineers. Read nginx combined access logs once, aggregate four operational views, and print colored terminal text or pipeline-safe JSON/CSV. This is an open-source weekend project with a $0 cash budget. See [PRD](PRD.md) for acceptance criteria and [architecture](PROJECT_ARCHITECTURE.md) for the executable contract.

## 2. Target Audience
| Persona | Pain | Result |
|---|---|---|
| On-call SRE | Needs a quick incident snapshot from a copied log | Ranked clients and failing paths without service setup |
| DevOps engineer | Repeats fragile shell pipelines | Stable machine-readable summaries |
| Small-site operator | Cannot justify a log analytics stack | Offline inspection with no infrastructure cost |

## 3. Competitive Analysis
These are qualitative positioning assumptions, not a current feature or pricing audit.
| Alternative | Approach | Trade-off for this brief | Our difference |
|---|---|---|---|
| GoAccess | Dedicated access-log analysis | Broader interactive reporting than this narrow contract needs | Small Python CLI with explicit export and failure semantics |
| Logstash / Elastic / Kibana | Ingest, index, visualize logs | Operational components exceed a stateless weekend tool | One local process and no indexing |
| AWStats | Periodic log reports | Report-generation workflow differs from an ad hoc pipeline | Read stdin and emit a finite summary |
| grep / awk | Composable text pipelines | Quoting, malformed input, and denominators require care | Tested combined-log parsing and one shared metric definition |

## 4. Unique Value Proposition
Turn a local nginx combined log into four exact, reproducible incident summaries with one command and no running service.

## 5. Business Model
Free open source, proposed MIT license. No paid tier, telemetry, advertising, or hosted service. Revenue, LTV and CAC do not apply to this release; contributor time is the constrained resource. Publishing or choosing a final distribution name requires a later explicit release action.

## 6. Technology Stack
| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved, locally available tooling |
| Interface | Click | Argument validation and help |
| Terminal | Rich | Tables and colors |
| Data | dataclasses, dict, set | Typed records and exact in-memory aggregation |
| Delivery | pip wheel, setuptools | Conventional local installation |
| Tests | pytest, standard-library subprocess | Fixtures, contracts and process behavior |

## 7. Timeline
| Window | Work | Deliverable |
|---|---|---|
| Saturday, 7 hours | Plan steps 1–4 | Parser, exact aggregations, CLI input |
| Sunday, 7 hours | Plan steps 5–8 | Exports, edge cases, benchmark, local wheel |
Should/Could features follow the weekend only if capacity remains. See [implementation plan](IMPLEMENTATION_PLAN.md).

## 8. KPIs
Targets are proposed acceptance goals, not measured results.
| Metric | Month 1 | Month 3 | Month 6 |
|---|---|---|---|
| Fixture metric accuracy | 100% | 100% | 100% |
| 1 GB reference-log processing | <30 s | <30 s | <30 s |
| Network calls during analysis | 0 | 0 | 0 |
| Peak RSS on reference corpus | ≤512 MiB | ≤512 MiB | ≤512 MiB |
| External SRE workflow trials | 3 | 5 | 10 |
Performance depends on the documented laptop and corpus; fail the release target if measurement disagrees.

## 9. Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python misses throughput target | Medium | High | Benchmark early and profile parsing before optimization |
| Adversarial unique values consume memory | High | High | Exact aggregate budget; fail with exit 4, never silently approximate |
| Custom nginx formats misparse | High | High | Support combined format only; count malformed lines explicitly |
| Logs expose sensitive values | Medium | High | Offline operation, strip URL queries, synthetic fixtures, no telemetry |
| Weekend scope expands | Medium | High | Must-only release and explicit exclusions |

## 10. Budget
| Item | Monthly cash | Constraint |
|---|---|---|
| Runtime and hosting | $0 | Existing laptop, no hosting |
| Libraries and tooling | $0 | Open-source tools |
| Labor | $0 cash | Approximately 14 volunteer hours, not free effort |
| Distribution | $0 planned | Local wheel first; publication outside this session |

## 11. Feature Roadmap
### MoSCoW
| Feature | Priority | Rationale |
|---|---|---|
| Combined-log parser and finite file/stdin stream | Must | All metrics depend on valid records |
| Four exact summaries | Must | Core incident value |
| Input diagnostics and cardinality guard | Must | Correctness and bounded resource use |
| Colored terminal output | Must | Default operator workflow |
| JSON and CSV output | Must | Approved pipeline requirement |
| pip installation and performance validation | Must | Delivery and acceptance requirements |
| gzip input | Should | Convenient later; shell decompression works now |
| Time-range filtering | Should | Helpful later; scope remains finite input |
| Alternate color theme | Could | Cosmetic polish |
| Auth, DB, HTTP API, server, cloud, Kubernetes | Won't | Explicit constraints |
| Live dashboard, tail-follow, custom log format, approximate metrics | Won't | Exceeds weekend contract |

### RICE Scoring
Planning estimates; confidence is a fraction in the calculation. Reach 1–10, impact 1–5, effort in 7-hour person-days. Score = Reach × Impact × Confidence / Effort.
| Feature | Reach | Impact | Confidence | Effort | Score |
|---|---|---|---|---|---|
| Parser and streaming | 10 | 5 | 80% | 0.40 | 100 |
| Four summaries | 10 | 5 | 80% | 0.45 | 88.89 |
| Diagnostics and resource guard | 10 | 4 | 80% | 0.40 | 80 |
| Terminal output | 10 | 3 | 80% | 0.35 | 68.57 |
| JSON/CSV | 8 | 4 | 80% | 0.40 | 64 |
| Packaging/performance | 10 | 4 | 70% | 0.50 | 56 |
| gzip | 5 | 2 | 60% | 0.30 | 20 |
| Time-range filter | 4 | 2 | 50% | 0.40 | 10 |
Scores order features; the implementation plan respects dependencies and folds safety into the aggregation step. Feature estimates overlap shared testing; the step-level 14-hour budget is the delivery schedule.

## Definition of Done
- [ ] All Must user stories pass their PRD acceptance criteria.
- [ ] Parser, aggregate, export and CLI integration tests pass; core parser/aggregate branch coverage ≥90%.
- [ ] Exit codes 0/1/2/3/4 and resource failures are tested.
- [ ] The 1 GB reference benchmark meets time and RSS targets with exact output parity.
- [ ] A locally installed wheel passes documented examples in a clean Python 3.11 environment.
- [ ] Documentation matches behavior and product code has no known critical/high security issue.
- [ ] Product review completed before a future release; external blueprint adversarial review remains separate.
No staging service is appropriate: local wheel execution is the delivery verification. This session produces plans only; these product checkboxes remain unchecked.
