# Strategic Plan: Nginx Stream Insights

## 1. Product Idea

Nginx Stream Insights is an open-source, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four operational views without retaining request records: top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich terminal output is the default; JSON and CSV support automation.

The MVP is a one-weekend, $0 project. It is intentionally a local CLI, not an observability platform.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE/DevOps | Needs a fast first view of a large log during an incident | One command, bounded-memory streaming, human-readable ranking |
| Platform engineer | CI/pipeline owner | Needs machine-readable summaries without running a service | Stable JSON and CSV schemas and meaningful exit codes |
| Systems administrator | Small-fleet operator | ELK-class infrastructure is disproportionate | Local, zero-service, pip-installable analysis |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | More UI/report surface than a small pipeline-oriented summary needs | Narrow four-metric contract and predictable JSON/CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, retention, search, dashboards | Operational cost, persistence, services, and setup contradict the brief | No server, database, or ongoing cost |
| AWStats | Established historical web analytics | Batch/report orientation and dated operational workflow | Incident-friendly streaming CLI |
| grep/awk/sort | Ubiquitous and composable | Fragile parsing, repeated scans, locale issues, no stable cross-format contract | One validated parser and one-pass aggregation |

## 4. Unique Value Proposition

Get a pipeline-safe operational summary of gigabyte-scale nginx logs in one local command, with no service or data store to deploy.

## 5. Business Model

The project is free and open source. There are no paid tiers, telemetry, hosted offering, CAC, or LTV targets. Value is measured through adoption, reliability, and time saved during investigations. This matches the $0 budget and avoids introducing commercial infrastructure into a weekend utility.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Required, portable, mature streaming I/O |
| CLI | Click | Stable command and option validation |
| Terminal UI | Rich | Color, tables, and TTY-aware presentation |
| Domain models | `dataclasses` | Lightweight typed records without framework overhead |
| Packaging | pip-compatible `pyproject.toml` | Standard local/virtualenv installation |
| Testing | pytest | Focused parser, aggregation, formatting, and CLI tests |

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Package skeleton and contracts | Installable command, fixture corpus, frozen schemas |
| Saturday afternoon | Parser and streaming aggregation | All four metrics computed in one pass |
| Sunday morning | Rich, JSON, and CSV renderers | Stable user and pipeline outputs |
| Sunday afternoon | Hardening and performance | Error semantics, test suite, 1 GB benchmark evidence, release docs |

## 8. KPIs

| Metric | Launch | 1 month | 3 months |
|---|---:|---:|---:|
| Processing time for 1 GB on reference laptop | <30 s | <30 s | <25 s stretch |
| Valid-line parsing accuracy on maintained fixtures | 100% | 100% | 100% |
| Raw-line/record retention | None | No regression | No regression |
| Supported output contracts | 3 | 3 stable | 3 stable |
| Critical/high known security issues | 0 | 0 | 0 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Nginx log-format variation breaks parsing | High | High | Explicit supported-format contract, clear parse diagnostics, representative fixtures |
| Exact unique-cardinality set exceeds memory | Medium | High | Cardinality guard and exit code 4; document exactness boundary |
| Python misses the 1 GB/30 s target | Medium | High | One pass, compiled regex, minimal allocations, benchmark early, profile before tuning |
| CSV representation is ambiguous across four reports | Medium | Medium | One normalized long-form schema with `report`, `rank`, `key`, `value`, `percentage` |
| Malformed lines silently distort percentages | Medium | High | Track valid/invalid counts; base percentages only on valid requests; warn or fail per policy |
| Terminal color leaks into pipelines | Low | Medium | TTY-aware default, `--no-color`, and color-free structured formats |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Software and libraries | $0 | Open-source dependencies |
| Hosting/database/cloud | $0 | None exists in the architecture |
| Delivery labor | One weekend | Solo contributor, opportunity cost only |
| Ongoing infrastructure | $0/month | Local execution only |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream nginx logs from a file or stdin | **Must** | Foundation for local and pipeline use |
| Top 10 IPs | **Must** | Core incident triage metric |
| Top 10 URLs by 4xx/5xx errors | **Must** | Core failure-location metric |
| Hourly request distribution | **Must** | Core traffic-shape metric |
| Unique User-Agent share | **Must** | Core client-diversity metric |
| Rich terminal, JSON, and CSV output | **Must** | Required human and pipeline interfaces |
| Malformed-line accounting and stable exit codes | **Should** | Makes automation dependable |
| 1 GB performance/memory benchmark | **Should** | Demonstrates the stated non-functional target |
| Transparent gzip input | **Could** | Useful convenience, unnecessary for MVP value |
| Database, HTTP API, auth, server, cloud, Kubernetes | **Won't** | Explicitly outside the local stateless product |

### RICE Scoring (Must + Should)

Confidence is expressed as a multiplier in the score: `Reach × Impact × Confidence / Effort`.

| Feature | Reach | Impact | Confidence | Effort (days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming file/stdin ingestion | 10 | 5 | 100% | 0.5 | 100.0 |
| Top 10 IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top error URLs | 10 | 5 | 95% | 0.5 | 95.0 |
| Hourly distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Unique User-Agent share | 8 | 4 | 90% | 0.5 | 57.6 |
| Three output formats | 10 | 5 | 90% | 1.0 | 45.0 |
| Error and exit-code contract | 9 | 4 | 90% | 0.5 | 64.8 |
| Performance benchmark | 8 | 5 | 80% | 0.75 | 42.7 |

Dependencies override raw score where necessary: ingestion and parsing precede every metric; the interface contract is frozen before renderer implementation.

## 12. Definition of Done

A feature is Done when:

- [ ] Behavior and acceptance criteria in `PRD.md` are implemented.
- [ ] Python 3.11 static checks and all unit/integration tests pass, with at least 90% coverage on parser and aggregation modules.
- [ ] CLI tests cover terminal, JSON, CSV, stdin, malformed input, and exit codes.
- [ ] Code review reaches the project acceptance threshold with no unresolved blocking finding.
- [ ] User-facing and implementation documentation is current.
- [ ] No known critical or high security issue remains.
- [ ] The 1 GB reference benchmark completes in under 30 seconds with bounded memory.

## 13. Kill Criteria

Stop or redesign the MVP if a representative 1 GB combined-log fixture cannot meet 30 seconds after profiling and focused optimization, if exact unique-cardinality cannot be bounded with an explicit safe failure, or if supporting common nginx combined logs requires format guessing that makes results non-deterministic. Do not solve these failures by adding a database or service.
