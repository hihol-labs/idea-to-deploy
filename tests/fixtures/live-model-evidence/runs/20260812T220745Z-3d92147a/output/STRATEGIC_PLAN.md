# Strategic Plan: nginx-log-report

## 1. Product Idea

`nginx-log-report` is a local, pip-installable Python 3.11 CLI that reads nginx combined access logs one line at a time and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. It is for DevOps and SRE engineers who need a fast incident or traffic summary without deploying a service or uploading operational logs.

The MVP is a one-weekend, open-source utility with colored terminal output by default and stable JSON and CSV contracts for pipelines. It holds only aggregate state in memory and writes no persistent data.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Responds to incidents | Needs a useful traffic/error picture in minutes, often on a restricted host | Runs one local command against a file or stdin with no service setup |
| DevOps engineer | Operates nginx fleets and CI jobs | Ad hoc shell pipelines are brittle and hard to reuse | Gets stable JSON/CSV schemas and documented exit codes |
| Platform engineer | Builds operational tooling | Large logs make load-all-at-once scripts slow or memory-heavy | Uses a single-pass parser with explicit cardinality limits and a performance target |

## 3. Competitive Analysis

| Alternative | What it does well | Weakness for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Rich interactive and HTML nginx analytics | Broader UI/configuration surface than a four-metric pipeline tool; separate native binary | Small pip-installed CLI with compact, stable JSON/CSV output |
| Logstash + Elasticsearch + Kibana | Durable ingestion, search, dashboards, long-term analysis | Requires multiple services, storage, administration, and non-zero operational cost | No server, database, indexing, or upload; immediate local answer |
| AWStats | Mature historical web analytics | Persistent reports and configuration are oriented toward periodic historical analysis | Stateless, stream-oriented incident snapshot |
| `grep`/`awk`/`sort` | Ubiquitous and excellent for quick one-offs | Quoting, malformed lines, status families, multiple reports, and portable schemas become fragile | One parser, one scan, deterministic metrics and errors |

## 4. Unique Value Proposition

Get the four nginx signals an on-call engineer needs from a gigabyte-scale log in one local, dependency-light command—without a database, dashboard stack, or hand-built shell pipeline.

## 5. Business Model

The project is open source and free to use. There are no paid tiers, hosted services, telemetry, or support commitments in the MVP. Value is measured through adoption and reliability rather than revenue; CAC and LTV are therefore not applicable. Contributions and downstream packaging are permitted under a permissive license selected before release.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, broadly available, fast enough with a compiled regex and single-pass I/O |
| CLI | Click | Reliable argument validation, help text, and usage exit behavior |
| Terminal rendering | Rich | Readable colored tables and automatic terminal capability handling |
| Domain models | `dataclasses` | Typed, dependency-free records and report objects |
| Aggregation | Standard-library `collections.Counter`, sets, fixed 24-slot array | Exact results with no persistent store |
| Packaging | `pyproject.toml` + pip | Reproducible install and console-script entry point |
| Testing | pytest | Unit, CLI, golden-output, and performance-smoke coverage |

Details and boundaries are defined in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).

## 7. Timeline

| Weekend block | Stage | Deliverable |
|---|---|---|
| Friday evening | Contract and project skeleton | CLI/output contracts, package layout, fixtures |
| Saturday morning | Parsing and aggregation | Combined-log parser and exact metrics |
| Saturday afternoon | Renderers and CLI | Terminal, JSON, CSV, validation, exit codes |
| Sunday morning | Hardening and performance | Edge-case tests, cardinality guard, 1 GB benchmark |
| Sunday afternoon | Packaging and release readiness | pip install smoke test, docs, license, release checklist |

## 8. KPIs

| Metric | Release target | 1 month | 3 months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | <30 s | <30 s | <25 s if profiling supports it |
| Peak RSS on reference 1 GB fixture | documented and within cardinality policy | no unbounded-growth defects | 10% improvement if needed |
| Correctness suite | all golden/edge tests pass | zero known P0 defects | zero known P0 defects |
| Installation success on Python 3.11 | Linux/macOS smoke tests pass | ≥95% of reported installs | ≥98% of reported installs |
| Community adoption | release published | 25 repository stars or 50 installs | 100 stars or 250 installs |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Regex parsing mishandles quoted/escaped fields | Medium | High | Central parser, adversarial fixtures, strict/non-strict behavior, golden examples |
| High-cardinality logs exhaust memory | Medium | High | Explicit User-Agent cardinality ceiling and exit code `4`; benchmark peak RSS |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early, profile, avoid per-line object churn, keep a compiled parser hot path |
| JSON/CSV schema drifts and breaks pipelines | Low | High | Versioned schema contract and byte-for-byte golden tests |
| Ambiguous malformed-line behavior undermines trust | Medium | Medium | Count skipped lines, expose counts in every output, `--strict` for fail-fast operation |
| Scope expands toward dashboards or ingestion services | Medium | Medium | Enforce the Won't list and CLI-only ADR |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime/frameworks | $0 | Python, Click, Rich, and pytest are open source |
| Hosting/database/cloud | $0 | None used |
| Development tools | $0 | Local open-source toolchain |
| Distribution | $0 | Source repository and public package index |
| Total MVP cash budget | **$0** | One-weekend contributor time is the only investment |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream nginx combined logs from a file or stdin | **Must** | Core local workflow and memory constraint |
| Compute all four required metrics in one pass | **Must** | The product has no value without the complete report |
| Colored terminal report | **Must** | Required default human interface |
| Stable `--json` and `--csv` outputs | **Must** | Required for automation and pipelines |
| Deterministic parsing policy and exit codes `0/1/2/3/4` | **Must** | Scripts must distinguish usage, data, internal, and cardinality failures |
| pip-installable Python 3.11 package | **Must** | Required delivery mechanism |
| Cardinality guard and 1 GB performance benchmark | **Must** | Makes the scale target and failure behavior credible |
| `--strict` malformed-line handling and `--no-color` | **Should** | Important control for CI and diagnosis but not the central metric set |
| Configurable nginx log formats | **Could** | Useful extension after the combined-format MVP is stable |
| Built-in `--follow` and periodic refresh | **Could** | Convenient, but `tail -F ... | nginx-log-report -` already composes well |
| Authentication, database, API, server, cloud, Kubernetes | **Won't** | Explicitly outside a local stateless CLI |
| Dashboards and long-term history | **Won't** | Better served by GoAccess or Elastic-class systems |

### RICE Scoring (Must + Should)

Confidence is expressed as a decimal in the formula `Reach × Impact × Confidence / Effort`.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| CLI contract, parsing policy, exit codes | 10 | 5 | 90% | 0.5 | 90.0 |
| Single-pass four-metric aggregation | 10 | 5 | 90% | 1.0 | 45.0 |
| File/stdin streaming parser | 10 | 5 | 85% | 1.0 | 42.5 |
| JSON and CSV output | 8 | 4 | 90% | 0.75 | 38.4 |
| Colored terminal report | 9 | 3 | 95% | 0.5 | 51.3 |
| pip packaging | 10 | 3 | 95% | 0.5 | 57.0 |
| Cardinality guard and performance evidence | 8 | 5 | 75% | 1.0 | 30.0 |
| Strict mode and no-color option | 6 | 2 | 90% | 0.5 | 21.6 |

Implementation order in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) respects both RICE value and technical dependencies; contract and packaging skeleton precede dependent behavior.

## 12. Definition of Done

A feature is Done when:

- [ ] Its PRD acceptance criteria are met and traceable to tests.
- [ ] Python 3.11 code imports and static checks complete without errors.
- [ ] Unit, CLI integration, and relevant golden-output tests pass with at least 90% line coverage for parser, aggregation, renderers, and CLI modules.
- [ ] The exact CLI and exit-code contracts remain consistent across architecture, plan, guide, and README.
- [ ] No known critical or high-severity security issues remain.
- [ ] User-facing documentation is updated.
- [ ] The wheel installs in a clean environment and its console entry point is manually smoke-tested.
- [ ] The reference 1 GB benchmark completes in under 30 seconds and records peak RSS and fixture details.

## 13. Kill Criteria

Re-scope or stop the MVP if a correct, profiled single-process implementation cannot process the reference 1 GB fixture in under 30 seconds on the documented laptop; if exact required metrics cannot remain within the documented memory envelope for representative logs; or if a stable combined-log parsing contract cannot be achieved in the weekend. Do not silently replace exact results with approximation: that requires a new product decision and PRD revision.
