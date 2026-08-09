# Strategic Plan: Nginx Insights CLI

## 1. Product Summary

Nginx Insights CLI is a local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx combined access logs in one pass and reports the top 10 client IPs, the top 10 URLs associated with 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent values. It defaults to readable colored terminal output and offers stable JSON and CSV for pipelines.

The MVP is deliberately local and stateless: no authentication, database, HTTP API, server process, cloud service, or Kubernetes. The delivery budget is $0 and the target is a focused one-weekend build.

## 2. Target Users

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Diagnoses incidents from a shell | Needs a fast overview before opening a larger observability system | One command produces incident-oriented rankings and distributions |
| DevOps engineer | Maintains nginx fleets and CI jobs | Ad hoc `awk` pipelines are fragile and hard to standardize | Stable JSON/CSV schemas support repeatable automation |
| Platform engineer | Builds developer tooling | Heavy log stacks are unjustified for local files and short-lived investigations | A pip-installable, zero-service CLI keeps adoption and operating cost low |

## 3. Competitive Analysis

| Alternative | Strength | Limitation for this use case | Nginx Insights distinction |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI/config surface than the four required incident metrics | Narrow, pipeline-first contract with simple JSON and CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, storage, search, and dashboards | Requires persistent services, setup, resources, and operations | Local one-process analysis with no infrastructure |
| AWStats | Established historical web statistics | Batch-oriented, dated operational workflow, persistent generated reports | Immediate terminal output designed for SRE triage |
| `grep`/`awk`/`sort` | Ubiquitous and composable | Quoting, parsing, portability, and metric definitions vary by author | Tested parsing and consistent metric/output semantics |

## 4. Unique Value Proposition

Get the four nginx incident signals most useful during local triage, in one streaming command with human-readable and automation-safe output, without deploying or operating a log platform.

## 5. Business Model

The project is open source and free. There is no monetization in the MVP; value is measured through engineering time saved and reliable reuse. Distribution through PyPI avoids hosting costs. Community maintenance remains optional after the one-weekend delivery.

## 6. Technology Strategy

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required, widely available, productive for a weekend CLI |
| CLI | Click | Mature argument parsing, help, and standard usage error behavior |
| Terminal UI | Rich | Accessible color and tables with automatic terminal detection |
| Domain models | `dataclasses` | Typed, dependency-free records and report structures |
| Processing | Single-process, one-pass aggregation | Minimum operational surface and no persistent state |
| Packaging | `pyproject.toml`, pip | Standard install and console-script distribution |

See [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for the runtime design and [PRD.md](PRD.md) for behavior.

## 7. Delivery Timeline

| Window | Focus | Deliverable |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable CLI and validated combined-log records |
| Saturday afternoon | Streaming aggregations | All four metrics with deterministic tie-breaking |
| Sunday morning | Rich, JSON, and CSV renderers | Stable human and pipeline output |
| Sunday afternoon | Tests, benchmark, docs, release check | Acceptance evidence and publishable package candidate |

## 8. KPIs

| Metric | Launch target | First month target | Measurement |
|---|---:|---:|---|
| Processing performance | 1 GB in under 30 seconds on the reference laptop | Remains under 30 seconds | Recorded benchmark command and elapsed time |
| Metric correctness | 100% of golden fixtures | No known correctness regressions | Unit and end-to-end fixtures |
| Pipeline compatibility | JSON and CSV parse successfully | Zero schema-breaking changes within 0.x minor line | Contract tests |
| Installation usability | Fresh Python 3.11 environment installs and shows help | Under 2 minutes from pip install to first report | Clean-environment smoke test |

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from combined format | Medium | High | Declare combined format as P0, count malformed lines, add a later custom-format option |
| Exact cardinality and counters consume too much memory | Medium | High | Stream lines, cap exact User-Agent cardinality, fail explicitly with exit code 4, benchmark high-cardinality fixtures |
| Python misses the 1 GB/30 s target | Medium | High | Avoid per-line regex recompilation and object retention; benchmark early; profile before optimizing |
| CSV representation is ambiguous across metric types | Medium | Medium | Define one long-form schema and lock it with golden tests |
| Terminal color corrupts redirected output | Low | Medium | Enable color only for a TTY; JSON/CSV never contain ANSI escapes |
| Malformed lines silently distort results | Medium | Medium | Track valid/invalid counts, warn on stderr, and return code 3 when no valid records exist |

## 10. Budget

| Item | Cost | Notes |
|---|---:|---|
| Development tools | $0 | Python and dependencies are open source |
| Hosting/services | $0 | No hosted runtime or persistence |
| Distribution | $0 | PyPI publishing has no required fee |
| Delivery labor | One weekend | Time constraint, not a cash expense |
| Total cash budget | **$0** | Matches the approved constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream combined logs from a file or stdin | **Must** | The CLI has no value without local streaming input |
| Top 10 client IPs | **Must** | Core incident signal |
| Top 10 error URLs for 4xx/5xx | **Must** | Core failure signal |
| Hourly request percentages | **Must** | Core traffic-shape signal |
| Unique User-Agent share | **Must** | Core client-diversity signal |
| Colored terminal report | **Must** | Required default experience |
| JSON and CSV output | **Must** | Required pipeline contract |
| Malformed-line accounting and complete exit codes | **Must** | Makes results operationally trustworthy |
| Gzip input | **Should** | Common for rotated logs but not necessary for launch |
| Custom nginx `log_format` | **Could** | Broadens compatibility at substantial parser complexity |
| Approximate bounded-memory aggregations | **Could** | Useful for extreme cardinality after exact MVP semantics are proven |
| Authentication, database, API, server, cloud, Kubernetes | **Won't** | Explicitly incompatible with the local stateless product boundary |

### RICE Scoring (Must and Should)

Scores use `(Reach × Impact × Confidence) / Effort`, where confidence is a decimal.

| Feature | Reach | Impact | Confidence | Effort (days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin + parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Malformed-line and exit contract | 9 | 4 | 90% | 0.50 | 64.8 |
| Top 10 client IPs | 9 | 4 | 95% | 0.35 | 97.7 |
| Top 10 error URLs | 9 | 5 | 95% | 0.40 | 106.9 |
| Hourly request percentages | 8 | 4 | 95% | 0.30 | 101.3 |
| Unique User-Agent share | 7 | 3 | 85% | 0.35 | 51.0 |
| Colored terminal report | 8 | 3 | 90% | 0.50 | 43.2 |
| JSON and CSV output | 8 | 5 | 90% | 0.75 | 48.0 |
| Gzip input | 5 | 2 | 70% | 0.35 | 20.0 |

Dependency order overrides raw RICE when necessary: input parsing precedes every metric, and metric models precede renderers.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are present in [PRD.md](PRD.md).
- [ ] Python 3.11 code is formatted, type-checked, and lint-clean under the selected project commands.
- [ ] Unit tests pass; the project-wide line-coverage target is at least 90%.
- [ ] Relevant integration and golden-output tests pass.
- [ ] A clean virtual environment can install the package through pip.
- [ ] No known Critical or High security issue remains.
- [ ] User-facing documentation and output contracts are current.
- [ ] The 1 GB benchmark passes on the named reference laptop before release.
- [ ] The exact candidate is accepted through the repository Verification Loop contract.

## 13. Kill and Reassessment Criteria

Re-scope or stop the MVP if a straightforward one-pass Python implementation cannot process 1 GB under 30 seconds after profiling, if exact metric semantics require persistent storage, or if supporting real target logs requires a configurable parser beyond the one-weekend budget. Do not introduce a server or database to rescue the local CLI concept.
