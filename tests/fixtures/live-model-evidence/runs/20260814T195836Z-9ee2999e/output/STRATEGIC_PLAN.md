# Strategic Plan: nginx-stream-report

## 1. Product Idea

`nginx-stream-report` is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four operational views without uploading logs or provisioning infrastructure: top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Human-readable colored terminal output is the default; JSON and CSV support automation.

The MVP is deliberately narrow: a zero-cost, one-weekend utility for quick incident triage and routine log inspection, not an observability platform.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE/DevOps responder | Needs a useful overview before a full stack is available | One command summarizes a local or piped log |
| Platform engineer | Automation owner | Needs stable machine-readable output in shell pipelines | `--json` and `--csv` with documented schemas and exit codes |
| Small-team operator | Maintainer without an observability budget | Cannot justify maintaining Elastic or another service | Local, stateless, open-source processing with no recurring cost |

## 3. Competitive Analysis

| Alternative | Strength | Limitation for this use case | Differentiator here |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI/configuration surface than a focused pipeline command | Small fixed report contract and native JSON/CSV pipeline modes |
| Logstash + Elastic + Kibana | Powerful ingestion, search, retention, dashboards | Operational cost and persistent infrastructure are disproportionate | No services, database, or log upload |
| AWStats | Established web-log reporting | Batch-oriented generated reports and older operational workflow | Stream input and immediate terminal feedback |
| `grep`/`awk` pipelines | Installed almost everywhere and composable | Fragile parsing, hard-to-reuse aggregations, inconsistent output contracts | Tested nginx parsing and one stable cross-format interface |

## 4. Unique Value Proposition

Get a pipeline-friendly nginx incident summary from a large local log in one command, with no service, database, configuration stack, or recurring cost.

## 5. Business Model

Open source at no charge. There is no paid tier, telemetry, hosted service, or monetization requirement for the MVP. Value is measured through adoption and saved operator time, not revenue; CAC and LTV are therefore not applicable.

## 6. Technology Stack

| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, familiar to operations teams |
| CLI | Click | Predictable argument validation, help, and exit behavior |
| Terminal rendering | Rich | Accessible color and table rendering with terminal detection |
| Domain models | `dataclasses` | Lightweight typed records without persistence machinery |
| Packaging | pip-compatible `pyproject.toml` | Standard installation and console-script entry point |
| Processing | Single-process streaming | Keeps deployment and memory behavior simple and auditable |

## 7. Timeline

| Period | Stage | Result |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable command and valid-line model |
| Saturday afternoon | Aggregation | All four metrics computed in one pass |
| Sunday morning | Text, JSON, CSV renderers | Stable human and pipeline outputs |
| Sunday afternoon | Tests, benchmark, documentation | Release candidate meeting correctness and performance gates |

## 8. KPIs

| Metric | Release target | One month | Three months |
|---|---:|---:|---:|
| Processing performance | 1 GB in under 30 seconds on the reference laptop | No regression | No regression |
| Peak resident memory | Bounded by unique-key policy and documented limit | No exhaustion on reference corpus | Limit tuned from feedback |
| Output correctness | 100% of golden fixtures | 100% | 100% |
| Installation-to-first-report | Under 5 minutes | Under 5 minutes | Under 3 minutes |
| External users successfully running the CLI | 1 release validator | 10 | 30 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined format | High | High | Fail clearly on malformed records, document the grammar, and defer configurable formats |
| High-cardinality IP/URL/User-Agent data exhausts memory | Medium | High | Apply an explicit configurable cardinality ceiling and exit with code 4 before uncontrolled growth |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early, parse once, avoid per-line regex recompilation and object retention |
| JSON/CSV schemas drift | Medium | Medium | Golden-output tests and versioned field contract |
| Terminal color contaminates pipelines | Low | Medium | Color only in text mode on suitable terminals; JSON/CSV never contain ANSI escapes |
| Scope grows toward a hosted analytics system | Medium | High | Keep server, database, auth, cloud, and Kubernetes in Won't scope |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development tools | $0 | Python and dependencies are open source |
| Hosting/infrastructure | $0 | Local CLI only |
| Database/managed services | $0 | None used |
| Distribution | $0 | Source repository and pip-compatible artifact |
| Total MVP budget | $0 | One-weekend engineering effort is the only input |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream combined-format nginx logs from a file or stdin | **Must** | Foundation for every report and for bounded processing |
| Top 10 client IPs | **Must** | Core traffic/source diagnostic |
| Top 10 URLs by 4xx/5xx count | **Must** | Core failure diagnostic |
| Hourly request percentages | **Must** | Required workload-shape view |
| Unique User-Agent share | **Must** | Required client-diversity signal |
| Colored terminal output | **Must** | Required default interaction |
| JSON output | **Must** | Required automation interface |
| CSV output | **Must** | Required pipeline/export interface |
| Configurable unique-cardinality ceiling | **Must** | Makes memory exhaustion explicit and safe |
| Gzip input | **Should** | Common operational convenience, but shell decompression is a workaround |
| `--no-color` override | **Should** | Useful for captured text output |
| Configurable nginx log formats | **Could** | Broadens adoption but threatens weekend scope |
| Approximate heavy-hitter algorithm | **Could** | Could reduce cardinality memory at the cost of exactness |
| Database, HTTP API, auth, server, cloud, Kubernetes | **Won't** | Contradicts the local stateless product boundary |

### RICE Scoring (Must and Should)

Confidence is represented as a decimal in the formula `(Reach × Impact × Confidence) / Effort`.

| Feature slice | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming input and combined-log parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Core four-metric aggregation | 10 | 5 | 90% | 1.0 | 45.0 |
| Default Rich terminal report | 9 | 4 | 90% | 0.5 | 64.8 |
| JSON renderer and schema | 8 | 4 | 95% | 0.35 | 86.9 |
| CSV renderer and schema | 7 | 3 | 90% | 0.35 | 54.0 |
| Cardinality ceiling and exhaustion handling | 10 | 5 | 80% | 0.5 | 80.0 |
| `--no-color` | 5 | 2 | 95% | 0.15 | 63.3 |
| Gzip input | 4 | 2 | 80% | 0.25 | 25.6 |

Dependencies override raw RICE order: parsing precedes aggregation and renderers; cardinality protection is built with aggregation rather than bolted on later.

## 12. Definition of Done

A feature is Done when:

- [ ] Its PRD acceptance criteria and output contract are implemented.
- [ ] Python 3.11 static checks and unit tests pass with at least 90% branch coverage for parser, aggregation, and renderers.
- [ ] Integration tests pass for file input, stdin, text, JSON, CSV, malformed input, and all exit codes.
- [ ] The fixed 1 GB reference fixture completes in under 30 seconds on the documented laptop profile.
- [ ] Peak memory and cardinality-exhaustion behavior are measured and recorded.
- [ ] Documentation and examples match the released interface.
- [ ] No known Critical or High security issue remains.
- [ ] The installable artifact is manually smoke-tested in a clean Python 3.11 virtual environment.

## 13. Kill Criteria

Stop or redesign the MVP if a representative 1 GB log cannot meet 30 seconds after profiling and bounded optimization, if exact aggregation cannot be made memory-safe under the documented cardinality ceiling, or if supporting real combined-format logs requires adding persistent or server infrastructure. These criteria protect the focused value proposition rather than justify scope expansion.

