# Strategic Plan: nginx-stream-stats

## 1. Product Idea

`nginx-stream-stats` is an installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich colored terminal output is the default; JSON and CSV make the same report usable in pipelines.

The product is intentionally local and stateless. It has no authentication, database, HTTP API, server process, cloud dependency, or Kubernetes deployment. The MVP target is a one-weekend, $0 open-source delivery that processes a 1 GB representative log in under 30 seconds on a documented laptop baseline.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates live incidents | Needs a useful traffic/error overview before a dashboard query is ready | One command produces bounded top lists and hourly percentages while reading incrementally |
| DevOps engineer | Operates small or isolated systems | Full observability stacks are too costly or unavailable | Local, pip-installable CLI with no service dependencies |
| Platform/automation engineer | Builds shell pipelines and scheduled checks | Colored human output is difficult to parse reliably | Stable `--json` and `--csv` schemas with explicit exit codes |

## 3. Competitive Analysis

| Alternative | Strength | Limitation for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Fast, mature interactive and HTML analytics | Broader UI/configuration surface than a four-metric pipeline tool | Narrow, predictable report contract and native JSON/CSV from a small Python package |
| Logstash + Elastic + Kibana | Powerful ingestion, storage, search, and visualization | Operationally heavy, stateful, and costly for a local one-shot answer | Zero-service, zero-database execution with immediate local output |
| AWStats | Established historical web analytics | Oriented toward generated reports and persistent history, not composable streaming CLI use | Stateless processing and pipeline-friendly formats |
| `grep`/`awk`/`sort` | Universally available and flexible | Fragile parsing, repeated full-file passes, locale/quoting issues, and no unified schema | Tested nginx parsing, one-pass aggregation, consistent metrics and error behavior |

## 4. Unique Value Proposition

Get the four nginx incident metrics an SRE most often needs from a large local log in one bounded-memory command, with equally explicit human and machine-readable outputs.

## 5. Business and Distribution Model

The project is open source and free to use. Distribution is through a Python package installable with `pip`; development and runtime services cost $0. Success is adoption and reliability rather than revenue. Contributions and issue reports are the feedback loop; paid hosting, telemetry, and commercial tiers are not part of the product.

## 6. Technology Stack

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required platform; broad availability in DevOps environments |
| CLI | Click | Stable command/option parsing and consistent help/errors |
| Terminal UI | Rich | Colored tables and progress-safe stderr behavior |
| Domain models | `dataclasses` | Explicit typed report and record structures without a framework |
| Parsing/aggregation | Python standard library | Streaming file iteration, datetime parsing, `Counter`, CSV and JSON support |
| Packaging | `pyproject.toml` + pip | Modern installable console entry point |
| Testing | pytest | Focused parser, aggregation, CLI, schema, and performance tests |

## 7. Delivery Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable CLI accepts files/stdin and classifies valid versus malformed lines |
| Saturday afternoon | Streaming aggregation | Four required metrics computed in a single pass with explicit resource limits |
| Sunday morning | Renderers and CLI behavior | Rich, JSON, and CSV outputs plus exit-code contract |
| Sunday afternoon | Tests, benchmark, docs, release check | Acceptance suite and 1 GB performance evidence ready for release |

## 8. KPIs

| Metric | 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| Representative 1 GB processing time on documented laptop | <30 s | <25 s | <20 s where profiling supports it |
| Correctness fixtures passing | 100% | 100% | 100% |
| Peak memory on bounded-cardinality benchmark | <256 MB | <192 MB | <160 MB |
| Released defects that silently produce incorrect output | 0 | 0 | 0 |
| Package installs/stars (directional adoption signal) | 25 | 100 | 250 |

Performance measurements must publish the hardware, filesystem/cache conditions, fixture characteristics, command, elapsed time, and peak resident memory; the target is not claimed from an estimate.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| nginx format variation breaks field extraction | High | High | Support one documented default combined format in MVP, fail explicitly on incompatible formats, and isolate parser tests |
| Exact unique/high-cardinality tracking exhausts memory | Medium | High | Enforce a configurable cardinality ceiling and exit with code 4 rather than swapping or returning a false result |
| 1 GB target misses 30 seconds | Medium | High | Benchmark early, use one pass, avoid per-line regex recompilation and object retention, profile before optimization |
| Malformed lines bias statistics unnoticed | Medium | High | Count malformed lines, expose the count in every output, and use exit code 3 when no valid records remain |
| JSON/CSV schemas drift across releases | Medium | Medium | Version/document schemas and lock them with golden CLI tests |
| Rich decoration contaminates pipelines | Low | Medium | Send diagnostics to stderr; JSON/CSV data alone goes to stdout; disable color in machine modes |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Python, Click, Rich, pytest | $0 | Open-source dependencies |
| Local development and benchmarks | $0 | Existing laptop, one-weekend time budget |
| Source hosting and basic CI | $0 | Free open-source tier |
| Runtime infrastructure | $0 | Local CLI; no hosted components |
| Total cash budget | **$0** | Time is constrained to one weekend |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream nginx combined-format input from files or stdin | **Must** | Foundation for local and piped analysis without loading the log |
| Top-10 client IPs | **Must** | Required incident traffic signal |
| Top-10 URLs by combined 4xx/5xx count | **Must** | Required error-hotspot signal |
| Hourly request distribution | **Must** | Required traffic-shape signal; each percentage is `100 × hourly_request_count / total_valid_requests` |
| Unique User-Agent share | **Must** | Required client-diversity signal with explicit cardinality guard |
| Rich colored default output | **Must** | Required default human interface |
| Stable JSON and CSV outputs | **Must** | Required pipeline interfaces |
| Malformed-line diagnostics and `0/1/2/3/4` exits | **Must** | Prevents silent or ambiguous automation failures |
| Gzip input | **Should** | Common operational convenience; plain streams still deliver the MVP value |
| Configurable top-N | **Could** | Useful flexibility but the product contract is top 10 |
| Custom nginx `log_format` grammar | **Could** | Broadens compatibility but risks the weekend schedule |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Explicitly excluded and contrary to the local stateless value proposition |

### RICE Scoring for Must and Should

Confidence is expressed as a multiplier in the calculation. Scores are ordered from highest to lowest and guide implementation sequencing, subject to technical dependencies.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Top-10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top-10 error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly request distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Streaming files/stdin parser | 10 | 5 | 90% | 0.75 | 60.0 |
| JSON and CSV output | 8 | 4 | 90% | 0.50 | 57.6 |
| Rich default output | 9 | 3 | 90% | 0.50 | 48.6 |
| Malformed-line and exit behavior | 10 | 5 | 95% | 1.00 | 47.5 |
| Unique User-Agent share and guard | 8 | 4 | 80% | 0.75 | 34.1 |
| Gzip input | 5 | 2 | 85% | 0.25 | 34.0 |

High-scoring aggregations follow the parser because it is an architectural dependency even when their individual RICE score is higher.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Python 3.11 code is formatted, type-checked per project policy, and imports cleanly.
- [ ] Unit and CLI tests pass with at least 90% line coverage for product modules.
- [ ] Relevant integration/golden-schema tests pass.
- [ ] The representative performance test records <30 seconds for 1 GB on the documented laptop baseline.
- [ ] Review is accepted under the repository's current Idea to Deploy verification contract.
- [ ] Documentation and CLI help match behavior.
- [ ] No known Critical or High security issue remains.
- [ ] The exact staged candidate has a current machine-oracle result and risk-tier adjudication receipt.

## 13. Product Kill and Reassessment Criteria

Re-scope or stop the MVP if a one-pass Python implementation cannot process the representative 1 GB fixture under 30 seconds after profiling, if exact required metrics cannot stay within a safe documented memory ceiling, or if supporting real-world combined-format logs requires a custom format language that cannot fit the one-weekend budget. Do not hide failure by weakening metric semantics.

The technical contracts are defined in `PROJECT_ARCHITECTURE.md`; delivery sequencing is defined in `IMPLEMENTATION_PLAN.md`.
