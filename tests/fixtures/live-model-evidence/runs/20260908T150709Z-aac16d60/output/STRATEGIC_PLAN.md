# Strategic Plan: nginx-insights

## 1. Product Idea

`nginx-insights` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It streams nginx access logs from files or standard input and emits four operational summaries without retaining log data: top client IPs, top URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Human-readable colored terminal output is the default; JSON and CSV support automation.

The MVP is intentionally narrow: no service to operate, no credentials, no database, and no network dependency. It should process a 1 GB log in under 30 seconds on a representative laptop while using memory that does not grow with the number of log lines, except for explicitly bounded aggregation keys.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Triage production incidents | Needs a useful traffic/error picture before a dashboard query is ready | One local command returns ranked IPs, failing URLs, time shape, and UA diversity |
| DevOps engineer | Operates nginx fleets and CI pipelines | Existing shell pipelines are fragile and hard to serialize | Stable terminal, JSON, and CSV contracts work with files or stdin |
| Platform engineer | Creates team diagnostics | Full observability stacks are excessive for ad hoc or restricted environments | Pip-installable, offline, stateless processing with no service dependencies |

## 3. Competitive Analysis

| Alternative | What it does | Weakness for this use case | nginx-insights distinction |
|---|---|---|---|
| GoAccess | Rich terminal and HTML nginx analytics | Broader UI and reporting surface than the four required incident summaries | Minimal pipeline-friendly contract and Python packaging |
| Logstash + Elasticsearch + Kibana | Durable ingestion, search, and dashboards | Operational cost, storage, setup time, and architecture are disproportionate | Zero-service, zero-storage, single-command analysis |
| AWStats | Historical web analytics from logs | Batch/report orientation and dated operational workflow | Fast streaming summaries for current DevOps/SRE work |
| grep/awk/sort | Composable local text processing | Parsing is brittle; multiple passes and sort stages can be slow and inconsistent | One parser, one pass, bounded policies, stable schemas and exit codes |

## 4. Unique Value Proposition

Get the four nginx signals most useful during local triage from a gigabyte-scale log in one pip-installed command, with no server or stored data and with terminal, JSON, and CSV output contracts.

## 5. Business Model

The project is free and open source. The MVP has no monetization, paid tier, telemetry, hosted component, CAC, or revenue target. Value is measured by adoption, trustworthy output, and reduced time-to-first-signal. Any future sponsorship or support model is outside the MVP and must not compromise the $0 runtime requirement.

## 6. Technology Stack

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Required platform; mature file and text streaming support |
| CLI | Click | Predictable option validation, help, and exit behavior |
| Terminal presentation | Rich | Readable ranked tables and automatic color/TTY handling |
| Domain models | Standard-library dataclasses | Typed records without validation-framework overhead |
| Packaging | `pyproject.toml` and pip | Standard local installation and console entry point |
| Tests | pytest | Fast unit, integration, CLI, and performance regression coverage |

## 7. Timeline

| Work block | Outcome | Estimate |
|---|---|---:|
| Saturday morning | Package skeleton, contracts, parser fixtures | 3 hours |
| Saturday afternoon | Streaming aggregation and cardinality policy | 4 hours |
| Sunday morning | Terminal, JSON, CSV renderers and CLI | 4 hours |
| Sunday afternoon | Tests, 1 GB benchmark, documentation, packaging check | 5 hours |

One-weekend delivery budget: approximately 16 engineering hours.

## 8. KPIs

| Metric | Release target | First-month target | Measurement |
|---|---:|---:|---|
| Performance | 1 GB in <30 s | Maintain across releases | Median of 3 local benchmark runs on the documented laptop profile |
| Correctness | 100% golden fixtures pass | No open P0 correctness defects | Automated fixture comparison |
| Invalid-line behavior | Deterministic skip/count policy | No unexplained parser aborts | Integration tests and emitted metadata |
| Pipeline compatibility | JSON and CSV parse successfully | No schema-breaking patch release | Schema/CSV tests |
| Time to first use | <30 seconds after package availability | 10 successful independent installs | Clean-environment install check |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Unbounded unique keys exhaust memory | Medium | High | Explicit unique-cardinality cap, fail closed with exit code 4, document sizing |
| nginx format variation causes invalid records | High | Medium | Support declared common/combined formats only in MVP, count skipped lines, use golden fixtures |
| Python misses the 1 GB/30 s target | Medium | High | One-pass byte-oriented hot path, avoid per-line Rich work, benchmark before release |
| URL query strings create misleading cardinality | Medium | Medium | Rank normalized URL paths by default and document normalization |
| Locale/timezone ambiguity distorts hourly buckets | Low | Medium | Parse nginx numeric offsets and bucket by the timestamp's recorded offset |
| Machine-output changes break pipelines | Medium | High | Versioned JSON schema, fixed CSV columns, golden contract tests |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and hosting | $0 | Local CLI; no hosted component |
| Database/cloud/Kubernetes | $0 | Explicitly out of scope |
| Dependencies | $0 | Open-source Python ecosystem |
| Development tooling | $0 | Open-source toolchain and existing laptop |
| Labor | One weekend | Approximately 16 hours; no cash budget allocated |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream logs from files and stdin | Must | The product has no value without bounded one-pass ingestion |
| Top-10 client IPs | Must | Core incident-triage signal |
| Top-10 URL paths by combined 4xx/5xx count | Must | Core error-localization signal |
| Hourly request distribution | Must | Required traffic-shape signal |
| Unique User-Agent share with bounded cardinality | Must | Required diversity signal and memory-safety boundary |
| Colored terminal report | Must | Required default experience |
| JSON output | Must | Required pipeline output |
| CSV output | Must | Required pipeline output |
| Invalid-line summary | Should | Operators need to judge report completeness |
| Gzip input | Could | Convenient, but shell decompression can cover the MVP |
| Custom nginx `log_format` parser | Could | Broadens compatibility but risks the weekend scope |
| Authentication, database, HTTP API, server, cloud, Kubernetes | Won't | Contradicts the local stateless product boundary |

### RICE Scoring (Must + Should)

| Feature | Reach | Impact | Confidence | Effort (days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Stream logs from files and stdin | 10 | 5 | 100% | 0.5 | 100.0 |
| Top-10 client IPs | 10 | 4 | 95% | 0.25 | 152.0 |
| Top-10 error URL paths | 10 | 5 | 95% | 0.4 | 118.8 |
| Hourly request distribution | 9 | 4 | 95% | 0.3 | 114.0 |
| Colored terminal report | 9 | 3 | 90% | 0.3 | 81.0 |
| JSON output | 8 | 4 | 95% | 0.3 | 101.3 |
| CSV output | 7 | 3 | 90% | 0.3 | 63.0 |
| Unique User-Agent share with bounded cardinality | 8 | 3 | 85% | 0.5 | 40.8 |
| Invalid-line summary | 8 | 3 | 90% | 0.25 | 86.4 |

Implementation order may adjust the descending scores for hard dependencies: ingestion and parsing precede every aggregation even where an individual report has a higher numerical score.

## 12. Success and Kill Criteria

Release the MVP only when all P0 acceptance criteria in `PRD.md` pass, the packaging smoke test succeeds on Python 3.11, and the documented benchmark meets the performance target. Re-scope or stop the project if a correct single-process implementation cannot process 1 GB within 30 seconds on the reference laptop after two measured optimization passes, or if exact common/combined log parsing cannot be made deterministic within the weekend.

## Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Code is written for Python 3.11 and static checks pass.
- [ ] Unit tests pass with at least 90% line coverage for parser, aggregation, and serialization modules.
- [ ] Integration and CLI contract tests pass where applicable.
- [ ] A review is accepted with no unresolved critical or high-severity issue.
- [ ] User documentation and machine-output schemas are updated.
- [ ] The 1 GB benchmark is recorded when the hot path changes.
- [ ] No network service, persistent data store, authentication, cloud, or Kubernetes dependency has been introduced.

## 13. Document Map

The normative product behavior is in `PRD.md`; system boundaries and interfaces are in `PROJECT_ARCHITECTURE.md`; delivery sequencing is in `IMPLEMENTATION_PLAN.md`; implementation-session prompts are in `CLAUDE_CODE_GUIDE.md`; and persistent repository rules are in `CLAUDE.md`.
