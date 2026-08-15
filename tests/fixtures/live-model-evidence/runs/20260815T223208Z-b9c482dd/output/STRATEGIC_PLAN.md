# Strategic Plan: Nginx Stream Analyzer

## 1. Product Idea

Nginx Stream Analyzer is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and emits four operational summaries without loading the whole file into memory: the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent values. Human-readable colored terminal output is the default; JSON and CSV make the same results usable in pipelines.

The MVP is intentionally local and stateless. It has no authentication, database, HTTP API, daemon, cloud dependency, or Kubernetes deployment. The delivery target is one weekend, the operating budget is $0, and the performance target is a 1 GB log in under 30 seconds on a representative laptop.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates production symptoms under time pressure | Needs a quick view of noisy clients and failing routes without importing data | One local command produces bounded top-10 and distribution summaries |
| DevOps engineer | Validates deployments and proxy behavior | Shell one-liners are brittle across formats and hard to reuse | Explicit parsing rules, stable output schemas, and deterministic exit codes |
| Platform engineer | Builds diagnostic pipelines | Interactive tools are difficult to automate | `--json`, `--csv`, stdin support, and clean stdout/stderr separation |

## 3. Competitive Analysis

| Alternative | What it does | Weakness for this use case | Our differentiation |
|---|---|---|---|
| GoAccess | Mature interactive and HTML nginx analytics | Broader UI/configuration surface than needed for four pipeline-friendly metrics | Smaller CLI contract, deterministic JSON/CSV, no dashboard workflow |
| Logstash + Elastic + Kibana | Ingests, stores, searches, and visualizes logs | Operationally heavy, persistent, and incompatible with a $0 one-weekend local tool | No services or storage; immediate one-shot analysis |
| AWStats | Produces historical web analytics reports | Oriented toward periodic reports and retained history | Streaming operational diagnostics with machine-readable output |
| `grep`/`awk`/`sort` | Flexible shell-native processing | Easy to misparse quoted fields; pipelines often sort unbounded cardinalities and vary by locale | Tested nginx parser, bounded aggregation policy, consistent errors and schema |

## 4. Unique Value Proposition

Get the four nginx incident summaries an SRE most often needs from a gigabyte-scale log, locally and in one command, with no service to deploy and no data to retain.

## 5. Business Model

The project is open source and free to use. There is no paid tier, telemetry, hosted component, CAC, or revenue target in the MVP. Value is measured in reduced time-to-first-diagnosis and reuse in internal pipelines. Contributions and maintenance remain community-driven; commercial hosting is explicitly outside scope.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Required platform; broad availability and strong text-processing ergonomics |
| CLI | Click | Stable option parsing, usage errors, and test support |
| Terminal rendering | Rich | Portable color and tables with automatic terminal awareness |
| Domain models | Standard-library dataclasses | Typed, dependency-light records and result objects |
| Parsing/aggregation | Python standard library | Streaming file iteration, timestamps, counters, CSV/JSON serialization |
| Packaging | `pyproject.toml` + pip | Standard installable CLI with console-script entry point |
| Testing | pytest + Click CliRunner | Fast unit, CLI, fixture, and contract tests |

## 7. Timeline

| Period | Stage | Result |
|---|---|---|
| Friday evening | Contract and fixtures | Package skeleton, log grammar, output schemas, exit codes, representative fixtures |
| Saturday morning | Streaming core | Line parser and aggregators with invalid-line accounting and cardinality guard |
| Saturday afternoon | CLI and renderers | Terminal, JSON, and CSV output with stdin/file handling |
| Sunday morning | Quality and performance | Unit/integration tests and reproducible 1 GB benchmark |
| Sunday afternoon | Packaging and documentation | pip-installable artifact, quick start, examples, and release checklist |

## 8. KPIs

| Metric | Launch / weekend | 1 month | 3 months |
|---|---:|---:|---:|
| Processing time for the benchmark 1 GB log | <30 s | <30 s | <25 s stretch goal |
| Peak resident memory on benchmark | <256 MiB target | <256 MiB | <192 MiB stretch goal |
| Correctness contract tests | 100% pass | 100% pass | 100% pass |
| Supported output contracts | terminal + JSON + CSV | no schema regressions | no schema regressions |
| Time to first useful output for a valid local log | one command | one command | one command |

Performance claims are accepted only against the documented fixture generator, hardware description, Python version, wall-clock method, and peak-memory measurement. The 30-second threshold is a release gate, not an assumed outcome.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined/common grammar | High | High | State the accepted grammar, expose `--log-format`, reject unsupported input clearly, and test escaping/missing fields |
| Exact unique User-Agent tracking grows with input cardinality | Medium | High | Configurable cardinality ceiling; terminate with exit code 4 rather than exhaust memory or silently approximate |
| Python misses the 1 GB / 30 s target | Medium | High | Benchmark early; use compiled regex once, streaming I/O, small dataclasses at boundaries, and profile before optimizing |
| CSV representation becomes ambiguous for multiple metric tables | Medium | Medium | Define a long-form schema with `metric`, `rank`/`bucket`, `key`, `count`, and `percentage` |
| Malformed logs silently distort percentages | Medium | High | Count invalid lines, base percentages only on valid requests, report diagnostics, and fail when no valid records exist |
| Color or diagnostics corrupt pipeline output | Low | High | Disable color for JSON/CSV and non-TTY output; reserve stdout for results and stderr for diagnostics |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Python, Click, Rich, pytest | $0 | Open-source dependencies |
| Hosting, database, cloud, Kubernetes | $0 | Not part of the product |
| Distribution via public Python package tooling | $0 | Standard package publication has no required hosting bill |
| Development labor | One weekend | Time constraint, not a cash expense |
| Total operating budget | $0/month | Local execution only |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Streaming nginx line parsing from file or stdin | **Must** | Foundation for bounded-memory local analysis |
| Top 10 client IPs | **Must** | Core incident metric |
| Top 10 URLs restricted to 4xx/5xx responses | **Must** | Core error triage metric |
| Hourly request percentage distribution | **Must** | Core traffic-shape metric |
| Unique User-Agent share with cardinality guard | **Must** | Core diversity metric with explicit safety behavior |
| Colored terminal, JSON, and CSV renderers | **Must** | Required interactive and pipeline interfaces |
| Configurable top-N and timezone | **Should** | Useful extension after the fixed MVP contract is stable |
| Gzip-compressed input | **Could** | Convenient but not required for initial value |
| Additional custom nginx format compiler | **Could** | Broadens compatibility at meaningful complexity |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts local stateless CLI scope |

### RICE Scoring (Must + Should)

Confidence is represented as a decimal in the calculation.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and input handling | 10 | 5 | 90% | 1.0 | 45.0 |
| Top 10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top 10 error URLs | 9 | 5 | 95% | 0.35 | 122.1 |
| Hourly request distribution | 8 | 4 | 95% | 0.30 | 101.3 |
| Terminal/JSON/CSV renderers | 10 | 5 | 85% | 0.75 | 56.7 |
| Unique User-Agent share and guard | 8 | 4 | 80% | 0.50 | 51.2 |
| Configurable top-N and timezone | 5 | 2 | 70% | 0.50 | 14.0 |

Dependency order overrides raw RICE where necessary: the parser precedes all metrics, and the normalized result model precedes renderers. Within those constraints, implementation follows descending value.

## 12. Definition of Done

A feature is done when:

- [ ] Its behavior and edge cases are captured in the PRD and architecture.
- [ ] Python 3.11 code passes formatting, linting, type checking, and all unit/integration tests.
- [ ] P0 acceptance criteria have executable tests, including malformed and empty input.
- [ ] Terminal, JSON, and CSV contracts remain mutually consistent.
- [ ] No known critical or high-severity security issues remain.
- [ ] User-facing documentation and `--help` are current.
- [ ] The frozen release candidate processes the documented 1 GB fixture in under 30 seconds on the named laptop profile without exceeding the cardinality ceiling.
- [ ] The pip-built wheel installs into a clean environment and the console command passes its smoke test.

## 13. Release and Kill Criteria

Release the MVP only if all P0 acceptance tests pass, all three output modes agree on metric values, the wheel installs cleanly, and the performance gate is measured successfully. Re-scope or stop after the weekend if the correct parser cannot meet the performance gate after profiling, exact User-Agent cardinality cannot be bounded with a clear failure contract, or format ambiguity prevents deterministic results. Do not hide a missed gate behind sampling or an approximate algorithm without a new product decision.

