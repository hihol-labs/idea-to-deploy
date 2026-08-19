# Strategic Plan: Nginx Stream Report

## 1. Product Idea

Nginx Stream Report is a local, installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four operational views in one pass: the ten busiest client IPs, the ten URLs with the most 4xx/5xx responses, the percentage of valid requests occurring in each clock hour, and the share of unique User-Agent values. The default presentation is colored terminal text; JSON and CSV modes make the same results usable in shell pipelines.

The product is intentionally local and stateless. It has no authentication, database, HTTP API, background service, cloud dependency, or Kubernetes deployment. The initial performance objective is to process a 1 GB representative log in under 30 seconds on the agreed laptop benchmark.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Responds to incidents and traffic anomalies | Needs a useful first-pass view without waiting for a dashboard or uploading sensitive logs | Runs one local command and immediately sees traffic sources, error URLs, hourly shape, and User-Agent diversity |
| Platform engineer | Operates shared nginx ingress or reverse proxies | Existing observability platforms can be unavailable, expensive, or excessive for an ad-hoc file | Uses a zero-service, pip-installable tool on files or stdin |
| DevOps engineer | Builds operational scripts and CI jobs | Human-oriented analyzers are difficult to compose reliably | Selects stable JSON or normalized CSV output and documented exit codes |

## 3. Competitive Analysis

| Alternative | What it does well | Weakness for this use case | Nginx Stream Report distinction |
|---|---|---|---|
| GoAccess | Mature real-time terminal and HTML nginx analytics | Larger feature surface and interactive UI than a four-metric pipeline tool needs | Small, deterministic report contract with native JSON/CSV and pip installation |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, retention, search, and dashboards | Requires multiple services, storage, configuration, and operating cost | No services or persistence; useful immediately on a local log |
| AWStats | Established historical web-log reporting | Report-generation workflow and legacy presentation are less suited to one-off pipelines | Streaming CLI designed for terminal and automation use |
| `grep`/`awk`/`sort`/`uniq` | Ubiquitous, flexible, and zero-install on many systems | Correct parsing, error handling, multi-metric aggregation, and portable structured output require bespoke pipelines | One tested command with explicit semantics and one-pass aggregation |

## 4. Unique Value Proposition

Get the four nginx incident-triage metrics that matter from a large local log in one pip-installed command, with no service to run and stable text, JSON, or CSV output.

## 5. Business Model

The project is open source and costs $0 to use. The MVP has no paid tier, telemetry, hosted service, or monetization requirement. Success is measured by utility, reproducibility, and adoption rather than revenue. Community contributions and maintainership are the operating model; any future sponsorship would remain outside the MVP and must not introduce a cloud dependency into the local CLI.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved runtime with broad workstation availability and adequate streaming performance |
| CLI | Click | Stable option parsing, usage errors, stdin/file handling, and exit behavior |
| Terminal presentation | Rich | Colored tables and automatic terminal capability handling |
| Domain models | Standard-library `dataclasses` | Typed, lightweight result and record contracts without another runtime dependency |
| Parsing and aggregation | Python standard library | Buffered input, regular expressions/string scanning, counters, JSON, CSV, timestamps |
| Packaging | `pyproject.toml` with pip entry point | Modern, installable CLI distribution |
| Quality | pytest, coverage, Ruff, mypy | Fast local feedback for correctness, style, and types |

See `PROJECT_ARCHITECTURE.md` for component boundaries and `PRD.md` for externally visible behavior.

## 7. Timeline

| Block | Stage | Deliverable |
|---|---|---|
| Saturday morning | Runway and contracts | Package skeleton, CLI surface, fixtures, output schemas, and benchmark definition |
| Saturday afternoon | Core processing | Streaming parser and exact bounded aggregations for all four metrics |
| Sunday morning | Presentations | Rich terminal, JSON, CSV, warnings, and complete exit-code behavior |
| Sunday afternoon | Assurance and release | Tests, 1 GB benchmark, documentation, wheel build, and local pip smoke test |

The one-weekend target assumes one experienced Python engineer and no scope expansion.

## 8. KPIs

| Metric | Release target | Month 1 target | Month 3 target |
|---|---:|---:|---:|
| Representative 1 GB processing time on the recorded laptop profile | < 30 s | < 30 s | < 25 s or documented hardware limit |
| Peak resident memory on normal-cardinality 1 GB fixture | < 512 MiB | < 512 MiB | < 384 MiB |
| Correctness suite for output and exit contracts | 100% pass | 100% pass on every release | 100% pass on every release |
| Core-module line coverage | >= 90% | >= 90% | >= 92% |
| Time from installation to first report | < 30 s, excluding download | < 30 s | < 20 s |
| Confirmed external users | n/a | 5 | 25 |

Performance claims are accepted only with a recorded fixture description, hardware profile, command, elapsed time, and peak RSS.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined-log grammar | Medium | High | State the exact accepted grammar, count malformed lines, test common escaping, and make custom formats explicitly out of scope for MVP |
| Exact unique tracking consumes excessive memory on adversarial cardinality | Medium | High | Enforce a configurable per-dimension unique-key ceiling and exit with code 4 instead of degrading silently |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark from the parser milestone, use buffered binary iteration and a precompiled parser, profile before optimizing, and avoid per-line object retention |
| CSV multi-section output is interpreted inconsistently | Low | Medium | Use one normalized schema with a `section` discriminator and golden-file tests |
| Malformed or mixed logs lead to misleading partial results | Medium | High | Report skipped-line counts, distinguish partial success from no valid input, and document exit code 3 |
| Weekend scope expands toward dashboards, storage, or custom parsers | Medium | Medium | Enforce MoSCoW scope and the explicit Won't list below |

## 10. Budget

| Item | One-time | Monthly | Comment |
|---|---:|---:|---|
| Runtime and libraries | $0 | $0 | Python and dependencies are open source |
| Development tools and CI | $0 | $0 | Local tools and free open-source/repository allowances only |
| Hosting, database, cloud, Kubernetes | $0 | $0 | Not used by architecture |
| Distribution | $0 | $0 | Build an installable wheel; public index publication is optional and has no required fee |
| Labor | One weekend | $0 cash budget | Constrained delivery effort, not a purchased service |

Total approved cash budget: **$0**.

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream a file or stdin without loading the full log | **Must** | Core value and prerequisite for the 1 GB target |
| Top-10 client IPs | **Must** | Required incident-triage metric |
| Top-10 URLs by combined 4xx/5xx count | **Must** | Required error-hotspot metric |
| Hourly request distribution as percentages | **Must** | Required traffic-shape metric |
| Unique User-Agent share | **Must** | Required client-diversity metric |
| Colored terminal report | **Must** | Approved default user experience |
| JSON and normalized CSV modes | **Must** | Required pipeline interfaces |
| Stable warnings and exit codes, including cardinality exhaustion | **Must** | Prevents silent automation failures and unsafe memory growth |
| Gzip-compressed input | **Should** | Common operational convenience, but shell decompression is an MVP fallback |
| `--top N` override | **Should** | Useful generalization while top 10 remains the default |
| `--no-color` terminal override | **Could** | Helpful for unusual terminals; redirection already suppresses styling |
| Custom nginx `log_format` grammar | **Won't** | Too broad for a one-weekend parser contract |
| Authentication, database, HTTP API, server, cloud, or Kubernetes | **Won't** | Conflicts with the approved local stateless product boundary |

### RICE Scoring (Must and Should)

Confidence is expressed as a decimal in the calculation.

| Feature | Reach (1-10) | Impact (1-5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin + parser | 10 | 5 | 90% | 1.0 | 45.0 |
| Top-10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top-10 error URLs | 9 | 5 | 95% | 0.35 | 122.1 |
| Hourly percentage distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Colored terminal report | 9 | 3 | 95% | 0.35 | 73.3 |
| Unique User-Agent share | 7 | 4 | 85% | 0.40 | 59.5 |
| JSON output | 8 | 4 | 95% | 0.30 | 101.3 |
| CSV output | 7 | 3 | 90% | 0.30 | 63.0 |
| Warnings and exit-code contract | 10 | 5 | 95% | 0.50 | 95.0 |
| Gzip input | 5 | 2 | 90% | 0.20 | 45.0 |
| `--top N` override | 4 | 2 | 85% | 0.15 | 45.3 |

Dependency order overrides raw RICE where a metric depends on parsing or an output depends on aggregation. `IMPLEMENTATION_PLAN.md` records the executable order.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md` and architecture contracts.
- [ ] Code is compatible with Python 3.11 and the wheel builds without errors.
- [ ] Unit tests pass and core-module line coverage is at least 90%.
- [ ] Integration and golden-output tests pass where applicable.
- [ ] Static checks (Ruff and mypy) pass.
- [ ] Review is accepted under the repository's current Idea to Deploy verification contract.
- [ ] User documentation and CLI help are updated.
- [ ] No known Critical or High security issue remains.
- [ ] The exact staged candidate passes the current machine oracle and risk-tier checker with a revalidated adjudication receipt.
- [ ] The built wheel is installed in a clean local environment and all output modes receive a manual smoke test.
- [ ] Performance-sensitive changes meet the 1 GB target or carry explicit benchmark evidence explaining the exception.

## 13. Release and Kill Criteria

Release the MVP only if all P0 acceptance criteria pass, the installable wheel smoke test succeeds, exact output schemas remain stable, and the recorded 1 GB benchmark is under 30 seconds. Stop or redesign the MVP if profiling shows that the approved exact metrics cannot meet 30 seconds in Python 3.11 on the reference laptop, or if normal-cardinality logs exceed 512 MiB despite targeted optimization. Do not evade either criterion with sampling or approximate counts without a new product decision.
