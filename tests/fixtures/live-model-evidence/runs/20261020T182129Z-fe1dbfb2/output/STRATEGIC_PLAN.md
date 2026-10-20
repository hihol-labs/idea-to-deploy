# Strategic Plan: nginx-log-report

## 1. Product Idea

`nginx-log-report` is an installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four operational views without requiring a service or persistent infrastructure: the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent values. The default presentation is colored terminal text; stable JSON and CSV schemas support pipelines.

The MVP is deliberately local, stateless, and open source. It must process a representative 1 GB log in under 30 seconds on a laptop while using bounded cardinality safeguards.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Incident responder | Needs a quick traffic/error picture before a full observability stack is available | One command gives the four highest-value summaries |
| Platform engineer | Automation owner | Shell pipelines need stable machine-readable output and exit behavior | JSON/CSV modes and documented exit codes are deterministic |
| DevOps engineer | Service operator | Ad hoc `grep`/`awk` commands are error-prone and hard to share | An installable, tested CLI provides repeatable parsing and aggregation |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, rich interactive reports | Broader UI and configuration surface than a four-metric pipeline tool | Minimal command contract and native JSON/CSV output |
| Logstash + Elastic + Kibana | Powerful ingestion, storage, search, and dashboards | Requires services, storage, setup, and operational cost | Zero-service local analysis with no retained data |
| AWStats | Established historical web analytics | Batch/reporting orientation and dated operational workflow | Stream-first execution and modern CLI/pipeline ergonomics |
| `grep`/`awk`/`sort` | Already installed, flexible, composable | Parsing is fragile, repeated sorts are expensive, scripts drift | One tested parser, a stable schema, and explicit failure modes |

## 4. Unique Value Proposition

Get a trustworthy nginx incident snapshot from a large local log in one command, with no server, database, configuration stack, or recurring cost.

## 5. Business Model

The project is open source and free to install and run. There are no paid tiers in the MVP. Value is measured by adoption, repeat use, and time saved during diagnosis rather than revenue. Optional future support or sponsorship is outside the one-weekend scope and must not compromise the $0 runtime promise.

## 6. Technology Stack

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required, portable, and fast enough with line-oriented parsing |
| CLI | Click | Mature option parsing, help generation, and usage exit behavior |
| Terminal output | Rich | Readable colored tables with automatic terminal handling |
| Domain models | `dataclasses` | Lightweight typed records without extra runtime dependencies |
| Aggregation | Standard-library dictionaries/counters | Single-process streaming with no persistence |
| Packaging | `pyproject.toml` + pip | Standard install and console-script distribution |
| Testing | pytest | Fast unit, CLI, golden-output, and performance tests |

## 7. Timeline

| Block | Focus | Deliverable |
|---|---|---|
| Saturday morning | Packaging, contracts, parser | Installable CLI and validated combined-log records |
| Saturday afternoon | Streaming aggregations | All four calculations with cardinality guardrails |
| Sunday morning | Renderers and failure behavior | Terminal, JSON, CSV, and exit-code contracts |
| Sunday afternoon | Quality and release readiness | Tests, 1 GB benchmark evidence, documentation, wheel build |

## 8. KPIs

| Metric | Launch target | 1 month | 3 months |
|---|---:|---:|---:|
| Representative 1 GB processing time | <30 seconds | <30 seconds | <25 seconds after profiling |
| Peak memory on benchmark fixture | <512 MiB within documented cardinality cap | <512 MiB | <384 MiB if profiling supports it |
| P0 acceptance tests passing | 100% | 100% | 100% |
| Valid combined-log parse accuracy on maintained fixtures | 100% | 100% | 100% |
| Successful installs on Python 3.11 | Linux | Linux + macOS | Linux + macOS + Windows |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Regex/date parsing misses valid nginx variants | Medium | High | Document the supported combined format; fixture-test quoting, IPv6, escapes, and timezone offsets |
| High-cardinality URLs or User-Agents exhaust memory | Medium | High | Enforce a configurable unique-key ceiling and terminate with exit code 4 rather than return misleading data |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early, compile the parser once, avoid per-line object retention, and profile before optimization |
| CSV cannot naturally represent four report shapes | Medium | Medium | Use a documented long-form schema with section/rank/key/value columns |
| Malformed lines silently distort percentages | Medium | High | Count rejected lines, provide strict mode, and base percentages only on valid requests |
| Terminal decoration leaks into pipelines | Low | Medium | Keep JSON/CSV undecorated and let Rich disable color for non-TTY output |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and hosting | $0 | Local CLI; no hosted components |
| Database/API/cloud | $0 | Explicitly absent |
| Dependencies | $0 | Open-source packages |
| Distribution | $0 | pip-installable package; public index publication is a later manual action |
| Development | One weekend | Owner time only |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream nginx combined logs from files and stdin | **Must** | Foundation for every report |
| Top 10 client IPs | **Must** | Core traffic concentration signal |
| Top 10 URLs with 4xx/5xx responses | **Must** | Core error diagnosis signal |
| Hourly request distribution | **Must** | Core temporal signal |
| Unique User-Agent share | **Must** | Required client-diversity signal |
| Colored terminal, JSON, and CSV renderers | **Must** | Required human and pipeline interfaces |
| Cardinality guard and exit contract | **Must** | Prevents incorrect results and uncontrolled memory |
| Gzip input | **Should** | Common operational convenience, but decompression may affect the performance target |
| Configurable top-N | **Could** | Useful generalization after the fixed top-10 contract is stable |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Conflicts with the approved local stateless scope |

### RICE Scoring (Must + Should)

`RICE = Reach × Impact × Confidence / Effort`; confidence is represented as a decimal in the calculation. Scores order delivery within technical dependencies.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Stream files/stdin and parse records | 10 | 5 | 90% | 0.75 | 60.0 |
| Top 10 client IPs | 9 | 4 | 90% | 0.25 | 129.6 |
| Top 10 error URLs | 10 | 5 | 90% | 0.35 | 128.6 |
| Hourly request distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Unique User-Agent share | 8 | 3 | 85% | 0.30 | 68.0 |
| Terminal/JSON/CSV renderers | 10 | 5 | 85% | 0.75 | 56.7 |
| Cardinality guard and exit contract | 8 | 5 | 80% | 0.40 | 80.0 |
| Gzip input | 5 | 2 | 70% | 0.30 | 23.3 |

Implementation follows dependency order first (parser before aggregations), then descending value among unblocked features. Gzip remains post-MVP unless the core benchmark and tests are already green.

## 12. Definition of Done

A feature is done when:

- [ ] Its behavior and edge cases match `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 type/syntax checks and lint checks pass.
- [ ] Unit and CLI integration tests pass; changed core modules maintain at least 90% branch coverage.
- [ ] Machine-readable outputs have golden-schema tests and contain no terminal styling.
- [ ] The complete `0/1/2/3/4` exit-code contract is tested where applicable.
- [ ] Documentation and `CLAUDE.md` status are updated.
- [ ] No known critical or high-severity security issue remains.
- [ ] The representative 1 GB benchmark is under 30 seconds on the documented laptop profile before release.
- [ ] A human reviews release-bound changes; publication remains an explicit manual action.

## 13. Kill Criteria

Pause or redesign the MVP if profiling shows the supported input cannot meet 1 GB in 30 seconds on the documented reference laptop, or if exact required metrics cannot stay within the documented memory/cardinality envelope without persistent storage. Do not weaken correctness or silently approximate results to preserve the deadline.

See `PROJECT_ARCHITECTURE.md` for the selected design and `PRD.md` for acceptance behavior.
