# Strategic Plan: nginx-stream-report

## 1. Product Idea

`nginx-stream-report` is a local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs once, incrementally, and reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, the percentage of valid requests in each hour of day, and the share of unique User-Agent values. It is designed for fast incident triage and pipeline-friendly use without operating a service or importing data into a database.

The MVP is a zero-cost open-source utility deliverable in one weekend. Its product specification is in [PRD.md](PRD.md), its technical design is in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), and its delivery sequence is in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Diagnoses production incidents | Needs immediate traffic/error concentration signals without preparing a stack | Runs one local command and receives bounded, readable summaries |
| DevOps engineer | Checks deployments and proxies | Shell one-liners are brittle and hard to reuse in automation | Uses stable JSON or CSV contracts in CI and scripts |
| Platform engineer | Handles large archived logs | GUI/import tools require setup, disk, and services | Processes a 1 GB log as a stateless stream on a laptop |

## 3. Problem and Opportunity

The gap is between ad hoc `grep`/`awk`, which is available but fragile, and full analytics platforms, which are powerful but expensive to install and operate. A purpose-built local CLI can make the four most common first-pass nginx questions repeatable, fast, and explainable. The opportunity is intentionally narrow: provide a dependable first look, then let users escalate to larger tools when they need historical correlation, dashboards, or search.

## 4. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Fast, mature, interactive terminal/HTML reports | Broader UI and configuration surface than the four required questions; machine-output workflow is not the primary experience | Narrow fixed report, explicit JSON/CSV schemas, Python/pip distribution |
| Logstash + Elasticsearch + Kibana | Rich ingestion, search, dashboards, and retention | Multi-service setup, resource cost, persistent storage, and operational burden | No services or persistence; immediate local result |
| AWStats | Established historical web analytics | Report-generation model and legacy configuration are excessive for incident-time streaming analysis | Single pass from file or stdin with modern pipeline outputs |
| `grep` / `awk` / `sort` / `uniq` | Already installed, composable, zero incremental cost | Locale/quoting/parsing errors, repeated scans, non-portable scripts, no shared output contract | Tested nginx parsing and all four metrics in one pass |

## 5. Unique Value Proposition

Answer the first four nginx traffic questions from a gigabyte-scale log in one local, reproducible command—without deploying, storing, or uploading anything.

## 6. Business and Licensing Model

The project is free and open source. There are no paid tiers, hosted services, telemetry, or monetization requirements in the MVP. Value is measured by adoption, repeat usage, correctness, and operational time saved rather than revenue, CAC, or LTV. A permissive license such as MIT is suitable, subject to the maintainer’s final repository-level choice.

## 7. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | User requirement; widely available to operators |
| CLI | Click | Stable argument parsing, help, and usage-error behavior |
| Terminal rendering | Rich | Colored, readable tables with automatic TTY behavior |
| Domain records | `dataclasses` | Typed records without runtime framework overhead |
| Streaming aggregation | Python standard library | Counters, buffered I/O, JSON, CSV, and datetime are sufficient |
| Packaging | `pyproject.toml`, pip | Standard install and console-script distribution |
| Quality tooling | pytest, Ruff, mypy | Fast tests, linting, and type checking; development-only dependencies |

## 8. Timeline

| Timebox | Work | Exit result |
|---|---|---|
| Saturday morning | Package skeleton, CLI contract, parser fixtures | Installable command and deterministic parse behavior |
| Saturday afternoon | Streaming aggregator and cardinality guard | All four metrics computed in one pass |
| Sunday morning | Rich, JSON, and CSV renderers | Human and pipeline output contracts complete |
| Sunday afternoon | Tests, 1 GB benchmark, docs, release dry run | Acceptance evidence and releasable package candidate |

## 9. KPIs

| Metric | Launch target | 1-month target | Measurement |
|---|---:|---:|---|
| Performance | 1 GB in under 30 seconds | Maintain target across releases | Published benchmark protocol on reference laptop |
| Parser correctness | 100% of canonical fixtures | No known P0 parsing defects | Unit and golden-output suite |
| Peak memory | Bounded by aggregation/cardinality guard | No unexplained growth with line count | Benchmark peak RSS |
| Pipeline stability | JSON/CSV golden tests pass | Zero unannounced schema breaks | CI compatibility tests |
| Time to first report | Under 30 seconds after installation | Under 2 minutes from discovery | Quick-start usability check |

The performance target is a product acceptance target, not a claim about an implementation that does not yet exist. The benchmark must record hardware, Python version, input hash/shape, warm/cold cache state, wall time, and peak RSS.

## 10. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Regex parsing is too slow for 1 GB / 30 s | Medium | High | Benchmark early; compile parser once; avoid per-line datetime objects where possible; profile before optimizing |
| Real nginx formats differ from common/combined | High | Medium | Explicit `--format`; strict versus skip policy; actionable malformed-line count; custom formats deferred |
| Unique User-Agent set exhausts memory | Medium | High | Configurable hard cardinality limit; terminate with exit code 4 before uncontrolled growth |
| Pipeline consumers depend on unstable output | Medium | High | Versioned documented JSON/CSV schemas and golden tests |
| Terminal colors leak into redirected output | Low | Medium | Rich auto-detection and explicit `--color/--no-color` control |
| Scope expands into a monitoring platform | Medium | Medium | Maintain Won't list: no database, API, server, cloud, Kubernetes, dashboards, or auth |

## 11. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python and approved dependencies are open source |
| Hosting and infrastructure | $0 | Local CLI; no hosted component |
| Development tooling | $0 | Open-source local toolchain |
| Delivery labor | One weekend | Fixed time budget; not a cash expense in this plan |
| Total cash budget | **$0** | Required constraint |

## Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream common/combined nginx logs from files and stdin | **Must** | Core input and statelessness contract |
| Top 10 client IPs | **Must** | Required incident-triage metric |
| Top 10 URLs with 4xx/5xx responses | **Must** | Required error-concentration metric |
| Hourly request distribution as percentages | **Must** | Required traffic-shape metric |
| Unique User-Agent share with cardinality guard | **Must** | Required metric; guard preserves bounded failure behavior |
| Colored terminal report | **Must** | Required default experience |
| Stable `--json` and `--csv` outputs | **Must** | Required pipeline integration |
| Strict malformed-line mode and parse summary | **Should** | Important for auditability but default can safely skip and count |
| Configurable top-N and color behavior | **Should** | Useful operational control without changing core value |
| Direct `.gz` input | **Could** | Convenient but shell decompression can cover MVP |
| Custom nginx `log_format` grammar | **Could** | Broadens compatibility but threatens weekend scope |
| Database, HTTP API, server, cloud, Kubernetes, or authentication | **Won't** | Explicitly out of scope and contrary to local stateless operation |

### RICE Scoring for Must and Should Features

Scores use `(Reach × Impact × Confidence) / Effort`, where confidence is a decimal and effort is person-days. Reach is relative first-month coverage on a 1–10 scale.

| Feature | Reach | Impact | Confidence | Effort | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming common/combined input | 10 | 5 | 90% | 0.75 | 60.0 |
| Top client IPs | 10 | 4 | 95% | 0.25 | 152.0 |
| Top error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly percentage distribution | 9 | 4 | 95% | 0.25 | 136.8 |
| Unique User-Agent share and guard | 8 | 4 | 85% | 0.40 | 68.0 |
| Colored terminal report | 9 | 3 | 90% | 0.40 | 60.8 |
| JSON and CSV outputs | 8 | 4 | 90% | 0.55 | 52.4 |
| Strict parsing and summary | 7 | 3 | 80% | 0.30 | 56.0 |
| Configurable top-N/color | 5 | 2 | 90% | 0.20 | 45.0 |

Dependency order supersedes raw score where a report depends on parsing and aggregation. Within each dependency layer, the implementation plan uses descending product value.

## Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Python 3.11 code is formatted, linted, and type-checked without errors.
- [ ] Unit and integration tests pass with at least 90% line coverage for the parsing, aggregation, and rendering packages.
- [ ] JSON and CSV contract changes have golden-output tests and documentation.
- [ ] The current exact candidate passes the project’s Idea to Deploy verification contract and risk-tier adjudication.
- [ ] No known Critical or High security defects remain.
- [ ] The 1 GB benchmark records wall time and peak RSS and meets the under-30-second target on the declared reference laptop.
- [ ] README and implementation status are updated.
- [ ] Installation into a clean Python 3.11 virtual environment and the documented smoke commands succeed.

## 14. Kill and Pivot Criteria

- Stop the weekend release if correct common/combined parsing cannot meet the 1 GB / 30 s target after profiling and one bounded optimization pass.
- Do not ship pipeline modes if their schemas cannot be made deterministic across terminal and redirected execution.
- Pivot to recommending GoAccess when users primarily require interactive exploration or HTML dashboards.
- Escalate to Elastic or another persistent system when the requirement becomes cross-file historical search, correlation, or retention.
