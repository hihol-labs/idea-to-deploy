# Strategic Plan: Nginx Lens

## 1. Idea
Nginx Lens is an open-source local CLI for DevOps/SRE engineers who need quick incident summaries from nginx access logs. It reads records sequentially and reports top-10 IPs, top-10 URLs by combined 4xx/5xx errors, hourly request percentages, and the share of unique User-Agents. Python 3.11, Click, Rich, and dataclasses are approved. This blueprint specifies future work; no executable product exists yet.

## 2. Target audience
| Persona | Role | Pain | Response |
|---|---|---|---|
| On-call engineer | SRE | Needs a traffic/error summary during an incident | One command over a file or stdin |
| Platform engineer | DevOps | Needs reproducible pipeline output | Stable JSON/CSV and exit codes |
| Service maintainer | Small-team operator | Cannot fund or operate analytics infrastructure | Local pip-installable tool with no services |

## 3. Competitive analysis
These are qualitative positioning assessments, not measured comparative benchmarks or claims about current versions.

| Alternative | Approach | Trade-off for this brief | Our distinction |
|---|---|---|---|
| GoAccess | Dedicated access-log analysis | Broader interactive/reporting surface than these four metrics need | Narrow Python CLI and explicit export contract |
| Logstash/Elastic/Kibana | Ingestion, indexing, dashboards | Operating a stack conflicts with the weekend and $0 infrastructure scope | No ingestion service or retained index |
| AWStats | Periodic web traffic reports | Report-generation workflow differs from incident-time stdin analysis | One-pass invocation with pipeline outputs |
| grep/awk | Composable text processing | Quoting, timestamps, and consistent schemas become custom scripts | Tested combined-log parsing and deterministic reports |

## 4. Unique value proposition
Get four incident-focused metrics from a local nginx combined access log with one command, without installing a service or writing a custom parser.

## 5. Business model
Free open-source software, proposed MIT license, no paid tiers, telemetry, monetization, or customer acquisition spend. Volunteer development is the only labor assumption. LTV and CAC are not applicable to a commercial funnel; adoption and correctness are the useful measures.

## 6. Technology stack
| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, familiar to target engineers |
| Command interface | Click | Typed options and consistent usage errors |
| Terminal | Rich | Readable tables and terminal-aware colors |
| Domain objects | dataclasses | Explicit records and report types |
| Distribution | pip, pyproject.toml | Local install and console entry point |
| Verification | pytest and standard-library benchmark driver | Reproducible semantics and timing |

## 7. Timeline
| Period | Stage | Deliverable |
|---|---|---|
| Saturday morning | Steps 1–3 | Package, parser, exact aggregator |
| Saturday afternoon | Steps 4–6 | JSON/CSV, terminal, CLI error handling |
| Sunday | Steps 7–8 | Edge cases, benchmark, wheel and documentation |

Estimated active work: 16 hours for one engineer. The one-weekend budget is a constraint, not a measured delivery guarantee.

## 8. KPIs
| Metric | Month 1 | Month 3 | Month 6 |
|---|---|---|---|
| 1 GB benchmark on recorded reference laptop | <30 s | Maintain <30 s | Maintain <30 s |
| P0 acceptance cases | All pass | All pass | All pass |
| Successful documented fresh-environment install | Required | Required per release | Required per release |
| Confirmed silent metric corruption defects | 0 | 0 | 0 |

Adoption targets remain discovery inputs, not invented user counts. Performance is unmeasured until implementation; see [implementation plan](IMPLEMENTATION_PLAN.md).

## 9. Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python parser misses throughput target | Medium | High | Benchmark early; optimize measured hotspots without changing stack silently |
| Unique-key memory grows with hostile logs | High | High | Shared explicit cardinality budget; fail with code 4 before inserting new keys |
| Custom nginx formats parsed incorrectly | High | High | Support combined format only; count malformed records explicitly |
| Logs contain private URLs/IPs | High | Medium | Local processing, no telemetry; synthetic test fixtures; sanitize terminal control characters |
| Scope exceeds weekend | Medium | High | Defer Should/Could features; keep all Must metrics and exports |

## 10. Budget
| Item | Monthly cost | Notes |
|---|---|---|
| Runtime infrastructure | $0 | User's existing laptop |
| Dependencies and tooling | $0 | Open-source stack |
| Distribution | $0 | Local wheel/pip installation; public publishing is a separate authorized action |
| Labor | $0 cash | 16 volunteer hours; opportunity cost excluded |

## 11. Feature Roadmap
### MoSCoW
| Feature | Priority | Rationale |
|---|---|---|
| Combined-log file/stdin parser and malformed accounting | Must | Basis for correct reports |
| Four exact metrics with cardinality guard | Must | Core incident value and safe resource behavior |
| JSON and CSV export | Must | Explicit pipeline requirement |
| Colored terminal report | Must | Default user experience |
| pip-installable CLI and exit contract | Must | Usable delivery surface |
| More helpful custom-format diagnostics | Should | Useful after initial supported-format guidance |
| Shell completion | Could | Convenience after MVP |
| Auth, database, HTTP API, cloud, Kubernetes | Won't | Conflicts with local stateless scope |
| Live tail, gzip, multiple input files, custom formats | Won't | Protect weekend scope; pipe decompressed/concatenated data externally if needed |

### RICE scoring
Estimates only. Confidence is a fraction in the calculation: score = Reach × Impact × Confidence / Effort. Effort is person-days of eight hours; shared foundation/testing work is allocated across features.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort | Score |
|---|---|---|---|---|---|
| Parser and malformed accounting | 10 | 5 | 80% | 0.40 | 100 |
| Four metrics and guard | 10 | 5 | 80% | 0.50 | 80 |
| JSON/CSV | 8 | 4 | 80% | 0.35 | 73.14 |
| Terminal report | 10 | 3 | 80% | 0.35 | 68.57 |
| Packaging and CLI integration | 10 | 3 | 80% | 0.40 | 60 |
| Improved format diagnostics | 5 | 2 | 60% | 0.25 | 24 |

Use descending RICE after prerequisites: packaging skeleton precedes parser work; final packaging follows integration. P0/P1/P2 in [PRD](PRD.md) map to Must/Should/Could.

## Definition of Done
- All P0 acceptance cases and full test suite pass; core parser/aggregation branch coverage target is at least 90%.
- Exact metric fixtures, machine-output schema checks, and all five exit statuses are verified.
- Benchmark records hardware, corpus shape, cardinality, timing, and peak RSS; target is 1,000,000,000 bytes in under 30 seconds within the default cardinality limit.
- Wheel installs into a clean Python 3.11 virtual environment and help/example commands succeed.
- Documentation matches behavior, license is included, no known high/critical security issue remains, and a future code review is recorded.
- Local smoke verification replaces staging deployment: this product has no service to deploy.
- External adversarial review of this blueprint is pending outside this session. Its outcome is not claimed here.

See [architecture](PROJECT_ARCHITECTURE.md), [PRD](PRD.md), [implementation prompts](CLAUDE_CODE_GUIDE.md), and [agent context](CLAUDE.md).
