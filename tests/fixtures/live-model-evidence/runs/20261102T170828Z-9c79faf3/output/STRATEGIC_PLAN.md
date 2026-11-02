# Strategic Plan: nginx-stream-insights

## 1. Product Idea

`nginx-stream-insights` is a local, installable Python 3.11 CLI for DevOps and SRE engineers. It consumes nginx access-log lines from a file or standard input without retaining raw events, then reports the top client IPs, error-heavy URLs, hourly traffic distribution, and the share of unique User-Agents. It is designed for fast incident triage and pipeline use without operating a service.

## 2. Target Users

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Restores service during incidents | Needs a useful traffic summary before a dashboard can be opened | One local command, progressive streaming, terminal-first summary |
| DevOps engineer | Maintains nginx fleets and automation | Ad-hoc shell pipelines are fragile and hard to reuse | Stable JSON/CSV schemas and documented exit codes |
| Platform engineer | Investigates exported logs | Central observability may be costly, unavailable, or excessive | Stateless, zero-infrastructure analysis on a laptop |

## 3. Competitive Analysis

| Alternative | Strength | Limitation for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI/reporting surface and additional operational choices | Narrow, pipeline-stable four-metric contract in a Python package |
| Logstash + Elastic + Kibana | Powerful ingestion, storage, search, dashboards | Requires services, storage, setup, and ongoing resources | No service or database; immediate local analysis |
| AWStats | Established historical reporting | Report-generation workflow and legacy-oriented UX | Streaming input and modern JSON/CSV automation |
| `grep`/`awk`/`sort` | Present on most Unix systems and composable | Quoting, parsing, portability, and repeated sorting are error-prone | Tested nginx parsing, bounded top lists, explicit malformed-input behavior |

## 4. Value Proposition

Get a reproducible operational summary from a large nginx log in one local command, with no service to deploy and no raw-log persistence.

## 5. Business Model

The project is open source and free. There is no paid tier, telemetry, hosted component, CAC, or revenue target. Value is measured in time saved during diagnosis and adoption by engineering teams, not monetization.

## 6. Technology Stack

| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Required, widely available, sufficient for the one-weekend scope |
| CLI | Click | Predictable argument parsing, help, and exit handling |
| Terminal output | Rich | Accessible color and tables with automatic terminal detection |
| Models | `dataclasses` | Small typed domain model without runtime framework overhead |
| Packaging | `pyproject.toml` + pip | Standard install and console-script entry point |
| Testing | pytest | Fast unit, integration, and performance-regression tests |

## 7. Timeline

| Period | Focus | Deliverable |
|---|---|---|
| Saturday morning | Package skeleton, parser, aggregates | Validated streaming core |
| Saturday afternoon | Metrics and terminal renderer | Useful local command |
| Sunday morning | JSON/CSV contracts and error handling | Pipeline-compatible CLI |
| Sunday afternoon | performance, packaging, docs | Releasable MVP |

## 8. KPIs

| Metric | MVP target | First month target | Measurement |
|---|---:|---:|---|
| Performance | 1 GB in under 30 seconds on the reference laptop | No regression beyond 10% | Repeatable benchmark fixture and command |
| Correctness | 100% of golden fixtures match expected metrics | Zero open P0 correctness defects | Automated tests and issue tracker |
| Memory | Does not scale with raw line count, except documented exact unique sets | Peak usage recorded on 1 GB benchmark | `/usr/bin/time -v` |
| Adoption | pip-installable artifact | 10 distinct users or 3 teams | Release downloads or voluntary feedback |
| Pipeline stability | JSON/CSV schema tested | No unannounced schema break | Contract tests and semantic versioning |

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python parsing misses the 30-second target | Medium | High | Keep the hot loop allocation-light; profile on a fixed 1 GB fixture; reject expensive regex backtracking |
| nginx format variations produce incorrect fields | High | High | Support and document common/combined formats first; explicit custom format is deferred; count malformed lines |
| Exact User-Agent cardinality consumes too much memory | Medium | High | Configurable cardinality ceiling and exit code 4; document the limit; consider approximation only after MVP |
| Terminal, JSON, and CSV results diverge | Medium | High | One report model feeding three renderers and cross-renderer golden tests |
| “Unique share” is misunderstood | Medium | Medium | Publish its numerator, denominator, zero-input behavior, and formula in all contracts |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development tools | $0 | Open-source stack and existing laptop |
| Infrastructure | $0/month | Local CLI only |
| Distribution | $0 | Source repository and public Python package index |
| Delivery time | One weekend | Single developer, narrow MVP |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Streaming common/combined log parsing | Must | Foundation for every metric and the memory target |
| Top-10 IPs | Must | Primary abuse and traffic-source diagnostic |
| Top-10 URLs with 4xx/5xx responses | Must | Primary application/error diagnostic |
| Hourly distribution and unique User-Agent share | Must | Completes the promised operational summary |
| Rich text, JSON, and CSV output | Must | Serves humans and pipelines |
| Stable input/error/exit-code behavior | Must | Required for dependable automation |
| Configurable top-N and cardinality ceiling | Should | Useful control without changing core semantics |
| `--follow` for appended file lines | Should | Enables live local observation |
| Approximate User-Agent cardinality | Could | Reduces worst-case memory but adds semantic complexity |
| Database, HTTP API, auth, server, cloud, Kubernetes | Won't | Explicitly outside the local stateless product |

### RICE Scoring (Must and Should)

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser | 10 | 5 | 95% | 0.8 | 59.4 |
| Stable behavior and exit codes | 9 | 5 | 95% | 0.8 | 53.4 |
| Core four-metric aggregation | 10 | 5 | 95% | 1.0 | 47.5 |
| Three output formats | 9 | 4 | 90% | 0.8 | 40.5 |
| Configurable top-N/cardinality ceiling | 6 | 3 | 85% | 0.4 | 38.3 |
| Follow mode | 5 | 3 | 70% | 0.7 | 15.0 |

Implementation order follows dependencies first and then descending value within each dependency layer; RICE does not put a renderer ahead of the report model it consumes.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Code runs on Python 3.11 and lint/type checks configured by the project pass.
- [ ] Unit and integration tests pass with at least 90% line coverage for core/parser modules.
- [ ] The 1 GB reference benchmark meets the under-30-second target for performance-sensitive changes.
- [ ] Terminal, JSON, and CSV documentation is updated when contracts change.
- [ ] Review finds no unresolved Critical or High security/correctness issue.
- [ ] The pip-built wheel installs in a clean virtual environment and its console command passes a smoke test.

## 13. Product Kill Criteria

Re-scope or stop the MVP if profiling shows the required performance cannot reasonably be met in Python 3.11 on the reference laptop, or if supporting the promised nginx formats requires unbounded memory. Do not silently weaken output correctness or the stated input contract.

