# Strategic Plan: Nginx Log Insights CLI

## 1. Product Idea

Nginx Log Insights CLI is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It streams nginx access logs without retaining event data and reports the top client IPs, the URLs producing the most 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent values. Human-readable colored terminal output is the default; stable JSON and CSV formats support automation.

The MVP is deliberately narrow: no authentication, database, HTTP service, cloud dependency, or Kubernetes deployment. A one-weekend implementation must remain free and open source while processing a 1 GB representative log in under 30 seconds on a reference laptop.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call operator | SRE responding to an incident | Needs a useful traffic and error snapshot without provisioning a stack | One local command produces four operational summaries |
| Service owner | DevOps engineer validating a deployment | Needs pipeline-friendly metrics from archived or streamed nginx logs | Deterministic JSON/CSV output and explicit exit codes |
| Platform engineer | Maintainer of lightweight runbooks | Heavy observability platforms are excessive for one-off log triage | Pip-installable, stateless, zero-service CLI |

## 3. Competitive Analysis

| Alternative | Strength | Limitation for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, rich interactive reports | Broader interface and configuration surface than the four required summaries | Purpose-built command and stable automation schemas |
| Logstash + Elastic + Kibana | Powerful ingestion, storage, search, and visualization | Requires services, storage, setup time, and operational cost | No server or persistence; immediate local result |
| AWStats | Established historical web analytics | Batch-oriented and report-heavy; not optimized for ephemeral CLI pipelines | Streaming local analysis with JSON/CSV output |
| grep/awk pipelines | Ubiquitous and dependency-light | Fragile parsing, inconsistent metrics, and no shared output contract | Tested parser, named metrics, and reliable exit semantics |

## 4. Unique Value Proposition

Get the four nginx incident-triage summaries an SRE needs from a large log in one local, scriptable command—without deploying or operating an analytics stack.

## 5. Business Model and Licensing

The project is a free, open-source developer utility. There are no paid tiers, hosted services, telemetry, or user accounts. Value is measured by adoption, reliability, and time saved during operations rather than revenue, LTV, or CAC. A permissive OSI-approved license should be selected before the first public release.

## 6. Technology Stack

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Approved target with broad laptop availability |
| CLI | Click | Mature argument validation, help, and exit handling |
| Terminal rendering | Rich | Colored, readable tables with terminal capability detection |
| Domain models | `dataclasses` | Lightweight typed records without validation-framework overhead |
| Packaging | `pyproject.toml` + pip | Standard installable CLI distribution |
| Tests | pytest | Fast unit and subprocess-level CLI verification |

See `PROJECT_ARCHITECTURE.md` for module boundaries and the complete CLI contract.

## 7. Timeline

| Window | Stage | Outcome |
|---|---|---|
| Saturday morning | Packaging, parser, and aggregation core | Logs stream into bounded top-10/hour counters and guarded User-Agent cardinality |
| Saturday afternoon | CLI and serializers | Terminal, JSON, and CSV contracts work end to end |
| Sunday morning | Correctness and performance tests | Fixtures, malformed-input behavior, and 1 GB benchmark are repeatable |
| Sunday afternoon | Documentation and release hardening | pip installation, examples, license, and release checklist are ready |

## 8. KPIs

| Metric | Release target | First month target | Three-month target |
|---|---:|---:|---:|
| Representative 1 GB processing time | <30 seconds | p95 <30 seconds on reference laptop | No regression above 30 seconds |
| Peak memory on benchmark | <512 MB | <512 MB | <512 MB |
| Golden-fixture metric accuracy | 100% | 100% | 100% |
| Supported output schema tests | 3/3 formats | 3/3 | 3/3 |
| Invalid-line diagnostics | Line number and reason | <1% ambiguous reports | <1% ambiguous reports |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Python parsing misses the 1 GB/30 s target | Medium | High | Compile one regex, stream bytes/text once, avoid per-line object churn, benchmark early |
| Real nginx formats differ from the supported combined format | High | Medium | State the accepted format, include actionable parse diagnostics, defer configurable formats |
| Exact unique User-Agent storage exhausts memory | Medium | High | Enforce a configurable hard cardinality limit and terminate with exit code 4 |
| CSV representation is ambiguous for four report sections | Medium | Medium | Use a documented long-form schema with a `section` discriminator |
| ANSI color corrupts redirected output | Low | Medium | Enable color only for terminal output and support explicit `--color/--no-color` |
| Malformed input silently distorts percentages | Medium | High | Count invalid lines, expose them in metadata, and provide strict mode with exit code 3 |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and pytest are open source |
| Hosting and infrastructure | $0 | Local CLI; no service is deployed |
| Database and observability | $0 | Neither is part of the product |
| Development | $0 cash budget | One-weekend maintainer effort |
| Total | $0 | Constraint satisfied |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Streaming combined-log parsing from file or stdin | Must | All reports depend on valid streaming input |
| Top-10 client IPs | Must | Core incident-triage requirement |
| Top-10 URLs by 4xx/5xx count | Must | Core error-localization requirement |
| Hourly request distribution percentages | Must | Core traffic-shape requirement |
| Unique User-Agent share with cardinality guard | Must | Core client-diversity requirement and memory safety boundary |
| Colored terminal renderer | Must | Required default experience |
| JSON and CSV renderers | Must | Required pipeline compatibility |
| Gzip-compressed input | Should | Common for rotated nginx logs but not required for the first usable release |
| Configurable log format | Could | Broadens nginx compatibility after the fixed parser is stable |
| Approximate distinct counting | Could | Could reduce memory but changes exactness semantics |
| Authentication, database, HTTP API, server, cloud, Kubernetes | Won't | Explicitly outside the local stateless CLI scope |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence represented as a decimal. Equal-score work is dependency-ordered in `IMPLEMENTATION_PLAN.md`.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Streaming combined-log parsing from file or stdin | 10 | 5 | 90% | 1.0 | 45.0 |
| Top-10 client IPs | 9 | 4 | 95% | 0.3 | 114.0 |
| Top-10 URLs by 4xx/5xx count | 10 | 5 | 95% | 0.5 | 95.0 |
| Hourly request distribution percentages | 8 | 4 | 95% | 0.3 | 101.3 |
| Unique User-Agent share with cardinality guard | 8 | 4 | 80% | 0.5 | 51.2 |
| Colored terminal renderer | 8 | 3 | 90% | 0.4 | 54.0 |
| JSON and CSV renderers | 9 | 4 | 90% | 0.6 | 54.0 |
| Gzip-compressed input | 5 | 2 | 80% | 0.4 | 20.0 |

## 12. Definition of Done

A release feature is done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Python 3.11 code passes formatting, linting, and type checks selected by the implementation team.
- [ ] Unit and CLI integration tests pass with at least 90% coverage of product modules.
- [ ] Terminal, JSON, and CSV golden-output tests pass where applicable.
- [ ] The 1 GB reference benchmark completes in under 30 seconds on the documented laptop profile.
- [ ] No known Critical or High security issue remains.
- [ ] User-facing installation and CLI documentation are current.
- [ ] A clean virtual environment can install the package with pip and invoke the console command.

## 13. Kill Criteria

Re-scope or stop the MVP if a representative 1 GB combined log cannot meet the 30-second target after parser profiling, or if exact User-Agent cardinality cannot stay within the documented memory ceiling without making exit code 4 routine. Do not expand into a service or persistence layer to rescue the concept; that would be a different product.
