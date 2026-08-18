# Strategic Plan: Nginx Stream Insights

## 1. Idea Overview

Nginx Stream Insights is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx combined access logs as a stream and produces four operational summaries: top-10 client IPs, top-10 URLs returning 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich colored text is the default; stable JSON and CSV modes support automation.

The MVP is deliberately local and stateless. It has no authentication, database, HTTP API, server, cloud service, or Kubernetes dependency. Delivery is constrained to one weekend and $0 operating budget.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Incident responder | Needs a fast first picture from a large log without uploading sensitive data | One command, streaming memory use, terminal summary |
| Platform engineer | Pipeline maintainer | Needs machine-readable metrics in shell/CI workflows | Stable `--json` and `--csv` schemas and explicit exit codes |
| DevOps generalist | Small-team operator | Full observability stacks are excessive for ad-hoc analysis | Zero-service pip install and local execution |

## 3. Competitive Analysis

| Alternative | Strength | Limitation for this use case | Our distinction |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI/config surface than a focused pipeline tool | Small fixed metric contract and JSON/CSV-first automation |
| Logstash + Elastic + Kibana | Powerful ingestion, search, dashboards | Operational cost and persistent infrastructure are disproportionate | Stateless, local, no services, $0 runtime budget |
| AWStats | Established historical web analytics | Persistent report workflow and legacy-oriented UX | Incident-oriented streaming CLI with modern output contracts |
| `grep`/`awk` pipelines | Universal and flexible | Easy to misparse quoted fields; hard to make metrics and errors consistent | Tested nginx parser, bounded behavior, reproducible output |

## 4. Unique Value Proposition

Get the four nginx incident summaries most often needed from gigabyte-scale logs, locally and pipeline-safely, with one installable command and no observability stack.

## 5. Business Model

Open-source utility under a permissive license. There are no paid tiers, hosted costs, CAC, or revenue targets in the MVP. Value is measured by reliable operational use and community adoption; contribution and maintenance costs are time only.

## 6. Technology Stack

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved runtime, broad operator availability |
| CLI | Click | Predictable options, help, validation, and exit handling |
| Terminal UI | Rich | Readable colored tables with terminal capability handling |
| Domain models | `dataclasses` | Explicit records without extra runtime dependencies |
| Packaging | pip-compatible `pyproject.toml` | Standard isolated installation and console entry point |
| Testing | pytest | Focused unit, integration, and performance regression tests |

## 7. Timeline

| Block | Work | Outcome |
|---|---|---|
| Saturday morning | Packaging, domain contracts, parser | Installable skeleton and validated streaming records |
| Saturday afternoon | Aggregation and text report | Four correct metrics in terminal mode |
| Sunday morning | JSON/CSV, error contracts | Pipeline-safe formats and exit semantics |
| Sunday afternoon | tests, 1 GB benchmark, docs, polish | Release candidate meeting quality and performance gates |

## 8. KPIs

| Metric | First release | Month 1 | Month 3 |
|---|---:|---:|---:|
| Processing time for a representative 1 GB log on the reference laptop | < 30 s | < 30 s | < 25 s if profiling justifies optimization |
| Peak memory on representative 1 GB log | Documented and bounded by distinct-value state | No regression > 10% | Cardinality strategy validated on field logs |
| Correctness fixture coverage | All four metric families and all exit codes | No open P0 defects | No known schema-breaking regressions |
| Adoption signal | Releasable package | 10 successful operator runs | 25 stars or 5 recurring users |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| High-cardinality IP, URL, or User-Agent values exhaust memory | Medium | High | Track explicit cardinality budget; terminate with exit code 4 rather than swap or corrupt results |
| Real nginx formats differ from combined format | High | Medium | State the accepted grammar, count malformed lines, reject wholly unusable input, defer configurable formats |
| Python misses the 1 GB/30 s target | Medium | High | Stream bytes/lines once, avoid per-line regex recompilation, profile on representative data before optimizing |
| CSV representation is ambiguous for multiple report sections | Medium | Medium | Use one long-form schema with a `metric` discriminator and deterministic row ordering |
| ANSI color corrupts redirected output | Low | Medium | Enable color only for suitable terminals; JSON/CSV never contain styling |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python and approved dependencies are open source |
| Hosting and infrastructure | $0 | Local CLI; no deployed service |
| Delivery labor | One weekend | Approved time-box |
| Ongoing infrastructure | $0/month | No cloud, database, or telemetry backend |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream combined-format logs from files and stdin | **Must** | Foundation for local and pipeline use |
| Top-10 client IPs | **Must** | Core incident summary |
| Top-10 4xx/5xx URLs | **Must** | Core failure summary |
| Hourly request distribution | **Must** | Core traffic-shape summary |
| Unique User-Agent share | **Must** | Core client-diversity summary |
| Rich terminal report | **Must** | Default human interface |
| JSON and CSV modes | **Must** | Required automation interface |
| Deterministic malformed-input and cardinality handling | **Must** | Required reliability and exit contract |
| Gzip input | **Should** | Common operational convenience; not essential to first release |
| Configurable nginx `log_format` | **Could** | Broadens compatibility but exceeds weekend parser scope |
| Persistent history, server, auth, database, cloud, Kubernetes | **Won't** | Contradicts the approved local stateless product boundary |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence as a decimal.

| Feature | Reach | Impact | Confidence | Effort (days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and input | 10 | 5 | 90% | 0.75 | 60.0 |
| Top IP aggregation | 9 | 4 | 95% | 0.25 | 136.8 |
| Error URL aggregation | 9 | 5 | 95% | 0.35 | 122.1 |
| Hourly distribution | 8 | 4 | 95% | 0.30 | 101.3 |
| Rich text output | 9 | 3 | 90% | 0.30 | 81.0 |
| JSON/CSV output | 8 | 4 | 90% | 0.50 | 57.6 |
| User-Agent uniqueness | 7 | 3 | 80% | 0.35 | 48.0 |
| Error/cardinality contract | 8 | 5 | 85% | 0.75 | 45.3 |
| Gzip input | 5 | 2 | 75% | 0.25 | 30.0 |

Dependency order overrides raw score where an aggregator requires the parser. The implementation sequence is parser, metric core, presentation, reliability, then optional gzip.

## 12. Definition of Done

A feature is done when:

- [ ] Behavior and interfaces match `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 type/static checks configured for the project pass.
- [ ] Unit tests pass with at least 90% coverage of parser and aggregation modules.
- [ ] CLI integration tests cover text, JSON, CSV, stdin, file input, and exit codes.
- [ ] The representative 1 GB performance gate completes in under 30 seconds on the documented laptop.
- [ ] Documentation and examples are current.
- [ ] No known Critical or High security issue remains.
- [ ] The exact candidate receives the review and verification evidence required by `.itd/VERIFICATION_CONTRACT.json`.

## 13. Success and Kill Criteria

Proceed to release when every P0 acceptance criterion passes and the performance gate is met. Re-scope or stop if a correct Python streaming implementation cannot process the reference 1 GB fixture in 30 seconds after profiling, or if exact unique-cardinality tracking cannot be bounded safely without violating the specified metrics. No hosted fallback is permitted.
