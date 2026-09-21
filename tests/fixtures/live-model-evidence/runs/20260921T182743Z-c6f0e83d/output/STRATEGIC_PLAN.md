# Strategic Plan: nginx-stream-report

## 1. Product Idea

`nginx-stream-report` is a local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four immediately useful views: the top 10 client IPs, the top 10 URLs returning 4xx/5xx responses, hourly request distribution, and the percentage share represented by unique User-Agent values. Rich-colored terminal text is the default; JSON and CSV provide stable pipeline output.

The MVP is deliberately local and stateless. It has no authentication, database, HTTP API, server process, cloud dependency, or Kubernetes deployment. The delivery budget is $0 and the target implementation window is one weekend.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Incident responder | Needs a useful traffic/error snapshot without provisioning a service | Runs one local command against a file or pipe and gets ranked results |
| DevOps engineer | Platform operator | Needs repeatable output for shell automation | Selects `--json` or `--csv` and relies on documented schemas and exit codes |
| Service owner | Backend engineer | Needs fast triage of noisy endpoints and suspicious clients | Sees top IPs, error URLs, and hourly concentration in a single pass |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader configuration and UI surface than a four-metric pipeline tool | Narrow, deterministic CLI contract with JSON and CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, and dashboards | Requires services, storage, setup, and operational budget | Zero-service, zero-storage local analysis |
| AWStats | Established historical web analytics | Batch/report orientation and dated operational workflow | Stream-first incident-oriented summaries |
| `grep`/`awk` pipelines | Ubiquitous and flexible | Fragile parsing, repeated work, inconsistent output contracts | Tested nginx parsing and one stable cross-format interface |

## 4. Unique Value Proposition

Turn a large nginx access log into the four incident-triage summaries an SRE needs, locally and in one streaming pass, with no service to operate.

## 5. Business Model

The project is free, open source, and has no paid tier in the MVP. Its value is reduced incident-triage time and a reusable pipeline contract. Distribution uses a public source repository and Python package metadata; no hosted control plane or monetized telemetry is planned.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required, broadly available, productive for a one-weekend CLI |
| CLI | Click | Stable option parsing, help, usage errors, and test support |
| Terminal UI | Rich | TTY-aware color and readable tables |
| Domain models | `dataclasses` | Lightweight typed records without persistence machinery |
| Packaging | `pyproject.toml` + pip | Standard install path and console-script entry point |
| Tests | pytest + Click `CliRunner` | Fast unit/CLI coverage and fixture-driven verification |

## 7. Timeline

| Period | Stage | Result |
|---|---|---|
| Saturday morning | Package, contracts, parser | Installable CLI shell and verified common/combined parsing |
| Saturday afternoon | Streaming aggregation | All four metrics computed with bounded top-10 structures |
| Sunday morning | Renderers and failure behavior | Rich, JSON, CSV, and exit-code contracts complete |
| Sunday afternoon | Performance, docs, release check | 1 GB benchmark, tests, and pip smoke test recorded |

## 8. KPIs

| Metric | MVP / 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| Processing time for a 1 GB representative log | <30 s on the reference laptop | Maintain <30 s | Maintain <30 s |
| Peak resident memory on the 1 GB benchmark | <512 MiB with documented unique-value cap | <384 MiB | <256 MiB |
| Valid-line parse rate on supported common/combined fixtures | 100% | 100% | 100% |
| Automated coverage of core parser/aggregation/rendering | >=90% | >=90% | >=90% |
| Output-contract regressions | 0 known | 0 known | 0 known |

Performance claims are accepted only against a documented fixture generator, machine description, and timed command; the 30-second target is not inferred from unit tests.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real logs vary from nginx common/combined syntax | High | High | Declare supported formats, count malformed lines, offer `--strict`, add adversarial fixtures |
| Exact unique User-Agent counting grows memory on hostile input | Medium | High | Enforce a configurable cardinality ceiling and exit with code 4 before exhaustion |
| Python misses the 1 GB / 30 s target | Medium | High | Profile a representative 1 GB input; avoid per-line regex recompilation and retained records |
| CSV/JSON contracts drift | Medium | Medium | Golden-output tests and versioned documented schemas |
| Terminal color contaminates pipelines | Low | Medium | Enable color only for default TTY output; never emit ANSI in JSON/CSV |
| Scope expands into a hosted analytics system | Medium | High | Keep server, database, auth, cloud, and Kubernetes explicitly out of scope |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Python, Click, Rich, pytest | $0 | Open-source dependencies |
| Local development and benchmark execution | $0 | Existing laptop |
| Hosting, database, cloud, Kubernetes | $0 | Not part of the product |
| Distribution | $0 | Source checkout and local `pip install` are sufficient for MVP |
| Total cash budget | **$0** | One-weekend personal engineering effort only |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream common/combined nginx lines from file or stdin | **Must** | Foundation for every report |
| Top-10 client IPs | **Must** | Primary traffic-source triage view |
| Top-10 URLs by 4xx/5xx count | **Must** | Primary failure triage view |
| Hourly request distribution | **Must** | Reveals time concentration; percentage is `100 × hourly_request_count / total_valid_requests` |
| Unique User-Agent share with safe cardinality ceiling | **Must** | Required metric with explicit memory failure behavior |
| Rich terminal, JSON, and CSV outputs | **Must** | Supports humans and pipelines |
| Follow a growing file with `--follow` | **Should** | Enables live operations but static streams already deliver MVP value |
| Configurable top-N | **Could** | Useful generalization; top 10 satisfies the approved product |
| Approximate cardinality mode | **Could** | Can reduce memory but weakens exactness and complicates semantics |
| Database, HTTP API, server, auth, cloud, Kubernetes | **Won't** | Conflicts with the approved local stateless scope |

### RICE Scoring (Must + Should)

| Feature | Reach (1-10) | Impact (1-5) | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Stream parser and input handling | 10 | 5 | 90% | 0.75 | 60.0 |
| Rich/JSON/CSV output contracts | 10 | 4 | 90% | 0.75 | 48.0 |
| Top-10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top-10 error URLs | 9 | 5 | 95% | 0.35 | 122.1 |
| Hourly percentage distribution | 8 | 3 | 95% | 0.20 | 114.0 |
| Unique User-Agent share and ceiling | 8 | 4 | 85% | 0.40 | 68.0 |
| Follow mode | 5 | 3 | 70% | 0.50 | 21.0 |

Dependency order overrides raw score where necessary: input parsing precedes all aggregations, and validated result models precede renderers. Within those constraints, higher-scoring metrics are implemented first. See `IMPLEMENTATION_PLAN.md`.

## 12. Definition of Done

A feature is done when:

- [ ] Its behavior and failure cases match `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 type/syntax checks and relevant unit/integration tests pass.
- [ ] Core parser, aggregator, renderer, and CLI coverage remains at least 90%.
- [ ] JSON and CSV outputs contain no ANSI color and match golden contracts.
- [ ] No known critical or high-severity security issue remains.
- [ ] User-facing documentation is updated when a contract changes.
- [ ] The installed console command is manually smoke-tested from a clean virtual environment.
- [ ] Performance-sensitive changes are checked against the representative 1 GB benchmark.

## 13. Kill Criteria

Re-scope or stop the MVP if representative benchmarking cannot reach 1 GB in under 30 seconds without native extensions, if exact User-Agent cardinality cannot be bounded safely with a clear failure contract, or if supported nginx formats cannot be parsed deterministically. Do not respond by adding a database or hosted service; reassess language/algorithm choices or narrow supported formats.

