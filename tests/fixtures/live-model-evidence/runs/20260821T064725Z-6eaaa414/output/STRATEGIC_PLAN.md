# Strategic Plan: nginx Stream Analytics CLI

## 1. Product Idea

A local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx combined access logs as a stream and produces four operational views without uploading or persisting logs: top 10 client IPs, top 10 URLs associated with 4xx/5xx responses, hourly request distribution, and the percentage share of unique User-Agent strings. Rich colored text is the default; JSON and CSV make the same report usable in pipelines.

The MVP is a zero-cost open-source utility delivered in one weekend. It is deliberately not an observability platform: there is no authentication, database, HTTP API, server, cloud service, or Kubernetes deployment.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates an incident from a rotated access log | Needs useful traffic and error signals before a dashboard can be configured | One local command emits a deterministic summary |
| DevOps engineer | Checks a deployment or reverse-proxy change | grep/awk pipelines are fragile and hard to share | Stable metrics, exit codes, and JSON/CSV contracts |
| Platform engineer | Automates fleet diagnostics | Interactive-only tools are difficult to compose | stdin/file input and machine-readable output |

## 3. Competitive Analysis

| Alternative | What it does well | Limitation for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive nginx analytics | Larger UI/reporting surface than a four-metric pipeline tool | Minimal local CLI with strict JSON/CSV schemas |
| Logstash + Elastic + Kibana | Powerful ingestion, search, and dashboards | Requires multiple services, storage, administration, and resources | No service or persistence; starts immediately |
| AWStats | Established historical web analytics | Batch-oriented, dated workflow, and generated reports | Stream-first operational summary for terminal use |
| grep/awk/sort | Ubiquitous and flexible | Locale-sensitive, hard to validate, memory-heavy sorting, brittle parsing | Tested nginx parsing and bounded top-k/cardinality behavior |

## 4. Unique Value Proposition

Get the four nginx access-log signals most useful during local incident triage in one composable, privacy-preserving command—without operating an analytics stack.

## 5. Business Model and License

The project is open source and free to use. There are no paid tiers, hosted services, or telemetry. Value is measured by adoption and saved diagnostic time, not revenue; distribution is through a standard Python package suitable for `pip` installation.

## 6. Technology Stack

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, strong standard-library streaming support |
| CLI | Click | Reliable argument validation, stdin/file handling, exit behavior |
| Terminal UI | Rich | Readable tables and color with terminal capability handling |
| Data models | `dataclasses` | Typed internal contracts without validation-framework overhead |
| Parsing/aggregation | Python standard library | Keeps dependencies and memory overhead small |
| Packaging | `pyproject.toml`, pip | Standard install and console-script distribution |
| Testing | pytest | Fast unit, integration, golden-output, and performance tests |

## 7. Timeline

| Period | Focus | Deliverable |
|---|---|---|
| Saturday morning | Package skeleton, parser, contracts | Installable CLI that parses representative logs |
| Saturday afternoon | Streaming aggregation | Four correct metrics with explicit malformed-line policy |
| Sunday morning | Rich, JSON, and CSV rendering | Stable human and pipeline outputs |
| Sunday afternoon | Tests, benchmark, docs, packaging | Release candidate meeting acceptance criteria |

## 8. KPIs

| Metric | Release target | First month | Three months |
|---|---:|---:|---:|
| Processing performance | 1 GB in under 30 seconds on the documented laptop baseline | No regression above 10% | Maintain target |
| Peak memory | Bounded by documented unique-cardinality limit; independent of line count otherwise | No exhaustion on representative logs | Limit tuned from feedback |
| Parser validity | 100% of valid golden corpus parsed correctly | Fewer than 1 confirmed parser defect per 10 issues | No open P0 parser defects |
| Machine-output stability | JSON/CSV contract tests pass | Zero unannounced schema breaks | Semantic versioning maintained |
| Adoption | Installable locally | 25 successful installs/stars combined | 100 successful installs/stars combined |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Regex parsing is too slow for 1 GB / 30 seconds | Medium | High | Benchmark early; avoid per-line object churn; profile before optimization |
| Unexpected nginx log variants are misclassified | High | High | Support one explicit combined-log grammar in MVP; report malformed counts and fail when no valid records exist |
| Unbounded unique IP/URL/User-Agent cardinality exhausts memory | Medium | High | Configurable hard cardinality ceiling; terminate with exit code 4 and a clear diagnostic |
| JSON and CSV drift from terminal semantics | Medium | Medium | One report dataclass rendered by all output adapters; golden contract tests |
| Color corrupts redirected output | Low | Medium | Auto-disable color when stdout is not a TTY; JSON/CSV never contain ANSI sequences |
| Weekend scope expands into a monitoring platform | Medium | High | Enforce Won't list and CLI-only architecture decision |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development tools | $0 | Python, Click, Rich, and pytest are open source |
| Hosting/infrastructure | $0 | Local CLI; no hosted runtime |
| Database/cloud/Kubernetes | $0 | Explicitly out of scope |
| Distribution | $0 | Source release and standard package index tooling |
| Total | $0 | One-weekend contributor time is the only investment |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream combined-log input from a file or stdin | **Must** | Foundation of all analysis and pipeline use |
| Top 10 client IPs | **Must** | Core traffic-source signal |
| Top 10 URLs by 4xx/5xx errors | **Must** | Core failure-triage signal |
| Hourly request distribution | **Must** | Core temporal signal |
| Unique User-Agent share | **Must** | Core client-diversity signal |
| Rich colored terminal report | **Must** | Approved default experience |
| JSON output | **Must** | Required pipeline contract |
| CSV output | **Must** | Required pipeline contract |
| Malformed-line accounting and exit codes 0/1/2/3/4 | **Must** | Required operational reliability |
| gzip input | **Should** | Common for rotated logs but not necessary for MVP value |
| Configurable top-N | **Could** | Useful flexibility beyond the approved top 10 |
| Additional nginx log formats | **Could** | Broadens adoption after the combined-format MVP |
| Authentication, database, API, server, cloud, Kubernetes | **Won't** | Contradicts the local stateless product boundary |
| Live dashboard or historical trend storage | **Won't** | Belongs to established observability products |

### RICE Scoring for Must and Should Features

Confidence is expressed as a decimal in the formula `(Reach × Impact × Confidence) / Effort`.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE |
|---|---:|---:|---:|---:|---:|
| Streaming file/stdin parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Top IP aggregation | 9 | 4 | 90% | 0.25 | 129.6 |
| Error URL aggregation | 10 | 5 | 90% | 0.35 | 128.6 |
| Hourly distribution | 8 | 4 | 90% | 0.25 | 115.2 |
| Unique User-Agent share and guard | 8 | 4 | 80% | 0.40 | 64.0 |
| Rich terminal report | 9 | 4 | 90% | 0.40 | 81.0 |
| JSON output | 8 | 4 | 95% | 0.25 | 121.6 |
| CSV output | 6 | 3 | 95% | 0.25 | 68.4 |
| Diagnostics and exit codes | 10 | 5 | 95% | 0.40 | 118.8 |
| gzip input | 6 | 3 | 80% | 0.30 | 48.0 |

Implementation remains dependency-aware: parsing precedes the individually high-scoring reports, while the report model precedes output adapters.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Code runs on Python 3.11 and package installation succeeds in a clean virtual environment.
- [ ] Unit and integration tests pass with at least 90% line coverage for parser, aggregation, and rendering modules.
- [ ] JSON and CSV golden contract tests pass without ANSI output.
- [ ] The 1 GB benchmark completes in under 30 seconds on the recorded laptop baseline.
- [ ] Unique-cardinality exhaustion is safely detected and returns exit code 4.
- [ ] Documentation is current and no known Critical or High security issue remains.
- [ ] The exact candidate passes the repository verification contract before release acceptance.

## 13. Kill Criteria

Stop or redesign the MVP if a representative 1 GB combined log cannot meet the performance target after profiling, if correct processing cannot be bounded against adversarial cardinality, or if supporting stable JSON/CSV requires retaining the input dataset in memory. Do not respond by adding a database or service; reassess the Python implementation or narrow the documented input contract.
