# Strategic Plan: Nginx Stream Analytics CLI

## 1. Product Idea

A local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads an nginx access-log stream once and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. It is designed for fast incident triage and pipeline use without deploying or operating a service.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call responder | SRE / DevOps engineer | Needs a quick traffic and error overview during an incident | One command produces bounded, actionable summaries |
| Platform engineer | CI/automation owner | Needs stable machine-readable output | `--json` and `--csv` provide deterministic pipeline formats |
| Application operator | Service owner | Cannot justify a monitoring stack for an ad-hoc log file | Local, stateless, zero-infrastructure analysis |

## 3. Problem and Value Proposition

Existing choices are either interactive dashboards requiring setup or flexible shell primitives requiring repeated, error-prone commands. The product's unique value proposition is: **a zero-configuration, single-pass nginx log summary that is human-friendly by default and pipeline-safe on demand.**

## 4. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI and configuration surface than a focused pipeline command | Smaller contract with explicit JSON/CSV output |
| Logstash + Elastic + Kibana | Powerful ingestion, search, and dashboards | Operational cost, persistent services, and excessive setup | No server, database, or cloud dependency |
| AWStats | Established web-log reporting | Batch-oriented and dated workflow; generates persistent reports | Stream-first local execution and modern CLI ergonomics |
| grep/awk/sort | Ubiquitous and composable | Multiple passes, quoting pitfalls, inconsistent parsing and output | Tested parser and all requested metrics in one pass |

## 5. Business Model and Budget

This is a free, open-source utility. There is no paid tier, telemetry, hosted component, or revenue target. Success is measured by utility, correctness, and adoption rather than LTV or CAC.

| Item | Cost | Note |
|---|---:|---|
| Runtime and hosting | $0 | Runs on the user's laptop; no hosted infrastructure |
| Dependencies | $0 | Python, Click, Rich, and standard-library components are open source |
| Development | $0 cash | One-weekend contributor effort |
| Distribution | $0 | Public Python package index and source repository |

## 6. Technology Strategy

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required stack; broadly available to operators |
| CLI | Click | Predictable option parsing, help text, and exit handling |
| Terminal presentation | Rich | Colored, readable tables with terminal capability handling |
| Domain records | `dataclasses` | Lightweight typed records without a validation framework |
| Parsing and aggregation | Python standard library | Keeps dependencies and memory overhead small |
| Packaging | pip-installable `pyproject.toml` package | Standard installation and console entry point |

## 7. Delivery Timeline

| Window | Outcome |
|---|---|
| Saturday morning | Package skeleton, CLI contract, streaming parser |
| Saturday afternoon | Aggregators and deterministic result model |
| Sunday morning | Text, JSON, and CSV renderers; error semantics |
| Sunday afternoon | Tests, 1 GB performance benchmark, packaging, documentation |

## 8. KPIs

| Metric | Release target | Measurement |
|---|---:|---|
| Performance | 1 GB in under 30 seconds on the reference laptop | Reproducible benchmark with a representative local log |
| Memory behavior | Does not scale with request count, except explicitly bounded distinct-value sets | Peak RSS during benchmark and cardinality-limit tests |
| Correctness | 100% pass rate for parser, aggregation, renderer, and CLI contract tests | Automated test suite |
| Pipeline stability | JSON and CSV parse successfully and contain no ANSI escape sequences | Machine-format integration tests |
| Installation | Clean Python 3.11 environment installs and exposes the command | Package smoke test |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats vary from the supported combined/common grammar | High | High | Declare accepted grammar, count malformed lines, and fail if no valid records exist |
| Exact unique User-Agent tracking can exhaust memory on adversarial cardinality | Medium | High | Configurable hard limit and exit code 4 rather than silently approximating |
| Python misses the 1 GB/30 s target | Medium | High | Byte-oriented single-pass benchmark, profile before optimization, avoid per-line regex recompilation |
| Locale/time-zone ambiguity changes hourly buckets | Medium | Medium | Use the timestamp's explicit offset and document bucket semantics |
| Color corrupts redirected output | Low | Medium | Enable color only for an interactive terminal; machine formats never emit ANSI |
| CSV representation of multiple report sections is misunderstood | Medium | Medium | Use a normalized row schema with a `section` discriminator |

## 10. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Streaming nginx parsing from a file or stdin | Must | All analysis depends on bounded, one-pass input |
| Top 10 client IPs | Must | Core traffic triage requirement |
| Top 10 error URLs for 4xx/5xx | Must | Core failure triage requirement |
| Hourly request percentages | Must | Required temporal distribution, normalized for comparison |
| Unique User-Agent share with exhaustion guard | Must | Required diversity metric with safe failure behavior |
| Colored terminal report | Must | Default human-facing output contract |
| JSON and CSV renderers | Must | Required pipeline integration contract |
| Configurable top-N and cardinality limit | Should | Useful operational control while preserving defaults |
| gzip input | Could | Common archive format but not required for the first weekend |
| Authentication, database, HTTP API, server, cloud, Kubernetes | Won't | Explicitly outside the local stateless CLI scope |

### RICE Scoring (Must and Should)

Scores use `(Reach × Impact × Confidence) / effort` and order implementation within dependency constraints.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and input | 10 | 5 | 90% | 0.75 | 60.0 |
| Default terminal report | 10 | 4 | 90% | 0.50 | 72.0 |
| Top IP aggregation | 9 | 4 | 95% | 0.25 | 136.8 |
| Error URL aggregation | 9 | 5 | 95% | 0.25 | 171.0 |
| Hourly request percentages | 8 | 4 | 95% | 0.25 | 121.6 |
| Unique User-Agent share and guard | 8 | 4 | 85% | 0.50 | 54.4 |
| JSON and CSV output | 8 | 4 | 90% | 0.50 | 57.6 |
| Configurable top-N/cardinality limit | 5 | 2 | 80% | 0.25 | 32.0 |

## 11. Definition of Done

A feature is done when:

- [ ] Its behavior and edge cases match `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 static checks and the full automated test suite pass.
- [ ] P0 acceptance criteria have automated evidence.
- [ ] JSON and CSV remain machine-parseable and free of terminal styling.
- [ ] No known critical or high-severity security issue remains.
- [ ] User-facing and implementation documentation is current.
- [ ] The packaged CLI is manually smoke-tested in a clean environment.

The MVP is complete only when the reference 1 GB benchmark finishes in under 30 seconds, all exit codes `0/1/2/3/4` are exercised, and no P0 requirement is open.

