# Strategic Plan: Nginx Stream Analyzer

## 1. Product Idea

Nginx Stream Analyzer is a local, installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and produces an immediately useful operational snapshot without uploading logs or operating infrastructure: top client IPs, error-heavy URLs, hourly traffic distribution, and the share of unique User-Agents. The default is colored terminal text, with JSON and CSV for pipelines.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE | Needs a fast incident snapshot on a laptop or host | One command, bounded-memory streaming, actionable rankings |
| Platform engineer | DevOps | Needs repeatable evidence in shell pipelines | Stable `--json` and `--csv` schemas and explicit exit codes |
| Small-team operator | Sysadmin | Full observability stacks are too costly or heavy | Free, local, stateless pip-installed CLI |

## 3. Competitive Analysis

| Alternative | Strengths | Limitations for this use case | Our differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI/reporting surface; external binary and configuration overhead | Narrow incident-focused output and Python/pip workflow |
| Logstash + Elastic + Kibana | Powerful ingestion, search, dashboards, retention | Requires services, storage, setup, and operational cost | Zero services, zero storage, local one-shot analysis |
| AWStats | Established historical web statistics | Batch-oriented, dated workflow, persistent reports/configuration | Streaming CLI with pipeline-friendly machine formats |
| `grep`/`awk`/`sort` | Ubiquitous and composable | Fragile parsing, repeated passes, unbounded sort patterns, inconsistent output | One tested parser, one pass, stable metrics contract |

## 4. Unique Value Proposition

Get a trustworthy nginx incident summary from a large local log in one command, without a database, server, or paid service.

## 5. Business Model

The project is open source and free. There is no monetization requirement for the one-weekend MVP; value is measured in operator time saved and adoption. Contributions and optional community sponsorship may support maintenance later, but no paid feature is in scope.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required, portable, strong standard-library streaming support |
| CLI | Click | Predictable commands, options, validation, and exit behavior |
| Terminal output | Rich | Accessible colored tables and controllable color behavior |
| Domain models | `dataclasses` | Typed, lightweight records without validation-framework overhead |
| Packaging | `pyproject.toml` + pip | Standard install and console-script entry point |
| Tests | pytest | Fast unit, integration, golden-output, and performance checks |

## 7. Timeline

| Block | Focus | Outcome |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable CLI reads common/combined logs safely |
| Saturday afternoon | Streaming aggregates | Four required metrics computed in one pass |
| Sunday morning | Renderers and exit behavior | Text, JSON, and CSV contracts complete |
| Sunday afternoon | QA, performance, docs | 1 GB benchmark evaluated; release candidate ready |

## 8. KPIs

| Metric | MVP target | Measurement |
|---|---:|---|
| Performance | 1 GB in under 30 seconds on the reference laptop | Timed generated-log benchmark with machine details recorded |
| Memory | Bounded by cardinality controls, not total line count | Peak RSS benchmark at multiple file sizes |
| Parse reliability | At least 99.9% of valid fixtures parsed | Parser fixture suite |
| Output correctness | 100% golden tests for all three formats | Integration tests |
| Ease of use | First valid report in under 30 seconds after install | Clean-environment smoke test |

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Custom nginx formats differ from supported formats | High | Medium | State supported format, count malformed lines, fail clearly when no valid records exist |
| Exact unique sets exhaust memory on hostile/high-cardinality input | Medium | High | Enforce configurable cardinality guard; exit `4` on exhaustion rather than silently approximate |
| Python misses the 1 GB/30 s goal | Medium | High | Benchmark early; precompile parsing, process bytes/lines once, avoid per-record object retention |
| CSV shape is ambiguous for heterogeneous metrics | Medium | Medium | Specify a normalized row schema with metric/rank/key/value fields |
| Terminal color breaks redirected output | Low | Medium | Auto-disable without TTY and provide explicit color policy |
| Malformed lines hide operational problems | Medium | Medium | Report valid/malformed counts and use exit `3` when no analyzable records remain |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Software and libraries | $0 | Open-source stack |
| Hosting and storage | $0 | Local, stateless execution |
| Delivery | One weekend | Approved scope constraint |
| Ongoing infrastructure | $0/month | No service, database, or cloud |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream nginx log from file or stdin | Must | Foundation of the product and pipeline use |
| Top-10 client IPs | Must | Immediate source-volume diagnosis |
| Top-10 URLs by 4xx/5xx errors | Must | Locates failing routes |
| Hourly request percentages | Must | Shows load distribution across the day |
| Unique User-Agent share | Must | Required client-diversity signal |
| Colored terminal output | Must | Default human interface |
| JSON and CSV output | Must | Required automation interface |
| Stable `0/1/2/3/4` exits and diagnostics | Must | Required operational reliability |
| Configurable top-N and cardinality ceiling | Should | Useful control while preserving top-10 default |
| Gzip input | Could | Convenient but shell decompression is an adequate MVP workaround |
| Database, HTTP API, server, auth, cloud, Kubernetes | Won't | Contradicts the local stateless product boundary |

### RICE Scoring (Must + Should)

| Feature | Reach | Impact | Confidence | Effort (days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream input and parse records | 10 | 5 | 90% | 0.75 | 60.0 |
| Core four-metric aggregation | 10 | 5 | 90% | 1.0 | 45.0 |
| Terminal report | 9 | 4 | 90% | 0.5 | 64.8 |
| JSON and CSV renderers | 7 | 4 | 90% | 0.5 | 50.4 |
| Exit/diagnostic contract | 10 | 4 | 95% | 0.5 | 76.0 |
| Configurable top-N/cardinality ceiling | 5 | 3 | 80% | 0.25 | 48.0 |
| Pip packaging | 10 | 4 | 95% | 0.25 | 152.0 |

Dependency order takes precedence where a higher RICE feature relies on parsing or aggregation.

## 12. Definition of Done

A feature is Done when:

- [ ] Behavior and acceptance criteria in `PRD.md` are satisfied.
- [ ] Python 3.11 code passes formatting, linting, and type checks selected during implementation.
- [ ] Unit and integration tests pass with at least 90% statement coverage on parser, aggregation, and rendering modules.
- [ ] Golden outputs pass for terminal-without-color, JSON, and CSV.
- [ ] The performance benchmark records 1 GB in under 30 seconds on the named reference laptop.
- [ ] Peak memory and unique-cardinality exhaustion behavior are tested.
- [ ] Documentation and `CLAUDE.md` status are updated.
- [ ] No known Critical or High security issue remains.
- [ ] The exact candidate satisfies the project verification contract before release.

## 13. MVP Success and Stop Conditions

Ship when all Must features and the Definition of Done are met within the $0/one-weekend boundary. Re-scope or stop if exact metrics cannot meet the target without unbounded memory, the supported log format cannot be specified deterministically, or the 1 GB target remains above 30 seconds after profiling and one focused optimization pass.
