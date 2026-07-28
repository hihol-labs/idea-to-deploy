# Strategic Plan: nginx-log-top

## 1. Product Idea

`nginx-log-top` is a local, pip-installable Python 3.11 CLI that turns nginx combined access logs into four immediately useful operational views: top client IPs, top URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. It streams files or stdin and emits colored terminal tables, JSON, or CSV.

The product is for engineers who need a trustworthy first answer during incident triage or routine log inspection without provisioning a service. The MVP is open source, costs $0 to operate, and is deliverable in one weekend.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Diagnoses incidents under time pressure | Raw logs are too large to inspect manually; platform setup delays triage | One command returns high-signal distributions in under 30 seconds per 1 GB |
| DevOps engineer | Validates deployments and proxy behavior | Needs repeatable evidence that works locally and in CI/shell pipelines | Stable exit codes plus JSON/CSV on stdout |
| Platform developer | Investigates application-facing nginx errors | Generic grep pipelines are fragile and difficult to share | Tested combined-log parser and deterministic top lists |

## 3. Competitive Analysis

| Alternative | What it does | Weakness for this use case | Our difference |
|---|---|---|---|
| GoAccess | Rich real-time and static nginx analytics | Broader UI/configuration surface; may be more than a quick pipeline needs | Narrow four-metric contract, Python/pip install, first-class JSON/CSV |
| Logstash + Elastic + Kibana | Durable ingestion, search, dashboards | Significant setup, services, storage, and operational cost | Zero-service, stateless, local one-shot processing |
| AWStats | Historical web-log reports | Batch/report configuration and legacy workflow; not optimized for ad hoc shell use | Immediate streaming CLI and pipeline-safe schemas |
| `grep`/`awk`/`sort` | Universal text processing | Parsing, quoting, timestamps, ties, and portability become bespoke scripts | Domain parser, deterministic output, documented error behavior |

`nginx-log-top` does not try to replace durable observability platforms. It owns the gap between “open the file” and “deploy an analytics stack.”

## 4. Unique Value Proposition

Get a deterministic incident-ready nginx traffic and error summary from a gigabyte-scale file in one local command, with no service, database, or data upload.

## 5. Business and Distribution Model

The MVP is a free, open-source developer utility distributed as a Python wheel/source package. There is no monetization target, paid infrastructure, telemetry, or hosted tier.

| Economic item | Value |
|---|---:|
| Price | $0 |
| Runtime infrastructure | $0 |
| Marginal processing cost | $0 to the project; user’s local compute |
| Delivery effort | One developer-weekend |
| CAC/LTV | Not applicable to a non-commercial MVP |

Sustainability comes from low maintenance surface: two runtime dependencies, no hosted systems, and a stable narrow interface.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved stack; fast iteration and ubiquitous SRE environment |
| CLI | Click | Mature option validation, stdin/file ergonomics, predictable exit handling |
| Terminal UX | Rich | Accessible colored tables and correct TTY behavior |
| Domain model | Standard-library dataclasses | Typed, explicit records without framework overhead |
| Aggregation | `collections.Counter`, set, datetime | Exact one-pass metrics with no data platform |
| Packaging | `pyproject.toml`, pip | Standard install and console entry point |
| Tests | pytest, Click testing helpers | Fast unit/integration feedback |

## 7. Timeline

| Period | Stage | Result |
|---|---|---|
| Saturday morning | Package, contracts, parser | Installable CLI skeleton and validated combined-log events |
| Saturday afternoon | Streaming aggregation | All four metrics correct on fixtures |
| Sunday morning | Rich/JSON/CSV interfaces | Stable human and pipeline outputs with exit codes |
| Sunday afternoon | Tests, benchmark, documentation | Acceptance suite and recorded 1 GB performance evidence |

## 8. KPIs

| Metric | Launch / 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | <30 s | <25 s | <20 s if profiling justifies optimization |
| P0 automated test pass rate | 100% | 100% | 100% |
| Package test coverage | ≥90% | ≥90% | ≥90% |
| Unhandled tracebacks on malformed-input corpus | 0 | 0 | 0 |
| JSON/CSV schema-breaking releases | 0 | 0 | 0 |
| GitHub installs/stars | Observe only; no target | Baseline adoption | Decide whether continued investment is warranted |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Python parsing misses the 1 GB/30 s target | Medium | High | Benchmark the hot loop early, compile parser once, profile before adding complexity |
| Exact distinct User-Agents consumes excessive memory on adversarial data | Medium | Medium | Record peak RSS; document cardinality trade-off; gate an approximate sketch behind evidence |
| Real nginx formats differ from combined format | High | Medium | State the supported format precisely; fail/skip predictably; defer custom formats |
| Machine-readable output becomes unstable | Medium | High | Golden schema tests and semantic-versioning discipline |
| ANSI/progress contaminates pipelines | Low | High | Strict stdout/stderr separation and TTY-aware tests |
| Scope expands into dashboards or ingestion services | Medium | High | Explicit Won’t list and CLI-only architecture decision |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and hosting | $0 | Local process only |
| Database/cloud/Kubernetes | $0 | Explicitly excluded |
| Libraries | $0 | Open-source Click, Rich, and test tooling |
| Distribution | $0 | Local pip install; public index publication optional |
| Development | One weekend | Pre-approved delivery budget |
| Total cash budget | **$0** | No paid dependencies or services |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream a file or stdin without loading it in full | **Must** | Core scalability and shell-use promise |
| Parse nginx combined access logs with safe malformed-line handling | **Must** | Every metric depends on trustworthy events |
| Top client IPs | **Must** | Primary traffic-source triage view |
| Top 4xx/5xx URLs | **Must** | Primary error-localization view |
| Hourly request distribution | **Must** | Shows bursts and incident timing |
| Exact unique User-Agent share | **Must** | Required audience-diversity signal |
| Colored terminal report | **Must** | Default operator experience |
| Stable JSON and CSV outputs | **Must** | Required pipeline integration |
| Configurable `--top` and strict parsing | **Should** | Useful control, but fixed top-10 lenient reporting can launch |
| gzip input auto-detection | **Could** | Common convenience after the fixed contract is stable |
| Custom nginx `log_format` grammar | **Could** | Broadens adoption but exceeds weekend scope |
| Database/history, HTTP API, server, auth, cloud, Kubernetes | **Won’t** | Contradicts the local stateless product boundary |
| Live dashboard or tail-follow mode | **Won’t** | Different lifecycle and terminal interaction model |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence expressed as a fraction. Reach estimates first-month user coverage on a 1–10 scale; effort is person-days.

| Feature | Reach | Impact | Confidence | Effort (days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Combined-log parser and malformed-line policy | 10 | 5 | 90% | 0.50 | 90.0 |
| Streaming file/stdin ingestion | 10 | 5 | 90% | 0.50 | 90.0 |
| Top client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top 4xx/5xx URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly distribution | 9 | 4 | 90% | 0.25 | 129.6 |
| Unique User-Agent share | 8 | 3 | 90% | 0.20 | 108.0 |
| JSON and CSV outputs | 9 | 5 | 90% | 0.50 | 81.0 |
| Colored terminal report | 8 | 3 | 95% | 0.35 | 65.1 |
| `--top` and `--strict` controls | 6 | 2 | 85% | 0.25 | 40.8 |

Dependency order overrides raw RICE where necessary: ingestion and parsing precede the high-scoring aggregations. Within each dependency layer, implementation follows descending RICE.

## 12. Release Roadmap

| Release | Scope | Gate |
|---|---|---|
| MVP / weekend | All Must features, packaging, acceptance and performance evidence | Every P0 criterion passes; 1 GB target measured |
| 1.1 candidate | Should features and only evidence-backed performance work | No machine-schema regression |
| Later, conditional | gzip/custom formats | User demand and maintenance capacity justify scope |

## 13. Definition of Done

A feature is Done when:

- [ ] Behavior and acceptance criteria are recorded in `PRD.md`.
- [ ] Python 3.11 code compiles and package installation succeeds.
- [ ] Unit and applicable CLI integration tests pass with at least 90% package coverage.
- [ ] JSON/CSV compatibility tests pass when machine output is affected.
- [ ] Relevant performance evidence is recorded; the final build processes 1 GB in under 30 seconds on the reference laptop.
- [ ] Code review reaches at least 8/10 with no unresolved Critical/High finding.
- [ ] Documentation (`README.md`, architecture, PRD, and CLI help) matches behavior.
- [ ] Security review finds no known Critical/High issue.
- [ ] Local wheel installation is manually smoke-tested; staging deployment is not applicable to a local-only CLI.

## 14. Kill Criteria

Stop or materially re-scope the MVP if any is true after a focused profiling pass:

- the 1 GB fixture cannot complete within 30 seconds on the reference laptop;
- correct processing requires loading raw records or adding a database/service;
- combined-log ambiguity prevents reliable values for the four promised metrics;
- JSON and CSV cannot be kept deterministic without breaking normal shell behavior.

See `PROJECT_ARCHITECTURE.md` for the selected design and `PRD.md` for the replayable acceptance contract.
