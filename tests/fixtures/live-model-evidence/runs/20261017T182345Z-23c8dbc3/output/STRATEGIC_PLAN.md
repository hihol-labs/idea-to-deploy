# Strategic Plan: nginx-stream-report

## 1. Product Idea

`nginx-stream-report` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four operational views without retaining the log data: top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the percentage of requests represented by unique User-Agent values. The default presentation is colored terminal text, with JSON and CSV modes for pipelines.

The MVP is intentionally narrow: no authentication, database, HTTP service, cloud dependency, or Kubernetes deployment. It must process a 1 GB log in under 30 seconds on a representative laptop.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Incident responder | Needs an immediate traffic/error summary on a host with limited tooling | One local command, bounded memory, useful terminal output |
| DevOps engineer | Pipeline and platform owner | Needs stable machine-readable summaries in shell jobs | `--json` and `--csv`, stdout/stderr separation, explicit exit codes |
| Systems administrator | nginx operator | Uses grep/awk but repeatedly rebuilds the same aggregations | Purpose-built parsing and all four reports in one pass |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI/configuration surface than a focused pipeline command | Small Python package with stable JSON/CSV schemas and no dashboard |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, and visualization | Persistent services, storage, setup, and operational cost | Fully local, stateless, zero-service processing |
| AWStats | Established historical web analytics | Batch-oriented, generated reports, dated workflow | Streaming terminal feedback and pipeline-friendly output |
| grep/awk/sort | Ubiquitous and composable | Fragile parsing, multiple passes, locale/escaping pitfalls | Tested nginx parsing and four consistent metrics in one pass |

## 4. Unique Value Proposition

Get a trustworthy nginx traffic and error snapshot from a large local log in one command, one pass, and no infrastructure.

## 5. Business Model

The project is open source and free. There is no monetization in the MVP; value is measured through engineering time saved and adoption. Development and operating budget are $0, using only local compute and open-source dependencies.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Required, widely available, productive for a weekend build |
| CLI | Click | Stable option parsing, validation, help, and exit handling |
| Terminal UI | Rich | Color, tables, and automatic non-TTY behavior |
| Domain models | `dataclasses` | Typed, dependency-free records and aggregation results |
| Tests | pytest | Fast unit, CLI, and performance-oriented tests |
| Packaging | `pyproject.toml` + pip | Standard installable CLI distribution |

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Packaging, contracts, parser | Installable command and validated combined-log parsing |
| Saturday afternoon | Streaming aggregation | All four metrics computed in one pass with bounded memory policy |
| Sunday morning | Renderers and CLI | Rich, JSON, and CSV output with stable exit behavior |
| Sunday afternoon | Tests, benchmark, documentation | Acceptance suite and 1 GB performance evidence |

## 8. KPIs

| Metric | MVP target | First month | Three months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | <30 s | <30 s | <25 s |
| Valid-line parsing rate on supported combined logs | >=99.9% | >=99.9% | >=99.95% |
| Peak memory on cardinality-bounded fixture | <256 MB | <256 MB | <200 MB |
| Automated acceptance checks passing | 100% | 100% | 100% |
| External users/runs | n/a | 10 users | 50 users |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats vary from the supported format | High | High | State the supported combined format, allow a format selector later, count malformed lines |
| Exact unique User-Agent tracking exhausts memory | Medium | High | Enforce a configurable hard cardinality ceiling and exit with code 4 |
| Python misses the 1 GB/30 s target | Medium | High | Single pass, compiled regex, minimal allocations, benchmark early, profile hot paths |
| Rich decorations leak into pipelines | Low | Medium | Use stdout/stderr discipline and disable color for non-TTY/machine modes |
| CSV representation of multiple report shapes is ambiguous | Medium | Medium | Use a normalized row schema with a `report` discriminator |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development | $0 | One-weekend owner contribution |
| Dependencies | $0 | Open-source Python packages |
| Hosting and storage | $0 | Local CLI; no services |
| CI | $0 | Optional free tier or local execution |
| Total | $0 | Constraint for MVP |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream supported nginx log input from file or stdin | Must | Foundation for every metric and pipeline use |
| Top 10 client IPs | Must | Core incident triage view |
| Top 10 error URLs | Must | Core reliability view for 4xx/5xx responses |
| Hourly distribution and unique User-Agent share | Must | Required traffic-shape and client-diversity views |
| Rich, JSON, and CSV renderers | Must | Required human and pipeline interfaces |
| Malformed-line accounting and complete exit-code contract | Must | Makes automation trustworthy |
| Gzip input | Should | Common log archival format, but shell decompression is an MVP workaround |
| Configurable top-N | Could | Useful flexibility after the fixed top-10 contract is stable |
| Custom nginx log formats | Could | Broadens adoption but increases parser complexity |
| Database, HTTP API, auth, cloud, Kubernetes | Won't | Conflicts with local stateless CLI scope |

### RICE Scoring (Must and Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with Confidence as a decimal.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Stream parser and input | 10 | 5 | 90% | 0.5 | 90.0 |
| Core top-IP and error-URL aggregations | 10 | 5 | 90% | 0.5 | 90.0 |
| Hourly distribution and UA share | 9 | 4 | 85% | 0.5 | 61.2 |
| Exit behavior and malformed-line accounting | 9 | 4 | 90% | 0.75 | 43.2 |
| Rich, JSON, and CSV renderers | 10 | 4 | 85% | 1.0 | 34.0 |
| Gzip input | 6 | 2 | 80% | 0.5 | 19.2 |

Implementation follows dependency order where necessary, then descending RICE value. See `IMPLEMENTATION_PLAN.md`.

## 12. Definition of Done

A feature is Done when:

- [ ] Behavior and acceptance criteria in `PRD.md` are satisfied.
- [ ] Python 3.11 code passes formatting, linting, and type checks selected during implementation.
- [ ] Unit and CLI integration tests pass with at least 90% line coverage for package code.
- [ ] The full suite passes for terminal, JSON, and CSV modes.
- [ ] The 1 GB benchmark completes in under 30 seconds on the recorded reference laptop.
- [ ] Documentation and CLI help describe inputs, schemas, limitations, and exit codes.
- [ ] No known Critical or High security issue remains.
- [ ] A clean virtual-environment install and manual smoke test succeed.

## 13. Kill Criteria

Re-scope or stop the MVP if a profiled single-pass implementation cannot reach 1 GB in 30 seconds on the reference laptop, exact unique-cardinality tracking cannot be bounded with a clear failure contract, or required packaging cannot be delivered within the one-weekend/$0 constraints.

