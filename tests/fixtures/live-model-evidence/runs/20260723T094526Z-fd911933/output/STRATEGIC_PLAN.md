# Strategic Plan: Nginx Stream Analytics CLI

## 1. Product Idea

An installable Python 3.11 command-line tool for DevOps and SRE engineers that reads nginx access logs as a stream and immediately reports the ten busiest client IPs, the ten URLs producing the most 4xx/5xx responses, hourly request distribution, and the proportion of distinct User-Agent values. It accepts a file or standard input, renders colored terminal output by default, and offers stable JSON and CSV output for pipelines.

The MVP is local, stateless, open source, and intentionally narrow enough for a one-weekend delivery. The durable behavior contract is defined in [PRD.md](PRD.md); technical choices are defined in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Triage production incidents | Needs a fast summary without uploading sensitive logs | Streams local files and prints actionable rankings |
| DevOps engineer | Builds shell-based operational workflows | Ad hoc `awk` scripts are brittle and hard to reuse | Provides stable `--json` and `--csv` contracts |
| Platform engineer | Reviews traffic and error patterns | Full observability stacks are excessive for one-off analysis | Installs with pip and runs with no service or database |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive dashboards | Broader configuration and UI than a focused pipeline command | Four explicit SRE metrics with predictable machine formats |
| Logstash + Elastic + Kibana | Powerful ingestion, search, and dashboards | Infrastructure, storage, configuration, and operating cost | Zero-service local analysis with no retained log data |
| AWStats | Established historical web reporting | Batch/report orientation and dated operational workflow | Immediate stream-oriented CLI output |
| `grep`/`awk`/`sort` | Available nearly everywhere; composable | Parsing and quoting are fragile; repeated sorts can consume time and disk | Tested nginx parsing, bounded top-k output, and one-pass aggregation |

## 4. Unique Value Proposition

Get the nginx traffic and error signals an on-call engineer needs from a local stream in one command, without deploying or operating an observability stack.

## 5. Business Model

The project is open source and free. There is no monetization in the MVP; value is measured through adoption, correctness, speed, and reduced incident-triage effort. No paid service, telemetry, hosted tier, or commercial dependency is planned.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Required target; broadly available and productive for a weekend build |
| CLI | Click | Stable argument parsing, stdin/file support, and clear exit handling |
| Terminal UI | Rich | Readable colored tables with standard color-disable behavior |
| Domain models | `dataclasses` | Typed, dependency-free records and aggregates |
| Packaging | pip-compatible `pyproject.toml` | Standard local/virtual-environment installation |
| Testing | pytest | Fast unit, CLI, golden-output, and performance regression tests |

## 7. Timeline

| Period | Stage | Outcome |
|---|---|---|
| Friday evening | Packaging, parser contract, fixtures | Installable skeleton and representative nginx parsing |
| Saturday morning | Streaming aggregation | All four required metrics computed in one pass |
| Saturday afternoon | Text, JSON, CSV renderers | Human and pipeline interfaces stabilized |
| Sunday morning | Correctness and malformed-input handling | Unit, CLI, and golden-output coverage |
| Sunday afternoon | 1 GB benchmark, docs, release check | Evidence for the performance target and releasable package |

## 8. KPIs

| Metric | 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| Correctness against golden fixtures | 100% | 100% | 100% |
| 1 GB processing time on documented laptop baseline | <30 s | <25 s | <20 s |
| Peak memory on the 1 GB representative benchmark | <512 MB | <384 MB | <256 MB |
| Successful installs in clean Python 3.11 environments | 100% of release checks | 100% | 100% |
| Open correctness defects rated high severity | 0 | 0 | 0 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| High-cardinality IPs, URLs, or User-Agents increase memory | Medium | High | Measure cardinality and peak memory; document the exactness trade-off; keep only counters required by the contract |
| Real nginx formats differ from the expected combined format | High | High | Define supported format precisely, test escaping and IPv6, count malformed lines, and fail clearly in strict mode |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early; use compiled regex once, local bindings, batched I/O, and profile before optimizing |
| CSV representation of multiple report sections is ambiguous | Medium | Medium | Specify a normalized row schema with a `report` discriminator before implementation |
| Terminal color contaminates redirected output | Low | Medium | Enable color only for a TTY and honor `NO_COLOR`; never color JSON or CSV |
| Exact unique User-Agent tracking is expensive on adversarial input | Medium | Medium | Preserve exact semantics for MVP, measure peak memory, and reject approximate counting unless the PRD changes |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and pytest are open source |
| Hosting and storage | $0 | Local CLI; no server, cloud, or database |
| Development tools | $0 | Open-source toolchain |
| Delivery labor | One weekend | Approved time budget; no cash spend |
| Ongoing infrastructure | $0/month | Users process their own local/stdin logs |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream a file or stdin without loading the complete log | **Must** | Core performance and pipeline value proposition |
| Top-10 client IPs | **Must** | Required incident and traffic signal |
| Top-10 URLs by combined 4xx/5xx response count | **Must** | Required error hotspot signal |
| Hourly request distribution | **Must** | Required temporal signal |
| Unique User-Agent share | **Must** | Required client-diversity signal |
| Colored terminal report with TTY-safe behavior | **Must** | Required default interface |
| Stable `--json` output | **Must** | Required pipeline format |
| Stable `--csv` output | **Must** | Required pipeline format |
| Malformed-line accounting and strict mode | **Should** | Operational trust is important, but core valid-log analysis can exist first |
| Custom nginx `log_format` support | **Could** | Broadens adoption after the combined-format MVP |
| Approximate high-cardinality counting | **Could** | May reduce memory, but changes exactness semantics |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Explicitly outside the local stateless CLI product |

### RICE Scoring (Must + Should)

Confidence is represented as a decimal in the score: `Reach × Impact × Confidence / Effort`.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Streaming input and parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Top-10 IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top-10 error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly distribution | 8 | 3 | 95% | 0.20 | 114.0 |
| Unique User-Agent share | 8 | 3 | 85% | 0.30 | 68.0 |
| Colored terminal output | 8 | 3 | 90% | 0.40 | 54.0 |
| JSON output | 7 | 4 | 95% | 0.30 | 88.7 |
| CSV output | 6 | 4 | 90% | 0.35 | 61.7 |
| Malformed-line accounting and strict mode | 7 | 4 | 85% | 0.40 | 59.5 |

Implementation order in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) respects both dependency order and RICE value: the stream/parser foundation comes first even where small downstream aggregations have higher standalone scores.

## 12. Definition of Done

A feature is done when:

- [ ] Behavior and acceptance criteria are reflected in the PRD before code changes.
- [ ] Code runs on Python 3.11 and packaging builds without errors.
- [ ] Unit and CLI tests pass with at least 90% branch coverage for parser and aggregation modules.
- [ ] Golden JSON and CSV outputs pass byte-for-byte compatibility checks.
- [ ] The representative 1 GB benchmark completes under 30 seconds on the documented laptop baseline.
- [ ] Peak-memory evidence is recorded and any cardinality limits are documented.
- [ ] Review passes with no unresolved critical/high security or correctness issue.
- [ ] README and CLI help are current.

## 13. Strategic Kill Criteria

Stop or rescope the MVP if a correct one-pass implementation cannot meet 1 GB in 30 seconds on the agreed laptop baseline after profiling, if exact required metrics demand unacceptable memory on representative logs, or if supporting real nginx combined logs requires scope beyond one weekend. A kill decision must record benchmark hardware, fixture characteristics, and measured evidence.
