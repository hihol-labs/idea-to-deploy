# Strategic Plan: Nginx Stream Analytics CLI

## 1. Product Idea

A local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and reports top client IPs, URLs producing the most 4xx/5xx responses, hourly traffic distribution, and the share of unique User-Agents. It is designed for fast incident triage and pipeline-friendly analysis without uploading logs or operating a service.

## 2. Target Users

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates incidents under time pressure | Ad hoc shell pipelines are slow to compose and easy to misread | One command produces stable, incident-oriented summaries |
| Platform engineer | Maintains nginx fleets and automation | Heavy observability stacks are excessive for one-off files | Local streaming analysis with JSON and CSV output |
| DevOps engineer | Diagnoses deployment regressions | Needs to connect errors, URLs, and traffic shape quickly | Top error URLs and hourly percentages in the same report |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, rich interactive reports | Broader UI and configuration surface than a focused pipeline tool | Narrow incident metrics, deterministic JSON/CSV, simple pip install |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards, retention | Operationally heavy, persistent, costly in time and resources | Zero-service, zero-database, local one-shot processing |
| AWStats | Established historical reporting | Batch-oriented and dated workflow; persistent report generation | Streaming CLI with modern terminal and pipeline formats |
| `grep`/`awk`/`sort` | Ubiquitous and composable | Fragile parsing, multiple passes, inconsistent edge-case handling | Tested parser, one-pass aggregation, explicit exit contract |

## 4. Unique Value Proposition

Incident-ready nginx traffic and error summaries from a local file or stdin in one command, without shipping sensitive logs or running infrastructure.

## 5. Business Model

The project is free and open source. There are no paid tiers, usage fees, or hosted components. Value is measured by adoption and reduced diagnostic time rather than revenue; CAC and LTV are not applicable to the one-weekend, $0 project.

## 6. Technology Stack

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Approved, widely available, supports modern typing and performance tooling |
| CLI | Click | Stable command/option parsing and test support |
| Terminal rendering | Rich | Accessible color, tables, and automatic terminal behavior |
| Domain models | `dataclasses` | Lightweight typed records without additional runtime frameworks |
| Packaging | pip-compatible `pyproject.toml` | Standard local and isolated installation |
| Processing | Single-process streaming aggregation | Bounded memory for all counters except explicitly guarded unique cardinality |

## 7. Delivery Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Packaging, contracts, parser | Installable command and validated nginx combined-log parsing |
| Saturday afternoon | Aggregation | All four metrics computed in one pass |
| Sunday morning | Renderers | Rich text, JSON, and CSV contracts complete |
| Sunday afternoon | Tests, performance, docs | Exit codes tested and 1 GB benchmark recorded |

## 8. KPIs

| Metric | Launch target | Month 1 target | Month 3 target |
|---|---:|---:|---:|
| Processing time for 1 GB representative log on reference laptop | <30 s | <30 s | <25 s |
| Valid-line parse accuracy on fixture corpus | 100% | 100% | 100% |
| Automated coverage of parser/aggregation/output contracts | >=90% | >=90% | >=92% |
| Median engineer time to obtain all four metrics | <1 min | <1 min | <45 s |
| Open critical correctness defects | 0 | 0 | 0 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined format | Medium | High | Fail clearly on unsupported lines, count malformed lines, document the accepted format, add fixture-driven parser tests |
| Python misses the 1 GB/30 s target | Medium | High | One pass, compiled regex or optimized tokenization, buffered I/O, benchmark before polish, profile before optimizing |
| Exact unique User-Agent tracking exhausts memory on hostile/high-cardinality input | Medium | High | Configurable cardinality ceiling; terminate with exit code 4 rather than silently approximating |
| CSV representation becomes ambiguous for multiple report sections | Medium | Medium | Define a normalized row schema with a `report` discriminator and stable columns |
| Colored output contaminates redirected pipelines | Low | Medium | Enable color only for terminal text on a TTY; JSON/CSV never contain ANSI escapes |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, and Rich are open source |
| Hosting/database/cloud | $0 | None used |
| Development | $0 cash | One weekend of contributor time |
| Test infrastructure | $0 | Local fixtures and laptop benchmark |
| Total | $0 | Meets approved budget |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream nginx combined logs from a file | **Must** | Core local analysis path |
| Stream from stdin | **Must** | Required for pipes and compressed-log workflows |
| Top-10 client IPs | **Must** | Primary traffic-source signal |
| Top-10 URLs by 4xx/5xx count | **Must** | Primary failure signal |
| Hourly request distribution | **Must** | Required traffic-shape metric |
| Unique User-Agent share | **Must** | Required client-diversity metric |
| Colored terminal report | **Must** | Default user experience |
| JSON and CSV output | **Must** | Required automation contract |
| Configurable top-N | **Should** | Useful extension but top-10 satisfies MVP |
| Strict malformed-line mode | **Should** | Helpful in validation pipelines; default tolerant mode can launch first |
| Additional nginx `log_format` definitions | **Could** | Broadens compatibility after the fixed parser is stable |
| Approximate unique counting | **Could** | Could reduce high-cardinality memory but changes exactness semantics |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the local stateless product boundary |

### RICE Scoring (Must + Should)

Confidence is expressed as a decimal in the calculation.

| Feature slice | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming input + combined-log parser | 10 | 5 | 90% | 0.8 | 56.25 |
| Core four-metric aggregation | 10 | 5 | 90% | 1.0 | 45.00 |
| JSON and CSV renderers | 8 | 4 | 90% | 0.5 | 57.60 |
| Colored terminal renderer | 9 | 4 | 90% | 0.5 | 64.80 |
| Unique-cardinality guard and exit code 4 | 7 | 5 | 80% | 0.4 | 70.00 |
| Configurable top-N | 5 | 2 | 90% | 0.2 | 45.00 |
| Strict malformed-line mode | 5 | 3 | 80% | 0.3 | 40.00 |

Dependency order takes precedence where a high RICE feature depends on parsing or aggregation. The implementation plan therefore establishes the input/parser foundation first, then the guard and metrics, then renderers.

## 12. Definition of Done

A feature is Done when:

- [ ] Behavior and acceptance criteria in `PRD.md` are implemented without changing scope implicitly.
- [ ] Python 3.11 type and syntax checks pass.
- [ ] Unit and integration tests pass with at least 90% coverage of parser, aggregation, and renderer modules.
- [ ] CLI tests cover output formats and exit codes `0/1/2/3/4`, where `4` means unique-cardinality exhaustion.
- [ ] Documentation and `--help` are consistent with `PROJECT_ARCHITECTURE.md`.
- [ ] No known Critical or High security issue remains.
- [ ] A representative 1 GB local benchmark completes in under 30 seconds on the named reference laptop.
- [ ] Package installs into a clean Python 3.11 virtual environment and the smoke test succeeds.

## 13. Kill Criteria

Re-scope or stop the MVP if the one-pass implementation cannot process the representative 1 GB fixture in under 30 seconds after profiling, exact required metrics cannot be computed within a safe documented memory bound, or supporting common nginx combined logs would require a server or persistent data store.

## 14. Related Documents

The behavioral contract is in `PRD.md`; technical decisions are in `PROJECT_ARCHITECTURE.md`; delivery sequence is in `IMPLEMENTATION_PLAN.md`.
