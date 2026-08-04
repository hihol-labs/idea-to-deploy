# Strategic Plan: nginx-stream-report

## 1. Product Idea

`nginx-stream-report` is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs incrementally from a file or standard input and reports top-10 client IPs, top-10 URLs producing 4xx/5xx responses, hourly request percentages, and the share of unique User-Agent values. It is designed for fast incident triage without uploading operational data or provisioning a service.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | Diagnoses incidents under time pressure | Needs a useful traffic/error summary immediately | One command, terminal-first output, explicit diagnostics |
| SRE/platform engineer | Investigates large logs locally | GUI stacks are too heavy for one-off analysis | Streaming bounded-memory processing and pipeline formats |
| Systems administrator | Works on minimal servers or copied log files | Ad-hoc shell pipelines are fragile and hard to reproduce | Installable, documented CLI with stable schemas and exit codes |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, rich interactive reports | Broader UI/configuration surface than a four-metric pipeline tool | Narrow, scriptable contract with JSON/CSV and Python installation |
| Logstash + Elastic + Kibana | Powerful ingestion, search, dashboards | Infrastructure, storage, and operating cost are disproportionate for local triage | Zero-service, zero-retention, local execution |
| AWStats | Established historical web analytics | Batch/report oriented and dated operational workflow | Streaming terminal feedback and modern machine-readable output |
| `grep`/`awk`/`sort` | Ubiquitous and flexible | Quoting, parsing, memory, locale, and metric semantics vary by script | Reproducible nginx parsing and stable formulas |

## 4. Unique Value Proposition

Get the four highest-value nginx triage signals from a gigabyte-scale log in one local command, with no service, database, or data upload.

## 5. Business Model

The project is open source and free. There is no paid tier, CAC target, or monetization dependency; value is measured through adoption, correctness, and operator time saved. Maintenance is community-driven and must remain compatible with the approved $0 cash budget.

## 6. Technology Stack

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Required, portable, strong standard-library streaming support |
| CLI | Click | Stable command/options/exit handling |
| Terminal rendering | Rich | Readable colored tables with automatic non-TTY behavior |
| Domain state | `dataclasses` | Explicit, low-overhead internal models |
| Packaging | `pyproject.toml`, pip | Standard install and console-script delivery |
| Tests/quality | pytest, Ruff, mypy | Fast local correctness and static checks |

## 7. Timeline

| Block | Scope | Result |
|---|---|---|
| Saturday morning | Package skeleton, CLI contract, parser | Installable command parses representative combined logs |
| Saturday afternoon | Streaming aggregators and limits | All four metrics computed incrementally |
| Sunday morning | Rich, JSON, CSV renderers | Human and pipeline contracts implemented |
| Sunday afternoon | Tests, 1 GB benchmark, docs, packaging | Release candidate with recorded evidence |

## 8. KPIs

| Metric | One month | Three months | Six months |
|---|---:|---:|---:|
| 1 GB benchmark on reference laptop | <30 s | <30 s | <30 s |
| Correctness fixture pass rate | 100% | 100% | 100% |
| Worst peak RSS across three 1 GiB baseline runs | <256 MiB | <256 MiB | <256 MiB |
| Successful installs from a clean Python 3.11 environment | 100% | 100% | 100% |
| Confirmed users or repository stars | 10 | 50 | 150 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| nginx format variations produce parse errors | High | High | Explicit combined-format MVP, documented parser contract, fixtures, actionable counters |
| Exact unique cardinality or long fields consume memory | Medium | High | Per-dimension entry, shared retained-byte, and 64 KiB line caps; fail closed with exit code 4 for key-budget exhaustion |
| Python misses the 1 GB/30 s target | Medium | High | Single-pass parser, no per-line regex recompilation, profiling and release benchmark |
| CSV/JSON contracts drift | Medium | Medium | Golden fixtures and schema assertions |
| Terminal color contaminates redirected output | Low | Medium | Color only for TTY text; never in JSON/CSV |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Open-source stack |
| Infrastructure | $0 | Local-only; no hosted components |
| Distribution | $0 | pip-compatible build artifacts and public package tooling |
| Delivery labor | One weekend | Pre-approved delivery constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Streaming combined-log parsing from path/stdin | Must | Foundation for every report and bounded processing |
| Top-10 client IPs | Must | Core traffic triage signal |
| Top-10 error URLs for 4xx/5xx | Must | Core failure triage signal |
| Hourly request percentage distribution | Must | Required temporal signal |
| Unique User-Agent share with cardinality guard | Must | Required client-diversity signal with safe failure |
| Rich text plus JSON and CSV output | Must | Required human and pipeline interfaces |
| gzip input | Should | Common archived-log workflow; not required for MVP value |
| Live `--follow` mode | Could | Helpful operational polish after finite-stream correctness |
| Custom nginx `log_format` parser | Could | Broadens compatibility but threatens weekend scope |
| Database, HTTP API, auth, cloud, Kubernetes | Won't | Contradicts local stateless CLI purpose |

### RICE Scoring (Must + Should)

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Streaming parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Rich/JSON/CSV output | 10 | 4 | 90% | 0.75 | 48.0 |
| Top IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Error URLs | 9 | 5 | 95% | 0.35 | 122.1 |
| Hourly percentages | 8 | 4 | 95% | 0.25 | 121.6 |
| Unique User-Agent share and guard | 7 | 3 | 85% | 0.40 | 44.6 |
| gzip input | 5 | 2 | 80% | 0.25 | 32.0 |

Dependency ordering overrides raw RICE where necessary: establish the parser and output contracts before exposing individual metrics.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Python 3.11 code passes Ruff and mypy.
- [ ] Unit and integration tests pass with at least 90% branch coverage for parser, aggregation, and rendering modules.
- [ ] The full CLI contract, including exit codes, has automated tests.
- [ ] The 1 GB reference benchmark completes in under 30 seconds on the named laptop with peak RSS recorded.
- [ ] JSON and CSV golden outputs remain stable and terminal output is manually verified.
- [ ] Documentation is current and no Critical/High security issue is known.
- [ ] A review score of at least 8/10 and the project verification contract are satisfied.

## 13. Kill Criteria

Stop or redesign the MVP if two profiling iterations cannot reach 1 GB in under 30 seconds on the reference laptop, exact cardinality cannot be bounded with a clear exit, or the parser cannot achieve 99.9% success on the declared combined-format validation corpus. Do not add infrastructure to conceal a failed local CLI premise.

See `PROJECT_ARCHITECTURE.md` for the technical contract and `PRD.md` for acceptance behavior.
