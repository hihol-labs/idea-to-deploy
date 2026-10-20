# Strategic Plan: nginx-log-top

## 1. Product Idea

`nginx-log-top` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. The default report is colored terminal text, with deterministic JSON and CSV modes for pipelines.

The MVP is deliberately local and stateless: it has no authentication, database, HTTP API, server process, cloud dependency, or Kubernetes deployment. The delivery target is one weekend with a $0 cash budget.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call engineer | SRE / platform engineer | Needs a quick incident summary without shipping sensitive logs elsewhere | One local command produces an actionable overview |
| Service owner | Backend / DevOps engineer | Needs to identify noisy clients and failing routes | Ranked IP and error-URL tables focus investigation |
| Automation author | CI / shell pipeline maintainer | Needs stable machine-readable data | `--json` and `--csv` avoid screen scraping |

## 3. Problem and Outcome

During incidents, a full observability stack may be unavailable, too slow to configure, or disproportionate for a single log file. Ad hoc `grep`, `awk`, and `sort` commands are quick but difficult to reproduce and easy to get subtly wrong. The desired outcome is a trustworthy first-pass report produced locally from a 1 GB log in under 30 seconds on a representative laptop.

## 4. Competitive Analysis

| Alternative | Strength | Limitation for this use case | Product distinction |
|---|---|---|---|
| GoAccess | Mature, fast, rich interactive reports | Broader UI and configuration surface than the four requested metrics | Smaller fixed contract and pipeline-oriented JSON/CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards, and retention | Operationally heavy; requires services, storage, and setup | Zero-service local analysis with no retained data |
| AWStats | Established historical web analytics | Oriented to generated historical reports rather than incident-time CLI pipelines | Immediate streaming output and modern machine formats |
| `grep` / `awk` / `sort` | Installed almost everywhere and composable | Fragile parsing, repeated recipes, sorting may consume substantial resources | Tested parser, explicit exit codes, and one reproducible command |

## 5. Unique Value Proposition

Get a repeatable incident-oriented nginx log summary from a local file or stdin in one command, without deploying or operating an analytics stack.

## 6. Business and Distribution Model

The project is open source and free to use. Distribution is a pip-installable package, with `pipx` recommended for isolated CLI installation. Success is adoption and reliability rather than revenue; there are no paid tiers, telemetry, or hosted services in the MVP.

## 7. Technology Strategy

| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Required platform; broad availability and fast delivery |
| CLI | Click | Clear option validation, help generation, and test utilities |
| Terminal UI | Rich | Portable color, tables, and automatic no-color behavior |
| Domain models | `dataclasses` | Lightweight typed records without validation-framework overhead |
| Packaging | `pyproject.toml` + pip | Standard installable CLI distribution |
| Tests | pytest + Click `CliRunner` | Fast unit and end-to-end CLI verification |

## 8. Timeline

| Window | Focus | Deliverable |
|---|---|---|
| Saturday morning | Package skeleton, parser, aggregation | Valid lines stream into bounded summaries |
| Saturday afternoon | Text, JSON, CSV rendering and CLI contract | End-to-end commands work on fixtures and stdin |
| Sunday morning | Correctness, malformed-input behavior, cardinality guard | Automated unit and CLI suite |
| Sunday afternoon | Benchmarking, packaging, documentation | Installable release candidate meeting the performance target |

## 9. KPIs

| Metric | Release target | One-month signal | Measurement |
|---|---:|---:|---|
| 1 GB processing time | `< 30 s` | Maintained across releases | Repeatable local benchmark with recorded laptop details |
| Peak resident memory | `< 512 MiB` on benchmark fixture | No regression above 10% | `/usr/bin/time -v` around benchmark command |
| Valid-line metric accuracy | 100% on golden fixtures | No known correctness defects | Golden-output tests for all formats |
| Malformed-line handling | Count and continue by default | No silent parse-loss reports | Mixed valid/invalid fixture tests |
| Installation-to-first-report | `< 30 s` excluding package download | Users can follow Quick Start unassisted | Fresh virtual-environment smoke test |

## 10. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from Combined Log Format | High | High | State supported format explicitly, report malformed count, design parser behind an interface |
| Exact unique User-Agent tracking exhausts memory on adversarial input | Medium | High | Enforce a configurable cardinality ceiling and exit with code 4 |
| Pure Python misses the 1 GB / 30 s target | Medium | High | Benchmark early, avoid per-line regex recompilation and retained records, profile before adding features |
| CSV cannot naturally encode several tables | Medium | Medium | Specify a normalized `section,key,value,rank` schema |
| Terminal color corrupts redirected output | Low | Medium | Disable color when output is not a TTY and support `--no-color` |
| Incorrect timezone assumptions distort hourly buckets | Medium | Medium | Use the numeric offset in each nginx timestamp and document bucket semantics |

## 11. Budget

The cash budget is fixed at $0. Development time is the only planned investment; all runtime and development dependencies must use open-source licenses compatible with distribution.

| Item | One-time cash | Monthly cash | Assumption |
|---|---:|---:|---|
| Python, Click, Rich, pytest toolchain | $0 | $0 | Open-source local tooling |
| Development and benchmark machine | $0 | $0 | Existing laptop |
| Package hosting | $0 | $0 | Public PyPI and source forge free tiers |
| Database, server, cloud, Kubernetes | $0 | $0 | Explicitly not used |
| **Total** | **$0** | **$0** | One-weekend labor is not assigned a cash cost |

## 12. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Streaming parser for nginx Combined Log Format from file or stdin | **Must** | All metrics depend on trusted bounded-memory ingestion |
| Top 10 client IPs | **Must** | Core incident triage question |
| Top 10 4xx/5xx URLs | **Must** | Core failure localization question |
| Hourly request percentages | **Must** | Required traffic-shape metric |
| Exact unique User-Agent share with cardinality guard | **Must** | Required audience-diversity metric with safe failure behavior |
| Rich terminal report | **Must** | Required default user experience |
| JSON and CSV output | **Must** | Required pipeline compatibility |
| Gzip-compressed input | **Should** | Common log rotation format, but decompression can be piped for MVP |
| Configurable top-N | **Could** | Useful flexibility after the fixed top-10 contract is stable |
| Additional nginx `log_format` definitions | **Could** | Broadens compatibility after the default parser is proven |
| Persistent history and dashboards | **Won't** | Conflicts with the local stateless product boundary |
| Authentication, HTTP API, cloud, or Kubernetes | **Won't** | Adds no value to a single-process local CLI |

### RICE Scoring (Must and Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence expressed as a decimal.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser from file/stdin | 10 | 5 | 90% | 0.75 | 60.0 |
| Top 10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top 10 error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly request percentages | 8 | 3 | 95% | 0.25 | 91.2 |
| Rich terminal report | 9 | 4 | 90% | 0.50 | 64.8 |
| JSON and CSV output | 8 | 4 | 90% | 0.60 | 48.0 |
| Unique User-Agent share and guard | 8 | 4 | 80% | 0.60 | 42.7 |
| Gzip-compressed input | 5 | 2 | 80% | 0.35 | 22.9 |

Dependencies override a raw score where necessary: the parser precedes every metric, and a shared result model precedes all renderers.

## 13. Definition of Done

A release feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Python 3.11 code passes formatting, linting, and type checks selected by the project.
- [ ] Unit and CLI tests pass with at least 90% statement coverage for `src/nginx_log_top`.
- [ ] Golden reports cover text, JSON, and CSV behavior where applicable.
- [ ] The 1 GB benchmark and peak-memory measurement are recorded for performance-sensitive changes.
- [ ] Documentation and `CLAUDE.md` implementation status are updated.
- [ ] No known Critical or High security issue remains.
- [ ] A fresh-environment pip installation and local smoke test pass.

## 14. Kill and Reassessment Criteria

Reassess the implementation approach if the representative 1 GB benchmark remains above 30 seconds after profiling and two focused optimization passes, if exact User-Agent tracking cannot stay under the memory ceiling for the documented cardinality limit, or if common Combined Log Format fixtures cannot be parsed with at least 99.9% valid-line success. Preserve the CLI contract while considering a faster parser implementation only after evidence triggers one of these criteria.
