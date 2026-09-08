# Strategic Plan: Nginx Stream Analytics CLI

## 1. Product Idea

Nginx Stream Analytics CLI is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four operational views without storing request records: top-10 client IPs, top-10 URLs producing 4xx/5xx responses, hourly request distribution, and the percentage share of unique User-Agents. Rich-colored terminal output is the default, while JSON and CSV support automation and pipelines.

The MVP is deliberately narrow: no service to operate, no database to secure, and no cloud dependency. A one-weekend delivery should turn a large log into a useful first-pass incident summary with a single local command.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs traffic and error concentration quickly, often on a laptop or bastion | One streaming pass and predictable exit codes |
| Platform engineer | Maintains nginx fleets and scripts | Needs machine-readable output without deploying an observability stack | Stable JSON/CSV schemas and stdin/file input |
| DevOps generalist | Supports small or cost-sensitive systems | Full analytics stacks are too expensive or slow to configure | A $0 open-source pip-installable CLI |

## 3. Competitive Analysis

| Alternative | Strength | Limitation for this use case | Our difference |
|---|---|---|---|
| GoAccess | Fast, mature, interactive reports | Broader UI and configuration surface than a small pipeline command needs | Narrow metrics, stable pipeline formats, Python extensibility |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards, retention | Operational cost and persistent infrastructure are disproportionate for local triage | Zero services, zero storage, immediate local result |
| AWStats | Established historical web analytics | Batch-oriented, persistent reports, dated operational workflow | Streaming incident-oriented summary |
| `grep`/`awk` pipelines | Ubiquitous and dependency-light | Fragile parsing, inconsistent output contracts, repeated scans | Tested parser, one pass, explicit errors and formats |

## 4. Unique Value Proposition

Turn a gigabyte-scale nginx access log into four incident-ready summaries in one local, stateless command—without building or operating an analytics platform.

## 5. Business Model

The project is free and open source. There is no paid tier, telemetry, hosted service, or monetization in the MVP. Value is measured in adoption, correctness, and time saved during diagnosis rather than revenue; contribution and distribution occur through the source repository and Python package index.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, modern typing and performance baseline |
| CLI | Click | Stable option parsing, help, input validation, exit behavior |
| Terminal presentation | Rich | Readable colored tables with automatic terminal capability handling |
| Domain models | `dataclasses` | Lightweight typed records without framework overhead |
| Parsing/aggregation | Python standard library | Streaming I/O, regex/date parsing, counters, JSON and CSV |
| Distribution | pip package | Familiar installation path for the target audience |

## 7. Timeline

| Window | Stage | Outcome |
|---|---|---|
| Friday evening | Skeleton and contracts | Package, CLI surface, fixtures, output schemas |
| Saturday morning | Parser and validation | Combined-log parsing and malformed-line policy |
| Saturday afternoon | Streaming aggregations | All four metrics computed in one pass |
| Sunday morning | Renderers and CLI integration | Terminal, JSON, and CSV outputs with exit codes |
| Sunday afternoon | Performance, tests, docs | 1 GB benchmark evidence, pip install smoke test, release-ready docs |

## 8. KPIs

| Metric | Launch target | 1 month | 3 months |
|---|---:|---:|---:|
| Processing time for 1 GB on reference laptop | <30 s | <30 s | <25 s if profiling supports it |
| Peak memory on 1 GB bounded-cardinality fixture | <256 MiB | <256 MiB | <192 MiB if practical |
| Valid fixture metric accuracy | 100% | 100% | 100% |
| Install-to-first-report time | <5 min | <3 min | <2 min |
| Open critical correctness defects | 0 | 0 | 0 |

Performance claims must name laptop CPU, OS, storage, Python version, fixture generation, command, and repeated-run result; the target is not generalized beyond that evidence.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real-world nginx formats differ from Combined Log Format | High | High | Explicit supported format, actionable parse errors, representative fixtures, later configurable format as P1 |
| Exact unique-IP/URL/UA sets exhaust memory on adversarial high-cardinality input | Medium | High | Configurable cardinality ceiling and exit code 4; never silently approximate |
| Python misses the 1 GB/30 s target | Medium | High | Single pass, compiled parser, minimal allocations, benchmark before polish, profile before optimization |
| CSV representation of multiple report sections is ambiguous | Medium | Medium | One long-form schema with `report`, `rank`, `key`, `count`, and `percentage` columns |
| Terminal color contaminates redirected output | Low | Medium | Disable color when not a TTY and for JSON/CSV; support explicit color policy |
| Malformed input yields misleading partial summaries | Medium | High | Fail-fast by default, line number in diagnostics, no report on parse failure |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Software and libraries | $0 | Python, Click, Rich, pytest, and tooling are open source |
| Infrastructure | $0 | Local execution; no server, database, cloud, or Kubernetes |
| Distribution | $0 | Public source repository and standard Python package index |
| Delivery labor | One weekend | Owner time; no cash expenditure approved |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream a file or stdin in one pass | **Must** | Foundation of the local, pipeline-friendly value proposition |
| Parse standard nginx Combined Log Format with clear errors | **Must** | Metrics are unsafe without deterministic parsing |
| Top-10 client IPs | **Must** | Core traffic concentration view |
| Top-10 4xx/5xx URLs | **Must** | Core failure concentration view |
| Hourly distribution and unique User-Agent share | **Must** | Completes the promised summary |
| Rich terminal, JSON, and CSV renderers | **Must** | Human and pipeline outputs are explicit product requirements |
| Cardinality ceiling with explicit exhaustion failure | **Must** | Protects memory without misreporting exact results |
| Configurable top-N and timezone normalization | **Should** | Useful extension, but fixed top-10 and source timestamps can ship |
| Gzip-compressed input | **Could** | Convenient but not needed for initial value |
| Configurable nginx `log_format` | **Could** | Expands compatibility after the fixed parser is proven |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the local stateless CLI scope |

### RICE Scoring (Must + Should)

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (days) | RICE score |
|---|---:|---:|---:|---:|---:|
| File/stdin streaming and Combined Log parsing | 10 | 5 | 90% | 0.75 | 60.0 |
| Top IP and error-URL aggregation | 10 | 5 | 90% | 0.75 | 60.0 |
| Hourly and User-Agent metrics | 9 | 4 | 90% | 0.50 | 64.8 |
| Terminal/JSON/CSV outputs | 10 | 4 | 90% | 0.75 | 48.0 |
| Cardinality ceiling and exit behavior | 8 | 5 | 80% | 0.50 | 64.0 |
| Configurable top-N and timezone | 6 | 2 | 70% | 0.50 | 16.8 |

Implementation order also respects dependencies: input and parsing precede aggregation even where an isolated RICE score is higher.

## 12. Definition of Done

A feature is Done when:

- [ ] Behavior and acceptance criteria are reflected in `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 code is typed, formatted, and passes static checks.
- [ ] Unit tests pass with at least 90% branch coverage for parser, aggregation, and rendering modules.
- [ ] CLI integration and pip-install smoke tests pass.
- [ ] Failure paths and the `0/1/2/3/4` exit-code contract are tested.
- [ ] No known critical or high-severity security issue remains.
- [ ] The 1 GB reference benchmark completes under 30 seconds on the documented laptop.
- [ ] README and command help are current.
- [ ] Review evidence is current for the exact candidate.

## 13. Kill Criteria

Stop or re-scope the MVP if exact metrics cannot meet the reference 1 GB/30 s target after profiling, if common Combined Log Format fixtures cannot be parsed deterministically, or if bounded memory requires silent approximation. A deliberate explicit ceiling failure is acceptable; silently incorrect output is not.

The technical contract is in `PROJECT_ARCHITECTURE.md`; delivery sequencing is in `IMPLEMENTATION_PLAN.md`; product acceptance is in `PRD.md`.
