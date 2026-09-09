# Strategic Plan: Nginx Pulse

## 1. Idea

Nginx Pulse is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and emits an operational snapshot: top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the percentage of valid requests represented by unique User-Agent strings. It is designed for fast incident triage and pipeline use without a service, database, or paid dependency.

## 2. Target Audience

| Persona | Role | Pain | How Nginx Pulse helps |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a useful traffic/error summary before a larger observability stack is available | One local command produces bounded rankings and distributions |
| Platform engineer | Maintains web infrastructure | Needs repeatable log checks in shell pipelines and automation | Stable JSON/CSV schemas and explicit exit codes |
| Developer-operator | Owns a small service | Cannot justify operating an analytics server | A pip-installable, stateless CLI has no service cost or maintenance |

## 3. Competitive Analysis

| Alternative | What it does | Weakness for this use case | Nginx Pulse distinction |
|---|---|---|---|
| GoAccess | Rich real-time terminal and HTML nginx analytics | Broader UI and configuration surface than a four-metric pipeline tool | Narrow, deterministic output contracts in text, JSON, and CSV |
| Logstash + Elastic + Kibana | Centralized ingestion, indexing, search, and dashboards | Operational cost and setup are disproportionate for a local one-off analysis | Zero-service, zero-storage local execution |
| AWStats | Generates historical web analytics reports | Batch/report orientation and older workflow are less suitable for incident pipelines | Streaming stdin/file processing with machine-readable output |
| `grep`/`awk` pipelines | Ad hoc local text processing | Fragile parsing, inconsistent metrics, and poor portability | Tested parser and stable metric definitions in an installable package |

## 4. Unique Value Proposition

Get a reliable, pipeline-friendly nginx incident snapshot from a large local log in one command, without deploying or operating anything.

## 5. Business Model

The project is open source and free to use. There are no paid tiers, hosted services, telemetry, or unit-economics targets. Value is measured by adoption, correctness, speed, and reduced incident-triage time; contribution and maintenance remain community-driven within a $0 software and infrastructure budget.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Approved runtime with broad laptop availability |
| CLI | Click | Predictable commands, option validation, and exit handling |
| Terminal UI | Rich | Accessible colored tables with terminal capability handling |
| Domain models | Standard-library dataclasses | Explicit records with no runtime framework overhead |
| Streaming and serialization | Python standard library | Line iteration, counters, datetime handling, JSON, and CSV require no extra service |
| Distribution | pip-installable package | Familiar installation and isolated execution via `pipx` |
| Quality | pytest, Ruff, mypy | Fast automated behavior, style, and type checks during development |

## 7. Timeline

| Weekend block | Stage | Result |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable CLI parses the supported combined-log format and reports malformed lines |
| Saturday afternoon | Streaming aggregation | All four metrics are computed with bounded top-10 rankings |
| Sunday morning | Text, JSON, and CSV renderers | Human and pipeline outputs conform to documented schemas |
| Sunday afternoon | Performance, tests, documentation | 1 GB benchmark evidence, release checks, and user guide are complete |

## 8. KPIs

| Metric | 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| Correctness on the maintained fixture corpus | 100% | 100% | 100% |
| 1 GB processing time on the reference laptop | <30 s | <25 s | <20 s |
| Peak memory on the 1 GB bounded-cardinality benchmark | <256 MB | <192 MB | <160 MB |
| Successful CI runs on Python 3.11 | 100% release branches | 100% release branches | 100% release branches |
| Distinct external users or stars | 10 | 50 | 150 |

Performance targets apply to a documented reference laptop, warm local filesystem, default parsing, and output redirected to avoid terminal-rendering variance.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Custom nginx formats do not match the supported parser | Medium | High | State the supported format, fail visibly, test escaping and malformed lines, defer custom format definitions |
| Exact unique-cardinality tracking exhausts memory on hostile/high-cardinality input | Medium | High | Enforce a configurable documented ceiling and exit with code 4 instead of silently approximating |
| Python misses the 1 GB / 30 s target | Medium | High | Benchmark early, keep the hot loop allocation-light, profile before optimization |
| Colored output contaminates redirected pipelines | Low | Medium | Enable color only for an interactive terminal; JSON and CSV never contain ANSI escapes |
| Metric definitions drift across renderers | Low | High | Produce one result model, then render the same model in all formats with contract tests |
| Corrupt input yields misleading totals | Medium | Medium | Count malformed lines, send diagnostics to stderr, and distinguish partial results with exit code 3 |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and development tools are open source |
| Hosting and storage | $0 | Local-only execution; no server or database |
| Distribution | $0 | Source hosting and PyPI publication can use free tiers |
| Delivery labor | One weekend | Time-boxed implementation by one developer |
| Total cash budget | $0 | No paid services or infrastructure |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream a file or stdin and parse nginx combined access logs | Must | No analysis is possible without valid streaming input |
| Top 10 client IPs by valid request count | Must | Core incident-triage signal |
| Top 10 URLs by 4xx/5xx response count | Must | Core failure-hotspot signal |
| Hourly request distribution | Must | Required time-of-day traffic view |
| Unique User-Agent share | Must | Required client-diversity signal |
| Colored terminal report | Must | Default operator experience |
| JSON output | Must | Required pipeline integration |
| CSV output | Must | Required pipeline/spreadsheet integration |
| Gzip-compressed input | Should | Common log-rotation format, but decompression can be composed externally for MVP |
| Custom nginx `log_format` definitions | Could | Broadens compatibility but materially expands parser scope |
| Approximate unique-cardinality mode | Could | Handles extreme cardinality but changes exactness semantics |
| Authentication, database, HTTP API, server, cloud, Kubernetes | Won't | Explicitly excluded and contrary to the local stateless product |

### RICE Scoring (Must + Should)

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Stream and parse combined logs | 10 | 5 | 100% | 1.0 | 50.0 |
| Top IPs | 10 | 4 | 95% | 0.3 | 126.7 |
| Error URLs | 10 | 5 | 95% | 0.4 | 118.8 |
| Hourly distribution | 9 | 4 | 95% | 0.3 | 114.0 |
| Unique User-Agent share | 8 | 3 | 90% | 0.3 | 72.0 |
| Colored terminal output | 9 | 3 | 90% | 0.5 | 48.6 |
| JSON output | 8 | 4 | 95% | 0.3 | 101.3 |
| CSV output | 6 | 3 | 90% | 0.4 | 40.5 |
| Gzip input | 5 | 2 | 80% | 0.4 | 20.0 |

The parser is the dependency-bearing foundation and is implemented first despite lower standalone RICE than simple downstream counters. Within each dependency layer, implementation follows descending RICE score.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and failure modes match `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 code passes Ruff and mypy without errors.
- [ ] Unit tests pass and changed production modules maintain at least 90% branch coverage.
- [ ] Integration and golden-output tests pass for text, JSON, and CSV where applicable.
- [ ] A peer review scores at least 8/10; the later external adversarial architecture review remains a separate activity.
- [ ] User-facing documentation is updated.
- [ ] No known Critical or High security issue remains.
- [ ] The packaged CLI is manually verified from an isolated environment.
- [ ] The 1 GB performance target is evidenced when a change touches parsing, aggregation, or rendering performance.

## 13. Success and Stop Conditions

The MVP succeeds when all P0 acceptance criteria in `PRD.md` pass, the package installs on Python 3.11, and the reference 1 GB fixture completes within 30 seconds. Re-scope or stop if exact required metrics cannot fit the $0/local constraint, if supported-format correctness falls below 100% on the fixture corpus, or if two measured optimization passes cannot bring the reference run under 30 seconds.

Architecture and delivery details are defined in `PROJECT_ARCHITECTURE.md` and `IMPLEMENTATION_PLAN.md`.
