# Strategic Plan: nginx-logstats

## 1. Idea
A local, pip-installable Python 3.11 CLI that streams finite nginx access logs and reports top-10 client IPs, top-10 URLs by combined 4xx/5xx error count, hourly request percentages, and the share of unique User-Agents. Default output is colored terminal text; JSON and CSV support pipelines. This blueprint specifies future work; no product has been implemented or benchmarked.

## 2. Target Audience
| Persona | Pain | Benefit |
|---|---|---|
| On-call SRE | Needs evidence from a copied log during an incident | One local command produces a compact traffic and error summary |
| DevOps engineer | Repeated shell pipelines disagree about parsing and denominators | Documented, deterministic metrics and machine output |
| Small-service maintainer | Cannot justify a log analytics deployment | No service, account, database, or recurring spend |

## 3. Competitive Analysis
These are qualitative positioning assumptions, not a current feature or pricing audit.

| Alternative | Approach | Trade-off for this use case | Our difference |
|---|---|---|---|
| GoAccess | Dedicated access-log analytics | Broader reporting interface than this narrowly scoped summary requires | Fixed metrics and a small Python CLI contract |
| Logstash / Elastic / Kibana | Ingestion, indexing, visualization stack | Operational infrastructure exceeds a local weekend tool's budget and scope | Stateless processing with no deployment |
| AWStats | Established log reporting workflow | Persistent report generation adds setup for a one-off incident | Read once and emit a disposable summary |
| grep / awk | Flexible shell composition | Quoted log fields, errors, ties, and distinct counts need consistent custom handling | Tested parsing and stable JSON/CSV schemas |

## 4. Unique Value Proposition
Turn a local nginx combined log into four exact, reproducible incident metrics with one command and no infrastructure.

## 5. Business Model
Open source, proposed MIT license; no paid tier, subscriptions, or revenue target. CAC and LTV are not applicable. Distribution is source plus a locally built pip wheel; public package publication is a separate future action requiring approval. No telemetry or external requests at runtime.

## 6. Technology Stack
| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved stack and straightforward local distribution |
| CLI | Click | Argument validation and consistent command help |
| Terminal | Rich | Readable tables and automatic terminal color handling |
| Internal contracts | dataclasses and standard-library collections | Explicit records and low overhead |
| Packaging and verification | setuptools, pip, pytest | Build a wheel and test installed behavior |

## 7. Timeline
| Period | Work | Deliverable |
|---|---|---|
| Saturday morning | Package, metric contract, parser | Installable skeleton and parser tests |
| Saturday afternoon | Aggregation, input handling | Exact streaming analysis and failure handling |
| Sunday morning | Three output modes and CLI | End-to-end reports |
| Sunday afternoon | Benchmark, edge tests, documentation | Reviewable local release candidate |

The estimated implementation effort is 16 hours; this is a planning estimate, not measured delivery evidence.

## 8. KPIs
| Metric | Month 1 | Month 3 | Month 6 |
|---|---|---|---|
| Reference 1 GB fixture throughput | Under 30 seconds | Preserve threshold | Preserve threshold |
| Golden fixture metric accuracy | Exact | Exact | Exact |
| Runtime service cost | $0 | $0 | $0 |
| Local incident dry runs | 3 | 5 | 10 |

Dry-run targets are aspirations, collected manually without telemetry. Performance acceptance uses the repeatable laptop protocol in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), not an unconditional promise for arbitrary hardware or cardinality.

## 9. Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python parser misses throughput target | Medium | High | Benchmark early; optimize parser and allocation after profiling |
| High distinct-key count consumes memory | High | High | Explicit cardinality ceiling; terminate with code 4 rather than approximate |
| Custom nginx formats silently corrupt metrics | Medium | High | Support combined format only; reject malformed records and report counts |
| Hostile log strings affect terminal rendering | Medium | Medium | Escape Rich markup and control characters; never execute input |
| Weekend scope expands | Medium | High | Freeze Must scope; defer Should/Could work |

## 10. Budget
| Item | Monthly cash | Notes |
|---|---|---|
| Development tools and dependencies | $0 | Open-source tools |
| Hosting, database, cloud | $0 | None used |
| Distribution | $0 | Local wheel; publication deferred |
| Labor | $0 cash | 16 volunteer hours, not zero economic effort |

## 11. Feature Roadmap
### MoSCoW
| Feature | Priority | Rationale |
|---|---|---|
| Combined-log parser with malformed counts | Must / P0 | Metrics require a trustworthy denominator |
| Four exact metrics and cardinality guard | Must / P0 | Core value and memory safety |
| File/stdin CLI and full exit contract | Must / P0 | Local and pipeline use |
| Colored terminal summary | Must / P0 | Default interaction |
| JSON and CSV reports | Must / P0 | Approved pipeline requirement |
| pip installation and performance verification | Must / P0 | Delivery constraints |
| Additional documented log formats | Should / P1 | Useful after a stable combined parser |
| Shell completion | Could / P2 | Convenience only |
| Auth, database, HTTP API, cloud, Kubernetes, live tailing | Won't | Outside the finite local CLI scope |

### RICE Scoring
Scores are assumptions for relative sequencing. Confidence is a decimal in the formula R × I × C / E; reach is a 1–10 relative scale. Effort is person-days, not a commitment.

| Feature | Reach | Impact | Confidence | Effort | Score |
|---|---|---|---|---|---|
| Parser | 10 | 5 | 80% | 0.30 | 133.33 |
| Metrics and cardinality guard | 10 | 5 | 80% | 0.40 | 100.00 |
| File/stdin CLI | 10 | 4 | 80% | 0.35 | 91.43 |
| Terminal summary | 10 | 3 | 80% | 0.30 | 80.00 |
| JSON and CSV | 8 | 4 | 80% | 0.40 | 64.00 |
| Packaging/performance acceptance | 10 | 4 | 80% | 0.65 | 49.23 |
| Additional formats | 4 | 2 | 50% | 0.50 | 8.00 |

Implement Must capabilities in descending score order after minimal packaging runway. See [PRD.md](PRD.md) for acceptance and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for dependency-aware steps.

## Definition of Done
- All P0 acceptance criteria pass, including exact output and all failure codes.
- Unit and subprocess integration suites pass; core parser/aggregation branch coverage reaches 90%.
- Wheel installs in a clean Python 3.11 environment and installed CLI tests pass.
- Reference benchmark meets time and memory criteria with environment recorded.
- Documentation and executable examples agree; no known critical/high security issues remain after review.
- Local candidate is independently reviewed before release; no staging server is applicable.
- Review and performance criteria above are future implementation gates. The blueprint's external adversarial review is pending outside this session.

Implementation instructions: [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md). Project memory: [CLAUDE.md](CLAUDE.md).
