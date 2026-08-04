# Strategic Plan: Nginx Stream Insights

## 1. Product Idea

Nginx Stream Insights is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads an nginx access log from a file or standard input, processes valid records in one pass, and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the percentage of distinct User-Agent values. Human-readable colored terminal output is the default; JSON and CSV make the same report usable in pipelines.

The MVP is deliberately narrow: no authentication, database, HTTP API, background service, cloud dependency, or Kubernetes. It must process a 1 GB log in under 30 seconds on a representative laptop without retaining individual requests in memory.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a useful traffic/error summary before opening a heavyweight observability stack | Produces the four core metrics locally in one command |
| Platform engineer | DevOps engineer maintaining nginx fleets | Needs repeatable shell-pipeline output for ad hoc checks | Provides stable JSON/CSV schemas and meaningful exit codes |
| Systems developer | Engineer debugging a local or air-gapped environment | Logs cannot be uploaded and dependencies must stay small | Processes local files/stdin with no network or persistent data |

## 3. Problem and Outcome

Existing choices tend to be either terse but bespoke (`grep`/`awk`) or operationally heavy (Elastic-based stacks). The product occupies the middle: a purpose-built, zero-service CLI with predictable metrics and machine-readable output. Success means an engineer can install it with pip, analyze a typical nginx combined-format log immediately, and trust that malformed data is reported rather than silently distorting the denominator.

## 4. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive terminal/HTML reports | Broader UI and configuration surface than the focused pipeline use case | Four explicit operational metrics, stable JSON/CSV, Python/pip distribution |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards, and retention | Requires services, storage, setup, and operational budget | Stateless local processing with no service or database |
| AWStats | Established historical web analytics | Batch/report-oriented and dated operational workflow | Stream-oriented incident analysis and pipeline-friendly output |
| `grep`/`awk` pipelines | Ubiquitous, composable, no new service | Fragile parsing, inconsistent denominators, hard-to-maintain cardinality handling | Tested parser contract, consistent report schema, explicit failures |

## 5. Unique Value Proposition

Get a trustworthy, pipeline-ready nginx incident summary from gigabyte-scale logs in one local command—without deploying or operating anything.

## 6. Business Model and Budget

The project is open source and free to use. There is no monetization in the MVP; value is measured in reduced incident-analysis time and community adoption. Development is a one-weekend effort using contributor time, existing hardware, and free open-source tooling.

| Cost item | Initial | Monthly | Notes |
|---|---:|---:|---|
| Software and dependencies | $0 | $0 | Python, Click, Rich, and development tools are open source |
| Hosting/infrastructure | $0 | $0 | No hosted runtime; package publication can use free PyPI/Git hosting |
| Database/cloud | $0 | $0 | Explicitly absent |
| Development hardware | $0 incremental | $0 | Representative laptop already available |
| Total cash budget | **$0** | **$0** | Contributor time is the only investment |

## 7. Technology Strategy

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required stack, broad SRE availability, productive weekend scope |
| CLI | Click | Stable command/options/errors and test support |
| Terminal presentation | Rich | Clear colored tables with automatic non-color fallback |
| Domain models | `dataclasses` | Typed, dependency-free records and report snapshots |
| Processing | Single-pass iterator plus bounded aggregators | Meets statelessness and performance goals |
| Distribution | pip-installable package | Familiar local installation and versioning |

## 8. Delivery Timeline

| Window | Stage | Result |
|---|---|---|
| Friday evening | Package skeleton, contracts, parser fixtures | Installable CLI shell and agreed formats |
| Saturday morning | Streaming parser and aggregation core | Four metrics computed from valid records |
| Saturday afternoon | Terminal, JSON, and CSV renderers | Equivalent reports across three formats |
| Sunday morning | Error/cardinality handling and tests | Complete `0/1/2/3/4` behavior |
| Sunday afternoon | Benchmark, documentation, release check | 1 GB evidence and pip-installable release candidate |

## 9. KPIs

| Metric | Launch / 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | <30 s | <25 s | <20 s or documented plateau |
| Peak memory on 1 GB benchmark | <256 MiB | <192 MiB | <160 MiB |
| Valid-record metric correctness on golden fixtures | 100% | 100% | 100% |
| Install-to-first-report success in clean Python 3.11 environment | ≥95% | ≥98% | ≥99% |
| Median time to useful report in user feedback | <2 min | <90 s | <60 s |

## 10. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined/common grammar | High | High | Declare supported formats, fail clearly, count malformed lines, provide representative fixtures |
| Exact unique User-Agent cardinality consumes unbounded memory | Medium | High | Enforce a configurable hard cap and exit `4` before memory exhaustion |
| Python parsing misses the 1 GB / 30 s target | Medium | High | Benchmark early, avoid per-line regex recompilation/object retention, profile before adding features |
| JSON and CSV semantics drift from terminal output | Medium | Medium | Build one immutable report model and renderer contract tests |
| Terminal color contaminates redirected output | Low | Medium | Auto-disable color when not a TTY and provide explicit `--no-color` |
| Malformed lines bias percentages silently | Medium | High | Base percentages only on valid requests and expose valid/malformed counts |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream a file or stdin without retaining requests | **Must** | Core value and scalability constraint |
| Top 10 client IPs | **Must** | Required operational metric |
| Top 10 error URLs for 4xx/5xx | **Must** | Required incident metric |
| Hourly request distribution | **Must** | Required traffic-shape metric |
| Unique User-Agent share with safe cap | **Must** | Required metric with necessary memory safety |
| Colored terminal, JSON, and CSV renderers | **Must** | Required human and pipeline interfaces |
| Complete exit codes and malformed-line diagnostics | **Must** | Required automation and trust contract |
| Configurable top-N and cardinality limit | **Should** | Useful flexibility without changing the default report |
| gzip input | **Could** | Convenient but not essential for the first release |
| Additional custom log formats | **Could** | Expands adoption after the core grammar is proven |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Conflicts with the local stateless CLI scope |
| Dashboards or retained historical analytics | **Won't** | Better served by GoAccess or Elastic-class systems |

### RICE Scoring (Must and Should)

`RICE = Reach × Impact × Confidence / Effort`, where confidence is a decimal.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Top client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Exit codes and malformed diagnostics | 9 | 5 | 90% | 0.5 | 81.0 |
| Terminal/JSON/CSV renderers | 10 | 5 | 85% | 0.75 | 56.7 |
| Unique User-Agent share and cap | 8 | 4 | 80% | 0.5 | 51.2 |
| Streaming file/stdin parser | 10 | 5 | 90% | 1.0 | 45.0 |
| Configurable top-N/cardinality cap | 5 | 2 | 80% | 0.25 | 32.0 |

Dependency order overrides raw RICE where necessary: establish parsing and the report model before metric/output slices. Within that constraint, implementation follows descending value.

## 12. Definition of Done

A feature is done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Code is typed, formatted, linted, and runs on Python 3.11.
- [ ] Unit tests and applicable CLI integration tests pass with at least 90% branch coverage in core parser/aggregation modules.
- [ ] Renderer contract tests prove semantic equivalence across terminal, JSON, and CSV.
- [ ] The 1 GB benchmark meets the under-30-second target on the documented reference laptop.
- [ ] No known critical/high security issue remains.
- [ ] User-facing documentation is updated and a clean-environment pip install is manually verified.
- [ ] The exact staged candidate passes the repository verification contract and risk-tier check.

## 13. Kill Criteria

Re-scope or stop the MVP if, after profiling the agreed parser, a Python 3.11 implementation cannot process the 1 GB reference log within 30 seconds without native extensions; if exact User-Agent cardinality cannot be bounded without an explicit exit; or if supporting real logs requires an unbounded custom-format language incompatible with one-weekend delivery.

## 14. Document Links

Technical decisions are in `PROJECT_ARCHITECTURE.md`; user behavior is in `PRD.md`; delivery sequencing is in `IMPLEMENTATION_PLAN.md`; step prompts are in `CLAUDE_CODE_GUIDE.md`.
