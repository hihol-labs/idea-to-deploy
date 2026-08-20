# Strategic Plan: Nginx Stream Analyzer

## 1. Product Summary

Nginx Stream Analyzer is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and produces an immediately useful operational summary: the top 10 client IPs, the top 10 URLs returning 4xx/5xx responses, hourly request distribution, and the percentage of requests represented by unique User-Agent values. Its primary interface is colored terminal text, with deterministic JSON and CSV modes for pipelines.

The MVP is deliberately local and stateless. It has no authentication, database, HTTP service, cloud dependency, or Kubernetes deployment. The delivery target is one weekend, the software and operating budget is $0, and the performance objective is to process a 1 GB log in under 30 seconds on a representative laptop.

## 2. Target Users

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Triage production incidents | Needs useful traffic/error signals before a dashboard can be opened | One command returns bounded, readable aggregates |
| DevOps engineer | Maintains nginx fleets and scripts | Ad hoc `awk` pipelines are fragile and hard to reuse | Stable CLI, exit codes, JSON, and CSV contracts |
| Platform engineer | Builds local diagnostics into automation | Heavy observability stacks are excessive for one-off files | Stream processing with no service or persistent state |

## 3. Value Proposition

Turn a large nginx access log into the four operational views most useful during first-pass triage, locally and in one command, without deploying or maintaining an observability stack.

## 4. Competitive Analysis

| Alternative | Strengths | Limitations for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI/reporting surface than needed; output conventions differ | Narrow, script-friendly four-metric contract with explicit JSON/CSV schemas |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, storage, search, dashboards | Operationally heavy, persistent, and costly in time/resources | Zero-service local analysis and no retained data |
| AWStats | Established historical reporting | Stateful reports and older batch-oriented workflow | Streaming one-shot analysis aimed at incident triage |
| `grep`/`awk`/`sort` | Available almost everywhere and composable | Format assumptions are duplicated, quoting is error-prone, multiple passes are common | Tested parser, one pass, stable outputs and failure semantics |

## 5. Business and Distribution Model

The project is open source and free to use. There is no paid tier, telemetry, hosted service, or monetization requirement for the MVP. Value is measured through utility, reliability, and adoption rather than revenue. Distribution is through a Python package installable with `pip`.

## 6. Technology Strategy

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required stack, broad SRE availability, adequate streaming throughput with careful parsing |
| CLI | Click | Stable option validation, help text, and exit handling |
| Terminal rendering | Rich | Accessible color and table output with automatic terminal handling |
| Domain models | `dataclasses` | Explicit typed records without extra runtime dependencies |
| Packaging | `pyproject.toml` + pip | Standard install and console-script entry point |
| Testing | pytest | Fast unit, golden-output, integration, and performance checks |

## 7. Feature Roadmap

### MoSCoW Prioritization

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream common/combined nginx log input from file or stdin | **Must** | Foundation for local and pipeline use without loading the file into memory |
| Top 10 client IPs | **Must** | Core traffic-source triage metric |
| Top 10 4xx/5xx URLs | **Must** | Core failure-triage metric |
| Hourly request distribution | **Must** | Shows traffic shape and incident windows |
| Unique User-Agent share | **Must** | Required diversity signal with an explicit resource-exhaustion failure |
| Colored terminal report | **Must** | Default human-facing interface |
| JSON output | **Must** | Required structured pipeline interface |
| CSV output | **Must** | Required tabular pipeline interface |
| Malformed-line accounting and stable exit codes | **Must** | Makes results and failures operationally trustworthy |
| Gzip-compressed input | **Should** | Common log-rotation format, but decompression can be piped for MVP |
| Configurable top-N | **Could** | Useful flexibility; top 10 meets the stated need |
| Additional nginx log-format definitions | **Could** | Broadens adoption but raises parsing scope |
| Database, HTTP API, server, cloud, Kubernetes, authentication | **Won't** | Contradicts the local stateless product boundary |
| Live dashboards or retained history | **Won't** | Covered by larger observability products and requires state/services |

### RICE Scoring for Must and Should Features

Scores use `(Reach × Impact × Confidence) / Effort`, with Confidence as a decimal. Ties are resolved by dependency order.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and input handling | 10 | 5 | 90% | 1.0 | 45.0 |
| Stable failure/exit contract | 9 | 5 | 90% | 0.5 | 81.0 |
| Top-IP aggregation | 10 | 4 | 95% | 0.5 | 76.0 |
| Error-URL aggregation | 10 | 5 | 95% | 0.75 | 63.3 |
| Hourly distribution | 9 | 4 | 90% | 0.5 | 64.8 |
| Unique User-Agent share and bound | 8 | 4 | 80% | 0.75 | 34.1 |
| Colored terminal report | 9 | 3 | 95% | 0.5 | 51.3 |
| JSON output | 8 | 4 | 95% | 0.5 | 60.8 |
| CSV output | 7 | 3 | 90% | 0.5 | 37.8 |
| Gzip input | 5 | 2 | 80% | 0.5 | 16.0 |

Implementation follows dependencies first, then descending value within each dependency layer; this avoids implementing outputs before a stable parser and domain contract exist.

## 8. Delivery Timeline

| Window | Focus | Deliverable |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable CLI and validated record stream |
| Saturday afternoon | Aggregation and resource bounds | Four correct metrics in one pass |
| Sunday morning | Terminal, JSON, and CSV renderers | Stable human and pipeline outputs |
| Sunday afternoon | Edge cases, benchmark, docs, packaging | Release candidate with evidence |

## 9. Success Metrics

| Metric | Release target | First-month target |
|---|---:|---:|
| 1 GB processing time | <30 seconds on documented reference laptop | Target maintained across releases |
| Peak memory | Bounded and documented; no file-sized buffering | No known unbounded aggregate except protected UA cardinality |
| Valid-line metric correctness | 100% on golden fixtures | No open correctness defects |
| Output contract coverage | Terminal, JSON, CSV golden tests pass | No backward-incompatible changes without versioning |
| Install-to-first-report | One pip install plus one command | Under 2 minutes for a new user |
| Malformed input transparency | Counts invalid lines; never silently treats them as valid | No silent parse-loss reports |

## 10. Budget

| Item | Cost | Notes |
|---|---:|---|
| Software dependencies | $0 | Open-source Python ecosystem |
| Infrastructure and hosting | $0 | Local CLI; no hosted components |
| Delivery labor | One weekend | Fixed time constraint; no cash budget allocated |
| Ongoing operations | $0/month | No service, storage, or account required |

## 11. Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Python parser misses the 1 GB/30 s target | Medium | High | Benchmark early; compile the log regex once; avoid per-line allocations and multi-pass processing |
| Unbounded unique User-Agent set exhausts memory | Medium | High | Enforce a documented cardinality ceiling and exit with code 4 before unsafe growth |
| Nginx format variations cause false invalid lines | High | Medium | State supported common/combined formats; test escaping, missing fields, IPv6, and malformed input |
| JSON/CSV schemas drift | Medium | Medium | Golden contract tests and explicit schema/version documentation |
| Terminal color corrupts redirected output | Low | Medium | Enable color only for terminal mode/TTY and never in JSON or CSV |
| Top-10 ties produce unstable results | Medium | Medium | Specify deterministic secondary lexical ordering |

## 12. Kill Criteria

Re-scope or stop the MVP if a representative 1 GB combined-format file cannot meet the 30-second target after parser profiling; if exact unique User-Agent tracking cannot be bounded with a clear failure contract; or if supporting real nginx quoting requires a dependency/complexity increase incompatible with a one-weekend delivery.

## 13. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Python 3.11 code is formatted, linted, and type-checked under the chosen project configuration.
- [ ] Unit and integration tests pass, with at least 90% statement coverage for parser, aggregation, and renderer modules.
- [ ] Golden tests cover terminal-without-color, JSON, and CSV output contracts.
- [ ] The representative 1 GB benchmark completes in under 30 seconds on the documented reference laptop.
- [ ] No known Critical or High security issues remain.
- [ ] Packaging installation and the console entry point are manually verified in a clean virtual environment.
- [ ] User and implementation documentation is current.

## 14. Planning References

The technical decisions are specified in `PROJECT_ARCHITECTURE.md`; user-facing requirements in `PRD.md`; and delivery sequencing in `IMPLEMENTATION_PLAN.md`.
