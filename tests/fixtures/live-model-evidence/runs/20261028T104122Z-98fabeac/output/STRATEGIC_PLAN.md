# Strategic Plan: nginx-stream-insights

## 1. Product Idea

`nginx-stream-insights` is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. It is designed for fast incident triage without uploading logs or operating a service.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE/DevOps | Needs a useful traffic/error summary during an incident | One command, terminal-first output, bounded-memory streaming |
| Platform engineer | Infrastructure owner | Needs repeatable analysis in shell pipelines | Stable `--json` and `--csv` schemas and explicit exit codes |
| Developer | Service owner | Needs to identify noisy clients and failing routes locally | Top-10 rankings and hourly percentages without a server stack |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Our differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI/configuration surface than a focused pipeline tool | Small, deterministic CLI contract and native JSON/CSV |
| Logstash + Elastic + Kibana | Powerful ingestion, search, dashboards | Operational cost and persistent infrastructure are disproportionate | Zero-service, local, stateless execution |
| AWStats | Established historical reports | Batch/web-report orientation and older operational workflow | Streaming stdin/file processing and modern pipeline formats |
| `grep`/`awk` | Ubiquitous and composable | Ad hoc parsing, fragile quoting, no common schema or cardinality guard | Tested nginx parsing and consistent multi-metric output |

## 4. Unique Value Proposition

Obtain a pipeline-ready nginx incident summary from a local log in one command, with bounded memory and no data leaving the laptop.

## 5. Business Model

The MVP is free and open source. There is no paid tier, telemetry, hosted service, CAC, or revenue target. Value is measured by adoption, correctness, and reduced triage time; future sponsorship or support is explicitly outside the weekend MVP.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, strong standard-library streaming support |
| CLI | Click | Stable option parsing, help, and exit handling |
| Terminal UI | Rich | Readable colored tables with automatic no-color behavior when needed |
| Data models | `dataclasses` | Explicit internal records without a framework |
| Packaging | `pyproject.toml`, pip | Standard local installation and console entry point |
| Tests | pytest | Focused unit, integration, and performance tests |

## 7. Timeline

| Period | Stage | Result |
|---|---|---|
| Saturday morning | Contract, parser, fixtures | Valid/invalid lines classified deterministically |
| Saturday afternoon | Streaming aggregation | Four required metrics and safety limits implemented |
| Sunday morning | Text/JSON/CSV interfaces | Stable human and machine-readable outputs |
| Sunday afternoon | Tests, benchmark, packaging, docs | Pip-installable release candidate with evidence for the 1 GB target |

## 8. KPIs

| Metric | MVP target | One month | Three months |
|---|---:|---:|---:|
| Processing time for a 1 GB representative log | <30 s on the reference laptop | Maintain | Maintain |
| Correctness on committed parser/output fixtures | 100% | 100% | 100% |
| Peak memory | Bounded by documented unique-cardinality limit | No regression | No regression |
| Install-to-first-report time | <5 min | <3 min | <3 min |
| Unhandled exceptions on documented inputs | 0 | 0 | 0 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| nginx formats differ from the supported combined/common-like contract | High | High | Explicit `--format`, strict parser tests, invalid-line counters, documented exclusions |
| Exact top-10 and unique counts grow with cardinality | Medium | High | Configurable cardinality ceiling; fail predictably with exit code 4 rather than swapping or lying |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early, single-pass parsing, avoid per-line regex recompilation and object retention |
| CSV representation is ambiguous for multiple report sections | Medium | Medium | Define a long-form schema with a `metric` discriminator |
| Terminal color contaminates redirected output | Low | Medium | Color only for terminal text; never color JSON/CSV; provide `--no-color` |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Software and dependencies | $0 | Open-source stack |
| Infrastructure/cloud | $0 | Local execution only |
| Delivery | One weekend | Approved time box; no paid services |
| Ongoing operations | $0 | No hosted runtime or database |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream file or stdin | Must | Core local and pipeline use cases depend on it |
| Top-10 IPs | Must | Required traffic-abuse signal |
| Top-10 error URLs | Must | Required route-failure signal |
| Hourly request percentages | Must | Required traffic-shape signal |
| Unique User-Agent share | Must | Required client-diversity signal |
| Colored terminal report | Must | Required default experience |
| JSON and CSV outputs | Must | Required automation contract |
| Invalid-line accounting | Should | Makes partial input quality visible |
| Gzip input | Could | Useful but not needed for first delivery |
| Custom arbitrary nginx format compiler | Could | Broadens compatibility at substantial parser cost |
| Database, HTTP API, auth, server, cloud, Kubernetes | Won't | Conflicts with the approved local stateless scope |

### RICE Scoring (Must + Should)

Confidence is represented as a decimal in the formula `(Reach × Impact × Confidence) / Effort`.

| Feature | Reach | Impact | Confidence | Effort (days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin + parser | 10 | 5 | 90% | 1.0 | 45.0 |
| Core four-metric aggregation | 10 | 5 | 90% | 1.0 | 45.0 |
| Colored terminal report | 9 | 3 | 90% | 0.4 | 60.8 |
| JSON output | 8 | 4 | 90% | 0.4 | 72.0 |
| CSV output | 7 | 3 | 85% | 0.4 | 44.6 |
| Invalid-line accounting | 8 | 3 | 90% | 0.3 | 72.0 |

Dependency order takes precedence where a high-scoring output feature depends on parsing and aggregation.

## 12. Definition of Done

A feature is Done when:

- [ ] Behavior and acceptance criteria in `PRD.md` are implemented.
- [ ] Code runs on Python 3.11 and packaging builds successfully.
- [ ] Unit and integration tests pass with at least 90% line coverage for the package.
- [ ] The committed performance test demonstrates 1 GB in under 30 seconds on the documented reference laptop.
- [ ] Text, JSON, CSV, and exit-code contracts are regression-tested.
- [ ] Documentation and `CLAUDE.md` status are updated.
- [ ] No known Critical or High security issue remains.
- [ ] A human review accepts the final candidate; no deployment is required for this local CLI.

## 13. MVP Kill Criteria

Re-scope or stop the MVP if a single-process Python implementation cannot meet 1 GB in 30 seconds after profiling, if exact metrics cannot be kept within a documented safe cardinality bound, or if supported nginx formats cannot be specified deterministically within the weekend.

