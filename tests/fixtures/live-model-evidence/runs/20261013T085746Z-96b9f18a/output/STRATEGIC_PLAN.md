# Strategic Plan: Nginx Lens

## 1. Idea

Nginx Lens is an open-source, local Python 3.11 CLI for DevOps/SRE engineers. It reads nginx combined access logs incrementally and emits top-10 IPs, top-10 URLs ranked by combined 4xx/5xx errors, hourly request percentages, and unique User-Agent share. Default output is colored terminal text; JSON and CSV support pipelines. The working distribution name is `nginx-lens`; availability must be checked before any public release.

## 2. Target Audience

| Persona | Role | Pain | Solution |
|---|---|---|---|
| On-call engineer | SRE | Needs a quick picture of an incident from a copied access log | One local command with error URL rankings |
| Service operator | DevOps | Cannot provision analytics infrastructure for occasional investigations | pip installation and file/stdin input |
| Automation author | Platform engineer | Shell summaries drift between teams | Stable JSON and CSV schemas and exit codes |

## 3. Competitive Analysis

Qualitative positioning, not a current feature or pricing audit.

| Alternative | Approach | Tradeoff for this brief | Our distinction |
|---|---|---|---|
| GoAccess | Dedicated access-log analysis and reporting | Broader reporting surface than the four required summaries | Small Python CLI with a fixed machine-output contract |
| Logstash/Elastic/Kibana | Ingest, store, search, and visualize logs | Operating a persistent analytics stack exceeds a weekend and local-only scope | No services or persistent store |
| AWStats | Periodic web traffic statistics | Report-generation workflow is more than an ad hoc terminal investigation requires | One invocation over a file or pipe |
| grep/awk | Composable text processing | Quoting, malformed lines, and output consistency become script maintenance | Explicit parser, denominators, and reproducible ordering |

## 4. Unique Value Proposition

Turn a local nginx access log into four deterministic, pipeline-ready operational summaries with one pip-installed command and no infrastructure.

## 5. Business Model

Free and open source, with a proposed MIT license at implementation. No paid tiers, billing, or monetization. LTV and CAC are not monetary planning metrics for this project; distribution is through source and pip packaging. Maintenance is voluntary and local processing creates no hosted per-user expense.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved stack and standard parsing/serialization libraries |
| Commands | Click | Typed arguments, mutually exclusive output validation, help |
| Terminal | Rich | Readable tables and TTY-aware color |
| Models | dataclasses | Explicit in-memory record and report contracts |
| Packaging | pyproject.toml and pip | Installable wheel and console entry point |
| Verification | pytest, coverage, standard timing tools | Semantic checks and measured performance |

## 7. Timeline

| Weekend period | Work | Outcome |
|---|---|---|
| Saturday morning | Package, CLI contract, parser | Valid records and deterministic failures |
| Saturday afternoon | Counters and report model | Four exact metrics |
| Sunday morning | Terminal and exports | Usable human and pipeline outputs |
| Sunday afternoon | Edge cases, benchmark, packaging | Release candidate with recorded evidence |

Plan assumes one developer and 16 focused hours. Further calendar commitments are excluded.

## 8. KPIs

Targets are hypotheses, not achieved results. No product telemetry; feedback is voluntary.

| Metric | Month 1 target | Month 3 target | Month 6 target |
|---|---|---|---|
| P0 acceptance suite | Passing on Python 3.11 | Remains passing | Remains passing |
| 1 GB baseline processing | Under 30 seconds on recorded laptop | No regression on same fixture | No regression on same fixture |
| Engineer pilot feedback | 3 voluntary trials | 5 cumulative trials | 10 cumulative trials |
| Reporting correctness defects | No known release-blocking defects | Same | Same |

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python parser misses throughput target | Medium | High | Benchmark early; optimize measured bottleneck before adding optional features |
| Distinct keys grow with input | High | High | Exact bounded dictionaries; fail with exit 4 before exceeding configured cardinality |
| Custom nginx formats differ from combined | High | Medium | Explicit combined-only grammar; malformed counts and exit 3 |
| Sensitive URLs/IPs escape into reports | Medium | High | Local-only operation, strip query strings, document report sensitivity |
| Weekend scope grows | Medium | High | Freeze P0; defer all P1/P2 work until release criteria pass |

## 10. Budget

| Item | Monthly cash | Comment |
|---|---|---|
| Hosting/database/cloud | $0 | None used |
| Runtime and libraries | $0 | Open-source stack |
| Development/testing | $0 | Existing laptop; 16 hours donated labor |
| Distribution | $0 planned | Local wheel and source install; public publication is a later action |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Combined-log file/stdin streaming and validation | Must / P0 | Foundation for every result |
| Four exact metrics with cardinality guard | Must / P0 | Core product value and defined resource behavior |
| Colored terminal report | Must / P0 | Default on-call workflow |
| JSON and CSV exports | Must / P0 | Approved pipeline requirement |
| pip packaging, help, and exit codes | Must / P0 | Usable installation and automation |
| Native gzip input | Should / P1 | Convenience; external decompression already works |
| Shell completion | Could / P2 | Optional usability polish |
| Auth, database, HTTP API, server, cloud, Kubernetes | Won't | Explicit constraints |
| Custom formats, live dashboard, follow mode, approximate counts | Won't for MVP | More semantics and testing than the weekend permits |

### RICE Scoring

Confidence is expressed as a fraction for calculation: R × I × C / E. These are planning estimates, not measured adoption. One person-day is eight hours. Feature estimates cover feature work; the remaining weekend allowance covers verification and integration.

| Feature | Reach | Impact | Confidence | Effort (days) | Score |
|---|---|---|---|---|---|
| Streaming and validation | 10 | 5 | 80% | 0.25 | 160 |
| Four metrics and guard | 10 | 5 | 80% | 0.375 | 106.67 |
| Colored terminal | 8 | 3 | 90% | 0.25 | 86.4 |
| JSON/CSV | 8 | 4 | 80% | 0.375 | 68.27 |
| Packaging/help/exit codes | 10 | 4 | 90% | 0.625 | 57.6 |
| Native gzip | 5 | 2 | 70% | 0.25 | 28 |

Deliver in descending value order subject to dependencies: package and exit-code skeleton precede parsing; final packaging follows outputs. P1 is outside the weekend commitment.

## Definition of Done

- [ ] All P0 acceptance criteria in [PRD.md](PRD.md) pass.
- [ ] Core parser and aggregation branch coverage reaches 90%; integration tests pass.
- [ ] Human/code review is recorded and any required external architecture conditions are resolved.
- [ ] No known critical/high security issues remain after review of input and output handling.
- [ ] Under-30-second performance target and peak RSS are measured on a documented laptop and fixture.
- [ ] Wheel installs in a clean environment and file/stdin smoke checks succeed.
- [ ] README and schemas match actual behavior; no claim of an untested release.

Local clean-environment installation replaces staging deployment. No runtime criteria are achieved by this blueprint alone. See [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), and [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md).
