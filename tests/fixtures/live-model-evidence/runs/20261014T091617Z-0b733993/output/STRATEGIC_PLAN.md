# Strategic Plan: Nginx Stream Analyzer

## 1. Product Idea

Nginx Stream Analyzer is an open-source, local Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. It favors a fast, zero-service workflow: pipe a log into the command or pass a local file and receive colored terminal output, JSON, or CSV.

The MVP is a one-weekend, $0 build. It is not an observability platform and stores no operational data.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| Incident responder | On-call SRE | Needs a quick traffic/error view without uploading sensitive logs | One local streaming command with useful defaults |
| Service operator | DevOps engineer | Needs repeatable summaries in shell pipelines | Stable JSON/CSV schemas and explicit exit codes |
| Systems generalist | Platform engineer | Cannot justify an ELK deployment for one-off triage | Pip-installable, stateless, no service dependencies |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this job | Differentiation |
|---|---|---|---|
| GoAccess | Mature interactive and HTML analytics | Broader UI and configuration surface than a four-metric pipeline command | Smaller contract, deterministic JSON/CSV, Python install |
| Logstash + Elastic + Kibana | Powerful ingestion, search, retention, dashboards | Operational cost, persistent services, and data movement | No infrastructure or retained data; immediate local result |
| AWStats | Established historical reports | Batch/reporting orientation and dated operational workflow | Stream-first CLI for incident-time use |
| grep/awk/sort/uniq | Ubiquitous and composable | Parsing is fragile; multiple passes and bespoke scripts are common | One tested nginx parser and one stable summary schema |

## 4. Unique Value Proposition

Obtain a pipeline-safe nginx traffic and error summary from large local logs in one command, without deploying or operating anything.

## 5. Business Model

The project is free and open source. There are no paid tiers, telemetry, hosted costs, CAC, or monetization goals for the MVP. Value is measured by operator time saved and trustworthy local execution.

## 6. Technology Stack

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Required, portable, mature text-processing ecosystem |
| CLI | Click | Predictable options, help, validation, and exit behavior |
| Terminal UI | Rich | Colored tables and progress-free stream-friendly rendering |
| Domain models | `dataclasses` | Typed, lightweight records without a validation framework |
| Packaging | pip-compatible `pyproject.toml` | Standard isolated installation and console entry point |
| Testing/quality | pytest, Ruff, mypy | Fast local feedback and explicit correctness checks |

## 7. Timeline

| Window | Stage | Outcome |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable command and validated combined-log records |
| Saturday afternoon | Streaming aggregation | Four required metrics with bounded top-k state |
| Sunday morning | Terminal, JSON, CSV renderers | Stable human and pipeline outputs |
| Sunday afternoon | Robustness and performance | Exit behavior, tests, documentation, 1 GB benchmark evidence |

## 8. KPIs

| Metric | MVP target | 1 month | 3 months |
|---|---:|---:|---:|
| Processing time for 1 GB on benchmark laptop | <30 s | <30 s | <25 s where optimization remains clear |
| Valid-line parsing accuracy on supported fixtures | 100% | 100% | 100% |
| Peak memory on 1 GB benchmark | <256 MiB | <256 MiB | <192 MiB |
| Required output/exit contract test pass rate | 100% | 100% | 100% |
| Fresh-install time to first report | <30 s after package download | <30 s | <30 s |

Hardware, OS, filesystem cache state, Python version, and fixture checksum must be recorded with performance results so the time target is reproducible.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined format | High | High | State the grammar; return parse statistics; reject an entirely invalid input |
| Exact unique User-Agent cardinality grows beyond the memory budget | Medium | High | Enforce a configurable hard cardinality ceiling and exit with code 4 |
| Python misses the 1 GB/30 s target | Medium | High | Single pass, compiled parser, batched reads, no per-line Rich work; benchmark early |
| CSV representation becomes ambiguous for multi-table output | Medium | Medium | Use a normalized record schema with `metric`, `key`, `value`, `rank`, and `unit` |
| Broken pipes or unreadable inputs confuse automation | Medium | Medium | Stable diagnostics on stderr and the complete 0/1/2/3/4 exit contract |
| Malformed lines bias percentages | Medium | High | Denominator is `total_valid_requests`; expose valid and skipped counts |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development tools | $0 | Python and all dependencies are open source |
| Infrastructure | $0/month | Local-only; no servers, database, or cloud |
| Distribution | $0 | Source repository and pip-compatible artifacts |
| Labor | One weekend | Primary fixed constraint; no cash budget |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Streaming combined-log parsing from file or stdin | **Must** | Foundation of every result and large-file behavior |
| Top 10 client IPs by valid request count | **Must** | Required incident signal |
| Top 10 URLs by 4xx/5xx response count | **Must** | Required error triage signal |
| Hourly request distribution percentage | **Must** | Required traffic-shape signal |
| Unique User-Agent share | **Must** | Required client-diversity signal |
| Colored terminal, JSON, and CSV output | **Must** | Required human and pipeline interfaces |
| Stable diagnostics and exit codes 0/1/2/3/4 | **Must** | Required for reliable automation |
| gzip input | **Should** | Common log rotation format, but decompression may be piped for MVP |
| Auto-detection/custom nginx formats | **Could** | Useful but conflicts with a small, predictable weekend scope |
| Database, HTTP API, server, authentication, cloud, Kubernetes | **Won't** | Explicitly excluded and unnecessary for local one-shot analysis |

### RICE Scoring (Must and Should)

Confidence is expressed as a decimal in the calculation. Higher scores are implemented first where dependencies permit.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and input | 10 | 5 | 90% | 0.75 | 60.0 |
| Top IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Error URLs | 9 | 5 | 95% | 0.25 | 171.0 |
| Hourly distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Unique User-Agent share and ceiling | 8 | 4 | 80% | 0.50 | 51.2 |
| Terminal/JSON/CSV output | 10 | 5 | 90% | 0.75 | 60.0 |
| Diagnostics and exit codes | 9 | 5 | 95% | 0.50 | 85.5 |
| gzip input | 6 | 3 | 80% | 0.50 | 28.8 |

Dependency order overrides raw RICE where necessary: parsing precedes all metrics, and aggregation precedes rendering.

## 12. Definition of Done

A feature is Done when:

- [ ] Its PRD acceptance criteria and CLI contracts are implemented.
- [ ] Unit and integration tests pass with at least 90% statement coverage for `src/`.
- [ ] Static checks (`ruff check`, `ruff format --check`, `mypy`) pass.
- [ ] Output fixtures and the complete 0/1/2/3/4 exit contract pass.
- [ ] No known critical/high security issue applies to the shipped dependency set.
- [ ] Relevant README and command help are current.
- [ ] Performance claims are backed by a recorded benchmark on the named fixture and hardware.
- [ ] A clean Python 3.11 virtual environment can install the package and run the smoke flow.

## 13. Delivery and Kill Criteria

Ship the MVP when every P0 criterion passes and a 1 GB supported-format fixture completes in under 30 seconds on the designated laptop. Re-scope or stop if a single-pass Python implementation cannot meet that performance threshold after profiling, if exact User-Agent tracking cannot stay within the agreed memory ceiling, or if the weekend limit would require a database/service architecture. The PRD is the behavioral source of truth; architecture and implementation documents refine it without expanding scope.
