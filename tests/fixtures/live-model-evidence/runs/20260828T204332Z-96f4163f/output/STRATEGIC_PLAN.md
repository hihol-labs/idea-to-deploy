# Strategic Plan: nginx-insight

## 1. Product Summary

`nginx-insight` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four immediately actionable views: top-10 client IPs, top-10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Colored terminal output is the default; stable JSON and CSV outputs make the same report usable in pipelines.

The value proposition is intentionally narrow: answer common incident-triage questions from a large log file without deploying a service, storing logs, or learning a query platform.

## 2. Target Users

| Persona | Role | Pain | Resolution |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a useful traffic/error summary in minutes | One local command produces the four core views |
| Platform engineer | Maintains hosts and CI jobs | Cannot introduce a hosted log stack for an ad-hoc task | Stateless CLI runs from pip and writes machine-readable output |
| Operations-minded developer | Debugs a service from exported nginx logs | `grep` pipelines are brittle and hard to reproduce | Explicit parsing rules, exit codes, and deterministic ordering |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Our distinction |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI/reporting surface and another native binary to distribute | Small pip-installable tool with a fixed incident report contract |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards, retention | Operationally heavy, stateful, and incompatible with a $0 one-weekend local tool | No service, index, database, or ongoing administration |
| AWStats | Established historical web analytics | Oriented toward generated historical reports rather than pipeline-friendly triage | Streaming one-shot analysis with JSON and CSV |
| `grep` / `awk` | Already present and composable | Parsing and quoting are fragile; four views require multiple bespoke commands | One tested parser and one reproducible aggregate contract |

## 4. Unique Value Proposition

Turn a gigabyte nginx access log into the four incident summaries an SRE asks for, locally and reproducibly, with one pip-installed command and no infrastructure.

## 5. Business Model

The product is free and open source. There is no monetization target, CAC, or paid tier. Success is adoption and operational usefulness, not revenue; this keeps the delivery budget at $0 and avoids a commercial feature surface.

## 6. Technology Stack

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Required, widely available, strong text-streaming support |
| CLI | Click | Predictable options, help text, validation, and exit handling |
| Terminal presentation | Rich | Accessible colored tables with automatic non-TTY behavior |
| Domain models | `dataclasses` | Lightweight typed records without a framework |
| Packaging | pip-compatible `pyproject.toml` | Standard isolated installation and console entry point |
| Testing | pytest | Fast unit, CLI, fixture, and performance-contract tests |

## 7. Timeline

| Delivery window | Stage | Result |
|---|---|---|
| Friday evening | Contract and parser | Package skeleton, CLI contract, combined-log parser |
| Saturday morning | Streaming analytics | Exact aggregates, malformed-line accounting, cardinality guard |
| Saturday afternoon | Output formats | Rich, JSON, and CSV renderers with deterministic schemas |
| Sunday morning | Quality and performance | Unit/CLI tests plus a representative 1 GB benchmark |
| Sunday afternoon | Documentation and release | pip build/install smoke test and usage documentation |

## 8. KPIs

| Metric | Release target | One-month target | Three-month target |
|---|---:|---:|---:|
| Performance | 1 GB in under 30 seconds on the reference laptop | No regression | No regression |
| Correctness | Golden fixtures pass for all four metrics and all output formats | Zero confirmed calculation defects | Zero open P0 defects |
| Installability | Clean Python 3.11 environment installs and runs | 95% successful reported installs | 98% successful reported installs |
| Utility | Four required views in every successful report | 10 recurring users | 25 recurring users |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Python parser misses the 30-second target | Medium | High | Benchmark early; compile regex once; avoid per-line allocations; profile before optimizing |
| nginx format variation causes rejected lines | High | Medium | State supported combined format; count and sample malformed lines; fail when no valid records exist |
| High-cardinality values exhaust memory | Medium | High | Enforce a configurable unique-key ceiling and exit with code 4 before uncontrolled growth |
| CSV representation is ambiguous for multiple report sections | Medium | Medium | Define a normalized row schema with `section`, `key`, `count`, and `percentage` columns |
| Color corrupts redirected output | Low | Medium | Enable color only for TTY terminal output; JSON and CSV never contain styling |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python and selected dependencies are open source |
| Hosting and storage | $0 | Local-only, stateless execution |
| Delivery | $0 cash budget | One-weekend contributor effort |
| Ongoing operations | $0 | No deployed service or database |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream combined-format logs from files or stdin | Must | All reporting depends on bounded, one-pass ingestion |
| Top-10 client IPs | Must | Core traffic-source view |
| Top-10 error URLs | Must | Core 4xx/5xx triage view |
| Hourly request distribution | Must | Core traffic-shape view |
| Unique User-Agent share | Must | Core client-diversity view |
| Colored terminal report | Must | Required default user experience |
| JSON output | Must | Required pipeline integration |
| CSV output | Must | Required pipeline integration |
| Malformed-line diagnostics and cardinality guard | Must | Makes failure safe and explainable on real logs |
| Multiple input files and stdin | Should | Common operational workflow, but one file proves the MVP |
| Gzip input | Could | Convenient for archived logs, not required for the first release |
| Live `--follow` mode | Could | Useful operational polish after one-shot correctness is proven |
| Authentication, database, HTTP API, server, cloud, Kubernetes | Won't | Explicitly outside the local stateless CLI scope |

### RICE Scoring for Must and Should Features

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and input handling | 10 | 5 | 90% | 1.0 | 45.0 |
| Core four aggregates | 10 | 5 | 90% | 1.5 | 30.0 |
| Terminal report | 9 | 4 | 90% | 0.5 | 64.8 |
| JSON output | 8 | 4 | 95% | 0.4 | 76.0 |
| CSV output | 7 | 3 | 90% | 0.4 | 47.3 |
| Failure diagnostics and cardinality guard | 8 | 5 | 80% | 0.7 | 45.7 |
| Multiple files and stdin | 8 | 3 | 90% | 0.5 | 43.2 |

Dependency order overrides raw score where needed: establish the CLI and parser before aggregates and renderers. Within a dependency level, higher RICE score is implemented first.

## 12. Definition of Done

A feature is done when:

- [ ] Its behavior and edge cases match `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 type, lint, and unit checks pass.
- [ ] P0 acceptance tests and applicable CLI integration tests pass.
- [ ] The complete exit-code contract remains `0/1/2/3/4`.
- [ ] User-facing documentation and output schemas are updated.
- [ ] No known critical or high-severity security issue remains.
- [ ] The staged release candidate passes the project verification contract and risk-tier review.
- [ ] The pip artifact installs in a clean environment and the reference 1 GB benchmark is recorded.

## 13. Kill Criteria

Stop or redesign the MVP if an optimized release candidate cannot process the representative 1 GB fixture in under 30 seconds on the named reference laptop, if exact aggregation cannot remain within the defined cardinality guard, or if common combined-format logs cannot be parsed reliably. Do not solve these failures by silently adding persistence or a server.
