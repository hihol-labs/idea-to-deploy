# Strategic Plan: Nginx Lens

## 1. Idea
Nginx Lens is a local, pip-installable Python 3.11 CLI that reads nginx combined access logs incrementally and emits an incident triage summary at EOF. It reports top-10 client IPs, top-10 URLs by combined 4xx/5xx errors, hourly request percentages, and unique User-Agent share. Streaming means incremental reading, not a live dashboard or follow mode.

## 2. Audience
| Persona | Role | Pain | Outcome |
|---|---|---|---|
| On-call engineer | SRE | Needs traffic clues during an incident | One terminal command |
| Platform maintainer | DevOps | Needs repeatable offline analysis | Stable JSON and CSV |
| Service developer | Backend engineer | Needs error hotspots without infrastructure | Local URL ranking |

## 3. Competitive analysis
Qualitative positioning, not a current product/version audit; these are the alternatives supplied in the brief.

| Alternative | Approach | Trade-off for this project | Differentiation |
|---|---|---|---|
| GoAccess | Dedicated access-log analysis | Broader reporting surface than this fixed report needs | Small fixed pipeline contract |
| Logstash/Elastic/Kibana | Central ingestion, search, visualization | Operating an ingestion/search stack exceeds this weekend scope | Local execution without services |
| AWStats | Historical traffic reporting | Historical reporting is beyond this stateless one-shot workflow | Disposable per-run analysis |
| grep/awk | Composable text processing | Team must maintain parsing and aggregation scripts | Tested nginx semantics and shared output schema |

## 4. Value proposition
Turn a local nginx log into four exact, reproducible triage views without operating a service.

## 5. Business model
Open source under MIT; no paid tier, billing, telemetry, or acquisition budget. LTV and CAC do not apply to this noncommercial MVP. Maintainer labor is donated; $0 is cash expenditure, not zero effort.

## 6. Stack
| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved laptop runtime |
| CLI | Click | Argument validation and help |
| Terminal | Rich | Readable colored summaries |
| Models | dataclasses | Explicit records and reports |
| Packaging | pip, pyproject.toml | Local installation |
| Verification | pytest, standard-library timing | Offline correctness and performance evidence |

## 7. Timeline
| Window | Work | Deliverable |
|---|---|---|
| Saturday morning | Contracts, parser | Validated record stream |
| Saturday afternoon | Aggregation and limits | Exact report model |
| Sunday morning | CLI and renderers | Pipeline-compatible output |
| Sunday afternoon | Benchmark, packaging, docs | Locally verified wheel |
Implementation budget: 16 focused hours; see [implementation plan](IMPLEMENTATION_PLAN.md).

## 8. KPIs
Targets, not measured results. Later milestones are maintenance checkpoints, not new paid scope.

| Metric | Month 1 | Month 3 | Month 6 |
|---|---|---|---|
| Representative 1 GB run | <30 s | Retain <30 s | Retain <30 s |
| Golden fixture correctness | Exact | Retain | Retain |
| Hosted infrastructure cost | $0 | $0 | $0 |
| Fresh local install and small fixture | <30 s with cached dependencies | Retain | Retain |

## 9. Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python misses throughput | Medium | High | Early benchmark; profile parser before polishing |
| Unbounded distinct keys | High | High | Explicit caps, exit 4, no silent approximation |
| Custom nginx formats | High | Medium | Combined format only; count rejected lines |
| Sensitive URLs and terminal escapes | Medium | High | Strip queries; escape terminal controls; local-only |
| Weekend exceeds budget | Medium | Medium | Defer Should/Could features |

## 10. Budget
| Item | Monthly cash | Comment |
|---|---|---|
| Hosting/storage | $0 | No hosted runtime |
| Dependencies/tools | $0 | Open source tooling |
| Labor | $0 cash | 16 donated hours |
| Total | $0 | Existing laptop assumed |

## 11. Feature Roadmap
### MoSCoW
| Feature | Priority | Rationale |
|---|---|---|
| Combined-log file/stdin parser | Must | Required input |
| Four exact analytics and cardinality limits | Must | Core value and bounded resource behavior |
| Colored terminal report | Must | Default operator workflow |
| JSON/CSV output | Must | Approved pipeline requirement |
| Malformed input diagnostics and exit codes | Must | Trustworthy automation |
| Gzip input | Should | Useful for archives after MVP |
| Shell completions | Could | Convenience |
| Auth, DB, HTTP, server, cloud, Kubernetes | Won't | Contradict approved scope |
| Follow mode and custom log-format DSL | Won't | Exceed weekend scope |

### RICE scoring
Planning assumptions only. Confidence is a decimal multiplier; score = Reach × Impact × Confidence / effort in person-days (8 hours/day). Ordered descending; dependencies override score when needed.

| Feature | Reach | Impact | Confidence | Effort | Score |
|---|---|---|---|---|---|
| Parser | 10 | 5 | 80% | 0.35 | 114.3 |
| Exact analytics and limits | 10 | 5 | 80% | 0.50 | 80.0 |
| Terminal report | 10 | 4 | 80% | 0.25 | 128.0 |
| JSON/CSV | 8 | 4 | 80% | 0.35 | 73.1 |
| Diagnostics | 10 | 4 | 80% | 0.20 | 160.0 |
| Gzip | 5 | 2 | 60% | 0.25 | 24.0 |

Priority order: diagnostics, terminal, parser, analytics, exports, gzip. Establish diagnostics first; terminal depends on report data, so parser and analytics must precede its completed integration. MVP estimates exclude packaging and benchmarks; those consume the remaining time budget.

## Definition of Done
- All Must requirements in [PRD](PRD.md) have passing acceptance tests.
- Unit and integration tests pass; core parser/aggregation branch coverage targets at least 90%.
- Performance recorded on a named laptop with fixture distribution and peak RSS; no unmeasured speed claims.
- Local wheel installation and CLI smoke tests pass; documentation matches schema and exit codes.
- Review and security findings resolved before release; independent review is pending external harness execution, not performed in this blueprint session.
- Local installation replaces staging deployment; publication requires separate authorization.

See [architecture](PROJECT_ARCHITECTURE.md), [guide](CLAUDE_CODE_GUIDE.md), and [project instructions](CLAUDE.md).
