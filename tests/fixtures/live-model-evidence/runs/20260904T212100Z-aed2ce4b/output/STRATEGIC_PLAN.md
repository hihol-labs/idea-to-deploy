# Strategic Plan: nginx-log-report

## 1. Product Idea

`nginx-log-report` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs one line at a time and produces an operational summary: top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request percentages, and the share of unique User-Agent strings. Rich terminal output is the default; stable JSON and CSV modes make the same analysis composable in pipelines.

The MVP is deliberately narrow: a stateless local process, no service to operate, and no data retained after the command exits. It is a $0 open-source project intended to be implementable over one weekend.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Investigates incidents from a shell | Needs a useful traffic/error picture before a dashboard is available | One command turns a large access log into the four most useful triage summaries |
| DevOps engineer | Maintains nginx hosts and CI jobs | `grep`/`awk` pipelines are fragile and inconsistent | Stable parsing, output schemas, and exit codes are reusable in automation |
| Platform engineer | Supports constrained or isolated environments | Full observability stacks are too costly or unavailable | Runs locally with no server, credentials, database, or network dependency |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | More features and presentation modes than a small pipeline task needs | Smaller fixed report contract with first-class JSON/CSV and Python packaging |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, retention, and dashboards | Operationally heavy; requires services, storage, and configuration | Zero-service, zero-retention, one-shot local analysis |
| AWStats | Established historical web analytics | Report-generation workflow and persistent history do not suit fast incident triage | Immediate stream-to-summary execution with no retained state |
| `grep`/`awk`/`sort` | Ubiquitous and flexible | Quoting, malformed lines, combined-log parsing, portability, and multi-metric consistency are fragile | One tested parser computes all metrics in a single pass with a versioned contract |

## 4. Unique Value Proposition

Get a deterministic nginx incident summary from a large local log in one command, without deploying or operating anything.

## 5. Business Model and License

The product is free and open source. There are no paid tiers, hosted components, telemetry, or usage fees. Value is measured through adoption, correctness, speed, and maintainer sustainability rather than revenue. A permissive OSI-approved license should be selected before the first public release; dependency licenses must be checked in the packaging step.

## 6. Technology Stack

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required, broadly available, and fast enough with a compiled regex and single-pass loop |
| CLI | Click | Predictable options, validation, help text, and exit behavior |
| Terminal presentation | Rich | Accessible colored tables with automatic non-TTY behavior |
| Domain models | `dataclasses` | Explicit typed records without a framework |
| Packaging | `pyproject.toml`, pip | Standard local and isolated installation path |
| Testing | pytest | Focused unit, CLI, golden-output, and performance tests |

## 7. Delivery Timeline

| Window | Work | Deliverable |
|---|---|---|
| Saturday morning | Package skeleton, domain contracts, parser | Installable CLI that parses representative combined logs |
| Saturday afternoon | Aggregation and resource guards | One-pass implementation of all four metrics |
| Sunday morning | Rich, JSON, and CSV renderers | Stable human and pipeline output contracts |
| Sunday afternoon | Tests, 1 GB benchmark, docs, release check | Release candidate with recorded correctness and performance evidence |

## 8. KPIs

| Metric | Release target | 1 month | 3 months |
|---|---:|---:|---:|
| Valid-log correctness on golden corpus | 100% | 100% | 100% |
| Malformed-line accounting | 100% | 100% | 100% |
| 1 GB runtime on reference laptop | <30 s | <30 s | <25 s where profiling supports it |
| Peak memory on bounded-cardinality benchmark | <512 MiB | <512 MiB | <384 MiB |
| Pipeline schema compatibility regressions | 0 | 0 | 0 |
| Documented user-reported successful runs | n/a | 10 | 50 |

The reference laptop, corpus generator, command, wall-clock method, and peak-RSS measurement must be recorded with benchmark results; the performance target is not accepted from an estimate.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined format | High | Medium | Fail visibly, count invalid lines, document grammar, and defer custom formats to P2 |
| High-cardinality values exhaust laptop memory | Medium | High | Configurable hard cardinality ceiling, deterministic exit code 4, and peak-RSS tests |
| Python misses the 1 GB/30 s target | Medium | High | Byte/line streaming, compiled parser, no per-line Rich work, profiling before optimization |
| JSON and CSV drift semantically | Medium | High | One report model, schema/golden tests, deterministic ordering |
| Terminal colors corrupt redirected output | Low | Medium | Color only on TTY by default; machine modes never emit ANSI |
| Ambiguous malformed-input policy hides data loss | Medium | High | Report valid/invalid totals; exit 3 when no valid records remain |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python and selected dependencies are open source |
| Infrastructure | $0 | Local CLI; no hosted runtime or storage |
| Delivery labor | One weekend | Approved constraint; no cash budget assigned |
| Distribution | $0 | Source repository and local/pip installation; public index publication is optional |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream nginx combined logs from files or stdin | Must | Foundation for local and pipeline use without loading the file into memory |
| Top 10 IPs | Must | Primary traffic-source triage view |
| Top 10 error URLs | Must | Identifies endpoints driving 4xx/5xx responses |
| Hourly request distribution | Must | Reveals traffic concentration and gaps |
| Unique User-Agent share | Must | Required client-diversity signal |
| Rich terminal report | Must | Default interactive experience |
| JSON and CSV output | Must | Required pipeline interoperability |
| Stable exit codes and malformed-line accounting | Must | Automation must distinguish usage, input, data, and resource failures |
| pip-installable package | Must | Required distribution mechanism |
| Gzip file input | Should | Common log rotation format; MVP remains valuable without it |
| Configurable cardinality limit | Should | Makes resource failure explicit and testable |
| Custom nginx `log_format` grammar | Could | Broadens compatibility but risks the weekend scope |
| Live `tail -f` dashboard | Could | Useful operational polish, not needed for one-shot analysis |
| Database, HTTP API, auth, server, cloud, Kubernetes | Won't | Explicitly outside the local stateless product boundary |

### RICE Scoring (Must and Should)

Confidence is expressed as a decimal in the formula `(Reach × Impact × Confidence) / Effort`.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming file/stdin parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Top 10 IPs | 9 | 4 | 90% | 0.25 | 129.6 |
| Top 10 error URLs | 9 | 5 | 90% | 0.35 | 115.7 |
| Rich terminal report | 9 | 4 | 90% | 0.35 | 92.6 |
| Hourly distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Unique User-Agent share | 8 | 3 | 85% | 0.30 | 68.0 |
| JSON output | 8 | 4 | 95% | 0.30 | 101.3 |
| CSV output | 7 | 3 | 90% | 0.30 | 63.0 |
| Stable exits and malformed accounting | 8 | 5 | 95% | 0.40 | 95.0 |
| pip packaging | 10 | 4 | 95% | 0.30 | 126.7 |
| Cardinality limit | 6 | 5 | 80% | 0.35 | 68.6 |
| Gzip input | 5 | 2 | 90% | 0.20 | 45.0 |

RICE informs ordering within dependency constraints: parsing and the report model precede every apparently higher-scoring consumer.

## 12. Definition of Done

A release is Done when:

- [ ] The package installs on a clean Python 3.11 environment with pip.
- [ ] All P0 acceptance criteria in `PRD.md` pass.
- [ ] Unit, CLI integration, golden-output, and packaging tests pass with at least 90% branch coverage for parser, aggregator, and renderers.
- [ ] A generated 1 GB corpus completes in under 30 seconds on the recorded reference laptop.
- [ ] Peak memory remains within the documented bound or exits with code 4 at the configured limit.
- [ ] JSON and CSV contain no ANSI escapes and match their documented schemas.
- [ ] Static checks and dependency/license checks pass with no known Critical or High security issue.
- [ ] `PROJECT_ARCHITECTURE.md`, `PRD.md`, user-facing usage documentation, and release notes agree.
- [ ] The exact release candidate and its evidence are independently reviewed before release.

## 13. Kill Criteria

Stop or rescope the MVP if a representative 1 GB log cannot meet 30 seconds after profiling-guided optimization; exact required metrics cannot be computed within an acceptable laptop memory bound; or stable parsing requires supporting arbitrary nginx formats in the first release. Do not silently weaken correctness or redefine the metrics to preserve the schedule.

