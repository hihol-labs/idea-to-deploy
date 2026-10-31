# Strategic Plan: nginx-log-report

## 1. Product Idea

`nginx-log-report` is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx combined access logs as a stream and produces an operational snapshot: top-10 client IPs, top-10 URLs with 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. It is designed for fast incident triage and repeatable pipeline use without uploading logs or operating infrastructure.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Diagnoses production incidents | Needs a useful view before a dashboard or query is ready | One command, streaming aggregation, terminal summary |
| DevOps engineer | Audits nginx behavior on a laptop or jump host | Log files are large and may contain sensitive data | Local-only processing with bounded memory and no persistence |
| Automation author | Builds shell and CI pipelines | Colored prose is hard to parse reliably | Stable `--json` and `--csv` output contracts |

## 3. Competitive Analysis

| Alternative | Strength | Limitation for this use case | Our distinction |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI and configuration surface than a focused pipeline tool | Small, predictable four-metric report with JSON/CSV contracts |
| Logstash + Elastic + Kibana | Powerful indexing, search, and dashboards | Requires services, storage, setup, and ongoing operations | Zero-service, stateless, local execution |
| AWStats | Established historical reporting | Oriented toward generated historical reports and configuration | Immediate streaming triage with modern pipeline formats |
| `grep` / `awk` / `sort` | Ubiquitous and composable | Complex quoting, repeated parsing, locale differences, and high-memory sorts | Tested parser and stable semantics in one installable command |

## 4. Unique Value Proposition

Turn a large nginx access log into four incident-ready metrics in one local command, without a database, server, or paid service.

## 5. Business and Distribution Model

The project is open source and free to use. Distribution is through a standard Python package installable by `pip`; there is no hosted tier or monetization in the one-weekend MVP. Success is adoption, reproducibility, and operator time saved rather than revenue.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Required, portable, fast enough with streaming I/O |
| CLI | Click | Clear option validation and conventional exit behavior |
| Terminal output | Rich | Colored, readable tables with automatic no-color handling |
| Domain records | `dataclasses` | Typed data boundaries without validation-framework overhead |
| Packaging | `pyproject.toml` + pip | Standard installation and console entry point |
| Tests | pytest | Fast unit, integration, and performance-oriented checks |

## 7. Timeline

| Session | Focus | Result |
|---|---|---|
| Saturday morning | Package skeleton, parser, fixtures | Installable CLI and verified combined-log parsing |
| Saturday afternoon | Streaming aggregation and safeguards | Four metrics computed with bounded streaming state |
| Sunday morning | Terminal, JSON, and CSV renderers | Stable human and pipeline output |
| Sunday afternoon | CLI integration, tests, profiling, docs | Release candidate meeting functional and performance gates |

## 8. KPIs

| Metric | MVP target | First month target | Measurement |
|---|---:|---:|---|
| Throughput | 1 GB in under 30 seconds on the reference laptop | Maintained across releases | Benchmark fixture and elapsed wall time |
| Valid-line correctness | 100% on documented fixtures | No known P0 parsing defects | Unit and golden-output tests |
| Peak memory | Bounded by configured cardinality limit | No unbounded growth regressions | Peak RSS benchmark |
| Pipeline stability | JSON/CSV schemas documented and tested | No breaking schema change without major version | Contract tests |
| Time to first useful report | One command after install | Under 2 minutes for a new user | Manual quick-start check |

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from combined format | Medium | High | Define supported grammar, count malformed lines, fail clearly when none are valid |
| Unique-value tracking grows beyond laptop memory | Medium | High | Configurable hard ceiling and exit code `4` on unique-cardinality exhaustion |
| Python misses the 1 GB/30 s target | Medium | High | Single-pass parsing, compiled regex, lean records, benchmark early, profile before optimization |
| CSV representation is ambiguous for several tables | Medium | Medium | One normalized row schema with metric/rank/key/value columns |
| Terminal color contaminates redirected output | Low | Medium | Enable color only for TTY by default; provide `--color/--no-color` |
| Approximate data silently replaces exact results | Low | High | MVP uses exact counters; no approximation without a future explicit mode and PRD change |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and pytest are open source |
| Hosting and storage | $0 | Local CLI; no service or persisted data |
| Distribution | $0 | Source repository and pip-compatible package artifacts |
| Delivery labor | One weekend | Approved time constraint; no paid vendor dependencies |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Streaming combined-log parser | **Must** | Foundation for correct, bounded processing |
| Top-10 client IPs | **Must** | Core incident-triage metric |
| Top-10 error URLs | **Must** | Identifies failing resources quickly |
| Hourly distribution | **Must** | Shows traffic concentration over the day |
| Unique User-Agent share | **Must** | Required diversity signal with explicit exhaustion protection |
| Rich terminal output | **Must** | Default operator experience |
| JSON output | **Must** | Required structured pipeline interface |
| CSV output | **Must** | Required tabular pipeline interface |
| Follow appended data with `--follow` | **Should** | Useful for live logs, but finite files/stdin deliver the base value |
| gzip input | **Could** | Convenient but can be composed externally for MVP |
| Custom nginx format parser | **Could** | Broadens adoption after combined format is reliable |
| Database, HTTP API, server, cloud, Kubernetes | **Won't** | Conflicts with local, stateless, zero-budget scope |

### RICE Scoring (Must and Should)

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and aggregators | 10 | 5 | 90% | 1.5 | 30.0 |
| Rich terminal output | 9 | 4 | 90% | 0.5 | 64.8 |
| JSON output | 7 | 4 | 95% | 0.35 | 76.0 |
| CSV output | 6 | 3 | 95% | 0.35 | 48.9 |
| Cardinality guard | 10 | 5 | 80% | 0.4 | 100.0 |
| Follow mode | 5 | 3 | 70% | 0.5 | 21.0 |

The implementation order also respects dependencies: packaging and parsing precede aggregation and rendering even when a downstream feature has a higher standalone RICE score.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and edge cases match `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] New code is typed and runs on Python 3.11.
- [ ] Unit and relevant integration tests pass; overall coverage is at least 90%.
- [ ] Performance-sensitive changes do not violate the 1 GB/30 s target on the reference laptop.
- [ ] Terminal, JSON, and CSV contract tests pass where applicable.
- [ ] Documentation and `CLAUDE.md` status are updated.
- [ ] Review finds no unresolved Critical or High security/reliability issue.
- [ ] The package installs in a clean virtual environment and the quick start is manually verified.

## 13. Kill and Re-scope Criteria

Re-scope before release if exact streaming processing cannot meet 1 GB in under 30 seconds after profiling, if bounded-memory exact User-Agent tracking proves impractical on the reference laptop, or if the combined-log grammar cannot be specified with reliable fixture coverage. Do not respond by adding a server, database, or paid dependency; instead narrow supported input or make an explicitly approved approximation mode a future proposal.
