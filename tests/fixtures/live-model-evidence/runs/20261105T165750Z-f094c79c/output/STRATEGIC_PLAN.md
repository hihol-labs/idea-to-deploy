# Strategic Plan: Nginx Lens

## 1. Idea

Nginx Lens is an open-source Python 3.11 CLI for DevOps/SRE engineers investigating local nginx access logs. It reads a file or stdin incrementally and emits top-10 IPs by request count, top-10 URLs by combined 4xx/5xx count, hourly request percentages, and the share of unique User-Agents. Rich terminal output is the default; JSON and CSV support pipelines. This blueprint plans the product; no implementation or performance result exists yet.

## 2. Target Audience

| Persona | Role | Pain | Response |
|---|---|---|---|
| Incident responder | On-call SRE | Needs traffic and error concentration during an incident | One command with four repeatable summaries |
| Platform engineer | DevOps maintainer | Ad hoc shell scripts differ across machines | Stable JSON/CSV schemas and exit codes |
| Service owner | Engineer on a small team | A persistent analytics stack exceeds the available budget | Local pip installation and no running services |

## 3. Competitive Analysis

These are qualitative positioning hypotheses, not a current benchmark or a claim about latest releases.

| Alternative | Approach | Trade-off for this brief | Our distinction |
|---|---|---|---|
| GoAccess | Specialized access-log reporting | Broader interactive reporting than this narrow Python workflow needs | Fixed four-metric contract and pipeline exports |
| Logstash/Elastic/Kibana | Ingestion, indexing, search, visualization | Persistent stack exceeds the explicit infrastructure scope | Single local process, no ingestion service |
| AWStats | Log-based statistical reporting | Report-generation workflow differs from immediate CLI inspection | stdin-first invocation with deterministic exports |
| grep/awk | Composable text-processing tools | Parsing, escaping and metric definitions become local scripts | Tested combined-log grammar and shared metric semantics |

## 4. Unique Value Proposition

Turn a local nginx combined access log into four precisely defined incident summaries with one pip-installable command and no infrastructure.

## 5. Business Model

Free software under MIT, without paid tiers, telemetry or monetization. LTV and CAC are not applicable to this volunteer utility. Distribution is a Python wheel and source archive; publishing is a separate human-approved action. Maintenance cost is contributor time.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved local runtime |
| CLI | Click | Argument parsing and usage errors |
| Presentation | Rich | Colored terminal tables |
| Domain model | dataclasses, standard-library counters | Small explicit contracts |
| Packaging | pip, pyproject.toml, setuptools | Installable wheel and console entry point |
| Verification | pytest, standard-library timing/resource tooling | Correctness and reproducible performance evidence |

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Steps 1–3 | Packaging, parser and exact aggregates |
| Saturday afternoon | Steps 4–5 | Machine output and terminal output |
| Sunday | Steps 6–8 | Failure handling, performance measurement and local release validation |

Budget approximately 16 engineering hours; optional features move beyond the weekend if Must work slips. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## 8. KPIs

Targets below are goals, not measured adoption or speed.

| Metric | Month 1 | Month 3 | Month 6 |
|---|---|---|---|
| Validated fixture correctness | All acceptance fixtures | Maintain | Maintain |
| Supported 1 GB benchmark | Under 30 s on declared laptop | No regression | No regression |
| Successful fresh-environment install | Python 3.11 | Maintain | Maintain |
| Unresolved critical correctness defects | 0 at release | 0 | 0 |

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python parsing misses speed target | Medium | High | Benchmark early; profile before optimizing; report failure honestly |
| Unique IP/path/UA counts exhaust memory | High for hostile input | High | Aggregate cardinality budget, fail with code 4 before insertion |
| nginx custom formats vary | High | Medium | Support documented combined grammar only; count rejected lines |
| Sensitive values leak through rendering | Medium | High | No telemetry, escape terminal markup, warn users to handle exports as log data |
| Weekend scope expands | Medium | High | Freeze Must scope; no server, database or follow mode |

## 10. Budget

| Item | Monthly cash | Comment |
|---|---|---|
| Runtime and libraries | $0 | Open-source stack |
| Hosting and database | $0 | Neither exists |
| Local testing | $0 incremental | Existing laptop; volunteer time is not a cash purchase |
| Total | $0 | No paid dependencies or services |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| File/stdin combined-log streaming and validation | Must | All metrics need valid records |
| Exact four-metric aggregation | Must | Core value proposition |
| JSON/CSV export | Must | Required pipeline interface |
| Colored terminal summary | Must | Required default experience |
| Resource limits and complete failure contract | Must | Prevent misleading output or memory exhaustion |
| pip packaging and local installation | Must | Required distribution route |
| Additional fixture-based troubleshooting examples | Should | Reduces support time after MVP |
| Shell completion | Could | Convenience after weekend |
| Auth, database, HTTP API, cloud, Kubernetes | Won't | Contradicts approved local scope |
| Custom log formats, gzip, live follow, approximate sketches | Won't | Requires additional semantics and testing |

### RICE Scoring

Estimates use normalized reach 1–10, impact 1–5 and confidence as a decimal. Effort is person-days of eight hours; scores are planning assumptions. Shared verification effort is accounted for in the implementation schedule.

| Feature | Reach | Impact | Confidence | Effort | RICE |
|---|---|---|---|---|---|
| Streaming parser | 10 | 5 | 80% | 0.30 | 133.33 |
| Exact metrics | 10 | 5 | 80% | 0.30 | 133.33 |
| JSON/CSV | 8 | 4 | 80% | 0.25 | 102.40 |
| Terminal summary | 10 | 3 | 80% | 0.25 | 96.00 |
| Resource/failure handling | 10 | 5 | 70% | 0.40 | 87.50 |
| pip packaging | 10 | 4 | 90% | 0.50 | 72.00 |
| Extra troubleshooting examples | 5 | 2 | 60% | 0.25 | 24.00 |

Order follows descending score subject to dependencies: packaging skeleton comes first, final packaging verification last. Minimal resource checks accompany aggregation, with comprehensive failure verification later. P0/P1/P2 in [PRD.md](PRD.md) correspond to Must/Should/Could.

## Definition of Done

- [ ] P0 acceptance criteria pass, including all exit codes and empty input.
- [ ] Unit and integration suites pass; core parser/aggregate branch coverage reaches 90%.
- [ ] Local wheel installs and CLI smoke test succeeds in a fresh Python 3.11 environment.
- [ ] Benchmark meets the target using the protocol in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).
- [ ] Correctness review and dependency/security checks find no unresolved critical/high defects.
- [ ] Documentation matches behavior; all implementation steps have evidence.
- [ ] External adversarial review is completed separately; no review is claimed in this blueprint session.

Staging deployment is inapplicable: local installation is the release validation target. Contributor instructions live in [CLAUDE.md](CLAUDE.md); execution prompts live in [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md).
