# Strategic Plan: nginx-insights

## 1. Product Idea

`nginx-insights` is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the ten busiest client IPs, the ten URL paths producing the most 4xx/5xx responses, request distribution by hour, and the share of unique User-Agent values. It defaults to a readable Rich terminal report and emits stable JSON or CSV for pipelines.

The MVP is deliberately local and stateless: no service to operate, no credentials, and no retained log data. The delivery budget is $0 and the target is a focused one-weekend build.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE investigating an incident | Needs a useful traffic/error overview before a dashboard can be configured | One command produces the four required views from a file or stdin |
| Platform engineer | DevOps engineer maintaining hosts and CI jobs | Needs composable output without deploying an analytics stack | Stable `--json` and `--csv` contracts, meaningful exit codes |
| Service owner | Developer diagnosing nginx-fronted applications | Needs to identify noisy IPs and broken routes quickly | Exact top-10 rankings with deterministic tie-breaking |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | nginx-insights distinction |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI/configuration surface than a four-metric pipeline tool | Narrow zero-service command with predictable JSON/CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards, retention | Operational cost and setup are disproportionate to an ad-hoc local report | No server, database, credentials, or persistent state |
| AWStats | Established historical web reporting | Batch-oriented and dated presentation; persistent report workflow | Streams modern CLI output directly to terminal or pipeline |
| `grep`/`awk` pipelines | Ubiquitous and flexible | Fragile parsing, hard-to-review quoting, inconsistent output contracts | Tested nginx parsing and one stable cross-platform command |

## 4. Unique Value Proposition

Get four incident-ready nginx traffic signals from a gigabyte-scale log in one local command, with human-friendly output and pipeline-safe formats, without operating an analytics service.

## 5. Business and Distribution Model

The project is free and open source. There is no paid tier, hosted service, telemetry, or monetization in the MVP. Distribution is through a standard Python package installable with `pip`; value is measured by adoption and reliable use rather than revenue. Community support and contributions are optional follow-ons, not delivery dependencies.

## 6. Technology Stack

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required, broadly available, fast enough with line-by-line parsing |
| CLI | Click | Stable option validation, help, stdin/file conventions, exit handling |
| Terminal UI | Rich | Colored tables with automatic plain-text behavior when appropriate |
| Domain models | `dataclasses` | Lightweight typed records and report objects without framework overhead |
| Packaging | `pyproject.toml` + pip | Standard install and console-script entry point |
| Testing | pytest | Focused unit, integration, output-contract, and performance tests |

## 7. Timeline

| Window | Milestone | Result |
|---|---|---|
| Saturday morning | Runway and parser | Installable skeleton; valid, malformed, common, and combined lines classified |
| Saturday afternoon | Streaming aggregation | Four exact metrics and bounded cardinality guard work in one pass |
| Sunday morning | CLI and renderers | Terminal, JSON, and CSV contracts plus exit codes are integrated |
| Sunday afternoon | Verification and docs | Correctness suite, 1 GB benchmark, packaging smoke test, user documentation |

## 8. KPIs

| Metric | Launch target | Month 1 target | Month 3 target |
|---|---:|---:|---:|
| Processing time for 1 GB benchmark fixture | <30 s | <30 s | <25 s |
| Peak resident memory on cardinality-bounded fixture | <512 MiB | <512 MiB | <384 MiB |
| Correctness on golden fixtures | 100% | 100% | 100% |
| Successful clean-environment pip install | 100% | 100% | 100% |
| Unhandled crashes on malformed-input tests | 0 | 0 | 0 |

Performance is measured on a documented laptop baseline (Python 3.11, local SSD, at least four modern CPU cores) with output redirected so terminal rendering does not distort parser throughput.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported contract | Medium | High | State supported common/combined formats; test escapes, IPv6, dashes, malformed lines; reject unsupported formats clearly |
| Exact unique values exhaust memory on hostile/high-cardinality logs | Medium | High | Configurable hard cap, fail closed with exit code 4, and no partial output represented as complete |
| Python misses the 1 GB/30 s target | Medium | High | Avoid per-line regex recompilation and full-file reads; profile representative data before polish |
| CSV multi-report shape surprises pipeline users | Medium | Medium | One documented long-form schema with golden contract tests |
| Color/control characters leak into redirected output | Low | Medium | Color only for interactive terminal mode; never color JSON/CSV |
| Malformed lines silently skew results | Medium | High | Count invalid lines, expose the count, and use the documented parse-failure exit policy |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and pytest are open source |
| Hosting/infrastructure | $0 | Local CLI only |
| Database/API services | $0 | Explicitly absent |
| Distribution | $0 | Build locally and publish through free package tooling if desired |
| Labor | One weekend | Owner-provided time; no cash budget |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream a file or stdin without loading it in full | **Must** | Core performance and pipeline value |
| Parse nginx common/combined access lines and account for malformed lines | **Must** | Every metric depends on trustworthy records |
| Top-10 client IPs | **Must** | Required incident signal |
| Top-10 URL paths by 4xx/5xx count | **Must** | Required error signal |
| Hourly request distribution as percentages | **Must** | Required traffic-shape signal |
| Unique User-Agent share | **Must** | Required client-diversity signal |
| Rich terminal, JSON, and CSV renderers | **Must** | Required human and pipeline interfaces |
| Cardinality limit and complete `0/1/2/3/4` exit contract | **Must** | Prevents misleading output and uncontrolled memory use |
| Gzip input | **Should** | Common operational convenience, but decompression can be piped for MVP |
| Optional top-N value | **Could** | Useful generalization after the fixed top-10 contract is stable |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the local, stateless product boundary |

### RICE Scoring (Must and Should)

Scores use `(Reach × Impact × Confidence) / Effort`; confidence is represented as a decimal in the calculation.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin | 10 | 5 | 95% | 0.5 | 95.0 |
| Common/combined parsing and malformed accounting | 10 | 5 | 90% | 0.75 | 60.0 |
| Top-10 IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly percentages | 8 | 4 | 95% | 0.25 | 121.6 |
| Unique User-Agent share | 7 | 3 | 85% | 0.35 | 51.0 |
| Three output renderers | 10 | 5 | 85% | 1.0 | 42.5 |
| Cardinality and exit contract | 9 | 5 | 90% | 0.5 | 81.0 |
| Gzip input | 5 | 2 | 70% | 0.4 | 17.5 |

Dependencies override raw score where necessary: input parsing precedes every aggregator, and the report model precedes renderers.

## 12. Definition of Done

A feature is done when:

- [ ] Behavior and acceptance criteria in `PRD.md` are implemented without expanding scope.
- [ ] Python 3.11 type/static checks selected by the project pass.
- [ ] Unit and integration tests pass with at least 90% line coverage for first-party modules.
- [ ] Golden terminal, JSON, CSV, and exit-code contract tests pass where applicable.
- [ ] The 1 GB performance oracle passes on the documented laptop baseline.
- [ ] A code review is accepted and no known Critical/High security issue remains.
- [ ] `README.md`, `PROJECT_ARCHITECTURE.md`, and CLI help are consistent.
- [ ] A clean virtual environment can install the wheel and run the smoke test.

## 13. Kill Criteria

Re-scope or stop the MVP if representative profiling shows the required 1 GB input cannot finish within 30 seconds on the baseline laptop without abandoning Python 3.11, or if exact required metrics cannot be produced within a defensible memory cap. Do not hide either failure with sampling or approximate results unless the PRD is explicitly revised.
