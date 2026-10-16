# Strategic Plan: nginx-log-top

## 1. Product Idea

`nginx-log-top` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four immediately useful views: the ten busiest client IPs, the ten URLs with the most 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. The default report is colored terminal text; stable JSON and CSV modes support pipelines.

The MVP is deliberately local, stateless, and single-process. It does not authenticate users, persist logs, expose an HTTP API, or require infrastructure.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Diagnoses an incident from rotated or live logs | Ad-hoc shell pipelines are slow to compose and easy to misread | One command emits the four agreed operational summaries |
| Platform engineer | Adds log checks to scripts and CI jobs | Human-oriented analyzers have unstable or hard-to-parse output | Versioned JSON and rectangular CSV contracts |
| Small-team DevOps engineer | Operates without an observability stack | ELK-class systems cost setup time and resources | Zero-service, `$0` local analysis installed with pip |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | More features and presentation surface than a four-metric pipeline tool needs | Smaller contract, native JSON/CSV, predictable noninteractive behavior |
| Logstash / Elasticsearch / Kibana | Powerful ingestion, search, dashboards, retention | Requires services, storage, configuration, and operating cost | No server or database; analysis starts immediately |
| AWStats | Established historical web reporting | Persistence-oriented and less natural in modern CLI pipelines | Streaming stdin/files and machine-readable output |
| `grep` / `awk` / `sort` | Ubiquitous and flexible | Quoting, nginx parsing, error handling, and several aggregations become brittle | Tested parser and all four metrics in one pass |

## 4. Unique Value Proposition

Get the essential nginx traffic and error picture from a local stream in one command, with no service to deploy and output that works equally well for people and pipelines.

## 5. Business Model

The project is free and open source. There are no paid tiers, hosted services, telemetry, or monetization requirements. Its return is reduced incident-analysis time and a reusable community tool; CAC, LTV, and unit economics are therefore not applicable.

## 6. Technology Stack

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required, widely available, adequate streaming performance |
| CLI | Click | Stable options, validation, help, and exit handling |
| Terminal UI | Rich | Color, tables, and automatic terminal capability handling |
| Domain records | `dataclasses` | Lightweight typed records without a validation framework |
| Packaging | `pyproject.toml` + pip | Standard installable CLI with a console entry point |
| Testing | pytest | Focused parser, aggregation, rendering, and end-to-end tests |

## 7. Timeline

| Session | Work | Outcome |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable command parses representative combined logs |
| Saturday afternoon | Streaming aggregation and cardinality guard | All four metrics computed in one pass with bounded failure behavior |
| Sunday morning | Text, JSON, and CSV renderers | Stable human and pipeline outputs |
| Sunday afternoon | Tests, benchmark, documentation, release check | Acceptance suite passes and 1 GB target is measured |

## 8. KPIs

| Metric | Launch target | Month 1 | Month 3 |
|---|---:|---:|---:|
| Valid-log correctness fixtures | 100% | 100% | 100% |
| 1 GB processing time on reference laptop | <30 s | <30 s | <25 s stretch |
| Peak memory on benchmark | <512 MiB | <512 MiB | <384 MiB stretch |
| Unhandled tracebacks for user/input errors | 0 | 0 | 0 |
| Clean pip installation in Python 3.11 | Pass | Pass | Pass |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats vary from the combined-log assumption | High | High | State accepted formats, count malformed lines, and fail when no valid records exist |
| Exact unique User-Agent counting exhausts memory on hostile/high-cardinality input | Medium | High | Enforce a configurable hard cap and exit with code 4 rather than silently approximate |
| Python parser misses the 1 GB / 30 s target | Medium | High | Keep the hot path single-pass, avoid regex backtracking, benchmark early, profile before adding features |
| JSON/CSV schemas drift and break pipelines | Medium | High | Golden-file tests and an explicit `schema_version` in JSON |
| Color or diagnostics contaminate redirected output | Low | High | Color only terminal text; keep diagnostics on stderr; never decorate JSON/CSV |
| Scope expands into a monitoring platform | Medium | Medium | Preserve explicit Won't items and the CLI-only architecture decision |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python and dependencies are open source |
| Hosting and database | $0 | Neither exists |
| Development infrastructure | $0 | Local machine and public package tooling |
| Delivery | One weekend | Time-boxed MVP |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream from stdin or one/more files | Must | Core local workflow and bounded-memory requirement |
| Top-10 IPs by request count | Must | Primary traffic-source signal |
| Top-10 error URLs for 4xx/5xx | Must | Primary failure signal |
| Hourly percentage distribution | Must | Reveals traffic shape while normalizing file size |
| Unique User-Agent share with cardinality guard | Must | Required metric with explicit safe failure |
| Colored terminal report | Must | Required default user experience |
| JSON and CSV output | Must | Required pipeline integration |
| Follow a growing file | Should | Useful for live incidents, but static/stdin streams deliver MVP value |
| Gzip input | Could | Useful for archives but not required for first delivery |
| Custom nginx `log_format` expressions | Could | Broadens compatibility at significant parser complexity |
| Authentication, database, HTTP API, server, cloud, Kubernetes | Won't | Contradicts the approved local stateless scope |

### RICE Scoring (Must and Should)

Confidence is expressed as a decimal in the calculation.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming inputs | 10 | 5 | 90% | 0.50 | 90.0 |
| Streaming aggregation core | 10 | 5 | 90% | 0.75 | 60.0 |
| Top error URLs | 9 | 5 | 90% | 0.25 | 162.0 |
| Top IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Hourly distribution | 8 | 4 | 90% | 0.25 | 115.2 |
| Terminal report | 9 | 3 | 90% | 0.30 | 81.0 |
| JSON and CSV | 8 | 4 | 90% | 0.50 | 57.6 |
| Unique User-Agent share and guard | 7 | 3 | 80% | 0.40 | 42.0 |
| Follow mode | 5 | 3 | 70% | 0.50 | 21.0 |

Dependencies override a purely descending score: parsing and the aggregation core precede individual metric renderers.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Code runs on Python 3.11 and formatting/static checks pass.
- [ ] Unit and integration tests pass with at least 90% statement coverage for `src/nginx_log_top`.
- [ ] Pipeline output has golden-file coverage and no terminal styling.
- [ ] The 1 GB benchmark records elapsed time and peak memory on the reference laptop.
- [ ] Documentation and `--help` are current.
- [ ] No known Critical or High security issue remains.
- [ ] A clean virtual environment can install and run the package.

## 13. Kill Criteria

Re-scope or stop the MVP if a representative 1 GB combined log cannot be processed under 30 seconds after profiling and one focused optimization pass, if exact metric definitions cannot be made stable across the supported format, or if delivery requires a database/service contrary to the approved constraints.

