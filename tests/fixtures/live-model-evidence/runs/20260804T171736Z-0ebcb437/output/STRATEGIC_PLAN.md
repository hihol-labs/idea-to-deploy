# Strategic Plan: Nginx Stream Analyzer

## 1. Product Idea

Nginx Stream Analyzer is an open-source, local Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and emits an operational summary without loading the file into memory or sending data elsewhere: top-10 client IPs, top-10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich colored text is the default; JSON and CSV make the same report usable in pipelines.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE | Needs a fast first view of a large incident log | One local command, bounded memory, useful aggregates |
| Platform engineer | DevOps | Needs repeatable output in shell pipelines | Stable `--json` and `--csv` schemas and exit codes |
| Service owner | Backend/operations lead | Needs error hotspots without deploying an observability stack | Top failing URLs and traffic distribution from existing logs |

## 3. Competitive Analysis

| Alternative | Strength | Limitation for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI and configuration surface than a focused pipeline tool | Narrow, predictable four-metric report with native JSON/CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards | Infrastructure, state, setup, and operating cost | Zero-service local analysis and no data retention |
| AWStats | Established historical reporting | Batch-oriented, persistent reports, dated operational workflow | Streaming CLI output designed for immediate incident use |
| `grep`/`awk` pipelines | Installed almost everywhere, composable | Fragile parsing and inconsistent metrics/schemas | Tested nginx parsing, one command, stable contracts |

## 4. Unique Value Proposition

Analyze a gigabyte of nginx traffic locally in one command, with stable human and machine-readable results, without standing up or operating an observability system.

## 5. Business Model

The MVP is free and open source. There are no paid tiers, hosted services, telemetry, or data collection. The economic value is reduced incident triage time; acquisition and distribution use the package index and source repository at $0 cash cost.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved stack, broad laptop availability |
| CLI | Click | Stable argument parsing and exit behavior |
| Terminal UI | Rich | Colored, readable default output |
| Domain models | `dataclasses` | Lightweight typed records without extra runtime machinery |
| Packaging | pip-compatible `pyproject.toml` | Standard local and virtual-environment installation |
| Processing | Single-process streaming | Bounded memory, simple profiling, no coordination overhead |

## 7. Timeline

| Period | Stage | Result |
|---|---|---|
| Saturday morning | Package, contracts, parser | Installable CLI skeleton and resilient streaming parser |
| Saturday afternoon | Aggregation | Four required metrics with bounded-memory safeguards |
| Sunday morning | Renderers | Rich text, JSON, and CSV output contracts |
| Sunday afternoon | Verification and polish | Tests, 1 GB benchmark, documentation, releasable package |

## 8. KPIs

| Metric | Launch target | 1-month target | Guardrail |
|---|---|---|---|
| 1 GB processing time | <30 s on the reference laptop | Sustain <30 s | No full-file buffering |
| Valid-line accounting | 100% in fixture tests | 100% | Valid + malformed = lines read |
| Output parity | All formats expose the same metrics | 100% schema compatibility | Golden-output tests |
| Peak resident memory | Measured and documented | Remains within the benchmark ceiling | Hard per-dimension cardinality limits and a maximum physical-line size; exhaustion exits 4 |
| Install-to-first-report | <30 s after package download | <30 s | One executable command |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real-world nginx formats vary | High | High | Explicit supported combined-log grammar, representative fixtures, malformed-line counter |
| Exact IP, URL, or User-Agent cardinality can exhaust memory | Medium | High | Configurable hard limits and documented exit code 4; never silently approximate |
| Python misses the 1 GB/30 s target | Medium | High | Byte/line streaming, compiled regex or split parser benchmarked early, profile before optimizing |
| CSV shape is ambiguous for heterogeneous metrics | Medium | Medium | Long-form schema with `metric,rank,key,value,unit` and golden tests |
| Colored output pollutes redirected pipelines | Low | Medium | Enable color only for an interactive terminal; machine modes never emit ANSI |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python and selected dependencies are open source |
| Hosting/infrastructure | $0 | Local CLI; no hosted component |
| Distribution | $0 | Source repository and public package index |
| Labor | One weekend | Approved delivery constraint; opportunity cost not cash spend |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Streaming nginx combined-log parsing | **Must** | Foundation for every metric and the performance promise |
| Top-10 client IPs | **Must** | Required incident triage metric |
| Top-10 4xx/5xx URLs | **Must** | Required error hotspot metric |
| Hourly request percentages | **Must** | Required load-shape metric |
| Exact unique User-Agent share with hard aggregate-cardinality guards | **Must** | Required diversity metric without hidden approximation or unbounded exact counters |
| Rich terminal, JSON, and CSV renderers | **Must** | Required human and pipeline interfaces |
| Gzip input | **Should** | Common operational convenience, but plain logs ship the MVP |
| Read from standard input | **Should** | Improves pipeline composition after file input is stable |
| Configurable top-N | **Could** | Useful flexibility but top-10 is the explicit product contract |
| Auth, database, HTTP API, server, cloud, Kubernetes | **Won't** | Conflicts with the local stateless CLI scope |

### RICE Scoring (Must + Should)

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Core four-metric aggregation | 10 | 5 | 90% | 1.00 | 45.0 |
| Terminal/JSON/CSV renderers | 10 | 4 | 90% | 0.75 | 48.0 |
| Unique-cardinality guard | 8 | 5 | 90% | 0.25 | 144.0 |
| Standard-input support | 6 | 3 | 80% | 0.25 | 57.6 |
| Gzip input | 5 | 3 | 80% | 0.25 | 48.0 |

RICE helps order thin vertical increments, but dependencies remain binding: package and parser contracts precede aggregation, and aggregation precedes rendering.

## 12. Definition of Done

A feature is Done when:

- [ ] The behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Code runs on Python 3.11 and lint/type checks pass.
- [ ] Unit and integration tests pass with at least 90% branch coverage in parser and aggregation modules.
- [ ] Machine-output golden tests pass and contain no ANSI sequences.
- [ ] The reference 1 GB benchmark completes in under 30 seconds.
- [ ] No known Critical or High security issue remains.
- [ ] User-facing and implementation documentation is current.
- [ ] A clean virtual environment can install the package and run the CLI.

## 13. Kill Criteria

Re-scope or stop the MVP if a representative 1 GB log cannot meet 30 seconds after profiling and one bounded optimization pass, if exact required metrics cannot remain within an explicit memory guard, or if delivery requires a service, database, or paid infrastructure.
