# Strategic Plan: nginx-logtop

## 1. Product Idea

`nginx-logtop` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx combined access logs line by line and reports the top client IPs, the URLs producing the most 4xx/5xx responses, hourly traffic distribution, and the share of unique User-Agents. It is optimized for one-off incident triage, capacity checks, and repeatable shell pipelines without uploading operational data or operating a service.

The MVP is a $0 open-source project deliverable in one weekend. It has no authentication, database, HTTP API, server, cloud dependency, or Kubernetes deployment.

## 2. Target Users

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a useful traffic summary before a larger observability query is ready | One local command produces the four core summaries |
| Platform engineer | DevOps engineer automating routine checks | Ad hoc shell scripts are hard to review and produce unstable output | Stable `--json` and `--csv` contracts support pipelines |
| Service owner | Backend engineer diagnosing client/server errors | Raw nginx logs hide which routes and clients dominate failures | Deterministic top-10 tables expose error-heavy URLs and active IPs |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | nginx-logtop differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive terminal and HTML reports | Broader configuration and UI surface than a four-metric pipeline step | Narrow contract, pip install, predictable JSON/CSV |
| Logstash + Elastic + Kibana | Powerful ingestion, indexing, dashboards, and historical search | Requires services, storage, setup, and ongoing operations | No service or database; local result in one command |
| AWStats | Established historical web-log reporting | Report-generation workflow and legacy-oriented presentation | Immediate streaming summary with modern pipeline formats |
| `grep`/`awk`/`sort` | Already present on many systems and highly composable | Multiple passes, locale-dependent behavior, fragile parsing, and inconsistent schemas | One-pass parser, explicit malformed-line policy, stable metric definitions |

## 4. Unique Value Proposition

Get a deterministic, pipeline-friendly nginx health snapshot from a large local log in one pass, without deploying or operating anything.

## 5. Business and Licensing Model

The product is free and open source under a permissive license. There are no paid tiers, hosted services, telemetry, or usage charges. Success is measured by utility, reliability, and adoption rather than revenue; community contributions and downstream packaging are the sustainability path.

## 6. Technology Strategy

| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Required stack, broad laptop availability, fast weekend delivery |
| CLI | Click | Reliable option parsing, help, validation, and exit handling |
| Terminal output | Rich | Readable colored tables with automatic TTY behavior |
| Data models | `dataclasses` with slots | Explicit contracts with low per-object overhead |
| Packaging | `pyproject.toml` and pip | Standard install and console-script entry point |
| Processing | Single-process, line-by-line aggregation | Fits stateless local use and bounded request-memory requirements |

## 7. One-Weekend Timeline

| Window | Outcome |
|---|---|
| Saturday morning | Package skeleton, CLI contract, parser fixtures, and exit behavior |
| Saturday afternoon | Streaming aggregates and deterministic ranking |
| Sunday morning | Rich, JSON, and CSV renderers plus end-to-end tests |
| Sunday afternoon | Performance benchmark, packaging checks, and user documentation |

## 8. KPIs and Acceptance Targets

| Metric | Launch target | First-month target | Measurement |
|---|---:|---:|---|
| Processing performance | 1 GB in under 30 seconds on the reference laptop | Preserve target on every release | Versioned benchmark command and machine notes |
| Peak memory excluding unique-UA set | Does not grow with line count | No regression above agreed benchmark tolerance | Peak RSS benchmark |
| Output correctness | All golden fixtures pass | Zero known P0 calculation defects | Automated parser and renderer tests |
| Pipeline stability | JSON/CSV schema documented and tested | No unannounced breaking schema changes | Contract tests and changelog review |
| Installation success | Clean Python 3.11 virtualenv install works | Reproducible on Linux and macOS | Packaging smoke test |

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python parser misses the 1 GB/30 s goal | Medium | High | Benchmark early; compile the parser once; avoid per-line Rich/dataclass allocation; profile before optimization |
| nginx format variants cause misleading skips | High | High | Scope MVP to combined format, count invalid lines, provide `--strict`, and document upstream conversion |
| Exact unique User-Agent cardinality exhausts memory | Medium | High | Enforce a configurable cardinality ceiling and exit with code `4` before returning an inexact result |
| JSON/CSV changes break automation | Medium | High | Version and test schemas; keep human presentation separate from machine renderers |
| Ambiguous ties produce flaky results | Medium | Medium | Specify count-descending and lexical-ascending tie-breaking |
| Sensitive logs leak through network behavior | Low | High | Keep processing entirely local and include no telemetry or remote integration |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, and Rich are open source |
| Hosting and storage | $0 | No hosted component or database |
| CI | $0 required | Local verification is sufficient; free open-source CI may be added later |
| Delivery labor | One weekend | Owner-contributed development time; no cash spend |
| Total cash budget | **$0** | Hard constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Streaming combined-log parser with invalid-line accounting | **Must** | Every metric depends on correct, one-pass input handling |
| Top-10 client IPs | **Must** | Required incident-triage metric |
| Top-10 URLs by combined 4xx/5xx count, with class subtotals | **Must** | Required error-localization metric |
| Hourly request distribution as percentages | **Must** | Required traffic-shape metric |
| Exact unique User-Agent share with exhaustion guard | **Must** | Required client-diversity metric without silently approximate output |
| Colored terminal output | **Must** | Required default experience |
| Stable JSON and CSV output | **Must** | Required pipeline integration |
| Strict malformed-line mode | **Should** | Useful for validation, while lenient processing serves most triage |
| Configurable top-N | **Could** | Helpful later, but the approved MVP contract is top 10 |
| Additional nginx `log_format` definitions | **Could** | Extends compatibility after the combined-format contract is stable |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Explicitly outside the local stateless CLI product |

### RICE Scoring for Must and Should Features

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence represented as a decimal. The values are planning estimates, not measured usage data.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and invalid-line accounting | 10 | 5 | 90% | 1.0 | 45.0 |
| Top-10 client IPs | 9 | 4 | 90% | 0.25 | 129.6 |
| Hourly request distribution | 8 | 4 | 90% | 0.25 | 115.2 |
| Top error URLs | 10 | 5 | 90% | 0.5 | 90.0 |
| Colored terminal output | 8 | 3 | 90% | 0.25 | 86.4 |
| JSON and CSV output | 9 | 4 | 85% | 0.5 | 61.2 |
| Exact unique User-Agent share and guard | 8 | 4 | 80% | 0.5 | 51.2 |
| Strict malformed-line mode | 5 | 2 | 80% | 0.25 | 32.0 |

Dependency order overrides raw RICE where necessary: parser foundations precede every aggregate, and aggregate contracts precede renderers.

## 12. Definition of Done

A feature is done when:

- [ ] Its behavior and acceptance criteria agree with `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Implementation works on Python 3.11 and packaging installs in a clean virtual environment.
- [ ] Unit and end-to-end tests pass, including malformed input and every exit code.
- [ ] Coverage is at least 90% for parser, aggregation, and renderer modules.
- [ ] The complete candidate passes static checks and the project verification contract.
- [ ] User-facing documentation and machine-output schemas are current.
- [ ] No known Critical or High security issue remains.
- [ ] The 1 GB benchmark is recorded and meets the under-30-second target on the named reference laptop.

## 13. Kill and Reassessment Criteria

Reassess the implementation approach if a profiled Python build cannot process the fixed 1 GB benchmark under 30 seconds, if exact unique-UA tracking cannot operate within a documented laptop memory budget at the default ceiling, or if supporting real combined logs requires format guessing that makes results non-deterministic. Do not solve these failures by adding a hosted service or database; narrow input scope, optimize the hot path, or explicitly revisit the product constraint.
