# Strategic Plan: Nginx Lens

## 1. Idea
Nginx Lens is an open-source, local Python 3.11 CLI for DevOps/SRE engineers. It streams finite nginx access-log files or stdin and reports top-10 IPs, top-10 URL paths by combined 4xx/5xx errors, hourly request percentages, and unique User-Agent share. Colored terminal output supports investigation; JSON and CSV support pipelines. This blueprint specifies future implementation; no product code or performance measurements exist yet.

## 2. Audience
| Persona | Role | Pain | Response |
|---|---|---|---|
| Incident responder | On-call SRE | Needs traffic and error hotspots during an incident | One local command with four summaries |
| Platform engineer | DevOps | Needs scriptable reports without operating a service | Stable JSON/CSV and exit codes |
| Small-site operator | Infrastructure generalist | Has logs but no analytics infrastructure budget | pip installation and offline processing |

## 3. Competitive Analysis
These are positioning alternatives supplied in the brief, not a current feature audit or measured comparison.

| Alternative | Typical approach | Trade-off for this brief | Our differentiation |
|---|---|---|---|
| GoAccess | Dedicated access-log reporting | Broader reporting surface than the four requested summaries | Narrow Python CLI contract with predictable pipeline outputs |
| Logstash/Elastic/Kibana | Ingestion, indexing, visualization stack | Operating an indexing stack exceeds this project's budget and scope | No service or storage setup |
| AWStats | Established log-report generation workflow | Historical reporting workflow exceeds a one-shot incident summary | Ephemeral stdin/file analysis |
| grep/awk | Custom shell pipelines | Multiple scripts must agree on quoting, denominators, and failures | One tested parsing and metric contract |

## 4. Unique Value Proposition
Turn a local nginx combined access log into four reproducible incident summaries with a single pip-installed command and no infrastructure.

## 5. Business Model
Free open source under MIT; no paid tiers, hosted product, telemetry, or monetization. LTV, CAC, and paid unit economics are inapplicable. Distribution is intended through pip; publishing needs separate human authorization. User support is best-effort issue triage.

## 6. Technology Stack
| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved portable runtime |
| CLI | Click | Argument validation and shell-friendly errors |
| Terminal | Rich | Tables and TTY color |
| Models | dataclasses | Explicit transient records and summaries |
| Processing | stdlib iterators, dictionaries, sets | Single-process streaming with explicit limits |
| Packaging/tests | pyproject.toml, pip, pytest | Installability and repeatable verification |

## 7. Timeline
| Period | Stage | Deliverable |
|---|---|---|
| Saturday morning | Packaging, parser, aggregation | Steps 1–4 in implementation plan |
| Saturday afternoon | Reports and CLI behavior | Steps 5–6 |
| Sunday | Integration, profiling, documentation | Steps 7–8 |

Estimated focused effort: 16 hours for one engineer; Should/Could work is deferred if the critical path slips.

## 8. KPIs
These are targets, not observed results.

| Metric | Month 1 | Month 3 | Month 6 |
|---|---|---|---|
| Correctness | All golden metric fixtures pass | Remains passing | Remains passing |
| Throughput | 1 GB (1,000,000,000 bytes) under 30 s on recorded laptop | No regression | No regression |
| Resource behavior | Explicit cardinality cap and no unbounded line allocation | Stable | Stable |
| Adoption | 3 volunteer SRE trials | 10 repeat users | 20 repeat users |
| Usability | Install and first report under 30 s with prerequisites ready | Same | Same |

## 9. Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python parser misses throughput goal | Medium | High | Benchmark early; profile hot path; do not claim success without timing |
| Adversarial unique fields exhaust RAM | High | High | Global exact-cardinality limit, bounded lines, exit 4 |
| Custom nginx formats misparse | High | High | Support combined format only; document rejects and invalid counts |
| Log output exposes sensitive values | Medium | High | Local execution, strip URL query/fragment, escape terminal control characters |
| Weekend scope slips | Medium | Medium | Freeze Must scope and defer Should/Could |

## 10. Budget
| Item | Monthly cash | Comment |
|---|---|---|
| Runtime and libraries | $0 | Open-source dependencies |
| Hosting/database | $0 | None |
| Tooling/distribution | $0 | Local tools; intended pip distribution |
| Labor | $0 cash | 16 volunteer engineering hours, not zero effort |

## 11. Feature Roadmap
### MoSCoW
| Feature | Priority | Rationale |
|---|---|---|
| File/stdin combined-log parsing and invalid-line accounting | Must | Every report depends on trustworthy input |
| Top-10 IPs and error URL paths | Must | Core incident questions |
| Hourly percentage distribution and unique User-Agent share | Must | Required traffic and diversity summaries |
| Colored terminal, JSON, CSV | Must | Interactive and pipeline use |
| Exact counters, resource bounds, exit codes 0/1/2/3/4 | Must | Reliable scripts and safe resource failure |
| Measured performance and pip packaging | Must | Explicit delivery constraints |
| Gzip input | Should | Convenient for archived logs; post-weekend |
| Custom log-format configuration | Could | Broader compatibility after stable parser |
| Auth, DB, HTTP API, server, cloud, Kubernetes, live tail | Won't | Contradicts local finite streaming scope |

### RICE Scoring
Planning estimates; confidence uses a decimal in calculations (80% = 0.8). Reach is relative 1–10, impact 1–5, effort person-days. Scores order work within dependency constraints; shared setup and final verification account for remaining weekend effort.

| Feature | Reach | Impact | Confidence | Effort | RICE |
|---|---|---|---|---|---|
| Input parsing | 10 | 5 | 80% | 0.25 | 160 |
| Top IP/error URL metrics | 10 | 5 | 80% | 0.25 | 160 |
| Hourly/UA metrics | 10 | 4 | 80% | 0.25 | 128 |
| Resource bounds and exit contract | 10 | 5 | 80% | 0.35 | 114.29 |
| Terminal/JSON/CSV reports | 10 | 4 | 80% | 0.40 | 80 |
| Packaging/performance evidence | 10 | 5 | 60% | 0.50 | 60 |
| Gzip input | 5 | 2 | 70% | 0.25 | 28 |

## Definition of Done
- [ ] All P0 criteria in [PRD.md](PRD.md) pass automated tests, including every exit code and output schema.
- [ ] Parser and aggregation branch coverage is at least 90%; full suite passes.
- [ ] Clean Python 3.11 environment installs the wheel and runs every output mode.
- [ ] Recorded laptop benchmark meets the target, with input/cardinality and peak RSS recorded.
- [ ] Code review accepted; no known critical/high security issues.
- [ ] Documentation matches delivered behavior; separate human authorization precedes publishing.

No staging service exists. Local wheel installation is the delivery validation. Adversarial architecture review is deferred to the external harness and is not claimed here.

## Related Documents
[Architecture](PROJECT_ARCHITECTURE.md), [PRD](PRD.md), [implementation plan](IMPLEMENTATION_PLAN.md), [execution guide](CLAUDE_CODE_GUIDE.md), [project instructions](CLAUDE.md), [quick start](README.md).
