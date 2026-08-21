# Strategic Plan: Nginx Stream Analyzer

## 1. Product Idea

Nginx Stream Analyzer is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the percentage share of unique User-Agent values. It produces colored terminal output by default and stable JSON or CSV for pipelines.

The MVP is intentionally narrow: one local process, no retained state, no network service, and no infrastructure bill. The source of truth for behavior is [PRD.md](PRD.md); the technical design is [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates incidents from a laptop or bastion | Needs immediate traffic and error hotspots without deploying a stack | One command over a file or stdin, with readable top-10 summaries |
| DevOps engineer | Builds shell and CI pipelines | Ad-hoc parsing is brittle and terminal-only tools are hard to compose | Stable `--json` and `--csv` output with documented exit codes |
| Platform engineer | Reviews large proxy logs | Full observability stacks are excessive for one-off local analysis | Bounded-memory streaming designed for a 1 GB file in under 30 seconds |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI/configuration surface than a narrow pipeline tool | Four explicit operational metrics, predictable machine output, Python install |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, retention, dashboards | Services, storage, setup time, and operational cost | Zero-service, zero-retention, local one-shot analysis |
| AWStats | Established historical web analytics | Batch/history orientation and dated workflow | Streaming CLI aimed at incident response and automation |
| `grep`/`awk`/`sort` | Ubiquitous and flexible | Format assumptions, quoting hazards, multiple passes, inconsistent JSON/CSV | Tested parser, one-pass aggregation, stable output contract |

## 4. Unique Value Proposition

Get the four nginx traffic signals most useful during triage from a gigabyte-scale log in one local, pipeline-friendly command—without deploying or operating anything.

## 5. Business Model

The project is open source and free. There is no monetization requirement for the MVP. Value is measured in engineer time saved and reproducibility, not revenue; community maintenance and optional sponsorship can be reconsidered only after demonstrated adoption.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Approved runtime with mature text-processing and packaging support |
| CLI | Click | Clear command/options validation and conventional exit behavior |
| Terminal presentation | Rich | Colored, readable tables with color-disable support |
| Domain models | `dataclasses` | Explicit records without an ORM or validation framework |
| Machine output | Python `json` and `csv` | Stable standard-library serialization with no extra runtime service |
| Distribution | pip package with console entry point | Familiar local installation for Python-using operations teams |

## 7. Timeline

| Period | Stage | Result |
|---|---|---|
| Friday evening | Contract and fixtures | Package skeleton, nginx combined-log fixtures, output schemas |
| Saturday morning | Parser and aggregators | One-pass valid-line processing and bounded top-10 tracking |
| Saturday afternoon | CLI and renderers | Text, JSON, and CSV modes with complete error mapping |
| Sunday morning | Correctness and performance | Unit/integration tests and 1 GB benchmark evidence |
| Sunday afternoon | Packaging and documentation | Installable wheel, usage docs, release checklist |

## 8. KPIs

| Metric | Initial release | Month 1 | Month 3 |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | < 30 s | < 30 s | < 25 s if profiling supports it |
| Peak memory on 1 GB high-cardinality fixture | Within documented cardinality cap | No exhaustion surprises | Fewer than 1% runs exit 4 in volunteered telemetry/issues |
| Metric correctness on golden fixtures | 100% | 100% | 100% |
| Output-schema compatibility | v1 documented | No breaking change | No breaking change |
| Adoption | Release published | 10 unique users/stars/download reporters | 50 unique users/stars/download reporters |

No runtime telemetry is collected; adoption and field reliability use package statistics and voluntarily reported issues.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from combined format | High | High | Explicit supported-format contract, malformed-line count, representative fixtures, future format option as P1 |
| Unique IP/URL/User-Agent cardinality exhausts memory | Medium | High | Configured cardinality budget, deterministic exit code `4`, benchmark with adversarial high-cardinality input |
| Python misses the 1 GB / 30 s target | Medium | High | Stream bytes/text once, avoid regex backtracking and full sorting, profile before optimizing, benchmark on a declared laptop |
| CSV representation is ambiguous for multiple report sections | Medium | Medium | Fixed long-form schema with `section`, `key`, `count`, and `percentage` columns |
| Malformed or partially written logs distort percentages | Medium | Medium | Base every percentage only on `total_valid_requests`; report valid and invalid line counts |
| Terminal color corrupts redirected output | Low | Medium | Auto-disable color off TTY and support `NO_COLOR`; JSON/CSV never contain ANSI escapes |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, and Rich are open source |
| Hosting/database/cloud | $0 | None exists in the architecture |
| Development infrastructure | $0 | Local tools and public CI free tier if later enabled |
| Delivery labor | One weekend | Scope is constrained to a focused MVP |
| Total cash budget | **$0** | No paid services or licenses |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream file and stdin input | **Must** | Core local and pipeline use cases depend on it |
| Top 10 IPs | **Must** | Primary traffic-source signal |
| Top 10 error URLs | **Must** | Primary failure-hotspot signal |
| Hourly request percentages | **Must** | Required traffic-shape signal |
| Unique User-Agent percentage | **Must** | Required client-diversity signal |
| Rich text, JSON, and CSV renderers | **Must** | Human and pipeline contracts are both explicit requirements |
| Malformed-line accounting and `0/1/2/3/4` exits | **Must** | Makes automation trustworthy |
| Configurable nginx log format | **Should** | Expands compatibility after the fixed MVP grammar is reliable |
| gzip input | **Should** | Common operational convenience, not essential for launch |
| Configurable top-N | **Could** | Useful flexibility but conflicts with the deliberately fixed top-10 MVP |
| Authentication, database, API, server, cloud, Kubernetes | **Won't** | Explicitly outside a local stateless CLI |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`, where confidence is a decimal.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin + parser | 10 | 5 | 90% | 1.0 | 45.0 |
| Malformed-line and exit contract | 10 | 5 | 90% | 0.5 | 90.0 |
| Top IP aggregation | 9 | 4 | 90% | 0.4 | 81.0 |
| Top error-URL aggregation | 9 | 5 | 90% | 0.5 | 81.0 |
| Hourly distribution | 8 | 4 | 90% | 0.4 | 72.0 |
| Unique User-Agent share | 8 | 3 | 80% | 0.4 | 48.0 |
| Text/JSON/CSV renderers | 10 | 4 | 90% | 1.0 | 36.0 |
| Configurable log format | 5 | 4 | 60% | 1.0 | 12.0 |
| gzip input | 5 | 3 | 80% | 0.5 | 24.0 |

Dependency order overrides raw score where necessary: the parser precedes aggregators, and complete aggregates precede renderers. The resulting execution order is defined in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## 12. Definition of Done

A release feature is done when:

- [ ] Its PRD acceptance criteria are mapped to tests.
- [ ] Code installs on Python 3.11 and the CLI starts without errors.
- [ ] Unit and integration tests pass with at least 90% branch coverage for parser, aggregation, and renderers.
- [ ] Golden fixtures produce exact text-normalized, JSON, and CSV results.
- [ ] The complete `0/1/2/3/4` exit-code contract is tested.
- [ ] A generated 1 GB fixture completes in under 30 seconds on the declared reference laptop without exceeding its cardinality budget.
- [ ] README and implementation documentation reflect released behavior.
- [ ] No known critical or high-severity security issue remains.
- [ ] A wheel installs and runs in a clean Python 3.11 virtual environment.

## 13. Kill Criteria

Stop or redesign the MVP if, after profiling and bounded optimization, it cannot process the reference 1 GB fixture under 30 seconds; if exact unique-cardinality accounting cannot be bounded with a clear failure contract; or if target users consistently require retained history or interactive exploration rather than one-shot local reports. Those outcomes invalidate the chosen value proposition rather than justify silent scope expansion.
