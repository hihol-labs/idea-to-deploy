# Strategic Plan: nginx-stream-report

## 1. Product idea

`nginx-stream-report` is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx combined/common access logs as a stream and produces four operational summaries without loading the complete file into memory: top 10 client IPs, top 10 URLs with 4xx/5xx responses, requests by hour, and the proportion of distinct User-Agent values. Terminal output is colored by default; JSON and CSV provide stable machine-readable output.

The MVP is a $0 open-source utility delivered in one weekend. It has no service component, account system, persistence layer, or hosted operating cost.

## 2. Target audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates incidents from a shell | Needs a useful overview before a dashboard is available | One command returns the four highest-value summaries |
| DevOps engineer | Operates small/self-hosted estates | Full observability stacks are costly to deploy and maintain | Local, dependency-light, stateless processing |
| Platform engineer | Builds incident pipelines | Ad-hoc output is hard to automate | Versioned JSON and rectangular CSV formats |

## 3. Competitive analysis

| Alternative | Strength | Weakness for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive and HTML reports | Broader UI/configuration surface than a four-metric pipeline tool | Narrow command contract and first-class JSON/CSV |
| Logstash + Elastic + Kibana | Powerful ingestion, search, retention, dashboards | Operational cost, services, storage, and setup are disproportionate | Zero-service, zero-storage local analysis |
| AWStats | Established historical web analytics | Batch-oriented, dated workflow, persistent report generation | Immediate streaming terminal feedback |
| `grep`/`awk` pipelines | Already installed and composable | Fragile parsing, locale/quoting issues, repeated scripts, no shared schema | Tested nginx parsing and stable cross-format semantics |

## 4. Unique value proposition

Get an incident-ready nginx traffic and error summary from a file or pipe, locally and with bounded memory, without operating an analytics stack.

## 5. Business and licensing model

The product is free and open source under a permissive license. There is no monetization in the MVP; value is measured by adoption, saved incident time, and maintainability. Distribution uses PyPI and source releases. CAC and LTV are not meaningful for a non-commercial weekend project; contribution and repeat-use metrics replace them.

## 6. Technology stack

| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, strong standard-library streaming support |
| CLI | Click | Predictable options, validation, help, and exit codes |
| Terminal UI | Rich | TTY-aware color and readable tables |
| Domain models | `dataclasses` | Explicit, lightweight records without a validation framework |
| Parsing/aggregation | Python standard library | Keeps cost and dependency count low |
| Packaging | `pyproject.toml`, pip | Standard install and console-script distribution |
| Quality | pytest, Ruff, mypy | Fast local verification for a typed CLI |

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Packaging, contracts, parser | Installable command and tolerant combined/common parsing |
| Saturday afternoon | Streaming aggregation | Four correct metrics with bounded-memory safeguards |
| Sunday morning | Terminal, JSON, CSV | Human and pipeline output contracts complete |
| Sunday afternoon | Tests, benchmark, docs | Acceptance suite, 1 GB performance evidence, release-ready docs |

## 8. KPIs

| Metric | First month | 3 months | 6 months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | <30 s | <25 s | <20 s |
| Peak RSS on 1 GB representative log | <256 MB | <192 MB | <160 MB |
| Valid-line parsing accuracy on fixture corpus | >=99.9% | >=99.95% | >=99.95% |
| PyPI installs | 50 | 250 | 750 |
| Median time from install to first report | <2 min | <90 s | <60 s |

Performance figures must name the laptop/CPU, OS, storage, Python version, fixture generator, and command; they are not universal hardware guarantees.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats vary from common/combined | High | High | Document supported grammar, tolerate escapes, count malformed lines, offer explicit failure threshold |
| Exact counters grow with attacker-controlled cardinality | Medium | High | Bound exact top-k candidate maps and document approximation/error behavior if a cap is reached |
| Python misses the 1 GB/30 s target | Medium | High | Avoid per-line regex recompilation/objects, benchmark early, profile before optimization |
| CSV interpretation differs across consumers | Medium | Medium | Publish one stable rectangular schema with a `metric` discriminator |
| Colored output pollutes pipes | Low | Medium | Enable color only for TTY terminal mode; JSON/CSV never emit styling |
| “Unique User-Agent share” is misunderstood | Medium | Medium | Define it as distinct non-empty UA strings divided by valid requests, with both counts emitted |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development | $0 cash | One weekend of contributor time |
| Runtime/hosting | $0/month | Runs locally; no hosted service |
| Dependencies | $0 | Open-source Python packages |
| Distribution | $0 | PyPI and source hosting free tiers |
| Optional CI | $0 | Public open-source allowance or local checks |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream common/combined logs from file or stdin | **Must** | Foundation for local and pipeline use |
| Top 10 client IPs | **Must** | Fast abuse/traffic concentration signal |
| Top 10 URLs among 4xx/5xx responses | **Must** | Direct incident triage value |
| Hourly request distribution | **Must** | Reveals traffic shape in the log’s own timezone |
| Distinct User-Agent share | **Must** | Highlights client diversity/bot-like patterns |
| Rich terminal report | **Must** | Default interactive experience |
| Stable JSON and CSV output | **Must** | Required pipeline integration |
| Malformed-line summary and strict threshold | **Should** | Makes partial data quality visible |
| Follow a growing file | **Should** | Useful during live incidents but not required for finite-file MVP proof |
| Configurable top-N | **Could** | Helpful flexibility beyond the approved top 10 |
| Custom nginx `log_format` grammar | **Could** | Broadens compatibility at meaningful parser cost |
| Database, HTTP API, auth, server, cloud, Kubernetes | **Won't** | Explicitly out of scope and contrary to local stateless value |

### RICE scoring (Must and Should)

RICE = Reach × Impact × Confidence / effort. Scores are directional estimates for implementation order.

| Feature | Reach | Impact | Confidence | Effort (days) | Score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin + parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Streaming aggregation for four metrics | 10 | 5 | 90% | 1.0 | 45.0 |
| Rich terminal report | 9 | 4 | 90% | 0.40 | 81.0 |
| Stable JSON output | 8 | 4 | 95% | 0.25 | 121.6 |
| Stable CSV output | 7 | 4 | 90% | 0.30 | 84.0 |
| Malformed-line policy | 8 | 3 | 85% | 0.30 | 68.0 |
| Follow mode | 6 | 3 | 70% | 0.50 | 25.2 |

Dependency order overrides raw RICE where necessary: parser and aggregation precede every renderer.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and edge cases match `PRD.md` acceptance criteria.
- [ ] Python 3.11 code passes Ruff, mypy, and pytest with branch coverage >=90% for parser/aggregation code.
- [ ] Integration tests pass for file input, stdin, terminal, JSON, and CSV where applicable.
- [ ] A review records no unresolved Critical or High findings.
- [ ] README and format contracts are updated.
- [ ] No known Critical/High dependency or security issue remains.
- [ ] The wheel installs in a clean local environment and the command is manually verified.
- [ ] Performance-sensitive changes include reproducible benchmark evidence.

## 13. MVP success and kill criteria

Proceed to a `0.1.0` release if all P0 criteria pass and a documented reference-laptop run processes a representative 1 GB file in under 30 seconds. Re-scope or stop if the target cannot be met after profiling, supported-format accuracy is below 99.9%, or the implementation requires a service/database to remain useful.

See `PRD.md` for behavior and `IMPLEMENTATION_PLAN.md` for delivery order.
