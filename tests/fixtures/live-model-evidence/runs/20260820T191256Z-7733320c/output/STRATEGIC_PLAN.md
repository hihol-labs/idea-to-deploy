# Strategic Plan: Nginx Stream Analytics CLI

## 1. Product Idea

Build an open-source, local Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. It emits colored terminal output by default and stable JSON or CSV for pipelines. It keeps no persistent state and sends no data off the machine.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a useful traffic/error summary without standing up infrastructure | One local command produces an immediate report |
| Platform engineer | Maintains hosts and CI jobs | Needs composable output and predictable failures | `--json`, `--csv`, documented schemas, and exit codes |
| Operations lead | Reviews traffic and reliability patterns | Needs quick hourly and client diversity indicators | Percent-based hourly distribution and unique User-Agent share |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Fast, mature, interactive reports | Broader UI/configuration surface than a small pipeline tool | Narrow metrics, stable machine formats, pip install |
| Logstash + Elastic + Kibana | Powerful ingestion, storage, and dashboards | Operationally heavy, persistent, and incompatible with a $0 local weekend scope | No services or database; immediate local analysis |
| AWStats | Established historical reporting | Batch/web-report orientation and persistent history | Streaming stdin/file input and terminal-first UX |
| `grep`/`awk` pipelines | Ubiquitous and dependency-light | Fragile parsing, inconsistent aggregation, hard-to-maintain schemas | Tested nginx parsing and one explicit contract |

## 4. Unique Value Proposition

Get the four incident-relevant nginx traffic summaries from a large log in one private, pipeline-friendly local command—without deploying or operating a service.

## 5. Business Model

The project is free and open source. There are no paid tiers, hosted services, telemetry, CAC, or revenue assumptions. Value is measured as saved operator time and reduced setup burden. Distribution uses public Python package infrastructure at no project cost.

## 6. Technology Stack

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Required, portable, mature streaming I/O |
| CLI | Click | Predictable options, help, and exit handling |
| Terminal | Rich | Colored, readable terminal tables with TTY-aware behavior |
| Domain models | `dataclasses` | Explicit structures without a framework |
| Packaging | pip-compatible `pyproject.toml` | Standard install and console entry point |
| Tests | pytest | Fast unit, CLI, golden-output, and performance tests |

## 7. Timeline

| Weekend block | Outcome |
|---|---|
| Saturday morning | Packaging, domain contracts, streaming parser |
| Saturday afternoon | Aggregation and metric correctness |
| Sunday morning | terminal/JSON/CSV renderers and CLI error contract |
| Sunday afternoon | tests, 1 GB benchmark, docs, package smoke test |

## 8. KPIs

| Metric | Release target | One month | Three months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | <30 s | <30 s | <25 s if profiling supports it |
| Peak memory on representative high-cardinality input | bounded by documented guardrails | no OOM reports | guardrail tuned from evidence |
| Correctness suite | all golden cases pass | no open P0 defect | no regression in schemas |
| Install-to-first-report time | <5 min | <5 min | <3 min |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined-log grammar | High | High | State the supported format, count malformed lines, fail if none are valid |
| High-cardinality IP/URL/User-Agent data exhausts memory | Medium | High | Explicit configurable-safe cardinality ceiling and exit code 4 |
| Python misses the 1 GB/30 s target | Medium | High | Byte-oriented single pass, compiled regex/parser profiling, benchmark gate |
| ANSI color contaminates redirected output | Low | Medium | Color only for TTY terminal mode; JSON/CSV never contain ANSI |
| CSV representation is ambiguous | Medium | Medium | Long-form schema with metric/rank/key/count/percentage columns |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development | $0 cash | One-weekend contributor effort |
| Runtime and hosting | $0 | Local CLI; no hosted component |
| Dependencies and CI | $0 | Open-source libraries and free public tooling |
| Ongoing operations | $0 | No server, database, or cloud resource |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream from file or stdin | Must | Required for local and pipeline use |
| Parse supported nginx combined access-log lines | Must | All metrics depend on valid parsing |
| Top-10 client IPs | Must | Core traffic diagnostic |
| Top-10 4xx/5xx URLs | Must | Core error diagnostic |
| Hourly request distribution | Must | Core temporal diagnostic |
| Unique User-Agent share | Must | Core client-diversity diagnostic |
| Colored terminal, JSON, and CSV output | Must | Required human and pipeline interfaces |
| Malformed-line summary and stable exit codes | Must | Operational predictability |
| Compressed input | Should | Common log archival workflow but shell decompression is viable |
| Configurable top-N | Could | Useful extension after the fixed top-10 contract is stable |
| Authentication, database, HTTP API, server, cloud, Kubernetes | Won't | Explicitly outside a private stateless CLI |

### RICE Scoring (Must and Should)

RICE = Reach × Impact × Confidence / Effort. Confidence is expressed as a decimal in the calculation.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE |
|---|---:|---:|---:|---:|---:|
| Hourly percentage distribution | 9 | 4 | 90% | 0.5 | 64.8 |
| File/stdin CLI and exit contract | 10 | 5 | 95% | 0.75 | 63.3 |
| Top IP and error-URL aggregations | 10 | 5 | 90% | 0.75 | 60.0 |
| Terminal, JSON, and CSV renderers | 10 | 4 | 90% | 0.75 | 48.0 |
| Streaming parser and malformed-line handling | 10 | 5 | 90% | 1.0 | 45.0 |
| Unique User-Agent share with guardrail | 9 | 4 | 80% | 0.75 | 38.4 |
| Compressed input | 5 | 2 | 70% | 0.5 | 14.0 |

Dependencies override raw RICE where necessary: parser contracts precede every aggregation, then work otherwise follows descending value.

## 12. Definition of Done

A feature is done when:

- [ ] Python 3.11 code is formatted, linted, and type-checked under the project configuration.
- [ ] Unit and CLI tests pass; core parser/aggregator coverage is at least 90%.
- [ ] Golden terminal, JSON, and CSV contracts pass.
- [ ] The 1 GB reference benchmark completes in under 30 seconds on the documented laptop profile.
- [ ] Package installation and console-entry-point smoke tests pass.
- [ ] Documentation and schemas match behavior.
- [ ] No known critical/high security issue remains.
- [ ] A current Idea to Deploy verification receipt accepts the exact candidate.

## 13. Release and Kill Criteria

Release only if all Must features and Definition of Done checks pass. Stop or rescope the MVP if a representative 1 GB file cannot meet 30 seconds after profiling, if bounded-memory behavior cannot be achieved for the declared cardinality envelope, or if reliable parsing requires supporting unbounded nginx format customization within the weekend.

See [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), [PRD.md](PRD.md), and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
