# Strategic Plan: nginx-log-report

## 1. Product idea

`nginx-log-report` is an installable Python 3.11 command-line tool for DevOps and SRE engineers. It consumes nginx access logs from a file or standard input one line at a time and emits four operational summaries: the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the percentage of distinct User-Agent values among requests with a User-Agent. Rich colored text is the human-facing default; stable JSON and CSV outputs support scripts and pipelines.

The MVP is deliberately local and stateless. It has no authentication, database, network service, cloud dependency, or Kubernetes deployment. Its performance target is processing a 1 GB log in under 30 seconds on a representative laptop while using memory proportional to distinct aggregation keys, not input size.

## 2. Target audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Diagnoses incidents from a shell | Needs a fast first-pass view without standing up infrastructure | One command produces the most useful traffic and error rankings |
| DevOps engineer | Operates nginx fleets and CI jobs | Ad-hoc `awk` pipelines are fragile and hard to standardize | Stable JSON/CSV contracts make the analysis repeatable |
| Platform engineer | Supports developers with local tooling | Larger observability stacks are costly for one-off log files | A pip-installable, zero-service tool works offline |

## 3. Competitive analysis

| Alternative | Strengths | Weaknesses for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive terminal/HTML analytics | Broader configuration and UI than a four-metric pipeline tool needs | Narrow, predictable reports with first-class JSON and normalized CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, retention, and dashboards | Requires services, storage, configuration, and ongoing operations | No service or persistent storage; immediate local result |
| AWStats | Established historical web analytics | Batch/report orientation and persistent generated artifacts are heavier than incident triage | Stateless streaming CLI focused on current operational questions |
| `grep`/`awk`/`sort` | Available almost everywhere and composable | Quoting, nginx format variations, memory-heavy sorts, and inconsistent output schemas | Tested parser and one stable interface for all four summaries |

## 4. Unique value proposition

Get a pipeline-safe nginx traffic and error snapshot from a large local log with one installable command, no service setup, and no retained data.

## 5. Business model and delivery economics

The project is open source and free to use. There is no monetization in the MVP: the value is reduced incident-triage time and a reusable portfolio/community utility. Distribution uses the Python package ecosystem; all selected runtime libraries are open source. Development is constrained to one weekend and no paid infrastructure.

## 6. Technology stack

| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved stack, broad laptop availability, adequate streaming performance with careful parsing |
| CLI | Click | Clear option validation, stdin/file handling, and conventional exit behavior |
| Terminal output | Rich | Readable colored tables and automatic terminal capability handling |
| Domain records | `dataclasses` | Lightweight typed records without a validation framework |
| Packaging | `pyproject.toml`, pip | Standard installable command entry point |
| Tests | pytest | Fast unit, contract, and performance-oriented tests |

See [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for boundaries and data flow.

## 7. One-weekend timeline

| Window | Outcome |
|---|---|
| Saturday morning | Package skeleton, CLI contract, parser fixtures, and streaming data model |
| Saturday afternoon | Aggregations and stable text/JSON/CSV renderers |
| Sunday morning | Integration, malformed-input behavior, and profiling against a generated 1 GB fixture |
| Sunday afternoon | Optimization, packaging validation, documentation, and release-candidate checks |

The dependency-ordered execution details are in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## 8. KPIs

| Metric | Release target | First month | Third month |
|---|---:|---:|---:|
| 1 GB processing time on the documented reference laptop | <30 s | <30 s at p95 of benchmark runs | No regression beyond 10% |
| Peak resident memory on the 1 GB benchmark | <512 MB | <512 MB | <512 MB |
| Correctness on parser/aggregation/output contract suite | 100% | 100% | 100% |
| Installation-to-first-report time | <2 min | <2 min | <2 min |
| Critical/high known security issues in direct dependencies | 0 | 0 | 0 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Python parsing misses the 30-second target | Medium | High | Benchmark early, avoid per-line regex backtracking, profile before optimizing, and document the reference hardware |
| Distinct IP/URL/User-Agent sets consume too much memory on adversarial logs | Medium | High | Track peak RSS, document cardinality limits, and provide a clear memory-error failure rather than silently changing exact results |
| nginx custom formats parse incorrectly | High | Medium | Scope P0 to documented common/combined shapes, count malformed lines, emit diagnostics to stderr, and fail if no valid lines exist |
| JSON/CSV schemas drift and break pipelines | Medium | High | Version the report schema and add golden contract tests |
| Colored output contaminates redirected output | Low | Medium | Enable Rich styling only for terminal text; JSON/CSV never contain ANSI escapes |
| Weekend scope expands into a monitoring platform | Medium | High | Enforce the MoSCoW list and explicit Won't scope below |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and dataclasses are open source |
| Development tools | $0 | Local editor, shell, pytest, and profiling tools |
| Hosting and storage | $0 | None required; execution is local and stateless |
| Distribution | $0 | Local wheel/sdist and public package hosting have no required fee |
| Total required cash budget | **$0** | One-weekend labor is the only investment |

## 11. Feature Roadmap

### MoSCoW prioritization

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream a file or stdin without loading the full log | **Must** | Core value and prerequisite for large logs and pipelines |
| Top 10 IPs | **Must** | Required operational report |
| Top 10 URLs with 4xx/5xx status | **Must** | Required error-focused report |
| Hourly request distribution | **Must** | Required traffic-shape report |
| Unique User-Agent share | **Must** | Required client-diversity report |
| Rich colored terminal output | **Must** | Required default presentation |
| Stable `--json` and `--csv` output | **Must** | Required pipeline interfaces |
| Malformed-line diagnostics and defined exit codes | **Should** | Essential operability, but not a primary metric |
| Transparent `.gz` input | **Could** | Useful for rotated logs if the weekend allows |
| Configurable top-N and timezone bucketing | **Could** | Helpful flexibility beyond the approved fixed report |
| Authentication, database, HTTP API, server, cloud, Kubernetes, live dashboard | **Won't** | Explicitly outside the local stateless CLI scope |

### RICE scoring for Must and Should features

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence represented as a decimal. Closely coupled report metrics are grouped where implementation and user reach are inseparable.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming file/stdin ingestion and parser | 10 | 5 | 90% | 1.0 | 45.0 |
| Top-IP and error-URL aggregations | 10 | 5 | 95% | 0.75 | 63.3 |
| Hourly and User-Agent aggregations | 9 | 4 | 90% | 0.5 | 64.8 |
| JSON and CSV renderers | 8 | 4 | 90% | 0.5 | 57.6 |
| Rich terminal renderer | 8 | 3 | 95% | 0.5 | 45.6 |
| Malformed-line diagnostics and exit codes | 7 | 4 | 85% | 0.5 | 47.6 |

Dependency constraints override raw scores where necessary: ingestion precedes aggregation, and the canonical report model precedes all renderers.

## 12. Definition of Done

A feature is Done when:

- [ ] Its acceptance criteria in [PRD.md](PRD.md) are covered by tests.
- [ ] Code runs on Python 3.11 and lint/type checks configured by the project pass.
- [ ] Unit and integration tests pass with at least 90% line coverage in parser, aggregation, and rendering modules.
- [ ] JSON and CSV golden contract tests pass without ANSI escape sequences.
- [ ] The documented 1 GB benchmark completes in under 30 seconds on the named reference laptop, with peak RSS recorded.
- [ ] Packaging smoke test installs the wheel into a clean environment and the console command runs.
- [ ] Documentation is consistent with [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).
- [ ] No known critical/high direct-dependency security issue remains.
- [ ] A local release-candidate run is manually verified; there is no staging deployment because this is a local CLI.

## 13. Kill and pivot criteria

Stop the weekend release or narrow scope if the parser cannot correctly handle the documented common/combined fixtures, exact aggregations exceed the memory budget on the reference 1 GB fixture, or the optimized run remains above 30 seconds. A performance failure should trigger a documented evaluation of a compiled parser or Go implementation, not the introduction of a service or database.
