# Strategic Plan: Nginx Stream Analytics CLI

## 1. Product Overview

Nginx Stream Analytics CLI is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four operational views without uploading data or provisioning services: top 10 client IPs, top 10 URLs with 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich colored text is the default; stable JSON and CSV modes support pipelines.

The MVP is a zero-cost, open-source utility deliverable in one weekend. It is deliberately not an observability platform: it answers a bounded post-incident and traffic-triage question quickly on a laptop.

## 2. Target Users

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a fast view of abusive clients and failing routes from a large local log | One command, streaming aggregation, deterministic top-10 reports |
| Platform engineer | Maintains nginx fleets and shell pipelines | Existing dashboards may be unavailable or too expensive for ad hoc analysis | Local operation plus JSON/CSV contracts and meaningful exit codes |
| Application operator | Developer investigating production errors | grep/awk pipelines are fragile around quoting, sorting, and percentages | Tested combined-log parsing and explicit malformed-line accounting |

## 3. Problem and Positioning

The product occupies the gap between improvised shell commands and persistent observability stacks. It favors privacy, setup speed, exact documented metrics, and pipeline compatibility over dashboards, historical storage, and real-time multi-node ingestion.

### Competitive analysis

| Alternative | Strength | Limitation for this job | Differentiation |
|---|---|---|---|
| GoAccess | Mature interactive terminal/HTML analytics; fast native implementation | Broader UI and configuration surface than a four-metric pipeline tool | Smaller contract, installable Python CLI, first-class JSON and CSV output |
| Logstash + Elasticsearch + Kibana | Powerful persistent search, dashboards, and distributed ingestion | Infrastructure, memory, setup, and operational cost are disproportionate for local one-off analysis | No service, database, credentials, or data upload |
| AWStats | Established historical web analytics | Report-generation workflow and dated presentation are less suited to incident-time shell use | Immediate streaming report with automation-friendly formats |
| grep/awk/sort/uniq | Ubiquitous, composable, and free | Multiple passes, quoting hazards, locale variance, and hard-to-reuse metric definitions | One tested command with stable schema and exit behavior |

## 4. Unique Value Proposition

Get the four nginx traffic and error signals most useful during local triage from a gigabyte-scale log in one command, with no service to deploy and no data leaving the laptop.

## 5. Business and Licensing Model

The MVP is open source and free to use. There is no monetization assumption, paid infrastructure, telemetry, or hosted tier. Success is adoption and reduced operator time; future sponsorship or maintenance funding can be evaluated only after real usage is demonstrated.

## 6. Technology Strategy

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Required stack, broad operator availability, mature packaging |
| CLI | Click | Predictable option parsing, help, stdin/file handling, exit behavior |
| Terminal | Rich | Legible colored tables and automatic color/TTY behavior |
| Domain model | `dataclasses` | Typed, low-overhead records and report models without framework coupling |
| Parsing/aggregation | Standard library | Avoid runtime cost and dependency surface; one-pass line iteration |
| Packaging | `pyproject.toml` + pip | Standard install and console entry point |
| Quality | pytest, Ruff, mypy | Fast unit/integration feedback and maintainable typed code |

## 7. Timeline

| Window | Work | Outcome |
|---|---|---|
| Friday evening | Package skeleton, contracts, fixtures, parser | Installable command and validated combined-log records |
| Saturday morning | Streaming aggregators and resource limits | Exact metric model with explicit cardinality failure |
| Saturday afternoon | Text, JSON, CSV renderers | Human and pipeline output contracts |
| Sunday morning | Integration, edge cases, performance tuning | End-to-end CLI and 1 GB benchmark evidence |
| Sunday afternoon | Packaging, docs, release rehearsal | Reproducible wheel/sdist and handoff-ready v0.1.0 |

## 8. KPIs

| Metric | 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | <30 s | <27 s | <25 s |
| Valid-line parse accuracy on supported format corpus | >=99.9% | >=99.95% | >=99.95% |
| Peak resident memory on 1 GB representative log | <512 MiB | <384 MiB | <256 MiB |
| Clean-install-to-first-report | <2 min | <90 s | <60 s |
| Confirmed operator users | 5 | 20 | 50 |

The performance KPI is valid only with a published reference machine, fixture-generation recipe, command, Python version, warm/cold-cache note, elapsed time, and peak RSS.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined format | High | High | Fail visibly on no-valid-record input, count skipped lines, document format scope, add corpus fixtures |
| Exact distinct-key maps exhaust memory on adversarial logs | Medium | High | Enforce `--max-cardinality`; exit 4 rather than emit misleading partial results |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early, compile regex once, avoid per-line allocations, profile before optimization |
| CSV shape is ambiguous for four heterogeneous sections | Medium | Medium | Define a normalized row schema with a `section` discriminator and fixed columns |
| Colored output corrupts redirected pipelines | Low | Medium | Default color to auto/TTY and keep JSON/CSV uncolored on stdout |
| Feature creep turns the CLI into an observability platform | Medium | High | Maintain explicit Won't scope and one-weekend release gate |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development tools | $0 | Python and selected libraries are open source |
| Hosting/cloud/database | $0 | None exists in the architecture |
| CI | $0 | Optional free open-source allowance; local checks remain authoritative |
| Distribution | $0 | Build local artifacts; PyPI publication is optional and free |
| Total MVP cash budget | **$0** | One weekend of contributor time is the only planned input |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Streaming nginx combined-log parser from files and stdin | **Must** | Foundation of every metric and pipeline workflow |
| Top 10 client IPs | **Must** | Core traffic/abuse signal |
| Top 10 error URLs for 4xx/5xx responses | **Must** | Core failure-triage signal |
| Hourly request percentages | **Must** | Required traffic-shape signal |
| Unique User-Agent share | **Must** | Required client-diversity signal |
| Rich colored terminal report | **Must** | Required default interaction |
| Stable JSON and CSV output | **Must** | Required pipeline interaction |
| Cardinality guard and complete exit-code contract | **Must** | Prevents resource failure from becoming false success |
| Gzip-compressed input | **Should** | Common operational convenience; MVP works after decompression |
| Custom nginx `log_format` configuration | **Could** | Broadens adoption but exceeds one-weekend core |
| Approximate bounded-memory cardinality | **Could** | Helps extreme logs but changes exactness semantics |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the local stateless CLI value proposition |
| Dashboards, log retention, alerting, multi-file history | **Won't** | Belongs to persistent observability platforms |

### RICE scoring for Must and Should features

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence as a decimal and effort in person-days. Ties are dependency-ordered.

| Feature | Reach | Impact | Confidence | Effort | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and input | 10 | 5 | 90% | 0.75 | 60.0 |
| Top IP aggregation | 9 | 4 | 95% | 0.25 | 136.8 |
| Error URL aggregation | 9 | 5 | 95% | 0.35 | 122.1 |
| Hourly percentages | 8 | 4 | 95% | 0.25 | 121.6 |
| Unique User-Agent share | 7 | 3 | 85% | 0.30 | 59.5 |
| JSON and CSV output | 8 | 4 | 90% | 0.50 | 57.6 |
| Rich terminal output | 8 | 3 | 90% | 0.40 | 54.0 |
| Cardinality guard and exit codes | 7 | 5 | 90% | 0.60 | 52.5 |
| Gzip input | 5 | 2 | 80% | 0.25 | 32.0 |

Implementation respects prerequisites before descending RICE order: input/parser first, then aggregations, safety and renderers. Gzip remains post-MVP unless time remains.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and edge cases match `PRD.md` acceptance criteria.
- [ ] Code runs on Python 3.11 and formatting, lint, and type checks pass.
- [ ] Unit and integration tests pass with at least 90% branch coverage for parser, aggregation, and output modules.
- [ ] CLI contract tests cover text, JSON, CSV, stdin, file input, malformed lines, broken pipe, and exit codes `0/1/2/3/4`.
- [ ] No known Critical or High security issue remains.
- [ ] The documented 1 GB benchmark completes in under 30 seconds on the reference laptop.
- [ ] Wheel and source distribution build and install into a clean virtual environment.
- [ ] `README.md`, `PROJECT_ARCHITECTURE.md`, and user-facing help agree with shipped behavior.

## 13. Product Kill Criteria

Re-scope or stop the MVP if, after profiling, the required exact metrics cannot process the reference 1 GB fixture within 30 seconds on Python 3.11; if representative supported-format parsing remains below 99.9%; or if safe exact-cardinality handling requires persistent storage. Do not silently weaken exactness or introduce a service to rescue the original scope.

## 14. Linked Specifications

Architecture and interfaces are authoritative in `PROJECT_ARCHITECTURE.md`; behavior and acceptance are in `PRD.md`; delivery sequencing is in `IMPLEMENTATION_PLAN.md`; execution prompts are in `CLAUDE_CODE_GUIDE.md`.
