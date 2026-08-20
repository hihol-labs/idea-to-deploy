# Strategic Plan: Nginx Stream Insights

## 1. Product Overview

Nginx Stream Insights is a local, installable Python 3.11 CLI for DevOps and
SRE engineers. It reads nginx access logs as a stream and produces four
operational summaries without uploading data or provisioning infrastructure:
top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request
distribution, and the share of unique User-Agent values. Human-readable Rich
terminal output is the default; JSON and CSV make the same report usable in
pipelines.

The MVP is an open-source utility delivered in one weekend with no hosted
service, authentication, database, API, cloud dependency, or recurring cost.

## 2. Target Users

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates incidents from a shell | Needs fast signal from a large log before a full observability stack is available | One command returns traffic and error hot spots locally |
| Platform engineer | Automates fleet diagnostics | Ad-hoc text parsing is brittle and difficult to consume downstream | Stable JSON/CSV schemas and documented exit codes |
| DevOps consultant | Works across constrained client environments | Cannot assume agents, credentials, servers, or data export approval | Pip-installable, offline, stateless CLI with no data egress |

## 3. Competitive Analysis

| Alternative | Strengths | Limitations for this use case | Our differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive dashboards | Broader UI and configuration surface than a four-metric pipeline tool | Narrow command contract, predictable JSON/CSV, Python installability |
| Logstash / Elasticsearch / Kibana | Powerful ingestion, search, and dashboards | Requires services, storage, configuration, and operational budget | Zero-service, one-shot local analysis |
| AWStats | Established web-log reports and historical views | Batch-oriented, legacy-feeling workflow, persisted reports | Streaming execution and pipeline-friendly output |
| grep / awk / sort | Ubiquitous and flexible | Locale/quoting errors, multiple passes, inconsistent schemas, difficult UA cardinality tracking | Tested single-pass parsing and one stable report contract |

## 4. Unique Value Proposition

Turn a large nginx access log into the four incident-response summaries SREs
need most, locally and in one command, with both readable and machine-stable
output.

## 5. Business Model

The MVP is free and open source. There is no monetization, paid tier, telemetry,
CAC, or hosted service. Success is adoption and dependable use in operational
workflows rather than revenue. Optional commercial support is outside the MVP
and would require a separate product decision.

## 6. Technology Stack

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Required, portable, mature streaming I/O |
| CLI | Click | Stable option parsing, help, validation, and exit behavior |
| Terminal UI | Rich | Accessible colored tables with automatic non-TTY handling |
| Domain models | `dataclasses` | Explicit lightweight records without a validation framework |
| Packaging | `pyproject.toml` and pip | Standard installable console entry point |
| Testing | pytest | Unit, contract, fixture, and performance regression coverage |

## 7. One-Weekend Timeline

| Window | Stage | Deliverable |
|---|---|---|
| Saturday morning | Packaging, contracts, parser | Installable CLI skeleton and validated combined-log parser |
| Saturday afternoon | Streaming aggregation | All four metrics with bounded top-10 structures and guarded UA cardinality |
| Sunday morning | Renderers and contracts | Rich, JSON, and CSV output with exit codes |
| Sunday afternoon | Verification and release | Fixtures, integration/performance checks, docs, and wheel build |

## 8. KPIs

| Metric | MVP target | First month target | Measurement |
|---|---:|---:|---|
| Performance | 1 GB in under 30 seconds on the reference laptop | Target retained across releases | Versioned benchmark fixture and command |
| Correctness | 100% of golden fixture assertions | No open correctness defects rated high | Golden-output contract tests |
| Installability | Clean Python 3.11 venv installs and runs | Successful smoke test for each release | Wheel install CI job |
| Pipeline stability | JSON/CSV schemas documented and tested | No unannounced breaking schema changes | Snapshot/schema tests and changelog |
| Operational usefulness | Four required summaries in every successful report | Feedback from at least five practitioners | Opt-in issue feedback; no telemetry |

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Exact unique User-Agent tracking exhausts memory on hostile/high-cardinality input | Medium | High | Enforce a documented cardinality ceiling and exit with code 4 without presenting a misleading partial report |
| Python misses the 1 GB / 30 s target | Medium | High | Single pass, compiled parser pattern, minimal allocations, benchmark early, profile before optimizing |
| Real nginx formats differ from the combined format | High | Medium | Define supported format precisely, count malformed lines, provide actionable diagnostics, defer configurable formats |
| ANSI color contaminates redirected output | Medium | Medium | Enable color only for an eligible terminal unless explicitly forced; never color JSON/CSV |
| CSV representation is ambiguous for multiple report sections | Medium | Medium | Specify one normalized row schema with metric and rank columns |
| Scope expands into a hosted analytics platform | Medium | High | Preserve explicit Won't items and CLI-only architecture decision |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and pytest are open source |
| Infrastructure | $0 | Local execution; no cloud or server |
| Distribution | $0 | Source repository and public package index |
| Labor | One weekend | Approved delivery constraint; no cash budget |
| Total recurring | $0/month | No hosted components |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream standard nginx combined logs from files and stdin | **Must** | Foundational input path and memory model |
| Top 10 client IPs | **Must** | Required traffic concentration signal |
| Top 10 URLs by 4xx/5xx count | **Must** | Required error hot-spot signal |
| Hourly request percentage distribution | **Must** | Required traffic-shape signal |
| Unique User-Agent share with exhaustion guard | **Must** | Required diversity signal and correctness boundary |
| Rich terminal, JSON, and CSV renderers | **Must** | Required human and pipeline interfaces |
| Gzip-compressed file input | **Should** | Common log rotation format but not necessary for first release |
| Explicit color mode controls | **Should** | Useful for CI and terminals, with safe auto behavior in MVP |
| Configurable nginx `log_format` | **Could** | Broadens compatibility but threatens weekend scope |
| Approximate cardinality mode | **Could** | Could handle extreme scale but changes exactness semantics |
| Database, HTTP API, server, cloud, Kubernetes, authentication | **Won't** | Contradicts the approved local stateless product |
| Historical trends or persistent dashboards | **Won't** | Requires storage and a different product architecture |

### RICE Scoring for Must and Should Features

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence expressed
as a decimal. They guide dependency-aware sequencing, not false precision.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming files/stdin | 10 | 5 | 90% | 0.5 | 90.0 |
| Top IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly percentage distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Unique User-Agent share and guard | 8 | 4 | 80% | 0.5 | 51.2 |
| Three output renderers | 10 | 5 | 85% | 0.75 | 56.7 |
| Color controls | 6 | 2 | 90% | 0.2 | 54.0 |
| Gzip input | 5 | 2 | 90% | 0.25 | 36.0 |

Implementation respects technical dependencies: input and parsing precede the
otherwise higher-scoring aggregations; all renderers follow one shared report
model.

## 12. Definition of Done

A feature is done when:

- [ ] Its behavior and acceptance criteria are documented in `PRD.md`.
- [ ] Code is implemented for Python 3.11 and lint/type checks pass.
- [ ] Unit and integration tests pass with at least 90% statement coverage for core parsing and aggregation modules.
- [ ] Machine-readable output and exit-code contracts have regression tests.
- [ ] The 1 GB performance benchmark meets the under-30-second target on the documented reference laptop.
- [ ] No known critical or high-severity security issues remain.
- [ ] User-facing documentation and `CLAUDE_CODE_GUIDE.md` stay synchronized.
- [ ] A wheel installs in a clean environment and the four golden flows are manually verified.

## 13. Release and Kill Criteria

Release only if correctness fixtures, all output contracts, clean installation,
and the performance target pass. Stop or narrow the MVP if a single-pass Python
implementation cannot process 1 GB under 30 seconds after measurement-guided
optimization, or if exact User-Agent cardinality cannot be bounded with an
honest failure contract. Do not silently replace exact results with estimates.

