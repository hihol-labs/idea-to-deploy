# Strategic Plan: nginx-stream-insights

## 1. Product Idea

`nginx-stream-insights` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream from files or standard input and produces four immediately useful views: the top 10 client IPs, the top 10 URLs responsible for 4xx/5xx responses, request distribution by hour, and the share of unique User-Agent values. Human-readable colored terminal output is the default; JSON and CSV provide stable pipeline interfaces.

The product optimizes for a one-off operational question: obtain a useful traffic and error summary without deploying or maintaining a service. It retains no log lines and creates no durable state.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs the highest-volume clients and failing URLs in seconds | One local command, bounded summaries, and deterministic exit codes |
| Platform engineer | Maintains nginx fleets and shell automation | Needs machine-readable results without operating an observability stack | Stable `--json` and `--csv` schemas; stdin and file inputs |
| Developer/operator | Debugs a service on a laptop or jump host | Existing dashboards are absent, delayed, or overkill | Zero-service pip install and streaming processing with laptop-scale performance |

## 3. Competitive Analysis

| Alternative | What it does well | Weakness for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature real-time terminal and HTML analytics | Broader UI and configuration surface than a four-metric pipeline tool; external binary distribution | Small Python package, deliberately narrow output contract, direct JSON/CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, retention, and dashboards | Operational cost, persistent infrastructure, and excessive setup for a local one-shot answer | No service, database, account, or recurring cost |
| AWStats | Established historical web-log reporting | Batch-oriented reports and dated workflow; not optimized for Unix pipelines | Streaming CLI designed for terminal and automation use |
| `grep`/`awk`/`sort` | Ubiquitous and flexible | Correct parsing and cross-platform scripts are hard to reproduce; repeated passes increase I/O | One tested parser, one pass, four consistent metrics |

## 4. Unique Value Proposition

Get the four nginx traffic signals most useful during triage from a gigabyte-scale log in one local, pipeline-friendly command—without deploying an observability stack.

## 5. Business Model

The project is free and open source. There are no paid tiers, hosted services, usage fees, telemetry, or monetization dependencies. Value is measured in adoption, correctness, and operator time saved rather than revenue, LTV, or CAC. Maintenance is community-driven and constrained to the narrow CLI scope.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Approved, broadly available, and fast enough with line-by-line parsing |
| CLI | Click | Predictable option validation, help text, stdin/file handling, and exit behavior |
| Terminal UI | Rich | Colored tables and automatic terminal capability handling |
| Domain models | Python `dataclasses` | Typed, dependency-free metric and result structures |
| Packaging | `pyproject.toml` with pip entry point | Standard install path and reproducible CLI command |
| Testing | pytest | Fast unit, contract, and performance tests |

## 7. Timeline

| Period | Stage | Result |
|---|---|---|
| Saturday morning | Package skeleton, parser, domain models | Installable CLI foundation and valid combined-log parsing |
| Saturday afternoon | Streaming aggregation and resource guards | All four metrics computed in one pass |
| Sunday morning | terminal, JSON, and CSV renderers | Stable human and pipeline output contracts |
| Sunday afternoon | tests, profiling, documentation, packaging | Release candidate meeting correctness and 1 GB performance target |

## 8. KPIs

| Metric | Launch target | 1-month target | 3-month target |
|---|---:|---:|---:|
| Processing time for a representative 1 GB log on the reference laptop | <30 s | <30 s, no regression | <25 s if profiling supports safe optimization |
| Peak memory excluding unique User-Agent keys | <150 MB | <150 MB | <125 MB |
| Golden-fixture metric accuracy | 100% | 100% | 100% |
| Output/exit-code contract tests passing | 100% | 100% | 100% |
| Valid lines processed despite isolated malformed lines | 100% | 100% | 100% |

The reference laptop and benchmark fixture must be recorded with each performance result; the 30-second target is not claimed across unspecified hardware.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Regex parsing misses customized nginx formats | Medium | High | Scope v1 to the documented combined format, report malformed counts, and design a replaceable parser boundary |
| Python misses the 1 GB / 30 s target | Medium | High | Single pass, compiled pattern, local bindings, bounded top-k selection, representative benchmark gate |
| High-cardinality User-Agent data exhausts memory | Medium | High | Configurable unique-cardinality limit and explicit exit code `4`; never silently approximate in v1 |
| CSV/JSON schemas drift between releases | Low | High | Golden snapshots and documented versioned schemas |
| Terminal color corrupts redirected output | Low | Medium | Rich auto-detection, `--no-color`, and no styling for JSON/CSV |
| Malformed lines lead to misleading summaries | Medium | Medium | Count warnings, define valid-record denominators, and fail when no valid records remain |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and pytest are open source |
| Hosting and data storage | $0 | Local execution; no backend or database |
| Infrastructure | $0 | Tests and benchmarks run locally or on free open-source CI allowances if later enabled |
| Delivery labor | One weekend | Scope is fixed to the v1 CLI and documentation |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream nginx combined-log input from files and stdin | **Must** | Foundation for every result and Unix-pipeline use |
| Top 10 IP addresses by valid request count | **Must** | Core incident-triage signal |
| Top 10 URLs by combined 4xx/5xx count | **Must** | Core failure-localization signal |
| Hourly request distribution as percentages | **Must** | Required traffic-shape view |
| Unique User-Agent share with cardinality guard | **Must** | Required diversity view without unbounded failure |
| Colored terminal, JSON, and CSV renderers | **Must** | Required interactive and pipeline outputs |
| Explicit malformed-line diagnostics and exit codes | **Must** | Required for trustworthy automation |
| Gzip input | **Should** | Common operational convenience; can follow the uncompressed MVP |
| Configurable top-N | **Could** | Useful flexibility but contradicts neither the fixed top-10 default nor MVP value |
| Custom nginx `log_format` definitions | **Could** | Expands compatibility but materially increases parser scope |
| Authentication, database, HTTP API, server, cloud, or Kubernetes | **Won't** | Explicitly outside the local stateless CLI product |
| Persistent history or dashboards | **Won't** | Belongs to observability platforms, not this one-shot tool |

### RICE Scoring (Must + Should)

`RICE = Reach × Impact × Confidence / Effort`, with Confidence represented as a decimal. Scores guide implementation order but dependencies remain authoritative.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming files/stdin and parser | 10 | 5 | 90% | 1.0 | 45.0 |
| Top IPs and error URLs | 10 | 5 | 95% | 0.75 | 63.3 |
| Hourly distribution | 9 | 4 | 95% | 0.25 | 136.8 |
| Unique User-Agent share and guard | 8 | 4 | 85% | 0.5 | 54.4 |
| Terminal/JSON/CSV output | 10 | 5 | 90% | 1.0 | 45.0 |
| Diagnostics and exit-code contract | 10 | 5 | 95% | 0.5 | 95.0 |
| Gzip input | 6 | 2 | 80% | 0.5 | 19.2 |

Implementation first establishes the parser dependency, then follows value and risk: trustworthy failure semantics, hourly aggregation, core top lists, cardinality-safe User-Agent aggregation, output contracts, and finally optional gzip support.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are represented in `PRD.md`.
- [ ] Python 3.11 code is typed and passes formatting/linting configured by the project.
- [ ] Unit and integration tests pass with at least 90% line coverage for `src/nginx_stream_insights`.
- [ ] Output schema and exit-code contract tests pass.
- [ ] No known Critical or High security findings remain.
- [ ] Relevant README and CLI help documentation are updated.
- [ ] The representative 1 GB benchmark stays under 30 seconds on the recorded reference laptop.
- [ ] Installation into a clean virtual environment and the three output modes are manually smoke-tested.

## 13. Strategic Boundaries and Kill Criteria

Stop or rescope the v1 effort if a representative optimized single-process prototype cannot process 1 GB in under 30 seconds on the reference laptop, if exact unique User-Agent tracking cannot be bounded with a clear failure mode, or if supporting real nginx inputs requires a general custom-format language. Do not respond by adding a server, database, cloud service, or distributed architecture; choose a narrower documented input contract or a more suitable implementation language in a separately approved project.

This strategy is implemented by `PROJECT_ARCHITECTURE.md`, sequenced in `IMPLEMENTATION_PLAN.md`, and made testable by `PRD.md`.
