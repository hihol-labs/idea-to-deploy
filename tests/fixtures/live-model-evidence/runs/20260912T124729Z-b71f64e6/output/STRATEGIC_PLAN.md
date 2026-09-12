# Strategic Plan: nginx-log-top

## 1. Product Idea

`nginx-log-top` is an installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich-colored terminal text is the default; JSON and CSV make the same results usable in pipelines.

The MVP is deliberately local and stateless. It has no service tier, credentials, database, network dependency, or telemetry. A one-weekend delivery and a $0 operating budget favor a focused Unix-style CLI over a general observability platform.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Incident responder | Needs a useful traffic/error summary before a larger stack is available | Produces four actionable aggregates from a local file or stdin in one command |
| DevOps engineer | Platform/operator | Frequently triages copied or rotated nginx logs | Handles large files with bounded-memory streaming and script-friendly formats |
| Backend engineer | Service owner | Needs to distinguish noisy clients, failing routes, and client diversity | Gives ranked IP/error URL views plus hourly and User-Agent percentages |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Fast, mature, interactive and HTML reports | Broader configuration/UI surface; output may be more than a quick pipeline needs | Narrow four-metric contract, pip install, deterministic JSON/CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards, retention | Requires services, storage, setup, and ongoing resources | Zero-service local analysis with no database |
| AWStats | Established historical web analytics | Batch/report orientation and dated operational workflow | Immediate stream processing aimed at incident triage |
| `grep`/`awk`/`sort` | Ubiquitous and composable | Fragile parsing, repeated scans, locale differences, unbounded sort intermediates | One parser, one pass, stable schema, explicit error behavior |

## 4. Unique Value Proposition

Get the four nginx traffic signals most useful during local triage from a gigabyte-scale log in one predictable, pipeline-safe command—without deploying or operating anything.

## 5. Business Model

The project is open source and free. There is no paid tier, hosted service, tracking, or monetization in the MVP. Value is measured through adoption, correctness, speed, and contributor health rather than revenue. If stewardship later requires funding, sponsorship can be evaluated without changing the local-only product contract.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Required, broadly available, strong text-streaming support |
| CLI | Click | Stable command/options contract and consistent usage errors |
| Terminal rendering | Rich | Readable ranked tables, colors, and TTY-aware presentation |
| Domain models | `dataclasses` | Typed, low-overhead structures without a validation framework |
| Packaging | `pyproject.toml` + pip | Standard installable CLI distribution |
| Testing | pytest | Focused unit, integration, golden-output, and performance tests |

See `PROJECT_ARCHITECTURE.md` for module boundaries and `IMPLEMENTATION_PLAN.md` for delivery order.

## 7. Timeline

| Window | Work | Result |
|---|---|---|
| Saturday morning | Package skeleton, models, parser | Valid combined-log lines become typed records |
| Saturday afternoon | Streaming aggregation and cardinality guard | All four metrics computed in one pass |
| Sunday morning | Text, JSON, CSV renderers and CLI contract | Human and pipeline interfaces complete |
| Sunday afternoon | Tests, profiling, docs, packaging | Release candidate validated against functional and performance gates |

## 8. KPIs

| Metric | MVP / first month | 3 months | 6 months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | < 30 s | < 30 s | < 25 s |
| Valid-line parsing accuracy on fixture corpus | 100% | 100% | 100% |
| Peak RSS on 1 GB bounded-cardinality fixture | < 300 MB | < 250 MB | < 200 MB |
| Automated coverage of core parser/aggregator | >= 90% | >= 92% | >= 92% |
| Pipeline format stability | schema v1 | no breaking change | no breaking change |

The reference laptop, fixture generator, command, and measurements must be recorded with performance results; elapsed time alone is not reproducible evidence.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined format | High | High | State the supported format, expose strict/lenient behavior, maintain malformed and escaped fixtures |
| Exact unique User-Agent counting exhausts memory on adversarial cardinality | Medium | High | Configurable cardinality ceiling and exit code 4; never silently approximate |
| Python misses the 1 GB / 30 s target | Medium | High | Single pass, compiled regex, minimal allocations, no full record retention, benchmark early |
| CSV representation is ambiguous for four differently shaped reports | Medium | Medium | Long-form rows with stable `report`, `key`, `count`, and `percentage` columns |
| Pipe and file errors are mistaken for empty data | Medium | High | Distinct exit codes, stderr diagnostics, and broken-pipe handling |
| ANSI styling contaminates redirected output | Low | Medium | Enable color only for text on a TTY unless explicitly overridden |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and pytest are open source |
| Infrastructure | $0/month | No server, cloud, database, or telemetry |
| Distribution | $0 | Source and wheel can be published through free public tooling |
| Delivery labor | One weekend | Explicit project constraint; no cash budget assigned |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream file or stdin without loading the full log | Must | Core scalability and Unix pipeline value |
| Parse nginx combined access-log records | Must | Required foundation for every metric |
| Top-10 client IPs | Must | Explicit primary report |
| Top-10 URLs by 4xx/5xx count | Must | Explicit primary error report |
| Hourly request percentage distribution | Must | Explicit primary time report |
| Exact unique User-Agent share | Must | Explicit primary diversity report |
| Rich terminal, JSON, and CSV output | Must | Explicit human and pipeline interfaces |
| Strict/lenient malformed-line policy and complete exit codes | Must | Makes automation reliable |
| Custom top-N value | Should | Useful extension with low complexity after fixed top-10 MVP |
| Read gzip-compressed files directly | Could | Helpful for rotated logs but not needed for core value |
| Additional nginx `log_format` definitions | Could | Broadens adoption after the initial parser is proven |
| Authentication, database, HTTP API, server, cloud, Kubernetes | Won't | Contradicts local stateless one-weekend scope |
| Live dashboard or historical retention | Won't | Belongs to broader alternatives such as GoAccess or Elastic |

### RICE Scoring (Must + Should)

Confidence is expressed as a decimal in the calculation; scores are sorted descending.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Parse and stream combined logs | 10 | 5 | 90% | 0.75 | 60.0 |
| Top-10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top-10 error URLs | 9 | 5 | 95% | 0.35 | 122.1 |
| Hourly percentage distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Rich/JSON/CSV output | 10 | 4 | 90% | 0.75 | 48.0 |
| Unique User-Agent share and guard | 8 | 4 | 80% | 0.75 | 34.1 |
| Error policy and exit codes | 9 | 4 | 90% | 0.50 | 64.8 |
| Configurable top-N | 5 | 2 | 90% | 0.20 | 45.0 |

Dependencies override pure score order: parsing/streaming must precede every aggregate. Within that constraint, implementation follows the ranked user value reflected in `IMPLEMENTATION_PLAN.md`.

## 12. Definition of Done

A feature is Done when:

- [ ] Behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Python 3.11 code imports and the package builds without errors.
- [ ] Unit and integration tests pass with core coverage at or above 90%.
- [ ] Golden text/JSON/CSV outputs pass and contain no accidental ANSI sequences.
- [ ] The 1 GB reference benchmark completes in under 30 seconds on the documented laptop.
- [ ] Code review passes with no known Critical or High security issue.
- [ ] `README.md` and CLI help are current.
- [ ] The pip-built wheel installs into a clean virtual environment and smoke tests pass.

## 13. Kill Criteria

Stop or rescope the MVP if a representative 1 GB file cannot meet 30 seconds after profiling and one bounded optimization pass; exact unique-cardinality cannot be bounded with an explicit failure contract; or the combined-log parser cannot achieve 100% correctness on the agreed fixture corpus. Do not add services or persistent storage to disguise failure against the local CLI premise.
