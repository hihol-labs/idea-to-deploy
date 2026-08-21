# Strategic Plan: nginx-stream-stats

## 1. Product Idea

`nginx-stream-stats` is a local, installable Python 3.11 CLI for DevOps and SRE engineers. It reads an nginx access log once, keeps only aggregate state in memory, and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich terminal output is the default; JSON and CSV make the same result usable in pipelines.

The one-weekend MVP is deliberately narrow: a reliable diagnostic tool between ad-hoc shell commands and operational analytics platforms, with no service to deploy or data store to maintain.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates incidents and traffic anomalies | Needs an immediate local summary without shipping logs elsewhere | One command produces four operational views from a file or stdin |
| DevOps engineer | Validates proxies, releases, and rate-limit behavior | Repeated `awk` pipelines are hard to review and reproduce | Stable metrics, deterministic ordering, and documented exit codes |
| Platform engineer | Builds shell/CI observability workflows | Human-oriented tools are difficult to automate | Versioned JSON and rectangular CSV output on stdout |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Larger reporting surface; interactive UI is unnecessary for a four-metric pipeline | Smaller contract, native JSON/CSV, pip installation |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards, retention | Requires services, storage, configuration, and operational cost | No infrastructure or retained data; immediate local execution |
| AWStats | Established historical web analytics | Batch/report orientation and dated workflow; persistent history is beyond scope | Streaming one-pass incident-oriented output |
| `grep`/`awk`/`sort` | Ubiquitous and flexible | Easy to misquote fields, repeated scans, locale differences, fragile automation | nginx-aware parsing, one pass, consistent schemas and errors |

## 4. Unique Value Proposition

Get the four nginx traffic signals most useful during an incident from a local file or stdin in one reproducible command, without deploying or operating an analytics stack.

## 5. Business Model

The product is open source and free. There is no monetization in the MVP, no hosted tier, and no telemetry. The success model is adoption and operational usefulness: low setup time, trustworthy output, and repeat usage. Development uses existing contributor time; all selected runtime dependencies are open source.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Approved runtime with broad laptop availability |
| CLI | Click | Stable option parsing, help, validation, and exit handling |
| Terminal rendering | Rich | Accessible tables, automatic terminal capability handling, and color |
| Domain models | Standard-library dataclasses | Explicit contracts without a validation framework |
| Parsing/aggregation | Python standard library | One-pass processing with no external service |
| Packaging | `pyproject.toml` + pip | Standard installable console entry point |
| Testing | pytest | Fast unit, integration, golden-output, and performance tests |

## 7. Timeline

| Period | Work | Result |
|---|---|---|
| Saturday morning | Package skeleton, domain contracts, parser | Installable command and validated line parsing |
| Saturday afternoon | Streaming aggregation and metrics | All four calculations available in memory |
| Sunday morning | Terminal, JSON, and CSV renderers | Stable human and pipeline output contracts |
| Sunday afternoon | Integration, edge-case, and 1 GB performance verification | Release candidate meeting acceptance gates |

## 8. KPIs

| Metric | MVP / first month target | Three-month target | Measurement |
|---|---:|---:|---|
| Performance on a representative 1 GB log | Under 30 seconds | Maintain under 30 seconds | Timed local benchmark on the documented reference laptop |
| Valid-line accounting accuracy | 100% on fixtures | 100% on regression corpus | Parser and end-to-end tests |
| Metric correctness | 100% on golden fixtures | 100% on regression corpus | Independent expected aggregates |
| Clean-install success | 100% on Python 3.11 CI | 100% | Fresh virtual-environment smoke test |
| Pipeline contract stability | JSON/CSV schemas tested | No unversioned breaking changes | Golden-output tests and release notes |

Performance results are meaningful only when the reference laptop, Python version, fixture generation method, input location, and elapsed wall-clock timing are recorded.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Regex parsing rejects legitimate format variations | Medium | High | Support documented common/combined formats only in MVP; count skipped lines; add representative fixtures |
| High-cardinality User-Agent input exhausts memory | Medium | High | Enforce an explicit cardinality ceiling and exit with code 4 before uncontrolled growth |
| Distinct IP/URL counters exceed laptop memory | Low | High | Keep aggregate records minimal, catch allocation failures as runtime failures, and document capacity boundary |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark parser hot path early; avoid per-line object retention and unnecessary regex/copies |
| JSON, CSV, and terminal metrics diverge | Low | High | Render all formats from one immutable report model and golden-test equivalence |
| Ambiguous malformed-line behavior erodes trust | Medium | Medium | Publish valid/skipped counts and define the no-valid-input exit condition |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and pytest are open source |
| Hosting, database, API, cloud | $0 | None exists in the approved architecture |
| Distribution | $0 | Source distribution/wheel can be built and installed locally |
| Delivery labor | $0 cash budget | One weekend of contributor time is the approved constraint |
| Total | **$0** | No paid service or infrastructure dependency |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream common/combined nginx lines from a file or stdin | **Must** | Foundation for all product value |
| Top-10 client IP report | **Must** | Required incident signal |
| Top-10 4xx/5xx URL report | **Must** | Required error hot-spot signal |
| Hourly percentage distribution | **Must** | Required traffic-shape signal |
| Unique User-Agent share | **Must** | Required client-diversity signal |
| Rich colored terminal output | **Must** | Approved default user experience |
| JSON and CSV output | **Must** | Required pipeline interoperability |
| Deterministic exit codes and malformed-line accounting | **Must** | Required automation and trust contract |
| Pip-installable Python 3.11 package | **Must** | Required distribution contract |
| Optional color suppression | **Should** | Useful for terminals and captured logs without changing metrics |
| Compressed input | **Could** | Convenient but unnecessary because decompression can be piped to stdin |
| Additional nginx log formats | **Could** | Valuable after the common/combined contract is proven |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Explicitly excluded; they add state and operations without helping the local task |

### RICE Scoring (Must and Should)

Confidence is represented as a decimal in the formula `(Reach × Impact × Confidence) / Effort`; effort is person-days. Scores guide dependency-aware sequencing and are not usage measurements.

| Feature group | Reach | Impact | Confidence | Effort | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and input handling | 10 | 5 | 90% | 1.0 | 45.0 |
| Core four aggregations | 10 | 5 | 90% | 1.5 | 30.0 |
| Deterministic error/exit behavior | 9 | 4 | 90% | 0.5 | 64.8 |
| JSON and CSV renderers | 8 | 4 | 90% | 0.75 | 38.4 |
| Rich terminal renderer and color control | 9 | 3 | 90% | 0.75 | 32.4 |
| Packaging and pip entry point | 10 | 4 | 95% | 0.5 | 76.0 |
| Performance and release verification | 10 | 5 | 80% | 1.0 | 40.0 |

Implementation follows prerequisites as well as RICE: packaging/contracts first, parser before aggregation, and the shared report model before any renderer.

## 12. Definition of Done

A release is Done when:

- [ ] The package installs in a clean Python 3.11 virtual environment and exposes `nginx-stream-stats`.
- [ ] Unit tests cover valid common/combined lines, malformed lines, status classes, timestamps, quoting, and missing User-Agent values.
- [ ] Integration tests prove file and stdin inputs and equivalent terminal/JSON/CSV metrics.
- [ ] P0 acceptance criteria in `PRD.md` pass with no placeholder behavior.
- [ ] The documented reference-laptop benchmark processes a representative 1 GB log in under 30 seconds.
- [ ] The unique-cardinality ceiling stops safely with exit code 4.
- [ ] Code review, dependency/license review, and security checks report no unresolved critical/high issues.
- [ ] `PROJECT_ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, user-facing help, and release notes reflect actual behavior.

## 13. Kill and Re-scope Triggers

- Re-scope the parser or choose a faster implementation strategy if the optimized Python candidate cannot meet 1 GB under 30 seconds on the declared reference laptop.
- Do not ship if valid-line accounting or any of the four metrics differs from golden fixtures.
- Revisit exact unique cardinality if realistic logs repeatedly hit the safe ceiling; approximation requires a new product decision and explicit output semantics.
- Stop feature expansion if the one-weekend limit threatens the Must set; Could items are dropped first.

## 14. Document Map

The product contract is in `PRD.md`; the technical design and CLI schema are in `PROJECT_ARCHITECTURE.md`; work sequencing is in `IMPLEMENTATION_PLAN.md`; executable prompts are in `CLAUDE_CODE_GUIDE.md`; repository rules live in `CLAUDE.md`.
