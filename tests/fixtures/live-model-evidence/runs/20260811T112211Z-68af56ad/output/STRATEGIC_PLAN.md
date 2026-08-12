# Strategic Plan: Nginx Stream Insights

## 1. Product Idea

Nginx Stream Insights is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx combined access logs from files or standard input in one pass and reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent values. It is designed for incident triage and pipeline use without uploading logs or operating infrastructure.

The MVP is an open-source utility delivered over one weekend with a $0 operating budget. It is not a log platform: it deliberately has no authentication, database, HTTP API, server, cloud service, or Kubernetes deployment.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates production incidents | Needs a useful traffic/error summary in seconds without provisioning a service | Streams local or piped logs and emits an immediate terminal report |
| DevOps engineer | Automates operational checks | Shell pipelines need stable machine-readable output and exit codes | Provides JSON, normalized CSV, and a `0/1/2/3/4` exit-code contract |
| Platform engineer | Handles large and sensitive log files | Cannot upload logs and cannot tolerate unbounded memory | Processes locally in one pass with an explicit unique-cardinality guard |

## 3. Problem and Value Proposition

During an incident, `grep`, `awk`, and ad hoc scripts are fast to begin but costly to compose correctly, reproduce, and integrate. Full observability stacks are powerful but require persistent services, configuration, and resource spend. This tool occupies the narrow space between them: one install, one command, four high-value summaries, exact pipeline output, and no operational footprint.

**Value proposition:** obtain a reproducible nginx traffic and error snapshot from a 1 GB log in under 30 seconds on a representative laptop, locally and with no service setup.

## 4. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, rich interactive reports | Broader UI/configuration surface than a four-metric pipeline tool | Smaller contract, predictable JSON/CSV, Python-native installation |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, querying, retention, dashboards | Requires multiple long-running services, storage, setup, and maintenance | Stateless local processing with $0 infrastructure |
| AWStats | Established web-log reporting and historical views | Oriented toward generated reports and retained history | Incident-focused streaming CLI with stdin support |
| `grep` / `awk` / `sort` | Ubiquitous, composable, no install in many environments | Fragile parsing, locale differences, repeated passes, difficult error handling | Tested nginx parsing, one-pass aggregation, explicit output schemas and exit codes |

The project does not aim to replace these alternatives for dashboards, historical analytics, arbitrary queries, or minimal one-off filtering.

## 5. Business and Distribution Model

- License: permissive open-source license.
- Distribution: Python package installable with pip.
- Revenue: none in the MVP; the product is a focused community utility.
- Unit economics: no hosted service, so infrastructure cost and per-run marginal cost are $0; maintenance time is the only ongoing cost.
- Adoption loop: searchable package metadata, concise examples, stable output contracts, and contributor-friendly tests.

## 6. Technology Strategy

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Approved stack, broad availability, adequate streaming performance with careful parsing |
| CLI | Click | Reliable option validation, help text, and standard exit behavior |
| Terminal UI | Rich | Colored, readable tables with TTY-aware behavior |
| Domain model | `dataclasses` | Lightweight typed records without a validation framework |
| Packaging | pip-compatible `pyproject.toml` | Familiar installation and console entry point |
| Processing | Single-process, single-pass streaming | Lowest complexity and predictable local resource usage |

## 7. Delivery Timeline

| Window | Milestone | Result |
|---|---|---|
| Saturday morning | Package, contracts, parser | Installable CLI skeleton and tested combined-log parsing |
| Saturday afternoon | Streaming aggregates | Four exact metrics with malformed-line accounting and cardinality guard |
| Sunday morning | Text, JSON, and CSV renderers | Stable human and pipeline output contracts |
| Sunday afternoon | Performance, integration, documentation | 1 GB benchmark evidence, acceptance tests, release-ready package |

## 8. Success Metrics

| Metric | MVP / first month target | Three-month target | Measurement |
|---|---:|---:|---|
| Processing performance | 1 GB in <30 seconds on the documented laptop profile | No regression beyond 10% | Reproducible local benchmark fixture and command |
| Peak resident memory | ≤512 MiB at default cardinality limit | No regression beyond 10% | `/usr/bin/time -v` benchmark |
| Correctness | All golden fixtures and output-schema tests pass | Zero unresolved correctness defects | Automated test suite and issue tracker |
| Pipeline stability | JSON and CSV schemas documented and tested | No breaking schema change without a major version | Snapshot/schema tests |
| Utility adoption | 25 package installs or repository stars | 100 installs or stars | Package/repository statistics, if published |

Performance claims are accepted only against a documented machine, fixture shape, command, elapsed time, and peak memory measurement.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Python parsing misses the 1 GB / 30 s target | Medium | High | Benchmark early; avoid per-line regex backtracking and unnecessary allocations; profile before optimizing |
| High-cardinality IPs, URLs, or User-Agents exhaust memory | Medium | High | Bound each exact distinct-key map with `--max-unique`; fail explicitly with exit code 4 |
| Real nginx formats differ from combined format | High | Medium | State the supported grammar, count malformed lines, provide actionable diagnostics, defer custom formats |
| CSV representation of multiple report sections is ambiguous | Medium | Medium | Use a documented normalized row schema with a `metric` discriminator |
| Colored output corrupts redirected pipelines | Low | Medium | Enable color only for an interactive terminal; JSON/CSV never contain ANSI escapes |
| Scope expands into a hosted analytics platform | Medium | High | Keep server, database, auth, cloud, Kubernetes, retention, and dashboards explicitly out of scope |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Open-source dependencies | $0 | Python, Click, Rich, and test tooling |
| Hosting / database / cloud | $0 | None exists in the approved architecture |
| Distribution | $0 | Source repository and public Python package tooling |
| Development | $0 cash budget | One weekend of owner time |
| Ongoing operations | $0 | No operated service |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream combined-format logs from files or stdin | **Must** | Foundation for local and pipeline use |
| Top 10 client IPs | **Must** | Core incident-triage signal |
| Top 10 URLs by combined 4xx/5xx count | **Must** | Core error hot-spot signal |
| Hourly request distribution | **Must** | Required traffic-shape view; each percentage is `100 × hourly_request_count / total_valid_requests` |
| Unique User-Agent share | **Must** | Required client-diversity signal |
| Colored terminal report | **Must** | Default interaction contract |
| JSON and CSV output | **Must** | Required pipeline integration contract |
| Cardinality guard and complete exit-code contract | **Must** | Makes bounded-memory behavior observable and automatable |
| Gzip-compressed input | **Should** | Common operational convenience, but decompression is not necessary for core value |
| Configurable nginx log format | **Could** | Broadens compatibility after the combined-format parser is stable |
| Persistent history or dashboards | **Won't** | Conflicts with stateless CLI scope |
| Authentication, database, API, server, cloud, Kubernetes | **Won't** | Explicitly excluded and unnecessary for local analysis |

### RICE Scoring for Must and Should Features

Scores use `(Reach × Impact × Confidence) / Effort`, where confidence is decimalized.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| File/stdin streaming and parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Top IP aggregation | 9 | 4 | 95% | 0.25 | 136.8 |
| Error URL aggregation | 10 | 5 | 95% | 0.25 | 190.0 |
| Hourly distribution | 8 | 3 | 95% | 0.25 | 91.2 |
| Unique User-Agent share | 7 | 3 | 85% | 0.25 | 71.4 |
| Colored terminal report | 9 | 3 | 90% | 0.50 | 48.6 |
| JSON and CSV output | 8 | 4 | 90% | 0.50 | 57.6 |
| Cardinality guard and exit codes | 8 | 5 | 90% | 0.50 | 72.0 |
| Gzip input | 5 | 2 | 75% | 0.25 | 30.0 |

Dependency order overrides raw RICE where necessary: parsing precedes every aggregation, and aggregation contracts precede renderers.

## 12. Definition of Done

A feature is done when:

- [ ] Its behavior and acceptance criteria agree with `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Code runs on Python 3.11 and lint/type checks selected by the project pass.
- [ ] Unit and integration tests pass with at least 90% line coverage for parser, aggregator, and renderer modules.
- [ ] P0 golden fixtures cover success, malformed data, output formats, and exit codes.
- [ ] Review is complete and no known critical or high-severity security issue remains.
- [ ] User-facing documentation and CLI help are updated.
- [ ] Performance-sensitive changes pass the documented 1 GB laptop benchmark.
- [ ] The exact candidate is verified according to the repository's Idea to Deploy verification contract.

## 13. Kill and Reassessment Criteria

Reassess the MVP if careful profiling shows that Python 3.11 cannot process the representative 1 GB fixture in under 30 seconds without violating the memory bound, or if exact required metrics cannot be maintained within the documented default cardinality limit for representative logs. Do not hide either failure with sampling or silently approximate results; revise the performance target, parser strategy, or product scope explicitly.

