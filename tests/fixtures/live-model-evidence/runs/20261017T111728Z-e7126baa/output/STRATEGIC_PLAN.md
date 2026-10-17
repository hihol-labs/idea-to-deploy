# Strategic Plan: nginx-insights

## 1. Product Idea

`nginx-insights` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs incrementally from a file or standard input and produces four immediately useful operational views: the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, the percentage distribution of valid requests by hour, and the share of unique User-Agent values. Rich colored text is the default; stable JSON and CSV modes support pipelines.

The MVP is intentionally narrow: one process, no persistent state, no network service, and no infrastructure to operate. It is designed for incident triage and quick local analysis of files up to 1 GB.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call engineer | SRE/DevOps | Needs a useful traffic/error summary before deciding which system to inspect next | Produces four operational summaries with one command and no service setup |
| Platform engineer | Infrastructure owner | Needs reproducible log analysis in scripts and CI jobs | Provides versioned JSON/CSV schemas, deterministic ordering, stdin, and explicit exit codes |
| Developer/operator | Service owner | Has an nginx log but no observability stack available locally | Installs with pip and runs offline with zero external dependencies at runtime beyond Python packages |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | nginx-insights differentiation |
|---|---|---|---|
| GoAccess | Fast, mature, interactive reports | Broader configuration surface and UI than a small pipeline-oriented summary needs | Four opinionated SRE metrics, stable machine output, Python-installable |
| Logstash + Elastic + Kibana | Powerful ingestion, search, dashboards, retention | Requires several services, storage, setup, and operating cost | No service, database, account, or persistent state |
| AWStats | Established historical reports | Batch/reporting orientation and generated pages are heavier than terminal triage | Immediate terminal and stdout-safe structured output |
| `grep`/`awk` pipelines | Available nearly everywhere and highly composable | Correct parsing, quoting, denominators, sorting, and repeatability become bespoke | One tested parser and explicit metric semantics |

## 4. Unique Value Proposition

Turn a local nginx access-log stream into four reliable incident-triage summaries in one command, without deploying or operating an analytics stack.

## 5. Business Model

The project is open source and free. There is no paid tier, telemetry, hosted component, CAC, or subscription unit economics in the MVP. Value is measured in operator time saved and repeatable analysis rather than revenue. Contributions and package hosting use free community infrastructure.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved, widely available, productive for a one-weekend build |
| CLI | Click | Predictable option validation, stdin/file handling, and exit behavior |
| Terminal UI | Rich | Readable tables and automatic color control |
| Domain models | `dataclasses` | Explicit typed records without a validation framework |
| Aggregation | Python iterators, `collections.Counter` | Single-pass processing with no database |
| Packaging | `pyproject.toml`, pip | Standard install and console-script entry point |
| Quality | pytest, Ruff, mypy | Fast local checks suitable for a small typed CLI |

## 7. Timeline

| Period | Work | Deliverable |
|---|---|---|
| Saturday morning | Package skeleton, parser, fixtures | Installable CLI and verified combined-log parser |
| Saturday afternoon | Streaming aggregators and limits | Correct metrics, malformed-line policy, cardinality guard |
| Sunday morning | Rich, JSON, and CSV renderers | Human and pipeline output contracts implemented |
| Sunday afternoon | End-to-end, performance, docs, polish | Tested release candidate and 1 GB benchmark evidence |

## 8. KPIs

| Metric | Release target | First month | Three months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | <30 s | <30 s p95 | <30 s p95 |
| Peak RSS on 1 GB representative log | <512 MiB | <512 MiB | <512 MiB |
| Valid combined-log parsing accuracy on test corpus | 100% | 100% | 100% |
| P0 acceptance tests passing | 100% | 100% | 100% |
| Time from install to first report | <2 min | <2 min | <2 min |

The reference laptop, generated benchmark corpus, Python version, command, elapsed time, and peak RSS must be recorded together; the speed KPI is not claimed from intuition.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the combined format | High | High | Explicitly support combined/common MVP grammar, count rejected lines, document custom formats as out of scope |
| High-cardinality inputs exhaust memory | Medium | High | Configurable distinct-key ceiling and explicit exit code 4; never silently approximate |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early, profile parser hot paths, avoid per-line regex recompilation and retained records |
| CSV cannot naturally represent four differently shaped reports | Medium | Medium | Define one normalized row schema with a `section` discriminator |
| Colored output contaminates pipelines | Low | Medium | Color only in terminal mode; JSON/CSV contain no ANSI escapes and use stdout exclusively for data |
| Malformed lines produce misleading denominators | Medium | High | Base all metrics on `total_valid_requests`, expose valid/rejected counts, offer strict mode |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Open-source dependencies |
| Hosting/infrastructure | $0 | Local CLI; no deployed service |
| Database/cloud | $0 | Neither exists in the architecture |
| Package publishing | $0 | Public PyPI and source hosting have free paths |
| Labor | One weekend | Fixed delivery constraint; no cash budget allocated |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream file/stdin and parse nginx common/combined lines | Must | All reports depend on bounded, correct ingestion |
| Top 10 client IPs | Must | Core incident-triage requirement |
| Top 10 error URLs for 4xx/5xx | Must | Core error-localization requirement |
| Hourly request percentage distribution | Must | Core traffic-shape requirement |
| Unique User-Agent share | Must | Core client-diversity requirement |
| Rich terminal, JSON, and CSV output | Must | Required interactive and pipeline interfaces |
| Explicit diagnostics and exit codes 0/1/2/3/4 | Must | Required automation contract and safe cardinality failure |
| Follow a growing file | Should | Useful for live operations but not required for bounded-file MVP |
| Gzip input | Could | Convenient but can follow after measured MVP performance |
| Custom nginx `log_format` grammar | Could | Broadens adoption but exceeds one-weekend parser scope |
| Database, HTTP API, auth, server, cloud, Kubernetes | Won't | Contradicts the local stateless CLI value proposition |

### RICE Scoring (Must and Should)

Confidence is expressed as a decimal in the formula `(Reach × Impact × Confidence) / Effort`.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE |
|---|---:|---:|---:|---:|---:|
| Streaming parser + input | 10 | 5 | 0.90 | 0.7 | 64.3 |
| Top IPs | 9 | 4 | 0.95 | 0.2 | 171.0 |
| Error URLs | 9 | 5 | 0.95 | 0.25 | 171.0 |
| Hourly distribution | 8 | 4 | 0.95 | 0.2 | 152.0 |
| Unique User-Agent share + guard | 7 | 4 | 0.80 | 0.35 | 64.0 |
| Rich/JSON/CSV renderers | 10 | 4 | 0.90 | 0.7 | 51.4 |
| Diagnostics and exit contract | 8 | 4 | 0.95 | 0.3 | 101.3 |
| Follow mode | 4 | 3 | 0.60 | 0.5 | 14.4 |

Dependency order overrides raw RICE where necessary: parsing precedes every metric, and metrics precede renderers.

## 12. Definition of Done

A feature is done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Typed implementation is present and Ruff and mypy pass.
- [ ] Unit tests pass; project coverage is at least 90% and parsing/aggregation branches are covered.
- [ ] End-to-end tests pass for terminal, JSON, CSV, stdin, malformed input, and exit codes 0/1/2/3/4.
- [ ] Documentation and `--help` are consistent with the actual interface.
- [ ] No known critical/high security issue remains.
- [ ] The exact release candidate processes the reference 1 GB corpus in under 30 seconds on the recorded reference laptop.
- [ ] Installation and a manual smoke run succeed in a clean Python 3.11 virtual environment.

## 13. Kill Criteria

Stop or redesign the MVP if a profiled and optimized single-process prototype cannot process the representative 1 GB corpus in under 30 seconds, if exact aggregation cannot stay within the documented cardinality limit on representative logs, or if common/combined parsing cannot be made deterministic without expanding into a general `log_format` engine. Do not hide failure by sampling or silently approximating.

