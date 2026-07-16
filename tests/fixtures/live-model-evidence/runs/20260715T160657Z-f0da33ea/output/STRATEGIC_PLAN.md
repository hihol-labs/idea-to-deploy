# Strategic Plan: Nginx Stream Analytics CLI

## 1. Idea Overview

Nginx Stream Analytics CLI is a local, pip-installable Python 3.11 tool for DevOps and SRE engineers. It reads nginx access logs from a file or standard input in one pass and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent strings. It emits colored terminal text by default and stable JSON or CSV for pipelines.

The product solves the gap between ad hoc shell commands and operationally heavy analytics platforms: an engineer can inspect a large log locally without provisioning storage or a service. The MVP is open source, costs $0 to operate, and is scoped to one weekend.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a quick traffic/error picture without uploading sensitive logs | Runs one local command and gets bounded summaries |
| Platform engineer | DevOps engineer automating diagnostics | Shell pipelines are brittle and hard to parse consistently | Uses versioned `--json` or `--csv` output |
| Service owner | Backend engineer investigating nginx failures | Full observability stacks are unavailable or too slow to configure | Gets URL error ranking and time distribution from an existing log |

## 3. Competitive Analysis

| Alternative | What it does | Weakness for this use case | Product distinction |
|---|---|---|---|
| GoAccess | Rich real-time terminal/HTML web-log analytics | More features and configuration than a four-metric pipeline tool needs | Smaller, explicit output contract with native JSON/CSV modes |
| Logstash + Elastic + Kibana | Ingests, stores, searches, and visualizes logs at scale | Requires services, storage, configuration, and ongoing operations | Zero-service, local, stateless execution |
| AWStats | Produces broad historical web analytics reports | Batch/report-oriented and dated workflow for incident pipelines | Stream-first CLI designed for immediate diagnostics |
| `grep`/`awk`/`sort` | Composable local text processing | Quoted nginx fields and multiple metrics make scripts fragile; sorting can use large temporary storage | Tested parsing and all required aggregates in one pass |

## 4. Unique Value Proposition

Get the four incident-relevant nginx traffic summaries from a gigabyte log in one local, pipeline-friendly command—without a database, service, or cloud bill.

## 5. Business Model

The project is free and open source. There are no paid tiers, CAC, or revenue targets for the MVP. Value is measured through adoption, reliability, and time saved during diagnostics; community contributions can fund maintenance indirectly. The zero-budget constraint excludes paid infrastructure and proprietary dependencies.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable runtime with adequate streaming I/O |
| CLI | Click | Stable option parsing, stdin/file arguments, exit handling |
| Terminal UI | Rich | Colored, readable tables with terminal capability detection |
| Domain model | `dataclasses` | Typed records and aggregates without framework overhead |
| Packaging | `pyproject.toml` + pip | Standard install and console-script distribution |
| Testing/quality | pytest, Ruff, mypy | Fast local correctness and static checks with no runtime services |

See [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for component boundaries.

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Packaging, contracts, parser | Installable skeleton and correct combined-log parsing |
| Saturday afternoon | Streaming aggregation | All four metrics computed in one pass |
| Sunday morning | Text, JSON, CSV renderers | Human and pipeline outputs with stable schemas |
| Sunday afternoon | Tests, benchmark, docs | Release candidate proven against correctness and 1 GB target |

Delivery follows the nine steps in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## 8. KPIs

| Metric | 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| Valid-log parse accuracy in fixtures | 100% | 100% | 100% |
| 1 GB benchmark on reference laptop | <30 s | <30 s | <25 s |
| Peak memory on 1 GB benchmark | <250 MB | <200 MB | <150 MB |
| Pipeline schema regressions | 0 | 0 | 0 |
| GitHub stars (directional adoption) | 10 | 50 | 150 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the combined format | High | High | Define combined format as MVP contract, count malformed lines, fail only in strict mode, document future format templates |
| Exact URL/User-Agent maps grow with input cardinality | Medium | High | Document O(unique keys) memory, benchmark adversarial data, provide a clear memory guardrail and future approximate mode |
| Python misses the 1 GB/30 s target | Medium | High | Avoid per-line regex backtracking and retained records; benchmark early; profile before optimizing |
| CSV representation of multiple report sections is misunderstood | Medium | Medium | Define a normalized row schema with a `metric` discriminator |
| Terminal color pollutes redirected output | Low | Medium | Disable color automatically when not a TTY and for JSON/CSV |
| Corrupt lines silently skew results | Medium | High | Report parsed/skipped counts on stderr in text mode and structured metadata in pipeline modes |

## 10. Budget

| Item | Monthly cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python and dependencies are open source |
| Hosting/database | $0 | Local CLI has neither |
| CI | $0 | Use a free open-source allowance or local checks |
| Distribution | $0 | Source repository and PyPI publishing are free |
| Labor | One weekend | Approved delivery constraint; no cash budget assigned |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream file/stdin without retaining requests | **Must** | Core value and large-file feasibility |
| Top 10 IPs | **Must** | Required traffic-source signal |
| Top 10 4xx/5xx URLs | **Must** | Required failure signal |
| Hourly request distribution | **Must** | Required temporal signal |
| Unique User-Agent share | **Must** | Required client-diversity signal |
| Colored terminal report | **Must** | Approved default experience |
| Stable JSON output | **Must** | Required pipeline integration |
| Stable CSV output | **Must** | Required pipeline integration |
| Malformed-line accounting and deterministic ties | **Should** | Makes automation trustworthy, but core metrics can exist first |
| Configurable nginx `log_format` | **Could** | Broadens compatibility after the combined-format MVP |
| Approximate bounded-memory cardinality/top-k | **Could** | Helps adversarial high-cardinality logs if exact maps become limiting |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Explicitly excluded; they contradict a local stateless CLI |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / effort`; confidence is decimal in the calculation.

| Feature | Reach | Impact | Confidence | Effort (days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming file/stdin foundation | 10 | 5 | 95% | 0.50 | 95.0 |
| Top 10 IPs | 10 | 4 | 95% | 0.25 | 152.0 |
| Top 10 error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly distribution | 9 | 4 | 95% | 0.25 | 136.8 |
| Unique User-Agent share | 8 | 3 | 90% | 0.25 | 86.4 |
| Colored terminal report | 9 | 3 | 90% | 0.40 | 60.8 |
| JSON output | 8 | 5 | 95% | 0.35 | 108.6 |
| CSV output | 7 | 4 | 90% | 0.35 | 72.0 |
| Malformed-line accounting and deterministic ties | 8 | 5 | 90% | 0.40 | 90.0 |

Dependency ordering overrides raw RICE where necessary: streaming and parsing precede every metric; the highest-value metrics then precede renderers. P0/P1 mapping is specified in [PRD.md](PRD.md).

## 12. Definition of Done

A feature is Done when:

- [ ] Behavior and output contracts in the PRD are implemented.
- [ ] Unit tests pass with at least 90% branch coverage for parser, aggregation, and renderers.
- [ ] CLI integration tests pass for file input, stdin, text, JSON, CSV, and invalid input.
- [ ] Ruff and mypy pass.
- [ ] Review passes with no unresolved critical or high issues.
- [ ] README and schemas are current.
- [ ] No known critical/high security issue exists.
- [ ] The packaged CLI is manually verified locally; staging is not applicable to a local-only CLI.
- [ ] The reference 1 GB benchmark completes in under 30 seconds with recorded hardware and peak memory.

## 13. Kill Criteria

Stop or redesign the MVP if correct combined-log parsing cannot reach 1 GB in 30 seconds on the named reference laptop after profiling, if exact aggregation exceeds 250 MB on the benchmark corpus, or if stable JSON/CSV semantics cannot represent all four required reports without ambiguity. The fallback is a narrower format contract or an explicitly approximate mode, not a hidden database or service.
