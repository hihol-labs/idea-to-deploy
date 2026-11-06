# Strategic Plan: Nginx Lens

## 1. Idea
A local, pip-installable Python CLI for DevOps/SRE engineers to stream nginx combined access logs into four actionable summaries, without uploading logs. This is a planning deliverable; no product implementation or performance measurement exists yet. Behavioral details live in [PRD](PRD.md), contracts in [architecture](PROJECT_ARCHITECTURE.md), and delivery in [implementation plan](IMPLEMENTATION_PLAN.md).

## 2. Target Audience
| Persona | Role | Pain | Response |
|---|---|---|---|
| On-call engineer | SRE | Needs traffic and error context during incidents | One local report from a file or pipe |
| Service owner | DevOps | Needs repeatable pipeline summaries | Stable JSON and CSV |
| Small-team operator | Infrastructure generalist | Cannot fund or maintain analytics infrastructure | $0 tooling with no services |

## 3. Competitive Analysis
These are qualitative positioning assumptions, not a current market or benchmark survey.
| Alternative | Approach | Trade-off for this brief | Our distinction |
|---|---|---|---|
| GoAccess | Dedicated access-log analysis | Broader reporting than this narrowly scoped task | Small explicit machine-readable contract |
| Logstash/Elastic/Kibana | Collection, indexing, dashboards | Operational infrastructure exceeds weekend scope | One process and no persistent index |
| AWStats | Periodic log reporting | Report-generation workflow adds setup for ad hoc use | Pipe directly into an EOF report |
| grep/awk | Shell-based extraction and counting | Teams must maintain parsing and escaping conventions | Tested combined-log parser and stable schemas |

## 4. Unique Value Proposition
Turn an nginx access-log stream into reproducible incident summaries using one local command and no infrastructure.

## 5. Business Model
Open source under MIT; no paid tiers, monetization or revenue target. LTV and CAC are not applicable; distribution is through source and a pip-compatible wheel. Publication is a later external action requiring approval. Maintainer time is donated.

## 6. Technology Stack
| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved, accessible to operators |
| CLI | Click | Argument validation and help |
| Terminal | Rich | Readable colored tables |
| Models | dataclasses | Explicit internal contracts |
| Packaging | pyproject.toml, pip | Local wheel installation |
| Tests | pytest | Fixture and subprocess coverage |

## 7. Timeline
| Period | Stage | Result |
|---|---|---|
| Saturday morning | Steps 1–3 | Packaging, bounded parser, exact aggregation |
| Saturday afternoon | Steps 4–6 | CLI, terminal, pipeline exports |
| Sunday | Steps 7–8 | Edge cases, benchmark, release candidate |
Target effort: 16 focused hours across one weekend; defer Should/Could work first.

## 8. KPIs
| Metric | 1 month | 3 months | 6 months |
|---|---|---|---|
| Correctness | All P0 fixture assertions pass | Maintain P0 compatibility | Maintain P0 compatibility |
| Throughput | 1 GB in <30 s on recorded laptop | No >10% regression on same fixture | Same threshold |
| Resident memory | Peak RSS <=512 MiB on reference fixture | Same limit | Same limit |
| Pipeline stability | JSON/CSV schema v1 documented | No breaking v1 changes | Version any intentional break |
Targets are unmeasured until implementation. Record hardware, OS, interpreter, fixture characteristics and run times.

## 9. Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Pure Python misses throughput target | Medium | High | Benchmark early after aggregation; optimize hot path within approved stack |
| High cardinality grows memory | High | High | Bound exact keys; fail explicitly with exit 4 |
| Custom nginx formats fail parsing | High | Medium | Support combined format only; count rejected lines |
| Ambiguous metric definitions | Medium | High | Golden fixtures and explicit denominators |
| Terminal escape sequences in logs | Medium | Medium | Render as literal untrusted text, sanitize controls |

## 10. Budget
| Item | Monthly cost | Comment |
|---|---|---|
| Runtime, libraries, tests | $0 | Open-source tools |
| Hosting/database | $0 | None |
| Existing laptop | $0 incremental | 16 donated engineering hours |
Total cash budget: $0. No paid services or infrastructure.

## 11. Feature Roadmap
### MoSCoW
| Feature | Priority | Rationale |
|---|---|---|
| Combined-log streaming parser | Must | Supplies all metrics |
| Four exact summaries with cardinality bounds | Must | Core value and reliable limits |
| File/stdin CLI with complete failure contract | Must | Operator integration |
| Colored terminal report | Must | Default experience |
| JSON and CSV exports | Must | Required pipeline integration |
| Correctness and performance verification | Must | Demonstrates promised behavior |
| gzip input | Should | Useful for rotated logs, deferred |
| Custom log-format support | Could | Adds parsing complexity |
| Live dashboard, auth, database, HTTP API, cloud, Kubernetes | Won't | Outside approved local CLI scope |

### RICE Scoring
Planning estimates use confidence as a fraction (80%=0.8); reach is a 1–10 relative score, not measured adoption. Effort totals two person-days, including tests and packaging.
| Feature | Reach | Impact | Confidence | Effort (days) | Score |
|---|---|---|---|---|---|
| Combined-log parser | 10 | 5 | 80% | 0.35 | 114.29 |
| Four bounded summaries | 10 | 5 | 80% | 0.40 | 100.00 |
| File/stdin CLI | 10 | 4 | 90% | 0.40 | 90.00 |
| Colored terminal report | 9 | 3 | 90% | 0.30 | 81.00 |
| JSON/CSV exports | 8 | 4 | 90% | 0.40 | 72.00 |
| Performance verification | 10 | 3 | 80% | 0.15 | 160.00 |
| gzip input | 4 | 2 | 60% | 0.25 | 19.20 |
Descending priority places performance scaffolding first; the final measurement waits on dependencies. Implementation follows the remaining ranking. gzip is post-MVP.

## Definition of Done
- All P0 acceptance criteria and unit/integration suites pass; core parser/aggregator branch coverage >=90%.
- Reference benchmark meets throughput and memory targets with reproducible evidence.
- Local wheel installs and all documented commands work.
- Documentation matches behavior; no known high-severity defects remain.
- External architecture review remains for the harness; no independent review occurred here.
- Release publication requires separate approval; staging deployment does not apply to this local CLI.
