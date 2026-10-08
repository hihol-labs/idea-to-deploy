# Strategic Plan: nginx-log-insights

## 1. Product Idea

`nginx-log-insights` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It consumes an nginx access-log file or standard input in one pass and reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent values. Human-readable colored terminal output is the default; stable JSON and CSV modes support automation.

The MVP is deliberately narrow: a zero-cost, open-source utility that provides an immediate incident and traffic snapshot without operating a service, database, or observability stack.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Investigates incidents under time pressure | Needs quick evidence from a large log without uploading it or writing one-off pipelines | One command produces a consistent operational summary locally |
| DevOps engineer | Maintains nginx hosts and deployment pipelines | Repeats fragile `awk`, `sort`, and `uniq` recipes | Packaged parsing, validation, and machine-readable output are reusable |
| Platform engineer | Builds troubleshooting runbooks | Needs predictable output and exit codes for pipelines | JSON/CSV schemas and exit codes `0/1/2/3/4` form an automation contract |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this project | Differentiation |
|---|---|---|---|
| GoAccess | Fast, mature, interactive terminal and HTML reporting | Broader UI/configuration surface than needed; output contract differs | Focused four-metric snapshot, pip-friendly JSON/CSV, Python installation |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, retention, querying, dashboards | Requires services, storage, setup, and operational cost | No services or persistence; immediate local execution |
| AWStats | Established historical web analytics | Stateful reports and legacy-style configuration; not ideal for incident-time streams | Stateless one-pass analysis and explicit automation contracts |
| `grep`/`awk`/`sort` | Ubiquitous and flexible | Recipes are error-prone, repeated, format-sensitive, and often create large intermediate sorts | Named metrics, parse accounting, bounded behavior, consistent output |

## 4. Unique Value Proposition

Get the four nginx traffic signals most useful during triage from a gigabyte-scale log in one local, reproducible command—without deploying or operating anything.

## 5. Business and Licensing Model

The project is free and open source. There is no monetization requirement, hosted tier, telemetry, or paid dependency. Value is measured through adoption in runbooks and reduction in time-to-first-signal, not revenue. A permissive license such as MIT is recommended when implementation begins.

## 6. Technology Strategy

| Component | Decision | Why |
|---|---|---|
| Runtime | Python 3.11 | Required stack, broad laptop availability, efficient line iteration |
| CLI | Click | Stable argument validation, help text, and exit behavior |
| Terminal rendering | Rich | Colored tables with automatic terminal capability handling |
| Domain models | Standard-library dataclasses | Typed, dependency-light records and result objects |
| Parsing/aggregation | Python standard library | Keeps installation small and budget at $0 |
| Packaging | `pyproject.toml` and pip | Required install path and console entry point |

## 7. Delivery Timeline

| Block | Duration | Outcome |
|---|---:|---|
| Saturday morning | 3 hours | Package skeleton, CLI contract, parser, fixtures |
| Saturday afternoon | 4 hours | Streaming aggregation and error/cardinality handling |
| Sunday morning | 3 hours | Terminal, JSON, and CSV renderers |
| Sunday afternoon | 4 hours | Tests, 1 GB benchmark, documentation, release check |

The one-weekend timebox is fixed. P1 work is admitted only after every P0 acceptance criterion and the performance benchmark pass.

## 8. Success Metrics

| Metric | Release target | Measurement |
|---|---:|---|
| Processing time | Less than 30 seconds for a representative 1 GB log on a documented laptop | Repeatable benchmark command, three runs, median reported |
| Valid-line accounting | 100% of fixture lines classified as valid or malformed | Parser tests |
| Report correctness | 100% match to expected results on deterministic fixtures | Golden-output and aggregation tests |
| Peak memory | At most 512 MiB on the representative 1 GB benchmark before configured cardinality exhaustion | Peak RSS measurement |
| Output compatibility | Terminal, JSON, and CSV encode identical metric values | Cross-renderer tests |
| Installability | Clean Python 3.11 virtual environment can install and invoke the console command | Packaging smoke test |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined format | High | High | Declare the accepted grammar, count malformed lines, fail predictably, defer configurable formats to P1 |
| High-cardinality IP/URL/User-Agent data exhausts memory | Medium | High | Enforce a configurable aggregate unique-value ceiling and exit with code 4 before uncontrolled growth |
| Python misses the 1 GB/30 second target | Medium | High | Benchmark the parser early, avoid per-line object churn, compile the regex once, profile before adding features |
| Machine-readable output changes unintentionally | Medium | Medium | Version and golden-test JSON/CSV schemas |
| Colored output contaminates pipelines | Low | Medium | Color only the default terminal renderer; JSON and CSV never emit ANSI sequences |
| Malformed input creates misleading totals | Medium | High | Report valid/malformed counts and use exit code 3 for parse-quality failure |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and dataclasses are open source |
| Infrastructure | $0 | Local-only; no service, database, or cloud resources |
| Distribution | $0 | Source distribution/wheel can be published through free public tooling |
| Labor | One weekend | Fixed owner timebox; no contractor spend |
| Total cash budget | **$0** | Must remain zero for MVP |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream a file or stdin and parse nginx combined access-log lines | **Must** | Foundation for every metric and pipeline use case |
| Report top-10 client IPs | **Must** | Core traffic-source signal |
| Report top-10 URLs with 4xx/5xx responses | **Must** | Core failure-triage signal |
| Report hourly request distribution as percentages | **Must** | Core traffic-shape signal |
| Report unique User-Agent share | **Must** | Core client-diversity signal |
| Render colored terminal, JSON, and CSV outputs | **Must** | Required human and pipeline interfaces |
| Enforce parse and unique-cardinality failure contracts | **Must** | Prevents silent corruption and uncontrolled memory use |
| Accept configurable nginx log formats | **Should** | Expands compatibility but is not needed for the defined MVP format |
| Read gzip-compressed files directly | **Should** | Common operational convenience; shell decompression is an MVP workaround |
| Follow a growing file directly | **Could** | `tail -F ... | nginx-log-insights -` already covers the main need |
| GeoIP, dashboards, retention, alerts, authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the local, stateless, one-weekend product boundary |

### RICE Scoring for Must and Should Features

RICE score is `(Reach × Impact × Confidence) / Effort`, where confidence is a decimal. Values are directional estimates for first-month users and determine implementation order after dependencies are respected.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE |
|---|---:|---:|---:|---:|---:|
| File/stdin streaming and combined-log parser | 10 | 5 | 100% | 0.75 | 66.7 |
| Top-10 IP aggregation | 10 | 4 | 95% | 0.25 | 152.0 |
| Error URL aggregation | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly distribution | 9 | 4 | 95% | 0.25 | 136.8 |
| Unique User-Agent share | 8 | 3 | 90% | 0.25 | 86.4 |
| Terminal/JSON/CSV rendering | 10 | 5 | 95% | 0.75 | 63.3 |
| Parse/cardinality failure contracts | 9 | 5 | 90% | 0.50 | 81.0 |
| Configurable log formats | 6 | 3 | 60% | 1.00 | 10.8 |
| Direct gzip input | 5 | 2 | 90% | 0.25 | 36.0 |

The parser is implemented first despite lower arithmetic RICE because it is a dependency for all higher-scoring metrics. Within that dependency boundary, work follows descending value.

## 12. Definition of Done

A P0 feature is done when:

- [ ] Its acceptance criteria in `PRD.md` are executable as tests.
- [ ] Python 3.11 lint/type checks selected by the project pass.
- [ ] Unit and integration tests pass with at least 90% branch coverage in parser, aggregation, and renderer modules.
- [ ] JSON/CSV golden contracts and terminal smoke checks pass.
- [ ] The documented representative 1 GB input completes in under 30 seconds on the reference laptop without exceeding 512 MiB peak RSS.
- [ ] A clean virtual environment installs the wheel and invokes the CLI.
- [ ] Documentation and `CLAUDE.md` status are current.
- [ ] No known critical or high-severity security issue remains.

## 13. Kill and Pivot Criteria

Stop or materially redesign the MVP if an optimized, profiled Python implementation cannot process the representative 1 GB fixture in under 30 seconds on the reference laptop, if exact aggregates cannot remain within the 512 MiB memory guard on representative production-shaped logs, or if supported log-format coverage is too narrow for the initial operators. A pivot may use documented approximate heavy-hitter algorithms, but it must change the PRD and output semantics first.

## 14. Related Documents

System boundaries and contracts are defined in `PROJECT_ARCHITECTURE.md`; requirements in `PRD.md`; sequencing and verification in `IMPLEMENTATION_PLAN.md`; implementation prompts in `CLAUDE_CODE_GUIDE.md`.
