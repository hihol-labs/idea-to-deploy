# Strategic Plan: Nginx Stream Insights

## 1. Product Idea

Nginx Stream Insights is a local, pip-installable Python 3.11 CLI for DevOps
and SRE engineers. It reads nginx access logs as a stream and produces four
operational summaries without uploading data or provisioning services:

- top 10 client IP addresses by valid request count;
- top 10 request URLs whose responses are 4xx or 5xx;
- hourly request distribution as a percentage, calculated exactly as
  `100 × hourly_request_count / total_valid_requests`;
- the share of unique User-Agents among valid requests.

Colored terminal output is the default. Stable `--json` and `--csv` modes make
the same report usable in pipelines. The product is open source, costs $0 to
operate, and is scoped for one weekend of implementation.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Investigates incidents from a shell | Needs a fast traffic/error picture without building a dashboard | Streams a local or piped log into an immediate report |
| Platform engineer | Owns nginx fleets and automation | Ad hoc shell pipelines are hard to repeat safely | Uses stable JSON/CSV fields and documented exit codes |
| DevOps engineer | Supports small services | GoAccess or Elastic may be more machinery than the question warrants | Installs one local CLI with no server, database, or cloud dependency |

## 3. Competitive Analysis

| Alternative | Strength | Limitation for this use case | Nginx Stream Insights difference |
|---|---|---|---|
| GoAccess | Mature interactive and HTML nginx analytics | Broader UI/reporting surface than a four-metric pipeline tool | Narrow, deterministic summaries with simple JSON/CSV contracts |
| Logstash + Elasticsearch + Kibana | Powerful centralized ingestion, search, and dashboards | Infrastructure, storage, administration, and cost are disproportionate for a local one-off analysis | Stateless local execution with no services |
| AWStats | Established historical web-log reporting | Batch-oriented generated reports and legacy operational model | Stream-first CLI suited to terminals and Unix pipelines |
| `grep`/`awk`/`sort` | Already installed and flexible | Combined-log quoting, URL parsing, malformed records, and portability make reusable scripts fragile | Tested parser and one stable cross-format contract |

## 4. Unique Value Proposition

Get the four nginx incident summaries most often needed from a local stream in
one command, with no data upload, persistent service, or hand-built shell
pipeline.

## 5. Business Model

The MVP is an open-source utility with no paid tier. Distribution through a
public Python package index keeps acquisition and operating cost at $0. Success
is measured by usefulness and reliability, not revenue. Optional future
sponsorship or organizational support is explicitly outside the weekend MVP.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required, widely available to target users |
| CLI | Click | Predictable option parsing, help text, and test runner |
| Terminal presentation | Rich | Colored tables and correct TTY/color handling |
| Domain models | `dataclasses` | Lightweight typed records without a persistence framework |
| Parsing/aggregation | Python standard library | Streaming I/O, regex/date parsing, counters, CSV/JSON serialization |
| Packaging | `pyproject.toml` + pip | Required install path with a console entry point |
| Testing | pytest + Click `CliRunner` | Unit and end-to-end CLI verification |

## 7. Timeline

| Timebox | Stage | Outcome |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable CLI reads combined-format records |
| Saturday afternoon | Aggregation and cardinality guard | Four metrics computed in one pass |
| Sunday morning | terminal, JSON, and CSV renderers | Deterministic output contracts implemented |
| Sunday afternoon | fixtures, performance run, docs, packaging | Release candidate meets functional and 1 GB target evidence |

## 8. KPIs

| Metric | MVP/one weekend | 1 month | 3 months |
|---|---:|---:|---:|
| Correctness fixtures passing | 100% | 100% | 100% |
| 1 GB processing time on reference laptop | <30 s | <30 s | <25 s |
| Peak memory excluding exact unique-UA set | Bounded by distinct IP/URL keys | Same | Same |
| Supported machine formats | JSON + CSV | Stable | Backward compatible |
| Open critical defects | 0 | 0 | 0 |

The performance KPI is accepted only with a recorded laptop specification,
input fixture description, wall-clock time, and peak resident memory.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined format | Medium | High | Make the supported grammar explicit; reject malformed lines without corrupting totals; defer custom formats |
| Exact User-Agent cardinality consumes too much memory | Medium | High | Enforce `--max-unique-user-agents`; terminate with exit code 4 rather than silently approximate |
| Python misses the 1 GB/30 s target | Medium | High | One-pass parsing, avoid per-line object retention, benchmark early, profile hot paths |
| CSV/JSON semantics drift from terminal output | Low | High | Build one report model and contract-test all renderers from it |
| Error URL cardinality grows on hostile inputs | Medium | Medium | Document memory behavior, benchmark high-cardinality fixtures, and consider a later bounded heavy-hitter algorithm |
| Locale/time-zone ambiguity changes hourly buckets | Low | Medium | Use the numeric UTC offset embedded in each nginx timestamp and label buckets `00`–`23` |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python and approved dependencies are open source |
| Hosting/database/cloud | $0 | None exist in the architecture |
| Distribution | $0 | pip-installable package; publishing can use free public infrastructure |
| Delivery labor budget | $0 cash | One weekend of contributor time |
| Total operating budget | $0/month | The CLI runs on the user's laptop |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream combined-format input from a file or stdin | **Must** | No analysis is possible without it |
| Top 10 client IPs | **Must** | Core traffic summary |
| Top 10 URLs by 4xx/5xx response count | **Must** | Core failure summary |
| Hourly percentage distribution | **Must** | Core traffic-shape summary |
| Exact unique User-Agent share with exhaustion guard | **Must** | Core audience-diversity summary with honest failure semantics |
| Colored terminal report | **Must** | Required default experience |
| JSON and CSV reports | **Must** | Required pipeline interoperability |
| Follow a growing file with `--follow` | **Should** | Useful for live operations but analysis of a finite stream ships first |
| Gzip input | **Could** | Convenient, but shell decompression can cover the MVP |
| Custom nginx `log_format` grammars | **Could** | Broadens adoption after the combined-format contract is stable |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the local stateless CLI goal |

### RICE Scoring (Must and Should)

`RICE = Reach × Impact × Confidence / Effort`. Confidence is represented as a
decimal in the calculation; scores are planning estimates, not measured usage.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin parsing | 10 | 5 | 90% | 0.50 | 90.0 |
| Top IP aggregation | 9 | 4 | 90% | 0.25 | 129.6 |
| Error URL aggregation | 10 | 5 | 90% | 0.35 | 128.6 |
| Hourly percentage distribution | 8 | 4 | 90% | 0.25 | 115.2 |
| Colored terminal report | 9 | 3 | 90% | 0.35 | 69.4 |
| JSON and CSV reports | 8 | 4 | 90% | 0.50 | 57.6 |
| Unique User-Agent share and guard | 7 | 4 | 80% | 0.50 | 44.8 |
| Follow mode | 5 | 3 | 70% | 0.50 | 21.0 |

Dependencies take precedence over the raw score: stream parsing is built
before every aggregation, then shared report modeling before renderers.

## 12. Definition of Done

A feature is done when:

- [ ] Its behavior and edge cases match `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 code passes formatting, linting, and type checks selected by the project.
- [ ] Unit tests pass and total coverage is at least 90%.
- [ ] CLI integration and golden-output tests pass where applicable.
- [ ] No known critical or high-severity security issue remains.
- [ ] README and implementation guidance are updated.
- [ ] The 1 GB benchmark evidence is recorded before the performance claim is accepted.
- [ ] Installation into a clean virtual environment and all `0/1/2/3/4` exit paths are manually verified.

## 13. MVP Success and Kill Criteria

Ship when all P0 acceptance criteria pass, the package installs on Python 3.11,
and the reference 1 GB combined-format log completes in under 30 seconds.
Re-scope or stop if a one-pass Python implementation cannot meet the target
after profiling, exact unique-UA tracking cannot fail safely at a documented
limit, or stable pipeline output cannot be delivered within the weekend.

