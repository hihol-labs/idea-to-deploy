# Strategic Plan: nginx-log-top

## 1. Product Summary

`nginx-log-top` is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the percentage of distinct User-Agent values. It defaults to colored terminal output and offers JSON and CSV for pipelines.

The product is deliberately narrow: no authentication, persistence, network service, cloud dependency, or cluster runtime. The MVP is an open-source, $0-budget weekend project.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates incidents from a shell | Needs a fast traffic/error overview without uploading logs | One local command produces the four core summaries |
| DevOps engineer | Automates diagnostics in scripts | Human-only tools are hard to compose | Stable JSON/CSV modes, stdin support, meaningful exit codes |
| Platform engineer | Reviews large rotated logs | Ad hoc grep/awk pipelines are fragile and memory-heavy | Streaming parser with bounded aggregation and a measurable 1 GB target |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Our distinction |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader configuration and UI than a four-metric pipeline tool needs | Narrow zero-service CLI with explicit JSON/CSV contracts |
| Logstash + Elastic + Kibana | Powerful ingestion, search, dashboards | Operationally heavy, persistent, costly in time and resources | No services, database, ingestion pipeline, or cloud bill |
| AWStats | Established historical reporting | Batch/web-report orientation and dated operational workflow | Immediate terminal analysis and pipeline-friendly output |
| grep/awk/sort/uniq | Ubiquitous and flexible | Repeated parsing, quoting hazards, weak error handling, multiple passes | One tested parser, one pass, consistent metrics and failures |

## 4. Unique Value Proposition

Get an incident-ready nginx traffic and error summary from a gigabyte-scale log in one local command, without deploying or configuring a service.

## 5. Business and Licensing Model

Open source and free to use. There is no paid tier or near-term monetization. Success is measured by usefulness, predictable behavior, and community adoption; contributions and issue reports are the feedback loop. A permissive license such as MIT is recommended.

## 6. Technology Stack

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required, widely available, productive for a weekend delivery |
| CLI | Click | Stable command/option parsing and shell-friendly errors |
| Presentation | Rich | Colored terminal tables with automatic no-color fallback |
| Domain models | `dataclasses` | Lightweight typed records without a validation framework |
| Packaging | pip-compatible `pyproject.toml` | Standard local and isolated installation |
| Testing (planned) | pytest | Fast unit, integration, golden-output, and performance checks |

## 7. Delivery Timeline

| Period | Focus | Exit result |
|---|---|---|
| Saturday morning | Package skeleton, log model, parser | Combined-log lines parse with explicit malformed-line behavior |
| Saturday afternoon | Streaming aggregation | All four metrics computed in one pass |
| Sunday morning | Terminal, JSON, and CSV renderers | Stable output contracts and CLI errors |
| Sunday afternoon | Tests, 1 GB benchmark, docs, packaging | Installable release candidate meeting acceptance criteria |

## 8. KPIs

| Metric | Release target | 1 month | 3 months |
|---|---:|---:|---:|
| Processing time for 1 GB fixture on reference laptop | <30 s | <30 s | <25 s if profiling supports it |
| Valid-line parse accuracy on supported format corpus | 100% | 100% | 100% |
| P0 automated acceptance checks passing | 100% | 100% | 100% |
| Peak RSS on 1 GB high-cardinality benchmark | <512 MB | <512 MB | <384 MB |
| External adopters/stars (non-binding) | 0 | 10 | 50 |

The reference laptop CPU, storage, OS, Python patch version, fixture hash, and warm/cold-cache conditions must be recorded with performance results.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| nginx formats differ from the supported combined format | High | High | State the format contract, count malformed lines, fail if no valid lines, design parser extension points |
| Exact unique User-Agent counting grows with cardinality | Medium | High | Document O(U) memory, benchmark adversarial cardinality, consider approximate mode only after MVP |
| Python misses the 1 GB/30 s target | Medium | High | Profile early, compile regex once, avoid per-line allocations, benchmark on a declared reference machine |
| CSV representation of multiple reports is ambiguous | Medium | Medium | Use one normalized schema with a `report` discriminator and fixed columns |
| ANSI output breaks redirected pipelines | Low | Medium | Disable color when stdout is not a TTY and in JSON/CSV modes |
| Malformed input produces misleading totals | Medium | High | Track and report skipped lines; define warning and terminal failure thresholds |

## 10. Budget

| Item | Cost | Notes |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, pytest are open source |
| Hosting/database/cloud | $0 | None exists in the architecture |
| Development | $0 cash | One weekend of contributor time |
| CI | $0 | Optional free open-source allowance; local checks remain authoritative |
| Total cash budget | **$0** | Hard constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream a file or stdin in supported nginx combined format | **Must** | Foundation for all value and pipeline use |
| Top-10 client IPs | **Must** | Core incident triage metric |
| Top-10 error URLs for 4xx/5xx responses | **Must** | Core error hotspot metric |
| Hourly request distribution | **Must** | Reveals traffic shape and incident windows |
| Share of unique User-Agents | **Must** | Required diversity signal |
| Colored terminal renderer | **Must** | Required default interaction |
| JSON and CSV renderers | **Must** | Required pipeline integration |
| Malformed-line counters and deterministic exit codes | **Should** | Operational trust and automation safety |
| Optional top-N override | **Could** | Useful polish, not necessary for the approved top-10 MVP |
| Additional nginx log-format configuration | **Could** | Expands adoption after the supported format is dependable |
| Auth, database, HTTP API, server, cloud, Kubernetes | **Won't** | Conflicts with the local stateless CLI product |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / person-days` and determine plan ordering while respecting technical dependencies.

| Feature | Reach | Impact | Confidence | Effort (days) | RICE |
|---|---:|---:|---:|---:|---:|
| Streaming file/stdin foundation | 10 | 5 | 90% | 0.75 | 60.0 |
| Top-10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top-10 error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Unique User-Agent share | 7 | 3 | 80% | 0.30 | 56.0 |
| Colored terminal renderer | 8 | 3 | 90% | 0.40 | 54.0 |
| JSON and CSV renderers | 9 | 4 | 90% | 0.60 | 54.0 |
| Malformed-line and exit contract | 8 | 4 | 90% | 0.45 | 64.0 |

## 12. Definition of Done

A release feature is done when:

- [ ] Its PRD acceptance criteria are automated and passing.
- [ ] The package installs on Python 3.11 and the `nginx-log-top` entry point runs.
- [ ] Unit, integration, golden-output, and relevant performance tests pass.
- [ ] The exact 1 GB fixture completes in under 30 seconds on the recorded reference laptop.
- [ ] Static checks and code review pass with no known critical/high security issues.
- [ ] User-facing contracts and README are current.
- [ ] No network service, database, authentication, cloud, or Kubernetes dependency has entered scope.

## 13. Kill and Pivot Criteria

Stop or re-scope the MVP if, after profiling the real parser and aggregators, the reference 1 GB fixture cannot complete in 30 seconds without abandoning the approved Python stack; if exact unique-agent counting requires unacceptable memory on the declared corpus, propose an explicit approximate opt-in rather than silently changing semantics.

See [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for technical decisions and [PRD.md](PRD.md) for the behavioral contract.
