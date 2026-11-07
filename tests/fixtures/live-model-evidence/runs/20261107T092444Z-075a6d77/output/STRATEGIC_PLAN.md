# Strategic Plan: Nginx Lens

## 1. Idea

Nginx Lens is a local, pip-installable Python 3.11 CLI for DevOps/SRE engineers. It reads nginx combined access logs once and reports top-10 IPs, top-10 URLs by combined 4xx/5xx errors, hourly request percentages, and the share of unique User-Agents. Rich terminal text is the default; JSON and CSV serve pipelines. This blueprint specifies future behavior; no product implementation or performance measurement exists yet.

## 2. Target Audience

| Persona | Pain | Outcome |
|---|---|---|
| On-call SRE | Needs a quick incident snapshot from a copied log | One local command reveals traffic and error leaders |
| Platform engineer | Needs stable machine-readable output | JSON/CSV reports slot into existing scripts |
| Small-service maintainer | Cannot justify an analytics platform | Offline analysis with no paid services or persistent infrastructure |

## 3. Competitive Analysis

These are qualitative planning comparisons, not fresh product research or measured benchmarks.

| Alternative | Approach | Trade-off for this use case | Nginx Lens distinction |
|---|---|---|---|
| GoAccess | Dedicated access-log analysis | Broader reporting warrants evaluating it before building | Narrow four-metric contract and Python integration |
| Logstash/Elastic/Kibana | Ingestion, indexing, visualization stack | Operational footprint exceeds a one-file local investigation | No services, storage setup, or indexing |
| AWStats | Established log-reporting workflow | Report configuration is more than this CLI needs | Immediate terminal and pipeline output |
| grep/awk | Composable text processing | Quoted fields, denominators, tie handling, and error policies need custom scripts | Tested combined-log parsing and consistent semantics |

## 4. Unique Value Proposition

Get four reproducible nginx traffic summaries locally with one streaming command and a stable pipeline contract.

## 5. Business Model

Open source under MIT; no paid tier, advertising, telemetry, or monetization. Revenue, CAC, and LTV are not applicable. A maintainer contributes one weekend; ongoing work is voluntary and capped to avoid a support commitment. Publishing packages or sending anything externally requires later human approval.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved runtime, standard-library streaming and counters |
| Command interface | Click | Argument validation and help |
| Human presentation | Rich | Readable colored terminal tables |
| Records | dataclasses | Explicit parsed-record and report contracts |
| Packaging | pip / pyproject.toml | Familiar local installation |
| Verification | pytest, standard-library timing/resource tools | Offline correctness and measured capacity |

## 7. Timeline

| Window | Work | Result |
|---|---|---|
| Saturday, 8 hours | Implementation steps 1–4 | Packaging, parser, counters, CLI |
| Sunday, 8 hours | Steps 5–8 | Exports, terminal rendering, capacity evidence, handoff |

Scope is one weekend, approximately 16 engineering hours; cut optional scope rather than silently relaxing correctness or the performance target.

## 8. KPIs

Targets below are hypotheses, not observed adoption.

| Metric | 1 month | 3 months | 6 months |
|---|---|---|---|
| Correctness on canonical fixtures | Exact agreement | Maintain | Maintain |
| 1 GB benchmark on recorded laptop | <30 seconds | Maintain | Maintain |
| Engineers who complete a local smoke run | 3 | 10 | 20 |
| Paid infrastructure cost | $0 | $0 | $0 |

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python parser misses throughput goal | Medium | High | Benchmark representative data early; optimize only after profiling |
| Exact counters grow with distinct keys | High | High | Shared cardinality budget; fail with code 4, never approximate silently |
| Custom nginx formats are mistaken for combined | High | Medium | Support combined only; count malformed lines and document format |
| Logs contain sensitive URLs and control bytes | High | High | Local-only processing; sanitize terminal text; synthetic fixtures |
| Weekend scope expands | Medium | High | Keep Should/Could out of MVP |

## 10. Budget

| Item | Monthly cash | Comment |
|---|---|---|
| Runtime and libraries | $0 | Open-source dependencies |
| Hosting, database, API | $0 | None used |
| Development and benchmark machine | $0 incremental | Existing laptop |
| Labor | $0 cash | Approximately 16 volunteer hours; opportunity cost exists |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Combined-log file/stdin streaming and malformed-line policy | Must / P0 | All metrics depend on valid records |
| Exact four-metric aggregation with cardinality guard | Must / P0 | Core value and truthful results |
| Click command and exit contract | Must / P0 | Usable local interface |
| JSON and CSV exports | Must / P0 | Explicit pipeline requirement |
| Colored terminal report | Must / P0 | Default experience |
| Capacity benchmark and pip installation | Must / P0 | Approved delivery constraints |
| gzip file input | Should / P1 | Useful for rotated logs; later release |
| Customizable top-N | Could / P2 | MVP fixes N=10 |
| Auth, DB, HTTP API, server, cloud, Kubernetes | Won't | Explicit exclusions |
| Continuous follow mode, custom formats, geolocation | Won't for MVP | Expands parser or runtime scope |

### RICE Scoring

Planning estimates: confidence is converted to a decimal in R × I × C / E; one person-day is 8 hours. Dependencies take precedence over raw ranking. Scores order stories and feature work within those dependencies.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (days) | Score |
|---|---|---|---|---|---|
| Streaming parser | 10 | 5 | 80% | 0.25 | 160 |
| Exact aggregation and guard | 10 | 5 | 80% | 0.375 | 106.67 |
| CLI contract | 10 | 4 | 80% | 0.3125 | 102.4 |
| JSON/CSV | 8 | 4 | 80% | 0.3125 | 81.92 |
| Terminal report | 10 | 3 | 80% | 0.3125 | 76.8 |
| Capacity and pip validation | 10 | 4 | 60% | 0.4375 | 54.86 |
| gzip input (deferred) | 5 | 2 | 50% | 0.25 | 20 |

The Must effort totals two person-days. Packaging and fixtures are enabling runway included in the step estimates in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Definition of Done

- [ ] All P0 acceptance criteria in [PRD.md](PRD.md) pass.
- [ ] Unit/integration tests pass; parser and aggregation branch coverage reaches 90%.
- [ ] Installable wheel passes a clean Python 3.11 environment smoke test.
- [ ] End-to-end benchmark meets <30 seconds for 1,000,000,000 bytes on a documented laptop and stays below 512 MiB peak RSS for the specified fixture.
- [ ] Review completed; no known critical/high security defects.
- [ ] README examples and JSON/CSV/exit-code contracts match [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).
- [ ] Optional scope stays deferred; local installation is manually verified. No staging or deployment is needed.

Execution prompts are in [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md); project instructions and status are in [CLAUDE.md](CLAUDE.md). The separate external harness will perform the adversarial review; this session has not done so.
