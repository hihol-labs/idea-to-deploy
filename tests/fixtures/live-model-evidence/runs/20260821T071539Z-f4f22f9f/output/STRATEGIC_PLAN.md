# Strategic Plan: Nginx Stream Analyzer

## 1. Product Idea

Nginx Stream Analyzer is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and produces an operational snapshot without uploading logs or provisioning infrastructure: top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the percentage of distinct User-Agent values. The MVP is an open-source, zero-budget utility deliverable in one weekend.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE/DevOps | Needs a fast incident overview on a laptop or bastion host | One command, bounded memory, terminal summary |
| Automation author | Platform engineer | Needs stable machine-readable data for shell pipelines | `--json`, `--csv`, documented schemas and exit codes |
| Service owner | Backend lead | Needs a privacy-preserving first look before adopting a larger observability stack | Fully local processing and no retained state |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader feature set and report UI than a small pipeline tool needs | Narrow, deterministic summaries with JSON/CSV contracts |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards | Operationally heavy, persistent, costly in time and resources | No service or database; immediate local analysis |
| AWStats | Established historical reporting | Batch-oriented, configuration-heavy, dated workflow | Streaming stdin/file workflow and modern packaging |
| `grep`/`awk` pipelines | Ubiquitous and composable | Fragile parsing, hard-to-reuse calculations, inconsistent errors | Tested nginx parsing and stable output semantics |

## 4. Unique Value Proposition

Get the four nginx incident metrics engineers reach for first, from a gigabyte-scale log in one local command, with no service, stored data, or paid infrastructure.

## 5. Business Model

The MVP is free and open source. There are no paid tiers, acquisition spend, or hosted costs. Success is adoption and operational usefulness rather than revenue; optional future sponsorship or support must not compromise the local-first core.

## 6. Technology Stack

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, mature packaging |
| CLI | Click | Predictable command/options/errors and test support |
| Terminal UI | Rich | Colored, readable default presentation |
| Data models | `dataclasses` | Lightweight explicit records without a framework |
| Packaging | pip-compatible `pyproject.toml` | Standard installation and console entry point |
| Processing | Single-process iterator pipeline | Stateless, simple, and memory-conscious |

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Friday evening | Package skeleton and contracts | Installable CLI, fixtures, output/exit-code specifications |
| Saturday morning | Parsing and aggregation | Streaming parser and all four metric accumulators |
| Saturday afternoon | Renderers | Rich terminal, JSON, and CSV output |
| Sunday morning | Correctness and failure paths | Unit/integration tests and malformed-input behavior |
| Sunday afternoon | Performance and release polish | 1 GB benchmark, docs, pip build smoke test |

## 8. KPIs

| Metric | 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | <30 s | <27 s | <25 s |
| Peak memory on 1 GB representative log | <256 MB | <192 MB | <160 MB |
| Valid-line parsing accuracy on fixtures | 100% | 100% | 100% |
| CLI contract test pass rate | 100% | 100% | 100% |
| GitHub users/stars (directional) | 10 | 50 | 150 |

The reference laptop, corpus generator, Python version, warm-up policy, and timing command must be recorded with benchmark results so performance claims are reproducible.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Nginx format variation breaks parsing | High | High | Explicit supported combined/common formats, configurable format deferred, malformed-line accounting |
| Exact unique User-Agent cardinality exhausts memory | Medium | High | Cardinality guard with exit code 4 and clear remediation |
| Python misses the 1 GB/30 s target | Medium | High | Profile representative data; avoid regex backtracking and per-line object retention |
| CSV cannot naturally represent heterogeneous reports | Medium | Medium | Fixed long-form schema with `report`, `rank/key/hour`, `count`, `percentage` columns |
| Color corrupts redirected output | Low | Medium | Auto-disable color for non-TTY; JSON/CSV never contain ANSI sequences |
| Scope expands into an observability platform | Medium | High | Enforce Won’t list and CLI-only ADR |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Open-source Python ecosystem |
| Hosting/database/cloud | $0 | None used |
| Development | $0 cash | One weekend of maintainer time |
| CI | $0 | Free open-source allowance or local checks |
| Total MVP cash budget | $0 | Approved constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream from file or stdin | Must | Core local and pipeline workflows |
| Parse nginx common/combined access lines | Must | Required basis for every report |
| Top-10 client IPs | Must | Required incident metric |
| Top-10 4xx/5xx URLs | Must | Required error hotspot metric |
| Hourly request distribution | Must | Required traffic-shape metric |
| Unique User-Agent share | Must | Required client-diversity metric |
| Rich terminal, JSON, and CSV renderers | Must | Required human and pipeline outputs |
| Complete exit-code and malformed-line reporting | Must | Required automation reliability |
| Gzip input | Should | Common archive workflow but not essential to MVP |
| Configurable nginx `log_format` | Could | Useful breadth after the fixed parser is proven |
| Database, HTTP API, authentication, server, cloud, Kubernetes | Won’t | Contradicts the local stateless product |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort` and are planning estimates.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming input and nginx parsing | 10 | 5 | 90% | 1.0 | 45.0 |
| Top-10 client IPs | 9 | 4 | 90% | 0.4 | 81.0 |
| Top-10 error URLs | 10 | 5 | 90% | 0.5 | 90.0 |
| Hourly distribution | 9 | 4 | 95% | 0.3 | 114.0 |
| Unique User-Agent share + guard | 8 | 4 | 80% | 0.5 | 51.2 |
| Terminal/JSON/CSV renderers | 10 | 5 | 85% | 1.0 | 42.5 |
| Exit-code and malformed-line contract | 9 | 5 | 95% | 0.5 | 85.5 |
| Gzip input | 5 | 2 | 70% | 0.5 | 14.0 |

Dependencies override raw score where necessary: parsing precedes metrics, and the normalized result model precedes renderers.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Code is compatible with Python 3.11 and the package builds and installs.
- [ ] Unit and CLI integration tests pass with at least 90% branch coverage for parser, aggregation, rendering, and error paths.
- [ ] Relevant malformed-input and boundary cases pass.
- [ ] Documentation and all output/exit-code contracts are current.
- [ ] No known Critical or High security issue remains.
- [ ] The 1 GB reference benchmark is recorded and meets the under-30-second target before release.

## 13. Kill Criteria

Re-scope or stop the MVP if a profiled, optimized Python implementation cannot process the representative 1 GB corpus in under 30 seconds on the defined reference laptop, exact User-Agent tracking cannot be bounded with an honest failure mode, or the supported nginx formats cannot be parsed deterministically. Do not solve these failures by adding a service, database, or paid infrastructure.

