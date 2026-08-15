# Strategic Plan: Nginx Stream Analyzer

## 1. Product Idea

Nginx Stream Analyzer is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four operational summaries without storing events: top 10 client IPs, top 10 URLs returning 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich colored text is the default; JSON and CSV make the same result usable in pipelines.

The MVP is an open-source utility delivered over one weekend with no hosted service, authentication, database, or paid infrastructure. `PROJECT_ARCHITECTURE.md` defines the technical contract, `PRD.md` defines observable behavior, and `IMPLEMENTATION_PLAN.md` sequences delivery.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates incidents from a shell | Needs a fast traffic/error snapshot before heavier tooling is available | One local command returns the highest-value summaries |
| Platform engineer | Maintains fleet logging and scripts | Needs stable machine-readable output for pipelines | Versioned JSON/CSV schemas and deterministic exit codes |
| DevOps engineer | Troubleshoots a service on a laptop or bastion | Cannot justify deploying a logging stack for one file | Pip-installable, stateless, offline processing |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Our differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Larger feature surface; output and UI exceed a four-metric pipeline need | Narrow contract, simple install, predictable JSON/CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, retention, dashboards | Operationally heavy, stateful, costly in setup and resources | Zero-service, zero-storage, one-shot local analysis |
| AWStats | Established web-log reporting | Batch/report orientation and broader historical reporting | Streaming execution and modern pipeline output |
| `grep`/`awk`/`sort` | Ubiquitous and composable | Fragile parsing, repeated passes, locale/platform differences | One pass, tested nginx parsing, consistent metrics and errors |

## 4. Unique Value Proposition

Get a reproducible operational summary from a large nginx log in one local command, without deploying or maintaining a logging platform.

## 5. Business Model

The product is open source and free. There is no monetization requirement for the MVP: the value is reduced incident-analysis time and a reusable public utility. Distribution uses a standard Python package through pip. Ongoing operating cost is $0; contributors bear only development time.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required, portable, strong standard-library streaming support |
| CLI | Click | Clear option validation, help, and stable exit handling |
| Terminal UI | Rich | Accessible colored tables with automatic terminal behavior |
| Domain models | `dataclasses` | Explicit lightweight records without a framework |
| Parsing/aggregation | Python standard library | Keeps dependencies and memory overhead bounded |
| Packaging | pip-compatible `pyproject.toml` | Familiar installation and console entry point |
| Testing | pytest plus generated fixtures | Unit, integration, malformed-input, and performance coverage |

## 7. Timeline

| Weekend block | Outcome |
|---|---|
| Saturday morning | Package skeleton, CLI contract, nginx parser, error taxonomy |
| Saturday afternoon | Streaming aggregators and bounded unique-cardinality strategy |
| Sunday morning | Rich, JSON, and CSV renderers; integration tests |
| Sunday afternoon | 1 GB benchmark, documentation, packaging, release readiness |

## 8. KPIs

| Metric | MVP target | First month | Third month |
|---|---:|---:|---:|
| Processing time for supported 1 GB log on reference laptop | <30 s | <30 s | <25 s if profiling justifies optimization |
| Peak resident memory on 1 GB benchmark | Recorded and within documented cardinality budget | No unbounded-growth reports | Stable or improved |
| Valid-line parsing correctness on golden fixtures | 100% | 100% regression pass | 100% regression pass |
| Output-format contract tests | Text/JSON/CSV all pass | No breaking schema change | SemVer-governed changes only |
| Critical/high security defects | 0 known | 0 known | 0 known |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| High-cardinality IP, URL, or User-Agent data exhausts memory | Medium | High | Explicit cardinality limits; terminate with exit code 4 before unsafe growth |
| Real nginx formats differ from the supported format | High | Medium | Declare the supported combined/common-compatible grammar; count malformed lines; fail if no valid lines |
| Python misses the 1 GB/30 s target | Medium | High | Single pass, precompiled parser, compact counters, representative benchmark before release |
| CSV cannot naturally represent heterogeneous report sections | Medium | Medium | Define a normalized row schema with `section`, `key`, `count`, `percentage`, and `rank` |
| Colored output pollutes redirected output | Low | Medium | Enable color only for interactive text output; JSON/CSV never contain ANSI sequences |
| One-weekend scope expands into a logging platform | Medium | High | Enforce MoSCoW and explicit Won't scope |

## 10. Budget

| Item | One-time | Monthly | Comment |
|---|---:|---:|---|
| Software and libraries | $0 | $0 | Python, Click, Rich, pytest are open source |
| Infrastructure | $0 | $0 | Local CLI; no server or database |
| Distribution | $0 | $0 | Source repository and Python package index |
| Development labor | One weekend | $0 cash budget | Time-boxed contributor effort |

Total cash budget: **$0**.

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream supported nginx logs from a file or stdin | Must | Foundation for local and piped use |
| Top 10 client IPs | Must | Core incident-traffic question |
| Top 10 URLs by 4xx/5xx errors | Must | Core failure-localization question |
| Hourly request distribution | Must | Core load-shape question |
| Unique User-Agent share | Must | Core client-diversity question |
| Colored Rich terminal report | Must | Required default experience |
| JSON and CSV output | Must | Required pipeline interoperability |
| Stable `0/1/2/3/4` exit-code contract | Must | Required automation safety |
| Configurable top-N | Should | Useful extension, but top 10 is sufficient for MVP |
| Additional nginx log formats | Should | Broadens adoption after the supported format is stable |
| Compressed-file input | Could | Convenient but shell decompression already composes with stdin |
| Approximate cardinality mode | Could | Could extend extreme workloads after accuracy semantics are designed |
| Authentication, database, HTTP API, server, cloud, Kubernetes | Won't | Conflicts with a local stateless CLI and the approved scope |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`; confidence is represented as a decimal in the calculation.

| Feature group | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and input handling | 10 | 5 | 90% | 1.0 | 45.0 |
| Core four aggregations | 10 | 5 | 90% | 1.5 | 30.0 |
| Stable exit/error contract | 9 | 4 | 95% | 0.5 | 68.4 |
| Rich terminal output | 9 | 4 | 90% | 0.5 | 64.8 |
| JSON and CSV output | 8 | 4 | 90% | 0.75 | 38.4 |
| Additional nginx formats | 6 | 3 | 60% | 1.5 | 7.2 |
| Configurable top-N | 5 | 2 | 80% | 0.5 | 16.0 |

Dependency order overrides raw score where necessary: establish package/input/parser foundations, then aggregation, then output and hardening. `IMPLEMENTATION_PLAN.md` records that executable order.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are present in `PRD.md`.
- [ ] Code is type-consistent and installs on Python 3.11.
- [ ] Unit and integration tests pass, with at least 90% coverage on parser, aggregation, and output modules.
- [ ] Performance-sensitive changes pass the representative 1 GB benchmark where applicable.
- [ ] Text, JSON, CSV, and exit-code contracts remain compatible.
- [ ] Documentation is updated and contains no unresolved placeholders.
- [ ] No known Critical or High security issues remain.
- [ ] The exact staged candidate passes the repository's Verification Loop and current risk-tier adjudication.

## 13. Release and Kill Criteria

Release the MVP only if all P0 stories pass, the `0/1/2/3/4` exit contract is tested, and a representative 1 GB log completes in under 30 seconds on the documented reference laptop. Stop or re-scope the effort if exact unique-cardinality tracking cannot be bounded safely, parsing correctness cannot be made deterministic for the declared format, or the performance target cannot be reached within the weekend without violating correctness.
