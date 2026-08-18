# Strategic Plan: nginx-insights

## 1. Product Idea

`nginx-insights` is a local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Its default Rich terminal report is intended for investigation by a person; JSON and CSV modes make the same report usable in shell pipelines.

The product is deliberately local and stateless. It creates no service, account, database, or persistent index. The MVP is delivered over one weekend with a $0 cash budget and an open-source dependency stack.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Diagnoses incidents under time pressure | Needs a useful traffic summary without shipping logs elsewhere | One local command, streaming input, readable colored output |
| DevOps engineer | Automates operational reporting | Ad hoc text output is brittle in pipelines | Stable `--json` and `--csv` schemas with documented exit codes |
| Platform engineer | Handles sensitive or large logs | Central observability systems may be unavailable, costly, or inappropriate | Local-only processing, no upload, no database, 1 GB performance target |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | nginx-insights differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI and configuration surface than a small pipeline tool needs | Focused four-metric contract and simple machine-readable output |
| Logstash + Elastic + Kibana | Powerful ingestion, search, dashboards, retention | Infrastructure, storage, administration, and cost are disproportionate for a local one-off analysis | Zero-service, zero-storage, pip-installed local execution |
| AWStats | Established historical web analytics | Persistent reports and legacy-oriented workflow; less natural for stdin pipelines | Streaming CLI designed for current DevOps workflows |
| `grep` / `awk` / `sort` | Usually installed and composable | Parsing is fragile, commands are hard to reproduce, and multiple passes are common | Tested nginx parsing, one pass, consistent metrics and schemas |

## 4. Unique Value Proposition

Get the four nginx traffic signals most useful during an incident from a local stream in one reproducible command, without deploying or operating an observability stack.

## 5. Business Model and License

The product is an open-source utility with no paid tier, authentication, telemetry, or hosted component. The initial business objective is engineering utility and adoption, not revenue. Distribution through PyPI keeps installation familiar; the repository license should be permissive (MIT is recommended). CAC, LTV, and unit economics are not applicable to the non-commercial MVP.

## 6. Technology Strategy

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required platform; fast enough with a compiled regex and single-pass aggregation |
| CLI | Click | Stable argument validation, help, and conventional exit behavior |
| Terminal UI | Rich | Color, tables, and automatic terminal capability handling |
| Domain model | Standard-library dataclasses | Typed records without a validation framework or runtime service |
| Packaging | `pyproject.toml`, pip | Standard install and console-script distribution |
| Tests/quality | pytest, Ruff, mypy | Fast local feedback and explicit parser/output contracts |

## 7. Delivery Timeline

| Window | Work | Result |
|---|---|---|
| Saturday morning | Package skeleton, parser, domain types | Installable command parses common/combined lines |
| Saturday afternoon | Streaming aggregators and calculations | Four required metrics produced in one pass |
| Sunday morning | terminal, JSON, and CSV renderers | Stable human and pipeline outputs |
| Sunday afternoon | error handling, tests, benchmark, docs | Release candidate demonstrated on a 1 GB fixture |

## 8. Success Metrics

| Metric | Release target | First month target | Measurement |
|---|---:|---:|---|
| Performance | 1 GB in under 30 seconds on the reference laptop | No regression above 10% | Reproducible local benchmark command and machine metadata |
| Correctness | 100% of golden fixtures match expected metrics | Zero unresolved P0 calculation bugs | pytest fixtures and issue tracker |
| Pipeline compatibility | JSON and CSV parse cleanly; no decoration on stdout | Zero schema-breaking changes in 0.x without release note | Schema tests |
| Installability | Clean Python 3.11 virtualenv install succeeds | Successful install instructions on Linux and macOS | CI matrix and manual smoke test |
| Utility | All four required metrics in one invocation | At least five real operational uses or users | Opt-in repository feedback; no telemetry |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Custom nginx formats do not match MVP parser | High | Medium | Clearly support common/combined only, report skipped lines, design parser protocol for later formats |
| Python misses the 1 GB/30 s target | Medium | High | One pass, precompiled parser, lean dataclasses, batched text I/O, benchmark before release |
| Cardinality consumes excessive memory | Medium | High | Configurable hard limit for exact unique User-Agents; deterministic exit `4` on exhaustion |
| Output formats drift apart | Medium | High | One report dataclass shared by all renderers and golden schema tests |
| Bad lines silently distort percentages | Medium | High | Define denominator as valid records, expose valid/skipped counts, exit `3` when none are valid |
| Terminal color contaminates pipelines | Low | Medium | Color only in terminal mode; JSON/CSV always undecorated and machine-parseable |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development | $0 cash | One-weekend contributor time |
| Runtime and hosting | $0 | Runs locally; there is no hosted component |
| Dependencies | $0 | Python, Click, Rich, and development tools are open source |
| Distribution | $0 | Public source repository and PyPI |
| Total MVP cash budget | **$0** | No cloud, database, server, or paid service |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream common/combined logs from files or stdin | **Must** | Foundation of the local workflow |
| Top 10 client IPs | **Must** | Required incident signal |
| Top 10 URLs with 4xx/5xx responses | **Must** | Required failure signal |
| Hourly request percentage distribution | **Must** | Required traffic-shape signal |
| Unique User-Agent share with cardinality guard | **Must** | Required diversity signal and safe failure behavior |
| Rich terminal report | **Must** | Required default output |
| JSON and CSV reports | **Must** | Required pipeline outputs |
| Gzip input | **Should** | Common operational convenience, but shell decompression is a workaround |
| Configurable top-N | **Could** | Useful generalization after the fixed top-10 contract is stable |
| Custom nginx format expressions | **Could** | Broadens compatibility at significant parser complexity |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Explicitly outside the local stateless product boundary |

### RICE Scoring (Must and Should)

Confidence is represented as a decimal in the calculation. Scores order delivery while dependency constraints still apply.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream files/stdin and parse logs | 10 | 5 | 100% | 1.0 | 50.0 |
| Rich terminal report | 9 | 4 | 90% | 0.5 | 64.8 |
| Top 10 client IPs | 9 | 4 | 95% | 0.4 | 85.5 |
| Top error URLs | 9 | 5 | 95% | 0.6 | 71.3 |
| Hourly percentage distribution | 8 | 4 | 95% | 0.4 | 76.0 |
| Unique User-Agent share and guard | 7 | 4 | 85% | 0.6 | 39.7 |
| JSON and CSV reports | 8 | 4 | 90% | 0.8 | 36.0 |
| Gzip input | 5 | 2 | 80% | 0.4 | 20.0 |

Implementation order in `IMPLEMENTATION_PLAN.md` respects both these scores and the parser/report dependencies.

## 12. Definition of Done

A release feature is done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 code is formatted, linted, typed, and imports without errors.
- [ ] Unit and integration tests pass with at least 90% coverage of product modules.
- [ ] Terminal, JSON, CSV, malformed-input, and exit-code golden tests pass.
- [ ] The 1 GB reference benchmark completes in under 30 seconds on the recorded laptop configuration.
- [ ] No known critical or high-severity security issue remains.
- [ ] Installation and CLI help are manually smoke-tested in a clean virtual environment.
- [ ] User and developer documentation are current.

## 13. Kill and Reassessment Criteria

Reassess the Python approach if an optimized single-pass implementation cannot process the reference 1 GB log in under 30 seconds. Do not ship the MVP if common/combined parsing cannot be made deterministic, if output schemas disagree, or if exact User-Agent cardinality can exceed its limit without exit `4`. Do not solve these problems by introducing a server, database, cloud service, or Kubernetes.

