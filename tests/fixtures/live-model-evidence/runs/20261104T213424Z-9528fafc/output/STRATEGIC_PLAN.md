# Strategic Plan: nginx-scan

## 1. Idea

An open-source Python 3.11 CLI for DevOps/SRE engineers that reads nginx combined access logs once and reports top-10 IPs, top-10 URLs by 4xx/5xx errors, hourly request percentages, and unique User-Agent share. It prints colored terminal text by default and supports JSON and CSV for pipelines. This blueprint is planning only; product implementation and performance verification remain future work.

## 2. Target audience

| Persona | Role | Pain | Response |
|---|---|---|---|
| On-call engineer | SRE | Needs a quick incident summary from an exported log | One command, no services |
| Platform engineer | DevOps | Repeated ad hoc scripts yield incompatible reports | Stable JSON/CSV contract |
| Small-site operator | Generalist | Monitoring infrastructure exceeds available time and budget | Local pip installation, $0 infrastructure |

## 3. Competitive analysis

These are qualitative positioning assumptions, not a current feature or price audit. No external research was performed.

| Alternative | Approach | Trade-off for this brief | Our difference |
|---|---|---|---|
| GoAccess | Dedicated access-log analytics and reporting | Broader interactive/reporting workflow than the required fixed summary | Narrow Python CLI and explicit pipeline schema |
| Logstash/Elastic/Kibana | Ingestion, indexed search and dashboards | Persistent infrastructure conflicts with the local stateless constraint | No deployment, indexing or retained data |
| AWStats | Scheduled log reporting | Historical/report-generation workflow exceeds a one-shot summary | Read stdin or a file directly |
| grep/awk | Shell text processing | Each team maintains its own parsing and report logic | Shared parser, deterministic metrics and tested exports |

## 4. Unique value proposition

Turn a local nginx combined log into four deterministic incident summaries with one pip-installed command and no infrastructure.

## 5. Business model

MIT open source; no paid tier, subscriptions, advertising or telemetry. Price, infrastructure spend and cash acquisition budget are $0. Volunteer maintenance and documentation are the support model. LTV and CAC are not revenue metrics here; track usefulness through reproducible reports and voluntary adoption feedback.

## 6. Technology stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved stack; standard-library streaming I/O |
| CLI | Click | Argument validation and shell-friendly errors |
| Terminal | Rich | Readable tables with TTY-aware color |
| Models | dataclasses | Explicit parsed records and report schema |
| Packaging | pip, pyproject.toml, setuptools | Local installable command |
| Tests | pytest, Click CliRunner | Golden metrics and observable CLI behavior |

See [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for runtime contracts.

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Steps 1–3 | Package scaffold, parsing and exact aggregation |
| Saturday afternoon | Steps 4–5 | Terminal and machine outputs |
| Sunday morning | Steps 6–7 | Failure handling and performance measurement |
| Sunday afternoon | Step 8 | Local wheel smoke test and documentation |

One developer, approximately 16 focused hours. Follow [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md); reduce deferred polish before compromising correctness.

## 8. KPIs

Targets are hypotheses, not measured results.

| Metric | First month | Three months | Six months |
|---|---|---|---|
| Runtime for declared 1 GB benchmark | <30 seconds | Preserve target | Preserve target |
| Exact golden-fixture results | All fixtures agree | No semantic regressions | No semantic regressions |
| Local install to first report after prerequisites | <30 seconds | Preserve | Preserve |
| Voluntary real-user feedback reports | 3 | 10 | 20 |

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python parsing misses throughput goal | Medium | High | Benchmark early; optimize measured hot path without changing metrics |
| High-cardinality inputs exhaust memory | High | High | Explicit cardinality/line limits; fail with code 4 instead of approximate answers |
| Custom nginx formats parse incorrectly | High | High | Combined format only; strict grammar, count malformed lines |
| Offsets distort hourly interpretation | Medium | Medium | Normalize timestamps to UTC before bucketing |
| Weekend scope grows | Medium | High | P0 only; defer Should/Could features |

## 10. Budget

| Item | Monthly cash | Comment |
|---|---|---|
| Runtime and storage | $0 | Existing laptop; no hosted service |
| Dependencies and tooling | $0 | Open-source tools |
| Delivery labor | $0 cash | Approximately 16 donated hours, real opportunity cost |
| Distribution | $0 | Local wheels; any public publishing needs separate approval |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Combined log file/stdin parser | Must | All reports depend on valid records |
| Four exact metrics | Must | Core value proposition |
| Colored terminal tables | Must | Default engineer workflow |
| JSON and CSV reports | Must | Required pipeline interfaces |
| Bounded resources and documented errors | Must | Safe processing of large, untrusted logs |
| pip-installable package | Must | Approved delivery mechanism |
| gzip input | Should | Useful convenience after MVP |
| Configurable top-N | Could | Polish; MVP is fixed top-10 |
| Auth, database, HTTP API, server, cloud, Kubernetes | Won't | Explicitly excluded |
| Live tailing, custom formats, dashboards | Won't | Beyond weekend scope |

### RICE scoring

Planning estimates use confidence as a decimal in R × I × C / E. Reach is a relative 1–10 score, impact 1–5, effort person-days; scores are not market evidence.

| Feature | Reach | Impact | Confidence | Effort | Score |
|---|---|---|---|---|---|
| Combined parser | 10 | 5 | 80% | 0.25 | 160 |
| Four metrics | 10 | 5 | 80% | 0.30 | 133.33 |
| Resource/error contract | 10 | 4 | 80% | 0.30 | 106.67 |
| Terminal tables | 10 | 3 | 80% | 0.25 | 96 |
| JSON/CSV | 8 | 4 | 80% | 0.30 | 85.33 |
| pip packaging | 10 | 3 | 90% | 0.30 | 90 |
| gzip | 6 | 2 | 60% | 0.20 | 36 |

Priority order by score: parser, metrics, resource handling, terminal, packaging, exports, gzip. Dependency setup precedes parser; final packaging verification follows exports. Resource handling starts with aggregation and completes during CLI integration. Gzip is deferred regardless of score.

## Definition of Done

A product feature is done when its [PRD](PRD.md) acceptance criteria pass; unit and CLI integration tests run green; core parser/aggregation coverage is at least 90%; documentation matches outputs; local wheel installation works; no known high/critical security defect remains; and review findings are resolved. Release readiness also requires a recorded performance run on declared hardware and an independently reviewed candidate. Local wheel smoke testing replaces staging deployment because this is a CLI. No code, coverage, performance or review result is claimed by this blueprint.

Execution prompts: [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md). Session rules: [CLAUDE.md](CLAUDE.md).
