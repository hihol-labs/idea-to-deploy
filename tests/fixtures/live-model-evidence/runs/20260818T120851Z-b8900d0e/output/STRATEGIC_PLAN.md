# Strategic Plan: Nginx Insights CLI

## 1. Product Idea

Nginx Insights CLI is a local, open-source Python 3.11 command-line tool for
DevOps and SRE engineers. It reads nginx access logs as a stream and produces
four immediately useful operational summaries: the top 10 client IPs, the top
10 URLs returning 4xx/5xx responses, the percentage distribution of requests
by hour, and the share of unique User-Agent values. Rich terminal output is the
default; JSON and CSV make the same results usable in pipelines.

The MVP is deliberately narrow: no service to operate, no retained data, no
account model, and no network dependency. See `PROJECT_ARCHITECTURE.md` for the
runtime design and `PRD.md` for the behavioral contract.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a fast view of noisy clients and failing routes without uploading sensitive logs | One local command returns the four incident-oriented summaries |
| Platform engineer | Maintains nginx fleets and shell pipelines | Ad hoc grep/awk chains are fragile and hard to reuse | Stable JSON/CSV schemas and documented exit codes |
| Application operator | Runs a small service without an observability stack | Full log platforms cost time and infrastructure | A zero-service, pip-installable analysis tool |

## 3. Competitive Analysis

| Alternative | What it does well | Weakness for this use case | Nginx Insights distinction |
|---|---|---|---|
| GoAccess | Mature interactive and HTML nginx analytics | Broader UI and configuration surface than a four-metric pipeline tool | Minimal command contract and first-class JSON/CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, retention, dashboards | Requires multiple services, storage, setup, and ongoing operations | Stateless local execution with no infrastructure |
| AWStats | Established periodic web-log reporting | Report-oriented, dated workflow; not optimized for one-shot CLI pipelines | Immediate terminal output and modern structured formats |
| grep/awk/sort/uniq | Available almost everywhere and composable | Parsing is brittle; multiple passes and locale differences make results inconsistent | One parser, one pass, stable semantics, tested output contracts |

## 4. Unique Value Proposition

Operationally useful nginx triage metrics from a gigabyte log in one local,
pipeline-friendly command—without deploying or maintaining an observability
stack.

## 5. Business Model

The project is free and open source. There are no paid tiers, hosted services,
telemetry, or per-user costs. Value is measured in engineer time saved and in
adoption, not revenue; CAC and LTV are therefore not meaningful MVP metrics.
The maintenance model is community contributions plus bounded maintainer time.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, broadly available, productive for a weekend build |
| CLI | Click | Stable argument parsing, validation, help, and exit handling |
| Terminal presentation | Rich | Accessible tables, color control, and terminal detection |
| Domain models | Standard-library dataclasses | Explicit typed records without a validation-framework dependency |
| Parsing/aggregation | Python standard library | Streaming iteration, counters, timestamps, CSV, and JSON need no extra runtime package |
| Packaging | pip-compatible `pyproject.toml` | Standard installation and console entry point |
| Testing | pytest | Fast unit/integration tests and easy fixture parametrization |

## 7. Timeline

| Delivery block | Scope | Result |
|---|---|---|
| Saturday morning | Package skeleton, domain model, parser | Combined-log records stream from files/stdin |
| Saturday afternoon | Aggregation and limits | All four metrics computed in one pass |
| Sunday morning | terminal, JSON, CSV, CLI contract | Stable user-facing outputs and exit codes |
| Sunday afternoon | tests, 1 GB benchmark, docs, packaging | Release candidate ready for local pip install |

Total delivery budget is one weekend, approximately 14–16 focused hours.

## 8. KPIs

| Metric | MVP / first month target | Three-month target | Six-month target |
|---|---:|---:|---:|
| Performance on a representative 1 GB combined log | under 30 seconds on the reference laptop | no regression above 10% | no regression above 10% |
| Peak resident memory, excluding exact User-Agent set growth | under 150 MB | under 150 MB | under 150 MB |
| Correctness fixture pass rate | 100% | 100% | 100% |
| Supported stable output formats | 3 | 3 | 3+ |
| Actionable user-reported correctness defects | 0 open critical | 0 open critical | 0 open critical |

The benchmark report must name laptop CPU, RAM, OS, Python version, input hash,
file size, elapsed time, and peak RSS so the 30-second claim is reproducible.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from Combined Log Format | High | High | Make Combined Log Format the explicit MVP input contract; reject or count malformed records predictably |
| Exact unique User-Agent cardinality consumes excessive memory | Medium | High | Enforce a configurable hard cardinality limit and exit with code 4 before uncontrolled growth |
| Python misses the 1 GB / 30 second target | Medium | High | Benchmark early; keep one pass, avoid per-line regex recompilation and unnecessary allocations |
| Terminal and structured outputs drift semantically | Medium | Medium | Render all formats from one immutable result object and use golden fixtures |
| “Hourly distribution” is interpreted inconsistently | Medium | Medium | Freeze the percentage formula and use the timestamp offset encoded in each valid log line |
| Sensitive log data leaks | Low | High | Process locally, perform no network I/O or telemetry, and retain no input |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime libraries | $0 | Open-source Python, Click, and Rich |
| Infrastructure | $0 | Local CLI; no hosted runtime or database |
| Distribution | $0 | Source repository and local `pip install .`; public index publication is optional later |
| Labor cash budget | $0 | One-weekend owner contribution |
| Ongoing service cost | $0/month | No server, storage, telemetry, or third-party API |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream Combined Log Format from a file or stdin | **Must** | Foundation for local files and Unix pipelines |
| Top 10 request IPs | **Must** | Core incident-triage metric |
| Top 10 4xx/5xx URLs | **Must** | Core error-hotspot metric |
| Hourly request percentage distribution | **Must** | Required traffic-shape metric |
| Unique User-Agent share with exhaustion guard | **Must** | Required diversity metric with safe failure semantics |
| Rich colored terminal report | **Must** | Required default experience |
| JSON output | **Must** | Required machine-readable pipeline format |
| CSV output | **Must** | Required tabular pipeline format |
| Strict parsing mode and complete exit codes | **Should** | Improves automation and diagnostics; permissive default remains usable |
| Gzip input autodetection | **Could** | Convenient but not essential; shell decompression already works |
| Custom nginx `log_format` parser | **Could** | Broadens use cases but risks the weekend scope |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the local stateless CLI value proposition |

### RICE Scoring (Must and Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with Confidence expressed
as a decimal. Ties are resolved by dependency order.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Top 10 request IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top 10 error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly percentage distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Stream file/stdin input | 10 | 5 | 100% | 0.5 | 100.0 |
| JSON output | 8 | 4 | 95% | 0.35 | 86.9 |
| Unique User-Agent share and guard | 8 | 4 | 90% | 0.4 | 72.0 |
| Rich terminal report | 9 | 4 | 90% | 0.5 | 64.8 |
| Strict parsing and exit codes | 7 | 4 | 90% | 0.4 | 63.0 |
| CSV output | 6 | 3 | 90% | 0.35 | 46.3 |

Implementation respects the descending value signal while placing shared
parser and aggregation dependencies before their consumer features. The exact
sequence is in `IMPLEMENTATION_PLAN.md`.

## 12. Success and Kill Criteria

Proceed to an MVP release only if representative fixtures are exact across all
formats and the 1 GB benchmark completes under 30 seconds on the documented
reference laptop. Stop or redesign the parser if two focused optimization
passes still miss the time target by more than 20%. Remove or explicitly label
the unique User-Agent metric experimental if exact cardinality cannot be bounded
with the specified exhaustion behavior.

## Definition of Done

A feature is “Done” only when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Code is written for Python 3.11 and static checks complete without errors.
- [ ] Unit tests pass with at least 90% branch coverage in parser, aggregation, and output modules.
- [ ] CLI integration and golden-output tests pass for terminal, JSON, and CSV.
- [ ] The representative performance benchmark meets the documented target.
- [ ] Peer code review records no unresolved critical or high-severity issue.
- [ ] `README.md`, CLI help, and implementation guidance are consistent.
- [ ] A clean-environment `pip install .` and smoke run succeed locally.
