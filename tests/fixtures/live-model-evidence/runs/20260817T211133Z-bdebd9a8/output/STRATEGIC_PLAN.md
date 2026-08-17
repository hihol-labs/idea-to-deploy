# Strategic Plan: Nginx Stream Analyzer

## 1. Product Idea

Nginx Stream Analyzer is a local, pip-installable Python 3.11 CLI for DevOps
and SRE engineers. It consumes nginx access logs incrementally from files or
standard input and produces an operational snapshot: the ten busiest client
IPs, the ten URLs with the most 4xx/5xx responses, request distribution by
hour, and the percentage of distinct User-Agent values. The default report is
colored terminal text; stable JSON and CSV modes make the same data suitable
for shell pipelines.

The MVP optimizes for a fast local answer without shipping logs to another
system. It is free, open source, stateless across runs, and intentionally has
no service tier, account, database, or network dependency.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Diagnoses incidents from a laptop or bastion host | Needs a useful traffic/error summary before a dashboard can be configured | One command reads a file or pipe and emits the four agreed metrics |
| DevOps engineer | Validates a rollout or proxy change | Existing observability may be unavailable, delayed, or too expensive for ad hoc logs | Local, zero-cost analysis with pipeline-safe JSON/CSV |
| Platform engineer | Builds repeatable operational scripts | Ad hoc `awk` chains are brittle and format-specific | Stable schemas, exit codes, and deterministic ordering |

## 3. Competitive Analysis

| Alternative | What it does well | Weakness for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature interactive and HTML nginx analytics | Broader UI/configuration surface than a four-metric pipeline tool | Smaller contract, pip install, stable JSON/CSV, no dashboard |
| Logstash + Elasticsearch + Kibana | Powerful centralized ingestion, search, and visualization | Operational cost, services, storage, and setup are disproportionate for local one-off analysis | No server, database, account, or recurring cost |
| AWStats | Established historical web-log reporting | Report generation and configuration are oriented toward persistent historical analysis | Immediate streaming CLI output and modern pipeline formats |
| `grep`/`awk`/`sort` | Ubiquitous and composable | Quoting, nginx parsing, timestamps, errors, and cross-platform behavior become fragile | Tested parser and one documented output/exit contract |

## 4. Unique Value Proposition

Get a trustworthy nginx traffic-and-error snapshot from a local file or pipe
in one command, without deploying or operating an observability stack.

## 5. Business Model

The project is open source and free to use. There are no paid tiers, hosted
services, telemetry, or user accounts. Value is measured in incident-response
time saved and reuse in operational scripts rather than revenue, CAC, or LTV.
The operating budget is fixed at $0; maintainers contribute time voluntarily.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Required, widely available to the target audience |
| CLI | Click | Mature option parsing, stdin/file conventions, predictable usage errors |
| Terminal rendering | Rich | Readable colored tables with automatic non-TTY color handling |
| Domain records | Standard-library dataclasses | Typed records without a validation framework or runtime service |
| Parsing/aggregation | Python standard library | Streaming I/O, timestamps, counters, JSON, and CSV need no extra system |
| Packaging | `pyproject.toml` + pip | Required installation route and console-script entry point |
| Verification | pytest, coverage, Ruff, mypy | Fast local tests and static checks; development-only dependencies |

See `PROJECT_ARCHITECTURE.md` for component boundaries and the CLI contract.

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable command and validated line parsing |
| Saturday afternoon | Streaming aggregation | Four exact metrics with deterministic ordering and limits |
| Sunday morning | Text, JSON, and CSV renderers | Human- and machine-readable output parity |
| Sunday afternoon | Tests, benchmark, docs, packaging | Release candidate meeting correctness and 1 GB performance gates |

## 8. KPIs

| Metric | Release target | 1 month | 3 months |
|---|---:|---:|---:|
| 1 GB benchmark duration on reference laptop | < 30 s | < 30 s | < 25 s if profiling supports it |
| Peak RSS on 1 GB benchmark within configured cardinality | <= 512 MiB | <= 512 MiB | <= 384 MiB |
| P0 acceptance tests passing | 100% | 100% | 100% |
| Output-schema compatibility failures | 0 | 0 | 0 |
| Valid nginx combined-log lines parsed in conformance corpus | 100% | 100% | 100% |

The reference laptop, corpus generator, Python patch version, wall-clock tool,
and peak-RSS tool must be recorded with every benchmark result. Performance is
not inferred from unit tests.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| High-cardinality URLs, IPs, or User-Agents exhaust memory | Medium | High | Configurable exact-cardinality ceiling and exit code 4; benchmark adversarial inputs |
| Real nginx `log_format` variants do not match combined/common input | High | Medium | Explicit supported grammar, actionable parse diagnostics, strict/non-strict modes; custom formats are deferred |
| Python misses the 1 GB / 30 s target | Medium | High | Byte-efficient single pass, no full-line retention, profile before optimization, release-blocking benchmark |
| JSON/CSV drift from terminal semantics | Medium | High | One report dataclass feeds all renderers; golden-output contract tests |
| ANSI color corrupts redirected output | Low | Medium | Auto-disable on non-TTY; `--color auto|always|never`; tests for redirected streams |
| Malformed input silently biases results | Medium | High | Count skipped lines, show warnings/metadata, provide `--strict`, fail when no valid records exist |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Python, Click, Rich, pytest, Ruff, mypy | $0 | Open-source dependencies |
| Repository and CI | $0 | Local development; free hosting/CI tier if used later |
| Runtime infrastructure | $0 | Runs on the user's machine; none is provisioned |
| Delivery labor | One weekend | Time-boxed maintainer contribution |
| Total cash budget | $0 | No cloud, database, domain, or paid service |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream files and stdin without loading the full input | **Must** | Core local-analysis value and performance constraint |
| Parse nginx combined and common access-log records | **Must** | Required basis for the four metrics |
| Top-10 client IPs by valid request count | **Must** | Explicit product outcome |
| Top-10 URLs by combined 4xx/5xx count | **Must** | Explicit product outcome |
| Hourly request percentages | **Must** | Explicit product outcome |
| Distinct User-Agent share with bounded cardinality | **Must** | Explicit product outcome and memory safety requirement |
| Rich terminal, JSON, and CSV renderers | **Must** | Default UX and pipeline contract |
| Strict parsing, diagnostics, and exit codes 0/1/2/3/4 | **Must** | Automation needs predictable failure semantics |
| Multiple input files in one aggregate report | **Should** | Common incident workflow; low incremental cost |
| Gzip input | **Could** | Convenient for rotated logs but not essential for MVP |
| Custom nginx `log_format` definitions | **Could** | Broadens compatibility at meaningful parser complexity |
| Database, HTTP API, server, cloud, Kubernetes, authentication | **Won't** | Contradicts the local stateless CLI scope |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`; confidence is expressed
as a decimal in the calculation.

| Feature | Reach (1-10) | Impact (1-5) | Confidence | Effort (days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream files/stdin | 10 | 5 | 100% | 0.5 | 100.0 |
| Parse combined/common records | 10 | 5 | 90% | 0.75 | 60.0 |
| Top IPs and error URLs | 10 | 5 | 95% | 1.0 | 47.5 |
| Hourly distribution | 9 | 4 | 95% | 0.5 | 68.4 |
| Distinct User-Agent share and limit | 8 | 4 | 85% | 0.75 | 36.3 |
| Text/JSON/CSV rendering | 10 | 5 | 90% | 1.0 | 45.0 |
| Diagnostics and exit contract | 9 | 5 | 90% | 0.75 | 54.0 |
| Multiple input files | 6 | 3 | 90% | 0.25 | 64.8 |

Implementation order in `IMPLEMENTATION_PLAN.md` respects dependencies first
and then the highest RICE value available within each dependency layer.

## Definition of Done

A feature is Done when:

- [ ] Its observable behavior and acceptance criteria are documented in `PRD.md`.
- [ ] Python 3.11 code is formatted and passes Ruff and mypy.
- [ ] Unit and integration tests pass with at least 90% line coverage for `src/`.
- [ ] P0 golden CLI tests pass for terminal, JSON, CSV, stdin, and file inputs.
- [ ] The 1 GB benchmark completes in under 30 seconds on the recorded reference laptop.
- [ ] README and implementation status are current.
- [ ] No known critical or high-severity security issue remains.
- [ ] Package installation in a clean virtual environment exposes the documented command.
- [ ] A human verifies the default terminal report with color auto-detection.

## 12. Release and Kill Criteria

Ship the MVP only if all P0 acceptance criteria pass and the recorded 1 GB
benchmark is below 30 seconds. Re-scope or stop the project if Python 3.11
cannot meet that performance target after profiling, if exact metrics cannot
fit within the documented cardinality budget on the reference laptop, or if
supporting real combined/common logs requires unplanned persistent services.

The detailed product kill criteria live in `PRD.md`.
