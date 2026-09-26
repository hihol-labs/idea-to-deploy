# Strategic Plan: nginx-stream-report

## 1. Product Idea

`nginx-stream-report` is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs one line at a time and emits four operational summaries: the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, request distribution by hour, and the share of unique User-Agent values. Human-readable colored terminal output is the default; stable JSON and CSV outputs support pipelines.

The MVP is deliberately local and stateless. It does not authenticate users, retain logs, expose a network service, or require infrastructure. The delivery constraint is one weekend, with a $0 software and hosting budget.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a quick traffic/error picture without shipping sensitive logs elsewhere | One local command over a file or stdin |
| Platform engineer | Maintains nginx fleets and shell pipelines | Ad-hoc `awk` scripts are inconsistent and hard to automate safely | Stable metrics plus JSON/CSV schemas and exit codes |
| Small-team operator | Runs a few hosts without an observability stack | A full log platform is too costly and operationally heavy | Zero-service, pip-installable CLI with terminal-first output |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Fast, mature, rich interactive reports | Broader UI and configuration surface than needed; automation schema is not the core experience | Four focused metrics with explicit JSON/CSV contracts |
| Logstash + Elastic + Kibana | Powerful ingestion, search, retention, and dashboards | Requires services, storage, setup, and ongoing operations | No database or server; immediate local analysis |
| AWStats | Mature historical web analytics | Batch/reporting orientation and dated operational workflow | Stream from stdin and produce pipeline-friendly output |
| `grep`/`awk`/`sort` | Available almost everywhere and composable | Fragile quoting/parsing, repeated scans, locale differences, no shared contract | One parse pass, consistent definitions, tested exit behavior |

## 4. Unique Value Proposition

Get the four nginx traffic signals most useful during triage from a local log in one command, without deploying or operating another system.

## 5. Business Model

The project is open source and free. There is no paid tier, telemetry, hosted service, CAC, or monetization requirement for the MVP. Value is measured in operator time saved and reproducible incident analysis rather than revenue. If maintained beyond the MVP, development remains community- or sponsor-funded without changing the local-only product contract.

## 6. Technology Stack

| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Required, portable, strong standard-library parsing and streaming I/O |
| CLI | Click | Predictable option validation, help, and exit-code behavior |
| Terminal UI | Rich | Colored, readable tables with automatic non-TTY degradation |
| Domain models | `dataclasses` | Typed, dependency-free records and report structures |
| Packaging | `pyproject.toml` + pip | Standard install path and console-script entry point |
| Testing | pytest | Fast unit/integration coverage and familiar fixtures |
| Quality | Ruff + mypy | Low-friction linting and type checking |

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Friday evening | Package skeleton, contracts, fixtures | Installable CLI shell and representative log corpus |
| Saturday morning | Parser and streaming aggregates | Correct single-pass analysis with bounded line buffering |
| Saturday afternoon | Terminal, JSON, and CSV renderers | Stable output contracts and error handling |
| Sunday morning | Tests and performance tuning | Correctness suite and 1 GB benchmark evidence |
| Sunday afternoon | Packaging and documentation | Reproducible pip install and release-ready docs |

## 8. KPIs

| Metric | MVP / first month | 3 months | 6 months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | < 30 s | < 25 s | < 20 s |
| Peak RSS on 1 GB representative fixture | < 512 MiB | < 384 MiB | < 256 MiB |
| P0 acceptance tests passing | 100% | 100% | 100% |
| Supported output contract regressions | 0 | 0 | 0 |
| Clean-install-to-first-report time | < 2 min | < 90 s | < 60 s |

The reference laptop and generated benchmark fixture must be recorded with every performance result; the targets are not considered proven until measured.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the combined format | High | High | Define the accepted grammar, show line-numbered diagnostics, and fail code 3 in strict mode |
| Exact cardinality state consumes excessive memory | Medium | High | Configurable unique-UA ceiling and explicit exit code 4 before uncontrolled growth |
| Python misses the 1 GB / 30 s target | Medium | High | Single pass, compiled regex, avoid per-line objects, profile before optimizing, benchmark in CI where feasible |
| CSV representation is ambiguous across report sections | Medium | Medium | Use one documented normalized schema with a `section` discriminator |
| Color corrupts redirected output | Low | Medium | Auto-disable color for non-TTY output and provide `--no-color` |
| IP/URL cardinality produces memory pressure | Medium | Medium | Document exact aggregation cost, measure adversarial fixtures, and reject infeasible expansion rather than add hidden approximation |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and test tools are open source |
| Hosting / database / cloud | $0 | None exists in the architecture |
| CI | $0 | Use a free open-source allowance or run locally |
| Distribution | $0 | Source distribution/wheel through standard Python tooling |
| Delivery labor | One weekend | Explicit time-box; no paid external services |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream nginx combined logs from a file or stdin | Must | Foundation for local and pipeline use |
| Top 10 client IPs | Must | Core traffic-source signal |
| Top 10 URLs by 4xx/5xx count | Must | Core failure-triage signal |
| Hourly request percentage distribution | Must | Core traffic-shape signal |
| Unique User-Agent share with exhaustion guard | Must | Required client-diversity signal and safe failure behavior |
| Colored terminal report | Must | Required default experience |
| JSON output | Must | Required automation format |
| CSV output | Must | Required pipeline/tabular format |
| Strict malformed-line handling | Must | Makes the defined data-format exit code enforceable in automation |
| Common-log-format support without User-Agent | Could | Broadens compatibility but weakens one required metric |
| Gzip input | Could | Convenient, but shell decompression already composes with stdin |
| Database, HTTP API, auth, server, cloud, Kubernetes | Won't | Contradicts the approved local stateless scope |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`; confidence is expressed as a decimal in the calculation. Ordering breaks close scores by dependency.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Top IP aggregation | 9 | 4 | 95% | 0.25 | 136.8 |
| Error URL aggregation | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly percentage distribution | 9 | 4 | 95% | 0.30 | 114.0 |
| Streaming file/stdin ingestion | 10 | 5 | 100% | 0.5 | 100.0 |
| Terminal report | 10 | 4 | 95% | 0.40 | 95.0 |
| JSON output | 8 | 4 | 95% | 0.35 | 86.9 |
| Unique User-Agent share and guard | 8 | 4 | 85% | 0.45 | 60.4 |
| CSV output | 7 | 3 | 90% | 0.35 | 54.0 |
| Strict malformed-line mode | 5 | 3 | 90% | 0.25 | 54.0 |

Dependency-correct implementation starts with ingestion and parsing, then builds the high-value aggregates, followed by renderers and strict-mode polish; raw score does not move a consumer ahead of its prerequisite.

## 12. Definition of Done

A feature is done when:

- [ ] Behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Python 3.11 code installs and the console command starts without errors.
- [ ] Unit and integration tests pass with at least 90% line coverage for `src/`.
- [ ] Static checks (`ruff` and `mypy`) pass.
- [ ] Relevant terminal, JSON, CSV, and exit-code contracts are tested.
- [ ] The 1 GB benchmark is recorded when performance-sensitive behavior changes.
- [ ] Documentation is updated in `README.md` and architecture/PRD when contracts change.
- [ ] No known Critical or High security issues remain.
- [ ] A human verifies the packaged CLI locally; there is no staging deployment for this local-only product.

## 13. Strategic Success and Kill Criteria

Proceed with release if all P0 acceptance criteria pass and the recorded reference benchmark processes 1 GB in under 30 seconds. Re-scope or stop if exact required metrics cannot meet the target within the one-weekend time-box, if a mandatory dependency introduces cost, or if implementation requires a database/server contrary to the product premise.
