# Strategic Plan: Nginx Lens

## 1. Idea

Nginx Lens is an open-source Python 3.11 CLI for DevOps/SRE engineers inspecting local nginx access logs. It reads one file or stdin incrementally and produces top-10 IPs, top-10 URLs by 4xx/5xx error count, hourly request percentages, and the share of unique User-Agents. Rich terminal output is the default; JSON and CSV serve pipelines. This blueprint specifies a future implementation; no product code exists yet.

## 2. Target Audience

| Persona | Role | Pain | Resolution |
|---|---|---|---|
| On-call responder | SRE | Needs traffic and error concentration during an incident | One local command with deterministic rankings |
| Platform operator | DevOps engineer | Has exported logs but no analytics infrastructure | File/stdin input without services or setup |
| Automation author | SRE | Needs the same metrics in scripts | Stable JSON/CSV and explicit failure codes |

## 3. Competitive Analysis

These are scope-based alternatives, not benchmarked performance or market-share claims.

| Alternative | Approach | Trade-off for this brief | Our distinction |
|---|---|---|---|
| GoAccess | Dedicated access-log analytics and reports | Broader reporting workflow than this fixed metric contract | Small Python CLI with explicit pipeline schemas |
| Logstash/Elastic/Kibana | Ingest, index and explore logs | Persistent service stack exceeds the $0 weekend/local scope | No infrastructure or retained log store |
| AWStats | Log-derived reporting | Report-oriented workflow exceeds immediate terminal inspection | Single invocation and machine-readable stdout |
| grep/awk | Composable text filtering and counting | Teams must maintain parsing and metric conventions themselves | Tested nginx parser and consistent denominators |

## 4. Unique Value Proposition

Turn a local nginx combined log into four actionable, reproducible summaries with one pip-installed command and no service dependencies.

## 5. Business Model

Free software under MIT; no paid tiers, advertising, telemetry or hosted product. Revenue, LTV and paid CAC are inapplicable; distribution is repository documentation and optional future community sharing. Developer time is donated and is not a $0 labor valuation. Local runtime uses the user's existing laptop.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved ecosystem and local portability |
| Arguments | Click | Explicit CLI validation and help |
| Terminal | Rich | Readable colored tables with escaped untrusted text |
| Domain records | dataclasses | Typed records without extra framework |
| Distribution | pip, pyproject.toml, setuptools | Conventional wheel and console entry point |
| Verification | pytest, standard-library benchmark tools | Local repeatable checks without paid services |

## 7. Timeline

| Weekend block | Stage | Result |
|---|---|---|
| Saturday, 8 hours | Contracts, parser, exact aggregates | Tested streaming domain layer |
| Sunday, 8 hours | CLI, exports, performance, packaging | Locally validated wheel candidate |

The eight steps and estimates are in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Performance risk is checked early enough to stop scope expansion.

## 8. KPIs

These are proposed goals, not measured outcomes or adoption forecasts.

| Metric | 1 month | 3 months | 6 months |
|---|---|---|---|
| Correctness on golden valid fixtures | 100% | 100% | 100% |
| 1 GB accepted benchmark, regular file to JSON | <30 seconds | <30 seconds | <30 seconds |
| Peak RSS on that benchmark | <=512 MiB | <=512 MiB | <=512 MiB |
| Formats covered by integration checks | text, JSON, CSV | all retained | all retained |
| Observed first-use local setup after dependencies cached | <=30 seconds | <=30 seconds | <=30 seconds |

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python parser misses throughput target | Medium | High | Benchmark parser early; profile locally; optimize hot path before polish |
| Unique keys grow with input size | High | High | Exact shared cardinality/key-byte limits; exit 4 without misleading report |
| Custom nginx formats are mistaken for combined logs | High | Medium | Explicit supported grammar, skipped-line accounting, exit 1 |
| Logs contain terminal controls or spreadsheet formulas | Medium | Medium | Escape terminal text; document raw machine data as untrusted |
| Weekend time runs out | Medium | High | Keep P1/P2 deferred; cut cosmetic work before correctness |

## 10. Budget

| Item | Monthly cash | Comment |
|---|---|---|
| Runtime and tests | $0 | Existing laptop, local fixtures |
| Dependencies and license | $0 | Open-source stack; verify licenses before release |
| Hosting, database, cloud | $0 | None required |
| Paid acquisition | $0 | None planned |
| Labor | $0 cash budget | Estimated 16 donated engineering hours |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Combined-log file/stdin streaming parser | Must | Every metric depends on valid requests |
| Top-10 IPs and error URLs | Must | Core incident triage |
| UTC hourly percentages and unique User-Agent share | Must | Required traffic summaries |
| Colored terminal report | Must | Default user experience |
| JSON and CSV exports | Must | Approved pipeline use |
| Exactness guards, diagnostics, pip install | Must | Trustworthy local operation |
| Gzip file convenience | Should | Useful after MVP; shell decompression works now |
| Status-family drilldown beyond the combined ranking | Could | Additional analysis after validation |
| Auth, database, HTTP API, server, cloud, Kubernetes | Won't | Explicit constraints |
| Follow mode, custom log-format DSL, approximate cardinality | Won't | Exceeds weekend contract |

### RICE Scoring

Estimates use reach on 1–10, impact on 1–5 and confidence as a fraction in the calculation. They are planning assumptions. Scores guide order subject to dependencies; effort totals include integration and tests.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE Score |
|---|---|---|---|---|---|
| Parser and streaming input | 10 | 5 | 80% | 0.35 | 114.29 |
| Top IP and error URL rankings | 10 | 5 | 80% | 0.35 | 114.29 |
| Hourly percentages and UA share | 10 | 4 | 80% | 0.30 | 106.67 |
| Terminal report | 10 | 3 | 90% | 0.30 | 90.00 |
| JSON/CSV exports | 8 | 4 | 80% | 0.40 | 64.00 |
| Exactness guards, diagnostics, pip install | 10 | 5 | 70% | 0.30 | 116.67 |
| Gzip convenience (deferred) | 4 | 2 | 60% | 0.25 | 19.20 |

Implement guard/packaging foundations first, then parser, rankings, percentages, terminal and exports. End-to-end hardening closes the weekend. P1 gzip is outside that estimate.

## Definition of Done

- [ ] All P0 acceptance criteria in [PRD.md](PRD.md) pass.
- [ ] Unit and integration suites pass; parser/aggregate branch coverage >=90%.
- [ ] Exact results agree across renderers and golden fixtures.
- [ ] End-to-end 1 GB performance and RSS targets are measured on a recorded laptop profile.
- [ ] Wheel installs in a clean Python 3.11 virtual environment; help and stdin flow work.
- [ ] Documentation and CLI help match [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).
- [ ] Independent product-code review and dependency/license checks complete before release.
- [ ] Local manual verification succeeds; no staging service is applicable.

Blueprint generation alone does not satisfy product DoD. The external harness owns the subsequent adversarial architecture review.
