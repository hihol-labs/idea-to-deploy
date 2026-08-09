# Strategic Plan: Nginx Log Lens

## 1. Product Idea

Nginx Log Lens is an open-source, local Python 3.11 command-line tool for
DevOps and SRE engineers. It reads nginx access logs as a stream and produces
four immediately useful views: top-10 client IPs, top-10 URLs producing 4xx or
5xx responses, hourly request distribution, and the share of distinct
User-Agent values. Terminal output is colored by default; JSON and CSV make the
same results safe to use in pipelines.

The product is deliberately narrow: install with `pip`, point it at a file or
stdin, and get an answer without operating a server or building a dashboard.
The MVP is a $0, one-weekend open-source delivery.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs quick traffic and error concentration without uploading logs | One local command returns the four primary diagnostics |
| Platform engineer | Maintains nginx fleets and shell automation | Ad hoc `awk` pipelines are brittle and hard to integrate consistently | Stable JSON/CSV schemas and documented exit codes support automation |
| Developer/operator | Runs a small service without an observability stack | GoAccess or Elastic can be too much setup for a one-off question | A pip-installable, stateless CLI has no service or storage overhead |

## 3. Competitive Analysis

| Alternative | What it does well | Weakness for this use case | Nginx Log Lens distinction |
|---|---|---|---|
| GoAccess | Rich real-time terminal and HTML analytics | More features and configuration than the four-question workflow needs; machine-output contract is not the main UX | Narrow, predictable metrics with first-class JSON and CSV |
| Logstash + Elasticsearch + Kibana | Durable ingestion, search, dashboards, and large-scale analysis | Requires multiple services, storage, configuration, and operational cost | No service, database, account, or persistent state |
| AWStats | Mature historical web-log reporting | Batch/report orientation and dated interactive workflow; requires configuration and generated artifacts | Streaming local analysis with immediate terminal output |
| `grep`/`awk`/`sort` | Ubiquitous, flexible, and free | Parsing, quoting, status filtering, portability, and error handling become fragile | Tested nginx parsing and one stable cross-platform command |

## 4. Unique Value Proposition

Get the four nginx traffic signals an on-call engineer needs from a local log
stream in one deterministic command—without deploying or operating anything.

## 5. Business Model

The project is free and open source. There are no paid tiers, telemetry, hosted
components, or monetization assumptions in the MVP. The value is reduced
incident-analysis time and a reusable portfolio/community utility. Distribution
uses PyPI-compatible packaging; ongoing infrastructure cost remains $0 by using
public open-source hosting and package infrastructure.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Approved target; broad laptop availability and fast delivery |
| CLI | Click | Mature argument validation, help, and exit behavior |
| Terminal UI | Rich | Colored tables and diagnostics with automatic terminal capability handling |
| Domain model | `dataclasses` | Explicit, lightweight records without a validation framework |
| Parsing/aggregation | Python standard library | Streaming iteration, `Counter`, datetime parsing, JSON, and CSV avoid extra runtime cost |
| Packaging | `pyproject.toml` + pip | Standard installation and console-script entry point |
| Quality | pytest, Ruff, mypy | Fast tests, linting, formatting, and static checking during development |

## 7. Timeline

| Period | Stage | Result |
|---|---|---|
| Saturday morning | Project skeleton, contracts, parser | Installable CLI reads combined/common logs and reports invalid input predictably |
| Saturday afternoon | Streaming aggregation | All four metrics computed in one pass with cardinality protection |
| Sunday morning | Rich, JSON, and CSV renderers | Human and pipeline outputs conform to stable schemas |
| Sunday afternoon | Tests, benchmark, documentation, release check | Acceptance suite passes, 1 GB benchmark is recorded, package builds locally |

## 8. KPIs

| Metric | Launch target | 1-month target | 3-month target |
|---|---:|---:|---:|
| Correctness on golden fixtures | 100% | 100% | 100% |
| 1 GB processing time on reference laptop | <30 seconds | <30 seconds | <25 seconds |
| Peak RSS on the 1 GB bounded-cardinality fixture | <512 MB | <512 MB | <384 MB |
| Valid lines processed per run without materialization | 100% | 100% | 100% |
| Packaging/install smoke-test success | 100% | 100% | 100% |
| Public issue median first response | n/a | <7 days | <5 days |

Performance claims must identify the laptop, OS, storage, Python version,
fixture generator, line count, cardinalities, elapsed-time method, and peak-RSS
method. The target is not claimed until that reproducible benchmark passes.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from common/combined format | High | High | State the supported grammar; reject unsupported custom formats predictably; add fixtures for escaping and missing fields |
| Exact distinct User-Agent tracking consumes excessive memory | Medium | High | Enforce a configurable cardinality ceiling and exit with code `4` rather than return an approximate answer |
| Exact IP/URL counters grow with adversarial cardinality | Low | High | Benchmark realistic and worst-case fixtures; document memory proportionality; add guarded resource tests before release |
| Terminal, JSON, and CSV renderers drift semantically | Medium | Medium | Render all formats from one immutable summary model and test equivalent values |
| The 30-second target varies by hardware and disk | Medium | Medium | Publish the reference environment and separate input I/O from parser benchmark evidence |
| Malformed lines silently bias incident conclusions | Medium | High | Count and report rejected lines; code `3` when no line is valid or strict mode rejects a line |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development | $0 cash | One-weekend owner contribution |
| Runtime infrastructure | $0/month | Entirely local; no hosted service |
| Database/API/cloud | $0/month | Explicitly absent |
| Repository and CI | $0/month | Free open-source tiers only; local checks remain authoritative |
| Package distribution | $0/month | Public Python package infrastructure |
| Total | **$0** | No paid dependency is required for MVP |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream a file or stdin without loading the log into memory | **Must** | Core value and performance constraint |
| Parse nginx common and combined access-log records | **Must** | All metrics depend on a defined supported input grammar |
| Top-10 IPs | **Must** | Required incident traffic view |
| Top-10 4xx/5xx URLs | **Must** | Required error concentration view |
| Hourly request distribution percentage | **Must** | Required temporal traffic view |
| Distinct User-Agent share with exhaustion guard | **Must** | Required client-diversity view and correctness boundary |
| Rich colored terminal report | **Must** | Required default interaction |
| Stable `--json` and `--csv` output | **Must** | Required pipeline support |
| Strict malformed-line mode | **Should** | Useful in CI, but lenient mode can serve the initial interactive workflow |
| Gzip input | **Could** | Convenient, but shell decompression can cover MVP |
| Configurable top-N | **Could** | Adds flexibility beyond the approved top-10 contract |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the local stateless CLI scope |
| Persistent history, dashboards, or tailing remote hosts | **Won't** | Belongs to full observability platforms, not this MVP |

### RICE Scoring (Must + Should)

RICE uses `(Reach × Impact × Confidence) / Effort`, with confidence represented
as a decimal. Scores guide dependency-aware implementation, not scope changes.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming file/stdin foundation | 10 | 5 | 100% | 0.5 | 100.0 |
| Common/combined parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Top-10 IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Hourly distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Top-10 error URLs | 9 | 5 | 95% | 0.5 | 85.5 |
| Rich terminal report | 9 | 4 | 90% | 0.5 | 64.8 |
| Distinct User-Agent share and guard | 8 | 4 | 85% | 0.5 | 54.4 |
| JSON and CSV renderers | 8 | 4 | 90% | 0.75 | 38.4 |
| Strict malformed-line mode | 4 | 2 | 80% | 0.25 | 25.6 |

The dependency-adjusted order is streaming and parsing first, then the four
aggregations, then renderers and strict-mode polish. This avoids implementing a
high-scoring leaf metric before the shared data path it needs.

## 12. Definition of Done

A feature is Done only when:

- [ ] Its behavior and edge cases match `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 code compiles and all unit tests pass with at least 90% line coverage.
- [ ] Applicable integration and CLI snapshot/schema tests pass.
- [ ] Ruff and mypy checks pass.
- [ ] A peer review (when a reviewer is available) reports no unresolved blocking issue.
- [ ] Documentation and help text are updated.
- [ ] No known critical or high-severity security issue remains.
- [ ] The package installs into a clean local virtual environment and the golden flow is manually verified.
- [ ] Performance-sensitive changes retain a reproducible benchmark result under the stated target.

## 13. Release and Kill Criteria

Release the MVP only if golden fixtures agree across all three output formats,
the complete exit-code contract is tested, and the reproducible 1 GB benchmark
meets the target on the declared reference laptop. Re-scope or stop the MVP if
exact results cannot fit a practical laptop memory envelope, common/combined
logs cannot be parsed reliably, or the single-process design cannot reach the
time target without native extensions that exceed the one-weekend budget.

The functional contract is in `PRD.md`, the technical authority is
`PROJECT_ARCHITECTURE.md`, and delivery sequencing is in
`IMPLEMENTATION_PLAN.md`.
