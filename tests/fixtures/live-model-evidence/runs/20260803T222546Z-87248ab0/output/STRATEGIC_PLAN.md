# Strategic Plan: Nginx Log Stats

## 1. Product Idea

Nginx Log Stats is a local, open-source Python 3.11 CLI that turns nginx combined access logs into four immediate operational views: top client IPs, top URLs producing 4xx/5xx responses, request volume by hour, and the share of unique User-Agent values. It reads files or stdin as a stream and supports colored terminal, JSON, and CSV output. It is for engineers who need a fast first answer without deploying an observability stack.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Responds to incidents | Needs traffic and error concentration within minutes | One local command produces the four highest-value summaries |
| DevOps engineer | Operates small/medium nginx fleets | Full analytics stacks are too costly or slow to provision | Zero-service, pip-installable analysis works on exported logs and stdin |
| Platform developer | Builds shell-based operational automation | Human-only reports are hard to integrate | Versioned JSON and stable CSV keep stdout pipeline-safe |

## 3. Competitive Analysis

| Alternative | What it does | Weakness for this use case | Nginx Log Stats difference |
|---|---|---|---|
| GoAccess | Rich real-time terminal/HTML nginx analytics | Broader interface and native binary may be more than a Python-centric pipeline needs | Narrow four-metric contract with first-class JSON/CSV and pip distribution |
| Logstash + Elasticsearch + Kibana | Centralized ingestion, search, storage, dashboards | Infrastructure, memory, setup, and ongoing operations violate the $0 local scope | No services, persistence, account, or deployment |
| AWStats | Persistent historical web analytics reports | Configuration and report-generation model is oriented toward retained reporting | One-shot streaming incident analysis |
| `grep`/`awk` pipelines | Ubiquitous ad hoc text analysis | Easy to misparse quoted fields/timezones; each metric needs bespoke commands | Tested combined-format parser and deterministic multi-metric report |

The project does not aim to replace historical observability platforms. It wins when the job is bounded, local, urgent, and pipeline-oriented.

## 4. Unique Value Proposition

Get trustworthy nginx traffic and error concentration from a local log stream in one command, without running or paying for an analytics service.

## 5. Business Model

The product is a $0 open-source utility. There are no paid tiers, hosted service, ads, or data collection. The economic goal is engineering-time savings: if one incident avoids 10 minutes of hand-built shell analysis, adoption has delivered value. Maintenance is community- and maintainer-funded; no revenue, CAC, or LTV assumptions are required for the MVP.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved stack, broad SRE availability, fast weekend delivery |
| CLI | Click | Mature option validation, stdin/file conventions, test runner |
| Terminal UI | Rich | Accessible colored tables and terminal capability detection |
| Domain models | `dataclasses` | Lightweight typed records without validation-framework overhead |
| Core processing | Python standard library | Streaming I/O, counters, JSON/CSV, timestamps; minimizes dependencies |
| Packaging | `pyproject.toml`, pip/pipx | Standard installable CLI distribution |
| Testing | pytest, Click testing helpers | Fast parser, aggregation, renderer, and CLI-contract verification |

See [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for component and interface contracts.

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Packaging, models, parser | Installable command skeleton and verified combined-log parsing |
| Saturday afternoon | Streaming metrics | Exact IP, error-URL, hourly, and User-Agent aggregations |
| Sunday morning | Terminal/JSON/CSV interfaces | Three contract-tested output modes and exit behavior |
| Sunday afternoon | Performance, hardening, docs | 1 GB benchmark evidence, clean-wheel smoke test, release-ready docs |

The one-weekend commitment is a delivery constraint, not a promise to omit failed-gate remediation. If correctness or performance fails, scope stays at P0 and release moves rather than weakening acceptance.

## 8. KPIs

| Metric | 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| Representative 1 GB processing time | <30 s | <30 s | <25 s after evidence-led optimization |
| P0 acceptance tests passing | 100% | 100% | 100% |
| Valid-line parse accuracy on maintained fixture corpus | 100% | 100% | 100% |
| Known false-success machine-output cases | 0 | 0 | 0 |
| Package installs/downloads | 25 | 100 | 300 |
| Confirmed external users or teams | 3 | 10 | 25 |

Performance is always reported with fixture, hardware, OS, and Python version. Downloads are directional adoption evidence, not proof of active use.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Python parser misses the 1 GB/30 s goal | Medium | High | Benchmark early; profile; optimize hot path; consider chunked workers only if measured |
| Real nginx formats differ from combined format | High | Medium | State grammar clearly; categorize malformed lines; maintain representative fixtures; defer configurable formats |
| Distinct URL/IP/User-Agent cardinality increases memory | Medium | High | Document exact-counter behavior; measure peak RSS; add guarded approximate mode only as a later feature |
| CSV multi-section shape surprises consumers | Medium | Medium | Publish stable schema, golden fixtures, schema version for JSON, and compatibility tests |
| Terminal escape sequences in log fields spoof output | Low | High | Sanitize control characters and disable Rich markup for untrusted cells |
| Error skipping hides damaged data | Medium | Medium | Show valid/malformed totals; provide `--strict`; keep diagnostics on stderr |
| Project name conflicts on package index | Low | Medium | Check index before release and change distribution name while preserving CLI contract if necessary |

## 10. Budget

| Item | One-time | Monthly | Comment |
|---|---:|---:|---|
| Development tools | $0 | $0 | Python and dependencies are open source |
| Hosting/runtime | $0 | $0 | Runs locally; no server, database, or cloud |
| CI for public repository | $0 | $0 | Use an available free open-source allowance or run locally |
| Package publication | $0 | $0 | Public package index publication is free |
| Developer labor | One weekend | Maintenance as available | Time budget, not cash spend |
| **Cash total** | **$0** | **$0** | Hard product constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream combined-format input from file/stdin | **Must** | Foundation for every metric and pipeline workflow |
| Top client IPs | **Must** | Core traffic-concentration question |
| Top 4xx/5xx URLs | **Must** | Core incident/error question |
| 24-hour request distribution | **Must** | Core traffic timing question |
| Unique User-Agent share | **Must** | Explicit product outcome |
| Colored terminal report | **Must** | Default human interface |
| JSON output | **Must** | Required pipeline interface |
| CSV output | **Must** | Required pipeline interface |
| Strict/default malformed-line policy | **Should** | Improves trust and automation but does not create the base metrics |
| Configurable top-N | **Should** | Small usability gain beyond top-10 default |
| Gzip input | **Could** | Convenient, but shell decompression already composes with stdin |
| Configurable nginx `log_format` | **Could** | Broadens compatibility at significant parser/UX cost |
| Live periodically refreshing UI | **Could** | Useful for endless streams, but final-on-EOF reports satisfy MVP |
| Database/history, HTTP API, auth, cloud, Kubernetes | **Won't** | Violates stateless local CLI constraints |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / effort` and are directional planning inputs. Reach is a 1–10 first-month relative scale; effort is person-days.

| Feature | Reach | Impact | Confidence | Effort (days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Stream combined-format file/stdin | 10 | 5 | 95% | 0.75 | 63.33 |
| Top client IPs | 9 | 4 | 95% | 0.25 | 136.80 |
| 24-hour distribution | 8 | 4 | 95% | 0.25 | 121.60 |
| Top 4xx/5xx URLs | 9 | 5 | 95% | 0.40 | 106.88 |
| Unique User-Agent share | 7 | 3 | 90% | 0.25 | 75.60 |
| Colored terminal report | 9 | 3 | 90% | 0.40 | 60.75 |
| Strict/default malformed policy | 8 | 4 | 85% | 0.50 | 54.40 |
| Configurable top-N | 5 | 2 | 95% | 0.10 | 47.50 |
| JSON output | 8 | 4 | 95% | 0.75 | 40.53 |
| CSV output | 6 | 3 | 90% | 0.75 | 21.60 |

Dependency order overrides raw score where necessary: input parsing precedes all metrics, the shared report model precedes renderers, and machine schemas are finalized before compatibility tests. [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) encodes this feasible order.

## Definition of Done

A feature is Done only when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md` and architecture contracts.
- [ ] Python 3.11 code is formatted, linted, and type-checked under the repository's selected tools.
- [ ] Unit and applicable CLI integration tests pass; overall coverage is at least 90% and P0 branches are covered.
- [ ] Machine-output golden tests prove stdout remains parseable and diagnostics remain on stderr.
- [ ] Security checks find no known Critical or High issues, and untrusted terminal content is tested.
- [ ] Relevant README and interface documentation are current.
- [ ] A clean locally built wheel installs and the console entry point is manually smoke-tested.
- [ ] Performance-sensitive changes include reproducible measurements; release requires the 1 GB/<30 s gate.
- [ ] Evidence is recorded in the active Idea to Deploy verification receipt; narration alone is not acceptance.

## Release and Kill Criteria

Release the MVP when all P0 criteria pass, the wheel installs in a clean environment, and the reference 1 GB benchmark completes correctly in under 30 seconds. Pause or re-scope the project if, after one weekend plus one bounded remediation cycle, the tool cannot beat a documented `awk` baseline on usability while meeting correctness, or if exact counters exceed reasonable laptop memory on the representative fixture. Never solve a missed gate by silently introducing a service, database, paid dependency, or approximate metric.

