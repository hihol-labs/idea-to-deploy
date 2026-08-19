# Strategic Plan: Nginx Log Lens

## 1. Product Idea

Nginx Log Lens is an open-source, local Python 3.11 command-line tool for
DevOps and SRE engineers. It reads an nginx access log as a stream and produces
four immediately useful operational views: top client IPs, top URLs producing
4xx/5xx responses, hourly request distribution, and the share of unique
User-Agents. Rich colored text is the human-facing default; JSON and CSV make
the same report safe to consume in pipelines.

The MVP is deliberately narrow: one process, bounded-memory aggregation, no
network service, and no persisted state. It is intended for fast incident
triage and ad-hoc analysis of files that are too large for comfortable manual
inspection but do not justify deploying an observability platform.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Investigates production incidents | Needs a useful summary before a full stack query or dashboard is ready | Produces the four core signals with one local command |
| DevOps engineer | Maintains nginx hosts and pipelines | Shell one-liners are fragile and difficult to reuse | Provides stable parsing, exit codes, and JSON/CSV contracts |
| Platform engineer | Supports teams with limited observability | Heavy log platforms are costly to deploy and operate | Offers a zero-service, pip-installable diagnostic tool |

## 3. Competitive Analysis

| Alternative | What it does well | Weakness for this use case | Our differentiation |
|---|---|---|---|
| GoAccess | Mature interactive and HTML nginx analytics | Broader UI/reporting surface than needed; another binary and workflow | Focused four-metric CLI with explicit machine formats |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, retention, and dashboards | Operational cost and setup are disproportionate for one local file | No services, persistence, or infrastructure |
| AWStats | Established historical web statistics | Batch-oriented and dated operational workflow; persisted reports | Streaming, incident-oriented output with pipeline contracts |
| `grep` / `awk` / `sort` | Ubiquitous and flexible | Parsing assumptions are implicit; exact pipelines are hard to review and reuse | Tested nginx parsing and consistent text/JSON/CSV semantics |

## 4. Unique Value Proposition

Get a trustworthy incident-ready summary from a large nginx access log in one
local command, without deploying or operating a log platform.

## 5. Business Model

The project is free and open source. The MVP has no monetization, paid tier, or
hosted component. Its value is reduced incident-analysis time and a reusable
reference implementation. Distribution through PyPI keeps adoption friction
low. Any future sponsorship or support model is outside the MVP and must not
alter the local-first contract.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, and sufficient for the performance target with streaming I/O |
| CLI | Click | Stable commands, options, validation, and exit handling |
| Terminal presentation | Rich | Accessible colored tables with automatic non-TTY behavior |
| Domain models | `dataclasses` | Small typed records without framework overhead |
| Packaging | pip-compatible `pyproject.toml` | Standard installation and console-script distribution |
| Tests/quality | pytest, Ruff, mypy | Fast local feedback for parser, aggregation, output, and type contracts |

## 7. Timeline

| Weekend block | Focus | Result |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable CLI reads valid and malformed combined-format lines |
| Saturday afternoon | Streaming aggregation and cardinality guard | All four metrics computed with bounded top-10 structures and an explicit unique-cardinality limit |
| Sunday morning | Rich, JSON, and CSV renderers | Stable human and pipeline outputs with exit-code handling |
| Sunday afternoon | Tests, 1 GB benchmark, documentation, release check | Acceptance evidence and a releasable package candidate |

## 8. KPIs

| Metric | MVP / first month target | 3-month target | 6-month target |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | < 30 seconds | Maintain < 30 seconds | Maintain < 30 seconds |
| Peak resident memory on 1 GB fixture | <= 256 MiB under declared cardinality limit | Maintain | Maintain |
| Valid combined-log parsing accuracy on fixture suite | 100% | 100% | 100% |
| Output-contract regression tests | All pass | All pass | All pass |
| PyPI installs | Baseline only; no growth promise | 100 cumulative | 300 cumulative |

Adoption figures are directional, not release gates. Correctness, bounded
behavior, and the performance target are the MVP gates.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Regex/parser work dominates runtime | Medium | High | Precompile parsing, benchmark early, profile before optimizing |
| High-cardinality IPs, URLs, or User-Agents exhaust memory | Medium | High | Enforce a configurable documented unique-cardinality ceiling and exit with code 4 before unsafe growth |
| Real nginx formats vary from the supported contract | High | Medium | State that MVP supports combined format, count malformed lines, fail only when no valid records exist |
| JSON and CSV semantics drift from terminal output | Medium | High | Build all renderers from one immutable report model and use golden tests |
| ANSI color corrupts redirected output | Low | Medium | Enable color only for a terminal unless explicitly overridden by Rich behavior |
| A one-weekend schedule encourages scope creep | Medium | Medium | Enforce the Won't list and ship only the approved CLI surface |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and test tooling are open source |
| Infrastructure | $0 | Local CLI; no server, database, or cloud resources |
| Distribution | $0 | PyPI and source hosting have no required project fee |
| Labor accounting | $0 cash budget | One-weekend contributor time is the approved constraint |
| Total required cash | **$0** | No paid dependency or service is needed |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Streaming nginx combined-log parsing | **Must** | Foundation for correctness and the 1 GB performance target |
| Top-10 client IPs | **Must** | Core incident-triage signal |
| Top-10 URLs by 4xx/5xx errors | **Must** | Core failure-localization signal |
| Hourly request distribution | **Must** | Core traffic-shape signal; percentage is `100 × hourly_request_count / total_valid_requests` |
| Unique User-Agent share | **Must** | Core client-diversity signal |
| Colored Rich terminal report | **Must** | Approved default human interface |
| JSON and CSV output | **Must** | Required for automation and pipelines |
| Malformed-line accounting and exit codes `0/1/2/3/4` | **Must** | Makes automation deterministic and safe |
| Gzip input | **Should** | Common operational convenience, but decompression can be piped into stdin |
| Custom nginx format templates | **Could** | Expands compatibility after combined-format MVP is proven |
| Database, HTTP API, auth, server, cloud, Kubernetes | **Won't** | Contradicts the local stateless CLI product boundary |
| Interactive dashboard or retained history | **Won't** | Covered by heavier alternatives and incompatible with the weekend MVP |

### RICE Scoring (Must + Should)

Confidence is expressed as a multiplier in the formula
`Reach × Impact × Confidence / Effort`.

| Feature | Reach (1-10) | Impact (1-5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Top-10 IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly distribution | 8 | 3 | 95% | 0.20 | 114.0 |
| Unique User-Agent share and guard | 8 | 3 | 85% | 0.35 | 58.3 |
| Rich terminal output | 9 | 3 | 90% | 0.35 | 69.4 |
| JSON and CSV output | 8 | 4 | 95% | 0.50 | 60.8 |
| Malformed input and exit codes | 9 | 5 | 90% | 0.50 | 81.0 |
| Gzip input | 5 | 2 | 80% | 0.25 | 32.0 |

Dependency order overrides raw RICE where required: the parser precedes every
metric even when small metric increments score higher. Within each dependency
level, the implementation order follows descending RICE.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Code is typed and runs on Python 3.11 without errors.
- [ ] Unit tests pass with at least 90% line coverage for product modules.
- [ ] CLI integration and golden-output tests pass where applicable.
- [ ] Ruff and mypy checks pass.
- [ ] The full 1 GB reference benchmark completes in under 30 seconds on the declared laptop profile.
- [ ] No known Critical or High security issue remains.
- [ ] User-facing and implementation documentation is current.
- [ ] The exact release candidate has been independently reviewed in its designated review session.

## 13. MVP Kill Criteria

Re-scope or stop the MVP if, after profiling and one focused optimization pass,
the approved Python design cannot process the fixed 1 GB benchmark below 30
seconds, cannot keep memory bounded under the declared cardinality ceiling, or
cannot parse the supported combined format reliably. Do not solve those failures
by adding a database, server, or distributed architecture.

