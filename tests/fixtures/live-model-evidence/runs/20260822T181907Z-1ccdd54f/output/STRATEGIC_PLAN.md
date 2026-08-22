# Strategic Plan: nginx-stream-report

## 1. Product Idea

`nginx-stream-report` is an open-source, local Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four operational summaries without loading the whole file into memory: top 10 client IPs, top 10 URLs with 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich colored text is the default, while JSON and CSV provide stable pipeline-friendly output.

The MVP is a one-weekend, $0 project distributed as a pip-installable package. It is intentionally not a service: there is no authentication, database, HTTP API, server, cloud dependency, or Kubernetes deployment.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates incidents from a terminal | Needs a useful traffic/error snapshot before a larger observability stack is available | One local command produces the four highest-value summaries |
| DevOps engineer | Operates small and medium nginx installations | Existing analytics stacks are costly or too heavy for ad hoc work | Stateless streaming analysis has no service or storage overhead |
| Platform engineer | Builds shell and CI pipelines | Human-oriented tools often lack stable machine output | `--json` and `--csv` provide deterministic, uncolored output |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive dashboards | Broader UI and configuration surface than a four-metric pipeline tool | Smaller fixed contract, pip install, JSON/CSV-first automation |
| Logstash + Elastic + Kibana | Powerful ingestion, search, retention, visualization | Operational cost and setup are disproportionate to one local log | Zero services, zero persistence, immediate local result |
| AWStats | Established historical web reporting | Batch/report workflow and persistent history do not fit ad hoc streaming | Single-run terminal analysis with no retained state |
| `grep`/`awk`/`sort` | Ubiquitous and composable | Complex quoting, repeated parsing, locale differences, and whole-file sorts | Tested nginx parsing and four consistent metrics in one pass |

## 4. Unique Value Proposition

Get a reliable, pipeline-ready nginx traffic and error summary from a large local log in one command, with no service to deploy and no data to retain.

## 5. Business and Licensing Model

The project is free and open source. There are no paid tiers, hosted services, telemetry, or monetization requirements in the MVP. Value is measured by utility, adoption, correctness, and contributor sustainability rather than revenue. A permissive license should be selected before the first public release.

## 6. Technology Stack

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required platform; modern typing and performance baseline |
| CLI | Click | Stable command/option validation and exit handling |
| Terminal rendering | Rich | Accessible colored tables and automatic no-color behavior |
| Domain model | Standard-library dataclasses | Explicit low-overhead records without a validation framework |
| Parsing/aggregation | Python standard library | Keeps runtime dependencies and overhead small |
| Packaging | `pyproject.toml` + pip | Standard install and console-script distribution |
| Testing | pytest | Focused unit, CLI, golden-output, and performance tests |

## 7. Delivery Timeline

| Window | Work | Deliverable |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable CLI that streams and validates combined-format records |
| Saturday afternoon | Aggregation and safety limits | Four correct metrics with bounded failure behavior |
| Sunday morning | Rich, JSON, and CSV renderers | Stable human and machine output contracts |
| Sunday afternoon | Integration, performance, packaging docs | Test evidence including a 1 GB benchmark under 30 seconds on the reference laptop |

## 8. KPIs

| Metric | Release target | 1 month | 3 months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | < 30 s | < 30 s | Maintain < 30 s |
| Peak memory on representative 1 GB log | < 256 MiB | < 256 MiB | < 256 MiB |
| Golden-fixture metric accuracy | 100% | 100% | 100% |
| Unhandled exceptions on supported inputs | 0 | 0 | 0 |
| External usage signal (stars, installs, or explicit feedback) | Baseline established | 10 | 30 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats vary from the configured combined format | High | High | Declare the accepted format, count malformed lines, fail when no valid records exist, and defer custom formats |
| Exact unique User-Agent tracking can exhaust memory | Medium | High | Enforce a configurable cardinality ceiling and exit with code 4 rather than swapping or returning an approximation |
| Python parsing misses the 1 GB/30 s target | Medium | High | Benchmark early, parse once per line, avoid regex backtracking and per-record retained objects |
| JSON/CSV contracts drift from terminal semantics | Medium | Medium | One typed report model and golden tests shared by all renderers |
| Terminal color corrupts redirected output | Low | Medium | Disable color for non-TTY output and always disable it for JSON/CSV |
| Weekend scope expands into a log platform | Medium | High | Enforce Won't priorities and the CLI-only architecture decision |

## 10. Budget

| Item | Cost | Notes |
|---|---:|---|
| Development tools | $0 | Python and selected libraries are open source |
| Infrastructure | $0 | Local CLI; no hosted runtime |
| Data/storage | $0 | User-supplied logs; no retained data |
| Distribution | $0 | Source repository and public package index |
| Total MVP cash budget | **$0** | One-weekend labor is the approved non-cash constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Streaming combined-log parsing with malformed-line accounting | **Must** | All reports depend on correct one-pass ingestion |
| Top-10 IP and top-10 error URL reports | **Must** | Core incident-triage value proposition |
| Hourly percentage distribution and unique User-Agent share | **Must** | Completes the promised four-metric contract |
| Colored Rich terminal output | **Must** | Required default experience |
| Stable JSON and CSV output | **Must** | Required pipeline integration |
| Exact cardinality limit and complete exit-code behavior | **Must** | Prevents misleading or uncontrolled failure |
| Gzip input | **Should** | Common operational convenience, but decompression can be piped for MVP |
| Configurable top-N | **Could** | Useful flexibility after the fixed top-10 contract is stable |
| Custom nginx `log_format` parser | **Could** | Expands compatibility but materially increases parser scope |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Explicitly outside the local stateless CLI product |

### RICE Scoring for Must and Should Features

Scores use `(Reach × Impact × Confidence) / Effort`, with Confidence represented as a decimal.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and malformed-line accounting | 10 | 5 | 90% | 0.75 | 60.0 |
| Top-10 IP and error URL aggregation | 10 | 5 | 90% | 0.75 | 60.0 |
| Rich terminal output | 9 | 3 | 90% | 0.40 | 60.8 |
| JSON and CSV output | 8 | 4 | 90% | 0.60 | 48.0 |
| Hourly distribution and User-Agent share | 9 | 4 | 85% | 0.75 | 40.8 |
| Cardinality limit and exit behavior | 10 | 4 | 90% | 0.90 | 40.0 |
| Gzip input | 5 | 2 | 70% | 0.50 | 14.0 |

Dependency order overrides close score differences: parser and domain contracts precede aggregation, which precedes rendering. `IMPLEMENTATION_PLAN.md` records that executable order.

## 12. Definition of Done

A feature is Done only when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 code is formatted, type-checked, and free of compile errors.
- [ ] Unit and CLI integration tests pass with at least 90% line coverage for product modules.
- [ ] Golden tests prove identical report semantics across terminal, JSON, and CSV formats.
- [ ] The complete `0/1/2/3/4` exit-code contract is tested.
- [ ] The 1 GB reference benchmark completes in under 30 seconds with recorded peak memory.
- [ ] Packaging installs into a clean virtual environment and exposes the documented command.
- [ ] User documentation is current and no Critical or High security finding remains open.

## 13. Product Boundaries and Kill Criteria

Reassess or stop the MVP if the reference implementation cannot meet the 1 GB/30 s target without abandoning Python 3.11, if exact User-Agent cardinality cannot be bounded with an honest failure contract, or if supported nginx input cannot achieve 100% golden-fixture correctness. Do not respond by adding a database, service, cloud component, or approximate output under the same contract.

This strategy is realized by `PROJECT_ARCHITECTURE.md`, sequenced in `IMPLEMENTATION_PLAN.md`, and made testable in `PRD.md`.
