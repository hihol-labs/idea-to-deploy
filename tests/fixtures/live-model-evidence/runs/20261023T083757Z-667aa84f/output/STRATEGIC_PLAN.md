# Strategic Plan: Nginx Stream Analyzer

## 1. Product Idea

Nginx Stream Analyzer is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. It produces readable colored terminal output by default and machine-readable JSON or CSV for pipelines.

The MVP is deliberately narrow: one process, bounded memory, no persistent state, and no network service. Delivery is constrained to one weekend with a $0 operating and tooling budget.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| Incident responder | On-call SRE | Needs a fast first view of a large log without uploading it | Runs one local command and gets the highest-signal aggregates |
| Platform engineer | DevOps engineer | Needs repeatable summaries inside shell pipelines | Uses stable JSON/CSV schemas and documented exit codes |
| Service owner | Backend engineer | Needs to identify noisy clients and failing routes | Sees top IPs and error URLs without deploying an observability stack |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader configuration and UI surface than a four-metric pipeline tool | Smaller contract, deterministic exports, Python-native installation |
| Logstash + Elastic + Kibana | Powerful ingestion, storage, search, and dashboards | Infrastructure, memory, setup, and operations are disproportionate for a local one-off analysis | Zero services and zero persistent infrastructure |
| AWStats | Established historical web analytics | Oriented toward generated reports and persistent history rather than ad-hoc streaming | Immediate terminal and pipeline output from stdin or a file |
| grep/awk/sort | Ubiquitous and composable | Fragile parsing, repeated scans, locale differences, and no unified schema | One tested parser, one pass, stable metric definitions |

## 4. Unique Value Proposition

Analyze a gigabyte of nginx access logs locally in one command, with useful human output and stable pipeline formats, without deploying or operating anything.

## 5. Business Model

The project is open source and free to use. There is no paid tier, telemetry, hosted service, CAC, or LTV target. Value is measured by adoption, correctness, and time saved during incident triage. Contributions and package distribution use free public tooling.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required platform; broad availability and mature text-processing support |
| CLI | Click | Predictable option validation, help text, and exit handling |
| Terminal rendering | Rich | Accessible colored tables with automatic terminal capability handling |
| Domain models | `dataclasses` | Lightweight typed records with no model framework overhead |
| Packaging | `pyproject.toml` + pip | Standard installable CLI distribution |
| Testing | pytest | Fast unit, integration, and CLI contract tests |

## 7. Timeline

| Period | Stage | Result |
|---|---|---|
| Friday evening | Contracts and parser skeleton | Package, CLI, fixtures, and log-line parsing contract |
| Saturday morning | Streaming aggregation | All four required metrics in one pass with bounded-memory safeguards |
| Saturday afternoon | Output formats | Rich, JSON, and CSV output contracts implemented and tested |
| Sunday morning | Robustness and performance | Malformed-input policy, exit codes, and 1 GB benchmark verified |
| Sunday afternoon | Packaging and documentation | pip-installable release candidate and operator documentation |

## 8. KPIs

| Metric | MVP / 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| Processing time for 1 GB on reference laptop | < 30 s | < 25 s | < 20 s if profiling justifies it |
| Valid-line parsing accuracy on supported format corpus | 100% | 100% | 100% |
| Peak RSS on 1 GB bounded-cardinality benchmark | < 256 MiB | < 192 MiB | < 160 MiB |
| P0 acceptance tests passing | 100% | 100% | 100% |
| Unhandled tracebacks for documented CLI inputs | 0 | 0 | 0 |

Benchmark results must name the machine, storage type, Python version, input hash, and command; the performance target is not claimed until measured.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Unbounded distinct IP, URL, or User-Agent values exhaust memory | Medium | High | Configurable cardinality caps; fail closed with exit code 4 and no misleading partial report |
| nginx format variants parse incorrectly | Medium | High | Support one explicit default combined format in MVP; reject or count malformed lines; fixture corpus documents boundaries |
| Python misses the 1 GB / 30 s target | Medium | High | Single pass, compiled regex, low-allocation records, buffered I/O, and an early benchmark gate |
| CSV representation is ambiguous for multiple report sections | Medium | Medium | Define one long-form schema with a `metric` discriminator and stable columns |
| Color/control sequences pollute redirected output | Low | Medium | Enable color only for terminal text on a TTY; JSON and CSV never contain ANSI escapes |
| Exact unique User-Agent counting conflicts with bounded memory | Medium | High | Enforce an explicit cap and return exit code 4 rather than silently approximate in the MVP |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and pytest are open source |
| Development tools | $0 | Local editor, Git, and public CI free tier if used |
| Hosting and operations | $0 | Local CLI; no server or cloud resources |
| Package publication | $0 | Public package index |
| Total | **$0** | Labor is the one-weekend delivery constraint, not a cash expense |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream from file and stdin | Must | Required for local use and shell pipelines |
| Parse documented nginx combined log format | Must | All metrics depend on reliable event extraction |
| Top-10 client IPs | Must | Core incident-triage signal |
| Top-10 4xx/5xx URLs | Must | Core error-localization signal |
| Hourly request distribution | Must | Required traffic-shape signal |
| Unique User-Agent share | Must | Required client-diversity signal |
| Colored terminal output | Must | Default user experience in the brief |
| JSON and CSV outputs | Must | Required automation interface |
| Cardinality guard and exit code 4 | Must | Prevents uncontrolled memory use without corrupting results |
| gzip input | Should | Common log archival format, but shell decompression is an MVP workaround |
| Custom nginx log formats | Could | Expands reach but threatens weekend scope and parser certainty |
| Approximate cardinality mode | Could | Could handle hostile cardinality while retaining an estimate |
| Database, HTTP API, authentication, server, cloud, Kubernetes | Won't | Contradicts the local stateless CLI product and adds no MVP value |

### RICE Scoring (Must + Should)

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Parse format + stream file/stdin | 10 | 5 | 95% | 0.7 | 67.9 |
| Core top-10 aggregations | 10 | 5 | 90% | 0.8 | 56.3 |
| Hourly distribution | 9 | 4 | 95% | 0.3 | 114.0 |
| Unique User-Agent share + guard | 9 | 4 | 85% | 0.5 | 61.2 |
| Colored terminal output | 8 | 3 | 95% | 0.3 | 76.0 |
| JSON and CSV outputs | 8 | 4 | 95% | 0.6 | 50.7 |
| gzip input | 5 | 2 | 80% | 0.4 | 20.0 |

RICE informs feature order after dependencies: the parser and streaming core precede every aggregation even where a dependent metric has a higher arithmetic score. See `IMPLEMENTATION_PLAN.md` for the dependency-adjusted sequence.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and edge cases match `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Code is typed and imports on Python 3.11 without errors.
- [ ] Unit and integration tests pass with at least 90% line coverage for product modules.
- [ ] CLI acceptance tests pass for terminal, JSON, CSV, stdin, file input, malformed data, and exit codes `0/1/2/3/4`.
- [ ] The 1 GB benchmark completes in under 30 seconds on the named reference laptop.
- [ ] Packaging installs in a clean virtual environment and exposes the documented command.
- [ ] Documentation is current and no Critical or High security issue is known.
- [ ] A human review has accepted the final implementation candidate; no deployment is required for this local CLI.

## 13. Kill Criteria

- Stop the MVP and reconsider the implementation language if an optimized, profiled Python implementation cannot process the fixed 1 GB corpus within 30 seconds on the reference laptop.
- Do not release if supported-format fixtures yield incorrect aggregates or if machine formats are unstable.
- Do not claim bounded-memory behavior if cardinality exhaustion can produce a plausible-looking partial success report.

