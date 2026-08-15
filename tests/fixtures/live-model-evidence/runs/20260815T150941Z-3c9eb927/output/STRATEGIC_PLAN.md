# Strategic Plan: nginx-insight

## 1. Product Idea

`nginx-insight` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the top 10 client IP addresses, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. It defaults to readable colored terminal output and also emits deterministic JSON or CSV for pipelines.

The MVP is an open-source utility delivered in one weekend with no hosted service, recurring infrastructure, or data retention.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a quick traffic and error summary without shipping sensitive logs elsewhere | Runs one local command against a file or stdin and gets immediate operational signals |
| Platform engineer | DevOps engineer building shell pipelines | Existing terminal reports are hard to automate | Uses stable JSON or CSV output and documented exit codes |
| Small-site operator | Engineer without an observability stack | Full log platforms cost too much time and infrastructure | Installs with pip and analyzes logs with no server or database |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | nginx-insight difference |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader configuration and UI surface than the four required answers | Focused one-command output with explicit pipeline formats |
| Logstash + Elastic + Kibana | Powerful ingestion, search, dashboards, retention | Operationally heavy, persistent, and unsuitable for a $0 weekend utility | Local, ephemeral, single-process analysis |
| AWStats | Established historical reporting | Report-generation workflow and persistent history exceed the incident-response need | Immediate streaming CLI summary with no state |
| grep/awk/sort | Ubiquitous and flexible | Complex quoting, repeated passes, format fragility, and inconsistent output contracts | One tested parser and deterministic multi-metric report |

## 4. Unique Value Proposition

Get the four nginx traffic signals most useful during triage from a local log stream in one command, without deploying or operating an observability stack.

## 5. Business Model

The project is free and open source. There is no paid tier, telemetry, hosted component, or monetization target for the MVP. Value is measured by saved engineering time and adoption, not revenue; contributor support and sponsorship can be reconsidered only after demonstrated usage.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved, broadly available, productive for a weekend delivery |
| CLI | Click | Stable argument parsing, help, validation, and exit behavior |
| Terminal presentation | Rich | Accessible tables and automatic color handling |
| Domain models | Standard-library dataclasses | Explicit typed records without framework overhead |
| Parsing and aggregation | Python standard library | Streaming iteration and low dependency count |
| Packaging | pip-installable Python package | Familiar local installation and isolated execution |
| Testing | pytest | Fast unit, CLI, golden-output, and performance tests |

## 7. Timeline

| Block | Stage | Result |
|---|---|---|
| Saturday morning | Package, contracts, parser | Installable command shell and validated streaming records |
| Saturday afternoon | Aggregation and limits | All four metrics with deterministic ranking and cardinality protection |
| Sunday morning | Terminal, JSON, CSV | Three output modes conform to documented schemas |
| Sunday afternoon | Tests, benchmark, documentation | Acceptance suite passes and a 1 GB benchmark completes under 30 seconds on the reference laptop |

## 8. KPIs

| Metric | Launch target | Month 1 target | Month 3 target |
|---|---:|---:|---:|
| 1 GB analysis wall time on reference laptop | <30 s | <30 s | <25 s |
| Valid-line parsing correctness on fixture suite | 100% | 100% | 100% |
| Peak memory on 1 GB representative fixture | ≤512 MiB | ≤512 MiB | ≤384 MiB |
| Successful pipeline-format contract tests | 100% | 100% | 100% |
| Confirmed external users | 1 | 10 | 30 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Python parsing misses the 30-second target | Medium | High | Benchmark from the parser step, avoid per-line regex recompilation and unnecessary allocations, profile before optimizing |
| nginx format variation causes invalid records | High | Medium | Explicitly support common and combined formats, count skipped lines, document custom formats as out of scope |
| High-cardinality fields exhaust memory | Medium | High | Enforce a configurable exact User-Agent cardinality ceiling and terminate with exit code 4 rather than silently approximate |
| JSON and CSV semantics drift from terminal output | Medium | High | Build one report model and render all formats from it; use golden contract tests |
| Percentages are misunderstood | Low | Medium | Define denominators in PRD and schemas and test rounding independently from raw counts |
| Malformed or hostile log text corrupts terminal output | Low | Medium | Treat input as data, never execute it, and let Rich escape terminal markup |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development tools | $0 | Python and required libraries are open source |
| Hosting and infrastructure | $0 | Local CLI only |
| Database and storage | $0 | No database or retained service state |
| Distribution | $0 | Source repository and standard Python packaging |
| Total MVP cash budget | **$0** | One-weekend engineering time is the only investment |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream nginx common/combined logs from files or stdin | **Must** | Every metric depends on correct one-pass input processing |
| Top 10 client IPs by request count | **Must** | Core incident-triage question |
| Top 10 error URLs by combined 4xx/5xx count | **Must** | Core failure-localization question |
| Hourly request distribution percentages | **Must** | Core traffic-shape question |
| Unique User-Agent share | **Must** | Core client-diversity question |
| Colored terminal report | **Must** | Required default user experience |
| Deterministic `--json` and `--csv` output | **Must** | Required pipeline integration |
| Explicit malformed-line reporting and exit codes `0/1/2/3/4` | **Must** | Required reliable automation contract |
| Gzip-compressed file input | **Should** | Common in rotated nginx logs, but shell decompression is an MVP fallback |
| Configurable top-N | **Could** | Useful beyond the specified top 10 but not required for launch |
| Custom nginx `log_format` definitions | **Could** | Broadens compatibility at significant parser complexity |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the local, stateless, $0 product boundary |
| Persistent dashboards and historical correlation | **Won't** | Belongs to GoAccess or Elastic-class products |

### RICE Scoring for Must and Should Features

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence as a decimal. They order delivery where dependencies allow.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming common/combined parser | 10 | 5 | 90% | 0.50 | 90.0 |
| Top IP aggregation | 9 | 4 | 95% | 0.20 | 171.0 |
| Hourly distribution | 8 | 4 | 95% | 0.15 | 202.7 |
| Error URL aggregation | 9 | 5 | 95% | 0.25 | 171.0 |
| Unique User-Agent share and ceiling | 8 | 4 | 85% | 0.30 | 90.7 |
| Colored terminal report | 9 | 4 | 90% | 0.35 | 92.6 |
| JSON and CSV renderers | 8 | 5 | 90% | 0.40 | 90.0 |
| Diagnostics and exit contract | 8 | 5 | 95% | 0.35 | 108.6 |
| Gzip input | 5 | 2 | 80% | 0.20 | 40.0 |

Dependency ordering takes precedence over a raw score: parser first, then the highest-scoring independent aggregations, cardinality protection, report renderers, and finally optional gzip input.

## 12. Definition of Done

A feature is Done when:

- [ ] The behavior and acceptance criteria are specified in `PRD.md`.
- [ ] Python 3.11 code is typed and passes linting and static checks selected during implementation.
- [ ] Unit and CLI tests pass with at least 90% line coverage for parsing, aggregation, and rendering modules.
- [ ] Integration and golden-output tests pass where applicable.
- [ ] The exit-code contract `0/1/2/3/4` is preserved.
- [ ] Documentation is updated in `README.md` and the implementation guides.
- [ ] No known Critical or High security issue remains.
- [ ] The 1 GB performance acceptance test passes on the documented reference laptop.
- [ ] A human review accepts the exact candidate according to the project verification contract.

## 13. Kill Criteria

Stop or rescope the MVP if the supported-format correctness suite cannot reach 100%, if exact metrics cannot process the representative 1 GB fixture in under 30 seconds with bounded laptop memory, or if delivering the minimum output and pipeline contracts exceeds one weekend. Do not hide a failure by adding persistence, a server, approximate counts, or paid infrastructure.

