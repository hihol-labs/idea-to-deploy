# Strategic Plan: nginx-stream-report

## 1. Product Idea

`nginx-stream-report` is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four immediately useful views: the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, the percentage distribution of valid requests by hour, and the share of unique User-Agent values. It is intentionally a focused local diagnostic tool rather than an observability platform.

The MVP is open source, costs $0 to operate, and is scoped for one weekend. The performance target is to process a 1 GB log in under 30 seconds on a representative laptop while keeping memory bounded by distinct-key cardinality rather than file size.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates an incident from a downloaded or local nginx log | Needs a useful traffic/error summary before a full stack can be queried | One streaming command returns the four diagnostic views |
| DevOps engineer | Checks a deployment or reverse proxy | Ad hoc shell pipelines are fragile and hard to share | Stable CLI, JSON, CSV, and documented exit codes |
| Platform engineer | Automates log triage in a pipeline | Terminal-oriented tools often lack machine-readable output | Deterministic `--json` and `--csv` modes with color disabled |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Fast, mature, interactive reports | Broader UI/reporting surface than needed; output model differs from a small pipeline tool | Narrow, scriptable four-metric report with explicit schemas |
| Logstash + Elastic + Kibana | Powerful ingestion, search, dashboards, retention | Requires services, storage, setup, and ongoing operations | No service, database, or infrastructure; run locally once |
| AWStats | Established historical web analytics | Persistent/report-generation workflow and legacy-oriented configuration | Modern pip CLI designed for one-shot streaming analysis |
| `grep`/`awk`/`sort` | Ubiquitous and flexible | Multiple passes, quoting hazards, locale differences, and high memory/disk use for sorts | One tested cross-platform command and stable output contract |

## 4. Unique Value Proposition

Turn a large local nginx access log into a predictable incident-triage summary in one command, without deploying or operating an observability stack.

## 5. Business Model

The product is free and open source. There is no paid tier, hosted service, telemetry, or operating revenue in the MVP. Value is measured through utility, reliability, and adoption rather than unit economics. Distribution through PyPI and source hosting remains free within the approved budget.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved, broadly available, productive for a weekend build |
| CLI | Click | Mature argument parsing, help text, and exit handling |
| Terminal presentation | Rich | Readable tables and color with TTY awareness |
| Domain records | `dataclasses` | Explicit low-overhead parsed-record and report models |
| Structured output | Python `json` and `csv` | Stable formats without additional runtime dependencies |
| Packaging | `pyproject.toml`, pip, console script | Standard install and distribution path |
| Verification | pytest, coverage, Ruff, mypy | Fast local quality feedback; development-only dependencies |

## 7. Timeline

| Window | Work | Result |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser fixtures | Installable CLI shell and validated parsing behavior |
| Saturday afternoon | Streaming aggregation and cardinality guard | Correct one-pass report model |
| Sunday morning | Text, JSON, and CSV renderers | Human and pipeline outputs |
| Sunday afternoon | Performance, integration tests, documentation | Release candidate meeting correctness and speed gates |

## 8. KPIs

| Metric | Release target | Month 1 target | Month 3 target |
|---|---:|---:|---:|
| 1 GB processing time on the reference laptop | <30 s | <30 s | <25 s where optimization is evidence-backed |
| Peak memory on a bounded-cardinality 1 GB fixture | <256 MiB | <256 MiB | <192 MiB |
| Parser correctness on supported-format fixtures | 100% | 100% | 100% |
| Automated branch coverage | >=90% | >=90% | >=90% |
| Confirmed external users | 0 | 10 | 50 |

Benchmark results must name the laptop CPU, storage medium, Python patch version, input size, valid-line count, and unique-cardinality profile; the timing target is not considered proven without that context.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats vary from the supported combined/common forms | High | High | Publish the grammar, count malformed lines, fail when no valid records exist, and defer custom formats |
| Distinct IP, URL, or User-Agent cardinality exhausts memory | Medium | High | Enforce configurable documented caps and stop with exit code 4 before uncontrolled growth |
| Python misses the 1 GB/30 s target | Medium | High | Use bytes-oriented single-pass parsing, avoid per-line Rich work, benchmark early, profile before optimizing |
| CSV semantics are ambiguous across four report sections | Medium | Medium | Use one documented long-form schema with a `section` discriminator |
| Pipe failures or unreadable files produce partial-looking output | Low | High | Render only after successful aggregation and use the complete exit-code contract |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python and dependencies are open source |
| Hosting/infrastructure | $0 | None required |
| Distribution | $0 | PyPI and source hosting |
| Development labor | One weekend | Approved time budget; no cash expenditure |
| Total cash budget | **$0** | Hard constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream nginx combined/common access logs from a file or stdin | **Must** | Foundation for local and pipeline use |
| Top 10 client IPs | **Must** | Core traffic-source diagnostic |
| Top 10 URLs by combined 4xx/5xx count | **Must** | Core error diagnostic |
| Hourly request percentage distribution | **Must** | Core temporal diagnostic |
| Share of unique User-Agent values | **Must** | Core client-diversity diagnostic |
| Colored terminal report plus `--json` and `--csv` | **Must** | Required interactive and pipeline interfaces |
| Malformed-line accounting and stable exit codes `0/1/2/3/4` | **Must** | Makes automation trustworthy |
| Configurable distinct-key cardinality ceiling | **Must** | Prevents unbounded memory consumption |
| Explicit `--no-color` option | **Should** | Useful for captured terminal output even outside structured modes |
| Configurable top-N | **Could** | Helpful but the approved product specifically targets top 10 |
| Gzip input | **Could** | Convenient but not required; shell decompression can feed stdin |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the local stateless CLI scope |
| Custom nginx `log_format` language | **Won't** | Too broad for the one-weekend MVP |

### RICE Scoring for Must and Should

RICE score is `(Reach × Impact × Confidence) / Effort`, with confidence expressed as a decimal. Scores guide implementation order but dependencies still place the parser before derived metrics.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Streaming file/stdin ingestion | 10 | 5 | 100% | 0.5 | 100.0 |
| Stable output modes | 10 | 5 | 95% | 0.75 | 63.3 |
| Top client IPs | 9 | 4 | 95% | 0.6 | 57.0 |
| Top error URLs | 9 | 5 | 95% | 0.8 | 53.4 |
| Hourly percentage distribution | 8 | 4 | 95% | 0.6 | 50.7 |
| Malformed-line and exit-code contract | 9 | 5 | 90% | 0.9 | 45.0 |
| Unique User-Agent share | 8 | 3 | 85% | 0.6 | 34.0 |
| Cardinality ceiling | 7 | 5 | 85% | 1.0 | 29.8 |
| `--no-color` | 4 | 2 | 90% | 0.2 | 36.0 |

## 12. Definition of Done

A release is done when:

- [ ] The package installs with pip on Python 3.11 and exposes the documented console command.
- [ ] Supported valid records produce the exact PRD metrics and malformed records are counted.
- [ ] Text, JSON, and CSV contracts pass golden integration tests.
- [ ] Exit codes `0/1/2/3/4` pass end-to-end tests, including unique-cardinality exhaustion for code 4.
- [ ] Unit and integration tests pass with at least 90% branch coverage.
- [ ] Ruff and mypy checks pass.
- [ ] The benchmark processes 1 GB in under 30 seconds on the documented reference laptop.
- [ ] A bounded-cardinality benchmark remains within the documented memory target.
- [ ] README and CLI help reflect the final behavior.
- [ ] No known Critical or High security defect remains.

## 13. Kill Criteria

- Stop or rescope the MVP if a correct single-process implementation cannot meet the 1 GB/30 s target after profiling and one focused optimization cycle.
- Do not release if supported valid records can be silently omitted or structured output can be emitted partially on failure.
- Reduce the supported log grammar rather than introduce a service, database, or multi-process architecture during the weekend scope.

