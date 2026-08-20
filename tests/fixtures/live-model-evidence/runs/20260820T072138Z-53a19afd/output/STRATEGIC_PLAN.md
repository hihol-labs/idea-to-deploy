# Strategic Plan: nginx Stream Analytics CLI

## 1. Product Idea

Build an installable, local Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx combined-format access logs as a stream and reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich colored text is the default; JSON and CSV make the same results usable in pipelines.

The product is intentionally local, stateless, and single-process. It has no authentication, database, HTTP API, server process, cloud dependency, or Kubernetes deployment.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE investigating an incident | Needs an immediate traffic/error summary without deploying infrastructure | One command reads a file or stdin and prints the four required metrics |
| Platform engineer | DevOps engineer maintaining automation | Needs stable machine-readable output and meaningful failure signals | `--json`, `--csv`, and exit codes `0/1/2/3/4` provide a pipeline contract |
| Service owner | Engineer reviewing a large production log locally | Existing shell pipelines are fragile and full observability stacks are excessive | Streaming aggregation targets a 1 GB log in under 30 seconds on a laptop |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Our difference |
|---|---|---|---|
| GoAccess | Fast, mature, rich interactive and HTML reports | Broader configuration and output surface than a four-metric pipeline tool | Narrow, deterministic report schema with first-class JSON/CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, storage, search, and dashboards | Requires multiple services, storage, configuration, and operations | Zero-service local analysis with no database or network dependency |
| AWStats | Mature historical web analytics | Report-generation workflow and persistent history do not fit quick stream analysis | Ephemeral incident-focused analysis from file or stdin |
| `grep`/`awk`/`sort` pipelines | Already available and composable | Parsing, quoting, status filtering, ties, malformed lines, and portability are easy to get wrong | Tested nginx parsing and one stable cross-platform CLI contract |

## 4. Unique Value Proposition

Get the four nginx incident metrics an SRE needs from a gigabyte-scale log in one local command, with readable terminal output and pipeline-safe JSON/CSV, without deploying or operating anything.

## 5. Business Model

The tool is open source and free. There is no monetization in the MVP, no telemetry, and no hosted tier. Value is measured in reduced incident-analysis time and reliable automation rather than revenue. With a $0 cash budget, development uses existing contributor hardware and free/open-source tooling; maintenance is community-driven.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, and suitable for a pip-installed CLI |
| CLI | Click | Stable option parsing, stdin/file handling, help, and exit behavior |
| Terminal rendering | Rich | Accessible colored tables with automatic no-color behavior for redirected output |
| Domain models | Standard-library dataclasses | Explicit report records without a validation-framework dependency |
| Streaming/parsing | Python standard library | Line-by-line I/O, regex/datetime parsing, counters, JSON, and CSV are sufficient |
| Packaging | `pyproject.toml` + pip | Standard install and console-script entry point |
| Quality | pytest, Ruff, mypy | Free local checks for behavior, style, and type contracts |

## 7. Delivery Timeline

| Weekend block | Work | Outcome |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable CLI reads file/stdin and distinguishes valid from malformed lines |
| Saturday afternoon | Streaming aggregations | All four metrics computed with bounded-memory protections |
| Sunday morning | Rich, JSON, and CSV renderers | Stable human and machine output contracts |
| Sunday afternoon | Tests, benchmark, packaging docs | Quality gates pass and the 1 GB performance target is measured |

## 8. KPIs

| Metric | Release target | First month | Third month |
|---|---:|---:|---:|
| Processing time for representative 1 GB log on reference laptop | <30 s | <30 s at p95 of benchmark runs | No regression beyond 10% |
| Peak resident memory on bounded-cardinality benchmark | <256 MiB | <256 MiB | <256 MiB |
| Correctness fixtures passing | 100% | 100% on every release | 100% on every release |
| Installation-to-first-report time | <2 min | <2 min | <90 s |
| Unhandled tracebacks for documented user errors | 0 | 0 reported | 0 reported |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from combined format | Medium | High | Define combined format as the MVP contract, count malformed lines, and return exit code `3` when no valid record exists |
| Exact unique User-Agent tracking exhausts memory on adversarial/high-cardinality input | Medium | High | Enforce a documented unique-cardinality limit and stop with exit code `4`; never silently approximate |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early; use compiled regex, one-pass aggregation, minimal allocations, and profile before optimizing |
| JSON/CSV shapes drift across releases | Low | High | Golden-output tests and explicit schema/version policy |
| Colored terminal output harms automation or accessibility | Low | Medium | Disable color when not a TTY and support `NO_COLOR`; machine modes never emit ANSI codes |
| Top-10 tie ordering becomes nondeterministic | Medium | Medium | Specify count-descending, key-ascending ordering and test ties |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Python, Click, Rich, pytest, Ruff, mypy | $0 | Open-source dependencies |
| Hosting, database, cloud, Kubernetes | $0 | Explicitly out of scope |
| Developer infrastructure | $0 incremental | Existing laptop and public package tooling |
| Delivery labor | One weekend | Time-boxed scope; no cash allocation |
| Total cash budget | **$0** | Release must not depend on paid services |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream combined-format logs from a file or stdin | **Must** | Foundation for local and pipeline use |
| Top 10 client IPs | **Must** | Core incident metric |
| Top 10 URLs by combined 4xx/5xx count | **Must** | Core error-triage metric |
| Hourly request distribution | **Must** | Core traffic-shape metric; each percentage is `100 × hourly_request_count / total_valid_requests` |
| Unique User-Agent share | **Must** | Core diversity metric, defined as unique valid User-Agents divided by valid requests, expressed as a percentage |
| Rich colored terminal report | **Must** | Required default experience |
| JSON and CSV modes | **Must** | Required pipeline integration |
| Deterministic exit codes and malformed-line accounting | **Must** | Required for dependable automation |
| Gzip input auto-detection | **Should** | Common operational convenience but decompression may be done upstream |
| Configurable top-N | **Could** | Helpful generalization that is not needed for the fixed top-10 MVP |
| Additional nginx log formats | **Could** | Broadens use after the combined-format contract is stable |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the approved local stateless CLI scope |

### RICE Scoring (Must and Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence as a decimal. Rows are ordered by descending score; closely coupled reporting work can share an implementation step.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Top 10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top 10 error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Malformed-line and exit-code contract | 9 | 5 | 90% | 0.40 | 101.3 |
| Unique User-Agent share + limit | 8 | 4 | 85% | 0.35 | 77.7 |
| JSON and CSV output | 9 | 4 | 90% | 0.50 | 64.8 |
| Stream file/stdin + parsing | 10 | 5 | 90% | 0.75 | 60.0 |
| Rich terminal output | 8 | 3 | 90% | 0.50 | 43.2 |
| Gzip input | 6 | 2 | 75% | 0.40 | 22.5 |

Dependency order takes precedence where a high-scoring metric needs the parser first. `IMPLEMENTATION_PLAN.md` sequences a thin parsing foundation, the high-value metrics, then output modes and hardening.

## 12. Definition of Done

A feature is done when:

- [ ] Its behavior and acceptance criteria in `PRD.md` are implemented without expanding the locked scope.
- [ ] Python 3.11 code installs through pip and the console entry point runs.
- [ ] Unit and integration tests pass with at least 90% line coverage for product modules.
- [ ] The complete quality suite (Ruff, mypy, pytest) passes.
- [ ] Default, JSON, and CSV output contracts remain deterministic and documented.
- [ ] No known critical or high-severity security issues remain.
- [ ] The 1 GB representative benchmark completes in under 30 seconds on the documented reference laptop.
- [ ] Documentation is current and a clean virtual-environment install is manually verified.

## 13. Kill Criteria

Stop or rescope the MVP if profiling shows that the approved Python 3.11 single-process design cannot process a representative 1 GB log within 30 seconds after targeted optimization, or if exact unique-cardinality handling cannot be bounded with a clear exit-code `4` failure contract. Do not add services, persistence, or paid infrastructure to hide either failure.
