# Strategic Plan: Nginx Stream Insights

## 1. Product idea

Nginx Stream Insights is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the percentage of distinct User-Agent values. The default output is colored terminal text; JSON and CSV modes support pipelines. The MVP is a stateless, single-process utility delivered in one weekend with no paid services.

## 2. Target audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a useful traffic/error summary without uploading sensitive logs | One local command produces incident-oriented rankings and distributions |
| Platform engineer | DevOps owner of nginx fleets | Needs predictable machine-readable output for shell automation | Stable `--json` and `--csv` schemas with stdout/stderr separation |
| Systems administrator | Operator of a small deployment | Full observability stacks are too expensive or complex | Zero-service, pip-installable analysis with a $0 operating budget |

## 3. Competitive analysis

| Alternative | What it does | Weakness for this use case | Our difference |
|---|---|---|---|
| GoAccess | Rich real-time terminal/HTML web-log analytics | Broader UI and configuration surface than the four incident metrics require | Focused, script-friendly report with explicit JSON and CSV contracts |
| Logstash + Elasticsearch + Kibana | Ingests, stores, searches, and visualizes logs at scale | Requires services, storage, configuration, and operational ownership | Local one-shot streaming with no infrastructure or persistence |
| AWStats | Produces historical web analytics reports | Batch/report workflow and legacy operational model are less pipeline-friendly | Immediate CLI output and modern Python packaging |
| `grep`/`awk`/`sort` | Composable local text processing | Parsing, quoting, status filtering, and aggregation become brittle and non-portable | Tested nginx parsing and all four metrics in one stable command |

## 4. Unique value proposition

Get the four nginx incident metrics an operator needs from a large local log in one command, without deploying or paying for an observability stack.

## 5. Business model

The project is open source and free to use. There is no monetization in the MVP: price, CAC, and paid-service cost are all $0. Success is measured by adoption, correctness, and saved operator time rather than revenue. Community support and contributions are the sustainable operating model.

## 6. Technology stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Required, widely available, fast enough with streaming and bounded work per line |
| CLI | Click | Mature option parsing, help, exit codes, and testing support |
| Terminal output | Rich | Accessible colored tables with automatic non-TTY behavior |
| Domain models | `dataclasses` | Typed lightweight records without a validation framework |
| Packaging | pip-compatible `pyproject.toml` | Standard installation and console entry point |
| Tests | pytest + Click `CliRunner` | Fast unit and end-to-end CLI tests |

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Packaging, input, parser | Installable CLI parses common/combined nginx records and stdin |
| Saturday afternoon | Streaming aggregation | All four metrics computed with bounded per-record processing |
| Sunday morning | Renderers and UX | Rich, JSON, and CSV outputs with stable contracts |
| Sunday afternoon | Quality and performance | Tests, documentation, and 1 GB benchmark evidence |

## 8. KPIs

| Metric | Month 1 | Month 3 | Month 6 |
|---|---:|---:|---:|
| Correct results on golden fixtures | 100% | 100% | 100% |
| 1 GB processing time on reference laptop | <30 s | <30 s | <25 s |
| Peak memory on 1 GB representative log | <250 MB | <200 MB | <150 MB |
| Successful installs from a clean Python 3.11 environment | 95% | 98% | 99% |
| GitHub stars or equivalent adoption signal | 10 | 50 | 150 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined/common grammar | High | High | Document the supported grammar, count malformed lines, and add fixtures from representative variants |
| Exact unique-IP/User-Agent tracking exceeds memory on high-cardinality logs | Medium | High | Stream all records, document cardinality-driven memory, benchmark representative worst cases, and defer approximate counting unless evidence requires it |
| Python misses the 1 GB/30 s target | Medium | High | Avoid regex backtracking and per-line allocations; profile before changing architecture |
| CSV representation of multiple report sections confuses pipelines | Medium | Medium | Define one normalized row schema with `section`, `key`, `value`, and `rank` columns |
| Terminal colors corrupt redirected output | Low | Medium | Disable color automatically for non-TTY output and never color JSON/CSV |

## 10. Budget

| Item | One-time | Monthly | Comment |
|---|---:|---:|---|
| Development tools and libraries | $0 | $0 | Python, Click, Rich, and pytest are open source |
| Hosting and infrastructure | $0 | $0 | Local CLI; no server, cloud, or database |
| Distribution | $0 | $0 | Source repository and public package index have free tiers |
| Total | **$0** | **$0** | Labor is a one-weekend personal contribution |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream file input and stdin | **Must** | Required for local files and Unix pipelines without loading the file into memory |
| Parse documented nginx common/combined records and report malformed-line count | **Must** | Every metric depends on reliable parsing and observable failure handling |
| Top-10 client IPs | **Must** | Core incident metric |
| Top-10 4xx/5xx URLs | **Must** | Core error-triage metric |
| Hourly request distribution | **Must** | Core traffic-shape metric |
| Unique User-Agent share | **Must** | Core client-diversity metric |
| Colored Rich terminal report | **Must** | Required default user experience |
| JSON and CSV renderers | **Must** | Required pipeline interoperability |
| Configurable nginx log format | **Should** | Expands compatibility, but the documented standard formats can launch first |
| Configurable ranking limit | **Could** | Helpful polish; top 10 is the approved MVP behavior |
| Live refresh/tail dashboard | **Won't** | Adds stateful UI concerns beyond one-shot streaming analysis |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the local, stateless, $0 product boundary |

### RICE scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / person-days` and are planning estimates.

| Feature | Reach | Impact | Confidence | Effort (days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Rich terminal report | 9 | 4 | 90% | 0.25 | 129.60 |
| Streaming input + parser diagnostics | 10 | 5 | 90% | 0.40 | 112.50 |
| JSON and CSV renderers | 8 | 4 | 90% | 0.30 | 96.00 |
| Core four-metric aggregation | 10 | 5 | 90% | 0.50 | 90.00 |
| Configurable nginx log format | 5 | 3 | 60% | 0.50 | 18.00 |

Dependency constraints take precedence over raw RICE: parsing and aggregation must precede renderers. The Should item is scheduled after the complete MVP.

## 12. Definition of Done

A feature is Done when:

- [ ] Behavior and acceptance criteria in `PRD.md` are implemented.
- [ ] Python 3.11 type checks/lint checks and unit tests pass with at least 90% coverage of parser, aggregation, and renderers.
- [ ] CLI integration tests pass for terminal, JSON, CSV, stdin, malformed input, and exit codes.
- [ ] Code review passes with no unresolved critical findings.
- [ ] `README.md` and command help match actual behavior.
- [ ] No known Critical or High security issues remain.
- [ ] A representative 1 GB benchmark completes in under 30 seconds on the recorded reference laptop.
- [ ] Installation and the golden flow are manually verified in a clean virtual environment.

## 13. Strategic kill criteria

Re-scope or stop the MVP if a tested, profiled Python implementation cannot meet 1 GB in 30 seconds without violating correctness; standard combined logs cannot be parsed reliably; or exact high-cardinality metrics require unacceptable laptop memory. Do not introduce a server or paid infrastructure to rescue the local CLI proposition.

See `PRD.md` for behavioral requirements and `IMPLEMENTATION_PLAN.md` for delivery order.
